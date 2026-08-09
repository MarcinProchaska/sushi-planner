#!/bin/bash
# ---------------------------------------------------------------------------
# Sushi Planner — publikacja zmian na GitHuba (macOS).
#
# To samo, co robi publikuj.bat na Windowsie: porównuje pliki w tym folderze
# z tym, co leży na GitHubie, i wysyła tylko te, które się różnią. Niczego nie
# kasuje. Porównanie idzie po git-owym SHA blobu, więc identyczny plik nie
# generuje pustego commita.
#
# Pierwsze uruchomienie:
#     chmod +x publikuj.command
# potem wystarczy dwuklik w Finderze.
#
# Zero zależności poza tym, co macOS ma z pudełka: bash, curl, shasum, base64.
# Żadnego jq, żadnego Pythona, żadnego lokalnego klona repozytorium.
# ---------------------------------------------------------------------------
set -u

OWNER='MarcinProchaska'
REPO='sushi-planner'
BRANCH='main'
TOKEN_FILE="$HOME/.sushi-github-token"
FOLDER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Czego nie wysyłamy: same skrypty publikujące, token i śmieci systemowe.
# Kropkowce lecą hurtem — na Macu to .DS_Store, na OneDrive rozmaite ślady synchronizacji.
pomijamy() {
  case "$1" in
    publikuj.command|publikuj.ps1|publikuj.bat|.*|Icon*|desktop.ini|*.download|~\$*) return 0 ;;
  esac
  return 1
}

C_OK=$'\033[32m'; C_ERR=$'\033[31m'; C_WARN=$'\033[33m'
C_TIT=$'\033[36m'; C_DIM=$'\033[90m'; C_0=$'\033[0m'

echo
echo "${C_TIT}  Sushi Planner - publikacja na GitHuba${C_0}"
echo '  ------------------------------------------------------------'
echo "${C_DIM}  Folder: $FOLDER${C_0}"

# --- token -----------------------------------------------------------------
if [ ! -f "$TOKEN_FILE" ]; then
  echo "${C_WARN}  Nie znalazłem zapisanego tokenu GitHuba.${C_0}"
  echo
  echo '  Zrób to raz:'
  echo '   1. Wejdź na https://github.com/settings/personal-access-tokens/new'
  echo '   2. Token name: sushi-planner'
  echo '   3. Expiration: wybierz np. 1 rok'
  echo '   4. Repository access: Only select repositories -> sushi-planner'
  echo '   5. Permissions -> Repository permissions -> Contents: Read and write'
  echo '   6. Generate token i skopiuj go (zaczyna się od github_pat_)'
  echo
  # -s, czyli bez echa: wklejony token nie pojawia się na ekranie i nie zostaje
  # w oknie terminala, na zrzucie ekranu ani w nagraniu. Terminal i tak nie zapisuje
  # tego, czego nie wypisał.
  printf '  Wklej token tutaj (nie pokaże się na ekranie): '
  read -rs WKLEJONY
  echo
  WKLEJONY="$(printf '%s' "$WKLEJONY" | tr -d '[:space:]')"
  if [ -z "$WKLEJONY" ]; then
    echo "${C_ERR}  Pusty token, przerywam.${C_0}"; exit 1
  fi
  # Najpierw prawa, potem treść — inaczej token przez moment leży czytelny dla wszystkich.
  : > "$TOKEN_FILE"; chmod 600 "$TOKEN_FILE"
  printf '%s' "$WKLEJONY" > "$TOKEN_FILE"
  unset WKLEJONY
  echo "${C_OK}  Token zapisany w $TOKEN_FILE${C_0}"
  echo
fi
TOKEN="$(tr -d '[:space:]' < "$TOKEN_FILE")"

API="https://api.github.com/repos/$OWNER/$REPO"
gh() { curl -sS -m 60 -H "Authorization: Bearer $TOKEN" -H 'Accept: application/vnd.github+json' \
            -H 'X-GitHub-Api-Version: 2022-11-28' -H 'User-Agent: sushi-planner-publish' "$@"; }

koniec() {
  echo
  if [ "${BLEDY:-0}" -gt 0 ]; then
    printf '  Coś poszło nie tak - Enter zamyka'; read -r _
  elif [ "${WYSLANE:-0}" -eq 0 ]; then
    echo "${C_DIM}  Nie było czego wysyłać. Okno zamknie się za 10 sekund.${C_0}"; sleep 10
  else
    echo "${C_DIM}  Gotowe. Okno zamknie się samo za 4 sekundy.${C_0}"; sleep 4
  fi
}

# --- czy token ma prawo PISAĆ ------------------------------------------------
# Samo „czy odczyt działa" nic tu nie mówi: repozytorium jest publiczne, więc każdy
# ważny token je przeczyta — także taki, który nie ma do niego żadnych uprawnień.
# Dlatego pytamy o `permissions.push`, czyli o to, co GitHub myśli o TYM tokenie
# przy TYM repozytorium.
ODP="$(gh -w '\n%{http_code}' "$API")"
KOD="$(printf '%s' "$ODP" | tail -1)"
if [ "$KOD" != '200' ]; then
  echo "${C_ERR}  Token nie działa albo nie widzi repozytorium (HTTP $KOD).${C_0}"
  echo "${C_ERR}  Skasuj plik $TOKEN_FILE i uruchom skrypt ponownie, żeby podać nowy:${C_0}"
  echo "     rm \"$TOKEN_FILE\""
  BLEDY=1; koniec; exit 1
fi
PISZE="$(printf '%s' "$ODP" | tr -d '\n\r' \
  | sed -n 's/.*"permissions":{[^}]*"push":\([a-z]*\).*/\1/p')"
if [ "$PISZE" != 'true' ]; then
  echo
  echo "${C_ERR}  Token czyta to repozytorium, ale nie ma prawa do niego pisać.${C_0}"
  echo
  echo '  Najczęstsza przyczyna: przy zakładaniu tokenu pole Repository access'
  echo '  zostało na domyślnym "Public Repositories (read-only)". To daje odczyt'
  echo '  wszystkich publicznych repo i zapis do żadnego - a nasze jest publiczne,'
  echo '  więc odczyt działa i wygląda, jakby token był dobry.'
  echo
  echo '  Popraw obie rzeczy naraz:'
  echo '   1. https://github.com/settings/tokens?type=beta -> Twój token -> Edit'
  echo '   2. Repository access: Only select repositories -> sushi-planner'
  echo '   3. Permissions -> Repository permissions -> Contents: Read and write'
  echo '   4. Update token'
  echo
  echo '  Potem uruchom skrypt jeszcze raz - zapisanego tokenu nie musisz kasować.'
  BLEDY=1; koniec; exit 1
fi

# --- co leży na GitHubie -----------------------------------------------------
# Listing to płaska tablica obiektów, w których `sha` stoi po `name`. Zamiast jq (macOS
# go nie ma) zwijamy odpowiedź do jednej linii, tniemy po obiektach i wyciągamy pary
# jednym przebiegiem. Zwinięcie jest po to, żeby zadziałało także wtedy, gdyby GitHub
# kiedyś zaczął odpowiadać sformatowanym JSON-em.
ZDALNE="$(gh "$API/contents?ref=$BRANCH" \
  | tr -d '\n\r' | tr '}' '\n' \
  | sed -n 's/.*"name":[[:space:]]*"\([^"]*\)"[^}]*"sha":[[:space:]]*"\([^"]*\)".*/\1 \2/p')"
if [ -z "$ZDALNE" ]; then
  echo "${C_WARN}  Repozytorium wygląda na puste - wyślę wszystko.${C_0}"
fi
zdalne_sha() { printf '%s\n' "$ZDALNE" | awk -v n="$1" '$1==n {print $2; exit}'; }

# --- porównanie i wysyłka ----------------------------------------------------
WYSLANE=0; BEZ_ZMIAN=0; BLEDY=0
ZNALEZIONE=0; ODMOWA=0

for SCIEZKA in "$FOLDER"/*; do
  [ -f "$SCIEZKA" ] || continue
  NAZWA="$(basename "$SCIEZKA")"
  pomijamy "$NAZWA" && continue
  ZNALEZIONE=$((ZNALEZIONE + 1))

  # git-owy SHA blobu: sha1("blob <długość>\0" + zawartość) — dokładnie to, co
  # GitHub oddaje w polu `sha`, więc porównanie jest jeden do jednego.
  ROZMIAR="$(stat -f%z "$SCIEZKA")"
  LOKALNE_SHA="$( { printf 'blob %s\0' "$ROZMIAR"; cat "$SCIEZKA"; } | shasum -a 1 | cut -d' ' -f1)"
  ZDALNE_SHA="$(zdalne_sha "$NAZWA")"

  if [ -n "$ZDALNE_SHA" ] && [ "$ZDALNE_SHA" = "$LOKALNE_SHA" ]; then
    printf '  bez zmian   %s\n' "$NAZWA"
    BEZ_ZMIAN=$((BEZ_ZMIAN + 1))
    continue
  fi

  TRESC="$(base64 < "$SCIEZKA" | tr -d '\n')"
  CIALO="$(mktemp)"
  {
    printf '{"message":"Aktualizacja %s","branch":"%s"' "$NAZWA" "$BRANCH"
    [ -n "$ZDALNE_SHA" ] && printf ',"sha":"%s"' "$ZDALNE_SHA"
    printf ',"content":"%s"}' "$TRESC"
  } > "$CIALO"

  # Treść odpowiedzi zostaje: sam numer HTTP nic nie tłumaczy, a GitHub pisze wprost,
  # co mu się nie podoba. Numer doklejamy w ostatniej linii.
  ODP="$(gh -X PUT -H 'Content-Type: application/json' \
           --data-binary "@$CIALO" -w '\n%{http_code}' \
           "$API/contents/$NAZWA")"
  rm -f "$CIALO"
  KOD="$(printf '%s' "$ODP" | tail -1)"

  if [ "$KOD" = '200' ] || [ "$KOD" = '201' ]; then
    printf '%s  WYSLANO     %s%s\n' "$C_OK" "$NAZWA" "$C_0"
    WYSLANE=$((WYSLANE + 1))
  else
    KOMUNIKAT="$(printf '%s' "$ODP" | tr -d '\n\r' \
      | sed -n 's/.*"message":[[:space:]]*"\([^"]*\)".*/\1/p')"
    printf '%s  BLAD        %s - HTTP %s%s\n' "$C_ERR" "$NAZWA" "$KOD" "$C_0"
    [ -n "$KOMUNIKAT" ] && printf '%s              %s%s\n' "$C_DIM" "$KOMUNIKAT" "$C_0"
    [ "$KOD" = '403' ] && ODMOWA=1
    BLEDY=$((BLEDY + 1))
  fi
done

if [ "$ZNALEZIONE" -eq 0 ]; then
  echo "${C_ERR}  Brak plików do wysłania.${C_0}"
  BLEDY=1; koniec; exit 1
fi

echo '  ------------------------------------------------------------'
if [ "$WYSLANE" -gt 0 ]; then
  echo "${C_OK}  Wysłano $WYSLANE plik(ów), bez zmian: $BEZ_ZMIAN.${C_0}"
  echo
  echo '  Serwer zaciągnie to sam dziś w nocy (ok. 4:30).'
  echo '  Żeby od razu, zaloguj się i wpisz:'
  echo "${C_TIT}     ssh root@srv103.mikr.us -p 10103${C_0}"
  echo "${C_TIT}     sushi-update${C_0}"
elif [ "$BLEDY" -gt 0 ]; then
  echo "${C_ERR}  Nie udało się wysłać $BLEDY plik(ów).${C_0}"
  # Odczyt zadziałał (sprawdziliśmy go na starcie), a zapis nie — to zawsze znaczy
  # to samo: token ma Contents ustawione na Read-only zamiast Read and write.
  if [ "$ODMOWA" -gt 0 ]; then
    echo
    echo "${C_WARN}  HTTP 403 przy zapisie, choć odczyt zadziałał. Token ma prawo czytać,${C_0}"
    echo "${C_WARN}  ale nie pisać - w jego uprawnieniach Contents stoi na Read-only.${C_0}"
    echo
    echo '  Popraw to tak:'
    echo '   1. https://github.com/settings/tokens?type=beta -> Twój token -> Edit'
    echo '   2. Permissions -> Repository permissions -> Contents: Read and write'
    echo '   3. Update token'
    echo '  Nowego tokenu nie musisz zakładać - wystarczy zmienić uprawnienie.'
    echo '  Gdybyś jednak zakładał nowy, skasuj najpierw zapisany:'
    echo "     rm \"$TOKEN_FILE\""
  fi
else
  echo '  Nic się nie zmieniło - GitHub ma już aktualne pliki.'
fi

koniec
