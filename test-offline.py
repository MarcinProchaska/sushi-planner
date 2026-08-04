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

    # --- przełącznik lista / kafelki ---
    print('\n== LISTA / KAFELKI ==')
    for widok, tbl in [('ing','ing'), ('prep','prep'), ('items','items'), ('sets','sets')]:
        pg.click(f'.nav[data-v="{widok}"]'); pg.wait_for_timeout(250)
        check(f'przełącznik widoku w {widok}',
              pg.locator(f'[data-viewgroup="{widok}"] button').count() == 2)

    # składniki: lista -> kafelki -> lista
    pg.click('.nav[data-v="ing"]'); pg.wait_for_timeout(250)
    check('składniki startują jako lista', pg.locator('table[data-tbl="ing"]').count() == 1)
    ile = pg.locator('table[data-tbl="ing"] tbody tr').count()
    pg.click('[data-viewgroup="ing"] button[data-vm="cards"]'); pg.wait_for_timeout(300)
    check('po przełączeniu nie ma tabeli', pg.locator('table[data-tbl="ing"]').count() == 0)
    check('kafelków tyle co wierszy', pg.locator('.tiles-grid .tcard').count() == ile,
          (pg.locator('.tiles-grid .tcard').count(), ile))
    check('kafelek pokazuje cenę jednostkową', 'Cena za' in pg.content())
    check('akcje na kafelku', pg.locator('.tcard [data-edit-ing]').count() == ile)

    # wybór zostaje po przejściu na inną zakładkę i z powrotem
    pg.click('.nav[data-v="dash"]'); pg.wait_for_timeout(200)
    pg.click('.nav[data-v="ing"]'); pg.wait_for_timeout(250)
    check('tryb kafelków przetrwał zmianę widoku', pg.locator('.tiles-grid .tcard').count() == ile)
    check('zapisany w localStorage', 'cards' in pg.evaluate("() => localStorage.getItem('sp_widok')"),
          pg.evaluate("() => localStorage.getItem('sp_widok')"))

    # edycja z kafelka działa
    pg.click('.tcard [data-edit-ing="ogorek"]'); pg.wait_for_timeout(300)
    check('edytor otwiera się z kafelka', pg.locator('#fName').input_value() == 'Ogórek',
          pg.locator('#fName').input_value())
    pg.click('#dlgFoot button:has-text("Anuluj")'); pg.wait_for_timeout(200)
    pg.click('[data-viewgroup="ing"] button[data-vm="list"]'); pg.wait_for_timeout(300)
    check('powrót do listy', pg.locator('table[data-tbl="ing"]').count() == 1)

    # półprodukty: kafelki -> lista (odwrotnie niż reszta)
    pg.click('.nav[data-v="prep"]'); pg.wait_for_timeout(250)
    check('półprodukty startują jako kafelki', pg.locator('table[data-tbl="prep"]').count() == 0)
    pg.click('[data-viewgroup="prep"] button[data-vm="list"]'); pg.wait_for_timeout(300)
    check('półprodukty w tabeli', pg.locator('table[data-tbl="prep"]').count() == 1)
    check('tabela półproduktów sortowalna', pg.locator('table[data-tbl="prep"] th.sortable').count() > 0)
    check('kolumna kosztu jednostkowego', 'Koszt / j.m.' in pg.content())
    pg.click('[data-viewgroup="prep"] button[data-vm="cards"]'); pg.wait_for_timeout(300)

    # rolki: kafelek klikalny, panel szczegółów działa
    pg.click('.nav[data-v="items"]'); pg.wait_for_timeout(250)
    pg.click('[data-viewgroup="items"] button[data-vm="cards"]'); pg.wait_for_timeout(300)
    check('kafelki rolek', pg.locator('.tcard[data-pick-item]').count() > 0)
    pg.click('.tcard[data-pick-item="uramaki-losos"]'); pg.wait_for_timeout(350)
    check('klik w kafelek wybiera rolkę',
          pg.locator('.tcard[data-pick-item="uramaki-losos"].sel').count() == 1)
    check('panel szczegółów pod kafelkami', 'Rozbicie kosztu' in pg.content())
    pg.click('[data-viewgroup="items"] button[data-vm="list"]'); pg.wait_for_timeout(300)
    check('rolki wracają do tabeli', pg.locator('table[data-tbl="items"]').count() == 1)

    # zestawy
    pg.click('.nav[data-v="sets"]'); pg.wait_for_timeout(250)
    pg.click('[data-viewgroup="sets"] button[data-vm="cards"]'); pg.wait_for_timeout(300)
    ilez = pg.locator('.tcard[data-pick-set]').count()
    check('kafelki zestawów', ilez > 0)
    check('kafelek zestawu pokazuje rabat', 'Rabat vs à la carte' in pg.content())
    pg.click('[data-viewgroup="sets"] button[data-vm="list"]'); pg.wait_for_timeout(300)
    check('zestawy wracają do tabeli',
          pg.locator('table[data-tbl="sets"] tbody tr').count() == ilez)

    # --- sortowanie tabel ---
    print('\n== SORTOWANIE ==')
    pg.click('.nav[data-v="ing"]'); pg.wait_for_timeout(250)

    def col(idx):
        """tekst kolumny idx ze wszystkich wierszy tabeli składników"""
        return pg.evaluate(
            "i => [...document.querySelectorAll('table[data-tbl=ing] tbody tr')]"
            ".map(r => r.cells[i] ? r.cells[i].textContent.trim() : '')", idx)

    def liczby(vals):
        out = []
        for v in vals:
            s = v.replace('\u00a0', '').replace(' ', '').replace('zł', '').replace('%', '').replace(',', '.')
            try: out.append(float(s))
            except ValueError: out.append(None)
        return out

    check('nagłówki są klikalne', pg.locator('table[data-tbl="ing"] th.sortable').count() == 7,
          pg.locator('table[data-tbl="ing"] th.sortable').count())
    check('kolumna Akcje nie jest sortowalna',
          pg.locator('table[data-tbl="ing"] th[data-nosort]').count() == 1)

    # kolumna 5 = Cena / j.m.
    pg.click('table[data-tbl="ing"] th:nth-child(6)'); pg.wait_for_timeout(200)
    asc = liczby(col(5))
    czyste = [x for x in asc if x is not None]
    check('rosnąco po cenie jednostkowej', czyste == sorted(czyste), czyste[:6])
    check('puste na końcu przy rosnąco',
          all(x is not None for x in asc[:len(czyste)]), asc[-3:])
    check('strzałka w górę na nagłówku',
          'asc' in pg.locator('table[data-tbl="ing"] th:nth-child(6)').get_attribute('class'))

    pg.click('table[data-tbl="ing"] th:nth-child(6)'); pg.wait_for_timeout(200)
    desc = liczby(col(5))
    czyste_d = [x for x in desc if x is not None]
    check('malejąco po drugim kliknięciu', czyste_d == sorted(czyste_d, reverse=True), czyste_d[:6])
    check('puste nadal na końcu przy malejąco',
          all(x is not None for x in desc[:len(czyste_d)]), desc[-3:])
    check('strzałka w dół na nagłówku',
          'desc' in pg.locator('table[data-tbl="ing"] th:nth-child(6)').get_attribute('class'))

    # tekst, nie liczby
    pg.click('table[data-tbl="ing"] th:nth-child(1)'); pg.wait_for_timeout(200)
    nazwy = [n.split(' archiwum')[0] for n in col(0)]
    # kolejność polska, nie ASCII: Ł idzie po L, a nie po Z
    ALFA = 'aąbcćdeęfghijklłmnńoópqrsśtuvwxyzźż'
    def pl_key(s):
        return [ALFA.index(c) if c in ALFA else 99 for c in s.lower()]
    check('rosnąco po nazwie', nazwy == sorted(nazwy, key=pl_key), nazwy[:6])
    check('Ł sortuje się po L, nie po Z',
          nazwy.index('Łosoś') < nazwy.index('Majonez'), nazwy)

    # wybór przeżywa przerysowanie widoku
    pierwsza = col(0)[0]
    pg.click('.nav[data-v="items"]'); pg.wait_for_timeout(200)
    pg.click('.nav[data-v="ing"]'); pg.wait_for_timeout(250)
    check('sortowanie przetrwało zmianę widoku', col(0)[0] == pierwsza, (pierwsza, col(0)[0]))
    check('strzałka odtworzona po przerysowaniu',
          'asc' in pg.locator('table[data-tbl="ing"] th:nth-child(1)').get_attribute('class'))

    # pozostałe tabele też mają mechanizm
    for widok, tbl in [('items', 'items'), ('sets', 'sets'), ('hist', 'hist')]:
        pg.click(f'.nav[data-v="{widok}"]'); pg.wait_for_timeout(250)
        check(f'tabela {tbl} sortowalna', pg.locator(f'table[data-tbl="{tbl}"] th.sortable').count() > 0)

    # sortowanie zestawów po food coście
    pg.click('.nav[data-v="sets"]'); pg.wait_for_timeout(250)
    pg.click('table[data-tbl="sets"] th:nth-child(6)'); pg.wait_for_timeout(200)
    fc = [x for x in liczby(pg.evaluate(
        "() => [...document.querySelectorAll('table[data-tbl=sets] tbody tr')]"
        ".map(r => r.cells[5].textContent.trim())")) if x is not None]
    check('zestawy rosnąco po food coście', fc == sorted(fc), fc)

    # --- wartości odżywcze i odpad ---
    print('\n== WARTOŚCI ODŻYWCZE ==')
    # Hosomaki Ogórek = nori 1/2 ×1 (1,4 g) + ryż 110 g + ogórek 25 g
    r = pg.evaluate("() => CALC.itemNutr(CALC.item('hosomaki-ogorek'))")
    check('masa rolki = 136,4 g', abs(r['mass'] - 136.4) < 0.01, r['mass'])
    kcal = 350*1.4/100 + 355*110/100 + 15*25/100
    check('kcal rolki policzone ze składników', abs(r['nutr']['kcal'] - kcal) < 0.01,
          (r['nutr']['kcal'], kcal))
    check('brak brakujących tabel', r['missing'] == [], r['missing'])

    # nori liczone w arkuszach — bez wagi jednostki nie da się nic policzyć
    r2 = pg.evaluate("""() => {
      const g = CALC.ing('nori-1-2'); const stara = g.gPerUnit;
      g.gPerUnit = null;
      const bez = CALC.itemNutr(CALC.item('hosomaki-ogorek'));
      g.gPerUnit = stara;
      return {mass: bez.mass, noMass: bez.noMass};
    }""")
    check('bez wagi jednostki masa nie zawiera nori', abs(r2['mass'] - 135.0) < 0.01, r2['mass'])
    check('i aplikacja to zgłasza', 'Nori 1/2' in r2['noMass'], r2['noMass'])

    # --- ODPAD w półprodukcie ---
    print('\n== ODPAD W PÓŁPRODUKCIE ==')
    w = pg.evaluate("""() => {
      const bazowy = {id:'test-odpad', name:'Ogórek krojony', yieldQty:500, yieldUnit:'g',
        items:[{kind:'ing', refId:'ogorek', qty:500},
               {kind:'ing', refId:'ogorek', qty:500, waste:true}]};
      const bezFlagi = JSON.parse(JSON.stringify(bazowy));
      bezFlagi.items[1].waste = false;
      const koszt = p => p.items.reduce((s,c)=>s+(c.qty||0)*(CALC.ingUnitCost(c.refId)||0),0);
      return {
        zOdpadem:  CALC.prepNutr(bazowy).nutr.kcal,
        bezFlagi:  CALC.prepNutr(bezFlagi).nutr.kcal,
        ogorekNaG: CALC.ingNutr('ogorek').kcal,
        kosztPartii: koszt(bazowy),
        kosztJedn: koszt(bazowy)/500,
        grams: CALC.prepNutr(bazowy).grams
      };
    }""")
    check('odpad nie wchodzi do wartości odżywczych',
          abs(w['zOdpadem'] - w['ogorekNaG']) < 1e-9, (w['zOdpadem'], w['ogorekNaG']))
    check('bez flagi wartość byłaby dwa razy większa',
          abs(w['bezFlagi'] - 2*w['ogorekNaG']) < 1e-9, w['bezFlagi'])
    check('odpad NADAL wchodzi do kosztu (1000 g ogórka)',
          abs(w['kosztPartii'] - 15.0) < 1e-9, w['kosztPartii'])
    check('koszt jednostkowy podwojony przez odpad',
          abs(w['kosztJedn'] - 0.03) < 1e-9, w['kosztJedn'])
    check('1 g półproduktu waży 1 g', w['grams'] == 1, w['grams'])

    # pętla w półproduktach nie zawiesza silnika
    cyc = pg.evaluate("""() => {
      DB.preps.push({id:'petla', name:'Pętla', yieldQty:100, yieldUnit:'g',
                     items:[{kind:'prep', refId:'petla', qty:100}]});
      let ok = true;
      try { CALC.prepNutr('petla'); } catch(e) { ok = false; }
      DB.preps.pop();
      return ok;
    }""")
    check('półprodukt wskazujący na siebie nie zapętla silnika', cyc)

    # zera to wypełniona tabela, nie brak danych — inaczej tacki i pałeczki
    # wisiałyby na liście braków na zawsze
    z = pg.evaluate("""() => {
      const g = CALC.ing('paleczki');
      const stare = g.nutr;
      g.nutr = {kcal:0, fat:0, satfat:0, carbs:0, sugars:0, protein:0, salt:0};
      const wynik = {ma: hasNutr(g.nutr), pusto: hasNutr(null), brak: hasNutr({})};
      g.nutr = stare;
      return wynik;
    }""")
    check('same zera liczą się jako wypełniona tabela', z['ma'] is True, z)
    check('brak obiektu to brak danych', z['pusto'] is False and z['brak'] is False, z)

    # --- ALERGENY ---
    print('\n== ALERGENY ==')
    a = pg.evaluate("() => CALC.itemNutr(CALC.item('uramaki-losos')).alerg")
    for al in ('ryby', 'mleko', 'sezam'):
        check(f'Uramaki Łosoś dziedziczy alergen: {al}', al in a, a)
    sa = pg.evaluate("() => CALC.setNutr(CALC.set('zestaw-9')).alerg")
    check('zestaw zbiera alergeny ze wszystkich rolek', 'ryby' in sa and len(sa) >= 3, sa)

    # --- ZESTAW: skalowanie po kawałkach ---
    print('\n== ODŻYWCZE W ZESTAWIE ==')
    s = pg.evaluate("""() => {
      const st = CALC.set('zestaw-1');
      const r = CALC.setNutr(st);
      const recznie = st.entries.reduce((acc,e)=>{
        const it = CALC.item(e.itemId); const n = CALC.itemNutr(it);
        return acc + n.nutr.kcal * e.pieces / it.pieces;
      },0);
      return {z: r.nutr.kcal, recznie, mass: r.mass};
    }""")
    check('kcal zestawu = suma rolek przeliczonych po kawałkach',
          abs(s['z'] - s['recznie']) < 0.01, (s['z'], s['recznie']))
    check('masa zestawu dodatnia', s['mass'] > 0, s['mass'])

    # opakowanie nie może zwiększać masy porcji
    op = pg.evaluate("""() => {
      const st = JSON.parse(JSON.stringify(CALC.set('zestaw-1')));
      const przed = CALC.setNutr(st).mass;
      st.comps = (st.comps||[]).concat([{refId:'tacka-hp09', qty:1},{refId:'paleczki', qty:2}]);
      return {przed, po: CALC.setNutr(st).mass};
    }""")
    check('tacka i pałeczki nie zwiększają masy porcji',
          abs(op['przed'] - op['po']) < 1e-9, op)

    # --- UI ---
    print('\n== UI: ODŻYWCZE ==')
    pg.click('.nav[data-v="items"]'); pg.wait_for_timeout(250)
    pg.click('tr[data-pick-item="uramaki-losos"]'); pg.wait_for_timeout(300)
    tekst = pg.content()
    check('tabela odżywcza na karcie rolki', 'Wartości odżywcze' in tekst)
    check('kolumna w 100 g', 'w 100 g' in tekst)
    check('energia w kJ i kcal', 'kJ /' in tekst)
    check('alergeny wypisane', 'Ryby' in tekst and 'Mleko' in tekst)
    pg.click('button[data-edit-item="uramaki-losos"]'); pg.wait_for_timeout(300)
    pg.click('#dlgFoot button:has-text("Anuluj")'); pg.wait_for_timeout(200)

    pg.click('.nav[data-v="ing"]'); pg.wait_for_timeout(250)
    pg.click('button[data-edit-ing="ogorek"]'); pg.wait_for_timeout(300)
    check('pole kcal w edytorze składnika', pg.locator('#fN_kcal').is_visible())
    check('pole soli w edytorze składnika', pg.locator('#fN_salt').is_visible())
    check('pole wagi jednostki', pg.locator('#fGram').is_visible())
    check('checkbox alergenu', pg.locator('#fA_gluten').count() == 1)
    pg.fill('#fN_kcal', '17')
    pg.check('#fA_seler')
    pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(400)
    zap = pg.evaluate("() => ({k: CALC.ing('ogorek').nutr.kcal, a: CALC.ing('ogorek').alerg})")
    check('zmiana kcal zapisana', zap['k'] == 17, zap)
    check('zaznaczony alergen zapisany', 'seler' in zap['a'], zap)
    pg.evaluate("() => { CALC.ing('ogorek').nutr.kcal = 15; CALC.ing('ogorek').alerg = []; save(); render(); }")
    pg.wait_for_timeout(250)

    pg.click('.nav[data-v="prep"]'); pg.wait_for_timeout(250)
    pg.click('button[data-edit-prep="ryz-gotowany"]'); pg.wait_for_timeout(300)
    check('przełącznik odpadu w edytorze półproduktu', pg.locator('[data-w="0"]').count() == 1)
    check('podgląd energii półproduktu', pg.locator('#pKcal').inner_text() != '—',
          pg.locator('#pKcal').inner_text())
    pg.click('#dlgFoot button:has-text("Anuluj")'); pg.wait_for_timeout(200)

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
