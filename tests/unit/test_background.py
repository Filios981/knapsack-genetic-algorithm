"""Testy funkcji procesu obliczeń (background.py) — wywoływanej tu bezpośrednio, bez osobnego procesu."""

import queue
import threading

from knapsack_ga import background
from knapsack_ga.background import FAILED, FINISHED, PROGRESS, SELECTION, STEPS, run_in_process
from knapsack_ga.ga.engine import run_ga
from knapsack_ga.models import GAParams, StopReason


def collect(messages: queue.Queue) -> list[tuple[str, object]]:
    items = []
    while not messages.empty():
        items.append(messages.get())
    return items


def test_messages_contain_all_generations_and_the_result(p02_problem):
    params = GAParams(seed=5, max_generations=300, stagnation_limit=1_000_000)
    messages: queue.Queue = queue.Queue()
    run_in_process(p02_problem, params, record_selection=True, messages=messages, stop=threading.Event())

    received = collect(messages)
    kinds = [kind for kind, _ in received]
    assert kinds[-1] == FINISHED
    result = received[-1][1]
    expected = run_ga(p02_problem, params)  # ten sam przebieg co bez procesu (to samo ziarno)
    assert (result.chromosome, result.history) == (expected.chromosome, expected.history)

    stats = [s for kind, batch in received if kind == PROGRESS for s in batch]
    assert [s.generation for s in stats] == list(range(301))  # wszystkie pokolenia, w kolejności, bez powtórzeń
    traces = [t for kind, batch in received if kind == SELECTION for t in batch]
    assert [t.generation for t in traces] == list(range(300))


def test_selection_is_not_sent_unless_requested(p02_problem):
    messages: queue.Queue = queue.Queue()
    run_in_process(p02_problem, GAParams(seed=1), record_selection=False, messages=messages, stop=threading.Event())
    assert SELECTION not in [kind for kind, _ in collect(messages)]


def test_stop_event_cancels_the_run(p02_problem):
    stop = threading.Event()
    stop.set()
    messages: queue.Queue = queue.Queue()
    run_in_process(p02_problem, GAParams(seed=1), record_selection=False, messages=messages, stop=stop)
    kind, result = collect(messages)[-1]
    assert kind == FINISHED
    assert result.stop_reason is StopReason.CANCELLED
    assert result.generations_run == 0


def test_error_is_reported_as_message(p02_problem, monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError("awaria")

    monkeypatch.setattr(background, "run_ga", broken)
    messages: queue.Queue = queue.Queue()
    run_in_process(p02_problem, GAParams(seed=1), record_selection=False, messages=messages, stop=threading.Event())
    assert collect(messages) == [(FAILED, "RuntimeError: awaria")]


def test_selection_recording_stops_at_the_limit(p02_problem, monkeypatch):
    monkeypatch.setattr(background, "MAX_RECORDED_SPINS", 250)  # N = 100 — mieszczą się 2 pokolenia
    messages: queue.Queue = queue.Queue()
    params = GAParams(seed=1, max_generations=10, stagnation_limit=1_000_000)
    run_in_process(p02_problem, params, record_selection=True, messages=messages, stop=threading.Event())
    traces = [t for kind, batch in collect(messages) if kind == SELECTION for t in batch]
    assert [t.generation for t in traces] == [0, 1]  # pierwsze pokolenia, bez przerw


def test_steps_are_sent_until_the_gene_limit(p02_problem, monkeypatch):
    # 4 etapy · N = 10 · n = 5 = 200 genów na pokolenie — w limicie 650 mieszczą się 3 pokolenia
    monkeypatch.setattr(background, "MAX_RECORDED_STEP_GENES", 650)
    params = GAParams(seed=1, population_size=10, max_generations=20, stagnation_limit=1_000_000)
    messages: queue.Queue = queue.Queue()
    run_in_process(p02_problem, params, False, messages, threading.Event(), record_steps=True)
    received = collect(messages)
    steps = [s for kind, batch in received if kind == STEPS for s in batch]
    assert [s.generation for s in steps] == [0, 1, 2]
    assert received[-1][1].history == run_ga(p02_problem, params).history  # zapis nie zmienia przebiegu


def test_steps_are_not_sent_unless_requested(p02_problem):
    messages: queue.Queue = queue.Queue()
    run_in_process(p02_problem, GAParams(seed=1), record_selection=False, messages=messages, stop=threading.Event())
    assert STEPS not in [kind for kind, _ in collect(messages)]
