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
r = run('adduser', 'kuchnia@lokal.pl', 'chef', stdin='tajnehaslo2\ntajnehaslo2\n')
check('dodanie kucharza', 'Dodano konto' in r.stdout, r.stdout + r.stderr)
r = run('adduser', 'podglad@lokal.pl', 'viewer', stdin='tajnehaslo3\ntajnehaslo3\n')
check('dodanie konta podglądu', 'Dodano konto' in r.stdout, r.stdout + r.stderr)
r = run('adduser', 'ania@lokal.pl', 'staff', stdin='tajnehaslo4\ntajnehaslo4\n')
check('dodanie konta pracownika', 'Dodano konto' in r.stdout, r.stdout + r.stderr)
r = run('adduser', 'zly@lokal.pl', 'chef', stdin='krotkie\nkrotkie\n')
check('odrzucenie zbyt krótkiego hasła', 'co najmniej 8' in r.stdout, r.stdout)
r = run('users')
check('lista kont pokazuje 4 konta', r.stdout.count('@lokal.pl') == 4, r.stdout)
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
        check('podgląd widzi dane', pg3.evaluate("() => DB.items.length") >= 23)
        check('plakietka pokazuje podgląd', 'podgląd' in pg3.locator('#syncBadge').inner_text(),
              pg3.locator('#syncBadge').inner_text())
        pg3.click('.nav[data-v="ing"]')
        pg3.wait_for_timeout(400)
        # edycja jest teraz w kafelku, więc tam sprawdzamy, czy konto podglądu jej nie widzi
        if pg3.locator('[data-viewgroup="ing"] button[data-vm="cards"]').count():
            pg3.click('[data-viewgroup="ing"] button[data-vm="cards"]')
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
              == {'szef@lokal.pl': 'owner', 'kuchnia@lokal.pl': 'chef',
                  'podglad@lokal.pl': 'viewer', 'ania@lokal.pl': 'staff'},
              lista['users'])
        check('konto podglądu nie widzi listy',
              pg3.evaluate("async () => (await fetch('/api/users')).status") == 403)

        check('krótkie hasło odrzucone',
              api('/api/users', {'email': 'nowy@lokal.pl', 'role': 'chef', 'password': 'krotkie'})
              ['status'] == 400)
        check('konto dodane',
              api('/api/users', {'email': 'nowy@lokal.pl', 'role': 'chef',
                                 'password': 'dlugiehaslo1'})['status'] == 200)
        check('duplikat odrzucony',
              api('/api/users', {'email': 'nowy@lokal.pl', 'role': 'chef',
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
              api('/api/users/update', {'email': 'szef@lokal.pl', 'role': 'chef'})['status'] == 400)
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
              and pg.locator('#uKolory .kolorbtn').count() == 9)
        check('skrót ograniczony do sześciu znaków',
              pg.evaluate("() => document.getElementById('uSkrot').maxLength") == 6)
        pg.fill('#uNazwa', 'Kasia Kucharska')
        pg.fill('#uSkrot', 'kasia')
        pg.click('#uKolory .kolorbtn[data-kolor="#2E6FB7"]')
        pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(1200)
        os_kasia = pg.evaluate("() => osobaZMaila('kuchnia@lokal.pl', false)")
        check('nazwa, skrót i kolor zapisane przy koncie',
              os_kasia and os_kasia['name'] == 'Kasia Kucharska'
              and os_kasia['code'] == 'kasia' and os_kasia['color'] == '#2E6FB7', os_kasia)
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
              {'email':'doskasowania@lokal.pl', 'role':'chef', 'password':'dlugiehaslo1'})['status'] == 200)
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


        print('\n== GRAFIK: KONTO PRACOWNIKA ==')
        # Cała rzecz sprowadza się do jednego pytania: czy konto założone po to,
        # żeby ktoś zapisał się na zmianę, może przy okazji zobaczyć albo zmienić
        # cokolwiek innego. Odpowiedź musi brzmieć „nie" na każdej ścieżce.
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
        check('pracownik nie dostaje składników', dane['data']['ingredients'] == [], dane['data'].get('ingredients'))
        check('ani receptur rolek', dane['data']['items'] == [])
        check('ani zestawów i cen', dane['data']['sets'] == [] and dane['data']['settings'] == {})
        check('ale dostaje szablon zmian', bool(dane['data'].get('shiftTpl')), list(dane['data'].keys()))
        surowe = json.dumps(dane)
        check('w odpowiedzi nie ma ani jednej ceny zakupu',
              '"pricePack"' not in surowe and '"priceVending"' not in surowe, surowe[:200])

        check('pracownik nie zapisze całej bazy',
              pgA.evaluate("""async () => (await fetch('/api/data',{method:'PUT',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({rev:0,data:{ingredients:[]}})})).status""") == 403)
        check('pracownik nie widzi listy kont',
              pgA.evaluate("async () => (await fetch('/api/users')).status") == 403)
        check('interfejs zwinięty do grafiku', pgA.evaluate("() => document.body.classList.contains('tylkoGrafik')"))
        check('i pokazuje kalendarz', pgA.evaluate("() => VIEW") == 'graf')
        check('wylogowanie zostaje pod ręką',
              pgA.evaluate("() => document.getElementById('navOut').closest('.navitems').id") == 'grp-pulpit')
        check('a pracownik nie widzi z tej grupy niczego poza grafikiem', pgA.evaluate("""() => {
          return [...document.querySelectorAll('#grp-pulpit .nav')]
            .filter(b => getComputedStyle(b).display !== 'none')
            .every(b => b.dataset.v === 'graf' || b.id === 'navOut'); }"""))

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


        print('\n== GRAFIK: UPRAWNIENIE I WIELE DNI ==')
        # Układanie grafiku to osobne uprawnienie: kucharz z pełnym dostępem do bazy
        # nie ma go z automatu, a pracownik może je dostać.
        check('kucharz bez uprawnienia nie wpisze innych',
              shift(pg2, {'op': 'set', 'date': jutro, 'shift': zmiana,
                          'person': {'email': 'ania@lokal.pl'}, 'on': True})['status'] == 403)
        check('ani nie zmieni grafiku przez zapis całej bazy', pg2.evaluate(f"""async () => {{
          const st = await (await fetch('/api/data')).json();
          st.data.signups = {{}};
          st.data.shiftTpl = {{pn:[],wt:[],sr:[],cz:[],pt:[],so:[],nd:[]}};
          const r = await fetch('/api/data', {{method:'PUT', headers:{{'Content-Type':'application/json'}},
            body: JSON.stringify({{rev: st.rev, data: st.data}})}});
          if(!r.ok) return 'odrzucone:' + r.status;
          const po = await (await fetch('/api/data')).json();
          return po.data.shiftTpl.pn.length > 0 ? 'grafik ocalał' : 'GRAFIK SKASOWANY';
        }}""") in ('grafik ocalał', 'odrzucone:403'))

        check('nadanie uprawnienia', api('/api/users/update',
              {'email': 'ania@lokal.pl', 'sched': True})['status'] == 200)
        check('flaga zapisana przy koncie',
              json.load(open(f'{DATA}/users.json'))['ania@lokal.pl']['sched'] is True)
        check('lista kont pokazuje uprawnienie',
              [u for u in api('/api/users')['users'] if u['email'] == 'ania@lokal.pl'][0]['sched'] is True)
        pgA.reload(); pgA.wait_for_timeout(1800)
        check('pracownik z uprawnieniem układa grafik',
              pgA.evaluate("() => mozeGrafik()") is True)
        check('i wpisze kogoś innego',
              shift(pgA, {'op': 'set', 'date': jutro, 'shift': zmiana,
                          'person': {'email': 'szef@lokal.pl'}, 'on': True})['status'] == 200)
        check('a właściciel ma uprawnienie z urzędu, bez flagi',
              json.load(open(f'{DATA}/users.json'))['szef@lokal.pl'].get('sched') in (None, False)
              and pg.evaluate("() => mozeGrafik()") is True)

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

        check('odebranie uprawnienia', api('/api/users/update',
              {'email': 'ania@lokal.pl', 'sched': False})['status'] == 200)
        check('i pracownik znowu nie wpisze innych',
              shift(pgA, {'op': 'set', 'date': jutro, 'shift': zmiana,
                          'person': {'email': 'szef@lokal.pl'}, 'on': False})['status'] == 403)

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
