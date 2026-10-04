#!/usr/bin/env python3
"""Same water, two datums — put a CO-OPS gauge on the STOFS-3D datum with VDatum.

STOFS-3D-Atlantic reports water level relative to NAVD88. A CO-OPS gauge is
most often pulled relative to MLLW, the chart datum. Plot the two together as
fetched and the model looks ~1 m low; the gap is the datum, not the model.

This example spawns three ocean-mcp servers as MCP stdio subprocesses (the same
`uv run` lines as .mcp.json) and chains five tool calls:

  1. stofs-mcp   stofs_get_station_forecast  STOFS-3D-Atlantic water level (NAVD88)
  2. coops-mcp   coops_get_water_levels      CO-OPS observed water level (MLLW)
  3. coops-mcp   coops_get_station           gauge latitude / longitude
  4. vdatum-mcp  vdatum_convert              MLLW -> NAVD88 offset at the gauge
  5. coops-mcp   coops_get_datums            the gauge's own datum sheet, as an
                                             independent check on step 4

The top panel compares the series as fetched; the bottom panel shifts the
observations onto NAVD88 with the VDatum offset and compares again.

Verified against the live services (2026-10-03, Charleston SC 8665530)
---------------------------------------------------------------------
vdatum_convert puts MLLW at -0.968 m NAVD88. The CO-OPS datum sheet gives
NAVD88 = 1.800 m and MLLW = 0.843 m above station datum, i.e. MLLW at
-0.957 m NAVD88. The two independent offsets agree to about 1 cm.

For the 2026-10-01 12z cycle the comparison as fetched shows a -0.753 m bias;
on NAVD88 it is +0.215 m. That remaining ~0.2 m is the model, not the datum:
stofs_compare_with_observations, which requests the gauge from CO-OPS directly
in NAVD, reports +0.203 m for the same cycle and window (the 1.2 cm gap is
the VDatum vs datum-sheet difference above).

Usage
-----
    python3 examples/charleston_vdatum_stofs3d_vs_coops.py
    python3 examples/charleston_vdatum_stofs3d_vs_coops.py --station 8670870 \
            --cycle-date 2026-09-30

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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parent.parent
TIME_FMT = "%Y-%m-%d %H:%M"  # STOFS + CO-OPS emit this exact format
CALL_TIMEOUT_S = 240.0

SERIES_1 = "#2a78d6"  # blue   — categorical slot 1 (CO-OPS observed)
SERIES_2 = "#eb6834"  # orange — categorical slot 2 (STOFS-3D)
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


# --------------------------------------------------------------------------- #
# Plot
# --------------------------------------------------------------------------- #
def make_plot(
    t: list[datetime],
    stofs: list[float],
    obs_mllw: list[float],
    obs_navd: list[float],
    raw_stats: dict[str, float],
    fixed_stats: dict[str, float],
    vdatum_offset: float,
    sheet_offset: float,
    station: str,
    name: str,
    cycle: str,
    out_path: Path,
) -> None:
    """Top: as fetched (NAVD88 vs MLLW). Bottom: both on NAVD88.

    figsize (12, 8.5) at dpi=100 -> 1200x850 px, under the 1600 px rule.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8.5), sharex=True, gridspec_kw={"hspace": 0.28}
    )

    panels = (
        (
            ax1,
            obs_mllw,
            "CO-OPS observed (MLLW, as fetched)",
            raw_stats,
            "(a)  As fetched — STOFS-3D on NAVD88, gauge on MLLW",
        ),
        (
            ax2,
            obs_navd,
            "CO-OPS observed (shifted to NAVD88 by vdatum_convert)",
            fixed_stats,
            f"(b)  Both on NAVD88 — gauge shifted by vdatum_convert "
            f"({vdatum_offset:+.3f} m; CO-OPS datum sheet {sheet_offset:+.3f} m, "
            f"{abs(vdatum_offset - sheet_offset) * 100:.1f} cm apart)",
        ),
    )
    for ax, obs, obs_label, stats, title in panels:
        lo = min(min(obs), min(stofs))
        hi = max(max(obs), max(stofs))
        span = hi - lo
        # Headroom above the tide so the legend and stats box sit on clear space.
        ax.set_ylim(lo - 0.08 * span, hi + 0.45 * span)
        ax.plot(t, obs, color=SERIES_1, lw=1.8, label=obs_label, zorder=3)
        ax.plot(
            t,
            stofs,
            color=SERIES_2,
            lw=1.6,
            ls="--",
            label="STOFS-3D-Atlantic (NAVD88)",
            zorder=4,
        )
        ax.axhline(0, color=MUTED, lw=0.8, ls=":")
        ax.set_ylabel("Water level (m)", fontsize=11, color=INK)
        ax.set_title(title, fontsize=11, color=INK, loc="left", pad=8)
        ax.grid(True, color=GRID, lw=0.7)
        ax.tick_params(colors=MUTED)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.legend(loc="upper left", fontsize=9, frameon=False, labelcolor=MUTED)
        ax.text(
            0.985,
            0.96,
            (
                f"STOFS − gauge\n"
                f"Bias: {stats['bias']:+.3f} m\n"
                f"RMSE: {stats['rmse']:.3f} m\n"
                f"R:    {stats['correlation']:.3f}\n"
                f"N:    {stats['n']}"
            ),
            transform=ax.transAxes,
            fontsize=9,
            va="top",
            ha="right",
            family="monospace",
            color=INK,
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=GRID, alpha=0.9),
        )

    fig.suptitle(
        f"{name} ({station}) — same water, two datums  |  STOFS-3D cycle {cycle}",
        fontsize=13,
        color=INK,
        x=0.065,
        ha="left",
    )
    ax2.set_xlabel("Time (UTC)", fontsize=11, color=INK)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%Hz"))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=12))
    fig.text(
        0.065,
        0.012,
        "Sources: NOAA STOFS-3D-Atlantic via stofs_get_station_forecast; NOAA "
        "CO-OPS via coops_get_water_levels / coops_get_datums; NOAA VDatum grids "
        "via vdatum_convert.",
        fontsize=8.5,
        color=MUTED,
        ha="left",
    )
    fig.subplots_adjust(left=0.065, right=0.985, top=0.91, bottom=0.12)
    fig.savefig(out_path, dpi=100, facecolor="white")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
async def run(args: argparse.Namespace) -> int:
    station = args.station
    cycle_date = args.cycle_date or (
        datetime.now(timezone.utc) - timedelta(days=3)
    ).strftime("%Y-%m-%d")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. STOFS-3D-Atlantic (NAVD88) ------------------------------------- #
    print(
        f"[1/5] MCP → stofs-mcp  : stofs_get_station_forecast "
        f"({station}, 3d_atlantic, {cycle_date} 12z)"
    )
    stofs = _parse_json_or_die(
        await call_mcp_tool(
            "servers/stofs-mcp",
            "stofs_mcp",
            "stofs_get_station_forecast",
            {
                "station_id": station,
                "model": "3d_atlantic",
                "cycle_date": cycle_date,
                "cycle_hour": "12",
                "response_format": "json",
            },
        ),
        "stofs_get_station_forecast",
    )
    if not stofs.get("times"):
        sys.exit("STOFS-3D returned an empty series for this station/cycle.")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    t0 = datetime.strptime(stofs["times"][0], TIME_FMT)
    horizon = min(now, t0 + timedelta(hours=args.max_hours))
    model = {
        t: v
        for t, v in zip(stofs["times"], stofs["values"])
        if v is not None and datetime.strptime(t, TIME_FMT) <= horizon
    }
    if not model:
        sys.exit(
            "STOFS cycle too recent for an observation overlap — use an older one."
        )
    win_start = datetime.strptime(min(model), TIME_FMT)
    win_end = datetime.strptime(max(model), TIME_FMT)
    print(
        f"      STOFS {stofs.get('datum')} pts={len(model)} "
        f"window {win_start:%Y-%m-%d %H:%M} → {win_end:%Y-%m-%d %H:%M} UTC"
    )

    # ---- 2. CO-OPS observed, MLLW (the usual request) ---------------------- #
    print(f"[2/5] MCP → coops-mcp  : coops_get_water_levels ({station}, MLLW, 6-min)")
    coops = _parse_json_or_die(
        await call_mcp_tool(
            "servers/coops-mcp",
            "coops_mcp",
            "coops_get_water_levels",
            {
                "station_id": station,
                "begin_date": win_start.strftime("%Y-%m-%d"),
                "end_date": (win_end + timedelta(days=1)).strftime("%Y-%m-%d"),
                "datum": "MLLW",
                "units": "metric",
                "interval": "6",
                "time_zone": "gmt",
                "response_format": "json",
            },
        ),
        "coops_get_water_levels",
    )
    obs_mllw: dict[str, float] = {}
    for rec in coops.get("data", {}).get("data", []):
        try:
            obs_mllw[rec["t"]] = float(rec["v"])
        except (KeyError, TypeError, ValueError):
            continue
    if not obs_mllw:
        sys.exit(f"CO-OPS returned no usable observations for {station}.")
    print(f"      CO-OPS MLLW observations={len(obs_mllw)}")

    # ---- 3. Gauge position ------------------------------------------------- #
    print(f"[3/5] MCP → coops-mcp  : coops_get_station ({station})")
    info = await call_mcp_tool(
        "servers/coops-mcp",
        "coops_mcp",
        "coops_get_station",
        {"station_id": station},
    )
    lat = _search_or_die(r"\*\*Latitude\*\*:\s*([-\d.]+)", info, "station latitude")
    lon = _search_or_die(r"\*\*Longitude\*\*:\s*([-\d.]+)", info, "station longitude")
    name_m = re.search(r"\*\*Name\*\*:\s*(.+)", info)
    state_m = re.search(r"\*\*State\*\*:\s*(.+)", info)
    name = name_m.group(1).strip() if name_m else station
    if state_m:
        name = f"{name}, {state_m.group(1).strip()}"
    print(f"      {name} at {lat:.4f}, {lon:.4f}")

    # ---- 4. VDatum: MLLW -> NAVD88 offset at the gauge --------------------- #
    print("[4/5] MCP → vdatum-mcp : vdatum_convert (mllw → navd88, z=0)")
    conv = await call_mcp_tool(
        "servers/vdatum-mcp",
        "vdatum_mcp",
        "vdatum_convert",
        {
            "datum_from": "mllw",
            "datum_to": "navd88",
            "lat": f"{lat}",
            "lon": f"{lon}",
            "z": "0.0",
        },
    )
    vdatum_offset = _search_or_die(
        r"\*\*Output:\*\*\s*([-\d.]+)\s*m", conv, "the VDatum result"
    )
    print(f"      MLLW = {vdatum_offset:+.4f} m NAVD88 (VDatum)")

    # ---- 5. CO-OPS datum sheet, independent check -------------------------- #
    print(f"[5/5] MCP → coops-mcp  : coops_get_datums ({station})")
    sheet = await call_mcp_tool(
        "servers/coops-mcp",
        "coops_mcp",
        "coops_get_datums",
        {"station_id": station, "units": "metric"},
    )
    navd_above_stnd = _search_or_die(r"\|\s*NAVD88\s*\|\s*([-\d.]+)", sheet, "NAVD88")
    mllw_above_stnd = _search_or_die(r"\|\s*MLLW\s*\|\s*([-\d.]+)", sheet, "MLLW")
    sheet_offset = mllw_above_stnd - navd_above_stnd
    print(
        f"      MLLW = {sheet_offset:+.4f} m NAVD88 (datum sheet) — "
        f"differs from VDatum by {abs(vdatum_offset - sheet_offset) * 100:.1f} cm"
    )

    # ---- Align and compare -------------------------------------------------- #
    common = sorted(set(model) & set(obs_mllw))
    if len(common) < 10:
        sys.exit(f"Only {len(common)} overlapping timestamps — nothing to compare.")
    t = [datetime.strptime(s, TIME_FMT) for s in common]
    m = [model[s] for s in common]
    o_mllw = [obs_mllw[s] for s in common]
    o_navd = [v + vdatum_offset for v in o_mllw]
    raw_stats = compute_stats(m, o_mllw)
    fixed_stats = compute_stats(m, o_navd)
    print(
        f"\n      as fetched : bias {raw_stats['bias']:+.3f} m  "
        f"RMSE {raw_stats['rmse']:.3f} m"
        f"\n      on NAVD88  : bias {fixed_stats['bias']:+.3f} m  "
        f"RMSE {fixed_stats['rmse']:.3f} m  (n={fixed_stats['n']})"
    )

    cycle = f"{cycle_date} 12z"
    stem = f"charleston_vdatum_stofs3d_vs_coops_{station}"
    png = out_dir / f"{stem}.png"
    make_plot(
        t,
        m,
        o_mllw,
        o_navd,
        raw_stats,
        fixed_stats,
        vdatum_offset,
        sheet_offset,
        station,
        name,
        cycle,
        png,
    )
    (out_dir / f"{stem}.json").write_text(
        json.dumps(
            {
                "station_id": station,
                "station_name": name,
                "lat": lat,
                "lon": lon,
                "cycle": cycle,
                "stofs_datum": stofs.get("datum"),
                "coops_datum": "MLLW",
                "mllw_to_navd88_m": {
                    "vdatum_convert": round(vdatum_offset, 4),
                    "coops_datum_sheet": round(sheet_offset, 4),
                },
                "statistics": {"as_fetched": raw_stats, "on_navd88": fixed_stats},
                "series": {
                    "time": common,
                    "stofs_navd88": m,
                    "coops_mllw": o_mllw,
                    "coops_navd88_via_vdatum": [round(v, 4) for v in o_navd],
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
        "--station",
        default="8665530",
        help="CO-OPS station inside the STOFS-3D-Atlantic domain (default: "
        "8665530, Charleston SC).",
    )
    p.add_argument(
        "--cycle-date",
        default=None,
        help="STOFS-3D cycle date YYYY-MM-DD (12z). Default: three days ago, "
        "so the forecast overlaps observed data.",
    )
    p.add_argument(
        "--max-hours",
        type=int,
        default=72,
        help="Hours from the start of the STOFS series to compare (default 72).",
    )
    p.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parent),
        help="Where to write the PNG and JSON (default: examples/).",
    )
    return asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
