"""Krzyżowanie jednopunktowe."""

import random

from knapsack_ga.models import Chromosome, PairTrace


def one_point_crossover(
    parent_a: Chromosome, parent_b: Chromosome, rng: random.Random
) -> tuple[Chromosome, Chromosome]:
    """Wymiana końcówek za losowym punktem cięcia k z [1, n - 1]; dla n == 1 zwraca kopie rodziców.

    Przykład (k = 2): 01|110 i 10|001 -> 01|001 i 10|110.
    """
    cut = _cut_point(len(parent_a), rng)
    if cut is None:
        return list(parent_a), list(parent_b)
    return cross_at(parent_a, parent_b, cut)


def _cut_point(length: int, rng: random.Random) -> int | None:
    """Losowy punkt cięcia z [1, n - 1]; None dla n < 2 (nie ma czego wymieniać — bez losowania)."""
    return rng.randint(1, length - 1) if length >= 2 else None


def cross_at(parent_a: Chromosome, parent_b: Chromosome, cut: int) -> tuple[Chromosome, Chromosome]:
    """Potomkowie: geny 1…cut od jednego rodzica, reszta od drugiego."""
    return parent_a[:cut] + parent_b[cut:], parent_b[:cut] + parent_a[cut:]


def crossover_population(
    parents: list[Chromosome], crossover_prob: float, rng: random.Random, trace: list[PairTrace] | None = None
) -> list[Chromosome]:
    """Łączy kolejnych rodziców w pary (1-2, 3-4, ...) i krzyżuje każdą parę z prawdopodobieństwem `crossover_prob`.

    Pary nieskrzyżowane są kopiowane. Przy nieparzystej liczbie rodziców ostatni jest kopiowany.
    Zawsze zwraca nowe listy, nigdy obiekty rodziców. Z listą `trace` dopisuje do niej liczbę i punkt
    krzyżowania każdej pary (widok „Krok po kroku”) — bez zmiany kolejności losowań.
    """
    offspring: list[Chromosome] = []
    for index in range(0, len(parents) - 1, 2):
        parent_a, parent_b = parents[index], parents[index + 1]
        draw = rng.random()
        cut = _cut_point(len(parent_a), rng) if draw < crossover_prob else None
        if cut is not None:
            child_a, child_b = cross_at(parent_a, parent_b, cut)
        else:
            child_a, child_b = list(parent_a), list(parent_b)
        if trace is not None:
            trace.append(PairTrace(draw, cut))
        offspring.extend([child_a, child_b])
    if len(parents) % 2 == 1:
        offspring.append(list(parents[-1]))
    return offspring
