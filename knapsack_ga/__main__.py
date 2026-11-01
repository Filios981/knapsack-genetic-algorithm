"""Punkt startowy: ``python -m knapsack_ga`` uruchamia interfejs graficzny."""

import multiprocessing
import sys

if __name__ == "__main__":
    # Proces obliczeń w paczce .exe uruchamia ten sam plik — freeze_support obsługuje ten przypadek.
    multiprocessing.freeze_support()
    # Import wewnątrz bloku: proces obliczeń wczytuje ten moduł ponownie i nie powinien ładować PyQt6.
    from knapsack_ga.gui.app import main

    sys.exit(main())
