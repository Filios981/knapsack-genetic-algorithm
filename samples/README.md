# Zbiory przykładowe

Optima obliczone programowaniem dynamicznym; dla zbiorów p01, p02, p07 i rosetta zgodne z wartościami
podawanymi w źródłach.

## Zbiory ze znanym optimum

| plik | *n* | pojemność | optimum | waga optimum | przedmioty w optimum | źródło |
|---|---|---|---|---|---|---|
| p02-5-items.csv | 5 | 26 | 51 | 26 | 2, 3, 4 | J. Burkardt, *KNAPSACK_01* — P02 |
| p01-10-items.csv | 10 | 165 | 309 | 165 | 1, 2, 3, 4, 6 | J. Burkardt, *KNAPSACK_01* — P01 |
| p07-15-items.csv | 15 | 750 | 1458 | 749 | 1, 3, 5, 7, 8, 9, 14, 15 | J. Burkardt, *KNAPSACK_01* — P07 |
| rosetta-22-items.csv | 22 | 400 | 1030 | 396 | 1, 2, 3, 4, 5, 7, 11, 16, 17, 18, 19, 21 | Rosetta Code, *Knapsack problem/0-1* (nazwy przetłumaczone) |
| random-50-items.csv | 50 | 880 | 2297 | 880 | 31 przedmiotów | losowy, ziarno 2026 |
| random-100-items.csv | 100 | 1678 | 3582 | 1677 | 53 przedmioty | losowy, ziarno 1018 |

## Przypadki brzegowe i formaty

Pliki `format-*` (poza `format-polish-excel.csv`) zawierają dane z `p02-5-items.csv` zapisane na różne
sposoby (optimum 51 przy pojemności 26).

| plik | co sprawdza |
|---|---|
| edge-all-too-heavy.csv | każdy przedmiot cięższy niż plecak — wynik: pusty plecak |
| edge-all-fit.csv | wszystkie przedmioty się mieszczą — wynik: wszystkie |
| format-polish-excel.csv | eksport z polskiego Excela: BOM, średniki, przecinki dziesiętne, pojemność 10,5 w komentarzu |
| format-pasted-text.txt | tekst rozdzielony spacjami, bez nagłówka i bez pojemności |
| format-two-lists.txt | listy `w = [...]`, `v = [...]` i `W = 26` |
| format-text-with-units.txt | opisy i jednostki, wartość przed wagą, pojemność w tekście |
| format-horizontal.txt | dane poziome: wiersz wag i wiersz wartości |
| format-cp1250.csv | kodowanie Windows-1250, końce linii CRLF, nazwy przedmiotów |
| format-count-capacity.txt | pierwszy wiersz „liczba przedmiotów, pojemność”, dalej „wartość waga” |
