import json
from playwright.sync_api import sync_playwright

URL = 'file:///root/sushi-planner/sushi-planner.html'
errors = []
FAIL = []


def check(name, cond, extra=''):
    print(('  OK   ' if cond else '  FAIL ') + name + (('  -> ' + str(extra)) if extra and not cond else ''))
    if not cond:
        FAIL.append(name)


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 1440, 'height': 1000})
    pg.on('console', lambda m: errors.append(m.type + ': ' + m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errors.append('pageerror: ' + str(e)))
    pg.goto(URL)
    pg.wait_for_timeout(700)

    print('\n== START ==')
    check('brak błędów JS przy starcie', not errors, errors)
    check('pulpit się wyrenderował', pg.locator('h1').first.inner_text() == 'Pulpit')

    # --- zgodność silnika z Pythonem ---
    print('\n== SILNIK OBLICZEŃ ==')
    res = pg.evaluate("""() => {
      const out = {items:{}, sets:{}};
      DB.items.forEach(i=>{ const c=CALC.itemCalc(i); out.items[i.name]={net:c.net, fc:c.fc, per:c.perPiece, sug:c.suggested}; });
      DB.sets.forEach(s=>{ const c=CALC.setCalc(s); out.sets[s.name]={net:c.net, fc:c.fc, pieces:c.pieces}; });
      out.rice = CALC.prepUnitCost('ryz-gotowany');
      out.zaprawa = CALC.prepUnitCost('zaprawa');
      return out;
    }""")

    # oczekiwane wartości policzone niezależnie w Pythonie (audit.py)
    EXP_ITEMS = {
        'Hosomaki Ogórek': 1.5567, 'Hosomaki Łosoś': 4.1617, 'Uramaki Łosoś': 6.9033,
        'Uramaki Tilapia': 3.0369, 'Futomaki Philadelphia': 8.9617,
        'Uramaki Tuńczyk Tatar Goma': 6.7558, 'Futomaki Kalmar Tempura': 5.2089,
    }
    for k, v in EXP_ITEMS.items():
        got = res['items'][k]['net']
        check(f'koszt „{k}” = {v}', abs(got - v) < 0.005, round(got, 4))

    EXP_SETS = {'Zestaw 1': 7.6557, 'Zestaw 9': 27.8881, 'Zestaw 10': 47.7007, 'Sylwester 2': 43.3553}
    for k, v in EXP_SETS.items():
        got = res['sets'][k]['net']
        check(f'koszt „{k}” = {v}', abs(got - v) < 0.005, round(got, 4))

    check('food cost Zestaw 1 = 28,5%', abs(res['sets']['Zestaw 1']['fc'] - 0.28510) < 0.0005, res['sets']['Zestaw 1']['fc'])
    check('kawałki Zestaw 10 = 100', res['sets']['Zestaw 10']['pieces'] == 100, res['sets']['Zestaw 10']['pieces'])
    check('ryż gotowany 4,7878 zł/kg', abs(res['rice'] * 1000 - 4.7878) < 0.01, round(res['rice'] * 1000, 4))
    check('zaprawa 4,3845 zł/l', abs(res['zaprawa'] - 4.3845) < 0.001, res['zaprawa'])

    # sugerowana cena: koszt netto * 1.08 / 0.30, zaokrąglona do ,90
    sug = res['items']['Uramaki Łosoś']['sug']
    check('sugerowana cena Uramaki Łosoś = 24,90', abs(sug - 24.9) < 0.001, sug)

    # --- nawigacja przez wszystkie widoki ---
    print('\n== WIDOKI ==')
    for v, h in [('ing', 'Składniki'), ('prep', 'Półprodukty'), ('items', 'Rolki'),
                 ('sets', 'Zestawy'), ('hist', 'Historia cen'), ('sim', 'Symulacja „co jeśli”'),
                 ('set', 'Ustawienia'), ('dash', 'Pulpit')]:
        pg.click(f'.nav[data-v="{v}"]')
        pg.wait_for_timeout(220)
        check(f'widok {v}', pg.locator('h1').first.inner_text() == h, pg.locator('h1').first.inner_text())
    check('brak błędów JS po obejściu widoków', not errors, errors)

    # --- edycja składnika + historia ---
    print('\n== EDYCJA CENY + HISTORIA ==')
    pg.click('.nav[data-v="ing"]'); pg.wait_for_timeout(200)
    pg.fill('#ingQ', 'Łosoś'); pg.wait_for_timeout(250)
    pg.click('button[data-edit-ing="losos"]'); pg.wait_for_timeout(250)
    check('dialog otwarty', pg.locator('#dlg').is_visible())
    pg.fill('#fPrice', '89.5')
    pg.fill('#fNote', 'test podwyżki')
    pg.wait_for_timeout(120)
    check('podgląd ceny jednostkowej', '0,0895' in pg.locator('#fCalc').inner_text(), pg.locator('#fCalc').inner_text())
    pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(350)
    newcost = pg.evaluate("() => CALC.itemCalc(CALC.item('uramaki-losos')).net")
    check('koszt Uramaki Łosoś wzrósł po podwyżce', newcost > 6.9, round(newcost, 3))
    hist = pg.evaluate("() => DB.history.length")
    check('zapisano wpis w historii cen', hist == 1, hist)
    pg.click('.nav[data-v="hist"]'); pg.wait_for_timeout(250)
    check('historia widoczna w tabeli', 'test podwyżki' in pg.content())

    # cofnięcie zmiany
    pg.evaluate("() => { CALC.ing('losos').packPrice = 74.5; DB.history=[]; save(); render(); }")

    # --- dodanie pozycji menu ---
    print('\n== NOWA POZYCJA MENU ==')
    pg.click('.nav[data-v="items"]'); pg.wait_for_timeout(200)
    pg.click('button[data-act="addItem2"]'); pg.wait_for_timeout(250)
    pg.fill('#iName', 'Test Roll')
    pg.fill('#iPieces', '8')
    pg.fill('#iPrice', '30')
    pg.select_option('#iAdd', 'losos')
    pg.click('#iAddBtn'); pg.wait_for_timeout(200)
    pg.fill('#itComps input[data-q="0"]', '50'); pg.wait_for_timeout(200)
    net = pg.locator('#iNet').inner_text()
    check('koszt 50 g łososia ≈ 3,72 zł', net.startswith('3,72') or net.startswith('3,73'), net)
    fc = pg.locator('#iFc').inner_text()
    check('food cost policzony na żywo', '%' in fc and fc != '—', fc)
    pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(350)
    check('pozycja dodana', pg.evaluate("() => !!DB.items.find(i=>i.name==='Test Roll')"))

    # --- zestaw z opakowaniem ---
    print('\n== ZESTAW: DODATKI I OPAKOWANIE ==')
    pg.click('.nav[data-v="sets"]'); pg.wait_for_timeout(200)
    pg.click('button[data-edit-set="zestaw-1"]'); pg.wait_for_timeout(300)
    before = pg.locator('#sNet').inner_text()
    pg.select_option('#sAddC', 'imbir-marynowany')
    pg.fill('#sAddCQty', '1')
    pg.click('#sAddCBtn'); pg.wait_for_timeout(250)
    after = pg.locator('#sNet').inner_text()
    check('koszt zestawu rośnie po dodaniu imbiru', before != after, before + ' -> ' + after)
    check('imbir = +2,40 zł', '10,06' in after, after)
    pg.click('#dlgFoot button:has-text("Anuluj")'); pg.wait_for_timeout(200)
    check('anulowanie nie zapisało zmian',
          abs(pg.evaluate("() => CALC.setCalc(CALC.set('zestaw-1')).net") - 7.6557) < 0.01)

    # --- symulacja ---
    print('\n== SYMULACJA ==')
    pg.click('.nav[data-v="sim"]'); pg.wait_for_timeout(250)
    pg.select_option('#simIng', 'losos')
    pg.fill('#simPct', '25')
    pg.click('#simRun'); pg.wait_for_timeout(400)
    check('wynik symulacji widoczny', 'Wpływ na zestawy' in pg.content())
    check('ceny wróciły do stanu sprzed symulacji',
          abs(pg.evaluate("() => CALC.ing('losos').packPrice") - 74.5) < 0.001,
          pg.evaluate("() => CALC.ing('losos').packPrice"))


    # --- opakowanie zestawu ---
    print('\n== DODATKI ZESTAWU ==')
    pg.click('.nav[data-v="sets"]'); pg.wait_for_timeout(250)
    check('baner o braku dodatków', 'nie ma żadnych dodatków' in pg.content())
    check('pole roli zniknęło ze składników', pg.evaluate(
        "() => DB.ingredients.every(g=>g.role===undefined)"))
    check('pole pack zniknęło z zestawów', pg.evaluate(
        "() => DB.sets.every(s=>s.pack===undefined)"))
    # nadaj cenę tacce i pałeczkom, żeby dało się policzyć
    pg.evaluate("""() => {
      CALC.ing('tacka-hp09').packQty = 300; CALC.ing('tacka-hp09').packPrice = 360;   // 1,20 zł/szt
      CALC.ing('paleczki').packQty  = 1000; CALC.ing('paleczki').packPrice  = 150;    // 0,15 zł/para
      save(); render();
    }""")
    pg.wait_for_timeout(250)
    pg.click('button[data-edit-set="zestaw-1"]'); pg.wait_for_timeout(350)
    lista = pg.locator('#sAddC').inner_text()
    check('jedna lista dodatków zawiera tackę', 'Tacka HP09' in lista, lista[:80])
    check('jedna lista dodatków zawiera pałeczki', 'Pałeczki' in lista)
    check('lista dodatków pokazuje cenę jednostkową', 'brak ceny' in lista or '·' in lista)
    for ref, qty in (('tacka-hp09', '1'), ('paleczki', '2'), ('sos-kikoman-saszetka', '2')):
        pg.select_option('#sAddC', ref)
        pg.fill('#sAddCQty', qty)
        pg.click('#sAddCBtn'); pg.wait_for_timeout(200)
    pg.wait_for_timeout(300)
    tot = pg.locator('#sExtraTot').inner_text()
    # 1×1,20 + 2×0,15 + 2×1,75 = 5,00
    check('koszt dodatków = 5,00 zł', '5,00' in tot, tot)
    fc = pg.locator('#sFc').inner_text()
    check('food cost zestawu wzrósł po doliczeniu dodatków', fc.startswith('47'), fc)
    pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(400)
    check('dodatki zapisane', pg.evaluate("() => CALC.setCalc(CALC.set('zestaw-1')).packaging > 4.9"))
    check('kolumna Dodatki w tabeli', 'Dodatki' in pg.content())
    check('trzy pozycje w dodatkach', pg.evaluate("() => CALC.set('zestaw-1').comps.length") == 3)

    # --- migracja starego formatu ---
    print('\n== MIGRACJA pack -> comps ==')
    mig = pg.evaluate("""() => {
      const s = {id:'stary', name:'Stary format', vat:0.08, price:50, entries:[],
                 comps:[{refId:'paleczki', qty:1}],
                 pack:{trayId:'tacka-hp09', trayQty:2, chopId:'paleczki', chopQty:3,
                       sauceId:'sos-kikoman-saszetka', sauceQty:2}};
      migratePack(s);
      return {haspack: s.pack!==undefined, comps: s.comps};
    }""")
    check('pole pack skasowane', mig['haspack'] is False)
    check('tacka przeniesiona do dodatków',
          any(c['refId'] == 'tacka-hp09' and c['qty'] == 2 for c in mig['comps']), mig['comps'])
    check('pałeczki zsumowane (1 z comps + 3 z pack)',
          any(c['refId'] == 'paleczki' and c['qty'] == 4 for c in mig['comps']), mig['comps'])
    check('sos przeniesiony', any(c['refId'] == 'sos-kikoman-saszetka' for c in mig['comps']))
    check('bez duplikatów', len(mig['comps']) == 3, mig['comps'])

    # --- zdjęcia ---
    print('\n== ZDJĘCIA ==')
    pg.click('.nav[data-v="items"]'); pg.wait_for_timeout(250)
    pg.click('button[data-edit-item="hosomaki-losos"]'); pg.wait_for_timeout(300)
    check('pole zdjęcia w edytorze rolki', pg.locator('#iPhoto').is_visible())
    pg.set_input_files('#iPhotoIn', '/root/sushi-planner/fixture.png')
    pg.wait_for_timeout(700)
    check('podgląd zdjęcia po wgraniu', pg.locator('#iPhoto img').count() == 1)
    pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(400)
    photo = pg.evaluate("() => CALC.item('hosomaki-losos').photo")
    check('zdjęcie zapisane jako JPEG', bool(photo) and photo.startswith('data:image/jpeg'), (photo or '')[:30])
    check('zdjęcie zmniejszone poniżej 120 kB', len(photo) < 120000, f'{len(photo)//1024} kB')
    check('miniatura w tabeli rolek', pg.locator('tr[data-pick-item="hosomaki-losos"] img.thumb').count() == 1)
    pg.click('tr[data-pick-item="hosomaki-losos"]'); pg.wait_for_timeout(300)
    check('duże zdjęcie w panelu szczegółów', pg.locator('img.hero').count() == 1)
    # usunięcie zdjęcia
    pg.click('button[data-edit-item="hosomaki-losos"]'); pg.wait_for_timeout(300)
    pg.click('#iPhotoRm'); pg.wait_for_timeout(250)
    pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(350)
    check('zdjęcie usunięte', not pg.evaluate("() => CALC.item('hosomaki-losos').photo"))

    # --- eksport ---
    print('\n== EKSPORT ==')
    pg.click('.nav[data-v="set"]'); pg.wait_for_timeout(250)
    with pg.expect_download() as d:
        pg.click('#expCsv')
    dl = d.value
    dl.save_as('/root/sushi-planner/out_test.csv')
    csv = open('/root/sushi-planner/out_test.csv', encoding='utf-8-sig').read()
    check('CSV zawiera sekcje', 'SKŁADNIKI' in csv and 'ZESTAWY' in csv and 'RECEPTURY' in csv)
    with pg.expect_download() as d2:
        pg.click('#expJson')
    d2.value.save_as('/root/sushi-planner/out_test.json')
    j = json.load(open('/root/sushi-planner/out_test.json', encoding='utf-8'))
    check('JSON kompletny', len(j['ingredients']) >= 49 and len(j['sets']) == 13 and len(j['items']) >= 23)

    # --- ciemny motyw + zrzuty ---
    print('\n== MOTYW + ZRZUTY ==')
    pg.click('.nav[data-v="dash"]'); pg.wait_for_timeout(300)
    pg.screenshot(path='/root/sushi-planner/shot-dash.png', full_page=True)
    pg.click('.nav[data-v="items"]'); pg.wait_for_timeout(200)
    pg.click('tr[data-pick-item="futomaki-philadelphia"]'); pg.wait_for_timeout(300)
    pg.screenshot(path='/root/sushi-planner/shot-items.png', full_page=True)
    pg.click('.nav[data-v="sets"]'); pg.wait_for_timeout(200)
    pg.click('tr[data-pick-set="zestaw-9"]'); pg.wait_for_timeout(300)
    pg.screenshot(path='/root/sushi-planner/shot-sets.png', full_page=True)
    pg.click('#themeBtn'); pg.wait_for_timeout(300)
    pg.click('.nav[data-v="dash"]'); pg.wait_for_timeout(300)
    pg.screenshot(path='/root/sushi-planner/shot-dark.png', full_page=True)
    check('motyw ciemny aktywny', pg.evaluate("()=>document.documentElement.getAttribute('data-theme')") == 'dark')

    # --- mobile (najpierw z powrotem jasny motyw) ---
    pg.click('#themeBtn'); pg.wait_for_timeout(250)
    pg.set_viewport_size({'width': 400, 'height': 820})
    pg.wait_for_timeout(250)
    pg.screenshot(path='/root/sushi-planner/shot-mobile.png', full_page=True)
    check('motyw wrócił do jasnego', pg.evaluate("()=>document.documentElement.getAttribute('data-theme')")=='light')

    print('\n== BŁĘDY KONSOLI ==')
    check('brak błędów JS w całym teście', not errors, errors)
    b.close()

print('\n' + '=' * 60)
print(('WSZYSTKO PRZESZŁO' if not FAIL else 'NIEPOWODZENIA: ' + ', '.join(FAIL)))
print('=' * 60)
