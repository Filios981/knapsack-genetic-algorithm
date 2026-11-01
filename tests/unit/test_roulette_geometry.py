"""Geometria koła ruletki w animacji: kąt obrotu wskazuje osobnika wybranego przez selekcję;
liczby losowe i granice wycinków w procentach jak w przykładzie z zajęć."""

import pytest

from knapsack_ga.ga.selection import cumulative_sums, spin_wheel
from knapsack_ga.gui.roulette_widget import boundary_labels, draw_percent, slice_bounds, slice_widths, wheel_angle


class FixedRandom:
    """Zwraca zadaną liczbę z [0, 1) — spin_wheel wylosuje r = value * suma."""

    def __init__(self, value: float) -> None:
        self.value = value

    def random(self) -> float:
        return self.value


def slice_under_pointer(angle: float, bounds: list[tuple[float, float]]) -> int:
    """Wycinek [start, end), w którym leży kąt — ten, który po obrocie stoi pod wskaźnikiem."""
    matches = [index for index, (start, end) in enumerate(bounds) if start <= angle < end]
    assert len(matches) == 1
    return matches[0]


def test_angle_is_proportional_to_r():
    assert wheel_angle(0, 167) == 0
    assert wheel_angle(41.75, 167) == pytest.approx(90)
    assert wheel_angle(83.5, 167) == pytest.approx(180)


def test_bounds_follow_cumulative_sums():
    assert slice_bounds((1, 1, 2)) == [(0, 90), (90, 180), (180, 360)]
    assert slice_bounds((0, 3, 0, 1))[0] == (0, 0)  # f = 0 — wycinek o szerokości 0


@pytest.mark.parametrize(
    "fitnesses",
    [(51, 40, 39, 37), (0, 5, 0, 5, 2), (0, 0, 0)],  # zwykłe wartości; zera; Σf = 0 — równe wycinki
)
def test_pointer_shows_individual_chosen_by_spin_wheel(fitnesses):
    bounds = slice_bounds(fitnesses)
    widths = slice_widths(fitnesses)
    total = sum(widths)
    cumulative = cumulative_sums(list(fitnesses))
    boundaries = [s / total for s in cumulative_sums(widths)[:-1]]
    # r = 0, r dokładnie na granicach wycinków, r tuż przed końcem koła, kilka punktów wewnątrz
    for value in [0.0, *boundaries, 0.999999, 0.13, 0.5, 0.77]:
        spin = spin_wheel(cumulative, FixedRandom(value))
        assert slice_under_pointer(wheel_angle(spin.r, total), bounds) == spin.index


# Przykład z zajęć (PAG, slajdy 20–22): przystosowania 8 chromosomów, Σ = 212, wylosowane liczby w procentach.
LECTURE_FITNESSES = (13, 11, 27, 43, 53, 37, 17, 11)
LECTURE_BOUNDARIES = [6.13, 11.32, 24.06, 44.34, 69.34, 86.79, 94.81, 100.0]
LECTURE_NUMBERS = [79, 44, 9, 74, 45, 86, 48, 23]
LECTURE_CHOSEN = [6, 4, 2, 6, 5, 6, 5, 3]  # ch6 ch4 ch2 ch6 ch5 ch6 ch5 ch3


def test_boundaries_in_percent_match_lecture_example():
    labels = boundary_labels(slice_bounds(LECTURE_FITNESSES))
    assert [round(percent, 2) for _, percent in labels] == LECTURE_BOUNDARIES


def test_lecture_draws_choose_the_same_chromosomes():
    cumulative = cumulative_sums(list(LECTURE_FITNESSES))
    chosen = [spin_wheel(cumulative, FixedRandom(number / 100)).index + 1 for number in LECTURE_NUMBERS]
    assert chosen == LECTURE_CHOSEN
    spin = spin_wheel(cumulative, FixedRandom(0.79))
    assert draw_percent(spin.r, 212) == pytest.approx(79)


def test_boundary_labels_skip_crowded_and_large_wheels():
    assert [percent for _, percent in boundary_labels(slice_bounds((1, 1, 98)))] == [100.0]  # 1% i 2% przy zerze
    assert [percent for _, percent in boundary_labels(slice_bounds((4, 1, 95)))] == [4.0, 100.0]  # 5% przy 4%
    assert boundary_labels(slice_bounds(tuple([1] * 21))) == []  # za dużo wycinków
