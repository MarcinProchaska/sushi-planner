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
import getpass
import hashlib
import hmac
import json
import os
import secrets
import shutil
import socket
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('SUSHI_DATA', os.path.join(BASE, 'data'))
INDEX = os.path.join(BASE, 'sushi-planner.html')


def version():
    """Wersja z pliku VERSION + skrót commita odczytany wprost z .git (bez wołania gita)."""
    ver = 'dev'
    try:
        with open(os.path.join(BASE, 'VERSION'), encoding='utf-8') as f:
            ver = f.read().strip() or 'dev'
    except OSError:
        pass
    sha = ''
    try:
        with open(os.path.join(BASE, '.git', 'HEAD'), encoding='utf-8') as f:
            head = f.read().strip()
        if head.startswith('ref:'):
            ref = head.split(' ', 1)[1].strip()
            rp = os.path.join(BASE, '.git', ref)
            if os.path.exists(rp):
                with open(rp, encoding='utf-8') as f:
                    sha = f.read().strip()[:7]
            else:                                   # spakowane referencje
                with open(os.path.join(BASE, '.git', 'packed-refs'), encoding='utf-8') as f:
                    for line in f:
                        if line.rstrip().endswith(' ' + ref):
                            sha = line.split(' ', 1)[0][:7]
                            break
        else:
            sha = head[:7]
    except OSError:
        pass
    return {'version': ver, 'commit': sha}

USERS_F = lambda: os.path.join(DATA_DIR, 'users.json')
DATA_F = lambda: os.path.join(DATA_DIR, 'data.json')
SECRET_F = lambda: os.path.join(DATA_DIR, 'secret')
BACKUP_D = lambda: os.path.join(DATA_DIR, 'backup')

MAX_BODY = 32 * 1024 * 1024        # 32 MB — z zapasem na zdjęcia
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
# HTTP
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = 'SushiPlanner'
    sys_version = ''
    protocol_version = 'HTTP/1.1'

    def handle_one_request(self):
        # ten sam obiekt obsługuje wszystkie żądania na jednym połączeniu,
        # więc flagę trzeba zerować przy każdym z osobna
        self._body_done = False
        return BaseHTTPRequestHandler.handle_one_request(self)

    # ---- pomocnicze ----
    def _drain(self):
        """Dokończ czytanie treści żądania.

        Przy HTTP/1.1 połączenie jest trzymane otwarte. Jeśli odpowiemy błędem
        (401/403/400) nie wyczytawszy body, jego resztka zostaje w buforze gniazda
        i serwer weźmie ją za początek kolejnego żądania — następne zapytanie
        z tej samej karty dostaje wtedy 400. Dlatego opróżniamy bufor zawsze.
        """
        if getattr(self, '_body_done', False):
            return
        self._body_done = True
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except (TypeError, ValueError):
            return
        while n > 0:
            chunk = self.rfile.read(min(n, 65536))
            if not chunk:
                break
            n -= len(chunk)

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
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except (TypeError, ValueError):
            n = 0
        if n > MAX_BODY:
            # za duże, żeby czytać do pamięci — zamykamy połączenie zamiast opróżniać
            self._body_done = True
            self.close_connection = True
            return None
        self._body_done = True
        raw = self.rfile.read(n) if n else b'{}'
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

    def _owner(self):
        """Zwraca użytkownika tylko gdy jest właścicielem; inaczej sam odpowiada błędem."""
        u = self._user()
        if not u:
            self._json(401, {'error': 'Zaloguj się.'})
            return None
        if u['role'] != 'owner':
            self._json(403, {'error': 'Tylko właściciel może zarządzać kontami.'})
            return None
        return u

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
            self._json(200, dict({'ok': True, 'time': int(time.time())}, **version()))
            return

        if path == '/api/me':
            u = self._user()
            info = {'mode': 'server', 'user': u}
            info.update(version())
            self._json(200 if u else 401, info)
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

        if path == '/api/users':
            if not self._owner():
                return
            users = read_json(USERS_F(), {})
            out = [{'email': e, 'role': u.get('role', 'viewer'), 'created': u.get('created')}
                   for e, u in sorted(users.items())]
            self._json(200, {'users': out})
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

        if path == '/api/logout':
            self._json(200, {'ok': True}, extra=[self._cookie('', 0)])
            return

        if path in ('/api/users', '/api/users/update', '/api/users/delete'):
            me = self._owner()
            if not me:
                return
            b = self._body()
            if b is None:
                self._json(400, {'error': 'Błędne dane.'})
                return
            email = str(b.get('email', '')).strip().lower()
            if not email or '@' not in email:
                self._json(400, {'error': 'Podaj poprawny adres e-mail.'})
                return

            with _lock:
                users = read_json(USERS_F(), {})

                if path == '/api/users':                       # nowe konto
                    if email in users:
                        self._json(409, {'error': 'Konto o tym adresie już istnieje.'})
                        return
                    role = b.get('role', 'chef')
                    pw = str(b.get('password', ''))
                    if role not in ROLES:
                        self._json(400, {'error': 'Nieprawidłowa rola.'})
                        return
                    if len(pw) < 8:
                        self._json(400, {'error': 'Hasło musi mieć co najmniej 8 znaków.'})
                        return
                    users[email] = {'pw': hash_pw(pw), 'role': role, 'created': int(time.time())}

                elif path == '/api/users/update':              # zmiana roli lub hasła
                    if email not in users:
                        self._json(404, {'error': 'Nie ma takiego konta.'})
                        return
                    if 'role' in b and b['role']:
                        if b['role'] not in ROLES:
                            self._json(400, {'error': 'Nieprawidłowa rola.'})
                            return
                        if email == me['email'] and b['role'] != 'owner':
                            self._json(400, {'error': 'Nie możesz odebrać uprawnień samemu sobie.'})
                            return
                        users[email]['role'] = b['role']
                    if b.get('password'):
                        if len(str(b['password'])) < 8:
                            self._json(400, {'error': 'Hasło musi mieć co najmniej 8 znaków.'})
                            return
                        users[email]['pw'] = hash_pw(str(b['password']))

                else:                                          # usunięcie
                    if email not in users:
                        self._json(404, {'error': 'Nie ma takiego konta.'})
                        return
                    if email == me['email']:
                        self._json(400, {'error': 'Nie możesz usunąć własnego konta.'})
                        return
                    del users[email]

                write_json_atomic(USERS_F(), users)
                try:
                    os.chmod(USERS_F(), 0o600)
                except OSError:
                    pass

            self._json(200, {'ok': True})
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
    entry.setdefault('created', int(time.time()))
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
    v = version()
    print('Sushi Planner %s%s słucha na http://%s:%d  (dane: %s)'
          % (v['version'], (' ' + v['commit']) if v['commit'] else '', a.host, a.port, DATA_DIR))
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
