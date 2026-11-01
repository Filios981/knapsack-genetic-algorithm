"""Testy krzyżowania jednopunktowego."""

import random

from knapsack_ga.ga.crossover import crossover_population, one_point_crossover


def test_children_swap_tails_after_the_same_cut_point():
    for seed in range(100):
        child_a, child_b = one_point_crossover([0] * 6, [1] * 6, random.Random(seed))
        cut = child_a.index(1)

        assert 1 <= cut <= 5
        assert child_a == [0] * cut + [1] * (6 - cut)
        assert child_b == [1] * cut + [0] * (6 - cut)


def test_example_from_documentation():
    """Przykład: k = 2, 01|110 i 10|001 -> 01|001 i 10|110."""

    class CutAtTwo(random.Random):
        def randint(self, a, b):
            return 2

    assert one_point_crossover([0, 1, 1, 1, 0], [1, 0, 0, 0, 1], CutAtTwo()) == ([0, 1, 0, 0, 1], [1, 0, 1, 1, 0])


def test_all_cut_points_are_used():
    cuts = {one_point_crossover([0] * 6, [1] * 6, random.Random(seed))[0].index(1) for seed in range(200)}
    assert cuts == {1, 2, 3, 4, 5}


def test_single_gene_chromosomes_are_copied():
    assert one_point_crossover([0], [1], random.Random(1)) == ([0], [1])


def test_probability_zero_copies_and_one_always_crosses():
    parents = [[0] * 8, [1] * 8] * 50
    copied = crossover_population(parents, 0.0, random.Random(1))
    crossed = crossover_population(parents, 1.0, random.Random(1))

    assert copied == parents
    assert all(child not in ([0] * 8, [1] * 8) for child in crossed)


def test_crossover_rate_is_close_to_probability():
    parents = [[0] * 8, [1] * 8] * 5000
    offspring = crossover_population(parents, 0.8, random.Random(1))
    crossed_pairs = sum(1 for child in offspring[::2] if child != [0] * 8)
    assert abs(crossed_pairs / 5000 - 0.8) < 0.02


def test_odd_number_of_parents_keeps_population_size():
    parents = [[0, 0, 0], [1, 1, 1], [0, 1, 0]]
    offspring = crossover_population(parents, 1.0, random.Random(1))

    assert len(offspring) == 3
    assert offspring[2] == [0, 1, 0]


def test_offspring_are_new_lists():
    """Ten sam rodzic wybrany dwa razy (losowanie ze zwracaniem) — potomkowie nie mogą być tym samym obiektem."""
    parent = [1, 0, 1]
    offspring = crossover_population([parent, parent], 0.0, random.Random(1))

    assert all(child is not parent for child in offspring)
    assert offspring[0] is not offspring[1]
