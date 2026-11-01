"""Import danych w dowolnym układzie i zapis CSV.

Format danych prowadzącego nie jest znany, dlatego zamiast jednego sztywnego formatu liczby są
wyciągane z dowolnego tekstu, proponowana jest interpretacja (separator, przecinek dziesiętny,
nagłówek, role kolumn, pojemność), a okno importu pozwala ją poprawić przed przyjęciem danych.
"""

import csv
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from knapsack_ga.models import Item, KnapsackProblem


class DataFormatError(ValueError):
    """Błędne dane wejściowe; komunikat po polsku dla użytkownika, z numerem wiersza, jeśli jest znany."""

    def __init__(self, message: str, line_number: int | None = None) -> None:
        super().__init__(message if line_number is None else f"Wiersz {line_number}: {message}")
        self.line_number = line_number


class ColumnRole(Enum):
    NUMBER = "Nr"
    WEIGHT = "Waga"
    VALUE = "Wartość"
    NAME = "Nazwa"  # tylko dla tekstu wiersza
    SKIP = "Pomiń"


@dataclass(frozen=True)
class RawRow:
    line_number: int  # numer wiersza w tekście źródłowym (od 1, do komunikatów o błędach)
    text: str | None  # tekst wiersza: kolumna tekstowa lub pierwsza grupa słów (kandydat na nazwę
    #                   albo słowo „Wagi” / „Wartości” w danych poziomych)
    numbers: tuple[float, ...]


@dataclass(frozen=True)
class RawTable:
    rows: tuple[RawRow, ...]
    header: tuple[str, ...] | None  # nazwy kolumn liczbowych, jeśli znaleziono nagłówek
    capacity: float | None  # proponowana pojemność znaleziona w tekście
    roles: tuple[ColumnRole, ...] | None  # proponowane role kolumn liczbowych; None = wybiera użytkownik
    text_role: ColumnRole  # proponowana rola tekstu wiersza: NAME albo SKIP (brak tekstu / ten sam we wszystkich)
    count_line: int | None = None  # numer wiersza „n W” (liczba przedmiotów i pojemność), jeśli rozpoznany

    @property
    def column_count(self) -> int:
        return len(self.rows[0].numbers) if self.rows else 0


@dataclass(frozen=True)
class ParsedData:
    items: tuple[Item, ...]
    capacity: float | None  # None, gdy tekst nie zawiera pojemności


# --- Liczby ---------------------------------------------------------------------------------------

# Liczba w tekście: minus (tylko gdy nie stoi tuż za literą lub cyfrą, np. nie w „A-1”), cyfry,
# opcjonalna część dziesiętna. Klucz słownika: czy przecinek może być separatorem dziesiętnym.
_NUMBER = {
    False: re.compile(r"(?:(?<!\w)-)?\d+(?:\.\d+)?"),
    True: re.compile(r"(?:(?<!\w)-)?\d+(?:[.,]\d+)?"),
}
# Całe słowo będące liczbą, z krótką jednostką doklejoną na końcu, np. „12”, „12,5”, „12kg”, „24zł”.
_WORD_NUMBER = {
    False: re.compile(r"(-?\d+(?:\.\d+)?)[^\W\d_]{0,3}"),
    True: re.compile(r"(-?\d+(?:[.,]\d+)?)[^\W\d_]{0,3}"),
}
# Znaki obcinane z brzegów słów w tekście rozdzielonym spacjami: „[12,” -> „12”, „Wagi:” -> „Wagi”.
_PUNCTUATION = "[](){}:;,.=–—\"'"
# Najdłuższy dopisek przy liczbie, przy którym pole nadal jest liczbą, np. „12 kg”, „150 PLN”, „1 szt.”.
_MAX_UNIT_LENGTH = 5


def _to_float(number_text: str) -> float:
    return float(number_text.replace(",", "."))


def parse_number(text: str, decimal_comma: bool) -> float:
    """Liczba zapisana z kropką (lub — gdy `decimal_comma` — także z przecinkiem) jako separatorem dziesiętnym.

    Zgłasza ValueError dla tekstu, który nie jest liczbą (także „inf”, „nan”, „1e5”).
    """
    cleaned = text.strip()
    if not _NUMBER[decimal_comma].fullmatch(cleaned):
        raise ValueError(f"»{cleaned}« nie jest liczbą")
    return _to_float(cleaned)


def format_number(value: float) -> str:
    """Liczba bez zbędnego „.0”: 12.0 -> "12", 12.5 -> "12.5"."""
    return str(int(value)) if float(value).is_integer() else repr(float(value))


# --- Słowa kluczowe -------------------------------------------------------------------------------

# Słowa rozpoznawane w nagłówkach i etykietach wierszy (po zamianie na małe litery bez polskich znaków).
_ROLE_PREFIXES = (
    (ColumnRole.NUMBER, ("numer", "number")),
    (ColumnRole.WEIGHT, ("weight", "wag")),
    (ColumnRole.VALUE, ("value", "wartos", "cena", "ceny", "zysk", "profit", "price")),
    (ColumnRole.NAME, ("name", "nazw", "przedmiot", "item", "opis")),
)
_NUMBER_WORDS = {"nr", "no", "lp", "id"}

# Wiersz z pojemnością: słowo kluczowe, ewentualnie jedno słowo więcej („plecaka”), „=” lub „:”, liczba.
_CAPACITY = re.compile(r"\b(?:capacity|pojemno\w*|maks\w*|max\w*|w)\b(?:\s+\w+)?\s*[=:]?\s*(?=-?\d)", re.IGNORECASE)


def _normalize(word: str) -> str:
    """Małe litery, bez polskich znaków i interpunkcji: „Wartość [zł]” -> „wartosczl”."""
    decomposed = unicodedata.normalize("NFKD", word.lower().replace("ł", "l"))
    return "".join(char for char in decomposed if char.isalnum())


def _keyword_role(word: str) -> ColumnRole | None:
    """Rola kolumny wskazywana przez słowo z nagłówka lub etykietę wiersza; None, gdy słowo nie jest rozpoznane."""
    normalized = _normalize(word)
    if not normalized:
        return None
    if normalized in _NUMBER_WORDS:
        return ColumnRole.NUMBER
    for role, prefixes in _ROLE_PREFIXES:
        if normalized.startswith(prefixes):
            return role
    return None


def _find_capacity(line: str, decimal_comma: bool) -> float | None:
    """Pojemność z wiersza ze słowem kluczowym i dokładnie jedną liczbą, np. „Pojemność plecaka: 26 kg”, „W = 26”."""
    numbers = _NUMBER[decimal_comma].findall(line)
    if len(numbers) != 1 or not _CAPACITY.search(line):
        return None
    return _to_float(numbers[0])


# --- Podział wierszy na pola ----------------------------------------------------------------------

_WHITESPACE = " "  # separator „spacje”: dowolny ciąg białych znaków


@dataclass
class _Line:
    """Wiersz źródła po wyciągnięciu liczb (wewnętrzny etap extract_table)."""

    line_number: int
    source: str
    numbers: list[float]
    positions: list[int]  # numery pól, z których pochodzą liczby (do dopasowania nagłówka)
    text: str | None
    labels: list[str | None]  # słowo stojące tuż przed każdą liczbą, np. „waga” w „waga 12 kg”


def _detect_separator(line: str) -> str:
    """Separator kolumn jednego wiersza: średnik, tabulator, przecinek albo spacje."""
    if ";" in line:
        return ";"
    if "\t" in line:
        return "\t"
    commas_without_space = len(re.findall(r",(?=\S)", line))
    if commas_without_space >= 2 or (commas_without_space == 1 and not re.search(r"\s", line)):
        return ","
    return _WHITESPACE


def _choose_separator(lines: list[tuple[int, str]]) -> str:
    """Separator najczęstszy wśród wierszy wyglądających na dane (co najmniej dwie grupy cyfr)."""
    data_like = [line for _, line in lines if len(re.findall(r"\d+", line)) >= 2] or [line for _, line in lines]
    votes = Counter(_detect_separator(line) for line in data_like)
    return votes.most_common(1)[0][0]


def _split_fields(line: str, separator: str) -> list[str]:
    """Pola wiersza rozdzielonego średnikiem, tabulatorem lub przecinkiem (z obsługą cudzysłowów)."""
    return next(csv.reader([line], delimiter=separator))


def _field_number(field: str, decimal_comma: bool) -> float | None:
    """Liczba z pola, np. „12”, „12,5”, „12 kg”; None, gdy pole jest tekstem (np. „Śpiwór”, „Bateria 9V”)."""
    match = _NUMBER[decimal_comma].search(field)
    if match is None:
        return None
    rest = (field[: match.start()] + field[match.end() :]).strip()
    if any(char.isdigit() for char in rest) or len(rest) > _MAX_UNIT_LENGTH:
        return None
    return _to_float(match.group())


def _word_numbers(word: str, decimal_comma: bool) -> list[float] | None:
    """Liczby z jednego słowa: „12”, „[12,”, „12kg”, „12,7,11”; None, gdy słowo jest tekstem."""
    cleaned = word.strip(_PUNCTUATION)
    pattern = _WORD_NUMBER[decimal_comma]
    if match := pattern.fullmatch(cleaned):
        return [_to_float(match.group(1))]
    parts = cleaned.split(",")
    matches = [pattern.fullmatch(part) for part in parts]
    if len(parts) > 1 and all(matches):
        return [_to_float(match.group(1)) for match in matches if match]
    return None


def _clean_name(words: list[str]) -> str | None:
    """Nazwa z grupy słów bez końcowych słów kluczowych: [„Mapa”, „waga”] -> „Mapa”."""
    while len(words) > 1 and _keyword_role(words[-1]) is not None:
        words = words[:-1]
    return " ".join(words) or None


def _parse_separated_line(line_number: int, source: str, separator: str, decimal_comma: bool) -> _Line:
    """Wiersz z separatorem: pola liczbowe -> liczby, pola tekstowe -> tekst wiersza (nazwa)."""
    numbers, positions, texts = [], [], []
    for position, field in enumerate(_split_fields(source, separator)):
        number = _field_number(field.strip(), decimal_comma)
        if number is not None:
            numbers.append(number)
            positions.append(position)
        elif field.strip():
            texts.append(field.strip())
    return _Line(line_number, source, numbers, positions, " ".join(texts) or None, [None] * len(numbers))


def _parse_spaced_line(line_number: int, source: str, decimal_comma: bool) -> _Line:
    """Wiersz rozdzielony spacjami: liczby ze słów, tekst = pierwsza grupa słów (np. „Krem do opalania 11 70”).

    Dla każdej liczby zapamiętywane jest słowo stojące tuż przed nią (etykieta), np. „waga” w „waga 12 kg”.
    """
    numbers: list[float] = []
    labels: list[str | None] = []
    groups: list[list[str]] = [[]]
    for word in source.split():
        found = _word_numbers(word, decimal_comma)
        if found is not None:
            label = groups[-1][-1] if groups[-1] else None
            numbers.extend(found)
            labels.extend([label] + [None] * (len(found) - 1))
            if groups[-1]:
                groups.append([])
            continue
        cleaned = word.strip(_PUNCTUATION)
        if any(char.isalnum() for char in cleaned):
            groups[-1].append(cleaned)
    first_group = next((group for group in groups if group), [])
    return _Line(line_number, source, numbers, list(range(len(numbers))), _clean_name(first_group), labels)


def _parse_line(line_number: int, source: str, separator: str, decimal_comma: bool) -> _Line:
    if separator == _WHITESPACE:
        return _parse_spaced_line(line_number, source, decimal_comma)
    return _parse_separated_line(line_number, source, separator, decimal_comma)


# --- Wyciągnięcie tabeli --------------------------------------------------------------------------


def _capacity_and_lines(text: str, decimal_comma: bool | None) -> tuple[float | None, list[tuple[int, str]]]:
    """Kroki 2–3: pominięcie pustych wierszy i komentarzy, odczyt pojemności (pierwsza znaleziona wygrywa)."""
    capacity = None
    lines = []
    for line_number, raw_line in enumerate(text.lstrip("﻿").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        found = _find_capacity(line, decimal_comma is not False)
        if found is not None:
            capacity = found if capacity is None else capacity
        elif not line.startswith("#"):
            lines.append((line_number, line))
    return capacity, lines


def _split_header(parsed: list[_Line]) -> tuple[_Line | None, list[_Line]]:
    """Nagłówek = ostatni wiersz bez liczb przed danymi (wcześniejsze to wstęp, np. tytuł); dane = reszta."""
    first_data = next((index for index, line in enumerate(parsed) if line.numbers), None)
    if first_data is None:
        raise DataFormatError("Nie znaleziono liczb — dane muszą zawierać wagi i wartości przedmiotów.")
    header = parsed[first_data - 1] if first_data > 0 else None
    data = parsed[first_data:]
    for line in data:
        if not line.numbers:
            raise DataFormatError("wiersz bez liczb wśród danych — usuń go albo popraw", line.line_number)
    return header, data


def _is_count_line(data: list[_Line]) -> bool:
    """Krok 3a: pierwszy wiersz danych to „n W” (format zbiorów testowych, np. „10 269”, dalej „wartość waga”).

    Warunki: dwie liczby bez słów, n — liczba całkowita równa liczbie pozostałych wierszy, W > 0,
    każdy pozostały wiersz ma dwie liczby. Przypadkowa zgodność z wierszem przedmiotu jest mało
    prawdopodobna, a rozpoznanie i tak widać w podglądzie (pojemność i liczba przedmiotów).
    """
    first, rest = data[0], data[1:]
    if len(first.numbers) != 2 or first.text or not rest:
        return False
    count, capacity = first.numbers
    return (
        count.is_integer() and int(count) == len(rest) and capacity > 0 and all(len(line.numbers) == 2 for line in rest)
    )


def _check_column_counts(data: list[_Line]) -> None:
    """Krok 9: każdy wiersz danych musi mieć tyle samo liczb (najczęstsza liczba kolumn jest wzorcem)."""
    expected = Counter(len(line.numbers) for line in data).most_common(1)[0][0]
    wrong = [line for line in data if len(line.numbers) != expected]
    if not wrong:
        return
    message = f"liczba wartości liczbowych ({len(wrong[0].numbers)}) różni się od pozostałych wierszy ({expected})"
    if len(wrong) > 1:
        message += "; podobnie wiersze " + ", ".join(str(line.line_number) for line in wrong[1:6])
    raise DataFormatError(message, wrong[0].line_number)


def _numeric_role(name: str) -> ColumnRole:
    role = _keyword_role(name)
    return ColumnRole.SKIP if role in (None, ColumnRole.NAME) else role


def _header_roles(
    header: _Line | None, first_row: _Line, separator: str
) -> tuple[tuple[str, ...] | None, tuple[ColumnRole, ...] | None]:
    """Nazwy i role kolumn liczbowych odczytane z nagłówka."""
    if header is None:
        return None, None
    if separator == _WHITESPACE:
        words = [word.strip(_PUNCTUATION) for word in header.source.split()]
        pairs = [(word, _numeric_role(word)) for word in words]
        pairs = [(word, role) for word, role in pairs if role is not ColumnRole.SKIP]
        if len(pairs) != len(first_row.numbers):
            return None, None
        return tuple(word for word, _ in pairs), tuple(role for _, role in pairs)
    fields = _split_fields(header.source, separator)
    names = tuple(fields[position].strip() if position < len(fields) else "" for position in first_row.positions)
    return names, tuple(_numeric_role(name) for name in names)


def _label_role(label: str | None) -> ColumnRole | None:
    """Rola liczby wskazywana przez słowo przed nią: „waga 12” -> waga, „Przedmiot 1” / „Nr 1” -> numer."""
    role = _keyword_role(label or "")
    return ColumnRole.NUMBER if role is ColumnRole.NAME else role


def _roles_from_labels(data: list[_Line]) -> tuple[ColumnRole, ...] | None:
    """Role kolumn ze słów przy liczbach — gdy w każdym wierszu dana kolumna ma tę samą etykietę."""
    roles = []
    for column in range(len(data[0].numbers)):
        column_roles = {_label_role(line.labels[column]) for line in data}
        if len(column_roles) != 1:
            return None
        roles.append(column_roles.pop() or ColumnRole.SKIP)
    return tuple(roles)


def _valid_roles(roles: tuple[ColumnRole | None, ...]) -> bool:
    """Dokładnie jedna kolumna wag i jedna wartości, najwyżej jedna kolumna numerów."""
    return (
        roles.count(ColumnRole.WEIGHT) == 1
        and roles.count(ColumnRole.VALUE) == 1
        and roles.count(ColumnRole.NUMBER) <= 1
    )


def _is_numbering(values: list[float]) -> bool:
    """Czy kolumna może być numerem przedmiotu: dodatnie liczby całkowite bez powtórzeń."""
    return all(value > 0 and value.is_integer() for value in values) and len(set(values)) == len(values)


def _default_roles(rows: tuple[RawRow, ...]) -> tuple[ColumnRole, ...] | None:
    """Krok 8 bez nagłówka: 2 kolumny -> waga, wartość; 3 kolumny -> numer, waga, wartość; inaczej brak propozycji."""
    columns = len(rows[0].numbers) if rows else 0
    if columns == 2:
        return ColumnRole.WEIGHT, ColumnRole.VALUE
    if columns == 3 and _is_numbering([row.numbers[0] for row in rows]):
        return ColumnRole.NUMBER, ColumnRole.WEIGHT, ColumnRole.VALUE
    return None


def _propose_text_role(rows: tuple[RawRow, ...]) -> ColumnRole:
    """Tekst wiersza to nazwa, chyba że go brak albo jest taki sam we wszystkich wierszach (np. „Przedmiot”)."""
    texts = [row.text for row in rows]
    if not any(texts):
        return ColumnRole.SKIP
    return ColumnRole.NAME if len(rows) == 1 or len(set(texts)) > 1 else ColumnRole.SKIP


def extract_table(text: str, decimal_comma: bool | None = None) -> RawTable:
    """Wyciągnięcie wierszy liczb z dowolnego tekstu.

    Pomija puste wiersze, komentarze, słowa, jednostki i nawiasy; rozpoznaje separator kolumn,
    nagłówek i wiersz z pojemnością oraz proponuje role kolumn. `decimal_comma=None` oznacza
    automatyczne rozpoznanie przecinka dziesiętnego. Propozycja ról: z nagłówka, w drugiej
    kolejności ze słów przy liczbach („waga 12 kg”), w ostatniej — domyślna kolejność kolumn.
    Zgłasza DataFormatError, gdy brak danych albo wiersze mają różną liczbę liczb.
    """
    capacity, lines = _capacity_and_lines(text, decimal_comma)
    if not lines:
        raise DataFormatError("Nie znaleziono danych — wklej albo wczytaj listę przedmiotów.")
    separator = _choose_separator(lines)
    comma = decimal_comma if decimal_comma is not None else separator != ","
    header, data = _split_header([_parse_line(number, line, separator, comma) for number, line in lines])
    count_line = None
    if capacity is None and header is None and _is_count_line(data):
        count_line, capacity = data[0].line_number, data[0].numbers[1]
        data = data[1:]
    _check_column_counts(data)
    rows = tuple(RawRow(line.line_number, line.text, tuple(line.numbers)) for line in data)
    names, header_roles = _header_roles(header, data[0], separator)
    label_roles = _roles_from_labels(data)
    if header_roles and _valid_roles(header_roles):
        roles = header_roles
    elif label_roles and _valid_roles(label_roles):
        roles = label_roles
    elif count_line is not None:
        roles = ColumnRole.VALUE, ColumnRole.WEIGHT  # format „n W”: przedmioty zapisane jako „wartość waga”
    else:
        roles = _default_roles(rows)
    return RawTable(rows, names, capacity, roles, _propose_text_role(rows), count_line)


def is_horizontal(table: RawTable) -> bool:
    """Dane poziome: 2–3 wiersze opisane słowami „Wagi” / „Wartości” (/ „Nr”) — do transpozycji."""
    if not 2 <= len(table.rows) <= 3:
        return False
    roles = tuple(_keyword_role(row.text or "") for row in table.rows)
    return None not in roles and _valid_roles(roles)


def transpose(table: RawTable) -> RawTable:
    """Zamiana wierszy z kolumnami (dane poziome); słowa „Wagi” / „Wartości” na początku wierszy ustalają role.

    Po transpozycji numer wiersza w komunikatach o błędach to numer kolumny danych źródłowych.
    """
    columns = table.column_count
    rows = tuple(
        RawRow(line_number=column + 1, text=None, numbers=tuple(row.numbers[column] for row in table.rows))
        for column in range(columns)
    )
    labels = tuple(row.text or "" for row in table.rows)
    label_roles = tuple(_numeric_role(label) for label in labels)
    roles = label_roles if _valid_roles(label_roles) else _default_roles(rows)
    return RawTable(rows, labels if any(labels) else None, table.capacity, roles, ColumnRole.SKIP)


# --- Tworzenie przedmiotów ------------------------------------------------------------------------


def _check_roles(roles: tuple[ColumnRole, ...], columns: int) -> None:
    if len(roles) != columns:
        raise ValueError(f"liczba ról ({len(roles)}) nie odpowiada liczbie kolumn ({columns})")
    if roles.count(ColumnRole.WEIGHT) != 1 or roles.count(ColumnRole.VALUE) != 1:
        raise DataFormatError("Wskaż dokładnie jedną kolumnę „Waga” i jedną kolumnę „Wartość”.")
    if roles.count(ColumnRole.NUMBER) > 1:
        raise DataFormatError("Wskaż najwyżej jedną kolumnę „Nr”.")


def _item_numbers(rows: tuple[RawRow, ...], number_column: int | None) -> list[int]:
    """Krok 10: numery z kolumny „Nr” (dodatnie, całkowite, bez powtórzeń) albo kolejne od 1."""
    if number_column is None:
        return list(range(1, len(rows) + 1))
    numbers: list[int] = []
    for row in rows:
        value = row.numbers[number_column]
        if value <= 0 or not value.is_integer():
            raise DataFormatError(
                f"numer przedmiotu »{format_number(value)}« nie jest dodatnią liczbą całkowitą", row.line_number
            )
        if int(value) in numbers:
            raise DataFormatError(f"powtórzony numer przedmiotu {int(value)}", row.line_number)
        numbers.append(int(value))
    return numbers


def build_items(table: RawTable, roles: tuple[ColumnRole, ...], use_names: bool) -> tuple[Item, ...]:
    """Utworzenie przedmiotów według ról kolumn (dokładnie jedna WEIGHT i jedna VALUE, najwyżej jedna NUMBER).

    Przy `use_names` tekst wiersza staje się nazwą przedmiotu. Bez kolumny NUMBER przedmioty są
    numerowane kolejno od 1. Przy błędach zgłasza DataFormatError. Znaki i zakresy wag i wartości
    sprawdza dopiero walidacja (validation.py).
    """
    _check_roles(roles, table.column_count)
    weight_column = roles.index(ColumnRole.WEIGHT)
    value_column = roles.index(ColumnRole.VALUE)
    number_column = roles.index(ColumnRole.NUMBER) if ColumnRole.NUMBER in roles else None
    numbers = _item_numbers(table.rows, number_column)
    return tuple(
        Item(
            number=number,
            weight=row.numbers[weight_column],
            value=row.numbers[value_column],
            name=(row.text or "") if use_names else "",
        )
        for number, row in zip(numbers, table.rows, strict=True)
    )


def _split_names(text: str) -> list[str]:
    """Nazwy: jedna w wierszu, oddzielone średnikami albo (w jednym wierszu bez średników) przecinkami."""
    stripped = text.strip()
    if not stripped:
        return []
    if "\n" in stripped:
        parts = stripped.splitlines()
    elif ";" in stripped:
        parts = stripped.split(";")
    else:
        parts = stripped.split(",")
    names = (part.strip().strip("[]\"', ") for part in parts)
    return [name for name in names if name]


def parse_two_lists(
    weights_text: str, values_text: str, names_text: str = "", decimal_comma: bool = False
) -> tuple[Item, ...]:
    """Tryb „dwie listy”: wszystkie liczby z każdego tekstu, np. "w = [12, 7, 11]"; listy muszą mieć równą długość.

    Nazwy (opcjonalne): jedna w wierszu albo oddzielone średnikami.
    """
    weights = [_to_float(number) for number in _NUMBER[decimal_comma].findall(weights_text)]
    values = [_to_float(number) for number in _NUMBER[decimal_comma].findall(values_text)]
    if not weights or not values:
        raise DataFormatError("Podaj co najmniej jedną wagę i jedną wartość.")
    if len(weights) != len(values):
        raise DataFormatError(f"Listy mają różną długość — wag: {len(weights)}, wartości: {len(values)}.")
    names = _split_names(names_text)
    if names and len(names) != len(weights):
        raise DataFormatError(f"Liczba nazw ({len(names)}) różni się od liczby przedmiotów ({len(weights)}).")
    return tuple(
        Item(number=index + 1, weight=weight, value=value, name=names[index] if names else "")
        for index, (weight, value) in enumerate(zip(weights, values, strict=True))
    )


def parse_items_text(text: str) -> ParsedData:
    """Import automatyczny z proponowaną interpretacją, bez okna (testy, zbiory przykładowe).

    Dane poziome są transponowane automatycznie; gdy nie da się ustalić ról kolumn — DataFormatError.
    """
    table = extract_table(text)
    if is_horizontal(table):
        table = transpose(table)
    if table.roles is None:
        raise DataFormatError(
            "Nie udało się ustalić, która kolumna to waga, a która wartość "
            f"(liczba kolumn liczbowych: {table.column_count}) — wskaż je w oknie importu."
        )
    items = build_items(table, table.roles, use_names=table.text_role is ColumnRole.NAME)
    return ParsedData(items, table.capacity)


# --- Pliki ----------------------------------------------------------------------------------------


def read_text_file(path: Path) -> str:
    """Odczyt pliku tekstowego jako UTF-8 (z BOM lub bez); gdy nie jest poprawnym UTF-8 — jako Windows-1250."""
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1250", errors="replace")


def save_csv(path: Path, problem: KnapsackProblem) -> None:
    """Zapis w formacie tej aplikacji: "# capacity=", nagłówek number;name;weight;value (cudzysłowy przy nazwach — csv).

    Kodowanie UTF-8 ze znacznikiem BOM, aby Excel poprawnie pokazał polskie znaki.
    """
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        file.write(f"# capacity={format_number(problem.capacity)}\n")
        writer = csv.writer(file, delimiter=";", lineterminator="\n")
        writer.writerow(["number", "name", "weight", "value"])
        for item in problem.items:
            writer.writerow([item.number, item.name, format_number(item.weight), format_number(item.value)])
