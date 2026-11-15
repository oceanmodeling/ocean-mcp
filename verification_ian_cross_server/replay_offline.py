"""Offline replay of the WP2 Ian workflow: recompute every number from the archive.

    python3 replay_offline.py

No network: socket connections and DNS lookups are disabled before anything
else runs. Standard library only; no Ocean-MCP or MCP package is imported.
Exits with status 1 if any check fails. Checks:

1. Every file listed in manifest.json has the recorded SHA-256.
2. Every recorded tool response has the recorded text and result SHA-256,
   in the session record and in the manifest.
3. analyze.compute() on the session record reproduces results.json exactly,
   and geometry_table.md exactly; REPORT.md contains that table verbatim.
4. An independent implementation here (integer millimetres) reproduces the
   residual extremes and their times, and they equal the manuscript values
   +2.209 m (Fort Myers, 22:18 and 22:30 UTC on 28 September) and
   -1.755 m (St. Petersburg, 23:00 UTC).
5. An independent interpolation and spherical-law-of-cosines distance agree
   with the archived haversine distances to within 1 m.

There is no figure to regenerate: WP2 adds a table, not a figure.
"""

from __future__ import annotations

import socket


def _no_network(*_args, **_kwargs):
    raise OSError("network access is disabled in replay_offline.py")


socket.socket.connect = _no_network  # type: ignore[method-assign]
socket.socket.connect_ex = _no_network  # type: ignore[method-assign]
socket.create_connection = _no_network  # type: ignore[assignment]
socket.getaddrinfo = _no_network  # type: ignore[assignment]

import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze  # noqa: E402

EXPECTED = {
    "8725520": ("max", 2209, ["2022-09-28 22:18", "2022-09-28 22:30"]),
    "8726520": ("min", -1755, ["2022-09-28 23:00"]),
}

failures: list[str] = []
passed = 0


def check(ok: bool, what: str) -> None:
    """Count a passed check or record a failure."""
    global passed
    if ok:
        passed += 1
    else:
        failures.append(what)
        print(f"FAIL: {what}")


def sha256_bytes(data: bytes) -> str:
    """SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def canonical(obj) -> str:
    """Same canonical JSON as run_workflow.py."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def mm(v: str) -> int:
    """'2.613' -> 2613, '-1.2' -> -1200, without floating point."""
    v = v.strip()
    sign = -1 if v.startswith("-") else 1
    whole, _, frac = v.lstrip("+-").partition(".")
    return sign * (int(whole or "0") * 1000 + int((frac + "000")[:3]))


def independent_extremes(record: dict) -> dict:
    """Residual extremes in integer millimetres, implemented separately from analyze.py."""
    texts = {}
    for c in record["calls"]:
        sid = c["arguments"].get("station_id")
        texts[(c["tool"], sid)] = c["result"]["content"][0]["text"]
    out = {}
    for sid, (kind, _, _) in EXPECTED.items():
        obs = json.loads(texts[("coops_get_water_levels", sid)])["data"]["data"]
        pred = json.loads(texts[("coops_get_tide_predictions", sid)])["data"][
            "predictions"
        ]
        p = {r["t"]: mm(r["v"]) for r in pred if r["v"].strip()}
        res = {
            r["t"]: mm(r["v"]) - p[r["t"]]
            for r in obs
            if r["v"].strip() and r["t"] in p
        }
        best = max(res.values()) if kind == "max" else min(res.values())
        out[sid] = (best, sorted(t for t, v in res.items() if v == best), len(res))
    return out


def slc_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Spherical law of cosines, same radius as analyze.py."""
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    c = math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl)
    return 6371.0088 * math.acos(max(-1.0, min(1.0, c)))


def independent_geometry(record: dict, results: dict) -> None:
    """Re-interpolate the storm centre and recompute distances by a different formula."""
    bt = json.loads(
        next(c for c in record["calls"] if c["tool"] == "nhc_get_best_track")["result"][
            "content"
        ][0]["text"]
    )
    fixes = sorted(
        (
            (datetime.strptime(p["datetime"], "%Y%m%d %H%M UTC"), p["lat"], p["lon"])
            for p in bt["track_points"]
        ),
        key=lambda f: f[0],
    )
    gauges = results["geometry"]["gauges"]
    for ev in results["geometry"]["events"]:
        t = datetime.strptime(ev["t"], "%Y-%m-%d %H:%M")
        (t0, la0, lo0), (t1, la1, lo1) = (
            [f for f in fixes if f[0] <= t][-1],
            [f for f in fixes if f[0] > t][0],
        )
        w = (t - t0).total_seconds() / (t1 - t0).total_seconds()
        lat, lon = la0 + w * (la1 - la0), lo0 + w * (lo1 - lo0)
        for sid, g in gauges.items():
            d = slc_km(lat, lon, g["lat"], g["lon"])
            archived = ev["to_gauge"][sid]["distance_km"]
            check(
                abs(d - archived) < 0.001,
                f"independent distance {ev['t']} {sid}: {d:.4f} vs {archived}",
            )


def main() -> int:
    """Run all checks; return the exit status."""
    manifest = json.loads((HERE / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        check(sha256_bytes((HERE / name).read_bytes()) == digest, f"checksum of {name}")

    raw = (HERE / "session_record.json").read_bytes()
    record = json.loads(raw)
    by_seq = {c["seq"]: c for c in manifest["calls"]}
    for c in record["calls"]:
        text = c["result"]["content"][0]["text"]
        check(
            sha256_bytes(text.encode("utf-8")) == c["text_sha256"],
            f"call {c['seq']} text checksum",
        )
        check(
            sha256_bytes(canonical(c["result"]).encode("utf-8")) == c["result_sha256"],
            f"call {c['seq']} result checksum",
        )
        check(
            by_seq[c["seq"]]["text_sha256"] == c["text_sha256"],
            f"call {c['seq']} checksum in manifest",
        )
        check(
            c["result"].get("structuredContent", {}).get("result") == text,
            f"call {c['seq']} structuredContent equals text",
        )

    archived = json.loads((HERE / "results.json").read_text())
    recomputed = analyze.compute(record)
    recomputed["session_record_sha256"] = sha256_bytes(raw)
    recomputed = json.loads(json.dumps(recomputed, ensure_ascii=False))
    diffs = analyze.deep_diff(archived, recomputed)
    for d in diffs[:20]:
        print(
            f"  differs: {d['path']}: archived={d['saved']!r} recomputed={d['new']!r}"
        )
    check(not diffs, f"results.json reproduced ({len(diffs)} differences)")

    table = analyze.geometry_table(recomputed)
    check(
        table == (HERE / "geometry_table.md").read_text(),
        "geometry_table.md reproduced",
    )
    report = HERE / "REPORT.md"
    check(
        report.exists() and table.strip() in report.read_text(),
        "REPORT.md contains the reproduced geometry table",
    )

    ind = independent_extremes(record)
    for sid, (kind, value_mm, times) in EXPECTED.items():
        got, got_times, pairs = ind[sid]
        check(pairs == 720, f"{sid}: 720 matched pairs (got {pairs})")
        check(
            got == value_mm and got_times == times,
            f"{sid}: {kind} {got / 1000:+.3f} m at {got_times}, expected {value_mm / 1000:+.3f} m at {times}",
        )
        r = archived["residuals"][sid]
        arch_val, arch_times = (
            (r["max_residual_m"], r["max_times"])
            if kind == "max"
            else (r["min_residual_m"], r["min_times"])
        )
        check(
            mm(arch_val) == got and arch_times == got_times,
            f"{sid}: archived extreme equals independent result",
        )
    check(
        archived["all_targets_reproduced"] is True,
        "results.json reports all targets reproduced",
    )

    independent_geometry(record, archived)

    print(f"{passed} checks passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
