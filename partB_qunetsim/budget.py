"""Per-window attempt budget of every link (A22): M attempts, each succeeds with probability q.
Dice come from one seeded RNG per (seed, window, link), so SP and MP see the same dice.
"""
import numpy as np


class Budget:
    """A22: per window each link has M attempts; every attempt succeeds with probability q."""

    def __init__(self, edges, M, q, seed):
        self.M, self.q, self.seed = M, q, seed
        self.link_index = {self.key(*e): i for i, e in enumerate(sorted(self.key(*e) for e in edges))}
        self.left, self.rngs, self.used = {}, {}, 0
        self.new_window(0)

    @staticmethod
    def key(a, b):
        """Links are undirected: (a, b) and (b, a) are the same link."""
        return tuple(sorted((a, b)))

    def new_window(self, window):
        """Refill every link to M attempts and reseed its RNG from (seed, window, link index)."""
        self.left = {k: self.M for k in self.link_index}
        self.rngs = {k: np.random.default_rng([self.seed, window, i]) for k, i in self.link_index.items()}

    def attempt(self, a, b):
        """One hop attempt. None if the link has no attempts left, else True (landed) or False."""
        k = self.key(a, b)
        if self.left[k] == 0:
            return None
        self.left[k] -= 1
        self.used += 1
        return bool(self.rngs[k].random() < self.q)

    def hop_lands(self, a, b):
        """Retry the hop while attempts remain. True if it landed within the budget."""
        while True:
            outcome = self.attempt(a, b)
            if outcome is None or outcome:
                return bool(outcome)


def dry_pair(budget, path):
    """The A22 logic for one pair with no simulator: hops in order, stop at the first hop that runs dry."""
    return all(budget.hop_lands(a, b) for a, b in zip(path, path[1:]))


def dry_request(budget, loads):
    """Dry run of one all-or-nothing request. loads = [(path, number_of_pairs), ...]. Stops at the first failed pair."""
    for path, m in loads:
        for _ in range(m):
            if not dry_pair(budget, path):
                return False
    return True
