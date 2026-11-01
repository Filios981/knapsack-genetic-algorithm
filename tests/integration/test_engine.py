"""Testy całego algorytmu i rozwiązania dokładnego."""

import bisect
import itertools
from pathlib import Path

import pytest

from knapsack_ga.data_io import parse_items_text, read_text_file
from knapsack_ga.exact import can_solve_exact, solve_exact
from knapsack_ga.ga.engine import run_ga
from knapsack_ga.ga.fitness import is_feasible, total_value, total_weight
from knapsack_ga.ga.selection import cumulative_sums
from knapsack_ga.models import (
    GAParams,
    Item,
    KnapsackProblem,
    MutationMethod,
    RepairMethod,
    SelectionTrace,
    StepTrace,
    StopReason,
)

SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "samples"

# Zbiory ze znanym optimum (samples/README.md): plik, wartość optimum, waga optimum.
OPTIMA = [
    ("p02-5-items.csv", 51, 26),
    ("p01-10-items.csv", 309, 165),
    ("p07-15-items.csv", 1458, 749),
    ("rosetta-22-items.csv", 1030, 396),
    ("random-50-items.csv", 2297, 880),
    ("random-100-items.csv", 3582, 1677),
]

ALL_SAMPLES = [name for name, _, _ in OPTIMA] + ["edge-all-too-heavy.csv", "edge-all-fit.csv", "format-cp1250.csv"]


def load_problem(file_name: str) -> KnapsackProblem:
    data = parse_items_text(read_text_file(SAMPLES_DIR / file_name))
    return KnapsackProblem(items=data.items, capacity=data.capacity)


# --- Rozwiązanie dokładne -------------------------------------------------------------------------


@pytest.mark.parametrize(("file_name", "value", "weight"), OPTIMA)
def test_exact_solution_matches_known_optimum(file_name, value, weight):
    problem = load_problem(file_name)
    solution = solve_exact(problem)

    assert solution.total_value == value
    assert solution.total_weight == weight
    assert total_value(list(solution.chromosome), problem) == value


def test_exact_solution_is_not_available_for_fractional_weights():
    problem = KnapsackProblem(items=(Item(1, 2.5, 10), Item(2, 4, 12)), capacity=10.5)
    assert not can_solve_exact(problem)
    with pytest.raises(ValueError):
        solve_exact(problem)


def test_exact_solution_rounds_fractional_capacity_down():
    problem = KnapsackProblem(items=(Item(1, 5, 10), Item(2, 6, 12)), capacity=10.9)
    assert solve_exact(problem).total_value == 12


# --- Poprawność wyniku ----------------------------------------------------------------------------


@pytest.mark.parametrize("file_name", ALL_SAMPLES)
def test_result_is_feasible_and_consistent(file_name):
    problem = load_problem(file_name)
    result = run_ga(problem, GAParams(seed=1, max_generations=200))
    chromosome = list(result.chromosome)

    assert is_feasible(chromosome, problem)
    assert result.total_value == total_value(chromosome, problem)
    assert result.total_weight == total_weight(chromosome, problem)
    assert result.selected_items == tuple(item for gene, item in zip(chromosome, problem.items, strict=True) if gene)
    assert len(result.history) == result.generations_run + 1


def test_best_so_far_never_decreases_and_equals_result():
    result = run_ga(load_problem("random-50-items.csv"), GAParams(seed=3))
    best_so_far = [stats.best_so_far for stats in result.history]

    assert best_so_far == sorted(best_so_far)
    assert best_so_far[-1] == result.total_value
    assert result.history[result.found_in_generation].best == result.total_value


def test_small_problems_reach_optimum():
    for file_name, value, _ in OPTIMA[:3]:
        assert run_ga(load_problem(file_name), GAParams(seed=1)).total_value == value


def test_edge_cases():
    too_heavy = run_ga(load_problem("edge-all-too-heavy.csv"), GAParams(seed=1))
    all_fit = run_ga(load_problem("edge-all-fit.csv"), GAParams(seed=1))

    assert too_heavy.total_value == 0
    assert too_heavy.selected_items == ()
    assert all_fit.total_value == 150


# --- Powtarzalność --------------------------------------------------------------------------------


def test_same_seed_gives_identical_run():
    problem = load_problem("rosetta-22-items.csv")
    first = run_ga(problem, GAParams(seed=42))
    second = run_ga(problem, GAParams(seed=42))

    assert first.chromosome == second.chromosome
    assert first.history == second.history


def test_random_seed_is_reported_and_reproduces_the_run():
    problem = load_problem("p07-15-items.csv")
    first = run_ga(problem, GAParams(seed=None))
    second = run_ga(problem, GAParams(seed=first.seed))
    assert first.history == second.history


# --- Warunki zatrzymania --------------------------------------------------------------------------


def test_stop_reasons():
    problem = load_problem("p01-10-items.csv")

    stagnation = run_ga(problem, GAParams(seed=1, stagnation_limit=1, max_generations=1000))
    limit = run_ga(problem, GAParams(seed=1, stagnation_limit=1000, max_generations=5))
    cancelled = run_ga(problem, GAParams(seed=1), should_stop=lambda: True)

    assert stagnation.stop_reason is StopReason.STAGNATION
    assert (limit.stop_reason, limit.generations_run) == (StopReason.MAX_GENERATIONS, 5)
    assert (cancelled.stop_reason, cancelled.generations_run) == (StopReason.CANCELLED, 0)


def test_stagnation_stops_exactly_after_limit():
    result = run_ga(load_problem("p07-15-items.csv"), GAParams(seed=1, stagnation_limit=30))
    assert result.stop_reason is StopReason.STAGNATION
    assert result.generations_run - result.found_in_generation == 30


def test_callbacks_receive_every_generation():
    received = []
    result = run_ga(load_problem("p01-10-items.csv"), GAParams(seed=1), on_generation=received.append)
    assert tuple(received) == result.history


# --- Zapis selekcji dla animacji koła ruletki -----------------------------------------------------


def test_selection_trace_can_be_replayed():
    traces: list[SelectionTrace] = []
    params = GAParams(seed=5, population_size=20)
    result = run_ga(load_problem("rosetta-22-items.csv"), params, on_selection=traces.append)

    assert len(traces) == result.generations_run
    assert [trace.generation for trace in traces] == list(range(result.generations_run))
    for trace in traces:
        cumulative = cumulative_sums(list(trace.fitnesses))
        assert len(trace.draws) == len(trace.selected) == params.population_size
        for r, index in zip(trace.draws, trace.selected, strict=True):
            assert min(bisect.bisect_right(cumulative, r), len(cumulative) - 1) == index


@pytest.mark.parametrize("file_name", ALL_SAMPLES)
def test_greedy_repair_result_is_feasible_and_reproducible(file_name):
    problem = load_problem(file_name)
    params = GAParams(seed=3, repair_method=RepairMethod.GREEDY, max_generations=50)
    result = run_ga(problem, params)

    assert is_feasible(list(result.chromosome), problem)
    assert result.total_value == total_value(list(result.chromosome), problem)
    again = run_ga(problem, params)
    assert (again.chromosome, again.history) == (result.chromosome, result.history)


# --- Zapis pokolenia krok po kroku (widok „Krok po kroku”) ----------------------------------------


def genes(bits: str) -> list[int]:
    return [int(bit) for bit in bits]


def check_step(step: StepTrace, problem: KnapsackProblem, params: GAParams) -> None:
    """Każdy etap zapisu wynika z poprzedniego — tak, jak pokazuje go widok."""
    parents = [step.population[index] for index in step.selected]
    assert [step.fitnesses[index] for index in step.selected] == [
        total_value(genes(parent), problem) for parent in parents
    ]
    for number, pair in enumerate(step.pairs):
        first, second = parents[2 * number], parents[2 * number + 1]
        children = step.offspring[2 * number : 2 * number + 2]
        if pair.cut is None:
            assert pair.draw >= params.crossover_prob
            assert children == (first, second)
        else:
            assert pair.draw < params.crossover_prob
            assert 1 <= pair.cut <= problem.size - 1
            assert children == (first[: pair.cut] + second[pair.cut :], second[: pair.cut] + first[pair.cut :])
    if params.population_size % 2 == 1:
        assert step.offspring[-1] == parents[-1]  # ostatni rodzic bez pary — kopiowany
    for before, after, mutation in zip(step.offspring, step.mutated, step.mutations, strict=True):
        assert tuple(i for i in range(problem.size) if before[i] != after[i]) == mutation.loci
        if params.mutation_method is MutationMethod.PER_INDIVIDUAL:
            assert (mutation.draw < params.mutation_prob) == (len(mutation.loci) == 1)
        else:
            assert mutation.draw is None
    for mutant, repaired, value in zip(step.mutated, step.new_population, step.new_fitnesses, strict=True):
        assert is_feasible(genes(repaired), problem)
        assert all(a >= b for a, b in zip(mutant, repaired, strict=True))  # naprawa tylko wyjmuje (1 -> 0)
        assert value == total_value(genes(repaired), problem)


@pytest.mark.parametrize("mutation_method", list(MutationMethod))
@pytest.mark.parametrize("repair_method", list(RepairMethod))
def test_step_traces_reproduce_every_stage_without_changing_the_run(mutation_method, repair_method):
    problem = load_problem("p02-5-items.csv")
    params = GAParams(
        seed=4,
        population_size=7,  # nieparzyste — ostatni rodzic bez pary
        max_generations=30,
        stagnation_limit=1_000_000,
        mutation_method=mutation_method,
        repair_method=repair_method,
    )
    steps: list[StepTrace] = []
    traced = run_ga(problem, params, on_steps=steps.append)
    plain = run_ga(problem, params)

    assert (traced.chromosome, traced.history) == (plain.chromosome, plain.history)  # zapis nie zmienia przebiegu
    assert [step.generation for step in steps] == list(range(30))
    for step, following in itertools.pairwise(steps):
        assert following.population == step.new_population
        assert following.fitnesses == step.new_fitnesses
    for step in steps:
        check_step(step, problem, params)
