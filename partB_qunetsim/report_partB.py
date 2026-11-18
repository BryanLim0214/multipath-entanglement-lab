"""Reads results/partB*.csv and writes results/partB_summary.md and figures/F3_partB_success.(png|pdf).
Every number in the summary and the figure comes from the CSV files; nothing is typed by hand.
"""
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qmp.stats import mean_ci          # noqa: E402

SP_COLOR, MP_COLOR = "#D55E00", "#0072B2"
KEYS = ["experiment", "topology", "method", "k", "q", "M", "n", "drop_rate"]


def fmt(values, digits=2):
    """'mean ± half-width' with the shared decimal rule (2 places)."""
    m, h = mean_ci(values)
    return f"{m:.{digits}f} ± {h:.{digits}f}"


def per_setting(df):
    """One row per setting with the mean and 95% CI of each metric across seeds."""
    rows = []
    for key, g in df.groupby(KEYS, dropna=False, sort=True):
        row = dict(zip(KEYS, key))
        sr_m, sr_h = mean_ci(g["success_rate"])
        row.update(seeds=len(g), sr_mean=sr_m, sr_half=sr_h, success=fmt(g["success_rate"]),
                   time=fmt(g["completion_time"].dropna()) if g["completion_time"].notna().any() else "n/a",
                   attempts=fmt(g["attempts"] / g["requests"], 1),
                   corr=f"{g['correlated'].sum()}/{g['delivered'].sum()}")
        rows.append(row)
    return pd.DataFrame(rows)


def md_table(df, cols, heads):
    """Markdown table from selected columns."""
    lines = ["| " + " | ".join(heads) + " |", "|" + "---|" * len(heads)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def wilson(successes, trials, z=1.959964):
    """95% Wilson score interval for a binomial proportion. Unlike a t interval it stays valid at 0 and 1."""
    if trials == 0:
        return 0.0, 1.0
    p = successes / trials
    centre = (p + z * z / (2 * trials)) / (1 + z * z / trials)
    half = z * ((p * (1 - p) / trials + z * z / (4 * trials * trials)) ** 0.5) / (1 + z * z / trials)
    return centre - half, centre + half


def analytic_check(s, an, df=None):
    """E1 and E2 settings with the analytic value, and whether it lies inside a 95% Wilson interval of the pooled
    requests. In E1 and E2 each window holds one request and every link refills each window, so requests are
    independent trials; a t interval over seeds has zero width whenever all seeds agree (all 0 or all 1)."""
    if df is None:
        df = pd.read_csv(ROOT / "results" / "partB.csv")
    an = an.assign(n=an.n.astype(str))
    m = s[s.experiment.isin(["E1", "E2"])].assign(n=lambda d: d.n.astype(str)).merge(an, on=["experiment", "topology", "method", "k", "q", "M", "n"])
    pooled = df.assign(n=df.n.astype(str)).groupby(["experiment", "method", "q", "n"])[["served", "requests"]].sum()
    bounds = [wilson(*pooled.loc[(r.experiment, r.method, r.q, r.n)]) for r in m.itertuples()]
    m["lo"], m["hi"] = [b[0] for b in bounds], [b[1] for b in bounds]
    m["inside"] = (m.analytic >= m.lo - 1e-12) & (m.analytic <= m.hi + 1e-12)
    m["analytic_s"] = m.analytic.map(lambda x: f"{x:.2f}")
    m["inside_s"] = m.inside.map({True: "yes", False: "NO"})
    return m


def summary(df, s, an, to):
    """Write results/partB_summary.md."""
    out = ["# Part B summary (QuNetSim)", "",
           "Mean ± 95% CI (t interval) over seeds, from `results/partB.csv`. Success rate = served requests / requests.",
           "Completion time is the mean seconds per served request (simulator wall clock). Attempts are per request.",
           "Correlated = delivered pairs that passed the Z/X check / delivered pairs (QuNetSim exposes no fidelity).", ""]
    heads = ["topology", "method", "k", "q", "M", "n", "seeds", "success rate", "time (s)", "attempts", "correlated"]
    cols = ["topology", "method", "k", "q", "M", "n", "seeds", "success", "time", "attempts", "corr"]
    for exp, title in [("E1", "E1 chain, sanity"), ("E2", "E2 two-branch"), ("E3", "E3 3x3 grid with contention"),
                       ("E3_sensitivity", "Sensitivity: k = 3 on the grid")]:
        out += [f"## {title}", "", md_table(s[s.experiment == exp], cols, heads), ""]
    e4 = s[s.experiment == "E4"]
    out += ["## E4 simulator packet drop (q = 1, budget never binds)", "",
            md_table(e4, ["topology", "method", "k", "drop_rate", "seeds", "success", "time", "attempts", "corr"],
                     ["topology", "method", "k", "drop rate", "seeds", "success rate", "time (s)", "attempts", "correlated"]), ""]
    m = analytic_check(s, an)
    out += ["## Analytic check (E1, E2)", "",
            "Is the analytic value inside the 95% Wilson interval of the pooled requests (20 seeds x 10 independent requests)?", "",
            md_table(m.assign(wil=[f"{a:.3f} to {b:.3f}" for a, b in zip(m.lo, m.hi)]),
                     ["experiment", "method", "q", "n", "success", "wil", "analytic_s", "inside_s"],
                     ["experiment", "method", "q", "n", "simulated", "Wilson 95%", "analytic", "inside"]), "",
            f"Inside: {int(m.inside.sum())} of {len(m)} settings.", ""]
    miss = m[~m.inside]
    out += ["Misses: " + (", ".join(f"{r.method} q={r.q} n={r.n} (sim {r.sr_mean:.3f}, analytic {r.analytic:.3f})"
                                    for r in miss.itertuples()) or "none") + ".", ""]
    wins = []
    for exp in ["E2", "E3"]:
        sub = df[df.experiment == exp].assign(n=lambda d: d.n.astype(str))
        piv = sub.pivot_table(index=["topology", "q", "M", "n", "seed"], columns="method", values="success_rate")
        d = piv["MP"] - piv["SP"]
        wins.append((exp, d.mean(), (d > 0).sum(), (d < 0).sum(), len(d)))
    out += ["## MP minus SP, paired by seed", "",
            "| experiment | mean difference | runs MP better | runs SP better | runs |", "|---|---|---|---|---|"]
    for exp, md, up, dn, n in wins:
        out.append(f"| {exp} | {md:.3f} | {up} | {dn} | {n} |")
    out += ["", "## Timeouts and totals", "",
            f"Runs: {len(df)}. Requests: {int(df.requests.sum())}. Timeouts (simulator waits that expired): "
            f"{int(to.timeouts.sum())}, of which in E4: {int(to[to.experiment == 'E4'].timeouts.sum())}.",
            f"Delivered pairs correlated: {int(df.correlated.sum())} of {int(df.delivered.sum())}."]
    (ROOT / "results" / "partB_summary.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def figure(s, an):
    """F3: (a) two-branch n=4 success vs q, (b) grid SP vs MP."""
    plt.style.use(str(ROOT / "figures" / "qmp.mplstyle"))
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.16, 2.5))
    two = s[(s.experiment == "E2") & (s.n.astype(str) == "4")]
    for method, color in (("SP", SP_COLOR), ("MP", MP_COLOR)):
        d = two[two.method == method].sort_values("q")
        a.errorbar(d.q, d.sr_mean, yerr=d.sr_half, color=color, marker="o", ms=3, capsize=2)
        z = an[(an.experiment == "E2") & (an.method == method) & (an.n == 4)].sort_values("q")
        a.plot(z.q, z.analytic, color="black", lw=0.6)
        a.text(d.q.iloc[-1] + 0.01, d.sr_mean.iloc[-1], f"{'Multipath' if method == 'MP' else 'Single-path'}",
               color=color, va="center", fontsize=8)
    a.text(0.5, 0.97, "thin black: analytic", fontsize=7, color="#333333", va="top")
    a.set_title("(a) Two-branch network, n = 4, M = 4")
    for ax, ttl in ((b, "(b) 3x3 grid, 4 requests per window, M = 6"),):
        grid = s[s.experiment == "E3"]
        for method, color in (("SP", SP_COLOR), ("MP", MP_COLOR)):
            d = grid[grid.method == method].sort_values("q")
            ax.errorbar(d.q, d.sr_mean, yerr=d.sr_half, color=color, marker="o", ms=3, capsize=2)
            ax.text(d.q.iloc[-1] + 0.01, d.sr_mean.iloc[-1], "Multipath" if method == "MP" else "Single-path",
                    color=color, va="center", fontsize=8)
        ax.set_title(ttl)
    for ax in (a, b):
        ax.set_xlabel("link success probability q")
        ax.set_ylim(0, 1.02)
        ax.set_xlim(0.47, 1.0)
    a.set_ylabel("request success rate (mean, 95% CI)")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(ROOT / "figures" / f"F3_partB_success.{ext}")


WORD = {"E1": "One", "E2": "Two", "E3": "Three", "E3_sensitivity": "ThreeK", "E4": "Four",
        "chain": "Chain", "two_branch": "Branch", "grid": "Grid",
        0.0: "Zero", 0.1: "One", 0.2: "Two", 0.3: "Three", 0.5: "Five", 0.6: "Six", 0.7: "Seven", 0.8: "Eight",
        0.9: "Nine", 1.0: "Ten", "1": "One", "2": "Two", "4": "Four", "1-3": "Var"}


def macros(df, s, an, to):
    """report/partB.tex: one macro per setting, e.g. \\pbTwoBranchMPnFourqNine (mean success) and \\pbciTwo...
    (95% CI half-width), \\pbattThreeGridMPnVarqFive (attempts per request), plus totals."""
    out = ["% Generated by partB_qunetsim/report_partB.py. Do not edit."]
    add = lambda k, v: out.append(f"\\newcommand{{\\{k}}}{{{v}}}")
    for r in s.itertuples():
        tail = f"d{WORD[r.drop_rate]}" if r.experiment == "E4" else f"q{WORD[r.q]}"
        key = f"{WORD[r.experiment]}{WORD[r.topology]}{r.method}n{WORD[str(r.n)]}{tail}"
        add(f"pb{key}", f"{r.sr_mean:.2f}")
        add(f"pbci{key}", f"{r.sr_half:.2f}")
        g = df[(df.experiment == r.experiment) & (df.topology == r.topology) & (df.method == r.method)
               & (df.n.astype(str) == str(r.n)) & (df.q == r.q) & (df.drop_rate == r.drop_rate)]
        add(f"pbatt{key}", f"{(g.attempts / g.requests).mean():.1f}")
    for r in an.itertuples():
        add(f"pban{WORD[r.experiment]}{r.method}n{WORD[str(r.n)]}q{WORD[r.q]}", f"{r.analytic:.2f}")
    m = analytic_check(s, an)
    add("pbAnalyticInside", int(m.inside.sum()))
    add("pbAnalyticTotal", len(m))
    for exp in ["E2", "E3", "E4"]:
        sub = df[df.experiment == exp].assign(n=lambda d: d.n.astype(str))
        if sub.empty:
            continue
        piv = sub.pivot_table(index=["topology", "q", "M", "n", "drop_rate", "seed"], columns="method",
                              values="success_rate")
        d = piv["MP"] - piv["SP"]
        w = WORD[exp]
        add(f"pbDiff{w}", f"{d.mean():.2f}")
        add(f"pbBetter{w}", int((d > 0).sum()))
        add(f"pbWorse{w}", int((d < 0).sum()))
        add(f"pbRuns{w}", len(d))
    add("pbRunsTotal", len(df))
    add("pbRequests", int(df.requests.sum()))
    add("pbDelivered", int(df.delivered.sum()))
    add("pbCorrelated", int(df.correlated.sum()))
    add("pbTimeouts", int(to.timeouts.sum()))
    add("pbTimeoutsFour", int(to[to.experiment == "E4"].timeouts.sum()))
    add("pbSeeds", int(df.seed.nunique()))
    (ROOT / "report" / "partB.tex").write_text("\n".join(out) + "\n", encoding="utf-8")


def main():
    """Build the summary, the figure and the report macros from the CSV files."""
    df = pd.read_csv(ROOT / "results" / "partB.csv")
    an = pd.read_csv(ROOT / "results" / "partB_analytic.csv")
    to = pd.read_csv(ROOT / "results" / "partB_timeouts.csv")
    s = per_setting(df)
    summary(df, s, an, to)
    figure(s, an)
    macros(df, s, an, to)
    print("wrote results/partB_summary.md, figures/F3_partB_success.(png|pdf) and report/partB.tex")


if __name__ == "__main__":
    main()
