"""Figure 1: the primary claim, as a forest plot.

Eight local model families, 40 held-out arithmetic items each, step-by-step
policy minus direct answering, with 95% paired-bootstrap intervals over items.
Every family improves; gain tracks available headroom rather than model size.

Reading the figure: qwen3:4b has the highest direct baseline and the smallest
gain, and its interval is the narrowest; llama3.2:1b has a zero baseline and a
mid-sized gain. That ordering is the headroom account of the effect, and it is
the reason the claim is framed as "every family tested" rather than "large effect".

Plotting logic only; all numbers come from raw_data.py.
"""
from __future__ import annotations

import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from raw_data import DATA  # noqa: E402

BLUE = "#0F4D92"
GREY = "#5A5A5A"
LIGHT = "#D9D9D9"


def apply_style() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
        "axes.labelsize": 9.5,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "legend.frameon": False,
        "figure.dpi": 300,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    })


def main() -> None:
    apply_style()
    rows = DATA["rows"]
    fig, ax = plt.subplots(figsize=(6.6, 4.1))
    ypos = list(range(len(rows)))[::-1]

    ax.axvline(0.0, color=GREY, lw=0.9, zorder=1)
    for y, r in zip(ypos, rows):
        ax.plot([r["ci_lo"], r["ci_hi"]], [y, y], color=BLUE, lw=1.8,
                solid_capstyle="round", zorder=3)
        ax.plot([r["gain"]], [y], "o", color=BLUE, ms=5.5, zorder=4,
                markeredgecolor="white", markeredgewidth=0.6)
        ax.plot([r["direct"], r["step_calc"]], [y - 0.22, y - 0.22], color=LIGHT,
                lw=1.1, zorder=2, solid_capstyle="butt")

    ax.set_yticks(ypos)
    ax.set_yticklabels([r["family"] for r in rows])
    ax.set_xlabel("accuracy difference (step-by-step − direct)")
    ax.set_xlim(-0.08, 1.02)
    ax.set_xticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_ylim(-0.5, len(rows) - 0.35)

    handles = [
        plt.Line2D([], [], color=BLUE, marker="o", ms=5.5, lw=1.8,
                   label=f"gain with 95% CI ({DATA['boot_reps']}-rep paired bootstrap)"),
        plt.Line2D([], [], color=LIGHT, lw=1.1,
                   label="direct → step-by-step accuracy"),
    ]
    # Legend above the axes: inside the data area it covered the two lowest
    # families, which are the two with the largest gains.
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.01),
              ncol=2, fontsize=8, handlelength=2.4, borderaxespad=0.0,
              columnspacing=1.6)

    fig.tight_layout(rect=(0, 0.085, 1, 0.94), pad=1.2)
    fig.text(0.012, 0.012,
             f"{DATA['n_families']}/{DATA['n_families']} families improve; "
             f"{DATA['n_items']} held-out items per family. Intervals are "
             f"{DATA['boot_reps']}-rep paired bootstraps over the per-item flags in "
             "the signed bundle.",
             fontsize=7.4, color=GREY, ha="left", va="bottom", wrap=True)
    out = HERE / "fig1_transfer_forest"
    for ext in ("png", "pdf"):
        fig.savefig(out.with_suffix("." + ext), dpi=300,
                    bbox_inches="tight", pad_inches=0.06)
    print(f"wrote {out}.png and {out}.pdf")


if __name__ == "__main__":
    main()
