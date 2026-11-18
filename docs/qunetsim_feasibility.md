# QuNetSim feasibility probes (Week 1)

Everything below was checked against the **installed** library at
`D:\QuantumFinalProject\.venv\Lib\site-packages\qunetsim\` (written `site-packages/qunetsim/...`), using only
`.venv\Scripts\python.exe`. Nothing in `src/` or in the library was touched. Probe code is in `partB_qunetsim/probes/`.

How to rerun any probe (each runs in its own process with a hard timeout and kills hung process trees):

```
.venv\Scripts\python.exe partB_qunetsim\probes\run_probes.py p1        # or p2 ... p8, or no argument for all
.venv\Scripts\python.exe partB_qunetsim\probes\run_probes.py p7        # failure injection, about 4 min, writes results/partB_probe_p7_failure_injection.csv
.venv\Scripts\python.exe partB_qunetsim\probes\run_probes.py p8        # concurrency, about 6 min, writes results/partB_probe_p8_concurrency.csv
```

Two things every script needs (found the hard way, see "Gotchas"): an `if __name__ == "__main__":` guard, and
**one network per Python process**.

| probe | file | question | result file |
|---|---|---|---|
| P1 | `p1_chain.py` | does swap mode give a correlated end-to-end pair, with no leftover halves? | stdout |
| P2 | `p2_routing_hook.py` | is our routing function used? | stdout |
| P3 | `p3_loss.py` | do `packet_drop_rate` and `Fibre` model EPR loss? | stdout |
| P4 | `p4_metering.py` | can we count per-link `send_epr` calls? | stdout |
| P5 | `p5_memory_limit.py` | what happens at a memory limit? | stdout |
| P6 | `p6_runtime.py` | how long does a request take? | `results/partB_probe_runtime.csv` |
| P7 | `p7_failure_injection.py` | three ways to inject the A22 failure model | `results/partB_probe_p7_failure_injection.csv` |
| P8 | `p8_concurrency.py` | are simultaneous requests safe (issue #170)? | `results/partB_probe_p8_concurrency.csv` |

## Verdict per component (Part B)

Each line is based on the probe named in brackets. "Works" means observed in a probe, not assumed.

| component | verdict | basis |
|---|---|---|
| Single-path request | GO. Swap mode plus our routing function builds the pair hop by hop; both halves are correlated in Z and X; B keeps no leftover halves. | P1, P2, P4 |
| Multipath (several paths for one demand) | GO with sequential sub-requests. The library has no path splitting, so we issue one request per path. Two simultaneous requests, on different branches or sharing links, gave 40/40 correct pairs, but four simultaneous requests on one path failed intermittently and once stalled for minutes. Concurrency gave no speed-up (0.12 s versus 0.13 s per two requests), so sequential costs nothing measurable. | P2, P8 |
| Failure injection (A22) | GO with implementation (iii), manual hop-by-hop, for the final Part B experiments; (ii) pre-drawn outcomes is an acceptable fast fallback. Not (i): injecting inside swap mode throws daemon-thread tracebacks, waits about 19 s per failed request and leaves orphan halves. `packet_drop_rate` is only a secondary, handout-literal variant. | P3, P7 |
| Memory limits | Usable only as a counter check. Overflow halves are dropped silently and the sender still gets "ACK ok", so our own per-link budget (M) must enforce capacity. | P5 |
| Fidelity | Not exposed. Simulated pairs are ideal (perfect Z and X correlation in every probe). The Werner-model fidelity (A5) must be computed in our code. | P1, P3, P7 |
| Runtime | About 0.07 s per sequential request at delay 0 (P6), plus about 3 s once per process; concurrency does not change this (P8). | P6, P8 |

## The Part B failure model (A22)

Per window, each link has a budget of **M attempts** (its memories). Each hop attempt uses one attempt from that link's budget and succeeds with probability **q** (seeded RNG). A failed hop is retried while its link has attempts left. A pair is delivered over a path when every hop has succeeded. A request succeeds when all n pairs are delivered within the window. Routes are chosen BEFORE outcomes are known. That is what makes Part B different from Part A.

As a secondary, handout-literal variant, the simulator's own `packet_drop_rate` is also run (it drops classical packets and ACKs too, see Q2, so it is a sensitivity check only). The draw per attempt is made in our code, not in the library: Q2 shows the library has no per-link EPR success parameter.

## Q4. Which library version are we using?

**Summary.** `qunetsim 0.1.3.post1`, `eqsn 0.0.8`, Python 3.11.9, as pinned.

Evidence
- `.venv/Lib/site-packages/qunetsim-*/METADATA` says `Version: 0.1.3.post1`; `pip list` shows `EQSN 0.0.8`; `sys.version` is 3.11.9.
- `requirements.txt` / `requirements.lock.txt:23` pin `qunetsim==0.1.3.post1`.
- The installed release differs from GitHub master in important ways (see corrections below), so cite this installed source, not web pages.

Implications for Part B
- Cite `site-packages/qunetsim/...:line` in the report; line numbers in this file refer to this exact release.
- Do not upgrade the library mid-project; behaviours below are release-specific.

## Q1. How does QuNetSim pick the route for an entanglement request? Can we replace the rule?

**Summary.** The route comes from `Network.quantum_routing_algo`, default `nx.shortest_path`, and we **can** replace it with any
3-argument function. But the route is only *used* when `network.use_ent_swap = True`. With it off, the library creates the
end-to-end pair directly and ignores the route.

Evidence (source)
- Defaults: `site-packages/qunetsim/components/network.py:38` `_quantum_routing_algo = nx.shortest_path`; `:43` `_use_ent_swap = False`; `:45` `_delay = 0.1`; `:46` `_packet_drop_rate = 0`.
- Setter requires a callable with exactly 3 parameters (graph, source, dest): `site-packages/qunetsim/components/network.py:109-128` (check at `:121-125`).
- `get_quantum_route(source, dest)` calls `quantum_routing_algo(self.quantum_network, source, dest)`: `site-packages/qunetsim/components/network.py:336-346`.
- Request handling, `site-packages/qunetsim/components/network.py:_process_queue`: the *classical* route decides whether the pair is between neighbours (`:547` `len(route) == 2` creates the pair directly with `backend.create_EPR`, `:553`). Otherwise `:565` calls `get_quantum_route` (**always**, before the `if`), then `:567-575`:
  `use_ent_swap` -> `_entanglement_swap(...)` (`:362-427`), else `_establish_epr(...)` (`:429-449`), which makes the pair directly (`Qubit` + `H` + `cnot`, `:441-448`) and never looks at `route`.
- `_entanglement_swap` is a real hop-by-hop procedure: it calls `send_epr(next_hop, q_id, await_ack=True)` for every link on the route (`:379-380`) and then `send_teleport` from each middle host to the next (`:419`). The "swap" is done by teleporting a half along the chain.

Evidence (probes), `p2_routing_hook.py` (rerun: `run_probes.py p2`)
```
[PASS] swap ON: EPR was built hop by hop along exactly the route our function returned      (links S-b1, b1-b2, b2-D, one call each)
[PASS] swap OFF: routing fn was CALLED but its route was NOT used (no hop-by-hop EPR)         (routing-fn calls = 1, per-link calls = {})
[PASS] dispenser: request 1 used branch a, request 2 used branch b                            (a-branch links, then b-branch links)
```
`p1_chain.py` (rerun: `run_probes.py p1`): A-B-C chain, swap ON, 40 requests A->C:
```
[OBSERVED] missing halves: 0/40; Z-correlated 20/20; X-correlated 20/20
[PASS] end-to-end EPR A-C via swap: both halves present, perfectly correlated in Z and X
```
(X-basis agreement shows a real Bell pair, not just classical correlation. `p1_chain.py` now also asserts, via `Host.get_epr_pairs` (`site-packages/qunetsim/components/host.py:1199`), that no EPR half is left at A, B or C after the 40 requests; the rerun printed `{'A': [], 'B': [], 'C': []}` and PASS.)

Implications for Part B
- Single-path baselines: install our own routing function (`net.quantum_routing_algo = f`) and use `use_ent_swap=True`. Our function sees only `(graph, source, dest)`, so for per-request paths use a closure/dispenser (works for sequential requests, P2).
- The hypothesis "the hook is only called when swap is on" is **false**: it is called in both modes; it is only *used* when swap is on. Never trust a log line that says "route chosen" without checking links used (P4).
- For multipath (one request split over several paths) the library offers no splitting. We must issue one request per path ourselves. `_entanglement_swap` reuses an already-stored pair on a link instead of creating a new one (`site-packages/qunetsim/components/network.py:379-383`, `shares_epr` at `:283`), which is a hazard for simultaneous requests that share a link. Tested in P8 (below): two simultaneous requests were fine, four were not.
- Fallback ("manual hop-by-hop") if the hook is not enough: our code calls, per link, `Host.send_epr(neighbor, q_id, await_ack=True)` (`site-packages/qunetsim/components/host.py:844`), `Host.get_epr(partner, q_id, wait=...)` (`site-packages/qunetsim/components/host.py:1470`), and does the swap itself on the middle host with `Qubit.cnot` (`site-packages/qunetsim/objects/qubit.py:221`), `Qubit.H` (`:188`), `Qubit.measure` (`:319`), `Qubit.X`/`Qubit.Z` (`:158`, `:170`), sending the two bits with `Host.send_classical` (`site-packages/qunetsim/components/host.py:810`); or reuse the library's own teleport hop `Host.send_teleport` (`site-packages/qunetsim/components/host.py:1058`). This fallback was built and run in P7 (iii) (below); the API names are cited by file:line there.

## Q2. Can we set link loss, noise, or memory limits? Which parameters?

**Summary.** Loss is available only as one **network-wide** packet drop rate that hits classical packets and ACKs as well, so it
cannot model a per-link EPR success probability. A per-link `Fibre` model exists but only acts on data qubits sent with
`send_qubit`, not on EPR creation. EPR memory can be capped per host (and per partner), but extra halves are silently discarded. There is no gate-noise or decoherence setting for EPR pairs. Our paper-model losses/capacities should be applied in our own code.

Evidence (source)
- `Network.packet_drop_rate` property + setter, range 0-1: `site-packages/qunetsim/components/network.py:154-175`. `Network.delay` property + setter: `:131-151`. The delay is a `time.sleep` per packet in the single network queue thread: `site-packages/qunetsim/components/network.py:515-517`.
- The drop check is in `_process_queue`: `site-packages/qunetsim/components/network.py:520-526`: `random.random() > (1 - packet_drop_rate)` -> log, release the qubit if the payload is quantum, `continue`. It runs for **every** packet taken from the queue (EPR requests, classical messages, ACKs, teleport messages), before any routing. No per-link, per-type or per-payload condition.
- Per-connection channel model: `QuantumConnection(sender_id, receiver_id, model=None)`, default `Fibre()`: `objects/connections/quantum_connection.py:10-14`. `Fibre(length=0.0, alpha=0.0)`: `channel_models/fibre.py:4-22` (alpha must be in [0,1]); `transmission_p = 10 ** (-alpha*length/10)`: `site-packages/qunetsim/objects/connections/channel_models/fibre.py:82`; `qubit_func` drops the qubit with probability `1 - transmission_p`: `site-packages/qunetsim/objects/connections/channel_models/fibre.py:84-97`. Other model: `BinaryErasure(probability)` (`channel_models/binary_erasure.py`). Classical links have `ClassicalConnection(..., model=None)` with `ClassicalModel` (`site-packages/qunetsim/objects/connections/classical_connection.py:9-13`).
- `Host.add_q_connection/add_connection` take **no `model=`** (`site-packages/qunetsim/components/host.py:584-611`); the only way to attach a model is to build the connection yourself: `host.quantum_connections[other] = QuantumConnection(host_id, other, model=Fibre(...))` (property at `site-packages/qunetsim/components/host.py:229`; used in `_common.py`).
- The model is consulted in exactly one place: `site-packages/qunetsim/components/network.py:466` (`...model.qubit_func(q)` inside `_route_quantum_info`, `:451`), which runs only for packets whose payload is a qubit (`send_qubit`). EPR creation uses `backend.create_EPR` (`:553`, `:441-448`) and never calls `qubit_func`.
- Memory: `Host.set_epr_memory_limit(limit, host_id=None)` `site-packages/qunetsim/components/host.py:1285-1297`; property `Host.storage_epr_limit` `site-packages/qunetsim/components/host.py:181-203`. Storage default mode is per-partner (`site-packages/qunetsim/objects/storage/quantum_storage.py:23`, setter `:64-80`, per-host `:100-119`). When the limit is hit, `add_qubit_from_host` releases the new qubit and returns with no error (`site-packages/qunetsim/objects/storage/quantum_storage.py:225-227`). There is no overwrite/evict mode (grep for overwrite/evict/replace: no hits). `Host.storage_limit = n` is broken: it *calls* an int (`site-packages/qunetsim/components/host.py:226`).
- `Host.delay` (`site-packages/qunetsim/components/host.py:46,126-149`) is stored but never read anywhere: setting it does nothing. `Network.set_delay = x` does not exist as an attribute (`hasattr(Network, "set_delay")` is `False`); assigning it just creates an unused attribute, delay stays 0.1 (verified by running).

Evidence (probes)
`p3_loss.py` (rerun: `run_probes.py p3`, ~3 min), chain A-B-C, swap ON, 30 attempts per rate:
```
[PASS] drop_rate=0:   end-to-end EPR success 30/30, Z-correlated 30/30
[OBSERVED] drop_rate=0.2: 9/30 = 0.30 (an earlier run gave 13/30); arrived pairs Z-correlated 9/9
[OBSERVED] drop_rate=0.5: 2/30 = 0.07 (an earlier run gave 0/30); arrived pairs Z-correlated 2/2
[PASS] drop_rate=0.5: classical neighbour messages delivered 44/100  -> classical packets ARE dropped too
[PASS] Fibre p~0.7 on A-B: end-to-end EPR success 30/30  -> Fibre does NOT affect EPR creation (swap mode)
[PASS] Fibre p~0.7 on A-B: data qubits delivered 22/30 (expect ~21)  -> Fibre DOES drop send_qubit qubits
```
- Loss does not damage EPR halves that arrive (all still perfectly correlated); it makes the whole request fail, because an EPR packet, its per-hop ACKs and teleport messages each can be dropped. The success rate falls much faster than `1 - rate` (many packets per request). A failed request leaves partial halves behind and throws tracebacks in library daemon threads (the failure path itself has a bug: `site-packages/qunetsim/components/network.py:402` prints `host.EPR_store`, which does not exist).
- An earlier run gave 29/30 at rate 0; cause: the first request in a process takes ~3 s (EQSN start-up), longer than our wait. The probe now does one warm-up request first.

`p5_memory_limit.py` (rerun: `run_probes.py p5`): host B limit 1, A sends B three pairs:
```
[none]        stored at B=3, at A=3
[global]      set_epr_memory_limit(1):          ACKs=[True,True,True]; stored at B=1, at A=3; no exception
[per_partner] set_epr_memory_limit(1, "A"):     stored at B=1, at A=3
[property]    B.storage_epr_limit = 1:          stored at B=1, at A=3
Host.storage_limit = 1 raised TypeError: 'int' object is not callable  (site-packages/qunetsim/components/host.py:226)
```
So the sender is still told "ACK ok", B silently keeps 1, the other 2 are released, and A is left with 3 half-orphans. No overwrite mode.

Implications for Part B
- Do **not** use `packet_drop_rate` to represent link success probability q_ij: it is global and also kills ACKs/classical messages, which makes requests hang or fail for the wrong reason.
- Apply the A22 failure model (budget of M attempts per link per window, success probability q per attempt) in our own code. P7 compares three ways to do it; the recommendation is in the P7 section. Capacity per link is the same budget M.
- Per-link `Fibre` is only useful if we send qubits with `send_qubit`; not for EPR distribution in the swap mode.
- If we use memory limits, remember overflow is silent: check `get_epr_pairs` counts ourselves. Set limits before the first pair arrives.
- Always set `host.max_ack_wait` (`site-packages/qunetsim/components/host.py:152-175`) to a finite value when using loss; the default `None` makes `await_ack` wait forever (`site-packages/qunetsim/components/host.py:746`).

## Q3. How long does one run take, and how does it grow with the number of requests?

**Summary.** With `network.delay = 0`, one single-path request on a 6- or 9-node network costs about 0.06-0.07 s, plus ~0.3 s fixed;
it is about 0.07 s per sequential request (P6), and total time grew roughly linearly over r = 1 to 16 requests (3 repeats each). With the default delay (0.1 s) it is about 10-15 times slower. A fresh process pays ~3.3 s once (EQSN start-up).

Evidence, `p6_runtime.py` (rerun: `run_probes.py p6`, ~6 min). Data: `results/partB_probe_runtime.csv`, figure: `figures/F0_qunetsim_runtime.png`. Mean seconds over 3 repeats (sequential requests, swap ON, delay=0, one untimed warm-up request first):

| r (requests) | 1 | 2 | 4 | 8 | 16 |
|---|---|---|---|---|---|
| two-branch, 6 nodes (S->D, 3 hops) | 0.16 | 0.49 | 0.60 | 0.87 | 1.21 |
| 3x3 grid, 9 nodes (corner to corner, 4 hops) | 0.29 | 0.42 | 0.52 | 0.98 | 1.33 |

```
two_branch_6: seconds ~ 0.28 + 0.06 * r        grid_3x3: seconds ~ 0.28 + 0.07 * r
first (warm-up) request incl. process start: mean 3.32 s (excluded)
default delay 0.1 s, r=4:  two_branch_6 5.92 s (vs 0.60 at delay 0);  grid_3x3 8.02 s (vs 0.52)
```
Source of the delay cost: one `time.sleep(delay)` per packet in the single network thread, `site-packages/qunetsim/components/network.py:515-517`; every hop of every request is several packets.

Implications for Part B
- Always set `network.delay = 0`. Repeats are noisy (e.g. r=2: 0.40-0.60 s), so use several seeds and report ranges.
- Budget: ~0.07 s per request at 3-4 hops. A few hundred requests per run is fine (tens of seconds); thousands of requests x many seeds x methods is not. Plan Part B experiments with a small number of requests per run (the paper figures need only the toy/small cases) and run seeds in parallel processes.
- Run each experiment in a fresh process (one network per process) and pay the ~3 s start-up once per process, not per request.
- P6 timed sequential requests only. Concurrent requests are covered by P8: two simultaneous requests took 0.12 s versus 0.13 s sequential, so concurrency gives no speed-up.

## P7. Injecting the A22 failure model into QuNetSim

Setup (`p7_failure_injection.py`, rerun: `run_probes.py p7`, about 4 min): chain A-B-C and the 6-node two-branch network (branches used in turn), M = 4 attempts per link per window, q = 0.6, one pair per window, 30 windows, seed 7. One seeded RNG per link (`numpy.random.default_rng([7, link_index])`), so the draws do not depend on thread timing. Data: `results/partB_probe_p7_failure_injection.csv`. The model predicts a delivery rate of `(1 - 0.4^4)^hops`: 0.95 for the chain (2 hops) and 0.93 for the two-branch network (3 hops). A 20 000-window run of the same `Budget` class gave 0.948 and 0.925, so the draws are unbiased and the 25/30 in the two-branch rows is sample noise.

| implementation | topology | windows | delivered | seconds per delivered pair | daemon tracebacks | orphan halves left | lines of code |
|---|---|---|---|---|---|---|---|
| (i) inject inside swap mode | chain, M=4 | 30 | 29 | 0.71 | yes | 0 | 48 |
| (i) | chain, M=1 (stress) | 8 | 3 | 31.8 | yes | 2 | 48 |
| (i) | two-branch, M=4 | 28 (stopped by the 90 s limit) | 23 | 4.1 | yes | 5 | 48 |
| (ii) pre-drawn, library end-to-end `send_epr` | chain | 30 | 29 | 0.048 | none | 0 | 31 |
| (ii) | two-branch | 30 | 25 | 0.057 | none | 0 | 31 |
| (iii) manual hop-by-hop swaps | chain | 30 | 29 | 0.063 | none | 0 | 61 |
| (iii) | two-branch | 30 | 25 | 0.105 | none | 0 | 61 |

Every delivered pair in every row was correlated. Alternate pairs were measured in Z and the others in X: for example 15/15 Z and 14/14 X on the chain.

Lines of code are the non-blank, non-comment lines of the functions each implementation needs, counted by the probe.

The tracebacks column records whether any daemon-thread traceback appeared on standard error during the run. Counts were not saved, so none are given.

**Caveat.** Each row is one seed (7) and at most 30 windows. Implementations (ii) and (iii) share the same per-link draws, so their delivered counts are equal by construction. Comparing them tells us about cost, and about how much of the work the simulator really performs. It does not compare delivery rates. The delivery rates themselves match the model's prediction, which was checked with a 20 000-window run (see above).

**(i) Inject inside swap mode.** A `Host` subclass overrides `send_epr` (`site-packages/qunetsim/components/host.py:844`). For neighbour calls it draws against the link budget and, when the budget is used up, returns without creating a pair. Pairs that are delivered are fine. A failed hop breaks the library:
- The swap waits for the missing half with `host.get_epr(route[0], q_id, wait=10)` (`site-packages/qunetsim/components/network.py:396`), prints four diagnostic lines and then crashes in its own error path: `AttributeError: ... no attribute 'EPR_store'` at `site-packages/qunetsim/components/network.py:402`, in a daemon thread. If the first hop worked but a later one did not, the teleport step fails instead: `AssertionError` at `site-packages/qunetsim/components/protocols.py:218` (after a wait of 10 s, `site-packages/qunetsim/utils/constants.py:15`).
- The requester's `send_epr(await_ack=True)` never gets its ACK. With the default `max_ack_wait=None` it would wait forever (`site-packages/qunetsim/components/host.py:746`); we set 15 s. The longest window was 19.0 s.
- Orphan halves are left in storage (2 after the M=1 run, 5 after the two-branch run, counted with `get_epr_pairs`).
- No run hung. But each failed request costs about 19 s, so 30 windows at a 5 percent failure rate cost 20 s, and the stress run cost 95 s.

**(ii) Pre-drawn outcomes.** Our code draws every hop attempt of the path first (`window_delivered`). Only when all hops landed within budget do we call the library's `send_epr` from source to destination, with swap mode on and a routing function that returns the chosen path. No tracebacks, no orphans, 0.05 to 0.06 s per delivered pair. The simulator sees only requests we already decided to deliver, and the hop attempts that failed are not simulated at all. This is the "delivery animator" concern: the library confirms a pair whose success our code had already drawn.

**(iii) Manual hop-by-hop.** Per hop, `make_hop_pair` does a real `send_epr` between neighbours and fetches both halves with `get_epr` (`site-packages/qunetsim/components/host.py:1470`). A failed attempt consumes budget, and the two halves are released with `Qubit.release` (`site-packages/qunetsim/objects/qubit.py:146`). When every hop holds a pair, each middle host runs a Bell-state measurement on its two halves with `Qubit.cnot` (`objects/qubit.py:221`), `Qubit.H` (`:188`) and `Qubit.measure` (`:319`). It sends the two bits to the end node with `Host.send_classical` (`site-packages/qunetsim/components/host.py:810`, `await_ack=True`). The end node reads them with `Host.get_next_classical` (`site-packages/qunetsim/components/host.py:1457`; it returns a `Message`, bits in `.content`) and applies `Qubit.X` (`objects/qubit.py:158`) and `Qubit.Z` (`:170`) according to the XOR of the bits. The corrections matter: the X-basis check passed on all 14 (chain) and 12 (two-branch) pairs only because they are applied. No in-process shortcut was used; the bits travel as simulator messages. No tracebacks, no orphans, 0.06 to 0.11 s per delivered pair.

How much of the quantum work the simulator performs:
- (i): everything, but it fails on the first injected failure.
- (ii): pair creation and its internal swaps for delivered requests only; our code decides success.
- (iii): creation of every attempted pair (failed ones included), every gate and measurement of the swaps, and the classical messages. Our code decides which attempts fail and the order of steps. One difference: the library's own swap teleports a half along the route (`site-packages/qunetsim/components/network.py:419`), while (iii) does the textbook Bell measurement with Pauli correction. Both give a correlated pair. (iii) does not use the library's routing hook, because it walks the path we hand it.

**Recommendation: (iii)** for the Part B experiments. It is the only option that is correct under failures, has no daemon-thread tracebacks or orphans, and runs real pair creation, gates, measurements and classical messages in the simulator. It costs about 60 lines and is 1.3 to 1.8 times slower than (ii) per delivered pair (0.063 versus 0.048 s on the chain, 0.105 versus 0.057 s on the two-branch network). (ii) is a valid fast fallback for large sweeps if we state that the simulator only confirms delivery. Do not use (i).

## P8. Concurrent requests (GitHub issue #170)

Issue #170 (`tqsd/QuNetSim`, open, no comments), in two lines: with more than one qubit in flight per link, or with several senders, the reporter's receiver gets almost no qubits (about 97 to 99 percent lost for `send_qubit`). EPR and teleport requests also fail intermittently with `ValueError: Qid doesent match id!` (`site-packages/qunetsim/backends/eqsn_backend.py:229`), while single streams are stable.

A possible cause for EPR requests is in the backend: halves are queued per host pair in a plain FIFO (`site-packages/qunetsim/backends/eqsn_backend.py:199-207` stores, `:210-229` pops and compares the id), not looked up by `q_id`, so two simultaneous requests on one link could pop each other's half. We did not prove this mechanism; we only observed the failures below.

Setup (`p8_concurrency.py`, rerun: `run_probes.py p8`, about 6 min): two-branch network, swap on, `max_ack_wait` 10 s, threads each calling `send_epr(await_ack=True)` from S, 20 trials per scenario (c stops at 120 s), each pair measured in Z or X. The probe records whether the request intervals overlapped. Data: `results/partB_probe_p8_concurrency.csv`.

| scenario | requests | requests correct | trials with all correct | intervals overlapped | seconds per trial |
|---|---|---|---|---|---|
| a_seq: one request per branch, one after another (baseline) | 40 | 40 | 20/20 | 0/20 | 0.13 |
| a_conc: one request per branch, simultaneous | 40 | 40 | 20/20 | 20/20 | 0.12 |
| b_same_path: two requests over the same 3 links | 40 | 40 | 20/20 | 20/20 | 0.14 |
| b_partial: S to D on branch a and S to a2 (2 shared links) | 40 | 40 | 20/20 | 20/20 | 0.10 |
| c_same_path4: four requests over the same 3 links | 28 | 27 | 6/7 | 7/7 | 36.7 |

In a and b there was no "Qid doesent match" error and no traceback. In c, one request got no ACK and the library printed the `site-packages/qunetsim/components/network.py:402` traceback; one trial took about 4 minutes, which dominates the 36.7 s average. Earlier exploratory runs of c showed the same kind of missing ACKs, and one run stalled until it was killed. They were not saved, so they are reported here as observations only, not as data. So four simultaneous requests are not reliable. With 0 failures in 20 trials, the exact 95 percent upper bound on the per-trial failure rate of the two-request cases is about 14 percent, so "fine" means "no failure seen in 20 trials", not "proved safe".

Conclusion: issue the sub-requests of a multipath demand **sequentially**. Concurrency gave no speed-up (0.12 s versus 0.13 s for two requests; one network thread handles all packets) and adds the risk above. Cost of sequential sub-requests: about 0.07 s each (P6), so a demand split over k paths costs about 0.07 k s, for example about 0.2 s for k = 3. P7 (iii) already works one pair at a time.

## Parameters we can use

| name | scope | verified by |
|---|---|---|
| `Network.quantum_routing_algo = f(graph, src, dst)` | global (one function; use a closure for per-request paths) | `site-packages/qunetsim/components/network.py:109-128`; P2 |
| `Network.use_ent_swap` (must be `True` for the route to matter) | global | `site-packages/qunetsim/components/network.py:53-58`, `:565-575`; P2 |
| `Network.packet_drop_rate` (0-1) | global, hits all packets incl. ACKs | `site-packages/qunetsim/components/network.py:154-175`, `:520-526`; P3 |
| `Network.delay` (seconds per packet) | global | `site-packages/qunetsim/components/network.py:131-151`, `:515-517`; P6 |
| `Host.max_ack_wait` (seconds; default = wait forever) | per host | `site-packages/qunetsim/components/host.py:152-175`; P3 |
| `QuantumConnection(a, b, model=Fibre(length, alpha))` | per link, **data qubits only** | `site-packages/qunetsim/objects/connections/quantum_connection.py:10-14`, `site-packages/qunetsim/objects/connections/channel_models/fibre.py:82`, `site-packages/qunetsim/components/network.py:466`; P3 |
| `Host.set_epr_memory_limit(limit, host_id=None)` / `Host.storage_epr_limit` | per host; per partner by default | `site-packages/qunetsim/components/host.py:1285`, `:181`; `site-packages/qunetsim/objects/storage/quantum_storage.py:23,64-80,225-227`; P5 |
| `Host.send_epr(receiver, q_id, await_ack, no_ack, block)` / `get_epr(host, q_id, wait)` | per host | `site-packages/qunetsim/components/host.py:844`, `:1470`; P1 |
| `Host` subclass overriding `send_epr` for metering | per host (no library edit) | `_common.py:MeteredHost`; P4 |
| `Host.delay`, `Network.set_delay` | no effect | `site-packages/qunetsim/components/host.py:46,126-149` (never read); runtime check |
| `Host.storage_limit = n` | broken (TypeError) | `site-packages/qunetsim/components/host.py:226`; P5 |

P4 (metering, rerun: `run_probes.py p4`): a `Host` subclass records `(sender, receiver)` on every `send_epr` call, then calls the parent:
```
[chain]             A->C swap ON : per-link EPR attempts {'A-B': 1, 'B-C': 1}; end-to-end call [('A','C')]; teleports [('B','C')]   PASS
[two_branch]        S->D swap ON : {'S-a1': 1, 'a1-a2': 1, 'D-a2': 1} (default shortest path chose the a-branch)               PASS
[two_branch_noswap] S->D swap OFF: no link used at all (pair created directly)                                                 PASS
```
(`D-a2` is the link a2-D; keys are sorted pairs.) Link usage can therefore be metered with swap ON, without editing the library; with swap OFF it cannot, because no link is ever used.

## Corrections to the claims from the earlier web-research pass

1. **Wrong:** "the routing hook is called/used only when `use_ent_swap` is True". It is **called in both modes** (`site-packages/qunetsim/components/network.py:565` runs before the `if` at `:567`) but only **used** when True. With False the route is computed and thrown away (P2).
2. **Refinement:** for neighbours, the pair is created directly before any quantum route is computed (`site-packages/qunetsim/components/network.py:547-553`); the swap/direct choice is only reached for non-adjacent hosts, decided by the *classical* route length.
3. **Refinement:** `Fibre`/`QuantumConnection(model=)` exist as claimed, but `Host.add_*connection` cannot pass `model=`, and the model is not applied to EPR creation, so it does **not** change EPR success in swap mode (P3: 30/30).
4. **Refinement:** `packet_drop_rate` affects classical packets and ACKs too, not only EPR halves (`site-packages/qunetsim/components/network.py:520-526`, P3: 44/100 delivered at 0.5).
5. **Extra:** `Host.delay` is a no-op; `Host.storage_limit` setter is broken; `Network.reset_network()` breaks the library (below).
6. Confirmed unchanged: defaults at `site-packages/qunetsim/components/network.py:38,43,45,46`; 3-parameter setter check; `get_quantum_route`; `delay` and `packet_drop_rate` are properties with setters; `network.set_delay = x` is a silent no-op; `Fibre(length, alpha)` and its formula; `send_epr`, `get_epr`, `set_epr_memory_limit` signatures (also read with `inspect.signature`).
7. **Now tested (P8):** GitHub issue #170 (concurrent in-flight sends are buggy). Two simultaneous swap-mode EPR requests were correct in 20/20 trials in every layout we tried; four simultaneous requests on one path failed intermittently. See the P8 section.

## Gotchas found (important for Part B code)

- EQSN starts child processes (`site-packages/eqsn/gates.py:30-31`): on Windows every script needs `if __name__ == "__main__":`, else it re-runs itself and hangs.
- Never call `Network.reset_network()` (`site-packages/qunetsim/components/network.py:26-32`): `site-packages/qunetsim/components/protocols.py:7` binds the first `Network` instance forever, so after a reset every request hangs (we saw this). Use one network per process; for repeats, start a new process (as `p6` does).
- The first request in a process takes ~3 s (EQSN workers). Warm up before timing.
- Library errors in daemon threads print tracebacks, and `site-packages/qunetsim/components/network.py:399-402` prints stray lines to stdout on a failed swap. `run_probes.py` hides stderr tracebacks and counts them.
- Our scripts `network.stop(True)` in a `finally`, use `get_epr(..., wait=5)` or shorter, and are run under a hard timeout.

## Go/No-Go recommendation for Part B

Replaced by the per-component table at the top ("Verdict per component"). Summary of the conditions:

- **Single path:** swap mode plus a routing closure; verify each request's links with the metering subclass (P4) in tests.
- **Multipath:** one request per path, sent one after another (P8). Cost: about 0.07 s per sub-request (P6), so k paths cost about 0.07 k s per demand.
- **Failure injection:** P7 (iii), manual hop-by-hop, so the simulator performs the swaps. Draws come from our seeded RNG (A22).
- **Memory limits:** drop extra halves silently; enforce capacity with our own per-link budget M.
- **Fidelity:** not exposed by QuNetSim; compute the Werner-model fidelity (A5) in our code.
- **Speed:** about 0.07 s per request, about 3 s process start-up. Keep per-run request counts small; parallelise across processes, not within one.
- **Robustness:** infinite `await_ack` by default and a global singleton. Always set `max_ack_wait`, call `network.stop(True)` in `finally`, use hard timeouts, one network per process.
