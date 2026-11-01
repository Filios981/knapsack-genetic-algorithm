"""Selekcja metodą koła ruletki."""

import bisect
import random
from typing import NamedTuple


class Spin(NamedTuple):
    """Jedno zakręcenie kołem: indeks wybranego osobnika i wylosowany punkt r."""

    index: int
    r: float


def cumulative_sums(fitnesses: list[float]) -> list[float]:
    """S_j = f_1 + ... + f_j; ostatni element to suma przystosowań (granice wycinków koła)."""
    sums = []
    running_total = 0.0
    for value in fitnesses:
        running_total += value
        sums.append(running_total)
    return sums


def wheel_widths(fitnesses: list[float] | tuple[float, ...]) -> list[float]:
    """Szerokości wycinków koła: przystosowania; gdy ich suma = 0 — równe (losowanie równomierne, jak spin_wheel).

    Używane przy pokazywaniu koła (animacja, widok „Krok po kroku”); spin_wheel liczy to samo wprost.
    """
    if sum(fitnesses) <= 0:
        return [1.0] * len(fitnesses)
    return list(fitnesses)


def spin_wheel(cumulative: list[float], rng: random.Random) -> Spin:
    """Losuje r z [0, S_N) i wybiera pierwszego osobnika, dla którego S_j > r (bisect_right).

    Osobnik o przystosowaniu 0 ma wycinek o szerokości 0 i nigdy nie zostanie wybrany. Indeks jest
    ograniczany do N - 1 na wypadek błędu zaokrąglenia (r bliskie S_N). Gdy S_N == 0 — wybór równomierny
    (koło z N równymi wycinkami, r z [0, N)).
    """
    count = len(cumulative)
    total = cumulative[-1]
    if total <= 0:
        r = rng.random() * count
        return Spin(min(int(r), count - 1), r)
    r = rng.random() * total
    index = bisect.bisect_right(cumulative, r)
    return Spin(min(index, count - 1), r)


def roulette_wheel_selection(fitnesses: list[float], count: int, rng: random.Random) -> list[Spin]:
    """Zakręca kołem `count` razy (losowanie ze zwracaniem).

    Wywołujący zamienia zakręcenia na rodziców (population[spin.index]); ten sam chromosom może zostać
    wybrany kilka razy, więc rodziców nie wolno modyfikować „w miejscu”. Zakręcenia trafiają też do
    SelectionTrace na potrzeby animacji koła.
    """
    cumulative = cumulative_sums(fitnesses)
    return [spin_wheel(cumulative, rng) for _ in range(count)]
