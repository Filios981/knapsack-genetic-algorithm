"""Testy mutacji."""

import random

import pytest

from knapsack_ga.ga.mutation import MUTATIONS, mutate_each_gene, mutate_individual
from knapsack_ga.models import MutationMethod

# --- Mutacja na gen (opcja) -----------------------------------------------------------------------


def test_probability_zero_changes_nothing_and_one_flips_everything():
    chromosome = [0, 1, 1, 0, 1]

    assert mutate_each_gene(chromosome, 0.0, random.Random(1)) == chromosome
    assert mutate_each_gene(chromosome, 1.0, random.Random(1)) == [1, 0, 0, 1, 0]


def test_each_gene_is_flipped_with_given_probability():
    mutated = mutate_each_gene([0] * 10_000, 0.2, random.Random(1))
    assert abs(sum(mutated) / 10_000 - 0.2) < 0.02


# --- Mutacja na osobnika (jak na zajęciach) -------------------------------------------------------


def test_individual_mutation_flips_exactly_one_gene_or_none():
    chromosome = [0, 1, 1, 0, 1]

    assert mutate_individual(chromosome, 0.0, random.Random(1)) == chromosome
    for seed in range(50):
        mutated = mutate_individual(chromosome, 1.0, random.Random(seed))
        assert sum(a != b for a, b in zip(chromosome, mutated, strict=True)) == 1


def test_individual_mutation_frequency_and_locus_are_uniform():
    rng = random.Random(7)
    changed_positions = []
    trials = 20_000
    for _ in range(trials):
        mutated = mutate_individual([0] * 5, 0.2, rng)
        changed_positions += [index for index, gene in enumerate(mutated) if gene]
    assert abs(len(changed_positions) / trials - 0.2) < 0.01  # około 20% potomków zmutowanych
    for locus in range(5):  # każde miejsce mutacji podobnie często (ok. 1/5)
        assert abs(changed_positions.count(locus) / len(changed_positions) - 0.2) < 0.02


def test_individual_mutation_uses_the_lecture_scheme():
    """Jak w notatce z zajęć: liczba < p_m → mutacja w miejscu l; liczba ≥ p_m → bez zmian."""

    class Scripted:
        def __init__(self, number: float, locus: int) -> None:
            self.number, self.locus = number, locus

        def random(self) -> float:
            return self.number

        def randrange(self, _stop: int) -> int:
            return self.locus

    assert mutate_individual([1, 0, 1, 1, 0], 0.2, Scripted(0.15, 1)) == [1, 1, 1, 1, 0]  # TAK, l = 2
    assert mutate_individual([1, 0, 1, 1, 0], 0.2, Scripted(0.56, 1)) == [1, 0, 1, 1, 0]  # NIE


@pytest.mark.parametrize("mutate", [mutate_individual, mutate_each_gene])
def test_argument_is_not_modified(mutate):
    chromosome = [0, 1, 1]
    mutate(chromosome, 1.0, random.Random(1))
    assert chromosome == [0, 1, 1]


def test_every_method_has_an_operator():
    assert set(MUTATIONS) == set(MutationMethod)
