"""Rozwiązanie dokładne (programowanie dynamiczne) — wyłącznie do weryfikacji algorytmu genetycznego."""

import math
from dataclasses import dataclass

from knapsack_ga.ga.fitness import WEIGHT_TOLERANCE, total_weight
from knapsack_ga.models import KnapsackProblem

# Największa liczba komórek n * (W + 1), dla której liczymy optimum (ok. 20 MB pamięci, kilka sekund).
MAX_CELLS = 20_000_000


@dataclass(frozen=True)
class ExactSolution:
    total_value: float
    total_weight: float
    chromosome: tuple[int, ...]


def has_integer_weights(problem: KnapsackProblem) -> bool:
    """Programowanie dynamiczne po pojemnościach wymaga całkowitych wag (ułamkowa pojemność jest zaokrąglana w dół)."""
    return all(float(item.weight).is_integer() for item in problem.items)


def can_solve_exact(problem: KnapsackProblem) -> bool:
    """Czy optimum da się policzyć: wagi całkowite i rozmiar tablicy n * (W + 1) nie większy niż MAX_CELLS."""
    capacity = math.floor(problem.capacity + WEIGHT_TOLERANCE)
    return has_integer_weights(problem) and capacity >= 0 and problem.size * (capacity + 1) <= MAX_CELLS


def solve_exact(problem: KnapsackProblem) -> ExactSolution:
    """Rozwiązanie optymalne w czasie O(n * W); dla wag niecałkowitych lub zbyt dużego problemu zgłasza ValueError.

    best[c] — największa wartość przedmiotów rozpatrzonych dotąd przy pojemności c;
    taken[i][c] — czy przedmiot i należy do tego najlepszego wyboru (do odtworzenia rozwiązania).
    """
    if not can_solve_exact(problem):
        raise ValueError("Optimum liczone jest tylko dla całkowitych wag i niezbyt dużej pojemności plecaka.")
    capacity = math.floor(problem.capacity + WEIGHT_TOLERANCE)
    best = [0.0] * (capacity + 1)
    taken: list[bytearray] = []
    for item in problem.items:
        weight = int(item.weight)
        take = bytearray(capacity + 1)
        for c in range(capacity, weight - 1, -1):  # malejąco — każdy przedmiot użyty najwyżej raz
            with_item = best[c - weight] + item.value
            if with_item > best[c]:
                best[c] = with_item
                take[c] = 1
        taken.append(take)

    chromosome = [0] * problem.size
    c = capacity
    for index in range(problem.size - 1, -1, -1):  # odtworzenie wyboru od ostatniego przedmiotu
        if taken[index][c]:
            chromosome[index] = 1
            c -= int(problem.items[index].weight)
    return ExactSolution(best[capacity], total_weight(chromosome, problem), tuple(chromosome))
