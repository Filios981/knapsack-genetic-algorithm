"""Każdy moduł pakietu daje się zaimportować (sprawdza też, czy zainstalowano PyQt6 i matplotlib)."""

import importlib

import pytest

MODULES = [
    "knapsack_ga.models",
    "knapsack_ga.data_io",
    "knapsack_ga.validation",
    "knapsack_ga.exact",
    "knapsack_ga.ga.fitness",
    "knapsack_ga.ga.population",
    "knapsack_ga.ga.selection",
    "knapsack_ga.ga.crossover",
    "knapsack_ga.ga.mutation",
    "knapsack_ga.ga.repair",
    "knapsack_ga.ga.stopping",
    "knapsack_ga.ga.engine",
    "knapsack_ga.gui.app",
    "knapsack_ga.gui.main_window",
    "knapsack_ga.gui.items_table",
    "knapsack_ga.gui.import_dialog",
    "knapsack_ga.gui.params_panel",
    "knapsack_ga.gui.results_panel",
    "knapsack_ga.gui.chart_widget",
    "knapsack_ga.gui.roulette_widget",
    "knapsack_ga.gui.worker",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports(module_name: str):
    importlib.import_module(module_name)
