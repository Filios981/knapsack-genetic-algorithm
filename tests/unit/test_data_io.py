"""Testy importu danych."""

from pathlib import Path

import pytest

from knapsack_ga.data_io import (
    ColumnRole,
    DataFormatError,
    build_items,
    extract_table,
    format_number,
    is_horizontal,
    parse_items_text,
    parse_number,
    parse_two_lists,
    read_text_file,
    save_csv,
    transpose,
)
from knapsack_ga.models import Item, KnapsackProblem

# Dane zbioru p02-5-items.csv (P02) — te same dane zawierają też pliki format-*.
S01_PAIRS = [(12, 24), (7, 13), (11, 23), (8, 15), (9, 16)]

W, V, N, SKIP = ColumnRole.WEIGHT, ColumnRole.VALUE, ColumnRole.NUMBER, ColumnRole.SKIP


def pairs(items: tuple[Item, ...]) -> list[tuple[float, float]]:
    return [(item.weight, item.value) for item in items]


def load_sample(samples_dir: Path, name: str) -> str:
    return read_text_file(samples_dir / name)


# --- Liczby ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "decimal_comma", "expected"),
    [("12", False, 12.0), (" 12.5 ", False, 12.5), ("12,5", True, 12.5), ("12.5", True, 12.5), ("-3", False, -3.0)],
)
def test_parse_number_accepts_numbers(text, decimal_comma, expected):
    assert parse_number(text, decimal_comma) == expected


@pytest.mark.parametrize("text", ["12,5", "abc", "", "inf", "nan", "1e5", "12 kg", "1.2.3"])
def test_parse_number_rejects_non_numbers(text):
    with pytest.raises(ValueError):
        parse_number(text, decimal_comma=False)


def test_format_number_drops_trailing_zero():
    assert format_number(12.0) == "12"
    assert format_number(12.5) == "12.5"


# --- Kodowanie plików -----------------------------------------------------------------------------


def test_read_text_file_utf8_with_bom_strips_marker(samples_dir):
    text = read_text_file(samples_dir / "format-polish-excel.csv")
    assert not text.startswith("﻿")
    assert "Wartość" in text


def test_read_text_file_falls_back_to_windows_1250(samples_dir):
    text = read_text_file(samples_dir / "format-cp1250.csv")
    assert "Śpiwór" in text
    assert "Żywność" in text


# --- Wszystkie zbiory przykładowe -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("file_name", "count", "capacity"),
    [
        ("p02-5-items.csv", 5, 26),
        ("p01-10-items.csv", 10, 165),
        ("p07-15-items.csv", 15, 750),
        ("rosetta-22-items.csv", 22, 400),
        ("random-50-items.csv", 50, 880),
        ("random-100-items.csv", 100, 1678),
        ("edge-all-too-heavy.csv", 3, 5),
        ("edge-all-fit.csv", 3, 100),
        ("format-polish-excel.csv", 4, 10.5),
        ("format-pasted-text.txt", 5, None),
        ("format-text-with-units.txt", 5, 26),
        ("format-horizontal.txt", 5, 26),
        ("format-cp1250.csv", 5, 26),
        ("format-count-capacity.txt", 5, 26),
    ],
)
def test_samples_import_automatically(samples_dir, file_name, count, capacity):
    data = parse_items_text(load_sample(samples_dir, file_name))

    assert len(data.items) == count
    assert data.capacity == capacity
    assert [item.number for item in data.items] == list(range(1, count + 1))


@pytest.mark.parametrize(
    "file_name",
    [
        "p02-5-items.csv",
        "format-pasted-text.txt",
        "format-text-with-units.txt",
        "format-horizontal.txt",
        "format-cp1250.csv",
        "format-count-capacity.txt",
    ],
)
def test_samples_with_s01_data_give_s01_items(samples_dir, file_name):
    """format-text-with-units.txt: wartość przed wagą — role rozpoznane ze słów „wartość” i „waga” przy liczbach."""
    assert pairs(parse_items_text(load_sample(samples_dir, file_name)).items) == S01_PAIRS


def test_names_from_text_column(samples_dir):
    rosetta = parse_items_text(load_sample(samples_dir, "rosetta-22-items.csv")).items
    cp1250 = parse_items_text(load_sample(samples_dir, "format-cp1250.csv")).items

    assert (rosetta[0].name, rosetta[10].name) == ("mapa", "krem do opalania")
    assert [item.name for item in cp1250] == ["Śpiwór", "Latarka", "Kuchenka", "Żywność", "Mapa"]


def test_polish_excel_header_number_column_and_decimal_comma(samples_dir):
    items = parse_items_text(load_sample(samples_dir, "format-polish-excel.csv")).items
    assert pairs(items) == [(2.5, 10), (4.0, 12), (3.5, 9), (5.5, 20)]


# --- Separatory, nagłówki, pojemność, nazwy -------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "12\t24\n7\t13",  # komórki skopiowane z Excela
        "12;24\n7;13",
        "12 24\n7 13",
        "12,24\n7,13",  # przecinek bez spacji, jedna para w wierszu — separator kolumn
        "12, 24\n7, 13",  # przecinek ze spacją — separatorem są spacje
        "12 kg 24 zł\n7 kg 13 zł",
    ],
)
def test_separators(text):
    assert pairs(parse_items_text(text).items) == [(12, 24), (7, 13)]


def test_decimal_comma_with_spaces_and_decimal_dot_in_comma_csv():
    assert pairs(parse_items_text("12,5 24\n7,5 13").items) == [(12.5, 24), (7.5, 13)]
    assert pairs(parse_items_text("1,2.5,10\n2,3.5,20").items) == [(2.5, 10), (3.5, 20)]


def test_comma_csv_with_names_containing_spaces():
    items = parse_items_text("krem do opalania,11,70\nmapa,9,150").items
    assert [(item.name, item.weight, item.value) for item in items] == [("krem do opalania", 11, 70), ("mapa", 9, 150)]


@pytest.mark.parametrize(
    "header",
    ["weight;value", "Waga;Wartość", "WAGA [kg];Wartość [zł]", "wagi;ceny"],
)
def test_header_in_polish_and_english(header):
    assert pairs(parse_items_text(f"{header}\n12;24\n7;13").items) == [(12, 24), (7, 13)]


def test_header_with_reversed_columns():
    assert pairs(parse_items_text("Wartość;Waga\n24;12\n13;7").items) == [(12, 24), (7, 13)]


def test_header_with_extra_unknown_column_is_skipped():
    table = extract_table("Nr;Waga;Wartość;Objętość\n1;12;24;3\n2;7;13;4")
    assert table.roles == (N, W, V, SKIP)


def test_spaced_header_with_name_and_units():
    items = parse_items_text("Lp. Nazwa Waga [kg] Wartość [zł]\n1 Krem do opalania 11 70\n2 Mapa 9 150").items
    assert [(item.number, item.name, item.weight, item.value) for item in items] == [
        (1, "Krem do opalania", 11, 70),
        (2, "Mapa", 9, 150),
    ]


def test_title_before_header_is_ignored():
    assert pairs(parse_items_text("Lista przedmiotów\nWaga;Wartość\n12;24").items) == [(12, 24)]


@pytest.mark.parametrize(
    ("line", "capacity"),
    [
        ("# capacity=165", 165),
        ("# pojemność=10,5", 10.5),
        ("Pojemność plecaka: 50 kg", 50),
        ("W = 26", 26),
        ("Maksymalna waga: 30", 30),
        ("max 40", 40),
    ],
)
def test_capacity_detection(line, capacity):
    assert parse_items_text(f"{line}\n12 24\n7 13").capacity == capacity


def test_count_and_capacity_line(samples_dir):
    """format-count-capacity.txt: pierwszy wiersz „n W”, dalej „wartość waga” (np. zbiory low-dimensional)."""
    table = extract_table(load_sample(samples_dir, "format-count-capacity.txt"))
    assert (table.count_line, table.capacity, table.roles) == (1, 26, (V, W))
    assert len(table.rows) == 5


@pytest.mark.parametrize(
    "text",
    [
        "4 26\n24 12\n13 7\n23 11\n15 8\n16 9",  # n różne od liczby pozostałych wierszy
        "5.5 26\n24 12\n13 7\n23 11\n15 8\n16 9",  # n niecałkowite
        "W = 30\n5 26\n24 12\n13 7\n23 11\n15 8\n16 9",  # pojemność podana słowem — wiersz to przedmiot
        "weight value\n2 26\n24 12\n13 7",  # nagłówek — pierwszy wiersz to przedmiot
        "Plecak 2 26\n24 12\n13 7",  # słowo w wierszu — przedmiot z nazwą
    ],
)
def test_count_line_requires_exact_match(text):
    assert extract_table(text).count_line is None


def test_comment_mentioning_capacity_without_value_is_not_capacity(samples_dir):
    """edge-all-too-heavy.csv: komentarz „heavier than the capacity, optimum value = 0” nie może dać pojemności 0."""
    assert parse_items_text(load_sample(samples_dir, "edge-all-too-heavy.csv")).capacity == 5


def test_names_in_spaced_text():
    items = parse_items_text("Krem do opalania 11 70\nMapa 9 150").items
    assert [item.name for item in items] == ["Krem do opalania", "Mapa"]


def test_name_after_number_column():
    items = parse_items_text("1 Mapa 9 150\n2 Kompas 13 35").items
    assert [(item.number, item.name) for item in items] == [(1, "Mapa"), (2, "Kompas")]


def test_trailing_keyword_is_removed_from_name():
    items = parse_items_text("Mapa — waga 9 kg, wartość 150 zł\nKompas — waga 13 kg, wartość 35 zł").items
    assert [(item.name, item.weight, item.value) for item in items] == [("Mapa", 9, 150), ("Kompas", 13, 35)]


def test_identical_text_in_all_rows_is_not_a_name(samples_dir):
    table = extract_table(load_sample(samples_dir, "format-text-with-units.txt"))
    assert table.text_role is SKIP


def test_three_columns_without_numbering_get_no_proposal():
    """Trzecia kolumna bez numeracji (np. 2.5) — role musi wskazać użytkownik."""
    assert extract_table("2.5 12 24\n2.5 7 13").roles is None


# --- Błędy ----------------------------------------------------------------------------------------


def test_different_number_count_reports_line():
    with pytest.raises(DataFormatError) as error:
        extract_table("12;24\n7;13\n# komentarz\n11")
    assert error.value.line_number == 4
    assert str(error.value).startswith("Wiersz 4:")


def test_row_without_numbers_inside_data_reports_line():
    with pytest.raises(DataFormatError) as error:
        extract_table("12;24\nbrak danych\n7;13")
    assert error.value.line_number == 2


@pytest.mark.parametrize("text", ["", "   \n# tylko komentarz\n", "same słowa\nbez liczb"])
def test_no_data_is_an_error(text):
    with pytest.raises(DataFormatError):
        extract_table(text)


def test_too_many_columns_without_header_needs_user_roles():
    with pytest.raises(DataFormatError, match="wskaż je w oknie importu"):
        parse_items_text("1 2 3 4\n5 6 7 8")


def test_forced_decimal_dot_rejects_decimal_comma():
    with pytest.raises(DataFormatError):
        extract_table("2,5;10\n3;20", decimal_comma=False)


@pytest.mark.parametrize(
    "roles",
    [(W, SKIP), (W, W), (N, N)],
)
def test_build_items_requires_one_weight_and_one_value(roles):
    table = extract_table("12;24\n7;13")
    with pytest.raises(DataFormatError):
        build_items(table, roles, use_names=False)


def test_build_items_rejects_bad_numbering():
    duplicated = extract_table("1;12;24\n1;7;13")
    fractional = extract_table("1.5;12;24\n2;7;13")
    with pytest.raises(DataFormatError, match="powtórzony numer") as error:
        build_items(duplicated, (N, W, V), use_names=False)
    assert error.value.line_number == 2
    with pytest.raises(DataFormatError, match="dodatnią liczbą całkowitą"):
        build_items(fractional, (N, W, V), use_names=False)


def test_build_items_with_user_roles_and_numbers_from_data():
    table = extract_table("7 24 12\n3 13 7")
    items = build_items(table, (N, V, W), use_names=False)
    assert [(item.number, item.weight, item.value) for item in items] == [(7, 12, 24), (3, 7, 13)]


# --- Zapis i ponowny odczyt -----------------------------------------------------------------------


def test_save_and_load_round_trip(tmp_path):
    problem = KnapsackProblem(
        items=(
            Item(number=3, weight=2.5, value=10, name="Śpiwór; zimowy"),
            Item(number=7, weight=4, value=12.25, name="Żywność"),
            Item(number=9, weight=1, value=0, name=""),
        ),
        capacity=10.5,
    )
    path = tmp_path / "problem.csv"

    save_csv(path, problem)
    data = parse_items_text(read_text_file(path))

    assert data.items == problem.items
    assert data.capacity == problem.capacity


# --- Tryb „dwie listy” ----------------------------------------------------------------------------


def test_two_lists_like_in_code():
    items = parse_two_lists("w = [12, 7, 11, 8, 9]", "v = [24, 13, 23, 15, 16]")
    assert pairs(items) == S01_PAIRS


def test_two_lists_from_columns_with_decimal_comma_and_names():
    items = parse_two_lists("2,5\n4,0", "10\n12", names_text="mapa\nkompas", decimal_comma=True)
    assert [(item.name, item.weight, item.value) for item in items] == [("mapa", 2.5, 10), ("kompas", 4.0, 12)]


@pytest.mark.parametrize("names_text", ["mapa; kompas", "['mapa', 'kompas']", "mapa, kompas"])
def test_two_lists_name_separators(names_text):
    items = parse_two_lists("1 2", "3 4", names_text=names_text)
    assert [item.name for item in items] == ["mapa", "kompas"]


def test_two_lists_of_different_length():
    with pytest.raises(DataFormatError, match="wag: 3, wartości: 2"):
        parse_two_lists("1 2 3", "4 5")


def test_two_lists_with_wrong_number_of_names():
    with pytest.raises(DataFormatError, match="Liczba nazw"):
        parse_two_lists("1 2", "3 4", names_text="mapa")


# --- Dane poziome ---------------------------------------------------------------------------------


def test_horizontal_data_with_labels_is_detected_and_transposed(samples_dir):
    table = extract_table(load_sample(samples_dir, "format-horizontal.txt"))
    transposed = transpose(table)

    assert is_horizontal(table)
    assert transposed.roles == (W, V)
    assert pairs(build_items(transposed, transposed.roles, use_names=False)) == S01_PAIRS


def test_two_lists_file_in_rows_mode_needs_transposition(samples_dir):
    """format-two-lists.txt w trybie „wiersze”: etykiety „w” / „v” nierozpoznane — użytkownik naciska „Transponuj”."""
    table = extract_table(load_sample(samples_dir, "format-two-lists.txt"))
    transposed = transpose(table)

    assert not is_horizontal(table)
    assert table.capacity == 26
    assert transposed.roles == (W, V)
    assert pairs(build_items(transposed, transposed.roles, use_names=False)) == S01_PAIRS
