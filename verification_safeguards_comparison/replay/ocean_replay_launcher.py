#!/usr/bin/env python3
"""Record and replay HTTP traffic for an unmodified MCP server package.

The launcher is kept outside every Ocean-MCP package. It patches the HTTP
transport of the server process and then runs the package's own entry point
(``python -m <module>``), so the package source is never changed.

Patched, at class level, before the package is imported:

* ``httpx.AsyncHTTPTransport.handle_async_request`` and
  ``httpx.HTTPTransport.handle_request``. Every httpx client ends there,
  including the packages' ``RetryTransport`` subclasses, which call
  ``super().handle_async_request``.
* ``socket.getaddrinfo``, ``socket.create_connection``, ``socket.socket.connect``
  and ``connect_ex`` (replay mode only): anything that is not answered from
  the archive and still tries to reach the network is refused and logged.

Modes:

* ``record``: perform the real request, archive the request and the decoded
  response body under its SHA-256, and log it.
* ``replay``: serve only from the archive. A request that is not archived is
  refused (``ReplayMiss``), logged as a violation and reported on stderr.

Matching (replay):

1. exact: method, scheme, host, port, path and the multiset of query
   parameters, ignoring only ``application`` (a CO-OPS client tag that the
   API documents as an identifier of the calling application; it does not
   select data).
2. head_from_get: a HEAD request is answered with the status and headers of
   the archived GET of the same resource.
3. coops_slice: a CO-OPS ``datagetter`` request for ``product=water_level``
   whose parameters equal those of an archived *master* response except
   ``begin_date``/``end_date`` is answered with the master's records whose
   time lies in [begin, end] (inclusive, as the API does). The slice is
   serialised in the master's own byte format, which is verified by a
   byte-exact round trip of the master before any slice is served. If the
   requested range is not inside the master's requested range, the request
   is a miss.

Archives are directories holding ``index.json`` and ``bodies/``. Several can
be stacked with ``--archive``; earlier ones take precedence, which is how a
synthetic (mutated) file replaces a real one for one task.

Only the standard library and httpx are imported, so the launcher runs in any
server environment. Run it as ``python -I ocean_replay_launcher.py ...``.
"""

from __future__ import annotations

import argparse
import atexit
import datetime as _dt
import hashlib
import json
import os
import runpy
import socket
import sys
import threading
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

IGNORED_PARAMS = frozenset({"application"})
COOPS_DATAGETTER = ("https", "api.tidesandcurrents.noaa.gov", "/api/prod/datagetter")
DROP_HEADERS = frozenset({"content-encoding", "content-length", "transfer-encoding"})


class ReplayMiss(RuntimeError):
    """A request that the archive cannot answer (replay mode)."""


class NetworkBlocked(RuntimeError):
    """A socket-level network attempt in replay mode."""


def utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def request_key(method: str, url: str) -> dict:
    parts = urlsplit(url)
    params = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k not in IGNORED_PARAMS
    )
    port = parts.port
    return {
        "method": method.upper(),
        "scheme": parts.scheme.lower(),
        "host": (parts.hostname or "").lower(),
        "port": port,
        "path": parts.path,
        "params": [list(p) for p in params],
    }


def key_string(key: dict) -> str:
    return json.dumps(key, sort_keys=True, separators=(",", ":"))


def _body_suffix(content_type: str, url: str) -> str:
    path = urlsplit(url).path.lower()
    for ext in (".nc", ".grib2", ".txt", ".json", ".html", ".csv", ".pdf", ".xml"):
        if path.endswith(ext):
            return ext
    ct = (content_type or "").lower()
    if "json" in ct:
        return ".json"
    if "html" in ct:
        return ".html"
    if "text" in ct:
        return ".txt"
    return ".bin"


# --- CO-OPS slicing ---------------------------------------------------------


def coops_serialize(doc: dict) -> bytes:
    """Serialise a CO-OPS datagetter water_level JSON document in the API's
    own layout: ``{"metadata":{...}, "data": [{"t":"..", "v":"..", ...},...]}``
    followed by a newline."""
    md = json.dumps(doc["metadata"], separators=(",", ":"), ensure_ascii=False)
    recs = ",".join(
        "{"
        + ", ".join(
            json.dumps(k, ensure_ascii=False) + ":" + json.dumps(v, ensure_ascii=False)
            for k, v in rec.items()
        )
        + "}"
        for rec in doc["data"]
    )
    return ('{"metadata":' + md + ', "data": [' + recs + "]}\n").encode("utf-8")


def coops_time(value: str, *, end: bool) -> _dt.datetime:
    """Parse a CO-OPS begin/end_date. A date without a time means 00:00 for
    begin_date and 23:59 for end_date."""
    value = value.strip()
    for fmt in ("%Y%m%d %H:%M", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M"):
        try:
            return _dt.datetime.strptime(value, fmt)
        except ValueError:
            pass
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            d = _dt.datetime.strptime(value, fmt)
            return d.replace(hour=23, minute=59) if end else d
        except ValueError:
            pass
    raise ValueError(f"unparseable CO-OPS date {value!r}")


# --- archive ----------------------------------------------------------------


class Archive:
    def __init__(self, root: Path, writable: bool = False) -> None:
        self.root = Path(root)
        self.writable = writable
        self.index_path = self.root / "index.json"
        self.bodies = self.root / "bodies"
        self.lock = threading.Lock()
        if self.index_path.exists():
            self.doc = json.loads(self.index_path.read_text())
        else:
            if not writable:
                raise FileNotFoundError(f"archive index not found: {self.index_path}")
            self.doc = {"format": "ocean-replay-archive/1", "entries": [], "dns": {}}
        self.by_key: dict[str, dict] = {}
        for e in self.doc["entries"]:
            self.by_key.setdefault(key_string(e["key"]), e)
        self._verified_masters: dict[str, dict] = {}

    def body_bytes(self, entry: dict) -> bytes:
        path = self.root / entry["response"]["body_file"]
        data = path.read_bytes()
        got = sha256_bytes(data)
        if got != entry["response"]["body_sha256"]:
            raise ReplayMiss(
                f"archive corruption: {path} has sha256 {got}, index says "
                f"{entry['response']['body_sha256']}"
            )
        return data

    def add(
        self,
        key: dict,
        url: str,
        status: int,
        headers: list[list[str]],
        body: bytes,
        provenance: dict,
        kind: str = "exact",
    ) -> dict:
        if not self.writable:
            raise RuntimeError("archive is read-only")
        sha = sha256_bytes(body)
        ctype = next((v for k, v in headers if k.lower() == "content-type"), "")
        rel = f"bodies/{sha}{_body_suffix(ctype, url)}"
        with self.lock:
            self.bodies.mkdir(parents=True, exist_ok=True)
            target = self.root / rel
            if not target.exists():
                tmp = target.with_suffix(target.suffix + ".part")
                tmp.write_bytes(body)
                os.replace(tmp, target)
            entry = {
                "id": f"e{len(self.doc['entries']) + 1:04d}",
                "kind": kind,
                "key": key,
                "url": url,
                "response": {
                    "status": status,
                    "headers": headers,
                    "body_file": rel,
                    "body_sha256": sha,
                    "bytes": len(body),
                },
                "provenance": provenance,
            }
            self.doc["entries"].append(entry)
            self.by_key[key_string(key)] = entry
            self.save()
        return entry

    def add_dns(self, host: str, addresses: list[str]) -> None:
        with self.lock:
            known = self.doc.setdefault("dns", {})
            if sorted(set(known.get(host, [])) | set(addresses)) != known.get(host):
                known[host] = sorted(set(known.get(host, [])) | set(addresses))
                self.save()

    def save(self) -> None:
        tmp = self.index_path.with_suffix(".json.part")
        self.root.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(self.doc, indent=1, sort_keys=False) + "\n")
        os.replace(tmp, self.index_path)

    def masters(self) -> list[dict]:
        return [e for e in self.doc["entries"] if e.get("kind") == "coops_master"]

    def verified_master(self, entry: dict) -> dict:
        """Load a CO-OPS master and prove that coops_serialize reproduces its
        bytes exactly; refuse to slice it otherwise."""
        if entry["id"] in self._verified_masters:
            return self._verified_masters[entry["id"]]
        raw = self.body_bytes(entry)
        doc = json.loads(raw)
        if coops_serialize(doc) != raw:
            raise ReplayMiss(
                f"CO-OPS master {entry['id']} does not round-trip byte-exactly; "
                "slicing refused"
            )
        self._verified_masters[entry["id"]] = doc
        return doc


# --- engine -----------------------------------------------------------------


class Engine:
    def __init__(self, mode: str, archives: list[Archive], log_path: Path | None):
        self.mode = mode
        self.archives = archives
        self.log_path = log_path
        self.log_lock = threading.Lock()
        self.counts = {"served": 0, "recorded": 0, "miss": 0, "network_blocked": 0}
        self.seq = 0

    # logging
    def log(self, record: dict) -> None:
        record = {"seq": self.seq, "time": utcnow(), "pid": os.getpid(), **record}
        self.seq += 1
        if self.log_path is None:
            return
        with self.log_lock:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True) + "\n")

    def violation(self, kind: str, detail: dict) -> None:
        self.counts["miss" if kind == "replay_miss" else "network_blocked"] += 1
        self.log({"event": kind, **detail})
        print(f"[ocean-replay] VIOLATION {kind}: {json.dumps(detail)}", file=sys.stderr)

    # matching
    def lookup(self, method: str, url: str) -> tuple[Archive, dict, str] | None:
        key = request_key(method, url)
        ks = key_string(key)
        for arc in self.archives:
            if ks in arc.by_key:
                return arc, arc.by_key[ks], "exact"
        if key["method"] == "HEAD":
            gks = key_string({**key, "method": "GET"})
            for arc in self.archives:
                if gks in arc.by_key:
                    return arc, arc.by_key[gks], "head_from_get"
        return None

    def coops_slice(self, url: str) -> tuple[bytes, dict, Archive, dict] | None:
        key = request_key("GET", url)
        if (key["scheme"], key["host"], key["path"]) != COOPS_DATAGETTER:
            return None
        params = dict((k, v) for k, v in key["params"])
        if params.get("product") != "water_level":
            return None
        if "begin_date" not in params or "end_date" not in params:
            return None
        want_lo = coops_time(params["begin_date"], end=False)
        want_hi = coops_time(params["end_date"], end=True)
        rest = {k: v for k, v in params.items() if k not in ("begin_date", "end_date")}
        # Archive order decides first (an overlay beats the base archive);
        # within one archive the earliest-retrieved covering master is used.
        for arc in self.archives:
            found = self._slice_from(arc, rest, want_lo, want_hi)
            if found is not None:
                return found
        return None

    def _slice_from(self, arc, rest, want_lo, want_hi):
        candidates = []
        for m in arc.masters():
            mp = dict((k, v) for k, v in m["key"]["params"])
            mrest = {k: v for k, v in mp.items() if k not in ("begin_date", "end_date")}
            if (m["key"]["scheme"], m["key"]["host"], m["key"]["path"]) != COOPS_DATAGETTER:
                continue
            if mrest != rest:
                continue
            lo = coops_time(mp["begin_date"], end=False)
            hi = coops_time(mp["end_date"], end=True)
            if lo <= want_lo and want_hi <= hi:
                candidates.append((m["provenance"].get("retrieved_at", ""), m["id"], m))
        if not candidates:
            return None
        candidates.sort(key=lambda c: (c[0], c[1]))
        master = candidates[0][2]
        doc = arc.verified_master(master)
        kept = [
            rec
            for rec in doc["data"]
            if want_lo <= _dt.datetime.strptime(rec["t"], "%Y-%m-%d %H:%M") <= want_hi
        ]
        body = coops_serialize({"metadata": doc["metadata"], "data": kept})
        info = {
            "master_id": master["id"],
            "master_sha256": master["response"]["body_sha256"],
            "records_in_master": len(doc["data"]),
            "records_served": len(kept),
        }
        return body, info, arc, master

    def replay(self, method: str, url: str) -> tuple[int, list[list[str]], bytes, dict]:
        found = self.lookup(method, url)
        if found:
            arc, entry, rule = found
            body = b"" if rule == "head_from_get" else arc.body_bytes(entry)
            info = {
                "rule": rule,
                "entry_id": entry["id"],
                "archive": str(arc.root),
                "source": entry["provenance"].get("source"),
            }
            return entry["response"]["status"], entry["response"]["headers"], body, info
        sliced = self.coops_slice(url) if method.upper() == "GET" else None
        if sliced:
            body, info, arc, master = sliced
            info.update({"rule": "coops_slice", "archive": str(arc.root), "source": "derived"})
            return master["response"]["status"], master["response"]["headers"], body, info
        raise ReplayMiss(f"not archived: {method} {url}")

    # httpx glue
    def build_response(self, httpx, request, status, headers, body):
        hdrs = [(k, v) for k, v in headers if k.lower() not in DROP_HEADERS]
        return httpx.Response(status, headers=hdrs, content=body, request=request)

    async def handle_async(self, httpx, request, original):
        url = str(request.url)
        method = request.method
        if self.mode == "replay":
            try:
                status, headers, body, info = self.replay(method, url)
            except ReplayMiss as exc:
                self.violation("replay_miss", {"method": method, "url": url, "error": str(exc)})
                raise
            self.counts["served"] += 1
            self.log(
                {
                    "event": "served",
                    "method": method,
                    "url": url,
                    "status": status,
                    "bytes": len(body),
                    "body_sha256": sha256_bytes(body),
                    **info,
                }
            )
            return self.build_response(httpx, request, status, headers, body)
        # record
        response = await original()
        body = await response.aread()
        await response.aclose()
        headers = [[k, v] for k, v in response.headers.multi_items()]
        arc = self.archives[0]
        entry = arc.add(
            request_key(method, url),
            url,
            response.status_code,
            headers,
            body if method.upper() != "HEAD" else b"",
            {"source": "recorded", "retrieved_at": utcnow(), "http_version": response.http_version},
        )
        self.counts["recorded"] += 1
        self.log(
            {
                "event": "recorded",
                "method": method,
                "url": url,
                "status": response.status_code,
                "bytes": len(body),
                "body_sha256": entry["response"]["body_sha256"],
                "entry_id": entry["id"],
            }
        )
        return self.build_response(httpx, request, response.status_code, headers, body)

    def handle_sync(self, httpx, request, original):
        url = str(request.url)
        method = request.method
        if self.mode == "replay":
            try:
                status, headers, body, info = self.replay(method, url)
            except ReplayMiss as exc:
                self.violation("replay_miss", {"method": method, "url": url, "error": str(exc)})
                raise
            self.counts["served"] += 1
            self.log({"event": "served", "method": method, "url": url, "status": status,
                      "bytes": len(body), "body_sha256": sha256_bytes(body), **info})
            return self.build_response(httpx, request, status, headers, body)
        response = original()
        body = response.read()
        response.close()
        headers = [[k, v] for k, v in response.headers.multi_items()]
        entry = self.archives[0].add(
            request_key(method, url), url, response.status_code, headers,
            body if method.upper() != "HEAD" else b"",
            {"source": "recorded", "retrieved_at": utcnow(), "http_version": response.http_version},
        )
        self.counts["recorded"] += 1
        self.log({"event": "recorded", "method": method, "url": url, "status": response.status_code,
                  "bytes": len(body), "body_sha256": entry["response"]["body_sha256"],
                  "entry_id": entry["id"]})
        return self.build_response(httpx, request, response.status_code, headers, body)


ENGINE: Engine | None = None


def install(mode: str, archive_dirs: list[str], log_path: str | None) -> Engine:
    """Patch httpx (and, in replay mode, socket) for this process."""
    global ENGINE
    if mode not in ("record", "replay"):
        raise ValueError(mode)
    if mode == "record" and len(archive_dirs) != 1:
        raise ValueError("record mode takes exactly one --archive")
    archives = [Archive(Path(d), writable=(mode == "record")) for d in archive_dirs]
    engine = Engine(mode, archives, Path(log_path) if log_path else None)
    ENGINE = engine

    import httpx  # noqa: PLC0415  (imported after argument parsing on purpose)

    orig_async = httpx.AsyncHTTPTransport.handle_async_request
    orig_sync = httpx.HTTPTransport.handle_request

    async def patched_async(self, request):
        return await engine.handle_async(httpx, request, lambda: orig_async(self, request))

    def patched_sync(self, request):
        return engine.handle_sync(httpx, request, lambda: orig_sync(self, request))

    httpx.AsyncHTTPTransport.handle_async_request = patched_async
    httpx.HTTPTransport.handle_request = patched_sync

    orig_getaddrinfo = socket.getaddrinfo

    if mode == "replay":
        dns: dict[str, list[str]] = {}
        for arc in archives:
            for host, addrs in arc.doc.get("dns", {}).items():
                dns.setdefault(host, addrs)

        def guarded_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            h = host.decode() if isinstance(host, bytes) else host
            if h in dns:
                out = []
                for addr in dns[h]:
                    fam = socket.AF_INET6 if ":" in addr else socket.AF_INET
                    sockaddr = (addr, port or 0, 0, 0) if fam == socket.AF_INET6 else (addr, port or 0)
                    out.append((fam, type or socket.SOCK_STREAM, proto or 6, "", sockaddr))
                engine.log({"event": "dns_from_archive", "host": h, "addresses": dns[h]})
                return out
            engine.violation("network_blocked", {"call": "getaddrinfo", "host": h})
            raise socket.gaierror(socket.EAI_NONAME, f"ocean-replay: DNS for {h!r} is not archived")

        def blocked(name):
            def _f(*args, **kwargs):
                engine.violation("network_blocked", {"call": name, "args": repr(args[1:3])})
                raise NetworkBlocked(f"ocean-replay: network access blocked ({name})")
            return _f

        socket.getaddrinfo = guarded_getaddrinfo
        socket.create_connection = blocked("create_connection")
        socket.socket.connect = blocked("socket.connect")
        socket.socket.connect_ex = blocked("socket.connect_ex")
    else:

        def recording_getaddrinfo(host, port, *args, **kwargs):
            res = orig_getaddrinfo(host, port, *args, **kwargs)
            h = host.decode() if isinstance(host, bytes) else host
            try:
                archives[0].add_dns(h, [r[4][0] for r in res])
            except Exception:  # pragma: no cover - logging only
                pass
            return res

        socket.getaddrinfo = recording_getaddrinfo

    def summary():
        engine.log({"event": "summary", "mode": mode, "counts": engine.counts,
                    "archives": [str(a.root) for a in archives]})
        print(f"[ocean-replay] {mode} summary: {json.dumps(engine.counts)}", file=sys.stderr)

    atexit.register(summary)
    engine.log({"event": "start", "mode": mode, "archives": [str(a.root) for a in archives],
                "python": sys.version.split()[0], "argv": sys.argv})
    return engine


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mode", choices=("record", "replay"), required=True)
    ap.add_argument("--archive", action="append", required=True,
                    help="archive directory; repeat to stack (first wins)")
    ap.add_argument("--log", help="JSON-lines request log")
    ap.add_argument("-m", dest="module", required=True,
                    help="server module to run, as python -m would")
    args = ap.parse_args(argv)
    install(args.mode, args.archive, args.log)
    sys.argv = [args.module]
    runpy.run_module(args.module, run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
