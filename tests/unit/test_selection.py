"""Testy koła ruletki."""

import random
from collections import Counter

import pytest

from knapsack_ga.ga.selection import cumulative_sums, roulette_wheel_selection, spin_wheel


def test_cumulative_sums_are_slice_boundaries():
    """Przykład: przystosowania 51, 40, 39, 37."""
    assert cumulative_sums([51, 40, 39, 37]) == [51, 91, 130, 167]


def test_spin_lands_in_the_slice_containing_r():
    """r = 103.54 leży w wycinku [91, 130) — wybrany osobnik C (indeks 2)."""

    class FixedRandom(random.Random):
        def random(self):
            return 0.62

    spin = spin_wheel([51, 91, 130, 167], FixedRandom())
    assert spin.index == 2
    assert spin.r == pytest.approx(103.54)


def test_individuals_with_zero_fitness_are_never_selected():
    spins = roulette_wheel_selection([0, 0, 5, 0], 1000, random.Random(1))
    assert {spin.index for spin in spins} == {2}


def test_all_fitness_zero_gives_uniform_selection():
    spins = roulette_wheel_selection([0, 0, 0, 0], 40_000, random.Random(1))
    counts = Counter(spin.index for spin in spins)

    assert set(counts) == {0, 1, 2, 3}
    assert all(abs(count / 40_000 - 0.25) < 0.01 for count in counts.values())


def test_selection_frequencies_are_proportional_to_fitness():
    spins = roulette_wheel_selection([10, 30, 60], 100_000, random.Random(1))
    counts = Counter(spin.index for spin in spins)

    assert counts[0] / 100_000 == pytest.approx(0.1, abs=0.01)
    assert counts[1] / 100_000 == pytest.approx(0.3, abs=0.01)
    assert counts[2] / 100_000 == pytest.approx(0.6, abs=0.01)


def test_rounding_error_at_the_end_of_the_wheel_is_capped():
    class AlmostOne(random.Random):
        def random(self):
            return 1.0  # nie występuje w random.random(), ale symuluje r == S_N po zaokrągleniu

    assert spin_wheel([1, 2, 3], AlmostOne()).index == 2


def test_selection_returns_requested_number_of_spins():
    assert len(roulette_wheel_selection([1, 2, 3], 7, random.Random(1))) == 7
