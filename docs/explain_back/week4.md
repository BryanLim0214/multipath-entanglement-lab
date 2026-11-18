# Week 4 explain-back: results, statistics and the hard questions

These are the questions most likely to come up at the presentation. Each answer is short and points to the file that backs it. Read the answer, open the file, and say it back in your own words.

## Statistics

**1. What does "mean ± 95% CI over 30 seeds" mean here?**
- Each seed is one full run: new requests and new link dice, the same for every method.
- `qmp.stats.mean_ci` takes the 30 blocking ratios, gives their mean, and gives a Student-t half-width (ddof = 1).
- If we repeated the whole study many times, about 95% of such intervals would contain the true mean.

**2. Why are the comparisons "paired"?**
- For one seed, every method sees the same requests and the same link capacities.
- So we can subtract method A from method B seed by seed, and the luck cancels out.
- `qmp.stats.paired_diff_ci` does this for the extension verdict. The CI of a paired difference is much narrower than two separate CIs.

**3. Why did Part B switch to a Wilson interval for the analytic check?**
- When all 20 seeds give exactly 1.0, or all give 0.0, the t-interval has zero width, so any analytic value except exactly 1 or 0 looks like a miss.
- In E1 and E2 each window holds one request, and the links refill every window, so the requests are independent yes/no trials.
- A Wilson interval on the pooled 200 trials stays valid at 0 and 1. It is in `report_partB.wilson`.

## The results

**4. Did the paper's main claim reproduce?**
- Yes, qualitatively. Multipath blocks fewer requests than single path at every q and every load, for both the heuristic and the ILP (`results/partA_summary.md`, figure F1).
- QuNetSim agrees on all three networks (`results/partB_summary.md`, figure F3).

**5. What did not reproduce, and is that a failure?**
- The paper's blocking levels did not: it prints 0.27 and 0.42 at q = 0.9, and ours are near 0. Neither did its claim that the heuristic and the ILP are comparable.
- This is a finding, not a failure. The paper leaves out n, K and the exact arrival model, and those set the load. `docs/differences_from_paper.md` lists every difference, and the sensitivity study tests the two biggest.

**6. How do you know n was not tuned to make the result look good?**
- n was chosen only by how well MP-Heu's split share (Γ) matched the paper's Table I (`experiments/calibrate_n.py`).
- The blocking ratio was never computed during calibration, and that choice was committed before any blocking ratio existed (commit `0a2cb4c`).

**7. Why is your heuristic so much worse than your ILP?**
- Two diagnostics separate the causes (`report/main.tex`, Part A):
  - The ILP forced to keep the spare seat (ILP-δ) blocks 0.18.
  - The heuristic without the spare seat (δ = 1) blocks 0.09.
- Each alone costs little. Together they cost a lot, so the spare-seat rule hurts a greedy placer far more than an optimal one.

**8. What happened with SP-ILP and the time limit?**
- The general path model, with K = 1, sometimes could not prove optimality within 60 s. It had found the best answer, but could not prove the tiny tie-break term.
- `ilp.solve_single_path` is the same problem with the pair counts fixed at n. It proves those windows in under 0.1 s.
- `tests/test_ilp_equivalence.py` checks that both models give the same optimum on 200 random windows. Part A was rerun with it, and the report prints how many windows hit the limit.

## The extension

**9. The hypothesis was supported. Why not claim a win?**
- Turning the spare seat off for everyone (δ = 1) helps even more, at every q. So the deadline condition is not what matters.
- The honest summary: the paper's spare-seat rule is the main cost of its heuristic in this model.

**10. Was the hypothesis really fixed before the runs?**
- `docs/scope_note.md`, with the threshold of 0.03 at q = 0.5 and the CI rule, was committed on 2026-11-17 (`bb742b6`). The Part C results were produced on 2026-11-18.

## Reproducibility

**11. How does someone else rerun everything?**
- Run `python -m pytest -q`, then `python run_all.py --quick` (3 seeds, about the shape only), or `--full`.
- On smaller machines, use `tools/run_safe.ps1`. The README has the exact commands.

**12. Why did experiments crash the computer at first?**
- Every Python process reserved about 1.5 GB of maths-library buffers, and QuNetSim starts one process per qubit.
- With one BLAS thread per process, each needs about 100 MB (`docs/TROUBLESHOOTING.md`).

## Limits to say out loud

**13. What would you need before trusting these numbers for real hardware?**
- Probabilistic swaps.
- Memory decay inside a window.
- A real noise model, so fidelity is measured rather than turned into a hop limit.
- The authors' exact n, K and arrival model.
