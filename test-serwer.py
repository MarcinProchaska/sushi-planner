"""Test end-to-end trybu serwerowego: logowanie, zapis, konflikt, rola podglądu, restart."""
import json
import os
import shutil
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.abspath(__file__))
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


def start(port):
    env = dict(os.environ, SUSHI_DATA=DATA)
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
        check('pulpit widoczny', pg.locator('h1').first.inner_text() == 'Pulpit')
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


        print('\n== ZARZADZANIE KONTAMI (API) ==')
        # kucharz nie ma dostepu do kont
        code = pg2.evaluate("async()=>(await fetch('/api/users')).status")
        check('kucharz nie widzi listy kont (403)', code == 403, code)
        code = pg2.evaluate("""async()=>(await fetch('/api/users',{method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({email:'x@x.pl',role:'owner',password:'haslohaslo'})})).status""")
        check('kucharz nie zalozy konta (403)', code == 403, code)

        # wlasciciel: lista
        j = pg.evaluate("async()=>(await fetch('/api/users')).json()")
        check('wlasciciel widzi 3 konta', len(j['users']) == 3, [u['email'] for u in j['users']])
        check('role poprawne',
              {u['email']: u['role'] for u in j['users']} ==
              {'szef@lokal.pl': 'owner', 'kuchnia@lokal.pl': 'chef', 'podglad@lokal.pl': 'viewer'})

        # Playwright przekazuje do evaluate JEDEN argument — stąd destrukturyzacja tablicy
        async_post = """async([p,b])=>{const r=await fetch(p,{method:'POST',
          headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
          return {s:r.status, j:await r.json().catch(()=>({}))};}"""

        # walidacje
        r = pg.evaluate(async_post, ['/api/users', {'email': 'nowy@lokal.pl', 'role': 'chef', 'password': 'krotkie'}])
        check('odrzuca haslo ponizej 8 znakow', r['s'] == 400 and '8 znak' in r['j'].get('error', ''), r)
        r = pg.evaluate(async_post, ['/api/users', {'email': 'zlarola@lokal.pl', 'role': 'admin', 'password': 'dobrehaslo'}])
        check('odrzuca nieznana role', r['s'] == 400, r)
        r = pg.evaluate(async_post, ['/api/users', {'email': 'bezmalpy', 'role': 'chef', 'password': 'dobrehaslo'}])
        check('odrzuca zly e-mail', r['s'] == 400, r)
        r = pg.evaluate(async_post, ['/api/users', {'email': 'kuchnia@lokal.pl', 'role': 'chef', 'password': 'dobrehaslo'}])
        check('odrzuca duplikat konta (409)', r['s'] == 409, r)

        # zabezpieczenia przed odcieciem sie
        r = pg.evaluate(async_post, ['/api/users/update', {'email': 'szef@lokal.pl', 'role': 'chef'}])
        check('nie mozna odebrac uprawnien sobie', r['s'] == 400, r)
        r = pg.evaluate(async_post, ['/api/users/delete', {'email': 'szef@lokal.pl'}])
        check('nie mozna usunac wlasnego konta', r['s'] == 400, r)

        # dodanie konta i logowanie na nie
        r = pg.evaluate(async_post, ['/api/users', {'email': 'nowy@lokal.pl', 'role': 'chef', 'password': 'nowehaslo123'}])
        check('dodano konto przez API', r['s'] == 200, r)
        ctx4 = br.new_context(); pg4 = ctx4.new_page()
        pg4.goto(URL); pg4.wait_for_timeout(700)
        pg4.fill('#lgMail', 'nowy@lokal.pl'); pg4.fill('#lgPass', 'nowehaslo123')
        pg4.click('#lgBtn'); pg4.wait_for_timeout(1500)
        check('nowe konto sie loguje', pg4.locator('#loginWrap').count() == 0)

        # zmiana hasla
        r = pg.evaluate(async_post, ['/api/users/update', {'email': 'nowy@lokal.pl', 'password': 'innehaslo456'}])
        check('zmieniono haslo', r['s'] == 200, r)
        st = pg.evaluate("""async()=>{const r=await fetch('/api/login',{method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({email:'nowy@lokal.pl',password:'nowehaslo123'})});return r.status;}""")
        check('stare haslo juz nie dziala', st == 401, st)

        # zmiana roli dziala natychmiast dla zalogowanej osoby
        r = pg.evaluate(async_post, ['/api/users/update', {'email': 'nowy@lokal.pl', 'role': 'viewer'}])
        check('zmieniono role na viewer', r['s'] == 200, r)
        code = pg4.evaluate("""async()=>{const r=await fetch('/api/data',{method:'PUT',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({rev:SRV.rev,data:DB})});return r.status;}""")
        check('degradacja roli dziala od razu na aktywnej sesji (403)', code == 403, code)

        # usuniecie konta odcina dostep natychmiast
        r = pg.evaluate(async_post, ['/api/users/delete', {'email': 'nowy@lokal.pl'}])
        check('usunieto konto', r['s'] == 200, r)
        code = pg4.evaluate("async()=>(await fetch('/api/data')).status")
        check('usuniete konto traci dostep natychmiast (401)', code == 401, code)
        ctx4.close()

        print('\n== ZAKLADKA UZYTKOWNICY W INTERFEJSIE ==')
        pg.reload(); pg.wait_for_timeout(1500)
        check('wlasciciel widzi zakladke', pg.locator('#navUsers:visible').count() == 1)
        check('kucharz nie widzi zakladki', pg2.locator('#navUsers:visible').count() == 0)
        pg.click('.nav[data-v="users"]'); pg.wait_for_timeout(1200)
        check('lista kont w interfejsie', pg.locator('h1').first.inner_text() == 'Użytkownicy')
        txt = pg.locator('.tw').inner_text()
        check('widac wszystkie konta', 'szef@lokal.pl' in txt and 'kuchnia@lokal.pl' in txt, txt[:120])
        check('wlasne konto oznaczone', 'to Ty' in txt)
        check('brak przycisku usuniecia przy sobie',
              pg.locator('button[data-del-user="szef@lokal.pl"]').count() == 0)

        # dodanie konta z interfejsu
        pg.click('button[data-act="addUser"]'); pg.wait_for_timeout(400)
        pg.fill('#uMail', 'zinterfejsu@lokal.pl')
        pg.select_option('#uRole', 'viewer')
        pg.fill('#uPass', 'haslozinterfejsu')
        pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(1200)
        check('konto dodane z interfejsu',
              'zinterfejsu@lokal.pl' in pg.locator('.tw').inner_text())
        users = json.load(open(f'{DATA}/users.json'))
        check('zapisane na dysku z rola viewer',
              users.get('zinterfejsu@lokal.pl', {}).get('role') == 'viewer', users.keys())
        check('haslo zahaszowane',
              'haslozinterfejsu' not in json.dumps(users.get('zinterfejsu@lokal.pl', {})))


        print('\n== AKTUALIZACJA Z APLIKACJI ==')
        # tylko właściciel
        for sciezka in ['/api/update/check', '/api/update/status']:
            code = pg2.evaluate(f"async()=>(await fetch('{sciezka}')).status")
            check(f'kucharz nie ma dostepu do {sciezka} (403)', code == 403, code)
        code = pg2.evaluate("async()=>(await fetch('/api/update/run',{method:'POST'})).status")
        check('kucharz nie uruchomi aktualizacji (403)', code == 403, code)
        code = pg3.evaluate("async()=>(await fetch('/api/update/run',{method:'POST'})).status")
        check('konto podgladu nie uruchomi aktualizacji (403)', code == 403, code)

        # właściciel: sprawdzenie działa i nie rusza serwera
        j = pg.evaluate("async()=>(await fetch('/api/update/check')).json()")
        check('wlasciciel dostaje wynik sprawdzenia',
              'output' in j and 'available' in j and 'version' in j, list(j.keys()))
        check('sprawdzenie nie zatrzymalo serwera',
              pg.evaluate("async()=>(await fetch('/api/health')).status") == 200)
        # to nie jest repozytorium git, więc update.sh musi to zgłosić, a nie wysypać się
        check('bledne sprawdzenie oznaczone jako nieudane (nie jako brak zmian)',
              j['ok'] is False and j['available'] is False, {'ok': j['ok'], 'available': j['available']})
        check('czytelny komunikat poza repozytorium',
              'repozytorium git' in j['output'] or 'Bez zmian' in j['output']
              or 'Dostępna' in j['output'], j['output'][:120])

        j2 = pg.evaluate("async()=>(await fetch('/api/update/status')).json()")
        check('status zwraca wersje i zajetosc',
              'busy' in j2 and 'version' in j2 and 'log' in j2, list(j2.keys()))
        check('serwer nie raportuje trwajacej aktualizacji', j2['busy'] is False, j2['busy'])

        # przycisk widoczny tylko dla właściciela
        pg.click('.nav[data-v="set"]'); pg.wait_for_timeout(600)
        check('wlasciciel widzi przycisk aktualizacji', pg.locator('#srvUpd:visible').count() == 1)
        pg2.click('.nav[data-v="set"]'); pg2.wait_for_timeout(600)
        check('kucharz nie widzi przycisku aktualizacji', pg2.locator('#srvUpd').count() == 0)

        # okno aktualizacji otwiera się i pokazuje wynik zamiast się zawiesić
        pg.click('#srvUpd'); pg.wait_for_timeout(2500)
        tekst = pg.locator('#updBody').inner_text()
        check('okno aktualizacji pokazuje wynik',
              'Zainstalowana wersja' in tekst or 'Tylko właściciel' in tekst, tekst[:120])
        pg.click('#dlgFoot button:has-text("Zamknij")'); pg.wait_for_timeout(300)

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
