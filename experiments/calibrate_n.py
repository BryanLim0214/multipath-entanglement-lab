"""Calibrate the unspecified pairs-per-request range n (A1) against the paper's MP-Heu Gamma (Table I).

Runs MP-Heu for every candidate, seed and q; picks the lowest RMSE. Blocking ratio and MP-ILP Gamma are held out.
"""
import _bootstrap  # noqa: F401
import argparse

import numpy as np
import pandas as pd
import yaml

from experiments.common import (ROOT, Timer, add_common_args, load_config, out_dir, run_job, run_pool,
                                shrink_for_quick, write_csv_atomic, write_text_atomic)
from qmp.stats import mean_ci

NOTE = "calibrated on MP-Heu Gamma only; blocking ratio and MP-ILP Gamma are held out"


def summarize(df: pd.DataFrame, paper_gamma: dict) -> tuple[pd.DataFrame, dict]:
    """Mean Gamma and CI per (candidate, q), plus the RMSE against the paper per candidate."""
    rows = []
    for (cand, q), g in df.groupby(["n_spec", "q"], sort=False):
        mean, ci = mean_ci(g["gamma"])
        rows.append(dict(candidate=cand, q=q, gamma_mean=mean, gamma_ci=ci, paper_gamma=paper_gamma[q]))
    table = pd.DataFrame(rows)
    trend = {c: bool(g.sort_values("q")["gamma_mean"].iloc[-1] < g.sort_values("q")["gamma_mean"].iloc[0])
             for c, g in table.groupby("candidate", sort=False)}
    table["trend_ok"] = table["candidate"].map(trend)  # Gamma at q=0.9 below Gamma at q=0.5, as in the paper
    rmse = {c: float(np.sqrt(np.mean((g["gamma_mean"] - g["paper_gamma"]) ** 2)))
            for c, g in table.groupby("candidate", sort=False)}
    return table, rmse


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_common_args(ap)
    args = ap.parse_args()
    cfg = load_config("calibration")
    if args.quick:
        cfg = shrink_for_quick(cfg)
    paper = yaml.safe_load((ROOT / "data" / "paper_values.yaml").read_text(encoding="utf-8"))
    paper_gamma = dict(zip(paper["q"], paper["small"]["gamma"]["MP-Heu"]))
    with Timer():
        jobs = [dict(experiment="calibration", method="MP-Heu", rows=cfg["rows"], cols=cfg["cols"], R=R, M=cfg["M"],
                     T=cfg["T"], tc=tc, q=q, F=cfg["F"], f=cfg["f"], n_spec=cand, seed=s, trace_path=None)
                for cand in cfg["candidates"] for R in cfg["R"] for tc in cfg["tc"] for q in cfg["q"]
                for s in range(cfg["seeds"])]
        df = pd.DataFrame(run_pool(run_job, jobs, args.workers))
        table, rmse = summarize(df, paper_gamma)
        out = out_dir(args.quick)
        write_csv_atomic(table, out / "calibration.csv")
        choice = min(rmse, key=lambda c: (rmse[c], c))
        text = yaml.safe_dump({"choice": choice, "rmse": rmse, "note": NOTE}, sort_keys=False)
        write_text_atomic(text, out / "calibration_choice.yaml")
        print(text)


if __name__ == "__main__":
    main()
