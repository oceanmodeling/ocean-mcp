#!/usr/bin/env python3
"""Regional vs global: CBOFS and STOFS-2D-Global against the Baltimore gauge.

NOAA runs a regional model for Chesapeake Bay (CBOFS, ROMS) and a global
surge model (STOFS-2D-Global, ADCIRC) that also writes output at the same
tide gauge. This example scores both against the CO-OPS gauge at Baltimore
over the same hours, on the same datum.

It spawns three ocean-mcp servers as MCP stdio subprocesses (the same
`uv run` lines as .mcp.json) and chains four tool calls:

  1. ofs-mcp    ofs_compare_with_coops      CBOFS vs the gauge, last 48 h, on
                                            NAVD88 (hourly)
  2. coops-mcp  coops_get_datums            the gauge's NAVD88 -> MSL offset
  3. stofs-mcp  stofs_get_station_forecast  STOFS-2D-Global (LMSL) from the
                                            cycle whose nowcast covers the window
  4. coops-mcp  coops_get_water_levels      the gauge on MSL, 6-min

CBOFS is moved from NAVD88 to MSL with the gauge's datum sheet, so both
models are scored against one gauge series on one datum, at the same hourly
times. As a check, the gauge readings ofs_compare_with_coops returned on
NAVD88, shifted the same way, must match the MSL readings from step 4.

Verified against the live services (2026-10-04, Baltimore 8574680)
-----------------------------------------------------------------
The CBOFS grid cell used is the nearest water cell, 1.16 km from the gauge.
STOFS-2D-Global's station output for 8574680 sits at the gauge (the
stofs_list_stations table is a curated subset; the station file has it).
The gauge's datum sheet puts MSL 0.010 m above NAVD88, and the shifted
NAVD88 gauge readings match the MSL readings to 0.0 cm. For the committed
run (2026-10-02 23z to 2026-10-04 22z, 48 hourly points; STOFS cycle
2026-10-03 00z): CBOFS bias +0.053 m, RMSE 0.084 m, R 0.957; STOFS-2D-Global
bias -0.040 m, RMSE 0.064 m, R 0.978. The default window ends now, so a
fresh run scores a different 48 hours.

Usage
-----
    python3 examples/baltimore_cbofs_vs_stofs2d.py
    python3 examples/baltimore_cbofs_vs_stofs2d.py --hours 72

Requires: mcp, matplotlib, numpy; `uv` on PATH (servers launched with
`uv run --directory ...`, same as .mcp.json).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parent.parent
TIME_FMT = "%Y-%m-%d %H:%M"  # OFS, STOFS and CO-OPS all emit this format
CALL_TIMEOUT_S = 300.0
STATION = "8574680"  # Baltimore, Fort McHenry

SERIES_1 = "#2a78d6"  # blue   — categorical slot 1 (gauge)
SERIES_2 = "#eb6834"  # orange — categorical slot 2 (CBOFS)
SERIES_3 = "#1baf7a"  # aqua   — categorical slot 3 (STOFS-2D-Global)
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


def _parse_json_or_die(text: str, what: str) -> dict[str, Any]:
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


def compute_stats(model: list[float], obs: list[float]) -> dict[str, float]:
    """Bias, RMSE, MAE, peak |error| and Pearson R for two aligned series."""
    import numpy as np

    m = np.asarray(model, dtype=float)
    o = np.asarray(obs, dtype=float)
    err = m - o
    r = float(np.corrcoef(m, o)[0, 1]) if len(m) > 1 else float("nan")
    return {
        "bias": round(float(err.mean()), 4),
        "rmse": round(float(np.sqrt((err**2).mean())), 4),
        "mae": round(float(np.abs(err).mean()), 4),
        "peak_error": round(float(np.abs(err).max()), 4),
        "correlation": round(r, 4),
        "n": int(len(m)),
    }


def stofs_cycle_covering(start: datetime) -> tuple[str, str]:
    """Latest STOFS-2D-Global cycle whose file (nowcast from cycle - 6 h) covers start."""
    t = start + timedelta(hours=6)
    cycle = t.replace(hour=t.hour - t.hour % 6, minute=0, second=0, microsecond=0)
    return cycle.strftime("%Y-%m-%d"), cycle.strftime("%H")


# --------------------------------------------------------------------------- #
# Plot
# --------------------------------------------------------------------------- #
def make_plot(
    t: list[datetime],
    obs: list[float],
    cbofs: list[float],
    stofs: list[float],
    cb_stats: dict[str, float],
    st_stats: dict[str, float],
    cb_dist_km: float,
    stofs_cycle: str,
    out_path: Path,
) -> None:
    """Top: water level on MSL. Bottom: model minus gauge.

    figsize (12, 8.5) at dpi=100 -> 1200x850 px, under the 1600 px rule.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(12, 8.5),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 2], "hspace": 0.28},
    )
    for ax in (ax1, ax2):
        ax.grid(True, color=GRID, lw=0.7)
        ax.tick_params(colors=MUTED)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.axhline(0, color=MUTED, lw=0.8, ls=":")

    cb_label = f"CBOFS (regional, ROMS; grid cell {cb_dist_km:.1f} km away)"
    st_label = f"STOFS-2D-Global (global, ADCIRC; cycle {stofs_cycle})"
    ax1.plot(t, obs, color=SERIES_1, lw=2.2, label="CO-OPS gauge (observed)", zorder=3)
    ax1.plot(t, cbofs, color=SERIES_2, lw=1.6, ls="--", label=cb_label, zorder=4)
    ax1.plot(t, stofs, color=SERIES_3, lw=1.6, ls="-.", label=st_label, zorder=4)
    lo = min(min(obs), min(cbofs), min(stofs))
    hi = max(max(obs), max(cbofs), max(stofs))
    span = hi - lo
    ax1.set_ylim(lo - 0.08 * span, hi + 0.55 * span)
    ax1.set_ylabel("Water level, MSL (m)", fontsize=11, color=INK)
    ax1.set_title(
        "(a)  Water level — both models and the gauge on MSL, hourly",
        fontsize=11,
        color=INK,
        loc="left",
        pad=8,
    )
    ax1.legend(loc="upper left", fontsize=9, frameon=False, labelcolor=MUTED)

    cb_err = [m - o for m, o in zip(cbofs, obs)]
    st_err = [m - o for m, o in zip(stofs, obs)]
    ax2.plot(t, cb_err, color=SERIES_2, lw=1.8, label="CBOFS − gauge", zorder=3)
    ax2.plot(t, st_err, color=SERIES_3, lw=1.8, label="STOFS-2D − gauge", zorder=3)
    elo, ehi = min(cb_err + st_err), max(cb_err + st_err)
    espan = max(ehi - elo, 0.1)
    ax2.set_ylim(elo - 0.1 * espan, ehi + 0.7 * espan)
    ax2.set_ylabel("Model − gauge (m)", fontsize=11, color=INK)
    ax2.set_title(
        "(b)  Error — same hours, same gauge",
        fontsize=11,
        color=INK,
        loc="left",
        pad=8,
    )
    ax2.legend(loc="upper left", fontsize=9, frameon=False, labelcolor=MUTED)
    ax2.text(
        0.985,
        0.95,
        (
            f"{'':10s}{'CBOFS':>9s}{'STOFS-2D':>10s}\n"
            f"{'Bias (m)':10s}{cb_stats['bias']:>+9.3f}{st_stats['bias']:>+10.3f}\n"
            f"{'RMSE (m)':10s}{cb_stats['rmse']:>9.3f}{st_stats['rmse']:>10.3f}\n"
            f"{'R':10s}{cb_stats['correlation']:>9.3f}"
            f"{st_stats['correlation']:>10.3f}\n"
            f"{'N':10s}{cb_stats['n']:>9d}{st_stats['n']:>10d}"
        ),
        transform=ax2.transAxes,
        fontsize=9,
        va="top",
        ha="right",
        family="monospace",
        color=INK,
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=GRID, alpha=0.9),
    )
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%Hz"))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    ax2.set_xlabel("Time (UTC)", fontsize=11, color=INK)

    fig.suptitle(
        f"Baltimore ({STATION}) — regional CBOFS vs global STOFS-2D against "
        f"the gauge, {t[0]:%d %b %H}z – {t[-1]:%d %b %H}z",
        fontsize=13,
        color=INK,
        x=0.07,
        ha="left",
    )
    fig.text(
        0.07,
        0.012,
        "Sources: NOAA CBOFS via ofs_compare_with_coops; NOAA STOFS-2D-Global via "
        "stofs_get_station_forecast; NOAA CO-OPS via coops_get_water_levels /\n"
        "coops_get_datums. CBOFS moved from NAVD88 to MSL with the gauge's datum "
        "sheet.",
        fontsize=8.5,
        color=MUTED,
        ha="left",
    )
    fig.subplots_adjust(left=0.07, right=0.985, top=0.91, bottom=0.12)
    fig.savefig(out_path, dpi=100, facecolor="white")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
async def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. CBOFS vs the gauge (NAVD88) ------------------------------------ #
    print(
        f"[1/4] MCP → ofs-mcp   : ofs_compare_with_coops "
        f"({STATION}, cbofs, {args.hours} h)"
    )
    cb = _parse_json_or_die(
        await call_mcp_tool(
            "servers/ofs-mcp",
            "ofs_mcp",
            "ofs_compare_with_coops",
            {
                "station_id": STATION,
                "model": "cbofs",
                "hours_to_compare": args.hours,
                "response_format": "json",
            },
        ),
        "ofs_compare_with_coops",
    )
    cb_times = cb.get("comparison_times") or []
    if not cb_times:
        sys.exit("ofs_compare_with_coops returned no aligned series.")
    print(
        f"      {len(cb_times)} hourly points, {cb_times[0]} → {cb_times[-1]} UTC; "
        f"CBOFS {cb.get('model_datum')}, gauge {cb.get('obs_datum')}, "
        f"grid cell {cb.get('model_grid_distance_km')} km away"
    )

    # ---- 2. Gauge datum sheet: NAVD88 -> MSL ------------------------------- #
    print(f"[2/4] MCP → coops-mcp : coops_get_datums ({STATION})")
    sheet = await call_mcp_tool(
        "servers/coops-mcp",
        "coops_mcp",
        "coops_get_datums",
        {"station_id": STATION, "units": "metric"},
    )
    navd = _search_or_die(r"\|\s*NAVD88\s*\|\s*([-\d.]+)", sheet, "NAVD88")
    msl = _search_or_die(r"\|\s*MSL\s*\|\s*([-\d.]+)", sheet, "MSL")
    navd_to_msl = navd - msl  # add to a NAVD88 height to get an MSL height
    print(f"      MSL height = NAVD88 height {navd_to_msl:+.3f} m")

    # ---- 3. STOFS-2D-Global (LMSL) ----------------------------------------- #
    start = datetime.strptime(cb_times[0], TIME_FMT)
    end = datetime.strptime(cb_times[-1], TIME_FMT)
    cyc_date, cyc_hour = stofs_cycle_covering(start)
    print(
        f"[3/4] MCP → stofs-mcp : stofs_get_station_forecast "
        f"({STATION}, 2d_global, {cyc_date} {cyc_hour}z)"
    )
    st = _parse_json_or_die(
        await call_mcp_tool(
            "servers/stofs-mcp",
            "stofs_mcp",
            "stofs_get_station_forecast",
            {
                "station_id": STATION,
                "model": "2d_global",
                "cycle_date": cyc_date,
                "cycle_hour": cyc_hour,
                "response_format": "json",
            },
        ),
        "stofs_get_station_forecast",
    )
    stofs = {
        t: v for t, v in zip(st.get("times", []), st.get("values", [])) if v is not None
    }
    print(f"      STOFS {st.get('datum')} pts={len(stofs)}")

    # ---- 4. The gauge on MSL ------------------------------------------------ #
    print(f"[4/4] MCP → coops-mcp : coops_get_water_levels ({STATION}, MSL, 6-min)")
    co = _parse_json_or_die(
        await call_mcp_tool(
            "servers/coops-mcp",
            "coops_mcp",
            "coops_get_water_levels",
            {
                "station_id": STATION,
                "begin_date": start.strftime("%Y-%m-%d"),
                "end_date": (end + timedelta(days=1)).strftime("%Y-%m-%d"),
                "datum": "MSL",
                "units": "metric",
                "interval": "6",
                "time_zone": "gmt",
                "response_format": "json",
                "max_records": 5000,
            },
        ),
        "coops_get_water_levels",
    )
    gauge_msl: dict[str, float] = {}
    for rec in co.get("data", {}).get("data", []):
        try:
            gauge_msl[rec["t"]] = float(rec["v"])
        except (KeyError, TypeError, ValueError):
            continue

    # ---- Align on the CBOFS hours ------------------------------------------ #
    rows = []
    for t, cbm, cbo in zip(cb_times, cb["model_values"], cb["obs_values"]):
        if t in stofs and t in gauge_msl and cbm is not None and cbo is not None:
            rows.append(
                (t, cbm + navd_to_msl, cbo + navd_to_msl, stofs[t], gauge_msl[t])
            )
    if len(rows) < 12:
        sys.exit(f"Only {len(rows)} hours where all three series overlap.")
    times = [r[0] for r in rows]
    cbofs_msl = [round(r[1], 4) for r in rows]
    stofs_msl = [r[3] for r in rows]
    obs = [r[4] for r in rows]
    check = max(abs(r[2] - r[4]) for r in rows)
    print(
        f"\n      gauge check: ofs gauge (NAVD88 → MSL) vs CO-OPS MSL, "
        f"max |difference| {check * 100:.1f} cm over {len(rows)} hours"
    )
    cb_stats = compute_stats(cbofs_msl, obs)
    st_stats = compute_stats(stofs_msl, obs)
    for name, s in (("CBOFS", cb_stats), ("STOFS-2D", st_stats)):
        print(
            f"      {name:9s}: bias {s['bias']:+.3f} m  RMSE {s['rmse']:.3f} m  "
            f"R {s['correlation']:.3f}  (n={s['n']})"
        )

    stem = f"baltimore_cbofs_vs_stofs2d_{STATION}"
    png = out_dir / f"{stem}.png"
    make_plot(
        [datetime.strptime(s, TIME_FMT) for s in times],
        obs,
        cbofs_msl,
        stofs_msl,
        cb_stats,
        st_stats,
        float(cb.get("model_grid_distance_km") or 0.0),
        f"{cyc_date} {cyc_hour}z",
        png,
    )
    (out_dir / f"{stem}.json").write_text(
        json.dumps(
            {
                "station_id": STATION,
                "station_name": cb.get("station_name"),
                "window_utc": [times[0], times[-1]],
                "datum": "MSL",
                "navd88_to_msl_m": round(navd_to_msl, 4),
                "cbofs_grid_distance_km": cb.get("model_grid_distance_km"),
                "stofs_cycle": f"{cyc_date} {cyc_hour}z",
                "gauge_check_max_abs_diff_m": round(check, 4),
                "statistics": {"cbofs": cb_stats, "stofs_2d_global": st_stats},
                "series": {
                    "time": times,
                    "gauge_msl": obs,
                    "cbofs_msl": cbofs_msl,
                    "stofs_2d_global_lmsl": stofs_msl,
                },
            },
            indent=2,
        )
    )
    print(f"\nwrote {png}\nwrote {out_dir / f'{stem}.json'}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--hours",
        type=int,
        default=48,
        help="Hours to compare, ending now (default 48, max 96).",
    )
    p.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parent),
        help="Where to write the PNG and JSON (default: examples/).",
    )
    return asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
