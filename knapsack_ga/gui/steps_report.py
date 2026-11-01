"""Widok „Krok po kroku”: jedno pokolenie w etapach jak w przykładzie z zajęć.

Funkcja step_report_html tworzy HTML z zapisu StepTrace — bez Qt, więc da się ją testować bez okna.
Wszystkie liczby pochodzą z przebiegu algorytmu (to samo ziarno = te same tabele). Numeracja od 1.
"""

from knapsack_ga.data_io import format_number
from knapsack_ga.ga.selection import cumulative_sums, wheel_widths
from knapsack_ga.models import GAParams, KnapsackProblem, MutationMethod, RepairMethod, StepTrace

MUTATION_COLOR = "#c62828"  # zanegowany gen — na czerwono, jak na slajdach z zajęć
TABLE = '<table border="1" cellspacing="0" cellpadding="3">'
MONO = "style=\"font-family: Consolas, 'Courier New', monospace;\""


def _weight(bits: str, problem: KnapsackProblem) -> float:
    return sum(item.weight for bit, item in zip(bits, problem.items, strict=True) if bit == "1")


def _number(value: float) -> str:
    return format_number(round(value, 6))


def _bits(text: str) -> str:
    """Chromosom czcionką o stałej szerokości (kolumny genów jeden pod drugim)."""
    return f"<span {MONO}>{text}</span>"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{header}</th>" for header in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"{TABLE}<tr>{head}</tr>{body}</table>"


def _population_section(trace: StepTrace, problem: KnapsackProblem) -> str:
    widths = wheel_widths(trace.fitnesses)
    total = sum(widths)
    ends = cumulative_sums(widths)
    rows = []
    for index, bits in enumerate(trace.population):
        start = ends[index] - widths[index]
        rows.append(
            [
                str(index + 1),
                _bits(bits),
                _number(_weight(bits, problem)),
                _number(trace.fitnesses[index]),
                f"{100 * widths[index] / total:.2f}",
                f"{100 * start / total:.2f}–{100 * ends[index] / total:.2f}",
            ]
        )
    title = (
        "1. Populacja początkowa (pokolenie 0) — losowe chromosomy, osobniki z nadwagą naprawione"
        if trace.generation == 0
        else f"1. Populacja pokolenia {trace.generation}"
    )
    note = " (Σ<i>F</i> = 0 — wszystkie wycinki równe)" if sum(trace.fitnesses) <= 0 else ""
    return (
        f"<h3>{title}</h3>"
        + _table(["Nr", "Chromosom", "Waga", "<i>F</i>", "Wycinek koła [%]", "Przedział [%]"], rows)
        + f"<p>Σ<i>F</i> = <b>{_number(sum(trace.fitnesses))}</b>{note}</p>"
    )


def _selection_section(trace: StepTrace) -> str:
    total = sum(wheel_widths(trace.fitnesses))
    rows = [
        [str(k + 1), f"{100 * r / total:.2f}", str(index + 1), _bits(trace.population[index])]
        for k, (r, index) in enumerate(zip(trace.draws, trace.selected, strict=True))
    ]
    pool = [str(index + 1) for index in trace.selected]
    pairs = ", ".join(" i ".join(pool[i : i + 2]) for i in range(0, len(pool), 2))
    return (
        "<h3>2. Selekcja — koło ruletki</h3>"
        f"<p>{len(trace.selected)} losowań liczby z [0, 100); wybrany jest osobnik, w którego przedziale leży "
        "liczba.</p>"
        + _table(["Losowanie", "Liczba", "Wybrany osobnik", "Chromosom"], rows)
        + f"<p>Pula rodzicielska (kolejne pary): {pairs}</p>"
    )


def _crossover_section(trace: StepTrace, params: GAParams) -> str:
    parents = [trace.population[index] for index in trace.selected]
    numbers = [index + 1 for index in trace.selected]
    rows = []
    for k, pair in enumerate(trace.pairs):
        first, second = parents[2 * k], parents[2 * k + 1]
        child_a, child_b = trace.offspring[2 * k], trace.offspring[2 * k + 1]
        crossed = pair.cut is not None
        if crossed:
            cut = pair.cut
            shown_parents = f"{_bits(first[:cut] + '|' + first[cut:])}<br>{_bits(second[:cut] + '|' + second[cut:])}"
            # Wymieniona część (geny l+1…n od drugiego rodzica) pogrubiona — jak na slajdach z zajęć.
            shown_children = (
                f"{_bits(child_a[:cut] + '|<b>' + child_a[cut:] + '</b>')}<br>"
                f"{_bits(child_b[:cut] + '|<b>' + child_b[cut:] + '</b>')}"
            )
        else:
            shown_parents = f"{_bits(first)}<br>{_bits(second)}"
            shown_children = f"{_bits(child_a)}<br>{_bits(child_b)}"
        rows.append(
            [
                str(k + 1),
                f"{numbers[2 * k]}<br>{numbers[2 * k + 1]}",
                shown_parents,
                f"{pair.draw:.3f}",
                "TAK" if crossed else "NIE",
                str(pair.cut) if crossed else "—",
                shown_children,
            ]
        )
    if len(parents) % 2 == 1:
        rows.append(["—", str(numbers[-1]), _bits(parents[-1]), "—", "bez pary", "—", _bits(trace.offspring[-1])])
    p_c = _number(params.crossover_prob)
    return (
        f"<h3>3. Krzyżowanie jednopunktowe (<i>p<sub>c</sub></i> = {p_c})</h3>"
        f"<p>Pary w kolejności z puli rodzicielskiej. Liczba z [0, 1) mniejsza od {p_c} — krzyżowanie w punkcie "
        "<i>l</i>: geny 1…<i>l</i> od jednego rodzica, pozostałe (pogrubione) od drugiego.</p>"
        + _table(["Para", "Rodzice", "Chromosomy rodziców", "Liczba", "Krzyżowanie", "<i>l</i>", "Potomkowie"], rows)
    )


def _mark_genes(bits: str, positions: tuple[int, ...]) -> str:
    """Chromosom z wyróżnionymi genami (zanegowanymi w mutacji)."""
    marked = "".join(
        f'<b><span style="color:{MUTATION_COLOR}">{gene}</span></b>' if index in positions else gene
        for index, gene in enumerate(bits)
    )
    return _bits(marked)


def _mutation_section(trace: StepTrace, params: GAParams) -> str:
    p_m = _number(params.mutation_prob)
    per_individual = params.mutation_method is MutationMethod.PER_INDIVIDUAL
    rows = []
    for k, (before, after, mutation) in enumerate(zip(trace.offspring, trace.mutated, trace.mutations, strict=True)):
        loci = ", ".join(str(locus + 1) for locus in mutation.loci) or "—"
        rows.append(
            [
                str(k + 1),
                _bits(before),
                f"{mutation.draw:.3f}" if mutation.draw is not None else "—",
                "TAK" if mutation.loci else "NIE",
                loci,
                _mark_genes(after, mutation.loci),
            ]
        )
    if per_individual:
        rule = (
            f"Dla każdego potomka liczba z [0, 1); mniejsza od {p_m} — negacja jednego genu w losowym miejscu "
            "<i>l</i> (na czerwono)."
        )
    else:
        rule = f"Mutacja na gen: każdy gen negowany z prawdopodobieństwem {p_m} (zanegowane — na czerwono)."
    kind = "na osobnika" if per_individual else "na gen"
    return f"<h3>4. Mutacja (<i>p<sub>m</sub></i> = {p_m}, {kind})</h3><p>{rule}</p>" + _table(
        ["Potomek", "Po krzyżowaniu", "Liczba", "Mutacja", "<i>l</i>", "Po mutacji"], rows
    )


def _repair_section(trace: StepTrace, problem: KnapsackProblem, params: GAParams) -> str:
    method = (
        "zachłanna — wyjmowane przedmioty o najmniejszym stosunku wartości do wagi"
        if params.repair_method is RepairMethod.GREEDY
        else "losowa — wyjmowane losowe przedmioty"
    )
    rows = []
    for k, (before, after) in enumerate(zip(trace.mutated, trace.new_population, strict=True)):
        if before == after:
            continue
        removed = [problem.items[i].number for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b]
        rows.append(
            [
                str(k + 1),
                _bits(before),
                _number(_weight(before, problem)),
                ", ".join(map(str, removed)),
                _bits(after),
                _number(_weight(after, problem)),
            ]
        )
    title = f"<h3>5. Naprawa (<i>W</i> = {_number(problem.capacity)}, naprawa {method})</h3>"
    if not rows:
        return title + "<p>Żaden potomek nie przekracza pojemności — naprawa niepotrzebna.</p>"
    return (
        title
        + f"<p>Potomkowie z nadwagą: {len(rows)} z {len(trace.mutated)}.</p>"
        + _table(["Potomek", "Po mutacji", "Waga", "Wyjęte przedmioty", "Po naprawie", "Waga po"], rows)
    )


def _new_population_section(trace: StepTrace, problem: KnapsackProblem) -> str:
    rows = [
        [str(k + 1), _bits(bits), _number(_weight(bits, problem)), _number(value)]
        for k, (bits, value) in enumerate(zip(trace.new_population, trace.new_fitnesses, strict=True))
    ]
    best = max(range(len(trace.new_fitnesses)), key=trace.new_fitnesses.__getitem__)
    return (
        f"<h3>6. Nowa populacja (pokolenie {trace.generation + 1})</h3>"
        + _table(["Nr", "Chromosom", "Waga", "<i>F</i>"], rows)
        + f"<p>Σ<i>F</i>: {_number(sum(trace.fitnesses))} → <b>{_number(sum(trace.new_fitnesses))}</b> · "
        f"najlepszy w nowej populacji: osobnik {best + 1}, <i>F</i> = {_number(trace.new_fitnesses[best])} "
        f"(w poprzedniej: {_number(max(trace.fitnesses))})</p>"
    )


def step_report_html(trace: StepTrace, problem: KnapsackProblem, params: GAParams) -> str:
    """Całe pokolenie trace.generation -> trace.generation + 1 jako HTML (dla QTextBrowser albo pliku)."""
    return "".join(
        [
            f"<h2>Pokolenie {trace.generation} → {trace.generation + 1}</h2>",
            _population_section(trace, problem),
            _selection_section(trace),
            _crossover_section(trace, params),
            _mutation_section(trace, params),
            _repair_section(trace, problem, params),
            _new_population_section(trace, problem),
        ]
    )
