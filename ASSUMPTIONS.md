# Assumptions

The paper (Halder, Matus, Fettweis, GLOBECOM 2024) leaves some model details unspecified or inconsistent. Each choice we had to make gets an **A-number**. Code that depends on a choice cites it in a one-line comment, for example `# A8`.

**Status key**
- **paper**: stated in the paper.
- **inferred**: derived from the paper's numbers or the authors' earlier work.
- **assumed**: our own choice.
- **calibrated**: tuned against one paper number (disclosed), with every other number held out.

| ID | Topic | What the paper says | Our choice | Status |
|---|---|---|---|---|
| A1 | Pairs per request, n^r | Never given. | Candidates U{1..3}, U{2..4}, U{2..6}, U{2..10}. U{2..10} is the net-rate range the authors used in their earlier paper [R1], for a different model (secondary source; page not yet verified). We pick the one whose MP-Heu **Γ** (Table I) matches best. **Blocking ratio is held out** as the test. Residuals are reported. | calibrated |
| A2 | Max paths per request, K (ILP) | Not given. | K = min(deg s, deg d), so at most 4 on a 3×3 grid. | assumed |
| A3 | Arrival times | "poison distribution with parameters (\|t_c\|/4, \|R\|)" | This matches NumPy's `poisson(lam, size)` signature, so we use `a = rng.poisson(t_c/4, size=\|R\|)`. Sensitivity checks: λ = ⌊t_c/4⌋, and treating the draws as inter-arrival gaps. The gap reading would push many arrivals past T, so we consider it implausible. | inferred |
| A4 | Single-path baselines | "not presented in this work" (footnote 1). | SP-ILP is MP-ILP with K=1. SP-Heu is MP-Heu with splitting disabled (Alg. 3 lines 25–35 skipped). SP-SPF is the lab's plain baseline: hop-shortest path, with the same δ rule as the heuristics. | assumed |
| A5 | Fidelity model | F=0.95, f=0.78 gives "4 intermediate nodes", and f=0.6 gives 10. No formula is stated. | Werner-state swapping with ideal swaps: w=(4F−1)/3 and F_L=(3w^L+1)/4 over L links. This gives exactly 4 and 10 (checked numerically). The authors' earlier paper [R1] reportedly uses the same formula as its Eq. 2. That is a secondary source, still to be verified against the open-access text. f is read as the *minimum required* fidelity, although the paper calls it "maximum allowed". | inferred |
| A6 | Link capacity | C_ij ≤ M, generated with probability q_ij. | Each window, C_ij ~ Binomial(M, q), independent across links. Capacity is undirected and shared by both directions, as in constraint (4c). | paper + assumed (independence) |
| A7 | Edge-disjointness | Text says "edge-disjoint". Constraint (2d) is per *directed* arc. | Undirected edge-disjointness. The as-written directed version is kept only as a toy-case comparison. | assumed |
| A8 | δ (headroom) | Alg. 3: BC_i ≥ n·δ, or Σ⌊BC_i/δ⌋ ≥ n. Fig. 1c shows only γ links consumed. | A path alone qualifies if BC ≥ n·δ. When splitting, path j carries γ_j ≤ ⌊BC_j/δ⌋. Seats consumed = γ, not γ·δ. The ILP as written has no δ. | paper + inferred |
| A9 | α in Alg. 3 | α_i = β_kd / l_kd; Fig. 1 example values. | α_i = bottleneck of (k→i, then the best route from i to d) ÷ the number of intermediate nodes on that route. Nodes already on the path are excluded. Ties are broken randomly with a seeded RNG. This matches 4 of the 5 α values in Fig. 1; α₃ is printed as 4/2 but the rule gives 3/2, and the outcome is unchanged. | inferred |
| A10 | Path search state | Line 18: "Update G′ by removing all links from path". | The path search for one request uses a private copy of G′. The shared G′ changes only when a request is actually allocated. | assumed |
| A11 | Dead end in Alg. 3 | "Return False, exit()" | A dead end stops the search for *more* paths for this request. Paths already found are kept. | assumed |
| A12 | Alg. 3 lines 22–24 | "for all i: if BC_i ≥ nδ then allocate" | Allocate on the first qualifying path (the highest BC), then stop. | assumed |
| A13 | ILP objective and timing | "Maximize X^r ρ^r" (Σ missing). Solved per window. | Each window maximizes Σ_r ρ_r X_r + ε·(deterministic id tie-break). Unplaced requests carry over to their next eligible window. | paper + assumed |
| A14 | Window eligibility | t^r ∈ [a, b−h+1], t ≥ A_w, t+h−1 ≤ B_w. | As stated: window w is eligible if some start time fits entirely inside it. | paper |
| A15 | h, b | h ~ U[1,4]; b random in [a+h+1, \|T\|]. | Integer uniform draws, inclusive. | paper + assumed (integer) |
| A16 | Order within a window | Sort R_w by decreasing ρ. | ρ descending, then arrival time, then request id. | paper + assumed (ties) |
| A17 | "K-shortest paths P_ij" (heuristic) | K not given; the same letter K is reused. | All simple paths with ≤ I^r+1 hops. This set is complete and small on 3×3 and 5×5 grids. | assumed |
| A18 | Big-M (Δ) | Δ not given. | The tightest valid values: Δ = n^r in (4a)/(4b), and Δ = K in (2b). | assumed |
| A19 | Fair comparison | Not discussed. | "Same dice for everyone": every method sees the same link outcomes and the same requests for a given seed, so comparisons are paired. | assumed |
| A20 | Paper numbers | Only some are printed in the text. | Points read off the paper's figures are digitized by eye (±0.03) and labeled "approx., digitized" in every overlay. | disclosed |
| A22 | Part B link failure | No paper value; this is about our simulator choice. Probe P3 (`docs/qunetsim_feasibility.md`) found two problems. The per-link `Fibre` loss does **not** affect EPR pairs in swap mode. The global `packet_drop_rate` also drops classical and ACK packets. | Per window, each link has a budget of M attempts (its memories). Each hop attempt uses one attempt and succeeds with probability q (seeded RNG). Failed hops are retried while the link has attempts left. A pair is delivered when every hop on its path has succeeded, and a request succeeds when all n pairs arrive within the window. Routes are chosen **before** outcomes are known, which is what makes Part B differ from Part A. How this is implemented inside QuNetSim is decided by probe P7. The handout-literal variant, which uses the simulator's own `packet_drop_rate`, is also run and reported. | assumed; implementation pending P7 |
| A21 | ILP-δ (our diagnostic) | (not in paper) | The paper's ILP plus a per-request, per-edge cap π_r(e) ≤ ⌊C_e/δ⌋. Every heuristic allocation is then also feasible for ILP-δ. | ours |

## Paper inconsistencies we found

These are reported, not silently fixed.

1. The Fig. 1 request is written ⟨s,d,n⟩ = ⟨6,7,4⟩, but the walk-through routes 7→6.
2. In the Fig. 1 walk-through, α₃ is printed as 4/2. Under the rule that reproduces the other four α values, it is 3/2, because the bottleneck of 8→3→5→6 is min(3,4,4)=3. The chosen path is unaffected.
3. The objective (1) is written without the sum over requests.
4. In Section IV, the multipath heuristic is listed as "(SP-Heu)", which is a typo for MP-Heu.
5. The abstract says swapping is probabilistic, but the model treats swapping as always successful.
6. f^r is called the "maximum allowed fidelity". It behaves as a minimum required fidelity.
7. Constraint (2d) enforces disjointness per directed arc, while the text says the paths are edge-disjoint.

## References

- **[P]** J. Halder, E. Matus, G. Fettweis, "On the Concurrent Multipath Entanglement Distribution in Quantum Networks," *IEEE GLOBECOM 2024*, pp. 2791–2796, doi:10.1109/GLOBECOM52923.2024.10901810. This is the paper being reproduced, and the only primary source for model details.
- **[R1]** Halder, Rajabov, Bassoli, Fitzek, Fettweis, "Optimal routing and end-to-end entanglement distribution in quantum networks," *Scientific Reports* 14 (2024), open access, PMC11336113. It solves a different (offline, resource-minimising) problem. It is cited here only as secondary support, and every detail taken from it is marked as such.
