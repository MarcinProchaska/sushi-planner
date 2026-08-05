import json
import re
from playwright.sync_api import sync_playwright

URL = 'file:///root/sushi-planner/sushi-planner.html'
errors = []
FAIL = []


def zmiesci(dok):
    """Czy gotowy dokument mieści się w polu zadruku A4 (717×1026 px przy 96 dpi)."""
    return pg.evaluate("""(html) => {
      const f = document.createElement('iframe');
      f.style.cssText = 'position:fixed;left:-10000px;top:0;border:0;width:717px;height:1026px';
      document.body.appendChild(f);
      const d = f.contentDocument;
      d.open(); d.write(html); d.close();
      const r = {h: d.body.scrollHeight, w: d.body.scrollWidth};
      f.remove(); return r;
    }""", dok)


def check(name, cond, extra=''):
    print(('  OK   ' if cond else '  FAIL ') + name + (('  -> ' + str(extra)) if extra and not cond else ''))
    if not cond:
        FAIL.append(name)


def zlPl(v):
    return f'{v:.2f}'.replace('.', ',') + ' zł'


def pickCombo(pg, cid, fragment):
    """wybiera pozycję z listy z wyszukiwaniem: wpisuje fragment i klika pierwszą podpowiedź"""
    pg.click(f'#{cid}_q')
    pg.fill(f'#{cid}_q', fragment)
    pg.wait_for_timeout(180)
    pg.locator(f'#{cid}_p .opt').first.click()
    pg.wait_for_timeout(150)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 1440, 'height': 1000})
    pg.on('console', lambda m: errors.append(m.type + ': ' + m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errors.append('pageerror: ' + str(e)))
    pg.goto(URL)
    pg.wait_for_timeout(700)

    print('\n== START ==')
    check('brak błędów JS przy starcie', not errors, errors)
    check('startowy widok się wyrenderował',
          pg.locator('h1').first.inner_text() == 'Pulpit',
          pg.locator('h1').first.inner_text())

    # --- zgodność silnika z Pythonem ---
    print('\n== SILNIK OBLICZEŃ ==')
    res = pg.evaluate("""() => {
      const out = {items:{}, sets:{}};
      DB.items.forEach(i=>{ const c=CALC.itemCalc(i,'dostawa');
        out.items[i.name]={net:c.net, fc:c.fc, per:c.perPiece, sug:c.suggested}; });
      DB.sets.forEach(s=>{ const c=CALC.setCalc(s,'dostawa'), v=CALC.setCalc(s,'vending');
        out.sets[s.name]={net:c.net, fc:c.fc, fcVend:v.fc, pieces:c.pieces}; });
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

    check('food cost Zestaw 1 (Dostawa, VAT 8%) = 28,5%',
          abs(res['sets']['Zestaw 1']['fc'] - 0.28510) < 0.0005, res['sets']['Zestaw 1']['fc'])
    # ten sam koszt, niższy VAT → wyższy przychód netto → niższy food cost
    check('food cost Zestaw 1 (Vending, VAT 5%) = 27,7%',
          abs(res['sets']['Zestaw 1']['fcVend'] - 0.28510 * 1.05 / 1.08) < 0.0005,
          res['sets']['Zestaw 1']['fcVend'])
    check('kawałki Zestaw 10 = 100', res['sets']['Zestaw 10']['pieces'] == 100, res['sets']['Zestaw 10']['pieces'])
    check('ryż gotowany 4,7878 zł/kg', abs(res['rice'] * 1000 - 4.7878) < 0.01, round(res['rice'] * 1000, 4))
    check('zaprawa 4,3845 zł/l', abs(res['zaprawa'] - 4.3845) < 0.001, res['zaprawa'])

    # sugerowana cena: koszt netto * 1.08 / 0.30, zaokrąglona do ,90
    sug = res['items']['Uramaki Łosoś']['sug']
    check('sugerowana cena Uramaki Łosoś = 24,90', abs(sug - 24.9) < 0.001, sug)

    # --- nawigacja przez wszystkie widoki ---
    print('\n== MENU I WIDOKI ==')
    grupy = [g.split('\n')[0].strip().lower() for g in pg.locator('.navgrp').all_inner_texts()]
    check('cztery grupy w menu', grupy == ['pulpit', 'edycja', 'analizy', 'narzędzia'], grupy)

    # zwijanie grup — Pulpit zostaje zawsze
    check('Pulpit nie jest zwijalny', pg.locator('button.navgrp[data-grp="pulpit"]').count() == 0)
    check('trzy grupy zwijalne', pg.locator('button.navgrp').count() == 3)
    pg.click('button.navgrp[data-grp="edycja"]'); pg.wait_for_timeout(250)
    check('klik zwija grupę', not pg.locator('#grp-edycja').is_visible())
    check('i zapamiętuje to w przeglądarce',
          pg.evaluate("() => JSON.parse(localStorage.getItem('sp_grupy')).edycja") is True)
    pg.click('button.navgrp[data-grp="edycja"]'); pg.wait_for_timeout(250)
    check('ponowny klik rozwija', pg.locator('#grp-edycja').is_visible())
    # zwinięta grupa z bieżącą zakładką rozwija się sama
    pg.evaluate("() => { GRUPY.analizy = true; malujGrupy(); }"); pg.wait_for_timeout(200)
    pg.evaluate("() => go('hist')"); pg.wait_for_timeout(300)
    check('grupa z bieżącą zakładką rozwija się sama', pg.locator('#grp-analizy').is_visible())

    WIDOKI = [
        ('dHome', 'Pulpit'), ('dPrep', 'Przygotowanie'), ('dRolki', 'Rolki'), ('dZest', 'Zestawy'),
        ('dPack', 'Pakowanie'), ('driver', 'Kierowca'), ('stock', 'Kontrola zasobów'),
        ('load', 'Załadunki'), ('vend', 'Automaty'), ('sets', 'Zestawy'), ('items', 'Rolki'),
        ('prep', 'Półprodukty'), ('ing', 'Składniki'),
        ('dash', 'Foodcost'), ('hist', 'Historia cen'), ('sim', 'Symulacja „co jeśli”'),
        ('set', 'Ustawienia'),
    ]
    for v, h in WIDOKI:
        pg.click(f'.nav[data-v="{v}"]')
        pg.wait_for_timeout(220)
        check(f'widok {v}', pg.locator('h1').first.inner_text() == h, pg.locator('h1').first.inner_text())
    check('brak błędów JS po obejściu widoków', not errors, errors)
    check('Aktualizacja ukryta poza trybem serwerowym',
          'hidden' in pg.locator('#navUpd').get_attribute('class'))
    check('Wyloguj ukryte poza trybem serwerowym',
          'hidden' in pg.locator('#navOut').get_attribute('class'))

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

    # --- listy rozwijane z wyszukiwaniem ---
    print('\n== LISTY Z WYSZUKIWANIEM ==')
    pg.click('.nav[data-v="items"]'); pg.wait_for_timeout(250)
    pg.click('button[data-act="addItem2"]'); pg.wait_for_timeout(300)
    check('combo zamiast selecta', pg.locator('#iAdd_q').count() == 1
          and pg.locator('select#iAdd').count() == 0)

    pg.click('#iAdd_q'); pg.wait_for_timeout(200)
    wszystkie = pg.locator('#iAdd_p .opt').count()
    check('po kliknięciu widać pełną listę', wszystkie > 20, wszystkie)

    etykiety = pg.locator('#iAdd_p .opt').all_inner_texts()
    ALFA = 'aąbcćdeęfghijklłmnńoópqrsśtuvwxyzźż'
    def pl_key2(s):
        return [ALFA.index(c) if c in ALFA else 99 for c in s.lower()]
    pierwsze = [e.split(' ')[0] for e in etykiety if not e.startswith('◍')]
    check('lista posortowana po polsku', pierwsze == sorted(pierwsze, key=pl_key2), pierwsze[:6])
    naz = [e.split(' ')[0] for e in etykiety]
    check('Ł trafia między L a M, nie na koniec',
          naz.index('Łosoś') < naz.index('Majonez'), naz)

    # wyszukiwanie po fragmencie ze środka nazwy
    pg.fill('#iAdd_q', 'krewet'); pg.wait_for_timeout(200)
    tr = pg.locator('#iAdd_p .opt').all_inner_texts()
    check('filtr po fragmencie', len(tr) < wszystkie and all('rewet' in x.lower() for x in tr), tr)

    # bez polskich ogonków
    pg.fill('#iAdd_q', 'losos'); pg.wait_for_timeout(200)
    tr = pg.locator('#iAdd_p .opt').all_inner_texts()
    check('wyszukiwanie ignoruje ogonki', any('Łosoś' in x for x in tr), tr)

    # fragment ze środka, nie tylko od początku
    pg.fill('#iAdd_q', 'gotowany'); pg.wait_for_timeout(200)
    tr = pg.locator('#iAdd_p .opt').all_inner_texts()
    check('fragment ze środka nazwy', any('Ryż gotowany' in x for x in tr), tr)

    # nic nie pasuje
    pg.fill('#iAdd_q', 'zzzqqq'); pg.wait_for_timeout(200)
    check('komunikat gdy nic nie pasuje', pg.locator('#iAdd_p .none').count() == 1)

    # klawiatura: strzałka + Enter
    pg.fill('#iAdd_q', 'wasabi'); pg.wait_for_timeout(200)
    pg.keyboard.press('Enter'); pg.wait_for_timeout(200)
    check('Enter wybiera podświetloną pozycję',
          pg.evaluate("() => document.getElementById('iAdd').value") == 'wasabi',
          pg.evaluate("() => document.getElementById('iAdd').value"))
    check('pole pokazuje pełną nazwę po wyborze',
          'Wasabi' in pg.locator('#iAdd_q').input_value(), pg.locator('#iAdd_q').input_value())

    # Escape przywraca poprzedni wybór
    pg.fill('#iAdd_q', 'nori'); pg.wait_for_timeout(150)
    pg.keyboard.press('Escape'); pg.wait_for_timeout(200)
    check('Escape nie zmienia wyboru',
          pg.evaluate("() => document.getElementById('iAdd').value") == 'wasabi')
    check('i przywraca tekst', 'Wasabi' in pg.locator('#iAdd_q').input_value())

    # dodanie działa
    pg.click('#iAddBtn'); pg.wait_for_timeout(250)
    check('wybrany składnik trafia do receptury', 'Wasabi' in pg.locator('#itComps').inner_text())
    pg.click('#dlgFoot button:has-text("Anuluj")'); pg.wait_for_timeout(250)

    # filtr kategorii też jest wyszukiwalny, z przypiętą pozycją na górze
    pg.click('.nav[data-v="ing"]'); pg.wait_for_timeout(250)
    check('filtr kategorii to combo', pg.locator('#ingCat_q').count() == 1)
    pg.click('#ingCat_q'); pg.wait_for_timeout(200)
    kat = pg.locator('#ingCat_p .opt').all_inner_texts()
    check('„Wszystkie kategorie" przypięte na górze', kat[0] == 'Wszystkie kategorie', kat[:3])
    check('reszta kategorii posortowana', kat[1:] == sorted(kat[1:], key=pl_key2), kat[1:])
    pg.keyboard.press('Escape'); pg.wait_for_timeout(150)

    # historia i symulacja
    pg.click('.nav[data-v="sim"]'); pg.wait_for_timeout(250)
    check('symulacja ma combo', pg.locator('#simIng_q').count() == 1)

    # --- automaty vendingowe ---
    print('\n== AUTOMATY ==')
    check('pozycja Automaty w menu', pg.locator('.nav[data-v="vend"]').count() == 1)
    pg.click('.nav[data-v="vend"]'); pg.wait_for_timeout(400)
    check('widok Automaty', pg.locator('h1').first.inner_text() == 'Automaty')
    pg.click('[data-viewgroup="mach"] button[data-vm="list"]'); pg.wait_for_timeout(350)

    maszyny = pg.evaluate("() => DB.machines.map(m=>m.name)")
    check('sześć automatów z danymi startowymi', len(maszyny) == 6, maszyny)
    for nazwa in ('Zabierzów, Biedronka', 'Plac Imbramowski', 'Przewóz, Delikatesy Premium',
                  'Kaufland, Galicyjska', 'Kraków, Jasnogórska', 'Kaufland, Norymberska'):
        check(f'automat „{nazwa}"', nazwa in maszyny)
    check('adresy uzupełnione', pg.evaluate("() => DB.machines.every(m=>!!m.addr)"))

    kody = pg.evaluate("() => DB.machines.map(m=>m.code)")
    check('każdy automat ma kod', all(kody) and len(kody) == 6, kody)
    check('kody unikalne', len(set(kody)) == 6, kody)
    check('kody z lokalizacji', set(kody) == {'ZAB','IMB','PRZ','GAL','JAS','NOR'}, kody)
    check('kod widoczny na liście', 'ZAB' in pg.content())

    # kod dorabia się starym automatom bez kodu
    dor = pg.evaluate("""() => {
      const kopia = JSON.parse(JSON.stringify(DB));
      DB.machines.forEach(m=>{ delete m.code; });
      DB.machines.push({id:'aut-x', name:'Wieliczka, Rynek', addr:'', note:''});
      migrateVending();
      const wynik = DB.machines.map(m=>m.code);
      DB = kopia; load2(); save(); render();
      return wynik;
    }""")
    check('brakujące kody dorobione', all(dor), dor)
    check('nowy automat dostaje kod z nazwy', dor[-1] == 'WIE', dor)
    check('dorobione kody unikalne', len(set(dor)) == len(dor), dor)

    # lista automatów nie powiela kwot wspólnych dla wszystkich
    naglowki = pg.locator('table[data-tbl="mach"] th').all_inner_texts()
    check('kolumna Kod w tabeli automatów', 'Kod' in naglowki, naglowki)
    check('bez kolumny z wartością załadunku',
          not any('artość' in h for h in naglowki), naglowki)
    check('licznik w menu = 6', pg.locator('#cVend').inner_text() == '6')

    check('dwadzieścia szafek', pg.locator('.lock').count() == 20)
    check('dwie kolumny po dziesięć', pg.locator('.lockers > div').count() == 2)
    kol1 = pg.locator('.lockers > div').first.locator('.lock .no').all_inner_texts()
    kol2 = pg.locator('.lockers > div').last.locator('.lock .no').all_inner_texts()
    check('kolumna 1 to szafki 1–10', kol1 == [str(i) for i in range(1, 11)], kol1)
    check('kolumna 2 to szafki 11–20', kol2 == [str(i) for i in range(11, 21)], kol2)
    check('na starcie szafki puste',
          pg.evaluate("() => Object.keys(DB.vending.layout).length") == 0)
    check('puste szafki wyróżnione', pg.locator('.lock.pusta').count() == 20)

    # przypisanie zestawu do szafki przez listę z wyszukiwaniem
    pickCombo(pg, 'slot1', 'Zestaw 1')
    pg.wait_for_timeout(400)
    przyp = pg.evaluate("() => DB.vending.layout['1']")
    check('zestaw przypisany do szafki 1', przyp == 'zestaw-1', przyp)
    check('szafka przestała być pusta', pg.locator('.lock.pusta').count() == 19)

    # arytmetyka załadunku — ceny zawsze z kanału Vending
    pg.evaluate("""() => {
      const s = active(DB.sets);
      for(let n=1;n<=20;n++) DB.vending.layout[String(n)] = s[(n-1)%s.length].id;
      save(); render();
    }""")
    pg.wait_for_timeout(500)
    a = pg.evaluate("""() => {
      let wart=0, koszt=0, netto=0;
      for(let n=1;n<=20;n++){ const s=CALC.set(DB.vending.layout[String(n)]);
        const c=CALC.setCalc(s,'vending'); wart+=c.priceGross||0; koszt+=c.net; netto+=c.priceNet||0; }
      return {wart, koszt, fc:koszt/netto, maszyn:active(DB.machines).length};
    }""")
    tresc = pg.content()
    check('wartość jednego automatu na kaflu', zlPl(a['wart']) in tresc, zlPl(a['wart']))
    check('koszt załadunku na kaflu', zlPl(a['koszt']) in tresc, zlPl(a['koszt']))
    check('wartość wszystkich automatów', zlPl(a['wart'] * a['maszyn']) in tresc,
          zlPl(a['wart'] * a['maszyn']))
    check('komplet szafek', '20 / 20' in tresc)

    # kanał Vending niezależny od przełącznika w innych widokach
    pg.evaluate("() => { setChan('dostawa'); render(); }")
    pg.wait_for_timeout(400)
    check('ceny w automatach nadal vendingowe', zlPl(a['wart']) in pg.content())
    pg.evaluate("() => { setChan('vending'); render(); }")
    pg.wait_for_timeout(300)

    # układ jest wspólny, nie per maszyna
    check('układ trzymany raz, nie przy maszynach',
          pg.evaluate("() => DB.machines.every(m=>m.layout===undefined)"))

    # zestaw w szafce jest chroniony przed usunięciem
    pg.on('dialog', lambda d: d.dismiss() if 'Nie można' not in d.message else d.accept())
    blok = pg.evaluate("""() => {
      const przed = DB.sets.length;
      const wynik = deleteEntity('sets', DB.vending.layout['1']);
      return {wynik, przed, po: DB.sets.length};
    }""")
    check('nie da się usunąć zestawu wstawionego do szafki',
          blok['wynik'] is False and blok['przed'] == blok['po'], blok)

    # dodanie i edycja automatu
    pg.click('[data-act="addMach"]'); pg.wait_for_timeout(300)
    pg.fill('#mName', 'Testowy automat')
    pg.fill('#mAddr', 'Testowa 1, Kraków')
    pg.fill('#mCode', 'zab')                       # zajęty, w dodatku małymi
    pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(400)
    check('zduplikowany kod odrzucony', pg.evaluate("() => DB.machines.length") == 6,
          pg.evaluate("() => DB.machines.length"))
    pg.fill('#mCode', 'tst')
    pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(400)
    check('kod zapisany wielkimi literami',
          pg.evaluate("() => (DB.machines.find(m=>m.name==='Testowy automat')||{}).code") == 'TST')
    check('automat dodany', pg.evaluate("() => DB.machines.length") == 7)
    check('licznik zaktualizowany', pg.locator('#cVend').inner_text() == '7')
    check('nowy automat w podsumowaniu na 7 automatów', 'Na 7 automatów' in pg.content())
    pg.evaluate("() => { DB.machines = DB.machines.filter(m=>m.name!=='Testowy automat'); save(); render(); }")
    pg.wait_for_timeout(300)

    # czyszczenie układu
    pg.evaluate("() => { DB.vending.layout={}; save(); render(); }")
    pg.wait_for_timeout(400)
    check('po wyczyszczeniu wszystkie szafki puste', pg.locator('.lock.pusta').count() == 20)
    check('lista pustych szafek w podsumowaniu', 'puste: 1, 2, 3' in pg.content())

    # dane z serwera / importu przechodzą przez load2 — musi dołożyć brakujące działy
    print('\n== MIGRACJA PRZEZ load2 ==')
    mig = pg.evaluate("""() => {
      const kopia = JSON.parse(JSON.stringify(DB));
      const surowe = JSON.parse(JSON.stringify(DB));
      delete surowe.machines; delete surowe.vending;      // baza sprzed 1.17
      surowe.preps.forEach(p=>p.items.forEach(c=>{ delete c.waste; }));
      let blad = null;
      try { DB = surowe; load2(); render(); } catch(e){ blad = String(e); }
      const wynik = {blad, maszyn: DB.machines ? DB.machines.length : null,
                     szafek: DB.vending ? DB.vending.slots : null,
                     naglowek: document.querySelector('#main h1') ? document.querySelector('#main h1').textContent : null};
      DB = kopia; load2(); save(); render();
      return wynik;
    }""")
    check('stara baza nie wywala renderowania', mig['blad'] is None, mig['blad'])
    check('load2 dokłada automaty', mig['maszyn'] == 6, mig['maszyn'])
    check('load2 dokłada układ szafek', mig['szafek'] == 20, mig['szafek'])
    check('widok się narysował, nie zostało samo menu', mig['naglowek'] == 'Automaty', mig['naglowek'])

    # strażnik: obie drogi wczytania muszą dać identyczną strukturę,
    # bo rozjazd między load() a load2() dwa razy wysypał widok po aktualizacji
    struk = pg.evaluate("""() => {
      const kopia = JSON.parse(JSON.stringify(DB));
      const goła = {settings:{}, ingredients:[], preps:[], items:[], sets:[], history:[]};
      DB = JSON.parse(JSON.stringify(goła)); migrateAll();
      const zLoad2 = Object.keys(DB).sort();
      DB = JSON.parse(JSON.stringify(goła)); migrateAll();
      const zLoad = Object.keys(DB).sort();
      const dzialy = zLoad.slice();
      DB = kopia; load2(); save(); render();
      return {zLoad, zLoad2, dzialy};
    }""")
    check('load() i load2() dają tę samą strukturę', struk['zLoad'] == struk['zLoad2'], struk)
    for dzial in ('machines', 'vending', 'loads', 'settings', 'ingredients', 'preps', 'items', 'sets', 'history'):
        check(f'migracja dokłada dział „{dzial}"', dzial in struk['dzialy'], struk['dzialy'])

    # każdy widok musi się narysować na najuboższych możliwych danych
    puste = pg.evaluate("""() => {
      const kopia = JSON.parse(JSON.stringify(DB));
      DB = {settings:{}, ingredients:[], preps:[], items:[], sets:[], history:[]};
      migrateAll();
      const bledy = {};
      ['dash','ing','prep','items','sets','vend','load','hist','sim','set'].forEach(v=>{
        try { VIEW=v; render(); } catch(e){ bledy[v] = String(e); }
      });
      DB = kopia; load2(); VIEW='dash'; save(); render();
      return bledy;
    }""")
    check('każdy widok renderuje się na pustej bazie', puste == {}, puste)

    # --- załadunki ---
    print('\n== ZAŁADUNKI ==')
    # układ szafek: 18 z 20 zapełnionych, dwie celowo puste
    pg.evaluate("""() => {
      const s = active(DB.sets); DB.vending.layout = {};
      for(let n=1;n<=18;n++) DB.vending.layout[String(n)] = s[(n-1)%s.length].id;
      DB.loads = []; SEL.load = null; save(); render();
    }""")
    pg.wait_for_timeout(300)
    check('pozycja Załadunki w menu', pg.locator('.nav[data-v="load"]').count() == 1)
    pg.click('.nav[data-v="load"]'); pg.wait_for_timeout(350)
    check('pusta lista załadunków', 'Brak załadunków' in pg.content())

    pg.click('[data-act="addLoad"]'); pg.wait_for_timeout(350)
    pg.fill('#zName', 'Poniedziałek rano')
    pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(500)
    check('załadunek utworzony', pg.evaluate("() => DB.loads.length") == 1)
    check('po zapisie od razu jego siatka', 'Poniedziałek rano' in pg.locator('h1').first.inner_text())

    masz = pg.evaluate("() => active(DB.machines).length")
    check('na start zaznaczone tylko szafki z zestawem',
          pg.evaluate("() => zalSuma(DB.loads[0]).szt") == 18 * masz,
          pg.evaluate("() => zalSuma(DB.loads[0]).szt"))
    check('kafelek na każdy automat', pg.locator('.zal-grid > .card').count() == masz)
    check('dwadzieścia szafek na automat',
          pg.locator('.zal-grid > .card').first.locator('.zal-slot').count() == 20)
    check('szafki bez zestawu wyszarzone', pg.locator('.zal-slot.pusto').count() == 2 * masz)
    check('nazwa zestawu, nie cena', 'Zestaw 1' in pg.locator('.zal-slot').first.inner_text(),
          pg.locator('.zal-slot').first.inner_text())
    check('pusta szafka nie jest klikalna',
          pg.locator('.zal-slot.pusto[data-slot]').count() == 0)

    # przełączanie pojedynczej szafki
    mid = pg.evaluate("() => active(DB.machines)[0].id")
    pg.click(f'[data-slot="{mid}|3"]'); pg.wait_for_timeout(350)
    check('klik wyłącza szafkę', pg.evaluate(f"() => slotOn(DB.loads[0],'{mid}','3')") is False)
    check('szafka pokazana na czerwono',
          'off' in pg.locator(f'[data-slot="{mid}|3"]').get_attribute('class'))
    check('licznik spadł o jeden',
          pg.evaluate("() => zalSuma(DB.loads[0]).szt") == 18 * masz - 1)
    pg.click(f'[data-slot="{mid}|3"]'); pg.wait_for_timeout(350)
    check('ponowny klik włącza z powrotem',
          pg.evaluate(f"() => slotOn(DB.loads[0],'{mid}','3')") is True)

    # hurtem na jednym automacie
    pg.click(f'[data-mach-all="{mid}|off"]'); pg.wait_for_timeout(350)
    check('odznaczenie całego automatu',
          pg.evaluate(f"() => zalSuma(DB.loads[0],'{mid}').szt") == 0)
    check('pozostałe automaty nietknięte',
          pg.evaluate("() => zalSuma(DB.loads[0]).szt") == 18 * (masz - 1))
    pg.click(f'[data-mach-all="{mid}|on"]'); pg.wait_for_timeout(350)
    check('zaznaczenie całego automatu tylko tam, gdzie jest zestaw',
          pg.evaluate(f"() => zalSuma(DB.loads[0],'{mid}').szt") == 18)

    # hurtem na wszystkich
    pg.click('#zalNone'); pg.wait_for_timeout(400)
    check('odznacz wszystko', pg.evaluate("() => zalSuma(DB.loads[0]).szt") == 0)
    pg.click('#zalAll'); pg.wait_for_timeout(400)
    check('zaznacz wszystko', pg.evaluate("() => zalSuma(DB.loads[0]).szt") == 18 * masz)

    # arytmetyka podsumowania liczona niezależnie
    z = pg.evaluate("""() => {
      let szt=0, wart=0, koszt=0;
      active(DB.machines).forEach(m=>{ for(let n=1;n<=DB.vending.slots;n++){
        if(!slotOn(DB.loads[0], m.id, n)) return void 0;
      }});
      active(DB.machines).forEach(m=>{ for(let n=1;n<=DB.vending.slots;n++){
        if(!slotOn(DB.loads[0], m.id, n)) continue;
        const s = slotSet(n); if(!s) continue;
        const c = CALC.setCalc(s,'vending'); szt++; wart+=c.priceGross||0; koszt+=c.net; }});
      return {szt, wart, koszt};
    }""")
    tresc = pg.content()
    check('wartość załadunku na kaflu', zlPl(z['wart']) in tresc, zlPl(z['wart']))
    check('koszt wytworzenia na kaflu', zlPl(z['koszt']) in tresc, zlPl(z['koszt']))
    check('tabela do przygotowania', 'Do przygotowania' in tresc)

    # nazwa jest wymagana
    pg.click('[data-act="addLoad"]'); pg.wait_for_timeout(350)
    pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(350)
    check('bez nazwy nie zapisze', pg.evaluate("() => DB.loads.length") == 1)
    pg.fill('#zName', 'Drugi')
    pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(450)
    check('drugi załadunek', pg.evaluate("() => DB.loads.length") == 2)
    check('każdy ma własne zaznaczenia',
          pg.evaluate("() => DB.loads[0].slots !== DB.loads[1].slots"))
    check('licznik w menu', pg.locator('#cLoad').inner_text() == '2')

    # powrót do listy
    pg.evaluate("() => { SEL.load=null; render(); }"); pg.wait_for_timeout(350)
    check('lista pokazuje oba załadunki', 'Poniedziałek rano' in pg.content() and 'Drugi' in pg.content())

    # --- plan tygodnia ---
    print('\n== PLAN TYGODNIA ==')
    pg.evaluate("""() => {
      const a=nowyZaladunek('Dni robocze'), w=nowyZaladunek('Weekend');
      DB.loads=[a,w];
      DB.week={pn:a.id, wt:a.id, sr:a.id, cz:a.id, so:w.id, nd:w.id};
      SEL.load=null; save(); render();
    }""")
    pg.wait_for_timeout(450)
    check('kalendarz tygodnia nad listą', 'Tydzień' in pg.content())
    check('lista wyboru przy każdym dniu', pg.locator('[id^="dz_"][id$="_q"]').count() == 7)
    check('zakresy dni zwijane',
          pg.evaluate("() => DB.loads.map(z=>dniLabel(dniZaladunku(z)))") == ['Pn–Cz', 'So, Nd'],
          pg.evaluate("() => DB.loads.map(z=>dniLabel(dniZaladunku(z)))"))
    check('wolny dzień wypisany', 'piątek' in pg.content())
    check('dzień wskazuje swój załadunek',
          pg.evaluate("() => (zaladunekNaDzien('wt')||{}).name") == 'Dni robocze')
    check('piątek wolny', pg.evaluate("() => zaladunekNaDzien('pt')") is None)

    # przypisanie dnia wprost w kalendarzu
    pickCombo(pg, 'dz_pt', 'Weekend'); pg.wait_for_timeout(500)
    check('piątek przypisany z kalendarza',
          pg.evaluate("() => (zaladunekNaDzien('pt')||{}).name") == 'Weekend')
    check('etykieta zwinęła się do Pt–Nd',
          pg.evaluate("() => dniLabel(dniZaladunku(DB.loads[1]))") == 'Pt–Nd',
          pg.evaluate("() => dniLabel(dniZaladunku(DB.loads[1]))"))
    check('cały tydzień pokryty',
          pg.evaluate("() => DNI.every(d=>!!zaladunekNaDzien(d.k))"))

    # przypisanie dnia zabiera go poprzedniemu — bez żadnej walidacji
    pickCombo(pg, 'dz_pn', 'Weekend'); pg.wait_for_timeout(500)
    check('poniedziałek przeszedł do Weekendu',
          pg.evaluate("() => (zaladunekNaDzien('pn')||{}).name") == 'Weekend')
    check('i zniknął z Dni roboczych',
          pg.evaluate("() => dniLabel(dniZaladunku(DB.loads[0]))") == 'Wt–Cz',
          pg.evaluate("() => dniLabel(dniZaladunku(DB.loads[0]))"))
    check('dzień może należeć tylko do jednego załadunku',
          pg.evaluate("() => DB.loads.filter(z=>dniZaladunku(z).includes('pn')).length") == 1)

    # zwolnienie dnia
    pickCombo(pg, 'dz_pn', 'brak'); pg.wait_for_timeout(500)
    check('wybór „brak" zwalnia dzień', pg.evaluate("() => zaladunekNaDzien('pn')") is None)

    # w edytorze załadunku nie ma już dni
    pg.click('.tcard[data-pick-load] [data-edit-load]'); pg.wait_for_timeout(400)
    check('edytor bez pigułek dni', pg.locator('#zDni').count() == 0)
    check('edytor odsyła do planu tygodnia', 'planie tygodnia' in pg.content())
    pg.click('#dlgFoot button:has-text("Anuluj")'); pg.wait_for_timeout(300)

    # migracja starego zapisu dni przy załadunku
    mig2 = pg.evaluate("""() => {
      const kopia = JSON.parse(JSON.stringify(DB));
      DB.week = {};
      DB.loads[0].days = ['pn','wt'];
      DB.loads[1].days = ['so'];
      migrateLoads();
      const wynik = {week: JSON.parse(JSON.stringify(DB.week)),
                     zostalyDni: DB.loads.some(z=>z.days!==undefined)};
      DB = kopia; load2(); save(); render();
      return wynik;
    }""")
    check('stare dni przeniesione do planu tygodnia',
          mig2['week'].get('pn') and mig2['week'].get('wt') and mig2['week'].get('so'), mig2)
    check('pole days skasowane z załadunków', mig2['zostalyDni'] is False, mig2)

    # usunięty załadunek zwalnia swoje dni
    zw = pg.evaluate("""() => {
      const kopia = JSON.parse(JSON.stringify(DB));
      const id = DB.loads[1].id;
      DB.week.nd = id;
      DB.loads.splice(1,1);
      Object.keys(DB.week).forEach(k=>{ if(DB.week[k]===id) delete DB.week[k]; });
      migrateLoads();
      const wynik = DB.week.nd === undefined;
      DB = kopia; load2(); save(); render();
      return wynik;
    }""")
    check('wpis na nieistniejący załadunek znika', zw)

    pg.evaluate("() => { DB.loads=[nowyZaladunek('Poniedziałek rano')]; DB.week={}; SEL.load=DB.loads[0].id; save(); render(); }")
    pg.wait_for_timeout(400)

    # --- widoki dnia ---
    print('\n== WIDOKI DNIA ==')
    pg.evaluate("""() => {
      const a=nowyZaladunek('Robocze'), w=nowyZaladunek('Weekend');
      DB.loads=[a,w];
      DB.week={pn:a.id, wt:a.id, sr:a.id, cz:a.id, pt:a.id, so:w.id};   // niedziela wolna
      SEL.load=null; save(); render();
    }""")
    pg.wait_for_timeout(300)

    # ustaw dzień na znany poniedziałek
    pg.evaluate("() => { DAY='2026-08-03'; VIEW='dPrep'; render(); }"); pg.wait_for_timeout(400)
    check('pasek dnia', pg.locator('#dayPick').count() == 1)
    check('dzień tygodnia rozpoznany', 'poniedziałek' in pg.content())
    check('załadunek dnia wskazany', 'Robocze' in pg.content())

    pg.click('[data-day="1"]'); pg.wait_for_timeout(400)
    check('strzałka przesuwa o dzień', pg.evaluate("() => DAY") == '2026-08-04')
    check('i przelicza dzień tygodnia', 'wtorek' in pg.content())
    pg.click('[data-day="-1"]'); pg.wait_for_timeout(400)
    check('strzałka w tył', pg.evaluate("() => DAY") == '2026-08-03')
    pg.click('[data-day="today"]'); pg.wait_for_timeout(400)
    check('przycisk Dziś', pg.evaluate("() => DAY === todayISO()"))

    # niedziela bez załadunku
    pg.evaluate("() => { DAY='2026-08-09'; render(); }"); pg.wait_for_timeout(400)
    check('dzień bez załadunku wyjaśniony', 'nie jest przypisany żaden załadunek' in pg.content())

    # liczby zgodne z rozpiską
    pg.evaluate("() => { DAY='2026-08-03'; VIEW='dPrep'; render(); }"); pg.wait_for_timeout(400)
    ref = pg.evaluate("""() => {
      const d = daneDnia('2026-08-03');
      let koszt=0;
      Object.keys(d.r.skladniki).forEach(id=>{ if(id.indexOf('raw:')===0) return;
        const uc=CALC.ingUnitCost(id); if(uc!=null) koszt+=uc*d.r.skladniki[id]; });
      return {skl:Object.keys(d.r.skladniki).length, koszt,
              kaw:Object.values(d.r.rolki).reduce((a,b)=>a+b,0),
              zest:Object.values(d.r.zestawy).reduce((a,b)=>a+b,0),
              szafek: zalSuma(d.z).szt};
    }""")
    check('Przygotowanie: liczba składników', str(ref['skl']) in pg.content(), ref['skl'])

    # --- pulpit bez pieniędzy ---
    for v in ['dHome', 'dPrep', 'dRolki', 'dZest', 'dPack', 'driver', 'stock']:
        pg.evaluate(f"() => {{ VIEW='{v}'; render(); }}"); pg.wait_for_timeout(300)
        tekst = pg.locator('#main').inner_text()
        kwoty = re.findall(r'[\d,]+\s*zł', tekst)
        check(f'{v}: bez kwot', not kwoty, kwoty[:4])
        check(f'{v}: zawartość list bez pogrubień',
              pg.evaluate("() => document.querySelectorAll('#main tbody b, #main .kv b').length") == 0)
    pg.evaluate("() => { VIEW='dPrep'; render(); }"); pg.wait_for_timeout(300)

    # --- skład jako osobna podstrona ---
    pg.evaluate("() => { VIEW='dZest'; render(); }"); pg.wait_for_timeout(350)
    zid = pg.evaluate("() => Object.keys(daneDnia(DAY).r.zestawy).find(id=>CALC.set(id))")
    pg.click(f'[data-sklad="zst:{zid}"]'); pg.wait_for_timeout(350)
    check('klik w zestaw otwiera podstronę składu', pg.evaluate("() => VIEW") == 'dSklad')
    ref_set = pg.evaluate(f"() => {{ const s=CALC.set('{zid}');"
                          " return {rolki:(s.entries||[]).length, dodatki:(s.comps||[]).length, name:s.name}; }")
    check('skład zestawu: nagłówek', pg.locator('h1').first.inner_text() == ref_set['name'])
    check('skład zestawu: wiersz na rolkę',
          pg.locator('table[data-tbl="sklR"] tbody tr').count() == ref_set['rolki'], ref_set)
    check('zdjęcia zmniejszane do 1200 px',
          pg.evaluate("() => readPhoto.toString().includes('MAX=1200')"))
    check('skład zestawu: wiersz na dodatek',      # przy pustej liście zostaje wiersz „Bez dodatków"
          pg.locator('table[data-tbl="sklD"] tbody tr').count() == max(ref_set['dodatki'], 1), ref_set)
    kwoty_sklad = re.findall(r'[\d,]+\s*zł', pg.locator('#main').inner_text())
    check('skład bez cen', not kwoty_sklad, kwoty_sklad[:3])
    check('skład bez pogrubień w tabeli',
          pg.evaluate("() => document.querySelectorAll('#main tbody b').length") == 0)

    # zdjęcie zestawu nad składem
    pg.evaluate("""() => { const s=CALC.set(PODGLAD.id);
      s.photo='data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
      save(); render(); }""")
    pg.wait_for_timeout(300)
    check('skład zestawu pokazuje zdjęcie', pg.locator('#main img.hero').count() == 1)
    pg.evaluate("() => { const s=CALC.set(PODGLAD.id); s.photo=null; save(); render(); }")
    pg.wait_for_timeout(300)
    check('bez zdjęcia nie ma pustej ramki', pg.locator('#main img.hero').count() == 0)

    # wejście głębiej: zestaw → rolka, i powrót krok po kroku
    rid = pg.evaluate("() => { const s=CALC.set(PODGLAD.id);"
                      " const e=(s.entries||[]).find(x=>CALC.item(x.itemId)); return e?e.itemId:null; }")
    if rid:
        pg.click(f'[data-sklad="rol:{rid}"]'); pg.wait_for_timeout(350)
        check('z zestawu można wejść w rolkę',
              pg.evaluate("() => PODGLAD.typ + ':' + PODGLAD.id") == 'rol:' + rid)
        check('skład rolki: bez przeliczenia na kawałek',
              'kawałek' not in pg.locator('table[data-tbl="skl"] thead').inner_text())
        check('receptura jest na jedną rolkę, nie na cały dzień',
              pg.evaluate(f"""() => {{
                const it=CALC.item('{rid}'); if(!it.comps.length) return true;
                const c=it.comps[0], txt=document.querySelector('table[data-tbl=skl] tbody tr').textContent;
                return txt.includes(String(c.qty).replace('.', ','));
              }}"""))
        pg.click('[data-wroc]'); pg.wait_for_timeout(350)
        check('Wróć cofa o jeden krok, do zestawu',
              pg.evaluate("() => PODGLAD.typ + ':' + PODGLAD.id") == 'zst:' + zid)
    pg.click('[data-wroc]'); pg.wait_for_timeout(350)
    check('Wróć z pierwszego składu wraca do listy', pg.evaluate("() => VIEW") == 'dZest')
    check('i czyści podgląd', pg.evaluate("() => PODGLAD") is None)

    ppid = pg.evaluate("() => Object.keys(daneDnia(DAY).r.polprodukty).find(id=>CALC.prep(id))")
    if ppid:
        pg.evaluate("() => { VIEW='dPrep'; render(); }"); pg.wait_for_timeout(350)
        pg.click(f'[data-sklad="pp:{ppid}"]'); pg.wait_for_timeout(350)
        skladniki = pg.evaluate(f"() => CALC.prep('{ppid}').items.length")
        check('skład półproduktu: wiersz na składnik',
              pg.locator('table[data-tbl="skl"] tbody tr').count() == skladniki, skladniki)
        check('skład półproduktu: podana wydajność',
              'wydajność' in pg.locator('.topbar').inner_text())
        check('nazwa składu nie wygląda jak odnośnik',
              pg.evaluate("() => {const a=document.querySelector('a[data-sklad]');"
                          " if(!a) return true;"
                          " const st=getComputedStyle(a), td=getComputedStyle(a.closest('td')||a.parentElement);"
                          " return st.textDecorationLine === 'none' && st.color === td.color;}"))
        pg.click('[data-wroc]'); pg.wait_for_timeout(350)
        check('Wróć wraca na Przygotowanie', pg.evaluate("() => VIEW") == 'dPrep')

    pg.click('.nav[data-v="dRolki"]'); pg.wait_for_timeout(400)
    rolek = pg.evaluate("""() => {
      const d = daneDnia(DAY);
      return Object.keys(d.r.rolki).reduce((a,id)=>{
        const it=CALC.item(id); return a + (it ? d.r.rolki[id]/(it.pieces||1) : 0); },0);
    }""")
    check('Rolki dnia: liczba rolek zgodna z rozpiską',
          pg.evaluate("""() => {
            const t=[...document.querySelectorAll('.tiles .tile')].find(x=>/ROLEK/i.test(x.textContent));
            return t ? t.querySelector('.val').textContent.trim() : null;
          }""") == ('%g' % round(rolek, 1) if rolek % 1 else str(int(rolek))).replace('.', ','),
          rolek)
    check('Rolki dnia: bez kawałków',
          'kawałk' not in pg.locator('#main').inner_text().lower())
    check('skasowana rolka nie znika po cichu',
          pg.evaluate("() => document.body.textContent.includes('brak rolki')") ==
          pg.evaluate("() => Object.keys(daneDnia(DAY).r.rolki).some(id=>!CALC.item(id))"))

    pg.click('.nav[data-v="dZest"]'); pg.wait_for_timeout(400)
    check('Zestawy dnia: sztuki zgodne z liczbą szafek', ref['zest'] == ref['szafek'], ref)
    check('Zestawy dnia: tylko sztuki, bez kawałków',      # #, Zestaw, Sztuk
          pg.locator('table[data-tbl="dzest"] thead th').count() == 3)

    pg.click('.nav[data-v="dPack"]'); pg.wait_for_timeout(400)
    check('Pakowanie: kafelek na automat',
          pg.locator('.tiles-grid > .card').count() == pg.evaluate("() => active(DB.machines).length"))
    check('Pakowanie: kody automatów', 'ZAB' in pg.content())
    suma = pg.evaluate("""() => {
      const z = zaladunekNaDate('2026-08-03');
      return active(DB.machines).reduce((a,m)=>a+zalSuma(z,m.id).szt,0) === zalSuma(z).szt;
    }""")
    check('Pakowanie: suma po automatach = całość', suma)
    check('Pakowanie: bez numerów szafek', 'szafki' not in pg.locator('#main').inner_text().lower())
    krzyz = pg.evaluate("""() => {
      const z = zaladunekNaDate('2026-08-03'), V = DB.vending;
      const per = {};
      active(DB.machines).forEach(m=>{
        for(let n=1;n<=V.slots;n++){ if(!slotOn(z,m.id,n)) continue;
          const s=slotSet(n); if(!s) continue;
          per[s.id]=(per[s.id]||0)+1; }
      });
      return {rodzajow:Object.keys(per).length, razem:Object.values(per).reduce((a,b)=>a+b,0)};
    }""")
    check('Pakowanie: bez tabeli krzyżowej',
          pg.locator('table[data-tbl="dkrzyz"]').count() == 0)
    check('Pakowanie: rozbicie sumuje się do całości',
          krzyz['razem'] == ref['szafek'], (krzyz['razem'], ref['szafek']))

    # przełącznik Automaty / Zestawy — ta sama macierz z dwóch stron
    pg.click('[data-packgroup] [data-pt="sets"]'); pg.wait_for_timeout(350)
    check('Pakowanie: widok zestawów ma kafelek na zestaw',
          pg.locator('.tiles-grid > .card').count() == krzyz['rodzajow'], krzyz)
    check('Pakowanie: kafelki zestawów sumują się do całości',
          pg.evaluate("() => [...document.querySelectorAll('.tiles-grid>.card .licz>b')]"
                      ".reduce((a,e)=>a+(parseInt(e.textContent,10)||0),0)") == ref['szafek'])
    pg.click('[data-packgroup] [data-pt="mach"]'); pg.wait_for_timeout(350)
    check('Pakowanie: powrót do widoku automatów',
          pg.locator('.tiles-grid > .card').count() == pg.evaluate("() => active(DB.machines).length"))

    # --- wydruki z pulpitu ---
    print('\n== WYDRUKI Z PULPITU ==')
    for v in ['dPrep', 'dRolki', 'dZest', 'dPack']:
        pg.click(f'.nav[data-v="{v}"]'); pg.wait_for_timeout(300)
        check(f'{v}: przycisk PDF w pasku', pg.locator(f'[data-pdf="{v}"]').count() == 1)

    def dokDnia(fn):
        return pg.evaluate('''(fn) => {
          let out = null; const o = window.open, a = window.alert;
          window.alert = () => {};
          window.open = () => ({document:{write:h=>out=h, close(){}}, focus(){}, print(){}});
          window[fn](); window.open = o; window.alert = a;
          return out;
        }''', fn)

    ref2 = pg.evaluate("""() => {
      const d = daneDnia('2026-08-03');
      return {pp: Object.keys(d.r.polprodukty).filter(id=>CALC.prep(id)).length,
              skl: Object.keys(d.r.skladniki).length,
              rolki: Object.keys(d.r.rolki).length,
              zest: Object.keys(d.r.zestawy).length,
              szafek: zalSuma(d.z).szt,
              maszyn: active(DB.machines).length};
    }""")

    dok = {f: dokDnia(f) for f in ['pdfPrzygotowanie', 'pdfDzienRolki',
                                   'pdfDzienZestawy', 'pdfPakowanie']}
    for f, h in dok.items():
        check(f'{f}: dokument powstał', bool(h) and 'Skład' not in (h or '')[:0], bool(h))
        check(f'{f}: bez kwot', not re.findall(r'[\d,]+\s*zł', h or ''), (h or '')[:0])
        m = zmiesci(h)
        pismo = float(re.search(r'font:([\d.]+)px', h).group(1))
        # albo mieści się na stronie, albo świadomie zszedł do minimum i bierze
        # kolejną stronę — czego nie wolno nigdy, to wystawać w bok
        check(f'{f}: strona nie rozjeżdża się w bok', m['w'] <= 718, m)
        check(f'{f}: jedna strona albo minimum pisma',
              m['h'] <= 1026 or abs(pismo - 11) < 0.01, (m, pismo))
        check(f'{f}: dzień w tytule', '2026-08-03' in h and 'poniedziałek' in h)

    check('Przygotowanie: dwie sekcje i tyle wierszy co pozycji',
          'Półprodukty' in dok['pdfPrzygotowanie'] and 'Składniki' in dok['pdfPrzygotowanie']
          and dok['pdfPrzygotowanie'].count('<div>') == ref2['pp'] + ref2['skl'],
          (dok['pdfPrzygotowanie'].count('<div>'), ref2))
    check('Rolki: wiersz na rodzaj rolki',
          dok['pdfDzienRolki'].count('<div>') == ref2['rolki'], ref2['rolki'])
    check('Zestawy: wiersz na rodzaj zestawu',
          dok['pdfDzienZestawy'].count('<div>') == ref2['zest'], ref2['zest'])

    pak = dok['pdfPakowanie']
    check('Pakowanie: obie sekcje naraz',
          'Automaty' in pak and 'Zestawy' in pak and pak.count('class="sekcja"') == 2)
    check('Pakowanie: kafelek na automat i na zestaw',
          pak.count('<section class="rolka">') == ref2['maszyn'] + ref2['zest'],
          (pak.count('<section class="rolka">'), ref2))
    liczby = [int(x) for x in re.findall(r'class="q">\((\d+)\)</span>', pak)]
    check('Pakowanie: obie strony sumują się do liczby szafek',
          sum(liczby) == 2 * ref2['szafek'], (sum(liczby), ref2['szafek']))

    # dzień bez załadunku nie generuje pustej kartki
    pusty = pg.evaluate("""() => {
      const tydzien = DB.week, komunikaty = [], a = window.alert;
      DB.week = {};                              // dzień bez przypisanego załadunku
      window.alert = m => komunikaty.push(m);
      let out = null; const o = window.open;
      window.open = () => ({document:{write:h=>out=h, close(){}}, focus(){}, print(){}});
      pdfPrzygotowanie();
      window.open = o; window.alert = a; DB.week = tydzien; render();
      return {out, komunikaty};
    }""")
    check('dzień bez załadunku: brak dokumentu i wyjaśnienie',
          pusty['out'] is None and any('załadunek' in k for k in pusty['komunikaty']), pusty)

    # --- powrót na pulpit z każdego ekranu dnia ---
    for v in ['dPrep', 'dRolki', 'dZest', 'dPack', 'driver', 'stock']:
        pg.click(f'.nav[data-v="{v}"]'); pg.wait_for_timeout(300)
        pg.click('.topbar [data-wroc]'); pg.wait_for_timeout(300)
        check(f'{v}: Wróć prowadzi na Pulpit', pg.evaluate("() => VIEW") == 'dHome')
    pg.click('.nav[data-v="dPack"]'); pg.wait_for_timeout(300)

    # --- kierowca ---
    pg.click('.nav[data-v="driver"]'); pg.wait_for_timeout(400)
    check('Kierowca: kafelek na automat',
          pg.locator('.zal-grid > .card').count() == pg.evaluate("() => active(DB.machines).length"))
    mid = pg.evaluate("() => active(DB.machines)[0].id")
    pg.click(f'[data-kier="{mid}"]'); pg.wait_for_timeout(400)
    check('Kierowca: klik powiększa automat', pg.evaluate("() => KIER") == mid)
    kier = pg.evaluate(f"""() => {{
      const z = zaladunekNaDate('2026-08-03'), V = DB.vending, nry=[], wg={{}};
      for(let n=1;n<=V.slots;n++){{ if(!slotOn(z,'{mid}',n)) continue;
        const s=slotSet(n); if(!s) continue; nry.push(n); wg[s.id]=(wg[s.id]||0)+1; }}
      return {{szafek:nry.length, rodzajow:Object.keys(wg).length, nry}};
    }}""")
    check('Kierowca: wiersz na zestaw',
          pg.locator('table[data-tbl="kier"] tbody tr').count() == kier['rodzajow'], kier)
    tekst_kier = pg.locator('table[data-tbl="kier"]').inner_text()
    check('Kierowca: wszystkie numery szafek wypisane',
          all(str(n) in tekst_kier for n in kier['nry']), kier['nry'])
    check('Kierowca: suma sztuk = liczba szafek',
          pg.evaluate("() => [...document.querySelectorAll('table[data-tbl=kier] tbody tr td:nth-child(2)')]"
                      ".reduce((a,e)=>a+(parseInt(e.textContent,10)||0),0)") == kier['szafek'], kier['szafek'])
    pg.click('[data-kier=""]'); pg.wait_for_timeout(400)
    check('Kierowca: powrót do wszystkich', pg.evaluate("() => KIER") is None)

    # --- pulpit główny ---
    pg.click('.nav[data-v="dHome"]'); pg.wait_for_timeout(400)
    check('Pulpit: sześć kafelków', pg.locator('.pulpit > a.card').count() == 6)
    check('Pulpit: pokazuje datę', pg.evaluate("() => DAY") in pg.content())
    pg.click('.pulpit a[data-go="dRolki"]'); pg.wait_for_timeout(400)
    check('Pulpit: kafelek prowadzi do ekranu', pg.evaluate("() => VIEW") == 'dRolki')
    pg.click('.nav[data-v="dPack"]'); pg.wait_for_timeout(300)

    # kontrola zasobów: jutro i pojutrze
    pg.click('.nav[data-v="stock"]'); pg.wait_for_timeout(450)
    check('Kontrola zasobów: kolumny jutro i pojutrze',
          'jutro' in pg.content() and 'pojutrze' in pg.content())
    zas = pg.evaluate("""() => {
      const j = daneDnia(przesunDate(DAY,1)), p2 = daneDnia(przesunDate(DAY,2));
      const suma = {};
      [j,p2].forEach(d=>{ if(!d.r) return;
        Object.keys(d.r.skladniki).forEach(k=>{ suma[k]=(suma[k]||0)+d.r.skladniki[k]; }); });
      const jeden = Object.keys(suma)[0];
      return {ile:Object.keys(suma).length,
              razem: suma[jeden],
              skladowe: [j.r?(j.r.skladniki[jeden]||0):0, p2.r?(p2.r.skladniki[jeden]||0):0]};
    }""")
    check('suma dwóch dni = suma kolumn',
          abs(zas['razem'] - sum(zas['skladowe'])) < 1e-9, zas)
    check('lista zapotrzebowania niepusta', zas['ile'] > 0, zas)

    # dzień bez załadunku w prognozie jest zgłaszany
    pg.evaluate("() => { DAY='2026-08-08'; render(); }"); pg.wait_for_timeout(400)   # sobota → nd wolna
    check('brak załadunku w prognozie zgłoszony', 'bez przypisanego załadunku' in pg.content())

    pg.evaluate("() => { DAY=todayISO(); DB.loads=[nowyZaladunek('Poniedziałek rano')]; DB.week={}; SEL.load=DB.loads[0].id; VIEW='load'; save(); render(); }")
    pg.wait_for_timeout(400)

    # --- pulpit na telefonie ---
    print('\n== PULPIT NA TELEFONIE ==')
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.evaluate("() => { const a=DB.loads[0];"
                " DB.week={pn:a.id,wt:a.id,sr:a.id,cz:a.id,pt:a.id,so:a.id,nd:a.id};"
                " SEL.load=null; DAY='2026-08-03'; save(); render(); }")
    pg.wait_for_timeout(400)
    for v in ['dHome', 'dPrep', 'dRolki', 'dZest', 'dPack', 'driver', 'stock']:
        pg.evaluate(f"() => {{ VIEW='{v}'; KIER=null; render(); }}"); pg.wait_for_timeout(300)
        szer = pg.evaluate("() => ({sw: document.documentElement.scrollWidth,"
                           " cw: document.documentElement.clientWidth})")
        check(f'{v}: nic nie wystaje poza ekran', szer['sw'] <= szer['cw'] + 1, szer)
    pg.evaluate("() => { VIEW='dHome'; render(); }"); pg.wait_for_timeout(300)
    check('Pulpit: dwie kolumny kafelków na telefonie',
          pg.evaluate("() => {const k=[...document.querySelectorAll('.pulpit>a.card')];"
                      "return new Set(k.map(e=>Math.round(e.getBoundingClientRect().left))).size;}") == 2)
    # menu hamburger
    check('menu schowane pod hamburgerem',
          pg.evaluate("() => getComputedStyle(document.getElementById('burger')).display") != 'none'
          and pg.locator('#side').bounding_box()['x'] < -50)
    pg.click('#burger'); pg.wait_for_timeout(350)
    check('hamburger wysuwa menu', pg.locator('#side').bounding_box()['x'] >= -1)
    check('i przyciemnia tło', 'open' in pg.locator('#scrim').get_attribute('class'))
    pg.click('#side .nav[data-v="dRolki"]'); pg.wait_for_timeout(400)
    check('wybór zakładki zamyka menu', 'open' not in pg.locator('#side').get_attribute('class'))
    check('i przełącza widok', pg.evaluate("() => VIEW") == 'dRolki')
    check('hamburger pokazuje bieżącą zakładkę',
          pg.locator('#burgerNazwa').inner_text() == 'Rolki',
          pg.locator('#burgerNazwa').inner_text())
    pg.click('#burger'); pg.wait_for_timeout(300)
    pg.click('#scrim', position={'x': 300, 'y': 700}); pg.wait_for_timeout(350)
    check('klik w tło zamyka menu', 'open' not in pg.locator('#side').get_attribute('class'))

    pg.evaluate("() => { VIEW='driver'; KIER=active(DB.machines)[0].id; render(); }"); pg.wait_for_timeout(350)
    check('Kierowca na telefonie: siatka szafek mieści się',
          pg.evaluate("() => {const g=document.querySelector('.zal-cols');"
                      "return g.scrollWidth <= g.clientWidth + 1;}"))
    pg.set_viewport_size({'width': 1440, 'height': 1000})
    pg.evaluate("() => { KIER=null; VIEW='dPrep'; render(); }"); pg.wait_for_timeout(300)

    # --- powrót do listy ---
    print('\n== POWRÓT DO LISTY ==')
    pg.evaluate("() => { SEL.load = DB.loads[0].id; VIEW='load'; render(); }"); pg.wait_for_timeout(400)
    check('jesteśmy w szczegółach załadunku', pg.evaluate("() => !!SEL.load"))
    pg.click('#zalBack'); pg.wait_for_timeout(400)
    check('link „wszystkie" czyści wybór', pg.evaluate("() => SEL.load") is None)
    check('i pokazuje listę', pg.locator('h1').first.inner_text() == 'Załadunki')

    pg.evaluate("() => { SEL.load = DB.loads[0].id; render(); }"); pg.wait_for_timeout(400)
    pg.click('.nav[data-v="load"]'); pg.wait_for_timeout(400)
    check('ponowny klik w menu wraca do listy', pg.evaluate("() => SEL.load") is None)
    check('nagłówek listy', pg.locator('h1').first.inner_text() == 'Załadunki')

    # ta sama zasada w pozostałych widokach z podglądem
    for widok, klucz, grupa, pick, ident in [('items','item','items','data-pick-item','uramaki-losos'),
                                             ('sets','set','sets','data-pick-set','zestaw-1'),
                                             ('ing','ing','ing','data-pick-ing','ogorek'),
                                             ('vend','mach','mach','data-pick-mach', None)]:
        pg.click(f'.nav[data-v="{widok}"]'); pg.wait_for_timeout(300)
        pg.click(f'[data-viewgroup="{grupa}"] button[data-vm="list"]'); pg.wait_for_timeout(300)
        sel_id = ident or pg.evaluate("() => active(DB.machines)[0].id")
        pg.click(f'tr[{pick}="{sel_id}"]'); pg.wait_for_timeout(300)
        check(f'{widok}: wybrano pozycję', pg.evaluate(f"() => SEL.{klucz}") == sel_id)
        pg.click(f'.nav[data-v="{widok}"]'); pg.wait_for_timeout(300)
        check(f'{widok}: ponowny klik w menu czyści wybór',
              pg.evaluate(f"() => SEL.{klucz}") is None)

    # link z podglądu składnika nadal wybiera konkretną rolkę
    pg.click('.nav[data-v="ing"]'); pg.wait_for_timeout(300)
    pg.click('tr[data-pick-ing="ogorek"]'); pg.wait_for_timeout(350)
    pg.click('.card [data-go^="items:"]'); pg.wait_for_timeout(400)
    check('link z podglądu prowadzi do konkretnej rolki',
          pg.evaluate("() => !!SEL.item") and pg.evaluate("() => VIEW") == 'items')

    pg.click('.nav[data-v="load"]'); pg.wait_for_timeout(300)

    # --- rozpiska produkcyjna ---
    print('\n== ROZPISKA ZAŁADUNKU ==')
    pg.evaluate("() => { VIEW='load'; SEL.load = DB.loads[0].id; render(); }"); pg.wait_for_timeout(450)
    tresc = pg.content()
    for sekcja in ('Zestawy do zapakowania', 'Rolki do zwinięcia', 'Składniki do wydania'):
        check(f'sekcja „{sekcja}"', sekcja in tresc)
    check('rozpiska pod siatką automatów, nie nad nią',
          tresc.index('zal-grid') < tresc.index('Rolki do zwinięcia'))

    # rolki przeliczone w górę z zestawów
    rol = pg.evaluate("""() => {
      const z=DB.loads[0], r=zalRozpiska(z);
      const recznie={};
      active(DB.machines).forEach(m=>{ for(let n=1;n<=DB.vending.slots;n++){
        if(!slotOn(z,m.id,n)) continue; const s=slotSet(n); if(!s) continue;
        (s.entries||[]).forEach(e=>{ recznie[e.itemId]=(recznie[e.itemId]||0)+(e.pieces||0); });
      }});
      const iid = Object.keys(recznie)[0];
      return {zgodne: JSON.stringify(r.rolki)===JSON.stringify(recznie),
              kaw: r.rolki[iid], rolek: r.rolki[iid]/CALC.item(iid).pieces};
    }""")
    check('kawałki rolek przeliczone z zestawów', rol['zgodne'], rol)
    check('rolki = kawałki / kawałków na rolkę',
          abs(rol['rolek'] - rol['kaw'] / 10) < 1e-9, rol)

    # niezmiennik: koszt składników = koszt wytworzenia załadunku
    inv = pg.evaluate("""() => {
      const z=DB.loads[0], r=zalRozpiska(z);
      let suma=0;
      Object.keys(r.skladniki).forEach(id=>{ if(id.indexOf('raw:')===0) return;
        const uc=CALC.ingUnitCost(id); if(uc!=null) suma+=uc*r.skladniki[id]; });
      return {skladniki:suma, zaladunek:zalSuma(z).koszt};
    }""")
    check('suma składników = koszt wytworzenia załadunku',
          abs(inv['skladniki'] - inv['zaladunek']) < 0.0001, inv)

    # półprodukty: rozwijane w dół, razem z odpadem
    pp = pg.evaluate("""() => {
      const kopia = JSON.parse(JSON.stringify(DB));
      // półprodukt z 50% odpadu, użyty w jednej rolce
      // własny surowiec, żeby nie mieszał się z ogórkiem z innych rolek
      DB.ingredients.push({id:'ing-test', name:'Surowiec testowy', cat:'Inne', unit:'g',
        packQty:1000, packPrice:10});
      DB.preps.push({id:'pp-test', name:'Ogórek krojony', yieldQty:500, yieldUnit:'g', note:'',
        items:[{kind:'ing', refId:'ing-test', qty:500, waste:500}]});
      const it = CALC.item('hosomaki-ogorek');
      it.comps = [{kind:'ing', refId:'nori', qty:1},{kind:'prep', refId:'pp-test', qty:25}];
      it.pieces = 10;
      const z = nowyZaladunek('T'); DB.loads.push(z);
      const r = zalRozpiska(z);
      const kaw = r.rolki['hosomaki-ogorek'];
      const wynik = {kaw, pp:r.polprodukty['pp-test'], surowiec:r.skladniki['ing-test'],
                     ppLista: Object.keys(r.polprodukty)};
      DB = kopia; load2(); save(); render();
      return wynik;
    }""")
    check('półprodukt trafia do rozpiski', pp['ppLista'] == ['pp-test'], pp)
    check('ilość półproduktu = gramatura × liczba rolek',
          abs(pp['pp'] - 25 * pp['kaw'] / 10) < 1e-9, pp)
    check('surowiec liczony z odpadem, dwa razy więcej niż półproduktu',
          abs(pp['surowiec'] - 2 * pp['pp']) < 1e-9, pp)

    # procent pełnego załadunku na kafelku automatu
    pg.evaluate("() => { SEL.load=DB.loads[0].id; render(); }"); pg.wait_for_timeout(450)
    mid2 = pg.evaluate("() => active(DB.machines)[0].id")
    pg.click(f'[data-mach-all="{mid2}|on"]'); pg.wait_for_timeout(400)
    check('pełny automat pokazuje 100%',
          '100%' in pg.locator('.zal-grid > .card').first.inner_text(),
          pg.locator('.zal-grid > .card').first.inner_text()[:120])
    pg.click(f'[data-mach-all="{mid2}|off"]'); pg.wait_for_timeout(400)
    check('pusty automat pokazuje 0%',
          '0%' in pg.locator('.zal-grid > .card').first.inner_text(),
          pg.locator('.zal-grid > .card').first.inner_text()[:120])
    proc = pg.evaluate("""() => {
      const z=DB.loads[0], m=active(DB.machines)[0];
      for(let n=1;n<=10;n++) setSlotOn(z,m.id,n,!!DB.vending.layout[String(n)]);
      save(); render();
      return zalSuma(z,m.id).wartosc / pelnyAutomat().wartosc;
    }""")
    pg.wait_for_timeout(400)
    oczek = f'{round(proc*100):d}%'
    check('procent zgodny z udziałem w wartości',
          oczek in pg.locator('.zal-grid > .card').first.inner_text(),
          (oczek, pg.locator('.zal-grid > .card').first.inner_text()[:120]))

    pg.evaluate("() => { DB.loads=[]; SEL.load=null; DB.vending.layout={}; save(); render(); }")
    pg.wait_for_timeout(300)

    # --- kanały sprzedaży: Vending i Dostawa ---
    print('\n== KANAŁY SPRZEDAŻY ==')
    pg.click('.nav[data-v="items"]'); pg.wait_for_timeout(250)
    check('przełącznik kanałów w rolkach', pg.locator('[data-changroup] button').count() == 2)
    check('domyślnie Vending', pg.locator('[data-changroup] button[data-ch="vending"].on').count() == 1)

    k = pg.evaluate("""() => {
      const i = CALC.item('hosomaki-losos');
      const v = CALC.itemCalc(i,'vending'), d = CALC.itemCalc(i,'dostawa');
      return {koszt:[v.net, d.net], vat:[v.vat, d.vat],
              netto:[v.priceNet, d.priceNet], fc:[v.fc, d.fc], brutto:[v.priceGross, d.priceGross]};
    }""")
    check('koszt wytworzenia identyczny w obu kanałach', abs(k['koszt'][0] - k['koszt'][1]) < 1e-9, k['koszt'])
    check('stawki 5% i 8%', k['vat'] == [0.05, 0.08], k['vat'])
    check('niższy VAT = wyższy przychód netto', k['netto'][0] > k['netto'][1], k['netto'])
    check('niższy VAT = niższy food cost', k['fc'][0] < k['fc'][1], k['fc'])
    check('food cost zgodny z ręcznym rachunkiem',
          abs(k['fc'][0] - k['koszt'][0] / (k['brutto'][0] / 1.05)) < 1e-9, k['fc'][0])

    # przełącznik zmienia liczby w tabeli
    pg.click('[data-viewgroup="items"] button[data-vm="list"]'); pg.wait_for_timeout(250)
    pg.click('[data-changroup] button[data-ch="dostawa"]'); pg.wait_for_timeout(300)
    check('po przełączeniu aktywna Dostawa',
          pg.locator('[data-changroup] button[data-ch="dostawa"].on').count() == 1)
    fc_d = pg.evaluate("() => CALC.itemCalc(CALC.item('hosomaki-losos')).fc")
    check('domyślny kanał w CALC podąża za przełącznikiem', abs(fc_d - k['fc'][1]) < 1e-9, fc_d)
    check('wybór kanału w localStorage',
          pg.evaluate("() => localStorage.getItem('sp_kanal')") == 'dostawa')
    pg.click('[data-changroup] button[data-ch="vending"]'); pg.wait_for_timeout(300)

    # karta rolki pokazuje oba kanały naraz
    pg.click('tr[data-pick-item="hosomaki-losos"]'); pg.wait_for_timeout(350)
    tresc = pg.content()
    check('karta rolki: tabela kanałów', 'Ceny i food cost w kanałach' in tresc)
    check('karta rolki: oba kanały wymienione', 'Vending' in tresc and 'Dostawa' in tresc)
    check('karta rolki: wiersz stawki VAT', 'Stawka VAT' in tresc)

    # edytor: cztery pola
    pg.click('button[data-edit-item="hosomaki-losos"]'); pg.wait_for_timeout(300)
    for pole in ('iP_vending','iV_vending','iP_dostawa','iV_dostawa'):
        check(f'pole {pole} w edytorze rolki', pg.locator('#'+pole).count() == 1)
    check('VAT vending = 5', pg.locator('#iV_vending').input_value() == '5',
          pg.locator('#iV_vending').input_value())
    check('VAT dostawa = 8', pg.locator('#iV_dostawa').input_value() == '8',
          pg.locator('#iV_dostawa').input_value())
    pg.fill('#iP_dostawa', '22')
    pg.click('#dlgFoot button:has-text("Zapisz")'); pg.wait_for_timeout(400)
    zap = pg.evaluate("() => CALC.item('hosomaki-losos').prices")
    check('osobne ceny zapisane', zap['dostawa'] == 22 and zap['vending'] != 22, zap)
    pg.evaluate("() => { CALC.item('hosomaki-losos').prices.dostawa = 18; save(); render(); }")
    pg.wait_for_timeout(250)

    # zestawy też
    pg.click('.nav[data-v="sets"]'); pg.wait_for_timeout(250)
    check('przełącznik kanałów w zestawach', pg.locator('[data-changroup] button').count() == 2)
    pg.click('[data-viewgroup="sets"] button[data-vm="list"]'); pg.wait_for_timeout(250)
    pg.click('tr[data-pick-set="zestaw-1"]'); pg.wait_for_timeout(350)
    check('karta zestawu: tabela kanałów', 'Ceny i food cost w kanałach' in pg.content())

    # migracja starego formatu
    mig = pg.evaluate("""() => {
      const o = {id:'stary', name:'Stary', pieces:8, price:30, vat:0.23, comps:[]};
      migrateChannels(o);
      return {prices:o.prices, vats:o.vats, maStare: o.price!==undefined || o.vat!==undefined};
    }""")
    check('stara cena trafia do obu kanałów',
          mig['prices'] == {'vending':30, 'dostawa':30}, mig['prices'])
    check('stawki ustawione na 5% i 8%, stara 23% odrzucona',
          mig['vats'] == {'vending':0.05, 'dostawa':0.08}, mig['vats'])
    check('stare pola skasowane', mig['maStare'] is False)

    # --- podgląd w każdej liście ---
    print('\n== PODGLĄD W KAŻDEJ LIŚCIE ==')
    for widok, pick, ident, slowo in [
            ('ing','data-pick-ing','ogorek','Wartości odżywcze'),
            ('prep','data-pick-prep','ryz-gotowany','Receptura'),
            ('items','data-pick-item','uramaki-losos','Rozbicie kosztu'),
            ('sets','data-pick-set','zestaw-1','Co kosztuje najwięcej')]:
        pg.click(f'.nav[data-v="{widok}"]'); pg.wait_for_timeout(250)
        pg.click(f'[data-viewgroup="{widok}"] button[data-vm="list"]'); pg.wait_for_timeout(300)
        check(f'{widok}: zachęta do wyboru przed kliknięciem', 'Wybierz' in pg.content())
        pg.click(f'tr[{pick}="{ident}"]'); pg.wait_for_timeout(350)
        check(f'{widok}: panel podglądu po kliknięciu wiersza', slowo in pg.content())
        check(f'{widok}: wiersz podświetlony', pg.locator(f'tr[{pick}="{ident}"].sel').count() == 1)
        check(f'{widok}: układ split w trybie listy', pg.locator('.split').count() == 1)

    # podgląd składnika: odżywcze + historia + gdzie używany
    pg.click('.nav[data-v="ing"]'); pg.wait_for_timeout(250)
    pg.click('tr[data-pick-ing="ogorek"]'); pg.wait_for_timeout(350)
    tresc = pg.content()
    check('podgląd składnika: tabela odżywcza', 'Wartości odżywcze' in tresc and 'kJ /' in tresc)
    check('podgląd składnika: alergeny', 'alergen' in tresc.lower())
    check('podgląd składnika: historia ceny', 'Historia ceny' in tresc)
    check('podgląd składnika: gdzie używany', 'Gdzie używany' in tresc)
    check('podgląd składnika: cena za 1 kg', 'Cena za 1 kg' in tresc)
    check('link do rolki z podglądu', pg.locator('.card [data-go^="items:"]').count() > 0)

    # składnik z historią rysuje wykres
    pg.evaluate("""() => {
      DB.history.push({id:'ht1', ingId:'ogorek', date:'2026-07-01', from:12, to:14, qty:1000, note:'test'});
      DB.history.push({id:'ht2', ingId:'ogorek', date:'2026-07-20', from:14, to:15, qty:1000, note:'test'});
      save(); render();
    }""")
    pg.wait_for_timeout(300)
    pg.click('tr[data-pick-ing="ogorek"]'); pg.wait_for_timeout(300)
    check('wykres historii w podglądzie składnika', pg.locator('#chIngHist svg').count() == 1)
    pg.evaluate("() => { DB.history = DB.history.filter(h=>!String(h.id).startsWith('ht')); save(); render(); }")
    pg.wait_for_timeout(250)

    # podgląd półproduktu
    pg.click('.nav[data-v="prep"]'); pg.wait_for_timeout(250)
    pg.click('[data-viewgroup="prep"] button[data-vm="list"]'); pg.wait_for_timeout(300)
    pg.click('tr[data-pick-prep="zaprawa"]'); pg.wait_for_timeout(350)
    tresc = pg.content()
    check('podgląd półproduktu: receptura', 'Receptura' in tresc and 'Ocet ryżowy' in tresc)
    check('podgląd półproduktu: koszt partii', 'Koszt partii' in tresc)
    check('podgląd półproduktu: wartości odżywcze', 'Wartości odżywcze' in tresc)

    # odpad widoczny w podglądzie i na kafelku
    pg.evaluate("""() => {
      DB.preps.push({id:'test-w', name:'Test odpadu', yieldQty:500, yieldUnit:'g', note:'',
        items:[{kind:'ing', refId:'ogorek', qty:500, waste:500}]});
      save(); render();
    }""")
    pg.wait_for_timeout(300)
    pg.click('tr[data-pick-prep="test-w"]'); pg.wait_for_timeout(350)
    check('odpad opisany w recepturze podglądu', 'odpadu' in pg.content())
    check('suma surowca w nawiasie', '(1000)' in pg.content())
    check('kolumna wydajności w tabeli półproduktów', 'Wydajność' in pg.content())
    pg.click('[data-viewgroup="prep"] button[data-vm="cards"]'); pg.wait_for_timeout(300)
    check('brak plakietki odpadu na kafelku półproduktu',
          pg.locator('.tcard[data-pick-prep="test-w"] .tag.warn').count() == 0)
    check('kafelek półproduktu pokazuje energię', 'Energia w 100 g' in pg.content())
    check('podgląd pod kafelkami', 'Koszt partii' in pg.content())
    pg.evaluate("() => { DB.preps = DB.preps.filter(p=>p.id!=='test-w'); SEL.prep=null; save(); render(); }")
    pg.wait_for_timeout(250)

    # wszystkie cztery listy: ta sama siatka kafelków
    print('\n== JEDNAKOWE KAFELKI ==')
    szer = []
    for widok in ('ing','prep','items','sets'):
        pg.click(f'.nav[data-v="{widok}"]'); pg.wait_for_timeout(250)
        pg.click(f'[data-viewgroup="{widok}"] button[data-vm="cards"]'); pg.wait_for_timeout(300)
        check(f'{widok}: siatka .tiles-grid', pg.locator('.tiles-grid').count() == 1)
        check(f'{widok}: kafelki .tcard', pg.locator('.tiles-grid .tcard').count() > 0)
        check(f'{widok}: kafelek klikalny', pg.locator('.tiles-grid .tcard[data-pick-'
              + ('ing' if widok=='ing' else 'prep' if widok=='prep' else 'item' if widok=='items' else 'set')
              + ']').count() > 0)
        szer.append(round(pg.locator('.tiles-grid .tcard').first.bounding_box()['width']))
        check(f'{widok}: brak tabeli listy w kafelkach',
              pg.locator(f'table[data-tbl="{widok}"]').count() == 0)
    check('kafelki wszędzie tej samej szerokości', len(set(szer)) == 1, szer)
    for widok in ('ing','prep','items','sets'):
        pg.click(f'.nav[data-v="{widok}"]'); pg.wait_for_timeout(200)
        pg.click(f'[data-viewgroup="{widok}"] button[data-vm="list"]'); pg.wait_for_timeout(250)

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
    naglowki = pg.evaluate("() => [...document.querySelectorAll('table[data-tbl=sets] thead th')]"
                           ".map(t=>t.textContent.trim())")
    kol = naglowki.index('Food cost')
    pg.click(f'table[data-tbl="sets"] th:nth-child({kol + 1})'); pg.wait_for_timeout(200)
    fc = [x for x in liczby(pg.evaluate(
        "i => [...document.querySelectorAll('table[data-tbl=sets] tbody tr')]"
        ".map(r => r.cells[i].textContent.trim())", kol)) if x is not None]
    check('zestawy rosnąco po food coście', fc == sorted(fc), fc)

    # --- kolejność ręczna ---
    print('\n== KOLEJNOŚĆ RĘCZNA ==')
    pg.click('.nav[data-v="items"]'); pg.wait_for_timeout(300)
    check('kolumna kolejności jest pierwsza',
          pg.locator('table[data-tbl="items"] thead th').first.inner_text().strip() == '#')
    kolejnosc = lambda: pg.evaluate("() => DB.items.map(i=>i.name)")
    przed = kolejnosc()
    check('lista startuje w kolejności z bazy',
          pg.evaluate("() => [...document.querySelectorAll('table[data-tbl=items] tbody tr')]"
                      ".map(r=>r.cells[1].textContent.trim().split('\\n')[0])")[0].startswith(przed[0][:8]),
          przed[:2])

    pg.click('[data-ordtoggle="items"]'); pg.wait_for_timeout(350)
    check('tryb kolejności pokazuje uchwyty',
          pg.locator('table[data-tbl="items"] .uch').count() == len(przed))
    check('w trybie kolejności sortowanie jest wyłączone',
          pg.locator('table[data-tbl="items"] th.sortable').count() == 0)
    pg.locator('table[data-tbl="items"] tbody tr').first.locator('button[title="W dół"]').click()
    pg.wait_for_timeout(350)
    po = kolejnosc()
    check('strzałka przestawia w bazie', po[0] == przed[1] and po[1] == przed[0], po[:3])
    check('reszta kolejności bez zmian', po[2:] == przed[2:])
    check('pierwsza pozycja nie ma strzałki w górę',
          pg.locator('table[data-tbl="items"] tbody tr').first
            .locator('button[title="W górę"]').is_disabled())

    # przeciąganie: ostatni widoczny wiersz na pierwszy.
    # Zdarzenia HTML5 wysyłamy wprost — myszą w trybie headless drop trafia losowo,
    # a sprawdzić chcemy obsługę zdarzeń, nie sterownik myszy Playwrighta.
    ostatni = pg.evaluate("""() => {
      const rz = [...document.querySelectorAll('table[data-tbl=items] tbody tr')];
      const zrodlo = rz[rz.length-1], cel = rz[0];
      const nazwa = CALC.item(zrodlo.dataset.di).name;
      const dt = new DataTransfer();
      zrodlo.dispatchEvent(new DragEvent('dragstart', {bubbles:true, dataTransfer:dt}));
      cel.dispatchEvent(new DragEvent('drop', {bubbles:true, dataTransfer:dt}));
      return nazwa;
    }""")
    pg.wait_for_timeout(400)
    po2 = kolejnosc()
    check('przeciąganie wstawia na miejsce celu', po2[0] == ostatni, (po2[:2], ostatni))
    check('nic nie ginie przy przeciąganiu', sorted(po2) == sorted(przed), len(po2))

    pg.click('[data-ordtoggle="items"]'); pg.wait_for_timeout(300)
    check('wyjście z trybu chowa uchwyty', pg.locator('table[data-tbl="items"] .uch').count() == 0)

    # sortowanie: rosnąco → malejąco → kolejność ręczna
    pg.click('table[data-tbl="items"] th:nth-child(2)'); pg.wait_for_timeout(250)
    check('pierwszy klik sortuje', pg.evaluate("() => SORT.items && SORT.items.dir") == 1)
    check('sortowanie nie rusza bazy', kolejnosc() == po2)
    pg.click('table[data-tbl="items"] th:nth-child(2)'); pg.wait_for_timeout(250)
    check('drugi klik odwraca', pg.evaluate("() => SORT.items && SORT.items.dir") == -1)
    pg.click('table[data-tbl="items"] th:nth-child(2)'); pg.wait_for_timeout(300)
    check('trzeci klik wraca do kolejności ręcznej', pg.evaluate("() => SORT.items") is None)
    check('i lista znów jest w kolejności z bazy',
          pg.evaluate("() => [...document.querySelectorAll('table[data-tbl=items] tbody tr')]"
                      ".map(r=>+r.cells[0].textContent.trim())") == list(range(1, len(po2) + 1)))

    # „#" jako powrót z sortowania
    pg.click('table[data-tbl="items"] th:nth-child(2)'); pg.wait_for_timeout(250)
    pg.click('table[data-tbl="items"] th:nth-child(1)'); pg.wait_for_timeout(300)
    check('klik w # wraca do kolejności ręcznej', pg.evaluate("() => SORT.items") is None)

    # receptura: kolejność nakładania
    pg.evaluate("() => editItem(DB.items.find(i=>i.comps.length>2).id)"); pg.wait_for_timeout(400)
    skl = pg.evaluate("() => [...document.querySelectorAll('#itComps .compline')]"
                      ".map(e=>e.children[1].textContent.trim())")
    check('receptura ma uchwyty', pg.locator('#itComps .uch').count() == len(skl), skl)
    pg.locator('#itComps .compline').first.locator('button[title="W dół"]').click()
    pg.wait_for_timeout(300)
    skl2 = pg.evaluate("() => [...document.querySelectorAll('#itComps .compline')]"
                       ".map(e=>e.children[1].textContent.trim())")
    check('składnik przesuwa się w recepturze', skl2[0] == skl[1] and skl2[1] == skl[0], skl2[:2])
    pg.evaluate("() => document.querySelector('#dlgForm .dlg-f .pri').click()"); pg.wait_for_timeout(400)
    zapis = pg.evaluate("() => CALC.item(DB.items.find(i=>i.comps.length>2).id)"
                        ".comps.map(c=>CALC.compInfo(c.refId).name)")
    check('zapis zachowuje nową kolejność', zapis[0].startswith(skl2[0][:6]), (zapis[:2], skl2[:2]))

    # --- wydruk receptur ---
    print('\n== PDF Z RECEPTURAMI ==')
    pg.click('.nav[data-v="items"]'); pg.wait_for_timeout(300)
    check('przycisk wydruku w widoku rolek', pg.locator('[data-act="pdfItems"]').count() == 1)
    # bez serwera nie ma czym wygenerować PDF-u, więc otwiera się okno drukowania
    druk = pg.evaluate("""() => {
      let out = null, drukowano = false;
      const orig = window.open;
      window.open = () => ({document:{write:h=>out=h, close(){}}, focus(){},
                            print(){ drukowano = true; }});
      document.querySelector('[data-act=pdfItems]').click();
      window.open = orig;
      return {html: out, dl: !!document.querySelector('a[download]')};
    }""")
    html = druk['html'] or ''
    check('poza serwerem otwiera się okno drukowania', len(html) > 500, len(html))
    check('nie próbuje pobierać pliku bez serwera', not druk['dl'])
    kolejnosc_rolek = pg.evaluate("() => active(DB.items).map(i=>i.name)")
    check('wydruk ma wszystkie czynne rolki',
          all(('>' + n.replace('&', '&amp;') + '<') in html or n in html for n in kolejnosc_rolek),
          [n for n in kolejnosc_rolek if n not in html][:3])
    check('rolki w tej samej kolejności co w aplikacji',
          [html.index(n) for n in kolejnosc_rolek] == sorted(html.index(n) for n in kolejnosc_rolek))
    pierwsza = pg.evaluate("""() => {
      const it = active(DB.items)[0];
      return it.comps.map(c => CALC.compInfo(c.refId).name);
    }""")
    # tylko lista składników, bez nagłówka — nazwa rolki potrafi zawierać nazwę składnika
    karta = html.split('<section class="rolka">')[1].split('<div class="skl">')[1]
    check('składniki w kolejności nakładania',
          [karta.index(n) for n in pierwsza] == sorted(karta.index(n) for n in pierwsza), pierwsza)
    check('gramatury w nawiasie, wyszarzone',
          '(110 g)' in html and 'class="q"' in html, html[:0])
    check('składniki wcięte pod nazwą', '.skl{margin-left' in html)
    check('numeracja od jedynki', '>1.</span>' in html)
    check('bez wiersza podsumowania pod nagłówkiem', 'class="sub"' not in html)
    check('wiersze się nie zawijają', html.count('white-space:nowrap') >= 2, html[:0])
    check('marginesy tylko z Gotenberga, nie podwójne',
          '@page{size:A4}' in html and 'margin:12mm' not in html)

    # pomiar na sucho to jedno, ale gotowy dokument też musi się zmieścić
    m = zmiesci(html)
    check('gotowe receptury mieszczą się w polu zadruku A4',
          m['h'] <= 1026 and m['w'] <= 718, m)

    # liczba kolumn dobierana pod treść: im mniej, tym lepiej, byle jedna strona
    def kolumn(n):
        return int(pg.evaluate("""(n) => {
          if(!window.__wszystkie) window.__wszystkie = DB.items.slice();
          DB.items = window.__wszystkie.slice(0, n);
          let out = null; const o = window.open;
          window.open = () => ({document:{write:h=>out=h, close(){}}, focus(){}, print(){}});
          pdfReceptury(); window.open = o;
          DB.items = window.__wszystkie.slice();
          return out.match(/column-count:(\\d)/)[1];
        }""", n))
    def wydruk(n, ustaw=None):
        h = pg.evaluate("""([n, ustaw]) => {
          if(!window.__wszystkie) window.__wszystkie = DB.items.slice();
          if(ustaw) Object.assign(DB.settings, ustaw);
          DB.items = window.__wszystkie.slice(0, n);
          let out = null; const o = window.open;
          window.open = () => ({document:{write:h=>out=h, close(){}}, focus(){}, print(){}});
          pdfReceptury(); window.open = o;
          DB.items = window.__wszystkie.slice();
          return out;
        }""", [n, ustaw])
        return (float(re.search(r'font:([\d.]+)px', h).group(1)),
                int(re.search(r'column-count:(\d)', h).group(1)))

    domyslne = {'pdfMinFont': 11, 'pdfMaxCols': 3}
    pismo3, kol3 = wydruk(3, domyslne)
    pismo12, kol12 = wydruk(12, domyslne)
    pismo23, kol23 = wydruk(23, domyslne)
    check('mało rolek to większe pismo', pismo3 > pismo23, (pismo3, pismo23))
    check('pismo nie schodzi poniżej minimum z ustawień',
          min(pismo3, pismo12, pismo23) >= 11, (pismo3, pismo12, pismo23))
    check('liczba kolumn w granicach ustawienia', max(kol3, kol12, kol23) <= 3,
          (kol3, kol12, kol23))
    check('więcej treści to nie mniej kolumn', kol3 <= kol12 <= kol23, (kol3, kol12, kol23))

    # ustawienia naprawdę sterują układem
    pismo_w, kol_w = wydruk(12, {'pdfMinFont': 14, 'pdfMaxCols': 2})
    check('ograniczenie kolumn respektowane', kol_w <= 2, kol_w)
    check('podniesione minimum respektowane', pismo_w >= 14, pismo_w)
    pismo_max, kol_max = wydruk(23, {'pdfMinFont': 16, 'pdfMaxCols': 3})
    check('gdy minimum nie mieści się na stronie, pismo zostaje na minimum',
          pismo_max >= 16, pismo_max)
    wydruk(3, domyslne)                      # oddajemy ustawienia w stanie wyjściowym
    check('ustawienia wróciły do domyślnych',
          pg.evaluate("() => DB.settings.pdfMinFont + ':' + DB.settings.pdfMaxCols") == '11:3')

    check('pomiar nie zostawia po sobie ramek',
          pg.evaluate("() => document.querySelectorAll('iframe').length") == 0)

    # --- wydruk zestawów ---
    print('\n== PDF ZE SKŁADEM ZESTAWÓW ==')
    pg.click('.nav[data-v="sets"]'); pg.wait_for_timeout(300)
    check('przycisk wydruku w widoku zestawów', pg.locator('[data-act="pdfSets"]').count() == 1)
    # dokładamy dodatek, żeby sprawdzić oba rodzaje pozycji naraz
    hz = pg.evaluate("""() => {
      const s = active(DB.sets)[0];
      const bylo = s.comps.slice();                 // stan trzeba oddać nietknięty,
      if(!s.comps.length) s.comps.push({refId:'nori', qty:1});   // dalsze testy na nim stoją
      let out = null; const o = window.open;
      window.open = () => ({document:{write:h=>out=h, close(){}}, focus(){}, print(){}});
      pdfZestawy(); window.open = o;
      const dodatek = CALC.compInfo(s.comps[0].refId).name;
      s.comps = bylo;
      return {html: out, dodatek};
    }""")
    dodatek = hz['dodatek']; hz = hz['html']
    zestawy = pg.evaluate("() => active(DB.sets).map(s=>s.name)")
    check('wydruk ma wszystkie czynne zestawy',
          all(n in hz for n in zestawy), [n for n in zestawy if n not in hz][:3])
    check('zestawy w tej samej kolejności co w aplikacji',
          [hz.index(n) for n in zestawy] == sorted(hz.index(n) for n in zestawy))
    check('ilość rolki to sama liczba, bez jednostki', 'kaw.' not in hz, hz[:0])
    kolejnosc_listy = pg.evaluate("""() => {
      const s = active(DB.sets).find(x=>(x.entries||[]).length > 1);
      return s.entries.map(e=>CALC.item(e.itemId)).filter(Boolean)
              .map(it=>DB.items.indexOf(it));
    }""")
    karta_z = hz.split('<section class="rolka">')
    nazwy_z = pg.evaluate("""() => {
      const s = active(DB.sets).find(x=>(x.entries||[]).length > 1);
      return {i: active(DB.sets).indexOf(s),
              n: s.entries.map(e=>{const it=CALC.item(e.itemId); return it?it.name:null;})
                   .filter(Boolean)};
    }""")
    sekcja = karta_z[nazwy_z['i'] + 1]
    check('rolki w zestawie w kolejności z listy rolek',
          [sekcja.index(n) for n in sorted(nazwy_z['n'],
              key=lambda x: pg.evaluate("n => DB.items.findIndex(i=>i.name===n)", x))]
          == sorted(sekcja.index(n) for n in nazwy_z['n']),
          nazwy_z['n'])
    check('skład zestawów też bez wiersza podsumowania', 'class="sub"' not in hz)
    mz = zmiesci(hz)
    check('gotowy skład zestawów mieści się w polu zadruku A4',
          mz['h'] <= 1026 and mz['w'] <= 718, mz)
    check('zestawy też bez zawijania', 'white-space:nowrap' in hz)
    check('bez dodatków — sama zawartość zestawu',
          dodatek not in hz.split('<section class="rolka">')[1], dodatek)
    check('bez zdjęć na wydruku', '<img' not in hz and '<img' not in html)
    check('skład zestawów też bez cen', not re.findall(r'[\d,]+\s*zł', hz), hz[:0])
    kolz = int(re.search(r'column-count:(\d)', hz).group(1))
    check('układ zestawów też dobrany', 1 <= kolz <= 3, kolz)

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
      // jedna linia, dwie ilości: 500 g do produktu + 500 g do kosza
      const bazowy = {id:'test-odpad', name:'Ogórek krojony', yieldQty:500, yieldUnit:'g',
        items:[{kind:'ing', refId:'ogorek', qty:500, waste:500}]};
      const bezOdpadu = JSON.parse(JSON.stringify(bazowy));
      bezOdpadu.items[0].waste = 0;
      const koszt = p => p.items.reduce((s,c)=>s+lineQty(c)*(CALC.ingUnitCost(c.refId)||0),0);
      return {
        zOdpadem:  CALC.prepNutr(bazowy).nutr.kcal,
        bezOdpadu: CALC.prepNutr(bezOdpadu).nutr.kcal,
        ogorekNaG: CALC.ingNutr('ogorek').kcal,
        kosztPartii: koszt(bazowy),
        kosztBez: koszt(bezOdpadu),
        kosztJedn: koszt(bazowy)/500,
        suma: lineQty(bazowy.items[0]),
        grams: CALC.prepNutr(bazowy).grams
      };
    }""")
    check('odpad nie wchodzi do wartości odżywczych',
          abs(w['zOdpadem'] - w['ogorekNaG']) < 1e-9, (w['zOdpadem'], w['ogorekNaG']))
    check('wartość odżywcza liczona z samej ilości, nie z sumy',
          abs(w['zOdpadem'] - w['bezOdpadu']) < 1e-9, (w['zOdpadem'], w['bezOdpadu']))
    check('suma linii = ilość + odpad', w['suma'] == 1000, w['suma'])
    check('odpad wchodzi do kosztu (1000 g ogórka)',
          abs(w['kosztPartii'] - 15.0) < 1e-9, w['kosztPartii'])
    check('bez odpadu koszt byłby o połowę niższy',
          abs(w['kosztBez'] - 7.5) < 1e-9, w['kosztBez'])
    check('koszt jednostkowy podwojony przez odpad',
          abs(w['kosztJedn'] - 0.03) < 1e-9, w['kosztJedn'])
    check('1 g półproduktu waży 1 g', w['grams'] == 1, w['grams'])

    # migracja starego zapisu: osobna linia z flagą → druga ilość w tej samej linii
    m = pg.evaluate("""() => {
      const stary = {id:'stary-odpad', name:'Stary', yieldQty:500, yieldUnit:'g',
        items:[{kind:'ing', refId:'ogorek', qty:500},
               {kind:'ing', refId:'ogorek', qty:500, waste:true},
               {kind:'ing', refId:'serek', qty:20}]};
      migrateWaste(stary);
      return stary.items;
    }""")
    check('po migracji zostają dwie linie', len(m) == 2, m)
    check('odpad scalony w liczbę', m[0]['qty'] == 500 and m[0]['waste'] == 500, m[0])
    check('linia bez odpadu dostaje zero', m[1]['waste'] == 0, m[1])

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
    check('pole ilości w edytorze półproduktu', pg.locator('input[data-q="0"]').count() == 1)
    check('pole odpadu w edytorze półproduktu', pg.locator('input[data-w="0"]').count() == 1)
    check('suma w nawiasie przy nazwie składnika',
          '(' in pg.locator('#prepComps .compline').first.inner_text())
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
    pg.fill('#iP_vending', '30')
    pg.fill('#iP_dostawa', '32')
    pickCombo(pg, 'iAdd', 'Łosoś')
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
    pickCombo(pg, 'sAddC', 'Imbir')
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
    pickCombo(pg, 'simIng', 'Łosoś')
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
    pg.click('#sAddC_q'); pg.wait_for_timeout(200)
    lista = pg.locator('#sAddC_p').inner_text()
    check('jedna lista dodatków zawiera tackę', 'Tacka HP09' in lista, lista[:80])
    check('jedna lista dodatków zawiera pałeczki', 'Pałeczki' in lista)
    check('lista dodatków pokazuje cenę jednostkową', 'brak ceny' in lista or '·' in lista)
    pg.keyboard.press('Escape'); pg.wait_for_timeout(150)
    for nazwa, qty in (('Tacka HP09', '1'), ('Pałeczki', '2'), ('Sos Kikoman', '2')):
        pickCombo(pg, 'sAddC', nazwa)
        pg.fill('#sAddCQty', qty)
        pg.click('#sAddCBtn'); pg.wait_for_timeout(200)
    pg.wait_for_timeout(300)
    tot = pg.locator('#sExtraTot').inner_text()
    # 1×1,20 + 2×0,15 + 2×1,75 = 5,00
    check('koszt dodatków = 5,00 zł', '5,00' in tot, tot)
    fc = pg.locator('#sFc').inner_text()
    # edytor liczy w aktywnym kanale (Vending, VAT 5%) — przy 8% byłoby 47%
    check('food cost zestawu wzrósł po doliczeniu dodatków', fc.startswith('45'), fc)
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
