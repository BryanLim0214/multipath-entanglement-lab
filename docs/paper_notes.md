# Paper notes (written in my own words)

> The lab requires these notes "in your own words".
> - Use `study_guide.md` and `../ASSUMPTIONS.md` as references, but write the text yourself.
> - Short bullet points are fine.
> - Replace each `TODO(you):` prompt with your answer. The tracker stays red until none are left.

**Paper:** Halder, Matus, Fettweis, "On the Concurrent Multipath Entanglement Distribution in Quantum Networks", IEEE GLOBECOM 2024, pp. 2791 to 2796.

## Network model
TODO(you): Answer these:
- What are nodes, links, and memories (M)?
- What is q?
- How is a link's capacity C_ij produced in each window?
- What does swapping do, and what limits the length of a path?

## Request model
TODO(you): Answer these:
- What is in the tuple ⟨s, d, n, a, h, b, f⟩?
- When can a request run (which windows)?
- What is ρ, and why does a request's last chance get ρ = 1?

Then write the blocking-ratio formula.

## ILP formulation
TODO(you):
- List the variables, one line each.
- What is the objective?
- Summarise each constraint group in one line:
  - routing (2a to 2f);
  - pair distribution (3a, 3b);
  - pair allocation (4a to 4c).

## Heuristic steps
TODO(you): Describe each algorithm:
- Algorithm 1: the per-window loop.
- Algorithm 2: the order in which requests are handled.
- Algorithm 3: the greedy path walk using α, the δ check, and splitting.

Then re-trace the Fig. 1 example by hand: which paths are chosen, and how many pairs go on each?

## Evaluation setup
TODO(you): List the settings and results:
- Settings: topologies, |R|, M, T, t_c, q values, δ, F, f, number of runs, and solver.
- Metrics: Γ, BR, CT.
- The headline numbers they report.

## Fidelity table (by hand)
TODO(you): Use F = 0.95 and w = (4F − 1)/3. For L = 1 to 6 links, compute F_L = (3w^L + 1)/4. Where does F_L drop below 0.78?

| L (links) | intermediate nodes | F_L |
|---|---|---|
| 1 | 0 | |
| 2 | 1 | |
| 3 | 2 | |
| 4 | 3 | |
| 5 | 4 | |
| 6 | 5 | |

## Details the paper leaves out (my assumptions)
TODO(you): List what is missing and what you will choose for each. Cross-check your list against `../ASSUMPTIONS.md`.

## Things that looked wrong or inconsistent
TODO(you): Note anything that doesn't add up. Hint: check α₃ in Fig. 1.
