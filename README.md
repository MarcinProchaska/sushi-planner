# Sushi Planner

Kalkulator food costu i budowania menu dla lokalu sushi. Składniki z cenami, półprodukty,
receptury rolek, zestawy z policzonym opakowaniem, historia cen i symulacja podwyżek.

Jeden plik HTML plus serwer w czystym Pythonie. **Zero zależności zewnętrznych** — nie ma
`pip install`, nie ma Dockera, nie ma bazy danych do utrzymywania. Zużycie pamięci ~25 MB.

---

## Identyfikacja wizualna

Aplikacja nosi identyfikację **Noto Sushi**: czerwień **`#BD172F`**, czerń znaku **`#1D1D1B`**
i krój **Montserrat** — wszystko wzięte wprost z firmowych plików logo i ze strony notosushi.pl.

### Skale zamiast wartości „na oko"

Wcześniej w CSS-ie żyło 12 promieni, 18 stopni pisma, 9 grubości i 10 odstępów, dobieranych
pojedynczo. Nic nie leżało w linii z niczym, a każda nowa rzecz dokładała kolejną wartość.
Teraz są cztery skale w `:root` i nic poza nimi:

| Skala | Szczeble | Do czego |
|---|---|---|
| promień | `--r-0` 4 · `--r-1` 7 · `--r-2` 10 · `--r-3` 14 | mikroelement · kontrolka · pojemnik · dialog |
| pismo | `--t-0` 10 … `--t-7` 28 | osiem stopni |
| grubość | `--w-1` 500 · `--w-2` 600 · `--w-3` 700 | **trzy** — Montserrat ma cztery wagi, więc `520` czy `640` i tak było zaokrąglane przez przeglądarkę |
| odstęp | `--sp-0` 2 … `--sp-6` 24 | siatka 4-piksela z półkrokiem 6 |

### Trzy role koloru i ani jednej więcej

1. **Marka** `#BD172F` — akcja i wybór. Nigdy status, nigdy tło.
2. **Statusy** — `good` / `warn` / `crit`, zawsze z liczbą albo słowem obok.
3. **Dane** `--dane` — jedyny akcent poza tymi dwoma: linia na wykresie historii cen
   i znacznik informacji.

Wcześniej były jeszcze `--s1`…`--s8` (osiem barw, z czego siedem nieużywanych) i `--serious`.
Niebieski `--s1` trafiał do liczb typu „sugerowana cena", gdzie wyglądał jak odnośnik i nie
znaczył nic — teraz mówi to **waga pisma i etykieta obok**, a kolor zostaje przy swoich rolach.
Zniknęło też `var(--accent)`, do którego odwoływało się podświetlenie kafelków Pulpitu —
zmienna nigdy nie istniała, więc ten hover od zawsze nic nie robił.

### Czerwona ramka to wybór — wszędzie

Jeden token `--ramka-wybor` (`inset 0 0 0 2px`) obsługuje zakładkę menu, wybrany wiersz tabeli,
wybrany kafelek pozycji i zaznaczony dzień w kalendarzu. Wcześniej te cztery rzeczy miały cztery
różne postacie, w tym różowe tło i podwójną kreskę.

Wyjątkiem jest **przełącznik segmentowy** (Lista/Kafelki, Aktywne/Archiwum): tam wybór widać
z samego wypełnienia pigułki, a trzy czerwone ramki obok siebie w pasku listy krzyczałyby
głośniej niż akcja główna. Napis aktywnej pigułki nosi za to kolor marki, więc należy do tej
samej rodziny.

### Znaki w menu

Były to glify blokowe z Unicode. Powtarzały się — `▥` oznaczało i Pakowanie, i Automaty,
`▤` i Składniki, i Kalendarz — więc nie identyfikowały pozycji; a renderowane z zapasowego
kroju systemowego wyglądały inaczej na każdym systemie. Był to jedyny element interfejsu
bez kontroli wizualnej.

Teraz to własne SVG w jednej siatce 24×24, kreską 1,6, w `currentColor` — dziedziczą kolor
zakładki i działają w obu motywach. Wzięte z tego świata: **mata do zwijania** (Przygotowanie),
**przekrój rolki** (Rolki), **taca z przegródkami** (Zestawy), **siatka szafek** (Automaty).
Ten sam znak przy dwóch zakładkach jest dozwolony tylko wtedy, gdy zakładki naprawdę znaczą
to samo — i test tego pilnuje.

**Pasek da się zwinąć do samych znaków** (przycisk pod menu). Przy 23 pozycjach i pracy na
jednym ekranie przez osiem godzin 216 px to realna strata miejsca. Zwinięty pasek pokazuje
grupy jako kreski, a nazwę zostawia w podpowiedzi. Wybór trzyma przeglądarka, nie baza lokalu:
to ustawienie stanowiska, a nie firmy. Na telefonie pasek jest szufladą, więc zwijanie działa
dopiero od 901 px.

### Licznik to nie alarm

Przy zakładkach są dwie różne rzeczy, które wcześniej wyglądały tak samo:

- **licznik** — ile tego jest: `23` przy Rolkach, `49` przy Składnikach. Informacja, nie zadanie.
- **sygnał uwagi** — `24` przy Kalendarzu, czyli *zmiany bez kompletu w najbliższych dwóch
  tygodniach*. To jest zadanie.

Po zwinięciu paska pierwsza wersja zamieniała **wszystkie** liczniki w czerwoną kropkę.
Czerwona kropka w interfejsie znaczy „coś na ciebie czeka", więc obiecywała rzecz, której nie
było — sześć kropek przy sumach, które nikogo do niczego nie wzywają. Teraz sygnał uwagi ma
własną klasę (`.cnt.uwaga`), w rozwiniętym pasku różni się kolorem i wagą, a po zwinięciu
tylko on zostaje kropką; zwykłe sumy znikają. Podpowiedź mówi wprost, czego kropka dotyczy,
zamiast kazać zgadywać.

### Jeden pasek dla wszystkich list

Sześć list — Składniki, Półprodukty, Rolki, Zestawy, Automaty, Załadunki — składało sobie
pasek osobno. Na Rolkach stało w nim dziewięć rzeczy naraz: trzy grupy pigułek, dwa przyciski,
pole szukania i akcja główna. Przy tej liczbie „+ Rolka" **zawijało się do drugiej linii
i lądowało pod tytułem**, czyli najważniejszy przycisk trafiał tam, gdzie nikt go nie szuka.

Teraz pasek ma dwa rzędy i jeden podział:

| Rząd | Co w nim stoi | Zasada |
|---|---|---|
| górny | tytuł, licznik, ⎙ PDF, **+ Dodaj** | to, co robi coś **nowego** |
| dolny (`.paskopcji`) | szukaj, kategoria, kanał, widok, archiwum, kolejność | to, co zmienia **sposób patrzenia** na to, co już jest |

Rozważane było zwinięcie filtrów do jednego menu „Widok", ale menu chowa stan za kliknięciem —
a na Rolkach trzeba widzieć od razu, że lista jest przefiltrowana. Wszystkie sześć list ma
pasek tej samej wysokości (37 px) i test tego pilnuje razem z tym, że akcja główna nie schodzi
pod tytuł, a filtry nie wracają do górnego rzędu.

### Dwie gęstości

Ekran w biurze ogląda się z bliska, ekran dnia — z drugiej strony stołu i w rękawiczkach.
Klasa `.dzien` na `<main>` (zbiór `EKRANY_DNIA`) podnosi pismo bazowe, wiersze tabel i odstępy
w kartach dla Pulpitu, Przygotowania, Rolek, Zestawów, Pakowania, Kierowcy, Kontroli zasobów,
Składu i Kalendarza. Ekrany pieniędzy i ustawień zostają gęste. Żaden widok nie był
przepisywany — to jedna klasa i jeden blok reguł.

### Jedna przegródka

Ten sam prostokąt występował w aplikacji cztery razy — szafka w załadunku, szafka u kierowcy,
dzień w kalendarzu, kafelek zmiany — i był narysowany cztery razy osobno, z różnymi promieniami
i różnymi odcieniami. A cały ten biznes to dzielenie prostokąta na ponumerowane przegródki.

Teraz przegródka jest jedna: komponent `.slot` z jedną geometrią, numerem w lewym marginesie
i czterema stanami.

| Stan | Znaczy | Tło |
|---|---|---|
| `pelny` | jest jak ma być: szafka jedzie, zmiana obsadzona | `--tlo-ok` |
| `wylaczony` | czegoś brakuje: szafka wyłączona, zmiana bez kompletu | `--tlo-brak` |
| `pusty` | nie dotyczy: szafka bez zestawu, dzień poza miesiącem | `--tlo-nieczynny` |
| `wybrany` | zaznaczone teraz | `--ramka-wybor` |

Trzy tła to trzy tokeny, z których korzystają też paski zmian w kalendarzu i kafelki zmian —
wcześniej każde z tych miejsc mieszało sobie kolor osobno, przez co „komplet" w kalendarzu
i „szafka jedzie" w załadunku miały inny odcień zieleni, choć znaczą to samo. Przy okazji
szafki straciły pełne wypełnienie zielenią i czerwienią: krzyczały mocniej niż cokolwiek
innego w aplikacji, a mówią dokładnie to, co blade paski w kalendarzu.

**Osobnego kroju dla liczb nie ma i nie będzie.** Drugi font z sieci to zmiana widoczna na
każdym ekranie i zależność, która offline wygląda inaczej niż na serwerze. `tabular-nums`
globalnie załatwia to, o co chodziło: kolumny liczb, które się zgadzają.

### Znacznik zamiast plakietki

Pigułka z wypełnionym tłem to mocny sygnał: mówi „to jest osobny obiekt". Nosiła u nas
byle co — rolę konta, słowo „archiwum", kod automatu, procent food costu. Zielona pigułka
przy `11,7%` krzyczała głośniej niż liczba, którą miała opisać, a przy nazwie automatu
udawała etykietkę, choć to zwykły tekst.

**Plakietka jako kształt należy teraz do jednej rzeczy w całej aplikacji: do osoby w grafiku.**
Reszta mówi krojem i kolorem — `.tag` to znacznik tekstowy, a food cost to sam procent,
pogrubiony, w kolorze progu. Kolumna liczb czyta się z góry na dół jednym rzutem oka, czego
rząd kolorowych pigułek nie pozwalał zrobić.

### Nazwa dnia jest częścią daty

W pasku dnia stały obok siebie dwie rzeczy, które są jedną: pole z datą `07.08.2026`
i plakietka `piątek`. Teraz jest **„piątek 07.08.2026"** — tak, jak się datę mówi. Pole
`type=date` leży pod spodem niewidoczne, więc kliknięcie w datę dalej otwiera kalendarz
przeglądarki.

### Ramka to wybór — także w kalendarzu

Dzisiejszy dzień miał własną obwódkę, cieńszą od obwódki zaznaczenia, ale tego samego
koloru. Dwie ramki obok siebie każą się zastanawiać, która z nich czegoś chce.
**Dziś poznaje się teraz po czerwonej cyfrze dnia**, ramka została przy wyborze.

### Wolne miejsce to puste miejsce

W siatce miesiąca przy każdej zmianie stał ułamek: `2/2`, `0/1`, `1/2`. Trzeba go było
przeczytać i odjąć w pamięci, a przy okazji liczby o różnej długości rozpychały kafelki dnia
na różne szerokości i cała siatka się rozjeżdżała.

Teraz zmiana pokazuje **plakietki tych, którzy stoją, i puste prostokąty tam, gdzie jeszcze
nikogo nie ma** — tyle pustych, ile wolnych miejsc. Obsadę widać z całego miesiąca naraz,
bez czytania jednej cyfry.

Równość szerokości jest **wymuszona, nie przypadkowa**: w siatce miesiąca każda plakietka
ma stałe 54 px, a puste miejsce dokładnie tyle samo. Inaczej „AB" i „MarPro" dają dwa różne
rytmy i sąsiadujące dni przestają się zgadzać w pionie. W kolumnie tygodnia każdy wiersz idzie
na całą szerokość kolumny, więc plakietka, „Zapisz się" i puste miejsce są równe z definicji,
a krzyżyki i plusiki stoją w jednej kolumnie przy prawej krawędzi.

### Klawisz stoi obok tego, czego dotyczy

Krzyżyk „wypisz" siedział wewnątrz plakietki, a plusik „dopisz kogoś" obok przycisku
i mniejszy — trzy rozmiary i dwie różne relacje na przestrzeni jednego rzędu. Teraz to
jedna rodzina: **kwadratowy klawisz 30 × 30 obok elementu, którego dotyczy**.

| Klawisz | Przy czym stoi | Kto go widzi |
|---|---|---|
| ✕ | przy plakietce osoby | pracownik — przy swojej; układający grafik — przy każdej |
| + | przy „Zapisz się" | wyłącznie układający grafik |

### Tydzień: jeden klawisz na jedno wolne miejsce

Widok tygodnia służy do zapisywania się wprost w dniu, więc panel pod kalendarzem robił
drugą drogą to samo, tylko wolniej — zniknął. Zostaje w widoku miesiąca, gdzie w komórce
dnia nie ma miejsca na przyciski.

„Zapisz się" **znikało wcześniej, gdy na zmianie stanął ktokolwiek** — choć miejsce było
dalej wolne. Teraz jest tyle przycisków, ile wolnych miejsc, dokładnie tak jak pustych
prostokątów w siatce miesiąca. Przycisk stracił czerwień: w kolumnie tygodnia stoi
kilkanaście takich naraz, a czerwona ściana zabija każdą inną informację na ekranie.

### Telefon: kto stoi, widać zawsze

Skrót w kalendarzu jest po to, żeby jednym spojrzeniem zobaczyć, kto gdzie stoi. Na małym
ekranie plakietka po prostu **znikała** — czyli z telefonu nie było tego widać w ogóle,
a to on najczęściej leży na blacie. Odpowiedź zależy od tego, ile miejsca naprawdę zostaje
w komórce dnia:

| Ekran | Komórka | Co widać |
|---|---|---|
| ponad 940 px | ≥ 120 px | plakietki w rzędzie, tak jak zawsze |
| telefon położony | ~100 px | pełne plakietki ze skrótem, **jedna pod drugą** — obok siebie zmieściłaby się tylko jedna |
| telefon w pionie | ~48 px | **pionowa kreska w kolorze osoby**, wolne miejsce jako kreska pusta |

Osiem kolorów palety jest dobranych tak, żeby dało się je rozróżnić także przy niedowidzeniu
barw, więc na odpowiedź „czy ja tam stoję" wystarcza sama kreska. Nazwiska są o jedno
stuknięcie dalej, w panelu dnia.

Znika za to podpowiedź **„Ctrl+klik dokłada dzień, Shift+klik bierze zakres"** — wszędzie,
gdzie nie ma klawiatury (`pointer:coarse` albo ekran poniżej 940 px). To instrukcja dla kogoś,
kto ma czym ją wykonać; na dotyku była obietnicą bez pokrycia.

Przy okazji komórka kalendarza przestała podlegać luzowaniu ekranów dnia: reguła
`.main.dzien td{padding:11px 10px}` zjadała 20 px z komórki szerokiej na 47 px, czyli prawie
połowę, i nic już się w niej nie mieściło. Nagłówki dni skracają się do „Pn" od tej samej
szerokości — wcześniej dopiero od 760 px, przez co na telefonie położonym zlewały się
w jeden ciąg liter.

### Telefon położony: pasek daje się zwinąć

Telefon w poziomie ma 844 × 390 px — był **za szeroki na szufladę** (ta włączała się do 760 px)
i **za wąski na zwijanie paska do znaków** (to działało od 901 px). Zostawał mu na stałe
216-pikselowy pasek nawigacji na ekranie wysokim na 390 px, przez co kalendarz nie miał
gdzie się zmieścić.

Zwijanie łapie teraz od 761 px, czyli dokładnie od miejsca, w którym pasek przestaje być
szufladą — żadnej dziury między jednym a drugim. Dodatkowo na ekranie węższym niż 1000 px
pasek **startuje zwinięty**, o ile nikt wcześniej nie zdecydował inaczej: to 154 px więcej
na treść, czyli różnica między kalendarzem, który się mieści, a takim, który się rozjeżdża.
Zapisany wybór człowieka jest ważniejszy i zostaje uszanowany.

### Wszyscy albo tylko ja

Przy pełnej obsadzie miesiąc to ściana skrótów i znalezienie w niej własnych dni zajmuje
chwilę. Przełącznik **Wszyscy / Tylko ja** zostawia własne plakietki, a resztę zamienia
w szare prostokąty. Liczba wolnych miejsc się nie zmienia — dalej mówi prawdę.

Ukryta osoba **nie może zniknąć z układu**: zmiana skróciłaby się o wiersz i cały kalendarz
podskakiwałby przy każdym przełączeniu widoku. Zostaje więc prostokąt tej samej wielkości
(razem z miejscem po klawiszu, który przy niej stał) — „tu ktoś stoi, ale nie ty". Wolne
miejsce ma obrys i puste wnętrze, zajęte ma wypełnienie, więc jednego z drugim nie da się
pomylić. Wysokość kalendarza w obu trybach jest identyczna co do piksela i test tego pilnuje.

### Grafik na Pulpicie

Pierwsze pytanie dnia brzmi „kiedy mam zmianę", a odpowiedź wymagała wejścia w kalendarz.
Grafik stoi teraz **zaraz po Pulpicie** w menu i ma własny kafelek na ekranie Pulpitu.

Kafelek to **same cyfry**: pięć tygodni licząc od bieżącego, własne dni czerwonym boldem.
Nie ma na nim godzin, liczby zmian ani nazwy miesiąca — to wszystko jest w Grafiku, o jedno
kliknięcie dalej. Kafelek odpowiada na jedno pytanie: w które dni stoję.

Okno idzie od **bieżącego tygodnia**, nie od pierwszego dnia miesiąca. Miesiąc to podział
księgowy, a nie sposób, w jaki się pracuje: 28 sierpnia interesuje mnie wrzesień, a nie to,
co było 3 sierpnia. Pierwszy wiersz to zawsze ten tydzień, w którym stoimy — dni, które już
były, są przygaszone. Granicę miesiąca znaczy hairline: pionowy przed pierwszym dniem, a gdy
pierwszy wypada w poniedziałek — poziomy nad całym wierszem, bo wtedy granica leży nad rzędem.

Kto nie stoi w grafiku (albo nie jest zalogowany) widzi na miniaturze dni, w których brakuje
ludzi. Podtytuły kafelków Pulpitu zostają na dużym ekranie, a poniżej 760 px znikają — nazwa
i liczba wystarczą, a zaoszczędzony wiersz to na telefonie realna różnica.

### Dziś to podkreślona liczba dnia

Jedna konwencja w trzech miejscach: miniatura na Pulpicie, siatka miesiąca i nagłówek kolumny
w widoku tygodnia. Wcześniej „dziś" nosiło czerwoną cyfrę, czyli ten sam kolor co wybór
i co własne zmiany — trzy różne rzeczy mówione jednym środkiem. Podkreślenie jest ciche,
nie zabiera czerwieni i nie myli się z ramką zaznaczenia.

### Dymek jest nasz

Imię i nazwisko pod plakietką pokazywał natywny `title` przeglądarki: żółte pudełko,
systemowy krój, sekunda opóźnienia, w każdym systemie inaczej. Skoro aplikacja ma własny
dymek do wykresów, to samo pudełko obsługuje teraz plakietki — i reaguje także
na fokus z klawiatury.

### Godziny wybiera się, nie wklepuje

Pole `type=time` wygląda niepozornie, ale obsługuje się je wyłącznie z klawiatury: trafić
w segment godziny, wpisać dwie cyfry, przejść do minut. Układanie szablonu to kilkanaście
takich pól pod rząd. Teraz to **lista co kwadrans** — jedno kliknięcie, i nie da się wpisać
`25:70`. Nietypowa godzina ze starych danych dokłada się do listy, żeby otwarcie szablonu
nie skasowało po cichu czyjegoś `8:20`.

### Połówki rolek widać

Rolka zwija się w całości. `2,5 rolki` na dany dzień znaczy, że pół pójdzie do kosza albo
trzeba będzie dołożyć — czyli że liczba zestawów w automatach jest ustawiona niepraktycznie.
To nie błąd programu, tylko decyzja do poprawienia, więc w tabeli „Rolki dzień po dniu"
**taka liczba jest czerwona i wytłuszczona**.

### Skrót to podpis, nie kod

Skrót osoby szedł wielkimi literami niezależnie od tego, co ktoś wpisał: `MarPro` → `MARPRO`.
To jest czyjś podpis na kalendarzu, więc zostaje taki, jak go wpisano.

### Kasowanie mieszka tam, gdzie edycja

Krzyżyk przy wierszu listy kont stał milimetry od „Edytuj", a robił rzecz nieodwracalną.
Usuwanie konta przeniosło się do panelu edycji, do tej samej strefy ryzyka, w której siedzi
usuwanie składników, rolek i zestawów.

### Menu bez grupy „Grafik"

Grupa z jedną pozycją to nagłówek nad niczym. **Grafik** stanął przy ekranach dnia — tam się
na niego patrzy — a **Szablon zmian** w Edycji, bo to ustawianie, nie oglądanie. Kafelki
Pulpitu dostały przy okazji te same znaki SVG co menu: kafelek i zakładka prowadzą w to samo
miejsce, więc nie ma powodu, żeby wyglądały na dwie różne rzeczy.

### Podłoga jakości

- **Fokus klawiatury widać na wszystkim, co klikalne** (`:focus-visible`), a nie tylko
  w polach formularza. Wcześniej osoba pracująca z klawiatury nie wiedziała, gdzie jest.
- **`prefers-reduced-motion` wyłącza przejścia.** Narzędzie pracy nie ma prawa kręcić ekranem
  komuś, kto sobie tego nie życzy.
- **`--muted` przyciemniony** z `#8A8781` na `#6F6C67`. Poprzedni dawał **3,1:1** na szarym tle,
  poniżej 4,5:1 wymaganych dla tekstu — a tym kolorem są wszystkie podpowiedzi i etykiety.
- **Wyłączony przycisk jest czytelny**, a nie wyblakły: stonowane tło zamiast `opacity:.45`,
  które dawało ~2,5:1 i nie pozwalało przeczytać, co właściwie jest nieaktywne.
- **Cyfry tabularne w całej aplikacji**, nie tam, gdzie ktoś pamiętał dopisać klasę `.num`.

**Odnośnik poznaje się po kolorze, nie po kresce.** Podkreślenie pojawia się dopiero pod
kursorem — w gęstych tabelach stała kreska pod każdą nazwą robi z ekranu siatkę. Dotyczy to
także nazw prowadzących do składu na Pulpicie: noszą kolor tekstu, a nie czerwień, bo tam
klikalne jest wszystko i wyróżnianie tego kolorem niczego by nie porządkowało.

**Czerwień jest jednym akcentem i ma jedno znaczenie: akcja i wybór.** Nosi ją przycisk główny,
pasek przy wybranej zakładce, strzałka sortowania, kreska pod główką wydruku. Nigdy nie jest
tłem i **nigdy nie jest statusem** — inaczej ten sam kolor mówiłby naraz „firma" i „uwaga".
To nie jest przeczulenie: firmowa czerwień obok statusowej zieleni ma dla osoby z deuteranopią
odległość ΔE 5,0 przy progu 8, czyli jest nie do rozróżnienia samym kolorem. Dlatego statusy
mają własną skalę i **zawsze idą z liczbą albo słowem** — procent food costu, „brak w bazie",
ikona alertu. Test pilnuje, że żaden token statusu nie przyjmie wartości czerwieni marki.

Znak firmowy siedzi w aplikacji jako SVG z oryginalnych plików, odchudzony z metadanych.
Czerń znaku jedzie na `currentColor`, więc **ten sam rysunek działa na jasnym i na ciemnym
tle** — nie trzymamy dwóch wersji tego samego logo. Sygnet służy też za favicon i za znak
na pasku telefonu, gdy menu jest schowane pod hamburgerem.

| Gdzie | Co |
|---|---|
| pasek boczny | logo poziome (sygnet + napis), pod nim „Sushi Planner" |
| pasek na telefonie | sam sygnet, po prawej stronie hamburgera |
| favicon | sygnet w kolorach firmowych |
| główka wydruku | sygnet, nadtytuł „Noto Sushi", nazwa dokumentu, czerwona kreska |
| tryb ciemny | czernie ze strony: tło `#0F0F0F`, karty `#1A1A1A`, pasek czarny |

**Montserrat wczytuje się z Google Fonts.** Gdy sieci nie ma — plik otwarty z dysku, tablet
w kuchni bez internetu — zapasowy stos systemowy przejmuje bez migotania układu; aplikacja
działa identycznie, zmienia się tylko krój. Jeśli ma działać w firmowym kroju również offline,
wystarczy wrzucić pliki `woff2` do repozytorium i wkleić je do środka (plik urośnie o ok. 80 kB).

---

## Instalacja jednym poleceniem

Na serwerze, jako root:

```bash
curl -sSL https://raw.githubusercontent.com/UZYTKOWNIK/sushi-planner/main/install.sh \
  | sh -s -- --port 30123 --repo https://github.com/UZYTKOWNIK/sushi-planner.git
```

Podmień `UZYTKOWNIK` na swoją nazwę na GitHubie, a `30123` na swój port
(na mikr.us to `30000 + numer serwera`).

Potem załóż pierwsze konto:

```bash
sushi adduser twoj@email.pl owner
```

I wejdź na `https://srvNUMER-PORT.wykr.es` — darmowa subdomena Mikrusa ma HTTPS od ręki.

Instalator sam: doinstaluje `git`, `python3` i `curl` jeśli ich brakuje, pobierze kod
do `/opt/sushi-planner`, założy katalog danych `/var/lib/sushi-planner`, uruchomi usługę
systemd i włączy codzienną automatyczną aktualizację.

Szczegóły wdrożenia na mikr.us: [`INSTRUKCJA-mikrus.md`](INSTRUKCJA-mikrus.md).

---

## Automatyczna aktualizacja

Timer systemd raz na dobę (ok. 4:30) sprawdza, czy w repozytorium jest coś nowego.
Jeśli jest — instaluje. Ręcznie:

```bash
sushi-update            # zainstaluj, jeśli jest nowa wersja
sushi-update --check    # tylko sprawdź, nic nie instaluj
sushi-update --force    # wymuś, nawet gdy nic się nie zmieniło
```

Aktualizacja przebiega tak:

1. Sprawdza, czy na GitHubie jest nowszy commit. Jeśli nie — kończy bez ruszania czegokolwiek.
2. Pakuje dane do `backup/przed-aktualizacja-<data>.tar.gz` (10 ostatnich paczek w rotacji).
3. Pobiera nową wersję.
4. Sprawdza składnię `server.py` i obecność `sushi-planner.html`.
5. Restartuje usługę i **czeka, aż `/api/health` odpowie**.
6. Jeśli cokolwiek z powyższego zawiedzie — **wraca do poprzedniej wersji** i restartuje.
   Nieudany commit trafia na czarną listę, żeby aktualizacja nie próbowała go w kółko
   co dobę. Ominięcie: `sushi-update --force`.

**Dane nigdy nie są ruszane** — leżą w `/var/lib/sushi-planner`, poza katalogiem repozytorium.

Wyłączenie automatu:

```bash
systemctl disable --now sushi-planner-update.timer
```

---

## Wydanie nowej wersji

**Bez gita, na Windowsie:** w folderze z plikami leży `publikuj.bat`. Podmieniasz pliki
w folderze i klikasz go dwukrotnie — porówna zawartość z GitHubem i wyśle tylko to,
co się różni. Przy pierwszym uruchomieniu poprosi o token GitHuba (fine-grained,
ograniczony do tego jednego repozytorium, uprawnienie *Contents: Read and write*)
i zapisze go w `%USERPROFILE%\.sushi-github-token`.

Okno **zamyka się samo** po udanej wysyłce — nie ma tam nic do czytania poza listą
wysłanych plików. Zostaje otwarte tylko wtedy, gdy coś nie wyszło: brak tokenu, token bez
dostępu albo błąd przy którymś pliku. Wtedy jest po co patrzeć na ekran.

**Z gitem:**

```bash
echo "1.6.0" > VERSION
git commit -am "opis zmiany"
git push
```

Serwery zaktualizują się same przy najbliższym przebiegu timera, albo od razu po
`sushi-update` na serwerze. Numer wersji i skrót commita widać w aplikacji
w **Ustawieniach → Serwer**.

---

## Polecenia na serwerze

| Polecenie | Co robi |
|---|---|
| `sushi users` | lista kont |
| `sushi adduser mail@x.pl chef` | nowe konto |
| `sushi passwd mail@x.pl` | zmiana hasła |
| `sushi deluser mail@x.pl` | usunięcie konta |
| `sushi-update` | aktualizacja na żądanie |
| `systemctl status sushi-planner` | stan usługi |
| `journalctl -u sushi-planner -f` | logi na żywo |
| `journalctl -u sushi-planner-update` | historia aktualizacji |

### API serwera

Cały interfejs aplikacji stoi na tych trasach — jeśli którejś zabraknie, zakładka po prostu
przestaje działać, więc `test-serwer.py` sprawdza każdą z osobna:

| Trasa | Kto | Do czego |
|---|---|---|
| `GET /api/health` | każdy | monitoring; podaje `version` i `commit` |
| `GET /api/me` · `POST /api/login` · `POST /api/logout` | każdy | sesja |
| `GET /api/data` · `PUT /api/data` | zalogowany / `owner`+`chef` | odczyt i zapis bazy (blokada optymistyczna) |
| `GET /api/users` · `POST /api/users` · `POST /api/users/update` · `POST /api/users/delete` | `owner` | konta i role z poziomu aplikacji |
| `GET /api/update/check` · `POST /api/update/run` · `GET /api/update/status` | `owner` | zakładka **Aktualizacja** |
| `POST /api/pdf` | zalogowany | wydruki przez Gotenberga |
| `POST /api/shift` | własny wpis: każdy zalogowany; cudzy i zbiorczy: uprawnienie do grafiku | operacje na zapisach |

Aktualizację uruchamia jednostka `sushi-planner-update.service`, a nie potomek serwera —
`update.sh` restartuje usługę, więc proces odpalony z jej wnętrza zginąłby w połowie roboty.

Odpowiedź 401/403/404 **dokańcza czytanie treści żądania**, zanim odpowie. Bez tego przy
keep-alive niedoczytane bajty rozjeżdżają następne zapytanie na tym samym połączeniu
i przeglądarka dostaje z pozoru losowe 400. Test trzyma to za rękę: odmowa zapisu, a zaraz
po niej `GET /api/health` na tym samym połączeniu.

### Role

| Rola | Uprawnienia |
|---|---|
| `owner` | wszystko, w tym zakładka **Użytkownicy** do zarządzania kontami |
| `chef` | pełna edycja składników, receptur i zestawów |
| `viewer` | tylko podgląd receptur i gramatur — dobre na tablet w kuchni |
| `staff` | **pracownik**: sam grafik, zapisy na zmiany, zero cen i receptur |

Skrót i kolor pokazywany w grafiku ustawia się przy koncie, w tej samej zakładce.

Konta zakłada się w aplikacji (Użytkownicy) albo z konsoli poleceniem `sushi adduser`.

### Menu — pięć grup

Menu boczne dzieli się na pięć grup, według tego **kiedy** się z czegoś korzysta:

| Grupa | Zakładki | Kiedy |
|---|---|---|
| **Pulpit** | Pulpit · Przygotowanie · Rolki · Zestawy · Pakowanie · Kierowca · Kontrola zasobów | codziennie, w kuchni i w trasie |
| **Grafik** | Kalendarz · Szablon zmian | układanie obsady, zapisy na zmiany |
| **Edycja** | Załadunki · Automaty · Zestawy · Rolki · Półprodukty · Składniki | gdy coś się zmienia w menu albo w cenach |
| **Analizy** | Foodcost · Załadunki · Historia cen · Symulacja | raz na jakiś czas, przy liczeniu |
| **Narzędzia** | Użytkownicy · Ustawienia · Aktualizacja · Wyloguj | rzadko |

**Grafik**, **Edycja**, **Analizy** i **Narzędzia** zwijają się kliknięciem w nagłówek grupy — Pulpit
zostaje zawsze rozwinięty, bo to codzienna praca. Stan pamięta przeglądarka, a grupa
z bieżącą zakładką rozwija się sama, żeby nigdy nie było wątpliwości, gdzie się jest.

Aplikacja startuje na **Pulpicie** — data, załadunek dnia i sześć kafelków prowadzących
do ekranów roboczych. Dawny pulpit z food costem nie zniknął, jest w Analizach jako **Foodcost**.

**Na Pulpicie nie ma pieniędzy.** Żaden z ekranów dnia nie pokazuje cen, kosztów ani food
costu — w kuchni i w trasie liczy się co, ile i gdzie. Kwoty są w Edycji i w Analizach,
i test tego pilnuje: na każdym ekranie Pulpitu szuka wzorca „liczba + zł" i musi nie znaleźć nic.

Każdy ekran Pulpitu ma u góry **pasek dnia**: ‹ dzisiaj ›, data, nazwa dnia tygodnia
i nazwa załadunku, który tego dnia jedzie. Zmiana dnia przelicza wszystko na tym ekranie.
Dzień bez przypisanego załadunku pokazuje pustą rozpiskę i podpowiada, gdzie go przypisać.

| Ekran | Co pokazuje |
|---|---|
| **Przygotowanie** | półprodukty i surowce na dany dzień — od tego zaczyna się zmiana |
| **Rolki** | ile których rolek zwinąć, przeliczone w górę z zestawów, w podziale na kategorie |
| **Zestawy** | ile których zestawów zapakować |
| **Pakowanie** | te same zestawy rozbite na automaty — w dwóch widokach |
| **Kierowca** | wszystkie automaty z zaznaczonym załadunkiem; klik → powiększenie i numery szafek |
| **Kontrola zasobów** | składniki i półprodukty na jutro i pojutrze — czy trzeba zamawiać |

Na **Przygotowaniu**, **Rolkach** i **Zestawach** nazwa jest klikalna i otwiera **osobną
podstronę ze składem jednej sztuki** — nie rozpiskę całego dnia, tylko szybkie przypomnienie
dla kucharza: z czego składa się ten półprodukt, ta rolka, ten zestaw.

| Skład | Co pokazuje |
|---|---|
| półprodukt | wydajność partii i składniki tak, jak w recepturze; przy odpadzie osobne kolumny ilość / odpad / razem |
| rolka | ile kawałków ma rolka i ile czego idzie **na całą rolkę** |
| zestaw | zdjęcie, rolki w kawałkach (i ile to całych rolek) plus dodatki |

Składnik, który sam jest półproduktem, jest klikalny — z zestawu wchodzi się w rolkę,
z rolki w ryż. Nazwy nie są niebieskimi odnośnikami: to zwykły tekst z kropkowaną linią
i strzałką `›`, żeby tabela dalej czytała się jak tabela. **Wróć** cofa dokładnie o jeden krok tej drogi, a z pierwszego składu
wraca na listę, z której się weszło. Cen nie ma również tutaj.

**Pakowanie** ma przełącznik **Automaty / Zestawy** — ta sama macierz z dwóch stron.
„Automaty" to kafelek na maszynę z listą zestawów (pomaga załadować wózek pod jedną maszynę),
„Zestawy" to kafelek na zestaw z listą maszyn (pomaga odliczyć jeden zestaw na całą trasę).
Suma po kafelkach — w jednym i w drugim trybie — musi się zgadzać z liczbą szafek
w załadunku i test tego pilnuje.

Na Pulpicie liczy się to, co się robi rękami, więc **Rolki** podają tylko liczbę rolek do
zwinięcia, a **Zestawy** tylko liczbę sztuk — kawałki są w recepturze, nie na liście roboczej.

Lista rolek idzie **kategoriami**: nagłówek grupy z **sumą grupy po prawej**, pod nim rolki
w kolejności zwijania — plus kafelek na każdą kategorię nad tabelą. Suma siedzi w nagłówku,
a nie w osobnym wierszu „Razem": jeden wiersz mniej na grupę i liczba stoi tam, gdzie oko
i tak trafia, wchodząc w grupę. Hosomaki zwija się
inaczej niż Futomaki i zwykle robi je kto inny, więc „ile tego dziś jest" trzeba wiedzieć
osobno dla każdej grupy, a nie tylko łącznie. Pod nagłówkiem kategorii nazwa nie powtarza
kategorii — pod „Hosomaki" stoi po prostu „Ogórek". Tabeli pogrupowanej **nie da się
przesortować po kolumnach**: sortowanie rozbiłoby grupy, a kolejność zwijania jest tu
ważniejsza niż ranking ilości. Grupa złożona z samych rolek skasowanych z bazy nie dostaje
sumy — nie ma czego sumować i „Razem 0" wprowadzałoby w błąd. To samo rozbicie idzie na
**wydruk**: karta na kategorię, a suma grupy w tytule karty — „Hosomaki · 201,6".
Zawartość list jest pisana zwykłym tekstem: skoro pogrubione jest wszystko, pogrubienie
przestaje cokolwiek znaczyć.
Każdy ekran dnia ma **← Wróć** prowadzący na Pulpit główny.

Każdy powrót w aplikacji to ten sam przycisk **← Wróć** — w składzie, u kierowcy
i w szczegółach załadunku.

**Kierowca** to przegląd wszystkich maszyn z siatką szafek — zielona jedzie, czerwona
zostaje, szara nie ma przypisanego zestawu. Klik w automat powiększa jego układ i dokłada
tabelę „Co i gdzie włożyć": zestaw, ile sztuk, numery szafek.

**Na telefonie** menu chowa się pod **hamburgerem** — stały pasek na całą szerokość u góry
strony (nie pływający przycisk, który potrafił zasłonić „Wróć") z nazwą bieżącej zakładki.
Klik wysuwa pełne menu z grupami, a wybór zakładki, klik w tło albo Esc je zamyka. Wcześniej menu było paskiem przewijanym w bok, na którym gubiła się połowa
pozycji. Pulpit składa się do dwóch kolumn zamiast jednej — kafelki, kostki liczb
i skład mieszczą się bez przewijania w bok. Szerokie tabele (krzyżówka pakowania, kontrola
zasobów) przewijają się poziomo z **przyklejoną pierwszą kolumną**, więc zawsze widać, czego
dotyczy liczba. Test sprawdza na ekranie 390 px, że żaden ekran Pulpitu nie wystaje poza szerokość okna.

Ponowne kliknięcie zakładki w menu wraca z karty szczegółów do listy.


### Grafik zmian

Kto kiedy stoi. Trzy warstwy, od najbardziej ogólnej do najbardziej szczegółowej — i to
jest cała mechanika, reszta to widoki.

**1. Szablon tygodniowy.** Dla każdego dnia tygodnia lista zmian: nazwa, godzina od–do,
liczba osób. „W poniedziałki dwie osoby na I zmianie i jedna na II" wpisuje się raz i tyle.
Szablon obowiązuje bezterminowo, więc kalendarz jest wypełniony na wszystkie miesiące
w przód bez żadnej dalszej pracy — również na luty przyszłego roku.

**2. Tydzień inny niż reszta.** Przycisk **Zmień ten tydzień** wyodrębnia jeden tydzień
(klucz ISO, np. `2026-W33`) i od tej pory ten jeden chodzi po swojemu: inne godziny, więcej
osób w sobotę, dodatkowa zmiana w Walentynki. Reszta roku dalej słucha szablonu.
**Przywróć szablon** kasuje wyjątek.

Kopia do nadpisania zachowuje **identyfikatory zmian**. To nie jest szczegół: klucz zapisu
to `data|id zmiany`, a data należy do dokładnie jednego tygodnia, więc kolizji nie ma —
za to zapisy zrobione przed wyodrębnieniem tygodnia zostają na miejscu. Bez tego menedżer,
który chciał przesunąć jedną zmianę o godzinę, kasowałby przy okazji wszystkie zgłoszenia.

**3. Zapisy — kto pierwszy, ten stoi.** Klikasz „Zapisz się" i **od razu stoisz**, o ile
jest miejsce. Gdy miejsc nie ma, zapis się nie udaje i trzeba poprosić kogoś ze składu,
żeby się wypisał. Nazwiska stojących widać przy każdej zmianie, więc wiadomo, do kogo mówić.

Wcześniej działała tu kolejka chętnych, z której wybierał menedżer. Brzmiało rozsądnie,
a w praktyce znaczyło, że **nikt nie wie, czy przyjdzie**, dopóki ktoś nie kliknie — i że
każdy zapis wymagał drugiej decyzji, często tej samej osoby, która i tak zatwierdzała
wszystko po kolei. Teraz zapis **jest** decyzją, a menedżer wkracza tylko wtedy, gdy trzeba
coś poprawić.

Ponad liczbę miejsc nie wejdzie nikt — pilnuje tego i przeglądarka (przycisk gaśnie
i mówi, co zrobić), i serwer (odpowiada błędem), bo pierwsze jest wygodą, a drugie zasadą.
Kto układa grafik, ten wypisze i wpisze dowolną osobę, także wstecz.

Wypisanie to **krzyżyk przy nazwisku**, jeden mechanizm dla wszystkich: układający grafik widzi
go przy każdym, pracownik — tylko przy sobie. Osobnego przycisku „Wypisz się" pod spodem nie ma;
robił to samo drugą drogą i przy pełnym składzie stały obok siebie dwa przyciski o tym samym
skutku.

Migracja ze starego modelu robi się sama: przypisani wchodzą wprost, a chętni, którzy się
nie załapali, dopełniają wolne miejsca w kolejności zgłoszeń — bo od teraz właśnie tak
by to wyszło.

#### Zapis na wiele dni naraz

Zaznacza się tak jak w każdej liście plików: **klik** bierze jeden dzień, **Ctrl+klik**
dokłada albo zdejmuje, **Shift+klik** bierze cały zakres od poprzedniego kliknięcia.
Osobny „tryb zaznaczania" z przyciskiem wymagał nauki i jednego kliknięcia więcej za każdym
razem, a niczego nie dawał w zamian. (Na telefonie modyfikatorów nie ma, więc zostaje jeden
dzień naraz — podpowiedź o klawiszach chowa się tam, żeby nie kusiła.)

Po wykonaniu wpisu **zaznaczenie znika**. Zostawione świeciłoby dalej i przy następnym
kliknięciu w przycisk zadziałałoby drugi raz na te same dni. Które dni odpadły, mówi komunikat
przy panelu — wisi tam do następnego kliknięcia w kalendarz.

**Panel pod kalendarzem opisuje całe zaznaczenie, nie jeden dzień.** Data z nagłówka
znika — zostaje „Ustawiasz 5 dni" i lista dat — a zmiany są **łączone po nazwie**, z podsumowaniem
w stylu „I zmiana · jest w 5 z 5 dni · wolne miejsce w 4 z 5". Przyciski tam działają na wszystkie
zaznaczone dni naraz. Wcześniej panel pokazywał ostatnio kliknięty dzień i zapis wchodził tylko
na niego, choć zaznaczonych było pięć — każda część działała, a całość wyglądała jak awaria.

Przy jednym zaznaczonym dniu panel wraca do zwykłej postaci: data i nazwiska.

Dni, w których nie ma już miejsca albo nie ma zmiany o tej nazwie, **zostają pominięte
i wymienione z daty** — i tylko one zostają zaznaczone, żeby od razu było wiadomo, czym
się jeszcze zająć. Ciche „wpisano 4 z 6" byłoby gorsze od braku tej funkcji: człowiek
wychodzi z przekonaniem, że stoi w sześciu dniach.

Paczka idzie **jednym żądaniem**, nie pięcioma. Pięć osobnych mogłoby przejść w połowie
i nikt by nie wiedział, w połowie których.

Dopasowanie idzie po **nazwie zmiany**, nie po identyfikatorze: „I zmiana" w każdym
z zaznaczonych dni to inny wpis w bazie, a w tygodniu z własnym układem także inne id.
Nazwa jest tym, co użytkownik ma w głowie.

#### Kalendarz

Domyślnie **miesiąc**, przełącznikiem **tydzień**. W komórce dnia pasek na każdą zmianę:
skrót nazwy i obsada `2/2`. Kolor paska to jedyna rzecz, którą czyta się z całego miesiąca
naraz, więc mówi o pilności, a nie o samym stanie:

Na pasku stoją też **plakietki ze skrótami** osób przypisanych, w ich kolorach — dzięki temu
„kto gdzie stoi" widać z całego miesiąca naraz, bez wchodzenia w dzień. Na telefonie plakietki
znikają: komórka ma tam ~50 px, sześcioznakowy skrót i tak by się nie zmieścił, a rozpychałby
wiersze na różną wysokość. Kto stoi, widać wtedy w panelu dnia i w widoku tygodnia.

| Kolor | Znaczy |
|---|---|
| zielony | komplet — nic nie rób |
| czerwony | brakuje ludzi |
| szary | dzień już był, nic z tym nie zrobisz |

Kolor odpowiada na **jedno** pytanie: czy jest komplet. Data zmienia tylko to, czy da się
z tym jeszcze cokolwiek zrobić. Wcześniej czerwień znaczyła „za mniej niż trzy dni", przez co
grafik na przyszły miesiąc wyglądał na uporządkowany, choć nie stał na nim nikt.

**Tło komórki zostaje czyste** — niosą je paski zmian. „Dziś" i zaznaczenie to obwódki
w kolorze marki, cieńsza i grubsza, więc nie ma czego rozszyfrowywać.

**Czerwona ramka znaczy wybór — wszędzie.** Wybrany dzień w kalendarzu, zaznaczone dni,
wybrana zakładka w menu. Jedna zasada zamiast trzech różnych sposobów pokazywania tego samego.

**Obsadę niesie tło, nie krawędź.** Kafelek zmiany wygląda tak samo w kolumnie tygodnia
i w panelu dnia: szara ramka, a kolor tła mówi, czy jest komplet — dokładnie jak paski
w siatce miesiąca. Pogrubiona krawędź z lewej (w kafelkach, w bannerach, przy wybranej
zakładce menu) była trzecim sposobem mówienia tej samej rzeczy i nie pasowała do reszty;
zniknęła z całej aplikacji.

#### Jeden pasek nad kalendarzem

Wszystko siedzi w jednej linii: strzałki **po obu stronach** nazwy okresu, zaraz obok **Dziś**,
a po prawej godziny i przełącznik widoku. W widoku miesiąca nazwą jest miesiąc, w widoku
tygodnia — numer tygodnia z zakresem dat i sterowaniem wyjątkiem tygodnia. Dwa paski jeden pod
drugim zabierały dwa razy tyle wysokości i za każdym razem trzeba było szukać, w którym co siedzi.

Godziny po prawej to **twoje** godziny w wyświetlanym okresie, a w nawiasie liczba dni.
Bez zalogowania (plik z dysku) pokazują się wszystkie godziny okresu, z dopiskiem „razem".

W **widoku tygodnia** w kolumnach stoją same plakietki z kodem — nazwisko rozpychało wiersz
na dwie linie, a kod i tak mówi, kto to. Nazwiska są w panelu pod kalendarzem.

Plakietka ma tam **wysokość przycisku** i stoi w jednym rzędzie z „Zapisz się", więc rząd
się nie faluje. Kasowanie należy do plakietki, nie do wiersza:

| Kto | Co widzi |
|---|---|
| pracownik | „Zapisz się", a krzyżyk **tylko przy swojej** plakietce |
| układający grafik | krzyżyk przy **każdej** plakietce i plusik obok „Zapisz się" — dopisuje innych |

Plusik ma dokładnie ten sam rozmiar co krzyżyk (20 px, `box-sizing: border-box`, bo jeden
ma ramkę przycisku, a drugi nie).

#### Uprawnienie do układania grafiku

Kto może wpisywać innych, zmieniać szablon zmian i poprawiać grafik wstecz, decyduje
**osobny przełącznik przy koncie** — nie rola. Zmianami zajmuje się zwykle ktoś inny niż
osoba od cen i receptur: kucharz z pełnym dostępem do bazy nie musi mieć nic do grafiku,
a kierownik zmiany, który poza grafikiem nie ma w aplikacji nic do roboty, musi.
Właściciel ma je zawsze — to on je nadaje i nie może się od niego odciąć.

Serwer pilnuje tego na **każdej** ścieżce zapisu, także przy `PUT /api/data`: komu brakuje
uprawnienia, temu pola grafiku podmieniamy na te, które już są w bazie. Bez tego kucharz
z kartą otwartą od rana cofnąłby jednym zapisem wszystkie wpisy zrobione w międzyczasie,
i to nie chcąc.

#### Konto pracownika

Rola `staff` widzi **wyłącznie grafik**. Nie „ma schowane" — serwer nie wysyła jej reszty:
`GET /api/data` dla tej roli zwraca sam grafik plus puste kolekcje, więc w odpowiedzi nie ma
ani jednej ceny zakupu. Sprawdza to asercja, która przeszukuje surowy JSON.

Zapisywać taka osoba może wyłącznie przez `POST /api/shift`, który przyjmuje dzień, zmianę
i „chcę / nie chcę", a tożsamość bierze z ciasteczka — nie da się nim zapisać kogoś innego
ani ruszyć czegokolwiek poza grafikiem. `PUT /api/data` odpowiada takiemu kontu `403`.

Tą samą trasą chodzi **menedżer** i to nie jest kosmetyka. `POST /api/shift` podbija `rev`,
więc gdyby menedżer zapisywał grafik całym blobem bazy, każde zgłoszenie pracownika
unieważniałoby `rev` w jego otwartej karcie i witałoby go okienko o konflikcie. Tutaj każda
odpowiedź przynosi świeży `rev`, a operacje ruszają wyłącznie swój wiersz zapisów. Szablon
zmian i kartoteka jadą dalej zwykłym zapisem — to edycja menedżerska, przy której konflikt
jest konfliktem naprawdę.

#### Ludzie to konta, nie osobna lista

**Nie ma kartoteki pracowników.** W grafiku może stać wyłącznie ktoś, kto ma konto
w aplikacji — pilnuje tego serwer, nie tylko formularz. Dzięki temu nie ma dwóch list
do utrzymywania i nie da się wpisać do grafiku człowieka, który nigdy się do niego nie
zaloguje, więc i tak nie zobaczy, że ma przyjść.

W **Narzędzia → Użytkownicy**, przy każdym koncie, ustawia się to, co widać w grafiku:

- **imię i nazwisko** — podpis pod plakietką,
- **skrót do 6 znaków** — to, co stoi na kalendarzu; pusty oznacza „weź początek imienia",
- **kolor** z ośmiu do wyboru.

Osiem kolorów, a nie dowolny wybór z tęczy: mają się różnić także przy niedowidzeniu barw
i żaden nie może udawać firmowej czerwieni ani kolorów stanu zmiany — inaczej „kto stoi"
myliłoby się z „czy jest komplet". Napis na plakietce dobiera się sam, biały albo czarny,
zależnie od tego, który daje większy kontrast; przy 9-piksela­wej czcionce nie ma marginesu
na zgadywanie, więc test liczy kontrast dla każdego koloru i wymaga co najmniej 4,5:1.

Wpis w grafiku powstaje sam przy pierwszym zgłoszeniu albo wtedy, gdy właściciel nada komuś
skrót lub kolor. Zgłoszenia starsze niż pół roku kasują się same przy wczytaniu bazy: nikt
do nich nie wraca, a puchną w każdym zapisie.

#### Godziny w miesiącu

Długość zmiany liczy się z jej godzin, a zmiana przez północ (22:00–06:00) daje osiem godzin,
nie minus szesnaście — w gastronomii to normalny przypadek, nie błąd danych.

**Pracownik** widzi nad kalendarzem jedną liczbę: swoje godziny w wyświetlanym miesiącu
i liczbę zmian. **Kto układa grafik**, dostaje pod kalendarzem zestawienie wszystkich,
którzy się w tym miesiącu wpisali — godziny, liczba zmian i suma. Sortowane od największej
liczby godzin, bo układanie grafiku to w praktyce pilnowanie, żeby nie wyszło, że jedna
osoba zebrała trzy razy tyle co reszta.

Zestawienie jest **pod** kalendarzem, nie nad nim: najpierw się patrzy, kto gdzie stoi,
a dopiero potem sprawdza, czy godziny rozłożyły się równo. Skrócona wersja — godziny
bieżącego miesiąca przy każdym koncie — jest też w Użytkownikach.

### Zestaw = rolki + dodatki

Zestaw ma dwie sekcje. **Rolki** — co i ile kawałków. **Dodatki** — wszystko pozostałe:
tacka, pałeczki, sos w saszetce, imbir, wasabi, opłata SUP, serwetki. Jedna lista, wybierasz
z niej dowolny składnik i podajesz ilość.

Wcześniej tacka, pałeczki i sos miały osobne pole, a składnik trzeba było najpierw oznaczyć
„rolą w opakowaniu". To znikło — okazało się komplikacją bez pokrycia w tym, jak się z tego
korzysta. Stare zestawy migrują się same przy pierwszym wczytaniu: zawartość pola `pack`
ląduje w dodatkach, a gdy ten sam składnik był w obu miejscach, ilości się sumują.

### Zdjęcia

Rolka i zestaw mają zdjęcie (klik albo przeciągnięcie pliku). Jest zmniejszane do **1200 px
po dłuższym boku** i zapisywane jako JPEG.

Zdjęcie widać **w kafelku i w podglądzie** — tam pomaga poznać rolkę bez czytania nazwy.
**W tabeli go nie ma**: miniatura zabierała szerokość kolumnie z nazwą, a w widoku, który
służy do porównywania liczb w kolumnach, nic nie wnosiła. Rozmiar bazy i licznik zdjęć widać w Ustawieniach
→ Dane; powyżej 4 MB pojawia się ostrzeżenie — przy komplecie zdjęć w tej rozdzielczości
warto tam zaglądać.

### Kategorie rolek

„Hosomaki Ogórek" to w istocie **kategoria i nazwa sklejone w jeden ciąg**. Rozbite dają się
filtrować, sortować i skracać. Rolka ma więc `catId`, a kategoria — nazwę i **kod**:

| Kategoria | Kod |
|---|---|
| Hosomaki | HS |
| Uramaki | UR |
| Futomaki | FT |

Gdzie jest miejsce, pokazuje się **kategoria + nazwa** („Hosomaki Ogórek") — listy, karty,
skład, receptury, rozpiski. Gdzie miejsca nie ma, **kod + nazwa** („HS Ogórek") — etykiety
wykresów i wydruk składu zestawów, gdzie każda rolka powtarza się przy każdym zestawie.

Podział robi się sam przy pierwszym wczytaniu: pierwszy człon nazwy jest dopasowywany
(bez ogonków, po przedrostku, więc „Futomak" i „Futomaki" trafiają w to samo), kategoria
powstaje, jeśli jej nie ma, a z nazwy zostaje sam człon znaczący. **Nazwy nierozpoznane
zostają nietknięte** — lepiej rolka bez kategorii niż przycięta nazwa. Migracja odpala się
raz: gdy pole `catId` już jest, przestaje cokolwiek ruszać, i test tego pilnuje.

Kategorie edytuje się w **Ustawieniach** (nazwa, kod, licznik użycia). Kod musi być unikalny,
a kategorii w użyciu nie da się usunąć. W edytorze rolki kategoria jest listą rozwijaną,
a w polu „Nazwa" wpisuje się już tylko człon znaczący.

### Kolejność ręczna

Arkusz niósł informację, której nie da się odtworzyć z żadnej kolumny: **składniki rolki
były wypisane w kolejności nakładania na matę, a rolki w kolejności zwijania**. Aplikacja
trzyma to jako kolejność tablicy w bazie, a sortowanie tabel działa wyłącznie na widoku —
jedno nigdy nie nadpisze drugiego.

W tabelach jest kolumna **#** z pozycją w kolejności ręcznej. Klik w inny nagłówek sortuje
jak dotąd, ale cykl ma trzy stany: **rosnąco → malejąco → kolejność ręczna**. Klik w „#"
wraca do niej od razu. Numery w kolumnie „#" nie zmieniają się przy sortowaniu — przy cenie
malejąco nadal widać, że ta rolka jest trzecia do zwinięcia.

Kolejność zmienia się w dwóch miejscach:

- **w edytorze rolki i zestawu** — każdy wiersz receptury ma uchwyt ⠿ do przeciągania
  oraz ↑/↓ (bo na telefonie przeciąganie bywa uciążliwe)
- **na listach Rolki i Zestawy** — przycisk **⇅ Kolejność** przełącza listę w tryb
  przestawiania. Sortowanie jest wtedy wyłączone, żeby nie dało się przeciągać wierszy
  w widoku posortowanym po cenie i nie wiedzieć, co się właściwie zapisuje. Zapis jest
  natychmiastowy.

Przeciąganie działa po identyfikatorach, nie po numerach wierszy, więc przestawianie
w liście przefiltrowanej wyszukiwarką albo archiwum trafia we właściwe miejsce w bazie.

Kolejność widać tam, gdzie pracuje: **Pulpit → Rolki** układa się w kolejności zwijania
(nie od największej ilości), **Pulpit → Zestawy** w kolejności z listy zestawów, a skład
rolki i zestawu ma ponumerowane wiersze.

### Wydruk receptur (PDF)

Sześć wydruków, jeden układ. Cztery z **Pulpitu** — przycisk **⎙ PDF** w pasku ekranu dnia
drukuje to, co widać na ekranie, dla wybranego dnia:

| Ekran | Na kartce |
|---|---|
| Przygotowanie | półprodukty (z liczbą partii) i składniki po alfabecie, z ilością i liczbą opakowań |
| Rolki | ile których rolek zwinąć, kategoriami, z sumą grupy w tytule karty |
| Zestawy | ile których zestawów złożyć |
| Pakowanie | **obie strony naraz**: kafelki automatów z listą zestawów i kafelki zestawów z kodami automatów, w ramkach, rozdzielone nagłówkami sekcji |

Kafelek automatu na wydruku tytułowany jest **kodem, nie nazwą**. „Kaufland, Norymberska"
łamało się na dwie linie i rozpychało kafelek; „NOR" rozpoznaje się w pół sekundy i zawsze
mieści się w jednej. Dzięki temu sekcja Automatów nie potrzebuje rezerwy na drugą linię
tytułu — a niższe kafelki oznaczają większe pismo w całym dokumencie (16,75 px zamiast 15,25).
Rezerwa zostaje tam, gdzie nazwy naprawdę się łamią: w sekcji Zestawów.

**A gdy nazwa i tak się nie mieści — traci pierwszy wyraz.** Aplikacja składa dokument,
sprawdza w ukrytej ramce, czy któryś tytuł kafelka zajął dwie linie, i jeśli tak — skraca
pierwszy wyraz i szuka układu jeszcze raz: „Średni Mieszany" → „Śre. Mieszany" → „Ś. Mieszany".
Dwa podejścia i koniec. Skracamy **pierwszy** wyraz, bo w nazwach zestawów to rozmiar
(„Mały", „Średni", „Duży"), a drugi mówi, co jest w środku — i to on musi zostać czytelny.
Nazwa jednowyrazowa („Wegański") zostaje nietknięta, bo nie ma czego skracać.

Krótsze tytuły to niższe kafelki, więc pismo przy okazji zwykle rośnie — i dlatego po
skróceniu układ szuka się od nowa. **Pełne nazwy zostają w wierszach kafelków**; skrót
dotyczy wyłącznie tytułów, i wyłącznie w kafelkach. Na kartce z recepturami tytuł ma całą
szerokość kolumny, więc złamanie go nie boli, a „Hos. Rzodkiew Takuan" byłoby gorsze od
pełnej nazwy w dwóch liniach.

Pomiar liczy prostokąty zakresu obejmującego **sam tekst nazwy**. Objęcie całego nagłówka
dałoby osobny prostokąt dla numeru w `<span>` i każdy tytuł wyglądałby na złamany — na tym
się zresztą przejechałem przy pierwszym podejściu.

Wszystkie sześć ma **wspólną główkę**: sygnet, nadtytuł „Noto Sushi", nazwa dokumentu i
czerwona kreska pod spodem. Kartka z kuchni ma wyglądać jak dokument firmowy, a nie jak wydruk
z przeglądarki. **Dane zostają czarne** — czerwień jest tylko w kresce, w znaku i w numerach
kart, więc czarno-biała drukarka w kuchni nie gubi niczego, co się liczy.

W tytule stoi **nazwa załadunku**, nie data — kartki nie drukuje się codziennie, tylko wtedy,
gdy zmienia się załadunek, i wisi tak długo, jak długo ten załadunek obowiązuje. Te same cztery
wydruki można wywołać wprost z **karty załadunku** w Edycji, bez chodzenia po dniach.

#### Każda sekcja liczy kolumny osobno

Sekcje wydruku stoją jedna pod drugą i **każda dobiera liczbę kolumn samodzielnie**: sześć
automatów układa się w dwa rzędy po trzy, osiem zestawów w dwa po cztery. Reguła jest prosta —
najpierw **najmniej rzędów** (mniej rzędów to mniej miejsca w pionie), a przy remisie wygrywa
**układ równy**: sześć kafelków w trzech kolumnach to dwa pełne rzędy, w czterech byłby rząd
czterech i rząd dwóch z dziurą po prawej.

Wspólny pozostaje **stopień pisma** — jeden na cały dokument, bo różne rozmiary między
sekcjami czytałyby się jak dwa różne wydruki zszyte razem. Sufit liczby kolumn to
**Ustawienia → Maksymalnie kolumn** dla list tekstowych; Pakowanie ma własny, wyższy (4),
bo w kafelku stoi kod i jedna cyfra, a nie wiersz receptury. Gęstsze kafelki oznaczają
niższe sekcje, a niższe sekcje — większe pismo: ta zmiana podniosła Pakowanie z 13 na 15,25 px.

Siatka ma **1 px luzu z prawej**. Bez tego ramka kafelka w ostatniej kolumnie leżała dokładnie
na krawędzi pola zadruku i przy rasteryzacji znikała — na ekranie było dobrze, na papierze
kafelek nie miał prawego boku.

Kafelki Pakowania mają ramki i **równą wysokość w obrębie sekcji** — brakujące wiersze
dopychane są pustymi, a na nazwę zarezerwowane są dwie linie, żeby dłuższa nazwa automatu
nie rozjeżdżała rzędu. Równe prostokąty porównuje się wzrokiem, nierówne trzeba czytać.

#### Liczby stoją w kolumnie

Wiersz to **nazwa po lewej, szare kropki, liczba w swojej kolumnie, jednostka w następnej**.
Kropki są jedynym elementem, który może się zwężać — reszta ma stałą szerokość, więc cyfry
i przecinki stoją jedne pod drugimi w całej karcie. `tabular-nums` pilnuje, żeby „110" i „0,50"
miały tę samą szerokość znaku.

Szerokość tej kolumny **karta liczy ze swojej własnej treści**: najdłuższa wartość w karcie
wyznacza `--ilw` (w `ch`, czyli w szerokościach cyfry), tak samo jednostka — `--jmw`. Sztywna
rezerwa robiła jedno z dwojga: przy karcie z samymi jednocyfrowymi liczbami kropki urywały się
pół centymetra przed cyfrą, a przy „22464" wiersz wystawał poza kafelek. Kolumna dopasowana
do treści kurczy się, gdy nie ma czego mieścić, i rośnie, gdy trzeba — a kropki zawsze dobiegają
do liczby.

**Liczby nie są wytłuszczone.** Skoro stoją tam, gdzie oko ich szuka, nie muszą się przebijać
krojem — bold zostaje w nazwach kart. Zniknęły też nawiasy z receptur w Edycji: „Ryż (160 g)"
to teraz „Ryż …… 160 g". Nawias był protezą oddzielającą nazwę od liczby, a przy kolumnie
jest zbędny.

Kolumnę jednostki karta rezerwuje **tylko wtedy, gdy któryś jej wiersz ma jednostkę** —
w Pakowaniu żaden nie ma i pusty pasek zjadałby szerokość wąskiej kolumny. Przygotowanie ma
dwie takie pary (ilość + jednostka, opakowania + „opak."), obie wyrównane osobno.

Wiersza **„Razem" nie ma** — suma grupy stoi w tytule karty („Hosomaki · 201,6"), więc
powtarzanie jej na dole byłoby tą samą liczbą dwa razy.

Dzień bez przypisanego załadunku nie generuje pustej kartki — aplikacja mówi, czego brakuje.

I dwa z **Edycji**, jako wzorce niezależne od dnia. W widoku **Rolki** przycisk składa kartkę z recepturami,
w widoku **Zestawy** — kartkę ze składem zestawów (same rolki, liczba kawałków bez jednostki;
dodatki bierze się z Pakowania, nie z tej kartki). Obie mają numer, nazwę i wciętą listę
pozycji z ilościami — bez ramek, bez zdjęć i bez wiersza podsumowania pod tytułem.

Rolki w zestawie idą w **kolejności z listy rolek**, nie w kolejności wpisania do zestawu:
na każdej kartce schodzi się tak samo, z góry na dół, w tej kolejności co zwijanie.

Cała mechanika składania kartki — dobór pisma i kolumn, stopka, nagłówki, sekcje — siedzi
w jednej funkcji, więc każdy kolejny wydruk dostaje to samo zachowanie za darmo; dokumenty
różnią się wyłącznie tym, co trafia na listę. Karty z krótkimi listami (receptury, zestawy,
kafelki pakowania) trzymają się w całości, a długie wykazy (przygotowanie, rolki dnia)
przelewają się między kolumnami — inaczej czterdziestowierszowa lista składników wymuszałaby
jedną kolumnę i najmniejsze pismo.

**Układ dobiera się sam, pod jak największe pismo.** Aplikacja renderuje dokument w ukrytej
ramce o wymiarach pola zadruku A4 i dla każdej dozwolonej liczby kolumn szuka — binarnie —
największego stopnia pisma, przy którym całość mieści się na jednej stronie. Wygrywa
największa czcionka; przy remisie mniej kolumn.

**Wiersze się nie zawijają** (`white-space:nowrap`). Zawinięta nazwa rolki kosztuje wiersz
i rozwala rytm listy, więc zamiast zawijać, pomiar uznaje taki układ za niemieszczący się
i schodzi z czcionką albo z liczbą kolumn. Dlatego pomiar sprawdza **oba wymiary** —
w pionie z 4% zapasem na różnice w metrykach fontów, w poziomie na styk, bo tekst wystający
w bok zostałby ucięty.

Marginesy ustawia **wyłącznie Gotenberg** (0,4″ na boki, 0,5″ na górę i dół). CSS podaje
tylko `@page{size:A4}` — gdy dokładał własne `margin`, marginesy liczyły się dwa razy,
pomiar zakładał o 10% więcej miejsca niż było naprawdę i wydruk rozlewał się na drugą stronę.

Dwa parametry siedzą w **Ustawieniach → Wydruki PDF**:

| Ustawienie | Domyślnie | Co robi |
|---|---|---|
| Minimalna czcionka (px) | 11 | poniżej tego aplikacja nie zejdzie |
| Maksymalnie kolumn | 3 | sufit dla siatki |

Gdy przy minimalnym piśmie i maksymalnej liczbie kolumn treść **nadal nie mieści się na
jednej stronie**, wydruk nie robi się mniejszy — dostaje kolejną stronę. Czytelność jest
ważniejsza niż jedna kartka.

Składniki są wcięte pod nazwą rolki, a ilości stoją w nawiasie zaraz po nazwie, wyszarzone —
oko leci po nazwach, gramatura doczytuje się dopiero, gdy jest potrzebna.
Kolejność rolek i składników jest ta sama co w aplikacji, czyli ta z arkusza: **składniki
idą w kolejności nakładania na matę**. W stopce data wygenerowania i numer strony.

PDF powstaje **po stronie serwera**. Aplikacja wysyła gotowy HTML do `POST /api/pdf`,
serwer przepakowuje go w multipart i podaje Gotenbergowi, a wraca plik. Gotenberg na
Mikrusie chodzi w Dockerze, więc domyślny adres to `http://172.17.0.1:3001` (mostek
docker0); zmienia go zmienna `SUSHI_GOTENBERG`, a pusta wartość wyłącza wydruki.
Serwer próbuje adresu Gotenberga 7/8, a przy 404 sięga po starszy z szóstki.

Poza trybem serwerowym — gdy plik jest otwarty z dysku — nie ma czym generować PDF-u,
więc otwiera się **okno drukowania**: „Zapisz jako PDF" daje ten sam dokument, tylko
rękami. To samo dzieje się, gdy serwer odpowie błędem: aplikacja pyta i proponuje wydruk
z przeglądarki, zamiast zostawić użytkownika z komunikatem.

Wydruk jest dostępny dla wszystkich ról, łącznie z `viewer` — to czytanie, nie edycja.

### Automaty vendingowe

**Kod automatu może zawierać spację.** „KAU GAL" i „KAU NOR" czyta się lepiej niż „KAU"
i „KA2" — przy dwóch automatach tej samej sieci numer nie mówi nic o lokalizacji. Pole mieści
12 znaków, a zapis czyści wielokrotne spacje i te na brzegach, żeby „ZAB " i „ZAB" nie były
dwoma kodami, których nikt nie odróżni wzrokiem.

Kod generowany automatycznie z nazwy bierze **trzy pierwsze litery, a przy kolizji dokłada
drugi człon**: „Kaufland, Galicyjska" przy zajętym KAU daje KAU GAL, a nie KAU2.

Zakładka **Automaty** trzyma sześć maszyn (nazwy i adresy z notosushi.pl) oraz **wspólny
układ szafek**: dwie kolumny po dziesięć, szafki 1–10 i 11–20. Do każdej szafki przypisujesz
zestaw; układ jest jeden dla wszystkich maszyn, więc zmiana działa od razu na całej sieci.

Przy każdej szafce widać cenę brutto, koszt netto i food cost — zawsze w kanale **Vending**,
niezależnie od przełącznika w innych widokach, bo automat sprzedaje tylko tak.

Nad układem są liczby całego załadunku: ile szafek zapełnionych, wartość jednego automatu,
koszt wytworzenia, ważony food cost oraz to samo pomnożone przez liczbę czynnych maszyn.
Niżej tabela „Zestawy w jednym automacie" pokazuje, ile sztuk czego trzeba przygotować.

Każdy automat ma **kod** (ZAB, IMB, PRZ, GAL, JAS, NOR) — krótki i unikalny, po nim rozpozna
się maszynę tam, gdzie nie ma miejsca na nazwę.

**Kod i nazwa nie występują razem.** Tam, gdzie jest miejsce — kafelki automatów w Załadunkach,
Pakowaniu i u Kierowcy — stoi sama nazwa. Tam, gdzie miejsca nie ma — wiersze w kafelkach
zestawów, kolumny tabeli krzyżowej, wydruk pakowania — sam kod. Jedynym miejscem, gdzie widać
oba, jest lista i karta automatu w Edycji, bo tam się je właśnie definiuje. Kod jest wymagany, zapisuje się wielkimi
literami, a duplikat aplikacja odrzuci. Automatom bez kodu dorabia go sama z nazwy.

Lista automatów pokazuje kod, nazwę, adres i notatkę — bez kwot, bo układ szafek jest wspólny
i wartość załadunku wszędzie taka sama; te liczby są raz, nad układem.

Zestawu wstawionego do szafki nie da się usunąć — aplikacja powie, w których szafkach siedzi.

### Załadunki

Załadunek to **nazwany plan obejmujący wszystkie automaty naraz**. Zakładka **Załadunki**
pokazuje kafelek na każdą maszynę, a w nim jej dwadzieścia szafek w dwóch kolumnach.
Klikasz szafkę i przełączasz: **zielona jedzie w trasę, czerwona zostaje** — sam kolor,
bez ptaszków i krzyżyków. Numer szafki jest wytłuszczony po lewej.
Na kafelku szafki jest nazwa zestawu, nie cena — w kuchni i w trasie liczy się to, co pakujesz.

**Plan tygodnia** to siedem kafli nad listą — przy każdym dniu wybierasz z listy, który
załadunek tego dnia jedzie. Przypisanie działa od razu; wybór „brak" zwalnia dzień.

Jeden dzień to jeden załadunek i **nie da się tego złamać**, bo plan jest mapą dzień → załadunek,
a nie listą dni przy każdym załadunku. Przypisanie dnia zabiera go poprzedniemu samo z siebie —
nie ma konfliktu do zgłoszenia ani walidacji do przejścia.

Na liście i kafelkach załadunku widać, w które dni jedzie, z zakresami zwiniętymi do „Pn–Cz, So".
Dni bez przypisania mają przerywaną ramkę i są wypisane pod spodem. Załadunek w archiwum nie
blokuje swoich dni, a usunięty zwalnia je automatycznie.

Szafka bez przypisanego zestawu jest wyszarzona i nieklikalna — najpierw ustaw układ
w zakładce Automaty.

Nowy załadunek startuje z zaznaczonymi wszystkimi szafkami, które mają zestaw. Skróty:
✓ i ✕ przy każdym automacie zaznaczają albo czyszczą całą maszynę, a przyciski na górze
robią to samo dla całej sieci.

Przy każdym automacie widać, ile szafek jedzie i **jaki to procent pełnego załadunku** liczony
wartością — od razu widać, która maszyna jedzie pusta, a która pod korek.

Pod siatką **„Do przygotowania"** — cała rozpiska przeliczona w dół z zaznaczonych szafek:

| Tabela | Co pokazuje |
|---|---|
| Zestawy do zapakowania | ile sztuk którego zestawu |
| Rolki do zwinięcia | kawałki i przeliczenie na całe rolki |
| Półprodukty do zrobienia | ile ryżu, sałatki, zaprawy i ile to partii |
| Składniki do wydania | surowce z lodówki, w opakowaniach i w złotówkach |

Zapotrzebowanie na składniki **uwzględnia odpad z półproduktów** — na 500 g krojonego ogórka
schodzi kilogram surowego. Suma kosztu składników zgadza się co do grosza z kosztem wytworzenia
załadunku policzonym od strony zestawów; to ta sama liczba z dwóch stron i test tego pilnuje.

#### Tydzień dzień po dniu

Pod listą załadunków stoją dwie tabele z kolumną na każdy dzień tygodnia plus Razem:
**Rolki dzień po dniu** i **Zestawy dzień po dniu**. Rolki są **pogrupowane po kategoriach**,
a nagłówek grupy niesie sumę tej kategorii w każdym dniu — widać nie tylko „ile rolek
w tygodniu", ale i „ile Hosomaki w czwartek".

Suma tygodniowa mówi, ile trzeba kupić; rozbicie na dni mówi, kiedy to zrobić, a to dwie
różne decyzje: poniedziałek z dwoma automatami i piątek z sześcioma dają tę samą sumę
tygodniową i zupełnie inny dzień w kuchni. Dlatego tabele siedzą tuż pod planem tygodnia —
zmiana przypisania dnia od razu widać w liczbach.

Zero pokazuje się jako pauza; zero w tabeli to szum, nie informacja. Liczba sztuk zestawów
musi się zgadzać z liczbą szafek w tygodniu, a poniedziałek z rozpiską poniedziałkowego
załadunku — test pilnuje obu. W karcie pojedynczego załadunku tych tabel nie ma: tam liczy
się jeden załadunek, nie tydzień.

### Załadunki (Analizy)

Zakładka **Analizy → Załadunki** przelicza plan tygodnia na pieniądze i na robotę. Tydzień jest
tu jednostką naturalną, bo to on jest zaplanowany: wiadomo, który załadunek jedzie którego
dnia, więc wolumen liczy się wprost, bez zgadywania. **Miesiąc liczymy jako 30 dni**, czyli tydzień × 4,29 —
okrągło i tak samo dla każdego miesiąca, żeby porównywać jabłka z jabłkami.

| Co | Gdzie |
|---|---|
| szafki, wartość brutto, koszt netto, marża i food cost **na automat** | tabela „Automaty", tygodniowo i miesięcznie, z wierszem Razem |
| który dzień co wiezie i za ile | tabela „Tydzień dzień po dniu" |
| które zestawy robią wolumen i jaki mają udział w przychodzie | tabela „Zestawy w tygodniu" |
| który automat ile wozi | dwa wykresy obok siebie: **tygodniowy** i **miesięczny** |

Ile tego fizycznie wyjdzie — rolki i zestawy dzień po dniu — stoi w **Edycji → Załadunki**,
pod listą załadunków, czyli tam, gdzie układa się plan tygodnia.

To wolumen **załadowany**, nie sprzedany — mówi, ile towaru wjeżdża do maszyn, a nie ile
z nich wyjeżdża. Aplikacja pisze to wprost na karcie, żeby nikt nie wziął tej liczby za utarg.
Dzień bez przypisanego załadunku jest zgłaszany, bo zaniża cały rachunek.

Ceny są vendingowe — automat sprzedaje tylko tak. Trzy sumy liczone są niezależnie
(po automatach, po dniach i po zestawach) i test wymaga, żeby dały tę samą liczbę.

### Dwa kanały sprzedaży i VAT

Ta sama rolka sprzedana z automatu i przez aplikację dostawczą ma inną cenę i inną stawkę
VAT. Każda rolka i każdy zestaw ma więc dwa komplety: **Vending** i **Dostawa**, po jednej
cenie brutto i jednej stawce na kanał. Domyślnie 5% i 8% — do zmiany w Ustawieniach.

W listach rolek i zestawów jest przełącznik kanału; tabela i kafelki pokazują ceny tego,
który wybierzesz. Karta szczegółów pokazuje **oba naraz**, obok siebie: stawkę, cenę brutto,
cenę netto, food cost, marżę i sugerowaną cenę.

Zasada jest jedna i pilnuje jej silnik:

- **ceny zakupu są zawsze netto** — tak jak na fakturze, w kolumnie netto
- **ceny sprzedaży są zawsze brutto** — tak jak na paragonie
- **food cost = koszt netto ÷ przychód netto**, gdzie przychód netto = cena brutto ÷ (1 + VAT)

Dlatego ten sam koszt wytworzenia daje inny food cost w każdym kanale: przy 5% zostaje
więcej przychodu netto niż przy 8%, więc food cost jest niższy. Koszt się nie zmienia,
zmienia się to, ile z ceny zostaje dla lokalu.

#### Uśrednianie: zawsze ważone, nigdy arytmetyczne

Gdziekolwiek aplikacja pokazuje food cost **zbioru** pozycji — kafelek na Foodcoście, automat,
załadunek, tydzień — liczy go jako **sumę kosztów ÷ sumę przychodu netto**, nie jako średnią
z food costów poszczególnych pozycji. Średnia arytmetyczna kłamie: tanie hosomaki waży w niej
tyle samo, co Party Mix, choć sprzedaje się za dziesiątą część kwoty.

Kafelek na Foodcoście pokazuje **food cost zestawów**, bo to zestawy schodzą z automatu.
Rolki idą pod spodem drobnym drukiem, jako punkt odniesienia: ich ceny à la carte są
notowane po to, żeby dało się policzyć rabat w zestawie, a nie dlatego, że ktoś kupuje
pojedynczą rolkę z maszyny. Te dwie liczby muszą się różnić i to nie jest błąd — zestaw
niesie 16–39% rabatu wobec sumy cen à la carte plus tackę, pałeczki, sos, imbir, wasabi
i opłatę SUP, czyli koszt bez przychodu.

**Pozycja z niekompletną recepturą nie wchodzi do średniej.** Składnik bez ceny liczy się
w rozbiciu jako 0 zł — to wygodne przy wprowadzaniu danych, ale zaniża koszt, a przez to
i food cost. Taka pozycja zostaje poza średnią, dostaje alert w „Do sprawdzenia", a kafelek
pisze wprost, ile pozycji pominął. Lepiej policzyć mniej niż policzyć źle.

**Przychód netto sumuje się zestaw po zestawie**, każdy ze swoją stawką VAT — bo stawka
siedzi przy zestawie, nie przy załadunku. Dzielenie sumy brutto przez jedną stawkę
z ustawień dawało poprawny wynik tylko dopóty, dopóki wszystkie zestawy miały tę samą.

### Wartości odżywcze i alergeny

Składnik ma tabelę **na 100 g** — energia, tłuszcz, w tym kwasy nasycone, węglowodany,
w tym cukry, białko, sól. Dokładnie te siedem pozycji wymaga rozporządzenie 1169/2011,
więc wynik nadaje się na etykietę bez przepisywania. Do tego 14 alergenów UE
zaznaczanych jednym kliknięciem; rolka i zestaw dziedziczą je automatycznie.

Składniki liczone w sztukach (nori w arkuszach, krewetki, saszetki) potrzebują pola
**waga 1 jednostki** — bez niego nie ma z czego policzyć wartości na 100 g. Opakowania
mają tam 0, żeby tacka nie powiększała masy porcji.

### Odpad w półprodukcie

Każdy składnik receptury półproduktu ma **dwie ilości**: tę, która trafia do produktu,
i odpad. Odpad kosztuje, ale nie wchodzi do wartości odżywczych — bo płacisz za całe kilo
ogórka, a do rolki trafia pół. Przy nazwie, w nawiasie, widać ile surowca schodzi razem.

```
Ogórek krojony                wydajność 500 g
                          ilość   odpad   j.m.     koszt
  Ogórek (1000)             500     500      g   15,00 zł
```

Koszt: 15 zł za kilogram rozłożone na 500 g produktu, czyli 0,03 zł/g zamiast 0,015.
Wartości odżywcze: z 500 g miąższu na 500 g produktu, czyli jak dla świeżego ogórka.
Bez rozdzielenia tych dwóch liczb aplikacja policzyłaby dwa razy więcej kalorii,
niż jest naprawdę.

### Lista albo kafelki

Cztery listy — składniki, półprodukty, rolki, zestawy — działają identycznie: przełącznik
**☰ Lista / ▦ Kafelki**, filtr archiwum, ta sama siatka kafelków i ten sam panel podglądu.
W trybie listy podgląd jest po prawej, w trybie kafelków pod siatką. Klikasz wiersz albo
kafelek, podgląd się otwiera.

Ustawienie siedzi w localStorage przeglądarki (klucz `sp_widok`), osobno dla każdej listy,
a nie w danych lokalu — każdy pracuje tak, jak mu wygodnie, i nikomu nie przestawia widoku.

**W tabeli nie ma żadnych przycisków.** Tabela służy do porównywania liczb w kolumnach —
kolumna „Akcje" z trzema przyciskami w każdym wierszu zabierała miejsce i prosiła się
o pomyłkę. Edycja jest o jedno kliknięcie dalej: klikasz wiersz, otwiera się podgląd,
w nim jest **Edytuj**. Kafelek ma ten sam przycisk u dołu.

**Archiwum i usuwanie zniknęły z list całkowicie** — obie operacje są teraz na końcu
edycji (patrz niżej). Wcześniej „✕" stało w każdym wierszu obok „Edytuj"; jedno z tych
kliknięć jest nieodwracalne, drugie robi się dziesięć razy dziennie.

Co jest w podglądzie:

#### Wszystkie cztery podglądy mają jeden szkielet

Składnik, półprodukt, rolka i zestaw to cztery różne byty, ale patrzy się na nie tak samo:
co to jest, z czego się składa, ile kosztuje, gdzie się tego używa. Dlatego wszystkie cztery
podglądy składa **jedna funkcja** (`podgladKarta`), a sekcje idą zawsze w tej samej kolejności:

| # | Sekcja | Składnik | Półprodukt | Rolka | Zestaw |
|---|---|---|---|---|---|
| 1 | Skład | — | ✓ | ✓ | ✓ |
| 2 | Koszt i cena | ✓ | ✓ | ✓ | ✓ |
| 3 | Ceny i food cost w kanałach | — | — | ✓ | ✓ |
| 4 | Rozbicie kosztu | — | ✓ | ✓ | ✓ |
| 5 | Wartości odżywcze | ✓ | ✓ | ✓ | ✓ |
| 6 | Historia ceny | ✓ | — | — | — |
| 7 | Gdzie używany | ✓ | ✓ | ✓ | ✓ |

**Sekcja, która dla danego bytu nie ma sensu, po prostu wypada — reszta zostaje na swoim
miejscu.** Składnik nie ma składu, bo jest atomem; półprodukt nie ma ceny sprzedaży, bo się
go nie sprzedaje; tylko składnik ma historię ceny, bo tylko on ma cenę zakupu. Test sprawdza
to wprost: lista sekcji każdego podglądu musi być **podciągiem** kanonicznej siódemki —
dopisanie sekcji w złej kolejności albo tylko po jednej stronie wywala testy.

Nad sekcjami stoi zawsze to samo: nazwa, przycisk **Edytuj**, podtytuł i **dwa kafelki**
z najważniejszą liczbą. Dla rolki i zestawu to food cost i marża, dla półproduktu koszt
jednostkowy i za kilogram, dla składnika cena jednostkowa i liczba receptur.

„Gdzie używany" przy zestawie nie pokazuje receptur — zestaw nie wchodzi do żadnej — tylko
**numery szafek** w automacie i ile to sztuk na całą sieć.

#### Zwijanie sekcji

Każdy nagłówek sekcji jest przyciskiem — klik zwija, klik rozwija. Stan siedzi
w **localStorage przeglądarki** (klucz `sp_sekcje`), nie w danych lokalu: kucharz może mieć
zwinięte wartości odżywcze, właściciel rozwinięte, i nikt nikomu nic nie przestawia.

Kluczem jest nazwa sekcji, więc **„Wartości odżywcze" zwinięte przy składniku zostają zwinięte
także przy rolce**. To celowe: jeśli ktoś na tę sekcję nie patrzy, to nie patrzy na nią nigdzie.
Domyślnie wszystko jest rozwinięte.

#### Archiwum i usuwanie na końcu edycji

Stopka okna edycji to miejsce na **Zapisz** i **Anuluj** — nic więcej. Przycisk, który kasuje
pozycję bezpowrotnie, nie ma prawa stać obok przycisku klikanego dziesięć razy dziennie.
Obie ryzykowne operacje siedzą więc **na samym końcu bloku edycji**, za wszystkimi polami,
oddzielone kreską, opisane pełnym zdaniem: co robi archiwum, czego nie da się cofnąć.
Przyciski mówią „Przenieś do archiwum" i „Usuń bezpowrotnie", a nie „Archiwum" i „✕".

Nowa pozycja nie dostaje tej sekcji w ogóle — nie ma czego archiwizować ani kasować.

#### Dodawanie: najpierw wiersz, potem wybór

**„+ Dodaj składnik" wstawia pusty wiersz**, a składnik i ilość wpisuje się w nim.
Wcześniej pod listą stało osobne pole wyboru z przyciskiem obok — bardzo łatwo było wybrać
w nim pozycję, przejść do ilości i nie kliknąć „Dodaj", a potem szukać, czemu koszt się
nie zgadza. Teraz wiersz istnieje od razu, jest obrysowany kreską dopóki jest pusty,
a kursor stoi w polu wyboru.

Przy okazji **każdy istniejący wiersz też ma listę wyboru** — pomyłkę poprawia się na
miejscu, bez kasowania wiersza i wpisywania ilości od nowa. Dotyczy to wszystkich czterech
miejsc: receptury rolki, receptury półproduktu, rolek w zestawie i dodatków.

#### Rolka i zestaw wyglądają tak samo

Podgląd rolki i podgląd zestawu składa **jedna funkcja** (`podgladPozycji`), więc zakres
i kolejność informacji nie mogą się rozjechać. Sekcje idą zawsze tak: nazwa i **Edytuj**,
podtytuł (ile kawałków, ile pozycji, kanał, VAT), zdjęcie, dwa kafelki **Food cost** i
**Marża netto**, **Skład**, **Koszt i cena**, **Ceny i food cost w kanałach**, **Rozbicie
kosztu**, **Wartości odżywcze**. Test porównuje oba podglądy nagłówek po nagłówku i wiersz
po wierszu — nowa sekcja dodana po jednej stronie od razu wywala testy.

Różnice są tylko tam, gdzie są nieuniknione: rolka pokazuje „w tym półprodukty", zestaw
„w tym dodatki", i tylko zestaw ma **Sumę cen à la carte** oraz **Rabat zestawu** — rolka
nie jest zestawem, więc nie ma się do czego porównać.

Skład rolki idzie **w kolejności nakładania na matę**, nie od najdroższego składnika —
ta sama kolejność co na kartce z recepturą. Od kosztu jest wykres niżej.

### Listy rozwijane z wyszukiwaniem

Każda lista wyboru — składnik do receptury, rolka do zestawu, dodatek, zamiennik, składnik
w symulacji, filtr kategorii — jest **posortowana po polsku** (Ł idzie po L) i filtruje się
po **dowolnym fragmencie** wpisanego tekstu, nie tylko po pierwszej literze. Polskie ogonki
są ignorowane, więc „losos" znajduje „Łosoś", a „gotowany" znajduje „Ryż gotowany".

Strzałki i Enter działają jak w zwykłym selekcie, Escape zamyka samą listę bez zamykania
okna pod spodem.

### Sortowanie

Każda tabela — składniki, rolki, zestawy, historia cen, konta — sortuje się po kliknięciu
w nagłówek kolumny. Drugie kliknięcie odwraca kolejność. Liczby sortują się jak liczby
(„6,48 zł" to sześć i pół, nie tekst zaczynający się od szóstki), tekst po polsku
(Ł idzie po L, nie po Z), a puste pola i myślniki lądują zawsze na końcu — w obie strony,
żeby sortowanie „od najdroższego" nie zaczynało się od pozycji bez ceny.

Wybór trzyma się przy przechodzeniu między zakładkami i po każdej edycji.

### Archiwum

Składniki, półprodukty, rolki i zestawy można archiwizować zamiast usuwać. Każdy z tych
widoków ma przełącznik **Aktywne / Archiwum / Wszystko**.

Archiwizacja **nie zmienia kosztów** — schowany składnik nadal liczy się w recepturach,
w których występuje. Inaczej pół menu po cichu by „staniało". Zamiast tego na pulpicie
pojawia się ostrzeżenie „w archiwum, ale wciąż używane" z listą miejsc.

---

## Struktura

Wszystkie pliki leżą płasko, bez podkatalogów — dzięki temu da się wrzucić repozytorium
na GitHuba przez przeglądarkę, bez instalowania gita na własnym komputerze.

```
server.py                serwer (stdlib Pythona 3.8+)
sushi-planner.html       cała aplikacja w jednym pliku
install.sh               instalacja jednym poleceniem
update.sh                aktualizacja z wycofaniem przy awarii
VERSION                  numer wersji pokazywany w aplikacji
INSTRUKCJA-mikrus.md     wdrożenie krok po kroku
audyt-arkusza.md         co było nie tak w arkuszu Excela
test-*.py, test-*.sh     testy (patrz niżej)
```

Kod mieszka w `/opt/sushi-planner`, dane w `/var/lib/sushi-planner`.
Rozdzielenie jest celowe: aktualizacja nadpisuje pierwsze, nigdy drugie.

### `render()` nie wchodzi w samego siebie

Cały interfejs przerysowuje się jednym `render()`, który podmienia `innerHTML` i dopiero
potem podpina uchwyty zdarzeń. Ma to jedną pułapkę, kosztowną i niełatwą do zauważenia.

Pole tekstowe z uchwytem `change`, które woła `render()`: podmiana `innerHTML` wyrzuca
z DOM pole trzymające ognisko, a przeglądarka wystawia wtedy **drugie** `change` — jeszcze
na odpiętym węźle, ze starym uchwytem, który znowu woła `render()`. Zagnieżdżony przebieg
rysuje ekran i podpina uchwyty, po czym przerwana zewnętrzna podmiana nadpisuje ten DOM
swoim, a jej kolejka POST jest już pusta. Wychodzi ekran **bez żadnych uchwytów**: pola się
wpisują, tylko nic nie zapisują, i nic nie sygnalizuje błędu.

Dlatego `render()` jest tylko strażą: wywołanie w trakcie innego przebiegu nie rysuje —
zgłasza powtórkę, którą pętla wykonuje po zamknięciu bieżącego. Ostatni przebieg zawsze
podpina uchwyty do DOM-u, który naprawdę został na ekranie. Właściwe rysowanie siedzi
w `rysuj()`. Test na to jest w sekcji **GRAFIK: PORZĄDKI I ODPORNOŚĆ**.

---

## Testy

```bash
pip install playwright && playwright install chromium
python3 test-offline.py        # 1031 asercji — silnik, widoki, wydruki, grafik, język wizualny  (~70 s)
python3 test-serwer.py         # 150 asercji — logowanie, role, uprawnienia, konflikty, PDF, zapisy  (~45 s)
bash    test-aktualizacji.sh   #  28 asercji — pełny cykl aktualizacji i wycofania
```

### Poprawianie jednej sekcji

```bash
python3 test-offline.py --do "LISTY Z WYSZUKIWANIEM"   # ~6 s zamiast ~38 s
```

`--do` kończy przebieg zaraz po wskazanej sekcji. Sekcji **nie da się uruchomić od środka** —
kolejne korzystają ze stanu, który zostawiły poprzednie (dopisany składnik, zmieniona cena,
zarchiwizowana pozycja), więc start jest zawsze od początku. Przy poprawianiu czegoś w połowie
suite'u to i tak różnica między sześcioma sekundami a czterdziestoma.

### Dlaczego jest szybko

Sprawdzian trwał **146 s, z czego 93 s spał** — 294 wywołania `wait_for_timeout` po 300 ms
„z zapasem". Zapas był niepotrzebny: `render()` w aplikacji jest **synchroniczny**, więc zanim
`pg.click` wróci, DOM jest już przebudowany. Zostaje przeliczenie układu, na co wystarczą dwie
klatki (~30 ms). Pomocnik `odswiez(pg)` robi dokładnie to i zastąpił 285 sztywnych pauz —
przebieg spadł do **38 s bez zmiany ani jednej asercji**.

Jawne pauzy zostały tam, gdzie naprawdę coś dzieje się w tle i żadna klatka tego nie przyspieszy:
wczytanie i przeskalowanie zdjęcia, zamknięcie listy rozwijanej po utracie fokusu (120 ms
w aplikacji), wjazd menu na telefonie (animacja CSS 180 ms), zapis na serwer i restart.
Stabilność sprawdzona trzema przebiegami z rzędu: 38 s, 44 s, 38 s, za każdym razem komplet.

`test-aktualizacji.sh` zakłada lokalne repozytorium git, instaluje z niego aplikację,
wydaje nową wersję, aktualizuje, a potem celowo publikuje wersję z błędem składni
i wersję, która nie wstaje — i sprawdza, czy jedna i druga zostaną wycofane bez utraty danych.

---

## Bezpieczeństwo

- Hasła: scrypt z solą. Plik `users.json` ma prawa `600`.
- Sesje: ciasteczko podpisane HMAC-em, `HttpOnly`, `SameSite=Lax`, ważne 30 dni.
  Rola czytana z pliku przy każdym żądaniu, więc jej odebranie działa natychmiast.
- Zapis danych: plik tymczasowy + `rename`, czyli operacja atomowa.
- Konflikty: każdy zapis ma numer wersji; przy równoczesnej edycji druga osoba dostaje
  pytanie zamiast po cichu nadpisać cudzą pracę.
- Serwer nie udostępnia plików z dysku poza samą aplikacją.
- Usługa systemd chodzi z `NoNewPrivileges`, `ProtectSystem=full`, `ProtectHome`
  i zapisem ograniczonym do katalogu danych.
