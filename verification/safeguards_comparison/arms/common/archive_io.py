"""Read archived upstream bytes for arms A and B (standard library only).

This module holds no domain rules. It gives the Python arms exactly the bytes
the MCP sessions receive: the same archive stack (an overlay first, then the
base archive), the same entry for a URL, and, for CO-OPS water levels, the same
master response the replay would slice (the earliest-retrieved archived
response for that station, datum and units whose requested range covers the
window). Selecting records inside the window is left to each arm.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


class Stack:
    def __init__(self, vdir: Path, archives: list[str]):
        self.vdir = Path(vdir)
        self.archives = []
        for name in archives:
            root = self.vdir / "data/archive" / name
            self.archives.append((name, root, json.loads((root / "index.json").read_text())))
        self.used: list[dict] = []

    def _record(self, name, e, why):
        self.used.append({"archive": name, "entry": e["id"], "url": e["url"],
                          "sha256": e["response"]["body_sha256"], "why": why})

    def path_for_url(self, url: str) -> Path:
        want = _key(url)
        for name, root, doc in self.archives:
            for e in doc["entries"]:
                if _key(e["url"]) == want:
                    self._record(name, e, "url")
                    return root / e["response"]["body_file"]
        raise LookupError(f"not archived: {url}")

    def path_for_input(self, input_name: str) -> Path:
        for name, root, doc in self.archives:
            for e in doc["entries"]:
                if e["provenance"].get("input_name") == input_name:
                    self._record(name, e, "input_name")
                    return root / e["response"]["body_file"]
        raise LookupError(input_name)

    def request_params(self, input_name: str) -> dict:
        for _, _, doc in self.archives:
            for e in doc["entries"]:
                if e["provenance"].get("input_name") == input_name:
                    return dict(parse_qsl(urlsplit(e["url"]).query))
        raise LookupError(input_name)

    def coops_master(self, station: str, datum: str, begin: datetime, end: datetime) -> tuple[Path, dict]:
        """Path of the CO-OPS water_level master covering [begin, end], and its request parameters."""
        for name, root, doc in self.archives:
            cands = []
            for e in doc["entries"]:
                if e.get("kind") != "coops_master":
                    continue
                q = dict(parse_qsl(urlsplit(e["url"]).query))
                if q.get("station") != station or q.get("datum") != datum or q.get("units") != "metric":
                    continue
                if _t(q["begin_date"], False) <= begin and end <= _t(q["end_date"], True):
                    cands.append((e["provenance"].get("retrieved_at", ""), e["id"], e, q))
            if cands:
                cands.sort(key=lambda c: (c[0], c[1]))
                e, q = cands[0][2], cands[0][3]
                self._record(name, e, f"coops master {station} {datum}")
                return root / e["response"]["body_file"], q
        raise LookupError(f"no CO-OPS master for {station} {datum} {begin}..{end}")


def _key(url):
    p = urlsplit(url)
    return (p.scheme, p.netloc.lower(), p.path,
            tuple(sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k != "application")))


def _t(s, end):
    try:
        return datetime.strptime(s, "%Y%m%d %H:%M")
    except ValueError:
        d = datetime.strptime(s, "%Y%m%d")
        return d.replace(hour=23, minute=59) if end else d


def importable_check() -> dict:
    """Record that no Ocean-MCP package (or mcp/httpx) is importable in this environment."""
    import importlib.util

    mods = ["stofs_mcp", "coops_mcp", "erddap_mcp", "ww3_mcp", "ndbc_mcp", "nhc_mcp", "vdatum_mcp",
            "recon_mcp", "ofs_mcp", "rtofs_mcp", "winds_mcp", "usgs_mcp", "goes_mcp", "mcp", "httpx"]
    return {m: importlib.util.find_spec(m) is not None for m in mods}


def write_answer(vdir: Path, arm: str, answer: dict) -> Path:
    out = Path(vdir) / "results/answers" / arm
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{answer['task_id']}.json"
    p.write_text(json.dumps(answer, indent=1, default=_json_default, allow_nan=True) + "\n")
    return p


def _json_default(o):
    try:
        import numpy as np

        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    return str(o)
