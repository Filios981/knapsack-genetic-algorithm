"""Testy naprawy losowej i zachłannej."""

import random

from knapsack_ga.ga.fitness import is_feasible, total_weight
from knapsack_ga.ga.repair import greedy_removal_order, greedy_repair, make_repair, repair
from knapsack_ga.models import Item, KnapsackProblem, RepairMethod


def test_feasible_chromosome_is_not_changed(p02_problem):
    chromosome = [0, 1, 1, 1, 0]
    assert repair(chromosome, p02_problem, random.Random(1)) == chromosome


def test_overweight_chromosome_becomes_feasible_by_removing_items_only(p02_problem):
    for seed in range(200):
        repaired = repair([1, 1, 1, 1, 1], p02_problem, random.Random(seed))

        assert is_feasible(repaired, p02_problem)
        assert all(after <= before for before, after in zip([1, 1, 1, 1, 1], repaired, strict=True))


def test_repair_removes_only_as_many_items_as_needed(p02_problem):
    """Po naprawie dołożenie z powrotem ostatnio wyjętego przedmiotu znowu przekroczyłoby pojemność."""
    for seed in range(200):
        repaired = repair([1, 1, 1, 1, 1], p02_problem, random.Random(seed))
        removed = [index for index, gene in enumerate(repaired) if gene == 0]
        assert any(total_weight(repaired, p02_problem) + p02_problem.items[i].weight > 26 for i in removed)


def test_repair_is_random(p02_problem):
    results = {tuple(repair([1, 1, 1, 1, 1], p02_problem, random.Random(seed))) for seed in range(50)}
    assert len(results) > 1


def test_argument_is_not_modified(p02_problem):
    chromosome = [1, 1, 1, 1, 1]
    repair(chromosome, p02_problem, random.Random(1))
    assert chromosome == [1, 1, 1, 1, 1]


# --- Naprawa zachłanna ------------------------------------------------------------------------------

# Stosunki wartość/waga: 0.1, 2.0, 0.5, 0.5 — kolejność wyjmowania: 0, 2, 3 (remis 2/3 — mniejszy indeks), 1.
RATIO_PROBLEM = KnapsackProblem(items=(Item(1, 10, 1), Item(2, 10, 20), Item(3, 10, 5), Item(4, 10, 5)), capacity=20)


def test_removal_order_is_by_value_to_weight_ratio_then_index():
    assert greedy_removal_order(RATIO_PROBLEM) == [0, 2, 3, 1]


def test_greedy_repair_removes_least_valuable_per_kilogram_first():
    order = greedy_removal_order(RATIO_PROBLEM)
    assert greedy_repair([1, 1, 1, 1], RATIO_PROBLEM, order) == [0, 1, 0, 1]  # wyjęte 1 i 3, waga 20
    assert greedy_repair([1, 1, 1, 0], RATIO_PROBLEM, order) == [0, 1, 1, 0]  # wystarczy wyjąć przedmiot 1


def test_greedy_repair_keeps_feasible_chromosome_and_does_not_modify_argument(p02_problem):
    order = greedy_removal_order(p02_problem)
    feasible = [0, 1, 1, 1, 0]
    overweight = [1, 1, 1, 1, 1]

    assert greedy_repair(feasible, p02_problem, order) == feasible
    repaired = greedy_repair(overweight, p02_problem, order)
    assert is_feasible(repaired, p02_problem)
    assert overweight == [1, 1, 1, 1, 1]


def test_greedy_repair_of_all_too_heavy_items_gives_empty_knapsack():
    problem = KnapsackProblem(items=(Item(1, 10, 60), Item(2, 8, 15), Item(3, 6, 40)), capacity=5)
    assert greedy_repair([1, 1, 1], problem, greedy_removal_order(problem)) == [0, 0, 0]


def test_make_repair_selects_method(p02_problem):
    greedy = make_repair(p02_problem, RepairMethod.GREEDY, random.Random(1))
    assert greedy([1, 1, 1, 1, 1]) == greedy_repair([1, 1, 1, 1, 1], p02_problem, greedy_removal_order(p02_problem))

    rng_a, rng_b = random.Random(7), random.Random(7)
    assert make_repair(p02_problem, RepairMethod.RANDOM, rng_a)([1, 1, 1, 1, 1]) == repair(
        [1, 1, 1, 1, 1], p02_problem, rng_b
    )
