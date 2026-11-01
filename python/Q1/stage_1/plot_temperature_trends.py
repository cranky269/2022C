# -*- coding: utf-8 -*-
"""Q1 Stage 1: Berkeley global monthly temperature trend & decadal increase plots.

Publication-style figures (Times New Roman + ColorBrewer palette) with English labels.

Outputs:
  Fig.1  March temperature trend over years (absolute temperature global_tmean)
  Fig.2  Annual-mean temperature trend over years
  Fig.3  Decadal increase of March temperature (decade mean diff + within-decade first-to-last)
  Fig.4  Decadal increase of annual-mean temperature (same convention)

Input:  result/Q1/berkeley_global_monthly.csv
Output:
  image/Q1/march_temperature_trend.png
  image/Q1/annual_temperature_trend.png
  image/Q1/march_temperature_increase.png
  image/Q1/annual_temperature_increase.png
  result/Q1/march_decadal_increase.xlsx
  result/Q1/annual_decadal_increase.xlsx
  log/Q1/plot_temperature.log
"""
import logging
import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(BASE, "python", "Q1", "common"))

import pic_config  # noqa: E402

# ------------------------- Tunable parameters -------------------------
DATA_FILE = os.path.join(BASE, "result", "Q1", "berkeley_global_monthly.csv")
IMAGE_DIR = os.path.join(BASE, "image", "Q1")
RESULT_DIR = os.path.join(BASE, "result", "Q1")
LOG_DIR = os.path.join(BASE, "log", "Q1")

TARGET_MONTH = 3      # month of interest
ANCHOR_YEAR = 2022    # decade-grouping anchor: walk back 10 yrs per bin from here
ROLL_WINDOW = 10      # moving-average window (years) for trend plots
POS_KEY = "warm"      # color key for positive (warming) bars
NEG_KEY = "cool"      # color key for negative (cooling) bars

for _d in (IMAGE_DIR, RESULT_DIR, LOG_DIR):
    os.makedirs(_d, exist_ok=True)


# ------------------------- Logging -------------------------
def setup_logger(log_dir):
    logger = logging.getLogger("Q1_plot")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(os.path.join(log_dir, "plot_temperature.log"), encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


# ------------------------- Data loading & series -------------------------
def read_data(path):
    """Read monthly CSV, parse date and add year/month columns."""
    df = pd.read_csv(path, parse_dates=["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df


def month_series(df, month):
    """Yearly series of a given month's absolute temperature, indexed by year."""
    sub = df[df["month"] == month].sort_values("year")
    return pd.Series(sub["global_tmean"].to_numpy(),
                     index=sub["year"].to_numpy(), name=f"month_{month}_tmean")


def annual_series(df):
    """Yearly mean temperature series, indexed by year."""
    return df.groupby("year")["global_tmean"].mean()


# ------------------------- Decadal grouping & increase -------------------------
def build_decadal_bins(min_year, max_year, anchor):
    """Walk back 10-year bins from the anchor year; return [(start, end), ...] ascending."""
    bins = []
    end = anchor
    while end >= min_year:
        start = end - 9
        if start < min_year:
            start = min_year
        bins.append((start, end))
        end = start - 1
    bins.reverse()
    return bins


def decadal_mean(series, bins):
    """Mean value within each bin."""
    return [float(series.loc[(series.index >= s) & (series.index <= e)].mean())
            for s, e in bins]


def decadal_step(means):
    """Consecutive bin mean differences (later - earlier); length = len(means)-1."""
    return [means[i] - means[i - 1] for i in range(1, len(means))]


def decadal_endpoint(series, bins):
    """Within-bin first-to-last difference (last year - first year)."""
    return [float(series.loc[e] - series.loc[s]) for s, e in bins]


def bins_to_labels(bins):
    """(start, end) -> 'start-end' string label."""
    return [f"{s}-{e}" for s, e in bins]


def make_decadal_frame(bins, means, steps, endpoints):
    """Assemble decadal results into a DataFrame; step aligned to the current bin."""
    step_aligned = [None] + steps
    return pd.DataFrame({
        "Decade": bins_to_labels(bins),
        "Start": [s for s, _ in bins],
        "End": [e for _, e in bins],
        "Decade mean (degC)": [round(float(m), 4) for m in means],
        "Increase vs previous decade (degC)": [None if s is None else round(float(s), 4) for s in step_aligned],
        "Within-decade first-to-last (degC)": [round(float(v), 4) for v in endpoints],
    })


# ------------------------- Plotting helpers -------------------------
def _style_axes(ax, cfg, pal, zero_line=False):
    ax.grid(True, axis="y", alpha=cfg["axes"]["grid_alpha"],
            linestyle=cfg["axes"]["grid_linestyle"],
            linewidth=cfg["axes"]["grid_linewidth"], color=pal["grid"])
    ax.spines["top"].set_visible(cfg["axes"]["spines_top"])
    ax.spines["right"].set_visible(cfg["axes"]["spines_right"])
    if zero_line:
        ax.axhline(0, color=pal["neutral"], lw=0.8)


def sign_colors(values, pal):
    return [pal[POS_KEY] if v >= 0 else pal[NEG_KEY] for v in values]


def plot_trend(x, y, ylabel, title, out_path, cfg):
    """Trend line chart: annual values + moving average."""
    pal = cfg["palette"]
    fig, ax = plt.subplots(figsize=cfg["figure"]["figsize"], dpi=cfg["figure"]["dpi"])

    ax.plot(x, y, color=pal["primary"], lw=1.0, alpha=0.85,
            marker="o", markersize=2.5, markevery=10, label="Annual value", zorder=2)

    roll = pd.Series(y, index=x).rolling(ROLL_WINDOW, center=True, min_periods=1).mean()
    ax.plot(roll.index.to_numpy(), roll.to_numpy(), color=pal["secondary"], lw=2.0,
            label=f"{ROLL_WINDOW}-yr moving average", zorder=3)

    ax.set_xlabel("Year")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    _style_axes(ax, cfg, pal)
    ax.legend(frameon=False, loc="lower right")
    fig.savefig(out_path, bbox_inches=cfg["save"]["bbox_inches"],
                pad_inches=cfg["save"]["pad_inches"])
    plt.close(fig)


def plot_increase(frame, title, out_path, cfg):
    """Decadal increase chart: decade-mean difference between consecutive decades."""
    pal = cfg["palette"]
    fig, ax = plt.subplots(figsize=cfg["figure"]["figsize"], dpi=cfg["figure"]["dpi"])

    # consecutive decade-mean differences (drop the first bin with no baseline)
    sub = frame.iloc[1:].reset_index(drop=True)
    labs = sub["Decade"].to_numpy()
    vals = sub["Increase vs previous decade (degC)"].to_numpy(dtype=float)
    xs = np.arange(len(vals))

    bars = ax.bar(xs, vals, color=sign_colors(vals, pal), width=0.7)
    # value labels on top of each bar (signed)
    ax.bar_label(bars, fmt=lambda v: f"{v:+.2f}", fontsize=8,
                 padding=2, color=pal["text"])
    # line through the midpoints (bar-top centers)
    ax.plot(xs, vals, color=pal["text"], marker="o", markersize=4,
            lw=1.3, zorder=5)

    ax.set_xticks(xs)
    ax.set_xticklabels(labs, rotation=60, ha="right", fontsize=9)
    ax.set_ylabel("Increase (degC)")
    ax.set_title(title + "\n(Decade mean minus previous decade mean)")
    _style_axes(ax, cfg, pal, zero_line=True)

    fig.savefig(out_path, bbox_inches=cfg["save"]["bbox_inches"],
                pad_inches=cfg["save"]["pad_inches"])
    plt.close(fig)


# ------------------------- Result export -------------------------
def write_xlsx(frame, note_lines, out_path):
    """Write xlsx: 'Data' sheet + 'Notes' sheet (text explaining the data)."""
    with pd.ExcelWriter(out_path, engine="openpyxl") as w:
        frame.to_excel(w, sheet_name="Data", index=False)
        pd.DataFrame({"Note": note_lines}).to_excel(w, sheet_name="Notes", index=False)


def note_lines_for(series_name):
    return [
        f"Decadal statistics of global {series_name} temperature (Berkeley Earth).",
        "Source: result/Q1/berkeley_global_monthly.csv",
        f"Decade bins: walk back every 10 years from {ANCHOR_YEAR} (2022-2013, 2012-2003, ...); first bin is incomplete.",
        "Decade mean (degC): mean of all yearly values within the bin.",
        "Increase vs previous decade (degC): this bin mean - previous bin mean (empty for the first bin).",
        "Within-decade first-to-last (degC): last year - first year of the bin.",
    ]


# ------------------------- Main -------------------------
def main():
    logger = setup_logger(LOG_DIR)
    logger.info("Reading data: %s", DATA_FILE)
    df = read_data(DATA_FILE)
    logger.info("Data range: %s ~ %s, %d rows",
                df["date"].min().date(), df["date"].max().date(), len(df))

    cfg = pic_config.apply_mpl_style()
    min_year = int(df["year"].min())
    max_year = int(df["year"].max())

    march = month_series(df, TARGET_MONTH)
    annual = annual_series(df)

    # Fig.1 / Fig.2: trends
    plot_trend(march.index.to_numpy(), march.to_numpy(), "March temperature (degC)",
               "Global March Mean Temperature Trend (1850-2022)",
               os.path.join(IMAGE_DIR, "march_temperature_trend.png"), cfg)
    plot_trend(annual.index.to_numpy(), annual.to_numpy(), "Annual mean temperature (degC)",
               "Global Annual Mean Temperature Trend (1850-2022)",
               os.path.join(IMAGE_DIR, "annual_temperature_trend.png"), cfg)

    bins = build_decadal_bins(min_year, max_year, ANCHOR_YEAR)
    logger.info("Decade bins: %d bins, first %s, last %s",
                len(bins), bins_to_labels(bins)[0], bins_to_labels(bins)[-1])

    # Fig.3 / Fig.4: decadal increase
    for name, series, tag in (("March", march, "march"),
                              ("Annual-mean", annual, "annual")):
        means = decadal_mean(series, bins)
        steps = decadal_step(means)
        ends = decadal_endpoint(series, bins)
        frame = make_decadal_frame(bins, means, steps, ends)
        write_xlsx(frame, note_lines_for(name.lower()),
                   os.path.join(RESULT_DIR, f"{tag}_decadal_increase.xlsx"))
        plot_increase(frame, f"Decadal Increase in Global {name} Temperature",
                      os.path.join(IMAGE_DIR, f"{tag}_temperature_increase.png"), cfg)
        logger.info("%s: decade-mean range [%.3f, %.3f]", name, min(means), max(means))

    logger.info("Done. Figures -> %s, tables -> %s", IMAGE_DIR, RESULT_DIR)


if __name__ == "__main__":
    main()
