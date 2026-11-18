# Part A against the paper: trends, gaps and differences

Every number here comes from `results/partA_summary.md` and `data/paper_values.yaml`, which holds only values the paper prints. Figures F1 and F2 plot our curves with the paper's printed values marked.

## Trends: what matches

| Paper's claim | Ours | Match? |
|---|---|---|
| Multipath blocks fewer requests than single path | True for both pairs (Heu and ILP) at every q and every load | Yes |
| Blocking falls as q rises | True for all five methods | Yes |
| MP-Heu splits less often as q rises (Γ, Table I) | 0.64 to 0.33 over q = 0.5 to 0.9 | Yes, but Γ was our calibration target, so this is weak evidence |
| The ILP is slower than the heuristic, and MP-ILP slower than SP-ILP | Heuristics about 0.03 s per run, SP-ILP about 0.1 s, MP-ILP about 1.2 to 1.5 s | Yes, in ordering |

## Gaps: what does not match, and why we think so

**1. Blocking levels.**
- At q = 0.9 the paper prints 0.27 (MP-ILP) and 0.42 (SP-ILP). Ours are both 0.00.
- Under the printed parameters, our network is much less loaded.
- Two parts of the request model are open to another reading (A3 arrivals, A27 pairs per slot). `experiments/sensitivity.py` tests both after Part A was frozen. Its results are in `results/sensitivity.md` and the report's Section III-D.

**2. Heuristic against ILP.**
- The paper calls them comparable. Ours differ widely at low q: 0.48 against 0.07 at q = 0.5.
- **Diagnosis:**
  - The ILP with the heuristic's headroom cap (ILP-δ) blocks 0.18.
  - The heuristic with δ = 1 blocks 0.09.
  - Greedy search and headroom each cost little alone. Together they cost much more.
- This became our extension (Part C).

**3. Γ of the ILP (held out).**
- Ours is 0.25 to 0.15. The paper's is 0.70 to 0.52.
- The ILP's objective counts served requests, not paths, so equally optimal solutions can split more or less often. Th**4. Compute time.**
- The paper reports 373 to 428 s per SP-ILP run and 783 to 873 s per MP-ILP run, with CPLEX on unknown hardware.
- Ours are about 0.1 s and 1.2 to 1.5 s, with HiGHS on a path formulation (A26) and one thread per job.
- The ordering matches. The absolute times are not comparable.
- An earlier version of our SP-ILP was slower than MP-ILP and sometimes stopped at the 60 s limit. A smaller, equivalent single-path model fixed this without changing any blocking ratio at two decimals (A26).

erse of the paper. We did not investigate why.

## Differences

These are the places where our model may differ from the authors'. Each is recorded in `ASSUMPTIONS.md`.

- **Demand n (A1).** Never given in the paper. We use n ~ U{2,2}, which is always 2 pairs, chosen only by fit to MP-Heu Γ.
- **Paths per request K (A2).** Never given. We use K = min(deg s, deg d).
- **Arrivals (A3).** We read "Poisson(t_c/4, |R|)" as |R| direct draws of the arrival slot, not as gaps between arrivals.
- **Pairs per slot (A27).** We read n as the pairs needed in the window, not n in every one of the h slots.
- **Single-path methods (A4).** The paper does not present them. SP-ILP is the ILP with K = 1, and SP-Heu is the heuristic without splitting.
- **Headroom (A8).** Each pair uses one seat per link (Fig. 1c). δ caps only one request's share of a link.
- **Fidelity (A5).** Werner swapping is inferred, not stated. It reproduces both of the paper's hop limits.
- **Disjointness (A7).** Our paths share no undirected link. The paper's (2d) is per directed arc. We show the as-written version only on the toy network.
- **Solver (A26).** We use HiGHS on a path formulation, which gave the same optimum as the arc formulation on 200 random windows. The paper used CPLEX on the arc formulation.
- **Large setup.** Not run. The paper ran it with heuristics only.

The paper also contains seven internal inconsistencies, listed in `ASSUMPTIONS.md` under "Paper inconsistencies we found".
