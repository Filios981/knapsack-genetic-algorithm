"""Testy walidacji danych i parametrów."""

import pytest

from knapsack_ga.models import GAParams, Item, KnapsackProblem
from knapsack_ga.validation import validate_params, validate_problem


def problem(*weights_values: tuple[float, float], capacity: float = 10) -> KnapsackProblem:
    items = tuple(Item(number=i + 1, weight=w, value=v) for i, (w, v) in enumerate(weights_values))
    return KnapsackProblem(items=items, capacity=capacity)


def test_correct_problem_has_no_errors_or_warnings(p02_problem):
    report = validate_problem(p02_problem)
    assert report.ok
    assert report.warnings == ()


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        (problem(capacity=10), "Brak przedmiotów"),
        (problem((1, 1), capacity=0), "Pojemność plecaka"),
        (problem((0, 5), (20, 1)), "waga musi być większa od 0"),
        (problem((-2, 5), (20, 1)), "waga musi być większa od 0"),
        (problem((3, -1), (20, 1)), "wartość nie może być ujemna"),
    ],
)
def test_errors(data, fragment):
    report = validate_problem(data)
    assert not report.ok
    assert any(fragment in error for error in report.errors)


def test_duplicate_item_number_is_an_error():
    data = KnapsackProblem(items=(Item(1, 2, 3), Item(1, 4, 5)), capacity=3)
    assert any("Powtórzony numer" in error for error in validate_problem(data).errors)


def test_value_zero_is_allowed():
    assert validate_problem(problem((3, 0), (20, 1))).ok


def test_warning_for_items_heavier_than_capacity():
    report = validate_problem(problem((5, 1), (20, 1), (30, 1), capacity=10))
    assert report.ok
    assert any("cięższe niż pojemność" in warning and "2, 3" in warning for warning in report.warnings)


def test_warning_when_all_items_fit():
    report = validate_problem(problem((2, 1), (3, 1), capacity=10))
    assert report.ok
    assert any("wszystkie przedmioty" in warning for warning in report.warnings)


def test_default_params_are_valid():
    assert validate_params(GAParams()) == []


@pytest.mark.parametrize(
    "params",
    [
        GAParams(population_size=1),
        GAParams(crossover_prob=1.1),
        GAParams(mutation_prob=-0.1),
        GAParams(max_generations=0),
        GAParams(stagnation_limit=0),
    ],
)
def test_params_out_of_range(params):
    assert len(validate_params(params)) == 1
