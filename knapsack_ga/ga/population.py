"""Populacja początkowa."""

import random
from collections.abc import Callable

from knapsack_ga.ga.repair import repair
from knapsack_ga.models import Chromosome, KnapsackProblem


def random_chromosome(length: int, rng: random.Random) -> Chromosome:
    """Każdy gen równy 1 z prawdopodobieństwem 0.5, w przeciwnym razie 0."""
    return [rng.randint(0, 1) for _ in range(length)]


def initial_population(
    problem: KnapsackProblem,
    size: int,
    rng: random.Random,
    repair_chromosome: Callable[[Chromosome], Chromosome] | None = None,
) -> list[Chromosome]:
    """Utworzenie `size` losowych chromosomów i naprawa niedopuszczalnych (pierwsze sprawdzenie ograniczenia).

    `repair_chromosome` — funkcja naprawy (`repair.make_repair`; `run_ga` przekazuje ją według
    `GAParams.repair_method`); bez podania — naprawa losowa.
    """
    if repair_chromosome is None:
        return [repair(random_chromosome(problem.size, rng), problem, rng) for _ in range(size)]
    return [repair_chromosome(random_chromosome(problem.size, rng)) for _ in range(size)]
