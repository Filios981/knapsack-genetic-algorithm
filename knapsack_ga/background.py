"""Uruchomienie run_ga w osobnym procesie — dla interfejsu (gui/worker.py).

Wątki Pythona dzielą blokadę GIL: algorytm liczony w wątku obok okna zabierał oknu czas i interfejs
przestawał reagować. Osobny proces ma własny interpreter, więc okno działa płynnie, a algorytm
z pełną szybkością. Moduł nie importuje Qt — proces potomny uruchamia się szybciej.
Komunikacja: kolejka wiadomości (proces -> okno) i zdarzenie „zatrzymaj” (okno -> proces).
"""

import time
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Event

from knapsack_ga.ga.engine import run_ga
from knapsack_ga.models import GAParams, GenerationStats, KnapsackProblem, SelectionTrace, StepTrace

# Statystyki pokoleń wysyłane paczkami najwyżej co 50 ms — okno nie potrzebuje częstszych aktualizacji.
PROGRESS_INTERVAL_S = 0.05
# Zapis selekcji dla koła ruletki: najwyżej tyle losowań (N · liczba pokoleń) — cały przebieg
# przy parametrach domyślnych (100 · 1000), ok. 8 MB pamięci; przy większych N lub G — pierwsze pokolenia.
MAX_RECORDED_SPINS = 100_000
# Zapis pokoleń krok po kroku: najwyżej tyle genów (4 etapy · N · n na pokolenie) — przy N = 8 i
# n = 10 wszystkie pokolenia, przy N = 100 i n = 100 — 100 pierwszych.
MAX_RECORDED_STEP_GENES = 4_000_000

# Rodzaje wiadomości w kolejce: (rodzaj, dane).
PROGRESS = "progress"  # list[GenerationStats]
SELECTION = "selection"  # list[SelectionTrace]
STEPS = "steps"  # list[StepTrace]
FINISHED = "finished"  # GAResult
FAILED = "failed"  # str — komunikat błędu


def run_in_process(  # noqa: PLR0913, PLR0917 — multiprocessing przekazuje argumenty pozycyjnie
    problem: KnapsackProblem,
    params: GAParams,
    record_selection: bool,
    messages: Queue,
    stop: Event,
    record_steps: bool = False,
) -> None:
    """Funkcja procesu obliczeń: run_ga z funkcjami zwrotnymi wysyłającymi wiadomości do okna."""
    progress: list[GenerationStats] = []
    selections: list[SelectionTrace] = []
    steps: list[StepTrace] = []
    recorded_spins = 0
    recorded_genes = 0
    step_genes = 4 * params.population_size * problem.size
    last_sent = time.perf_counter()

    def send_pending() -> None:
        nonlocal progress, selections, steps, last_sent
        if progress:
            messages.put((PROGRESS, progress))
            progress = []
        if selections:
            messages.put((SELECTION, selections))
            selections = []
        if steps:
            messages.put((STEPS, steps))
            steps = []
        last_sent = time.perf_counter()

    def on_generation(stats: GenerationStats) -> None:
        progress.append(stats)
        if time.perf_counter() - last_sent >= PROGRESS_INTERVAL_S:
            send_pending()

    def on_selection(trace: SelectionTrace) -> None:
        nonlocal recorded_spins
        if recorded_spins + len(trace.draws) <= MAX_RECORDED_SPINS:
            recorded_spins += len(trace.draws)
            selections.append(trace)  # lista podmieniana w send_pending — odczyt nazwy przy każdym wywołaniu

    def on_steps(trace: StepTrace) -> bool:
        nonlocal recorded_genes
        if recorded_genes + step_genes > MAX_RECORDED_STEP_GENES:
            return False  # limit — algorytm przestaje zapisywać kolejne pokolenia
        recorded_genes += step_genes
        steps.append(trace)
        return True

    try:
        result = run_ga(
            problem,
            params,
            on_generation=on_generation,
            on_selection=on_selection if record_selection else None,
            should_stop=stop.is_set,
            on_steps=on_steps if record_steps else None,
        )
    except Exception as error:  # każdy błąd obliczeń trafia do okna jako komunikat
        messages.put((FAILED, f"{type(error).__name__}: {error}"))
    else:
        send_pending()
        messages.put((FINISHED, result))
