"""Wspólne fixtures testów."""

from pathlib import Path

import pytest

from knapsack_ga.models import Item, KnapsackProblem

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture
def samples_dir() -> Path:
    return SAMPLES_DIR


@pytest.fixture
def p02_problem() -> KnapsackProblem:
    """Zbiór p02-5-items.csv (P02): optimum — wartość 51, waga 26, przedmioty 2, 3, 4 (chromosom 01110)."""
    weights = [12, 7, 11, 8, 9]
    values = [24, 13, 23, 15, 16]
    items = tuple(Item(number=i + 1, weight=w, value=v) for i, (w, v) in enumerate(zip(weights, values, strict=True)))
    return KnapsackProblem(items=items, capacity=26)
