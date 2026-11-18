# Paper notes (write in YOUR own words)

> The lab requires these notes "in your own words".
> - Use `study_guide.md` and `../ASSUMPTIONS.md` as references, but write the text yourself.
> - Short bullet points are fine.
> - Delete the prompts (the lines starting with ✏️) as you answer them.

**Paper:** Halder, Matus, Fettweis, "On the Concurrent Multipath Entanglement Distribution in Quantum Networks", IEEE GLOBECOM 2024, pp. 2791–2796.

## Network model
✏️ What are nodes, links, and memories (M)? What is q? How is a link's capacity C_ij made each window? What does swapping do, and what limits path length?

## Request model and blocking ratio
✏️ What is in the tuple ⟨s, d, n, a, h, b, f⟩? When can a request run (windows)? What is ρ, and why does the last chance get ρ=1? Write the BR formula.

## ILP formulation
✏️ List the variables in one line each. What is the objective? Summarise each constraint group in one line: routing (2a–2f), pair distribution (3a–3b), pair allocation (4a–4c).

## Heuristic steps
✏️ Algorithm 1 (the per-window loop), Algorithm 2 (the order requests are handled in), Algorithm 3 (the greedy path walk using α, the δ check, and splitting). Re-trace the Fig. 1 example by hand: which paths, and how many pairs on each?

## Evaluation setup
✏️ The topologies, |R|, M, T, t_c, q values, δ, F, f, the number of runs, the solver, and the metrics (Γ, BR, CT). What headline numbers did they report?

## Fidelity table (by hand)
✏️ With F=0.95, compute F_L for L = 1…6 links using F_L = (3w^L+1)/4 with w = (4F−1)/3. Where does it drop below 0.78?

| L (links) | intermediate nodes | F_L |
|---|---|---|
| 1 | 0 | |
| 2 | 1 | |
| 3 | 2 | |
| 4 | 3 | |
| 5 | 4 | |
| 6 | 5 | |

## Details the paper leaves out (my assumptions)
✏️ List what's missing and what you will choose. Cross-check against `../ASSUMPTIONS.md`.

## Things that looked wrong or inconsistent
✏️ Note anything that doesn't add up (hint: check α₃ in Fig. 1).
