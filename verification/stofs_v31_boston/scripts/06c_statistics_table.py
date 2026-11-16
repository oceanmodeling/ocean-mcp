"""Step 6c: verification statistics as a typesettable table, and the figure caption.

Reads results/statistics_independent.json (and the manifest for archive
identifiers). Writes:
  results/table_boston_v31_statistics.csv / .json  (machine-readable)
  results/table_boston_v31_statistics.md / .tex    (for typesetting)
  figures/boston_stofs_v31_fig_caption.md          (caption for 06b's figure)
The forecast columns share the same 480 valid times; the nowcast columns have
different durations (6 h vs 24 h) and are not comparable with each other.

Usage: uv run --no-project --isolated --managed-python --python 3.13 --with-requirements requirements-analysis.txt \
           python scripts/06c_statistics_table.py
"""

from __future__ import annotations

import csv
import sys

import numpy as np

import _common as c

COLUMNS = [
    ("2d_global_forecast", "STOFS-2D-Global v3.1, forecast (0, 48] h"),
    ("3d_atlantic_forecast", "STOFS-3D-Atlantic v3.1, forecast (0, 48] h"),
    ("2d_global_nowcast", "STOFS-2D-Global v3.1, nowcast (-6, 0] h"),
    ("3d_atlantic_nowcast", "STOFS-3D-Atlantic v3.1, nowcast (-24, 0] h"),
]
# key, label, definition (e = model - observed), unit, decimals
METRICS = [
    ("n", "Matched pairs", "count of exact-timestamp pairs", "", 0),
    ("bias_m", "Mean bias", "mean(e)", "m", 4),
    ("rmse_m", "RMSE", "sqrt(mean(e^2))", "m", 3),
    ("mae_m", "MAE", "mean(|e|)", "m", 3),
    ("crmse_m", "Centred RMSE", "sqrt(mean((e - mean(e))^2))", "m", 3),
    ("pearson_r", "Pearson r", "cov(M,O)/(sd(M) sd(O))", "", 4),
    ("max_abs_error_m", "Max |e|", "max(|e|)", "m", 3),
    ("max_model_minus_max_obs_m", "max(M) - max(O)", "max(M) - max(O)", "m", 3),
    ("sd_ratio", "sd(M)/sd(O)", "ratio of population standard deviations", "", 3),
    (
        "best_lag_min",
        "Best-correlated lag",
        "lag maximizing r(M(t+lag), O(t)), 6-min steps",
        "min",
        0,
    ),
]


def best_lag_minutes(series: list[dict]) -> int:
    m = np.array([p["model_m"] for p in series])
    o = np.array([p["obs_m"] for p in series])
    best = (0, -2.0)
    for lag in range(-10, 11):  # +-60 min; positive = model later
        a, b = (m[lag:], o[: len(o) - lag]) if lag >= 0 else (m[:lag], o[-lag:])
        r = float(np.corrcoef(a, b)[0, 1])
        if r > best[1]:
            best = (lag, r)
    return best[0] * 6


SIGNED = {"bias_m", "max_model_minus_max_obs_m", "best_lag_min"}


def fmt(value, decimals: int, signed: bool = False) -> str:
    sign = "+" if signed and value != 0 else ""
    if decimals == 0:
        return f"{int(round(value)):{sign}d}"
    return f"{value:{sign}.{decimals}f}"


def main() -> int:
    res = c.load_json(c.RESULTS / "statistics_independent.json")["results"]
    values = {}
    for key, _ in COLUMNS:
        st = dict(res[key]["statistics"])
        st["sd_ratio"] = st["model_sd_m"] / st["obs_sd_m"]
        st["best_lag_min"] = best_lag_minutes(res[key]["series"])
        values[key] = st

    rows = []
    for key, label, definition, unit, dec in METRICS:
        rows.append(
            {
                "metric": label,
                "definition": definition,
                "unit": unit,
                **{col: values[col][key] for col, _ in COLUMNS},
            }
        )
    with open(c.RESULTS / "table_boston_v31_statistics.csv", "w", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=["metric", "definition", "unit"] + [k for k, _ in COLUMNS]
        )
        w.writeheader()
        w.writerows(rows)
    c.dump_json(
        {
            "case": {"station": c.STATION, "cycle": c.CYCLE_ISO + " UTC"},
            "columns": dict(COLUMNS),
            "note": "e = model - observed (m). Forecast columns share 480 valid times; "
            "nowcast columns differ in duration and are not comparable.",
            "rows": rows,
        },
        c.RESULTS / "table_boston_v31_statistics.json",
    )

    def cells(key, dec):
        return [
            fmt(values[col][key], dec, key in SIGNED).replace("-", "−")
            for col, _ in COLUMNS
        ]

    def md_text(text):  # pipes inside a cell would split the Markdown table
        return text.replace("|", "\\|").replace(" - ", " − ")

    md = [
        "| Metric | Definition | Unit | 2D forecast | 3D forecast | 2D nowcast | 3D nowcast |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for key, label, definition, unit, dec in METRICS:
        md.append(
            f"| {md_text(label)} | {md_text(definition)} | {unit} | "
            + " | ".join(cells(key, dec))
            + " |"
        )
    md.append("")
    md.append(
        "e = model − observed. Forecast window: 0 < lead ≤ 48 h (same 480 valid times for "
        "both models). Nowcast windows differ (6 h vs 24 h) and are not comparable."
    )
    (c.RESULTS / "table_boston_v31_statistics.md").write_text("\n".join(md) + "\n")

    def tex(s):
        s = s.replace(" - ", " − ")
        return s.replace("−", "$-$").replace("|e|", r"$|e|$").replace("^2", r"$^2$")

    lines = [
        r"\begin{tabular}{lrrrr}",
        r"\hline",
        r"Metric & 2D fc & 3D fc & 2D nc & 3D nc \\",
        r"\hline",
    ]
    for key, label, _, unit, dec in METRICS:
        name = tex(label) + (f" ({unit})" if unit else "")
        lines.append(
            name + " & " + " & ".join(tex(x) for x in cells(key, dec)) + r" \\"
        )
    lines += [r"\hline", r"\end{tabular}"]
    (c.RESULTS / "table_boston_v31_statistics.tex").write_text("\n".join(lines) + "\n")

    man = c.load_json(c.MANIFEST)["entries"]
    f2, f3 = values["2d_global_forecast"], values["3d_atlantic_forecast"]
    bias_share = f3["bias_m"] ** 2 / f3["rmse_m"] ** 2

    def lag(v):
        return f"{v:+d}".replace("-", "−")

    caption = f"""**Figure. STOFS v3.1 forecast water level at Boston, MA (NOAA CO-OPS 8443970), cycle 2026-10-30 12:00 UTC.**
(A) Observed water level and the STOFS-2D-Global and STOFS-3D-Atlantic station forecasts for the
same 480 six-minute valid times, 2026-10-30 12:06 to 2026-11-01 12:00 UTC (forecast lead 0 < lead ≤ 48 h;
lead time on the top axis). (B) Signed error, model − observed. Model values are the NOAA station NetCDF
products (STOFS-2D-Global `STOFS_2D_GLOBAL.V3.1.0`, referenced to local mean sea level, LMSL, per NOAA
documentation; STOFS-3D-Atlantic `stofs.v3.1.6`, LMSL per the file's `zeta` metadata). Observations are
NOAA CO-OPS 6-minute water levels on the station's mean sea level datum (MSL, 1983–2001 tidal epoch);
they are **preliminary** and may be revised. Pairs are exact timestamp matches; no vertical offset or
transformation is applied. Both products are operationally **bias-corrected with recent CO-OPS
observations** (STOFS-2D-Global: station correction from the previous 5 days of nowcast bias;
STOFS-3D-Atlantic: open-boundary adjustment from the 2-day nowcast bias at 11 East Coast stations), so the
comparison describes corrected operational guidance, not independent model skill. The STOFS-3D error is
dominated by tidal phase and amplitude (best-correlated lag {lag(f3["best_lag_min"])} min, model later; model
standard deviation {100 * (f3["sd_ratio"] - 1):.1f}% above observed; the mean bias contributes {100 * bias_share:.0f}% of the
mean squared error) rather than a constant offset; the STOFS-2D lag is {lag(f2["best_lag_min"])} min.
Statistics are given in Table X. Inputs: station NetCDF SHA-256
`{man["stofs_2d_global"]["sha256"][:12]}…` (2D) and `{man["stofs_3d_atlantic"]["sha256"][:12]}…` (3D); CO-OPS
response `{man["coops_water_level_msl"]["sha256"][:12]}…` (full checksums and URLs in the archived manifest).
"""
    (c.FIGURES / "boston_stofs_v31_fig_caption.md").write_text(caption)
    print("\n".join(md))
    print("lags (min):", {k: values[k]["best_lag_min"] for k, _ in COLUMNS})
    return 0


if __name__ == "__main__":
    sys.exit(main())
