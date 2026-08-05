#!/usr/bin/env python3
"""
Sushi Planner — serwer.

Zero zależności zewnętrznych: tylko biblioteka standardowa Pythona 3.8+.
Zużycie pamięci ~20 MB, więc mieści się nawet na Mikrusie 1.0 (384 MB RAM).

Użycie:
    python3 server.py init                      # katalog danych + klucz sesji
    python3 server.py adduser szef@lokal.pl owner
    python3 server.py adduser kuchnia@lokal.pl chef
    python3 server.py users                     # lista kont
    python3 server.py passwd szef@lokal.pl      # zmiana hasła
    python3 server.py deluser kuchnia@lokal.pl
    python3 server.py run --port 30123          # uruchomienie

Role:
    owner   — pełna edycja + zarządzanie danymi
    chef    — pełna edycja
    viewer  — tylko podgląd receptur i gramatur
"""

import argparse
import base64
import io
import getpass
import hashlib
import hmac
import json
import os
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
ROLES = ('owner', 'chef', 'viewer')

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
            if u['role'] != 'owner':
                self._json(403, {'error': 'Tylko właściciel widzi konta.'})
                return
            users = read_json(USERS_F(), {})
            lista = [{'email': e, 'role': v.get('role', 'viewer'), 'created': v.get('created')}
                     for e, v in sorted(users.items())]
            self._json(200, {'users': lista})
            return

        if path in ('/api/update/check', '/api/update/status'):
            u = self._user()
            if not u:
                self._json(401, {'error': 'Zaloguj się.'})
                return
            if u['role'] != 'owner':
                self._json(403, {'error': 'Tylko właściciel może aktualizować.'})
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

        if path == '/api/data':
            u = self._user()
            if not u:
                self._json(401, {'error': 'Zaloguj się.'})
                return
            with _lock:
                st = read_json(DATA_F(), {'rev': 0, 'data': None, 'updatedAt': None, 'updatedBy': None})
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
            if u['role'] != 'owner':
                self._json(403, {'error': 'Tylko właściciel zarządza kontami.'})
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
            if u['role'] != 'owner':
                self._json(403, {'error': 'Tylko właściciel może aktualizować.'})
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
            if u['role'] not in ('owner', 'chef'):
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
                backup_data()
                new = {'rev': cur + 1, 'data': b['data'],
                       'updatedAt': int(time.time()), 'updatedBy': u['email']}
                write_json_atomic(DATA_F(), new)
            self._json(200, {'rev': new['rev'], 'updatedAt': new['updatedAt'],
                             'updatedBy': new['updatedBy']})
            return

        self._json(404, {'error': 'Nie znaleziono.'})


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
    q.add_argument('role', nargs='?', default='chef', choices=list(ROLES))
    q.set_defaults(fn=cmd_adduser)

    q = sub.add_parser('passwd', help='zmień hasło')
    q.add_argument('email')
    q.set_defaults(fn=cmd_passwd)

    q = sub.add_parser('deluser', help='usuń konto')
    q.add_argument('email')
    q.set_defaults(fn=cmd_deluser)

    sub.add_parser('users', help='lista kont').set_defaults(fn=cmd_users)

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
