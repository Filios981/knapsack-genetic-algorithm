"""Walidacja danych wejściowych i parametrów algorytmu."""

from dataclasses import dataclass

from knapsack_ga.data_io import format_number
from knapsack_ga.models import GAParams, KnapsackProblem

# Ile numerów przedmiotów wymienić w jednym komunikacie, zanim zostanie skrócony „…”.
_MAX_LISTED = 10


@dataclass(frozen=True)
class ValidationReport:
    errors: tuple[str, ...]  # blokują uruchomienie algorytmu
    warnings: tuple[str, ...]  # pokazywane użytkownikowi, który decyduje, czy kontynuować

    @property
    def ok(self) -> bool:
        return not self.errors


def _list_numbers(numbers: list[int]) -> str:
    listed = ", ".join(str(number) for number in numbers[:_MAX_LISTED])
    return listed + (", …" if len(numbers) > _MAX_LISTED else "")


def validate_problem(problem: KnapsackProblem) -> ValidationReport:
    """Sprawdzenie danych problemu.

    Błędy: brak przedmiotów, waga <= 0, wartość < 0, pojemność <= 0, powtórzony numer przedmiotu.
    Ostrzeżenia: przedmioty cięższe niż pojemność, suma wag wszystkich przedmiotów <= pojemność.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if not problem.items:
        errors.append("Brak przedmiotów — dodaj co najmniej jeden przedmiot.")
    if problem.capacity <= 0:
        errors.append(f"Pojemność plecaka musi być większa od 0 (jest {format_number(problem.capacity)}).")

    seen: set[int] = set()
    for item in problem.items:
        if item.weight <= 0:
            errors.append(f"Przedmiot {item.number}: waga musi być większa od 0 (jest {format_number(item.weight)}).")
        if item.value < 0:
            errors.append(f"Przedmiot {item.number}: wartość nie może być ujemna (jest {format_number(item.value)}).")
        if item.number in seen:
            errors.append(f"Powtórzony numer przedmiotu: {item.number}.")
        seen.add(item.number)

    if problem.items and problem.capacity > 0:
        too_heavy = [item.number for item in problem.items if item.weight > problem.capacity]
        if too_heavy:
            warnings.append(
                f"Przedmioty cięższe niż pojemność plecaka — nigdy nie trafią do plecaka: {_list_numbers(too_heavy)}."
            )
        total_weight = sum(item.weight for item in problem.items)
        if total_weight <= problem.capacity:
            warnings.append(
                f"Suma wag wszystkich przedmiotów ({format_number(total_weight)}) nie przekracza pojemności "
                f"({format_number(problem.capacity)}) — rozwiązaniem są wszystkie przedmioty."
            )
    return ValidationReport(tuple(errors), tuple(warnings))


def validate_params(params: GAParams) -> list[str]:
    """Komunikaty o parametrach spoza dopuszczalnych zakresów."""
    errors: list[str] = []
    if params.population_size < 2:
        errors.append("Wielkość populacji musi wynosić co najmniej 2.")
    if not 0 <= params.crossover_prob <= 1:
        errors.append("Prawdopodobieństwo krzyżowania musi należeć do przedziału [0, 1].")
    if not 0 <= params.mutation_prob <= 1:
        errors.append("Prawdopodobieństwo mutacji musi należeć do przedziału [0, 1].")
    if params.max_generations < 1:
        errors.append("Maksymalna liczba pokoleń musi wynosić co najmniej 1.")
    if params.stagnation_limit < 1:
        errors.append("Limit stagnacji musi wynosić co najmniej 1.")
    return errors
