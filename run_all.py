"""Run the whole experiment pipeline: Part A, Part C, figures and numbers.

--quick: 3 seeds, q in {0.5, 0.9}, results in results/quick/, uses the saved calibration choice.
--full: everything, in the order calibrate, small, load, audit, partC, figures (large only with --with-large).
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")  # inherited by every step; see docs/TROUBLESHOOTING.md


def run_step(script: str, *args: str) -> None:
    """Run one experiment script as a subprocess and stop the pipeline if it fails."""
    cmd = [PY, str(ROOT / "experiments" / script), *args]
    print(f"\n>>> {' '.join(cmd[1:])}", flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def run_part_b(quick: bool) -> None:
    """Part B in QuNetSim. It uses its own small pool (3 workers, one process per qubit), not --workers.
    --quick runs 4 tasks per group into results/quick/; the full run also writes the summary and F3."""
    cmd = [PY, "-m", "partB_qunetsim.run_partB", *(["--quick"] if quick else [])]
    print(f"\n>>> {' '.join(cmd[1:])}", flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)
    if not quick:
        subprocess.run([PY, "-m", "partB_qunetsim.report_partB"], check=True, cwd=ROOT)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--quick", action="store_true")
    mode.add_argument("--full", action="store_true")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--with-large", action="store_true", help="also run the 5x5 large-scale heuristics")
    args = ap.parse_args()
    flags = ["--workers", str(args.workers)] + (["--quick"] if args.quick else [])
    t0 = time.perf_counter()
    if args.full:
        run_step("calibrate_n.py", *flags)
    run_step("run_partA.py", "--config", "small", *flags)
    run_step("run_partA.py", "--config", "load", *flags)
    if args.full and args.with_large:
        run_step("run_partA.py", "--config", "large", *flags)
    run_step("audit_invariants.py", *flags)
    run_step("run_partC.py", *flags)
    run_part_b(args.quick)
    run_step("make_figures.py", *(["--quick"] if args.quick else []))
    print(f"\ntotal wall time: {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
