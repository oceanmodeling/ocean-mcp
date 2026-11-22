"""Part A figures from results/panel_*.json (DESIGN.md 8).

Main figure: four panels, 190 mm x 130 mm; (a) map on the left at full height,
(b)-(d) stacked on the right. Fallback: two panels, 190 mm wide. Vector PDF and
600 dpi PNG; the page size is exact (no bbox_inches). Writes
results/figure_checks.json: smallest font size at final size and whether any
legend box contains a plotted data point (display coordinates).

    uv run --offline --no-project --isolated --managed-python --python 3.13.12 \
        --with-requirements scripts/requirements-figures.txt python -I scripts/make_figures.py
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.collections import PathCollection  # noqa: E402

PACKAGE = Path(__file__).resolve().parents[1]
RES = PACKAGE / "results"
FIG = PACKAGE / "figures"

BLUE, ORANGE, INK = "#2a78d6", "#eb6834", "#0b0b0b"
MUTED, GRID = "#52514e", "#e4e3df"
COAST = "#9c9a94"  # coastline, light grey (non-MCP context)
KT_TO_MS = 1852 / 3600
LANDFALL = datetime(2022, 9, 28, 19, 5)
MM = 1 / 25.4
INTENSITY = LinearSegmentedColormap.from_list("intensity", ["#cfe0f5", BLUE, INK])
PDF_META = {"CreationDate": None, "ModDate": None}
PNG_META = {"Software": None}


def load(name: str):
    return json.loads((RES / name).read_text())


def t(s: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise ValueError(s)


def with_breaks(times, values, max_gap: timedelta):
    """Insert NaN where a value is missing or the time step exceeds max_gap."""
    xs, ys, prev = [], [], None
    for ti, v in zip(times, values):
        if prev is not None and ti - prev > max_gap:
            xs.append(prev + (ti - prev) / 2)
            ys.append(np.nan)
        xs.append(ti)
        ys.append(np.nan if v is None else float(v))
        prev = ti
    return xs, ys


def style() -> None:
    plt.rcParams.update(
        {
            "font.size": 8.5,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": INK,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "axes.unicode_minus": True,
        }
    )


def tidy(ax) -> None:
    ax.grid(color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def label(ax, letter: str, x: float = -0.09) -> None:
    """Bold panel label at the top left, just above the axes."""
    ax.text(
        x,
        1.02,
        letter,
        transform=ax.transAxes,
        fontsize=10,
        fontweight="bold",
        va="bottom",
        ha="left",
    )


def landfall_line(ax) -> bool:
    lo, hi = ax.get_xlim()
    x = mdates.date2num(LANDFALL)
    if lo <= x <= hi:
        ax.axvline(LANDFALL, color=INK, lw=0.9, ls=(0, (4, 2)), zorder=1)
        return True
    return False


# ------------------------------------------------------------------ panels

MAP_X, MAP_Y = (-89.5, -79.0), (16.0, 31.0)


def panel_map(ax, a, fallback_sfmr=None):
    """Best track, gauges, buoy, flight track, landfall; key and colorbar in the empty south-west."""
    bt = a["best_track"]
    lons = [p["lon"] for p in bt]
    lats = [p["lat"] for p in bt]
    f = a["flight_track"]["points"]
    ac = a["flight_track"]["aircraft"]
    # Natural Earth 1:50m coastline, the one non-MCP input (AMENDMENTS.md A7)
    for line in load("coastline_subset.json")["polylines"]:
        ax.plot(
            [q[0] for q in line], [q[1] for q in line], color=COAST, lw=0.5, zorder=1
        )
    ax.plot(lons, lats, color=MUTED, lw=0.9, zorder=2)
    if fallback_sfmr is None:
        sc = ax.scatter(
            lons,
            lats,
            c=[p["max_wind"] for p in bt],
            cmap=INTENSITY,
            vmin=20,
            vmax=140,
            s=14,
            edgecolors=INK,
            linewidths=0.4,
            zorder=3,
        )
        ax.plot(
            [p["lon"] for p in f], [p["lat"] for p in f], color=ORANGE, lw=0.7, zorder=4
        )
        cbar_label = "Best-track\nmax wind (kt)"
    else:
        ax.scatter(lons, lats, color=MUTED, s=8, zorder=3)
        ax.plot(
            [p["lon"] for p in f],
            [p["lat"] for p in f],
            color="#d9d8d4",
            lw=0.6,
            zorder=3,
        )
        pts = fallback_sfmr
        sc = ax.scatter(
            [q[1] for q in pts],
            [q[0] for q in pts],
            c=[q[2] for q in pts],
            cmap=LinearSegmentedColormap.from_list(
                "sfmr", ["#fbe1d3", ORANGE, "#5a2108"]
            ),
            vmin=0,
            vmax=140,
            s=2.5,
            linewidths=0,
            zorder=4,
        )
        cbar_label = f"{ac} SFMR\nsurface wind (kt)"
    markers = {}
    for sid, g in a["tide_gauges"].items():
        markers[sid] = ax.plot(
            g["lon"], g["lat"], marker="^", ms=4.5, color=INK, ls="none", zorder=6
        )[0]
    gm, gs_ = a["tide_gauges"]["8725520"], a["tide_gauges"]["8726520"]
    ax.annotate(
        "Fort Myers",
        (gm["lon"], gm["lat"]),
        xytext=(gm["lon"] + 0.55, gm["lat"] - 0.75),
        fontsize=8,
        ha="left",
        va="top",
        arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.5},
        zorder=7,
    )
    ax.annotate(
        "St. Petersburg",
        (gs_["lon"], gs_["lat"]),
        xytext=(gs_["lon"] + 0.45, gs_["lat"] + 0.65),
        fontsize=8,
        ha="left",
        va="bottom",
        arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.5},
        zorder=7,
    )
    b = a["buoy"]
    markers["buoy"] = ax.plot(
        b["lon"],
        b["lat"],
        marker="s",
        ms=4.5,
        mfc="white",
        mec=INK,
        mew=1.0,
        ls="none",
        zorder=6,
    )[0]
    ax.annotate(
        b["id"],
        (b["lon"], b["lat"]),
        xytext=(b["lon"] - 0.3, b["lat"] - 0.3),
        fontsize=8,
        ha="right",
        va="top",
        zorder=7,
    )
    lf = a["landfall"]
    markers["landfall"] = ax.plot(
        lf["lon"],
        lf["lat"],
        marker="*",
        ms=5.5,
        mfc=ORANGE,
        mec=INK,
        mew=0.5,
        ls="none",
        zorder=7,
    )[0]
    ax.wp9_markers = markers  # for the overlap checks
    ax.set_xlim(*MAP_X)
    ax.set_ylim(*MAP_Y)
    ax.set_aspect(1 / math.cos(math.radians(23.5)))
    ax.set_xticks(range(-88, -78, 3))
    ax.set_yticks(range(16, 32, 3))
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{abs(v):.0f}°W"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}°N"))
    tidy(ax)
    if fallback_sfmr is None:
        handles = [
            Line2D(
                [],
                [],
                color=MUTED,
                lw=0.9,
                marker="o",
                ms=3.5,
                mfc=BLUE,
                mec=INK,
                mew=0.4,
                label="Best track",
            ),
            Line2D([], [], color=ORANGE, lw=0.8, label=f"{ac} (HDOB)"),
        ]
    else:
        handles = [
            Line2D(
                [],
                [],
                color=MUTED,
                lw=0.9,
                marker="o",
                ms=3,
                mfc=MUTED,
                mec=MUTED,
                label="Best track",
            ),
            Line2D([], [], color=ORANGE, lw=0, marker="o", ms=3, label=f"{ac} SFMR"),
        ]
    handles += [
        Line2D([], [], marker="^", color=INK, ls="none", ms=4.5, label="Tide gauge"),
        Line2D(
            [], [], marker="s", mfc="white", mec=INK, ls="none", ms=4.5, label="Buoy"
        ),
        Line2D(
            [], [], marker="*", mfc=ORANGE, mec=INK, ls="none", ms=6, label="Landfall"
        ),
        Line2D([], [], color=COAST, lw=0.5, label="Coastline (Natural Earth)"),
    ]
    return sc, handles, cbar_label


def map_key(fig, ax, sc, handles, cbar_label, cbar_mm) -> None:
    """Key (two columns) and horizontal colorbar below the map, outside it (A7)."""
    ax.set_anchor("N")
    ax.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(-0.12, -0.075),
        ncol=2,
        frameon=False,
        borderaxespad=0.0,
        handlelength=1.2,
        handletextpad=0.5,
        columnspacing=0.8,
        labelspacing=0.3,
    )
    x, y, w = cbar_mm
    cax = axes_mm(fig, x, y, w, 2.2, "colorbar")
    cb = plt.colorbar(sc, cax=cax, orientation="horizontal")
    cb.set_ticks([20, 80, 140])
    cb.ax.tick_params(labelsize=8, length=2)
    W, H = fig.get_size_inches() / MM
    fig.text(
        (x + w + 2) / W,
        (y + 1.1) / H,
        cbar_label,
        fontsize=8,
        va="center",
        ha="left",
    )


def panel_b(ax, b):
    rows = b["rows"]
    tt = [t(r["time"]) for r in rows]
    gap = timedelta(seconds=60)
    x, y = with_breaks(tt, [r["sfmr_kt"] for r in rows], gap)
    ax.plot(x, y, color=BLUE, lw=0.8, label="SFMR surface (10-s max)", zorder=4)
    x, y = with_breaks(tt, [r["fl_wind_kt"] for r in rows], gap)
    ax.plot(x, y, color=ORANGE, lw=0.8, label="Flight level (30-s mean)", zorder=3)
    # AMENDMENTS.md A6: the 6-hourly best-track values joined linearly in time (was a
    # nearest-record step); the line runs on toward the next record and is clipped at the edge.
    bt = b["best_track"]
    ax.plot(
        [t(r["time"]) for r in bt],
        [r["max_wind_kt"] for r in bt],
        color=INK,
        lw=0.8,
        marker="o",
        ms=3.5,
        label="Best track, 1-min max wind (6-hourly, linear between)",
        zorder=5,
    )
    ax.set_ylabel("Wind (kt)")
    sec = ax.secondary_yaxis(
        "right", functions=(lambda k: k * KT_TO_MS, lambda m: m / KT_TO_MS)
    )
    sec.set_ylabel("Wind (m/s)")
    ax.set_xlim(tt[0] - timedelta(minutes=10), tt[-1] + timedelta(minutes=10))
    ax.set_ylim(0, 165)
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0, 24, 2)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.set_xlabel(f"28 Sep 2022, time (UTC); aircraft {b['aircraft']}", labelpad=1)
    tidy(ax)
    return landfall_line(ax)


def panel_c(ax, c):
    tt = [t(r["time"]) for r in c["rows"]]
    x, y = with_breaks(
        tt,
        [r["wvht_m"] for r in c["rows"]],
        timedelta(minutes=1.5 * c["median_interval_min"]),
    )
    ax.plot(
        x,
        y,
        color=BLUE,
        lw=1.1,
        label=f"Buoy {c['station_id']} significant wave height (from ww3-mcp)",
    )
    ax.set_ylabel("Hs (m)")
    ax.set_ylim(0, 10)
    tidy(ax)


def panel_d(ax, d):
    colours = {"8725520": BLUE, "8726520": ORANGE}
    for sid, s in d["stations"].items():
        tt = [t(x) for x in s["times"]]
        ax.plot(tt, [float(v) for v in s["observed_m"]], color=colours[sid], lw=1.1)
        ax.plot(
            tt,
            [float(v) for v in s["residual_m"]],
            color=colours[sid],
            lw=0.9,
            ls=(0, (1, 1)),
        )
    ck = d["checks"]
    ax.annotate(
        f"+{ck['fort_myers_residual_max_m']} m, 22:18",
        (
            t(ck["fort_myers_residual_max_first_time"]),
            float(ck["fort_myers_residual_max_m"]),
        ),
        xytext=(t("2022-09-29 06:00"), 2.6),
        fontsize=8,
        va="center",
        arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.6},
    )
    ax.annotate(
        f"{ck['st_petersburg_residual_min_m'].replace('-', '\u2212')} m, 23:00",
        (
            t(ck["st_petersburg_residual_min_time"]),
            float(ck["st_petersburg_residual_min_m"]),
        ),
        xytext=(t("2022-09-29 06:00"), -1.95),
        fontsize=8,
        va="center",
        arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.6},
    )
    ax.set_ylabel("Water level (m)")
    ax.set_ylim(-2.4, 3.2)
    tidy(ax)
    return [
        Line2D([], [], color=BLUE, lw=1.1, label="Fort Myers"),
        Line2D([], [], color=INK, lw=1.1, label="observed, MLLW"),
        Line2D([], [], color=ORANGE, lw=1.1, label="St. Petersburg"),
        Line2D([], [], color=INK, lw=0.9, ls=(0, (1, 1)), label="residual"),
    ]


def time_axis(ax):
    ax.set_xlim(datetime(2022, 9, 27), datetime(2022, 9, 30))
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 12]))
    ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 18]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M"))


def axes_mm(fig, x, y, w, h, label):
    """Axes at a position given in mm from the lower-left corner."""
    W, H = fig.get_size_inches() / MM
    return fig.add_axes([x / W, y / H, w / W, h / H], label=label)


# ------------------------------------------------------------------ checks


def drawn_texts(fig) -> list:
    """Visible, non-empty texts, without tick labels of ticks outside the view interval."""
    skip = set()
    for ax in fig.axes:
        for axis, (lo, hi) in (
            (ax.xaxis, sorted(ax.get_xlim())),
            (ax.yaxis, sorted(ax.get_ylim())),
        ):
            for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                loc = tick.get_loc()
                if loc is not None and not (lo - 1e-9 <= loc <= hi + 1e-9):
                    skip.update({id(tick.label1), id(tick.label2)})
    return [
        x
        for x in fig.findobj(matplotlib.text.Text)
        if x.get_visible() and x.get_text().strip() and id(x) not in skip
    ]


def checks(fig) -> dict:
    fig.canvas.draw()
    sizes = [a.get_fontsize() for a in drawn_texts(fig)]
    overlaps = []
    for ax in fig.axes:
        leg = ax.get_legend()
        if leg is None:
            continue
        box = leg.get_window_extent()
        n = 0
        for art in ax.get_children():
            if (
                isinstance(art, Line2D)
                and art.get_visible()
                and art.get_label() != "_nolegend_"
            ):
                xy = (
                    np.column_stack(art.get_data(orig=False))
                    if len(art.get_xdata())
                    else np.empty((0, 2))
                )
                if xy.size:
                    xy = np.array(
                        [
                            [mdates.date2num(x) if isinstance(x, datetime) else x, y]
                            for x, y in xy
                        ],
                        dtype=float,
                    )
                    xy = xy[~np.isnan(xy).any(axis=1)]
                    disp = ax.transData.transform(xy)
                    axbox = ax.get_window_extent()
                    disp = np.array([q for q in disp if axbox.contains(*q)]).reshape(
                        -1, 2
                    )
                    n += (
                        int(box.contains_points(disp).sum())
                        if hasattr(box, "contains_points")
                        else int(sum(box.contains(px, py) for px, py in disp))
                    )
            elif isinstance(art, PathCollection):
                disp = art.get_offset_transform().transform(art.get_offsets())
                n += int(sum(box.contains(px, py) for px, py in disp))
        overlaps.append(
            {
                "axes": ax.get_label() or str(fig.axes.index(ax)),
                "points_inside_legend": n,
            }
        )
    fig_box = fig.bbox
    letters = [
        tx
        for tx in fig.findobj(matplotlib.text.Text)
        if tx.get_fontweight() == "bold" and re.fullmatch(r"\(\w\)", tx.get_text())
    ]
    clashes, outside = [], []
    for ax in fig.axes:
        leg = ax.get_legend()
        if leg is None:
            continue
        box = leg.get_window_extent()
        if (
            box.x0 < fig_box.x0
            or box.y0 < fig_box.y0
            or box.x1 > fig_box.x1
            or box.y1 > fig_box.y1
        ):
            outside.append(ax.get_label())
        for tx in letters:
            if box.overlaps(tx.get_window_extent()):
                clashes.append((ax.get_label(), tx.get_text()))
    text_outside = [
        tx.get_text()
        for tx in drawn_texts(fig)
        if not (
            fig_box.contains(*tx.get_window_extent().p0)
            and fig_box.contains(*tx.get_window_extent().p1)
        )
    ]
    # legend against the other panels' axes, including their tick marks (AMENDMENTS.md A8)
    renderer = fig.canvas.get_renderer()
    legend_vs_axes = []
    main_axes = [ax for ax in fig.axes if ax.get_label() in ("a", "b", "c", "d")]
    for ax in main_axes:
        leg = ax.get_legend()
        if leg is None:
            continue
        box = leg.get_window_extent()
        for other in main_axes:
            if other is ax:
                continue
            ob = other.get_window_extent()
            pad = 3.5 * fig.dpi / 72  # major tick length, pt -> px
            if (
                box.x0 < ob.x1 + pad
                and box.x1 > ob.x0 - pad
                and box.y0 < ob.y1 + pad
                and box.y1 > ob.y0 - pad
            ):
                legend_vs_axes.append((ax.get_label(), other.get_label()))
    # any two drawn texts overlapping (texts of one legend excluded among themselves)
    texts = drawn_texts(fig)
    owner = {}
    for ax in fig.axes:
        leg = ax.get_legend()
        if leg is not None:
            for tx in leg.get_texts():
                owner[id(tx)] = id(leg)
    text_pairs = []
    for i, t1 in enumerate(texts):
        b1 = t1.get_window_extent(renderer)
        for t2 in texts[i + 1 :]:
            if owner.get(id(t1)) is not None and owner.get(id(t1)) == owner.get(id(t2)):
                continue
            if b1.overlaps(t2.get_window_extent(renderer)):
                text_pairs.append((t1.get_text(), t2.get_text()))
    # map markers: landfall star against the Fort Myers triangle, and labels against markers
    marker_checks = {}
    for ax in fig.axes:
        mk = getattr(ax, "wp9_markers", None)
        if not mk:
            continue
        boxes = {k: v.get_window_extent(renderer) for k, v in mk.items()}
        marker_checks["landfall_star_overlaps_fort_myers_triangle"] = bool(
            boxes["landfall"].overlaps(boxes["8725520"])
        )
        marker_checks["labels_over_markers"] = [
            (tx.get_text(), k)
            for tx in ax.texts
            for k, bb in boxes.items()
            if matplotlib.text.Text.get_window_extent(tx, renderer).overlaps(bb)
        ]
    return {
        "min_font_pt": min(sizes),
        "font_sizes_pt": sorted(set(sizes)),
        "legend_overlap": overlaps,
        "legend_vs_panel_letter": clashes,
        "legend_outside_page": outside,
        "legend_vs_other_axes": legend_vs_axes,
        "text_outside_page": text_outside,
        "overlapping_text_pairs": text_pairs,
        "map_markers": marker_checks,
    }


def save(fig, stem: str) -> None:
    fig.savefig(FIG / f"{stem}.pdf", metadata=PDF_META)
    fig.savefig(FIG / f"{stem}_600dpi.png", dpi=600, metadata=PNG_META)


def main() -> None:
    style()
    FIG.mkdir(exist_ok=True)
    a, b, c, d = (load(f"panel_{k}.json") for k in "abcd")
    report = {}

    # ---- main figure, 190 mm x 130 mm
    fig = plt.figure(figsize=(190 * MM, 130 * MM))
    ax_a = axes_mm(fig, 13, 11, 60, 112, "a")
    ax_d = axes_mm(fig, 91, 13, 86, 25, "d")
    ax_c = axes_mm(fig, 91, 50.5, 86, 22.5, "c")
    ax_b = axes_mm(fig, 91, 90, 86, 24.5, "b")
    ax_c.sharex(ax_d)
    sc, handles, cbl = panel_map(ax_a, a)
    map_key(fig, ax_a, sc, handles, cbl, (14, 5.0, 26))
    lf_b = panel_b(ax_b, b)
    ax_b.legend(
        loc="lower right",
        bbox_to_anchor=(1.0, 1.0),
        ncol=1,
        frameon=False,
        borderaxespad=0.1,
        handlelength=1.5,
        labelspacing=0.25,
    )
    panel_c(ax_c, c)
    d_handles = panel_d(ax_d, d)
    time_axis(ax_d)
    plt.setp(ax_c.get_xticklabels(), visible=False)
    lf_c = landfall_line(ax_c)
    lf_d = landfall_line(ax_d)
    ax_c.legend(
        loc="lower right", bbox_to_anchor=(1.0, 1.0), frameon=False, borderaxespad=0.1
    )
    ax_d.legend(
        handles=d_handles,
        loc="lower right",
        bbox_to_anchor=(1.0, 1.0),
        ncol=2,
        frameon=False,
        borderaxespad=0.1,
        handlelength=1.8,
        columnspacing=0.9,
    )
    ax_d.set_xlabel("Time (UTC), 2022", labelpad=1)
    label(ax_a, "(a)", -0.17)
    for ax in (ax_b, ax_c, ax_d):
        label(ax, f"({ax.get_label()})", -0.15)
    report["main"] = checks(fig)
    report["main"]["landfall_line_drawn"] = {"b": lf_b, "c": lf_c, "d": lf_d}
    save(fig, "ian_4panel_190mm")
    plt.close(fig)

    # ---- fallback, 190 mm x 125 mm: (a) track and reconnaissance winds, (b) water levels
    pts = [(lat, lon, r["sfmr_kt"]) for r, (lat, lon) in _flight_sfmr(a, b)]
    fig = plt.figure(figsize=(190 * MM, 125 * MM))
    ax_a = axes_mm(fig, 14, 31, 58, 88, "a")
    ax_w = axes_mm(fig, 90, 15, 92, 92, "b")
    sc, handles, cbl = panel_map(ax_a, a, fallback_sfmr=pts)
    map_key(fig, ax_a, sc, handles, cbl, (15, 5.5, 26))
    w_handles = panel_d(ax_w, d)
    time_axis(ax_w)
    lf_fb = landfall_line(ax_w)
    ax_w.legend(
        handles=w_handles,
        loc="lower right",
        bbox_to_anchor=(1.0, 1.0),
        ncol=2,
        frameon=False,
        borderaxespad=0.1,
        handlelength=1.8,
        columnspacing=0.9,
    )
    ax_w.set_xlabel("Time (UTC), 2022", labelpad=1)
    label(ax_a, "(a)", -0.19)
    label(ax_w, "(b)", -0.10)
    report["fallback"] = checks(fig)
    report["fallback"]["landfall_line_drawn"] = {"b": lf_fb}
    save(fig, "ian_2panel_fallback_190mm")
    plt.close(fig)

    (RES / "figure_checks.json").write_text(json.dumps(report, indent=1) + "\n")
    print(
        json.dumps(
            {
                k: {
                    "min_font_pt": v["min_font_pt"],
                    "legend_overlap": v["legend_overlap"],
                }
                for k, v in report.items()
            },
            indent=1,
        )
    )


def _flight_sfmr(a, b):
    """Flight-track positions (QC-passing) paired with QC-passing SFMR by time."""
    by_time = {r["time"][11:]: r for r in b["rows"]}
    for p in a["flight_track"]["points"]:
        r = by_time.get(p["time"])
        if r is not None and r["sfmr_kt"] is not None:
            yield r, (p["lat"], p["lon"])


if __name__ == "__main__":
    main()
