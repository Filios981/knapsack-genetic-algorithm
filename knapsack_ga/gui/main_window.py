"""Okno główne: układ paneli, menu „Plik”, przyciski Uruchom / Zatrzymaj."""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QCloseEvent, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from knapsack_ga.data_io import DataFormatError, ParsedData, format_number, parse_number, read_text_file, save_csv
from knapsack_ga.exact import solve_exact
from knapsack_ga.gui.chart_widget import FitnessChart
from knapsack_ga.gui.import_dialog import FILE_FILTER, ImportDialog
from knapsack_ga.gui.items_table import ItemsTable
from knapsack_ga.gui.params_panel import ParamsPanel
from knapsack_ga.gui.results_panel import ResultsPanel
from knapsack_ga.gui.roulette_widget import RoulettePanel
from knapsack_ga.gui.steps_panel import StepsPanel
from knapsack_ga.gui.worker import GAWorker
from knapsack_ga.models import GAParams, GAResult, GenerationStats, KnapsackProblem, SelectionTrace, StepTrace
from knapsack_ga.validation import validate_params, validate_problem

INVALID_STYLE = "background-color: #f6c9c9;"  # pole z błędną wartością


def samples_dir() -> Path:
    """Katalog zbiorów przykładowych: obok pliku .exe (paczka PyInstaller) albo w katalogu projektu."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "samples"
    return Path(__file__).resolve().parents[2] / "samples"


class MainWindow(QMainWindow):
    """U góry dane (ItemsTable + pojemność) i parametry (ParamsPanel), na dole wynik (ResultsPanel)
    i wykres (FitnessChart).

    Uruchom: odczyt tabeli -> validate_problem / validate_params -> start GAWorker w QThread.
    """

    run_finished = pyqtSignal(object)  # GAResult — po wyświetleniu wyniku (testy interfejsu)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Problem plecakowy — algorytm genetyczny")
        self._thread: QThread | None = None
        self._worker: GAWorker | None = None
        self._run_problem: KnapsackProblem | None = None  # dane i parametry trwającego przebiegu
        self._run_params: GAParams | None = None
        self._last: tuple[GAResult, KnapsackProblem] | None = None  # ostatni wynik — do porównania z optimum

        self.data_box = self._build_data_box()
        self.results = ResultsPanel()
        self.results.compare_requested.connect(self.compare_with_optimum)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_chart_page(), "Przebieg")
        self.roulette = RoulettePanel()
        self.tabs.addTab(self.roulette, "Koło ruletki")
        self.steps_panel = StepsPanel()
        self.tabs.addTab(self.steps_panel, "Krok po kroku")
        self._traces: list[SelectionTrace] = []  # losowania selekcji trwającego przebiegu
        self._steps: list[StepTrace] = []  # pokolenia krok po kroku trwającego przebiegu

        top = QSplitter(Qt.Orientation.Horizontal)
        top.addWidget(self.data_box)
        top.addWidget(self._build_params_column())
        top.setStretchFactor(0, 3)
        top.setStretchFactor(1, 2)
        bottom = QSplitter(Qt.Orientation.Horizontal)
        bottom.addWidget(self.results)
        bottom.addWidget(self.tabs)
        bottom.setStretchFactor(0, 2)
        bottom.setStretchFactor(1, 3)
        main = QSplitter(Qt.Orientation.Vertical)
        main.addWidget(top)
        main.addWidget(bottom)
        main.setStretchFactor(0, 2)
        main.setStretchFactor(1, 3)
        main.setChildrenCollapsible(False)
        # Przewijanie tylko wtedy, gdy ekran jest mniejszy niż minimalny rozmiar okna (np. skalowanie 150%).
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(main)
        self.setCentralWidget(scroll)
        self._build_menu()
        self._update_data_summary()

    # --- Budowa okna -------------------------------------------------------------------------------

    def _build_data_box(self) -> QGroupBox:
        self.capacity_edit = QLineEdit()
        self.capacity_edit.setPlaceholderText("np. 165")
        self.capacity_edit.setMaximumWidth(140)
        self.capacity_edit.textChanged.connect(self._on_capacity_changed)
        self.table = ItemsTable()
        self.table.items_changed.connect(self._update_data_summary)
        self.data_summary = QLabel()

        capacity_row = QHBoxLayout()
        capacity_row.addWidget(QLabel("Pojemność plecaka (W):"))
        capacity_row.addWidget(self.capacity_edit)
        capacity_row.addStretch()
        buttons = QHBoxLayout()
        for text, slot in (
            ("+ Dodaj", self.table.add_row),
            ("− Usuń", self.table.remove_selected_rows),
            ("Wyczyść", self.clear_items),
            ("Import…", self.open_import),
        ):
            button = QPushButton(text)
            button.clicked.connect(lambda _=False, handler=slot: handler())
            buttons.addWidget(button)
        buttons.addStretch()

        box = QGroupBox("Dane")
        layout = QVBoxLayout(box)
        layout.addLayout(capacity_row)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        layout.addWidget(self.data_summary)
        return box

    def _build_params_column(self) -> QWidget:
        """Parametry, przyciski Uruchom / Zatrzymaj i postęp (bieżące pokolenie)."""
        self.params_panel = ParamsPanel()
        self.run_button = QPushButton("▶ Uruchom")
        self.stop_button = QPushButton("■ Zatrzymaj")
        self.run_button.setStyleSheet("font-weight: 600; padding: 4px 16px;")
        self.stop_button.setEnabled(False)
        self.run_button.clicked.connect(self.start_run)
        self.stop_button.clicked.connect(self.stop_run)
        self.progress_label = QLabel()
        run_row = QHBoxLayout()
        run_row.addWidget(self.run_button)
        run_row.addWidget(self.stop_button)
        run_row.addWidget(self.progress_label, stretch=1)
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.params_panel)
        layout.addLayout(run_row)
        layout.addStretch()
        return column

    def _build_chart_page(self) -> QWidget:
        self.chart = FitnessChart()
        save_button = QPushButton("Zapisz wykres PNG…")
        save_button.clicked.connect(self.save_chart)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(save_button)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self.chart)
        layout.addLayout(buttons)
        return page

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&Plik")
        self.file_actions: list[QAction] = []
        for text, shortcut, slot in (
            ("Wczytaj plik…", QKeySequence.StandardKey.Open, self.open_file),
            ("Importuj z tekstu…", "Ctrl+I", self.open_import),
            ("Zapisz dane CSV…", QKeySequence.StandardKey.Save, self.save_data),
        ):
            action = menu.addAction(text)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(lambda _=False, handler=slot: handler())
            self.file_actions.append(action)
        menu.addAction("Zapisz wykres PNG…").triggered.connect(self.save_chart)
        menu.addSeparator()
        menu.addAction("Zakończ").triggered.connect(self.close)

    # --- Dane --------------------------------------------------------------------------------------

    def load_problem(self, problem: KnapsackProblem) -> None:
        """Wstawienie danych do tabeli i pola pojemności (np. ze zbioru przykładowego)."""
        self.apply_import(ParsedData(problem.items, problem.capacity), replace=True)

    def apply_import(self, data: ParsedData, replace: bool) -> None:
        self.table.set_items(data.items, append=not replace)
        if data.capacity is not None:
            self.capacity_edit.setText(format_number(data.capacity))
        self._forget_result()
        self.statusBar().showMessage(f"Wczytano przedmiotów: {len(data.items)}", 5000)

    def open_import(self, text: str | None = None) -> None:
        dialog = ImportDialog(self, start_dir=samples_dir())
        if text is not None:
            dialog.set_text(text)
        if dialog.exec() == ImportDialog.DialogCode.Accepted:
            self.apply_import(dialog.accepted_data(), dialog.replace_mode())

    def open_file(self, path: Path | None = None) -> None:
        """Wczytanie pliku: treść trafia do okna importu z podglądem."""
        if path is None:
            name, _ = QFileDialog.getOpenFileName(self, "Wczytaj plik z danymi", str(samples_dir()), FILE_FILTER)
            if not name:
                return
            path = Path(name)
        try:
            text = read_text_file(path)
        except OSError as error:
            self._warn("Błąd odczytu", f"Nie udało się odczytać pliku:\n{error}")
            return
        self.open_import(text)

    def save_data(self) -> None:
        problem = self.read_problem()
        if problem is None:
            return
        name, _ = QFileDialog.getSaveFileName(self, "Zapisz dane", str(samples_dir()), "CSV (*.csv)")
        if name:
            try:
                save_csv(Path(name), problem)
            except OSError as error:
                self._warn("Błąd zapisu", f"Nie udało się zapisać pliku:\n{error}")

    def clear_items(self) -> None:
        if self.table.rowCount() and self._confirm("Wyczyść", "Usunąć wszystkie przedmioty z tabeli?"):
            self.table.clear_items()
            self._forget_result()

    def read_problem(self) -> KnapsackProblem | None:
        """Dane z tabeli i pola pojemności; przy nieczytelnych liczbach — komunikat, podświetlenie i None."""
        problems: list[str] = []
        items = ()
        try:
            items = self.table.read_items()
        except DataFormatError as error:
            problems.append(str(error))
        capacity = 0.0
        text = self.capacity_edit.text().strip()
        try:
            capacity = parse_number(text, decimal_comma=True)
            self.capacity_edit.setStyleSheet("")
        except ValueError:
            self.capacity_edit.setStyleSheet(INVALID_STYLE)
            missing = "Podaj pojemność plecaka (liczba większa od 0)."
            problems.insert(0, f"Pojemność: »{text}« nie jest liczbą." if text else missing)
        if problems:
            self._warn("Błędne dane", "\n".join(problems))
            return None
        return KnapsackProblem(items, capacity)

    def _on_capacity_changed(self) -> None:
        self.capacity_edit.setStyleSheet("")
        self._update_data_summary()

    def _update_data_summary(self) -> None:
        count, total = self.table.summary()
        text = f"Przedmiotów: {count} · suma wag: {format_number(round(total, 6))}"
        try:
            capacity = parse_number(self.capacity_edit.text(), decimal_comma=True)
        except ValueError:
            capacity = None
        if capacity is not None and count and total <= capacity:
            text += " · suma wag ≤ pojemność — zmieszczą się wszystkie przedmioty"
        self.data_summary.setText(text)

    # --- Uruchomienie ------------------------------------------------------------------------------

    def start_run(self) -> None:
        if self._thread is not None:
            return
        problem = self.read_problem()
        if problem is None:
            return
        params = self.params_panel.get_params()
        report = validate_problem(problem)
        errors = list(report.errors) + validate_params(params)
        if errors:
            self._warn("Błędne dane", "\n".join(errors))
            return
        if report.warnings and not self._confirm("Ostrzeżenie", "\n".join(report.warnings) + "\n\nKontynuować?"):
            return

        self._forget_result()
        self._run_problem, self._run_params = problem, params
        self._set_running(True)
        self._thread = QThread(self)
        self._traces, self._steps = [], []
        self._worker = GAWorker(problem, params, record_selection=True, record_steps=True)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.selection.connect(self._on_selection)
        self._worker.steps.connect(self._on_steps)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def stop_run(self) -> None:
        if self._worker is not None:
            self._worker.request_stop()
            self.stop_button.setEnabled(False)
            self.progress_label.setText("Zatrzymywanie…")

    def _on_progress(self, batch: list[GenerationStats]) -> None:
        for stats in batch:
            self.chart.append(stats)
        last = batch[-1]
        self.progress_label.setText(f"Pokolenie {last.generation} · najlepszy: {format_number(last.best_so_far)}")

    def _on_selection(self, batch: list[SelectionTrace]) -> None:
        self._traces.extend(batch)  # koło ruletki dostaje losowania po zakończeniu przebiegu

    def _on_steps(self, batch: list[StepTrace]) -> None:
        self._steps.extend(batch)  # widok „Krok po kroku” dostaje pokolenia po zakończeniu przebiegu

    def _on_finished(self, result: GAResult) -> None:
        problem, params = self._run_problem, self._run_params
        self.chart.set_history(result.history)
        self.results.show_result(result, problem, params)
        self.roulette.set_traces(self._traces)
        self.steps_panel.set_traces(self._steps, problem, params)
        self._last = (result, problem)
        seconds = f"{result.elapsed_seconds:.2f} s"
        self.progress_label.setText(f"Zakończono po {result.generations_run} pokoleniach ({seconds})")
        self.run_finished.emit(result)

    def _on_failed(self, message: str) -> None:
        self.progress_label.setText("Błąd obliczeń")
        self._warn("Błąd obliczeń", message)

    def _on_thread_finished(self) -> None:
        self._worker.deleteLater()
        self._thread.deleteLater()
        self._worker = None
        self._thread = None
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        self.data_box.setEnabled(not running)
        self.params_panel.setEnabled(not running)
        self.run_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        for action in self.file_actions:
            action.setEnabled(not running)

    def is_running(self) -> bool:
        return self._thread is not None

    # --- Wynik -------------------------------------------------------------------------------------

    def compare_with_optimum(self) -> None:
        if self._last is None:
            return
        result, problem = self._last
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            solution = solve_exact(problem)
        except ValueError as error:
            QApplication.restoreOverrideCursor()
            self._warn("Optimum niedostępne", str(error))
            return
        QApplication.restoreOverrideCursor()
        self.results.show_exact(solution, result)
        self.chart.show_optimum(solution.total_value)

    def save_chart(self) -> None:
        name, _ = QFileDialog.getSaveFileName(self, "Zapisz wykres", "wykres.png", "PNG (*.png)")
        if name:
            try:
                self.chart.save_png(Path(name))
            except OSError as error:
                self._warn("Błąd zapisu", f"Nie udało się zapisać wykresu:\n{error}")

    def _forget_result(self) -> None:
        """Wynik dotyczy poprzednich danych — po zmianie danych lub przed nowym przebiegiem znika."""
        self._last = None
        self.results.clear()
        self.chart.reset()
        self.roulette.clear()
        self.steps_panel.clear()
        self.progress_label.clear()

    # --- Komunikaty i zamykanie --------------------------------------------------------------------

    def _warn(self, title: str, text: str) -> None:
        QMessageBox.warning(self, title, text)

    def _confirm(self, title: str, text: str) -> bool:
        answer = QMessageBox.question(self, title, text)
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event: QCloseEvent) -> None:
        """Zamknięcie okna w trakcie obliczeń: zatrzymanie algorytmu i zaczekanie na wątek."""
        if self._thread is not None and self._worker is not None:
            self._worker.request_stop()
            self._thread.quit()
            self._thread.wait(5000)
        event.accept()
