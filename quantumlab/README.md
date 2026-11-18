# QuantumLab

An interactive 3D browser companion to the lab project that reproduces Halder, Matus and Fettweis (GLOBECOM 2024), "multipath entanglement distribution". It is a teaching tool and is not graded. Tier 1 holds the landing page, the Story chapters 1 to 5, and the Fig. 1 debugger. The Arena and the Code Lab come next.

## Run it

It needs a web server, because browsers block ES modules and `fetch` on `file://` pages. From the repository root:

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
| `js/chapters/ch1.js` to `ch5.js`, `js/fig1.js` | The rooms |
| `data/hints.json` | Five help levels per task id |
| `data/fig1_steps.json`, `data/rushhour.json`, `data/fidelity.json` | Written by the exporter from the real engine |
| `tools/export_data.py` | Exporter. Run with `.venv\Scripts\python.exe quantumlab	ools\export_data.py` |
| `tools/check_contrast.py` | Computes the contrast table below from `css/lab.css` |
| `tools/parity_check.mjs` | Lets a test compare the JavaScript referee and formulas with Python |
| `vendor/` | three.js 0.170.0 and the fonts, with URLs and sha256 in `vendor/SOURCES.md` |

## Where the numbers come from

- The exporter imports `src/qmp` and runs `heuristic.alpha_scores`, `heuristic.place_heuristic`, `ilp.solve_path` and `fidelity.max_intermediate`. Each data file stores the last commit that touched `src/` and a sha256 of the source of the functions used.
- Rush hour answers are the ILP optimum from `qmp.ilp.solve_path` (with `K=1` for one road per request, and `delta=2` for the spare-seat rule) and the heuristic answer with the lowest-id tie-break.
- The chapter 4 meter is computed in the page with the Werner formula. The test suite checks that it agrees with the exported limits, and the page shows an error if they ever disagree.
- `tests/test_quantumlab_data.py` re-runs the exporter and compares it with the committed data, checks the hint file, and runs the JavaScript referee against `core.validate` on 11 broken answers and the exported optima.

## Assumptions used

A5 (Werner fidelity), A8 and A9 (heuristic seats and tie-break), A21 (the spare-seat cap per request and link). Each is cited where the code uses it.

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

