"""Part C: the deadline-aware delta extension on the small setup, plus the pre-registered verdict.

Runs six methods on the same 30 seeds as Part A, writes results/partC.csv and results/partC_verdict.md.
"""
import _bootstrap  # noqa: F401
import argparse

from experiments.analysis import verdict_text
from experiments.common import (Timer, add_common_args, calibrated_n_spec, load_config, out_dir, run_experiment,
                                shrink_for_quick, write_text_atomic)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_common_args(ap)
    args = ap.parse_args()
    cfg = load_config("partC")
    if args.quick:
        cfg = shrink_for_quick(cfg)
    out = out_dir(args.quick)
    with Timer():
        df = run_experiment(cfg, calibrated_n_spec(), args.workers, out / "partC.csv")
        text = verdict_text(df) if 0.5 in cfg["q"] else "Verdict needs q = 0.5.\n"
        write_text_atomic(text, out / "partC_verdict.md")
        print(text)


if __name__ == "__main__":
    main()
