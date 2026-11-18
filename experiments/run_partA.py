"""Part A: run every method over the seeds and settings of a config (small, load or large).

Writes a long-format CSV, results/partA_<config>.csv, and (small only) JSON traces for seeds 0-2.
"""
import _bootstrap  # noqa: F401
import argparse

from experiments.common import (Timer, add_common_args, calibrated_n_spec, load_config, out_dir, run_experiment,
                                shrink_for_quick)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_common_args(ap)
    ap.add_argument("--config", required=True, choices=["small", "load", "large"])
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.quick:
        cfg = shrink_for_quick(cfg)
    out = out_dir(args.quick)
    trace_dir = out / "traces" if args.config == "small" else None
    with Timer():
        run_experiment(cfg, calibrated_n_spec(), args.workers, out / f"partA_{args.config}.csv", trace_dir)


if __name__ == "__main__":
    main()
