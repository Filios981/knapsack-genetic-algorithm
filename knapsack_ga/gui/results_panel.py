"""Wynik: wybrane przedmioty, łączna wartość, waga plecaka, przebieg, porównanie z optimum."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from knapsack_ga.data_io import format_number
from knapsack_ga.exact import ExactSolution, can_solve_exact
from knapsack_ga.ga.fitness import WEIGHT_TOLERANCE
from knapsack_ga.models import GAParams, GAResult, Item, KnapsackProblem, StopReason

NO_EXACT_HINT = "Optimum jest liczone programowaniem dynamicznym tylko dla całkowitych wag i niezbyt dużej pojemności."


def stop_reason_text(reason: StopReason, params: GAParams) -> str:
    """Powód zatrzymania z faktycznymi wartościami limitów, np. „brak poprawy przez 500 pokoleń”."""
    if reason is StopReason.STAGNATION:
        return f"brak poprawy przez {params.stagnation_limit} pokoleń"
    if reason is StopReason.MAX_GENERATIONS:
        return f"osiągnięto limit {params.max_generations} pokoleń"
    return reason.value


class ResultsPanel(QGroupBox):
    """`show_result` po zakończeniu algorytmu, `show_exact` po porównaniu z optimum, `clear` przed startem."""

    compare_requested = pyqtSignal()  # przycisk „Porównaj z optimum (DP)”

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Wynik", parent)
        self.value_label = QLabel()
        self.value_label.setStyleSheet("font-size: 12pt; font-weight: 600;")
        self.weight_label = QLabel()
        self.weight_label.setStyleSheet("font-size: 12pt;")
        self.optimum_label = QLabel()
        self.run_label = QLabel()
        self.run_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.chromosome = QLineEdit()
        self.chromosome.setReadOnly(True)
        self.chromosome.setToolTip("Najlepszy osobnik: gen i = 1 — przedmiot i jest w plecaku.")
        self.compare_button = QPushButton("Porównaj z optimum (DP)")
        self.compare_button.clicked.connect(self.compare_requested)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(("Nr", "Nazwa", "Waga", "Wartość"))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(self.fontMetrics().height() + 8)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column, width in ((0, 50), (2, 80), (3, 80)):
            self.table.setColumnWidth(column, width)

        summary = QGridLayout()
        summary.addWidget(self.value_label, 0, 0)
        summary.addWidget(self.weight_label, 0, 1)
        summary.addWidget(self.optimum_label, 1, 0, 1, 2)
        summary.addWidget(self.run_label, 2, 0, 1, 2)
        chromosome_row = QGridLayout()
        chromosome_row.addWidget(QLabel("Chromosom:"), 0, 0)
        chromosome_row.addWidget(self.chromosome, 0, 1)
        chromosome_row.addWidget(self.compare_button, 0, 2)

        layout = QVBoxLayout(self)
        layout.addLayout(summary)
        layout.addLayout(chromosome_row)
        layout.addWidget(QLabel("Przedmioty w plecaku:"))
        layout.addWidget(self.table)
        self.clear()

    def clear(self) -> None:
        self.value_label.setText("Wartość plecaka: —")
        self.weight_label.setText("Waga plecaka: —")
        self.optimum_label.setText("Optimum (DP): —")
        self.run_label.setText("Uruchom algorytm, aby zobaczyć wynik.")
        self.chromosome.clear()
        self.table.setRowCount(0)
        self.compare_button.setEnabled(False)
        self.compare_button.setToolTip("")

    def show_result(self, result: GAResult, problem: KnapsackProblem, params: GAParams) -> None:
        self.value_label.setText(f"Wartość plecaka: {format_number(result.total_value)}")
        self.weight_label.setText(
            f"Waga plecaka: {format_number(result.total_weight)} / {format_number(problem.capacity)}"
        )
        self.optimum_label.setText("Optimum (DP): —")
        self.run_label.setText(  # krótkie wiersze bez zawijania — etykieta zachowuje wysokość na małym ekranie
            f"Znaleziono w pokoleniu {result.found_in_generation} z {result.generations_run} · "
            f"{params.mutation_method.value} · {params.repair_method.value}\n"
            f"Powód zatrzymania: {stop_reason_text(result.stop_reason, params)}\n"
            f"Czas: {result.elapsed_seconds:.2f} s · Ziarno: {result.seed} · "
            f"w plecaku {len(result.selected_items)} z {problem.size} przedmiotów"
        )
        self.chromosome.setText("".join(str(gene) for gene in result.chromosome))
        self.chromosome.setCursorPosition(0)
        self.chromosome.deselect()
        self._fill_table(result.selected_items)
        exact_available = can_solve_exact(problem)
        self.compare_button.setEnabled(exact_available)
        self.compare_button.setToolTip("" if exact_available else NO_EXACT_HINT)

    def show_exact(self, solution: ExactSolution, result: GAResult) -> None:
        optimum = format_number(solution.total_value)
        if result.total_value >= solution.total_value - WEIGHT_TOLERANCE:
            text = f"Optimum (DP): {optimum} ✔ — wynik algorytmu genetycznego jest optymalny"
        else:
            percent = 100 * result.total_value / solution.total_value
            missing = format_number(round(solution.total_value - result.total_value, 6))
            text = f"Optimum (DP): {optimum} — wynik to {percent:.1f}% optimum (brakuje {missing})"
        self.optimum_label.setText(text)

    def _fill_table(self, items: tuple[Item, ...]) -> None:
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            cells = (str(item.number), item.name, format_number(item.weight), format_number(item.value))
            for column, text in enumerate(cells):
                cell = QTableWidgetItem(text)
                if column != 1:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, cell)
