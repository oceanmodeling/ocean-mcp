"""Observed water level at two CO-OPS stations during Hurricane Ian's landfall.

Fort Myers (8725520) sits ~55 km southeast of the Cayo Costa landfall, in the
onshore-flow right-front quadrant, and records a +2.613 m MLLW surge. St.
Petersburg (8726520), ~130 km north, was under offshore flow and records a
-1.201 m negative surge (blowout) at almost the same moment.

Input is the saved JSON response of coops_get_water_levels for both stations
(fixed window 2022-09-27 to 2022-09-29, datum MLLW, 6-min interval), so this
replots without network access.
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
#   FIG_DPI=300 FIG_OUT=submission/figures python3 examples/ian_coops_surge_vs_blowout.py
DPI = int(os.environ.get("FIG_DPI", "100"))
OUTDIR = os.environ.get("FIG_OUT", "examples")

SERIES_1 = "#2a78d6"  # blue   — validated categorical slot 1
SERIES_2 = "#eb6834"  # orange — validated categorical slot 2
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#d8d7d2"

LANDFALL = datetime(2022, 9, 28, 19, 5)  # HURDAT2 'L', Cayo Costa FL, 130 kt

STATIONS = [
    ("8725520", SERIES_1, "surge"),
    ("8726520", SERIES_2, "blowout"),
]


def load():
    """Load the saved coops_get_water_levels responses."""
    with open("examples/ian_coops_water_levels.json") as fh:
        return json.load(fh)


def series(payload):
    """Extract (times, values) from one station's tool response."""
    records = payload["data"]["data"]
    times, values = [], []
    for rec in records:
        if rec.get("v") in (None, "", " "):
            continue
        times.append(datetime.strptime(rec["t"], "%Y-%m-%d %H:%M"))
        values.append(float(rec["v"]))
    return times, values


def main():
    payloads = load()

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.axhline(0, color=MUTED, linewidth=1, zorder=2)
    ax.annotate("MLLW", xy=(0.004, 0), xycoords=("axes fraction", "data"),
                xytext=(0, 4), textcoords="offset points",
                fontsize=9, color=MUTED, va="bottom")

    ax.axvline(LANDFALL, color=INK, linewidth=1.4, linestyle=(0, (5, 4)), zorder=3)
    ax.annotate(
        "Landfall\n2022-09-28 19:05 UTC\n130 kt · 941 mb",
        xy=(LANDFALL, 3.02),
        xytext=(-8, 0),
        textcoords="offset points",
        ha="right", va="top",
        fontsize=9.5, color=INK,
    )

    for station_id, color, _ in STATIONS:
        payload = payloads[station_id]
        name = payload["data"]["metadata"]["name"]
        times, values = series(payload)
        ax.plot(times, values, color=color, linewidth=2,
                label=f"{name} ({station_id})", zorder=4)

        peak_i = max(range(len(values)), key=lambda i: values[i])
        min_i = min(range(len(values)), key=lambda i: values[i])
        # Annotate whichever extreme is the storm response for this station.
        idx = peak_i if abs(values[peak_i]) > abs(values[min_i]) else min_i
        mark = values[idx]
        ax.plot([times[idx]], [mark], marker="o", markersize=9, color=color,
                markeredgecolor="white", markeredgewidth=1.6, zorder=6)
        offset = (16, 12) if mark > 0 else (16, -20)
        ax.annotate(
            f"{mark:+.3f} m MLLW\n{times[idx]:%b %d %H:%M} UTC",
            xy=(times[idx], mark),
            xytext=offset,
            textcoords="offset points",
            fontsize=9.5, color=INK,
            arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=1),
        )

        # Direct label at the end of each trace, so identity is never colour-alone.
        ax.annotate(
            name,
            xy=(times[-1], values[-1]),
            xytext=(6, 0),
            textcoords="offset points",
            fontsize=9.5, color=MUTED, va="center",
        )

    ax.set_ylabel("Observed water level (m, MLLW)", fontsize=10, color=MUTED)
    ax.set_xlabel("2022 (UTC)", fontsize=10, color=MUTED)
    ax.set_ylim(-1.8, 3.1)
    ax.set_xlim(datetime(2022, 9, 27), datetime(2022, 9, 30, 14))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))

    ax.grid(True, color=GRID, linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)

    ax.set_title(
        "Hurricane Ian (2022) — storm surge and negative surge, "
        "6-min verified water levels",
        fontsize=13, color=INK, loc="left", pad=12,
    )
    ax.legend(frameon=False, fontsize=9.5, loc="lower left", labelcolor=MUTED)

    fig.text(
        0.006, 0.015,
        "Source: NOAA CO-OPS via coops_get_water_levels "
        "(begin_date=2022-09-27, end_date=2022-09-29, datum=MLLW, interval=6). "
        "720 records per station, no gaps.",
        fontsize=8.5, color=MUTED, ha="left",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    out = os.path.join(OUTDIR, "ian_coops_surge_vs_blowout.png")
    fig.savefig(out, dpi=DPI, facecolor="white")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
