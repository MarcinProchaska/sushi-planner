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
| `test-offline.py` | 1509 asercji, Playwright, tryb offline | ~80 s |
| `test-serwer.py` | 453 asercji, end-to-end trybu serwerowego, wszystkie trasy API | ~70 s |
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
- **Ceny Too Good To Go stoją OBOK rachunku, nie w nim.** `tggCena` i `tggOpak` przy
  zestawie nie wchodzą do `setCalc` — food cost, marża i rabat liczą się wyłącznie
  z kanałów Vending i Dostawa i mają się nie zmienić ani o grosz przez to, że zestaw
  dostał drugą cenę na inny serwis. Trzy asercje pilnują tego wprost (koszt, food cost,
  marża przed zmianą i po). Gdyby kiedyś miało być inaczej, to decyzja właściciela.
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
- **Skrypty publikujące nie pomijają NICZEGO, w tym siebie.** Każdy miał na liście wyjątków
  własną nazwę — i `publikuj.ps1` nie było ani w repozytorium, ani w historii gita, bo żaden
  skrypt nigdy go nie wysłał; trzeba je było napisać od nowa, kiedy zniknął dysk, na którym
  leżało. Lista wyjątków to dziś tylko `.*`, `Icon*`, `desktop.ini`, `*.download`, `~$*`.
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
- **Zanim wstawisz pole wyboru w ciasne miejsce, policz, co ma w nim się zmieścić.**
  Lista w wolnym miejscu grafiku dostała pole szerokie na 54 px, a miała pokazywać
  „Bartłomiej Przybylski · 118 h" — czyli godziny, jedyny powód, dla którego ta lista
  podaje cokolwiek poza nazwiskiem, były ucięte. Rozwiązanie: element w komórce tylko
  OTWIERA okienko, a okienko ma własną szerokość i nie musi się w nim mieścić.
- **`font: inherit` na przycisku zabiera też rozmiar pisma.** Pastylka jako `<button>`
  brała 11 px z rodzica zamiast 10 px z `.kod` i była o dwa piksele wyższa od zwykłej —
  rząd w komórce dnia falował. Resetując chrom przycisku: `font-family`, nie `font`.
- **Pole formularza w klikalnym kontenerze musi zatrzymać kliknięcie.** Komórka dnia
  w grafiku ma nasłuch, który zaznacza dzień i woła `render()`. Lista wolnego miejsca
  siedzi w tej komórce, więc klik w nią przerysowywał grafik i wymieniał pole pod palcem:
  lista otwierała się na `mousedown` (przez `focus`) i znikała na `mouseup`. Wygląda to
  jak „lista nie działa", a jest to konflikt dwóch nasłuchów. Wstawiając interaktywny
  element w coś, co już reaguje na klik: `stopPropagation` na `mousedown` i `click`.
  Skutek uboczny do sprawdzenia w testach: asercje klikające `[data-graf-dzien]` trafiały
  w środek komórki, czyli teraz w listę — celują w `.dn`.
- **Ta sama osoba wpisana dwa razy zajmuje JEDNO miejsce.** Fikstrura „obsadź zmianę
  do kompletu" pętlą po `slots` z jednym `os-a` daje jedno zajęte miejsce, nie komplet —
  aplikacja słusznie nie dubluje. Do kompletu potrzeba tylu różnych osób, ile miejsc.
- **Powtórzony znak w menu musi znaczyć powtórzoną rzecz.** Nowa zakładka „Faktury"
  dostała `faktura`, którego używają już „Zakupy" — asercja złapała to od razu.
  Nowa zakładka = nowy znak w `IKONY`, chyba że naprawdę prowadzi tam, gdzie istniejąca.
- **Do ekranu prowadzą TRZY drogi: kafelek, pozycja w menu i adres.** Granica uprawnień
  musi stać we wszystkich trzech — sam ukryty kafelek nie chroni niczego, bo `go()`
  wywołane z adresu albo z historii omija go bokiem.
- **`1fr` w siatce to `minmax(auto, 1fr)`, więc kolumna rozpycha się pod treść.**
  Kafelek z najdłuższą kwotą był na telefonie szerszy od sąsiada, choć siatka miała
  „dwie równe kolumny". `minmax(0, 1fr)` odbiera kolumnie prawo do rośnięcia. Ta sama
  pułapka co `min-width:auto` we flexie.
- **Reguła dla telefonu pisana na `a.card` omija kafelki, które nie są odnośnikami.**
  Kafelek faktur donikąd nie prowadzi, więc jest `div`-em — i jako jedyny zostawał
  z większym luzem i widocznym podtytułem. Selektor pisz na `.card`, chyba że chodzi
  właśnie o klikalność.
- **Reguła biznesowa poza repozytorium i tak musi mieć test.** Trzy liczby na kafelku
  zobowiązań liczy węzeł Code w `n8n-platnosci-cu20.json`, czyli JavaScript, którego
  nie wykonuje ani aplikacja, ani serwer. Sekcja testów wyciąga `jsCode` z pliku workflow
  i puszcza go na fikstrurach w stronie Playwrighta — to ten sam silnik. Inaczej pierwszym
  sprawdzeniem byłby przebieg na produkcji, a pomyłka w statusach wychodzi dopiero wtedy,
  gdy ktoś porówna kafelek z CU 2.0.
- **Piąty raz test zależny od kalendarza — tym razem nie od daty, tylko od DNIA TYGODNIA.**
  Sekcja grafiku ustawiała szablon na JUTRO, a potem brała `querySelector('.tyg
  [data-graf-wolne]')`, czyli PIERWSZĄ pastylkę w widoku tygodnia — a ta należy do
  poniedziałku. Zgadzało się to raz na siedem dni i przez cztery dni wyglądało jak
  zepsuty wybór z listy. Reguła rozszerza się: **asercja ma adresować to, co sama
  ustawiła** (tu: selektor z `data-graf-wolne^="<iso>|"`), a nie to, co akurat wyszło
  pierwsze. „Pierwszy na ekranie" jest bezpieczne tylko wtedy, gdy na ekranie jest jeden.
- **Włączenie `SRV.on` w teście offline budzi WSZYSTKIE kafelki serwerowe.** Nowa sekcja
  o zobowiązaniach podniosła tryb serwerowy i kafelek Sprzedaży obok sięgnął po dane
  przez `file://` — błąd konsoli wypadł dopiero w sekcji BŁĘDY KONSOLI na końcu suity,
  czyli jak najdalej od przyczyny. Podnosząc `SRV.on`, uciszaj sąsiadów (tu: podstawiony
  `SPRZ_PUL_KLUCZ`) i przywracaj stan na końcu sekcji.
- **PowerShell NIE rozróżnia wielkości liter w nazwach zmiennych, bash rozróżnia.**
  Przy przepisywaniu `publikuj.command` na `publikuj.ps1` `$ZDALNE` (tablica plików
  z GitHuba) i `$zdalne` (SHA jednego pliku) skleiły się w jedną zmienną: pierwszy plik
  jeszcze się porównał, drugi poszedł na PUT bez `sha` (HTTP 422), trzeci indeksował już
  `$null`. To samo siedziało w `$REPO` kontra `$repo`. Pilnuje tego teraz sekcja
  **SKRYPTY PUBLIKUJĄCE** w `test-offline.py` — czyta plik, nie uruchamia go, bo
  PowerShella w piaskownicy nie ma. Przepisując cokolwiek z basha na PowerShell:
  najpierw przejrzyj nazwy zmiennych, potem logikę.
- **Skryptów publikujących nie da się tu uruchomić — więc sprawdzaj je statycznie.**
  `publikuj.ps1` pojechał do Marcina nigdy nieodpalony i wywrócił się na drugim pliku.
  Co da się sprawdzić bez PowerShella: BOM, końce wierszy, kolizje nazw zmiennych,
  zawartość listy wyjątków, zgodność liczenia SHA blobu z `git hash-object`.
- **`outline-width` liczy się na 3 px, gdy ramki nie ma.** Wartość początkowa to `medium`,
  czyli 3 px — `outlineWidth === 0` nie znaczy „bez ramki" i nigdy nie będzie prawdą.
  O braku ramki mówi `outlineStyle === 'none'`. Asercja „dziś bez drugiej ramki" przechodziła
  tylko dlatego, że komórka zawsze miała klasę `.zaz`; wywróciła się, gdy raz jej nie miała.
- **Element przeniesiony do `body` wychodzi z `opacity` i z koloru rodzica — ale wpada pod
  `<dialog>`.** Okienko listy musi wyjść z komórki dnia, bo rodzic z `opacity` przygasza
  także `position:fixed`, a rodzic z własnym `color` przebarwia tekst. W oknie jest odwrotnie:
  `<dialog>` rysuje się w warstwie NAD stroną, więc okienko w `body` jest widoczne, ale
  żadne kliknięcie go nie dosięga („element is not visible / intercepts pointer events"
  w Playwrightcie). Stąd `if(!q.closest('dialog')) document.body.appendChild(pop)`.
- **Dodanie opakowania w środku komórki psuje wszystkie reguły pisane na dzieci.**
  `.zm` dostało wiersz `.gl`, a reguły telefonu celowały w `.kal .zm>span:first-child`
  i `.kal .zm .ludzie` jako dziecko `.zm` — po zmianie nic z nich nie działało i plakietki
  łamały pasek na dwie linie. Przy zmianie struktury: `grep -n '\.zm' template.html`.
- **Puste miejsce po klawiszu trzeba zarezerwować, inaczej rząd się rozjeżdża.**
  `.xbtn.puste` to span bez treści o wymiarach krzyżyka. Pamiętaj wtedy o asercjach
  liczących klawisze: `.xbtn` łapie i prawdziwe, i puste — w testach `:not(.puste)`.
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
