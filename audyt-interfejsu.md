# Audyt interfejsu Sushi Planner

Stan wyjściowy: wersja **1.66.0**. Przegląd całej aplikacji pod kątem spójności wizualnej,
zgodnie ze skillem *Front-end Design*.

> **Poziom A wdrożony w 1.67.0**, razem z własnymi znakami w menu (opcja B3b) i zwijaniem
> paska do samych ikon. Liczby wyrównane globalnie przez `tabular-nums`, bez drugiego kroju.
> Poziomy **B** (poza ikonami) i **C** czekają na decyzję.

---

## 0. Czym ta aplikacja właściwie jest

Zanim cokolwiek przestawię, muszę nazwać, co projektuję — inaczej „ujednolicenie" skończy się
wygładzeniem wszystkiego do tej samej papki.

**Sushi Planner to narzędzie pracy, nie strona.** Cztery różne osoby, cztery różne sytuacje:

| Kto | Gdzie | Czego szuka | Ile ma czasu |
|---|---|---|---|
| właściciel | biurko, duży ekran | pieniądze: food cost, marże, ceny | godziny |
| kuchnia | tablet, mokre ręce | co dziś zrobić i ile | sekundy |
| kierowca | telefon, samochód | która szafka, w którym automacie | sekundy |
| pracownik | telefon, po pracy | moje zmiany | minuta |

Z tego wynika hierarchia, której dziś nie widać w kodzie: **ekrany dnia i grafik muszą być
czytelne z odległości i jednym spojrzeniem, ekrany pieniędzy mogą być gęste.** Dziś jedne
i drugie są rysowane tym samym rozmiarem pisma i tą samą gęstością.

**Skąd bierze się charakter tej aplikacji.** Cały ten biznes to *dzielenie prostokąta na
ponumerowane przegródki*: 20 szafek w automacie, 7 dni × 2 zmiany w kalendarzu, kafelki
na wydruku, przekrój rolki. To już jest w aplikacji — ale narysowane cztery razy, na cztery
sposoby. **Przegródka to naturalny znak rozpoznawczy tego interfejsu** i to na niej warto
skupić całą odwagę, a resztę wyciszyć.

---

## 1. Co znalazłem

### 1.1 Zaznaczenie: sześć różnych mechanizmów

Ustaliliśmy zasadę „czerwona ramka to wybór". Jest stosowana w **dwóch** miejscach z sześciu:

| Miejsce | Jak dziś wygląda | Zgodne? |
|---|---|---|
| dzień w kalendarzu | czerwona ramka | ✅ |
| zakładka menu | czerwona ramka + szare tło | ✅ |
| wiersz tabeli (`tr.sel`) | **różowe tło**, bez ramki | ❌ |
| kafelek pozycji (`.tcard.sel`) | czerwona ramka **+ druga ramka w cieniu** (podwójna kreska) | ⚠️ |
| przełącznik `Lista / Kafelki` | biała pigułka + cień | ❌ inny język |
| szafka w automacie (`.zal-slot.on`) | **pełne zielone tło** | ❌ zielony to status, nie wybór |

To jest główny powód wrażenia, że „interfejs dalej nie jest jednolity".

### 1.2 Kolor: trzy systemy naraz, jeden martwy

W `:root` żyją trzy niezależne skale:

1. **marka** — `#BD172F`, akcja i wybór. Używana poprawnie.
2. **statusy** — `good / warn / serious / crit`. `--serious` **nie jest używany nigdzie**.
3. **paleta akcentów** `--s1…--s8` — osiem barw, z czego używane są **dwie**:
   - `--s1` (niebieski) w 10 miejscach: „sugerowana cena", „koszt jednostkowy",
     „cena za jednostkę". Niebieski nie znaczy tam nic — a wygląda jak odnośnik.
   - `--s3` (zielony) raz: **gradientowa kropka na ekranie logowania**, niebiesko-zielona,
     została z czasów sprzed identyfikacji Noto Sushi. To pierwszy ekran, jaki widzi nowy
     pracownik, i jedyne miejsce w aplikacji bez czerwieni marki.

Sześć martwych zmiennych (`--s2`, `--s4`…`--s8`, `--serious`) i jedna **nieistniejąca**:
`.pulpit a.card:hover{border-color:var(--accent)}` — `--accent` nie jest nigdzie zdefiniowany,
więc podświetlenie kafelków Pulpitu **nie działa**.

### 1.3 Typografia: jeden krój na wszystkie role, dziewięć grubości

Montserrat robi wszystko: nagłówki, etykiety, tabele liczb, wydruki.

- **18 różnych stopni pisma** (9 / 9,5 / 10 / 10,5 / 11 / 11,5 / 12 / 12,5 / 13 / 14,5 /
  15 / 16 / 18 / 19 / 20 / 22 / 27 px). Nie ma skali — są wartości dobierane pojedynczo.
- **9 grubości**: 520, 540, 560, 600, 620, 640, 660, 700, 800. Montserrat ma 4 wagi
  (400/500/600/700), więc `520`, `540`, `560`, `620`, `640`, `660` **są zaokrąglane przez
  przeglądarkę** do najbliższej dostępnej. Sześć z dziewięciu „grubości" to złudzenie.
- Montserrat to krój **witrynowy**: szeroki, geometryczny, o mało zróżnicowanych cyfrach
  (1 / 7, 6 / 8). Aplikacja jest w 80% tabelą liczb. `tabular-nums` jest dokładany ręcznie
  klasą `.num` — i w części miejsc go nie ma.

### 1.4 Geometria: brak skali

- **12 różnych promieni**: 0, 3, 4, 5, 6, 7, 8, 9, 10 (`--r`), 14, 999 px.
  Przycisk 8, mały przycisk 7, kafelek 8, karta 10, dialog 14, plakietka 7, znacznik 5, tag 999.
- **10 różnych odstępów** w `gap` (2, 4, 5, 6, 8, 9, 10, 12, 14, 16) i ~20 wariantów `padding`.
- Efekt: nic nie leży w jednej linii z niczym, a każda nowa rzecz dostaje kolejną wartość
  „na oko".

### 1.5 Kafelek z liczbą: cztery warianty tego samego

| Gdzie | Etykieta | Liczba |
|---|---|---|
| Foodcost, Automaty (`.tile`) | 11,5 px, wersaliki, `--muted` | 27 px / 660 |
| podgląd rolki (mini-kafelki) | 11 px, wersaliki | 20 px, **kolorowana statusem** |
| pasek grafiku (`.godzsuma`) | wtrącone „razem" | 15 px / bold |
| wiersz `.kv` | zwykły tekst z lewej | bold z prawej |

Cztery sposoby powiedzenia „etykieta i wartość".

### 1.6 Pasek narzędzi listy: przeciążony i niestabilny

Na ekranie **Rolki** w jednym pasku stoi: tytuł, licznik, przełącznik kanału
(Vending/Dostawa), przełącznik widoku (Lista/Kafelki), przycisk Kolejność, przycisk PDF,
pole szukania, przełącznik archiwum (Aktywne/Archiwum/Wszystko) i przycisk `+ Rolka`.
**Trzy różne grupy pigułek obok siebie**, a akcja główna zawija się do drugiej linii i ląduje
pod tytułem — czyli najważniejszy przycisk jest w najmniej oczekiwanym miejscu.

Dla porównania: pasek Grafiku po ostatnich zmianach jest czysty. Dwa ekrany, dwa różne
pomysły na to samo.

### 1.7 Ikony w menu: dekoracja, która się powtarza

23 pozycje menu, ikony z Unicode: `▣ ◍ ◈ ▦ ▥ ➜ ⚖ ▤ ◫ ⇪ ◱ ◷ ◔ ◉ ⚙ ⟳ ⏻`.

- **Powtarzają się**: `▥` to i Pakowanie, i Automaty; `▤` to i Składniki, i Kalendarz;
  `◫` to i Szablon zmian, i Załadunki (Analizy). Skoro ikona nie identyfikuje pozycji,
  nie robi nic poza zajmowaniem miejsca.
- To **glify blokowe**, renderowane z zapasowego kroju systemowego — inaczej na Windows,
  inaczej na Androidzie, inaczej na iOS. Jedyny element interfejsu, nad którym nie mamy
  kontroli wizualnej.

### 1.8 Dostępność i podłoga jakości

| Rzecz | Stan |
|---|---|
| Widoczny fokus klawiatury | **tylko na polach formularza.** Przyciski, zakładki menu, komórki kalendarza, wiersze tabel, przełączniki sekcji — nic. Osoba pracująca z klawiatury nie wie, gdzie jest. |
| `prefers-reduced-motion` | **nieobsługiwany.** Jest 5 przejść, w tym wjazd menu na telefonie (180 ms) i `translateY` kafelków. |
| Kontrast `--muted` (#8A8781) | 3,58:1 na bieli, **3,12:1 na `--surface-2`**. Poniżej 4,5:1 wymaganych dla tekstu. Używany do wszystkich podpowiedzi i etykiet. |
| Przyciski wyłączone | `opacity:.45` → ~2,5:1. Nie da się przeczytać, co jest wyłączone. |
| Reszta kontrastów | dobrze: `--ink` 16,9:1, `--ink-2` 8,6:1, marka na bieli 6,3:1, biel na marce 6,3:1, wszystkie tagi statusów ≥ 4,9:1. |

### 1.9 Drobiazgi w kodzie CSS

- `.btn.pri:hover` **zadeklarowany dwa razy** z konfliktem: pierwszy ustawia ciemniejsze tło
  i `filter:none`, drugi `filter:brightness(1.07)`. Oba się stosują — wychodzi ciemna czerwień
  rozjaśniona z powrotem prawie do wyjściowej. Efekt: najazd na przycisk główny prawie nic
  nie zmienia.
- `.zmk .th b` zadeklarowane dwa razy pod rząd (raz `white-space`, raz `font-size`).
- `--pasek` i `--surface-2` mają tę samą wartość w jasnym motywie, różną w ciemnym —
  to jest w porządku, ale nazwa `--pasek` nic o tym nie mówi.

---

## 2. Co proponuję

Trzy poziomy. Każdy da się zrobić osobno.

### Poziom A — spójność (bez zmiany charakteru, ~1 wydanie)

Same porządki. Nic nie zaczyna wyglądać inaczej, wszystko zaczyna wyglądać tak samo.

**A1. Jedna zasada zaznaczenia.** Czerwona ramka wewnętrzna (`box-shadow: inset 0 0 0 2px`)
wszędzie: wiersz tabeli, kafelek pozycji, szafka, przełączniki. Różowe tło i zielone
wypełnienie znikają. Szafka „jedzie / nie jedzie" zostaje przy statusie (zielone/czerwone tło),
ale *wybrana* szafka dostaje ramkę — status i wybór przestają być tym samym.

**A2. Skala geometrii.** Cztery promienie zamiast dwunastu:
`--r-1: 6px` (kontrolki, plakietki), `--r-2: 9px` (karty, kafelki, boksy),
`--r-3: 14px` (dialog, okno logowania), `999px` (tag). Odstępy: 4 / 8 / 12 / 16 / 24 —
i nic pomiędzy.

**A3. Skala pisma.** Siedem stopni z nazwami zamiast osiemnastu wartości:
`11 / 12 / 13 / 15 / 18 / 22 / 28`. Trzy grubości: **500 / 600 / 700** — te, które Montserrat
naprawdę ma. Znikają wagi 520/540/560/620/640/660, które i tak są zaokrąglane.

**A4. Jeden kafelek z liczbą.** Komponent `.metryka` w dwóch rozmiarach (duży na pulpitach,
mały w podglądach). Cztery obecne warianty schodzą do jednego.

**A5. Sprzątanie kolorów.** Kasuję `--s2`…`--s8`, `--serious`. `--s1` (niebieski przy
„sugerowanej cenie") zastępuję **wagą i etykietą**, nie barwą — liczba wyliczona przez
aplikację ma inny status niż wpisana ręcznie i można to powiedzieć słowem. Naprawiam
`var(--accent)` i podwójny `.btn.pri:hover`.

**A6. Ekran logowania.** Niebiesko-zielona gradientowa kropka → **znak Noto Sushi**.
To jedyny ekran bez marki, a pierwszy, który ktoś widzi.

**A7. Podłoga jakości.**
- Widoczny fokus na wszystkim, co klikalne: `:focus-visible { outline: 2px solid var(--marka);
  outline-offset: 2px }`.
- `@media (prefers-reduced-motion: reduce)` wyłącza przejścia.
- `--muted` przyciemniony do **#6F6C67** (4,9:1 na bieli, 4,3:1 na `--surface-2`) —
  wygląda prawie tak samo, a da się przeczytać.
- Wyłączony przycisk: zamiast `opacity:.45` — stonowane tło i `--muted` tekst, czytelne.

### Poziom B — hierarchia ekranów (~1 wydanie)

**B1. Pasek listy do porządku.** Jeden wzorzec dla Rolek, Zestawów, Składników, Półproduktów,
Automatów, Załadunków — taki jak w Grafiku:

```
[ Tytuł  licznik ] ......................... [ szukaj ] [ ⚙ widok ▾ ] [ + Rolka ]
```

Przełączniki kanału, widoku i archiwum schodzą do **jednego menu „Widok"**, bo to trzy
ustawienia tego samego: co pokazać. Akcja główna przestaje się zawijać.

**B2. Dwie gęstości.** Ekrany dnia (Przygotowanie, Rolki, Zestawy, Pakowanie, Kierowca)
i Grafik dostają większe pismo bazowe i luźniejsze wiersze — czytane z tabletu na blacie
i z telefonu w aucie. Ekrany pieniędzy zostają gęste. To jedna klasa na `<main>`, nie
przepisywanie widoków.

**B3. Ikony w menu.** Dwie drogi, do wyboru:
- **(a) usunąć** — nagłówki grup i nazwy wystarczą, menu robi się spokojniejsze,
  a nazwy dostają więcej miejsca. Zgodnie z zasadą „zdejmij jeden dodatek przed wyjściem".
- **(b) narysować własne** — 8–10 znaków SVG z tego świata (arkusz nori, przekrój rolki,
  siatka szafek, furgonetka, waga). Wygląda dobrze, ale to praca i ryzyko przedobrzenia.

Rekomendacja: **(a)**, a odwagę wydać w jednym miejscu — patrz Poziom C.

### Poziom C — znak rozpoznawczy (~1 wydanie, największa zmiana)

**C1. Jedna przegródka.** Komponent `.slot` z jedną geometrią i jednym zestawem stanów,
używany przez: szafkę automatu, komórkę dnia w kalendarzu, kafelek zmiany, kafelek wydruku.
Dziś te cztery rzeczy są narysowane czterema sposobami, choć znaczą dokładnie to samo:
*ponumerowana przegródka, która jest pusta, zajęta albo wybrana*. To jest ta jedna rzecz,
którą ta aplikacja może się zapamiętać — i wynika wprost z tego, czym jest ten biznes.

**C2. Liczby jak w księdze (jedno ryzyko).** Osobny krój dla kwot i ilości — wąski, tabularny,
o jednoznacznych cyfrach (propozycja: **IBM Plex Mono**, z zapasem `ui-monospace`).
Montserrat zostaje głosem marki: nagłówki, nazwy, nawigacja. Liczby dostają własny głos.

- **Za:** to jest narzędzie do liczenia kosztów; kolumny wyrównują się z definicji, a nie
  przez `tabular-nums` dokładany ręcznie; wydruki z kropkowanymi odnośnikami już mają ten
  charakter i wreszcie by z czymś współgrały. Żadna aplikacja z generatora tak nie wygląda.
- **Przeciw:** drugi krój z sieci (offline zostaje `ui-monospace`, wygląda inaczej niż na
  serwerze), i to zmiana, którą widać na każdym ekranie. Jeśli ma być tylko schludnie,
  a nie charakternie — zamiast tego wystarczy `font-variant-numeric: tabular-nums`
  globalnie, za darmo i bez ryzyka.

---

## 3. Czego NIE proponuję

Żeby było jasne, gdzie stawiam granicę:

- **Nie zmieniam czerwieni ani Montserrata w nagłówkach.** To identyfikacja Noto Sushi,
  zeszła ze strony i z plików logo. Nie ma powodu jej ruszać.
- **Nie zmieniam układu ekranów dnia ani wydruków.** Są przetestowane, mieszczą się na
  jednej stronie i działają w kuchni.
- **Nie dokładam animacji.** Aplikacja ma pięć przejść i tyle wystarczy; więcej ruchu
  w narzędziu pracy przeszkadza.
- **Nie robię trybu „kompaktowego" w ustawieniach.** Gęstość ma wynikać z tego, do czego
  ekran służy, nie z przełącznika, który ktoś raz ustawi i zapomni.

---

## 4. Koszt i kolejność

| Poziom | Zakres | Ryzyko | Testy |
|---|---|---|---|
| **A** | tokeny, zaznaczenia, sprzątanie, dostępność | niskie — same porządki | ~15 nowych asercji |
| **B** | paski list, dwie gęstości, ikony | średnie — widać na każdym ekranie listy | ~10 |
| **C** | wspólna przegródka, krój liczb | wysokie — dotyka wydruków i kalendarza | ~15 |

Sensowna kolejność to **A → B → C**, z osobnym wydaniem na każdy poziom, żeby dało się
zobaczyć efekt i wycofać jeden krok bez ruszania reszty.

Sam poziom **A** zdejmuje większość wrażenia niejednolitości, bo naprawia to, co widać
najczęściej: zaznaczenie, odstępy i cztery różne kafelki z liczbą.
