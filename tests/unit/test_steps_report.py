"""Widok „Krok po kroku” — treść HTML dla ręcznie przygotowanego pokolenia."""

import pytest

from knapsack_ga.gui.steps_report import step_report_html
from knapsack_ga.models import GAParams, MutationMethod, MutationTrace, PairTrace, StepTrace

# Zbiór p02-5-items.csv (conftest: p02_problem): wagi 12, 7, 11, 8, 9; wartości 24, 13, 23, 15, 16; W = 26.
# Populacja: 11000 (waga 19, F = 37), 00110 (19, 38), 10001 (21, 40) — ΣF = 115.
# Koło: r = 10, 50, 100 -> 8.70%, 43.48%, 86.96% -> osobniki 1, 2, 3.
# Para 1: liczba 0.12, l = 3: 110|00 i 001|10 -> 110|10 i 001|00; osobnik 3 bez pary (kopia).
# Mutacja: potomek 1 — 0.15 < 0.2, l = 3: 11010 -> 11110 (waga 38 > 26); pozostali NIE.
# Naprawa zachłanna (kolejność 5, 2, 4, 1, 3): 11110 -> 10100 (wyjęte 2 i 4, waga 23).
STEP = StepTrace(
    generation=0,
    population=("11000", "00110", "10001"),
    fitnesses=(37.0, 38.0, 40.0),
    draws=(10.0, 50.0, 100.0),
    selected=(0, 1, 2),
    pairs=(PairTrace(0.12, 3),),
    offspring=("11010", "00100", "10001"),
    mutations=(MutationTrace(0.15, (2,)), MutationTrace(0.56, ()), MutationTrace(0.9, ())),
    mutated=("11110", "00100", "10001"),
    new_population=("10100", "00100", "10001"),
    new_fitnesses=(47.0, 23.0, 40.0),
)


@pytest.fixture
def html(p02_problem) -> str:
    return step_report_html(STEP, p02_problem, GAParams(population_size=3))


def test_all_six_stages_are_shown(html):
    for heading in ("1. Populacja początkowa", "2. Selekcja", "3. Krzyżowanie", "4. Mutacja", "5. Naprawa", "6. Nowa"):
        assert heading in html
    assert "Pokolenie 0 → 1" in html


def test_population_and_roulette_in_percent(html):
    assert "Σ<i>F</i> = <b>115</b>" in html
    assert "32.17" in html  # wycinek osobnika 1: 37 / 115
    assert "32.17–65.22" in html  # przedział osobnika 2
    for number in ("8.70", "43.48", "86.96"):
        assert number in html
    assert "Pula rodzicielska (kolejne pary): 1 i 2, 3" in html


def test_crossover_mutation_and_repair_details(html):
    assert "110|<b>10</b>" in html  # potomek 1: wymieniona część pogrubiona
    assert "bez pary" in html
    assert "0.120" in html and "0.150" in html and "0.560" in html
    assert '11<b><span style="color:#c62828">1</span></b>10' in html  # zanegowany gen 3 na czerwono
    assert "Potomkowie z nadwagą: 1 z 3." in html
    assert "<td>2, 4</td>" in html  # wyjęte przedmioty
    assert "Σ<i>F</i>: 115 → <b>110</b>" in html


def test_per_gene_mutation_and_no_repair(p02_problem):
    step = StepTrace(
        **{**STEP.__dict__, "mutations": (MutationTrace(None, ()),) * 3, "mutated": STEP.offspring},
    )
    step = StepTrace(**{**step.__dict__, "new_population": STEP.offspring, "new_fitnesses": (70.0, 23.0, 40.0)})
    html = step_report_html(step, p02_problem, GAParams(mutation_method=MutationMethod.PER_GENE))
    assert "na gen" in html
    assert "Żaden potomek nie przekracza pojemności" in html
