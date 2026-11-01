"""Start aplikacji: QApplication i okno główne."""

import os
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from knapsack_ga.data_io import parse_items_text, read_text_file
from knapsack_ga.gui.main_window import MainWindow, samples_dir
from knapsack_ga.models import GAResult, KnapsackProblem

PREFERRED_SIZE = (1280, 800)  # rozmiar okna do zrzutów ekranu
AUTOTEST_SAMPLE = "p01-10-items.csv"  # optimum 309
AUTOTEST_OPTIMUM = 309
AUTOTEST_TIMEOUT_MS = 60_000


def main() -> int:
    """Tworzy QApplication, pokazuje MainWindow i uruchamia pętlę zdarzeń; zwraca kod wyjścia.

    Z opcją `--autotest` aplikacja sama sprawdza się na zbiorze p01-10-items.csv (sprawdzenie paczki .exe na innym
    komputerze): kod wyjścia 0 — wynik optymalny, 1 — inny wynik, 2 — brak wyniku w ciągu minuty.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Problem plecakowy")
    window = MainWindow()
    available = app.primaryScreen().availableGeometry()
    width, height = PREFERRED_SIZE
    if available.width() < width or available.height() < height:
        window.showMaximized()  # mały ekran lub duże skalowanie (projektor) — całe dostępne miejsce
    else:
        window.resize(width, height)
        window.show()
    if "--autotest" in sys.argv:
        _start_autotest(app, window)
    return app.exec()


def _start_autotest(app: QApplication, window: MainWindow) -> None:
    data = parse_items_text(read_text_file(samples_dir() / AUTOTEST_SAMPLE))
    window.load_problem(KnapsackProblem(data.items, data.capacity))
    window.params_panel.seed.setText("1")

    def finished(result: GAResult) -> None:
        app.exit(0 if result.total_value == AUTOTEST_OPTIMUM else 1)

    window.run_finished.connect(finished)
    QTimer.singleShot(0, window.start_run)
    QTimer.singleShot(AUTOTEST_TIMEOUT_MS, lambda: os._exit(2))  # także gdy okno komunikatu blokuje aplikację
