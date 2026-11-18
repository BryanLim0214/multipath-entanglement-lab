"""Check that a results CSV has enough independent runs per setting (lab: >=30 seeds in Part A, >=20 in Part B).

A "setting" is every column except the seed and the measured metrics. Optionally checks that a second
file used exactly the same seeds (lab: "same seeds and runs" for the extension).
Usage: python tools/check_runs.py results/partA_small.csv --min 30 [--same-seeds-as results/other.csv]
"""
import argparse
import sys

import pandas as pd

METRICS = {"blocking_ratio", "success_rate", "gamma", "seconds", "windows_time_limit", "completion_time",
           "placed", "delivered", "objective"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--min", type=int, required=True)
    ap.add_argument("--same-seeds-as")
    args = ap.parse_args()
    df = pd.read_csv(args.csv)
    setting_cols = [c for c in df.columns if c != "seed" and c not in METRICS]
    counts = df.groupby(setting_cols, dropna=False)["seed"].nunique()
    short = counts[counts < args.min]
    print(f"{args.csv}: {len(counts)} settings, seeds per setting min {counts.min()} max {counts.max()}")
    if len(short):
        print(f"FAIL: {len(short)} setting(s) below {args.min} seeds:\n{short.head(10)}")
        sys.exit(1)
    if args.same_seeds_as:
        other = set(pd.read_csv(args.same_seeds_as)["seed"])
        mine = set(df["seed"])
        if not mine <= other:
            sys.exit(f"FAIL: seeds {sorted(mine - other)[:10]} are not in {args.same_seeds_as}")
        print(f"same seeds as {args.same_seeds_as}: ok")


if __name__ == "__main__":
    main()
