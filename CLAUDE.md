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

**Wszystkie trzy źródła leżą w tym repozytorium** — razem z `assemble.py`. Do 09.2026 tak nie
było: istniały wyłącznie w piaskownicy, a repozytorium miało sam wynik składania. Piaskownica
została wyczyszczona i źródła trzeba było odzyskiwać z `sushi-planner.html`. Odzyskanie wyszło
co do bajtu, ale **plik generowany nie jest kopią zapasową źródeł** i nie wolno go za taką
uważać.

Znaczniki, w które `assemble.py` wstawia treść, to `/*SEED*/` i `/*PART2*/` w `template.html`
— każdy dokładnie raz. Wstawka idzie jako tekst, bez ponownej serializacji JSON-a: inaczej
każde złożenie dawałoby inny plik przy identycznych danych.

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
| `test-offline.py` | 1363 asercji, Playwright, tryb offline | ~80 s |
| `test-serwer.py` | 428 asercji, end-to-end trybu serwerowego, wszystkie trasy API | ~70 s |
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
  własne `margin` liczyło się dwa razy i wydruk lądował na drugiej stronie. Wyjątek:
  wydruk z przeglądarki (tryb bez serwera), gdzie nie ma komu ich podać — wtedy i tylko
  wtedy dokument dostaje `margin` w `@page`. Format strony klient wybiera NAZWĄ układu
  (`strona:'etykieta'`), nigdy liczbami: wymiary siedzą w `UKLADY_STRON` w `server.py`.
- **Etykieta na opakowanie to jedyne miejsce bez Montserrata.** Naklejki składane dotąd
  w Wordzie są w Aptosie, a Montserrat jest od niego o 17% szerszy — akapit o alergenach
  łamał się na cztery linijki zamiast trzech. Aptosa (Microsoft) nie wolno wysłać na serwer,
  więc stack to `Aptos,Lato,…`: na maszynie z Office'em przeglądarka znajdzie oryginał,
  na serwerze rysuje Lato, dobrane pomiarem czterech zdań o znanej szerokości z gotowych
  etykiet (odchyłka 1,8%; Inter 11%, Montserrat 17%).
- **Etykieta ma dwa bloki i każdy odpowiada na inne pytanie.** Pierwszy — co jest
  w pudełku: ilość krążków i nazwa rolki, ciągiem, po kropce. Drugi — z czego to jest:
  składniki CAŁEGO zestawu, każdy raz, malejąco według masy, półprodukty rozłożone.
  Rozbicie składu na rolki stawiało tę samą sałatę na liście pięć razy i nikt nie
  doczytywał jej do końca. Kolejność po masie to nie ozdoba — tak wygląda wykaz
  składników na każdym opakowaniu w sklepie. Dodatki (kategoria z ustawień) idą
  na KONIEC pierwszego bloku, nie do składu: leżą obok sushi, a nie w nim, i przy
  sortowaniu masą lądowały wśród ilości śladowych. Liczy się to tylko dla dodatków
  samego zestawu — ten sam sezam użyty w środku rolki zostaje w składzie, bo zjada
  się go razem z sushi. Decyduje PIERWSZE wejście, a rolki liczymy przed dodatkami.
- **Masy liczą się przez mnożnik, nie przez sumowanie porcji.** Pozycja rolki wchodzi
  jako `kawałki/kawałki w rolce`, wejście w półprodukt dzieli przez jego wydajność.
  Składnik bez przelicznika na gramy (`unitGrams` = null) ZOSTAJE na liście, ale na
  końcu — i panel mówi o tym wprost, bo inaczej jego miejsce kłamałoby.
- **`<datalist>` to nie jest lista rozwijana.** Wygląda jak zwykłe pole tekstowe, podpowiada
  dopiero w trakcie pisania i nie daje się rozwinąć klikiem — a kategoria wpisywana z palca
  kończy się „Bazowe" obok „bazowe". Wszędzie, gdzie człowiek ma COŚ WYBRAĆ, idzie
  `combo()` + `fillCombo()`. Gdy wartość musi dać się także utworzyć (kategorie, jednostki
  — lista powstaje z tego, co już wpisano), dochodzi `{wolny:true}`: tekst spoza listy jest
  wtedy prawidłową wartością. Bez tej flagi lista zostaje ZAMKNIĘTA i wpis spoza niej jest
  po cichu cofany — tak ma być przy wyborze rolki czy składnika.
- **Wpis własny trafia do ukrytego pola dopiero przy zamknięciu listy.** Cokolwiek ma
  nadążać za pisaniem (podgląd ceny, przelicznik), czyta `#id_q`, a nie `#id`, i słucha
  `input` na `#id_q`.
- **Przekierowanie `>` pisze przez dowiązanie symboliczne** — zawsze `rm -f` przed zapisem.
- **Pliki wgrane przez stronę GitHuba tracą bit wykonywalności** (`install.sh`, `*.sh`).
- **Skrypty publikujące pomijają tylko SIEBIE, nie swoje rodzeństwo.** Publikacja z Maca
  wysyła `publikuj.bat` i `publikuj.ps1`, a publikacja z Windowsa — `publikuj.command`.
  Gdy każdy pomijał wszystkie trzy, żaden nie trafiał do repozytorium: wersje windowsowe
  istniały wyłącznie na jednym dysku i trzeba je było napisać od nowa, kiedy stamtąd znikły.
- **Ścieżki w testach liczą się od położenia pliku testu** (`KAT`), nigdy wpisane na sztywno.
  Wpisany katalog piaskownicy zniknął razem z nią i żaden test nie ruszył.
  Przy okazji sprawdź nazwę pliku, a nie tylko katalog: `KAT + '/fixture.png'` wskazywało
  obok `test-fixture.png` i Playwright czekał 30 s, zanim padł.
- **Zmiana mechanizmu wyróżnienia wymaga przeszukania WSZYSTKICH asercji.** Gdy `--ramka-wybor`
  przeszło z `box-shadow: inset` na `outline`, trzy stare asercje (`.nav.on` w dwóch miejscach,
  `.kal td.zaz`) dalej pytały o `boxShadow` i zgłosiły awarię czegoś, co działało.
  `grep -n boxShadow test-offline.py` przed zmianą, nie po niej. Uwaga: `inset` w kodzie
  granicy miesiąca i pustego miejsca w grafiku to co innego — tam zostaje.
- **Dwa `pg.on('dialog', …)` naraz to wyjątek przy PIERWSZYM okienku po rejestracji.**
  Drugi nasłuch dostaje okienko już obsłużone i wywala „Cannot accept dialog which is
  already handled" — w miejscu, które z przyczyną nie ma nic wspólnego. Rejestrując
  kolejny, zdejmij poprzedni (`pg.remove_listener`), więc trzymaj go pod nazwą.
- **Funkcja `async`, na którą nikt nie czeka, kończy się przed czasem.** `pdfEtykiety`
  wołało `zrobPdf` bez `await`; test zdążył przywrócić prawdziwy `confirm`, zanim doszła
  odpowiedź serwera, i okienko wyskoczyło naprawdę. Jeśli funkcja jest `async`, to
  wszystko, co w niej czeka na sieć, ma być `await`-owane — nawet gdy wołający wyniku
  nie używa.
- **Karta otwarta przed publikacją chodzi na starym kodzie.** Okno Aktualizacji pyta serwera,
  więc pokaże nową wersję, choć plik aplikacji w tej karcie jest sprzed wydania. Objaw:
  funkcja „przestała działać", a w konsoli `typeof nowaFunkcja === 'undefined'`. Zanim
  zaczniesz szukać w kodzie — twarde przeładowanie (`Cmd+Shift+R`). Kosztowało to jedno
  śledztwo 05.09.2026.

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
