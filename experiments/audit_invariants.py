"""Audit: on every window, check heuristic <= ILP-delta <= ILP when the solver proved optimality.

MP-Heu drives the simulation. On the same WindowInput the wrapper also solves ILP-delta and the plain ILP,
and the single-path chain SP-Heu <= SP-ILP-delta <= SP-ILP <= MP-ILP. Exits with code 1 on any violation.
"""
import _bootstrap  # noqa: F401
import argparse
import sys

import pandas as pd

from experiments.common import (Timer, add_common_args, calibrated_n_spec, load_config, out_dir,
                                run_pool, shrink_for_quick, sim_config, write_csv_atomic)
from experiments.methods import ILP_TIME_LIMIT
from qmp.core import objective
from qmp.heuristic import place_heuristic
from qmp.ilp import solve_path
from qmp.sim import simulate

TOL = 1e-9
COLUMNS = ["q", "seed", "window", "n_requests", "obj_heu", "obj_ilp_delta", "obj_ilp", "status_ilp_delta",
           "status_ilp", "obj_sp_heu", "obj_sp_ilp_delta", "obj_sp_ilp", "status_sp_ilp_delta", "status_sp_ilp",
           "violation", "inconclusive"]


class AuditPlacer:
    """MP-Heu placer that also solves ILP-delta and ILP on the same window and logs the objectives."""

    def __init__(self, q: float, seed: int):
        self.q, self.seed, self.rows = q, seed, []

    def __call__(self, win):
        heu = place_heuristic(win, multipath=True, delta=2)
        if win.requests:
            ilp_d = solve_path(win, delta=2, time_limit=ILP_TIME_LIMIT)
            ilp = solve_path(win, time_limit=ILP_TIME_LIMIT)
            sp = (place_heuristic(win, multipath=False, delta=2),
                  solve_path(win, K=1, delta=2, time_limit=ILP_TIME_LIMIT),
                  solve_path(win, K=1, time_limit=ILP_TIME_LIMIT))
            self.rows.append(self.log_row(win, heu, ilp_d, ilp, sp))
        return heu

    def log_row(self, win, heu, ilp_d, ilp, sp) -> dict:
        o_heu, o_d, o_ilp = (objective(win, r.allocations) for r in (heu, ilp_d, ilp))
        s_heu, s_d, s_ilp = (objective(win, r.allocations) for r in sp)
        d_ok, ilp_ok = ilp_d.status == "optimal", ilp.status == "optimal"
        sd_ok, sp_ok = sp[1].status == "optimal", sp[2].status == "optimal"
        violation = ((d_ok and o_heu > o_d + TOL) or (d_ok and ilp_ok and o_d > o_ilp + TOL)
                     or (sd_ok and s_heu > s_d + TOL) or (sd_ok and sp_ok and s_d > s_ilp + TOL)
                     or (sp_ok and ilp_ok and s_ilp > o_ilp + TOL))
        return dict(q=self.q, seed=self.seed, window=win.seed - self.seed * 1000,  # sim.make_window_input: seed = cfg.seed*1000 + w
                    n_requests=len(win.requests),
                    obj_heu=o_heu, obj_ilp_delta=o_d, obj_ilp=o_ilp, status_ilp_delta=ilp_d.status,
                    status_ilp=ilp.status, obj_sp_heu=s_heu, obj_sp_ilp_delta=s_d, obj_sp_ilp=s_ilp,
                    status_sp_ilp_delta=sp[1].status, status_sp_ilp=sp[2].status, violation=bool(violation),
                    inconclusive=not (d_ok and ilp_ok and sd_ok and sp_ok))


def audit_job(job: dict) -> list[dict]:
    """Worker: simulate one (q, seed) with the audit placer and return its logged windows."""
    cfg = sim_config(job)
    placer = AuditPlacer(job["q"], job["seed"])
    simulate(cfg, placer)
    return placer.rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_common_args(ap)
    args = ap.parse_args()
    cfg = load_config("small")
    if args.quick:
        cfg = shrink_for_quick(cfg)
    n_spec = calibrated_n_spec()
    with Timer():
        jobs = [dict(rows=cfg["rows"], cols=cfg["cols"], R=cfg["R"][0], M=cfg["M"], T=cfg["T"], tc=cfg["tc"][0],
                     q=q, F=cfg["F"], f=cfg["f"], n_spec=n_spec, seed=s)
                for q in cfg["q"] for s in range(cfg["seeds"])]
        rows = [r for part in run_pool(audit_job, jobs, args.workers) for r in part]
        df = pd.DataFrame(rows, columns=COLUMNS)
        write_csv_atomic(df, out_dir(args.quick) / "partA_invariants.csv")
        print(f"windows checked: {len(df)}")
        print(f"violations: {int(df['violation'].sum())}")
        print(f"inconclusive (time limit): {int(df['inconclusive'].sum())}")
        if df["violation"].any():
            print(df[df["violation"]].head(10).to_string())
            sys.exit(1)


if __name__ == "__main__":
    main()
