"""Summary tables and the pre-registered Part C verdict, computed from the long-format CSVs.

Used by run_partC.py (verdict file), make_figures.py (plots) and the numbers.tex generator.
"""
from __future__ import annotations

import pandas as pd

from qmp.stats import mean_ci, paired_diff_ci

# Pre-registered in docs/scope_note.md: SUPPORTED iff paired mean >= 3 pp and the 95% CI lower bound > 0.
THRESHOLD = 0.03
VERDICT_Q = 0.5


def summarize(df: pd.DataFrame, by: list[str], metric: str) -> pd.DataFrame:
    """Mean and 95% CI half-width of `metric` for every group in `by`."""
    rows = []
    for key, g in df.groupby(by, sort=True):
        key = key if isinstance(key, tuple) else (key,)
        mean, ci = mean_ci(g[metric])
        rows.append({**dict(zip(by, key)), "mean": mean, "ci": ci, "n": len(g)})
    return pd.DataFrame(rows)


def per_seed(df: pd.DataFrame, method: str, q: float, metric: str = "blocking_ratio") -> pd.Series:
    """One method's metric at one q, indexed by seed (so two methods can be paired)."""
    sub = df[(df["method"] == method) & (df["q"] == q)]
    return sub.set_index("seed")[metric].sort_index()


def paired_difference(df: pd.DataFrame, base: str, other: str, q: float) -> dict:
    """BR(base) - BR(other), paired by seed (A19): mean, CI half-width, lower and upper bound."""
    a, b = per_seed(df, base, q), per_seed(df, other, q)
    assert list(a.index) == list(b.index), "methods must share the same seeds"
    mean, ci = paired_diff_ci(a.values, b.values)
    return dict(q=q, mean=mean, ci=ci, lo=mean - ci, hi=mean + ci, n=len(a))


def is_supported(diff: dict) -> bool:
    """The rule exactly as pre-registered: mean >= 0.03 AND CI lower bound > 0."""
    return diff["mean"] >= THRESHOLD and diff["lo"] > 0


def gap_closed(df: pd.DataFrame, variant: str, q: float) -> float | None:
    """(BR_MP-Heu - BR_variant) / (BR_MP-Heu - BR_MP-ILP), from the means; None if the denominator is 0 or less."""
    heu = per_seed(df, "MP-Heu", q).mean()
    ilp = per_seed(df, "MP-ILP", q).mean()
    var = per_seed(df, variant, q).mean()
    return (heu - var) / (heu - ilp) if heu - ilp > 0 else None


def verdict_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per q: paired differences for deadline and d1, and the share of the heuristic-to-ILP gap closed."""
    rows = []
    for q in sorted(df["q"].unique()):
        dead = paired_difference(df, "MP-Heu", "MP-Heu-deadline", q)
        d1 = paired_difference(df, "MP-Heu", "MP-Heu-d1", q)
        rows.append(dict(q=q, deadline_diff=dead["mean"], deadline_ci=dead["ci"], deadline_lo=dead["lo"],
                         deadline_hi=dead["hi"], d1_diff=d1["mean"], d1_ci=d1["ci"],
                         gap_closed_deadline=gap_closed(df, "MP-Heu-deadline", q),
                         gap_closed_d1=gap_closed(df, "MP-Heu-d1", q)))
    return pd.DataFrame(rows)


def verdict_text(df: pd.DataFrame) -> str:
    """Markdown for results/partC_verdict.md. Every number comes from df."""
    d = paired_difference(df, "MP-Heu", "MP-Heu-deadline", VERDICT_Q)
    word = "SUPPORTED" if is_supported(d) else "NOT SUPPORTED"
    fmt = lambda x: "n/a" if x is None or pd.isna(x) else f"{x:.2f}"
    lines = [
        "# Part C verdict: deadline-aware delta",
        "",
        "Rule (pre-registered in docs/scope_note.md): at q = 0.5 on the 3x3 setup, the paired mean of "
        "BR(MP-Heu) - BR(MP-Heu-deadline) must be at least 0.03 and the lower bound of its 95% CI must be above 0.",
        "",
        f"**Verdict: {word}.**",
        "",
        f"At q = {VERDICT_Q}, n = {d['n']} paired seeds: mean difference {d['mean']:.4f}, "
        f"95% CI [{d['lo']:.4f}, {d['hi']:.4f}]. Threshold {THRESHOLD}.",
        "",
        "## All q",
        "",
        "| q | BR(MP-Heu) - BR(deadline), 95% CI | BR(MP-Heu) - BR(d1), 95% CI | gap closed, deadline | gap closed, d1 |",
        "|---|---|---|---|---|",
    ]
    for r in verdict_table(df).itertuples():
        lines.append(f"| {r.q} | {r.deadline_diff:.2f} ± {r.deadline_ci:.2f} | {r.d1_diff:.2f} ± {r.d1_ci:.2f} "
                     f"| {fmt(r.gap_closed_deadline)} | {fmt(r.gap_closed_d1)} |")
    lines += ["", "Gap closed = (BR_MP-Heu - BR_variant) / (BR_MP-Heu - BR_MP-ILP), from the means over seeds. "
              "n/a means MP-Heu is not above MP-ILP at that q."]
    return "\n".join(lines) + "\n"
