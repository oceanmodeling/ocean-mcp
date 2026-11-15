#!/usr/bin/env python3
"""Rate-limited, logged downloader for every NOAA request in WP5.

Rules enforced here (brief, "Restrictions"):

* one request at a time across *all* processes (an exclusive ``flock`` on a lock
  file is held from the start of a request until it has been written to disk);
* at least ``MIN_GAP_S`` seconds between the end of one request and the start of
  the next (the time of the last request is kept in a state file);
* at most one retry (after ``RETRY_WAIT_S``), only on a transport error, HTTP 429
  or HTTP 5xx;
* a request budget per phase; a request that would exceed it is refused;
* every attempt is appended to a JSON-lines log with URL, UTC start and end time,
  status, size and the SHA-256 of the body exactly as received (after transport
  decoding), and the body is saved under its SHA-256.

Standard library only. Usage as a module (``fetch(url, ...)``) or a command:

    python -I noaa_fetch.py --phase phase0 --tag s3_list --out DIR URL [URL ...]
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
STATE_DIR = PKG / "run_log" / "fetch_state"
LOCK = STATE_DIR / "noaa.lock"
LAST = STATE_DIR / "last_request_end.txt"
LOG = PKG / "run_log" / "noaa_requests.jsonl"
BUDGETS = PKG / "run_log" / "fetch_state" / "budgets.json"
MIN_GAP_S = 1.2
RETRY_WAIT_S = 5.0
TIMEOUT_S = 180.0
USER_AGENT = "ocean-mcp-wp5-evaluation/1.0 (python-urllib)"


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def _ext(url: str, ctype: str) -> str:
    path = url.split("?")[0].lower()
    for e in (".nc", ".pdf", ".html", ".htm", ".json", ".xml", ".txt", ".csv"):
        if path.endswith(e):
            return e
    c = (ctype or "").lower()
    for k, e in (("json", ".json"), ("xml", ".xml"), ("html", ".html"), ("pdf", ".pdf"), ("text", ".txt")):
        if k in c:
            return e
    return ".bin"


def _decode(body: bytes, enc: str) -> bytes:
    enc = (enc or "").lower()
    if enc == "gzip":
        return gzip.decompress(body)
    if enc == "deflate":
        return zlib.decompress(body)
    return body


def _budget_take(phase: str) -> tuple[int, int]:
    doc = json.loads(BUDGETS.read_text()) if BUDGETS.exists() else {}
    ph = doc.setdefault(phase, {"limit": None, "used": 0})
    if ph["limit"] is not None and ph["used"] >= ph["limit"]:
        raise RuntimeError(f"request budget for {phase} exhausted ({ph['used']}/{ph['limit']})")
    ph["used"] += 1
    BUDGETS.write_text(json.dumps(doc, indent=1) + "\n")
    return ph["used"], ph["limit"]


def set_budget(phase: str, limit: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "a+") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        doc = json.loads(BUDGETS.read_text()) if BUDGETS.exists() else {}
        doc.setdefault(phase, {"limit": None, "used": 0})["limit"] = limit
        BUDGETS.write_text(json.dumps(doc, indent=1) + "\n")


def fetch(url: str, out_dir: Path, *, phase: str, tag: str, method: str = "GET",
          headers: dict | None = None) -> dict:
    """Fetch one URL under the global lock; returns the log record of the final attempt."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "a+") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            rec = None
            for attempt in (1, 2):
                if LAST.exists():
                    gap = time.time() - float(LAST.read_text().strip() or 0)
                    if gap < MIN_GAP_S:
                        time.sleep(MIN_GAP_S - gap)
                used, limit = _budget_take(phase)
                start = utc()
                status, body, hdrs, err = None, b"", {}, None
                req = urllib.request.Request(url, method=method,
                                             headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip",
                                                      **(headers or {})})
                try:
                    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                        status = r.status
                        hdrs = {k.lower(): v for k, v in r.headers.items()}
                        body = r.read()
                except urllib.error.HTTPError as e:
                    status = e.code
                    hdrs = {k.lower(): v for k, v in e.headers.items()}
                    body = e.read()
                except Exception as e:  # transport error
                    err = f"{type(e).__name__}: {e}"
                end = utc()
                LAST.write_text(str(time.time()))
                body = _decode(body, hdrs.get("content-encoding", ""))
                sha = hashlib.sha256(body).hexdigest()
                path = None
                if method == "GET" and err is None:
                    path = out_dir / f"{sha}{_ext(url, hdrs.get('content-type', ''))}"
                    if not path.exists():
                        tmp = path.with_suffix(path.suffix + ".part")
                        tmp.write_bytes(body)
                        os.replace(tmp, path)
                rec = {"phase": phase, "tag": tag, "attempt": attempt, "method": method, "url": url,
                       "start_utc": start, "end_utc": end, "status": status, "error": err,
                       "bytes": len(body), "sha256": sha if err is None else None,
                       "content_type": hdrs.get("content-type"), "content_length": hdrs.get("content-length"),
                       "last_modified": hdrs.get("last-modified"), "etag": hdrs.get("etag"),
                       "path": str(path.relative_to(PKG)) if path and path.is_relative_to(PKG) else (str(path) if path else None),
                       "budget_used": used, "budget_limit": limit}
                with open(LOG, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, sort_keys=True) + "\n")
                retryable = err is not None or status == 429 or (status is not None and status >= 500)
                if not retryable or attempt == 2:
                    break
                time.sleep(RETRY_WAIT_S)
            return rec
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--method", default="GET")
    ap.add_argument("urls", nargs="+")
    a = ap.parse_args()
    for u in a.urls:
        r = fetch(u, Path(a.out), phase=a.phase, tag=a.tag, method=a.method)
        print(json.dumps({k: r[k] for k in ("status", "bytes", "sha256", "path", "url", "error")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
