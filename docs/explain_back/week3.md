# Week 3 explain-back: Part B in QuNetSim, and the extension runs

These are the questions an advisor is most likely to ask about Part B and the extension. Each answer gives a short plain explanation and the place in the code to point at. Read the answer, open the function, and say it back in your own words.

## Why Part B looks the way it does

**1. Why not just call QuNetSim's built-in entanglement swap?**
- Probe P3 showed that QuNetSim's per-link loss settings never touch EPR pairs, so a link could not fail.
- Probe P7 showed that injecting a failure inside QuNetSim's own swap crashes it.
- So we build each end-to-end pair ourselves, hop by hop (`delivery.deliver_pair`). Every step except the failure dice is a real QuNetSim call. The failure dice come from our attempt budget (A22).
- `run_partB.crosscheck` still runs QuNetSim's own swap once, with no loss, over our routes, to show both ways give correlated pairs.

**2. What happens on one hop?**
- `delivery.make_hop_pair` asks the link's budget for attempts. Each attempt really creates a pair with `send_epr`, and both ends fetch their halves.
- The budget decides whether an attempt "landed". A failed attempt throws its pair away, and the next attempt costs one more of the link's M.

**3. How does a middle node join two pairs?**
- `delivery.bell_measure` does a CNOT, a Hadamard and two measurements on the two qubits the node holds.
- `delivery.swap_and_correct` sends the 2 classical bits to the destination. The destination applies X and Z corrections.
- `delivery.check_correlation` then measures both ends in Z or X. A real Bell pair gives equal outcomes in both bases, and the `correlated` column counts these.

**4. What is the attempt budget?**
- `budget.Budget` gives every link M attempts per window, and each attempt lands with chance q (A22).
- All requests and paths that use a link share its attempts. Multipath gets no free extra attempts, only more of the network.
- When a window starts, every link refills to M (`new_window`).

**5. How do single path and multipath see the "same dice"?**
- Each link draws from its own random stream, seeded by (seed, window, link) in `Budget.new_window`.
- SP and MP with the same seed therefore face the same luck on every link.
- `run_one` also replays each request in a dry run without the simulator (`budget.dry_request`). If the simulator and the dry run disagree, that counts as a "dice mismatch". The log reports this count, and it must be 0.

**6. Where do the routes come from?**
- SP: `routing.sp_route` asks QuNetSim's own router (`get_quantum_route`, which calls `nx.shortest_path`).
- MP: `routing.k_disjoint_paths` finds up to k paths that share no link, shortest first, each with at most 4 middle nodes.
- `routing.split_pairs` spreads the n pairs evenly, so 3 pairs over 2 paths become 2 + 1.

**7. Why are requests served one after another, not at the same time?**
- QuNetSim issue #170: concurrent sends between the same hosts mix up their qubits.
- Probe P8 ran 4 requests at once. It failed sometimes and was no faster.
- So the order is fixed: requests one at a time, pairs one at a time (A22).

## The experiments

**8. What do E1 to E4 test?**
- **E1, chain A-B-C:** a sanity check. At q = 1 every request must succeed.
- **E2, two-branch network:** SP against MP (k = 2) over q from 0.5 to 0.9, with n = 2 and n = 4. `analytic.p_sp` and `analytic.p_mp` give exact success probabilities to compare against.
- **E3, 3×3 grid:** SP against MP over the same q values, with n drawn from 1 to 3. A k = 3 row checks whether a third path adds anything.
- **E4:** q = 1 with a budget that never binds. Failures come only from QuNetSim's own `packet_drop_rate`, from 0 to 0.3.

**9. Why does the analytic check matter?**
- On the two-branch network the paths share no link, so success has a closed form: each link needs at least m landings in M tries, a binomial tail (`analytic.p_at_least`).
- If the simulated success rate sits inside its CI around this number, the wiring is right: budget, routes, all-or-nothing rule.

**10. Why at least 20 runs, and what is the CI?**
- 20 seeds per setting (`SEEDS`), as the handout requires.
- `qmp.stats.mean_ci` gives the mean and a 95% Student-t half-width across seeds.

**11. What does Part B not measure?**
- Fidelity: QuNetSim models no noise or decoherence for these pairs.
- Real timing: completion time is simulator wall-clock time, useful only to compare methods with each other.
- That is why the report calls Part B a qualitative check.

## The extension (Part C)

**12. What exactly changed in the heuristic?**
- `heuristic.delta_for` returns 1 for a request on its last chance (ρ = 1) under the `deadline` policy, and 2 otherwise.
- Nothing else changes. Same paths, same order, same dice.

**13. How was the verdict decided?**
- The rule was written in `docs/scope_note.md` before any run: at q = 0.5 the paired mean difference must be at least 0.03, and its 95% CI must stay above 0.
- `experiments/analysis.verdict_table` computes it, and `results/partC_verdict.md` prints it.

**14. If the hypothesis is supported, why is the conclusion cautious?**
- δ = 1 for every request lowers blocking even more than the deadline rule, at every q.
- So what helps is dropping the spare-seat rule, not knowing about deadlines. The report says this plainly.
