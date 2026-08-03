#!/bin/bash
# Test pełnego cyklu: instalacja z repo -> aktualizacja -> wycofanie zepsutej wersji.
# Bez systemd (sandbox), więc usługę udajemy prostym menedżerem procesu.
set -u

WORK=/tmp/sp-cycle
FAIL=0
ok()  { echo "  OK   $1"; }
bad() { echo "  FAIL $1  -> ${2:-}"; FAIL=$((FAIL+1)); }
chk() { if [ "$1" = "0" ]; then ok "$2"; else bad "$2" "${3:-}"; fi; }

rm -rf "$WORK"; mkdir -p "$WORK"
cd "$WORK"

echo "== PRZYGOTOWANIE ZDALNEGO REPOZYTORIUM =="
git init --quiet --bare "$WORK/remote.git"
git clone --quiet "$WORK/remote.git" "$WORK/src"
cp -r /root/repo/. "$WORK/src/"
rm -rf "$WORK/src/.git" 2>/dev/null || true
cd "$WORK/src"
git init --quiet -b main
git config user.email t@t.pl; git config user.name Test
git remote add origin "$WORK/remote.git"
git add -A && git commit --quiet -m "wersja 1.3.0"
git push --quiet -u origin main
V1=$(git rev-parse --short HEAD)
chk $? "repozytorium z wersją 1.3.0 ($V1)"

echo
echo "== INSTALACJA (odwzorowanie install.sh bez systemd) =="
APP=$WORK/opt; DATA=$WORK/var
git clone --quiet --branch main "$WORK/remote.git" "$APP"
mkdir -p "$DATA"
SUSHI_DATA=$DATA python3 "$APP/server.py" init >/dev/null 2>&1
chk $? "init katalogu danych"
printf 'tajnehaslo1\ntajnehaslo1\n' | SUSHI_DATA=$DATA python3 "$APP/server.py" adduser szef@lokal.pl owner >/dev/null 2>&1
chk $? "utworzenie konta"

PORT=$(python3 -c "import socket;s=socket.socket();s.bind(('127.0.0.1',0));print(s.getsockname()[1]);s.close()")
# udawana usługa systemd
cat > "$WORK/svc.sh" <<EOF
#!/bin/sh
case "\$1" in
  restart|start)
    [ -f $WORK/pid ] && kill "\$(cat $WORK/pid)" 2>/dev/null
    sleep 0.4
    SUSHI_DATA=$DATA nohup python3 $APP/server.py run --port $PORT --host 127.0.0.1 \
      >>$WORK/svc.log 2>&1 &
    echo \$! > $WORK/pid
    sleep 1.2 ;;
  stop) [ -f $WORK/pid ] && kill "\$(cat $WORK/pid)" 2>/dev/null ;;
esac
exit 0
EOF
chmod +x "$WORK/svc.sh"
mkdir -p "$WORK/bin"
cat > "$WORK/bin/systemctl" <<EOF
#!/bin/sh
case "\$1" in
  restart|start|stop) exec $WORK/svc.sh "\$1" ;;
  *) exit 0 ;;
esac
EOF
chmod +x "$WORK/bin/systemctl"
mkdir -p "$WORK/etc/systemd/system"
printf 'ExecStart=/usr/bin/python3 %s/server.py run --port %s\n' "$APP" "$PORT" \
  > "$WORK/etc/systemd/system/sushi-planner.service"
# szablon z repo używa @PORT@ — atrapa usługi i tak startuje własną komendą

"$WORK/svc.sh" start
H=$(curl -fsS "http://127.0.0.1:$PORT/api/health" 2>/dev/null)
chk $? "serwer odpowiada po instalacji" "$H"
echo "$H" | grep -q '"version": *"1.3.0"'
chk $? "raportuje wersję 1.3.0" "$H"
echo "$H" | grep -q "\"commit\": *\"$V1\""
chk $? "raportuje commit $V1" "$H"

# zapis danych, żeby sprawdzić, czy przeżyją aktualizacje
COOKIE=$WORK/cookie
curl -fsS -c "$COOKIE" -X POST "http://127.0.0.1:$PORT/api/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"szef@lokal.pl","password":"tajnehaslo1"}' >/dev/null 2>&1
chk $? "logowanie przez API"
curl -fsS -b "$COOKIE" -X PUT "http://127.0.0.1:$PORT/api/data" \
  -H 'Content-Type: application/json' \
  -d '{"rev":0,"data":{"ingredients":[{"id":"losos","name":"Łosoś","packPrice":74.5}],"items":[],"sets":[],"preps":[],"history":[],"settings":{}}}' >/dev/null 2>&1
chk $? "zapis danych"

echo
echo "== AKTUALIZACJA DO NOWEJ WERSJI =="
cd "$WORK/src"
echo "1.4.0" > VERSION
sed -i 's|<title>Sushi Planner|<title>Sushi Planner v14|' sushi-planner.html
git add -A && git commit --quiet -m "wersja 1.4.0"
git push --quiet origin main
V2=$(git rev-parse --short HEAD)

UP() { cd "$APP" && PATH="$WORK/bin:$PATH" SUSHI_APP=$APP SUSHI_DATA=$DATA \
       SUSHI_SYSTEMD_DIR=$WORK/etc/systemd/system sh "$APP/update.sh" "$@" 2>&1; }
OUT=$(UP)
echo "$OUT" | grep -q "Zaktualizowano do 1.4.0"
chk $? "aktualizacja wykonana" "$OUT"
H=$(curl -fsS "http://127.0.0.1:$PORT/api/health" 2>/dev/null)
echo "$H" | grep -q '"version": *"1.4.0"'
chk $? "serwer działa na wersji 1.4.0" "$H"
grep -q "v14" "$APP/sushi-planner.html"
chk $? "nowy plik HTML wgrany"
python3 -c "
import json,sys
d=json.load(open('$DATA/data.json'))
sys.exit(0 if d['data']['ingredients'][0]['packPrice']==74.5 else 1)"
chk $? "dane przetrwały aktualizację"
ls "$DATA"/backup/przed-aktualizacja-*.tar.gz >/dev/null 2>&1
chk $? "powstała kopia przedaktualizacyjna"

echo
echo "== BRAK ZMIAN =="
OUT=$(UP)
echo "$OUT" | grep -q "Bez zmian"
chk $? "druga aktualizacja nic nie robi" "$OUT"

echo
echo "== WYCOFANIE ZEPSUTEJ WERSJI =="
cd "$WORK/src"
echo "1.5.0-zepsuta" > VERSION
printf '\nto nie jest poprawny python(((\n' >> server.py
git add -A && git commit --quiet -m "zepsuta wersja"
git push --quiet origin main

OUT=$(UP)
echo "$OUT" | grep -q "błąd składni"
chk $? "wykryto zepsuty kod" "$OUT"
echo "$OUT" | grep -q "Aktualizacja wycofana"
chk $? "wycofano aktualizację" "$OUT"
sleep 1
H=$(curl -fsS "http://127.0.0.1:$PORT/api/health" 2>/dev/null)
echo "$H" | grep -q '"version": *"1.4.0"'
chk $? "serwer nadal działa na sprawnej 1.4.0" "$H"
python3 -c "
import json,sys
d=json.load(open('$DATA/data.json'))
sys.exit(0 if d['data']['ingredients'][0]['packPrice']==74.5 else 1)"
chk $? "dane nietknięte po wycofaniu"

echo
echo "== WYCOFANIE, GDY SERWER NIE WSTAJE =="
cd "$WORK/src"
git revert --quiet --no-edit HEAD          # napraw składnię
echo "1.6.0-nie-wstaje" > VERSION
python3 - <<'PY'
s=open('server.py',encoding='utf-8').read()
s=s.replace("def cmd_run(a):","def cmd_run(a):\n    raise SystemExit('symulowana awaria startu')",1)
open('server.py','w',encoding='utf-8').write(s)
PY
git add -A && git commit --quiet -m "wersja, ktora nie wstaje"
git push --quiet origin main

OUT=$(UP)
echo "$OUT" | grep -q "nie odpowiada po aktualizacji"
chk $? "wykryto, że serwer nie wstał" "$OUT"
sleep 1
H=$(curl -fsS "http://127.0.0.1:$PORT/api/health" 2>/dev/null)
echo "$H" | grep -q '"version": *"1.4.0"'
chk $? "automatyczny powrót do działającej wersji" "$H"

echo
echo "== POWTORNA PROBA TEGO SAMEGO ZEPSUTEGO COMMITA =="
OUT=$(UP)
echo "$OUT" | grep -q "Pomijam"
chk $? "druga proba pomija znany zepsuty commit" "$OUT"

echo
echo "== TRYB --check =="
OUT=$(UP --check)
echo "$OUT" | grep -q "Dostępna nowa wersja"
chk $? "--check pokazuje dostępną wersję bez instalowania" "$OUT"
H=$(curl -fsS "http://127.0.0.1:$PORT/api/health" 2>/dev/null)
echo "$H" | grep -q '"version": *"1.4.0"'
chk $? "--check niczego nie zmienił"

"$WORK/svc.sh" stop 2>/dev/null
echo
echo "============================================================"
if [ "$FAIL" = "0" ]; then echo "WSZYSTKO PRZESZŁO"; else echo "NIEPOWODZENIA: $FAIL"; fi
echo "============================================================"
exit $FAIL
