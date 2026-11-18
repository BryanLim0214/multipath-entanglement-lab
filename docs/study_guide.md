# Study guide: the paper explained three ways

> AI-written study material, used as a scaffold. **Your graded notes go in `paper_notes.md`, in your own words.**
> Each idea has a 🧒 kid line, a 🎓 student line, a 🔬 expert line, and a ⚠️ note on where the analogy breaks.

## 1. Bell pairs: "magic coin pairs"
- 🧒 Two magic coins. Ask both the *same* question and they always agree. Ask *different* questions and the answers look random.
- 🎓 A Bell pair is two qubits whose measurement results are correlated. Measure both the same way and you get matching results. No value is fixed before you measure.
- 🔬 |Φ⁺⟩ = (|00⟩+|11⟩)/√2. These correlations break the classical CHSH limit (S = 2√2 > 2).
- ⚠️ Real coins have a hidden answer from the start; Bell pairs don't. And you can't send a message with them, because each side alone just sees random results.

## 2. Making links: "paper planes over a river"
- 🧒 Every round, each road throws M paper planes across a river. Each one lands with chance q, and a bell rings when one lands, so you know it worked.
- 🎓 Each round (window), each pair of neighbouring nodes makes M attempts. The successes are that link's capacity, C_ij.
- 🔬 C_ij ~ Binomial(M, q). In the paper, M=6 (small) and q ∈ {0.5,…,0.9}.
- ⚠️ Real attempts take time and hardware. Here, a whole round is squeezed into one step.

## 3. Rounds and forgetting: "fridge timer"
- 🧒 At the buzzer, everything in the fridge gets thrown out.
- 🎓 Quantum memories can only hold a pair for a cut-off time t_c, so all pairs are thrown away at the end of each window.
- 🔬 |W| = |T|/t_c windows. Window w covers timeslots [A_w, B_w].
- ⚠️ Real memories fade gradually. The paper uses a hard cut-off.

## 4. Swapping: "the matchmaker"
- 🧒 A middle city holds one coin paired with the left city and one paired with the right city. It joins them, then phones the result to both ends. Now the two end cities share a pair.
- 🎓 Entanglement swapping is a Bell-state measurement at the middle node, followed by a classical message so the ends can fix up their qubits.
- 🔬 BSM + Pauli correction. The paper assumes swaps always succeed.
- ⚠️ The middle city's coins are used up, and the end pair is useless until the phone call arrives.

## 5. Fidelity: "grey paint"
- 🧒 Every join mixes in a little grey paint. Long chains get too washed out to use.
- 🎓 Fidelity measures how close the pair is to perfect. It drops every time you swap, so a path can only pass through a limited number of middle nodes.
- 🔬 Werner parameter w = (4F−1)/3, and over L links F_L = (3w^L+1)/4. With F=0.95 and f=0.78: L ≤ 5.03, so 5 links, so **4 intermediate nodes**. With f=0.6: **10**.
- ⚠️ The grey is random noise, not a copy (quantum states can't be copied). Real swaps also add their own noise, which the model ignores.

## 6. Requests, blocking, multipath: "postcards on different routes"
- 🧒 A request says "send n pairs from S to D before my deadline". If no route has enough seats, the request is turned away. That is "blocked".
- 🎓 Single-path puts all n pairs on one route. Multipath splits them over several routes that share no link. Blocking ratio (BR) = blocked requests ÷ all requests.
- 🔬 Σ_k π^rk = n^r; the paths are edge-disjoint; Σ_r Σ_k β ≤ C_ij. BR = (|R| − Σ X^r)/|R|.
- ⚠️ A pair is never cut in half. Each pair travels whole, on one route.

## 7. ILP vs heuristic: "best possible answer vs quick rule of thumb"
- 🧒 The ILP is a super-careful planner that checks every option. The heuristic is a fast rule of thumb.
- 🎓 The ILP finds the best placement for each window. The heuristic walks greedily toward the destination, picking the neighbour with the best (bottleneck ÷ hops) ratio.
- 🔬 The ILP variables are X^r, X^rk, x^rk_ij, y^rk_i, π^rk, β^rk_ij, with constraints (2a)–(4c). The heuristic is Algorithms 1–3.
- ⚠️ "Best" only means best *within one window*. Over many windows, either method can end up ahead.

## 8. The two rules worth noticing
- **"Last chance goes first" (ρ).** Each request gets a priority ρ = i/|W_r| for its i-th eligible window, so a request's last chance has ρ=1 and is served first.
- **"Keep a spare seat" (δ=2).** The heuristic only lets a request use half of a path's seats. The ILP has no such rule. This mismatch is the starting point of our extension.

## Glossary (plain words)
| Term | Plain words |
|---|---|
| C_ij | seats on a road this round |
| window / t_c | a round, and its length |
| ρ | "last chance goes first" |
| δ | "keep a spare seat" |
| ILP | best possible answer, found by a solver |
| heuristic | quick rule of thumb |
| edge-disjoint | no shared road |
| Γ | share of placed requests that used split routes |
| common random numbers | same dice for everyone |
