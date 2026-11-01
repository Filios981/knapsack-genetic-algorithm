"""Zakładka „Krok po kroku”: wybrane pokolenie w etapach jak na zajęciach."""

from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QSpinBox, QTextBrowser, QVBoxLayout, QWidget

from knapsack_ga.gui.steps_report import step_report_html
from knapsack_ga.models import GAParams, KnapsackProblem, StepTrace

EMPTY_TEXT = "Uruchom algorytm — tu pojawi się wybrane pokolenie krok po kroku, jak w przykładzie z zajęć."


class StepsPanel(QWidget):
    """Wybór pokolenia i widok HTML (step_report_html). Zasilany listą StepTrace z sygnału GAWorker.steps
    (`set_traces` po zakończeniu algorytmu, `clear` przed nowym przebiegiem).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._traces: list[StepTrace] = []
        self._problem: KnapsackProblem | None = None
        self._params: GAParams | None = None

        self.generation = QSpinBox()
        self.generation.setKeyboardTracking(False)
        self.generation.valueChanged.connect(self.show_generation)
        self.info = QLabel()
        self.save_button = QPushButton("Zapisz jako HTML…")
        self.save_button.clicked.connect(self.save_html)
        self.view = QTextBrowser()

        top = QHBoxLayout()
        top.addWidget(QLabel("Pokolenie:"))
        top.addWidget(self.generation)
        top.addWidget(self.info, stretch=1)
        top.addWidget(self.save_button)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.view)
        self.clear()

    def set_traces(self, traces: list[StepTrace], problem: KnapsackProblem, params: GAParams) -> None:
        """Zapisane pokolenia (od 0); przy dużych N · n tylko pierwsze (limit zapisu)."""
        if not traces:
            self.clear()
            return
        self._traces, self._problem, self._params = list(traces), problem, params
        self.generation.blockSignals(True)
        self.generation.setRange(0, len(self._traces) - 1)
        self.generation.setValue(0)
        self.generation.blockSignals(False)
        self.generation.setEnabled(True)
        self.save_button.setEnabled(True)
        self.info.setText(f"zapisane pokolenia: 0–{len(self._traces) - 1}")
        self.show_generation(0)

    def clear(self) -> None:
        self._traces = []
        self.generation.blockSignals(True)
        self.generation.setRange(0, 0)
        self.generation.blockSignals(False)
        self.generation.setEnabled(False)
        self.save_button.setEnabled(False)
        self.info.clear()
        self.view.setPlainText(EMPTY_TEXT)

    def show_generation(self, generation: int) -> None:
        if self._traces:
            scroll = self.view.verticalScrollBar().value()
            self.view.setHtml(step_report_html(self._traces[generation], self._problem, self._params))
            self.view.verticalScrollBar().setValue(scroll)  # ten sam etap przy przeglądaniu kolejnych pokoleń

    def html(self) -> str:
        """HTML bieżącego pokolenia (zapis do pliku, testy)."""
        trace = self._traces[self.generation.value()]
        return step_report_html(trace, self._problem, self._params)

    def save_html(self) -> None:
        if not self._traces:
            return
        name, _ = QFileDialog.getSaveFileName(
            self, "Zapisz pokolenie", f"pokolenie-{self.generation.value()}.html", "HTML (*.html)"
        )
        if name:
            document = f'<!doctype html><html lang="pl"><meta charset="utf-8"><body>{self.html()}</body></html>'
            Path(name).write_text(document, encoding="utf-8")
