"""Part B figures from results/*.json (DESIGN.md 3.4, 4, 6).

  b2_ofs_cbofs_baltimore_90mm   model and observed water level, tool statistics
  b4_rtofs_hatteras_section_190mm  temperature section, cells without interpolation
  b1_ww3_<buoy>_90mm            only once results/b1_pairs.json exists (session 2)

Vector PDF and 600 dpi PNG, exact page size. Writes results/figure_checks.json
(smallest font, legend/data overlap, text outside the page).

    uv run --offline --no-project --isolated --managed-python --python 3.13.12 \
        --with-requirements scripts/requirements-figures.txt python -I scripts/make_figures.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import PathCollection, QuadMesh  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

PACKAGE = Path(__file__).resolve().parents[1]
RES = PACKAGE / "results"
FIG = PACKAGE / "figures"
BLUE, ORANGE, INK = "#2a78d6", "#eb6834", "#0b0b0b"
MUTED, GRID = "#52514e", "#e4e3df"
MM = 1 / 25.4
PDF_META = {"CreationDate": None, "ModDate": None}
PNG_META = {"Software": None}
TEMP = LinearSegmentedColormap.from_list(
    "temp", ["#08306b", BLUE, "#cfe0f5", "#fbe1d3", ORANGE, "#5a2108"]
)


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
            "axes.unicode_minus": True,
        }
    )


def tidy(ax) -> None:
    ax.grid(color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def axes_mm(fig, x, y, w, h):
    W, H = fig.get_size_inches() / MM
    return fig.add_axes([x / W, y / H, w / W, h / H])


def t(s: str) -> datetime:
    return datetime.strptime(s[:16], "%Y-%m-%d %H:%M")


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
    texts = drawn_texts(fig)
    fb = fig.bbox
    overlap = []
    for ax in fig.axes:
        leg = ax.get_legend()
        if leg is None:
            continue
        box = leg.get_window_extent()
        n = 0
        for art in ax.get_children():
            if isinstance(art, Line2D) and len(art.get_xdata()):
                xs = [
                    mdates.date2num(x) if isinstance(x, datetime) else x
                    for x in art.get_xdata()
                ]
                xy = np.column_stack(
                    [np.asarray(xs, float), np.asarray(art.get_ydata(), float)]
                )
                xy = xy[~np.isnan(xy).any(axis=1)]
                n += int(sum(box.contains(*p) for p in ax.transData.transform(xy)))
            elif isinstance(art, PathCollection):
                n += int(
                    sum(
                        box.contains(*p)
                        for p in art.get_offset_transform().transform(art.get_offsets())
                    )
                )
        overlap.append(n)
    outside = [
        x.get_text()
        for x in texts
        if not (
            fb.contains(*x.get_window_extent().p0)
            and fb.contains(*x.get_window_extent().p1)
        )
    ]
    return {
        "min_font_pt": min(x.get_fontsize() for x in texts),
        "legend_points_inside": overlap,
        "text_outside_page": outside,
    }


def save(fig, stem: str) -> None:
    fig.savefig(FIG / f"{stem}.pdf", metadata=PDF_META)
    fig.savefig(FIG / f"{stem}_600dpi.png", dpi=600, metadata=PNG_META)


# ------------------------------------------------------------------ B2


def fig_b2() -> dict:
    b = json.loads((RES / "b2.json").read_text())
    d = b["compare"]
    s = d["stats"]
    tt = [t(x) for x in d["comparison_times"]]
    fig = plt.figure(figsize=(90 * MM, 78 * MM))
    ax = axes_mm(fig, 15, 25, 71, 38)
    ax.plot(
        tt,
        d["obs_values"],
        color=INK,
        lw=1.2,
        marker="o",
        ms=2.2,
        label=f"CO-OPS {d['station_id']} observed, datum {d['obs_datum']}",
    )
    ax.plot(
        tt,
        d["model_values"],
        color=BLUE,
        lw=1.2,
        ls=(0, (5, 2)),
        label=f"{d['model'].upper()} model, datum {d['model_datum']}",
    )
    ax.set_ylabel("Water level (m)")
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 6, 12, 18]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M"))
    ax.set_xlim(tt[0] - timedelta(minutes=30), tt[-1] + timedelta(minutes=30))
    tidy(ax)
    ax.legend(
        loc="lower left",
        bbox_to_anchor=(-0.02, 1.0),
        frameon=False,
        borderaxespad=0.1,
        handlelength=2.2,
    )
    fig.text(
        4 / 90,
        2.5 / 78,
        "Returned by ofs_compare_with_coops:\nn = {n}, bias {b:+.3f} m, RMSE {r:.3f} m, MAE {m:.3f} m,\npeak error {p:.3f} m, r = {c:.3f}".format(
            n=s["n"],
            b=s["bias"],
            r=s["rmse"],
            m=s["mae"],
            p=s["peak_error"],
            c=s["correlation"],
        ),
        fontsize=8,
        va="bottom",
        ha="left",
    )
    ck = checks(fig)
    save(fig, "b2_ofs_cbofs_baltimore_90mm")
    plt.close(fig)
    return ck


# ------------------------------------------------------------------ B4


def edges(c: np.ndarray, lo: float | None = None) -> np.ndarray:
    """Cell edges midway between centres; the outer edges mirror the first/last half step."""
    mid = (c[:-1] + c[1:]) / 2
    first = c[0] - (mid[0] - c[0]) if len(c) > 1 else c[0] - 0.5
    last = c[-1] + (c[-1] - mid[-1]) if len(c) > 1 else c[-1] + 0.5
    e = np.concatenate([[first], mid, [last]])
    if lo is not None:
        e[0] = max(e[0], lo)
    return e


def fig_b4() -> dict:
    b = json.loads((RES / "b4_section.json").read_text())
    pts = b["points"]
    x = np.array([p["distance_km"] for p in pts])
    xe = edges(x, lo=x[0])
    xe[-1] = x[-1]
    fig = plt.figure(figsize=(190 * MM, 80 * MM))
    ax = axes_mm(fig, 16, 13, 150, 58)
    vmin = min(lv["value"] for p in pts for lv in p["levels"] if lv["depth"] <= 1000)
    vmax = max(lv["value"] for p in pts for lv in p["levels"] if lv["depth"] <= 1000)
    mesh = None
    for i, p in enumerate(pts):
        if not p["levels"]:
            continue
        z = np.array([lv["depth"] for lv in p["levels"]], float)
        v = np.array([lv["value"] for lv in p["levels"]], float)
        ze = edges(z, lo=0.0)
        mesh = ax.pcolormesh(
            [xe[i], xe[i + 1]],
            ze,
            v.reshape(-1, 1),
            cmap=TEMP,
            vmin=vmin,
            vmax=vmax,
            shading="flat",
            rasterized=False,
        )
    ax.plot(
        x, np.zeros_like(x) - 12, ls="none", marker="v", ms=3, color=INK, clip_on=False
    )
    ax.set_ylim(1000, 0)
    ax.set_xlim(xe[0], xe[-1])
    ax.set_ylabel("Depth (m)")
    ax.set_xlabel(
        "Distance along the section from 35.55°N 75.25°W towards 33.95°N 73.30°W (km)"
    )
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    cax = axes_mm(fig, 170, 13, 3.5, 58)
    cb = fig.colorbar(mesh, cax=cax)
    cb.set_label("Temperature (°C)")
    cb.ax.tick_params(labelsize=8)
    ck = checks(fig)
    ck["cells_drawn"] = sum(isinstance(a, QuadMesh) for a in ax.get_children())
    save(fig, "b4_rtofs_hatteras_section_190mm")
    plt.close(fig)
    return ck


# ------------------------------------------------------------------ B1 (after session 2)


def fig_b1() -> dict | None:
    if not (RES / "b1_pairs.json").exists():
        return None
    s1 = json.loads((RES / "b1_session1.json").read_text())
    pr = json.loads((RES / "b1_pairs.json").read_text())
    fc = s1["forecast"]["series"]
    t0, t1 = t(fc[0]["time"]), t(fc[-1]["time"])
    obs = [
        (t(o["time"]), o["wvht_m"])
        for o in pr["observations"]
        if t0 - timedelta(hours=1) <= t(o["time"]) <= t1 + timedelta(hours=1)
    ]
    fig = plt.figure(figsize=(90 * MM, 78 * MM))
    ax = axes_mm(fig, 15, 25, 71, 38)
    ot = [o[0] for o in obs]
    steps = np.diff([mdates.date2num(x) for x in ot]) * 1440
    med = float(np.median(steps)) if len(steps) else 30.0
    xs, ys = [], []
    for i, (ti, v) in enumerate(obs):
        if i and (ti - obs[i - 1][0]).total_seconds() / 60 > 1.5 * med:
            xs.append(ti - (ti - obs[i - 1][0]) / 2)
            ys.append(np.nan)
        xs.append(ti)
        ys.append(v)
    ax.plot(
        xs, ys, color=INK, lw=1.0, label=f"NDBC {s1['station_id']} observed (ndbc-mcp)"
    )
    ax.plot(
        [t(f["time"]) for f in fc],
        [f["hs_m"] for f in fc],
        color=BLUE,
        lw=1.2,
        marker="o",
        ms=2.5,
        label=f"GFS-Wave {s1['forecast']['cycle']} forecast (ww3-mcp)",
    )
    ax.set_ylabel("Hs (m)")
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 12]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M"))
    tidy(ax)
    ax.legend(
        loc="lower left", bbox_to_anchor=(-0.02, 1.0), frameon=False, borderaxespad=0.1
    )
    st = pr["stats"]
    fig.text(
        15 / 90,
        2.5 / 78,
        "Computed by the client from {n} pairs\n(nearest observation within 30 min):\nbias {b:+.3f} m, RMSE {r:.3f} m, MAE {m:.3f} m, r = {c}".format(
            n=st["n"],
            b=st["bias_m"],
            r=st["rmse_m"],
            m=st["mae_m"],
            c="n/a" if st["r"] is None else f"{st['r']:.3f}",
        ),
        fontsize=8,
        va="bottom",
        ha="left",
    )
    ck = checks(fig)
    save(fig, f"b1_ww3_{s1['station_id']}_90mm")
    plt.close(fig)
    return ck


def main() -> None:
    style()
    FIG.mkdir(exist_ok=True)
    report = {"b2": fig_b2(), "b4": fig_b4()}
    b1 = fig_b1()
    report["b1"] = b1 if b1 is not None else "not drawn: session 2 not archived yet"
    (RES / "figure_checks.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
