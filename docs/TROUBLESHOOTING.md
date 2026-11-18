# Troubleshooting

## The PC runs out of memory and programs crash during experiments

**Symptom (2026-11-18).** Claude Code and the experiment runs kept crashing. Logs showed `MemoryError: bad allocation`, and a test run was killed with exit code 137.

**Root cause.** Two things multiplied together.

1. **Every Python process reserved about 1.5 GB at startup.** numpy's maths library (OpenBLAS) prepares one work buffer per CPU thread, and this PC has 28 threads.

   | Setting | Private memory per process | Threads |
   |---|---|---|
   | Default | 1,579 MB | 50 |
   | `OPENBLAS_NUM_THREADS=1` | 102 MB | 4 |

2. **QuNetSim's simulation backend (EQSN) starts a separate process for every qubit.** One Part B run with 6 parallel workers had grown to **122 Python processes holding 91.6 GB**. Windows had stretched its page file to 128 GB just to stay up, and then killed whatever asked for memory next, including Claude Code.

   The run had also outlived the crashed session that started it. Each crash left another orphaned job behind, so the problem fed itself.

**Fix (in the code now).**
- One BLAS thread per process, set before numpy is first imported. Every child process inherits it, including EQSN's per-qubit processes. It is set in:
  - `experiments/_bootstrap.py`
  - `partB_qunetsim/__init__.py`
  - `run_all.py`
  - `tests/conftest.py`
- Our experiments run one task per process, so the extra BLAS threads never helped anyway.
- Part B runs at most 3 worker processes. Part A uses 12 workers.
- `tools/run_safe.ps1` runs the steps **one at a time**, logs each step, and refuses to start a step when less than 8 GB of memory is free.

**After the fix.** The Part A sweep with 12 workers uses 14 processes and 1.4 GB in total. The same work used about 16 GB before.

**If it happens again.**
1. Count the Python processes:

   ```powershell
   Get-Process python | Measure-Object PrivateMemorySize64 -Sum
   ```

2. Find the root job (the process whose command line is not `spawn_main`) and stop its whole tree:

   ```powershell
   taskkill /F /T /PID <id>
   ```

3. Do not run Part A and Part B at the same time.

## Part B finished all runs but never wrote its CSV (2026-11-18)

**Symptom.**
- The log reached `740/740 runs`.
- After that the step sat for 80 minutes, with 3 worker processes each holding 28 child processes, and `results/partB.csv` never appeared.

**Cause.**
- `with ProcessPoolExecutor(...)` waits, on exit, for every worker to quit.
- A worker never quits on its own: its QuNetSim network keeps host threads running, plus one EQSN process per qubit.
- The results lived only in the parent's memory, so killing the hang lost them.
- A second bug was waiting behind it: the timeout rows had no `n` column, so sorting them for `partB_timeouts.csv` would have raised `KeyError`.

**Fix in `partB_qunetsim/run_partB.py`.**
- Every finished run is appended at once to `results/partB_partial.jsonl`.
- The CSVs are written after each group.
- The pool is stopped with `kill_pool`, which ends each worker's process tree instead of waiting for it.
- The script ends with `os._exit` once its outputs are written.
- `--limit N` runs only the first N tasks per group. `--limit 6` checks the whole path in about 12 seconds.

**Fix in `tools/run_safe.ps1`.**
- `-File` passes `-Steps a,b` as the single string `"a,b"`. The runner now splits it.
- An unknown step name aborts the run. Before, it started a bare `python` that waited for input forever.
