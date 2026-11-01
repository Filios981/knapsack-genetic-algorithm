"""Testy wagi, wartości i dopuszczalności."""

from knapsack_ga.ga.fitness import fitness, is_feasible, total_value, total_weight
from knapsack_ga.models import Item, KnapsackProblem


def test_weight_and_value_of_optimal_chromosome(p02_problem):
    chromosome = [0, 1, 1, 1, 0]  # przedmioty 2, 3, 4 — optimum p02-5-items.csv

    assert total_weight(chromosome, p02_problem) == 26
    assert total_value(chromosome, p02_problem) == 51
    assert fitness(chromosome, p02_problem) == 51


def test_empty_knapsack(p02_problem):
    assert total_weight([0] * 5, p02_problem) == 0
    assert fitness([0] * 5, p02_problem) == 0


def test_feasibility_on_the_boundary(p02_problem):
    assert is_feasible([0, 1, 1, 1, 0], p02_problem)  # waga 26 = W
    assert not is_feasible([1, 1, 0, 1, 0], p02_problem)  # waga 27 = W + 1


def test_feasibility_with_floating_point_weights():
    """0.1 + 0.2 = 0.30000000000000004 — mimo to plecak o pojemności 0.3 jest dopuszczalny (tolerancja)."""
    problem = KnapsackProblem(items=(Item(1, 0.1, 1), Item(2, 0.2, 1)), capacity=0.3)
    assert is_feasible([1, 1], problem)
