#!/bin/sh
# ---------------------------------------------------------------------------
# Sushi Planner — aktualizacja z GitHuba.
#
# Uruchamiana ręcznie (`sushi-update`) albo przez timer systemd raz na dobę.
#
# Przebieg:
#   1. sprawdza, czy na GitHubie jest coś nowego — jeśli nie, kończy bez zmian
#   2. robi kopię danych
#   3. pobiera nową wersję
#   4. sprawdza poprawność plików i restartuje usługę
#   5. jeśli serwer nie wstaje — WRACA do poprzedniej wersji i restartuje
#
# Dane (/var/lib/sushi-planner) nie są nigdy dotykane.
# ---------------------------------------------------------------------------
set -e

APP_DIR="${SUSHI_APP:-/opt/sushi-planner}"
DATA_DIR="${SUSHI_DATA:-/var/lib/sushi-planner}"
SERVICE="${SUSHI_SERVICE:-sushi-planner}"
SYSTEMD_DIR="${SUSHI_SYSTEMD_DIR:-/etc/systemd/system}"
FAILED_F="$DATA_DIR/ostatnia-nieudana-aktualizacja"
FORCE=no

while [ $# -gt 0 ]; do
  case "$1" in
    --force) FORCE=yes; shift ;;
    --check) CHECK_ONLY=yes; shift ;;
    -h|--help) echo "Użycie: sushi-update [--check] [--force]"; exit 0 ;;
    *) echo "Nieznany argument: $1"; exit 1 ;;
  esac
done

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fail() { log "BŁĄD: $*"; exit 1; }

[ -d "$APP_DIR/.git" ] || fail "$APP_DIR nie jest repozytorium git. Uruchom install.sh."
cd "$APP_DIR"
git config --local --replace-all safe.directory "$APP_DIR" 2>/dev/null || true

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
[ "$BRANCH" = "HEAD" ] && BRANCH=main

# --- 1. czy jest coś nowego ------------------------------------------------
if ! git fetch --quiet origin "$BRANCH" 2>/dev/null; then
  log "Nie udało się połączyć z repozytorium — pomijam (spróbuję następnym razem)."
  exit 0
fi
OLD="$(git rev-parse HEAD)"
NEW="$(git rev-parse "origin/$BRANCH")"

if [ "$OLD" = "$NEW" ] && [ "$FORCE" = "no" ]; then
  log "Bez zmian — masz najnowszą wersję ($(cat VERSION 2>/dev/null || echo '?') ${OLD%${OLD#???????}})."
  exit 0
fi

BLACKLISTED=no
if [ -f "$FAILED_F" ] && [ "$(cat "$FAILED_F")" = "$NEW" ]; then BLACKLISTED=yes; fi

if [ "$CHECK_ONLY" = "yes" ]; then
  log "Dostępna nowa wersja: ${NEW%${NEW#???????}}"
  git --no-pager log --oneline "$OLD..$NEW" 2>/dev/null | head -20 || true
  [ "$BLACKLISTED" = "yes" ] && \
    log "UWAGA: ta wersja już raz nie wstała i została wycofana — nie zainstaluje się sama."
  exit 0
fi

# wersja, która już raz nie wstała — nie próbujemy w kółko co dobę
if [ "$FORCE" = "no" ] && [ "$BLACKLISTED" = "yes" ]; then
  log "Pomijam ${NEW%${NEW#???????}} — ta wersja już raz nie wstała i została wycofana."
  log "Żeby spróbować mimo to: sushi-update --force"
  exit 0
fi

log "Nowa wersja: ${OLD%${OLD#???????}} -> ${NEW%${NEW#???????}}"
git --no-pager log --oneline "$OLD..$NEW" 2>/dev/null | head -20 || true

# --- 2. kopia danych -------------------------------------------------------
if [ -f "$DATA_DIR/data.json" ]; then
  mkdir -p "$DATA_DIR/backup"
  STAMP="$(date '+%Y%m%d-%H%M%S')"
  tar -czf "$DATA_DIR/backup/przed-aktualizacja-$STAMP.tar.gz" \
      -C "$DATA_DIR" data.json users.json 2>/dev/null || true
  log "Kopia danych: przed-aktualizacja-$STAMP.tar.gz"
  # zostaw 10 ostatnich paczek przedaktualizacyjnych
  ls -1t "$DATA_DIR"/backup/przed-aktualizacja-*.tar.gz 2>/dev/null \
    | tail -n +11 | xargs -r rm -f
fi

# --- 3. pobranie nowej wersji ---------------------------------------------
git reset --hard --quiet "$NEW"

# --- 4. sprawdzenie i restart ---------------------------------------------
rollback() {
  log "Wracam do poprzedniej wersji ${OLD%${OLD#???????}}"
  mkdir -p "$DATA_DIR"
  echo "$NEW" > "$FAILED_F"
  git reset --hard --quiet "$OLD"
  systemctl restart "$SERVICE" 2>/dev/null || true
  sleep 3
  log "Aktualizacja wycofana, działa poprzednia wersja. Dane nietknięte."
  exit 1
}

if ! python3 -m py_compile "$APP_DIR/server.py" 2>/dev/null; then
  log "Nowa wersja server.py ma błąd składni."
  rollback
fi
if [ ! -s "$APP_DIR/sushi-planner.html" ]; then
  log "Brakuje pliku sushi-planner.html."
  rollback
fi

# port z pliku usługi — żeby sprawdzić właściwy adres
PORT="${SUSHI_PORT:-$(grep -o -- '--port [0-9]*' "$SYSTEMD_DIR/$SERVICE.service" 2>/dev/null | head -1 | tr -dc 0-9)}"
if [ -z "$PORT" ]; then
  log "Nie udało się ustalić portu z $SYSTEMD_DIR/$SERVICE.service — wycofuję dla bezpieczeństwa."
  log "Możesz podać port ręcznie: SUSHI_PORT=30123 sushi-update --force"
  rollback
fi

systemctl restart "$SERVICE" || rollback

# kontrola po restarcie jest obowiązkowa — bez niej awaria przeszłaby niezauważona
i=0; OK=""
while [ $i -lt 25 ]; do
  if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then OK=1; break; fi
  i=$((i+1)); sleep 1
done
[ -z "$OK" ] && { log "Serwer nie odpowiada po aktualizacji."; rollback; }

rm -f "$FAILED_F"
log "Zaktualizowano do $(cat VERSION 2>/dev/null || echo '?') (${NEW%${NEW#???????}}). Wszystko działa."
