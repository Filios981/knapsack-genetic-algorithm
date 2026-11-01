"""Struktury danych wspólne dla algorytmu i interfejsu."""

from dataclasses import dataclass
from enum import Enum

# n genów; gen i == 1 oznacza, że przedmiot i jest w plecaku.
Chromosome = list[int]


@dataclass(frozen=True)
class Item:
    number: int  # numer przedmiotu pokazywany użytkownikowi (z danych albo kolejny od 1)
    weight: float  # > 0
    value: float  # >= 0
    name: str = ""  # nazwa (opcjonalna; "" = brak)


@dataclass(frozen=True)
class KnapsackProblem:
    items: tuple[Item, ...]
    capacity: float  # > 0

    @property
    def size(self) -> int:
        """Liczba przedmiotów = długość chromosomu."""
        return len(self.items)


class RepairMethod(Enum):
    """Sposób naprawy osobnika z nadwagą."""

    RANDOM = "naprawa losowa"  # wyjmowanie losowych przedmiotów (opcja do porównania)
    GREEDY = "naprawa zachłanna"  # najpierw przedmioty o najmniejszym stosunku wartości do wagi


class MutationMethod(Enum):
    """Znaczenie prawdopodobieństwa mutacji p_m."""

    PER_INDIVIDUAL = "mutacja na osobnika"  # z p_m potomek ma zanegowany jeden losowy gen (jak na zajęciach)
    PER_GENE = "mutacja na gen"  # każdy gen negowany z p_m (opcja do porównania)


@dataclass(frozen=True)
class GAParams:
    population_size: int = 100  # N
    crossover_prob: float = 0.8  # p_c, wymagane w zadaniu
    mutation_prob: float = 0.2  # p_m, wymagane w zadaniu
    mutation_method: MutationMethod = MutationMethod.PER_INDIVIDUAL  # mutacja na gen — opcja
    max_generations: int = 1000  # G_max
    stagnation_limit: int = 500  # G_s
    repair_method: RepairMethod = RepairMethod.GREEDY  # naprawa losowa — opcja
    seed: int | None = None  # None = ziarno losowe


@dataclass(frozen=True)
class GenerationStats:
    generation: int  # 0 = populacja początkowa
    best: float  # najlepsze przystosowanie w pokoleniu
    mean: float
    worst: float
    best_so_far: float  # wartość najlepszego znalezionego osobnika


@dataclass(frozen=True)
class SelectionTrace:
    """Losowania koła ruletki w jednym pokoleniu — odtwarzane przez animację."""

    generation: int
    fitnesses: tuple[float, ...]  # szerokości wycinków koła
    draws: tuple[float, ...]  # wylosowane r z przedziału [0, suma przystosowań)
    selected: tuple[int, ...]  # indeksy wybranych rodziców


@dataclass(frozen=True)
class PairTrace:
    """Krzyżowanie jednej pary rodziców (widok „Krok po kroku”)."""

    draw: float  # liczba z [0, 1) porównana z p_c
    cut: int | None  # punkt krzyżowania l (geny 1…l od pierwszego rodzica); None — para nieskrzyżowana


@dataclass(frozen=True)
class MutationTrace:
    """Mutacja jednego potomka."""

    draw: float | None  # liczba z [0, 1) porównana z p_m (mutacja na osobnika); None — mutacja na gen
    loci: tuple[int, ...]  # indeksy zanegowanych genów (od 0)


@dataclass(frozen=True)
class StepTrace:
    """Jedno pokolenie krok po kroku: populacja g i wszystkie etapy prowadzące do populacji g + 1.

    Chromosomy zapisane jako napisy („10110”) — mniej pamięci niż krotki liczb.
    """

    generation: int
    population: tuple[str, ...]
    fitnesses: tuple[float, ...]
    draws: tuple[float, ...]  # wylosowane r z [0, suma przystosowań) — jak SelectionTrace
    selected: tuple[int, ...]  # indeksy wybranych rodziców — pula rodzicielska
    pairs: tuple[PairTrace, ...]
    offspring: tuple[str, ...]  # po krzyżowaniu
    mutations: tuple[MutationTrace, ...]
    mutated: tuple[str, ...]  # po mutacji
    new_population: tuple[str, ...]  # po naprawie = populacja pokolenia g + 1
    new_fitnesses: tuple[float, ...]


class StopReason(Enum):
    STAGNATION = "brak poprawy przez G_s pokoleń"
    MAX_GENERATIONS = "osiągnięto limit G_max pokoleń"
    CANCELLED = "przerwane przez użytkownika"


@dataclass(frozen=True)
class GAResult:
    chromosome: tuple[int, ...]  # najlepszy znaleziony osobnik
    selected_items: tuple[Item, ...]
    total_value: float
    total_weight: float
    found_in_generation: int
    generations_run: int
    stop_reason: StopReason
    seed: int  # faktycznie użyte ziarno (także wylosowane)
    elapsed_seconds: float
    history: tuple[GenerationStats, ...]
