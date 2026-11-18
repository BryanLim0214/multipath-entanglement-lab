# Scope note (one page): Multipath Entanglement Distribution

**Student:** Panhapiseth Lim (lim_p65274@utpb.edu), University of Texas of the Permian Basin  **Advisor:** ____________  **Date:** 2026-11-__  **Status:** DRAFT, awaiting advisor approval

**Goal.** Reproduce the core comparison in Halder, Matus & Fettweis (GLOBECOM 2024): multipath routing vs single-path routing, and ILP vs heuristic, measured by blocking ratio. Then check the qualitative claim in QuNetSim, and test one small extension.

## Topologies
- **Part A (Python model):** the paper's 3×3 grid (|R|=60, M=6, T=100, t_c=10, δ=2, F=0.95, f=0.78).
- **Part B (QuNetSim):**
  - a 6-node two-branch network (two disjoint S→D paths);
  - the 3×3 grid.
  - The 3-node chain A–B–C is a sanity check only.
- *Optional:* the paper's 5×5 grid, heuristics only.

## Metrics
1. **Blocking ratio** (Part A) / **success rate** (Part B): mean ± 95% CI. Part A uses 30 paired seeds; Part B uses ≥20 runs.
2. **Γ**: the share of placed requests that used more than one path (Table I).
3. **Time**: solver/heuristic compute time (Part A) and request completion time (Part B).

## Methods
- Single-path:
  - **SP-SPF**: plain shortest path (the lab's baseline).
  - **SP-Heu** and **SP-ILP**: our definitions, since the paper omits them.
- Multipath: **MP-Heu** and **MP-ILP**.
- Solver: PuLP with HiGHS, with CBC as a cross-check.
- Sweeps:
  - BR vs q ∈ {0.5,…,0.9}, which is the paper's axis.
  - BR vs load |R| ∈ {20,…,100} at q=0.7, which is the lab's axis.

## Extension: "keep a spare seat, unless it's your last chance" (deadline-aware δ)
- The paper's heuristic only lets a request use half of a path's capacity (δ=2). Its ILP has no such rule.
- We test a one-line change: use δ=1 *only* when the request is in its last eligible window (ρ=1).
- It is compared with δ=2 (the paper), δ=1 always, MP-ILP, and SP-Heu, on the same seeds.
- This is the handout's "heuristic variants" option, tested in Part A.

## Hypothesis (fixed before any run)
On the paper's small setup at q=0.5, deadline-aware δ lowers MP-Heu's blocking ratio by **≥3 percentage points**.

**Decision rule:**
- Supported if the paired mean difference is ≥3 pp **and** the lower bound of its 95% CI is >0.
- We also report what share of the gap between the heuristic and the ILP is closed.
- A negative result will be reported.

## Key assumptions
The full list is in `ASSUMPTIONS.md`, entries A1–A21.
- **Demand size n.** The paper never gives the demand size, so we calibrate n on **Γ only**. Blocking ratio stays a held-out check.
- **Fidelity limit.** It follows Werner swapping, which matches the paper's limits of 4 and 10 intermediate nodes.
- **Single-path baselines.** These are our own definitions.

## Cut list (in order, if behind)
1. QuantumLab Code Lab, then the other QuantumLab rooms (a teaching companion, not graded).
2. The 5×5 large-scale runs.
3. Part B grid: replace it with a smaller 2×3 ladder, keeping ≥2 informative topologies.
4. Last resort, and only with your approval: drop Part B. This is the handout's own fallback.

**Never cut:** 30 seeds and CIs, the hand-solved toy check, the extension plot, or the honest limitations.

## Questions for the advisor
1. Do you approve the topologies, metrics, extension and hypothesis above?
2. May AI tools read the paper PDF? (Handout rule on pasting paper text.)
3. Should the interactive QuantumLab companion be counted, or treated as non-graded?
4. Part B go/no-go: QuNetSim feasibility results are in `docs/qunetsim_feasibility.md`.

**Approved by:** ____________  **Date:** ____________
