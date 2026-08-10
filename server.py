#!/usr/bin/env python3
"""
Sushi Planner — serwer.

Zero zależności zewnętrznych: tylko biblioteka standardowa Pythona 3.8+.
Zużycie pamięci ~20 MB, więc mieści się nawet na Mikrusie 1.0 (384 MB RAM).

Użycie:
    python3 server.py init                      # katalog danych + klucz sesji
    python3 server.py adduser szef@lokal.pl owner
    python3 server.py adduser radek@lokal.pl admin
    python3 server.py adduser ania@lokal.pl staff
    python3 server.py users                     # lista kont
    python3 server.py passwd szef@lokal.pl      # zmiana hasła
    python3 server.py deluser radek@lokal.pl
    python3 server.py run --port 30123          # uruchomienie

Cztery poziomy uprawnień:
    owner  — właściciel: wszystko; jego konta nie da się usunąć ani zdegradować
    admin  — administrator: to samo, poza kontem właściciela
    staff  — pracownik: panel dnia i receptury BEZ CEN, zapisuje się na zmiany
    viewer — podgląd: to samo co pracownik, ale niczego nie zmienia
"""

import argparse
import datetime
import base64
import io
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('SUSHI_DATA', os.path.join(BASE, 'data'))
INDEX = os.path.join(BASE, 'sushi-planner.html')

USERS_F = lambda: os.path.join(DATA_DIR, 'users.json')
DATA_F = lambda: os.path.join(DATA_DIR, 'data.json')
SECRET_F = lambda: os.path.join(DATA_DIR, 'secret')
# Jeden plik na miesiąc — patrz nagłówek pliku, punkt 1.
SPRZEDAZ_F = lambda ym: os.path.join(DATA_DIR, 'sprzedaz-%s.json' % ym)
TOKEN_F = lambda: os.path.join(DATA_DIR, 'token-sprzedaz')
BACKUP_D = lambda: os.path.join(DATA_DIR, 'backup')

MAX_BODY = 32 * 1024 * 1024        # 32 MB — z zapasem na zdjęcia
# Gotenberg zamienia HTML na PDF. Na Mikrusie chodzi w Dockerze, więc widać go
# pod adresem mostka docker0. Zmienna pozwala wskazać inny adres albo wyłączyć.
GOTENBERG = os.environ.get('SUSHI_GOTENBERG', 'http://172.17.0.1:3001')
PDF_TIMEOUT = 90

# aktualizacja: skrypt i jednostka systemd, którą uruchamia timer
SERVICE = os.environ.get('SUSHI_SERVICE', 'sushi-planner')
UPDATE_SH = os.environ.get('SUSHI_UPDATE_SH', os.path.join(BASE, 'update.sh'))
UPDATE_UNIT = SERVICE + '-update.service'
UPDATE_LOG = lambda: os.path.join(DATA_DIR, 'aktualizacja.log')
SESSION_DAYS = 30
KEEP_BACKUPS = 20
# Cztery poziomy, od pełnych praw do samego patrzenia:
#   owner  — wszystko; konta nie da się usunąć ani odebrać mu roli
#   admin  — wszystko oprócz skasowania właściciela i zmiany jego roli
#   staff  — panel dnia i receptury BEZ CEN; zapisuje i wypisuje siebie z grafiku
#   viewer — to samo co staff, ale grafiku nie rusza
ROLES = ('owner', 'admin', 'staff', 'viewer')
MANAGERS = ('owner', 'admin')      # pełny dostęp do bazy i do kont
BEZ_CEN = ('staff', 'viewer')      # tym kontom ceny nie wychodzą z serwera


def moze_grafik(u):
    """Czy to konto układa grafik INNYM ludziom.

    Wcześniej było to osobne uprawnienie doklejane do roli. Przy czterech poziomach
    nie ma po co: kto zarządza bazą, ten zarządza i grafikiem, a kto nie — wpisuje
    wyłącznie siebie."""
    return bool(u) and u.get('role') in MANAGERS


def moze_edytowac(u):
    """Czy to konto zapisuje bazę: receptury, ceny, załadunki, automaty."""
    return bool(u) and u.get('role') in MANAGERS


def chroniony(u, email):
    """Konta właściciela nie rusza nikt poza nim samym — ani skasować, ani zmienić roli.
    Dzięki temu administrator nie może odciąć właściciela od jego własnego lokalu."""
    return bool(u) and u.get('role') != 'owner' and rola_konta(email) == 'owner'


def rola_konta(email):
    kon = read_json(USERS_F(), {}) or {}
    u = kon.get(str(email or '').strip().lower())
    return (u or {}).get('role')

_lock = threading.Lock()


# --------------------------------------------------------------------------
# pliki
# --------------------------------------------------------------------------
def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BACKUP_D(), exist_ok=True)


def read_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json_atomic(path, obj):
    """Zapis przez plik tymczasowy + rename — przerwanie w trakcie nie niszczy danych."""
    ensure_dirs()
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def backup_data():
    src = DATA_F()
    if not os.path.exists(src):
        return
    ensure_dirs()
    dst = os.path.join(BACKUP_D(), time.strftime('data-%Y%m%d-%H%M%S.json'))
    try:
        shutil.copy2(src, dst)
    except OSError:
        return
    old = sorted(os.listdir(BACKUP_D()))
    for name in old[:-KEEP_BACKUPS]:
        try:
            os.remove(os.path.join(BACKUP_D(), name))
        except OSError:
            pass


def secret():
    ensure_dirs()
    p = SECRET_F()
    if not os.path.exists(p):
        with open(p, 'wb') as f:
            f.write(secrets.token_bytes(32))
        os.chmod(p, 0o600)
    with open(p, 'rb') as f:
        return f.read()


def token_sprzedazy(nowy=False):
    """Klucz, którym n8n podpisuje wysyłkę sprzedaży.

    To nie jest konto: n8n nie jest człowiekiem, nie ma nazwiska w grafiku i nie ma po co
    dawać mu sesji. Zwykły klucz w nagłówku wystarcza, a przy okazji nie da się nim
    zalogować do aplikacji ani niczego w niej zobaczyć."""
    ensure_dirs()
    p = TOKEN_F()
    if nowy or not os.path.exists(p):
        with open(p, 'w') as f:
            f.write(secrets.token_urlsafe(32))
        os.chmod(p, 0o600)
    with open(p) as f:
        return f.read().strip()


# --------------------------------------------------------------------------
# hasła i sesje
# --------------------------------------------------------------------------
def hash_pw(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return base64.b64encode(salt).decode() + '$' + base64.b64encode(dk).decode()


def check_pw(password, stored):
    try:
        salt_b64, dk_b64 = stored.split('$')
        salt = base64.b64decode(salt_b64)
        expect = base64.b64decode(dk_b64)
    except (ValueError, TypeError):
        return False
    dk = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return hmac.compare_digest(dk, expect)


def zapisz_uzytkownikow(users):
    write_json_atomic(USERS_F(), users)
    try:
        os.chmod(USERS_F(), 0o600)
    except OSError:
        pass


def migruj_role():
    """Konta sprzed podziału na cztery poziomy.

    Rola „kucharz" miała pełną edycję bazy bez dostępu do kont — w nowym podziale
    to administrator. Osobny przełącznik „układa grafik" też znika: kto go miał,
    ten zarządzał ludźmi, więc zostaje administratorem. Nikomu nie zabieramy tu
    uprawnień; migracja ma być cicha i jednorazowa."""
    users = read_json(USERS_F(), {})
    if not isinstance(users, dict) or not users:
        return
    zmiana = False
    for e, u in users.items():
        if not isinstance(u, dict):
            continue
        rola = u.get('role', 'viewer')
        if rola == 'chef' or (u.get('sched') and rola != 'owner'):
            rola = 'admin'
        if rola not in ROLES:
            rola = 'viewer'
        if rola != u.get('role'):
            u['role'] = rola
            zmiana = True
        if 'sched' in u:
            u.pop('sched', None)
            zmiana = True
    if zmiana:
        zapisz_uzytkownikow(users)


def ilu_wlascicieli(users, pomin=None):
    return sum(1 for e, u in users.items()
               if u.get('role') == 'owner' and e != pomin)


def make_token(email, role):
    """Podpisany token — sesje przeżywają restart serwera."""
    exp = int(time.time()) + SESSION_DAYS * 86400
    payload = json.dumps({'e': email, 'r': role, 'x': exp}, separators=(',', ':')).encode()
    body = base64.urlsafe_b64encode(payload).decode().rstrip('=')
    sig = hmac.new(secret(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return body + '.' + sig


def read_token(token):
    if not token or '.' not in token:
        return None
    body, sig = token.rsplit('.', 1)
    good = hmac.new(secret(), body.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, good):
        return None
    try:
        pad = '=' * (-len(body) % 4)
        data = json.loads(base64.urlsafe_b64decode(body + pad))
    except Exception:
        return None
    if data.get('x', 0) < time.time():
        return None
    users = read_json(USERS_F(), {})
    u = users.get(data['e'])
    if not u:
        return None
    # rola zawsze z pliku, nie z ciasteczka — zmiana roli działa natychmiast
    return {'email': data['e'], 'role': u.get('role', 'viewer')}


# --------------------------------------------------------------------------
# aktualizacja
# --------------------------------------------------------------------------
_update_proc = None          # gdy nie ma systemd, trzymamy uchwyt do potomka


def wersja():
    try:
        with open(os.path.join(BASE, 'VERSION')) as f:
            return f.read().strip()
    except OSError:
        return '?'


def polecenie(args, timeout=120, cwd=None):
    """Uruchamia polecenie i zwraca (kod, wyjście). Brak programu to nie wyjątek."""
    try:
        p = subprocess.run(args, cwd=cwd or BASE, timeout=timeout,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return p.returncode, p.stdout.decode('utf-8', 'replace')
    except FileNotFoundError:
        return 127, 'Brak polecenia: %s' % args[0]
    except subprocess.TimeoutExpired:
        return 124, 'Polecenie przekroczyło czas: %s' % ' '.join(args)
    except Exception as e:
        return 1, '%s: %s' % (type(e).__name__, e)


def commit():
    rc, out = polecenie(['git', 'rev-parse', '--short', 'HEAD'], timeout=15)
    return out.strip() if rc == 0 else ''


def systemd_jest():
    return os.path.isdir('/run/systemd/system')


def update_trwa():
    if systemd_jest():
        rc, out = polecenie(['systemctl', 'is-active', UPDATE_UNIT], timeout=15)
        return out.strip() in ('activating', 'active')
    return _update_proc is not None and _update_proc.poll() is None


def update_log():
    if systemd_jest():
        rc, out = polecenie(['journalctl', '-u', UPDATE_UNIT, '-n', '200',
                             '--no-pager', '--output=cat'], timeout=20)
        if rc == 0 and out.strip():
            return out
    try:
        with open(UPDATE_LOG(), encoding='utf-8', errors='replace') as f:
            return f.read()[-20000:]
    except OSError:
        return ''


def update_start():
    """Odpala aktualizację. Zwraca (ok, komunikat)."""
    global _update_proc
    if update_trwa():
        return False, 'Aktualizacja już trwa.'
    if systemd_jest():
        # Własna jednostka jest tu istotna: update.sh restartuje usługę, więc
        # potomek odpalony z tego procesu zginąłby razem z nią.
        rc, out = polecenie(['systemctl', 'start', '--no-block', UPDATE_UNIT], timeout=30)
        if rc == 0:
            return True, ''
        blad = out.strip()
    else:
        blad = ''
    if not os.path.exists(UPDATE_SH):
        return False, 'Nie znalazłem skryptu aktualizacji (%s). %s' % (UPDATE_SH, blad)
    try:
        ensure_dirs()
        f = open(UPDATE_LOG(), 'ab')
        _update_proc = subprocess.Popen(['/bin/sh', UPDATE_SH], cwd=BASE,
                                        stdout=f, stderr=subprocess.STDOUT,
                                        start_new_session=True)
        return True, ''
    except Exception as e:
        return False, 'Nie udało się uruchomić aktualizacji: %s' % e


def multipart(czesci):
    """Składa ciało multipart/form-data. Każda część to (nazwa, nazwa_pliku, bajty)."""
    granica = '----sushi' + secrets.token_hex(16)
    buf = io.BytesIO()
    for nazwa, plik, dane in czesci:
        buf.write(('--%s\r\n' % granica).encode())
        if plik:
            buf.write(('Content-Disposition: form-data; name="%s"; filename="%s"\r\n'
                       'Content-Type: text/html; charset=utf-8\r\n\r\n' % (nazwa, plik)).encode())
        else:
            buf.write(('Content-Disposition: form-data; name="%s"\r\n\r\n' % nazwa).encode())
        buf.write(dane if isinstance(dane, bytes) else str(dane).encode('utf-8'))
        buf.write(b'\r\n')
    buf.write(('--%s--\r\n' % granica).encode())
    return granica, buf.getvalue()


def html_to_pdf(html, stopka=None, opcje=None):
    """HTML → PDF przez Gotenberga. Zwraca (bajty, None) albo (None, komunikat)."""
    if not GOTENBERG:
        return None, 'Generowanie PDF jest wyłączone na tym serwerze.'
    czesci = [('files', 'index.html', html.encode('utf-8'))]
    if stopka:
        czesci.append(('files', 'footer.html', stopka.encode('utf-8')))
    for k, v in (opcje or {}).items():
        czesci.append((k, None, v))
    granica, ciało = multipart(czesci)
    # Gotenberg 7/8 słucha pod /forms/chromium/..., starsza szóstka pod /convert/...
    sciezki = ['/forms/chromium/convert/html', '/convert/html']
    pdf, ostatni = None, 'Nie udało się połączyć z generatorem PDF.'
    for sciezka in sciezki:
        req = urllib.request.Request(GOTENBERG.rstrip('/') + sciezka, data=ciało, method='POST')
        req.add_header('Content-Type', 'multipart/form-data; boundary=' + granica)
        try:
            with urllib.request.urlopen(req, timeout=PDF_TIMEOUT) as r:
                pdf = r.read()
            break
        except urllib.error.HTTPError as e:
            ostatni = 'Gotenberg odrzucił dokument (HTTP %s).' % e.code
            if e.code == 404:
                continue                         # spróbujmy starszego adresu
            return None, ostatni
        except Exception as e:                   # sieć, timeout, brak usługi
            return None, 'Nie udało się połączyć z generatorem PDF (%s).' % type(e).__name__
    if pdf is None:
        return None, ostatni
    if not pdf.startswith(b'%PDF'):
        return None, 'Generator zwrócił coś, co nie jest PDF-em.'
    return pdf, None


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = 'SushiPlanner'
    sys_version = ''
    protocol_version = 'HTTP/1.1'

    # Jeden obiekt obsługuje całe połączenie, więc flagę trzeba zerować przy
    # każdym żądaniu — inaczej drugie zapytanie uzna, że już wyczytało treść.
    def handle_one_request(self):
        self._body_done = False
        BaseHTTPRequestHandler.handle_one_request(self)

    # ---- pomocnicze ----
    def _drain(self):
        """Wyczytuje treść żądania, jeśli nikt jej nie odczytał.

        Bez tego odpowiedź 401/403/404 zostawia bajty w gnieździe i przy
        keep-alive rozjeżdża NASTĘPNE zapytanie na tym samym połączeniu —
        przeglądarka dostaje wtedy z pozoru losowe 400.
        """
        if getattr(self, '_body_done', False):
            return
        self._body_done = True
        n = int(self.headers.get('Content-Length') or 0)
        if n <= 0:
            return
        if n > MAX_BODY:                       # śmieci nie wciągamy — zamykamy
            self.close_connection = True
            return
        left = n
        while left > 0:
            chunk = self.rfile.read(min(left, 65536))
            if not chunk:
                break
            left -= len(chunk)

    def _send(self, code, body=b'', ctype='application/json; charset=utf-8', extra=None):
        self._drain()
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def _json(self, code, obj, extra=None):
        self._send(code, json.dumps(obj, ensure_ascii=False), extra=extra)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n > MAX_BODY:
            return None
        raw = self.rfile.read(n) if n else b'{}'
        self._body_done = True
        try:
            return json.loads(raw or b'{}')
        except json.JSONDecodeError:
            return None

    def _user(self):
        raw = self.headers.get('Cookie')
        if not raw:
            return None
        c = SimpleCookie(raw)
        if 'sp_session' not in c:
            return None
        return read_token(c['sp_session'].value)

    def _https(self):
        return (self.headers.get('X-Forwarded-Proto', '').lower() == 'https'
                or self.headers.get('X-Forwarded-Ssl', '').lower() == 'on')

    def _cookie(self, value, days):
        parts = ['sp_session=' + value, 'Path=/', 'HttpOnly', 'SameSite=Lax',
                 'Max-Age=' + str(days * 86400)]
        if self._https():
            parts.append('Secure')
        return ('Set-Cookie', '; '.join(parts))

    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), fmt % args))

    # ---- routing ----
    def do_GET(self):
        path = self.path.split('?')[0]

        if path in ('/', '/index.html'):
            try:
                with open(INDEX, 'rb') as f:
                    html = f.read()
            except FileNotFoundError:
                self._send(500, 'Brak pliku sushi-planner.html obok server.py', 'text/plain; charset=utf-8')
                return
            self._send(200, html, 'text/html; charset=utf-8',
                       [('Cache-Control', 'no-cache')])
            return

        if path == '/api/health':
            self._json(200, {'ok': True, 'time': int(time.time()),
                             'version': wersja(), 'commit': commit()})
            return

        if path == '/api/users':
            u = self._user()
            if not u:
                self._json(401, {'error': 'Zaloguj się.'})
                return
            if u['role'] not in MANAGERS:
                self._json(403, {'error': 'Kontami zarządza właściciel i administrator.'})
                return
            users = read_json(USERS_F(), {})
            lista = [{'email': e, 'role': v.get('role', 'viewer'),
                       'created': v.get('created')}
                     for e, v in sorted(users.items())]
            self._json(200, {'users': lista})
            return

        if path in ('/api/update/check', '/api/update/status'):
            u = self._user()
            if not u:
                self._json(401, {'error': 'Zaloguj się.'})
                return
            if u['role'] not in MANAGERS:
                self._json(403, {'error': 'Aktualizuje właściciel albo administrator.'})
                return
            wsp = {'version': wersja(), 'commit': commit()}

            if path == '/api/update/status':
                self._json(200, dict(wsp, busy=update_trwa(), log=update_log()))
                return

            if update_trwa():
                self._json(200, dict(wsp, busy=True))
                return
            if not os.path.exists(UPDATE_SH):
                self._json(200, dict(wsp, ok=False, available=False,
                                     output='Nie znalazłem skryptu aktualizacji: ' + UPDATE_SH))
                return
            rc, out = polecenie(['/bin/sh', UPDATE_SH, '--check'], timeout=90)
            self._json(200, dict(wsp, ok=(rc == 0), available=('Dostępna nowa wersja' in out),
                                 output=out))
            return

        if path == '/api/me':
            u = self._user()
            if not u:
                self._json(401, {'mode': 'server', 'user': None})
            else:
                self._json(200, {'mode': 'server', 'user': u})
            return

        if path == '/api/sprzedaz/dni':
            # Pyta o to n8n przed zaciągnięciem archiwum, więc klucz w nagłówku,
            # nie ciasteczko. Sama lista dat nie mówi nic o pieniądzach.
            podany = self.headers.get('X-Token', '')
            if not hmac.compare_digest(podany, token_sprzedazy()):
                self._json(401, {'error': 'Zły klucz.'})
                return
            self._json(200, {'dni': dni_sprzedazy()})
            return

        if path == '/api/sprzedaz/eksport':
            # Stoi PRZED trasą miesiąca, bo tamta łapie po przedrostku i zażądałaby `ym`.
            u = self._user()
            if not u:
                self._json(401, {'error': 'Zaloguj się.'})
                return
            if u['role'] in BEZ_CEN:
                self._json(403, {'error': 'Twoje konto nie widzi cen.'})
                return
            with _lock:
                st = read_json(DATA_F(), {'rev': 0, 'data': None})
            dane = eksport_sprzedazy(st.get('data') or {})
            tresc = json.dumps(dane, ensure_ascii=False, indent=1).encode('utf-8')
            nazwa = 'sprzedaz-eksport-%s.json' % time.strftime('%Y-%m-%d')
            self._send(200, tresc, 'application/json; charset=utf-8',
                       [('Content-Disposition', 'attachment; filename="%s"' % nazwa)])
            return

        if path.startswith('/api/sprzedaz'):
            # W sprzedaży są pieniądze, więc poziomy „pracownik" i „podgląd" jej nie dostają —
            # tak samo, jak nie dostają cen w bazie.
            u = self._user()
            if not u:
                self._json(401, {'error': 'Zaloguj się.'})
                return
            if u['role'] in BEZ_CEN:
                self._json(403, {'error': 'Twoje konto nie widzi cen.'})
                return
            q = {}
            if '?' in self.path:
                for kawalek in self.path.split('?', 1)[1].split('&'):
                    if '=' in kawalek:
                        k, w = kawalek.split('=', 1)
                        q[k] = w
            mies = re.compile(r'^\d{4}-\d{2}$')
            # Jeden miesiąc albo zakres. Wykresy patrzą rok wstecz i pytanie o trzynaście
            # miesięcy po jednym byłoby trzynastoma żądaniami zamiast jednego.
            if mies.match(q.get('od', '')) and mies.match(q.get('do', '')):
                od, do = sorted([q['od'], q['do']])
                lista, biezacy = [], od
                while biezacy <= do and len(lista) < 36:
                    lista.append(biezacy)
                    r, m = int(biezacy[:4]), int(biezacy[5:]) + 1
                    if m > 12:
                        r, m = r + 1, 1
                    biezacy = '%04d-%02d' % (r, m)
                wynik = {}
                for ym in lista:
                    wynik.update(read_json(SPRZEDAZ_F(ym), {}) or {})
                self._json(200, {'od': od, 'do': do, 'sprzedaz': wynik})
                return
            ym = q.get('ym', '')
            if not mies.match(ym):
                self._json(400, {'error': 'Podaj miesiąc jako ym=RRRR-MM albo zakres od= i do=.'})
                return
            self._json(200, {'ym': ym, 'sprzedaz': read_json(SPRZEDAZ_F(ym), {}) or {}})
            return

        if path == '/api/data':
            u = self._user()
            if not u:
                self._json(401, {'error': 'Zaloguj się.'})
                return
            with _lock:
                st = read_json(DATA_F(), {'rev': 0, 'data': None, 'updatedAt': None, 'updatedBy': None})
            if u['role'] in BEZ_CEN:
                st = dict(st)
                st['data'] = bez_cen(st.get('data'))
                st['limited'] = True
            self._json(200, st)
            return

        self._json(404, {'error': 'Nie znaleziono.'})

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        path = self.path.split('?')[0]

        if path == '/api/login':
            b = self._body()
            if b is None:
                self._json(400, {'error': 'Błędne dane.'})
                return
            email = str(b.get('email', '')).strip().lower()
            pw = str(b.get('password', ''))
            users = read_json(USERS_F(), {})
            u = users.get(email)
            time.sleep(0.25)                       # hamulec na zgadywanie haseł
            if not u or not check_pw(pw, u.get('pw', '')):
                self._json(401, {'error': 'Nieprawidłowy e-mail lub hasło.'})
                return
            tok = make_token(email, u.get('role', 'viewer'))
            self._json(200, {'user': {'email': email, 'role': u.get('role', 'viewer')}},
                       extra=[self._cookie(tok, SESSION_DAYS)])
            return

        if path in ('/api/users', '/api/users/update', '/api/users/delete'):
            u = self._user()
            if not u:
                self._json(401, {'error': 'Zaloguj się.'})
                return
            if u['role'] not in MANAGERS:
                self._json(403, {'error': 'Kontami zarządza właściciel i administrator.'})
                return
            b = self._body()
            if b is None:
                self._json(400, {'error': 'Błędne dane.'})
                return
            email = str(b.get('email', '')).strip().lower()
            if '@' not in email:
                self._json(400, {'error': 'Podaj poprawny adres e-mail.'})
                return
            haslo = b.get('password')
            rola = b.get('role')
            if rola is not None and rola not in ROLES:
                self._json(400, {'error': 'Nieznana rola.'})
                return

            with _lock:
                users = read_json(USERS_F(), {})

                if path == '/api/users':
                    if email in users:
                        self._json(409, {'error': 'Takie konto już istnieje.'})
                        return
                    if not haslo or len(str(haslo)) < 8:
                        self._json(400, {'error': 'Hasło musi mieć co najmniej 8 znaków.'})
                        return
                    if rola == 'owner' and u['role'] != 'owner':
                        self._json(403, {'error': 'Konto właściciela zakłada tylko właściciel.'})
                        return
                    users[email] = {'pw': hash_pw(str(haslo)), 'role': rola or 'viewer',
                                    'created': int(time.time())}
                    zapisz_uzytkownikow(users)
                    self._json(200, {'ok': True})
                    return

                if email not in users:
                    self._json(404, {'error': 'Nie ma takiego konta.'})
                    return

                if path == '/api/users/delete':
                    if email == u['email']:
                        self._json(400, {'error': 'Nie da się usunąć własnego konta.'})
                        return
                    if chroniony(u, email):
                        self._json(403, {'error': 'Konta właściciela nie da się usunąć.'})
                        return
                    if users[email].get('role') == 'owner' and ilu_wlascicieli(users, email) == 0:
                        self._json(400, {'error': 'To ostatni właściciel — musi zostać ktoś, kto zarządza kontami.'})
                        return
                    del users[email]
                    zapisz_uzytkownikow(users)
                    self._json(200, {'ok': True})
                    return

                # /api/users/update
                if haslo:
                    if len(str(haslo)) < 8:
                        self._json(400, {'error': 'Hasło musi mieć co najmniej 8 znaków.'})
                        return
                    users[email]['pw'] = hash_pw(str(haslo))
                if rola and rola != users[email].get('role'):
                    if chroniony(u, email):
                        self._json(403, {'error': 'Roli właściciela zmienić nie można.'})
                        return
                    if rola == 'owner' and u['role'] != 'owner':
                        self._json(403, {'error': 'Właściciela mianuje tylko właściciel.'})
                        return
                    if (users[email].get('role') == 'owner'
                            and ilu_wlascicieli(users, email) == 0):
                        self._json(400, {'error': 'To ostatni właściciel — nie ma komu przekazać kont.'})
                        return
                    users[email]['role'] = rola
                zapisz_uzytkownikow(users)
            self._json(200, {'ok': True})
            return

        if path == '/api/update/run':
            u = self._user()
            if not u:
                self._json(401, {'error': 'Zaloguj się.'})
                return
            if u['role'] not in MANAGERS:
                self._json(403, {'error': 'Aktualizuje właściciel albo administrator.'})
                return
            ok, blad = update_start()
            if not ok:
                self._json(409 if 'trwa' in blad else 500, {'error': blad})
                return
            self._json(200, {'ok': True})
            return

        if path == '/api/pdf':
            u = self._user()
            if not u:
                self._json(401, {'error': 'Zaloguj się.'})
                return
            b = self._body()
            if b is None or not str(b.get('html', '')).strip():
                self._json(400, {'error': 'Brak dokumentu do wydrukowania albo za duży.'})
                return
            opcje = {'marginTop': '0.5', 'marginBottom': '0.5',
                     'marginLeft': '0.4', 'marginRight': '0.4',
                     'preferCssPageSize': 'false', 'printBackground': 'true'}
            if b.get('landscape'):
                opcje['landscape'] = 'true'
            pdf, blad = html_to_pdf(str(b['html']), b.get('footer'), opcje)
            if blad:
                self._json(502, {'error': blad})
                return
            nazwa = ''.join(c for c in str(b.get('name', 'wydruk'))
                            if c.isalnum() or c in '-_') or 'wydruk'
            self._send(200, pdf, 'application/pdf',
                       [('Content-Disposition', 'attachment; filename="%s.pdf"' % nazwa)])
            return

        if path == '/api/sprzedaz/dopasuj':
            # Tę klika człowiek w przeglądarce, więc ciasteczko sesji, a nie klucz n8n:
            # to nie jest przyjmowanie danych z zewnątrz, tylko naprawa własnych.
            u = self._user()
            if not u:
                self._json(401, {'error': 'Zaloguj się.'})
                return
            if u['role'] in BEZ_CEN:
                self._json(403, {'error': 'Twoje konto nie widzi cen.'})
                return
            with _lock:
                st = read_json(DATA_F(), {'rev': 0, 'data': None})
                if not isinstance(st.get('data'), dict):
                    self._json(409, {'error': 'Baza jest pusta.'})
                    return
                # Jak przy przyjmowaniu: bazy nie ruszamy, więc `rev` stoi w miejscu.
                wynik = dopasuj_sprzedaz(st['data'])
            self._json(200, wynik)
            return

        if path == '/api/sprzedaz':
            # Wysyła to n8n, nie przeglądarka — więc nagłówek z kluczem, nie ciasteczko.
            podany = self.headers.get('X-Token', '')
            if not hmac.compare_digest(podany, token_sprzedazy()):
                self._json(401, {'error': 'Zły klucz.'})
                return
            b = self._body()
            if b is None:
                self._json(400, {'error': 'Błędne dane.'})
                return
            with _lock:
                st = read_json(DATA_F(), {'rev': 0, 'data': None})
                if not isinstance(st.get('data'), dict):
                    self._json(409, {'error': 'Baza jest pusta.'})
                    return
                # Sprzedaż NIE rusza bazy — czytamy ją tylko po to, żeby rozpoznać automat
                # i zestaw. Dlatego `rev` nie idzie do przodu i otwarte karty nic nie tracą.
                wynik, blad = przyjmij_sprzedaz(st['data'], b.get('sprzedaz'))
                if blad:
                    self._json(400, {'error': blad})
                    return
            self._json(200, wynik)
            return

        if path == '/api/zdarzenie':
            # Druga wąska trasa zapisu, obok /api/shift i z tego samego powodu:
            # rejestruje kierowca i osoba pakująca, czyli konta, które nie zapisują bazy.
            u = self._user()
            if not u:
                self._json(401, {'error': 'Zaloguj się.'})
                return
            if u['role'] == 'viewer':
                self._json(403, {'error': 'Twoje konto ma tylko podgląd.'})
                return
            b = self._body()
            if b is None:
                self._json(400, {'error': 'Błędne dane.'})
                return
            with _lock:
                st = read_json(DATA_F(), {'rev': 0, 'data': None})
                if not isinstance(st.get('data'), dict):
                    self._json(409, {'error': 'Baza jest pusta — najpierw otwórz aplikację jako menedżer.'})
                    return
                blad = zmien_zdarzenie(st['data'], u, b)
                if blad:
                    self._json(400, {'error': blad})
                    return
                backup_data()
                nowy = {'rev': st.get('rev', 0) + 1, 'data': st['data'],
                        'updatedAt': int(time.time()), 'updatedBy': u['email']}
                write_json_atomic(DATA_F(), nowy)
            self._json(200, {'rev': nowy['rev'],
                             'zdarzenia': nowy['data'].get('zdarzenia', {}),
                             'staff': nowy['data'].get('staff', [])})
            return

        if path == '/api/shift':
            # Jedyna droga zapisu dla roli `staff`. Celowo wąska: bierze dzień,
            # zmianę i „chcę / nie chcę", a tożsamość czyta z ciasteczka — nie da się
            # przez nią zapisać kogoś innego ani ruszyć czegokolwiek poza grafikiem.
            u = self._user()
            if not u:
                self._json(401, {'error': 'Zaloguj się.'})
                return
            if u['role'] == 'viewer':
                self._json(403, {'error': 'Twoje konto ma tylko podgląd.'})
                return
            b = self._body()
            if b is None:
                self._json(400, {'error': 'Błędne dane.'})
                return
            # Granica biegnie po tym, KOGO wpis dotyczy, a nie jak nazywa się operacja:
            # swój wpis — także na kilka dni naraz — rusza każdy, cudzy tylko właściciel
            # i administrator. Brak uprawnienia to odmowa dostępu, nie błędne dane:
            # przeglądarka ma to odróżnić, a i w logu 403 czyta się inaczej niż 400.
            if b.get('person') and not moze_grafik(u):
                self._json(403, {'error': 'Nie masz uprawnienia do układania grafiku.'})
                return
            with _lock:
                st = read_json(DATA_F(), {'rev': 0, 'data': None})
                if not isinstance(st.get('data'), dict):
                    self._json(409, {'error': 'Baza jest pusta — najpierw otwórz aplikację jako menedżer.'})
                    return
                wynik = {'zrobione': [], 'pominiete': []}
                blad = zmien_grafik(st['data'], u, b, wynik)
                if blad:
                    self._json(400, {'error': blad})
                    return
                backup_data()
                nowy = {'rev': st.get('rev', 0) + 1, 'data': st['data'],
                        'updatedAt': int(time.time()), 'updatedBy': u['email']}
                write_json_atomic(DATA_F(), nowy)
            self._json(200, {'rev': nowy['rev'],
                             'signups': nowy['data'].get('signups', {}),
                             'staff': nowy['data'].get('staff', []),
                             'zrobione': wynik['zrobione'],
                             'pominiete': wynik['pominiete']})
            return

        if path == '/api/logout':
            self._json(200, {'ok': True}, extra=[self._cookie('', 0)])
            return

        self._json(404, {'error': 'Nie znaleziono.'})

    def do_PUT(self):
        path = self.path.split('?')[0]

        if path == '/api/data':
            u = self._user()
            if not u:
                self._json(401, {'error': 'Zaloguj się.'})
                return
            if not moze_edytowac(u):
                self._json(403, {'error': 'Twoje konto ma tylko podgląd.'})
                return
            b = self._body()
            if b is None or 'data' not in b:
                self._json(400, {'error': 'Błędne dane albo plik za duży.'})
                return
            with _lock:
                st = read_json(DATA_F(), {'rev': 0, 'data': None})
                cur = st.get('rev', 0)
                sent = b.get('rev', 0)
                if st.get('data') is not None and sent != cur:
                    self._json(409, {'error': 'Ktoś inny zapisał zmiany w międzyczasie.',
                                     'rev': cur, 'updatedBy': st.get('updatedBy'),
                                     'updatedAt': st.get('updatedAt')})
                    return
                nowe = b['data']
                backup_data()
                new = {'rev': cur + 1, 'data': nowe,
                       'updatedAt': int(time.time()), 'updatedBy': u['email']}
                write_json_atomic(DATA_F(), new)
            self._json(200, {'rev': new['rev'], 'updatedAt': new['updatedAt'],
                             'updatedBy': new['updatedBy']})
            return

        self._json(404, {'error': 'Nie znaleziono.'})


# --------------------------------------------------------------------------
# grafik zmian
# --------------------------------------------------------------------------
# Pola, które w ogóle wychodzą na konto pracownika. Reszta bazy — ceny zakupu,
# receptury, marże, faktury — nie ma z grafikiem nic wspólnego i nie ma powodu
# opuszczać serwera tylko dlatego, że ktoś dostał dostęp do zapisów na zmiany.
# Pola, w których siedzą pieniądze. Wszystko inne — gramatury, receptury, układ szafek,
# plan tygodnia — poziomom 3 i 4 jest potrzebne do pracy.
POLA_CEN = {
    'ingredients': ('packPrice',),
    'items': ('prices', 'vats', 'sheetNet', 'sheetFc'),
    'sets': ('prices', 'vats', 'sheetFc'),
}


def bez_cen(data):
    """Baza dla poziomów „pracownik" i „podgląd": wszystko oprócz pieniędzy.

    Kucharz przy blacie potrzebuje gramatur, kolejności składników i tego, ile czego
    zejdzie danego dnia. Nie potrzebuje wiedzieć, ile kosztuje kilogram łososia — a od
    tej wiedzy do rozmowy o marżach na zapleczu jest jeden krok.

    Ceny nie są tu CHOWANE w interfejsie, tylko wycinane po stronie serwera: nawet
    z konsolą przeglądarki nie da się do nich dojść, bo ich tam po prostu nie ma.
    Historia cen znika w całości — to sama tabela pieniędzy."""
    if not isinstance(data, dict):
        return data
    out = dict(data)
    for kolekcja, pola in POLA_CEN.items():
        lista = out.get(kolekcja)
        if not isinstance(lista, list):
            continue
        out[kolekcja] = [
            {k: v for k, v in poz.items() if k not in pola} if isinstance(poz, dict) else poz
            for poz in lista
        ]
    out['history'] = []
    ust = dict(out.get('settings') or {})
    for k in ('targetFc', 'alertFc', 'vats'):
        ust.pop(k, None)
    out['settings'] = ust
    return out


DNI_KOD = ('pn', 'wt', 'sr', 'cz', 'pt', 'so', 'nd')


def _iso_tydzien(dzien):
    """„2026-W33" — ten sam numer, który liczy przeglądarka. `isocalendar()`
    trzyma się ISO-8601, więc przełom roku wychodzi tak samo po obu stronach."""
    rok, nr, _ = datetime.date.fromisoformat(dzien).isocalendar()
    return '%04d-W%02d' % (rok, nr)


def _zmiany_dnia(data, dzien):
    """Zmiany obowiązujące tego dnia — z nadpisania tygodnia, a jak go nie ma,
    z szablonu. Ta sama reguła co w przeglądarce, tylko po stronie serwera."""
    nad = (data.get('shiftWeeks') or {}).get(_iso_tydzien(dzien))
    zrodlo = nad if isinstance(nad, dict) else (data.get('shiftTpl') or {})
    dzien_tyg = DNI_KOD[datetime.date.fromisoformat(dzien).weekday()]
    return [z for z in (zrodlo.get(dzien_tyg) or []) if isinstance(z, dict) and z.get('id')]


def _zmiana_dnia(data, dzien, sid):
    """Zmiana o danym id obowiązująca TEGO dnia. Nie wystarczy sprawdzić, czy takie id
    gdziekolwiek istnieje: zmiana skasowana z wtorku nie może przyjmować zapisów
    na wtorek."""
    for zm in _zmiany_dnia(data, dzien):
        if str(zm.get('id')) == sid:
            return zm
    return None


def _osoba_dla(data, email):
    """Kartoteka pracownika po e-mailu; zakłada wpis przy pierwszym zgłoszeniu,
    żeby menedżer nie musiał dublować każdego konta ręcznie."""
    data.setdefault('staff', [])
    for o in data['staff']:
        if str(o.get('email') or '').lower() == email.lower():
            return o
    o = {'id': 'os-%s' % secrets.token_hex(4), 'name': email.split('@')[0],
         'email': email, 'archived': False}
    data['staff'].append(o)
    return o


MAX_ZAPISOW = 20000


OPERACJE = ('self', 'set', 'batch')


def _wpis(data, dzien, zmiana, os_id, chce):
    """Wpisuje albo wypisuje jedną osobę z jednej zmiany.

    Zwraca True, gdy się udało. Jedyny powód niepowodzenia to brak miejsca —
    kto pierwszy, ten stoi, a gdy komplet, trzeba się z kimś dogadać."""
    klucz = '%s|%s' % (dzien, zmiana['id'])
    osoby = list((data['signups'].get(klucz) or {}).get('osoby') or [])
    if chce:
        if os_id not in osoby:
            if len(osoby) >= int(zmiana.get('slots') or 0):
                return False
            osoby.append(os_id)
    else:
        osoby = [x for x in osoby if x != os_id]
    if osoby:
        data['signups'][klucz] = {'osoby': osoby}
    else:
        data['signups'].pop(klucz, None)
    return True


def _kogo(data, u, b):
    """Kogo dotyczy operacja. Zwraca (błąd, osoba).

    W grafiku może stać wyłącznie ktoś, kto ma konto w aplikacji — nie ma osobnej
    listy nazwisk do utrzymywania i nie da się wpisać człowieka, który nigdy się nie
    zaloguje, więc i tak nie zobaczy, że ma przyjść."""
    wskazany = b.get('person')
    if not wskazany:
        return None, _osoba_dla(data, u['email'])
    if isinstance(wskazany, dict) and wskazany.get('email'):
        mail = str(wskazany['email']).strip().lower()
        if mail not in read_json(USERS_F(), {}):
            return 'Ta osoba nie ma konta w aplikacji.', None
        return None, _osoba_dla(data, mail)
    osoba = next((o for o in data['staff'] if o.get('id') == str(wskazany)), None)
    if osoba is None:
        return 'Nie ma takiej osoby na liście.', None
    return None, osoba


def dni_sprzedazy():
    """Dni, w których mamy już choć jedną sprzedaż.

    Import z archiwum i import z maili opisują tę samą rzeczywistość, ale innym kluczem —
    ten sam zakup wjechałby z obu źródeł jako dwie sprzedaże. Klucz po `Message-ID` tego
    nie złapie, bo nie ma wspólnego identyfikatora. Dlatego granicę stawiamy na dniach:
    dzień, który zna już aplikacja, archiwum pomija w całości. Dzień połowicznie
    zaimportowany zostaje więc niepełny — ale niepełny widać, a podwojony nie.
    """
    dni = set()
    if not os.path.isdir(DATA_DIR):
        return []
    for nazwa in sorted(os.listdir(DATA_DIR)):
        if not (nazwa.startswith('sprzedaz-') and nazwa.endswith('.json')):
            continue
        for w in (read_json(os.path.join(DATA_DIR, nazwa), {}) or {}).values():
            if isinstance(w, dict) and w.get('czas'):
                dni.add(time.strftime('%Y-%m-%d', time.localtime(w['czas'])))
    return sorted(dni)


def eksport_sprzedazy(data):
    """Wszystkie miesiące sprzedaży w jednym pliku, razem z kluczem do ich odczytania.

    Sama sprzedaż to numery seryjne i identyfikatory — bez listy automatów i układu
    szafek nie da się z niej nic wyczytać. Dlatego eksport niesie i jedno, i drugie:
    plik ma się tłumaczyć sam, także za rok i na cudzym komputerze.

    Automaty wypisujemy WSZYSTKIE, także archiwalne. Eksport służy do dochodzenia,
    co się stało; automat schowany po drodze jest wtedy najciekawszy.
    """
    mies = {}
    if os.path.isdir(DATA_DIR):
        for nazwa in sorted(os.listdir(DATA_DIR)):
            if nazwa.startswith('sprzedaz-') and nazwa.endswith('.json'):
                mies[nazwa[9:-5]] = read_json(os.path.join(DATA_DIR, nazwa), {}) or {}
    pole = lambda o, klucze: dict((k, o.get(k)) for k in klucze)
    return {
        'pobrano': int(time.time()),
        'wersja': wersja(),
        'automaty': [pole(m, ('id', 'code', 'name', 'addr', 'serial', 'archived'))
                     for m in (data.get('machines') or [])],
        'szafki': ((data.get('vending') or {}).get('layout') or {}),
        'zestawy': [pole(z, ('id', 'name', 'archived')) for z in (data.get('sets') or [])],
        'sprzedaz': mies,
    }


def dopasuj_sprzedaz(data):
    """Przypisuje automat i zestaw tym sprzedażom, którym się to nie udało przy przyjęciu.

    Numer seryjny bywa wpisany do automatu PÓŹNIEJ, niż przyszła pierwsza sprzedaż.
    Wtedy pieniądze leżą w koszyku „Nierozpoznane" i nie ma powodu, żeby zostały tam
    na zawsze — brakowało tylko jednej informacji, a teraz jest.

    **Rusza wyłącznie wpisy z polem `nieznane`.** Sprzedaż raz przypisana jest przypisana
    do NASZEGO identyfikatora automatu i zostaje przy nim — numer seryjny służy tylko do
    rozpoznania w chwili przyjęcia. Nie ma gwarancji, że operator nie zmieni sposobu
    wysyłania maili ani samych numerów; gdyby przypisanie szło za numerem przy każdym
    kliknięciu, taka zmiana po ich stronie przepisywałaby nam historię wstecz przez
    zamknięte miesiące. Pomyłkę w numerze prostuje się więc **zanim** sprzedaż zostanie
    przypisana, nie po.

    Z tego samego powodu zamrożony jest zestaw: uzupełniamy go tylko wtedy, gdy wpis go
    nie ma. Układ szafek zmienia się w czasie i sprzedaż sprzed miesiąca musi zostać
    przy zestawie, który wtedy w tej szafce stał.

    Do wpisu, którego dalej nie umiemy przypisać, nie dopisujemy śladu po próbie:
    ma wyglądać dokładnie tak samo jak przed kliknięciem.
    """
    wynik = {'sprawdzone': 0, 'przypisane': 0, 'zostalo': 0, 'miesiace': []}
    if not os.path.isdir(DATA_DIR):
        return wynik
    szafki = ((data.get('vending') or {}).get('layout') or {})
    for nazwa in sorted(os.listdir(DATA_DIR)):
        if not (nazwa.startswith('sprzedaz-') and nazwa.endswith('.json')):
            continue
        sciezka = os.path.join(DATA_DIR, nazwa)
        plik = read_json(sciezka, {}) or {}
        zmiana = 0
        for w in plik.values():
            if not isinstance(w, dict) or 'nieznane' not in w:
                continue
            wynik['sprawdzone'] += 1
            maszyna = _maszyna_po_numerze(data, w.get('serial'))
            zid = w.get('zestaw') or szafki.get(str(w.get('szafka')))
            if not (maszyna and zid):
                wynik['zostalo'] += 1
                continue
            w['maszyna'] = maszyna.get('id')
            w['zestaw'] = zid
            del w['nieznane']
            zmiana += 1
        if zmiana:
            write_json_atomic(sciezka, plik)
            wynik['przypisane'] += zmiana
            wynik['miesiace'].append(nazwa[9:-5])
    return wynik


def _numer(s):
    """Numer seryjny sprowadzony do znaków znaczących.

    W temacie maila numer stoi przed nazwą lokalu, oddzielony myślnikiem. Operator raz
    stawia przed tym myślnikiem spację, raz nie — i wtedy myślnik przykleja się do numeru
    (`SM-0240-26-`). To dalej ta sama maszyna. Ogranicznik na końcu napisu nie ma prawa
    decydować o tym, do kogo trafią pieniądze, więc obcinamy go po obu stronach
    porównania. Myślniki W ŚRODKU zostają: one numer budują (`SH01-100-22-24`).
    """
    return str(s or '').replace(' ', '').upper().strip('-–—_.,;:')


def _zestaw_po_nazwie(data, nazwa):
    """Zestaw rozpoznany po nazwie produktu, tak jak zapisał ją automat.

    Archiwum ELDRUT-a podaje przy sprzedaży nazwę („Duży mieszany 32 szt"), czego maile
    nie robią. Dla danych sprzed miesięcy jest ona **lepszym świadkiem niż układ szafek**:
    układ zmieniał się przez ten czas, a nazwa mówi wprost, co wtedy wyjechało.

    Dopasowujemy po przedrostku i bierzemy NAJDŁUŻSZE trafienie — nazwa z automatu niesie
    jeszcze liczbę kawałków („… 32 szt"), a przy dwóch pasujących zestawach dłuższa nazwa
    jest tą właściwą.
    """
    n = ' '.join(str(nazwa or '').lower().split())
    if not n:
        return None
    najlepszy = None
    for z in (data.get('sets') or []):
        zn = ' '.join(str(z.get('name') or '').lower().split())
        if zn and n.startswith(zn) and (najlepszy is None or len(zn) > najlepszy[0]):
            najlepszy = (len(zn), z.get('id'))
    return najlepszy[1] if najlepszy else None


def _maszyna_po_numerze(data, serial):
    s = _numer(serial)
    if not s:
        return None
    for m in (data.get('machines') or []):
        if _numer(m.get('serial')) == s:
            return m
    return None


def przyjmij_sprzedaz(data, pozycje):
    """Dopisuje sprzedaże do plików miesięcznych. Zwraca podsumowanie.

    Pozycja z n8n: {msgId, serial, szafka, kwota, czas}. Wszystko poza tym — nazwę
    automatu, zestaw, cenę katalogową — dokładamy tutaj, w chwili przyjęcia.

    Czego NIE odrzucamy: sprzedaży z nieznanego numeru seryjnego ani z szafki bez
    przypisanego zestawu. Takie wpisy zostają z powodem w polu `nieznane` — sprzedaż
    naprawdę się wydarzyła i pieniądze naprawdę wpłynęły, więc wyrzucenie jej dlatego,
    że my czegoś nie wiemy, byłoby zamiataniem problemu pod dywan. Widać je na ekranie.
    """
    wynik = {'przyjete': 0, 'powtorzone': 0, 'nieznane': 0, 'odrzucone': []}
    if not isinstance(pozycje, list):
        return None, 'Oczekiwano listy sprzedaży.'
    if len(pozycje) > 5000:
        return None, 'Za dużo pozycji naraz — najwyżej 5000.'

    # Grupujemy po miesiącu, żeby każdy plik otworzyć i zapisać RAZ, a nie raz na sprzedaż.
    # Przy zaciąganiu całej skrzynki wstecz to różnica między jednym zapisem a tysiącem.
    wg_miesiaca = {}
    for p in pozycje:
        if not isinstance(p, dict):
            wynik['odrzucone'].append('pozycja nie jest obiektem')
            continue
        mid = str(p.get('msgId') or '').strip()
        if not mid:
            wynik['odrzucone'].append('brak Message-ID')
            continue
        try:
            czas = int(p.get('czas'))
        except (TypeError, ValueError):
            wynik['odrzucone'].append(mid + ': brak czasu')
            continue
        ym = time.strftime('%Y-%m', time.localtime(czas))
        wg_miesiaca.setdefault(ym, []).append((mid, czas, p))

    for ym, lista in wg_miesiaca.items():
        plik = read_json(SPRZEDAZ_F(ym), {}) or {}
        zmiana = False
        for mid, czas, p in lista:
            if mid in plik:
                wynik['powtorzone'] += 1
                continue
            serial = str(p.get('serial') or '').strip()
            # Jeden mail potrafi zaraportować DWIE szafki naraz („z szafek 1, 15") —
            # to jeden klient, który zapłacił raz za dwa zestawy. Kwota jest wtedy
            # wspólna i nie da się jej rozdzielić bez cen z załadunku, więc na razie
            # liczy się przy PIERWSZEJ szafce z listy. Całą listę zapisujemy obok:
            # bez niej nie dałoby się tego później rozliczyć, a i nie byłoby wiadomo,
            # że sprzedaż w ogóle była zbiorcza.
            szafki = []
            for x in (p.get('szafki') if isinstance(p.get('szafki'), list) else [p.get('szafka')]):
                try:
                    szafki.append(int(x))
                except (TypeError, ValueError):
                    pass
            szafka = szafki[0] if szafki else None
            try:
                kwota = round(float(p.get('kwota')), 2)
            except (TypeError, ValueError):
                kwota = None

            wpis = {'czas': czas, 'serial': serial, 'szafka': szafka, 'kwota': kwota}
            if len(szafki) > 1:
                wpis['szafki'] = szafki
            nazwa = ' '.join(str(p.get('nazwa') or '').split())
            if nazwa:
                wpis['nazwa'] = nazwa
            maszyna = _maszyna_po_numerze(data, serial)
            if maszyna:
                wpis['maszyna'] = maszyna.get('id')
            else:
                wpis['nieznane'] = 'nieznany numer seryjny'

            # Zestaw: najpierw po nazwie z archiwum, bo ta pochodzi z chwili sprzedaży;
            # dopiero gdy jej nie ma — z układu szafek OBOWIĄZUJĄCEGO TERAZ. Tak czy tak
            # zapisujemy go na stałe.
            zid = (_zestaw_po_nazwie(data, nazwa)
                   or ((data.get('vending') or {}).get('layout') or {}).get(str(szafka)))
            if zid:
                wpis['zestaw'] = zid
            elif 'nieznane' not in wpis:
                wpis['nieznane'] = 'szafka bez przypisanego zestawu'

            if 'nieznane' in wpis:
                wynik['nieznane'] += 1
            plik[mid] = wpis
            wynik['przyjete'] += 1
            zmiana = True
        if zmiana:
            write_json_atomic(SPRZEDAZ_F(ym), plik)
    return wynik, None


ZDARZENIA = ('wyjazd', 'automat')
MAX_ZDARZEN = 20000          # ~7 wpisow dziennie przez osiem lat; hamulec na zapetlenie


def klucz_zdarzenia(dzien, rodzaj, mid):
    """Ten sam wzór co w zapisach grafiku: dzień, pion, reszta. Płaski klucz zamiast
    zagnieżdżonych obiektów, bo dzięki temu każda operacja rusza dokładnie jeden wiersz
    i dwa równoczesne zapisy nie mają jak się nadpisać."""
    return dzien + '|' + rodzaj + (('|' + mid) if rodzaj == 'automat' else '')


def zmien_zdarzenie(data, u, b):
    """Rejestracja wyjazdu z kuchni albo zatowarowania jednego automatu.

    Jedno zdarzenie na dzień: samochód wyjeżdża raz, każdy automat jest zatowarowany raz.
    Powtórzone kliknięcie nie jest błędem — po prostu nic nie zmienia.

    Czas bierzemy z zegara serwera. To ma być zapis tego, o której naprawdę wyjechano,
    a nie tego, co pokazywał telefon kierowcy.

    Zwraca komunikat błędu albo None."""
    rodzaj = str(b.get('rodzaj') or '')
    if rodzaj not in ZDARZENIA:
        return 'Nieznane zdarzenie.'

    dzien = str(b.get('date') or '')
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', dzien):
        return 'Błędna data.'
    try:
        datetime.date.fromisoformat(dzien)
    except ValueError:
        return 'Błędna data.'
    # Wyjazdu, którego jeszcze nie było, nie da się zarejestrować. Wstecz owszem —
    # ktoś mógł zapomnieć kliknąć, a data i godzina stempla i tak powiedzą prawdę.
    if dzien > time.strftime('%Y-%m-%d'):
        return 'Ten dzień jeszcze nie nadszedł.'

    mid = str(b.get('machine') or '')
    if rodzaj == 'automat':
        if not re.match(r'^[A-Za-z0-9_-]{1,40}$', mid):
            return 'Błędny identyfikator automatu.'
        if not any(m.get('id') == mid for m in (data.get('machines') or [])):
            return 'Nie ma takiego automatu.'

    data.setdefault('zdarzenia', {})
    klucz = klucz_zdarzenia(dzien, rodzaj, mid)
    osoba = _osoba_dla(data, u['email'])

    if b.get('on'):
        if klucz in data['zdarzenia']:
            return None                      # już zarejestrowane — powtórka to nie błąd
        if len(data['zdarzenia']) >= MAX_ZDARZEN:
            return 'Rejestr jest przepełniony.'
        data['zdarzenia'][klucz] = {'osoba': osoba['id'], 'czas': int(time.time())}
        return None

    wpis = data['zdarzenia'].get(klucz)
    if not wpis:
        return None                          # nie ma czego cofać
    # Swoje cofa każdy, cudze — właściciel albo administrator. Ta sama zasada,
    # co przy krzyżyku obok plakietki w grafiku.
    if wpis.get('osoba') != osoba['id'] and not moze_grafik(u):
        return 'To nie twój wpis — cofnie go właściciel albo administrator.'
    data['zdarzenia'].pop(klucz, None)
    return None


def zmien_grafik(data, u, b, wynik):
    """Operacja na zapisach: własny wpis, cudzy albo wiele dni naraz.

    Wszystko, co dotyczy zapisów, przechodzi tędy — także z konta układającego grafik.
    Dzięki temu wpis pracownika nie unieważnia stanu jego strony: każda odpowiedź
    oddaje nowy `rev`, a operacje nie nadpisują się nawzajem, bo każda rusza tylko
    swój wiersz. Szablon zmian i kartoteka jadą zwykłym zapisem bazy.

    Zwraca komunikat błędu albo None; szczegóły wykonania dopisuje do `wynik`."""
    op = str(b.get('op') or 'self')
    chce = bool(b.get('on'))
    grafikowy = moze_grafik(u)

    if op not in OPERACJE:
        return 'Nieznana operacja.'
    # `person` wskazuje kogoś innego; bez niego operacja dotyczy tego, kto ją wysłał —
    # a swój wpis, choćby na czterdziestu dniach, każdy stawia sam
    if b.get('person') and not grafikowy:
        return 'Nie masz uprawnienia do układania grafiku.'

    data.setdefault('signups', {})
    data.setdefault('staff', [])
    if chce and len(data['signups']) >= MAX_ZAPISOW:
        return 'Grafik jest przepełniony — odezwij się do osoby układającej grafik.'

    blad, osoba = _kogo(data, u, b)
    if blad:
        return blad

    dzis = time.strftime('%Y-%m-%d')

    # --- wiele dni naraz: po NAZWIE zmiany, bo identyfikator bywa inny w każdym tygodniu
    if op == 'batch':
        dni = b.get('days')
        if not isinstance(dni, list) or not dni:
            return 'Nie zaznaczono żadnego dnia.'
        if len(dni) > 200:
            return 'Za dużo dni naraz — zaznacz najwyżej 200.'
        nazwa = str(b.get('shiftName') or '').strip()
        if not nazwa:
            return 'Nie podano zmiany.'
        for dzien in dni:
            dzien = str(dzien)
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', dzien):
                return 'Błędna data.'
            try:
                datetime.date.fromisoformat(dzien)
            except ValueError:
                return 'Błędna data.'
            if chce and not grafikowy and dzien < dzis:
                wynik['pominiete'].append(dzien)
                continue
            zmiana = next((z for z in _zmiany_dnia(data, dzien) if z.get('name') == nazwa), None)
            if zmiana is None or not _wpis(data, dzien, zmiana, osoba['id'], chce):
                wynik['pominiete'].append(dzien)
            else:
                wynik['zrobione'].append(dzien)
        return None

    # --- pojedynczy dzień
    dzien = str(b.get('date') or '')
    sid = str(b.get('shift') or '')
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', dzien):
        return 'Błędna data.'
    try:
        datetime.date.fromisoformat(dzien)
    except ValueError:
        return 'Błędna data.'
    # grafik bywa uzupełniany po fakcie, więc wstecz może poprawiać ten, kto go układa
    if not grafikowy and dzien < dzis:
        return 'Ten dzień już minął.'
    if not re.match(r'^[A-Za-z0-9_-]{1,40}$', sid):
        return 'Błędny identyfikator zmiany.'
    zmiana = _zmiana_dnia(data, dzien, sid)
    if zmiana is None:
        return 'Tego dnia nie ma takiej zmiany.'
    if not _wpis(data, dzien, zmiana, osoba['id'], chce):
        return 'Na tej zmianie nie ma już wolnego miejsca.'
    wynik['zrobione'].append(dzien)
    return None


# --------------------------------------------------------------------------
# komendy
# --------------------------------------------------------------------------
def cmd_init(_a):
    ensure_dirs()
    secret()
    print('Katalog danych: ' + DATA_DIR)
    print('Klucz sesji utworzony.')
    if not read_json(USERS_F(), {}):
        print('\nNie ma jeszcze żadnego konta. Dodaj pierwsze:')
        print('  python3 server.py adduser twoj@email.pl owner')


def _set_password(email, role=None):
    users = read_json(USERS_F(), {})
    p1 = getpass.getpass('Hasło: ')
    if len(p1) < 8:
        print('Hasło musi mieć co najmniej 8 znaków.')
        return False
    if p1 != getpass.getpass('Powtórz hasło: '):
        print('Hasła się różnią.')
        return False
    entry = users.get(email, {})
    entry['pw'] = hash_pw(p1)
    if role:
        entry['role'] = role
    entry.setdefault('role', 'viewer')
    users[email] = entry
    write_json_atomic(USERS_F(), users)
    try:
        os.chmod(USERS_F(), 0o600)
    except OSError:
        pass
    return True


def cmd_adduser(a):
    if a.role not in ROLES:
        print('Rola musi być jedną z: ' + ', '.join(ROLES))
        sys.exit(1)
    email = a.email.strip().lower()
    ensure_dirs()
    if _set_password(email, a.role):
        print('Dodano konto %s (rola: %s).' % (email, a.role))


def cmd_passwd(a):
    email = a.email.strip().lower()
    users = read_json(USERS_F(), {})
    if email not in users:
        print('Nie ma takiego konta.')
        sys.exit(1)
    if _set_password(email):
        print('Hasło zmienione.')


def cmd_deluser(a):
    email = a.email.strip().lower()
    users = read_json(USERS_F(), {})
    if users.pop(email, None) is None:
        print('Nie ma takiego konta.')
        sys.exit(1)
    write_json_atomic(USERS_F(), users)
    print('Usunięto konto %s.' % email)


def cmd_token(a):
    print(token_sprzedazy(nowy=a.nowy))
    if a.nowy:
        print('\nStary klucz przestał działać — wpisz nowy w n8n.', file=sys.stderr)


def cmd_sprzedaz(a):
    """Odkłada wszystkie pliki sprzedaży do kopii i zostawia puste miejsce.

    Potrzebne raz: po poprawieniu odczytu numerów seryjnych import trzeba było
    przeprowadzić od nowa. Klucz po `Message-ID` pilnuje, żeby ten sam mail nie wszedł
    dwa razy — i dlatego bez wyczyszczenia stare, źle odczytane wpisy zostałyby na
    zawsze. Nic nie kasujemy bezpowrotnie: pliki lądują w katalogu kopii.
    """
    ensure_dirs()
    pliki = sorted(n for n in os.listdir(DATA_DIR)
                   if n.startswith('sprzedaz-') and n.endswith('.json'))
    if not pliki:
        print('Nie ma czego czyścić — żadnego pliku sprzedaży.')
        return
    if not a.wyczysc:
        print('Pliki sprzedaży (%d):' % len(pliki))
        for n in pliki:
            print('  %-24s %8d B  %d pozycji'
                  % (n, os.path.getsize(os.path.join(DATA_DIR, n)),
                     len(read_json(os.path.join(DATA_DIR, n), {}) or {})))
        print('\nAby je odłożyć do kopii i zacząć import od nowa: sushi sprzedaz --wyczysc')
        return
    kat = os.path.join(BACKUP_D(), 'sprzedaz-' + time.strftime('%Y%m%d-%H%M%S'))
    os.makedirs(kat)
    for n in pliki:
        os.rename(os.path.join(DATA_DIR, n), os.path.join(kat, n))
    print('Odłożono %d plików do %s' % (len(pliki), kat))
    print('Sprzedaż jest teraz pusta — puść import w n8n od nowa.')


def cmd_users(_a):
    users = read_json(USERS_F(), {})
    if not users:
        print('Brak kont.')
        return
    for e, u in sorted(users.items()):
        print('%-34s %s' % (e, u.get('role', 'viewer')))


class DualStackServer(ThreadingHTTPServer):
    """Nasłuch na IPv4 i IPv6 jednocześnie — subdomeny mikrus.cloud wymagają IPv6."""
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def cmd_run(a):
    ensure_dirs()
    secret()
    migruj_role()
    if not read_json(USERS_F(), {}):
        print('UWAGA: nie ma żadnego konta. Dodaj je komendą "adduser", '
              'inaczej nikt się nie zaloguje.', file=sys.stderr)
    if a.host in ('0.0.0.0', '::'):
        try:
            srv = DualStackServer(('::', a.port), Handler)
        except OSError:                       # system bez IPv6 — schodzimy do IPv4
            srv = ThreadingHTTPServer(('0.0.0.0', a.port), Handler)
    else:
        srv = ThreadingHTTPServer((a.host, a.port), Handler)
    srv.daemon_threads = True
    print('Sushi Planner słucha na http://%s:%d  (dane: %s)' % (a.host, a.port, DATA_DIR))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nZatrzymano.')


def main():
    p = argparse.ArgumentParser(description='Sushi Planner — serwer')
    sub = p.add_subparsers(dest='cmd')

    sub.add_parser('init', help='utwórz katalog danych i klucz sesji').set_defaults(fn=cmd_init)

    q = sub.add_parser('adduser', help='dodaj konto')
    q.add_argument('email')
    q.add_argument('role', nargs='?', default='staff', choices=list(ROLES))
    q.set_defaults(fn=cmd_adduser)

    q = sub.add_parser('passwd', help='zmień hasło')
    q.add_argument('email')
    q.set_defaults(fn=cmd_passwd)

    q = sub.add_parser('deluser', help='usuń konto')
    q.add_argument('email')
    q.set_defaults(fn=cmd_deluser)

    sub.add_parser('users', help='lista kont').set_defaults(fn=cmd_users)

    q = sub.add_parser('sprzedaz', help='pliki sprzedaży: podgląd i czyszczenie')
    q.add_argument('--wyczysc', action='store_true',
                   help='odłóż wszystkie pliki sprzedaży do kopii i zacznij od zera')
    q.set_defaults(fn=cmd_sprzedaz)

    q = sub.add_parser('token', help='klucz dla n8n do wysyłania sprzedaży')
    q.add_argument('--nowy', action='store_true', help='wygeneruj nowy i unieważnij stary')
    q.set_defaults(fn=cmd_token)

    q = sub.add_parser('run', help='uruchom serwer')
    q.add_argument('--port', type=int, default=int(os.environ.get('PORT', 8080)))
    q.add_argument('--host', default='0.0.0.0')
    q.set_defaults(fn=cmd_run)

    a = p.parse_args()
    if not getattr(a, 'fn', None):
        p.print_help()
        sys.exit(1)
    a.fn(a)


if __name__ == '__main__':
    main()
