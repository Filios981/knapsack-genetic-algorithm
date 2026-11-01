"""Warunek zatrzymania: stagnacja lub limit pokoleń."""

from knapsack_ga.models import StopReason


class StopCondition:
    """Liczy pokolenia i pokolenia bez poprawy (licznik stagnacji).

    `update` wywołuje się raz po ocenie każdego nowego pokolenia, podając, czy najlepszy znaleziony
    osobnik się poprawił (jego wartość wzrosła).
    """

    def __init__(self, max_generations: int, stagnation_limit: int) -> None:
        self.max_generations = max_generations  # G_max
        self.stagnation_limit = stagnation_limit  # G_s
        self.generation = 0
        self.generations_without_improvement = 0

    def update(self, improved: bool) -> StopReason | None:
        """Przejście o jedno pokolenie; zwraca powód zatrzymania albo None, gdy algorytm ma działać dalej.

        Stagnacja jest sprawdzana przed limitem pokoleń.
        """
        self.generation += 1
        if improved:
            self.generations_without_improvement = 0
        else:
            self.generations_without_improvement += 1

        if self.generations_without_improvement >= self.stagnation_limit:
            return StopReason.STAGNATION
        if self.generation >= self.max_generations:
            return StopReason.MAX_GENERATIONS
        return None
