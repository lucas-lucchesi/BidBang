import random

import pytest

from app.ai import limits
from app.game import Game


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def make_game(clock):
    def _make(n=3, **settings):
        players = [(f"p{i}", f"Joueur{i}") for i in range(1, n + 1)]
        return Game(players, settings, rng=random.Random(1), clock=clock)
    return _make


@pytest.fixture(autouse=True)
def _fresh_limits():
    """Les limites (créations de salons, échecs) sont par adresse et globales : on les remet à zéro
    avant chaque test pour qu'ils ne s'influencent pas."""
    limits.reset()
    yield
    limits.reset()
