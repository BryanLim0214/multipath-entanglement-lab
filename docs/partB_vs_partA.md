# Part B against Part A

The numbers come from `results/partB_summary.md` (QuNetSim, 20 seeds per setting) and `results/partA_summary.md` (abstract model, 30 seeds). Figure F3 shows Part B.

## What agrees

- **Multipath succeeds more often than single path in both parts**, on every network and at every q we tried.
  - In Part B, on the two-branch network with n = 4 at q = 0.9, multipath served 0.98 of requests and single path 0.31.
  - On the 3×3 grid at q = 0.5 the rates were 0.67 and 0.58.
- **Both parts improve as q rises**, and the gap between the methods narrows when links become reliable.

## Why the numbers differ

1. **The planner sees different things.** In Part A the routing decision is made after each link's capacity C_ij for the window is known. In Part B the routes are fixed first, and attempts succeed or fail while the pairs are being built (A22). A request can fail part-way, after it has spent attempts.
2. **Capacity works differently.** In Part A a link has C_ij seats, and each pair takes one. In Part B a link has M attempts, and a failed attempt is retried while attempts remain, so the budget is a shared pool.
3. **No optimiser or priority.** Part B has no ILP and no ρ. Requests are served one after another, in arrival order, because QuNetSim breaks with concurrent sends between the same hosts (issue #170).
4. **Different workload.** Part B uses small fixed workloads: one request per window on the two-branch network, four per window on the grid, n of 1 to 4. Part A uses the paper's 60 requests over 100 slots.
5. **Fidelity.** QuNetSim does not model fidelity for these EPR pairs, so only the hop limit carries over from Part A. Every delivered pair was checked for correlation in a random basis instead, and all of them passed.

## What Part B adds

- **The ranking holds when swapping is real:** Bell-state measurements, classical messages and Pauli corrections inside a packet-level simulator.
- **The cost of multipath is visible:** more attempts per request (6.9 against 5.6 on the grid at q = 0.5), and pairs wasted on a path that fails part-way. Part A cannot show this, because it never builds a pair.
- **The wiring is validated against exact values:** on the two-branch network the simulated success rate matches the closed-form binomial prediction in all 22 settings, within a 95% Wilson interval.

The comparison is qualitative. Neither part models hardware noise or memory decay.
