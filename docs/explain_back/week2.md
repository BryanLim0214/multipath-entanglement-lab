# Week 2 explain-back: the Part A engine and the ILP

These are the questions an advisor is most likely to ask about the Part A code. Each answer gives a short plain explanation, and the place in the code to point at. Read the answer, open the function, and say it back in your own words.

## The model

**1. Where does a link's capacity come from in each round?**
- `model.sample_capacity` draws `Binomial(M, q)` for every link. That is M attempts, each succeeding with chance q (A6).
- `sim.simulate` gives every window its own random stream, `default_rng([seed, 1, w])`.
- So every method sees the same link outcomes for the same seed and window. We call this "same dice for everyone" (A19), and `tests/test_model.py` checks it in all 10 windows.

**2. When may a request run?**
- `model.eligible_windows` keeps window w only if the request can start at or after its arrival, run h slots, and finish inside the window and by its deadline: max(a, A_w) + h − 1 ≤ min(b, B_w) (A14).
- Example from the tests: a request arriving at slot 8 with h = 4 cannot fit in window 1 (slots 1 to 10), because it would end at slot 11.

**3. What is ρ, and why does it matter?**
- `model.rho_for` numbers a request's eligible windows 1..k and gives the i-th one ρ = i/k. A request's last chance therefore has ρ = 1.
- Both the heuristic's ordering and the ILP's objective favour requests that are about to expire.

**4. Why is the hop limit 4?**
- `fidelity.max_intermediate(0.95, 0.78)` returns 4.
- Werner swapping multiplies w = (4F − 1)/3 along the path, and F_L = (3w^L + 1)/4 drops below 0.78 at L = 6 links.
- Six links means five middle nodes, so at most four middle nodes are allowed (A5).

## The heuristic (`heuristic.py`)

**5. How does the walk choose the next node?**
- `alpha_scores` gives each neighbour i the score α_i = min(c(k,i), β) / hops.
  - β is the bottleneck of the fewest-hop route from i to the destination, choosing the widest such route.
  - hops is the number of middle nodes on the route through i.
- `greedy_walk` moves to the best score.
- This reproduces the paper's Fig. 1 values, except α₃, where the paper's printed 4/2 should be 3/2.

**6. How does it get several paths?**
- `find_paths` copies the working graph, walks once, removes that path's links from the copy, and walks again.
- It stops when the source has no links left, or at a dead end.
- The paths are edge-disjoint by construction.

**7. What does δ = 2 do?**
- `choose_split` puts all n pairs on one path only if that path's bottleneck is at least 2n. Otherwise each path j may carry at most ⌊BC_j/2⌋ pairs.
- `use_seats` then subtracts only the pairs actually sent (A8, matching Fig. 1c).
- So δ caps how much one request may grab. It does not make pairs cost double.

**8. What is the extension in one line?**
- `delta_for` returns δ = 1 when ρ = 1, and otherwise the paper's δ = 2.
- In words: keep a spare seat, unless this is the request's last chance.

## The ILP (`ilp.py`)

**9. Why are there two ILPs?**
- `solve_arc` is the paper's formulation as written: flow variables on every arc.
- `solve_path` lists every allowed path and picks some of them.
- They give the same optimum on 200 random windows (`tests/test_ilp_equivalence.py`), and match an independent brute-force search on 150 (`tests/test_bruteforce.py`).
- `solve_path` is used for the experiments because it is much faster: about 2 s versus no answer in 30 s on a 60-request window (A26).

**10. How do we know the heuristic never beats the ILP?**
- `tests/test_invariants.py` solves 80 random windows three ways and checks heuristic ≤ ILP-δ ≤ ILP.
- ILP-δ is the ILP with the heuristic's δ cap added, so every heuristic answer is also a legal ILP-δ answer (A21).
- This only holds when the ILP reports "optimal". A time-limited solve counts as inconclusive, never as a pass.

**11. What stops a wrong answer from sneaking in?**
- `core.validate` is the referee. It checks:
  - every road starts and ends correctly;
  - every road uses real links;
  - no road visits a city twice;
  - the hop limit;
  - no link is shared between one request's roads;
  - all-or-nothing delivery;
  - link capacity.
- `sim.simulate` stops the run if any method's answer breaks a rule, or if a solver reports an error.

**12. How do we know the tests themselves work?**
- The canaries (`tests/test_canaries.py`, `tests/test_canaries_engine.py`) plant bugs and require our checks to catch them:
  - using seats twice;
  - forgetting the first link in α;
  - ignoring execution time;
  - breaking the same dice;
  - ignoring δ;
  - dropping a capacity constraint.
