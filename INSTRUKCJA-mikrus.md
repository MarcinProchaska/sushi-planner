# Sushi Planner na mikr.us — instrukcja

Twój serwer: **Mikrus 3.5** (1 vCPU, 4 GB RAM). Aplikacja zużyje ok. 25 MB, więc zostaje Ci
praktycznie cała maszyna.

Instalujesz raz, jednym poleceniem. Potem aktualizacje instalują się same, a Ty tylko
robisz `git push` u siebie.

---

## Krok 0 — wrzuć projekt na GitHuba

Robisz to raz, na swoim komputerze, w rozpakowanym katalogu z plikami:

```bash
git init -b main
git add -A
git commit -m "Sushi Planner"
```

Załóż puste repozytorium na [github.com/new](https://github.com/new) — nazwa `sushi-planner`.
Może być **prywatne**, ale wtedy serwer musi mieć do niego dostęp (patrz „Repozytorium prywatne"
na końcu). Na start najprościej: publiczne, bo w kodzie nie ma żadnych haseł ani danych.

```bash
git remote add origin https://github.com/TWOJ-LOGIN/sushi-planner.git
git push -u origin main
```

---

## Krok 1 — dwie liczby z panelu Mikrusa

| Co | Gdzie | Przykład |
|---|---|---|
| **numer serwera** | u góry panelu | `1234` |
| **port** | zakładka „Porty" | `301234` |

Każdy Mikrus dostaje trzy porty: `10000 + numer` (zajęty przez SSH), `20000 + numer`
i `30000 + numer`. Używamy tego trzeciego. W panelu dobierzesz jeszcze 7 za darmo.

W dalszej części zamiast `NUMER` wpisuj numer serwera, zamiast `PORT` — swój port,
a zamiast `TWOJ-LOGIN` — swoją nazwę na GitHubie.

---

## Krok 2 — instalacja

```bash
ssh root@srvNUMER.mikr.us -p 10NUMER
```

I jedno polecenie:

```bash
curl -sSL https://raw.githubusercontent.com/TWOJ-LOGIN/sushi-planner/main/install.sh \
  | sh -s -- --port PORT --repo https://github.com/TWOJ-LOGIN/sushi-planner.git
```

Instalator sam doinstaluje `git`, `python3` i `curl` jeśli ich brakuje, pobierze kod,
założy usługę systemd, włączy codzienną aktualizację i sprawdzi, czy serwer odpowiada.

## Krok 3 — konta

```bash
sushi adduser twoj@email.pl owner
sushi adduser kuchnia@lokal.pl chef
sushi adduser tablet@lokal.pl viewer
```

| Rola | Co może |
|---|---|
| `owner` | wszystko |
| `chef` | pełna edycja receptur, cen i zestawów |
| `viewer` | tylko podgląd — dobre na tablet w kuchni, nikt przypadkiem nic nie zmieni |

## Krok 4 — wejdź na stronę

```
https://srvNUMER-PORT.wykr.es
```

Na przykład serwer 1234 na porcie 301234 to `https://srv1234-301234.wykr.es`.
Subdomena działa od ręki, bez konfiguracji DNS, i **ma HTTPS z automatycznym certyfikatem**.

Przy pierwszym zalogowaniu dane z Twojego arkusza wgrają się na serwer automatycznie.
Od tej chwili wszyscy pracują na jednej, wspólnej bazie.

---

## Jak wypuszczać zmiany

U siebie na komputerze:

```bash
echo "1.4.0" > VERSION
git commit -am "poprawione ceny opakowań"
git push
```

Serwer zaciągnie to sam następnej nocy. Jeśli nie chcesz czekać:

```bash
ssh root@srvNUMER.mikr.us -p 10NUMER sushi-update
```

Aktualne wersje sprawdzisz w aplikacji w **Ustawieniach → Serwer** — jest tam numer wersji
i skrót commita.

### Co się dzieje, gdy wypuścisz coś zepsutego

Aktualizacja sprawdza składnię, restartuje usługę i czeka, aż serwer odpowie.
Jeśli nie odpowie — **sama wraca do poprzedniej wersji** i restartuje. Zepsuty commit trafia
na czarną listę, żeby nie próbowała go w kółko co dobę.

W praktyce: możesz wypchnąć błąd o 23:00 i rano zastać działającą aplikację na starej wersji
plus wpis w logu. Historia aktualizacji:

```bash
journalctl -u sushi-planner-update
```

---

## Kopie zapasowe

Serwer robi kopię przy każdym zapisie (20 ostatnich) i osobną paczkę przed każdą
aktualizacją (10 ostatnich). Wszystko w `/var/lib/sushi-planner/backup/`.

To chroni przed pomyłką, ale nie przed awarią dysku — warto ściągać kopię do siebie:

```bash
scp -r -P 10NUMER root@srvNUMER.mikr.us:/var/lib/sushi-planner ~/kopia-sushi
```

Przywrócenie starszej wersji danych:

```bash
systemctl stop sushi-planner
cp /var/lib/sushi-planner/backup/data-20260803-141500.json /var/lib/sushi-planner/data.json
systemctl start sushi-planner
```

Niezależnie od tego w aplikacji jest **Ustawienia → Eksport JSON**.

---

## Własna domena

Jeśli chcesz `foodcost.notosushi.pl` zamiast adresu `wykr.es`, użyj **Cytrusa**:

1. W panelu Mikrusa włącz Cytrusa.
2. U rejestratora domeny ustaw rekord **CNAME** dla `foodcost` na `backend.strony.me`.
3. W panelu Cytrusa dodaj domenę, jako cel podaj `http://TWOJE_IP:PORT`.

Certyfikat HTTPS założy się sam.

---

## Repozytorium prywatne

Jeśli wolisz repo prywatne, serwer potrzebuje dostępu. Najprościej przez klucz wdrożeniowy:

```bash
ssh-keygen -t ed25519 -N "" -f /root/.ssh/id_deploy
cat /root/.ssh/id_deploy.pub
```

Wklej ten klucz w GitHubie: repozytorium → Settings → Deploy keys → Add key (bez prawa zapisu).
Potem dopisz do `/root/.ssh/config`:

```
Host github.com
  IdentityFile /root/.ssh/id_deploy
```

I zainstaluj podając adres SSH zamiast HTTPS:

```
--repo git@github.com:TWOJ-LOGIN/sushi-planner.git
```

---

## Gdyby coś nie zadziałało

**Strona się nie otwiera** — `systemctl status sushi-planner`, a potem
`journalctl -u sushi-planner -n 40`. Sprawdź, czy port w usłudze zgadza się z panelem:

```bash
grep ExecStart /etc/systemd/system/sushi-planner.service
```

**Wykr.es nie odpowiada, a IP:PORT działa** — subdomena obsługuje tylko porty z Twojej puli.

**Nie mogę się zalogować** — `sushi users` pokaże listę kont, `sushi passwd mail@x.pl` zresetuje hasło.

**Aktualizacja nie wchodzi** — `sushi-update --check` pokaże, czy coś czeka i czy wersja
nie jest przypadkiem na czarnej liście po wcześniejszej nieudanej próbie.

**Chcę wyłączyć automatyczne aktualizacje** — `systemctl disable --now sushi-planner-update.timer`.

---

Sources:
- [Mikrus — udostępnione porty](https://wiki.mikr.us/udostepnione_porty/)
- [Mikrus — darmowa subdomena dla VPS](https://wiki.mikr.us/darmowa_subdomena_dla_vps/)
- [Mikrus — Cytrus](https://wiki.mikr.us/cytrus/)
