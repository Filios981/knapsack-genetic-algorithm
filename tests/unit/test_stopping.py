"""Testy warunku zatrzymania."""

from knapsack_ga.ga.stopping import StopCondition
from knapsack_ga.models import StopReason


def run(condition: StopCondition, improvements: list[bool]) -> list[StopReason | None]:
    return [condition.update(improved) for improved in improvements]


def test_stops_after_exactly_stagnation_limit_generations_without_improvement():
    results = run(StopCondition(max_generations=100, stagnation_limit=3), [False, False, False])
    assert results == [None, None, StopReason.STAGNATION]


def test_improvement_resets_stagnation_counter():
    results = run(StopCondition(max_generations=100, stagnation_limit=3), [False, False, True, False, False, False])
    assert results == [None, None, None, None, None, StopReason.STAGNATION]


def test_stops_at_generation_limit():
    results = run(StopCondition(max_generations=3, stagnation_limit=100), [True, True, True])
    assert results == [None, None, StopReason.MAX_GENERATIONS]


def test_stagnation_has_priority_when_both_conditions_meet():
    condition = StopCondition(max_generations=2, stagnation_limit=2)
    assert run(condition, [False, False]) == [None, StopReason.STAGNATION]
