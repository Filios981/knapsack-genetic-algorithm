"""Most między procesem obliczeń a oknem: QThread odbiera wiadomości i emituje sygnały Qt.

Algorytm liczy się w osobnym procesie (knapsack_ga/background.py). Wątek QThread tylko czeka na
wiadomości z kolejki — czekanie odbywa się poza kodem Pythona, więc nie zabiera oknu czasu.
"""

import multiprocessing
import queue

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from knapsack_ga.background import FAILED, FINISHED, PROGRESS, SELECTION, STEPS, run_in_process
from knapsack_ga.models import GAParams, KnapsackProblem

POLL_TIMEOUT_S = 0.2  # co tyle sprawdzane jest, czy proces obliczeń nie zakończył się bez wyniku


class GAWorker(QObject):
    """Przenoszony do QThread przez MainWindow; `run` wywoływane sygnałem QThread.started.

    Uruchamia proces obliczeń i zamienia jego wiadomości na sygnały: `progress` (lista GenerationStats
    od poprzedniej paczki), `selection` (lista SelectionTrace — tylko gdy `record_selection`, dla animacji
    koła), `steps` (lista StepTrace — tylko gdy `record_steps`, widok „Krok po kroku”), `finished` (GAResult),
    `failed` (komunikat). `request_stop()` ustawia zdarzenie sprawdzane
    przez algorytm przed każdym pokoleniem.
    """

    progress = pyqtSignal(object)  # list[GenerationStats]
    selection = pyqtSignal(object)  # list[SelectionTrace]
    steps = pyqtSignal(object)  # list[StepTrace]
    finished = pyqtSignal(object)  # GAResult
    failed = pyqtSignal(str)  # komunikat błędu

    def __init__(
        self, problem: KnapsackProblem, params: GAParams, record_selection: bool = False, record_steps: bool = False
    ) -> None:
        super().__init__()
        self._problem = problem
        self._params = params
        self._record_selection = record_selection
        self._record_steps = record_steps
        # „spawn” — nowy interpreter; jedyny sposób w Windows, to samo zachowanie w innych systemach.
        self._context = multiprocessing.get_context("spawn")
        self._stop = self._context.Event()

    def request_stop(self) -> None:
        """Przycisk „Zatrzymaj”: algorytm kończy po bieżącym pokoleniu (powód: przerwane przez użytkownika)."""
        self._stop.set()

    @pyqtSlot()
    def run(self) -> None:
        messages = self._context.Queue()
        process = self._context.Process(
            target=run_in_process,
            args=(self._problem, self._params, self._record_selection, messages, self._stop, self._record_steps),
            daemon=True,
        )
        process.start()
        try:
            self._forward_messages(messages, process)
        finally:
            process.join(timeout=5)
            if process.is_alive():
                process.terminate()

    def _forward_messages(self, messages, process) -> None:
        while True:
            try:
                kind, payload = messages.get(timeout=POLL_TIMEOUT_S)
            except queue.Empty:
                if not process.is_alive():
                    self.failed.emit(f"Proces obliczeń zakończył się bez wyniku (kod {process.exitcode}).")
                    return
                continue
            if kind == PROGRESS:
                self.progress.emit(payload)
            elif kind == SELECTION:
                self.selection.emit(payload)
            elif kind == STEPS:
                self.steps.emit(payload)
            elif kind == FINISHED:
                self.finished.emit(payload)
                return
            elif kind == FAILED:
                self.failed.emit(payload)
                return
