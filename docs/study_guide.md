# Study guide: the paper explained three ways

> Each idea is explained at three levels: **Kid**, **Student**, and **Expert**. Each one also says **where it breaks**, meaning where the simple picture stops being true. The detailed notes are in `paper_notes.md`.

## 1. Bell pairs: magic coin pairs
- **Kid:** You have two magic coins. Ask both the same question and they always agree. Ask them different questions and the answers look random.
- **Student:** A Bell pair is two qubits whose measurement results match when you measure both the same way. Neither result is decided before the measurement.
- **Expert:** |Φ⁺⟩ = (|00⟩ + |11⟩)/√2. Its correlations violate the classical CHSH bound (S = 2√2 > 2).
- **Where it breaks:**
  - Real coins have a hidden answer from the start. Bell pairs do not.
  - You cannot send a message with them, because each side on its own only sees random results.

## 2. Making links: paper planes over a river
- **Kid:** Every round, each road throws M paper planes across a river. Each plane lands with chance q, and a bell rings when one lands, so you know it worked.
- **Student:** In each round (a window), every pair of neighbouring nodes makes M attempts. The attempts that succeed are that link's capacity, C_ij.
- **Expert:** C_ij ~ Binomial(M, q). The paper uses M = 6 (small setup) and q ∈ {0.5, ..., 0.9}.
- **Where it breaks:** Real attempts take time and hardware. Here, a whole round happens in a single step.

## 3. Rounds and forgetting: the fridge timer
- **Kid:** When the buzzer goes off, everything in the fridge gets thrown out.
- **Student:** Quantum memories can only hold a pair for a cut-off time t_c, so every pair is discarded at the end of each window.
- **Expert:** There are |W| = |T|/t_c windows. Window w covers timeslots [A_w, B_w].
- **Where it breaks:** Real memories fade gradually. The paper instead uses a hard cut-off.

## 4. Swapping: the matchmaker
- **Kid:**
  - A middle city holds one coin paired with the left city, and one paired with the right city.
  - It joins the two, then phones the result to both ends.
  - Now the two end cities share a pair.
- **Student:** Entanglement swapping is a Bell-state measurement at the middle node. It is followed by a classical message, so the end nodes can correct their qubits.
- **Expert:** A Bell-state measurement plus a Pauli correction. The paper assumes every swap succeeds.
- **Where it breaks:**
  - The middle city's coins are used up.
  - The end pair is unusable until the phone call arrives.

## 5. Fidelity: grey paint
- **Kid:** Every join mixes in a little grey paint. A long chain gets too washed out to use.
- **Student:** Fidelity measures how close a pair is to perfect. It drops with every swap, so a path can only pass through a limited number of middle nodes.
- **Expert:**
  - Werner parameter w = (4F − 1)/3. Over L links, F_L = (3w^L + 1)/4.
  - With F = 0.95 and f = 0.78: L ≤ 5.03, so 5 links, which means **4 intermediate nodes**.
  - With f = 0.6: **10** intermediate nodes.
  - You can check both limits with the fidelity table in `paper_notes.md`.
- **Where it breaks:**
  - The grey is random noise, not a copy; quantum states cannot be copied.
  - Real swaps also add noise of their own, which this model ignores.

## 6. Requests, blocking, multipath: postcards on different routes
- **Kid:** A request says "send n pairs from S to D before my deadline". If no route has enough seats, the request is turned away. That is called "blocked".
- **Student:**
  - Single-path routing puts all n pairs on one route.
  - Multipath splits them over several routes that share no link.
  - The blocking ratio (BR) is blocked requests divided by all requests.
- **Expert:**
  - Σ_k π^rk = n^r.
  - The paths are edge-disjoint.
  - Σ_r Σ_k β ≤ C_ij.
  - BR = (|R| − Σ X^r)/|R|.
- **Where it breaks:** A pair is never cut in half. Each pair travels whole, on a single route.

## 7. ILP vs heuristic: the best possible answer vs a quick rule of thumb
- **Kid:** The ILP is a very careful planner that checks every option. The heuristic is a fast rule of thumb.
- **Student:**
  - The ILP finds the best placement within each window.
  - The heuristic walks greedily toward the destination. At each step it picks the neighbour with the best ratio of bottleneck capacity to number of hops.
- **Expert:**
  - ILP variables: X^r, X^rk, x^rk_ij, y^rk_i, π^rk, β^rk_ij.
  - ILP constraints: (2a) to (4c).
  - Heuristic: Algorithms 1 to 3.
- **Where it breaks:** "Best" only means best within one window. Over many windows, either method can end up ahead.

## 8. Two rules worth noticing
- **Last chance goes first (ρ).**
  - Each request gets a priority ρ = i/|W_r| in its i-th eligible window.
  - A request's last chance therefore has ρ = 1, and it is served first.
- **Keep a spare seat (δ = 2).**
  - The heuristic lets a request take at most half of a path's free seats.
  - Each pair still uses only one seat; δ just caps how much one request may grab.
  - The ILP has no such rule. That mismatch is where our extension starts.
- **Where these break:**
  - ρ only ranks requests inside one round; it does not plan ahead across rounds.
  - δ = 2 is a fixed safety margin, not something the paper derives. It may waste seats when nobody else needs them.

## Glossary in plain words
| Term | Plain words |
|---|---|
| C_ij | seats on a road this round |
| window, t_c | a round, and how long it lasts |
| ρ | last chance goes first |
| δ | keep a spare seat |
| ILP | the best possible answer, found by a solver |
| heuristic | a quick rule of thumb |
| edge-disjoint | no shared road |
| Γ | share of placed requests that used split routes |
| common random numbers | the same dice for everyone |
