# QuantumLab

An interactive 3D browser companion to the lab project that reproduces Halder, Matus and Fettweis (GLOBECOM 2024), "multipath entanglement distribution". It is a teaching tool and is not graded. Tier 1 holds the landing page, the Story chapters 1 to 5, and the Fig. 1 debugger. Tier 2 adds the Arena and Story chapter 6. Tier 3 adds the Code Lab, where you write your own placement rule in Python.

## Run it

It needs a web server, because browsers block ES modules and `fetch` on `file://` pages. Serve the repository root, not the `quantumlab` folder, because the Code Lab loads the engine from `src/qmp`. From the repository root:

    .venv\Scripts\python.exe -m http.server 8765

Then open http://localhost:8765/quantumlab/index.html. On GitHub Pages it works with no extra setup, and it works offline because three.js and the fonts are vendored.

## Layout

| Path | What it is |
|---|---|
| `index.html` | Landing page, importmap, and the empty room containers |
| `css/lab.css` | Design tokens (light and dark), layout, controls |
| `js/main.js` | Router, theme and reduce-motion controls, the H key |
| `js/three-stage.js` | Shared 3D stage: spheres for cities, tubes for seats, beads for pairs, HTML labels |
| `js/help-ladder.js` | The five help levels and per-task progress in localStorage |
| `js/ui.js`, `js/math.js`, `js/referee.js` | Element builder, captions and prediction box, exact formulas, port of `core.validate` |
| `js/chapters/ch1.js` to `ch6.js`, `js/arena.js`, `js/fig1.js` | The rooms |
| `js/codelab.js`, `js/codelab-runtime.js`, `js/codelab-worker.js`, `js/codelab-diff.js` | The Code Lab room, the page side of the Python runtime, the Web Worker that runs Pyodide, and the line diff for "Show me" |
| `py/codelab_adapter.py` | Turns the player's `choose_paths` into a qmp placer and scores it. The worker and the tests load this same file |
| `py/templates/`, `py/solutions/`, `py/skeletons/` | Lazy Walker and Splitter templates, one working solution per challenge, one fill-in-the-blank outline per challenge |
| `js/arena-model.js`, `js/arena-story.js` | Arena logic with no page elements (fates, seats, counters, why a request was blocked) and the plain-language story text |
| `data/hints.json` | Five help levels per task id |
| `data/fig1_steps.json`, `data/rushhour.json`, `data/fidelity.json`, `data/arena.json` | Written by the exporter from the real engine and the Part A results |
| `tools/export_data.py` | Exporter. Run with `.venv\Scripts\python.exe quantumlab\tools\export_data.py` |
| `tools/check_contrast.py` | Computes the contrast table below from `css/lab.css` |
| `tools/parity_check.mjs` | Lets a test compare the JavaScript referee and formulas with Python |
| `data/codelab.json` | Setup for the Code Lab (the Part A config and `n_spec`) and the sha256 of every Python file the browser runs |
| `tools/arena_check.mjs` | Runs the Arena replay logic over `data/arena.json` so a test can compare it with the exported numbers |
| `vendor/` | three.js 0.170.0 and the fonts, with URLs and sha256 in `vendor/SOURCES.md` |

## Where the numbers come from

- The exporter imports `src/qmp` and runs `heuristic.alpha_scores`, `heuristic.place_heuristic`, `ilp.solve_path` and `fidelity.max_intermediate`. Each data file stores the last commit that touched `src/` and a sha256 of the source of the functions used.
- Rush hour answers are the ILP optimum from `qmp.ilp.solve_path` (with `K=1` for one road per request, and `delta=2` for the spare-seat rule) and the heuristic answer with the lowest-id tie-break.
- The chapter 4 meter is computed in the page with the Werner formula. The test suite checks that it agrees with the exported limits, and the page shows an error if they ever disagree.
- `tests/test_quantumlab_data.py` re-runs the exporter and compares it with the committed data, checks the hint file, and runs the JavaScript referee against `core.validate` on 11 broken answers and the exported optima. For the Arena it also validates every allocation of every trace window with both `core.validate` and the JavaScript referee, checks that the JavaScript replay reproduces each blocking ratio, and checks that chapter 6 numbers equal the CSV means.

## Arena and chapter 6 data

`data/arena.json` is written by the same exporter, in one process and with no solver (the ILP traces are read, never re-solved).

- **Replays.** For q in {0.5, 0.7, 0.9} and seeds 0 to 2 it holds the Part A traces `results/traces/partA_<method>_q<q>_s<seed>.json` for SP-SPF, SP-Heu, MP-Heu, SP-ILP and MP-ILP, with every number kept as written. The requests and the seats per window are stored once per run, because every method sees the same ones (A19). The exporter checks that.
- **Rule switches.** The exporter runs `qmp.sim.simulate` with the heuristic for all eight on and off combinations of splitting, the spare-seat rule (`MP-Heu-d1`) and the hop limit (`-nohop`), with the same `SimConfig` and the same `n_spec` (from `experiments.common.calibrated_n_spec()`). MP-Heu and SP-Heu are the committed traces, and a test checks that re-running them gives the same bytes. The switches work for the heuristic pair only. The ILP traces exist only with all rules on.
- **Hop limit off** uses f = 0.6. With F = 0.95 that allows 10 middle cities (A5), and a 3 by 3 grid has at most 7, so the limit never binds. On this grid the hop limit changes the fate of at most a few requests per run, and of none in some runs, so the switch often shows little. That is a result, not a bug.
- **Chapter 6.** The 30-seed mean and 95% interval per method and q come from `results/partA_small.csv` through `qmp.stats.mean_ci`, and the paired difference (single-path minus multipath, same seed) through `qmp.stats.paired_diff_ci`. The paper's 0.27 and 0.42 at q = 0.9 come from `data/paper_values.yaml` (printed in the text, A20).
- **Provenance.** `meta` holds the engine commit, the hash of the engine functions, the hash of the Arena functions, and the sha256 of the traces, the CSV, the paper values and the calibration choice. `results/` is rewritten whenever Part A is re-run. After a re-run, run the exporter again, or `tests/test_quantumlab_data.py` will fail on purpose.
- **Why a request was blocked.** For the heuristic, the page replays the order in which it tries requests (A16) and subtracts the seats of the requests tried before it, so the seats shown are the ones it saw (A8). For the exact solver there is no order, so the seats at the end of the window are shown. The multipath figure is an upper bound that ignores the hop limit and the disjoint-roads rule, and the page says so.

## Code Lab

- **Runtime.** Pyodide 0.26.4 is loaded from `cdn.jsdelivr.net` inside a Web Worker, with numpy, networkx, scipy and pyyaml. The page needs an internet connection the first time, and shows a plain message with a "Try again" button if the CDN cannot be reached. A run that takes more than 45 seconds is stopped by terminating the worker, and Python restarts.
- **Real engine, no copies.** The worker fetches `core`, `model`, `fidelity`, `heuristic`, `sim` and `stats` from `../../src/qmp/` and writes them into the Python file system. `ilp.py` imports PuLP, which Pyodide does not have, so it is simply not loaded (`sim.py` does not import it). No stub is needed, and a test checks that no loaded module imports `pulp`. On GitHub Pages the site root must contain both `quantumlab/` and `src/`.
- **Referee.** Each answer goes through `qmp.core.validate` on the seats left at that request's turn, and nothing else: capacity, shared links, the middle-city limit and all-or-nothing. The spare-seat rule (A21) is a strategy of the paper's methods, not a law, so the referee does not check it and players may discover that keeping no spare seat beats MP-Heu (challenge 3). An illegal answer is rejected, the request stays unplaced in that window, and the referee's message is listed. Requests come in the engine's own order (A16), and seats are taken only for accepted answers.
- **Scoring.** The player's rule and the baseline run through `qmp.sim.simulate` on the same seeds (A19) with the Part A config and calibrated `n_spec`. The paired difference uses `qmp.stats.paired_diff_ci`. A win means the upper end of the 95% interval of (player minus baseline) is below 0, and challenge 2 also needs zero rejected answers. It uses 10 seeds, not 30, because the code runs in the browser. Baselines are SP-SPF (Lazy Walker), SP-Heu and MP-Heu, built the same way as in `experiments/methods.py`.
- **Badges** are stored in localStorage under `quantumlab.codelab.badges.v1`, and storage failures are ignored.
- **Tests.** `tests/test_codelab.py` runs the adapter in CPython. The Lazy Walker template reproduces the committed SP-SPF blocking ratios exactly on seeds 0 to 2 at q = 0.5, 0.7 and 0.9, illegal templates are rejected with the engine's messages, and each working solution wins its challenge.

## Assumptions used

A1 (pairs per request, the reason our levels differ from the paper's), A5 (Werner fidelity and the hop limit), A8 and A9 (heuristic seats and tie-break), A14 (eligible windows), A16 (request order), A19 (same dice for every method), A20 (paper values), A21 (the spare-seat cap per request and link, which the Code Lab baselines use and its referee does not enforce). Each is cited where the code uses it.

## Contrast ratios

Computed by `tools/check_contrast.py` from the tokens in `css/lab.css`. Text pairs need at least 4.5:1. Colors used only in drawings (`--sp`, `--ext` and the fidelity ramp) need at least 3:1 and are never used for text.

| Theme | Use | Pair | Colors | Ratio | Result |
|---|---|---|---|---|---|
| light | text | ink on paper | #1C1C1C / #F7F5F0 | 15.64 | pass |
| light | text | muted on paper | #4A4A4A / #F7F5F0 | 8.13 | pass |
| light | text | mp on paper | #0072B2 / #F7F5F0 | 4.76 | pass |
| light | text | warn on paper | #8A6100 / #F7F5F0 | 5.08 | pass |
| light | text | fail on paper | #B3261E / #F7F5F0 | 6.00 | pass |
| light | text | paper on ink | #F7F5F0 / #1C1C1C | 15.64 | pass |
| light | text | paper on muted | #F7F5F0 / #4A4A4A | 8.13 | pass |
| light | text | ink on rule | #1C1C1C / #D9D4C7 | 11.52 | pass |
| light | graphic | sp on paper | #D55E00 / #F7F5F0 | 3.55 | pass |
| light | graphic | ext on paper | #009E73 / #F7F5F0 | 3.14 | pass |
| light | graphic | ramp-0 on paper | #0E8C99 / #F7F5F0 | 3.69 | pass |
| light | graphic | ramp-1 on paper | #B07F00 / #F7F5F0 | 3.28 | pass |
| light | graphic | ramp-2 on paper | #B3261E / #F7F5F0 | 6.00 | pass |
| dark | text | ink on paper | #ECEAE4 / #131519 | 15.19 | pass |
| dark | text | muted on paper | #B9B6AE / #131519 | 9.02 | pass |
| dark | text | mp on paper | #56B4E9 / #131519 | 7.92 | pass |
| dark | text | warn on paper | #E3B341 / #131519 | 9.39 | pass |
| dark | text | fail on paper | #FF8F85 / #131519 | 8.29 | pass |
| dark | text | paper on ink | #131519 / #ECEAE4 | 15.19 | pass |
| dark | text | paper on muted | #131519 / #B9B6AE | 9.02 | pass |
| dark | text | ink on rule | #ECEAE4 / #2E3238 | 10.71 | pass |
| dark | graphic | sp on paper | #F28A3C / #131519 | 7.38 | pass |
| dark | graphic | ext on paper | #2FCB9F / #131519 | 8.85 | pass |
| dark | graphic | ramp-0 on paper | #3FC1CF / #131519 | 8.48 | pass |
| dark | graphic | ramp-1 on paper | #E3B341 / #131519 | 9.39 | pass |
| dark | graphic | ramp-2 on paper | #FF8F85 / #131519 | 8.29 | pass |

