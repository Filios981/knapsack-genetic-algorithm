"""Okno importu z podglądem — wspólne dla wklejonego tekstu i wczytanego pliku.

Interpretację tekstu proponuje data_io (separator, przecinek dziesiętny, nagłówek, role kolumn, pojemność);
okno pokazuje ją w podglądzie i pozwala poprawić przed przyjęciem danych.
"""

from pathlib import Path

from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from knapsack_ga.data_io import (
    ColumnRole,
    DataFormatError,
    ParsedData,
    RawTable,
    build_items,
    extract_table,
    format_number,
    is_horizontal,
    parse_number,
    parse_two_lists,
    read_text_file,
    transpose,
)
from knapsack_ga.models import Item

NUMERIC_ROLES = (ColumnRole.NUMBER, ColumnRole.WEIGHT, ColumnRole.VALUE, ColumnRole.SKIP)
TEXT_ROLES = (ColumnRole.NAME, ColumnRole.SKIP)
MAX_PREVIEW_ROWS = 500  # więcej wierszy nie poprawia czytelności podglądu, a spowalnia jego odświeżanie
FILE_FILTER = "Pliki tekstowe (*.txt *.csv *.tsv *.dat);;Wszystkie pliki (*)"


def _role_combo(roles: tuple[ColumnRole, ...], current: ColumnRole) -> QComboBox:
    combo = QComboBox()
    for role in roles:
        combo.addItem(role.value, role)
    combo.setCurrentIndex(combo.findData(current))
    return combo


class ImportDialog(QDialog):
    """Tryby „jeden przedmiot w wierszu” / „dwie listy”; podgląd odświeżany po każdej zmianie.

    Korekty: rola każdej kolumny (Nr / Waga / Wartość / Pomiń) i tekstu (Nazwa / Pomiń), zamiana
    waga <-> wartość, transpozycja, przecinek dziesiętny (auto / tak / nie), proponowana pojemność.
    Przyciski przyjęcia danych są nieaktywne, dopóki są błędy. Po zamknięciu przyciskiem „Zastąp”
    lub „Dodaj” — `accepted_data()` i `replace_mode()`.
    """

    def __init__(self, parent: QWidget | None = None, start_dir: Path | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import danych")
        self.resize(1000, 620)
        self._start_dir = start_dir
        self._source: RawTable | None = None  # tabela z tekstu, przed ewentualną transpozycją
        self._table: RawTable | None = None  # tabela pokazana w podglądzie
        self._roles: list[ColumnRole] = []
        self._text_role = ColumnRole.SKIP
        self._items: tuple[Item, ...] | None = None
        self._capacity: float | None = None
        self._replace = True

        mode_row = self._build_mode_row()  # najpierw — reakcje na zmiany tekstu sprawdzają wybrany tryb
        splitter = QSplitter()
        splitter.addWidget(self._build_source_box())
        splitter.addWidget(self._build_preview_box())
        splitter.setSizes([420, 580])
        layout = QVBoxLayout(self)
        layout.addLayout(mode_row)
        layout.addWidget(splitter, stretch=1)
        layout.addLayout(self._build_accept_row())
        self.refresh()

    # --- Budowa okna -------------------------------------------------------------------------------

    def _build_mode_row(self) -> QHBoxLayout:
        self.rows_mode = QRadioButton("jeden przedmiot w wierszu")
        self.lists_mode = QRadioButton("dwie listy: wagi i wartości")
        self.rows_mode.setChecked(True)
        modes = QButtonGroup(self)
        modes.addButton(self.rows_mode)
        modes.addButton(self.lists_mode)
        self.rows_mode.toggled.connect(self._on_mode_changed)
        row = QHBoxLayout()
        row.addWidget(QLabel("Tryb:"))
        row.addWidget(self.rows_mode)
        row.addWidget(self.lists_mode)
        row.addStretch()
        return row

    def _build_source_box(self) -> QGroupBox:
        """Lewa część: tekst źródłowy (tryb „wiersze”) albo trzy pola list (tryb „dwie listy”)."""
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText(
            "Wklej dane w dowolnym układzie, np.:\nPojemność plecaka: 26\nnazwa;waga;wartość\nmapa;9;150\nkompas;13;35"
        )
        self.weights_edit = QPlainTextEdit()
        self.values_edit = QPlainTextEdit()
        self.names_edit = QPlainTextEdit()
        self.weights_edit.setPlaceholderText("np. w = [12, 7, 11, 8, 9]")
        self.values_edit.setPlaceholderText("np. 24 13 23 15 16")
        self.names_edit.setPlaceholderText("opcjonalnie: jedna nazwa w wierszu albo oddzielone średnikami")
        for edit in (self.text_edit, self.weights_edit, self.values_edit, self.names_edit):
            edit.textChanged.connect(self.refresh)

        load_button = QPushButton("Wczytaj plik…")
        load_button.clicked.connect(self._load_file)
        clear_button = QPushButton("Wyczyść")
        clear_button.clicked.connect(self._clear_text)

        rows_page = QWidget()
        rows_layout = QVBoxLayout(rows_page)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.addWidget(self.text_edit)
        lists_page = QWidget()
        lists_layout = QFormLayout(lists_page)
        lists_layout.setContentsMargins(0, 0, 0, 0)
        lists_layout.addRow("Wagi:", self.weights_edit)
        lists_layout.addRow("Wartości:", self.values_edit)
        lists_layout.addRow("Nazwy:", self.names_edit)
        self.source_pages = QStackedWidget()
        self.source_pages.addWidget(rows_page)
        self.source_pages.addWidget(lists_page)

        source_buttons = QHBoxLayout()
        source_buttons.addWidget(load_button)
        source_buttons.addWidget(clear_button)
        source_buttons.addStretch()
        source_box = QGroupBox("Tekst")
        source_layout = QVBoxLayout(source_box)
        source_layout.addWidget(self.source_pages)
        source_layout.addLayout(source_buttons)
        return source_box

    def _build_preview_box(self) -> QGroupBox:
        """Prawa część: pojemność, podgląd z rolami kolumn, korekty i podsumowanie."""
        self.capacity_edit = QLineEdit()
        self.capacity_edit.setMinimumWidth(self.fontMetrics().horizontalAdvance("0") * 12)
        self.capacity_edit.textChanged.connect(self._rebuild)
        self.capacity_info = QLabel()
        self.capacity_info.setWordWrap(True)
        self.preview = QTableWidget()
        self.preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.swap_button = QPushButton("⇄ Zamień waga/wartość")
        self.swap_button.clicked.connect(self.swap_weight_value)
        self.transpose_button = QPushButton("Transponuj")
        self.transpose_button.setCheckable(True)
        self.transpose_button.setToolTip("Dla danych ułożonych poziomo: wiersz wag i wiersz wartości.")
        self.transpose_button.toggled.connect(self._apply_table)
        self.decimal_combo = QComboBox()
        for label, value in (("auto", None), ("tak", True), ("nie", False)):
            self.decimal_combo.addItem(label, value)
        self.decimal_combo.currentIndexChanged.connect(self.refresh)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)

        capacity_row = QHBoxLayout()
        capacity_row.addWidget(QLabel("Pojemność:"))
        capacity_row.addWidget(self.capacity_edit)
        capacity_row.addWidget(self.capacity_info, stretch=1)
        corrections = QHBoxLayout()
        corrections.addWidget(self.swap_button)
        corrections.addWidget(self.transpose_button)
        corrections.addStretch()
        corrections.addWidget(QLabel("Przecinek dziesiętny:"))
        corrections.addWidget(self.decimal_combo)
        preview_box = QGroupBox("Podgląd")
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.addLayout(capacity_row)
        preview_layout.addWidget(self.preview)
        preview_layout.addLayout(corrections)
        preview_layout.addWidget(self.summary_label)
        return preview_box

    def _build_accept_row(self) -> QHBoxLayout:
        self.replace_button = QPushButton("Zastąp dane w tabeli")
        self.append_button = QPushButton("Dodaj do tabeli")
        cancel_button = QPushButton("Anuluj")
        self.replace_button.clicked.connect(lambda: self._accept(replace=True))
        self.append_button.clicked.connect(lambda: self._accept(replace=False))
        cancel_button.clicked.connect(self.reject)
        self.replace_button.setDefault(True)
        accept_row = QHBoxLayout()
        accept_row.addStretch()
        for button in (self.replace_button, self.append_button, cancel_button):
            accept_row.addWidget(button)
        return accept_row

    # --- Interfejs dla okna głównego i testów --------------------------------------------------------

    def set_text(self, text: str) -> None:
        self.rows_mode.setChecked(True)
        self.text_edit.setPlainText(text)

    def accepted_data(self) -> ParsedData:
        if self._items is None:
            raise DataFormatError("Brak poprawnych danych do przyjęcia.")
        return ParsedData(self._items, self._capacity)

    def replace_mode(self) -> bool:
        return self._replace

    def roles(self) -> tuple[ColumnRole, ...]:
        return tuple(self._roles)

    def set_role(self, column: int, role: ColumnRole) -> None:
        """Zmiana roli kolumny liczbowej (jak wybór z listy nad kolumną podglądu)."""
        self._roles[column] = role
        self._fill_preview()
        self._rebuild()

    def can_accept(self) -> bool:
        return self.replace_button.isEnabled()

    # --- Odświeżanie -------------------------------------------------------------------------------

    def refresh(self) -> None:
        """Ponowna analiza tekstu źródłowego (zmiana tekstu, trybu lub ustawienia przecinka)."""
        if self.lists_mode.isChecked():
            self._source = None
            self._table = None
            self._rebuild()
            return
        text = self.text_edit.toPlainText()
        self._source = None
        if text.strip():
            try:
                self._source = extract_table(text, self.decimal_combo.currentData())
            except DataFormatError as error:
                self._show_error(str(error))
        if self._source is None:
            self._table = None
            self.preview.clear()
            self.preview.setRowCount(0)
            self.preview.setColumnCount(0)
            if not text.strip():
                self._show_error("Wklej dane albo wczytaj plik.", mark="")
            return
        if self._source.capacity is not None:
            self.capacity_edit.setText(format_number(self._source.capacity))
            if self._source.count_line is not None:
                self.capacity_info.setText(
                    f"(wiersz {self._source.count_line} to „liczba przedmiotów, pojemność”; "
                    "dalej „wartość waga” — sprawdź role)"
                )
            else:
                self.capacity_info.setText("(znaleziona w tekście)")
        elif not self.capacity_edit.text().strip():
            self.capacity_info.setText("(nie znaleziono — wpisz albo zostaw pustą)")
        self.transpose_button.blockSignals(True)
        self.transpose_button.setChecked(is_horizontal(self._source))  # dane poziome — propozycja transpozycji
        self.transpose_button.blockSignals(False)
        self._apply_table()

    def _apply_table(self) -> None:
        """Tabela do podglądu (po ewentualnej transpozycji) i proponowane role kolumn."""
        if self._source is None:
            return
        table = transpose(self._source) if self.transpose_button.isChecked() else self._source
        self._table = table
        self._roles = list(table.roles) if table.roles else [ColumnRole.SKIP] * table.column_count
        self._text_role = table.text_role
        self._fill_preview()
        self._rebuild()

    def _fill_preview(self) -> None:
        """Wiersz 0 — listy ról nad kolumnami; dalej dane (tekst wiersza i kolumny liczbowe)."""
        table = self._table
        if table is None:
            return
        has_text = any(row.text for row in table.rows)
        offset = 1 if has_text else 0
        rows = table.rows[:MAX_PREVIEW_ROWS]
        self.preview.clear()
        self.preview.setColumnCount(offset + table.column_count)
        self.preview.setRowCount(1 + len(rows))
        names = table.header or tuple(f"Kolumna {index + 1}" for index in range(table.column_count))
        self.preview.setHorizontalHeaderLabels((("Tekst",) if has_text else ()) + tuple(names))
        self.preview.setVerticalHeaderLabels(["Rola"] + [str(row.line_number) for row in rows])
        if has_text:
            text_combo = _role_combo(TEXT_ROLES, self._text_role)
            text_combo.currentIndexChanged.connect(lambda _, combo=text_combo: self._on_text_role(combo))
            self.preview.setCellWidget(0, 0, text_combo)
        for column, role in enumerate(self._roles):
            combo = _role_combo(NUMERIC_ROLES, role)
            combo.currentIndexChanged.connect(lambda _, index=column, box=combo: self._on_role(index, box))
            self.preview.setCellWidget(0, offset + column, combo)
        for row_index, row in enumerate(rows, start=1):
            if has_text:
                self.preview.setItem(row_index, 0, QTableWidgetItem(row.text or ""))
            for column, number in enumerate(row.numbers):
                self.preview.setItem(row_index, offset + column, QTableWidgetItem(format_number(number)))
        self.preview.resizeColumnsToContents()

    def _rebuild(self) -> None:
        """Budowa przedmiotów według bieżących ustawień; podsumowanie i blokada przycisków przy błędach."""
        self._items = None
        try:
            items = self._build_items()
            self._capacity = self._read_capacity()
        except DataFormatError as error:
            self._show_error(str(error))
            return
        if items is None:
            return
        self._items = items
        total = sum(item.weight for item in items)
        capacity = format_number(self._capacity) if self._capacity is not None else "nie podano (bez zmian w oknie)"
        self.summary_label.setText(
            f"✔ Przedmiotów: {len(items)} · suma wag: {format_number(round(total, 6))} · pojemność: {capacity}"
        )
        self._set_accept_enabled(True)

    def _build_items(self) -> tuple[Item, ...] | None:
        if self.lists_mode.isChecked():
            if not (self.weights_edit.toPlainText().strip() or self.values_edit.toPlainText().strip()):
                self._show_error("Wklej listę wag i listę wartości.", mark="")
                return None
            items = parse_two_lists(
                self.weights_edit.toPlainText(),
                self.values_edit.toPlainText(),
                self.names_edit.toPlainText(),
                decimal_comma=bool(self.decimal_combo.currentData()),
            )
            self._fill_lists_preview(items)
            return items
        if self._table is None:
            return None
        return build_items(self._table, tuple(self._roles), use_names=self._text_role is ColumnRole.NAME)

    def _fill_lists_preview(self, items: tuple[Item, ...]) -> None:
        self.preview.clear()
        self.preview.setColumnCount(4)
        self.preview.setRowCount(min(len(items), MAX_PREVIEW_ROWS))
        self.preview.setHorizontalHeaderLabels(("Nr", "Nazwa", "Waga", "Wartość"))
        for row, item in enumerate(items[:MAX_PREVIEW_ROWS]):
            cells = (str(item.number), item.name, format_number(item.weight), format_number(item.value))
            for column, text in enumerate(cells):
                self.preview.setItem(row, column, QTableWidgetItem(text))

    def _read_capacity(self) -> float | None:
        text = self.capacity_edit.text().strip()
        if not text:
            return None
        try:
            return parse_number(text, decimal_comma=True)
        except ValueError:
            raise DataFormatError(f"Pojemność: »{text}« nie jest liczbą.") from None

    # --- Reakcje na korekty --------------------------------------------------------------------------

    def swap_weight_value(self) -> None:
        if self.lists_mode.isChecked():
            weights = self.weights_edit.toPlainText()
            self.weights_edit.setPlainText(self.values_edit.toPlainText())
            self.values_edit.setPlainText(weights)
            return
        if ColumnRole.WEIGHT in self._roles and ColumnRole.VALUE in self._roles:
            weight, value = self._roles.index(ColumnRole.WEIGHT), self._roles.index(ColumnRole.VALUE)
            self._roles[weight], self._roles[value] = ColumnRole.VALUE, ColumnRole.WEIGHT
            self._fill_preview()
            self._rebuild()

    def _on_role(self, column: int, combo: QComboBox) -> None:
        self._roles[column] = combo.currentData()
        self._rebuild()

    def _on_text_role(self, combo: QComboBox) -> None:
        self._text_role = combo.currentData()
        self._rebuild()

    def _on_mode_changed(self) -> None:
        lists = self.lists_mode.isChecked()
        self.source_pages.setCurrentIndex(1 if lists else 0)
        self.transpose_button.setEnabled(not lists)
        self.refresh()

    def _show_error(self, message: str, mark: str = "✗ ") -> None:
        self._items = None
        self.summary_label.setText(mark + message)
        self._set_accept_enabled(False)

    def _set_accept_enabled(self, enabled: bool) -> None:
        self.replace_button.setEnabled(enabled)
        self.append_button.setEnabled(enabled)

    def _accept(self, replace: bool) -> None:
        self._replace = replace
        self.accept()

    def _load_file(self) -> None:
        start = str(self._start_dir) if self._start_dir else ""
        path, _ = QFileDialog.getOpenFileName(self, "Wczytaj plik z danymi", start, FILE_FILTER)
        if path:
            try:
                self.set_text(read_text_file(Path(path)))
            except OSError as error:
                QMessageBox.warning(self, "Błąd odczytu", f"Nie udało się odczytać pliku:\n{error}")

    def _clear_text(self) -> None:
        for edit in (self.text_edit, self.weights_edit, self.values_edit, self.names_edit):
            edit.clear()
        self.capacity_edit.clear()
        self.capacity_info.clear()
