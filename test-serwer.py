"""Test end-to-end trybu serwerowego: logowanie, zapis, konflikt, rola podglądu, restart."""
import io
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


# podstawiony skrypt aktualizacji — prawdziwy robi git reset i restart usługi,
# a sprawdzamy tu wyłącznie to, co robi serwer wokół niego
FAKE_UPDATE = '/tmp/sp-update.sh'
with open(FAKE_UPDATE, 'w') as _f:
    _f.write('#!/bin/sh\n'
             'if [ "$1" = "--check" ]; then\n'
             '  echo "[test] Dostępna nowa wersja: abc1234"\n'
             '  echo "abc1234 nowy wydruk PDF"\n'
             '  exit 0\n'
             'fi\n'
             'echo "[test] Nowa wersja: 0000000 -> abc1234"\n'
             'sleep 2\n'
             'echo "[test] Zaktualizowano do 9.9.9 (abc1234). Wszystko działa."\n')
os.chmod(FAKE_UPDATE, 0o755)


def start(port):
    env = dict(os.environ, SUSHI_DATA=DATA, SUSHI_GOTENBERG=GOTEN_URL,
               SUSHI_UPDATE_SH=FAKE_UPDATE)
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
r = run('adduser', 'kuchnia@lokal.pl', 'admin', stdin='tajnehaslo2\ntajnehaslo2\n')
check('dodanie administratora', 'Dodano konto' in r.stdout, r.stdout + r.stderr)
r = run('adduser', 'podglad@lokal.pl', 'viewer', stdin='tajnehaslo3\ntajnehaslo3\n')
check('dodanie konta podglądu', 'Dodano konto' in r.stdout, r.stdout + r.stderr)
r = run('adduser', 'ania@lokal.pl', 'staff', stdin='tajnehaslo4\ntajnehaslo4\n')
check('dodanie konta pracownika', 'Dodano konto' in r.stdout, r.stdout + r.stderr)
r = run('adduser', 'zly@lokal.pl', 'admin', stdin='krotkie\nkrotkie\n')
check('odrzucenie zbyt krótkiego hasła', 'co najmniej 8' in r.stdout, r.stdout)
r = run('users')
check('lista kont pokazuje 4 konta', r.stdout.count('@lokal.pl') == 4, r.stdout)
check('plik haseł ma prawa 600', oct(os.stat(f'{DATA}/users.json').st_mode)[-3:] == '600')
users = json.load(open(f'{DATA}/users.json'))
check('hasło nie jest zapisane jawnie',
      all('tajnehaslo' not in json.dumps(u) for u in users.values()))

# Konta sprzed podziału na cztery poziomy: rola „kucharz" miała pełną edycję bazy,
# a osobny przełącznik „układa grafik" dawał władzę nad ludźmi. Jedno i drugie to
# dzisiaj administrator — migracja ma to zrobić sama, bez pytania.
users['stary-kucharz@lokal.pl'] = {'pw': 'x', 'role': 'chef'}
users['stary-grafikowy@lokal.pl'] = {'pw': 'x', 'role': 'staff', 'sched': True}
users['stary-zwykly@lokal.pl'] = {'pw': 'x', 'role': 'staff', 'sched': False}
json.dump(users, open(f'{DATA}/users.json', 'w'))

print('\n== HIGIENA ŹRÓDŁA ==')
# Skrypt łatający puszczony dwa razy wkleja ten sam kod po raz drugi. Python bierze
# ostatnią definicję, więc aplikacja działa i żaden test zachowania tego nie widzi —
# a w pliku siedzą dwie kopie, które od tej chwili rozjeżdżają się przy każdej poprawce.
# Dlatego sprawdzamy sam kształt pliku, a nie to, co robi.
import ast as _ast
_drzewo = _ast.parse(io.open(f'{BASE}/server.py', encoding='utf-8').read())
_nazwy = [w.name for w in _drzewo.body
          if isinstance(w, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef))]
_dwakroc = sorted({n for n in _nazwy if _nazwy.count(n) > 1})
check('żadna funkcja serwera nie jest zdefiniowana dwa razy', not _dwakroc, _dwakroc)

# Sama lista funkcji to za mało. Ten sam skrypt wkleił drugi raz także dwie lambdy
# ścieżek i CAŁY blok trasy w środku metody — rzeczy, których `ast` na poziomie
# modułu nie widzi. Python bierze pierwszą pasującą gałąź `if`, więc druga kopia
# trasy była martwa i nie dało się jej zauważyć po zachowaniu serwera.
_przypisania = []
for _w in _drzewo.body:
    if isinstance(_w, _ast.Assign):
        _przypisania += [_c.id for _c in _w.targets if isinstance(_c, _ast.Name)]
_dwakroc2 = sorted({n for n in _przypisania if _przypisania.count(n) > 1})
check('żadna stała modułu nie jest przypisana dwa razy', not _dwakroc2, _dwakroc2)

def _trasy(fn):
    """Wszystkie `path == '...'` i `path.startswith('...')` w jednej metodzie."""
    out = []
    for w in _ast.walk(fn):
        if isinstance(w, _ast.Compare) and isinstance(w.left, _ast.Name) \
           and w.left.id == 'path' and isinstance(w.ops[0], _ast.Eq) \
           and isinstance(w.comparators[0], _ast.Constant):
            out.append(w.comparators[0].value)
        if isinstance(w, _ast.Call) and isinstance(w.func, _ast.Attribute) \
           and w.func.attr == 'startswith' and isinstance(w.func.value, _ast.Name) \
           and w.func.value.id == 'path' and w.args \
           and isinstance(w.args[0], _ast.Constant):
            out.append(w.args[0].value)
    return out

_bliznieta = []
for _w in _ast.walk(_drzewo):
    if isinstance(_w, _ast.FunctionDef):
        _t = _trasy(_w)
        _bliznieta += [(_w.name, p) for p in sorted(set(_t)) if _t.count(p) > 1]
check('żadna trasa nie jest obsłużona dwa razy w tej samej metodzie',
      not _bliznieta, _bliznieta)

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
        pg.evaluate("() => editIng('losos')")
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
        check('podgląd widzi receptury', pg3.evaluate("() => DB.items.length") >= 23)
        check('i składniki z jednostkami, na których stoją gramatury',
              pg3.evaluate("() => DB.ingredients.length > 0 && DB.ingredients.every(s=>!!s.unit)"))
        check('ale ani jednej ceny zakupu',
              pg3.evaluate("() => DB.ingredients.every(s=>s.packPrice === undefined)"))
        check('plakietka pokazuje podgląd', 'podgląd' in pg3.locator('#syncBadge').inner_text(),
              pg3.locator('#syncBadge').inner_text())
        # Konto podglądu nie ma po co widzieć ekranów, na których się zapisuje albo liczy
        check('zakładki Edycja, Analizy i Narzędzia w ogóle nie ma', pg3.evaluate("""() => {
          return ['grp-edycja','grp-analizy','grp-narzedzia']
            .every(id => getComputedStyle(document.getElementById(id)).display === 'none'); }"""))
        check('ekran składników jest poza jego zasięgiem', pg3.evaluate(
              "() => { go('ing'); return VIEW; }") == 'dHome')
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
        # liczba i jednostka jadą w osobnych kolumnach, więc szukamy ich osobno
        check('i gramatury składników',
              '>110</span>' in wyslane and '>g</span>' in wyslane, wyslane[:0])
        check('numeracja rolek w kolejności',
              wyslane.index('>1.<') < wyslane.index('>2.<'))

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

        print('\n== MIGRACJA KONT NA CZTERY POZIOMY ==')
        po = json.load(open(f'{DATA}/users.json'))
        check('kucharz staje się administratorem',
              po['stary-kucharz@lokal.pl']['role'] == 'admin', po['stary-kucharz@lokal.pl'])
        check('kto układał grafik, ten też — nikomu nie zabieramy uprawnień',
              po['stary-grafikowy@lokal.pl']['role'] == 'admin', po['stary-grafikowy@lokal.pl'])
        check('pracownik bez tej flagi zostaje pracownikiem',
              po['stary-zwykly@lokal.pl']['role'] == 'staff', po['stary-zwykly@lokal.pl'])
        check('a sama flaga znika z pliku',
              all('sched' not in u for u in po.values()), po)
        for e in ('stary-kucharz@lokal.pl', 'stary-grafikowy@lokal.pl', 'stary-zwykly@lokal.pl'):
            po.pop(e, None)
        json.dump(po, open(f'{DATA}/users.json', 'w'))

        print('\n== KONTA Z POZIOMU APLIKACJI ==')
        api = lambda p, b=None: pg.evaluate("""async ([p, b]) => {
          const r = await fetch(p, b ? {method:'POST', headers:{'Content-Type':'application/json'},
                                        body:JSON.stringify(b)} : undefined);
          return {status:r.status, ...(await r.json().catch(()=>({})))};
        }""", [p, b])

        lista = api('/api/users')
        check('właściciel widzi listę kont', lista['status'] == 200 and len(lista['users']) == 4,
              lista)
        check('lista podaje role', {u['email']: u['role'] for u in lista['users']}
              == {'szef@lokal.pl': 'owner', 'kuchnia@lokal.pl': 'admin',
                  'podglad@lokal.pl': 'viewer', 'ania@lokal.pl': 'staff'},
              lista['users'])
        check('i nic o osobnym uprawnieniu do grafiku — nie ma już czegoś takiego',
              all('sched' not in u for u in lista['users']), lista['users'])
        check('administrator też widzi listę kont',
              pg2.evaluate("async () => (await fetch('/api/users')).status") == 200)
        check('konto podglądu nie widzi listy',
              pg3.evaluate("async () => (await fetch('/api/users')).status") == 403)

        check('krótkie hasło odrzucone',
              api('/api/users', {'email': 'nowy@lokal.pl', 'role': 'admin', 'password': 'krotkie'})
              ['status'] == 400)
        check('konto dodane',
              api('/api/users', {'email': 'nowy@lokal.pl', 'role': 'admin',
                                 'password': 'dlugiehaslo1'})['status'] == 200)
        check('duplikat odrzucony',
              api('/api/users', {'email': 'nowy@lokal.pl', 'role': 'admin',
                                 'password': 'dlugiehaslo1'})['status'] == 409)
        check('hasło zapisane jako skrót, nie tekstem',
              'dlugiehaslo1' not in open(f'{DATA}/users.json').read())

        ctx4 = br.new_context()
        pg4 = ctx4.new_page()
        pg4.goto(URL); pg4.wait_for_timeout(700)
        pg4.fill('#lgMail', 'nowy@lokal.pl'); pg4.fill('#lgPass', 'dlugiehaslo1')
        pg4.click('#lgBtn'); pg4.wait_for_timeout(1500)
        check('nowe konto od razu się loguje', pg4.locator('#loginWrap').count() == 0)
        ctx4.close()

        check('zmiana roli', api('/api/users/update',
              {'email': 'nowy@lokal.pl', 'role': 'viewer'})['status'] == 200)
        check('rola zapisana',
              json.load(open(f'{DATA}/users.json'))['nowy@lokal.pl']['role'] == 'viewer')
        check('nie da się usunąć siebie',
              api('/api/users/delete', {'email': 'szef@lokal.pl'})['status'] == 400)
        check('nie da się odebrać roli ostatniemu właścicielowi',
              api('/api/users/update', {'email': 'szef@lokal.pl', 'role': 'admin'})['status'] == 400)

        # Administrator zarządza kontami na równi z właścicielem — poza jednym.
        # Inaczej mógłby odciąć właściciela od jego własnego lokalu.
        api2 = lambda p, b=None: pg2.evaluate("""async ([p, b]) => {
          const r = await fetch(p, b ? {method:'POST', headers:{'Content-Type':'application/json'},
                                        body:JSON.stringify(b)} : undefined);
          return {status:r.status, ...(await r.json().catch(()=>({})))};
        }""", [p, b])
        check('administrator nie usunie konta właściciela',
              api2('/api/users/delete', {'email': 'szef@lokal.pl'})['status'] == 403)
        check('ani nie zdegraduje właściciela',
              api2('/api/users/update', {'email': 'szef@lokal.pl', 'role': 'staff'})['status'] == 403)
        check('ani nie mianuje właścicielem samego siebie',
              api2('/api/users/update', {'email': 'ania@lokal.pl', 'role': 'owner'})['status'] == 403)
        check('a właściciel dalej stoi w pliku nietknięty',
              json.load(open(f'{DATA}/users.json'))['szef@lokal.pl']['role'] == 'owner')
        check('ale zwykłe konto administrator przestawi',
              api2('/api/users/update', {'email': 'ania@lokal.pl', 'role': 'viewer'})['status'] == 200)
        check('i z powrotem',
              api2('/api/users/update', {'email': 'ania@lokal.pl', 'role': 'staff'})['status'] == 200)
        check('nieistniejące konto to 404',
              api('/api/users/delete', {'email': 'nikt@lokal.pl'})['status'] == 404)
        check('konto usunięte',
              api('/api/users/delete', {'email': 'nowy@lokal.pl'})['status'] == 200)
        check('i zniknęło z pliku', 'nowy@lokal.pl' not in json.load(open(f'{DATA}/users.json')))

        pg.click('.nav[data-v="users"]'); pg.wait_for_timeout(600)
        check('zakładka Użytkownicy pokazuje konta',
              'kuchnia@lokal.pl' in pg.content() and 'podglad@lokal.pl' in pg.content())

        # Skrót i kolor nadaje się przy koncie — kartoteka grafiku nie jest osobnym bytem
        pg.click('[data-edit-user="kuchnia@lokal.pl"]'); pg.wait_for_timeout(400)
        check('edytor konta ma pola grafiku',
              pg.locator('#uNazwa').count() == 1 and pg.locator('#uSkrot').count() == 1
              and pg.locator('#uKolory .kolorbtn').count() == 16,
              pg.locator('#uKolory .kolorbtn').count())
        check('skrót ograniczony do sześciu znaków',
              pg.evaluate("() => document.getElementById('uSkrot').maxLength") == 6)
        check('nie ma już osobnego przełącznika „układa grafik"',
              pg.locator('#uSched').count() == 0)
        check('za to widać, co wybrana rola oznacza',
              len(pg.locator('#uOpisRoli').inner_text()) > 30,
              pg.locator('#uOpisRoli').inner_text())
        pg.fill('#uNazwa', 'Kasia Kucharska')
        pg.fill('#uSkrot', 'kasia')
        pg.click('#uKolory .kolorbtn[data-kolor="#085F88"]')
        pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(1200)
        os_kasia = pg.evaluate("() => osobaZMaila('kuchnia@lokal.pl', false)")
        check('nazwa, skrót i kolor zapisane przy koncie',
              os_kasia and os_kasia['name'] == 'Kasia Kucharska'
              and os_kasia['code'] == 'kasia' and os_kasia['color'] == '#085F88', os_kasia)
        # Skrót to czyjś podpis na kalendarzu, nie kod z bazy — zostaje taki, jak go
        # ktoś wpisał. Wersaliki na siłę robiły z „MarPro" → „MARPRO".
        check('skrót zostaje taki, jak go wpisano', 'kasia' in pg.content())
        check('lista kont pokazuje godziny w bieżącym miesiącu',
              'Godziny' in pg.locator('table[data-tbl="users"]').inner_text())

        # Krzyżyk przy wierszu stoi milimetry od „Edytuj", a robi rzecz nieodwracalną.
        # Usuwanie należy tam, gdzie edycja — za jednym kliknięciem więcej, świadomie.
        check('w wierszu listy nie ma już klawisza kasowania',
              pg.locator('table[data-tbl="users"] [data-del-user]').count() == 0)
        check('konto na próbę założone', api('/api/users',
              {'email':'doskasowania@lokal.pl', 'role':'staff', 'password':'dlugiehaslo1'})['status'] == 200)
        pg.evaluate("() => { USERS = null; render(); }"); pg.wait_for_timeout(900)
        pg.click('[data-edit-user="doskasowania@lokal.pl"]'); pg.wait_for_timeout(400)
        check('kasowanie konta siedzi w panelu edycji',
              pg.locator('#uUsun').count() == 1)
        check('i jest opisane jako nieodwracalne',
              'straci dostęp' in pg.locator('.ryzyko').inner_text(),
              pg.locator('.ryzyko').inner_text()[:120])
        pg.evaluate("() => { window.__conf = window.confirm; window.confirm = () => true; }")
        pg.click('#uUsun'); pg.wait_for_timeout(1200)
        pg.evaluate("() => { window.confirm = window.__conf; }")
        check('i naprawdę kasuje konto',
              'doskasowania@lokal.pl' not in json.load(open(f'{DATA}/users.json')))
        check('a lista od razu o tym wie',
              'doskasowania@lokal.pl' not in pg.locator('table[data-tbl="users"]').inner_text())
        check('własnego konta dalej nie da się usunąć — nie ma czym',
              pg.evaluate("""async () => {
                const r = await fetch('/api/users/delete', {method:'POST',
                  headers:{'Content-Type':'application/json'},
                  body: JSON.stringify({email: SRV.user.email})});
                return r.status; }""") == 400)

        pg.click('.nav[data-v="graf"]'); pg.wait_for_timeout(600)
        check('nowy skrót jest od razu do wyboru w grafiku',
              pg.evaluate("() => active(DB.staff).some(o=>o.code === 'kasia')"))


        print('\n== KONTO PRACOWNIKA: WSZYSTKO OPRÓCZ PIENIĘDZY ==')
        # Kucharz przy blacie potrzebuje gramatur, kolejności składników i tego, ile
        # czego zejdzie danego dnia. Nie potrzebuje wiedzieć, ile kosztuje kilogram
        # łososia. Ceny nie są tu CHOWANE w interfejsie — serwer ich nie wysyła, więc
        # nie ma ich także w konsoli przeglądarki.
        import datetime
        jutro = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        wczoraj = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

        ctxA = br.new_context()
        pgA = ctxA.new_page()
        bledyA = []
        pgA.on('pageerror', lambda e: bledyA.append(str(e)))
        pgA.goto(URL); pgA.wait_for_timeout(700)
        pgA.fill('#lgMail', 'ania@lokal.pl'); pgA.fill('#lgPass', 'tajnehaslo4')
        pgA.click('#lgBtn'); pgA.wait_for_timeout(1800)
        check('pracownik się loguje', pgA.locator('#loginWrap').count() == 0)

        dane = pgA.evaluate("async () => await (await fetch('/api/data')).json()")
        check('serwer oznacza dane jako okrojone', dane.get('limited') is True, list(dane.keys()))
        check('pracownik dostaje składniki z gramaturami',
              len(dane['data']['ingredients']) > 0
              and all(s.get('name') for s in dane['data']['ingredients']),
              dane['data'].get('ingredients', [])[:1])
        check('i receptury rolek', len(dane['data']['items']) > 0
              and all(i.get('comps') is not None for i in dane['data']['items']))
        check('i szablon zmian', bool(dane['data'].get('shiftTpl')), list(dane['data'].keys()))

        check('ale ani jednej ceny zakupu',
              all('packPrice' not in s for s in dane['data']['ingredients']),
              [s for s in dane['data']['ingredients'] if 'packPrice' in s][:1])
        check('ani jednej ceny sprzedaży rolki',
              all('prices' not in i and 'vats' not in i for i in dane['data']['items']))
        check('ani zestawu', all('prices' not in z and 'vats' not in z for z in dane['data']['sets']))
        check('ani gotowego food costu z arkusza',
              all('sheetFc' not in i and 'sheetNet' not in i for i in dane['data']['items']))
        check('historia cen znika w całości — to sama tabela pieniędzy',
              dane['data']['history'] == [], dane['data'].get('history'))
        check('a z ustawień wypadają cel food costu i stawki VAT',
              not any(k in dane['data']['settings'] for k in ('targetFc', 'alertFc', 'vats')),
              dane['data']['settings'])
        surowe = json.dumps(dane)
        check('w odpowiedzi nie ma ani jednej ceny zakupu',
              '"packPrice"' not in surowe and '"pricePack"' not in surowe, surowe[:200])

        check('pracownik nie zapisze całej bazy',
              pgA.evaluate("""async () => (await fetch('/api/data',{method:'PUT',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({rev:0,data:{ingredients:[]}})})).status""") == 403)
        check('pracownik nie widzi listy kont',
              pgA.evaluate("async () => (await fetch('/api/users')).status") == 403)
        check('interfejs zwinięty do podglądów', pgA.evaluate("() => document.body.classList.contains('bezCen')"))
        check('bez Edycji, Analiz i Narzędzi', pgA.evaluate("""() => {
          return ['grp-edycja','grp-analizy','grp-narzedzia']
            .every(id => getComputedStyle(document.getElementById(id)).display === 'none'); }"""))
        check('wylogowanie zostaje pod ręką',
              pgA.evaluate("() => document.getElementById('navOut').closest('.navitems').id") == 'grp-pulpit')
        check('ale panel dnia ma w całości', pgA.evaluate("""() => {
          const w = ['dHome','graf','dPrep','dRolki','dZest','dPack','driver','stock'];
          return w.every(v => {
            const b = document.querySelector(`.nav[data-v="${v}"]`);
            return b && getComputedStyle(b).display !== 'none'; }); }"""))
        # Receptury bez cen są dokładnie tym, po co pracownik otwiera aplikację przy blacie
        pgA.evaluate("() => go('dRolki')"); pgA.wait_for_timeout(700)
        check('na ekranie rolek widzi rozpiskę', pgA.evaluate("() => VIEW") == 'dRolki'
              and pgA.locator('#main').inner_text().strip() != '')
        check('i nigdzie na niej nie ma złotówek',
              'zł' not in pgA.locator('#main').inner_text(),
              pgA.locator('#main').inner_text()[:200])
        pgA.evaluate("() => go('graf')"); pgA.wait_for_timeout(700)

        print('\n== GRAFIK: ZAPISY NA ZMIANY ==')
        zmiana = pgA.evaluate(f"() => zmianyDnia('{jutro}')[0].id")
        shift = lambda strona, ciało: strona.evaluate("""async (b) => {
          const r = await fetch('/api/shift',{method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify(b)});
          return {status:r.status, ...(await r.json().catch(()=>({})))};
        }""", ciało)
        self_ = lambda strona, d, z, on: shift(strona, {'op':'self','date':d,'shift':z,'on':on})

        odp = self_(pgA, jutro, zmiana, True)
        check('pracownik zapisuje się na zmianę', odp['status'] == 200, odp)
        wpis = odp.get('signups', {}).get(f'{jutro}|{zmiana}', {})
        check('wpis od razu zajmuje miejsce, bez niczyjej decyzji',
              len(wpis.get('osoby', [])) == 1, wpis)
        moja = [o for o in odp['staff'] if o['email'] == 'ania@lokal.pl']
        check('kartoteka założona sama z konta', len(moja) == 1 and moja[0]['id'] == wpis['osoby'][0], odp['staff'])

        check('zgłoszenie na miniony dzień odrzucone',
              self_(pgA, wczoraj, zmiana, True)['status'] == 400)
        check('nieistniejąca zmiana odrzucona',
              self_(pgA, jutro, 'zm-nie-ma-takiej', True)['status'] == 400)
        check('bzdurna data odrzucona', self_(pgA, 'jutro', zmiana, True)['status'] == 400)
        check('konto podglądu nie zapisze się na zmianę',
              self_(pg3, jutro, zmiana, True)['status'] == 403)

        # osoba układająca grafik idzie tym samym wąskim kanałem — inaczej jej `rev`
        # byłby już nieaktualny po wpisie pracownika i zapis skończyłby się konfliktem 409
        osId = wpis['osoby'][0]
        rev_przed = pg.evaluate("() => SRV.rev")
        odp = shift(pg, {'op': 'set', 'date': jutro, 'shift': zmiana, 'person': osId, 'on': False})
        check('kto układa grafik, ten wypisze każdego', odp['status'] == 200, odp)
        check('miejsce naprawdę się zwolniło',
              odp['signups'].get(f'{jutro}|{zmiana}') is None, odp.get('signups'))
        check('rev poszedł do przodu', odp['rev'] > rev_przed, (rev_przed, odp.get('rev')))
        check('i można wpisać z powrotem',
              shift(pg, {'op': 'set', 'date': jutro, 'shift': zmiana,
                         'person': osId, 'on': True})['status'] == 200)
        sloty = pgA.evaluate(f"() => zmianyDnia('{jutro}')[0].slots")
        # W grafiku staje wyłącznie ktoś, kto ma konto — nie ma listy luźnych nazwisk
        check('osoba bez konta nie wejdzie do grafiku',
              shift(pg, {'op': 'set', 'date': jutro, 'shift': zmiana,
                         'person': {'email': 'ktos@zulicy.pl'}, 'on': True})['status'] == 400)
        check('i nie zostawia po sobie śladu w bazie',
              'ktos@zulicy.pl' not in open(f'{DATA}/data.json', encoding='utf-8').read())

        # zapełniamy zmianę do ostatniego miejsca kontami, które istnieją
        konta = ['kuchnia@lokal.pl', 'podglad@lokal.pl']
        for i in range(sloty - 1):
            check(f'wpisanie posiadacza konta ({i + 2}/{sloty})',
                  shift(pg, {'op': 'set', 'date': jutro, 'shift': zmiana,
                             'person': {'email': konta[i]}, 'on': True})['status'] == 200)
        nadmiar = shift(pg, {'op': 'set', 'date': jutro, 'shift': zmiana,
                             'person': {'email': 'szef@lokal.pl'}, 'on': True})
        check('ponad liczbę miejsc serwer nie wpisze nikogo', nadmiar['status'] == 400, nadmiar)
        check('odbity wpis nie zostawia nikogo w środku',
              len(json.load(open(f'{DATA}/data.json', encoding='utf-8'))
                  ['data']['signups'][f'{jutro}|{zmiana}']['osoby']) == sloty)
        check('pracownik bez uprawnienia nie wypisze cudzej osoby',
              shift(pgA, {'op': 'set', 'date': jutro, 'shift': zmiana,
                          'person': osId, 'on': False})['status'] == 403)
        pgA.reload(); pgA.wait_for_timeout(1500)
        check('pracownik widzi, że stoi w grafiku',
              pgA.evaluate(f"() => zapisy('{jutro}','{zmiana}').osoby.indexOf('{osId}')") >= 0)
        check('i że zmiana jest pełna',
              pgA.evaluate(f"() => obsada('{jutro}', zmianyDnia('{jutro}')[0]).wolne") == 0)

        odp = self_(pgA, jutro, zmiana, False)
        check('wypisanie się działa', odp['status'] == 200, odp)
        wpis3 = odp.get('signups', {}).get(f'{jutro}|{zmiana}', {})
        check('zwalnia dokładnie jedno miejsce',
              osId not in wpis3.get('osoby', []) and len(wpis3.get('osoby', [])) == sloty - 1, wpis3)
        check('i pracownik może wejść z powrotem',
              self_(pgA, jutro, zmiana, True)['status'] == 200)
        check('ale nie na zmianę, która jest już pełna',
              self_(pgA, jutro, zmiana, True)['status'] == 200)   # powtórka to nie błąd
        self_(pgA, jutro, zmiana, False)


        print('\n== GRAFIK: KTO UKŁADA GO INNYM ==')
        # Nie ma już osobnego przełącznika — grafik wynika z poziomu. Kto zarządza bazą,
        # ten zarządza i grafikiem; pracownik wpisuje wyłącznie siebie.
        check('administrator wpisze kogoś innego',
              shift(pg2, {'op': 'set', 'date': jutro, 'shift': zmiana,
                          'person': {'email': 'szef@lokal.pl'}, 'on': True})['status'] == 200)
        check('pracownik cudzego wpisu nie ruszy',
              shift(pgA, {'op': 'set', 'date': jutro, 'shift': zmiana,
                          'person': {'email': 'szef@lokal.pl'}, 'on': False})['status'] == 403)
        check('a administrator owszem',
              shift(pg2, {'op': 'set', 'date': jutro, 'shift': zmiana,
                          'person': {'email': 'szef@lokal.pl'}, 'on': False})['status'] == 200)
        check('i wpisze z powrotem',
              shift(pg2, {'op': 'set', 'date': jutro, 'shift': zmiana,
                          'person': {'email': 'szef@lokal.pl'}, 'on': True})['status'] == 200)
        # Wpis na wiele dni naraz to wciąż wpis WŁASNY — panel zaznaczonych dni daje
        # „Zapisz mnie na 4 dni" każdemu, kto w ogóle stawia swój wpis.
        check('pracownik zapisze się zbiorczo, choć grafiku nie układa',
              pgA.evaluate("() => mozeGrafik()") is False)

        # --- wiele dni naraz ---
        dni = pgA.evaluate("""() => {
          const out = [];
          for(let i = 1; out.length < 4 && i < 40; i++){
            const d = przesunISO(todayISO(), i);
            if(zmianyDnia(d).some(z=>z.name === 'I zmiana')) out.push(d);
          }
          return out; }""")
        zb = shift(pgA, {'op': 'batch', 'days': dni, 'shiftName': 'I zmiana', 'on': True})
        check('wpis zbiorczy jednym żądaniem', zb['status'] == 200, zb)
        check('serwer mówi, co się udało, a co nie',
              len(zb['zrobione']) + len(zb['pominiete']) == len(dni), zb)
        check('dzień z kompletem został pominięty', jutro in zb['pominiete'], zb)
        check('pozostałe dni mają wpis', all(
            dane['data']['signups'].get(f'{d}|' + [z['id'] for z in
                pgA.evaluate(f"() => zmianyDnia('{d}')") if z['name'] == 'I zmiana'][0])
            for d in zb['zrobione']
            for dane in [json.load(open(f'{DATA}/data.json', encoding='utf-8'))]), zb['zrobione'])
        zb2 = shift(pgA, {'op': 'batch', 'days': dni, 'shiftName': 'I zmiana', 'on': False})
        check('wypis zbiorczy też działa jednym żądaniem', zb2['status'] == 200, zb2)
        check('i zdejmuje z tych dni, gdzie ta osoba stała',
              len(zb2['zrobione']) == len(dni), zb2)
        check('nieznana nazwa zmiany to pominięcie, nie awaria',
              len(shift(pgA, {'op': 'batch', 'days': dni,
                              'shiftName': 'Nocna z kosmosu', 'on': True})['pominiete']) == len(dni))
        check('pusta lista dni odrzucona',
              shift(pgA, {'op': 'batch', 'days': [], 'shiftName': 'I zmiana', 'on': True})['status'] == 400)
        check('bzdurna data w paczce odrzuca całość',
              shift(pgA, {'op': 'batch', 'days': ['wczoraj'], 'shiftName': 'I zmiana',
                          'on': True})['status'] == 400)
        check('za dużo dni naraz odrzucone',
              shift(pgA, {'op': 'batch', 'days': [jutro] * 201, 'shiftName': 'I zmiana',
                          'on': True})['status'] == 400)

        check('a podgląd nie zapisze się nawet zbiorczo',
              shift(pg3, {'op': 'batch', 'days': dni, 'shiftName': 'I zmiana',
                          'on': True})['status'] == 403)

        print('\n== REJESTRACJA WYJAZDU I ZATOWAROWANIA ==')
        # Rejestruje kierowca i osoba pakująca, czyli konta, które NIE zapisują bazy.
        # Dlatego osobna, wąska trasa — tak samo jak przy grafiku.
        rej = lambda strona, ciało: strona.evaluate("""async (b) => {
          const r = await fetch('/api/zdarzenie',{method:'POST',
            headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
          return {status:r.status, ...(await r.json().catch(()=>({})))};
        }""", ciało)
        dzis = datetime.date.today().isoformat()
        maszyna = pg.evaluate("() => active(DB.machines)[0].id")

        odp = rej(pgA, {'rodzaj': 'wyjazd', 'date': dzis, 'on': True})
        check('pracownik rejestruje wyjazd', odp['status'] == 200, odp)
        wpis_w = odp.get('zdarzenia', {}).get(dzis + '|wyjazd', {})
        check('zapis niesie osobę i czas',
              bool(wpis_w.get('osoba')) and isinstance(wpis_w.get('czas'), int), wpis_w)
        # Czas ma pochodzić z zegara SERWERA. Telefon ze złym zegarem albo inna strefa
        # czasowa zatrułyby zapis, który ma być dowodem, o której samochód wyjechał.
        check('czas bierze się z zegara serwera, nie z żądania',
              abs(wpis_w.get('czas', 0) - int(time.time())) < 60, wpis_w.get('czas'))
        check('podanie własnego czasu niczego nie zmienia', pg.evaluate("""async (b) => {
          const r = await fetch('/api/zdarzenie',{method:'POST',
            headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
          const j = await r.json();
          return j.zdarzenia[b.date + '|wyjazd'].czas;
        }""", {'rodzaj': 'wyjazd', 'date': dzis, 'on': True, 'czas': 1}) == wpis_w.get('czas'))
        check('powtórzona rejestracja to nie błąd',
              rej(pgA, {'rodzaj': 'wyjazd', 'date': dzis, 'on': True})['status'] == 200)

        odp = rej(pgA, {'rodzaj': 'automat', 'date': dzis, 'machine': maszyna, 'on': True})
        check('i zatowarowanie konkretnego automatu', odp['status'] == 200, odp)
        check('każdy automat ma własny wiersz',
              (dzis + '|automat|' + maszyna) in odp.get('zdarzenia', {}), list(odp.get('zdarzenia', {})))
        check('automat spoza bazy odrzucony',
              rej(pgA, {'rodzaj': 'automat', 'date': dzis, 'machine': 'nie-ma', 'on': True})['status'] == 400)
        check('nieznane zdarzenie odrzucone',
              rej(pgA, {'rodzaj': 'kosmos', 'date': dzis, 'on': True})['status'] == 400)
        check('bzdurna data odrzucona',
              rej(pgA, {'rodzaj': 'wyjazd', 'date': 'dzisiaj', 'on': True})['status'] == 400)
        # Wyjazdu, którego jeszcze nie było, nie da się zarejestrować
        check('data z przyszłości odrzucona',
              rej(pgA, {'rodzaj': 'wyjazd', 'date': jutro, 'on': True})['status'] == 400)

        check('konto podglądu nie zarejestruje niczego',
              rej(pg3, {'rodzaj': 'wyjazd', 'date': dzis, 'on': True})['status'] == 403)
        check('ani nie zapisze bazy inną drogą', pg3.evaluate("""async () => (await fetch(
          '/api/data',{method:'PUT',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({rev:0,data:{}})})).status""") == 403)

        # Swoje cofa każdy, cudze — właściciel albo administrator. Ta sama zasada,
        # co przy krzyżyku obok plakietki w grafiku.
        odp = rej(pg2, {'rodzaj': 'wyjazd', 'date': dzis, 'on': False})
        check('cudzego wpisu pracownik nie cofnie — ale administrator tak',
              odp['status'] == 200, odp)
        check('i wpis naprawdę znika',
              (dzis + '|wyjazd') not in odp.get('zdarzenia', {}), odp.get('zdarzenia'))
        rej(pg2, {'rodzaj': 'wyjazd', 'date': dzis, 'on': True})
        check('cudzy wpis odbija się od pracownika',
              rej(pgA, {'rodzaj': 'wyjazd', 'date': dzis, 'on': False})['status'] == 400)
        check('własny owszem',
              rej(pgA, {'rodzaj': 'automat', 'date': dzis, 'machine': maszyna,
                        'on': False})['status'] == 200)
        check('cofnięcie nieistniejącego wpisu to nie awaria',
              rej(pgA, {'rodzaj': 'automat', 'date': dzis, 'machine': maszyna,
                        'on': False})['status'] == 200)

        rev_przed = pg.evaluate("() => SRV.rev")
        odp = rej(pg, {'rodzaj': 'automat', 'date': dzis, 'machine': maszyna, 'on': True})
        check('każda rejestracja podbija rev', odp['rev'] > rev_przed, (rev_przed, odp.get('rev')))
        check('a zdarzenia lądują w bazie na dysku',
              (dzis + '|automat|' + maszyna) in json.load(
                  open(f'{DATA}/data.json', encoding='utf-8'))['data']['zdarzenia'])
        # Pracownik dostaje bazę bez cen — ale rejestr wyjazdów pieniędzy nie zawiera,
        # więc ma go widzieć w całości.
        dane2 = pgA.evaluate("async () => await (await fetch('/api/data')).json()")
        check('pracownik widzi rejestr, bo nie ma w nim ani grosza',
              (dzis + '|automat|' + maszyna) in (dane2['data'].get('zdarzenia') or {}),
              list((dane2['data'].get('zdarzenia') or {})))

        print('\n== SPRZEDAŻ Z AUTOMATÓW ==')
        # Automaty ELDRUT raportują każdą sprzedaż osobnym mailem; n8n czyta skrzynkę
        # i wysyła je tutaj. To nie jest przeglądarka i nie jest człowiekiem, więc
        # uwierzytelnia się kluczem w nagłówku, a nie ciasteczkiem sesji.
        klucz = run('token').stdout.strip()
        check('klucz dla n8n da się wygenerować z konsoli', len(klucz) > 20, klucz[:8])

        import urllib.request, urllib.error
        def wyslij(pozycje, tok=None):
            zad = urllib.request.Request(
                f'http://127.0.0.1:{PORT}/api/sprzedaz',
                data=json.dumps({'sprzedaz': pozycje}).encode(),
                headers={'Content-Type': 'application/json',
                         'X-Token': klucz if tok is None else tok})
            try:
                with urllib.request.urlopen(zad, timeout=10) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read() or b'{}')

        check('bez klucza ani rusz', wyslij([], tok='')[0] == 401)
        check('zły klucz też odpada', wyslij([], tok='nie-ten')[0] == 401)

        # Numer seryjny wiąże sprzedaż z automatem. Bez niego nie ma jak jej przypisać.
        maszyna = pg.evaluate("() => active(DB.machines)[0].id")
        pg.evaluate("""async () => {
          const st = await (await fetch('/api/data')).json();
          st.data.machines[0].serial = 'SM-0241-26';
          st.data.vending.layout['4'] = active(st.data.sets).length
            ? st.data.sets[0].id : null;
          await fetch('/api/data', {method:'PUT', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({rev: st.rev, data: st.data})});
        }""")
        pg.wait_for_timeout(400)
        zestaw = pg.evaluate("() => DB.sets[0].id")
        teraz = int(time.time())
        ym = time.strftime('%Y-%m', time.localtime(teraz))

        kod, odp = wyslij([{'msgId': '<a@eldrut>', 'serial': 'SM-0241-26', 'szafka': 4,
                            'kwota': 110.0, 'czas': teraz}])
        check('sprzedaż przyjęta', kod == 200 and odp.get('przyjete') == 1, odp)
        plik = json.load(open(f'{DATA}/sprzedaz-{ym}.json', encoding='utf-8'))
        check('i leży w osobnym pliku miesięcznym', '<a@eldrut>' in plik, list(plik))
        # Sprzedaż NIE mieszka w bazie — baza leci do przeglądarki przy każdym wczytaniu.
        check('a bazy aplikacji nie tknęła',
              'sprzedaz' not in json.load(open(f'{DATA}/data.json', encoding='utf-8'))['data'])
        w = plik['<a@eldrut>']
        check('automat rozpoznany po numerze seryjnym', w.get('maszyna') == maszyna, w)
        # Układ szafek się zmienia; sprzedaż sprzed miesiąca ma zostać przy zestawie,
        # który wtedy w tej szafce stał. Dlatego rozwiązujemy go PRZY PRZYJĘCIU.
        check('a zestaw zapisany na stałe, nie liczony przy wyświetlaniu',
              w.get('zestaw') == zestaw, w)
        check('kwota od automatu zapisana taka, jaka przyszła', w.get('kwota') == 110.0)

        # Ten sam mail przetworzony drugi raz nie może zdublować sprzedaży — inaczej
        # nie dałoby się bezpiecznie puścić workflow na całej skrzynce wstecz.
        kod, odp = wyslij([{'msgId': '<a@eldrut>', 'serial': 'SM-0241-26', 'szafka': 4,
                            'kwota': 110.0, 'czas': teraz}])
        check('powtórzony mail nie dubluje sprzedaży',
              odp.get('powtorzone') == 1 and odp.get('przyjete') == 0, odp)
        check('i w pliku dalej jest jeden wpis',
              len(json.load(open(f'{DATA}/sprzedaz-{ym}.json', encoding='utf-8'))) == 1)

        # Sprzedaż z nieznanego automatu naprawdę się wydarzyła i pieniądze wpłynęły —
        # wyrzucenie jej dlatego, że my czegoś nie wiemy, byłoby zamiataniem pod dywan.
        kod, odp = wyslij([{'msgId': '<b@eldrut>', 'serial': 'SM-9999-99', 'szafka': 4,
                            'kwota': 99.0, 'czas': teraz}])
        check('sprzedaż z nieznanego numeru nie przepada',
              odp.get('przyjete') == 1 and odp.get('nieznane') == 1, odp)
        plik = json.load(open(f'{DATA}/sprzedaz-{ym}.json', encoding='utf-8'))
        check('ale wie, dlaczego jej nie przypisano',
              plik['<b@eldrut>'].get('nieznane') == 'nieznany numer seryjny', plik['<b@eldrut>'])

        check('pozycja bez Message-ID odrzucona',
              wyslij([{'serial': 'SM-0241-26', 'szafka': 4, 'kwota': 1, 'czas': teraz}])
              [1].get('przyjete') == 0)
        check('a lista zamiast obiektu to błąd', wyslij('nie-lista')[0] == 400)

        # Jednym żądaniem cała paczka — przy zaciąganiu skrzynki wstecz to różnica
        # między jednym zapisem pliku a tysiącem.
        paczka = [{'msgId': f'<p{i}@eldrut>', 'serial': 'SM-0241-26', 'szafka': 4,
                   'kwota': 40.0, 'czas': teraz - i * 3600} for i in range(40)]
        kod, odp = wyslij(paczka)
        check('cała paczka jednym żądaniem', kod == 200 and odp.get('przyjete') == 40, odp)

        odczyt = pg.evaluate(f"""async () => {{
          const r = await fetch('/api/sprzedaz?ym={ym}');
          return {{status:r.status, ...(await r.json().catch(()=>({{}})))}}; }}""")
        check('właściciel czyta sprzedaż miesiąca',
              odczyt['status'] == 200 and len(odczyt.get('sprzedaz') or {}) >= 40, odczyt['status'])
        check('bez miesiąca serwer nie zgaduje', pg.evaluate(
              "async () => (await fetch('/api/sprzedaz')).status") == 400)
        # W sprzedaży są pieniądze, więc poziomy bez cen jej nie dostają — tak samo,
        # jak nie dostają cen w bazie.
        check('pracownik sprzedaży nie zobaczy', pgA.evaluate(
              f"async () => (await fetch('/api/sprzedaz?ym={ym}')).status") == 403)
        check('podgląd też nie', pg3.evaluate(
              f"async () => (await fetch('/api/sprzedaz?ym={ym}')).status") == 403)

        # Jeden mail potrafi zaraportować dwie szafki naraz: „sprzedał za 71.00 z szafek
        # 1, 15". To jeden klient i jedna kwota — rozdzielić jej nie da się bez cen
        # z załadunku, więc liczy się przy pierwszej szafce, a cała lista zostaje przy
        # wpisie. Bez listy nie dałoby się tego później rozliczyć ani nawet zauważyć.
        kod, odp = wyslij([{'msgId': '<d@eldrut>', 'serial': 'SM-0241-26',
                            'szafki': [4, 19], 'kwota': 71.0, 'czas': teraz}])
        plik = json.load(open(f'{DATA}/sprzedaz-{ym}.json', encoding='utf-8'))
        d = plik['<d@eldrut>']
        check('sprzedaż z kilku szafek liczy się przy pierwszej z listy',
              d.get('szafka') == 4 and d.get('zestaw') == zestaw, d)
        check('ale cała lista szafek zostaje przy wpisie', d.get('szafki') == [4, 19], d)
        check('a kwota nie jest po cichu dzielona', d.get('kwota') == 71.0, d)
        check('pojedyncza szafka nie dostaje listy',
              'szafki' not in plik['<a@eldrut>'], plik['<a@eldrut>'])

        # Archiwum ELDRUT-a podaje przy sprzedaży nazwę produktu, czego maile nie robią.
        # Dla danych sprzed miesięcy jest lepszym świadkiem niż układ szafek: układ się
        # zmieniał, a nazwa mówi wprost, co wtedy wyjechało.
        nazwaZest = pg.evaluate("() => DB.sets[0].name")
        # Szafka 19 dostaje CO INNEGO niż nazwa, żeby było widać, które źródło wygrało.
        pg.evaluate("""async () => {
          const st = await (await fetch('/api/data')).json();
          st.data.vending.layout['19'] = 'zest-z-ukladu';
          await fetch('/api/data', {method:'PUT', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({rev: st.rev, data: st.data})});
        }""")
        pg.wait_for_timeout(400)
        kod, odp = wyslij([{'msgId': '<arch1@eldrut>', 'serial': 'SM-0241-26', 'szafki': [19],
                            'kwota': 58.0, 'czas': teraz - 90 * 86400,
                            'nazwa': nazwaZest + ' 32 szt'}])
        ymArch = time.strftime('%Y-%m', time.localtime(teraz - 90 * 86400))
        arch = json.load(open(f'{DATA}/sprzedaz-{ymArch}.json', encoding='utf-8'))['<arch1@eldrut>']
        check('zestaw z archiwum rozpoznany po nazwie, nie po dzisiejszej szafce',
              arch.get('zestaw') == zestaw and arch.get('zestaw') != 'zest-z-ukladu', arch)
        check('a sama nazwa zostaje przy wpisie jako świadek',
              arch.get('nazwa') == nazwaZest + ' 32 szt', arch)
        kod, odp = wyslij([{'msgId': '<arch2@eldrut>', 'serial': 'SM-0241-26', 'szafki': [19],
                            'kwota': 58.0, 'czas': teraz - 90 * 86400}])
        arch2 = json.load(open(f'{DATA}/sprzedaz-{ymArch}.json', encoding='utf-8'))['<arch2@eldrut>']
        check('a bez nazwy — z układu szafek', arch2.get('zestaw') == 'zest-z-ukladu', arch2)
        check('sprzedaż sprzed trzech miesięcy leży w pliku swojego miesiąca',
              ymArch != ym and '<arch1@eldrut>' not in
              json.load(open(f'{DATA}/sprzedaz-{ym}.json', encoding='utf-8')), ymArch)

        # Granica między archiwum a mailami biegnie po DNIACH: ten sam zakup z dwóch źródeł
        # ma dwa różne klucze, więc `Message-ID` go nie złapie. Dzień, który aplikacja już
        # zna, archiwum ma pominąć w całości.
        dni = pg.evaluate("""async () => {
          const r = await fetch('/api/sprzedaz/dni', {headers: {'X-Token': '%s'}});
          return {status: r.status, ...(await r.json().catch(()=>({})))}; }""" % klucz)
        dzisArch = time.strftime('%Y-%m-%d', time.localtime(teraz))
        staryArch = time.strftime('%Y-%m-%d', time.localtime(teraz - 90 * 86400))
        check('serwer podaje dni, które już zna', dni['status'] == 200
              and dzisArch in dni.get('dni', []) and staryArch in dni.get('dni', []), dni)
        check('lista dni bez klucza jest zamknięta', pg.evaluate(
              "async () => (await fetch('/api/sprzedaz/dni')).status") == 401)

        # Numer seryjny bywa wpisany do automatu PÓŹNIEJ, niż przyszła pierwsza sprzedaż
        # z tego automatu. Pieniądze leżą wtedy w „Nierozpoznanych" i musi istnieć droga,
        # żeby je odzyskać — bez ponownego zaciągania całej skrzynki.
        drugi = pg.evaluate("() => active(DB.machines)[1].id")
        pg.evaluate("""async () => {
          const st = await (await fetch('/api/data')).json();
          st.data.machines[1].serial = 'SM-9999-99';
          // Szafka 4 dostaje INNY zestaw niż w chwili przyjęcia sprzedaży.
          st.data.vending.layout['4'] = 'zest-przestawiony';
          await fetch('/api/data', {method:'PUT', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({rev: st.rev, data: st.data})});
        }""")
        pg.wait_for_timeout(400)

        # Przycisk stoi tam, gdzie problem — w karcie „Nierozpoznane" — i znika razem z nią.
        # Dlatego podsumowanie ląduje pod paskiem miesiąca, a nie w karcie: inaczej odpowiedź
        # na kliknięcie zniknęłaby w tej samej chwili, w której się pojawia.
        pg.evaluate("() => { SPRZ = null; SPRZ_WYNIK = null; go('sprzedaz'); }")
        pg.wait_for_timeout(900)
        check('karta „Nierozpoznane" ma przycisk dopasowania',
              pg.locator('#sprzDopasuj').count() == 1)
        pg.click('#sprzDopasuj')
        pg.wait_for_timeout(1200)
        podsum = pg.evaluate("() => SPRZ_WYNIK || ''")
        check('po kliknięciu widać, ile sprzedaży wróciło', 'Przypisano 1' in podsum, podsum)
        check('a przycisk znika razem z problemem, który miał rozwiązać',
              pg.locator('#sprzDopasuj').count() == 0)
        plik = json.load(open(f'{DATA}/sprzedaz-{ym}.json', encoding='utf-8'))
        check('i ma już swój automat', plik['<b@eldrut>'].get('maszyna') == drugi, plik['<b@eldrut>'])
        check('a powód zniknął razem z problemem', 'nieznane' not in plik['<b@eldrut>'])

        # NAJWAŻNIEJSZE: przestawienie szafki nie ma prawa przepisać historii. Sprzedaż raz
        # przypisana zostaje przy zestawie, który w tej szafce stał wtedy — inaczej jedna
        # zmiana układu cofnęłaby się przez wszystkie zamknięte miesiące.
        check('wpis przypisany wcześniej został przy SWOIM zestawie',
              plik['<a@eldrut>'].get('zestaw') == zestaw, plik['<a@eldrut>'])
        check('a zestaw z chwili przyjęcia zostaje, choć szafkę w międzyczasie przestawiono',
              plik['<b@eldrut>'].get('zestaw') == zestaw, plik['<b@eldrut>'])

        dop2 = pg.evaluate("""async () => (await (await fetch('/api/sprzedaz/dopasuj',
          {method:'POST'})).json())""")
        check('drugie kliknięcie nie ma już czego dopasować',
              dop2.get('przypisane') == 0 and dop2.get('sprawdzone') == 0, dop2)

        # Operator w temacie maila raz stawia spację przed myślnikiem, raz nie — wtedy
        # myślnik przykleja się do numeru. To dalej ta sama maszyna, a ogranicznik na
        # końcu napisu nie ma prawa decydować, do kogo trafią pieniądze.
        kod, odp = wyslij([{'msgId': '<c@eldrut>', 'serial': ' sm-0241-26- ', 'szafka': 4,
                            'kwota': 11.0, 'czas': teraz}])
        plik = json.load(open(f'{DATA}/sprzedaz-{ym}.json', encoding='utf-8'))
        check('ogranicznik doklejony do numeru nie gubi sprzedaży',
              plik['<c@eldrut>'].get('maszyna') == maszyna, plik['<c@eldrut>'])

        # NAJWAŻNIEJSZA REGUŁA TEGO MODUŁU: sprzedaż jest przypisana do NASZEGO
        # identyfikatora automatu, a numer seryjny służy tylko do rozpoznania w chwili
        # przyjęcia. Operator może jutro zmienić format maili albo same numery — i nic
        # z tego nie ma prawa przepisać nam historii wstecz. Dlatego przestawiamy numer
        # na inny automat i sprawdzamy, że przypisana sprzedaż ANI DRGNIE.
        pg.evaluate("""async () => {
          const st = await (await fetch('/api/data')).json();
          st.data.machines[0].serial = null;
          st.data.machines[2].serial = 'SM-0241-26';
          await fetch('/api/data', {method:'PUT', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({rev: st.rev, data: st.data})});
        }""")
        pg.wait_for_timeout(400)
        dop3 = pg.evaluate("""async () => (await (await fetch('/api/sprzedaz/dopasuj',
          {method:'POST'})).json())""")
        plik = json.load(open(f'{DATA}/sprzedaz-{ym}.json', encoding='utf-8'))
        check('przeniesienie numeru na inny automat nie rusza przypisanych sprzedaży',
              plik['<a@eldrut>'].get('maszyna') == maszyna, plik['<a@eldrut>'])
        check('ani ich nie odpina', 'nieznane' not in plik['<a@eldrut>'], plik['<a@eldrut>'])
        check('a dopasowanie w ogóle ich nie ogląda', dop3.get('sprawdzone') == 0, dop3)
        check('zestaw też stoi, gdzie stał',
              plik['<a@eldrut>'].get('zestaw') == zestaw, plik['<a@eldrut>'])

        check('pracownik nie dopasuje', pgA.evaluate(
              "async () => (await fetch('/api/sprzedaz/dopasuj', {method:'POST'})).status") == 403)
        check('podgląd też nie', pg3.evaluate(
              "async () => (await fetch('/api/sprzedaz/dopasuj', {method:'POST'})).status") == 403)

        # Sekcja sprząta po sobie: układ szafek wraca do tego, co zastała.
        pg.evaluate(f"""async () => {{
          const st = await (await fetch('/api/data')).json();
          st.data.vending.layout['4'] = '{zestaw}';
          await fetch('/api/data', {{method:'PUT', headers:{{'Content-Type':'application/json'}},
            body: JSON.stringify({{rev: st.rev, data: st.data}})}});
        }}""")
        pg.wait_for_timeout(400)

        # Eksport ma się tłumaczyć sam: same numery seryjne i identyfikatory zestawów
        # nic nie znaczą bez listy automatów i układu szafek.
        eks = pg.evaluate("""async () => {
          const r = await fetch('/api/sprzedaz/eksport');
          return {status: r.status, dysp: r.headers.get('content-disposition') || '',
                  tresc: await r.json().catch(()=>null)}; }""")
        check('eksport sprzedaży się pobiera', eks['status'] == 200, eks['status'])
        check('i przychodzi jako plik do zapisania', 'attachment' in eks['dysp']
              and 'sprzedaz-eksport-' in eks['dysp'], eks['dysp'])
        e = eks['tresc'] or {}
        check('niesie wszystkie miesiące', ym in (e.get('sprzedaz') or {}), list(e.get('sprzedaz') or {}))
        check('i tę samą sprzedaż, co plik na dysku',
              len((e.get('sprzedaz') or {}).get(ym) or {}) ==
              len(json.load(open(f'{DATA}/sprzedaz-{ym}.json', encoding='utf-8'))))
        # Bez tych dwóch rzeczy eksport jest workiem identyfikatorów.
        check('z numerami seryjnymi automatów',
              any(m.get('serial') for m in (e.get('automaty') or [])), e.get('automaty'))
        check('i z układem szafek', bool(e.get('szafki')), e.get('szafki'))
        check('a przy okazji mówi, z jakiej wersji pochodzi', bool(e.get('wersja')), e.get('wersja'))
        check('pracownik eksportu nie dostanie', pgA.evaluate(
              "async () => (await fetch('/api/sprzedaz/eksport')).status") == 403)

        # Eksport z Ustawień to JEDEN przycisk i jeden plik. Kopia zapasowa bez sprzedaży
        # byłaby kopią z dziurą dokładnie w miejscu pieniędzy, a dwa osobne eksporty obok
        # siebie znaczyłyby, że za każdym razem trzeba pamiętać, który jest ten pełny.
        pg.evaluate("() => { window.__plik = null; window.download = (n, t) => { window.__plik = t; }; }")
        pg.evaluate("() => go('set')")
        pg.wait_for_timeout(700)
        check('w Ustawieniach są oba eksporty',
              pg.locator('#expJson').count() == 1 and pg.locator('#expSprz').count() == 1)

        # Sama sprzedaż, bez półtoramegabajtowej bazy — do wysłania albo policzenia
        # poza aplikacją. Plik ma się tłumaczyć sam, więc niesie też automaty i szafki.
        pg.click('#expSprz')
        pg.wait_for_timeout(1500)
        sam = json.loads(pg.evaluate("() => window.__plik") or '{}')
        check('„Eksport sprzedaży" zapisuje samą sprzedaż',
              ym in (sam.get('sprzedaz') or {}) and 'ingredients' not in sam, list(sam))
        check('ale z kluczem do jej odczytania',
              bool(sam.get('automaty')) and bool(sam.get('szafki')), list(sam))
        pg.evaluate("() => { window.__plik = null; }")
        pg.click('#expJson')
        pg.wait_for_timeout(1500)
        zapis = pg.evaluate("() => window.__plik")
        check('„Eksport JSON" zapisał plik', bool(zapis), type(zapis).__name__)
        plikJ = json.loads(zapis) if zapis else {}
        check('a w pliku jest i baza, i sprzedaż',
              bool(plikJ.get('ingredients')) and ym in (plikJ.get('sprzedaz') or {}),
              list(plikJ.get('sprzedaz') or {}))
        check('ze wszystkimi pozycjami miesiąca',
              len(plikJ['sprzedaz'][ym]) ==
              len(json.load(open(f'{DATA}/sprzedaz-{ym}.json', encoding='utf-8'))))
        # Gdyby sprzedaż wróciła importem do bazy, pojechałaby do każdej przeglądarki
        # przy każdym wczytaniu — czyli tam, skąd ją celowo wyprowadziliśmy.
        check('a sama baza dalej sprzedaży nie zna',
              'sprzedaz' not in json.load(open(f'{DATA}/data.json', encoding='utf-8'))['data'])

        # Wykresy rysują się dopiero wtedy, gdy jest co rysować, więc sprawdzamy je tutaj,
        # na serwerze z prawdziwą sprzedażą, a nie w trybie offline.
        pg.evaluate("() => { SPRZ = null; SPRZ_WYK = null; SPRZ_WYNIK = null; go('sprzedaz'); }")
        pg.wait_for_timeout(2000)
        # `SPRZ` niesie dwa miesiące, bo kolumny „7 dni" i „30 dni" sięgają wstecz za
        # pierwszy dzień. Kafelki i zestawienia dotyczą jednak MIESIĄCA Z PASKA — bez
        # filtra pokazywały sumę dwóch miesięcy pod nazwą jednego.
        poprz = time.strftime('%Y-%m', time.localtime(teraz - 40 * 86400))
        wyslij([{'msgId': '<poprzedni@eldrut>', 'serial': 'SM-0241-26', 'szafki': [4],
                 'kwota': 999.0, 'czas': teraz - 40 * 86400}])
        pg.evaluate("() => { SPRZ = null; SPRZ_WYK = null; SPRZ_WYNIK = null; go('sprzedaz'); }")
        pg.wait_for_timeout(2000)
        biezacy = json.load(open(f'{DATA}/sprzedaz-{ym}.json', encoding='utf-8'))
        oczek = sum(1 for w in biezacy.values() if not w.get('nieznane'))
        kafel = pg.evaluate("() => +document.querySelector('.tiles .tile .val').textContent")
        check('kafelek liczy tylko miesiąc z paska, nie dwa naraz',
              poprz != ym and kafel == oczek, (kafel, oczek, poprz, ym))
        check('a kwota z tamtego miesiąca nie wsiąka w sumy', pg.evaluate(
              "() => [...document.querySelectorAll('.tiles .val')]"
              ".every(e => e.textContent.indexOf('999') < 0)"))

        check('są dwa wykresy: miesięczny i dzienny',
              pg.locator('#wykMies svg.wykres').count() == 1
              and pg.locator('#wykDzien svg.wykres').count() == 1)
        check('każdy ma własny przełącznik zakresu',
              pg.locator('[data-zakres="mies"] button').count() == 3
              and pg.locator('[data-zakres="dzien"] button').count() == 3)
        # Suma jest kilka razy wyższa od pojedynczego automatu — na wspólnej skali
        # przygniatałaby automaty do dołu, więc pasy mają OSOBNE osie. Poznajemy to po tym,
        # że wartości na osi nie tworzą jednego ciągu, tylko dwa.
        check('pasy mają osobne skale', pg.evaluate("""() => {
          const t = [...document.querySelectorAll('#wykMies text')]
            .map(e => Number(e.textContent.replace(/[^0-9]/g, '')))
            .filter(v => v > 0);
          return Math.max(...t) / Math.min(...t) > 2; }"""))
        check('a podpisów „cały lokal" i „automaty" nie ma — powtarzałyby legendę',
              pg.locator('#wykMies .pas').count() == 0)
        check('a przy liniach stoją podpisy, nie legenda pod spodem', pg.evaluate("""() => {
          const t = [...document.querySelectorAll('#wykMies .opis')].map(e => e.textContent);
          return t.indexOf('Razem') >= 0 && t.length >= 2; }"""))
        # Nazwa automatu bywa długa („Kaufland, Norymberska") i albo wychodzi poza kartę,
        # albo trzeba ją uciąć w połowie. Kod jest krótki, jednoznaczny i ten sam, którym
        # automat podpisany jest na załadunku.
        check('podpisy to KODY automatów, nie nazwy', pg.evaluate("""() => {
          const t = [...document.querySelectorAll('#wykMies .opis')].map(e => e.textContent);
          const kody = active(DB.machines).map(m => m.code);
          const nazwy = active(DB.machines).map(m => m.name).filter(n => kody.indexOf(n) < 0);
          return t.every(x => x === 'Razem' || kody.indexOf(x) >= 0)
                 && !t.some(x => nazwy.indexOf(x) >= 0); }"""))
        # Wykres szerszy od karty to dokładnie ta usterka, którą naprawialiśmy.
        check('wykres mieści się w karcie', pg.evaluate("""() => {
          const s = document.querySelector('#wykMies svg.wykres');
          const k = s.closest('.card');
          return s.getBoundingClientRect().width <= k.getBoundingClientRect().width + 1; }"""))
        # Oba wykresy liczą OKNA KROCZĄCE na każdy dzień: miesięczny sumuje 30 dni wstecz,
        # dzienny uśrednia 7. Miesiąc kalendarzowy jako punkt dawał dwanaście punktów w roku,
        # z których ostatni jest zawsze niepełny — i niczego nie mówił.
        okna = pg.evaluate("""() => {
          const d = {};
          for(let i = 0; i < 40; i++) d[przesunISO(todayISO(), -i)] = {m: 10};
          const w = oknaKroczace(d, 7, 30, false), s = oknaKroczace(d, 7, 7, true);
          return {suma: w.dla('m')[6], srednia: s.dla('m')[6],
                  pusto: oknaKroczace(d, 7, 30, false).dla('nie-ma')[6]}; }""")
        check('suma krocząca z 30 dni to suma trzydziestu dni', okna['suma'] == 300, okna)
        check('a średnia z 7 dni to średnia siedmiu', okna['srednia'] == 10, okna)
        check('automat bez danych nie dostaje zera, tylko przerwę', okna['pusto'] is None, okna)
        # Suma z trzydziestu dni policzona w trzecim dniu istnienia automatu jest sumą
        # z trzech dni i rysuje wzniesienie, którego nie było.
        # Rok, z którego znamy trzy miesiące, rysowany w całości to trzy czwarte pustego
        # panelu i dane ściśnięte w rogu — a szerokość jest tu tym, co pozwala coś odczytać.
        przyc = pg.evaluate("""() => {
          const d = {};
          for(let i = 0; i < 40; i++) d[przesunISO(todayISO(), -i)] = {m: 10};
          const w = oknaKroczace(d, 365, 30, false);
          return {ile: w.dni.length, od: w.dni[0], do: w.dni[w.dni.length-1],
                  dzis: todayISO(), pusto: w.razem.filter(v => v == null).length}; }""")
        check('zakres przycięty do tego, co naprawdę mamy',
              przyc['ile'] == 11 and przyc['do'] == przyc['dzis'], przyc)
        check('i nie ma w nim ani jednego pustego dnia', przyc['pusto'] == 0, przyc)

        check('niepełne okno to przerwa, nie zaniżona wartość', pg.evaluate("""() => {
          const d = {};
          for(let i = 0; i < 5; i++) d[przesunISO(todayISO(), -i)] = {m: 10};
          const w = oknaKroczace(d, 7, 30, false).dla('m');
          return w.every(v => v === null); }"""))

        check('trzeci wykres — dni tygodnia', pg.locator('#wykTydz svg.wykres').count() == 1)
        check('i on też ma swój przełącznik zakresu',
              pg.locator('[data-zakres="tydz"] button').count() == 3)
        # Oś pozioma tego wykresu to nie czas, tylko siedem dni tygodnia — jeśli podpisy
        # wyglądają jak daty, znaczy że rysuje się nie to źródło danych.
        check('na osi stoją dni tygodnia, nie daty', pg.evaluate("""() => {
          const t = [...document.querySelectorAll('#wykTydz text')].map(e => e.textContent);
          return ['pn','wt','śr','cz','pt','so','nd'].every(d => t.indexOf(d) >= 0); }"""))
        check('raport ma kolumnę na każdy dzień tygodnia i wiersz na zestaw',
              pg.evaluate("""() => {
          const t = document.querySelector('table[data-tbl="sprzRaport"]');
          if(!t) return false;
          const glowa = [...t.tHead.rows[0].cells].map(c => c.textContent.trim());
          return glowa.length === 8 && glowa.join(',') === 'Zestaw,pn,wt,śr,cz,pt,so,nd'
                 && t.tBodies[0].rows.length > 0; }"""))
        # Trzy rzeczy, które właściciel kazał usunąć, bo zaciemniały obraz.
        check('bez wiersza zbiorczego, bez liczników dni, bez przełącznika miar',
              pg.evaluate("""() => {
          const k = document.querySelector('table[data-tbl="sprzRaport"]').closest('.card');
          return k.textContent.indexOf('Wszystkie zestawy') < 0
                 && k.querySelector('table').textContent.indexOf('×') < 0
                 && !k.querySelector('[data-stat]'); }"""))
        # W komórce trzy liczby: mediana, średnia, maksimum — a w kolorze tekstu ta środkowa.
        check('w komórce trzy liczby rozdzielone ukośnikami', pg.evaluate("""() => {
          const t = document.querySelector('table[data-tbl="sprzRaport"]');
          const c = t.tBodies[0].rows[0].cells[1];
          const k = c.querySelector('.rapkom');
          if(!k || k.children.length !== 3) return false;
          // środkowe pole to średnia i tylko ono ma stać w kolorze tekstu — chyba że
          // cała komórka jest zerem, wtedy gaśnie razem z sąsiadami
          const sr = k.children[1];
          return /^[0-9,]+\/[0-9,]+\/[0-9,]+$/.test(c.textContent.trim())
                 && sr.classList.contains('s')
                 && k.children[0].classList.contains('mut')
                 && k.children[2].classList.contains('mut'); }"""))
        # Wyrównanie do prawej przesuwałoby średnią o tyle, o ile mediana jest dłuższa od
        # maksimum — i kolumna średnich przestawałaby być kolumną. Mierzymy to naprawdę.
        osKol = pg.evaluate("""() => {
          const t = document.querySelector('table.raport');
          const th = [...t.tHead.rows[0].cells];
          let max = 0, ile = 0;
          [...t.tBodies[0].rows].forEach(r => [...r.cells].forEach((c,i) => {
            const s = c.querySelector('.s'); if(!s) return;
            const a = s.getBoundingClientRect(), b = th[i].getBoundingClientRect();
            max = Math.max(max, Math.abs((a.left + a.right)/2 - (b.left + b.right)/2));
            ile++;
          }));
          const liczbowe = [...t.tBodies[0].rows].reduce((a,r)=>a
            + [...r.cells].filter(c => c.textContent.indexOf('/') >= 0).length, 0);
          return {ile: ile, liczbowe: liczbowe, max: Math.round(max * 100) / 100}; }""")
        # Mierzymy KAŻDĄ komórkę z liczbami, nie próbkę — inaczej asercja przechodziłaby
        # także wtedy, gdyby wyśrodkowana została jedna kolumna z siedmiu.
        check('średnia stoi dokładnie w osi swojej kolumny',
              osKol['ile'] > 3 and osKol['ile'] == osKol['liczbowe'] and osKol['max'] < 1,
              osKol)
        check('automat wybiera się z listy, nie z sześciu tabel', pg.evaluate("""() => {
          const s = document.getElementById('rapAut');
          return !!s && s.options.length === active(DB.machines).length + 1
                 && s.options[0].value === ''; }"""))
        check('układ tabeli przełącza się dwoma przyciskami', pg.evaluate("""() => {
          const b = [...document.querySelectorAll('[data-wg] button')].map(x => x.dataset.w);
          return b.join(',') === 'aut,dzien'; }"""))
        # W drugim układzie w kolumnach stoją automaty, a lista nad tabelą podaje dni —
        # gdyby przełącznik zmieniał tylko podpisy, tego byśmy nie zauważyli.
        check('przełączenie na dni tygodnia obraca tabelę', pg.evaluate("""async () => {
          document.querySelector('[data-wg] button[data-w="dzien"]').click();
          await new Promise(r => setTimeout(r, 700));
          const t = document.querySelector('table[data-tbl="sprzRaport"]');
          const glowa = [...t.tHead.rows[0].cells].map(c => c.textContent.trim());
          const s = document.getElementById('rapAut');
          const kody = active(DB.machines).map(m => m.code);
          const ok = glowa.length === active(DB.machines).length + 1
            && kody.every(k => glowa.some(g => g === k))
            && s.options.length === 7;
          document.querySelector('[data-wg] button[data-w="aut"]').click();
          await new Promise(r => setTimeout(r, 700));
          return ok && SPRZ_RAPORT.wg === 'aut'; }"""))
        check('wybór automatu z listy też przerysowuje', pg.evaluate("""async () => {
          const s = document.getElementById('rapAut');
          s.value = active(DB.machines)[0].id;
          s.dispatchEvent(new Event('change'));
          await new Promise(r => setTimeout(r, 600));
          const opis = document.querySelector('table[data-tbl="sprzRaport"]')
            .closest('.card').textContent;
          s.value = ''; s.dispatchEvent(new Event('change'));
          await new Promise(r => setTimeout(r, 600));
          return SPRZ_RAPORT.automat === ''
                 && opis.indexOf(active(DB.machines)[0].code) >= 0; }"""))
        # Raport liczy SZTUKI, więc jego suma musi zgadzać się z liczbą wpisów sprzedaży
        # w zakresie — nie z kwotami.
        check('przycisk wydruku stoi w karcie raportu', pg.evaluate("""() => {
          const b = document.querySelector('[data-act="pdfRaport"]');
          return !!b && !!b.closest('.card') &&
            b.closest('.card').querySelector('h2').textContent.indexOf('Raport sprzedaży') >= 0
            && !!b.closest('.card').querySelector('table[data-tbl="sprzRaport"]'); }"""))
        check('i naprawdę robi dokument', pg.evaluate("""() => {
          const stary = window.zrobPdf; let z = null;
          window.zrobPdf = (h, n) => z = {html: h, nazwa: n};
          document.querySelector('[data-act="pdfRaport"]').click();
          window.zrobPdf = stary;
          return !!z && z.nazwa === nazwaPlikuRaportu()
                 && z.nazwa.indexOf('raport-sprzedazy-wg-') === 0
                 && z.nazwa.indexOf(todayISO()) > 0
                 && z.html.indexOf('<table') >= 0; }"""))
        # Raport liczy SZTUKI, nie złotówki: suma maksimów po zestawach w danym dniu musi
        # zgadzać się z liczbą wpisów sprzedaży tego dnia, a nie z żadną kwotą.
        check('raport liczy sztuki, nie złotówki', pg.evaluate("""() => {
          const zapas = SPRZ_ZAKRES.raport;
          SPRZ_ZAKRES.raport = 7;
          const r = daneRaportu(null);
          const n = (new Date(todayISO() + 'T12:00:00').getDay() + 6) % 7;
          const zTabeli = r.wiersze.reduce((a,w)=>a + (w.d[n] ? w.d[n].maks : 0), 0);
          let zDanych = 0;
          Object.keys(SPRZ_WYK).forEach(k => {
            const w = SPRZ_WYK[k];
            if(!w || !w.czas || !w.zestaw) return;
            if(isoSprzedazy(w.czas) !== todayISO()) return;
            zDanych++; });
          SPRZ_ZAKRES.raport = zapas;
          return zTabeli === zDanych && zDanych > 0; }"""))
        check('a przełącznik zakresu naprawdę przerysowuje', pg.evaluate("""async () => {
          const przed = document.querySelector('#wykDzien svg.wykres').getAttribute('viewBox');
          document.querySelector('[data-zakres="dzien"] button[data-z="365"]').click();
          await new Promise(r => setTimeout(r, 900));
          const teraz = document.querySelectorAll('#wykDzien svg.wykres text').length;
          return teraz > 0 && SPRZ_ZAKRES.dzien === 365; }"""))

        print('\n== SPRZEDAŻ: KAFELEK I EKRAN ==')
        # Kafelek i ekran karmią się tym samym `/api/sprzedaz`, co Analizy, więc dopiero
        # tutaj — z prawdziwym serwerem i prawdziwymi wpisami — widać, czy liczą.
        # Jedna sprzedaż z nieznanego numeru seryjnego: taki wpis nie ma automatu, a mimo
        # to są to pieniądze z kasy i muszą się znaleźć w każdej kolumnie.
        wyslij([{'msgId': '<pulpit-nieznany@eldrut>', 'serial': 'SM-NIE-MA-TAKIEGO',
                 'szafki': [4], 'kwota': 12.34, 'czas': teraz}])
        pg.evaluate("""() => { DAY = todayISO(); SPRZ_PUL = null; SPRZ_PUL_KLUCZ = null;
          go('dHome'); }""")
        pg.wait_for_timeout(2500)
        check('właściciel ma kafelek sprzedaży na Pulpicie',
              pg.locator('#pulSprzedaz').count() == 1)
        # Rozwijana tabela w kafelku była pomyłką: na telefonie kafelek ma połowę rzędu,
        # a tabela z pięcioma kolumnami tam nie wchodzi. Sprzedaż dostała własny ekran —
        # tak samo, jak Grafik ma swój kalendarz, a nie rozwijaną miniaturę.
        check('kafelek jest odnośnikiem na ekran, a nie przełącznikiem', pg.evaluate("""() => {
          const k = document.getElementById('pulSprzedaz');
          return k.tagName === 'A' && k.dataset.go === 'dSprzedaz'
                 && !k.querySelector('.sekb') && !k.querySelector('.rozw')
                 && !k.querySelector('table') && !k.hasAttribute('aria-expanded'); }"""))
        # Wielka liczba to utarg wybranego dnia — po nią sięga się najczęściej; tydzień
        # i miesiąc stoją pod kreską, bo to już pytanie porównawcze.
        kafel = pg.evaluate("""() => {
          const k = document.getElementById('pulSprzedaz'), s = sumySprzedazyPulpit();
          return {duza: k.querySelector('.val').textContent.trim(),
                  pod: k.querySelector('.sub2').textContent.trim(),
                  lab: [...k.querySelectorAll('.okna .lab')].map(e => e.textContent.trim()),
                  kwoty: [...k.querySelectorAll('.okna b')].map(e => e.textContent.trim()),
                  // `.map(zl)` podałoby zl(kwota, indeks) i drugi argument obciąłby
                  // miejsca po przecinku — stąd jawna strzałka.
                  zRachunku: [s.razem.dzien, s.razem.d7, s.razem.d30].map(v => zl(v))}; }""")
        check('na kafelku utarg dnia dużą liczbą, 7 i 30 dni pod kreską',
              kafel['duza'] == kafel['zRachunku'][0] and kafel['pod'] == 'dziś'
              and kafel['lab'] == ['7 dni', '30 dni']
              and kafel['kwoty'] == kafel['zRachunku'][1:], kafel)
        # Suma jest tą samą sumą, którą liczą Analizy — dwa rachunki tych samych pieniędzy,
        # rozjeżdżające się o grosz, to pytanie, na które nikt nie umie odpowiedzieć.
        check('suma 30 dni policzona jeszcze raz, wprost z wpisów', pg.evaluate("""() => {
          const s = sumySprzedazyPulpit();
          let suma = 0;
          Object.keys(SPRZ_PUL).forEach(k => { const w = SPRZ_PUL[k];
            if(!w || !w.czas) return;
            const iso = isoSprzedazy(w.czas);
            if(iso > s.koniec || iso < przesunISO(s.koniec, -29)) return;
            suma += w.kwota || 0; });
          return Math.abs(suma - s.razem.d30) < 0.005 && suma > 0; }"""))
        # Ta sama nazwa stoi w Analizach — i to jest w porządku, tak samo jak „Zestawy"
        # stoją w Pulpicie (co złożyć dzisiaj) i w Edycji (jak zestaw jest zbudowany).
        check('w menu, w grupie Pulpit, zaraz za Grafikiem', pg.evaluate("""() => {
          const b = document.getElementById('navSprzPul');
          const w = [...b.closest('.navitems').children];
          return b.closest('.navitems').id === 'grp-pulpit'
                 && !b.classList.contains('hidden')
                 && w[w.indexOf(b) - 1].dataset.v === 'graf'
                 && b.querySelector('.lbl').textContent === 'Sprzedaż'; }"""))

        pg.click('#pulSprzedaz'); pg.wait_for_timeout(2000)
        check('kliknięcie kafelka otwiera ekran Sprzedaży', pg.evaluate("""() => {
          return VIEW === 'dSprzedaz'
                 && document.querySelector('.topbar h1').textContent.trim() === 'Sprzedaż'
                 && document.querySelector('.nav.on').dataset.v === 'dSprzedaz'; }"""))
        # Ekran należy do Pulpitu, więc chodzi za tym samym paskiem dnia, co reszta
        # Pulpitu — inaczej „dziś" na kafelku i „dziś" na ekranie znaczyłyby co innego.
        check('ekran ma pasek dnia', pg.locator('#ekrSprzedaz').count() == 1
              and pg.locator('.daybar').count() == 1)
        tab = pg.evaluate("""() => {
          const t = document.querySelector('table[data-tbl="pulSprz"]');
          const s = sumySprzedazyPulpit();
          const k = [...document.querySelectorAll('#ekrSprzedaz .tiles .tile')];
          return {glowa: [...t.tHead.rows[0].cells].map(c => c.textContent.trim()),
                  automaty: active(DB.machines).length,
                  wierszy: t.tBodies[0].rows.length,
                  nier: t.tBodies[0].innerText.indexOf('Nierozpoznane') >= 0,
                  suma: t.tBodies[0].rows[t.tBodies[0].rows.length-1].cells[0].textContent.trim(),
                  lab: k.map(e => e.querySelector('.lab').textContent.trim()),
                  val: k.map(e => e.querySelector('.val').textContent.trim()),
                  zRachunku: [s.razem.dzien, s.razem.d7, s.razem.d30].map(v => zl(v))}; }""")
        check('tabela: automat, dziś, wczoraj, 7 i 30 dni',
              tab['glowa'] == ['Automat', 'dziś', 'wczoraj', '7 dni', '30 dni'], tab)
        check('wiersz na automat, wiersz nierozpoznanych i „Razem"',
              tab['wierszy'] == tab['automaty'] + 2 and tab['nier']
              and tab['suma'] == 'Razem', tab)
        check('trzy kwoty nad tabelą to te same, co na kafelku',
              tab['lab'] == ['dziś', '7 dni', '30 dni'] and tab['val'] == tab['zRachunku'], tab)
        check('a wiersze sumują się do „Razem" w każdej kolumnie', pg.evaluate("""() => {
          const s = sumySprzedazyPulpit();
          return ['dzien','poprz','d7','d30'].every(k =>
            Math.abs(s.wiersze.reduce((a,w) => a + w[k], 0) + s.nier[k] - s.razem[k]) < 0.005); }"""))
        # Kreska w kolumnie „dziś" przy wierszu, który dokłada się do sumy pod spodem,
        # to kolumna, która się nie zgadza — a takiej nikt nie umie wytłumaczyć.
        check('nierozpoznane mają liczby w każdym oknie, nie tylko w najszerszym',
              pg.evaluate("""() => {
          const s = sumySprzedazyPulpit();
          return s.ileNier > 0 && s.nier.dzien > 0 && s.nier.d7 === s.nier.dzien
                 && s.nier.d30 === s.nier.dzien; }"""))
        # Dwa ekrany o tej samej nazwie muszą się do siebie przyznawać: tutaj pytamy
        # „ile dziś i z którego automatu", tam szukamy prawidłowości.
        check('z dołu ekranu prowadzi odnośnik do wykresów i raportu', pg.evaluate("""() => {
          const a = [...document.querySelectorAll('#ekrSprzedaz a[data-go="sprzedaz"]')];
          return a.length === 1 && a[0].textContent.indexOf('Wykresy i raport') >= 0; }"""))
        # „dziś" przy dniu sprzed dwóch dni byłoby po prostu nieprawdą, więc wtedy
        # w główkach stoją daty. Liczby idą za paskiem dnia, jak cały Pulpit.
        dzien = pg.evaluate("""async () => {
          DAY = przesunISO(todayISO(), -2); SPRZ_PUL_KLUCZ = null; go('dSprzedaz');
          await new Promise(r => setTimeout(r, 2200));
          const lab = [...document.querySelectorAll('#ekrSprzedaz .tiles .lab')]
            .map(e => e.textContent.trim());
          const glowa = [...document.querySelector('table[data-tbl="pulSprz"]')
            .tHead.rows[0].cells].map(c => c.textContent.trim());
          const s = sumySprzedazyPulpit();
          const wynik = {lab, glowa, koniec: s.koniec,
                         data: dataKrotko(przesunISO(todayISO(), -2)),
                         wczoraj: dataKrotko(przesunISO(todayISO(), -3))};
          DAY = todayISO(); SPRZ_PUL_KLUCZ = null; go('dSprzedaz');
          await new Promise(r => setTimeout(r, 2200));
          return wynik; }""")
        check('przy innym dniu w główkach stoją daty, nie „dziś" i „wczoraj"',
              dzien['lab'][0] == dzien['data'] and dzien['glowa'][2] == dzien['wczoraj']
              and dzien['koniec'] != time.strftime('%Y-%m-%d'), dzien)
        # Ekran wszedł przez `go()`, więc zostawił wpis w historii — „wstecz" musi wracać
        # na Pulpit, bo klawisza „Wróć" w aplikacji nie ma.
        pg.go_back(); pg.wait_for_timeout(1200)
        check('„wstecz" wraca z ekranu na Pulpit', pg.evaluate("() => VIEW") == 'dHome')

        # --- telefon ---
        # Sprzedaż jest tym, po co właściciel sięga po telefon najczęściej; przewijanie
        # pod sześć kafelków dnia zajmuje cały ekran.
        pg.set_viewport_size({'width': 390, 'height': 844})
        pg.evaluate("() => { go('dHome'); }"); pg.wait_for_timeout(1500)
        miejsce = pg.evaluate("""() => {
          const g = document.querySelector('.karta-graf').getBoundingClientRect();
          const s = document.getElementById('pulSprzedaz').getBoundingClientRect();
          const d = document.documentElement;
          return {tenSamRzad: Math.abs(g.top - s.top) < 4, poPrawej: s.left > g.left,
                  miesci: d.scrollWidth <= d.clientWidth + 1}; }""")
        check('na telefonie kafelek stoi w rzędzie Grafiku, po jego prawej',
              miejsce['tenSamRzad'] and miejsce['poPrawej'], miejsce)
        check('i nic nie wystaje poza szerokość ekranu', miejsce['miesci'], miejsce)
        pg.evaluate("() => go('dSprzedaz')"); pg.wait_for_timeout(1500)
        # Trzy kwoty w pudełkach obok siebie łamały się po „zł" na dwie linie; w słupku
        # każda ma całą szerokość ekranu.
        check('na ekranie kwoty stoją w słupku, każda w jednej linii', pg.evaluate("""() => {
          const k = [...document.querySelectorAll('#ekrSprzedaz .tiles .tile')];
          const d = document.documentElement;
          const lewe = new Set(k.map(e => Math.round(e.getBoundingClientRect().left)));
          return k.length === 3 && lewe.size === 1
                 && k.every(e => e.querySelector('.val').getBoundingClientRect().height < 34)
                 && d.scrollWidth <= d.clientWidth + 1; }"""))
        # Nazwa automatu („Kaufland, Norymberska") zawijała wiersz na trzy linie; kod jest
        # tą samą nazwą, którą automat nosi na wykresach, w raporcie i na załadunku.
        check('w tabeli zostaje sam kod automatu', pg.evaluate("""() => {
          const t = document.querySelector('table[data-tbl="pulSprz"]');
          return [...t.tBodies[0].rows[0].cells[0].querySelectorAll('.small')]
            .every(e => e.getBoundingClientRect().height === 0); }"""))
        pg.set_viewport_size({'width': 1280, 'height': 900}); pg.wait_for_timeout(600)
        pg.evaluate("() => go('dHome')"); pg.wait_for_timeout(800)

        # Pulpit ogląda też pracownik, a serwer wycina mu z bazy każdą cenę. Kafelek
        # i ekran z kwotami byłyby jedyną dziurą w tej zasadzie.
        pgA.evaluate("() => { go('dHome'); }"); pgA.wait_for_timeout(1500)
        check('pracownik nie widzi kafelka sprzedaży',
              pgA.locator('#pulSprzedaz').count() == 0)
        check('ani pozycji w menu', pgA.evaluate(
              "() => document.getElementById('navSprzPul').classList.contains('hidden')"))
        # Ukryta pozycja to nie zamknięte drzwi: adres można wpisać, a stan widoku wraca
        # z historii. Ekran musi odesłać sam z siebie.
        pgA.evaluate("() => go('dSprzedaz')"); pgA.wait_for_timeout(1200)
        check('a wejście na ekran odsyła go na Pulpit',
              pgA.evaluate("() => VIEW") == 'dHome')
        check('i nie ma na jego Pulpicie ani złotówki', pgA.evaluate(
              r"() => !/\d[\d  .,]*zł/.test(document.getElementById('main').innerText)"),
              pgA.locator('#main').inner_text()[:200])
        check('a danych i tak by nie dostał', pgA.evaluate(
              "async () => (await fetch('/api/sprzedaz?ym=%s')).status" % ym) == 403)

        # Jedyna droga, żeby przeprowadzić import od nowa: klucz po Message-ID nie wpuści
        # tych samych maili drugi raz, więc bez wyczyszczenia stare wpisy zostałyby na
        # zawsze. Dlatego polecenie istnieje — i dlatego nic nie kasuje bezpowrotnie.
        lista = run('sprzedaz').stdout
        check('polecenie pokazuje pliki sprzedaży', f'sprzedaz-{ym}.json' in lista, lista[:150])
        check('i samo z siebie niczego nie czyści', os.path.exists(f'{DATA}/sprzedaz-{ym}.json'))
        czysc = run('sprzedaz', '--wyczysc').stdout
        check('--wyczysc odkłada pliki do kopii', 'Odłożono' in czysc, czysc[:150])
        check('i sprzedaż jest pusta', not os.path.exists(f'{DATA}/sprzedaz-{ym}.json'))
        kopie = sorted(p for p in os.listdir(f'{DATA}/backup') if p.startswith('sprzedaz-'))
        check('ale nic nie zniknęło bezpowrotnie', bool(kopie)
              and os.path.exists(f'{DATA}/backup/{kopie[-1]}/sprzedaz-{ym}.json'), kopie)

        print('\n== ZAKUPY Z KSEF ==')
        # Faktury pobiera z KSeF ta sama automatyzacja, co sprzedaż z maili — więc ten sam
        # klucz w nagłówku i ta sama zasada: przeglądarka tu nie zagląda.
        def wyslijZ(wiersze, tok=None):
            zad = urllib.request.Request(
                f'http://127.0.0.1:{PORT}/api/zakupy',
                data=json.dumps({'zakupy': wiersze}).encode(),
                headers={'Content-Type': 'application/json',
                         'X-Token': klucz if tok is None else tok})
            try:
                with urllib.request.urlopen(zad, timeout=10) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read() or b'{}')

        check('bez klucza faktur nie przyjmiemy', wyslijZ([], tok='')[0] == 401)
        MAKRO, KSW, AUTO = '7010012345', '1234563218', '5252445211'
        dzis = time.strftime('%Y-%m-%d')
        dd = dzis.replace('-', '')
        def ksef(nip, i):
            return '%s-%s-%012X-%02X' % (nip, dd, i * 7919, i % 256)
        # Cena katalogowa kłamie u dostawcy, który rabatuje 117 pozycji ze 125 — dlatego
        # serwer liczy ją z wartości i ilości, a `CenaN` zapisuje tylko jako kontrolę.
        kod, wynikZ = wyslijZ([
            {'ksef': ksef(MAKRO, 1), 'poz': 1, 'data': dzis, 'dostawca': 'MAKRO',
             'opis': 'P MC ŁOS.ATL.FIL.TR.E', 'ilosc': 2.5, 'jm': 'kg',
             'CenaN': 66.99, 'CenaNRabat': 56.99, 'WartoscN': 142.475},
            {'ksef': ksef(MAKRO, 1), 'poz': 2, 'data': dzis, 'dostawca': 'MAKRO',
             'opis': 'MS FRYTURA 10L', 'ilosc': 1, 'jm': 'szt', 'WartoscN': 129.35},
            # bez pola `data` — datę wyjmujemy z drugiego segmentu numeru KSeF
            {'ksef': ksef(KSW, 2), 'poz': 1, 'dostawca': 'Kuchnie Świata',
             'P_7': 'Glony  Nori algi Gold 280g,100ark./10', 'P_8B': '3', 'P_8A': 'op',
             'P_11': '139,50'},
            {'ksef': 'bez-numeru', 'poz': 1, 'opis': 'coś'},
        ])
        check('faktury wchodzą jednym żądaniem', kod == 200 and wynikZ['przyjete'] == 3, wynikZ)
        # Wiersz nierozczytany ma wrócić z powodem, a nie zniknąć. Cichy `continue`
        # w pętli kosztował nas kiedyś cztery maile.
        check('a wiersz bez numeru KSeF wraca z powodem',
              len(wynikZ['odrzucone']) == 1 and 'KSeF' in wynikZ['odrzucone'][0], wynikZ)
        ymZ = dzis[:7]
        plikZ = json.load(open(f'{DATA}/zakupy-{ymZ}.json', encoding='utf-8'))
        wpis = plikZ[ksef(MAKRO, 1) + '|1']
        check('klucz to numer KSeF i numer pozycji', len(plikZ) == 3, list(plikZ))
        check('NIP wyjęty z numeru KSeF', wpis['nip'] == MAKRO, wpis)
        # 142,475 ÷ 2,5 = 56,99 — czyli cena PO rabacie, a nie katalogowe 66,99.
        check('cena jednostkowa policzona z wartości i ilości, nie z ceny katalogowej',
              abs(wpis['cena'] - 56.99) < 0.0001 and wpis['cenaN'] == 66.99, wpis)
        nori = plikZ[ksef(KSW, 2) + '|1']
        check('pola ze struktury KSeF (P_7, P_8B, P_11) też rozumiemy',
              abs(nori['cena'] - 46.5) < 0.0001 and nori['ilosc'] == 3, nori)
        check('data z numeru KSeF, gdy wiersz jej nie niesie', nori['data'] == dzis, nori)
        # Nazwa fakturowa wraca co tydzień z drobnymi różnicami w spacjach i wielkości
        # liter — dopasowanie ma być zrobione raz, więc rozpoznajemy postać znormalizowaną.
        check('klucz nazwy bez podwójnych spacji i wielkimi literami',
              nori['klucz'] == 'GLONY NORI ALGI GOLD 280G,100ARK./10', nori['klucz'])
        # Historyczne ściągnięcie roku puszcza się kilka razy — i to jest warunek, nie wygoda.
        _, powt = wyslijZ([{'ksef': ksef(MAKRO, 1), 'poz': 1, 'data': dzis,
                            'opis': 'P MC ŁOS.ATL.FIL.TR.E', 'ilosc': 2.5, 'WartoscN': 142.475}])
        check('powtórka tego samego importu nic nie dubluje',
              powt['powtorzone'] == 1 and powt['przyjete'] == 0
              and len(json.load(open(f'{DATA}/zakupy-{ymZ}.json', encoding='utf-8'))) == 3, powt)

        # --- czy tę fakturę już mamy? ---
        # Pobranie jednej faktury z KSeF kosztuje kilkadziesiąt sekund, więc n8n pyta
        # o to PRZED pobraniem. Pyta kluczem w nagłówku, bo to nie przeglądarka.
        def znane(pyt, tok=None):
            zad = urllib.request.Request(
                f'http://127.0.0.1:{PORT}/api/zakupy/znane?' + pyt,
                headers={'X-Token': klucz if tok is None else tok})
            try:
                with urllib.request.urlopen(zad, timeout=10) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read() or b'{}')

        kodZ, jest = znane('ksef=' + ksef(MAKRO, 1))
        check('faktura, którą mamy, jest rozpoznana po numerze KSeF',
              kodZ == 200 and jest['jest'] is True and jest['pozycji'] == 2
              and jest['miesiac'] == ymZ, jest)
        _, nieMa = znane('ksef=' + ksef(MAKRO, 999))
        check('a nieznanej nie udajemy, że mamy',
              nieMa['jest'] is False and nieMa['pozycji'] == 0, nieMa)

        # Numer KSeF niesie datę WYSŁANIA, a wpis leży pod datą WYSTAWIENIA. Faktura
        # wystawiona pod koniec miesiąca, a wysłana w następnym, siedzi w innym pliku,
        # niż mówi jej numer — szukanie po jednym miesiącu by jej nie znalazło i n8n
        # pobrałby ją drugi raz, płacąc za to minutą.
        # 200 dni wstecz, a nie 70: ekran Zakupów pokazuje domyślnie 90 dni i ta faktura
        # przestawiłaby liczniki w asercjach o ekranie. Test ma badać jedno naraz.
        dawno = time.strftime('%Y-%m-%d', time.localtime(teraz - 200 * 86400))
        wyslijZ([{'ksef': ksef(MAKRO, 77), 'poz': 1, 'data': dawno, 'dostawca': 'MAKRO',
                  'opis': 'ŁOSOŚ Z INNEGO MIESIĄCA', 'ilosc': 1, 'WartoscN': 57}])
        _, przelom = znane('ksef=' + ksef(MAKRO, 77))
        check('fakturę spod przełomu miesiąca też znajdujemy — szukamy po wszystkich',
              przelom['jest'] is True and przelom['miesiac'] == dawno[:7]
              and przelom['miesiac'] != ymZ, przelom)

        _, lista = znane('ym=' + ymZ)
        check('lista numerów z miesiąca', lista['ile'] == 2
              and ksef(MAKRO, 1) in lista['ksef']
              and ksef(MAKRO, 77) not in lista['ksef'], lista)
        _, zakres = znane('od=' + dawno[:7] + '&do=' + ymZ)
        check('i z zakresu miesięcy, jednym pytaniem',
              zakres['ile'] == 3 and ksef(MAKRO, 77) in zakres['ksef'], zakres)
        check('bez klucza nikt się nie dowie, co mamy', znane('ym=' + ymZ, tok='nie-ten')[0] == 401)
        check('a pytanie bez parametrów dostaje 400, nie pustą listę',
              znane('')[0] == 400, znane(''))

        # --- pomijany dostawca: odpada już na serwerze ---
        pg.evaluate("""async (nip) => {
          DB.zakupy.pomijaniNip = [nip]; save();
          await new Promise(r => setTimeout(r, 600)); }""", AUTO)
        pg.wait_for_timeout(800)
        _, autoW = wyslijZ([{'ksef': ksef(AUTO, 3), 'poz': 1, 'data': dzis,
                             'dostawca': 'AUTO-SERWIS', 'opis': 'PRZEGLĄD', 'ilosc': 1,
                             'WartoscN': 900}])
        check('faktura pomijanego dostawcy nie wchodzi do bazy',
              autoW['pominieci'] == 1 and autoW['przyjete'] == 0
              and len(json.load(open(f'{DATA}/zakupy-{ymZ}.json', encoding='utf-8'))) == 3, autoW)
        # Ale nie po cichu: liczba wraca w odpowiedzi, więc n8n wie, co się stało.
        check('i mówi wprost, ile odpadło', autoW['pominieci'] == 1, autoW)

        # --- odczyt ---
        odczytZ = pg.evaluate("""async (ym) => {
          const r = await fetch('/api/zakupy?ym=' + ym);
          return {status: r.status, ...(await r.json())}; }""", ymZ)
        check('właściciel czyta zakupy', odczytZ['status'] == 200
              and len(odczytZ.get('zakupy') or {}) == 3, odczytZ['status'])
        check('pracownik nie czyta zakupów, bo to ceny', pgA.evaluate(
              "async (ym) => (await fetch('/api/zakupy?ym=' + ym)).status", ymZ) == 403)
        check('konto podglądu też nie', pg3.evaluate(
              "async (ym) => (await fetch('/api/zakupy?ym=' + ym)).status", ymZ) == 403)

        # --- ekran ---
        pg.evaluate("() => { ZAK = null; ZAK_KLUCZ = null; go('zakupy'); }")
        pg.wait_for_timeout(2500)
        check('ekran Zakupów stoi w Analizach', pg.evaluate("""() => {
          const b = document.getElementById('navZakupy');
          return VIEW === 'zakupy' && b.closest('.navitems').id === 'grp-analizy'
                 && document.querySelector('.topbar h1').textContent.trim() === 'Zakupy'; }"""))
        check('pozycje pogrupowane po nazwie fakturowej, wszystkie czekają na decyzję',
              pg.evaluate("""() => {
          const g = zakGrupy();
          return g.length === 3 && g.every(x => x.stan === 'nowa')
                 && zakDoZrobienia() === 3; }"""))
        check('dostawcy rozpoznani po NIP-ie', pg.evaluate("""() => {
          const d = zakDostawcy();
          const makro = d.find(x => x.nip === '7010012345');
          const auto = d.find(x => x.nip === '5252445211');
          return makro && makro.pozycji === 2 && auto && auto.pomijany && !auto.pozycji; }"""))

        # --- dopasowanie do istniejącego składnika ---
        check('dopasowanie zapisuje składnik i przelicznik', pg.evaluate("""async () => {
          dlgZakDopasuj('P MC ŁOS.ATL.FIL.TR.E');
          await new Promise(r => setTimeout(r, 300));
          document.getElementById('zdIng').value = 'losos';
          document.getElementById('zdPrzel').value = '1000';
          [...document.querySelectorAll('#dlgFoot .btn')].find(b => b.textContent === 'Zapisz').click();
          await new Promise(r => setTimeout(r, 700));
          const d = DB.zakupy.dopasowania['P MC ŁOS.ATL.FIL.TR.E'];
          return !!d && d.ing === 'losos' && d.przelicz === 1000; }"""))
        # Kilogram z faktury na gramy w bazie: 56,99 ÷ 1000 × 1000 g w opakowaniu.
        check('propozycja ceny liczy się w jednostkach składnika', pg.evaluate("""() => {
          const p = zakPropozycje().find(x => x.ing.id === 'losos');
          return !!p && Math.abs(p.cena - 56.99) < 0.01 && p.dostaw === 1; }"""))

        # --- nowy składnik wprost z pozycji faktury ---
        check('z pozycji faktury da się od razu założyć składnik', pg.evaluate("""async () => {
          dlgZakDopasuj('GLONY NORI ALGI GOLD 280G,100ARK./10');
          await new Promise(r => setTimeout(r, 300));
          document.querySelector('[name="zdTryb"][value="nowy"]').click();
          document.getElementById('zdNazwa').value = 'Nori Gold z faktury';
          document.getElementById('zdKat').value = 'Suche';
          document.getElementById('zdUnit').value = 'ark.';
          const p = document.getElementById('zdPrzel');
          p.value = '100'; p.dispatchEvent(new Event('input'));
          await new Promise(r => setTimeout(r, 200));
          [...document.querySelectorAll('#dlgFoot .btn')].find(b => b.textContent === 'Zapisz').click();
          await new Promise(r => setTimeout(r, 700));
          const g = DB.ingredients.find(x => x.name === 'Nori Gold z faktury');
          const d = DB.zakupy.dopasowania['GLONY NORI ALGI GOLD 280G,100ARK./10'];
          // opakowanie idzie za przelicznikiem, a cena z faktur: 46,50 za op = 100 ark.
          return !!g && g.unit === 'ark.' && g.cat === 'Suche' && g.packQty === 100
                 && Math.abs(g.packPrice - 46.5) < 0.01 && !!d && d.ing === g.id; }"""))
        # Ta sama nazwa dwa razy to koniec z jedną prawdą o koszcie — ostrzegamy przed
        # zapisaniem, ale nie blokujemy, tak samo jak przy zajętej literze osoby.
        check('a przy nazwie, która już jest, staje ostrzeżenie', pg.evaluate("""async () => {
          dlgZakDopasuj('MS FRYTURA 10L');
          await new Promise(r => setTimeout(r, 300));
          document.querySelector('[name="zdTryb"][value="nowy"]').click();
          const n = document.getElementById('zdNazwa');
          n.value = 'Nori Gold z faktury'; n.dispatchEvent(new Event('input'));
          await new Promise(r => setTimeout(r, 200));
          const i = document.getElementById('zdNazwaInfo');
          const ok = i.classList.contains('uwaga-txt') && i.textContent.indexOf('już jest') > 0;
          DLG.close();
          return ok; }"""))

        # --- trzy poziomy pomijania ---
        check('pomijanie nazwy, dostawcy i pojedynczej dostawy', pg.evaluate("""() => {
          const k = 'MS FRYTURA 10L';
          DB.zakupy.pomijane[k] = true;
          const poNazwie = zakGrupy().find(g => g.klucz === k).stan;
          delete DB.zakupy.pomijane[k];
          const w = zakLista().find(x => x.klucz === k);
          DB.zakupy.pomijaneU[k + '|' + w.nip] = true;
          const poDostawcy = zakStanPoz(w);
          delete DB.zakupy.pomijaneU[k + '|' + w.nip];
          DB.zakupy.pomijanePoz[w.id] = true;
          const poDostawie = zakStanPoz(w);
          delete DB.zakupy.pomijanePoz[w.id];
          save();
          return poNazwie === 'pominieta' && poDostawcy === 'pominieta'
                 && poDostawie === 'pominieta' && zakStanPoz(w) === 'nowa'; }"""))

        # --- zatwierdzenie ceny ---
        cena = pg.evaluate("""() => {
          const przed = CALC.ing('losos').packPrice;
          const p = zakPropozycje().find(x => x.ing.id === 'losos');
          const ileHist = DB.history.length;
          zakZatwierdz(p);
          const g = CALC.ing('losos'), h = DB.history[DB.history.length - 1];
          return {przed: przed, po: g.packPrice, propozycja: p.cena,
                  wpisow: DB.history.length - ileHist, od: h.from, doo: h.to,
                  nota: h.note, ing: h.ingId}; }""")
        check('zatwierdzenie wpisuje cenę do składnika',
              abs(cena['po'] - cena['propozycja']) < 0.0001 and cena['po'] != cena['przed'], cena)
        # Historia cen nie może mieć dwóch rodzajów wpisów — inaczej przestaje być
        # jedną historią. Wpis jest ten sam, co przy ręcznej zmianie w Składnikach,
        # tylko z notatką mówiącą, skąd cena przyszła.
        check('i dokłada wpis do historii cen, z podaną fakturą',
              cena['wpisow'] == 1 and cena['ing'] == 'losos'
              and cena['od'] == cena['przed'] and cena['doo'] == cena['po']
              and 'Zakupy KSeF' in cena['nota'] and 'ŁOS' in cena['nota'], cena)

        # --- sprzątanie po pomijanym dostawcy ---
        _, ileAuto = wyslijZ([{'ksef': ksef(KSW, 4), 'poz': 9, 'data': dzis,
                               'opis': 'DO SPRZATNIECIA', 'ilosc': 1, 'WartoscN': 10}])
        sprz = pg.evaluate("""async (nip) => {
          const r = await fetch('/api/zakupy/sprzataj', {method: 'POST',
            headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nip: nip})});
          return {status: r.status, ...(await r.json())}; }""", KSW)
        check('sprzątanie usuwa z ksiąg wszystko od jednego dostawcy',
              sprz['status'] == 200 and sprz['usuniete'] == 2
              and all(w['nip'] != KSW for w in
                      json.load(open(f'{DATA}/zakupy-{ymZ}.json', encoding='utf-8')).values()), sprz)
        check('pracownik nie sprząta ksiąg', pgA.evaluate("""async (nip) => {
          const r = await fetch('/api/zakupy/sprzataj', {method: 'POST',
            headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nip: nip})});
          return r.status; }""", MAKRO) == 403)

        # --- pracownik nie widzi ekranu ---
        pgA.evaluate("() => go('zakupy')"); pgA.wait_for_timeout(1200)
        check('pracownik nie wchodzi na ekran Zakupów',
              pgA.evaluate("() => VIEW") != 'zakupy')

        # --- pomijanie dostawców grupowo ---
        # Po imporcie roku lista dostawców ma kilkadziesiąt pozycji, z czego połowa to
        # prąd, telefon i serwis auta. Odklikiwanie ich pojedynczo, każdego z osobnym
        # pytaniem o sprzątanie ksiąg, jest robotą na kwadrans.
        pasek = pg.evaluate("""async () => {
          ZAK_ZAZN = ['%s', '%s']; render();
          await new Promise(r => setTimeout(r, 400));
          const b = document.querySelector('[data-zpomin-grupa]');
          const o = document.querySelector('[data-zodznacz]');
          return {jest: !!b, napis: b ? b.textContent.trim() : '', odznacz: !!o,
                  zaznaczonych: [...document.querySelectorAll('[data-znipsel]')]
                    .filter(c => c.checked).length}; }""" % (MAKRO, KSW))
        check('zaznaczenie dwóch dostawców pokazuje pasek działań',
              pasek['jest'] and pasek['odznacz'] and pasek['zaznaczonych'] == 2, pasek)
        # Sprzątanie ksiąg zostawiamy odznaczone: tu badamy samo pomijanie, a kasowanie
        # po jednym NIP-ie ma już własną asercję wyżej.
        grupowo = pg.evaluate("""async () => {
          document.querySelector('[data-zpomin-grupa]').click();
          await new Promise(r => setTimeout(r, 400));
          const wierszy = document.querySelectorAll('#dlgBody table tbody tr').length;
          const sprz = document.getElementById('zgSprzataj');
          const bylo = !!sprz && sprz.checked;
          if(sprz) sprz.checked = false;
          [...document.querySelectorAll('#dlgFoot .btn')]
            .find(x => x.textContent === 'Pomijaj').click();
          await new Promise(r => setTimeout(r, 800));
          return {wierszy, bylo, lista: (DB.zakupy.pomijaniNip || []).slice(),
                  zazn: ZAK_ZAZN.length}; }""")
        check('jedno okno wymienia wszystkich zaznaczonych', grupowo['wierszy'] == 2, grupowo)
        # Sprzątanie zaproponowane, a nie wykonane po cichu — kasowanie wpisów jest
        # nieodwracalne po naszej stronie, więc ma być decyzją, nie skutkiem ubocznym.
        check('i proponuje sprzątnięcie ksiąg, zaznaczone domyślnie', grupowo['bylo'], grupowo)
        check('obaj dostawcy trafiają na listę pomijanych jednym kliknięciem',
              MAKRO in grupowo['lista'] and KSW in grupowo['lista'], grupowo)
        check('a zaznaczenie po akcji znika', grupowo['zazn'] == 0, grupowo)
        # Przywrócenie niczego nie kasuje, więc idzie bez pytania.
        wrocili = pg.evaluate("""async () => {
          ZAK_ZAZN = (DB.zakupy.pomijaniNip || []).slice(); render();
          await new Promise(r => setTimeout(r, 400));
          const b = document.querySelector('[data-zprzywroc-grupa]');
          const napis = b ? b.textContent.trim() : '';
          if(b) b.click();
          await new Promise(r => setTimeout(r, 600));
          return {napis, lista: (DB.zakupy.pomijaniNip || []).slice()}; }""")
        check('grupowe przywrócenie zdejmuje ich z listy bez pytania',
              wrocili['lista'] == [] and 'Przywróć' in wrocili['napis'], wrocili)

        # --- paczka eksportowa z KSeF ---
        # Pobieranie faktura po fakturze nie nadaje się do importu historycznego (64
        # zapytania na godzinę), więc rok wchodzi paczkami: ZIP zaszyfrowany AES-256-CBC,
        # pocięty na części. Budujemy taką paczkę naprawdę — z prawdziwym openssl-em,
        # prawdziwym ZIP-em i XML-ami w układzie FA — bo test na atrapie sprawdzałby
        # wyłącznie to, że atrapa pasuje do kodu.
        import base64 as _b64, zipfile as _zip

        def _faktura(nip, nazwa, dzien, poz):
            w = ''.join(
                '<FaWiersz><NrWierszaFa>%d</NrWierszaFa><P_7>%s</P_7><P_8A>%s</P_8A>'
                '<P_8B>%s</P_8B><P_9A>%s</P_9A><P_11>%s</P_11><P_12>5</P_12></FaWiersz>'
                % (i + 1, x[0], x[1], x[2], x[3], x[4]) for i, x in enumerate(poz))
            return ('<?xml version="1.0" encoding="UTF-8"?>'
                    '<Faktura xmlns="http://crd.gov.pl/wzor/2023/06/29/12648/">'
                    '<Podmiot1><DaneIdentyfikacyjne><NIP>%s</NIP><Nazwa>%s</Nazwa>'
                    '</DaneIdentyfikacyjne></Podmiot1>'
                    '<Fa><KodWaluty>PLN</KodWaluty><P_1>%s</P_1>%s</Fa></Faktura>'
                    % (nip, nazwa, dzien, w)).encode('utf-8')

        pk1 = ksef(MAKRO, 501)
        pk2 = ksef(KSW, 502)
        bufor = io.BytesIO()
        with _zip.ZipFile(bufor, 'w', _zip.ZIP_DEFLATED) as z:
            z.writestr(pk1 + '.xml', _faktura(MAKRO, 'MAKRO', dawno,
                       [('P MC ŁOS.ATL.FIL.TR.E', 'kg', '2.5', '66.99', '142.475'),
                        ('OGÓREK 5KG', 'szt', '2', '32.99', '63.00')]))
            # Plik w podkatalogu — dopasowanie po nazwie musi to znieść.
            z.writestr('faktury/' + pk2 + '.xml', _faktura(KSW, 'Kuchnie Świata', dawno,
                       [('Glony Nori algi Gold 280g,100ark./10', 'op', '3', '46.50', '139.50')]))
            # Faktura, której metadane nie znają — ma wrócić na listę, nie zniknąć.
            z.writestr('bez-numeru.xml', _faktura(MAKRO, 'MAKRO', dawno,
                       [('COKOLWIEK', 'szt', '1', '10.00', '10.00')]))
            z.writestr('_metadata.json', json.dumps(
                [{'ksefNumber': pk1, 'fileName': pk1 + '.xml'},
                 {'ksefNumber': pk2, 'fileName': pk2 + '.xml'}], ensure_ascii=False))

        kat = os.path.join(DATA, 'paczka-test')
        os.makedirs(kat, exist_ok=True)
        jawna = os.path.join(kat, 'paczka.zip')
        with open(jawna, 'wb') as f:
            f.write(bufor.getvalue())
        kluczB, ivB = os.urandom(32), os.urandom(16)
        zaszyfrowana = os.path.join(kat, 'paczka.aes')
        subprocess.run(['openssl', 'enc', '-aes-256-cbc', '-K', kluczB.hex(),
                        '-iv', ivB.hex(), '-in', jawna, '-out', zaszyfrowana], check=True)
        bajty = open(zaszyfrowana, 'rb').read()
        # Części to kawałki JEDNEGO strumienia — sklejenie przed odszyfrowaniem jest
        # warunkiem, nie wygodą. Dlatego tniemy paczkę na dwie i podajemy obie.
        cz1 = os.path.join(kat, 'ksef-cz01.zip.aes')
        cz2 = os.path.join(kat, 'ksef-cz02.zip.aes')
        with open(cz1, 'wb') as f:
            f.write(bajty[:len(bajty) // 2])
        with open(cz2, 'wb') as f:
            f.write(bajty[len(bajty) // 2:])
        plikKlucza = os.path.join(kat, 'ksef-klucz.json')
        with open(plikKlucza, 'w', encoding='utf-8') as f:
            json.dump({'okno': dawno[:7], 'algorytm': 'AES-256-CBC',
                       'kluczBase64': _b64.b64encode(kluczB).decode(),
                       'ivBase64': _b64.b64encode(ivB).decode()}, f)

        wyjscie = run('zakupy', '--paczka', cz1, cz2, '--klucz', plikKlucza).stdout
        check('paczka z dwóch części odszyfrowana i wczytana',
              'Przyjęte: 3' in wyjscie, wyjscie[-400:])
        # Faktura bez numeru KSeF nie ma klucza, więc nie ma jak jej zapisać — ale
        # zniknięcie bez śladu jest gorsze niż jawnie zgłoszony brak.
        check('a faktura bez numeru KSeF zgłoszona, nie połknięta',
              'bez numeru KSeF' in wyjscie and 'bez-numeru.xml' in wyjscie, wyjscie[-400:])
        plikPacz = json.load(open(f'{DATA}/zakupy-{dawno[:7]}.json', encoding='utf-8'))
        # 142,475 ÷ 2,5 = 56,99 — cena po rabacie, nie katalogowe 66,99 z P_9A.
        wpisP = plikPacz[pk1 + '|1']
        check('cena z paczki liczona tak samo, jak z n8n',
              abs(wpisP['cena'] - 56.99) < 0.0001 and wpisP['cenaN'] == 66.99, wpisP)
        check('dostawca i data wzięte z XML-a',
              wpisP['dostawca'] == 'MAKRO' and wpisP['data'] == dawno, wpisP)
        check('faktura z podkatalogu też weszła', (pk2 + '|1') in plikPacz, list(plikPacz))
        # Ten sam klucz, co przy n8n — więc paczkę można wczytać drugi raz bez szkody.
        znowu = run('zakupy', '--paczka', cz1, cz2, '--klucz', plikKlucza).stdout
        check('powtórne wczytanie tej samej paczki nic nie dubluje',
              'Przyjęte: 0' in znowu and 'powtórzone: 3' in znowu, znowu[-300:])
        # Paczka już odszyfrowana (albo z innego źródła) ma wejść bez klucza.
        bezKlucza = run('zakupy', '--paczka', jawna).stdout
        check('zwykły ZIP wchodzi bez klucza', 'powtórzone: 3' in bezKlucza, bezKlucza[-300:])
        brak = run('zakupy', '--paczka', cz1, cz2)
        check('a zaszyfrowana bez klucza mówi wprost, czego brakuje',
              'podaj plik klucza' in (brak.stdout + brak.stderr), (brak.stdout + brak.stderr)[-300:])

        # --- ta sama paczka, ale wgrana z przeglądarki ---
        # Bez tego okna paczkę trzeba wnieść na serwer przez scp i konsolę — czyli zejść
        # z aplikacji do powłoki, żeby zrobić rzecz, która jest częścią pracy z zakupami.
        pk3 = ksef(KSW, 503)
        bufor2 = io.BytesIO()
        with _zip.ZipFile(bufor2, 'w', _zip.ZIP_DEFLATED) as z:
            z.writestr(pk3 + '.xml', _faktura(KSW, 'Kuchnie Świata', dawno,
                       [('Ryż Seijou Calrose 9,07kg', 'op', '4', '59.00', '236.00')]))
            z.writestr('_metadata.json', json.dumps(
                [{'ksefNumber': pk3, 'fileName': pk3 + '.xml'}], ensure_ascii=False))
        jawna2 = os.path.join(kat, 'paczka2.zip')
        with open(jawna2, 'wb') as f:
            f.write(bufor2.getvalue())
        klucz2, iv2 = os.urandom(32), os.urandom(16)
        szyfr2 = os.path.join(kat, 'paczka2.aes')
        subprocess.run(['openssl', 'enc', '-aes-256-cbc', '-K', klucz2.hex(),
                        '-iv', iv2.hex(), '-in', jawna2, '-out', szyfr2], check=True)
        bajty2 = open(szyfr2, 'rb').read()
        polowa = len(bajty2) // 2
        ladunek = {
            'czesci': [{'nazwa': 'ksef-cz02.zip.aes',
                        'b64': _b64.b64encode(bajty2[polowa:]).decode()},
                       {'nazwa': 'ksef-cz01.zip.aes',
                        'b64': _b64.b64encode(bajty2[:polowa]).decode()}],
            'klucz': {'kluczBase64': _b64.b64encode(klucz2).decode(),
                      'ivBase64': _b64.b64encode(iv2).decode()}}

        async_fetch = """async (d) => {
          const r = await fetch('/api/zakupy/paczka', {method: 'POST',
            headers: {'Content-Type': 'application/json'}, body: JSON.stringify(d)});
          return Object.assign({status: r.status}, await r.json()); }"""
        # Części podajemy CELOWO w złej kolejności: serwer ma je poukładać po nazwie,
        # bo to kawałki jednego strumienia i sklejone na odwrót dają śmieci.
        wgr = pg.evaluate(async_fetch, ladunek)
        check('paczka wgrana z przeglądarki wchodzi tak samo, jak z konsoli',
              wgr['status'] == 200 and wgr['przyjete'] == 1 and wgr['pozycji'] == 1, wgr)
        check('a części sklejone po nazwie, nie w kolejności wysyłki',
              (pk3 + '|1') in json.load(open(f'{DATA}/zakupy-{dawno[:7]}.json', encoding='utf-8')))
        wgr2 = pg.evaluate(async_fetch, ladunek)
        check('drugie wgranie tej samej paczki nic nie dubluje',
              wgr2['przyjete'] == 0 and wgr2['powtorzone'] == 1, wgr2)
        # Zły klucz to najczęstsza pomyłka przy ręcznym wgrywaniu — ma o tym powiedzieć,
        # a nie zapisać śmieci albo milczeć.
        zlyKlucz = dict(ladunek)
        zlyKlucz['klucz'] = {'kluczBase64': _b64.b64encode(os.urandom(32)).decode(),
                             'ivBase64': _b64.b64encode(os.urandom(16)).decode()}
        zle = pg.evaluate(async_fetch, zlyKlucz)
        check('zły klucz kończy się jasnym błędem, nie zapisem śmieci',
              zle['status'] == 400 and 'odszyfrowa' in (zle.get('error') or ''), zle)
        check('a pracownik paczki nie wgra', pgA.evaluate(async_fetch, ladunek)['status'] == 403)

        # --- polecenie konsoli, bliźniak `sushi sprzedaz` ---
        listaZ = run('zakupy').stdout
        check('polecenie pokazuje pliki zakupów', f'zakupy-{ymZ}.json' in listaZ, listaZ[:150])
        czyscZ = run('zakupy', '--wyczysc').stdout
        check('--wyczysc odkłada je do kopii i zostawia puste miejsce',
              'Odłożono' in czyscZ and not os.path.exists(f'{DATA}/zakupy-{ymZ}.json'), czyscZ[:150])
        kopieZ = sorted(p for p in os.listdir(f'{DATA}/backup') if p.startswith('zakupy-'))
        check('ale nic nie ginie bezpowrotnie', bool(kopieZ)
              and os.path.exists(f'{DATA}/backup/{kopieZ[-1]}/zakupy-{ymZ}.json'), kopieZ)

        check('brak błędów JS u pracownika', not bledyA, bledyA[:2])
        ctxA.close()

        print('\n== KEEP-ALIVE PO ODMOWIE ==')
        # 403 bez wyczytania treści zostawia bajty w gnieździe i psuje NASTĘPNE
        # zapytanie na tym samym połączeniu — dokładnie ten błąd wrócił z PDF-em
        import http.client
        ciasteczko = [c for c in ctx3.cookies() if c['name'] == 'sp_session'][0]['value']
        con = http.client.HTTPConnection('127.0.0.1', PORT, timeout=10)
        tresc = json.dumps({'rev': 1, 'data': {'x': 'y' * 5000}})
        con.request('PUT', '/api/data', body=tresc,
                    headers={'Content-Type': 'application/json',
                             'Cookie': 'sp_session=' + ciasteczko})
        r1 = con.getresponse(); r1.read()
        check('zapis konta podglądu odrzucony (403)', r1.status == 403, r1.status)
        con.request('GET', '/api/health')
        r2 = con.getresponse(); tresc2 = r2.read()
        check('następne żądanie na tym samym połączeniu jest zdrowe',
              r2.status == 200 and b'"ok"' in tresc2, (r2.status, tresc2[:80]))
        con.close()

        print('\n== AKTUALIZACJA ==')
        wersja_pliku = open(f'{BASE}/VERSION').read().strip()
        chk = pg.evaluate("""async () => {
          const r = await fetch('/api/update/check');
          return {status:r.status, ...(await r.json())};
        }""")
        check('/api/update/check odpowiada właścicielowi', chk['status'] == 200, chk)
        check('podaje zainstalowaną wersję', chk.get('version') == wersja_pliku,
              (chk.get('version'), wersja_pliku))
        check('wykrywa dostępną aktualizację', chk.get('available') is True, chk)
        check('oddaje log sprawdzenia', 'nowy wydruk PDF' in (chk.get('output') or ''), chk)

        odm = pg3.evaluate("""async () => { const r = await fetch('/api/update/check');
          return {status:r.status, txt:(await r.text()).slice(0,120)}; }""")
        check('konto podglądu nie aktualizuje (403)', odm['status'] == 403, odm)

        st = pg.evaluate("async () => (await fetch('/api/update/status')).json()")
        check('status podaje, że nic nie trwa', st.get('busy') is False, st)

        uruch = pg.evaluate("async () => (await fetch('/api/update/run',{method:'POST'})).status")
        check('uruchomienie aktualizacji', uruch == 200, uruch)
        trwalo = False
        for _ in range(40):
            st = pg.evaluate("async () => (await fetch('/api/update/status')).json()")
            if st.get('busy'):
                trwalo = True
            elif trwalo:
                break
            time.sleep(0.5)
        check('status pokazywał instalację w toku', trwalo)
        check('log doszedł do końca', 'Zaktualizowano do' in (st.get('log') or ''), st.get('log'))
        check('powtórny start w trakcie odrzucony albo przyjęty po zakończeniu',
              pg.evaluate("async () => (await fetch('/api/update/run',{method:'POST'})).status")
              in (200, 409))

        zdr = pg.evaluate("async () => (await fetch('/api/health')).json()")
        check('/api/health podaje wersję', zdr.get('version') == wersja_pliku, zdr)

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
        # Wylogowanie jest w menu, nie w Ustawieniach: w karcie Serwer stało obok
        # „Pobierz dane z serwera" i „Sprawdź aktualizacje" — trzy przyciski, z których
        # każdy robił coś zupełnie innego.
        check('w karcie serwera nie ma już drugiego wylogowania',
              pg.locator('#srvOut').count() == 0)
        check('a pobranie danych nazywa się tym, czym jest',
              'Pobierz dane z serwera' in pg.locator('#main').inner_text())
        pg.click('#navOut')
        # Czekamy na EKRAN, nie na zegar: wylogowanie idzie żądaniem do serwera i przy
        # zajętym serwerze potrafiło nie zdążyć w 1,5 s — asercja padała raz na kilka
        # przebiegów, w miejscu, które z niczym nie miało związku.
        # Trzeci raz ta sama asercja zamigała, więc czekamy dłużej i pod koniec pytamy
        # jeszcze serwera. Wylogowanie to żądanie sieciowe, a testy chodzą obok siebie
        # z drugą przeglądarką i serwerem KSeF-em w tle — osiem sekund bywa za mało.
        try:
            pg.wait_for_selector('#loginForm', timeout=20000)
        except Exception:
            pass
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
        # Ikonę i manifest przeglądarka pobiera, ZANIM ktokolwiek zdąży się zalogować.
        # Gdyby stały za logowaniem, iPhone powiesiłby na pulpicie pustą kratkę.
        def pobierz(path):
            req = urllib.request.Request(URL + path)
            try:
                r = urllib.request.urlopen(req, timeout=5)
                return r.status, r.headers.get('Content-Type', ''), r.read()
            except urllib.error.HTTPError as e:
                return e.code, '', b''
        kod, ctype, body = pobierz('/apple-touch-icon.png')
        check('ikona wychodzi bez logowania', kod == 200, kod)
        check('i jest prawdziwym PNG-iem', body[:8] == b'\x89PNG\r\n\x1a\n', body[:8])
        check('podana jako obrazek', 'image/png' in ctype, ctype)
        check('ta sama ikona leży pod /ikona.png', pobierz('/ikona.png')[2] == body)
        kodM, ctypeM, bodyM = pobierz('/manifest.webmanifest')
        check('manifest wychodzi bez logowania', kodM == 200, kodM)
        mj = json.loads(bodyM.decode('utf-8'))
        # `standalone` to jest właśnie ten tryb bez paska przeglądarki, dla którego
        # aplikacja ma własny pasek nawigacji na dole ekranu.
        check('manifest zamawia tryb aplikacji', mj.get('display') == 'standalone', mj.get('display'))
        check('i pokazuje na ikonę, która naprawdę istnieje',
              bool(mj.get('icons')) and all(i['src'] == '/ikona.png' for i in mj['icons']),
              mj.get('icons'))
        check('kolory z identyfikacji, nie domyślne',
              mj.get('theme_color') == '#BD172F', mj.get('theme_color'))

        check('/api/health działa', status('/api/health') == 200)
        check('/api/pdf bez ciasteczka = 401', status('/api/pdf', 'POST') == 401)
        check('/api/update/check bez ciasteczka = 401', status('/api/update/check') == 401)
        check('/api/update/run bez ciasteczka = 401', status('/api/update/run', 'POST') == 401)

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
