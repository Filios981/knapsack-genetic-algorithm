"""Edytowalna tabela przedmiotów: numer (tylko odczyt), nazwa (opcjonalna), waga, wartość.

Numery przedmiotów pochodzą z danych (np. kolumna „Nr” w imporcie) albo są nadawane kolejno; nowy wiersz
dostaje numer o 1 większy od największego, usunięcie wiersza nie zmienia numerów pozostałych — wynik
odwołuje się do tej samej numeracji co dane źródłowe.
"""

import contextlib
from collections.abc import Iterable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QKeyEvent
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem, QWidget

from knapsack_ga.data_io import DataFormatError, format_number, parse_number
from knapsack_ga.models import Item

COLUMNS = ("Nr", "Nazwa", "Waga", "Wartość")
NUMBER, NAME, WEIGHT, VALUE = range(len(COLUMNS))
INVALID_BRUSH = QBrush(QColor("#f6c9c9"))  # tło błędnej komórki


class ItemsTable(QTableWidget):
    """Tabela przedmiotów; liczby można wpisywać z kropką lub przecinkiem dziesiętnym."""

    items_changed = pyqtSignal()  # po każdej zmianie zawartości (podsumowanie pod tabelą)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, len(COLUMNS), parent)
        self.setHorizontalHeaderLabels(COLUMNS)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(NAME, QHeaderView.ResizeMode.Stretch)
        for column, width in ((NUMBER, 50), (WEIGHT, 80), (VALUE, 80)):
            self.setColumnWidth(column, width)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(self.fontMetrics().height() + 8)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.itemChanged.connect(self._on_item_changed)

    # --- Edycja ------------------------------------------------------------------------------------

    def add_row(self) -> int:
        """Pusty wiersz na końcu tabeli z kolejnym numerem; zwraca indeks wiersza."""
        row = self.rowCount()
        self._insert(row, Item(max(self._numbers(), default=0) + 1, 0, 0), empty=True)
        self.items_changed.emit()
        return row

    def remove_selected_rows(self) -> None:
        for row in sorted({index.row() for index in self.selectedIndexes()}, reverse=True):
            self.removeRow(row)
        self.items_changed.emit()

    def clear_items(self) -> None:
        self.setRowCount(0)
        self.items_changed.emit()

    def set_items(self, items: Iterable[Item], append: bool = False) -> None:
        """Wypełnienie tabeli; przy `append` przedmioty dopisywane są z kolejnymi numerami po istniejących."""
        if not append:
            self.setRowCount(0)
        next_number = max(self._numbers(), default=0) + 1
        for offset, item in enumerate(items):
            number = next_number + offset if append else item.number
            self._insert(self.rowCount(), Item(number, item.weight, item.value, item.name))
        self.items_changed.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Enter w ostatnim wierszu dodaje nowy wiersz (szybkie wpisywanie); w innym — przejście w dół."""
        enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        if enter and self.state() != QAbstractItemView.State.EditingState and self.rowCount() > 0:
            row = self.currentRow()
            if row == self.rowCount() - 1:
                self.setCurrentCell(self.add_row(), NAME)
            else:
                self.setCurrentCell(row + 1, max(self.currentColumn(), NAME))
            return
        super().keyPressEvent(event)

    # --- Odczyt ------------------------------------------------------------------------------------

    def read_items(self) -> tuple[Item, ...]:
        """Przedmioty z tabeli; całkowicie puste wiersze są pomijane.

        Komórki, których nie da się odczytać jako liczby, oraz wagi <= 0 i wartości < 0 są podświetlane.
        Gdy jakaś liczba jest nieczytelna — DataFormatError z numerem wiersza tabeli i nazwą kolumny.
        Zakresy sprawdza też validation.py (komunikaty z numerami przedmiotów).
        """
        self._clear_marks()
        items: list[Item] = []
        errors: list[str] = []
        for row in range(self.rowCount()):
            name, weight_text, value_text = (self._text(row, column) for column in (NAME, WEIGHT, VALUE))
            if not (name or weight_text or value_text):
                continue
            numbers: dict[int, float] = {}
            for column, text in ((WEIGHT, weight_text), (VALUE, value_text)):
                try:
                    numbers[column] = parse_number(text, decimal_comma=True)
                except ValueError:
                    self._mark(row, column)
                    shown = f"»{text}« nie jest liczbą" if text else "brak liczby"
                    errors.append(f"Wiersz {row + 1}, kolumna „{COLUMNS[column]}”: {shown}.")
            if len(numbers) < 2:
                continue
            if numbers[WEIGHT] <= 0:
                self._mark(row, WEIGHT)
            if numbers[VALUE] < 0:
                self._mark(row, VALUE)
            items.append(Item(int(self._text(row, NUMBER)), numbers[WEIGHT], numbers[VALUE], name))
        if errors:
            more = f"\n(oraz {len(errors) - 5} innych błędów)" if len(errors) > 5 else ""
            raise DataFormatError("\n".join(errors[:5]) + more)
        return tuple(items)

    def summary(self) -> tuple[int, float]:
        """Liczba wierszy z danymi i suma czytelnych wag — do paska pod tabelą (bez podświetlania błędów)."""
        count, total = 0, 0.0
        for row in range(self.rowCount()):
            texts = [self._text(row, column) for column in (NAME, WEIGHT, VALUE)]
            if any(texts):
                count += 1
                with contextlib.suppress(ValueError):  # nieczytelna waga — pomijana w sumie
                    total += parse_number(texts[1], decimal_comma=True)
        return count, total

    # --- Pomocnicze --------------------------------------------------------------------------------

    def _insert(self, row: int, item: Item, empty: bool = False) -> None:
        self.blockSignals(True)  # wypełnianie wiersza to nie edycja użytkownika
        self.insertRow(row)
        number = QTableWidgetItem(str(item.number))
        number.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.setItem(row, NUMBER, number)
        self.setItem(row, NAME, QTableWidgetItem(item.name))
        for column, value in ((WEIGHT, item.weight), (VALUE, item.value)):
            cell = QTableWidgetItem("" if empty else format_number(value))
            cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(row, column, cell)
        self.blockSignals(False)

    def _numbers(self) -> list[int]:
        return [int(self._text(row, NUMBER)) for row in range(self.rowCount())]

    def _text(self, row: int, column: int) -> str:
        cell = self.item(row, column)
        return cell.text().strip() if cell is not None else ""

    def _mark(self, row: int, column: int) -> None:
        self.blockSignals(True)
        self.item(row, column).setBackground(INVALID_BRUSH)
        self.blockSignals(False)

    def _clear_marks(self) -> None:
        self.blockSignals(True)
        for row in range(self.rowCount()):
            for column in (WEIGHT, VALUE):
                self.item(row, column).setBackground(QBrush())
        self.blockSignals(False)

    def _on_item_changed(self, cell: QTableWidgetItem) -> None:
        self.blockSignals(True)
        cell.setBackground(QBrush())  # poprawiona komórka traci podświetlenie
        self.blockSignals(False)
        self.items_changed.emit()

    def is_marked(self, row: int, column: int) -> bool:
        """Czy komórka jest podświetlona jako błędna (testy)."""
        return self.item(row, column).background() == INVALID_BRUSH
