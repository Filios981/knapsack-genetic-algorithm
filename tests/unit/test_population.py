"""Testy populacji początkowej."""

import random

from knapsack_ga.ga.fitness import is_feasible
from knapsack_ga.ga.population import initial_population, random_chromosome
from knapsack_ga.ga.repair import make_repair
from knapsack_ga.models import Item, KnapsackProblem, RepairMethod


def test_random_chromosome_has_binary_genes_of_given_length():
    chromosome = random_chromosome(1000, random.Random(1))

    assert len(chromosome) == 1000
    assert set(chromosome) == {0, 1}
    assert 400 < sum(chromosome) < 600  # około połowy genów równych 1


def test_initial_population_is_feasible(p02_problem):
    population = initial_population(p02_problem, 100, random.Random(1))

    assert len(population) == 100
    assert all(len(chromosome) == 5 for chromosome in population)
    assert all(is_feasible(chromosome, p02_problem) for chromosome in population)


def test_all_items_too_heavy_gives_empty_knapsacks():
    problem = KnapsackProblem(items=(Item(1, 10, 60), Item(2, 8, 15), Item(3, 6, 40)), capacity=5)
    population = initial_population(problem, 20, random.Random(1))
    assert all(chromosome == [0, 0, 0] for chromosome in population)


def test_initial_population_with_greedy_repair_is_feasible(p02_problem):
    rng = random.Random(1)
    population = initial_population(p02_problem, 100, rng, make_repair(p02_problem, RepairMethod.GREEDY, rng))
    assert all(is_feasible(chromosome, p02_problem) for chromosome in population)
