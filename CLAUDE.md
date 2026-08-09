# Sushi Planner — zasady pracy nad kodem

Aplikacja do liczenia food costu i planowania produkcji dla Noto Sushi.
Działa w trzech trybach: lokalnym (plik z dysku), serwerowym (Mikrus) i chmurowym (Supabase).

## Architektura — przeczytaj, zanim cokolwiek zmienisz

`sushi-planner.html` to **plik generowany**. Nigdy go nie edytuj ręcznie.

```
template.html  (CSS + silnik)
part2.js       (widoki)          →  assemble.py  →  sushi-planner.html
seed.json      (dane startowe)
```

Zmieniasz `template.html`, `part2.js` albo `seed.json`, potem uruchamiasz `assemble.py`.

`server.py` to osobny byt — serwer HTTP na **samej bibliotece standardowej Pythona 3.8+**.
Żadnych zależności zewnętrznych, ma się mieścić w ~25 MB RAM.

## Dyscyplina zmian

**Każda zmiana w wygenerowanych źródłach to skrypt Pythona**, który najpierw weryfikuje
wszystkie wzorce, a dopiero potem zapisuje:

```python
if src.count(old) != 1:
    sys.exit(f"wzorzec nie jest unikalny: {src.count(old)} trafień")
src = src.replace(old, new)
```

Nigdy nie zapisuj pliku „w ciemno". Jeśli wzorzec nie pasuje dokładnie raz — przerwij i zgłoś.

## Testy — obowiązkowe przed każdym wydaniem

| Skrypt | Co sprawdza | Czas |
|---|---|---|
| `test-offline.py` | 778 asercji, Playwright, tryb offline | ~38 s |
| `test-serwer.py` | 80 asercji, end-to-end trybu serwerowego, wszystkie trasy API | ~32 s |
| `test-aktualizacji.sh` | pełny cykl samoaktualizacji na prawdziwym repo git | dłużej |

Do iterowania nad jedną rzeczą: `test-offline.py --do NAZWA_SEKCJI` (≈6 s).

**Nie zgłaszaj zadania jako zrobionego, jeśli testy nie przechodzą.**

## Czego pilnować szczególnie

- **`server.py` nigdy nie może się skurczyć.** Raz opublikowanie starszej wersji skasowało
  `/api/update/*`, `/api/users/*` i poprawkę keep-alive. Przed zmianą porównaj listę tras
  z tą w `test-serwer.py`.
- **Migracje danych dopisuj do `migrateAll()`**, nie do pojedynczej ścieżki wczytywania.
  Ten sam błąd (migracja w `load()`, ale nie w `load2()`) zdarzył się dwa razy.
- **Na Pulpicie nie ma pieniędzy.** Żaden ekran dnia nie pokazuje cen, kosztów ani food costu.
  Test szuka wzorca „liczba + zł" na każdym ekranie Pulpitu i musi nie znaleźć nic.
- **Marginesy wydruku ustawia wyłącznie Gotenberg.** W CSS tylko `@page{size:A4}` —
  własne `margin` liczyło się dwa razy i wydruk lądował na drugiej stronie.
- **Przekierowanie `>` pisze przez dowiązanie symboliczne** — zawsze `rm -f` przed zapisem.
- **Pliki wgrane przez stronę GitHuba tracą bit wykonywalności** (`install.sh`, `*.sh`).

## Logika obliczeń — nie zmieniaj bez wyraźnego polecenia

- cena jednostkowa składnika = cena opakowania ÷ ilość w opakowaniu
- koszt półproduktu = suma kosztów składników (ilość + odpad) ÷ wydajność
- **food cost % = koszt netto ÷ przychód netto**, przychód netto = cena brutto ÷ (1 + VAT)
- koszt zestawu = Σ (koszt kawałka × liczba kawałków) + dodatki
- sugerowana cena = koszt netto × (1 + VAT) ÷ docelowy food cost, zaokrąglona do końcówki ,90
- średnia food costu jest **ważona**: sumuj koszty i przychody, dziel dopiero na końcu;
  pozycje bez cen składników wypadają ze średniej i są liczone osobno jako pominięte

Ceny zakupu zawsze **netto**, ceny sprzedaży zawsze **brutto**.
Dwa kanały sprzedaży: Vending (VAT 5%) i Dostawa (8%) — osobna cena i stawka.

## Identyfikacja wizualna

Czerwień `#BD172F`, tusz `#1D1D1B`, Montserrat z systemowym zapasem, znak firmowy jako SVG
w `currentColor`. Tryb ciemny ma własne, rozjaśnione warianty tokenów.
Odnośniki nie są podkreślone — podkreślenie pojawia się dopiero pod kursorem.

## Wydania

Numer wersji siedzi w pliku `VERSION` (semver, np. `1.59.0`). Podbij go w tym samym commicie,
co zmiana. Serwer produkcyjny zaciąga `main` sam, timerem systemd ok. 4:30, i **sam wraca
do poprzedniego commita**, jeśli po restarcie nie odpowiada.

## Czego NIE robić bez pytania

- **Nie zmieniaj cen zestawów.** Cennik jest niespójny (rabat od 0% do 32% względem sumy
  cen à la carte) i jest tego świadomy właściciel — decyzja należy do niego.
- Nie dodawaj zależności zewnętrznych ani do `server.py`, ani do aplikacji.
  Zero buildu i zero `node_modules` to celowa decyzja, nie niedopatrzenie.
- Nie ruszaj danych produkcyjnych (`/var/lib/sushi-planner`) — repozytorium zawiera tylko kod.

## Język

Interfejs, komunikaty, komentarze w kodzie i opisy commitów — **po polsku**.
Nazwy zmiennych i funkcji mogą być po angielsku tam, gdzie już takie są.
