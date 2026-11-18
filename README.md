# Multipath Entanglement Distribution: reproduction, QuNetSim check, and extension

**Authors:** Panhapiseth Lim and Victor Akinmade, University of Texas of the Permian Basin

This is a 4-week lab project that reproduces Halder, Matus & Fettweis, *"On the Concurrent Multipath Entanglement Distribution in Quantum Networks"* (IEEE GLOBECOM 2024). It has three parts:

- **Part A:** a Python model comparing single-path vs multipath routing, and ILP vs heuristic.
- **Part B:** the same question in the QuNetSim simulator.
- **Part C:** one extension, the "spare seat" (deadline-aware δ) rule.

> **New to quantum networks?** Start with [`docs/study_guide.md`](docs/study_guide.md). It explains everything three ways: like you're 5, as a student, and as an expert. The paper itself is summarised in [`docs/paper_notes.md`](docs/paper_notes.md).

## Results at a glance
- **Part A** ([`results/partA_summary.md`](results/partA_summary.md), figures F1 and F2). Reproduced: multipath blocks fewer requests than single path at every q and every load. Not reproduced: the paper's absolute blocking levels, and its claim that the heuristic and the ILP are comparable.
- **Part B** ([`results/partB_summary.md`](results/partB_summary.md), figure F3). The same comparison in QuNetSim, with real Bell-state measurements and swaps. Multipath succeeds more often when link capacity is short (two-branch network and grid). Under the simulator's own packet drop it does not help, and on the grid it does worse.
- **Part C** ([`results/partC_verdict.md`](results/partC_verdict.md), figure F4). The pre-registered hypothesis is supported, but plain δ = 1 does even better, so the cost comes from the spare-seat rule itself.
- **Report:** [`report/main.tex`](report/main.tex). Every number in it is generated into `report/numbers.tex`.

## Setup (Windows, Python 3.11)
```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe tools\check_tracker.py
```
Python 3.11 is required because QuNetSim 0.1.3 breaks on Python ≥3.12 ([issue #171](https://github.com/tqsd/QuNetSim/issues/171)). The exact versions that were installed are in `requirements.lock.txt`.

## Rerun everything
```powershell
.venv\Scripts\python.exe -m pytest -q             # tests, toy networks, planted-bug canaries
.venv\Scripts\python.exe run_all.py --quick       # 3 seeds, results in results/quick/
.venv\Scripts\python.exe run_all.py --full        # all figures and results
```
On a machine with less than 32 GB of memory, run the long steps one at a time with the guarded runner. It refuses to start a step when memory is low, and logs to `results/logs/`:
```powershell
powershell -ExecutionPolicy Bypass -File tools\run_safe.ps1 -Steps small,load,audit,partC,figures,partB,sensitivity
.venv\Scripts\python.exe -m partB_qunetsim.report_partB   # Part B summary and figure F3
```
QuNetSim starts one process per qubit, so never run Part A and Part B at the same time. [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) explains why.

## Layout
| Path | What |
|---|---|
| `ASSUMPTIONS.md` | Every modelling choice the paper left open (A1–A27), plus paper inconsistencies we found |
| `docs/` | Study guide, paper notes, QuNetSim feasibility, scope note |
| `tracker.yaml` + `tools/check_tracker.py` | Every lab requirement, each with a machine check. PASS means the evidence exists. |
| `src/qmp/` | Part A engine: model, fidelity, heuristic, ILP, simulator, statistics |
| `experiments/` | Part A and Part C runs, calibration, invariant audit, figures, sensitivity study |
| `partB_qunetsim/` | Part B in QuNetSim (hop-by-hop swaps, attempt budget, routing), plus the Week-1 probes |
| `results/`, `figures/` | Generated CSVs, summaries and figures F0 to F4 |
| `report/` | IEEE-style report (LaTeX); `numbers.tex` is generated |
| `quantumlab/` | QuantumLab, the interactive 3D lab: open `quantumlab/index.html` through any local web server |
| `tests/toy_expected.md` | Toy networks solved by hand *before* any solver code, with progressive hints |
| `.claude/agents/` | The AI agents used: `builder` and `hostile-reviewer` (see `AI_LOG.md`) |

## AI use
AI assistants were used under the lab's rules. Every request and every accept/change/reject decision is logged in [`AI_LOG.md`](AI_LOG.md).

The source PDFs are not committed, for copyright reasons.
