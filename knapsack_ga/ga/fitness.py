"""Waga, wartość, dopuszczalność i przystosowanie osobnika."""

from knapsack_ga.models import Chromosome, KnapsackProblem

# Sumy wag niecałkowitych mogą mieć błąd zaokrąglenia (0.1 + 0.2 != 0.3).
WEIGHT_TOLERANCE = 1e-9


def total_weight(chromosome: Chromosome, problem: KnapsackProblem) -> float:
    """Suma wag przedmiotów, których gen jest równy 1."""
    return sum(item.weight for gene, item in zip(chromosome, problem.items, strict=True) if gene == 1)


def total_value(chromosome: Chromosome, problem: KnapsackProblem) -> float:
    """Suma wartości przedmiotów, których gen jest równy 1."""
    return sum(item.value for gene, item in zip(chromosome, problem.items, strict=True) if gene == 1)


def fits(weight: float, capacity: float) -> bool:
    """Czy dana waga mieści się w plecaku (z tolerancją WEIGHT_TOLERANCE)."""
    return weight <= capacity + WEIGHT_TOLERANCE


def is_feasible(chromosome: Chromosome, problem: KnapsackProblem) -> bool:
    """True, gdy łączna waga nie przekracza pojemności — osobnik dopuszczalny."""
    return fits(total_weight(chromosome, problem), problem.capacity)


def fitness(chromosome: Chromosome, problem: KnapsackProblem) -> float:
    """Przystosowanie = łączna wartość; po naprawie każdy osobnik w populacji jest dopuszczalny, więc bez kar."""
    return total_value(chromosome, problem)
