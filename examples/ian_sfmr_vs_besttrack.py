"""Compare SFMR-measured surface wind against the HURDAT2 best track for Ian (2022).

Panel (a): SFMR radial wind profile from the NOAA N42RF (P-3) mission of
2022-09-28, as returned by recon_get_sfmr.
Panel (b): HURDAT2 best-track intensity from nhc_get_best_track.

The headline: the SFMR peak of 67.1 m/s (130.4 kt) matches the best-track
landfall intensity of 130 kt to better than 1 kt — two independent archives,
two different servers.

Inputs are the saved JSON responses of the MCP tools, so this replots without
network access. They were produced with these fixed arguments:

  recon_get_sfmr      year=2022, storm_name="ian", storm_number=9, basin="al",
                      filename="NOAA_SFMR20220928H1.nc", bin_size_km=10,
                      max_radius_km=200, response_format="json"
                      -> examples/ian_sfmr_NOAA20220928H1.json
  nhc_get_best_track  storm_id="AL092022", response_format="json"
                      -> examples/ian_besttrack_AL092022.json
"""

import json
import os
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Default 100 dpi keeps the PNG under 1600 px for on-screen review.
# For print (>=300 dpi at 190 mm column width):
#   FIG_DPI=300 FIG_OUT=submission/figures python3 examples/ian_sfmr_vs_besttrack.py
DPI = int(os.environ.get("FIG_DPI", "100"))
OUTDIR = os.environ.get("FIG_OUT", "examples")

MS_PER_KT = 0.514444
LANDFALL_KT = 130  # HURDAT2, 2022-09-28 1905 UTC, Cayo Costa FL

SERIES_1 = "#2a78d6"  # blue   — validated categorical slot 1
SERIES_2 = "#eb6834"  # orange — validated categorical slot 2
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#d8d7d2"

# HURDAT2 flags landfall with record identifier 'L'. nhc_get_best_track parses
# that field but does not emit it, so the five landfall times below are taken
# from the raw HURDAT2 file rather than from the tool response.
LANDFALLS = [
    ("2022-09-27 08:30", 110, "W Cuba"),
    ("2022-09-28 02:00", 110, "Dry Tortugas"),
    ("2022-09-28 19:05", 130, "Cayo Costa, FL"),
    ("2022-09-28 20:35", 125, "Pirate Harbor, FL"),
    ("2022-09-30 18:05", 70, "Georgetown, SC"),
]


def load():
    """Load the saved SFMR and best-track tool responses."""
    with open("examples/ian_sfmr_NOAA20220928H1.json") as fh:
        sfmr = json.load(fh)
    with open("examples/ian_besttrack_AL092022.json") as fh:
        track = json.load(fh)
    return sfmr, track


def parse_track_time(s):
    """Parse a best-track datetime string like '20220928 1905 UTC'."""
    return datetime.strptime(s.replace(" UTC", ""), "%Y%m%d %H%M")


def plot_radial_profile(ax, mission):
    """Draw SFMR mean and max surface wind against radius from storm center."""
    bins = mission["profile"]
    centers = [(b["radius_min_km"] + b["radius_max_km"]) / 2 for b in bins]
    mean_ws = [b["mean_wind_ms"] for b in bins]
    max_ws = [b["max_wind_ms"] for b in bins]

    ax.axhline(
        LANDFALL_KT * MS_PER_KT,
        color=MUTED,
        linewidth=1.4,
        linestyle=(0, (6, 4)),
        zorder=2,
    )
    ax.annotate(
        f"HURDAT2 landfall intensity  {LANDFALL_KT} kt",
        xy=(202, LANDFALL_KT * MS_PER_KT),
        xytext=(0, -6),
        textcoords="offset points",
        ha="right",
        va="top",
        fontsize=9,
        color=MUTED,
    )

    ax.plot(centers, max_ws, color=SERIES_2, linewidth=2, marker="o", markersize=4,
            markeredgecolor="white", markeredgewidth=0.6, label="Max wind", zorder=4)
    ax.plot(centers, mean_ws, color=SERIES_1, linewidth=2, marker="o", markersize=4,
            markeredgecolor="white", markeredgewidth=0.6, label="Mean wind", zorder=3)

    peak_r = centers[max_ws.index(max(max_ws))]
    peak_w = max(max_ws)
    ax.plot([peak_r], [peak_w], marker="o", markersize=9, color=SERIES_2,
            markeredgecolor="white", markeredgewidth=1.6, zorder=5)
    ax.annotate(
        f"{peak_w:.1f} m/s  ({peak_w / MS_PER_KT:.1f} kt)\n{mission['peak_radius_km']} km radius",
        xy=(peak_r, peak_w),
        xytext=(28, 6),
        textcoords="offset points",
        fontsize=9.5,
        color=INK,
        arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=1),
    )

    ax.set_xlabel("Radius from storm center (km)", fontsize=10, color=MUTED)
    ax.set_ylabel("SFMR surface wind (m s$^{-1}$)", fontsize=10, color=MUTED)
    ax.set_xlim(0, 205)
    ax.set_ylim(0, 78)

    # Secondary scale is the same measure in knots — a unit conversion, not a
    # second data axis.
    kt_ax = ax.secondary_yaxis(
        "right", functions=(lambda v: v / MS_PER_KT, lambda v: v * MS_PER_KT)
    )
    kt_ax.set_ylabel("(kt)", fontsize=10, color=MUTED)
    kt_ax.tick_params(colors=MUTED, labelsize=9)

    ax.set_title(
        f"(a)  SFMR radial wind profile — {mission['aircraft']}, "
        f"{mission['n_obs']:,} obs",
        fontsize=11, color=INK, loc="left", pad=10,
    )
    ax.legend(frameon=False, fontsize=9.5, loc="upper right", labelcolor=MUTED)


def plot_intensity(ax, track, mission_date):
    """Draw best-track intensity over time with landfalls marked."""
    pts = track["track_points"]
    times = [parse_track_time(p["datetime"]) for p in pts]
    winds = [p["max_wind"] for p in pts]

    day_start = datetime.strptime(mission_date, "%Y%m%d")
    day_end = day_start.replace(hour=23, minute=59)
    ax.axvspan(day_start, day_end, color=SERIES_1, alpha=0.07, zorder=1)
    ax.annotate(
        "SFMR mission\n2022-09-28",
        xy=(day_start, 6),
        xytext=(4, 0),
        textcoords="offset points",
        fontsize=9,
        color=MUTED,
        va="bottom",
    )

    ax.plot(times, winds, color=SERIES_1, linewidth=2, zorder=3)

    lf_times = [datetime.strptime(t, "%Y-%m-%d %H:%M") for t, _, _ in LANDFALLS]
    lf_winds = [w for _, w, _ in LANDFALLS]
    ax.plot(lf_times, lf_winds, linestyle="none", marker="v", markersize=9,
            color=SERIES_2, markeredgecolor="white", markeredgewidth=1,
            label="Landfall (HURDAT2 'L')", zorder=5)

    lf_t = datetime.strptime("2022-09-28 19:05", "%Y-%m-%d %H:%M")
    ax.annotate(
        "Cayo Costa, FL\n2022-09-28 19:05 UTC\n130 kt · 941 mb",
        xy=(lf_t, LANDFALL_KT),
        xytext=(14, -46),
        textcoords="offset points",
        fontsize=9.5,
        color=INK,
        arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=1),
    )

    ax.set_ylabel("Best-track max wind (kt)", fontsize=10, color=MUTED)
    ax.set_ylim(0, 155)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.set_title(
        f"(b)  HURDAT2 best track — {track['storm_id']}, {track['count']} points",
        fontsize=11, color=INK, loc="left", pad=10,
    )
    ax.legend(frameon=False, fontsize=9.5, loc="upper left", labelcolor=MUTED)


def style(ax):
    """Apply recessive grid and axis styling."""
    ax.grid(True, color=GRID, linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)


def main():
    sfmr, track = load()
    mission = sfmr["missions"][0]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.4))
    plot_radial_profile(ax1, mission)
    plot_intensity(ax2, track, mission["date"])
    for ax in (ax1, ax2):
        style(ax)

    fig.suptitle(
        "Hurricane Ian (AL092022) — aircraft SFMR vs. HURDAT2 best track",
        fontsize=13, color=INK, x=0.006, ha="left", y=0.985,
    )
    fig.text(
        0.006, 0.015,
        "Sources: AOML HRD SFMR archive via recon_get_sfmr; NOAA HURDAT2 via "
        "nhc_get_best_track. Landfall times from raw HURDAT2 record identifier 'L'.",
        fontsize=8.5, color=MUTED, ha="left",
    )
    fig.tight_layout(rect=(0, 0.035, 1, 0.955))
    out = os.path.join(OUTDIR, "ian_sfmr_vs_besttrack.png")
    fig.savefig(out, dpi=DPI, facecolor="white")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
