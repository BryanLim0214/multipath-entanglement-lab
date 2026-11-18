# Scope note: multipath entanglement distribution

**Students:** Panhapiseth Lim (lim_p65274@utpb.edu) and Victor Akinmade (akinmade_v27471@utpb.edu), UTPB

**Advisor:** ____________  **Date:** 2026-11-__

**Goal.** Reproduce Halder, Matus and Fettweis (GLOBECOM 2024): multipath vs single-path routing, and ILP vs heuristic, by blocking ratio. Then check the claim in QuNetSim, and test one small extension.

## Topologies
1. **3×3 grid.** The paper's small setup: |R|=60, M=6, T=100, t_c=10, δ=2, F=0.95, f=0.78. Used in Parts A and B.
2. **6-node two-branch network.** Two disjoint routes S→D. Used in Part B.

The 3-node chain is only a wiring check, not an experiment.

## Metrics
1. **Blocking ratio** in Part A, and **success rate** in Part B. Both are reported as a mean with a 95% CI, over 30 paired seeds in Part A and 20 or more runs in Part B.
2. **Γ**, the share of served requests that used more than one path.
3. **Time:** compute time in Part A, and request completion time in Part B.

## Methods
- **Single path:** SP-SPF (plain shortest path, the lab baseline), SP-Heu and SP-ILP. The paper omits the single-path versions, so we define them ourselves.
- **Multipath:** MP-Heu and MP-ILP.
- **Sweeps:** blocking ratio against q (the paper's axis) and against load |R| (the lab's axis).

**Part B link failure.** Each link has M attempts per round, and each attempt succeeds with chance q. Routes are fixed before outcomes are known. The simulator's own `packet_drop_rate` is run as a second variant.

## Extension
**Deadline-aware δ**, or "keep a spare seat unless it is your last chance".

The paper's heuristic lets a request take at most half of a path's free seats (δ=2), but the paper's ILP has no such limit. We use δ=1 only when the request is in its last eligible window (ρ=1). This is compared with δ=2, δ=1 always, MP-ILP and SP-Heu, on the same seeds. This is the handout's "heuristic variants" option, tested in Part A.

## Hypothesis
On the 3×3 setup at q=0.5, deadline-aware δ lowers MP-Heu's blocking ratio by at least 3 percentage points. It counts as supported if the paired mean difference is at least 3 pp **and** the lower bound of its 95% CI is above 0. A negative result will be reported.

## Assumptions
These are listed in `ASSUMPTIONS.md` (A1 to A22). The key one: the paper never gives the demand size n, so we calibrate n on Γ only, and blocking ratio stays a held-out check.

## Cut list (in this order, if behind schedule)
1. The QuantumLab companion (not graded).
2. The Part B grid becomes a 2×3 ladder.
3. Part B entirely, with your approval only.

## Questions for the advisor
1. Do you approve the topologies, metrics, extension and hypothesis?
2. Part B loss: is a wrapper-based per-link q (closest to the paper) acceptable as the main model, with the simulator's `packet_drop_rate` as the second variant?
3. May AI tools read the paper PDF?
4. Should the QuantumLab companion count toward the grade?

**Approved by:** ____________  **Date:** ____________
