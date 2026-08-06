# Sushi Planner

Kalkulator food costu i budowania menu dla lokalu sushi. Składniki z cenami, półprodukty,
receptury rolek, zestawy z policzonym opakowaniem, historia cen i symulacja podwyżek.

Jeden plik HTML plus serwer w czystym Pythonie. **Zero zależności zewnętrznych** — nie ma
`pip install`, nie ma Dockera, nie ma bazy danych do utrzymywania. Zużycie pamięci ~25 MB.

---

## Identyfikacja wizualna

Aplikacja nosi identyfikację **Noto Sushi**: czerwień **`#BD172F`**, czerń znaku **`#1D1D1B`**
i krój **Montserrat** — wszystko wzięte wprost z firmowych plików logo i ze strony notosushi.pl.

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

Konta zakłada się w aplikacji (Użytkownicy) albo z konsoli poleceniem `sushi adduser`.

### Menu — cztery grupy

Menu boczne dzieli się na cztery grupy, według tego **kiedy** się z czegoś korzysta:

| Grupa | Zakładki | Kiedy |
|---|---|---|
| **Pulpit** | Pulpit · Przygotowanie · Rolki · Zestawy · Pakowanie · Kierowca · Kontrola zasobów | codziennie, w kuchni i w trasie |
| **Edycja** | Załadunki · Automaty · Zestawy · Rolki · Półprodukty · Składniki | gdy coś się zmienia w menu albo w cenach |
| **Analizy** | Foodcost · Załadunki · Historia cen · Symulacja | raz na jakiś czas, przy liczeniu |
| **Narzędzia** | Użytkownicy · Ustawienia · Aktualizacja · Wyloguj | rzadko |

**Edycja**, **Analizy** i **Narzędzia** zwijają się kliknięciem w nagłówek grupy — Pulpit
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

Wszystkie sześć ma **wspólną główkę**: sygnet, nadtytuł „Noto Sushi", nazwa dokumentu i
czerwona kreska pod spodem. Kartka z kuchni ma wyglądać jak dokument firmowy, a nie jak wydruk
z przeglądarki. **Dane zostają czarne** — czerwień jest tylko w kresce, w znaku i w numerach
kart, więc czarno-biała drukarka w kuchni nie gubi niczego, co się liczy.

W tytule stoi **nazwa załadunku**, nie data — kartki nie drukuje się codziennie, tylko wtedy,
gdy zmienia się załadunek, i wisi tak długo, jak długo ten załadunek obowiązuje. Te same cztery
wydruki można wywołać wprost z **karty załadunku** w Edycji, bez chodzenia po dniach.

Kafelki Pakowania mają ramki i **równą wysokość w obrębie sekcji** — brakujące wiersze
dopychane są pustymi, a na nazwę zarezerwowane są dwie linie, żeby dłuższa nazwa automatu
nie rozjeżdżała rzędu. Równe prostokąty porównuje się wzrokiem, nierówne trzeba czytać.

#### Liczby stoją w kolumnie

Wiersz to **nazwa po lewej, szare kropki, liczba w swojej kolumnie, jednostka w następnej**.
Kropki są jedynym elementem, który może się zwężać — reszta ma stałą szerokość, więc cyfry
i przecinki stoją jedne pod drugimi w całej karcie. `tabular-nums` pilnuje, żeby „110" i „0,50"
miały tę samą szerokość znaku.

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

---

## Testy

```bash
pip install playwright && playwright install chromium
python3 test-offline.py        # 696 asercji — silnik, widoki, wydruki, identyfikacja  (~38 s)
python3 test-serwer.py         #  80 asercji — logowanie, role, konta, konflikty, PDF  (~32 s)
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
