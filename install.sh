#!/bin/sh
# ---------------------------------------------------------------------------
# Sushi Planner — instalacja jednym poleceniem.
#
#   curl -sSL https://raw.githubusercontent.com/UZYTKOWNIK/sushi-planner/main/install.sh \
#     | sh -s -- --port 30123 --repo https://github.com/UZYTKOWNIK/sushi-planner.git
#
# Albo z rozpakowanego katalogu:   sudo sh install.sh --port 30123
#
# Kod trafia do /opt/sushi-planner (nadpisywany przy aktualizacji),
# dane do /var/lib/sushi-planner (nietykalne).
# ---------------------------------------------------------------------------
set -e

APP_DIR=/opt/sushi-planner
DATA_DIR=/var/lib/sushi-planner
SERVICE=sushi-planner
PORT=""
REPO="${SUSHI_REPO:-}"
BRANCH="${SUSHI_BRANCH:-main}"
AUTOUPDATE=yes

while [ $# -gt 0 ]; do
  case "$1" in
    --port)        PORT="$2"; shift 2 ;;
    --repo)        REPO="$2"; shift 2 ;;
    --branch)      BRANCH="$2"; shift 2 ;;
    --no-autoupdate) AUTOUPDATE=no; shift ;;
    -h|--help)
      echo "Użycie: install.sh --port <PORT> [--repo <URL>] [--branch <gałąź>] [--no-autoupdate]"
      exit 0 ;;
    *) echo "Nieznany argument: $1"; exit 1 ;;
  esac
done

if [ "$(id -u)" != "0" ]; then
  echo "Uruchom jako root (sudo)."; exit 1
fi
if [ -z "$PORT" ]; then
  echo "Podaj port: --port 30123   (to Twój port z panelu Mikrusa)"; exit 1
fi
case "$PORT" in ''|*[!0-9]*) echo "Port musi być liczbą."; exit 1 ;; esac

say() { echo "==> $*"; }

# --- 1. zależności --------------------------------------------------------
say "Sprawdzam zależności"
NEED=""
command -v git     >/dev/null 2>&1 || NEED="$NEED git"
command -v python3 >/dev/null 2>&1 || NEED="$NEED python3"
command -v curl    >/dev/null 2>&1 || NEED="$NEED curl"
if [ -n "$NEED" ]; then
  say "Instaluję:$NEED"
  if command -v apt-get >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $NEED
  elif command -v dnf >/dev/null 2>&1; then dnf install -y -q $NEED
  elif command -v apk >/dev/null 2>&1; then apk add --no-cache $NEED
  else echo "Nieznany menedżer pakietów. Zainstaluj ręcznie:$NEED"; exit 1
  fi
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)' \
  || { echo "Potrzebny Python 3.8 lub nowszy."; exit 1; }
say "$(python3 --version), $(git --version)"

# --- 2. kod ---------------------------------------------------------------
if [ -d "$APP_DIR/.git" ]; then
  say "Aktualizuję istniejącą instalację w $APP_DIR"
  cd "$APP_DIR"
  [ -n "$REPO" ] && git remote set-url origin "$REPO"
  git fetch --quiet origin "$BRANCH"
  git checkout --quiet -B "$BRANCH" "origin/$BRANCH"
else
  if [ -z "$REPO" ]; then
    # uruchomiono z rozpakowanego katalogu — spróbuj wziąć adres stąd
    HERE="$(cd "$(dirname "$0")" && pwd)"
    if [ -d "$HERE/.git" ]; then
      REPO="$(git -C "$HERE" remote get-url origin 2>/dev/null || true)"
    fi
  fi
  if [ -z "$REPO" ]; then
    echo "Podaj adres repozytorium: --repo https://github.com/TWOJ-LOGIN/sushi-planner.git"
    exit 1
  fi
  say "Pobieram kod z $REPO ($BRANCH)"
  rm -rf "$APP_DIR"
  git clone --quiet --branch "$BRANCH" --depth 20 "$REPO" "$APP_DIR"
  cd "$APP_DIR"
fi
git config --local --replace-all safe.directory "$APP_DIR" 2>/dev/null || true

# --- 3. dane --------------------------------------------------------------
say "Przygotowuję katalog danych $DATA_DIR"
mkdir -p "$DATA_DIR"
# przeniesienie danych ze starej instalacji (gdy dane leżały obok kodu)
if [ -f "$APP_DIR/data/data.json" ] && [ ! -f "$DATA_DIR/data.json" ]; then
  say "Przenoszę dane ze starej lokalizacji"
  cp -a "$APP_DIR/data/." "$DATA_DIR/"
fi
chmod 700 "$DATA_DIR"
SUSHI_DATA="$DATA_DIR" python3 "$APP_DIR/server.py" init >/dev/null

# --- 4. usługa ------------------------------------------------------------
say "Konfiguruję usługę systemd"
cat > /etc/systemd/system/$SERVICE.service <<EOF
[Unit]
Description=Sushi Planner — food cost i menu
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
Environment=SUSHI_DATA=$DATA_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 $APP_DIR/server.py run --port $PORT
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ProtectKernelTunables=true
RestrictSUIDSGID=true
ReadWritePaths=$DATA_DIR

[Install]
WantedBy=multi-user.target
EOF

if [ "$AUTOUPDATE" = "yes" ]; then
cat > /etc/systemd/system/$SERVICE-update.service <<EOF
[Unit]
Description=Sushi Planner — sprawdzenie i instalacja aktualizacji
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/sh $APP_DIR/update.sh
TimeoutStartSec=300
EOF
cat > /etc/systemd/system/$SERVICE-update.timer <<'EOF'
[Unit]
Description=Codzienne sprawdzanie aktualizacji Sushi Plannera

[Timer]
OnCalendar=*-*-* 04:30:00
RandomizedDelaySec=1800
Persistent=true

[Install]
WantedBy=timers.target
EOF
fi

# krótkie polecenia pod ręką
ln -sf "$APP_DIR/update.sh" /usr/local/bin/sushi-update
printf '#!/bin/sh\nexec env SUSHI_DATA=%s python3 %s/server.py "$@"\n' "$DATA_DIR" "$APP_DIR" \
  > /usr/local/bin/sushi
chmod +x /usr/local/bin/sushi "$APP_DIR/update.sh" 2>/dev/null || true

systemctl daemon-reload
systemctl enable --quiet $SERVICE 2>/dev/null || systemctl enable $SERVICE >/dev/null 2>&1
systemctl restart $SERVICE
if [ "$AUTOUPDATE" = "yes" ]; then
  systemctl enable --quiet $SERVICE-update.timer 2>/dev/null || systemctl enable $SERVICE-update.timer >/dev/null 2>&1
  systemctl start $SERVICE-update.timer
fi

# --- 5. sprawdzenie -------------------------------------------------------
say "Sprawdzam, czy odpowiada"
i=0
while [ $i -lt 30 ]; do
  if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then OK=1; break; fi
  i=$((i+1)); sleep 1
done
if [ -z "$OK" ]; then
  echo "Serwer nie odpowiada. Zajrzyj do logów:  journalctl -u $SERVICE -n 40"
  exit 1
fi

VER=$(cat "$APP_DIR/VERSION" 2>/dev/null || echo '?')
HAS_USERS=$(SUSHI_DATA="$DATA_DIR" python3 "$APP_DIR/server.py" users 2>/dev/null | grep -c '@' || true)

echo
echo "==================================================================="
echo " Sushi Planner $VER działa na porcie $PORT."
[ "$AUTOUPDATE" = "yes" ] && echo " Automatyczna aktualizacja: włączona (codziennie ok. 4:30)."
echo
if [ "$HAS_USERS" = "0" ]; then
echo " NASTĘPNY KROK — załóż konto:"
echo "   sushi adduser twoj@email.pl owner"
echo
fi
HOST=$(hostname 2>/dev/null || echo srvNUMER)
echo " Adres:"
echo "   https://$HOST-$PORT.wykr.es"
echo "   (subdomena wykr.es bierze nazwę serwera, nie 'srv' + numer)"
echo
echo " Polecenia:"
echo "   sushi users                     lista kont"
echo "   sushi adduser mail@x.pl chef    nowe konto"
echo "   sushi-update                    aktualizacja na żądanie"
echo "   systemctl status $SERVICE"
echo "   journalctl -u $SERVICE -f"
echo "==================================================================="
