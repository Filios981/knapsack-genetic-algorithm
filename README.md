# Problem plecakowy — podstawowy algorytm genetyczny

Autor: Filip Moś

Aplikacja okienkowa rozwiązująca dyskretny problem plecakowy (0/1) podstawowym algorytmem genetycznym.
Użytkownik podaje dowolną liczbę przedmiotów (waga, wartość) i pojemność plecaka, a program zwraca
listę przedmiotów, które mają trafić do plecaka, ich łączną wartość i wagę plecaka.

## Funkcje

- wprowadzanie przedmiotów w tabeli albo import tekstu lub pliku (CSV, TXT) w różnych układach,
  z podglądem i możliwością poprawienia, które kolumny to waga, a które wartość,
- podstawowy algorytm genetyczny: kodowanie binarne, selekcja kołem ruletki, krzyżowanie jednopunktowe,
  mutacja, pełna wymiana pokoleniowa,
- naprawa osobników przekraczających pojemność plecaka,
- wykres najlepszego wyniku i średniej populacji w kolejnych pokoleniach,
- porównanie wyniku z rozwiązaniem dokładnym (programowanie dynamiczne),
- animacja koła ruletki odtwarzająca losowania selekcji z wybranego pokolenia,
- widok „Krok po kroku”: jedno pokolenie rozpisane na etapy (populacja, losowania, krzyżowanie,
  mutacja, naprawa, nowa populacja),
- ziarno generatora liczb losowych — ten sam przebieg można powtórzyć.

## Parametry algorytmu

| parametr | wartość |
|---|---|
| prawdopodobieństwo krzyżowania *p_c* | 0.8 (dla każdej pary rodziców) |
| prawdopodobieństwo mutacji *p_m* | 0.2 (dla każdego potomka: zmiana jednego losowego genu) |
| selekcja | koło ruletki |
| osobniki z nadwagą | naprawa zachłanna — wyjmowanie przedmiotów o najmniejszym stosunku wartości do wagi, aż plecak się zmieści |
| warunek zatrzymania | brak poprawy najlepszego wyniku przez *G_s* = 500 pokoleń albo *G_max* = 1000 pokoleń |
| wielkość populacji *N* | 100 |

W oknie można też wybrać mutację „na gen” (każdy gen z prawdopodobieństwem *p_m*) i naprawę losową,
żeby porównać je z wariantami domyślnymi.

## Wyniki

Parametry domyślne, 20 uruchomień (ziarna 1–20) dla każdego zbioru z katalogu `samples/`:

| zbiór | przedmioty | optimum | trafienia optimum | średni wynik | najgorszy wynik | średni czas |
|---|---|---|---|---|---|---|
| p02-5-items | 5 | 51 | 100% | 100% | 100% | 0,20 s |
| p01-10-items | 10 | 309 | 100% | 100% | 100% | 0,23 s |
| p07-15-items | 15 | 1458 | 100% | 100% | 100% | 0,27 s |
| rosetta-22-items | 22 | 1030 | 100% | 100% | 100% | 0,30 s |
| random-50-items | 50 | 2297 | 100% | 100% | 100% | 0,68 s |
| random-100-items | 100 | 3582 | 0% | 99,33% | 98,21% | 1,39 s |

Mniejsza populacja (*N* = 10–20) dawała dla 100 przedmiotów 85–90% optimum, a większa (*N* = 500)
liczyła około pięć razy dłużej przy prawie tym samym wyniku. Przy *G_s* = 20–50 algorytm zatrzymywał się,
zanim znalazł dobre rozwiązanie dla większych zbiorów.

## Struktura projektu

```
knapsack_ga/
    models.py         struktury danych (przedmiot, problem, parametry, wynik)
    data_io.py        import danych z tekstu i plików, zapis CSV
    validation.py     sprawdzenie danych i parametrów
    exact.py          rozwiązanie dokładne (programowanie dynamiczne) do porównania
    background.py     uruchomienie algorytmu w osobnym procesie
    ga/               algorytm genetyczny — po jednym module na etap
        population.py  fitness.py  selection.py  crossover.py
        mutation.py  repair.py  stopping.py  engine.py (główna pętla)
    gui/              interfejs PyQt6
tests/                testy (pytest)
samples/              zbiory przykładowe ze znanym optimum
scripts/build_exe.py  budowanie wersji .exe
```

## Instalacja

Wymagany Python 3.11.

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Uruchomienie

```
.venv\Scripts\python.exe -m knapsack_ga
```

Wersja dla komputera bez Pythona:

```
.venv\Scripts\python.exe scripts\build_exe.py
```

Powstaje folder `dist\ProblemPlecakowy\` z plikiem `ProblemPlecakowy.exe` i katalogiem `samples\`.
`ProblemPlecakowy.exe --autotest` sprawdza, czy program działa na danym komputerze (kod wyjścia 0 —
poprawnie).

## Testy

```
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
```
