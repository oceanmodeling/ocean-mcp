#!/usr/bin/env python3
"""Hurricane Ian: the coast floods first, the rivers days later.

Ian's surge hit the Fort Myers tide gauge within hours of landfall on
2022-09-28. Inland, the rain it dropped took days to drain: the Peace and
Myakka rivers crested on 2022-10-01 at the largest annual peaks in their
records. This example puts both on one timeline.

It spawns three ocean-mcp servers as MCP stdio subprocesses (the same
`uv run` lines as .mcp.json) and chains these tool calls:

  1. nhc-mcp    nhc_get_best_track         Ian's HURDAT2 track (AL092022)
  2. coops-mcp  coops_get_station          Fort Myers gauge position
  3. coops-mcp  coops_get_water_levels     Fort Myers water level above MHHW
  4. usgs-mcp   usgs_get_daily_values      daily mean discharge, per river
  5. usgs-mcp   usgs_get_peak_streamflow   annual peak record, per river

The best track is used to find when Ian's centre passed closest to each
gauge; nothing here hard-codes the landfall time.

Verified against the live services (2026-10-03)
-----------------------------------------------
Peace River at SR 70 at Arcadia (02296750): daily mean 49,900 ft3/s on
2022-10-01, up from 6,170 on 2022-09-27; annual peak 50,800 ft3/s, the
largest in the record (previous: 43,000 historic estimate, 1912; 36,200,
1933). Myakka River near SR 72 near Sarasota (02298830): daily mean 12,600
ft3/s on 2022-10-01; annual peak 12,900 ft3/s, the largest in the record
(previous: 11,100, 2003). Both Ian peaks carry USGS peak code 9 (hurricane).
USGS daily means are for local (EDT) days, not UTC days.

Usage
-----
    python3 examples/ian_coast_to_river_flooding.py

Requires: mcp, matplotlib, numpy; `uv` on PATH (servers launched with
`uv run --directory ...`, same as .mcp.json).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parent.parent
TIME_FMT = "%Y-%m-%d %H:%M"  # CO-OPS emits this exact format
CALL_TIMEOUT_S = 240.0
CFS_TO_CMS = 0.0283168

STORM_ID = "AL092022"
COAST_STATION = "8725520"  # Fort Myers, FL
RIVERS = (
    ("02296750", "Peace R. at Arcadia"),
    ("02298830", "Myakka R. near Sarasota"),
)
START, END = "2022-09-24", "2022-10-09"

SERIES_1 = "#2a78d6"  # blue   — categorical slot 1 (Fort Myers water level)
SERIES_2 = "#eb6834"  # orange — categorical slot 2 (Peace River)
SERIES_3 = "#1baf7a"  # aqua   — categorical slot 3 (Myakka River)
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#d8d7d2"


# --------------------------------------------------------------------------- #
# MCP plumbing (same pattern as the other MCP examples)
# --------------------------------------------------------------------------- #
def _uv() -> str:
    """Locate the `uv` launcher (same one .mcp.json relies on)."""
    found = shutil.which("uv")
    if found:
        return found
    fallback = Path.home() / "miniconda3" / "bin" / "uv"
    if fallback.exists():
        return str(fallback)
    sys.exit("error: `uv` not found on PATH — needed to launch the MCP servers.")


async def call_mcp_tool(
    server_dir: str,
    module: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Spawn one ocean-mcp server over stdio, call a single tool, return its text."""
    params = StdioServerParameters(
        command=_uv(),
        args=[
            "run",
            "--directory",
            str(REPO_ROOT / server_dir),
            "python",
            "-m",
            module,
        ],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=60.0)
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments=arguments),
                timeout=CALL_TIMEOUT_S,
            )
    if not result.content:
        raise RuntimeError(f"{tool_name} returned no content")
    text = getattr(result.content[0], "text", "")
    if result.isError:
        raise RuntimeError(f"{tool_name} reported an error:\n{text}")
    return text


def _parse_json_or_die(text: str, what: str) -> Any:
    """Tool returned JSON on success, or a plain-text error message on failure."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        sys.exit(f"\n{what} did not return JSON — the tool said:\n\n{text}\n")


def _search_or_die(pattern: str, text: str, what: str) -> float:
    """Pull one number out of a markdown-only tool response."""
    m = re.search(pattern, text)
    if not m:
        sys.exit(f"\nCould not read {what} — the tool said:\n\n{text}\n")
    return float(m.group(1))


# --------------------------------------------------------------------------- #
# Track geometry
# --------------------------------------------------------------------------- #
def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def closest_approach(
    track: list[tuple[datetime, float, float]], lat: float, lon: float
) -> tuple[datetime, float]:
    """Time and distance of the track's closest pass, interpolated every 10 min."""
    best = (track[0][0], float("inf"))
    for (t0, la0, lo0), (t1, la1, lo1) in zip(track, track[1:]):
        steps = max(1, int((t1 - t0).total_seconds() // 600))
        for k in range(steps + 1):
            f = k / steps
            t = t0 + (t1 - t0) * f
            d = _km(la0 + (la1 - la0) * f, lo0 + (lo1 - lo0) * f, lat, lon)
            if d < best[1]:
                best = (t, d)
    return best


# --------------------------------------------------------------------------- #
# Plot
# --------------------------------------------------------------------------- #
def make_plot(
    coast_t: list[datetime],
    coast_v: list[float],
    coast_peak: tuple[datetime, float],
    pass_time: datetime,
    pass_km: float,
    rivers: list[dict[str, Any]],
    out_path: Path,
) -> None:
    """Top: Fort Myers water level above MHHW. Bottom: river daily mean flow.

    figsize (12, 8.5) at dpi=100 -> 1200x850 px, under the 1600 px rule.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8.5), sharex=True, gridspec_kw={"hspace": 0.3}
    )
    for ax in (ax1, ax2):
        ax.grid(True, color=GRID, lw=0.7)
        ax.tick_params(colors=MUTED)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.axvline(pass_time, color=MUTED, lw=1, ls="--", zorder=2)

    # ---- (a) the coast ------------------------------------------------------ #
    ax1.plot(coast_t, coast_v, color=SERIES_1, lw=1.6, zorder=3)
    ax1.axhline(0, color=MUTED, lw=0.8, ls=":")
    pk_t, pk_v = coast_peak
    ax1.set_ylim(min(coast_v) - 0.15, pk_v * 1.15)
    ax1.plot(
        [pk_t],
        [pk_v],
        marker="o",
        ms=9,
        color=SERIES_1,
        mec="white",
        mew=1.6,
        zorder=5,
    )
    ax1.annotate(
        f"Surge peak {pk_v:.2f} m above MHHW\n{pk_t:%d %b %H:%M} UTC",
        xy=(pk_t, pk_v),
        xytext=(14, -6),
        textcoords="offset points",
        fontsize=9.5,
        color=INK,
        va="top",
    )
    ax1.text(
        pass_time,
        ax1.get_ylim()[0] + 0.05,
        f"  Ian's centre {pass_km:.0f} km from the gauge, "
        f"{pass_time:%d %b %H:%M} UTC (best track)",
        fontsize=9,
        color=MUTED,
        va="bottom",
    )
    ax1.set_ylabel("Water level above MHHW (m)", fontsize=11, color=INK)
    ax1.set_title(
        f"(a)  Coast — CO-OPS Fort Myers ({COAST_STATION}), 6-min observed",
        fontsize=11,
        color=INK,
        loc="left",
        pad=8,
    )

    # ---- (b) the rivers ----------------------------------------------------- #
    colors = (SERIES_2, SERIES_3)
    # Label placement: the first river's label sits beside its crest; the
    # second's goes in the open upper right (axes fraction) with a leader line,
    # clear of the first river's recession limb.
    label_at = (None, (0.63, 0.60))
    for river, color, at in zip(rivers, colors, label_at):
        days = [d + timedelta(hours=12) for d in river["days"]]  # mid-day
        ax2.plot(
            days,
            river["cms"],
            color=color,
            lw=2,
            marker="o",
            ms=4,
            mec="white",
            mew=0.6,
            label=river["label"],
            zorder=3,
        )
        i = river["cms"].index(max(river["cms"]))
        if river["rank"] == 1:
            record = f"largest of {river['n_peaks']} on record"
        else:
            record = f"rank {river['rank']} of {river['n_peaks']} on record"
        ax2.annotate(
            f"{river['label']}: crest {river['days'][i]:%d %b}, "
            f"{river['cms'][i]:,.0f} m³/s daily mean\n"
            f"annual peak {river['peak_cfs']:,.0f} ft³/s — {record}",
            xy=(days[i], river["cms"][i]),
            xytext=(16, 4) if at is None else at,
            textcoords="offset points" if at is None else "axes fraction",
            fontsize=9.5,
            color=INK,
            va="center",
            arrowprops=None
            if at is None
            else dict(arrowstyle="-", color=MUTED, lw=0.8, shrinkB=4),
        )
    ax2.set_ylim(0, max(max(r["cms"]) for r in rivers) * 1.3)
    ax2.set_ylabel("Daily mean discharge (m³/s)", fontsize=11, color=INK)
    ax2.set_title(
        "(b)  Rivers — USGS daily mean discharge (local days)",
        fontsize=11,
        color=INK,
        loc="left",
        pad=8,
    )
    ax2.legend(loc="upper left", fontsize=9.5, frameon=False, labelcolor=MUTED)
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax2.set_xlabel("2022 (UTC)", fontsize=11, color=INK)

    fig.suptitle(
        "Hurricane Ian (2022) — the coast floods first, the rivers days later",
        fontsize=13,
        color=INK,
        x=0.07,
        ha="left",
    )
    fig.text(
        0.07,
        0.012,
        "Sources: NOAA HURDAT2 via nhc_get_best_track; NOAA CO-OPS via "
        "coops_get_water_levels; USGS NWIS via usgs_get_daily_values / "
        "usgs_get_peak_streamflow.",
        fontsize=8.5,
        color=MUTED,
        ha="left",
    )
    fig.subplots_adjust(left=0.07, right=0.985, top=0.91, bottom=0.11)
    fig.savefig(out_path, dpi=100, facecolor="white")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
async def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n_calls = 3 + 2 * len(RIVERS)
    step = 0

    def say(msg: str) -> None:
        nonlocal step
        step += 1
        print(f"[{step}/{n_calls}] {msg}")

    # ---- 1. Best track ------------------------------------------------------ #
    say(f"MCP → nhc-mcp   : nhc_get_best_track ({STORM_ID})")
    bt = _parse_json_or_die(
        await call_mcp_tool(
            "servers/nhc-mcp",
            "nhc_mcp",
            "nhc_get_best_track",
            {"storm_id": STORM_ID, "response_format": "json"},
        ),
        "nhc_get_best_track",
    )
    track = [
        (datetime.strptime(p["datetime"], "%Y%m%d %H%M UTC"), p["lat"], p["lon"])
        for p in bt.get("track_points", [])
    ]
    if len(track) < 2:
        sys.exit("Best track returned too few points.")
    print(f"      {len(track)} track points, source {bt.get('source')}")

    # ---- 2. Fort Myers gauge position -------------------------------------- #
    say(f"MCP → coops-mcp : coops_get_station ({COAST_STATION})")
    info = await call_mcp_tool(
        "servers/coops-mcp",
        "coops_mcp",
        "coops_get_station",
        {"station_id": COAST_STATION},
    )
    lat = _search_or_die(r"\*\*Latitude\*\*:\s*([-\d.]+)", info, "station latitude")
    lon = _search_or_die(r"\*\*Longitude\*\*:\s*([-\d.]+)", info, "station longitude")
    pass_time, pass_km = closest_approach(track, lat, lon)
    print(f"      closest approach {pass_time:%Y-%m-%d %H:%M} UTC, {pass_km:.0f} km")

    # ---- 3. Fort Myers water level above MHHW ------------------------------ #
    say(f"MCP → coops-mcp : coops_get_water_levels ({COAST_STATION}, MHHW, 6-min)")
    coops = _parse_json_or_die(
        await call_mcp_tool(
            "servers/coops-mcp",
            "coops_mcp",
            "coops_get_water_levels",
            {
                "station_id": COAST_STATION,
                "begin_date": START,
                "end_date": END,
                "datum": "MHHW",
                "units": "metric",
                "interval": "6",
                "time_zone": "gmt",
                "response_format": "json",
                "max_records": 5000,
            },
        ),
        "coops_get_water_levels",
    )
    coast: list[tuple[datetime, float]] = []
    for rec in coops.get("data", {}).get("data", []):
        try:
            coast.append((datetime.strptime(rec["t"], TIME_FMT), float(rec["v"])))
        except (KeyError, TypeError, ValueError):
            continue
    if not coast:
        sys.exit(f"CO-OPS returned no usable observations for {COAST_STATION}.")
    coast_peak = max(coast, key=lambda p: p[1])
    print(
        f"      {len(coast)} obs; peak {coast_peak[1]:.3f} m above MHHW at "
        f"{coast_peak[0]:%Y-%m-%d %H:%M} UTC"
    )

    # ---- 4-5. Rivers -------------------------------------------------------- #
    rivers: list[dict[str, Any]] = []
    for site, label in RIVERS:
        say(f"MCP → usgs-mcp  : usgs_get_daily_values ({site}, discharge)")
        dv = _parse_json_or_die(
            await call_mcp_tool(
                "servers/usgs-mcp",
                "usgs_mcp",
                "usgs_get_daily_values",
                {
                    "site_number": site,
                    "start_date": START,
                    "end_date": END,
                    "parameter_code": "00060",
                    "response_format": "json",
                },
            ),
            "usgs_get_daily_values",
        )
        series = dv["data"]["value"]["timeSeries"][0]
        days, cms = [], []
        for v in series["values"][0]["value"]:
            q = float(v["value"])
            if q <= -999999:
                continue
            days.append(datetime.strptime(v["dateTime"][:10], "%Y-%m-%d"))
            cms.append(q * CFS_TO_CMS)
        if not days:
            sys.exit(f"USGS returned no daily values for {site}.")

        say(f"MCP → usgs-mcp  : usgs_get_peak_streamflow ({site})")
        peaks = _parse_json_or_die(
            await call_mcp_tool(
                "servers/usgs-mcp",
                "usgs_mcp",
                "usgs_get_peak_streamflow",
                {"site_number": site, "response_format": "json"},
            ),
            "usgs_get_peak_streamflow",
        )
        annual = [
            (p["peak_dt"], float(p["peak_va"]), p.get("peak_cd", ""))
            for p in peaks
            if p.get("peak_va", "").strip()
        ]
        ian = [a for a in annual if START <= a[0] <= END]
        if not ian:
            sys.exit(f"No annual peak inside {START}..{END} for {site}.")
        peak_dt, peak_cfs, peak_cd = max(ian, key=lambda a: a[1])
        rank = 1 + sum(1 for a in annual if a[1] > peak_cfs)
        i = cms.index(max(cms))
        print(
            f"      {series['sourceInfo']['siteName']}: crest {days[i]:%Y-%m-%d} "
            f"({max(cms) / CFS_TO_CMS:,.0f} ft3/s daily mean); annual peak "
            f"{peak_cfs:,.0f} ft3/s on {peak_dt}, rank {rank} of {len(annual)}"
        )
        rivers.append(
            {
                "site": site,
                "label": label,
                "site_name": series["sourceInfo"]["siteName"],
                "days": days,
                "cms": cms,
                "peak_dt": peak_dt,
                "peak_cfs": peak_cfs,
                "peak_cd": peak_cd,
                "rank": rank,
                "n_peaks": len(annual),
            }
        )

    stem = "ian_coast_to_river_flooding"
    png = out_dir / f"{stem}.png"
    make_plot(
        [t for t, _ in coast],
        [v for _, v in coast],
        coast_peak,
        pass_time,
        pass_km,
        rivers,
        png,
    )
    (out_dir / f"{stem}.json").write_text(
        json.dumps(
            {
                "storm_id": STORM_ID,
                "window": [START, END],
                "coast": {
                    "station_id": COAST_STATION,
                    "datum": "MHHW",
                    "lat": lat,
                    "lon": lon,
                    "closest_approach_utc": pass_time.strftime(TIME_FMT),
                    "closest_approach_km": round(pass_km, 1),
                    "peak_m_above_mhhw": coast_peak[1],
                    "peak_time_utc": coast_peak[0].strftime(TIME_FMT),
                },
                "rivers": [
                    {
                        "site": r["site"],
                        "site_name": r["site_name"],
                        "annual_peak": {
                            "date": r["peak_dt"],
                            "discharge_cfs": r["peak_cfs"],
                            "peak_code": r["peak_cd"],
                            "rank": r["rank"],
                            "n_annual_peaks": r["n_peaks"],
                        },
                        "daily_mean_cms": {
                            d.strftime("%Y-%m-%d"): round(q, 1)
                            for d, q in zip(r["days"], r["cms"])
                        },
                    }
                    for r in rivers
                ],
            },
            indent=2,
        )
    )
    print(f"\nwrote {png}\nwrote {out_dir / f'{stem}.json'}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parent),
        help="Where to write the PNG and JSON (default: examples/).",
    )
    return asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
