"""Główna pętla podstawowego algorytmu genetycznego."""

import random
import time
from collections.abc import Callable

from knapsack_ga.ga.crossover import crossover_population
from knapsack_ga.ga.fitness import fitness, total_weight
from knapsack_ga.ga.mutation import MUTATIONS
from knapsack_ga.ga.population import initial_population
from knapsack_ga.ga.repair import make_repair
from knapsack_ga.ga.selection import roulette_wheel_selection
from knapsack_ga.ga.stopping import StopCondition
from knapsack_ga.models import (
    Chromosome,
    GAParams,
    GAResult,
    GenerationStats,
    KnapsackProblem,
    MutationTrace,
    PairTrace,
    SelectionTrace,
    StepTrace,
    StopReason,
)


def _generation_stats(generation: int, fitnesses: list[float], best_so_far: float) -> GenerationStats:
    return GenerationStats(
        generation=generation,
        best=max(fitnesses),
        mean=sum(fitnesses) / len(fitnesses),
        worst=min(fitnesses),
        best_so_far=best_so_far,
    )


# Geny 0/1 -> znaki „0”/„1” (bytes.translate jest ok. 10 razy szybsze niż "".join(map(str, …))).
_GENE_CHARS = bytes.maketrans(b"\x00\x01", b"01")


def _bits(chromosome: Chromosome) -> str:
    """Chromosom jako napis „10110” — zapis w StepTrace."""
    return bytes(chromosome).translate(_GENE_CHARS).decode("ascii")


def _best_index(fitnesses: list[float]) -> int:
    """Indeks osobnika o największym przystosowaniu (przy remisie — pierwszego)."""
    return max(range(len(fitnesses)), key=fitnesses.__getitem__)


def run_ga(  # noqa: PLR0913 — dane, parametry i cztery opcjonalne funkcje zwrotne (tylko z nazwy)
    problem: KnapsackProblem,
    params: GAParams,
    *,  # funkcje zwrotne tylko z nazwy
    on_generation: Callable[[GenerationStats], None] | None = None,
    on_selection: Callable[[SelectionTrace], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    on_steps: Callable[[StepTrace], bool | None] | None = None,
) -> GAResult:
    """Uruchamia algorytm genetyczny i zwraca najlepszego znalezionego osobnika.

    Jedno pokolenie: selekcja (koło ruletki) -> krzyżowanie jednopunktowe -> mutacja -> naprawa ->
    ocena; potomkowie w całości zastępują populację (bez elitaryzmu). Najlepszy znaleziony osobnik
    jest przechowywany poza populacją.

    `on_generation` — wywoływana po ocenie każdej populacji (także pokolenia 0);
    `on_selection` — otrzymuje losowania koła ruletki z każdego pokolenia (animacja koła);
    `should_stop` — sprawdzana przed każdym pokoleniem (przycisk „Zatrzymaj”);
    `on_steps` — otrzymuje każde pokolenie krok po kroku (StepTrace, widok „Krok po kroku”); gdy zwróci
    False (np. limit zapisu), kolejne pokolenia nie są już zapisywane. Zapis nie zmienia kolejności losowań,
    więc przebieg jest taki sam jak bez niego. Żadna z funkcji nie zależy od Qt.
    Parametry i dane muszą być wcześniej sprawdzone (validation.py).
    """
    seed = params.seed if params.seed is not None else random.randrange(2**32)
    rng = random.Random(seed)  # jedyne źródło losowości — to samo ziarno daje ten sam przebieg
    start_time = time.perf_counter()

    # Mutacja wybranego rodzaju: na osobnika albo na gen.
    mutate = MUTATIONS[params.mutation_method]
    # Naprawa wybranego rodzaju: losowa albo zachłanna.
    repair_chromosome = make_repair(problem, params.repair_method, rng)

    # Pokolenie 0: losowa populacja, naprawiona.
    population = initial_population(problem, params.population_size, rng, repair_chromosome)
    fitnesses = [fitness(chromosome, problem) for chromosome in population]
    best = _best_index(fitnesses)
    best_chromosome: Chromosome = list(population[best])  # kopia — przechowywana poza populacją
    best_value = fitnesses[best]
    found_in_generation = 0
    history = [_generation_stats(0, fitnesses, best_value)]
    if on_generation is not None:
        on_generation(history[-1])

    record_steps = on_steps is not None
    stop_condition = StopCondition(params.max_generations, params.stagnation_limit)
    stop_reason: StopReason | None = None
    while stop_reason is None:
        if should_stop is not None and should_stop():
            stop_reason = StopReason.CANCELLED
            break
        generation = stop_condition.generation + 1

        # Selekcja: N rodziców losowanych kołem ruletki.
        spins = roulette_wheel_selection(fitnesses, params.population_size, rng)
        if on_selection is not None:
            on_selection(
                SelectionTrace(
                    generation=generation - 1,  # koło zbudowane z populacji poprzedniego pokolenia
                    fitnesses=tuple(fitnesses),
                    draws=tuple(spin.r for spin in spins),
                    selected=tuple(spin.index for spin in spins),
                )
            )
        parents = [population[spin.index] for spin in spins]

        # Krzyżowanie, mutacja, naprawa; potomkowie zastępują populację.
        logs: tuple[list[PairTrace], list[MutationTrace]] | tuple[None, None] = (
            ([], []) if record_steps else (None, None)
        )
        pair_log, mutation_log = logs
        offspring = crossover_population(parents, params.crossover_prob, rng, pair_log)
        mutated: list[str] = []
        new_population = []
        for child in offspring:  # mutacja i naprawa na przemian — naprawa losowa też losuje (kolejność losowań)
            mutant = mutate(child, params.mutation_prob, rng, mutation_log)
            if record_steps:
                mutated.append(_bits(mutant))
            new_population.append(repair_chromosome(mutant))
        new_fitnesses = [fitness(chromosome, problem) for chromosome in new_population]
        if record_steps:  # on_steps zwraca False, gdy nie chce kolejnych pokoleń (limit zapisu)
            record_steps = (
                on_steps(
                    StepTrace(
                        generation=generation - 1,
                        population=tuple(_bits(chromosome) for chromosome in population),
                        fitnesses=tuple(fitnesses),
                        draws=tuple(spin.r for spin in spins),
                        selected=tuple(spin.index for spin in spins),
                        pairs=tuple(pair_log),
                        offspring=tuple(_bits(child) for child in offspring),
                        mutations=tuple(mutation_log),
                        mutated=tuple(mutated),
                        new_population=tuple(_bits(chromosome) for chromosome in new_population),
                        new_fitnesses=tuple(new_fitnesses),
                    )
                )
                is not False
            )
        population, fitnesses = new_population, new_fitnesses

        # Aktualizacja najlepszego znalezionego osobnika — tylko przy ściśle większej wartości.
        candidate = _best_index(fitnesses)
        improved = fitnesses[candidate] > best_value
        if improved:
            best_chromosome = list(population[candidate])
            best_value = fitnesses[candidate]
            found_in_generation = generation

        history.append(_generation_stats(generation, fitnesses, best_value))
        if on_generation is not None:
            on_generation(history[-1])
        stop_reason = stop_condition.update(improved)  # warunek zatrzymania

    return GAResult(
        chromosome=tuple(best_chromosome),
        selected_items=tuple(item for gene, item in zip(best_chromosome, problem.items, strict=True) if gene == 1),
        total_value=best_value,
        total_weight=total_weight(best_chromosome, problem),
        found_in_generation=found_in_generation,
        generations_run=stop_condition.generation,
        stop_reason=stop_reason,
        seed=seed,
        elapsed_seconds=time.perf_counter() - start_time,
        history=tuple(history),
    )
