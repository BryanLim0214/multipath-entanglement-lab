"""Turns a player's choose_paths(net, request) into a real qmp placer and scores it against the paper's methods.

The same file runs in the browser (Pyodide, inside a Web Worker) and in CPython for the tests, so the page
can never score a rule differently from the engine. Every answer goes through qmp.core.validate first.
"""
from __future__ import annotations

import contextlib
import io
import json
import time
import traceback
from dataclasses import dataclass, field
from functools import partial

from qmp import heuristic
from qmp.core import Allocation, PlaceResult, Request, WindowInput, validate
from qmp.sim import SimConfig, simulate
from qmp.stats import paired_diff_ci

SPARE = 2  # the baselines keep a spare seat (A21). It is their strategy, so the referee below does not enforce it
SMALL = {"rows": 3, "cols": 3, "R": 60, "M": 6, "T": 100, "tc": 10, "F": 0.95, "f": 0.78}
MAX_MESSAGES = 12
MAX_PRINT_CHARS = 2000

BASELINES = {
    "lazy": partial(heuristic.place_spf, delta=SPARE),  # the Lazy Walker rule, as in Part A
    "sp_heu": partial(heuristic.place_heuristic, multipath=False, delta=SPARE),
    "mp_heu": partial(heuristic.place_heuristic, multipath=True, delta=SPARE),
}
BASELINE_NAMES = {"lazy": "Lazy Walker (SP-SPF)", "sp_heu": "SP-Heu", "mp_heu": "MP-Heu"}


class PlayerCrash(Exception):
    """The player's code raised an error, or has a syntax error. The message is plain English."""


@dataclass
class RunLog:
    """What happened to the player's answers during a run."""
    illegal: int = 0
    declined: int = 0
    served: int = 0
    messages: list = field(default_factory=list)
    seed: int = 0

    def reject(self, window: int, request_id: int, problems: list[str]) -> None:
        """Count an illegal answer and keep the first few messages."""
        self.illegal += 1
        for text in problems:
            if len(self.messages) < MAX_MESSAGES and text not in [m["text"] for m in self.messages]:
                self.messages.append({"seed": self.seed, "window": window, "text": text})


class Net:
    """What the player sees: the network with the seats left in this window, at this request's turn."""

    def __init__(self, caps, max_middle: int, nodes: list[int]):
        self._caps = caps
        self.max_middle = max_middle
        self.spare = SPARE  # what the paper's methods keep per pair. Information only: the referee does not require it
        self.nodes = list(nodes)

    def neighbors(self, u: int) -> list[int]:
        """Cities next to u over a link that still has at least one free seat, in increasing order."""
        return sorted(self._caps.get(u, {}))

    def pairs(self, u: int, v: int) -> int:
        """Free seats on the link between u and v (0 if there is no link or no seat)."""
        return self._caps.get(u, {}).get(v, 0)


class PlayerRequest:
    """What the player sees of a request."""

    def __init__(self, src: int, dst: int, n: int, last_chance: bool):
        self.src, self.dst, self.n, self.last_chance = src, dst, n, last_chance


def normalise(answer) -> tuple[list[tuple[list[int], int]], list[str]]:
    """Check the shape of the answer: a list of (path, pairs). Returns the roads and any shape problems."""
    if not isinstance(answer, (list, tuple)):
        return [], ["choose_paths must return a list of (path, pairs) tuples, or [] to decline."]
    roads = []
    for k, item in enumerate(answer, 1):
        try:
            path, pairs = item
            roads.append(([int(c) for c in path], int(pairs)))
        except (TypeError, ValueError):
            return [], [f"Answer item {k} must look like ([city, city, ...], pairs), with whole numbers."]
    return roads, []


def check_answer(win: WindowInput, caps, req: Request, roads) -> list[str]:
    """Every rule the answer breaks, in plain words: qmp.core.validate on the seats left at this request's turn.

    That is physics and capacity only (endpoints, links, shared links, middle cities, all-or-nothing, seats).
    Keeping a spare seat is a strategy, not a law, so it is not checked.
    """
    left = {e: caps.get(e[0], {}).get(e[1], 0) for e in win.capacity}
    one = WindowInput(win.graph, left, [req], {req.id: 1.0}, {req.id: win.max_mid[req.id]}, 0)
    return validate(one, [Allocation(req.id, roads)])


def ask_player(choose_paths, net: Net, view: PlayerRequest):
    """Call the player's function; turn any error into a PlayerCrash with the line number in the player's code."""
    try:
        return choose_paths(net, view)
    except Exception as error:  # the player's code can fail in any way
        lines = [f.lineno for f in traceback.extract_tb(error.__traceback__) if f.filename == "<your code>"]
        where = f"line {lines[-1]}: " if lines else ""
        raise PlayerCrash(f"Your code stopped with an error at {where}{type(error).__name__}: {error}") from None


def make_placer(choose_paths, log: RunLog, window_counter: list):
    """A qmp placer: requests in the engine's own order, seats taken only when the player's answer is legal."""
    def placer(win: WindowInput) -> PlaceResult:
        start = time.perf_counter()
        window_counter[0] += 1
        caps = heuristic.build_caps(win)
        net = Net(caps, next(iter(win.max_mid.values()), 0), sorted(win.graph.nodes))
        allocations = []
        for req in heuristic.request_order(win):
            last = win.rho[req.id] == 1.0
            roads, problems = normalise(ask_player(choose_paths, net, PlayerRequest(req.s, req.d, req.n, last)))
            if not problems and not roads:
                log.declined += 1
                continue
            problems = problems or check_answer(win, caps, req, roads)
            if problems:
                log.reject(window_counter[0], req.id, problems)
                continue
            for path, pairs in roads:
                heuristic.use_seats(caps, path, pairs)
            allocations.append(Allocation(req.id, roads))
            log.served += 1
        return PlaceResult(allocations, "heuristic", time.perf_counter() - start)
    return placer


def load_player_function(source: str):
    """Compile the player's source and return its choose_paths. Syntax errors become a plain message."""
    namespace = {"__name__": "player"}
    try:
        exec(compile(source, "<your code>", "exec"), namespace)
    except SyntaxError as error:
        raise PlayerCrash(f"Python cannot read your code: {error.msg} on line {error.lineno}.") from None
    except Exception as error:
        raise PlayerCrash(f"Your code stopped while loading: {type(error).__name__}: {error}") from None
    if not callable(namespace.get("choose_paths")):
        raise PlayerCrash("Your code must define a function named choose_paths(net, request).")
    return namespace["choose_paths"]


def config_for(q: float, seed: int, n_spec: str) -> SimConfig:
    """The Part A small-setup config for one q and seed."""
    return SimConfig(SMALL["rows"], SMALL["cols"], SMALL["R"], SMALL["M"], SMALL["T"], SMALL["tc"], q,
                     SMALL["F"], SMALL["f"], n_spec, seed)


def player_blocking(source: str, q: float, seed: int, n_spec: str) -> tuple[float, RunLog]:
    """Blocking ratio of the player's rule for one seed, and the log of its answers."""
    log = RunLog(seed=seed)
    placer = make_placer(load_player_function(source), log, [0])
    return simulate(config_for(q, seed, n_spec), placer).blocking_ratio, log


def run_challenge(source: str, baseline: str, q: float, seeds: list[int], n_spec: str,
                  zero_illegal: bool = False) -> dict:
    """Score the player's rule against a baseline on paired seeds. Returns a plain dict (JSON-friendly)."""
    total = RunLog()
    mine, theirs = [], []
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        function = load_player_function(source)
        for seed in seeds:
            total.seed = seed
            placer = make_placer(function, total, [0])
            cfg = config_for(q, seed, n_spec)
            mine.append(simulate(cfg, placer).blocking_ratio)
            theirs.append(simulate(cfg, BASELINES[baseline]).blocking_ratio)
    mean, ci = paired_diff_ci(mine, theirs)
    won = mean + ci < 0 and (total.illegal == 0 or not zero_illegal)
    return {"baseline": BASELINE_NAMES[baseline], "q": q, "seeds": list(seeds), "player": mine, "baseline_values": theirs,
            "mean_diff": mean, "ci": ci, "won": bool(won), "illegal": total.illegal, "declined": total.declined,
            "served": total.served, "messages": total.messages, "printed": buffer.getvalue()[:MAX_PRINT_CHARS]}


def run_challenge_json(source: str, baseline: str, q: float, seeds_json: str, n_spec: str, zero_illegal: bool) -> str:
    """Entry point for the worker: always returns JSON, with an error field when the player's code fails."""
    try:
        result = run_challenge(source, baseline, q, json.loads(seeds_json), n_spec, zero_illegal)
    except PlayerCrash as error:
        result = {"error": str(error)}
    return json.dumps(result)
