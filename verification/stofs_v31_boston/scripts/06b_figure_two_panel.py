"""Step 6b: two-panel publication figure (supersedes the three-panel 06_figure.py).

Panel A: CO-OPS observations and the two STOFS forecasts over the common
0 < lead <= 48 h window. Panel B: signed errors (model - observation).
Statistics are a separate table (06c_statistics_table.py); metadata are in the
caption (figures/boston_stofs_v31_fig_caption.md). Sized for a 190 mm column
with every font >= 7 pt at final size. Reads results/statistics_independent.json.

Writes figures/boston_stofs_v31_fig.{pdf,svg}, a preview PNG (150 dpi,
<= 1600 px) and a 300 dpi PNG.

Usage: uv run --no-project --isolated --managed-python --python 3.13 --with-requirements requirements-analysis.txt \
           python scripts/06b_figure_two_panel.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

import _common as c  # noqa: E402

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SERIES = {"2d_global": "#2a78d6", "3d_atlantic": "#eb6834"}  # validated slots 1-2
STYLE = {"2d_global": "-", "3d_atlantic": (0, (5, 2))}  # second cue besides colour
LABEL = {"2d_global": "STOFS-2D-Global v3.1", "3d_atlantic": "STOFS-3D-Atlantic v3.1"}
WIDTH_IN = 190 / 25.4


def main() -> int:
    res = c.load_json(c.RESULTS / "statistics_independent.json")["results"]
    fc = {m: res[f"{m}_forecast"] for m in c.STOFS_FILES}
    t = [
        datetime.strptime(p["time"], "%Y-%m-%d %H:%M")
        for p in fc["2d_global"]["series"]
    ]
    obs = [p["obs_m"] for p in fc["2d_global"]["series"]]
    if [p["obs_m"] for p in fc["3d_atlantic"]["series"]] != obs:
        sys.exit("models must share valid times and observations")
    cycle = datetime.strptime(c.CYCLE_ISO, "%Y-%m-%d %H:%M")

    plt.rcParams.update(
        {
            "font.size": 8.5,
            "axes.titlesize": 9,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": INK,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )
    fig, (ax_a, ax_b) = plt.subplots(
        2,
        1,
        figsize=(WIDTH_IN, 5.2),
        sharex=True,
        gridspec_kw={"height_ratios": [1.5, 1.0], "hspace": 0.12},
    )

    ax_a.plot(
        t, obs, color=INK, lw=1.6, label="CO-OPS observed (preliminary)", zorder=4
    )
    for m in c.STOFS_FILES:
        ax_a.plot(
            t,
            [p["model_m"] for p in fc[m]["series"]],
            color=SERIES[m],
            lw=1.3,
            ls=STYLE[m],
            label=LABEL[m],
            zorder=3,
        )
    ax_a.set_ylabel("Water level (m)\nmodel LMSL / gauge MSL,\nno offset applied")
    ax_a.set_ylim(min(obs) - 0.4, max(obs) + 0.8)
    ax_a.legend(frameon=False, loc="upper left", ncol=3, handlelength=2.6)
    ax_a.text(
        -0.105,
        1.0,
        "A",
        transform=ax_a.transAxes,
        fontsize=10,
        fontweight="bold",
        va="top",
    )

    ax_b.axhline(0, color=MUTED, lw=0.8, zorder=1)
    for m in c.STOFS_FILES:
        ax_b.plot(
            t,
            [p["model_m"] - p["obs_m"] for p in fc[m]["series"]],
            color=SERIES[m],
            lw=1.2,
            ls=STYLE[m],
            label=LABEL[m],
        )
    ax_b.set_ylabel("Model − observed (m)")
    ax_b.legend(frameon=False, loc="lower right", ncol=2, handlelength=2.6)
    ax_b.text(
        -0.105,
        1.0,
        "B",
        transform=ax_b.transAxes,
        fontsize=10,
        fontweight="bold",
        va="top",
    )
    ax_b.set_xlabel("Valid time (UTC)")

    for ax in (ax_a, ax_b):
        ax.grid(color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    ax_a.set_xlim(t[0] - timedelta(minutes=30), t[-1] + timedelta(minutes=30))
    ax_b.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 12]))
    ax_b.xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 18]))
    ax_b.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %H:%M"))
    lead = ax_a.secondary_xaxis(
        "top",
        functions=(
            lambda x: (x - mdates.date2num(cycle)) * 24,
            lambda h: mdates.date2num(cycle) + h / 24,
        ),
    )
    lead.set_xticks(range(0, 49, 6))
    lead.tick_params(colors=MUTED)
    lead.set_xlabel("Lead time from the 2026-10-30 12:00 UTC cycle (h)", color=MUTED)

    fig.subplots_adjust(left=0.125, right=0.95, top=0.88, bottom=0.11)
    c.FIGURES.mkdir(parents=True, exist_ok=True)
    stem = c.FIGURES / "boston_stofs_v31_fig"
    fig.savefig(f"{stem}.pdf")
    fig.savefig(f"{stem}.svg")
    fig.savefig(f"{stem}_preview.png", dpi=150)
    fig.savefig(f"{stem}_300dpi.png", dpi=300)
    sizes = sorted(
        {
            plt.rcParams[k]
            for k in (
                "font.size",
                "xtick.labelsize",
                "ytick.labelsize",
                "legend.fontsize",
            )
        }
    )
    print(
        "wrote",
        c.rel(stem) + ".{pdf,svg,_preview.png,_300dpi.png}; font sizes (pt):",
        sizes,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
