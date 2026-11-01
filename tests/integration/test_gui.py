"""Testy interfejsu PyQt6 oraz elementów okna: tabela, parametry, wykres, koło ruletki."""

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QMessageBox

from knapsack_ga.data_io import ColumnRole, DataFormatError, read_text_file
from knapsack_ga.gui.chart_widget import FitnessChart
from knapsack_ga.gui.import_dialog import ImportDialog
from knapsack_ga.gui.items_table import NAME, VALUE, WEIGHT, ItemsTable
from knapsack_ga.gui.main_window import MainWindow, samples_dir
from knapsack_ga.gui.params_panel import ParamsPanel
from knapsack_ga.gui.roulette_widget import FULL_TURNS, RoulettePanel, wheel_angle
from knapsack_ga.models import GAParams, GenerationStats, Item, RepairMethod, SelectionTrace, StopReason

SAMPLES = Path(__file__).resolve().parent.parent.parent / "samples"


@pytest.fixture
def messages(monkeypatch):
    """Okna komunikatów zastąpione zapisem treści; pytanie „Kontynuować?” — odpowiedź „Tak”."""
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: shown.append(text))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    return shown


@pytest.fixture
def window(qtbot, messages):
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    return main_window


def accept_dialog_automatically(monkeypatch) -> None:
    """Okno importu „zatwierdzone” bez wyświetlania — przyjmuje dane w zaproponowanej interpretacji."""
    monkeypatch.setattr(ImportDialog, "exec", lambda _self: QDialog.DialogCode.Accepted)


def run_and_wait(qtbot, window: MainWindow):
    with qtbot.waitSignal(window.run_finished, timeout=20000) as signal:
        window.start_run()
    qtbot.waitUntil(lambda: not window.is_running(), timeout=5000)
    return signal.args[0]


# --- Wczytanie pliku, uruchomienie, wynik ----------------------------------------------------------


def test_file_to_result_and_optimum(qtbot, window, monkeypatch):
    accept_dialog_automatically(monkeypatch)
    window.open_file(SAMPLES / "p01-10-items.csv")
    assert window.table.rowCount() == 10
    assert window.capacity_edit.text() == "165"

    window.params_panel.seed.setText("1")
    result = run_and_wait(qtbot, window)

    numbers = [int(window.results.table.item(row, 0).text()) for row in range(window.results.table.rowCount())]
    assert numbers == [1, 2, 3, 4, 6]
    assert result.total_value == 309
    assert "309" in window.results.value_label.text()
    assert "165 / 165" in window.results.weight_label.text()
    assert window.results.compare_button.isEnabled()

    window.compare_with_optimum()
    assert "309 ✔" in window.results.optimum_label.text()


def test_fractional_weights_disable_optimum_comparison(qtbot, window, monkeypatch):
    accept_dialog_automatically(monkeypatch)
    window.open_file(SAMPLES / "format-polish-excel.csv")
    run_and_wait(qtbot, window)
    assert not window.results.compare_button.isEnabled()
    assert window.results.compare_button.toolTip()


# --- Błędne dane ------------------------------------------------------------------------------------


def test_invalid_cell_is_reported_and_highlighted(qtbot, window, messages, monkeypatch):
    accept_dialog_automatically(monkeypatch)
    window.open_file(SAMPLES / "p01-10-items.csv")
    window.table.item(2, WEIGHT).setText("abc")

    window.start_run()

    assert not window.is_running()
    assert "Wiersz 3" in messages[-1] and "»abc«" in messages[-1]
    assert window.table.is_marked(2, WEIGHT)
    window.table.item(2, WEIGHT).setText("29")
    assert not window.table.is_marked(2, WEIGHT)  # poprawa komórki usuwa podświetlenie


def test_out_of_range_values_and_missing_capacity(window, messages):
    window.table.set_items([Item(1, 0, 5), Item(2, 3, -1)])
    window.start_run()
    assert "pojemność" in messages[-1].lower()

    window.capacity_edit.setText("10")
    window.start_run()
    assert "Przedmiot 1: waga musi być większa od 0" in messages[-1]
    assert "Przedmiot 2: wartość nie może być ujemna" in messages[-1]
    assert window.table.is_marked(0, WEIGHT)
    assert window.table.is_marked(1, VALUE)
    assert not window.is_running()


# --- Zatrzymanie ------------------------------------------------------------------------------------


def test_stop_returns_best_so_far_with_cancelled_reason(qtbot, window, monkeypatch):
    accept_dialog_automatically(monkeypatch)
    window.open_file(SAMPLES / "random-100-items.csv")
    window.params_panel.max_generations.setValue(1_000_000)
    window.params_panel.stagnation.setValue(1_000_000)

    with qtbot.waitSignal(window.run_finished, timeout=20000) as signal:
        window.start_run()
        assert window.is_running()
        assert not window.params_panel.isEnabled()  # parametry zablokowane na czas obliczeń
        qtbot.waitUntil(lambda: window.progress_label.text().startswith("Pokolenie"), timeout=5000)
        window.stop_run()
    qtbot.waitUntil(lambda: not window.is_running(), timeout=5000)

    result = signal.args[0]
    assert result.stop_reason is StopReason.CANCELLED
    assert result.generations_run < 1_000_000
    assert "przerwane przez użytkownika" in window.results.run_label.text()
    assert window.params_panel.isEnabled()


# --- Okno importu -----------------------------------------------------------------------------------


def test_import_dialog_roles_swap_and_append(qtbot, window):
    dialog = ImportDialog()
    qtbot.addWidget(dialog)
    dialog.set_text(read_text_file(SAMPLES / "format-text-with-units.txt"))

    assert dialog.roles() == (ColumnRole.NUMBER, ColumnRole.VALUE, ColumnRole.WEIGHT)  # ze słów przy liczbach
    assert dialog.capacity_edit.text() == "26"
    assert dialog.can_accept()
    assert [item.weight for item in dialog.accepted_data().items] == [12, 7, 11, 8, 9]

    dialog.swap_weight_value()
    assert [item.weight for item in dialog.accepted_data().items] == [24, 13, 23, 15, 16]
    dialog.swap_weight_value()

    dialog.set_role(0, ColumnRole.SKIP)  # bez kolumny „Nr” — numery kolejne
    dialog.set_role(1, ColumnRole.SKIP)
    assert not dialog.can_accept()  # brak kolumny „Wartość”
    assert dialog.summary_label.text().startswith("✗")
    dialog.set_role(1, ColumnRole.VALUE)
    assert dialog.can_accept()

    dialog.append_button.click()
    assert not dialog.replace_mode()
    window.table.set_items([Item(1, 5, 5), Item(2, 6, 6)])
    window.apply_import(dialog.accepted_data(), dialog.replace_mode())
    assert window.table.rowCount() == 7
    assert [window.table.item(row, 0).text() for row in range(7)] == ["1", "2", "3", "4", "5", "6", "7"]


def test_import_dialog_transposes_horizontal_data(qtbot):
    dialog = ImportDialog()
    qtbot.addWidget(dialog)
    dialog.set_text(read_text_file(SAMPLES / "format-horizontal.txt"))

    assert dialog.transpose_button.isChecked()  # dane poziome — transpozycja zaproponowana automatycznie
    data = dialog.accepted_data()
    assert [(item.weight, item.value) for item in data.items][:2] == [(12, 24), (7, 13)]
    assert data.capacity == 26

    dialog.transpose_button.setChecked(False)
    assert not dialog.can_accept()  # bez transpozycji: 2 wiersze po 5 liczb — role nieustalone


def test_import_dialog_blocks_acceptance_on_errors(qtbot):
    dialog = ImportDialog()
    qtbot.addWidget(dialog)
    dialog.set_text("12;24\n7;13;5\n")
    assert not dialog.can_accept()
    assert "Wiersz 2" in dialog.summary_label.text()
    with pytest.raises(DataFormatError):
        dialog.accepted_data()

    dialog.set_text("12;24\n7;13\n")
    dialog.capacity_edit.setText("abc")
    assert not dialog.can_accept()
    dialog.capacity_edit.setText("15,5")
    assert dialog.can_accept()
    assert dialog.accepted_data().capacity == 15.5


def test_import_dialog_two_lists_mode(qtbot):
    dialog = ImportDialog()
    qtbot.addWidget(dialog)
    dialog.lists_mode.setChecked(True)
    dialog.weights_edit.setPlainText("w = [12, 7, 11]")
    dialog.values_edit.setPlainText("24 13")
    assert not dialog.can_accept()
    assert "różną długość" in dialog.summary_label.text()

    dialog.values_edit.setPlainText("24 13 23")
    dialog.names_edit.setPlainText("mapa; kompas; woda")
    assert dialog.can_accept()
    assert [item.name for item in dialog.accepted_data().items] == ["mapa", "kompas", "woda"]
    assert dialog.preview.rowCount() == 3


# --- Tabela przedmiotów, parametry, wykres ----------------------------------------------------------


def test_items_table_numbering_and_reading(qtbot):
    table = ItemsTable()
    qtbot.addWidget(table)
    table.set_items([Item(3, 12, 24, "mapa"), Item(7, 7, 13)])
    row = table.add_row()
    assert table.item(row, 0).text() == "8"  # kolejny numer po największym

    table.item(row, WEIGHT).setText("2,5")  # przecinek dziesiętny
    table.item(row, VALUE).setText("4")
    table.add_row()  # pusty wiersz — pomijany przy odczycie
    items = table.read_items()
    assert [item.number for item in items] == [3, 7, 8]
    assert items[2].weight == 2.5
    assert items[0].name == "mapa"
    assert table.summary() == (3, 21.5)

    table.selectRow(0)
    table.remove_selected_rows()
    assert [table.item(r, 0).text() for r in range(table.rowCount())] == ["7", "8", "9"]  # bez przenumerowania


def test_enter_in_last_row_adds_row(qtbot):
    table = ItemsTable()
    qtbot.addWidget(table)
    table.set_items([Item(1, 1, 1)])
    table.setCurrentCell(0, NAME)
    qtbot.keyClick(table, Qt.Key.Key_Return)
    assert table.rowCount() == 2
    assert table.currentRow() == 1


def test_params_panel_defaults_and_values(qtbot):
    panel = ParamsPanel()
    qtbot.addWidget(panel)
    assert panel.get_params() == GAParams()

    panel.mutation.lineEdit().setText("0,05")  # przecinek dziesiętny
    panel.mutation.interpretText()
    panel.repair.setCurrentIndex(panel.repair.findData(RepairMethod.RANDOM))
    panel.seed.setText("42")
    params = panel.get_params()
    assert params.mutation_prob == pytest.approx(0.05)
    assert params.repair_method is RepairMethod.RANDOM
    assert params.seed == 42

    panel.restore_defaults()
    assert panel.get_params() == GAParams()


def test_chart_series_optimum_and_png(qtbot, tmp_path):
    chart = FitnessChart()
    qtbot.addWidget(chart)
    history = tuple(GenerationStats(g, 10 + g, 5 + g, 1, 10 + g) for g in range(5))
    for stats in history:
        chart.append(stats)
    chart.set_history(history)
    chart.show_optimum(20)
    chart.save_png(tmp_path / "wykres.png")

    assert (tmp_path / "wykres.png").stat().st_size > 0
    labels = [text.get_text() for text in chart.figure.legends[0].get_texts()]
    assert "najlepszy znaleziony: 14" in labels
    assert "optimum (DP): 20" in labels
    chart.reset()
    assert not chart.figure.legends[0].get_texts()[-1].get_text().startswith("optimum")


def test_samples_dir_exists():
    assert (samples_dir() / "p01-10-items.csv").exists()


# --- Koło ruletki ----------------------------------------------------------------------------------


def roulette_traces() -> list[SelectionTrace]:
    """Dwa pokolenia po N = 3 losowania; w pokoleniu 1 wszystkie przystosowania 0."""
    return [
        SelectionTrace(0, (51.0, 40.0, 39.0), (103.5, 0.0, 60.0), (2, 0, 1)),
        SelectionTrace(1, (0.0, 0.0, 0.0), (2.5, 0.4, 1.0), (2, 0, 1)),
    ]


def test_roulette_spins_land_on_recorded_selection(qtbot):
    panel = RoulettePanel()
    qtbot.addWidget(panel)
    assert not panel.spin_button.isEnabled()  # przed przebiegiem — brak danych

    panel.set_traces(roulette_traces())
    assert panel.generation.maximum() == 1
    assert "Σf = 130" in panel.generation_info.text()
    panel.speed.setValue(panel.speed.maximum())

    with qtbot.waitSignal(panel.wheel.spin_finished, timeout=5000):
        panel.spin_once()
    assert panel.selected_so_far() == [2]
    assert panel.wheel.highlighted == 2
    assert panel.wheel.angle == pytest.approx(wheel_angle(103.5, 130) + 360 * FULL_TURNS)
    assert "osobnik 3: f = 39, p = 30.00% (wycinek 70.00–100.00)" in panel.pick_label.text()
    assert "Wylosowana liczba: 79.62 z [0, 100)" in panel.draw_label.text()
    assert panel.parents_list.item(0).text().startswith("1. liczba 79.62 → osobnik 3")

    panel.skip_animation()
    assert panel.selected_so_far() == [2, 0, 1]
    assert panel.parents_list.count() == 3
    assert "bez pary" in panel.parents_list.item(2).text()  # N nieparzyste — ostatni rodzic kopiowany
    assert not panel.spin_button.isEnabled()

    panel.generation.setValue(1)  # Σf = 0 — równe wycinki, r z [0, N)
    assert panel.selected_so_far() == []
    assert "losowanie równomierne" in panel.generation_info.text()
    panel.spin_all()
    qtbot.waitUntil(lambda: len(panel.selected_so_far()) == 3, timeout=10000)
    assert panel.wheel.angle % 360 == pytest.approx(wheel_angle(1.0, 3))

    panel.restart_button.click()
    assert panel.parents_list.count() == 0
    panel.clear()
    assert not panel.generation.isEnabled()


def test_roulette_tab_receives_selection_of_the_run(qtbot, window, monkeypatch):
    accept_dialog_automatically(monkeypatch)
    window.open_file(SAMPLES / "p01-10-items.csv")
    window.params_panel.seed.setText("1")
    result = run_and_wait(qtbot, window)

    assert window.roulette.generation.maximum() == result.generations_run - 1  # koło z pokoleń 0 … G-1
    window.roulette.skip_animation()
    assert len(window.roulette.selected_so_far()) == GAParams().population_size

    window.load_problem(window.read_problem())  # zmiana danych — wynik i koło znikają
    assert not window.roulette.generation.isEnabled()


# --- Widok „Krok po kroku” -------------------------------------------------------------------------


def test_steps_tab_shows_generations_of_the_run(qtbot, window, monkeypatch):
    accept_dialog_automatically(monkeypatch)
    window.open_file(SAMPLES / "p02-5-items.csv")
    window.params_panel.population.setValue(8)  # jak przykład z zajęć
    window.params_panel.seed.setText("3")
    result = run_and_wait(qtbot, window)

    panel = window.steps_panel
    assert panel.generation.maximum() == result.generations_run - 1
    assert "Pokolenie 0 → 1" in panel.html()
    panel.generation.setValue(5)
    assert "Pokolenie 5 → 6" in panel.html()
    assert "Pokolenie 5" in panel.view.toPlainText()
    assert "Pula rodzicielska" in panel.html()

    window.load_problem(window.read_problem())  # zmiana danych — widok czyszczony
    assert not panel.generation.isEnabled()
