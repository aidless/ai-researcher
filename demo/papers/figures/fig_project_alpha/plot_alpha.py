"""Figure 2: what survives correcting for the number of arms.

Each arm in this study was analysed on its own, so the family-wise error rate is
0.05 per arm times the number of arms. This figure shows the project-level
Benjamini-Hochberg value for every primary endpoint that can be recomputed from
per-item evidence, on a log scale, against the 0.05 line.

Two endpoints clear it, and they are the same effect measured twice (arithmetic
transfer, on 8 families and on 2). Three of the endpoints that do not clear it
were reported as findings in earlier drafts of this paper. The swarm-amplification
arm is the clearest case: five seeds, excess +0.032, a nominal interval of
[0.001, 0.063] that is within-run evidence and no more.

The figure also carries the two caveats that make these values optimistic: arms
with a directional claim but no recomputable test sit outside the family, and one
arm is excluded as withdrawn. Both are annotated rather than left to the caption,
because a multiplicity plot whose denominator is understated is the kind of chart
that flatters its author.

Plotting logic only; numbers come from raw_data.py.
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
RED = "#B03A2E"
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
    fig, ax = plt.subplots(figsize=(6.9, 3.9))
    ypos = list(range(len(rows)))[::-1]

    ax.axvline(DATA["alpha"], color=GREY, lw=1.0, ls=(0, (4, 3)), zorder=1)
    for y, r in zip(ypos, rows):
        colour = BLUE if r["survives"] else RED
        ax.plot([1e-18, r["plot_p"]], [y, y], color=LIGHT, lw=1.0, zorder=2)
        ax.plot([r["plot_p"]], [y], "o", color=colour, ms=6.5, zorder=3,
                markeredgecolor="white", markeredgewidth=0.7)

    ax.set_xscale("log")
    ax.set_xlim(1e-18, 3.0)
    ax.set_xticks([1e-16, 1e-12, 1e-8, 1e-4, 1e-2])
    ax.set_xticklabels(["1e-16", "1e-12", "1e-8", "1e-4", "1e-2"])
    ax.set_yticks(ypos)
    ax.set_yticklabels([r["label"] for r in rows])
    ax.set_ylim(-0.6, len(rows) - 0.3)
    ax.set_xlabel("project-level Benjamini-Hochberg p  (family of "
                  f"{DATA['family_size']} primary endpoints)")

    ax.text(DATA["alpha"], len(rows) - 0.45, "  α = 0.05", color=GREY,
            fontsize=8, va="center", ha="left")

    handles = [
        plt.Line2D([], [], color=BLUE, marker="o", ms=6.5, lw=0,
                   label=f"survives correction ({DATA['n_surviving']}/"
                         f"{DATA['family_size']})"),
        plt.Line2D([], [], color=RED, marker="o", ms=6.5, lw=0,
                   label="does not survive"),
    ]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.01),
              ncol=2, fontsize=8, handlelength=1.2, borderaxespad=0.0,
              columnspacing=1.8)

    fig.tight_layout(rect=(0, 0.10, 1, 0.93), pad=1.2)
    n_untested = len(DATA["untested_directional_claims"])
    fig.text(0.012, 0.012,
             f"Both survivors are the arithmetic transfer effect. "
             f"{n_untested} further arms carry a directional claim with no "
             "recomputable test and therefore sit outside this family, so every "
             "value shown is optimistic;\n"
             f"{len(DATA['withdrawn'])} arm is excluded as withdrawn "
             f"({', '.join(DATA['withdrawn']) or 'none'}).",
             fontsize=7.4, color=GREY, ha="left", va="bottom")
    out = HERE / "fig2_project_alpha"
    for ext in ("png", "pdf"):
        fig.savefig(out.with_suffix("." + ext), dpi=300,
                    bbox_inches="tight", pad_inches=0.06)
    print(f"wrote {out}.png and {out}.pdf")


if __name__ == "__main__":
    main()
