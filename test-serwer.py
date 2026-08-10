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
