"""Step 6: publication figure from the independent results (results/statistics_independent.json).

Panel A: CO-OPS observations, STOFS-2D-Global and STOFS-3D-Atlantic over the
common forecast window. Panel B: signed errors (model - observation). Panel C:
verification statistics. Writes figures/boston_stofs_v31_validation.{pdf,svg},
a preview PNG (<=1600 px, 150 dpi) and a 300 dpi PNG.

Usage: uv run --no-project --isolated --managed-python --python 3.13 --with-requirements requirements-analysis.txt \
           python scripts/06_figure.py
"""

from __future__ import annotations

import sys
import textwrap
from datetime import datetime, timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

import _common as c  # noqa: E402

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#ffffff"
SERIES = {"2d_global": "#2a78d6", "3d_atlantic": "#eb6834"}  # validated slots 1-2
STYLE = {"2d_global": "-", "3d_atlantic": (0, (5, 2))}  # line style as a second cue
LABEL = {"2d_global": "STOFS-2D-Global v3.1", "3d_atlantic": "STOFS-3D-Atlantic v3.1"}


def main() -> int:
    res = c.load_json(c.RESULTS / "statistics_independent.json")["results"]
    cycle = datetime.strptime(c.CYCLE_ISO, "%Y-%m-%d %H:%M")
    plt.rcParams.update(
        {
            "font.size": 8,
            "axes.titlesize": 8.5,
            "axes.labelsize": 8,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": INK,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )
    fig = plt.figure(figsize=(7.48, 8.6), facecolor=SURFACE)
    gs = fig.add_gridspec(3, 1, height_ratios=[1.5, 1.0, 1.1], hspace=0.28)
    ax_a = fig.add_subplot(gs[0])
    ax_b = fig.add_subplot(gs[1], sharex=ax_a)
    ax_c = fig.add_subplot(gs[2])

    fc = {m: res[f"{m}_forecast"] for m in c.STOFS_FILES}
    t = [
        datetime.strptime(p["time"], "%Y-%m-%d %H:%M")
        for p in fc["2d_global"]["series"]
    ]
    obs = [p["obs_m"] for p in fc["2d_global"]["series"]]
    assert all([p["obs_m"] for p in fc["3d_atlantic"]["series"]] == obs for _ in [0]), (
        "models must share valid times and observations"
    )

    # Panel A
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
    ax_a.set_ylabel("Water level (m)\nmodel: LMSL · obs: CO-OPS MSL")
    ax_a.set_title(
        "A  Water level at Boston, MA (CO-OPS 8443970), forecast lead 0–48 h",
        loc="left",
    )
    ax_a.legend(frameon=False, loc="upper left", ncol=3, fontsize=7.2, handlelength=2.6)
    ax_a.set_ylim(min(obs) - 0.35, max(obs) + 0.75)

    # Panel B
    ax_b.axhline(0, color=MUTED, lw=0.8, zorder=1)
    for m in c.STOFS_FILES:
        err = [p["model_m"] - p["obs_m"] for p in fc[m]["series"]]
        ax_b.plot(t, err, color=SERIES[m], lw=1.2, ls=STYLE[m], label=LABEL[m])
    ax_b.set_ylabel("Model − observed (m)")
    ax_b.set_title("B  Signed error (no vertical offset applied)", loc="left")
    ax_b.legend(
        frameon=False,
        loc="lower right",
        ncol=2,
        fontsize=7.2,
        handlelength=2.6,
        bbox_to_anchor=(1.0, 1.0),
        borderaxespad=0.1,
    )

    for ax in (ax_a, ax_b):
        ax.grid(color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    ax_a.set_xlim(t[0] - timedelta(minutes=30), t[-1] + timedelta(minutes=30))
    ax_b.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 12]))
    ax_b.xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 18]))
    ax_b.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %H:%M"))
    ax_a.tick_params(labelbottom=False)
    lead = ax_a.secondary_xaxis(
        "top",
        functions=(
            lambda x: (x - mdates.date2num(cycle)) * 24,
            lambda h: mdates.date2num(cycle) + h / 24,
        ),
    )
    lead.set_xticks(range(0, 49, 6))
    lead.tick_params(labelsize=7, colors=MUTED)
    lead.set_xlabel(
        "lead time from the cycle, 2026-10-30 12:00 UTC (h)", fontsize=7, color=MUTED
    )
    ax_b.set_xlabel("valid time (UTC)")

    # Panel C
    ax_c.axis("off")
    ax_c.set_title(
        "C  Verification statistics, same 480 six-minute valid times (e = model − observed)",
        loc="left",
    )
    rows = [
        ("Matched pairs, n", "n", "{:d}"),
        ("Mean bias, mean(e) (m)", "bias_m", "{:+.4f}"),
        ("RMSE (m)", "rmse_m", "{:.3f}"),
        ("MAE, mean|e| (m)", "mae_m", "{:.3f}"),
        ("Centred RMSE (m)", "crmse_m", "{:.3f}"),
        ("Pearson r", "pearson_r", "{:.4f}"),
        ("Max |e| (m)", "max_abs_error_m", "{:.3f}"),
        ("max(model) − max(obs) (m)", "max_model_minus_max_obs_m", "{:+.3f}"),
    ]
    cell = [
        [name]
        + [
            fmt.format(fc[m]["statistics"][key]).replace("-", "\u2212")
            for m in c.STOFS_FILES
        ]
        for name, key, fmt in rows
    ]
    table = ax_c.table(
        cellText=cell,
        colLabels=["Metric", LABEL["2d_global"], LABEL["3d_atlantic"]],
        colLoc="left",
        cellLoc="left",
        colWidths=[0.42, 0.29, 0.29],
        bbox=[0.0, 0.0, 1.0, 0.94],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.4)
    for (r, col), cl in table.get_celld().items():
        cl.set_edgecolor(GRID)
        cl.set_linewidth(0.6)
        if r == 0:
            cl.set_text_props(weight="bold")
            if col:
                cl.get_text().set_color(SERIES[list(c.STOFS_FILES)[col - 1]])

    footer = (
        "Model: NOAA STOFS station NetCDF, cycle 2026-10-30 12:00 UTC; STOFS-2D-Global "
        "(STOFS_2D_GLOBAL V3.1.0) LMSL per NOAA documentation, STOFS-3D-Atlantic "
        "(stofs.v3.1.6) LMSL per file metadata. Observations: NOAA CO-OPS 6-min water "
        "level, MSL datum (1983–2001 epoch), preliminary. Valid times 2026-10-30 12:06 to "
        "2026-11-01 12:00 UTC, exact timestamp matching. Both products apply "
        "observation-based bias corrections; this is not an independent skill assessment."
    )
    fig.text(
        0.1, 0.012, textwrap.fill(footer, 132), fontsize=6.3, color=MUTED, va="bottom"
    )
    fig.subplots_adjust(left=0.1, right=0.945, top=0.93, bottom=0.085)

    c.FIGURES.mkdir(parents=True, exist_ok=True)
    stem = c.FIGURES / "boston_stofs_v31_validation"
    fig.savefig(f"{stem}.pdf")
    fig.savefig(f"{stem}.svg")
    fig.savefig(f"{stem}_preview.png", dpi=150)  # <=1600 px for on-screen review
    fig.savefig(f"{stem}_300dpi.png", dpi=300)
    print("wrote", c.rel(stem) + ".{pdf,svg,_preview.png,_300dpi.png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
