"""Shared helpers for the experiment scripts: configs, the job runner, atomic CSV writing.

A job is one (setting, seed, method) simulation. Jobs run in a process pool and each returns one CSV row.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd
import yaml

from experiments.methods import ILP_METHODS, METHODS
from qmp.sim import SimConfig, simulate, to_trace

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
CHOICE_FILE = RESULTS / "calibration_choice.yaml"
COLUMNS = ["experiment", "method", "rows", "cols", "R", "M", "T", "tc", "q", "f", "n_spec", "seed",
           "blocking_ratio", "gamma", "placed", "seconds", "windows_time_limit"]
QUICK_SEEDS = 3
QUICK_Q = [0.5, 0.9]


def add_common_args(ap: argparse.ArgumentParser) -> None:
    """The flags every script accepts."""
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--quick", action="store_true",
                    help="3 seeds, q in {0.5, 0.9}; writes to results/quick/")


def out_dir(quick: bool) -> Path:
    d = RESULTS / "quick" if quick else RESULTS
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_config(name: str) -> dict:
    return yaml.safe_load((ROOT / "experiments" / "configs" / f"{name}.yaml").read_text(encoding="utf-8"))


def calibrated_n_spec() -> str:
    """The n_spec chosen by calibrate_n.py (A1); never typed by hand."""
    if not CHOICE_FILE.exists():
        raise SystemExit(f"{CHOICE_FILE} is missing. Run experiments/calibrate_n.py first.")
    return yaml.safe_load(CHOICE_FILE.read_text(encoding="utf-8"))["choice"]


def shrink_for_quick(cfg: dict) -> dict:
    """Quick mode: fewer seeds, q in {0.5, 0.9}, and only the smallest and largest |R|."""
    cfg = dict(cfg)
    cfg["seeds"] = QUICK_SEEDS
    cfg["q"] = [q for q in cfg["q"] if q in QUICK_Q] or cfg["q"]
    if len(cfg["R"]) > 1:
        cfg["R"] = [cfg["R"][0], cfg["R"][-1]]
    if len(cfg["tc"]) > 1:
        cfg["tc"] = cfg["tc"][:1]
    return cfg


def make_jobs(cfg: dict, n_spec: str, trace_dir: Path | None = None) -> list[dict]:
    """One job per (R, tc, q, seed, method). ILP jobs come first so the pool stays busy to the end."""
    jobs = []
    for R, tc, q in itertools.product(cfg["R"], cfg["tc"], cfg["q"]):
        for seed in range(cfg["seeds"]):
            for method in cfg["methods"]:
                job = dict(experiment=cfg["experiment"], method=method, rows=cfg["rows"], cols=cfg["cols"],
                           R=R, M=cfg["M"], T=cfg["T"], tc=tc, q=q, F=cfg["F"], f=cfg["f"],
                           n_spec=n_spec, seed=seed, trace_path=None)
                if trace_dir and seed in cfg.get("trace_seeds", []) and q in cfg.get("trace_q", []):
                    job["trace_path"] = str(trace_dir / f"partA_{method}_q{q}_s{seed}.json")
                jobs.append(job)
    jobs.sort(key=lambda j: j["method"] not in ILP_METHODS)  # stable sort: ILP first
    return jobs


def sim_config(job: dict) -> SimConfig:
    return SimConfig(rows=job["rows"], cols=job["cols"], R=job["R"], M=job["M"], T=job["T"], tc=job["tc"],
                     q=job["q"], F=job["F"], f=job["f"], n_spec=job["n_spec"], seed=job["seed"])


def run_job(job: dict) -> dict:
    """Run one simulation (worker function) and return one CSV row."""
    cfg = sim_config(job)
    res = simulate(cfg, METHODS[job["method"]])
    if job["trace_path"]:
        Path(job["trace_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(job["trace_path"]).write_text(json.dumps(to_trace(res, cfg)), encoding="utf-8")
    row = {k: job[k] for k in COLUMNS if k in job}
    row.update(blocking_ratio=res.blocking_ratio, gamma=res.gamma, placed=len(res.placed),
               seconds=res.total_seconds, windows_time_limit=res.time_limit_windows)
    return row


def run_pool(func, jobs: list, workers: int) -> list:
    """Map func over jobs in a process pool. Results keep the order of jobs."""
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(func, jobs, chunksize=1))


def write_csv_atomic(df: pd.DataFrame, path: Path) -> None:
    """Write to a temporary file, then rename, so a crash never leaves a half-written CSV."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def write_text_atomic(text: str, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def run_experiment(cfg: dict, n_spec: str, workers: int, out_csv: Path, trace_dir: Path | None = None) -> pd.DataFrame:
    """Run every job of a config, write the long-format CSV, and return it."""
    jobs = make_jobs(cfg, n_spec, trace_dir)
    print(f"{cfg['experiment']}: {len(jobs)} jobs on {workers} workers")
    rows = run_pool(run_job, jobs, workers)
    df = pd.DataFrame(rows, columns=COLUMNS)
    df = df.sort_values(["method", "R", "tc", "q", "seed"], kind="stable").reset_index(drop=True)
    write_csv_atomic(df, out_csv)
    print(f"wrote {out_csv} ({len(df)} rows)")
    return df


class Timer:
    """Prints the wall time of a script when it ends."""

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        print(f"wall time: {time.perf_counter() - self.t0:.1f} s")
