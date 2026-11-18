# Toy networks: hand-worked answers

The lab requires two things: "On a 4-6 node toy network, work out the optimal answer by hand and confirm your ILP returns it", and "Confirm the heuristic never beats the ILP".

These answers were worked out by hand and committed **before** any solver code existed. The git history proves the order. Each toy has progressive hints, so you can re-derive the answer yourself before reading the solution.

**Rules for both toys:**
- There is one window, and the capacities are already known.
- A request is either fully served (all n pairs) or blocked.
- **SP** puts all n pairs on one path. A path carries at most its bottleneck, the smallest capacity along it.
- **MP** may split the n pairs over paths that share no link. Each link's capacity is shared by every request that uses it.
- A path may have at most **I** intermediate nodes.
- The ILP maximises Σ ρ_r · X_r, where X_r = 1 if request r is served.
- The heuristic follows the paper's δ = 2 rule (A8). A single path qualifies if its bottleneck is ≥ n·δ. A split is allowed if Σ ⌊BC/δ⌋ ≥ n. Each pair uses one seat per link.

---

## Toy 1: when is splitting needed?

```
            (2)   2   (2)
          /             \
        1 ──(1)── 4 ──(1)── 5
          \             /
            (2)   3   (2)
```

**Links (capacity):** 1-2: 2, 2-5: 2, 1-3: 2, 3-5: 2, 1-4: 1, 4-5: 1. **Hop limit:** I = 4, which never binds here.

| Request | Route | n | ρ |
|---|---|---|---|
| r1 | 1 → 5 | 4 | 1 |
| r2 | 1 → 5 | 1 | 1 |

<details><summary>Nudge</summary>

How many different routes lead from 1 to 5? What is the most pairs each one can carry?
</details>

<details><summary>Hint 1</summary>

There are exactly three routes: 1-2-5, 1-3-5 and 1-4-5. Their bottlenecks are 2, 2 and 1.
</details>

<details><summary>Hint 2</summary>

No single route can carry 4 pairs. Together, though, the routes can carry 2 + 2 + 1 = 5 pairs, which is exactly what r1 and r2 need.
</details>

<details><summary>Full solution</summary>

**SP-ILP: objective 1.**
- r1 needs one path with bottleneck ≥ 4. None exists, so r1 is blocked.
- r2 fits on any path.
- Only one request is served.

**MP-ILP: objective 2.**
- r1 splits 2 + 2 over 1-2-5 and 1-3-5.
- r2 takes 1-4-5.
- All 5 seats leaving node 1 are used, so both requests are served.
- Other optimal splits exist, for example r1 = 2 + 1 + 1 and r2 on the route with a seat left. The objective is the same.

**Heuristic (δ = 2): objective 1.**
- r1:
  - A single path needs bottleneck ≥ 8; none has it.
  - Splitting would need ⌊2/2⌋ + ⌊2/2⌋ + ⌊1/2⌋ = 2 ≥ 4, which fails.
  - So r1 is blocked.
- r2:
  - A single path needs bottleneck ≥ 2. Route 1-2-5 (or 1-3-5, on a tie) qualifies.
  - So r2 is served.
- The heuristic scores 1, below the ILP's 2. This is consistent with "the heuristic never beats the ILP".

**What this toy tests:** that multipath is needed, and that the δ rule makes the heuristic strictly worse than the ILP here.
</details>

---

## Toy 2: when does the fidelity limit bite?

```
  1 ──(3)── 2 ──(3)── 3          short route: 1 intermediate node
  │                   │
 (2)                 (2)
  │                   │
  4 ──(2)── 5 ──(2)── 6          long route 1-4-5-6-3: 3 intermediate nodes
```

**Links (capacity):** 1-2: 3, 2-3: 3, 1-4: 2, 4-5: 2, 5-6: 2, 6-3: 2. **Fidelity:** F = 0.95 and f = 0.85.

| Request | Route | n | ρ |
|---|---|---|---|
| rA | 1 → 3 | 4 | 1 |
| rB | 1 → 3 | 3 | 0.5 |

<details><summary>Nudge</summary>

Before routing anything, work out how many intermediate nodes a path may have when f = 0.85.
</details>

<details><summary>Hint 1</summary>

w = (4·0.95 − 1)/3 = 0.93333. You need w^L ≥ (4·0.85 − 1)/3 = 0.8, where L is the number of links. Solve for the largest L.
</details>

<details><summary>Hint 2</summary>

L ≤ ln 0.8 / ln 0.93333 = 3.23, so at most 3 links, which means **I = 2**. That rules out the long route, which has 3 intermediate nodes. Only 1-2-3 is left, and it has 3 seats.
</details>

<details><summary>Full solution</summary>

**Hop limit:** I = 2, from the hints.

**MP-ILP and SP-ILP: objective 0.5.**
- rA needs 4 pairs, but the only allowed route has 3 seats, so rA is blocked.
- rB needs 3 pairs and fits exactly on 1-2-3.

**The same instance without the hop limit: objective 1.0.**
- rA splits over the short route and the long route (2 + 2, or 3 + 1), so it is served.
- That uses at least 4 of the 5 seats, which leaves at most 1 for rB, so rB is blocked.
- Serving rB instead would give only 0.5.

The optimum changes from 0.5 to 1.0, and the served request changes from rB to rA. So this toy catches a missing or wrong fidelity constraint.

**Heuristic (δ = 2): objective 0.**
- Its walk finds 1-2-3 and 1-4-5-6-3, then drops the long route because of the hop limit.
- rA: 3 ≥ 8 fails, and ⌊3/2⌋ = 1 ≥ 4 fails, so rA is blocked.
- rB: 3 ≥ 6 fails, and 1 ≥ 3 fails, so rB is blocked.
- The heuristic scores 0, below the ILP's 0.5.

**What this toy tests:** the fidelity hop limit, the ρ weighting, and the δ rule.
</details>

---

## Machine-readable expected values

The solver tests read this block.

```yaml
toy1:
  I: 4
  edges: [[1, 2, 2], [2, 5, 2], [1, 3, 2], [3, 5, 2], [1, 4, 1], [4, 5, 1]]   # [u, v, capacity]
  requests: [{id: r1, s: 1, d: 5, n: 4, rho: 1.0}, {id: r2, s: 1, d: 5, n: 1, rho: 1.0}]
  expected: {sp_ilp: 1.0, mp_ilp: 2.0, mp_heu_delta2: 1.0, mp_ilp_served: [r1, r2], sp_ilp_served: [r2]}
toy2:
  F: 0.95
  f: 0.85
  I: 2
  edges: [[1, 2, 3], [2, 3, 3], [1, 4, 2], [4, 5, 2], [5, 6, 2], [6, 3, 2]]   # [u, v, capacity]
  requests: [{id: rA, s: 1, d: 3, n: 4, rho: 1.0}, {id: rB, s: 1, d: 3, n: 3, rho: 0.5}]
  expected: {mp_ilp: 0.5, sp_ilp: 0.5, mp_ilp_no_hop_limit: 1.0, mp_heu_delta2: 0.0, mp_ilp_served: [rB], mp_ilp_no_hop_limit_served: [rA]}
```
