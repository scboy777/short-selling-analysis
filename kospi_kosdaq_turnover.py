# =============================================================================
# KOSPI / KOSDAQ Daily Turnover (거래대금) Charts
# =============================================================================
#
# Generates two charts showing ~3 months of daily trading value with a
# 20-day moving average overlay.  Data sourced from Bloomberg via xbbg.
#
# Requirements:
#   pip install xbbg==0.7.7 matplotlib seaborn pandas
#
# Usage:
#   python kospi_kosdaq_turnover.py              → save PNGs to current dir
#   python kospi_kosdaq_turnover.py --show       → also display interactively
#   python kospi_kosdaq_turnover.py -o ~/charts  → save to custom directory
# =============================================================================

import argparse
from datetime import date, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns
from xbbg import blp

# ── Bloomberg tickers ────────────────────────────────────────────────────────
INDEXES = [
    {"bbg": "KOSPI Index",  "label": "KOSPI",  "fname": "kr_kospi_turnover.png"},
    {"bbg": "KOSDAQ Index", "label": "KOSDAQ", "fname": "kr_kosdaq_turnover.png"},
]

# ── Style palette ────────────────────────────────────────────────────────────
BG    = "#f5f6f7"
SPINE = "#9ca3af"
TEXT  = "#1f2933"
NAVY  = "#003a5d"
AMBER = "#d97706"

SESSIONS = 65      # ~3 months of trading days to display
BUFFER   = 130     # calendar-day lookback to ensure enough sessions
AVG_WIN  = 20      # moving-average window


def fetch_turnover(bbg_ticker: str, start: str, end: str) -> pd.Series:
    """Fetch daily turnover (KRW) for a Bloomberg index ticker via BDH."""
    df = blp.bdh(bbg_ticker, "TURNOVER", start, end)
    if df.empty:
        return pd.Series(dtype=float)
    # xbbg returns MultiIndex columns (ticker, field) — flatten
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(0)
    return df["TURNOVER"].dropna()


def draw_turnover_chart(
    tv: pd.Series,
    label: str,
    output_path: Path,
) -> Path:
    """Draw a single turnover bar chart with 20-day average line."""
    # Convert KRW → 조원 (trillions), keep last N sessions
    tv_tr = (tv / 1e12).iloc[-SESSIONS:]
    avg_20d = tv_tr.iloc[-AVG_WIN:].mean()

    sns.set_style("white")
    sns.set_context("talk", font_scale=1.0)

    fig, ax = plt.subplots(figsize=(16, 7))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    vals = tv_tr.to_numpy(dtype=float)
    x = list(range(len(tv_tr)))

    ax.bar(x, vals, color=NAVY, edgecolor="none", width=0.7)
    ax.axhline(avg_20d, color=AMBER, linewidth=2, linestyle="--",
               label=f"20D avg  {avg_20d:.2f} Wtn")

    # Annotate today's bar
    last_val = vals[-1]
    annot_y = max(last_val, avg_20d) * 1.18
    ax.annotate(
        f"{last_val:.2f} Wtn",
        xy=(x[-1], last_val),
        xytext=(x[-1], annot_y),
        ha="center", va="bottom",
        fontsize=20, fontweight="bold", color=AMBER,
        arrowprops=dict(
            arrowstyle="-|>", color=AMBER, lw=2.0,
            connectionstyle="arc3,rad=0.0",
        ),
    )

    # X-axis: ~10 evenly spaced date labels
    step = max(1, len(tv_tr) // 10)
    xtick_pos = list(range(0, len(tv_tr), step))
    ax.set_xticks(xtick_pos)
    ax.set_xticklabels(
        [tv_tr.index[i].strftime("%m/%d") for i in xtick_pos],
        rotation=45, ha="right", fontsize=11,
    )
    ax.set_xlim(-0.5, len(tv_tr) - 0.5)

    # Spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(SPINE)
    ax.tick_params(axis="both", colors=TEXT)

    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{v:.1f} Wtn")
    )
    ax.set_title(
        f"{label} Daily Trading Value Trend",
        loc="left", fontsize=18, fontweight="bold", color=TEXT, pad=16,
    )
    legend = ax.legend(frameon=False, fontsize=12, loc="upper right")
    for txt in legend.get_texts():
        txt.set_color(TEXT)

    fig.text(0.01, 0.01, "Source: Bloomberg via xbbg",
             ha="left", va="bottom", fontsize=9, color="#6b7280")
    fig.tight_layout(pad=2.0)

    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="KOSPI/KOSDAQ turnover charts")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("."),
                        help="Directory to save PNGs (default: current dir)")
    parser.add_argument("--show", action="store_true",
                        help="Display charts interactively after saving")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    end = date.today()
    start = end - timedelta(days=BUFFER)
    start_s, end_s = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    for idx in INDEXES:
        print(f"Fetching {idx['label']} turnover …")
        tv = fetch_turnover(idx["bbg"], start_s, end_s)
        if tv.empty:
            print(f"  ⚠ No data for {idx['label']} — skipping")
            continue

        out = draw_turnover_chart(tv, idx["label"], args.output_dir / idx["fname"])
        print(f"  ✓ Saved → {out}")

    if args.show:
        # Re-open saved images for interactive display
        for idx in INDEXES:
            p = args.output_dir / idx["fname"]
            if p.exists():
                img = plt.imread(str(p))
                fig, ax = plt.subplots(figsize=(14, 6))
                ax.imshow(img)
                ax.axis("off")
                fig.suptitle(idx["label"])
        plt.show()


if __name__ == "__main__":
    main()
