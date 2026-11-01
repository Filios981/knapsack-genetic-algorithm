"""Animacja koła ruletki odtwarzająca rzeczywiste losowania selekcji.

Koło nie losuje od nowa: obraca się do punktu r zapisanego przez algorytm (SelectionTrace), więc
zatrzymuje się na tym osobniku, którego wybrała selekcja w danym pokoleniu.
"""

import math

from PyQt6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from knapsack_ga.data_io import format_number
from knapsack_ga.ga.selection import cumulative_sums
from knapsack_ga.ga.selection import wheel_widths as slice_widths
from knapsack_ga.models import SelectionTrace

# Wycinki na przemian w dwóch odcieniach niebieskiego — numer osobnika podaje etykieta, nie kolor;
# wylosowany osobnik wyróżniony pomarańczowym.
SLICE_COLORS = (QColor("lightblue"), QColor("skyblue"))
SELECTED_COLOR = QColor("orange")
LABEL_COLOR = QColor("black")
GAP_WIDTH = 2  # szczelina między wycinkami w kolorze tła
HUB_RATIO = 0.22  # promień piasty (środka koła w kolorze tła) względem promienia koła
NUMBER_MIN_DEGREES = 9.0  # numer osobnika tylko na wycinkach co najmniej tak szerokich
VALUE_MIN_DEGREES = 20.0  # numer i przystosowanie
BOUNDARY_LABELS_MAX = 20  # podpisy granic w procentach tylko przy małej populacji (np. N = 8–10)
BOUNDARY_MIN_DEGREES = 12.0  # najmniejszy odstęp między podpisami granic
POINTER_CLEARANCE_DEGREES = 6.0  # bez podpisu tuż pod wskaźnikiem

FULL_TURNS = 3  # pełne obroty przed zatrzymaniem („Zakręć raz”, pierwszy obrót „Zakręć wszystkie”)
SPEED_DURATIONS_MS = (4000, 2800, 2000, 1200, 600)  # suwak szybkości 1–5; domyślnie 3 — ok. 2 s
SPEEDUP = 0.8  # „Zakręć wszystkie”: każdy kolejny obrót krótszy o 20%…
MIN_DURATION_MS = 250  # …ale nie krótszy niż 0,25 s


def slice_bounds(fitnesses: tuple[float, ...]) -> list[tuple[float, float]]:
    """Granice wycinków w stopniach, liczone od wskaźnika zgodnie z ruchem wskazówek zegara.

    Osobnik j zajmuje [360 * S_(j-1) / S_N, 360 * S_j / S_N) — te same sumy skumulowane co w selekcji
    (ga/selection.py), więc punkt r leży w wycinku osobnika wybranego dla tego r.
    """
    cumulative = cumulative_sums(slice_widths(fitnesses))
    total = cumulative[-1]
    starts = [0.0, *cumulative[:-1]]
    return [(360.0 * start / total, 360.0 * end / total) for start, end in zip(starts, cumulative, strict=True)]


def boundary_labels(bounds: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Podpisy granic wycinków: (kąt w stopniach, skumulowany procent koła) na końcu każdego wycinka.

    Jak na kole ruletki z zajęć: granica osobnika j to 100 * S_j / S_N, ostatnia — 100. Tylko przy co
    najwyżej BOUNDARY_LABELS_MAX niepustych wycinkach; podpis bliższy niż BOUNDARY_MIN_DEGREES od
    poprzedniego jest pomijany (nakładałyby się).
    """
    ends = [end for start, end in bounds if end > start]
    if len(ends) > BOUNDARY_LABELS_MAX:
        return []
    labels: list[tuple[float, float]] = []
    previous = 0.0  # „100” na końcu koła to zarazem 0 na jego początku
    for end in ends:
        near_end = end < 360.0 and 360.0 - end < BOUNDARY_MIN_DEGREES  # zbyt blisko podpisu „100”
        if end - previous < BOUNDARY_MIN_DEGREES or near_end:
            continue
        labels.append((end, 100.0 * end / 360.0))
        previous = end
    return labels


def draw_percent(r: float, total: float) -> float:
    """Wylosowana liczba w procentach obwodu koła (jak na zajęciach: liczba z [0, 100)): 100 * r / total."""
    return 100.0 * r / total


def wheel_angle(r: float, total: float) -> float:
    """Obrót koła (w stopniach), po którym punkt r znajduje się pod nieruchomym wskaźnikiem: 360 * r / total."""
    return 360.0 * r / total


class RouletteWheel(QWidget):
    """Rysuje wycinki przez QPainter.drawPie i obraca koło przez QVariantAnimation (krzywa OutCubic —
    koło zwalnia jak prawdziwa ruletka). Wskaźnik stoi u góry; koło obraca się przeciwnie do ruchu
    wskazówek zegara, aż pod wskaźnikiem znajdzie się punkt r.
    """

    spin_finished = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._fitnesses: tuple[float, ...] = ()
        self._bounds: list[tuple[float, float]] = []
        self._total = 0.0
        self._angle = 0.0  # bieżący obrót koła w stopniach
        self._highlight: int | None = None  # wyróżniony (wylosowany) osobnik
        self._pending: int | None = None  # osobnik wyróżniany po zakończeniu trwającego obrotu
        self._animation = QVariantAnimation(self)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._set_angle)
        self._animation.finished.connect(self._on_animation_finished)

    @property
    def total(self) -> float:
        """Suma szerokości wycinków — przedział losowania r (Σf albo N przy Σf = 0)."""
        return self._total

    @property
    def angle(self) -> float:
        return self._angle

    @property
    def highlighted(self) -> int | None:
        return self._highlight

    def set_fitnesses(self, fitnesses: tuple[float, ...]) -> None:
        """Nowe koło (inne pokolenie): obrót od zera, bez wyróżnienia."""
        self._animation.stop()
        self._fitnesses = fitnesses
        self._bounds = slice_bounds(fitnesses) if fitnesses else []
        self._total = sum(slice_widths(fitnesses)) if fitnesses else 0.0
        self._angle = 0.0
        self._highlight = self._pending = None
        self.update()

    def is_spinning(self) -> bool:
        return self._animation.state() == QVariantAnimation.State.Running

    def spin_to(self, r: float, index: int, duration_ms: int, full_turns: int) -> None:
        """Obrót od bieżącego położenia o kilka pełnych obrotów do kąta wheel_angle(r); po zatrzymaniu
        wyróżnienie osobnika `index` i sygnał spin_finished.
        """
        start = self._angle % 360.0
        self._angle = start
        self._highlight = None
        self._pending = index
        self._animation.setStartValue(start)
        self._animation.setEndValue(wheel_angle(r, self._total) + 360.0 * max(full_turns, 1))
        self._animation.setDuration(duration_ms)
        self._animation.start()

    def show_at(self, r: float, index: int) -> None:
        """Ustawienie bez animacji („Pomiń animację”); nie wysyła spin_finished."""
        self._animation.stop()
        self._angle = wheel_angle(r, self._total)
        self._highlight = index
        self._pending = None
        self.update()

    def _set_angle(self, value: float) -> None:
        self._angle = value
        self.update()

    def _on_animation_finished(self) -> None:
        self._highlight, self._pending = self._pending, None
        self.update()
        self.spin_finished.emit()

    # --- Rysowanie ---------------------------------------------------------------------------------

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        text_color = self.palette().windowText().color()
        if not self._fitnesses:
            painter.setPen(text_color)
            message = "Uruchom algorytm — koło odtworzy losowania selekcji z wybranego pokolenia."
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, message)
            return

        pointer_size = 16.0
        boundaries = boundary_labels(self._bounds)
        # Miejsce na podpisy granic dookoła koła (tylko gdy są pokazywane).
        margin = painter.fontMetrics().horizontalAdvance("100.00") + 6 if boundaries else 4
        radius = min(self.width() - 2 * margin, self.height() - pointer_size - 2 * margin) / 2
        center = QPointF(self.width() / 2, pointer_size + margin + radius)
        circle = QRectF(-radius, -radius, 2 * radius, 2 * radius)

        surface = self.palette().window().color()
        hub = radius * HUB_RATIO
        painter.translate(center)
        painter.save()
        painter.rotate(-self._angle)  # dodatni kąt QPainter = zgodnie z ruchem wskazówek zegara
        painter.setPen(Qt.PenStyle.NoPen)
        for index, (start, end) in enumerate(self._bounds):
            if end <= start:
                continue  # przystosowanie 0 — wycinek o szerokości 0, osobnik nie może zostać wybrany
            painter.setBrush(SELECTED_COLOR if index == self._highlight else SLICE_COLORS[index % 2])
            # drawPie: kąty w 1/16 stopnia, od godziny 3 przeciwnie do ruchu wskazówek zegara.
            painter.drawPie(circle, round((90.0 - end) * 16), round((end - start) * 16))
        # Szczeliny między wycinkami od piasty do obwodu; przy bardzo wąskich wycinkach cieńsze albo żadne.
        arc_per_slice = 2 * math.pi * radius / len(self._bounds)
        gap = GAP_WIDTH if arc_per_slice >= 8 else 1 if arc_per_slice >= 3 else 0
        if gap:
            painter.setPen(QPen(surface, gap))
            for start, end in self._bounds:
                if end > start:
                    direction = math.radians(start)
                    x, y = math.sin(direction), -math.cos(direction)
                    painter.drawLine(QPointF(hub * x, hub * y), QPointF(radius * x, radius * y))
        painter.restore()

        self._draw_labels(painter, radius)
        self._draw_boundaries(painter, radius, boundaries)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(surface)
        painter.drawEllipse(QPointF(0, 0), hub, hub)  # piasta — zakrywa zbiegające się wąskie wycinki
        painter.setBrush(text_color)
        painter.drawEllipse(QPointF(0, 0), 4, 4)
        top = -radius - 2
        pointer = QPolygonF(
            [
                QPointF(-pointer_size / 2, top - pointer_size),
                QPointF(pointer_size / 2, top - pointer_size),
                QPointF(0, top + 4),
            ]
        )
        painter.drawPolygon(pointer)

    def _draw_boundaries(self, painter: QPainter, radius: float, boundaries: list[tuple[float, float]]) -> None:
        """Skumulowane procenty na granicach wycinków, poza kołem (jak na wykresie kołowym z zajęć)."""
        painter.setPen(self.palette().windowText().color())
        metrics = painter.fontMetrics()
        for angle, percent in boundaries:
            screen = (angle - self._angle) % 360.0
            if min(screen, 360.0 - screen) < POINTER_CLEARANCE_DEGREES:
                continue  # granica pod wskaźnikiem — podpis zasłoniłby wskaźnik
            text = f"{percent:.2f}"
            direction = math.radians(screen)
            distance = radius + 4 + metrics.horizontalAdvance(text) / 2
            x, y = distance * math.sin(direction), -distance * math.cos(direction)
            box = QRectF(x - 40, y - metrics.height() / 2, 80, metrics.height())
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_labels(self, painter: QPainter, radius: float) -> None:
        """Numer osobnika (od 1) i przystosowanie na wycinku — tekst poziomy, niezależnie od obrotu koła."""
        painter.setPen(LABEL_COLOR)
        line_height = painter.fontMetrics().height()
        for index, (start, end) in enumerate(self._bounds):
            width = end - start
            if width < NUMBER_MIN_DEGREES:
                continue
            text = str(index + 1)
            if width >= VALUE_MIN_DEGREES:
                text += f"\n{format_number(self._fitnesses[index])}"
            middle = math.radians((start + end) / 2 - self._angle)  # od góry, zgodnie z ruchem wskazówek
            distance = radius * (0.72 if width < VALUE_MIN_DEGREES else 0.62)
            x, y = distance * math.sin(middle), -distance * math.cos(middle)
            box = QRectF(x - 40, y - line_height, 80, 2 * line_height)
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)


class RoulettePanel(QWidget):
    """Wybór pokolenia, przyciski „Zakręć raz” / „Zakręć wszystkie” / „Pomiń animację” / „Od początku”,
    szybkość, opis losowania i lista wybranych rodziców.

    Zasilany listą SelectionTrace zebraną z sygnału GAWorker.selection (`set_traces` po zakończeniu
    algorytmu, `clear` przed nowym przebiegiem).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._traces: list[SelectionTrace] = []
        self._trace: SelectionTrace | None = None
        self._done = 0  # liczba pokazanych losowań w bieżącym pokoleniu
        self._spin_all = False
        self._next_duration = 0

        self.wheel = RouletteWheel()
        self.wheel.spin_finished.connect(self._on_spin_finished)
        self.generation = QSpinBox()
        self.generation.setKeyboardTracking(False)
        self.generation.valueChanged.connect(self.show_generation)
        self.generation_info = QLabel()
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(1, len(SPEED_DURATIONS_MS))
        self.speed.setValue(3)
        self.speed.setMaximumWidth(120)
        self.step_label = QLabel()
        self.draw_label = QLabel()
        self.pick_label = QLabel()
        self.pick_label.setStyleSheet("font-weight: 600;")
        self.parents_list = QListWidget()
        self.spin_button = QPushButton("Zakręć raz")
        self.spin_all_button = QPushButton("Zakręć wszystkie")
        self.skip_button = QPushButton("Pomiń animację")
        self.restart_button = QPushButton("Od początku")
        self.spin_button.clicked.connect(self.spin_once)
        self.spin_all_button.clicked.connect(self.spin_all)
        self.skip_button.clicked.connect(self.skip_animation)
        self.restart_button.clicked.connect(lambda: self.show_generation(self.generation.value()))

        top = QHBoxLayout()
        top.addWidget(QLabel("Pokolenie:"))
        top.addWidget(self.generation)
        top.addWidget(self.generation_info, stretch=1)
        top.addWidget(QLabel("Szybkość:"))
        top.addWidget(self.speed)
        details = QVBoxLayout()
        for label in (self.step_label, self.draw_label, self.pick_label):
            details.addWidget(label)
        details.addWidget(QLabel("Wybrani rodzice (kolejne pary → krzyżowanie):"))
        details.addWidget(self.parents_list, stretch=1)
        middle = QHBoxLayout()
        middle.addWidget(self.wheel, stretch=3)
        middle.addLayout(details, stretch=2)
        buttons = QHBoxLayout()
        for button in (self.spin_button, self.spin_all_button, self.skip_button, self.restart_button):
            buttons.addWidget(button)
        buttons.addStretch()
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(middle, stretch=1)
        layout.addLayout(buttons)
        self.clear()

    # --- Dane --------------------------------------------------------------------------------------

    def set_traces(self, traces: list[SelectionTrace]) -> None:
        """Zapisane losowania kolejnych pokoleń (od 0); przy dużych N · G tylko pierwsze pokolenia."""
        self._traces = list(traces)
        if not self._traces:
            self.clear()
            return
        last = len(self._traces) - 1
        self.generation.blockSignals(True)
        self.generation.setRange(0, last)
        self.generation.setValue(0)
        self.generation.blockSignals(False)
        self.generation.setEnabled(True)
        self.show_generation(0)

    def clear(self) -> None:
        self._traces = []
        self._trace = None
        self._done = 0
        self._spin_all = False
        self.wheel.set_fitnesses(())
        self.generation.blockSignals(True)
        self.generation.setRange(0, 0)
        self.generation.blockSignals(False)
        self.generation.setEnabled(False)
        for label in (self.generation_info, self.step_label, self.draw_label, self.pick_label):
            label.clear()
        self.parents_list.clear()
        self._update_buttons()

    def selected_so_far(self) -> list[int]:
        """Indeksy (od 0) osobników pokazanych już jako wybrani w bieżącym pokoleniu."""
        return list(self._trace.selected[: self._done]) if self._trace is not None else []

    # --- Losowania ---------------------------------------------------------------------------------

    def show_generation(self, generation: int) -> None:
        """Koło z populacji danego pokolenia, bez pokazanych losowań."""
        if not self._traces:
            return
        self._trace = self._traces[generation]
        self._done = 0
        self._spin_all = False
        self.wheel.set_fitnesses(self._trace.fitnesses)
        count = len(self._trace.selected)
        total = format_number(round(sum(self._trace.fitnesses), 6))
        available = f" · zapisane pokolenia: 0–{len(self._traces) - 1}"
        self.generation_info.setText(f"N = {count} · Σf = {total}{available}")
        if sum(self._trace.fitnesses) <= 0:
            self.generation_info.setText(self.generation_info.text() + " · Σf = 0: losowanie równomierne")
        self.step_label.setText(f"Losowanie 0 z {count}")
        self.draw_label.clear()
        self.pick_label.clear()
        self.parents_list.clear()
        self._update_buttons()

    def spin_once(self) -> None:
        if self._can_spin():
            self._spin_all = False
            self._start_spin(SPEED_DURATIONS_MS[self.speed.value() - 1], FULL_TURNS)

    def spin_all(self) -> None:
        """Kolejne obroty jeden po drugim, coraz krótsze (SPEEDUP), aż do ostatniego losowania."""
        if self._can_spin():
            self._spin_all = True
            self._next_duration = SPEED_DURATIONS_MS[self.speed.value() - 1]
            self._start_spin(self._next_duration, FULL_TURNS)

    def skip_animation(self) -> None:
        """Wszystkie pozostałe losowania (także trwające) od razu na liście; koło na ostatnim r."""
        if self._trace is None:
            return
        self._spin_all = False
        while self._done < len(self._trace.selected):
            self._record_draw()
        self.wheel.show_at(self._trace.draws[-1], self._trace.selected[-1])
        self._update_buttons()

    def _can_spin(self) -> bool:
        return self._trace is not None and not self.wheel.is_spinning() and self._done < len(self._trace.selected)

    def _start_spin(self, duration_ms: int, full_turns: int) -> None:
        k = self._done
        self.step_label.setText(f"Losowanie {k + 1} z {len(self._trace.selected)}")
        self.draw_label.setText(self._draw_text(k))
        self.pick_label.clear()
        self.wheel.spin_to(self._trace.draws[k], self._trace.selected[k], duration_ms, full_turns)
        self._update_buttons()

    def _on_spin_finished(self) -> None:
        self._record_draw()
        if self._spin_all and self._done < len(self._trace.selected):
            self._next_duration = max(MIN_DURATION_MS, round(self._next_duration * SPEEDUP))
            self._start_spin(self._next_duration, 1)
            return
        self._spin_all = False
        self._update_buttons()

    def _record_draw(self) -> None:
        """Losowanie nr _done: opis wybranego osobnika i wpis na liście rodziców."""
        k = self._done
        index = self._trace.selected[k]
        fitness = self._trace.fitnesses[index]
        start, end = slice_bounds(self._trace.fitnesses)[index]
        share, start_percent, end_percent = (end - start) / 3.6, start / 3.6, end / 3.6  # stopnie -> % koła
        self.step_label.setText(f"Losowanie {k + 1} z {len(self._trace.selected)}")
        self.draw_label.setText(self._draw_text(k))
        self.pick_label.setText(
            f"→ osobnik {index + 1}: f = {format_number(fitness)}, p = {share:.2f}% "
            f"(wycinek {start_percent:.2f}–{end_percent:.2f})"
        )
        # Pary jak w crossover_population: 1-2, 3-4, …; przy nieparzystym N ostatni rodzic bez pary (kopia).
        count = len(self._trace.selected)
        pair = "bez pary — kopiowany" if count % 2 == 1 and k == count - 1 else f"para {k // 2 + 1}"
        percent = draw_percent(self._trace.draws[k], self.wheel.total)
        self.parents_list.addItem(
            f"{k + 1}. liczba {percent:.2f} → osobnik {index + 1} (f = {format_number(fitness)}) — {pair}"
        )
        self.parents_list.scrollToBottom()
        self._done += 1

    def _draw_text(self, k: int) -> str:
        """Wylosowana liczba w procentach (jak na zajęciach) i odpowiadający jej punkt r na skali przystosowań."""
        r = self._trace.draws[k]
        total = format_number(round(self.wheel.total, 6))
        return f"Wylosowana liczba: {draw_percent(r, self.wheel.total):.2f} z [0, 100)  (r = {r:.2f} z Σf = {total})"

    def _update_buttons(self) -> None:
        spinning = self.wheel.is_spinning()
        remaining = self._trace is not None and self._done < len(self._trace.selected)
        self.spin_button.setEnabled(remaining and not spinning)
        self.spin_all_button.setEnabled(remaining and not spinning)
        self.skip_button.setEnabled(remaining)
        self.restart_button.setEnabled(self._trace is not None and (self._done > 0 or spinning))
