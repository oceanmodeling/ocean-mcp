#!/usr/bin/env python3
"""WP5 replay launcher: the WP1 launcher, unchanged, plus three CO-OPS answer rules.

``ocean_replay_launcher.py`` in this directory is a byte-identical copy of the WP1 launcher
(sha256 203398c3708a202b6240f5b00de9c0b2826f3534f43133d05631b810073aba87; checked at start-up).
This wrapper imports it, replaces ``Engine.coops_slice`` with the function below, and runs the
launcher's own ``main()``. Nothing else changes: matching order, fail-loud behaviour, logging,
DNS and socket guards are the WP1 code.

Added rules (DESIGN.md 5.2). They apply only to CO-OPS ``datagetter`` requests for
``product=water_level`` with ``begin_date``/``end_date``, after WP1 rules 1 and 2 have failed:

3. (WP1) slice of a covering data master, in the master's byte layout.
5. *empty slice*: if the covering data master has no record in [begin, end], CO-OPS answers
   with its generic no-data document (HTTP 200), not an empty list. The archived template is
   the exact body CO-OPS returned in Phase 0 for an inactive station and for an active station
   outside its data (two requests, byte-identical, sha256 500bdf8b...). It is served instead.
4b. *no-data master*: a master request that CO-OPS answered with the generic no-data document
   (sha256 500bdf8b..., the only error body accepted here) covers every sub-range of its own
   range; that document is served verbatim. Any other error document (rate limit, maintenance,
   malformed request) is an acquisition gap and is never served.
4a. *unsupported datum*: an error master whose status is 400 and whose message lists the
   supported datums ("The supported Datum values are: ...") answers any range for the same
   station and datum. Phase 0 showed the body does not depend on the dates (two ranges,
   byte-identical, sha256 d93e3df0...).

Usage: python -I wp5_launcher.py --mode replay --archive A [--archive B] --log L -m <module>
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WP1_LAUNCHER_SHA256 = "203398c3708a202b6240f5b00de9c0b2826f3534f43133d05631b810073aba87"
_src = (HERE / "ocean_replay_launcher.py").read_bytes()
if hashlib.sha256(_src).hexdigest() != WP1_LAUNCHER_SHA256:
    raise SystemExit("ocean_replay_launcher.py differs from the WP1 launcher; refusing to run")
sys.path.insert(0, str(HERE))
import ocean_replay_launcher as L  # noqa: E402

UNSUPPORTED_PREFIX = "The supported Datum values are"
import re  # noqa: E402
NO_DATUM = re.compile(r"^There is no [A-Za-z0-9]+ for the station")  # amendment A5
NODATA_SHA256 = "500bdf8b7540e3b178fa94711e95e7bd7633578dac4778da5faed9dc45cbfb0f"
_wp1_coops_slice = L.Engine.coops_slice


def _split(url: str):
    key = L.request_key("GET", url)
    if (key["scheme"], key["host"], key["path"]) != L.COOPS_DATAGETTER:
        return None
    p = dict((k, v) for k, v in key["params"])
    if p.get("product") != "water_level" or "begin_date" not in p or "end_date" not in p:
        return None
    rest = {k: v for k, v in p.items() if k not in ("begin_date", "end_date")}
    return p, rest


def _entry_rest(e: dict):
    mp = dict((k, v) for k, v in e["key"]["params"])
    return mp, {k: v for k, v in mp.items() if k not in ("begin_date", "end_date")}


def _template(engine):
    for arc in engine.archives:
        for e in arc.doc["entries"]:
            if e.get("kind") == "coops_nodata_template":
                return arc, e
    raise L.ReplayMiss("rule 5 needs a coops_nodata_template entry; none is archived")


def coops_slice(self, url: str):
    sp = _split(url)
    if sp is None:
        return None
    params, rest = sp
    found = _wp1_coops_slice(self, url)
    if found is not None:
        body, info, arc, master = found
        if info.get("records_served", 1) > 0:
            return found
        tarc, t = _template(self)
        tbody = tarc.body_bytes(t)
        info = {**info, "wp5_rule": "5_empty_slice", "template_entry": t["id"],
                "template_sha256": t["response"]["body_sha256"]}
        return tbody, info, tarc, t
    lo = L.coops_time(params["begin_date"], end=False)
    hi = L.coops_time(params["end_date"], end=True)
    for arc in self.archives:  # 4b: error master covering the range
        for e in arc.doc["entries"]:
            if e.get("kind") != "coops_error_master" or e["response"]["body_sha256"] != NODATA_SHA256:
                continue
            mp, mrest = _entry_rest(e)
            if (e["key"]["scheme"], e["key"]["host"], e["key"]["path"]) != L.COOPS_DATAGETTER or mrest != rest:
                continue
            if L.coops_time(mp["begin_date"], end=False) <= lo and hi <= L.coops_time(mp["end_date"], end=True):
                return arc.body_bytes(e), {"wp5_rule": "4b_error_master", "master_id": e["id"],
                                          "master_sha256": e["response"]["body_sha256"]}, arc, e
    for arc in self.archives:  # 4a: unsupported datum, any range
        for e in arc.doc["entries"]:
            if e.get("kind") != "coops_error_master" or e["response"]["status"] != 400:
                continue
            _, mrest = _entry_rest(e)
            if (e["key"]["scheme"], e["key"]["host"], e["key"]["path"]) != L.COOPS_DATAGETTER or mrest != rest:
                continue
            body = arc.body_bytes(e)
            try:
                msg = json.loads(body)["error"]["message"].strip()
            except Exception:
                continue
            if msg.startswith(UNSUPPORTED_PREFIX) or NO_DATUM.match(msg):
                return body, {"wp5_rule": "4a_unsupported_datum", "master_id": e["id"],
                              "master_sha256": e["response"]["body_sha256"]}, arc, e
    return None


L.Engine.coops_slice = coops_slice


# --- amendment A6: CO-OPS documents with extra top-level keys after "data" ----------------
# Some masters end with `],"disclaimers": [...]}` instead of `]}`. The WP1 serializer cannot
# reproduce that tail, so WP1 rule 3 refuses to slice them. Here the tail is kept verbatim:
# a master is accepted only if (WP1 serialization of its metadata and records, without the
# closing "]}\n") + (its raw tail starting at the "]" that closes "data") equals its bytes
# exactly; a slice is then the WP1 serialization of the kept records + the same raw tail.
_wp1_serialize = L.coops_serialize
_wp1_verified = L.Archive.verified_master
_TAILS: dict[int, bytes] = {}


def coops_serialize(doc: dict) -> bytes:
    body = _wp1_serialize(doc)
    tail = _TAILS.get(id(doc["metadata"]))
    if tail is None:
        return body
    return body[:-3] + tail  # body ends with b"]}\n"


def verified_master(self, entry: dict) -> dict:
    try:
        return _wp1_verified(self, entry)
    except L.ReplayMiss:
        raw = self.body_bytes(entry)
        doc = json.loads(raw)
        prefix = _wp1_serialize(doc)[:-3]
        if not (raw.startswith(prefix) and raw[len(prefix):len(prefix) + 1] == b"]"):
            raise
        _TAILS[id(doc["metadata"])] = raw[len(prefix):]
        if coops_serialize(doc) != raw:
            del _TAILS[id(doc["metadata"])]
            raise
        self._verified_masters[entry["id"]] = doc
        return doc


L.coops_serialize = coops_serialize
L.Archive.verified_master = verified_master

if __name__ == "__main__":
    L.main()
