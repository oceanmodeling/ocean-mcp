"""Read archived inputs for the reference code (standard library only; no Ocean-MCP import).

The archives use the replay launcher's on-disk format (``index.json`` + ``bodies/``), which is
plain JSON: each entry has ``url``, ``kind``, ``key`` (method, host, path, params) and
``response.body_file`` / ``response.body_sha256``. Bodies are verified against their SHA-256
on every read.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

UTC = dt.timezone.utc


class ArchiveError(RuntimeError):
    pass


class Archive:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.doc = json.loads((self.root / "index.json").read_text())
        self.entries = self.doc["entries"]

    def body(self, entry: dict) -> bytes:
        p = self.root / entry["response"]["body_file"]
        data = p.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["response"]["body_sha256"]:
            raise ArchiveError(f"sha256 mismatch for {p}")
        return data

    def path(self, entry: dict) -> Path:
        return self.root / entry["response"]["body_file"]


def params(entry: dict) -> dict:
    return dict(parse_qsl(urlsplit(entry["url"]).query, keep_blank_values=True))


def coops_time(s: str, end: bool) -> dt.datetime:
    s = s.strip()
    for fmt in ("%Y%m%d %H:%M", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(s, fmt).replace(tzinfo=UTC)
        except ValueError:
            pass
    d = dt.datetime.strptime(s, "%Y%m%d").replace(tzinfo=UTC)
    return d.replace(hour=23, minute=59) if end else d


_S3_3D = re.compile(r"stofs_3d_atl\.(\d{8})/stofs_3d_atl\.t(\d{2})z\.points\.(cwl(?:\.noanomaly)?)\.nc$")
_S3_2D = re.compile(r"stofs_2d_glo\.(\d{8})/stofs_2d_glo\.t(\d{2})z\.points\.(cwl(?:\.noanomaly)?)\.nc$")


def model_files(arcs: list[Archive]) -> list[dict]:
    """Station NetCDF entries: product, cycle (UTC datetime), variant, archive, entry."""
    out = []
    for a in arcs:
        for e in a.entries:
            path = urlsplit(e["url"]).path
            for prod, rx in (("3d", _S3_3D), ("2d", _S3_2D)):
                m = rx.search(path)
                if m and e["response"]["status"] == 200:
                    d, hh, var = m.groups()
                    cyc = dt.datetime.strptime(d + hh, "%Y%m%d%H").replace(tzinfo=UTC)
                    out.append({"product": prod, "cycle": cyc, "variant": var, "archive": a, "entry": e})
    return out


NODATA_SHA256 = "500bdf8b7540e3b178fa94711e95e7bd7633578dac4778da5faed9dc45cbfb0f"  # Phase 0 probe
UNSUPPORTED_PREFIX = "The supported Datum values are"


class CoopsObs:
    """CO-OPS water_level masters indexed by station and datum.

    Three kinds of archived answer are accepted (DESIGN.md 3.2, 5.2):
    * data masters (a ``data`` list): their records in [lo, hi];
    * the generic no-data document (HTTP 200, sha256 NODATA_SHA256) for the master's own range;
    * the unsupported-datum document (HTTP 400, message "The supported Datum values are ..."),
      which CO-OPS returns for any range (Phase 0) and therefore covers every range.
    Any other error document is an acquisition gap, never an observation fact: ``records``
    raises on it.
    """

    def __init__(self, arcs: list[Archive]):
        self.masters: dict[tuple[str, str], list[dict]] = {}
        for a in arcs:
            for e in a.entries:
                if e.get("kind") not in ("coops_master", "coops_error_master"):
                    continue
                p = params(e)
                if p.get("product") != "water_level":
                    continue
                key = (p["station"], p["datum"])
                self.masters.setdefault(key, []).append({
                    "lo": coops_time(p["begin_date"], end=False),
                    "hi": coops_time(p["end_date"], end=True),
                    "retrieved_at": e.get("provenance", {}).get("retrieved_at", ""),
                    "archive": a, "entry": e, "doc": None,
                })
        for v in self.masters.values():
            v.sort(key=lambda m: (m["lo"], m["retrieved_at"]))

    def _doc(self, m: dict) -> dict:
        if m["doc"] is None:
            m["doc"] = json.loads(m["archive"].body(m["entry"]))
        return m["doc"]

    def _answer(self, m: dict) -> str:
        doc = self._doc(m)
        if "data" in doc and "error" not in doc:
            return "data"
        msg = str((doc.get("error") or {}).get("message", "")).strip()
        if m["entry"]["response"]["status"] == 400 and msg.startswith(UNSUPPORTED_PREFIX):
            return "unsupported_datum"
        if m["entry"]["response"]["body_sha256"] == NODATA_SHA256:
            return "no_data"
        raise ArchiveError(f"master {m['entry']['id']} holds an error that is not an observation fact "
                           f"(status {m['entry']['response']['status']}: {msg!r}); refetch it")

    def records(self, station: str, datum: str, lo: dt.datetime, hi: dt.datetime) -> dict:
        """Records with lo <= t <= hi from all masters that overlap (first master wins on a
        duplicate time). ``served``: data / no_data / unsupported_datum / missing_master."""
        allm = self.masters.get((station, datum), [])
        for m in allm:
            if self._answer(m) == "unsupported_datum":
                return {"records": [], "masters": [m["entry"]["id"]], "served": "unsupported_datum",
                        "fully_covered": True}
        ms = [m for m in allm if m["lo"] <= hi and m["hi"] >= lo]
        # coverage: the union of the overlapping masters' ranges must contain [lo, hi]
        cur, covered = lo, False
        for m in sorted(ms, key=lambda m: m["lo"]):
            if m["lo"] <= cur:
                cur = max(cur, m["hi"] + dt.timedelta(minutes=1))
            if cur > hi:
                covered = True
                break
        seen, recs, used, kinds = set(), [], [], set()
        for m in ms:
            used.append(m["entry"]["id"])
            k = self._answer(m)
            kinds.add(k)
            if k != "data":
                continue
            for r in self._doc(m).get("data", []):
                t = dt.datetime.strptime(r["t"], "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
                if lo <= t <= hi and t not in seen:
                    seen.add(t)
                    recs.append((t, r))
        recs.sort(key=lambda x: x[0])
        served = "missing_master" if not covered else ("data" if recs else "no_data")
        return {"records": recs, "masters": used, "served": served, "fully_covered": covered}


def exact_body(arcs: list[Archive], url_pred) -> tuple[Archive, dict] | None:
    for a in arcs:
        for e in a.entries:
            if url_pred(e["url"]):
                return a, e
    return None
