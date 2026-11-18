"""Make the report figures (F1, F2, F4, optional large-scale), partA_summary.md and numbers.tex.

Reads only the CSVs in results/ (or results/quick/ with --quick). Style: figures/qmp.mplstyle, fixed method colors.
"""
import _bootstrap  # noqa: F401
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from experiments.analysis import THRESHOLD, VERDICT_Q, summarize, verdict_table
from experiments.common import ROOT, Timer, out_dir
from experiments.outputs import load_csv, paper_values, write_numbers, write_summary

BLUE, VERMILLION, GREY, GREEN, PURPLE = "#0072B2", "#D55E00", "#555555", "#009E73", "#7B3294"
# method -> (color, linestyle, marker, legend label). ILP solid, heuristic dashed.
STYLE = {
    "SP-SPF": (GREY, "--", "x", "SP-SPF"),
    "SP-Heu": (VERMILLION, "--", "s", "SP-Heu"),
    "MP-Heu": (BLUE, "--", "o", "MP-Heu"),
    "SP-ILP": (VERMILLION, "-", "s", "SP-ILP"),
    "MP-ILP": (BLUE, "-", "o", "MP-ILP"),
    "MP-Heu-d1": (PURPLE, "-.", "^", r"MP-Heu, $\delta=1$"),
    "MP-Heu-deadline": (GREEN, "--", "D", "MP-Heu-deadline"),
    "MP-ILP-delta": (GREY, ":", "v", r"MP-ILP-$\delta$"),
}
IEEE_WIDTH = 7.16


def draw_method(ax, summary: pd.DataFrame, method: str, x: str, label=None) -> None:
    """One method's mean line with its 95% CI band."""
    color, ls, marker, name = STYLE[method]
    s = summary[summary["method"] == method].sort_values(x)
    ax.fill_between(s[x], s["mean"] - s["ci"], s["mean"] + s["ci"], color=color, alpha=0.18, linewidth=0)
    ax.plot(s[x], s["mean"], color=color, linestyle=ls, marker=marker, label=label or name)


def paper_marker(ax, x, y, marker="o", label=None) -> None:
    ax.plot([x], [y], linestyle="none", marker=marker, markersize=6, markerfacecolor="none",
            markeredgecolor="black", markeredgewidth=1.0, label=label, zorder=5)


def save(fig, base: Path) -> None:
    base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(base.with_suffix(".png"), dpi=300)
    fig.savefig(base.with_suffix(".pdf"))
    plt.close(fig)
    print(f"wrote {base.with_suffix('.png')}")


def figure_f1(small, load, fig_dir: Path, paper: dict) -> None:
    """F1: blocking ratio vs q (left) and vs |R| at q=0.7 (right)."""
    methods = ["SP-SPF", "SP-Heu", "MP-Heu", "SP-ILP", "MP-ILP"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(IEEE_WIDTH, 2.85))
    s = summarize(small, ["method", "q"], "blocking_ratio")
    for m in methods:
        draw_method(ax1, s, m, "q")
    if 0.9 in set(small["q"]):
        printed = paper["small"]["blocking_ratio_at_q09"]
        paper_marker(ax1, 0.9, printed["MP-ILP"], label="paper (printed, q = 0.9)")
        paper_marker(ax1, 0.9, printed["SP-ILP"])
        for m in ("SP-ILP", "MP-ILP"):
            ax1.annotate(f"paper {m} {printed[m]:.2f}", (0.9, printed[m]), xytext=(-8, 0),
                         textcoords="offset points", ha="right", va="center", fontsize=7)
    ax1.set_xlabel("link success probability q")
    ax1.set_ylabel("blocking ratio")
    ax1.set_xticks(sorted(small["q"].unique()))
    handles, names = ax1.get_legend_handles_labels()
    fig.legend(handles, names, loc="lower center", ncol=6, handlelength=2.4, columnspacing=1.2,
               bbox_to_anchor=(0.5, 0.0))
    if load is not None:
        sl = summarize(load, ["method", "R"], "blocking_ratio")
        for m in methods:
            draw_method(ax2, sl, m, "R")
        ax2.set_xticks(sorted(load["R"].unique()))
    ax2.set_xlabel(r"requests $|R|$ (q = 0.7)")
    ax2.set_ylabel("blocking ratio")
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    save(fig, fig_dir / "F1_partA_blocking")


def figure_f2(small, fig_dir: Path, paper: dict) -> None:
    """F2: Gamma vs q for MP-Heu and MP-ILP with the paper's Table I values."""
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    s = summarize(small, ["method", "q"], "gamma")
    labels = {"MP-Heu": "MP-Heu\n(calibration target)", "MP-ILP": "MP-ILP\n(held out)"}
    qs = sorted(small["q"].unique())
    for m in ("MP-Heu", "MP-ILP"):
        draw_method(ax, s, m, "q", label="_nolegend_")
        last = s[(s["method"] == m) & (s["q"] == qs[-1])].iloc[0]
        ax.annotate(labels[m], (qs[-1], last["mean"]), xytext=(6, 0), textcoords="offset points",
                    color=STYLE[m][0], va="center", fontsize=8)
    for m, marker in (("MP-Heu", "o"), ("MP-ILP", "s")):
        vals = [v for q, v in zip(paper["q"], paper["small"]["gamma"][m]) if q in qs]
        ax.plot([q for q in paper["q"] if q in qs], vals, linestyle="none", marker=marker, markersize=6,
                markerfacecolor="none", markeredgecolor="black", label=f"paper Table I, {m}")
    ax.set_xlim(qs[0] - 0.03, qs[-1] + 0.33)
    ax.set_xticks(qs)
    ax.set_xlabel("link success probability q")
    ax.set_ylabel(r"$\Gamma$ (multipath share)")
    ax.legend(loc="upper right", fontsize=7)
    fig.tight_layout()
    save(fig, fig_dir / "F2_partA_gamma")


def figure_f4(partc, fig_dir: Path) -> None:
    """F4: extension. Left: BR vs q for five variants. Right: paired difference to MP-Heu with CI bars."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(IEEE_WIDTH, 2.5))
    s = summarize(partc, ["method", "q"], "blocking_ratio")
    for m in ("MP-Heu", "MP-Heu-d1", "MP-Heu-deadline", "MP-ILP", "MP-ILP-delta"):
        draw_method(ax1, s, m, "q")
    ax1.set_xlabel("link success probability q")
    ax1.set_ylabel("blocking ratio")
    ax1.set_xticks(sorted(partc["q"].unique()))
    ax1.legend(loc="upper right")
    v = verdict_table(partc)
    ax2.errorbar(v["q"], v["deadline_diff"], yerr=v["deadline_ci"], color=GREEN, marker="D", linestyle="--",
                 label=r"BR(MP-Heu) $-$ BR(deadline)")
    ax2.axhline(THRESHOLD, color="black", linestyle="--", linewidth=0.9, label=f"pre-registered threshold {THRESHOLD}")
    ax2.axhline(0, color="black", linewidth=0.6)
    ax2.set_xlabel("link success probability q")
    ax2.set_ylabel("paired BR difference")
    ax2.set_xticks(sorted(partc["q"].unique()))
    ax2.legend(loc="upper right")
    fig.tight_layout()
    save(fig, fig_dir / "F4_partC_extension")


def figure_large(large, fig_dir: Path, paper: dict) -> None:
    """Extra: large-scale blocking ratio vs q, SP-Heu and MP-Heu at each t_c, with the paper's printed q=0.9 values."""
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    markers = {10: "o", 20: "^"}
    for tc, g in large.groupby("tc"):
        s = summarize(g, ["method", "q"], "blocking_ratio")
        for m in ("SP-Heu", "MP-Heu"):
            color, ls, _, _ = STYLE[m]
            d = s[s["method"] == m].sort_values("q")
            ax.fill_between(d["q"], d["mean"] - d["ci"], d["mean"] + d["ci"], color=color, alpha=0.18, linewidth=0)
            ax.plot(d["q"], d["mean"], color=color, linestyle=ls, marker=markers[tc], label=f"{m}, $t_c$={tc}")
        key = f"tc{tc}"
        for m in ("SP-Heu", "MP-Heu"):
            paper_marker(ax, 0.9, paper["large"]["blocking_ratio_at_q09"][key][m], marker=markers[tc],
                         label="paper (printed)" if (tc, m) == (10, "SP-Heu") else None)
    ax.set_xlabel("link success probability q")
    ax.set_ylabel("blocking ratio")
    ax.legend(loc="upper right", fontsize=7)
    fig.tight_layout()
    save(fig, fig_dir / "extra" / "large_scale")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    results = out_dir(args.quick)
    fig_dir = ROOT / "figures" / "quick" if args.quick else ROOT / "figures"
    numbers = results / "numbers.tex" if args.quick else ROOT / "report" / "numbers.tex"
    plt.style.use(str(ROOT / "figures" / "qmp.mplstyle"))
    paper = paper_values()
    with Timer():
        small, load = load_csv(results, "partA_small.csv"), load_csv(results, "partA_load.csv")
        partc, large = load_csv(results, "partC.csv"), load_csv(results, "partA_large.csv")
        figure_f1(small, load, fig_dir, paper)
        figure_f2(small, fig_dir, paper)
        if partc is not None:
            figure_f4(partc, fig_dir)
        if large is not None:
            figure_large(large, fig_dir, paper)
        write_summary(results)
        write_numbers(results, numbers)
        print(f"wrote {results / 'partA_summary.md'} and {numbers}")


if __name__ == "__main__":
    main()
