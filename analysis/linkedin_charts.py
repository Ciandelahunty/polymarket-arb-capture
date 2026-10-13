"""Five summary images (and a PDF carousel) for sharing the project, e.g. on LinkedIn.

The figures are typed in from the final results.py output (collection ended
7 Oct 2026, 12:50 UTC), so this script needs no data files. Everything you
might want to change - theme, colours, font, wording, size - is in the
SETTINGS block below.

    python analysis/linkedin_charts.py            # writes to analysis/output/linkedin/

The design uses the Inter font if it is installed (free from Google Fonts or
rsms.me/inter); otherwise it falls back to Helvetica or Arial.
"""
import argparse
import csv
import os
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch

# --------------------------------------------------------------------------
# SETTINGS: change anything here
# --------------------------------------------------------------------------
OUT_DIR = Path(__file__).parent / "output" / "linkedin"
SIZE_IN = (10.8, 13.5)        # 4:5 portrait; at DPI 100 this is 1080 x 1350 px
DPI = 100
THEME = "dark"                # "dark" or "light"

THEMES = {
    "dark": {
        "background": "#15191f",  # page
        "panel":      "#1e252d",  # rounded cards behind the content
        "edge":       "#2c3540",  # card borders and grid lines
        "ink":        "#f2f4f7",  # titles and numbers
        "muted":      "#aab4c0",  # subtitles, labels, footnotes
        "quiet":      "#3a4552",  # "nothing happened"
        "blue":       "#4c74ff",  # neutral accent
        "yes":        "#34a85f",  # green: buying / arbitrage present
        "no":         "#ef5a5f",  # red: selling / arbitrage gone
    },
    "light": {
        "background": "#ffffff",
        "panel":      "#f4f6f9",
        "edge":       "#e1e6ec",
        "ink":        "#1b2026",
        "muted":      "#56616e",
        "quiet":      "#cdd4dc",
        "blue":       "#2e5cff",
        "yes":        "#1f9d55",
        "no":         "#e0464b",
    },
}
FONTS = ["Inter", "Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]
FOOTER = "Cian Delahunty  ·  github.com/Ciandelahunty/polymarket-arb-capture"
DISCLAIMER = "Independent project, not affiliated with Polymarket"
PERIOD = "20 Polymarket events  ·  22 Sept – 7 Oct 2026  ·  a snapshot every 2 seconds"

# --------------------------------------------------------------------------
# RESULTS (final run, 7 Oct 2026)
# --------------------------------------------------------------------------
EPISODES = 1387                       # buy-side violation episodes at 1 basket
EPISODES_AT_100 = 11                  # ... that ever reached a violation at 100
SNAPSHOT_VIOLATION_SHARE = 1.2        # % of event-snapshots, buy side, 1 basket
BOT_PROFIT = 12.22                    # USD net, paper bot reacting 2 s late
BOT_PRICE_GAP = 69.61                 # USD: $1 a basket at resolution minus prices paid, before fees
BOT_INTEREST = 21.40                  # USD Treasury bills would have paid on the money until resolution
BOT_FEES = 35.99                      # USD taker fees on those trades
BOT_CAPITAL = 1130.69                 # USD committed across its 867 trades
BOT_TRADES = 867
ENDINGS = [                           # how the 1,387 episodes ended: (label, count, colour key)
    ("Offers withdrawn or repriced before anyone bought", 1343, "quiet"),
    ("Some outcomes traded", 17, "blue"),
    ("One trader bought the whole basket", 27, "yes"),
]
# Gap to the no-arbitrage bound, cents per basket: (p5, p25, median, p75, p95)
GAPS = {
    "Buy 1":    (2.69, 6.84, 12.78, 24.01, 48.87),
    "Buy 100":  (4.11, 10.36, 23.10, 36.35, 107.85),
    "Buy 500":  (5.78, 28.82, 60.07, 117.93, 250.33),
    "Sell 1":   (2.88, 5.99, 10.38, 16.07, 32.74),
    "Sell 100": (3.24, 7.37, 12.46, 20.77, 43.07),
    "Sell 500": (4.02, 13.89, 22.39, 38.87, 73.54),
}
# Buy-side event-snapshots in violation at 500 baskets, by discount rate
RATES = [(0.0, 19058), (3.11, 2087), (4.11, 544), (5.11, 20)]
RATE_USED = 4.11
# Optional sixth image: the full distribution of the buy-side gap at 1 basket. It needs the
# processed data once (python analysis/linkedin_charts.py --with-data), which saves the
# histogram here; later runs reuse the saved file.
HIST_FILE = OUT_DIR / "gap_histogram.csv"
HIST_EDGES = np.arange(-16, 82, 2)    # cents per basket

# --------------------------------------------------------------------------
C = THEMES[THEME]
for folder in filter(None, [os.environ.get("EXTRA_FONT_DIR")]):   # optional: a folder of .ttf files
    for f in Path(folder).glob("*.ttf"):
        font_manager.fontManager.addfont(str(f))
plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": FONTS,
    "text.color": C["ink"], "axes.labelcolor": C["muted"],
    "xtick.color": C["muted"], "ytick.color": C["muted"],
    "axes.edgecolor": C["edge"], "figure.facecolor": C["background"],
    "axes.facecolor": "none", "savefig.facecolor": C["background"],
})


def panel(fig, x, y, w, h, radius=0.025):
    """A rounded card in figure coordinates, drawn behind everything else."""
    fig.patches.append(FancyBboxPatch((x, y), w, h, transform=fig.transFigure, zorder=-1,
                                      boxstyle=f"round,pad=0,rounding_size={radius}",
                                      facecolor=C["panel"], edgecolor=C["edge"], linewidth=1.2))


def pill(fig, x, y, text, colour):
    """A small rounded label, like a Yes/No button."""
    fig.text(x, y, text, fontsize=13, fontweight="bold", color=colour, va="center",
             bbox=dict(boxstyle="round,pad=0.45,rounding_size=0.8", facecolor=colour + "26",
                       edgecolor="none"))


def plain(text):
    """Text drawn literally: a dollar sign is just a dollar sign."""
    return text.replace("\\$", "$")


def page(title, subtitle):
    """A blank page with a title block and footer; returns the figure."""
    fig = plt.figure(figsize=SIZE_IN, dpi=DPI)
    fig.patches.append(plt.Rectangle((0, 0.992), 1, 0.008, transform=fig.transFigure,
                                     facecolor=C["blue"], linewidth=0))
    fig.text(0.07, 0.94, title, fontsize=34, fontweight="bold", va="top", linespacing=1.15)
    fig.text(0.07, 0.855, plain(subtitle), fontsize=18, color=C["muted"], va="top", linespacing=1.45,
             parse_math=False)
    fig.text(0.07, 0.045, FOOTER, fontsize=13, color=C["muted"])
    fig.text(0.07, 0.022, DISCLAIMER, fontsize=11, color=C["muted"], alpha=0.8)
    return fig


def note(fig, text, y=0.125):
    """Explanatory text under a chart."""
    fig.text(0.07, y, plain(text), fontsize=16, color=C["muted"], va="top", linespacing=1.5,
             parse_math=False)


def card_headline():
    fig = page("Most visible arbitrage\ncan't be captured", PERIOD)
    raw = BOT_PRICE_GAP - BOT_FEES
    rows = [
        ("Visible", f"{SNAPSHOT_VIOLATION_SHARE}%",
         "of the time, a basket\ncost less than its \\$1\npayout at the best prices", C["yes"]),
        ("At 100 baskets (about \\$100)", f"{EPISODES_AT_100} of {EPISODES:,}",
         "of those cheap baskets\nwere still profitable\nfor 100 baskets", C["no"]),
        ("Reacting 2 seconds late", f"{raw / BOT_CAPITAL:.1%}",
         f"made by a test bot on\n\\${BOT_CAPITAL:,.0f}, {BOT_PROFIT / BOT_CAPITAL:.1%} more\nthan Treasury bills pay", C["blue"]),
    ]
    for i, (tag, big, small, colour) in enumerate(rows):
        y = 0.685 - i * 0.19
        panel(fig, 0.07, y - 0.08, 0.86, 0.17)
        pill(fig, 0.105, y + 0.052, tag, colour)
        fig.text(0.1, y - 0.015, big, fontsize=46, fontweight="bold", color=C["ink"], va="center")
        fig.text(0.585, y - 0.015, plain(small), fontsize=18, color=C["muted"], va="center",
                 linespacing=1.35, parse_math=False)
    note(fig, "A basket is one share of every outcome in an event. Exactly one outcome wins,\n"
              "so a basket always pays \\$1. Arbitrage is visible when a basket costs less than \\$1\n"
              "at the best listed prices, and capturable when that is still true after fees,\n"
              "at a realistic size, by the time a trader can act.", y=0.19)
    return fig


def card_waffle():
    fig = page("Most cheap baskets vanished\nbefore anyone bought them",
               f"Each square is one stretch of time when a basket could be bought\n"
               f"for less than its \\$1 payout ({EPISODES:,} in all), coloured by how it ended")
    panel(fig, 0.07, 0.27, 0.86, 0.52)
    ax = fig.add_axes([0.1, 0.3, 0.8, 0.46])
    cols = 46
    i = 0
    for label, n, key in ENDINGS:
        for _ in range(n):
            r, c = divmod(i, cols)
            ax.add_patch(FancyBboxPatch((c, -r), 0.78, 0.78, boxstyle="round,pad=0,rounding_size=0.18",
                                        facecolor=C[key], linewidth=0))
            i += 1
    rows = -(-i // cols)
    ax.set_xlim(-0.2, cols)
    ax.set_ylim(-rows + 0.6, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    for k, (label, n, key) in enumerate(ENDINGS):
        y = 0.205 - k * 0.045
        fig.patches.append(FancyBboxPatch((0.07, y - 0.009), 0.022, 0.018, transform=fig.transFigure,
                                          boxstyle="round,pad=0,rounding_size=0.004",
                                          facecolor=C[key], linewidth=0))
        fig.text(0.105, y, f"{n:,}", fontsize=18, fontweight="bold", va="center")
        fig.text(0.19, y, label, fontsize=17, va="center", color=C["ink"])
    return fig


def card_gaps():
    fig = page("Trading every outcome at once\nalmost always loses money",
               "How much more than \\$1 a basket cost to buy, or how much\n"
               "less than \\$1 it raised when sold, after fees")
    panel(fig, 0.07, 0.2, 0.86, 0.6)
    key_ax = fig.add_axes([0.1, 0.735, 0.8, 0.045])   # how to read the marks, inside the panel
    key_ax.set_xlim(0, 10)
    key_ax.set_ylim(-1, 1)
    key_ax.axis("off")
    for x0, kind, label in [(0.2, "dot", "typical"), (2.9, "bar", "half the time"), (6.6, "line", "90% of the time")]:
        if kind == "dot":
            key_ax.plot(x0 + 0.25, 0, "o", markersize=11, color=C["muted"])
        elif kind == "bar":
            key_ax.add_patch(plt.Rectangle((x0, -0.45), 0.7, 0.9, color=C["muted"], alpha=0.35, linewidth=0))
        else:
            key_ax.plot([x0, x0 + 0.7], [0, 0], color=C["muted"], linewidth=2, solid_capstyle="round")
        key_ax.text(x0 + (0.6 if kind == "dot" else 0.95), 0, label, fontsize=15, color=C["muted"], va="center")
    ax = fig.add_axes([0.28, 0.27, 0.61, 0.45])
    names = list(GAPS)[::-1]
    for y, name in enumerate(names):
        p5, p25, med, p75, p95 = GAPS[name]
        colour = C["yes"] if name.startswith("Buy") else C["no"]
        ax.plot([p5, p95], [y, y], color=colour, linewidth=2, solid_capstyle="round", alpha=0.7)
        ax.barh(y, p75 - p25, left=p25, height=0.42, color=colour, alpha=0.3, linewidth=0)
        ax.plot(med, y, "o", markersize=13, color=colour, markeredgecolor=C["panel"], markeredgewidth=2.5)
        ax.text(med, y + 0.38, f"{med:.0f}¢", ha="center", fontsize=14, fontweight="bold")
    side, size = zip(*(n.split() for n in names))
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels([f"{s} {q} basket{'s' if q != '1' else ''}" for s, q in zip(side, size)],
                       fontsize=16, color=C["ink"])
    ax.set_xscale("log")
    ax.set_xlim(1, 300)
    ax.set_xticks([1, 3, 10, 30, 100, 300])
    ax.set_xticklabels(["1¢", "3¢", "10¢", "30¢", "$1", "$3"], fontsize=14)
    ax.xaxis.set_minor_locator(plt.NullLocator())
    ax.annotate("a profit would\nbe below 0¢", xy=(1, -0.85), xytext=(1.6, -0.85), fontsize=13,
                color=C["muted"], va="center", annotation_clip=False,
                arrowprops=dict(arrowstyle="-|>", color=C["muted"], linewidth=1))
    ax.set_ylim(-1.2, len(names) - 0.4)
    ax.grid(axis="x", color=C["edge"], linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ["top", "right", "left", "bottom"]:
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    ax.set_xlabel("cents per basket (log scale)", fontsize=14)
    note(fig,"Bigger trades lose more because the best prices are only available for a few\n"
              "shares. A larger order has to take pricier offers further down the order book.",
         y=0.17)
    return fig


def card_fees():
    fig = page("Fees and interest took\nmost of what the bot found",
               f"What a test bot reacting 2 seconds late made from {BOT_TRADES} trades,\n"
               f"held to resolution, in US dollars and as a share of the \\${BOT_CAPITAL:,.0f} committed")
    panel(fig, 0.07, 0.2, 0.86, 0.6)
    ax = fig.add_axes([0.11, 0.28, 0.78, 0.45])
    steps = [("Profit before\nfees and interest", BOT_PRICE_GAP, C["yes"], True),
             ("Taker fees", -BOT_FEES, C["no"], False),
             ("Interest at 4.11%\na year (T-bills)", -BOT_INTEREST, C["quiet"], False),
             ("Profit above\nTreasury bills", BOT_PROFIT, C["blue"], True)]
    level = 0.0
    for x, (label, value, colour, from_zero) in enumerate(steps):
        lo, hi = (0, value) if from_zero else (level + value, level)
        ax.bar(x, hi - lo, bottom=lo, width=0.56, color=colour, linewidth=0)
        ax.text(x, hi + 1.5, f"{'−' if value < 0 else ''}\\${abs(value):.2f}", ha="center",
                fontsize=19, fontweight="bold")
        ax.text(x, hi + 5.2, f"{'−' if value < 0 else ''}{abs(value) / BOT_CAPITAL:.1%}", ha="center",
                fontsize=13, color=C["muted"])
        new_level = value if from_zero else level + value
        if x < len(steps) - 1:
            ax.plot([x + 0.28, x + 0.72], [new_level, new_level], color=C["muted"], linewidth=1,
                    linestyle=(0, (2, 2)))
        level = new_level
    ax.set_xticks(range(len(steps)))
    ax.set_xticklabels([s[0] for s in steps])
    ax.set_ylim(0, BOT_PRICE_GAP * 1.22)
    ax.set_yticks([])
    ax.tick_params(axis="x", length=0, labelsize=15, labelcolor=C["ink"], pad=10)
    for sp in ["top", "right", "left", "bottom"]:
        ax.spines[sp].set_visible(False)
    raw = BOT_PRICE_GAP - BOT_FEES
    months = BOT_INTEREST / BOT_CAPITAL / (RATE_USED / 100) * 12
    note(fig, f"Treasury bills paying {RATE_USED}% a year would have earned about \\${BOT_INTEREST:.0f} on the same\n"
              f"\\${BOT_CAPITAL:,.0f}, which stays tied up until each event resolves (about {months:.1f} months on\n"
              f"average). After fees the bot made \\${raw:.2f} ({raw / BOT_CAPITAL:.1%}), so only \\${BOT_PROFIT:.2f} "
              f"({BOT_PROFIT / BOT_CAPITAL:.1%}) more.", y=0.17)
    return fig


def card_rates():
    fig = page("What counts as arbitrage\ndepends on the interest rate",
               "Snapshots of an event in which buying 500 baskets (about \\$500)\n"
               "locked in a profit, by the yearly interest rate the money had to beat")
    panel(fig, 0.07, 0.25, 0.86, 0.54)
    ax = fig.add_axes([0.14, 0.38, 0.72, 0.36])
    fig.text(0.1, 0.765, "number of snapshots, log scale", fontsize=13, color=C["muted"], va="top")
    xs = [r[0] for r in RATES]
    ys = [r[1] for r in RATES]
    ax.plot(xs, ys, color=C["muted"], linewidth=1.5, alpha=0.6, zorder=1)
    for x, y in zip(xs, ys):
        used = abs(x - RATE_USED) < 1e-9
        ax.plot(x, y, "o", markersize=18 if used else 13, color=C["blue"] if used else C["muted"],
                markeredgecolor=C["panel"], markeredgewidth=2.5, zorder=2)
        ax.text(x, y * 1.9, f"{y:,}", ha="center", fontsize=18, fontweight="bold")
    used_y = dict(RATES)[RATE_USED]
    ax.plot([RATE_USED, RATE_USED], [8, used_y], color=C["blue"], linewidth=1.5,
            linestyle=(0, (4, 3)), zorder=0)
    ax.set_yscale("log")
    ax.set_ylim(8, 90000)
    ax.set_xlim(-0.5, 5.7)
    ax.set_yticks([])
    ax.yaxis.set_minor_locator(plt.NullLocator())
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{x:g}%\nrate used" if abs(x - RATE_USED) < 1e-9 else f"{x:g}%"
                        for x in xs], fontsize=16, color=C["ink"], va="top")
    for lab, x in zip(ax.get_xticklabels(), xs):
        if abs(x - RATE_USED) < 1e-9:
            lab.set_color(C["blue"])
            lab.set_fontweight("bold")
    ax.tick_params(length=0, pad=10)
    ax.set_xlabel("yearly interest rate (4.11% = 3-month US Treasury bill)", fontsize=14, labelpad=10)
    for s in ["top", "right", "left", "bottom"]:
        ax.spines[s].set_visible(False)
    note(fig, "Most of these snapshots come from one market that pays out in about 15 months.\n"
              "A basket there usually cost about 96–98¢ for a \\$1 payout: a return of 1.5–3.5%\n"
              "a year, less than Treasury bills pay. Locking money away for less than cash earns\n"
              "isn't arbitrage, so only the times when it dipped cheaper count, and how many\n"
              "do depends on the rate chosen.", y=0.215)
    return fig

def save_histogram():
    """Histogram of the buy-side gap at 1 basket from the processed data, saved to HIST_FILE."""
    from episodes import gap_values, needed_columns
    from load import load_processed
    df = load_processed(columns=needed_columns())
    gap = gap_values(df, "buy", 1).where(df["t_years"] > 0).dropna().to_numpy() * 100
    counts, _ = np.histogram(gap, bins=HIST_EDGES)
    with open(HIST_FILE, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["left_c", "right_c", "share"])
        for lo, hi, n in zip(HIST_EDGES[:-1], HIST_EDGES[1:], counts):
            w.writerow([lo, hi, n / len(gap)])
        w.writerow([HIST_EDGES[-1], "inf", (gap >= HIST_EDGES[-1]).sum() / len(gap)])
    print(f"Saved {HIST_FILE} from {len(gap):,} event-snapshots")


def card_distribution():
    rows = list(csv.DictReader(open(HIST_FILE)))
    left = np.array([float(r["left_c"]) for r in rows[:-1]])
    share = np.array([float(r["share"]) for r in rows[:-1]]) * 100
    tail = float(rows[-1]["share"]) * 100
    width = left[1] - left[0]
    below = share[left < 0].sum()
    fig = page("A basket cheaper than \\$1\nwas the rare exception",
               "How far the cost of one share of every outcome was from its \\$1 payout,\n"
               "at the best prices, after fees, across every event and snapshot")
    panel(fig, 0.07, 0.2, 0.86, 0.6)
    ax = fig.add_axes([0.165, 0.29, 0.735, 0.45])
    colours = [C["yes"] if l < 0 else C["quiet"] for l in left]
    shown = np.where((left < 0) & (share > 0), np.maximum(share, share.max() * 0.004), share)
    ax.bar(left + width / 2, shown, width=width * 0.86, color=colours, linewidth=0)
    ax.axvline(0, color=C["ink"], linewidth=1.2)
    ax.text(0.8, share.max() * 1.1, "\\$1 payout", ha="left", fontsize=14, color=C["ink"])
    median = GAPS["Buy 1"][2]
    ax.axvline(median, color=C["blue"], linewidth=1.5, linestyle=(0, (4, 3)))
    ax.text(median + 0.8, share.max() * 0.97, f"typical:\n{median:.0f}¢ over", ha="left", va="top",
            fontsize=13, color=C["blue"])
    ax.set_xlim(left[0], left[-1] + width)
    ax.set_ylim(0, share.max() * 1.15)
    ax.set_xticks([-10, 0, 10, 20, 40, 60, 80])
    ax.set_xticklabels(["10¢ under", "0", "10¢ over", "20¢", "40¢", "60¢", "80¢"], fontsize=13)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.tick_params(length=0, labelsize=13)
    ax.grid(axis="y", color=C["edge"], linewidth=0.8)
    ax.set_axisbelow(True)
    for sp in ["top", "right", "left"]:
        ax.spines[sp].set_visible(False)
    ax.set_ylabel("share of snapshots", fontsize=14, labelpad=8)
    ax.set_xlabel("cost of a basket above its \\$1 payout", fontsize=14)
    # magnified view of the part below $1
    ins = fig.add_axes([0.56, 0.5, 0.31, 0.2])
    neg = left < 0
    top = share[neg].max() if share[neg].max() > 0 else 1
    # Bands with only a handful of snapshots would be a fraction of a pixel tall and vanish;
    # give every non-empty band a thin minimum height so it still shows, as in the main chart.
    heights = np.where(share[neg] > 0, np.maximum(share[neg], top * 0.02), 0)
    ins.bar(left[neg] + width / 2, heights, width=width * 0.86, color=C["yes"], linewidth=0, zorder=3)
    ins.set_xlim(left[0], 0)
    ins.set_ylim(0, top * 1.15)
    ins.yaxis.set_major_locator(plt.MaxNLocator(4))
    ins.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.1f}%"))
    ins.set_xticks([-15, -10, -5, 0])
    ins.set_xticklabels(["15¢", "10¢", "5¢", "0"], fontsize=11)
    ins.tick_params(length=0, labelsize=11, colors=C["muted"])
    for sp in ["top", "right", "left", "bottom"]:
        ins.spines[sp].set_visible(False)
    ins.set_title(f"Under \\$1, magnified: {below:.1f}% of snapshots", fontsize=13, color=C["yes"],
                  loc="left", pad=8)
    note(fig, f"Each bar is a 2¢ band. Green bars are baskets cheaper than \\$1, mostly by a\n"
              f"few cents; the cheapest was 15¢ under. {tail:.0f}% of snapshots cost more than\n"
              "80¢ over and sit off the right of the chart.", y=0.17)
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-data", action="store_true",
                    help="build the distribution image from the processed data (slow, needed once)")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.with_data:
        save_histogram()
    cards = [("1_headline", card_headline), ("2_how_episodes_ended", card_waffle),
             ("3_gaps", card_gaps), ("4_fees", card_fees), ("5_interest_rates", card_rates)]
    if HIST_FILE.exists():
        cards.insert(3, ("3b_distribution", card_distribution))
    else:
        print("No gap histogram yet: run with --with-data once to add the distribution image.")
    with PdfPages(OUT_DIR / "carousel.pdf") as pdf:
        for name, make in cards:
            fig = make()
            fig.savefig(OUT_DIR / f"{name}.png", dpi=DPI)
            pdf.savefig(fig)
            plt.close(fig)
    print(f"Saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
