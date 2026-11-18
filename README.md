# Multipath Entanglement Distribution: reproduction, QuNetSim check, and extension

**Authors:** Panhapiseth Lim and Victor Akinmade, University of Texas of the Permian Basin

This is a 4-week lab project that reproduces Halder, Matus & Fettweis, *"On the Concurrent Multipath Entanglement Distribution in Quantum Networks"* (IEEE GLOBECOM 2024). It has three parts:

- **Part A:** a Python model comparing single-path vs multipath routing, and ILP vs heuristic.
- **Part B:** the same question in the QuNetSim simulator.
- **Part C:** one extension, the "spare seat" (deadline-aware δ) rule.

> **New to quantum networks?** Start with [`docs/study_guide.md`](docs/study_guide.md). It explains everything three ways: like you're 5, as a student, and as an expert. The paper itself is summarised in [`docs/paper_notes.md`](docs/paper_notes.md).

## Status: Week 1 (reading, feasibility, scope)
Project code (`src/`) starts only after the advisor approves [`docs/scope_note.md`](docs/scope_note.md). Live checklist: run `tools/check_tracker.py` (see below).

## Setup (Windows, Python 3.11)
```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe tools\check_tracker.py
```
Python 3.11 is required because QuNetSim 0.1.3 breaks on Python ≥3.12 ([issue #171](https://github.com/tqsd/QuNetSim/issues/171)). The exact versions that were installed are in `requirements.lock.txt`.

## Layout
| Path | What |
|---|---|
| `ASSUMPTIONS.md` | Every modelling choice the paper left open (A1–A21), plus paper inconsistencies we found |
| `docs/` | Study guide, paper notes, QuNetSim feasibility, scope note |
| `tracker.yaml` + `tools/check_tracker.py` | Every lab requirement, each with a machine check. PASS means the evidence exists. |
| `partB_qunetsim/probes/` | Small QuNetSim tests answering the Week-1 feasibility questions |
| `tests/toy_expected.md` | Toy networks solved by hand *before* any solver code, with progressive hints |
| `.claude/agents/` | The AI agents used: `builder` and `hostile-reviewer` (see `AI_LOG.md`) |

## AI use
AI assistants were used under the lab's rules. Every request and every accept/change/reject decision is logged in [`AI_LOG.md`](AI_LOG.md).

The source PDFs are not committed, for copyright reasons.
