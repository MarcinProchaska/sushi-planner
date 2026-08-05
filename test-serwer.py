"""Test end-to-end trybu serwerowego: logowanie, zapis, konflikt, rola podglądu, restart."""
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

BASE = '/root/sushi-planner'
DATA = '/tmp/sp-data'
FAIL = []


def check(name, cond, extra=''):
    print(('  OK   ' if cond else '  FAIL ') + name + (('  -> ' + str(extra)) if extra and not cond else ''))
    if not cond:
        FAIL.append(name)


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def run(*args, stdin=None):
    env = dict(os.environ, SUSHI_DATA=DATA)
    return subprocess.run([sys.executable, f'{BASE}/server.py', *args],
                          input=stdin, capture_output=True, text=True, env=env, timeout=60)


# --- podstawiony Gotenberg: nie mamy go w sandboksie, a sprawdzić chcemy
#     to, co pisze serwer: czy wysyła index.html i czy oddaje bajty dalej ---
GOTEN = {'body': b'', 'ctype': '', 'calls': 0}

class FakeGoten(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        GOTEN['body'] = self.rfile.read(n)
        GOTEN['ctype'] = self.headers.get('Content-Type', '')
        GOTEN['calls'] += 1
        if self.path != '/forms/chromium/convert/html':
            self.send_response(404); self.send_header('Content-Length', '0'); self.end_headers(); return
        pdf = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
        self.send_response(200)
        self.send_header('Content-Type', 'application/pdf')
        self.send_header('Content-Length', str(len(pdf)))
        self.end_headers()
        self.wfile.write(pdf)
    def log_message(self, *a): pass

GOTEN_PORT = free_port()
_goten = ThreadingHTTPServer(('127.0.0.1', GOTEN_PORT), FakeGoten)
threading.Thread(target=_goten.serve_forever, daemon=True).start()
GOTEN_URL = 'http://127.0.0.1:%d' % GOTEN_PORT


def start(port):
    env = dict(os.environ, SUSHI_DATA=DATA, SUSHI_GOTENBERG=GOTEN_URL)
    p = subprocess.Popen([sys.executable, f'{BASE}/server.py', 'run', '--port', str(port),
                          '--host', '127.0.0.1'], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            s = socket.create_connection(('127.0.0.1', port), 0.3)
            s.close()
            return p
        except OSError:
            time.sleep(0.1)
    raise RuntimeError('serwer nie wystartował')


shutil.rmtree(DATA, ignore_errors=True)

print('\n== KONFIGURACJA SERWERA ==')
r = run('init')
check('init tworzy katalog danych', os.path.isdir(DATA) and os.path.exists(f'{DATA}/secret'), r.stderr)
r = run('adduser', 'szef@lokal.pl', 'owner', stdin='tajnehaslo1\ntajnehaslo1\n')
check('dodanie właściciela', 'Dodano konto' in r.stdout, r.stdout + r.stderr)
r = run('adduser', 'kuchnia@lokal.pl', 'chef', stdin='tajnehaslo2\ntajnehaslo2\n')
check('dodanie kucharza', 'Dodano konto' in r.stdout, r.stdout + r.stderr)
r = run('adduser', 'podglad@lokal.pl', 'viewer', stdin='tajnehaslo3\ntajnehaslo3\n')
check('dodanie konta podglądu', 'Dodano konto' in r.stdout, r.stdout + r.stderr)
r = run('adduser', 'zly@lokal.pl', 'chef', stdin='krotkie\nkrotkie\n')
check('odrzucenie zbyt krótkiego hasła', 'co najmniej 8' in r.stdout, r.stdout)
r = run('users')
check('lista kont pokazuje 3 konta', r.stdout.count('@lokal.pl') == 3, r.stdout)
check('plik haseł ma prawa 600', oct(os.stat(f'{DATA}/users.json').st_mode)[-3:] == '600')
users = json.load(open(f'{DATA}/users.json'))
check('hasło nie jest zapisane jawnie',
      all('tajnehaslo' not in json.dumps(u) for u in users.values()))

PORT = free_port()
proc = start(PORT)
URL = f'http://127.0.0.1:{PORT}'

try:
    with sync_playwright() as p:
        br = p.chromium.launch()

        print('\n== LOGOWANIE ==')
        ctx = br.new_context()
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(URL)
        pg.wait_for_timeout(900)
        check('ekran logowania po wejściu', pg.locator('#loginForm').is_visible())
        check('dane niedostępne bez logowania', pg.locator('.main h1').count() == 0
              or not pg.locator('#loginWrap').is_hidden())

        pg.fill('#lgMail', 'szef@lokal.pl')
        pg.fill('#lgPass', 'zle-haslo')
        pg.click('#lgBtn')
        pg.wait_for_timeout(900)
        check('złe hasło odrzucone', 'Nieprawidłowy' in pg.locator('#lgErr').inner_text(),
              pg.locator('#lgErr').inner_text())

        pg.fill('#lgPass', 'tajnehaslo1')
        pg.click('#lgBtn')
        pg.wait_for_timeout(1500)
        check('logowanie właściciela', pg.locator('#loginWrap').count() == 0)
        check('widok startowy po zalogowaniu',
              pg.locator('h1').first.inner_text() == 'Pulpit',
              pg.locator('h1').first.inner_text())
        check('plakietka pokazuje serwer', 'serwer' in pg.locator('#syncBadge').inner_text(),
              pg.locator('#syncBadge').inner_text())
        check('dane z arkusza zasiane na serwer', os.path.exists(f'{DATA}/data.json'))
        st = json.load(open(f'{DATA}/data.json'))
        check('serwer ma komplet danych',
              len(st['data']['ingredients']) == 49 and len(st['data']['sets']) == 13,
              (len(st['data']['ingredients']), len(st['data']['sets'])))
        check('zapisano autora zmiany', st['updatedBy'] == 'szef@lokal.pl', st['updatedBy'])

        print('\n== ZAPIS NA SERWER ==')
        rev0 = pg.evaluate('() => SRV.rev')
        pg.click('.nav[data-v="ing"]')
        pg.wait_for_timeout(300)
        pg.fill('#ingQ', 'Łosoś')
        pg.wait_for_timeout(300)
        pg.click('button[data-edit-ing="losos"]')
        pg.wait_for_timeout(300)
        pg.fill('#fPrice', '99.9')
        pg.click('#dlgFoot button:has-text("Zapisz")')
        pg.wait_for_timeout(1800)
        st = json.load(open(f'{DATA}/data.json'))
        saved = [g for g in st['data']['ingredients'] if g['id'] == 'losos'][0]['packPrice']
        check('zmiana ceny trafiła na serwer', abs(saved - 99.9) < 0.001, saved)
        check('numer wersji wzrósł', pg.evaluate('() => SRV.rev') > rev0)
        check('powstała kopia zapasowa', len(os.listdir(f'{DATA}/backup')) >= 1)

        print('\n== DRUGI UŻYTKOWNIK WIDZI ZMIANY ==')
        ctx2 = br.new_context()
        pg2 = ctx2.new_page()
        pg2.goto(URL)
        pg2.wait_for_timeout(700)
        pg2.fill('#lgMail', 'kuchnia@lokal.pl')
        pg2.fill('#lgPass', 'tajnehaslo2')
        pg2.click('#lgBtn')
        pg2.wait_for_timeout(1500)
        price2 = pg2.evaluate("() => CALC.ing('losos').packPrice")
        check('kucharz widzi cenę zapisaną przez właściciela', abs(price2 - 99.9) < 0.001, price2)

        print('\n== KONFLIKT DWÓCH SESJI ==')
        # kucharz zapisuje, właściciel ma nieaktualną wersję i próbuje nadpisać
        pg2.evaluate("() => { CALC.ing('ryz').packPrice = 111; save(); }")
        pg2.wait_for_timeout(1500)
        pg.on('dialog', lambda d: d.accept())      # OK = wczytaj wersję z serwera
        pg.evaluate("() => { SRV.rev = 1; CALC.ing('nori').packPrice = 12345; save(); }")
        pg.wait_for_timeout(2500)
        st = json.load(open(f'{DATA}/data.json'))
        ryz = [g for g in st['data']['ingredients'] if g['id'] == 'ryz'][0]['packPrice']
        nori = [g for g in st['data']['ingredients'] if g['id'] == 'nori'][0]['packPrice']
        check('zapis kucharza nie został zdeptany', abs(ryz - 111) < 0.001, ryz)
        check('nadpisanie odrzucone (wybrano wersję z serwera)', abs(nori - 49.5) < 0.001, nori)

        print('\n== ROLA: TYLKO PODGLĄD ==')
        ctx3 = br.new_context()
        pg3 = ctx3.new_page()
        pg3.goto(URL)
        pg3.wait_for_timeout(700)
        pg3.fill('#lgMail', 'podglad@lokal.pl')
        pg3.fill('#lgPass', 'tajnehaslo3')
        pg3.click('#lgBtn')
        pg3.wait_for_timeout(1500)
        check('podgląd widzi dane', pg3.evaluate("() => DB.items.length") >= 23)
        check('plakietka pokazuje podgląd', 'podgląd' in pg3.locator('#syncBadge').inner_text(),
              pg3.locator('#syncBadge').inner_text())
        pg3.click('.nav[data-v="ing"]')
        pg3.wait_for_timeout(400)
        vis = pg3.locator('button[data-edit-ing]:visible').count()
        check('przyciski edycji ukryte dla podglądu', vis == 0, vis)
        # próba zapisu z pominięciem interfejsu — serwer musi odmówić
        code = pg3.evaluate("""async () => {
          const r = await fetch('/api/data',{method:'PUT',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({rev:SRV.rev, data:DB})});
          return r.status;
        }""")
        check('serwer odrzuca zapis od konta podglądu (403)', code == 403, code)

        print('\n== PDF Z RECEPTURAMI ==')
        pg.click('.nav[data-v="items"]')
        pg.wait_for_timeout(400)
        check('przycisk PDF w widoku rolek', pg.locator('[data-act="pdfItems"]').count() == 1)
        przed = GOTEN['calls']
        with pg.expect_download(timeout=20000) as dl:
            pg.click('[data-act="pdfItems"]')
        plik = dl.value
        check('plik nazwany po zawartości', plik.suggested_filename == 'receptury-rolek.pdf',
              plik.suggested_filename)
        sciezka = plik.path()
        check('to naprawdę PDF', open(sciezka, 'rb').read(4) == b'%PDF')
        check('serwer odpytał Gotenberga', GOTEN['calls'] == przed + 1, GOTEN['calls'])
        wyslane = GOTEN['body'].decode('utf-8', 'replace')
        check('poszedł multipart z index.html', 'multipart/form-data' in GOTEN['ctype']
              and 'filename="index.html"' in wyslane)
        check('stopka z datą dołączona', 'filename="footer.html"' in wyslane
              and 'wygenerowano' in wyslane)
        check('dokument zawiera nazwy rolek',
              'Hosomaki Ogórek' in wyslane and 'Futomaki Philadelphia' in wyslane)
        check('i gramatury składników', '110 g' in wyslane, wyslane[:0])
        check('numeracja rolek w kolejności',
              wyslane.index('>1<') < wyslane.index('>2<'))

        # awaria generatora nie może wywalić aplikacji ani zwrócić śmieci jako PDF
        odp = pg.evaluate("""async () => {
          const r = await fetch('/api/pdf',{method:'POST',headers:{'Content-Type':'application/json'},
            body: JSON.stringify({html:'<p>test</p>', name:'x', gotenberg:'zły'})});
          return {status:r.status, ct:r.headers.get('content-type')};
        }""")
        check('poprawne żądanie zwraca PDF', odp['status'] == 200 and 'pdf' in odp['ct'], odp)
        odp2 = pg.evaluate("""async () => {
          const r = await fetch('/api/pdf',{method:'POST',headers:{'Content-Type':'application/json'},
            body: JSON.stringify({name:'x'})});
          return r.status;
        }""")
        check('żądanie bez treści odrzucone (400)', odp2 == 400, odp2)

        print('\n== RESTART SERWERA ==')
        proc.terminate()
        proc.wait(timeout=10)
        proc = start(PORT)
        pg.goto(URL)
        pg.wait_for_timeout(1500)
        check('sesja przetrwała restart (bez ponownego logowania)',
              pg.locator('#loginWrap').count() == 0)
        check('dane przetrwały restart',
              abs(pg.evaluate("() => CALC.ing('ryz').packPrice") - 111) < 0.001)

        print('\n== WYLOGOWANIE ==')
        pg.click('.nav[data-v="set"]')
        pg.wait_for_timeout(500)
        check('karta serwera w ustawieniach', 'Wersja danych' in pg.content())
        pg.click('#srvOut')
        pg.wait_for_timeout(1500)
        check('po wylogowaniu wraca ekran logowania', pg.locator('#loginForm').count() == 1)

        print('\n== BEZPIECZEŃSTWO ==')
        import urllib.request, urllib.error
        def status(path, method='GET'):
            req = urllib.request.Request(URL + path, method=method)
            try:
                return urllib.request.urlopen(req, timeout=5).status
            except urllib.error.HTTPError as e:
                return e.code
        check('/api/data bez ciasteczka = 401', status('/api/data') == 401)
        check('/api/me bez ciasteczka = 401', status('/api/me') == 401)
        check('nie da się pobrać users.json', status('/data/users.json') == 404)
        check('nie da się wyjść z katalogu', status('/../server.py') in (400, 404))
        check('/api/health działa', status('/api/health') == 200)
        check('/api/pdf bez ciasteczka = 401', status('/api/pdf', 'POST') == 401)

        check('brak błędów JS', not errs, errs)
        br.close()
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()

print('\n' + '=' * 60)
print('WSZYSTKO PRZESZŁO' if not FAIL else 'NIEPOWODZENIA: ' + ', '.join(FAIL))
print('=' * 60)
sys.exit(1 if FAIL else 0)
