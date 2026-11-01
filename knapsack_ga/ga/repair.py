"""Naprawa osobników przekraczających pojemność.

Stosowana po utworzeniu populacji początkowej oraz po krzyżowaniu i mutacji. Domyślnie naprawa zachłanna;
naprawa losowa pozostaje do porównania — wybór parametrem `GAParams.repair_method`.
"""

import random
from collections.abc import Callable

from knapsack_ga.ga.fitness import fits, total_weight
from knapsack_ga.models import Chromosome, KnapsackProblem, RepairMethod


def repair(chromosome: Chromosome, problem: KnapsackProblem, rng: random.Random) -> Chromosome:
    """Dopuszczalna kopia chromosomu.

    Dopóki plecak jest za ciężki, wyjmowany jest losowo wybrany przedmiot (gen 1 -> 0). Realizacja:
    indeksy genów równych 1 ustawiane są w losowej kolejności, a przedmioty wyjmowane po kolei, aż waga
    się zmieści. Chromosom dopuszczalny jest zwracany bez zmian (jako kopia). Zawsze się kończy: każdy
    krok wyjmuje jeden przedmiot, a pusty plecak zawsze się mieści.
    """
    repaired = list(chromosome)
    weight = total_weight(repaired, problem)
    if fits(weight, problem.capacity):
        return repaired

    packed = [index for index, gene in enumerate(repaired) if gene == 1]
    rng.shuffle(packed)  # losowa kolejność wyjmowania przedmiotów
    for index in packed:
        if fits(weight, problem.capacity):
            break
        repaired[index] = 0
        weight -= problem.items[index].weight
    return repaired


def greedy_removal_order(problem: KnapsackProblem) -> list[int]:
    """Indeksy przedmiotów w kolejności wyjmowania przy naprawie zachłannej.

    Od najmniejszego stosunku wartości do wagi (najmniej „opłacalny” kilogram); przy remisie — od
    najmniejszego indeksu. Liczona raz na przebieg algorytmu.
    """
    return sorted(
        range(problem.size), key=lambda index: (problem.items[index].value / problem.items[index].weight, index)
    )


def greedy_repair(chromosome: Chromosome, problem: KnapsackProblem, removal_order: list[int]) -> Chromosome:
    """Dopuszczalna kopia chromosomu — naprawa zachłanna.

    Dopóki plecak jest za ciężki, wyjmowany jest przedmiot o najmniejszym stosunku wartości do wagi spośród
    tych, które są w plecaku (`removal_order` z `greedy_removal_order`). Nie korzysta z losowości. Chromosom
    dopuszczalny jest zwracany bez zmian (jako kopia); zawsze się kończy, jak naprawa losowa.
    """
    repaired = list(chromosome)
    weight = total_weight(repaired, problem)
    for index in removal_order:
        if fits(weight, problem.capacity):
            break
        if repaired[index] == 1:
            repaired[index] = 0
            weight -= problem.items[index].weight
    return repaired


def make_repair(
    problem: KnapsackProblem, method: RepairMethod, rng: random.Random
) -> Callable[[Chromosome], Chromosome]:
    """Funkcja naprawy wybranego rodzaju — jedno miejsce wyboru dla populacji początkowej i pętli algorytmu."""
    if method is RepairMethod.GREEDY:
        order = greedy_removal_order(problem)
        return lambda chromosome: greedy_repair(chromosome, problem, order)
    return lambda chromosome: repair(chromosome, problem, rng)
