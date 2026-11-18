# Toy networks: solve these BY HAND before any solver code exists

> **Lab rule:** "On a 4-6 node toy network, work out the optimal answer by hand and confirm your ILP returns it."
> - Fill in the answer boxes, then commit this file **before** `src/qmp/ilp.py` exists.
> - The git history proves the order.
> - The solutions are intentionally not included.

**Rules for both toys (one window, capacities already known):**
- A request is either fully served or blocked. All n pairs must be delivered.
- Single-path (SP): all n pairs go on one path. A path can carry at most its **bottleneck** (the smallest capacity along it).
- Multipath (MP): the n pairs may be split over several paths that share **no link**. Each link's capacity is shared by every request that uses it.
- A path may have at most **I** intermediate (middle) nodes.
- The ILP maximises Σ ρ_r · X_r, where X_r = 1 if request r is served.

---

## Toy 1: "When is splitting needed?" (I = 4, so the hop limit doesn't matter)

```
            (2)   2   (2)
          /             \
        1 ──(1)── 4 ──(1)── 5
          \             /
            (2)   3   (2)
```
(three routes from 1 to 5: via 2, via 4, via 3)
Edges (capacity): 1–2: **2**, 2–5: **2**, 1–3: **2**, 3–5: **2**, 1–4: **1**, 4–5: **1**

| Request | From → To | n (pairs) | ρ |
|---|---|---|---|
| r1 | 1 → 5 | 4 | 1 |
| r2 | 1 → 5 | 1 | 1 |

**Your answers:**
- SP-ILP optimal objective = ____. Which requests are served, and on which paths? ________________
- MP-ILP optimal objective = ____. Which requests are served, and how are the pairs split over paths? ________________
- 🧠 Bonus (heuristic with δ=2, the "keep a spare seat" rule): can r1 be served? ____. Can r2? ____. Explain in one line: ________________

---

## Toy 2: "When does the fidelity limit bite?" (f = 0.85, so I = 2: at most 2 middle nodes)

```
  1 ──(3)── 2 ──(3)── 3          (short route: 1 middle node)
  │                   │
 (2)                 (2)
  │                   │
  4 ──(2)── 5 ──(2)── 6          (long route 1-4-5-6-3: 3 middle nodes)
```
Edges (capacity): 1–2: **3**, 2–3: **3**, 1–4: **2**, 4–5: **2**, 5–6: **2**, 6–3: **2**

| Request | From → To | n (pairs) | ρ |
|---|---|---|---|
| rA | 1 → 3 | 4 | 1 |
| rB | 1 → 3 | 3 | 0.5 |

**Your answers:**
- Check first: with F=0.95 and f=0.85, is the max number of middle nodes really 2? Show the w^L calculation: ________________
- MP-ILP optimal objective = ____. Which requests are served, and on which paths? ________________
- 🧠 What would the MP-ILP objective be if you *forgot* the hop limit? ____. Why does that matter for testing our code? ________________
- 🧠 Bonus (heuristic with δ=2): what happens to rA and to rB? ________________

---
Solved by: ____________  Date: ____________
