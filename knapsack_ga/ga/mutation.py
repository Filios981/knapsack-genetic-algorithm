"""Mutacja — negacja genów."""

import random
from collections.abc import Callable

from knapsack_ga.models import Chromosome, MutationMethod, MutationTrace


def mutate_individual(
    chromosome: Chromosome, mutation_prob: float, rng: random.Random, trace: list[MutationTrace] | None = None
) -> Chromosome:
    """Mutacja na osobnika (jak na zajęciach): losowana jest liczba z [0, 1); gdy jest mniejsza od
    `mutation_prob`, negowany jest jeden gen w losowym miejscu (locus). Zwraca nowy chromosom.
    Z listą `trace` dopisuje do niej liczbę i miejsce mutacji (widok „Krok po kroku”).
    """
    mutated = list(chromosome)
    if not mutated:
        return mutated
    draw = rng.random()
    loci: tuple[int, ...] = ()
    if draw < mutation_prob:
        locus = rng.randrange(len(mutated))
        mutated[locus] = 1 - mutated[locus]
        loci = (locus,)
    if trace is not None:
        trace.append(MutationTrace(draw, loci))
    return mutated


def mutate_each_gene(
    chromosome: Chromosome, mutation_prob: float, rng: random.Random, trace: list[MutationTrace] | None = None
) -> Chromosome:
    """Mutacja na gen (opcja do porównania): każdy gen negowany niezależnie z prawdopodobieństwem p_m."""
    mutated = [1 - gene if rng.random() < mutation_prob else gene for gene in chromosome]
    if trace is not None:  # liczb losowych jest tyle, ile genów — zapisywane są tylko zanegowane miejsca
        flipped = tuple(index for index, gene in enumerate(mutated) if gene != chromosome[index])
        trace.append(MutationTrace(None, flipped))
    return mutated


MUTATIONS: dict[
    MutationMethod, Callable[[Chromosome, float, random.Random, list[MutationTrace] | None], Chromosome]
] = {
    MutationMethod.PER_INDIVIDUAL: mutate_individual,
    MutationMethod.PER_GENE: mutate_each_gene,
}
