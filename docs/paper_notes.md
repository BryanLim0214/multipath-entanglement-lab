# Paper notes

**Paper:** J. Halder, E. Matus, G. Fettweis, "On the Concurrent Multipath Entanglement Distribution in Quantum Networks", IEEE GLOBECOM 2024, pp. 2791 to 2796.

**In one sentence:** in each time window, decide which requests to serve, and over which edge-disjoint paths, so that as many requests as possible get their Bell pairs before they expire. Solve it with an ILP and with a fast greedy heuristic, and show that splitting a request over several paths blocks fewer requests than using one path.

## Network model
- **Graph G(V, E, M).** Nodes are quantum repeaters and routers. Edges are quantum channels between neighbours.
- **Memories.** Every neighbouring pair (i, j) has M memory units, so it can try to make at most M Bell pairs per window. Local operations at nodes are assumed error-free.
- **Link generation.** At the start of each window, each of the M memories on (i, j) tries once and succeeds with probability q_ij. The number that succeed is the link's capacity C_ij for that window, an integer from 0 to M. In the evaluation every link uses the same q.
- **Each success** is a perfect |Φ⁺⟩ pair with initial fidelity F.
- **Time.** Time is cut into slots. A window lasts t_c slots, where t_c is the memory cut-off time. There are |W| = |T|/t_c windows, each running from slot A_w to slot B_w. Every pair is thrown away at the end of its window, and memories refresh together.
- **Swapping.** An intermediate node joins its two neighbouring pairs into one longer pair. The model treats swapping as always successful.
- **What limits path length is fidelity.** Every swap lowers fidelity, so a request with minimum fidelity f^r may use at most I^r intermediate nodes. The paper gives only the resulting numbers (4 for f = 0.78, 10 for f = 0.6), not the formula. See the table below.

## Request model
- **Tuple.** Each request is r = ⟨s, d, n, a, h, b, f⟩:
  - s: source;
  - d: destination;
  - n: number of qubits, which means n end-to-end pairs;
  - a: arrival slot;
  - h: execution time in slots, much smaller than t_c;
  - b: deadline;
  - f: the fidelity the request needs. The paper calls it "maximum allowed", but it acts as a minimum.
- **When it can run.** A request may start at any slot t in [a, b − h + 1], and must finish inside a single window: t ≥ A_w and t + h − 1 ≤ B_w. The windows where that is possible form its eligible set W_r.
- **Priority ρ.**
  - The eligible windows are sorted in time and numbered i = 1 to |W_r|. In its i-th eligible window, the request gets ρ = i/|W_r|.
  - So a request's last chance has ρ = 1, and is handled first.
  - This makes sense: a request with later windows still available can afford to wait. One on its last chance cannot.
- **Unplaced requests** stay in the pool and try again in their next eligible window.
- **Blocking ratio:** BR = (|R| − Σ_r X^r) / |R|, the share of requests never served.

## ILP formulation
This ILP is solved once per window, with C fixed for that window.

**Variables (per request r and path index k):**
- X^r (binary): r is placed.
- X^rk (binary): r uses its k-th path.
- x^rk_ij (binary): the k-th path of r uses link (i, j).
- y^rk_i (binary): node i is an intermediate node on that path.
- π^rk (integer): pairs sent over that path.
- β^rk_ij (integer): pairs that path uses on link (i, j).

**Objective:** maximise Σ_r ρ^r X^r. The printed formula drops the Σ. Requests on their last chance count the most.

**Routing constraints:**
- (2a) Flow conservation. If path k is chosen, one unit of flow leaves s and arrives at d. Otherwise the path is empty.
- (2b) and (2c) Link X^r to the X^rk: r is placed exactly when at least one of its paths is used.
- (2d) Different paths of the same request never share a link.
- (2e) Mark each node the path leaves through, other than s and d, as an intermediate node.
- (2f) At most I^r intermediate nodes per path. This is the fidelity limit.

**Pair-distribution constraints:**
- (3a) Pairs go only on chosen paths: π^rk ≤ n^r X^rk.
- (3b) If r is placed, its paths carry exactly n^r pairs in total.

**Pair-allocation constraints:**
- (4a) and (4b) A path's pairs show up on every link the path uses, and nowhere else. These are big-M linearisations with the constant Δ.
- (4c) Over all requests and both directions, a link carries at most C_ij pairs.

## Heuristic steps
**Algorithm 1 (main loop):**
1. Mark every request unplaced, and compute W_r and ρ for each.
2. For each window in time order:
   - generate links, giving C;
   - collect R_w, the unplaced requests eligible now;
   - call Place(R_w, C) and mark the requests it places;
   - discard all pairs.
3. Return BR.

**Algorithm 2 (Place-Heu):**
- Copy the graph with the current capacities (G′).
- Precompute neighbour lists, and the shortest paths with their bottlenecks.
- Sort R_w by ρ, highest first.
- For each request, call MultiPath-Alloc. After each placement, update G′ and the path data.

**Algorithm 3 (MultiPath-Alloc):**
- **Greedy walk.** Start at s. At the current node k:
  - if d is a neighbour, finish the path;
  - otherwise score each neighbour i by α_i = (bottleneck of the best route through i to d) ÷ (intermediate nodes on that route), then step to the best-scoring neighbour.
- **Repeat.** Save the finished path and its bottleneck, remove its links from the working graph, and walk again from s until no route is left. This gives edge-disjoint paths.
- **Filter and sort.** Drop paths with more than I^r intermediate nodes, then sort the rest by bottleneck, largest first.
- **One path.** If some path alone has bottleneck ≥ n·δ, put all n pairs on it.
- **Split.** Otherwise, if Σ ⌊BC_j / δ⌋ ≥ n, fill the paths in order, putting γ = min(⌊BC_j / δ⌋, pairs still needed) on each.
- **Block.** Otherwise the request is blocked.
- **Seat use.** A path carrying γ pairs uses γ seats on each of its links, so δ only limits how much of a path one request may take. With δ = 2, a request may take at most half of a path's free seats.

**Fig. 1 re-traced by hand** (request 7 → 6, n = 4, δ = 2):

First path:
| Step | Current node | Candidate neighbours | α values | Choice |
|---|---|---|---|---|
| 1 | 7 | 1, 8 | α₁ = 4/3 (7-1-2-4-6), α₈ = 4/2 (7-8-5-6) | 8 |
| 2 | 8 | 3, 5, 9 | α₃ = 3/2 (8-3-5-6, bottleneck min(3,4,4) = 3; paper prints 4/2), α₅ = 4/1, α₉ = 4/1 | tie between 5 and 9, paper takes 5 |
| 3 | 5 | 6 is a neighbour | | path 7-8-5-6, bottleneck 4 |

Second path. The links 7-8, 8-5 and 5-6 are removed, so the walk from 7 goes 7 → 1 → 2 → 4 → 6:
- At node 1: α₂ = 4/2, α₃ = 2/3.
- At node 2: α₄ = 4/1.
- The result is path 7-1-2-4-6, with bottleneck 4.

Node 7 now has no links left, so the walk stops.

Allocation:
- PT = {7-8-5-6, 7-1-2-4-6}, BC = {4, 4}.
- No single path has 4 ≥ n·δ = 8.
- Splitting works: ⌊4/2⌋ + ⌊4/2⌋ = 4 ≥ 4, so each path carries 2 pairs.

Remaining capacities:
| Link | Before | After |
|---|---|---|
| 7-8 | 5 | 3 |
| 8-5 | 8 | 6 |
| 5-6 | 4 | 2 |
| 7-1 | 4 | 2 |
| 1-2 | 6 | 4 |
| 2-4 | 4 | 2 |
| 4-6 | 4 | 2 |

This matches Fig. 1c exactly. It also confirms that a pair uses one seat per link (γ seats in total), not δ·γ.

## Evaluation setup
| | Small scale | Large scale |
|---|---|---|
| Topology | 3×3 grid | 5×5 grid |
| \|R\| | 60 | 1000 |
| M | 6 | 10 |
| T | 100 | 10000 |
| t_c (windows) | 10 (10) | 10 (1000) and 20 (500) |
| f, so I | 0.78, so 4 | 0.6, so 10 |
| Methods | SP-ILP, SP-Heu, MP-ILP, MP-Heu | SP-Heu, MP-Heu |
| Runs per q | 10 | 20 |

**Common to both scales:**
- F = 0.95.
- q ∈ {0.5, 0.6, 0.7, 0.8, 0.9}, the same on every link.
- δ = 2.
- Arrivals "Poisson(t_c/4, |R|)".
- h uniform on [1, 4], and b uniform on [a + h + 1, T].
- 95% confidence intervals.
- CPLEX 12.8 for the ILPs, Python 3.11 for the heuristics.

**Metrics:**
- Γ: the share of placed requests that used more than one path.
- BR: the blocking ratio.
- CT: compute time.

**Headline numbers:**
- **Small, q = 0.9:** BR 0.27 for MP-ILP vs 0.42 for SP-ILP. Multipath is lower at every q.
- **Γ falls as q rises:**
  - MP-ILP goes from 0.70 to 0.52.
  - MP-Heu goes from 0.66 to 0.45.
- **Compute time:**
  - SP-ILP 373 to 428 s, MP-ILP 783 to 873 s.
  - SP-Heu 1.4 s, MP-Heu 2 s.
- **Large, q = 0.9:**
  - t_c = 10: BR 0.231 for SP-Heu vs 0.156 for MP-Heu.
  - t_c = 20: BR 0.254 vs 0.173.
  - Γ for MP-Heu ranges 0.72 to 0.55 at t_c = 20, and 0.66 to 0.45 at t_c = 10.

## Fidelity table
For a Werner state, w = (4F − 1)/3, so F = 0.95 gives w = 0.93333. Ideal swapping multiplies w, so after L links F_L = (3w^L + 1)/4.

| L (links) | intermediate nodes | F_L | meets f = 0.78? |
|---|---|---|---|
| 1 | 0 | 0.9500 | yes |
| 2 | 1 | 0.9033 | yes |
| 3 | 2 | 0.8598 | yes |
| 4 | 3 | 0.8191 | yes |
| 5 | 4 | 0.7812 | yes |
| 6 | 5 | 0.7458 | no |

So the limit is at most 5 links, or 4 intermediate nodes, exactly the paper's number. The same formula with f = 0.6 allows 11 links, or 10 intermediate nodes, which also matches.

The margin is thin (5.03 links), so the formula fits the paper's numbers but is not stated in the paper. I record it as an inferred assumption (A5).

## Details the paper leaves out
These are my choices, cross-referenced to `ASSUMPTIONS.md`:
- How many pairs n each request needs (A1). I calibrate it on Γ only, and keep BR as the test.
- K, the number of candidate paths in the ILP (A2). I use min(deg s, deg d).
- Whether "Poisson(t_c/4, |R|)" gives arrival times or gaps (A3). I read it as arrival times, matching NumPy's `poisson(lam, size)`.
- The single-path ILP and heuristic (A4). They are not given, so I define them by turning off splitting.
- The fidelity formula (A5). Werner swapping, as in the table above.
- Whether links succeed independently (A6). I assume they do.
- Whether "edge-disjoint" is directed or undirected (A7). I use undirected.
- The exact α rule, tie-breaking, dead ends, and the shared vs private working graph (A9 to A12).
- The value of the big-M constant Δ (A18). I use the smallest valid values.

## Things that looked wrong or inconsistent
1. The Fig. 1 request is written ⟨6, 7, 4⟩, but the walk-through and the caption route 7 → 6.
2. α₃ in step (ii) is printed as 4/2. With the same rule that gives the other four α values, it is 3/2, because edge 8-3 has capacity 3. The chosen path does not change.
3. The objective is missing its Σ over requests.
4. Section IV calls the multipath heuristic "(SP-Heu)".
5. The abstract says swapping is probabilistic, but the model never lets a swap fail.
6. f is called the "maximum allowed fidelity", but it is used as a minimum.
7. Constraint (2d) only stops two paths using the same link in the same direction, while the text says the paths are edge-disjoint.
