# Part B setup: link loss and every parameter value

This page records how link failure is configured in QuNetSim and the exact values each experiment uses. All values are in `partB_qunetsim/run_partB.py` (constants at the top, `tasks_main` and `tasks_drops`). The reasons for the design are in `ASSUMPTIONS.md` A22 and `docs/qunetsim_feasibility.md`.

## Simulator settings (all experiments)

| Setting | Value | Where |
|---|---|---|
| QuNetSim version | 0.1.3.post1, Python 3.11, EQSN backend | `requirements.txt` |
| Entanglement swapping | hop by hop in our code: `send_epr` per link, Bell measurement at each middle node, 2 classical bits, Pauli correction at the end | `partB_qunetsim/delivery.py` |
| `network.delay` | 0 s (the default 0.1 s sleep per packet is removed) | `topologies.py`, `network.py:138` |
| `host.max_ack_wait` | 10 s (the default waits forever) | `topologies.py`, `host.py:162` |
| Requests | served one after another (concurrent sends mix up qubits, QuNetSim issue 170) | `run_partB.py` |
| Seeds | 1 to 20 for every setting, the same for single path and multipath | `SEEDS` |

## Two loss mechanisms

**1. Attempt budget (E1 to E3, the main experiments).** QuNetSim's per-link `Fibre` loss does not touch EPR pairs in swap mode, and its global drop rate also discards classical messages (probe P3). So each link gets its own **attempt budget**: per window, M attempts, each landing with probability q (A22). A failed attempt is retried while attempts remain. The budget is shared by every request and path that uses the link. The dice come from one seeded RNG per (seed, window, link), so single path and multipath see the same luck.

**2. Simulator packet drop (E4, the handout-literal variant).** QuNetSim's own `packet_drop_rate` (`network.py:154-175`), set before each run and reset to 0 after. It drops any packet with that probability: EPR halves, acknowledgements and classical correction bits alike (`network.py:520-526`). Here q = 1 and M = 100, so the attempt budget never binds and the drop rate is the only cause of failure. The library draws these drops from Python's global `random`, which we seed with the run's seed.

## Values per experiment

| Experiment | Topology | Methods | q | M | n per request | drop rate | Windows x requests per window | Wait |
|---|---|---|---|---|---|---|---|---|
| E1 sanity | chain A-B-C | SP | q = 0.6, 1.0 | 4 | 1 | 0 | 10 x 1 | 10 s |
| E2 | two-branch S-a1-a2-D, S-b1-b2-D | SP (k = 1), MP (k = 2) | q = 0.5, 0.6, 0.7, 0.8, 0.9 | 4 | 2 and 4 | 0 | 10 x 1 | 10 s |
| E3 | 3x3 grid | SP, MP (k = 2), MP (k = 3, sensitivity) | q = 0.5, 0.6, 0.7, 0.8, 0.9 | 6 | uniform {1, 2, 3} | 0 | 10 x 4 | 10 s |
| E4 loss sweep | two-branch | SP, MP (k = 2) | q = 1 | 100 | 2 | 0, 0.1, 0.2, 0.3 | 10 x 1 | 2 s |
| E4 loss sweep | 3x3 grid | SP, MP (k = 2) | q = 1 | 100 | uniform {1, 2, 3} | 0, 0.1, 0.2, 0.3 | 5 x 2 | 2 s |

On the grid, each request has a random source and destination; both are drawn from (seed, window) only, so the two methods get the same requests. A request succeeds only if all n pairs arrive; an expired wait counts as a failure and is logged in `results/partB_timeouts.csv`.

## What is not configured

- **Noise and fidelity.** QuNetSim's EPR pairs are ideal, and it exposes no fidelity, so none is set. Each delivered pair is instead checked for correlation in the Z or X basis.
- **Memory limits.** `set_epr_memory_limit` drops overflow halves silently while still reporting success (probe P5), so capacity is enforced by the attempt budget, not by the library.

Results: `results/partB_summary.md`. Figure: `figures/F3_partB_success.png`.
