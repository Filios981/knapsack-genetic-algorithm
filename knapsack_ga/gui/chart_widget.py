"""Wykres przystosowania w kolejnych pokoleniach, osadzony przez matplotlib FigureCanvasQTAgg."""

from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QWidget

from knapsack_ga.data_io import format_number
from knapsack_ga.models import GenerationStats

# (pole GenerationStats, opis w legendzie, kolor, grubość linii w punktach); kolory domyślne matplotlib
SERIES = (
    ("best_so_far", "najlepszy znaleziony", "C0", 1.6),
    ("best", "najlepszy w pokoleniu", "C1", 1.0),
    ("mean", "średnia populacji", "C2", 1.0),
)
REDRAW_INTERVAL_MS = 250  # odrysowanie trwa ok. 60 ms — częściej zajmowałoby większość czasu okna


class FitnessChart(FigureCanvasQTAgg):
    """Serie: najlepszy znaleziony, najlepszy w pokoleniu, średnia populacji (w funkcji numeru pokolenia).

    `append(stats)` zbiera punkty w trakcie działania algorytmu, zegar odrysowuje wykres;
    `set_history(history)` rysuje pełny przebieg po zakończeniu, `show_optimum(value)` dodaje linię optimum.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Figure(figsize=(6, 3.5), layout="constrained"))
        self.setParent(parent)
        self.axes = self.figure.add_subplot()
        self._lines = {
            key: self.axes.plot([], [], color=color, linewidth=width, label=label, solid_joinstyle="round")[0]
            for key, label, color, width in SERIES
        }
        self._lines["best_so_far"].set_zorder(3)  # najważniejsza seria nad pozostałymi
        self._legend = None
        self._optimum_line = None
        self._generations: list[int] = []
        self._values: dict[str, list[float]] = {key: [] for key, *_ in SERIES}
        self._dirty = False
        self._style_axes()
        self._timer = QTimer(self)
        self._timer.setInterval(REDRAW_INTERVAL_MS)
        self._timer.timeout.connect(self._redraw_if_dirty)
        self._timer.start()

    def reset(self) -> None:
        self._generations.clear()
        for values in self._values.values():
            values.clear()
        if self._optimum_line is not None:
            self._optimum_line.remove()
            self._optimum_line = None
        for key, label, *_ in SERIES:
            self._lines[key].set_label(label)
        self._redraw(update_legend=True)

    def append(self, stats: GenerationStats) -> None:
        self._generations.append(stats.generation)
        for key in self._values:
            self._values[key].append(getattr(stats, key))
        self._dirty = True

    def set_history(self, history: tuple[GenerationStats, ...]) -> None:
        """Pełny przebieg po zakończeniu; w legendzie — wartości z ostatniego pokolenia."""
        self._generations[:] = [stats.generation for stats in history]
        for key, label, *_ in SERIES:
            self._values[key][:] = [getattr(stats, key) for stats in history]
            if history:
                self._lines[key].set_label(f"{label}: {format_number(round(getattr(history[-1], key), 2))}")
        self._redraw(update_legend=True)

    def show_optimum(self, value: float) -> None:
        if self._optimum_line is not None:
            self._optimum_line.remove()
        label = f"optimum (DP): {format_number(value)}"
        self._optimum_line = self.axes.axhline(value, color="gray", linewidth=1.0, linestyle="--", label=label)
        self._redraw(update_legend=True)

    def save_png(self, path: Path) -> None:
        self.figure.savefig(path, dpi=150)

    def _style_axes(self) -> None:
        axes = self.axes
        axes.set_xlabel("pokolenie")
        axes.set_ylabel("wartość plecaka")
        axes.grid(True, alpha=0.3)
        axes.tick_params(labelsize=8)
        axes.ticklabel_format(axis="y", style="plain", useOffset=False)

    def _redraw_if_dirty(self) -> None:
        if self._dirty:
            self._redraw()

    def _redraw(self, update_legend: bool = False) -> None:
        """Odrysowanie serii; legenda tworzona od nowa tylko po zmianie opisów (w trakcie przebiegu — nie)."""
        self._dirty = False
        for key, line in self._lines.items():
            line.set_data(self._generations, self._values[key])
        self.axes.relim()
        self.axes.autoscale_view()
        self.axes.set_xlim(0, max(1, self._generations[-1] if self._generations else 1))
        if update_legend or self._legend is None:
            if self._legend is not None:
                self._legend.remove()
            # Legenda nad wykresem — wewnątrz osi zasłaniałaby któryś z przebiegów.
            handles, labels = self.axes.get_legend_handles_labels()
            self._legend = self.figure.legend(
                handles, labels, loc="outside upper left", ncols=2, frameon=False, fontsize=8
            )
        self.draw_idle()
