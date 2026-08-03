# Sushi Planner

Kalkulator food costu i budowania menu dla lokalu sushi. Składniki z cenami, półprodukty,
receptury rolek, zestawy z policzonym opakowaniem, historia cen i symulacja podwyżek.

Jeden plik HTML plus serwer w czystym Pythonie. **Zero zależności zewnętrznych** — nie ma
`pip install`, nie ma Dockera, nie ma bazy danych do utrzymywania. Zużycie pamięci ~25 MB.

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

### Role

| Rola | Uprawnienia |
|---|---|
| `owner` | wszystko, w tym zakładka **Użytkownicy** do zarządzania kontami |
| `chef` | pełna edycja składników, receptur i zestawów |
| `viewer` | tylko podgląd receptur i gramatur — dobre na tablet w kuchni |

Konta zakłada się w aplikacji (Użytkownicy) albo z konsoli poleceniem `sushi adduser`.

### Zestaw = rolki + dodatki

Zestaw ma dwie sekcje. **Rolki** — co i ile kawałków. **Dodatki** — wszystko pozostałe:
tacka, pałeczki, sos w saszetce, imbir, wasabi, opłata SUP, serwetki. Jedna lista, wybierasz
z niej dowolny składnik i podajesz ilość.

Wcześniej tacka, pałeczki i sos miały osobne pole, a składnik trzeba było najpierw oznaczyć
„rolą w opakowaniu". To znikło — okazało się komplikacją bez pokrycia w tym, jak się z tego
korzysta. Stare zestawy migrują się same przy pierwszym wczytaniu: zawartość pola `pack`
ląduje w dodatkach, a gdy ten sam składnik był w obu miejscach, ilości się sumują.

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
python3 test-offline.py        # 72 asercje — silnik obliczeń, archiwum, zdjęcia, eksport
python3 test-serwer.py         # 64 asercje — logowanie, role, konta, konflikty, restart
bash    test-aktualizacji.sh   # 28 asercji — pełny cykl aktualizacji i wycofania
```

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
