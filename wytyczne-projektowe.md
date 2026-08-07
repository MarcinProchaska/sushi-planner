# Wytyczne projektowe — Sushi Planner

Ten plik jest **rozstrzygnięciem**, nie inspiracją. Jeśli coś jest tu napisane, nowy ekran ma
się do tego stosować; jeśli czegoś tu nie ma, a okazało się ważne — dopisujemy regułę zamiast
robić wyjątek. Każda reguła ma powód. Powód jest częścią reguły: bez niego po pół roku nikt
nie wie, czy wolno ją złamać.

Stan na wersję **1.73.0**.

---

## 0. Do czego to służy

Narzędzie pracy w lokalu gastronomicznym. Patrzy się na nie:

- **z bliska i godzinami** — ekrany pieniędzy: food cost, ceny, receptury, analizy;
- **z półtora metra i przez kilka sekund** — ekrany dnia: przygotowanie, rolki, pakowanie,
  kierowca, grafik. Często z telefonu, w ruchu, z zajętymi rękami.

Z tego wynika większość decyzji poniżej. To nie jest strona do oglądania — to jest tabela,
w której ktoś szuka jednej liczby, i przycisk, w który ktoś ma trafić kciukiem.

---

## 1. Pogrubienie liczby znaczy: to jest podsumowanie

**Reguła.** W tabelach pogrubiamy liczby **wyłącznie w wierszach podsumowania** — nagłówek
grupy (`tr.grp`) i „Razem" (`tr.suma`). W zwykłym wierszu żadna liczba nie jest pogrubiona.

**Jeśli wiersz sumuje, pogrubiona jest CAŁA linia** — wszystkie liczby w niej, nie tylko ta,
którą ktoś uznał za najważniejszą.

**Kolor pogrubienia to ciemna szarość** (`--ink-2`), nie czerń. Przy wadze 700 czerń robi się
za ciężka i zaczyna konkurować z nagłówkami tabeli.

**Dlaczego.** Wcześniej pogrubienie oznaczało trzy rzeczy naraz: sumę wiersza, „najważniejszą
kolumnę tej tabeli" (koszt jednostkowy, liczba rolek, wartość miesięczna) i po prostu
przyzwyczajenie autora. W tabeli z dziesięcioma kolumnami wytłuszczone było pół wiersza
i nie dało się po tym poznać, która liczba jest podsumowaniem.

**Konsekwencje w kodzie.**

- `tr.grp>td` i `tr.suma>td` mają `font-weight:var(--w-3)` i `color:var(--ink-2)`.
- `tr.grp>td b, tr.suma>td b{font-weight:inherit;color:inherit}` — `<b>` w środku
  podsumowania nie ma już czego dokładać.
- Znacznik `.tag` (food cost, „brak cen", „archiwum") ma `font-weight:inherit`: w zwykłym
  wierszu jest zwykły, w podsumowaniu pogrubia się razem z linią. Nie wpisujemy mu wagi
  na sztywno.
- Numer porządkowy (`#`, `.ordcell .nr`) nie jest pogrubiony: to etykieta, nie wartość.

### 1a. Pogrubiony tekst znaczy: to jest rzecz, którą na tej karcie edytujesz

Pogrubiamy wyłącznie **kolumnę nazwy w listach, których wiersz otwiera edytor**: Składniki,
Półprodukty, Rolki, Zestawy, Automaty, Załadunki, Użytkownicy. Nic więcej — ani dni, w które
jedzie załadunek, ani adres konta, ani nazwa zestawu w tabeli pobocznej.

**Karty do czytania nie mają pogrubień w ogóle.** Rozpiski („Do przygotowania"), analizy,
historia cen, zestawienia, widoki kierowcy — tam nic się nie edytuje, więc nie ma czego
wyróżniać. Jedynym wyjątkiem są wiersze podsumowań z punktu 1.

**Dlaczego to kryterium, a nie „główny element ekranu".** Nie trzeba zgadywać, co na danym
ekranie jest najważniejsze — wystarczy sprawdzić, czy wiersz otwiera edytor. Karta
„Do przygotowania" ma trzy tabele (zestawy, rolki, składniki) i przy poprzednim kryterium
każda z nich miała równie dobre prawo do pogrubienia; przy tym — żadna, bo to lista roboty
do odczytania, a nie do zmieniania.

**Nagłówki kolumn** (`th`) zostają jak są: 600, szare, mniejszy stopień. To oznaczenie
nagłówka, nie pogrubienie treści.

---

## 2. Kolor ma trzy role i ani jednej więcej

1. **Marka `#BD172F`** — akcja i wybór. Nigdy status, nigdy tło.
2. **Statusy** — `good` / `warn` / `crit`. Zawsze z liczbą albo słowem obok, nigdy sam kolor.
3. **Dane `--dane`** — jedyny akcent poza tymi dwoma: linia na wykresie, znacznik informacji.

**Dlaczego statusy nie mogą używać czerwieni marki:** firmowa czerwień obok statusowej zieleni
ma dla osoby z deuteranopią odległość ΔE 5,0 przy progu 8 — są nie do rozróżnienia samym
kolorem. Test pilnuje, że żaden token statusu nie przyjmie wartości `#BD172F`.

**Wyjątek: role kont.** Na ekranie Użytkowników rola nosi kolory statusu (właściciel —
zielony, kucharz — pomarańczowy). Rola nie jest stanem, ale na tym ekranie jest **tematem**:
cztery zakresy uprawnień trzeba odróżnić jednym spojrzeniem, a słowa te występują wyłącznie
tutaj — nie stoją obok food costu ani obsady zmian, więc nie da się ich z nimi pomylić.
Poza tym ekranem rola jest zwykłym tekstem.

---

## 3. Czerwona ramka to wybór — wszędzie

Jeden token `--ramka-wybor` (`inset 0 0 0 2px`) obsługuje: zakładkę menu, wybrany wiersz
tabeli, wybrany kafelek pozycji, zaznaczony dzień w kalendarzu.

**Wyjątek:** przełącznik segmentowy (Lista/Kafelki, Miesiąc/Tydzień). Tam wybór widać
z wypełnienia pigułki; trzy czerwone ramki obok siebie w pasku listy krzyczałyby głośniej
niż akcja główna. Napis aktywnej pigułki nosi kolor marki, więc należy do tej samej rodziny.

**Dziś to podkreślona liczba dnia**, nie druga ramka. Ta sama konwencja w trzech miejscach:
miniatura na Pulpicie, siatka miesiąca, nagłówek kolumny w widoku tygodnia. Dwie ramki tego
samego koloru obok siebie kazały się zastanawiać, która z nich czegoś chce.

---

## 3a. Odnośnik to tekst ze strzałką

**Jeden wygląd w całej aplikacji:** tekst w kolorze tekstu, strzałka `›` po prawej,
podkreślenie dopiero pod kursorem. Wzorzec: nazwa półproduktu w rozpisce.

**Odnośnik nie jest czerwony i nie jest pogrubiony.** Czerwień znaczy tu akcję i wybór,
a pogrubienie — podsumowanie albo rzecz, którą się edytuje. Przejście w inne miejsce nie jest
żadną z tych rzeczy: ma się czytać jak tekst, który da się kliknąć. Strzałka mówi
„to prowadzi dalej" i robi to ciszej niż kolor — a w gęstej tabeli stała kreska pod każdą
nazwą robi z ekranu siatkę.

**Wyjątki:**

- `a.card` — kafelek-odnośnik (Pulpit, karty automatów u kierowcy). Klikalna jest cała karta,
  nie napis, więc strzałki nie dostaje.
- `a.zew` — odnośnik poza aplikację. Ta sama reguła, ale strzałka wychodząca `↗`, bo otwiera
  nową kartę przeglądarki.

**Zdanie kończy się odnośnikiem, nie kropką po nim.** Strzałka i kropka obok siebie
(„Ustaw plan tygodnia ›.") czytają się jak literówka.

---

## 4. Plakietka należy do osoby

**Plakietka** — wypełniony prostokąt w kolorze osoby ze skrótem w środku (`.kod`, `.osbtn`).
To mocny sygnał: „to jest osobny obiekt". W całej aplikacji przysługuje **jednej rzeczy:
osobie w grafiku**.

Wszystko inne — rola konta, „archiwum", kod automatu, procent food costu — to **znacznik
tekstowy** (`.tag`): kolor i ewentualnie mniejszy stopień pisma, bez tła i bez obwódki.

**Dlaczego.** Zielona pigułka przy `11,7%` krzyczała głośniej niż liczba, którą miała opisać,
a przy nazwie automatu udawała etykietkę, choć to zwykły tekst. Kolumna liczb ma się czytać
z góry na dół jednym rzutem oka; rząd kolorowych pigułek to uniemożliwiał.

---

## 5. Wolne miejsce to puste miejsce

W grafiku nie piszemy „1/2". Zmiana pokazuje **plakietki tych, którzy stoją, i puste prostokąty
tam, gdzie jeszcze nikogo nie ma** — tyle pustych, ile wolnych miejsc.

- Wolne miejsce: **obrys**, puste wnętrze.
- Miejsce zajęte przez kogoś, kogo w tym trybie nie pokazujemy („Tylko ja"): **wypełnienie**
  szarością. Nigdy nie znika — inaczej zmiana skróciłaby się o wiersz i kalendarz podskakiwałby
  przy przełączaniu widoku.
- **Równość szerokości jest wymuszona, nie przypadkowa.** W siatce miesiąca każde miejsce ma
  stałe 54 px; w wąskiej kolumnie tygodnia każdy wiersz idzie na całą szerokość. Inaczej „AB"
  i „MarPro" dają dwa różne rytmy i sąsiadujące dni przestają się zgadzać w pionie.

Ułamek trzeba było przeczytać i odjąć w pamięci, a przy okazji liczby o różnej długości
rozpychały kafelki dnia na różne szerokości.

---

## 6. Klawisz stoi obok tego, czego dotyczy

Jedna rodzina: **kwadratowy klawisz 30 × 30 obok elementu**, którego dotyczy.

| Klawisz | Przy czym stoi | Kto go widzi |
|---|---|---|
| ✕ | przy plakietce osoby | pracownik — przy swojej; układający grafik — przy każdej |
| + | przy „Zapisz się" | wyłącznie układający grafik |

Nie wsadzamy klawisza **do środka** plakietki i nie odsyłamy go na drugi koniec wiersza.
Kto go klika, nie powinien przejeżdżać wzrokiem przez pół ekranu, żeby sprawdzić, czy trafia
w ten wiersz, o który mu chodzi.

**Kasowanie mieszka tam, gdzie edycja** — w panelu edycji pozycji, w strefie ryzyka na końcu,
nigdy w wierszu listy obok „Edytuj". Strefa ryzyka opisuje **tę rzecz**, którą się edytuje:
przy składniku mówi o recepturach i kosztach, przy załadunku o dniach tygodnia. Jeden wspólny
opis dla wszystkich rodzajów pozycji to opis, który przy połowie z nich kłamie.

---

## 7. Jedna przegródka

Ponumerowana komórka to jeden komponent (`.slot`): szafka w załadunku, szafka u kierowcy.
Jedna geometria, jeden numer w rogu, jeden zestaw stanów, jedna receptura na tła:

| Stan | Znaczy | Tło |
|---|---|---|
| `pelny` | jest jak ma być | `--tlo-ok` |
| `wylaczony` | czegoś brakuje | `--tlo-brak` |
| `pusty` | nie dotyczy | `--tlo-nieczynny` |
| `wybrany` | zaznaczone teraz | `--ramka-wybor` |

Tych samych trzech tokenów używają paski zmian w kalendarzu i kafelki zmian — „komplet"
w kalendarzu i „szafka jedzie" w załadunku mają ten sam odcień, bo znaczą to samo.

**Numer ma własną kolumnę** o stałej szerokości, wyrównaną do prawej: „1" i „20" kończą się
w tym samym pionie, a nazwa zaczyna się zawsze w tym samym miejscu.

---

## 8. Nie powtarzamy tej samej informacji dwoma środkami

- Panel dnia pod kalendarzem **nie ma tła stanu**: ten sam dzień widać metr wyżej, pomalowany
  dokładnie tym samym kolorem. Obsadę widać ze składu — tyle plakietek, ilu ludzi.
- Nagłówek kafelka zmiany **nie powtarza ułamka**, skoro skład jest pod spodem.
- Nazwisko obok plakietki w panelu jest zbędne, skoro pełna lista z godzinami stoi
  pod kalendarzem.
- Etykieta nad polem, która powtarza tytuł okna („Kto staje" w oknie „Dopisz do zmiany"),
  jest zbędna.
- Nazwa przycisku zastępuje podpis nad nim („Import JSON" zamiast „Import z pliku JSON"
  + bezimienny przycisk).

Zasada ogólna: **jeśli coś jest już powiedziane, drugi środek nie dodaje informacji, tylko
szum.** Wyjątek: powtórzenie ratujące przed błędem nieodwracalnym (potwierdzenie usunięcia).

---

## 9. Skale zamiast wartości „na oko"

| Skala | Szczeble | Do czego |
|---|---|---|
| promień | `--r-0` 4 · `--r-1` 7 · `--r-2` 10 · `--r-3` 14 | mikroelement · kontrolka · pojemnik · dialog |
| pismo | `--t-0` 10 … `--t-7` 28 | osiem stopni |
| grubość | `--w-1` 500 · `--w-2` 600 · `--w-3` 700 | **trzy** — Montserrat ma cztery wagi |
| odstęp | `--sp-0` 2 … `--sp-6` 24 | siatka 4 px z półkrokiem 6 |

Nowa wartość spoza skali to sygnał, że albo skala jest za uboga (wtedy ją rozszerzamy raz,
dla wszystkich), albo element robi coś, czego nie powinien.

**Cyfry są tabularne globalnie** (`font-variant-numeric:tabular-nums` na `body`), nie tam,
gdzie ktoś pamiętał dopisać klasę.

---

## 10. Dwie gęstości

Klasa `.dzien` na `<main>` (zbiór `EKRANY_DNIA`) podnosi pismo bazowe, wiersze tabel i odstępy
w kartach. Dostają ją ekrany dnia i Grafik; ekrany pieniędzy i ustawień zostają gęste.

**Komórka kalendarza ma własną gęstość** i nie podlega luzowaniu — reguła
`.main.dzien td{padding:11px 10px}` zjadała 20 px z komórki szerokiej na 47 px.

---

## 11. Telefon nie jest małym monitorem

Progi, których używamy, i co się przy nich dzieje:

| Próg | Co się zmienia |
|---|---|
| ≤ 640 px | Pulpit i kafelki w dwóch kolumnach, mniejsze liczby, znikają podtytuły kafelków |
| ≤ 760 px | menu staje się szufladą pod hamburgerem; w kalendarzu plakietka zwija się do **pionowej kreski** w kolorze osoby |
| ≤ 939 px | nagłówki dni skracają się do „Pn"; w kalendarzu plakietki idą **w słupek**, jedna pod drugą |
| ≥ 761 px | pasek menu daje się zwinąć do samych znaków; poniżej 1000 px startuje zwinięty |

**Zasady, nie tylko liczby:**

- Informacji się **nie chowa, tylko skraca**. Plakietka, która nie mieści się w komórce,
  zamienia się w kreskę w kolorze osoby — nie znika. Z telefonu ma być widać, kto stoi.
- Instrukcji dla klawiatury nie pokazujemy tam, gdzie klawiatury nie ma
  (`@media (pointer:coarse)`).
- Klawisz musi zostać w zasięgu kciuka — w jednokolumnowym układzie wiersz nie rozciąga się
  na całą szerokość ekranu.

---

## 12. Podłoga jakości

- **Fokus klawiatury widać na wszystkim, co klikalne** (`:focus-visible`), nie tylko w polach.
- **`prefers-reduced-motion` wyłącza przejścia.** Narzędzie pracy nie kręci ekranem komuś,
  kto sobie tego nie życzy.
- **Kontrast tekstu ≥ 4,5:1**, także na szarym tle. Dotyczy zwłaszcza `--muted`, którym
  napisane są wszystkie podpowiedzi.
- **Wyłączony przycisk jest czytelny**, a nie wyblakły: stonowane tło zamiast `opacity`.
- **Dymki są nasze** (`#tip`), nie natywne `title`. Natywny wygląda inaczej w każdym systemie,
  ma sekundę opóźnienia i nie reaguje na fokus z klawiatury. `title` zostaje wyłącznie tam,
  gdzie treść jest dodatkiem, nie warunkiem zrozumienia ekranu.
- **Odnośnik poznaje się po kolorze, nie po kresce.** Podkreślenie pojawia się pod kursorem;
  stała kreska pod każdą nazwą robi z gęstej tabeli siatkę.

---

## 13. Słowa

- Nazwa mówi, **co się stanie**: „Pobierz dane z serwera", nie „Odśwież z serwera".
- Nie zostawiamy nazw, które opisują implementację albo historię projektu.
- Tekst, który przestał być prawdą, usuwamy — nieaktualna instrukcja jest gorsza od żadnej.
- Ostrzeżenie mówi, **co dokładnie przepadnie**, a nie „czy na pewno".
- Nie tłumaczymy rzeczy oczywistych z kontekstu (patrz punkt 8).

---

## 14. Czego nie robimy

- **Nie zmieniamy czerwieni ani Montserrata w nagłówkach.** To identyfikacja Noto Sushi.
- **Nie dokładamy animacji.** Aplikacja ma pięć przejść i tyle wystarczy.
- **Nie robimy trybu „kompaktowego" w ustawieniach.** Gęstość ma wynikać z tego, do czego
  ekran służy, nie z przełącznika, który ktoś raz ustawi i zapomni.
- **Nie dokładamy drugiego kroju dla liczb.** `tabular-nums` załatwia to, o co chodziło,
  bez zależności, która offline wygląda inaczej niż na serwerze.
- **Nie zostawiamy przycisku, który jednym kliknięciem kasuje wszystko.**

---

## 15. Jak pracujemy

1. **Zmiana najpierw w sesji, nie w publikacji.** Robimy ją lokalnie, pokazujemy zrzut,
   dopiero po akceptacji idzie na dysk i na serwer.
2. **Każda zmiana w kodzie to skrypt-łatka**, który sprawdza, że trafia dokładnie w jedno
   miejsce (`src.count(old) != 1 → sys.exit`). Bez tego przy 470 kB jednego pliku nie da się
   przewidzieć, co jeszcze się zmieniło.
3. **Regułę zapisuje test, nie pamięć.** Każda decyzja z tego pliku ma asercję w
   `test-offline.py` — inaczej wraca po trzech wydaniach. Test nazywa się zdaniem po polsku,
   które mówi, o co chodzi.
4. **Komentarz w kodzie mówi DLACZEGO**, a nie co robi linijka. Kod pokazuje „co".
5. Wydanie: obie serie testów na zielono → `VERSION` → README → pliki na dysk → `publikuj.bat`.
