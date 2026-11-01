"""Parametry algorytmu z kontrolą zakresów i przyciskiem „Przywróć domyślne”."""

from PyQt6.QtCore import QLocale, QRegularExpression
from PyQt6.QtGui import QRegularExpressionValidator, QValidator
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from knapsack_ga.models import GAParams, MutationMethod, RepairMethod

MAX_COUNT = 1_000_000  # górna granica pól N, G_max, G_s — praktycznie bez ograniczeń


class DecimalSpinBox(QDoubleSpinBox):
    """Pole liczby dziesiętnej z kropką (jak w dokumentacji), które przyjmuje także przecinek."""

    def __init__(self, decimals: int, step: float) -> None:
        super().__init__()
        self.setLocale(QLocale.c())
        self.setDecimals(decimals)
        self.setSingleStep(step)
        self.setRange(0.0, 1.0)

    def validate(self, text: str, pos: int) -> tuple[QValidator.State, str, int]:
        return super().validate(text.replace(",", "."), pos)

    def valueFromText(self, text: str) -> float:
        return super().valueFromText(text.replace(",", "."))


def _count_box(minimum: int, step: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(minimum, MAX_COUNT)
    box.setSingleStep(step)
    return box


class ParamsPanel(QGroupBox):
    """Pola parametrów; `get_params()` zwraca GAParams, `restore_defaults()` przywraca wartości z GAParams()."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Parametry algorytmu", parent)
        self.population = _count_box(2, 10)
        self.crossover = DecimalSpinBox(decimals=3, step=0.05)
        self.mutation = DecimalSpinBox(decimals=3, step=0.01)
        self.max_generations = _count_box(1, 100)
        self.stagnation = _count_box(1, 50)
        self.mutation_kind = QComboBox()
        self.mutation_kind.addItem("na osobnika (1 gen)", MutationMethod.PER_INDIVIDUAL)
        self.mutation_kind.addItem("na gen", MutationMethod.PER_GENE)
        self.repair = QComboBox()
        self.repair.addItem("zachłanna", RepairMethod.GREEDY)
        self.repair.addItem("losowa", RepairMethod.RANDOM)
        self.seed = QLineEdit()
        self.seed.setPlaceholderText("puste = losowe")
        self.seed.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,18}")))

        self.crossover.setToolTip("Wymagane w zadaniu: 0.8. Para rodziców jest krzyżowana z tym prawdopodobieństwem.")
        self.mutation.setToolTip("Wymagane w zadaniu: 0.2.")
        self.mutation_kind.setToolTip(
            "Na osobnika (jak na zajęciach): z prawdopodobieństwem p_m potomek ma zanegowany jeden losowy gen;\n"
            "na gen (do porównania): każdy gen potomka jest negowany z prawdopodobieństwem p_m."
        )
        self.stagnation.setToolTip("Algorytm kończy, gdy najlepszy wynik nie poprawił się przez tyle pokoleń.")
        self.repair.setToolTip(
            "Osobnik za ciężki: zachłanna — wyjmuje przedmioty o najmniejszym stosunku wartości do wagi;\n"
            "losowa — wyjmuje losowe przedmioty (do porównania)."
        )
        self.seed.setToolTip("To samo ziarno daje ten sam przebieg (powtarzalność). Puste pole — ziarno losowe.")

        # Dwie kolumny pól — panel jest niski, więc okno mieści się także na małym ekranie.
        grid = QGridLayout()
        fields = (
            ("Populacja (N):", self.population, "Limit pokoleń (G_max):", self.max_generations),
            ("Krzyżowanie (p_c):", self.crossover, "Limit stagnacji (G_s):", self.stagnation),
            ("Mutacja (p_m):", self.mutation, "Rodzaj mutacji:", self.mutation_kind),
            ("Selekcja:", QLabel("koło ruletki"), "Naprawa nadwagi:", self.repair),
            ("Ziarno (opcjonalne):", self.seed, None, None),
        )
        for row, (left_label, left_field, right_label, right_field) in enumerate(fields):
            grid.addWidget(QLabel(left_label), row, 0)
            grid.addWidget(left_field, row, 1)
            if right_field is not None:
                grid.addWidget(QLabel(right_label), row, 3)
                grid.addWidget(right_field, row, 4)
        grid.setColumnMinimumWidth(2, 12)  # odstęp między kolumnami
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(4, 1)

        restore_button = QPushButton("Przywróć domyślne")
        restore_button.clicked.connect(self.restore_defaults)
        buttons = QHBoxLayout()
        buttons.addWidget(restore_button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(grid)
        layout.addLayout(buttons)
        self.restore_defaults()

    def restore_defaults(self) -> None:
        defaults = GAParams()
        self.population.setValue(defaults.population_size)
        self.crossover.setValue(defaults.crossover_prob)
        self.mutation.setValue(defaults.mutation_prob)
        self.max_generations.setValue(defaults.max_generations)
        self.stagnation.setValue(defaults.stagnation_limit)
        self.mutation_kind.setCurrentIndex(self.mutation_kind.findData(defaults.mutation_method))
        self.repair.setCurrentIndex(self.repair.findData(defaults.repair_method))
        self.seed.clear()

    def get_params(self) -> GAParams:
        seed_text = self.seed.text().strip()
        return GAParams(
            population_size=self.population.value(),
            crossover_prob=self.crossover.value(),
            mutation_prob=self.mutation.value(),
            max_generations=self.max_generations.value(),
            stagnation_limit=self.stagnation.value(),
            mutation_method=self.mutation_kind.currentData(),
            repair_method=self.repair.currentData(),
            seed=int(seed_text) if seed_text else None,
        )
