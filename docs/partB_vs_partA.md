# Part B against Part A

The numbers come from `results/partB_summary.md` (QuNetSim, 20 seeds per setting) and `results/partA_summary.md` (abstract model, 30 seeds). Figure F3 shows Part B.

## What agrees

- **Multipath succeeds more often than single path in both parts** whenever link capacity is the limit, on every network and at every q we tried.
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

## Where multipath does not help: packet loss (E4)

The handout's loss sweep uses the simulator's own `packet_drop_rate` with q = 1, so the attempt budget never runs out and lost packets are the only failure.

- **Grid:** single path succeeds more often. At a drop rate of 0.1 the rates are 0.39 for single path and 0.28 for multipath. For 18 of the 36 node pairs on the 3×3 grid, the second disjoint path is two links longer than the shortest one, and every extra link adds packets that can be lost.
- **Two-branch network:** the two methods give identical results (0.09 at 0.1), because both routes have three links and the same seed drops the same packets.
- **Success falls much faster than the drop rate.** The drop hits every packet: EPR halves, acknowledgements and correction bits. A pair needs several of these to arrive.

So multipath helps when capacity is short, and it has nothing to offer against loss that hits every packet equally. Part A has no counterpart to this experiment, because its links never lose a pair once the seats are known.

## Cross-check of our swap

With QuNetSim's built-in entanglement swap and our multipath routes installed as its routing function (`run_partB.py --crosscheck`), 25 of 25 pairs were correlated on the chain, the two-branch network and the grid, with every path tested in both the Z and the X basis. Our hand-built swap therefore agrees with the library's own.

The comparison is qualitative. Neither part models hardware noise or memory decay.
