import json
import os
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
URL = 'file://' + ROOT + '/sushi-planner.html'
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
    pg.on('dialog', lambda d: d.accept())          # confirm()/alert() zawsze potwierdzamy
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
    print('\n== OPAKOWANIE ZESTAWU ==')
    pg.click('.nav[data-v="sets"]'); pg.wait_for_timeout(250)
    check('baner o brakującym opakowaniu', 'Uzupełnij opakowanie' in pg.content())
    # nadaj cenę tacce i pałeczkom, żeby dało się policzyć
    pg.evaluate("""() => {
      CALC.ing('tacka-hp09').packQty = 300; CALC.ing('tacka-hp09').packPrice = 360;   // 1,20 zł/szt
      CALC.ing('paleczki').packQty  = 1000; CALC.ing('paleczki').packPrice  = 150;    // 0,15 zł/para
      save(); render();
    }""")
    pg.wait_for_timeout(250)
    pg.click('button[data-edit-set="zestaw-1"]'); pg.wait_for_timeout(350)
    check('lista tacek zawiera oznaczone składniki',
          'Tacka HP09' in pg.locator('#pTray').inner_text(), pg.locator('#pTray').inner_text()[:80])
    pg.select_option('#pTray', 'tacka-hp09')
    pg.select_option('#pChop', 'paleczki')
    pg.select_option('#pSauce', 'sos-kikoman-saszetka')
    pg.fill('#pTrayQ', '1'); pg.fill('#pChopQ', '2'); pg.fill('#pSauceQ', '2')
    pg.wait_for_timeout(300)
    tot = pg.locator('#pPackTot').inner_text()
    # 1×1,20 + 2×0,15 + 2×1,75 = 5,00
    check('koszt opakowania = 5,00 zł', '5,00' in tot, tot)
    fc = pg.locator('#sFc').inner_text()
    check('food cost zestawu wzrósł po doliczeniu opakowania', fc.startswith('47'), fc)
    pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(400)
    check('opakowanie zapisane', pg.evaluate("() => CALC.setCalc(CALC.set('zestaw-1')).packaging > 4.9"))
    check('kolumna Opak. w tabeli', 'Opak.' in pg.content())

    # --- masowe uzupełnienie opakowania ---
    print('\n== MASOWE UZUPEŁNIENIE ==')
    before_n = pg.evaluate("() => DB.sets.filter(s=>!CALC.packRows(s).rows.length).length")
    pg.click('#fillPack'); pg.wait_for_timeout(500)
    after_n = pg.evaluate("() => DB.sets.filter(s=>!CALC.packRows(s).rows.length).length")
    check('wszystkie zestawy mają opakowanie', after_n == 0, f'{before_n} -> {after_n}')

    # --- zdjęcia ---
    print('\n== ZDJĘCIA ==')
    pg.click('.nav[data-v="items"]'); pg.wait_for_timeout(250)
    pg.click('button[data-edit-item="hosomaki-losos"]'); pg.wait_for_timeout(300)
    check('pole zdjęcia w edytorze rolki', pg.locator('#iPhoto').is_visible())
    pg.set_input_files('#iPhotoIn', ROOT + '/test-fixture.png')
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


    # --- archiwizacja ---
    print('\n== ARCHIWUM ==')
    pg.evaluate("() => { DB.ingredients.forEach(g=>delete g.archived); DB.items.forEach(i=>delete i.archived); DB.sets.forEach(x=>delete x.archived); DB.preps.forEach(p=>delete p.archived); save(); render(); }")
    pg.click('.nav[data-v="ing"]'); pg.wait_for_timeout(300)
    pg.fill('#ingQ', ''); pg.wait_for_timeout(300)
    n_all = pg.evaluate("() => DB.ingredients.length")

    # archiwizacja składnika NIEUŻYWANEGO — bez pytania
    pg.evaluate("() => { toggleArchive('ing','panko'); render(); }")
    pg.wait_for_timeout(300)
    check('nieużywany składnik trafia do archiwum',
          pg.evaluate("() => !!CALC.ing('panko').archived"))
    rows = pg.locator('tbody tr').count()
    check('domyślnie archiwum ukryte na liście', rows == n_all - 1, f'{rows} z {n_all}')
    pg.click('.pill-group[data-archgroup="ing"] button[data-av="arch"]'); pg.wait_for_timeout(300)
    check('widok Archiwum pokazuje tylko schowane', pg.locator('tbody tr').count() == 1)
    check('znacznik archiwum widoczny', 'archiwum' in pg.locator('tbody').inner_text())
    pg.click('.pill-group[data-archgroup="ing"] button[data-av="all"]'); pg.wait_for_timeout(300)
    check('widok Wszystko pokazuje komplet', pg.locator('tbody tr').count() == n_all)
    pg.click('.pill-group[data-archgroup="ing"] button[data-av="active"]'); pg.wait_for_timeout(300)

    # KLUCZOWE: archiwizacja NIE zmienia kosztów receptur
    before = pg.evaluate("() => CALC.itemCalc(CALC.item('uramaki-losos')).net")
    pg.evaluate("() => { toggleArchive('ing','losos'); render(); }")
    pg.wait_for_timeout(400)
    after = pg.evaluate("() => CALC.itemCalc(CALC.item('uramaki-losos')).net")
    check('koszt receptury bez zmian po archiwizacji składnika',
          abs(before - after) < 0.0001, f'{before} -> {after}')
    check('alert o archiwum wciąż w użyciu',
          pg.evaluate("() => problems().some(p=>p.k==='archused')"))
    # przywrócenie
    pg.evaluate("() => { toggleArchive('ing','losos'); toggleArchive('ing','panko'); render(); }")
    pg.wait_for_timeout(300)
    check('przywracanie z archiwum działa',
          pg.evaluate("() => !CALC.ing('losos').archived && !CALC.ing('panko').archived"))

    # rolki i zestawy znikają ze statystyk pulpitu
    # UWAGA: „Zestaw 1” jest podciągiem „Zestaw 10” — do testu bierzemy nazwę bez kolizji
    pg.evaluate("() => { CALC.set('zestaw-4').archived='2026-08-03'; save(); render(); }")
    pg.click('.nav[data-v="dash"]'); pg.wait_for_timeout(500)
    check('zarchiwizowany zestaw znika z wykresu pulpitu',
          'Zestaw 4' not in pg.locator('#chSets').inner_text(),
          pg.locator('#chSets').inner_text()[:80].replace('\n', ' '))
    pg.click('.nav[data-v="sets"]'); pg.wait_for_timeout(300)
    check('zestaw ukryty na liście', 'Zestaw 4' not in pg.locator('.tw').inner_text())
    pg.click('.pill-group[data-archgroup="sets"] button[data-av="arch"]'); pg.wait_for_timeout(300)
    check('zestaw widoczny w archiwum', 'Zestaw 4' in pg.locator('.tw').inner_text())
    pg.evaluate("() => { delete CALC.set('zestaw-4').archived; save(); render(); }")

    # archiwalna rolka nie pojawia się na liście wyboru w zestawie
    pg.evaluate("() => { CALC.item('hosomaki-tykwa-kanpyo').archived='2026-08-03'; save(); render(); }")
    pg.click('.nav[data-v="sets"]'); pg.wait_for_timeout(300)
    pg.click('.pill-group[data-archgroup="sets"] button[data-av="active"]'); pg.wait_for_timeout(300)
    pg.click('button[data-edit-set="zestaw-2"]'); pg.wait_for_timeout(400)
    opts = pg.locator('#sAdd').inner_text()
    check('archiwalna rolka poza listą wyboru', 'Tykwa Kanpyo' not in opts, opts[:100])
    pg.click('#dlgFoot button:has-text("Anuluj")'); pg.wait_for_timeout(200)
    # ale jeśli już jest w zestawie, musi zostać widoczna
    pg.click('button[data-edit-set="zestaw-6"]'); pg.wait_for_timeout(400)
    check('rolka użyta w zestawie zostaje na liście mimo archiwum',
          'Tykwa Kanpyo' in pg.locator('#sAdd').inner_text())
    pg.click('#dlgFoot button:has-text("Anuluj")'); pg.wait_for_timeout(200)
    pg.evaluate("() => { delete CALC.item('hosomaki-tykwa-kanpyo').archived; save(); render(); }")


    # --- trzy akcje w każdej liście ---
    print('\n== AKCJE W WIERSZACH ==')
    # liczymy w obrębie jednego wiersza — panel szczegółów ma własny przycisk Edytuj
    SPRAWDZ = """(k) => {
      const attr = {ing:'data-edit-ing', prep:'data-edit-prep',
                    items:'data-edit-item', sets:'data-edit-set'}[k];
      const arch = [...document.querySelectorAll('[data-arch-toggle^="'+k+':"]')];
      if(!arch.length) return {n:0, ok:false};
      const ok = arch.every(b => {
        const grupa = b.parentElement;
        return grupa.querySelector('['+attr+']') && grupa.querySelector('[data-del-row]');
      });
      return {n:arch.length, ok};
    }"""
    for view, nazwa in [('ing','Składniki'), ('prep','Półprodukty'),
                        ('items','Rolki'), ('sets','Zestawy')]:
        pg.click(f'.nav[data-v="{view}"]'); pg.wait_for_timeout(350)
        r = pg.evaluate(SPRAWDZ, view)
        check(f'{nazwa}: edytuj + archiwum + usuń w każdym wierszu ({r["n"]})', r['ok'], r)

    # archiwizacja jednym kliknięciem z listy
    pg.click('.nav[data-v="ing"]'); pg.wait_for_timeout(300)
    pg.fill('#ingQ', 'Panko'); pg.wait_for_timeout(350)
    pg.click('[data-arch-toggle="ing:panko"]'); pg.wait_for_timeout(400)
    check('archiwizacja prosto z listy', pg.evaluate("() => !!CALC.ing('panko').archived"))
    pg.click('.pill-group[data-archgroup="ing"] button[data-av="arch"]'); pg.wait_for_timeout(350)
    check('przycisk zmienia się na Przywróć',
          'Przywróć' in pg.locator('tbody').inner_text(), pg.locator('tbody').inner_text()[:80])
    pg.click('[data-arch-toggle="ing:panko"]'); pg.wait_for_timeout(400)
    check('przywracanie prosto z listy', pg.evaluate("() => !CALC.ing('panko').archived"))
    pg.click('.pill-group[data-archgroup="ing"] button[data-av="active"]'); pg.wait_for_timeout(300)

    # usuwanie zablokowane, gdy coś tego używa
    pg.fill('#ingQ', 'Łosoś'); pg.wait_for_timeout(350)
    n_before = pg.evaluate("() => DB.ingredients.length")
    pg.click('[data-del-row="ing:losos"]'); pg.wait_for_timeout(400)
    check('usuwanie używanego składnika zablokowane',
          pg.evaluate("() => DB.ingredients.length") == n_before)
    check('składnik nadal istnieje', pg.evaluate("() => !!CALC.ing('losos')"))

    # usuwanie nieużywanego działa
    pg.fill('#ingQ', 'Panko'); pg.wait_for_timeout(350)
    pg.click('[data-del-row="ing:panko"]'); pg.wait_for_timeout(500)
    check('nieużywany składnik da się usunąć', pg.evaluate("() => !CALC.ing('panko')"))
    pg.evaluate("""() => { DB.ingredients.push({id:'panko',name:'Panko',cat:'Dodatki',unit:'g',
                            packQty:null,packPrice:null,role:null}); save(); render(); }""")
    pg.fill('#ingQ', ''); pg.wait_for_timeout(300)


    # --- podmiana składnika w całym menu ---
    print('\n== PODMIANA SKŁADNIKA ==')
    pg.evaluate("() => { window.__kopia = clone({items:DB.items, preps:DB.preps, sets:DB.sets}); }")

    # Ryż -> Ryż gotowany: wystąpienie WEWNĄTRZ półproduktu musi zostać pominięte,
    # inaczej półprodukt liczyłby sam siebie i koszt zapadłby się do zera
    r = pg.evaluate("() => replaceEverywhere('ryz','ryz-gotowany',1)")
    check('ryż podmieniony w recepturach', r['zmienione'] == 23, r)
    check('wystąpienie w środku półproduktu pominięte', r['pominiete'] == 1, r)
    koszt = pg.evaluate("() => CALC.prepUnitCost('ryz-gotowany')*1000")
    check('koszt ryżu gotowanego nietknięty (4,7878 zł/kg)', abs(koszt - 4.7878) < 0.001, koszt)
    check('żaden półprodukt się nie zapętlił', pg.evaluate("() => !prepsBroken()"))
    net = pg.evaluate("() => CALC.itemCalc(CALC.item('futomaki-philadelphia')).net")
    # 190 g: 1,5833 zł (suchy) -> 0,9097 zł (gotowany) = -0,6736
    check('Futomaki Philadelphia tanieje o 0,67 zł', abs(net - (8.9617 - 0.6736)) < 0.01, net)

    # Nori 1/2 -> 0,5 szt Nori
    r2 = pg.evaluate("() => replaceEverywhere('nori-1-2','nori',0.5)")
    check('nori 1/2 podmienione', r2['zmienione'] == 13, r2)
    qty = pg.evaluate("""() => CALC.item('hosomaki-ogorek').comps.find(c=>c.refId==='nori').qty""")
    check('ilość przeliczona na 0,5 szt', abs(qty - 0.5) < 0.0001, qty)
    check('nie ma już odwołań do nori-1-2',
          pg.evaluate("() => occurrences('nori-1-2').length") == 0)

    # przywrócenie danych
    pg.evaluate("""() => { DB.items=window.__kopia.items; DB.preps=window.__kopia.preps;
                            DB.sets=window.__kopia.sets; save(); render(); }""")
    check('dane przywrócone do stanu wyjściowego',
          abs(pg.evaluate("() => CALC.itemCalc(CALC.item('futomaki-philadelphia')).net") - 8.9617) < 0.01)

    # próba stworzenia pętli: zaprawa występuje TYLKO w środku ryżu gotowanego,
    # więc podmiana na ryż gotowany musi zostać w całości pominięta
    przed = pg.evaluate("() => CALC.prepUnitCost('zaprawa')")
    rc = pg.evaluate("() => replaceEverywhere('zaprawa','ryz-gotowany',1)")
    check('podmiana grożąca pętlą w całości pominięta',
          rc['zmienione'] == 0 and rc['pominiete'] >= 1, rc)
    check('półprodukty nadal się liczą', pg.evaluate("() => !prepsBroken()"))
    pg.evaluate("""() => { DB.items=window.__kopia.items; DB.preps=window.__kopia.preps;
                            DB.sets=window.__kopia.sets; save(); render(); }""")
    check('po przywróceniu zaprawa znów się liczy',
          abs(pg.evaluate("() => CALC.prepUnitCost('zaprawa')") - przed) < 0.0001)

    # okno podmiany działa w interfejsie
    pg.click('.nav[data-v="ing"]'); pg.wait_for_timeout(300)
    pg.fill('#ingQ', 'Ryż'); pg.wait_for_timeout(350)
    pg.click('button[data-edit-ing="ryz"]'); pg.wait_for_timeout(300)
    pg.click('#dlgFoot button:has-text("Zamień wszędzie")'); pg.wait_for_timeout(700)
    check('okno podmiany pokazuje podgląd', pg.locator('#rpInfo').inner_text().count('zł') > 0,
          pg.locator('#rpInfo').inner_text()[:100])
    pg.click('#dlgFoot button:has-text("Anuluj")'); pg.wait_for_timeout(300)
    check('anulowanie nic nie zmieniło',
          abs(pg.evaluate("() => CALC.itemCalc(CALC.item('futomaki-philadelphia')).net") - 8.9617) < 0.01)
    pg.fill('#ingQ', ''); pg.wait_for_timeout(300)

    # --- eksport ---
    print('\n== EKSPORT ==')
    pg.click('.nav[data-v="set"]'); pg.wait_for_timeout(250)
    with pg.expect_download() as d:
        pg.click('#expCsv')
    dl = d.value
    dl.save_as('/tmp/out_test.csv')
    csv = open('/tmp/out_test.csv', encoding='utf-8-sig').read()
    check('CSV zawiera sekcje', 'SKŁADNIKI' in csv and 'ZESTAWY' in csv and 'RECEPTURY' in csv)
    with pg.expect_download() as d2:
        pg.click('#expJson')
    d2.value.save_as('/tmp/out_test.json')
    j = json.load(open('/tmp/out_test.json', encoding='utf-8'))
    check('JSON kompletny', len(j['ingredients']) >= 49 and len(j['sets']) == 13 and len(j['items']) >= 23)

    # --- ciemny motyw + zrzuty ---
    print('\n== MOTYW + ZRZUTY ==')
    pg.click('.nav[data-v="dash"]'); pg.wait_for_timeout(300)
    pg.screenshot(path='/tmp/shot-dash.png', full_page=True)
    pg.click('.nav[data-v="items"]'); pg.wait_for_timeout(200)
    pg.click('tr[data-pick-item="futomaki-philadelphia"]'); pg.wait_for_timeout(300)
    pg.screenshot(path='/tmp/shot-items.png', full_page=True)
    pg.click('.nav[data-v="sets"]'); pg.wait_for_timeout(200)
    pg.click('tr[data-pick-set="zestaw-9"]'); pg.wait_for_timeout(300)
    pg.screenshot(path='/tmp/shot-sets.png', full_page=True)
    pg.click('#themeBtn'); pg.wait_for_timeout(300)
    pg.click('.nav[data-v="dash"]'); pg.wait_for_timeout(300)
    pg.screenshot(path='/tmp/shot-dark.png', full_page=True)
    check('motyw ciemny aktywny', pg.evaluate("()=>document.documentElement.getAttribute('data-theme')") == 'dark')

    # --- mobile (najpierw z powrotem jasny motyw) ---
    pg.click('#themeBtn'); pg.wait_for_timeout(250)
    pg.set_viewport_size({'width': 400, 'height': 820})
    pg.wait_for_timeout(250)
    pg.screenshot(path='/tmp/shot-mobile.png', full_page=True)
    check('motyw wrócił do jasnego', pg.evaluate("()=>document.documentElement.getAttribute('data-theme')")=='light')

    print('\n== BŁĘDY KONSOLI ==')
    check('brak błędów JS w całym teście', not errors, errors)
    b.close()

print('\n' + '=' * 60)
print(('WSZYSTKO PRZESZŁO' if not FAIL else 'NIEPOWODZENIA: ' + ', '.join(FAIL)))
print('=' * 60)
