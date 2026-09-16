
/* ============================================================================
   WIDOK: PULPIT
   ========================================================================== */
function vDash(){
  const prob = problems();
  const fcs = active(DB.items).filter(i=>CALC.priceOf(i))
    .map(i=>CALC.itemCalc(i)).filter(c=>c.fc!=null);
  // Automat sprzedaje zestawy, nie pojedyncze rolki, więc kafelek pokazuje food cost
  // zestawów — ważony, czyli suma kosztów ÷ suma przychodu netto. Rolki idą pod spodem
  // drobnym drukiem: ich ceny à la carte to punkt odniesienia, a nie realna sprzedaż.
  const wZest = fcWazony(active(DB.sets).map(s=>CALC.setCalc(s)));
  const wRol  = fcWazony(fcs);
  const avg = wZest.fc;
  const pominiete = wZest.pominiete + wRol.pominiete;
  const over = fcs.filter(c=>c.fc>DB.settings.alertFc).length;
  const noPrice = active(DB.ingredients).filter(g=>g.packPrice==null||!g.packQty).length;

  const setRows = active(DB.sets).map(s=>{ const c=CALC.setCalc(s);
    return {label:s.name, v:c.fc||0, st:CALC.status(c.fc), c, go:{v:'sets',id:s.id}}; })
    .filter(r=>r.v>0).sort((a,b)=>b.v-a.v);

  const itemRows = active(DB.items).map(i=>{ const c=CALC.itemCalc(i);
    return {label:itNameK(i), v:c.fc||0, st:CALC.status(c.fc), c, go:{v:'items',id:i.id}}; })
    .filter(r=>r.v>0).sort((a,b)=>b.v-a.v).slice(0,12);

  after('dash',()=>{
    const a=document.getElementById('chSets'); if(a) wireChart(a,setRows,r=>
      `<b>${esc(r.label)}</b>food cost ${pct(r.v)} · koszt ${zl(r.c.net)} · cena ${zl(r.c.priceGross)}<br><span class="mut">marża ${zl(r.c.margin)} netto · ${r.c.pieces} kawałków</span>`);
    const b=document.getElementById('chItems'); if(b) wireChart(b,itemRows,r=>
      `<b>${esc(r.label)}</b>food cost ${pct(r.v)} · koszt ${zl(r.c.net)} · cena ${zl(r.c.priceGross)}`);
  });

  const alertsHtml = prob.length
    ? prob.slice(0,14).map(p=>`<div class="alert ${p.sev}" ${p.go?`data-go="${p.go.v}:${p.go.id||''}" style="cursor:pointer"`:''}>
        <div class="ic">${p.sev==='crit'?'!':p.sev==='warn'?'?':'i'}</div>
        <div class="txt"><b>${esc(p.title)}</b><br>${esc(p.msg)}</div></div>`).join('')
      + (prob.length>14?`<div class="small mut" style="padding:4px 2px">…i jeszcze ${prob.length-14}</div>`:'')
    : '<div class="empty">Brak problemów. Wszystkie pozycje mieszczą się w progach.</div>';

  return `
  <div class="topbar"><h1>Foodcost</h1><span class="sub">stan na ${todayISO()}</span><div class="spacer"></div>
    <button class="btn sm" data-act="addItem">+ Rolka</button>
    <button class="btn sm pri" data-act="addSet">+ Zestaw</button></div>

  ${STORAGE_OK?'':'<div class="banner">Przeglądarka blokuje zapis lokalny w tym trybie. Zmiany są tylko w pamięci karty — <b>eksportuj plik JSON</b> w Ustawieniach albo podłącz Supabase, żeby ich nie stracić.</div>'}

  <div class="tiles">
    <div class="tile"><div class="lab">Rolek w menu</div><div class="val num">${active(DB.items).length}</div>
      <div class="note">${active(DB.sets).length} zestawów · ${active(DB.ingredients).length} składników</div></div>
    <div class="tile"><div class="lab">Food cost zestawów</div>
      <div class="val num" style="color:${avg==null?'var(--muted)':avg>DB.settings.alertFc?'var(--crit-ink)':avg>DB.settings.targetFc?'var(--warn-ink)':'var(--good-ink)'}">${pct(avg)}</div>
      <div class="note">ważony · cel ${pct(DB.settings.targetFc,0)} · alert ${pct(DB.settings.alertFc,0)}<br>
        rolki ${pct(wRol.fc)} po cenach à la carte${pominiete
          ? ` · <b style="color:var(--crit-ink)">${pominiete} poza średnią</b> (niekompletna receptura)` : ''}</div></div>
    <div class="tile"><div class="lab">Powyżej progu</div><div class="val num" style="color:${over?'var(--crit-ink)':'var(--good-ink)'}">${over}</div>
      <div class="note">pozycji z food cost > ${pct(DB.settings.alertFc,0)}</div></div>
    <div class="tile"><div class="lab">Braki w danych</div><div class="val num" style="color:${noPrice?'var(--warn-ink)':'var(--good-ink)'}">${noPrice}</div>
      <div class="note">składników bez ceny zakupu</div></div>
  </div>

  <div class="split" style="margin-top:12px">
    <div class="grid">
      <div class="card"><h2>Food cost zestawów</h2>
        <div class="hint">Kliknij słupek, żeby otworzyć zestaw. Przerywana linia to cel ${pct(DB.settings.targetFc,0)}.</div>
        <div id="chSets">${setRows.length?barChartFc(setRows):'<div class="empty">Brak zestawów z ceną.</div>'}</div>
        <div class="legend"><span><i style="background:var(--good)"></i>w celu</span><span><i style="background:var(--warn)"></i>powyżej celu</span><span><i style="background:var(--crit)"></i>powyżej alertu</span></div>
      </div>
      <div class="card"><h2>Rolki o najwyższym food cost</h2>
        <div class="hint">12 rolek z najgorszym stosunkiem kosztu do ceny.</div>
        <div id="chItems">${itemRows.length?barChartFc(itemRows):'<div class="empty">Brak pozycji z ceną.</div>'}</div>
      </div>
    </div>
    <div class="card"><h2>Do sprawdzenia</h2><div class="hint">${prob.length} pozycji wymaga uwagi</div>${alertsHtml}</div>
  </div>`;
}

/* ============================================================================
   WSPÓLNY UKŁAD LIST
   Cztery listy — składniki, półprodukty, rolki, zestawy — wyglądają i zachowują
   się tak samo: przełącznik widoku, filtr archiwum, ta sama siatka kafelków
   i ten sam panel podglądu po prawej (albo pod spodem w trybie kafelków).
   ========================================================================== */
/** przycisk trybu ustawiania kolejności + podpowiedź, gdy jest włączony */
function ordBtn(key){
  return `<button class="btn sm ${ORD[key]?'pri':''}" data-ordtoggle="${key}"
    title="Przeciąganie wierszy — kolejność zapisuje się od razu">⇅ Kolejność</button>`;
}
function ordHint(key, co){
  return ORD[key] ? `<div class="banner">Ustawiasz <b>kolejność ${co}</b> — przeciągnij wiersz
    za uchwyt ⠿ albo użyj strzałek. Zapisuje się od razu, sortowanie jest na ten czas wyłączone.</div>` : '';
}
/** Pasek listy — ten sam we wszystkich sześciu widokach z listą.

    Dwa rzędy, bo to dwie różne rzeczy: górny robi coś nowego (dodaj, wydrukuj),
    dolny zmienia sposób patrzenia na to, co już jest (szukaj, filtruj, przełącz).
    Wcześniej wszystko stało w jednym rzędzie i przy dziewięciu elementach akcja główna
    zawijała się pod tytuł — czyli najważniejszy przycisk lądował tam, gdzie nikt go
    nie szuka. */
function paskListy(o){
  const opcje = [
    o.szukaj ? `<input id="${o.szukaj.id}" type="search" placeholder="${esc(o.szukaj.ph)}"
      value="${esc(o.szukaj.val || '')}" style="max-width:${o.szukaj.szer || '240px'}">` : '',
    o.pola || '',
    o.kanal ? chanPills() : '',
    viewPills(o.klucz),
    archPills(o.klucz),
    o.kolejnosc ? ordBtn(o.klucz) : '',
    o.info ? `<div class="spacer"></div><span class="mut small">${o.info}</span>` : '',
  ].filter(Boolean).join('');

  return `<div class="topbar">
    <h1>${esc(o.tytul)}</h1>${o.licznik ? `<span class="sub">${esc(o.licznik)}</span>` : ''}
    <div class="spacer"></div>${o.akcje || ''}
    ${o.dodaj ? `<button class="btn pri" data-act="${o.dodaj.act}">${esc(o.dodaj.lab)}</button>` : ''}
  </div>
  <div class="paskopcji">${opcje}</div>`;
}

function listLayout(key, tabela, kafelki, podglad){
  return VMODE[key]==='cards'
    ? `<div class="tiles-grid" style="margin-bottom:12px">${kafelki}</div>${podglad}`
    : `<div class="split">${tabela}${podglad}</div>`;
}

/** porównanie obu kanałów sprzedaży dla rolki albo zestawu */
function chanTable(o, calc){
  const w = CHANNELS.map(ch=>({ch, c:calc(o, ch.k)}));
  return `<div class="tw"><table><thead><tr><th>Kanał</th>
      ${w.map(x=>`<th class="r">${esc(x.ch.l)}${CHAN===x.ch.k?' •':''}</th>`).join('')}</tr></thead><tbody>
    <tr><td>Stawka VAT</td>${w.map(x=>`<td class="r num">${pct(x.c.vat,0)}</td>`).join('')}</tr>
    <tr><td>Cena brutto</td>${w.map(x=>`<td class="r num">${x.c.priceGross?zl(x.c.priceGross):'—'}</td>`).join('')}</tr>
    <tr><td>Cena netto</td>${w.map(x=>`<td class="r num">${x.c.priceGross?zl(x.c.priceNet):'—'}</td>`).join('')}</tr>
    <tr><td>Food cost</td>${w.map(x=>`<td class="r num"><span class="tag ${CALC.status(x.c.fc)==='none'?'':CALC.status(x.c.fc)}">${pct(x.c.fc)}</span></td>`).join('')}</tr>
    <tr><td>Marża netto</td>${w.map(x=>`<td class="r num">${x.c.margin!=null?zl(x.c.margin):'—'}</td>`).join('')}</tr>
    <tr><td>Sugestia przy ${pct(DB.settings.targetFc,0)}</td>${w.map(x=>`<td class="r num wylicz">${x.c.suggested?zl(x.c.suggested):'—'}</td>`).join('')}</tr>
    </tbody></table></div>
    <div class="hint">Koszt wytworzenia jest ten sam w obu kanałach — różni je stawka VAT i cena, więc i food cost.</div>`;
}

/** tabela odżywcza w jednej kolumnie — dla składnika i półproduktu */
function nutr100(n, naglowek){
  if(!hasNutr(n)) return '<div class="empty">Brak tabeli odżywczej.</div>';
  const kom=x=> x.k==='kcal'
    ? `${num((n.kcal||0)*4.184,0)} kJ / ${num(n.kcal||0,0)} kcal`
    : `${num(n[x.k]||0,(n[x.k]||0)<1?2:1)} ${x.u}`;
  return `<div class="tw"><table><thead><tr><th>Wartość odżywcza</th>
      <th class="r">${esc(naglowek||'w 100 g')}</th></tr></thead><tbody>
    ${NUTR.map(x=>`<tr><td>${x.sub?`<span class="mut">${esc(x.l)}</span>`:esc(x.l)}</td>
      <td class="r num">${kom(x)}</td></tr>`).join('')}
    </tbody></table></div>`;
}

function alergBlock(lista){
  return (lista && lista.length)
    ? `<div class="kv" style="margin-top:8px"><span>Alergeny</span><b>${lista.map(a=>esc(ALERG_NAME[a]||a)).join(', ')}</b></div>`
    : '<div class="hint" style="margin-top:8px">Brak zadeklarowanych alergenów.</div>';
}

/** punkty do wykresu historii ceny jednostkowej danego składnika */
function histPts(ingId){
  const hs = DB.history.filter(h=>h.ingId===ingId).sort((a,b)=>a.date.localeCompare(b.date));
  if(!hs.length) return [];
  const pts = hs.map(h=>({d:h.date, v:(h.to!=null&&h.qty)?h.to/h.qty:0, raw:h}));
  const p0 = hs[0];
  pts.unshift({d:p0.date, v:(p0.from!=null&&p0.qty)?p0.from/p0.qty:0, raw:p0});
  return pts;
}

/** panel „gdzie to jest używane" */
function usedByBlock(id){
  const u = CALC.usedBy(id);
  if(!u.length) return '<div class="hint">Nieużywany w żadnej recepturze.</div>';
  return u.map(x=>`<div class="kv"><span>${x.type==='item'?'rolka':x.type==='prep'?'półprodukt':'zestaw'}</span>
    <a href="#" data-go="${x.type==='item'?'items':x.type==='prep'?'prep':'sets'}:${x.id}">${esc(x.name)}</a></div>`).join('');
}

/* ============================================================================
   WIDOK: SKŁADNIKI
   ========================================================================== */
let ingFilter={q:'',cat:''};
function vIng(){
  const cats=[...new Set(DB.ingredients.map(g=>g.cat))].sort((a,b)=>a.localeCompare(b,'pl'));
  const list=archFilter(DB.ingredients,'ing').filter(g=>
    (!ingFilter.cat||g.cat===ingFilter.cat) &&
    (!ingFilter.q||g.name.toLowerCase().includes(ingFilter.q.toLowerCase())));
  const sel = SEL.ing ? CALC.ing(SEL.ing) : null;

  after('ing',()=>{
    const q=document.getElementById('ingQ');
    q.addEventListener('input',()=>{ingFilter.q=q.value; const s=q.selectionStart; render(); const n=document.getElementById('ingQ'); n.focus(); n.setSelectionRange(s,s);});
    fillCombo('ingCat',
      [{v:'', l:'Wszystkie kategorie', pin:true}, ...cats.map(c=>({v:c, l:c}))],
      ingFilter.cat, v=>{ ingFilter.cat=v; render(); });
    document.querySelectorAll('[data-pick-ing]').forEach(r=>r.addEventListener('click',e=>{
      if(e.target.closest('button')||e.target.closest('a'))return; SEL.ing=r.dataset.pickIng; render(); }));
    document.querySelectorAll('[data-edit-ing]').forEach(b=>b.addEventListener('click',()=>editIng(b.dataset.editIng)));
    document.querySelector('[data-act="addIng"]').addEventListener('click',()=>editIng(null));
    if(sel){ const el=document.getElementById('chIngHist');
      if(el) wireChart(el, histPts(sel.id), pt=>`<b>${esc(pt.d)}</b>${num(pt.v,4)} ${DB.settings.currency}/${esc(sel.unit)}`); }
  });

  const rows=list.map(g=>{
    const uc=CALC.ingUnitCost(g.id), used=CALC.usedBy(g.id).length;
    return `<tr data-pick-ing="${g.id}" style="cursor:pointer" class="${SEL.ing===g.id?'sel':''} ${g.archived?'arch':''}">
      <td><b>${esc(g.name)}</b>${g.archived?' <span class="tag">archiwum</span>':''}</td>
      <td><span class="tag">${esc(g.cat)}</span></td>
      <td class="r num">${g.packQty!=null?num(g.packQty,g.packQty%1?2:0):'—'}</td>
      <td>${esc(g.unit)}</td>
      <td class="r num">${g.packPrice!=null?zl(g.packPrice):'<span class="tag crit">brak</span>'}</td>
      <td class="r num">${uc!=null?num(uc,4):'—'}</td>
      <td class="r num mut">${used||'—'}</td>
      </tr>`;
  }).join('');

  const cards=list.map(g=>{
    const uc=CALC.ingUnitCost(g.id), used=CALC.usedBy(g.id).length;
    return `<div class="card tcard ${SEL.ing===g.id?'sel':''} ${g.archived?'arch':''}" data-pick-ing="${g.id}">
      <div class="th"><h3>${esc(g.name)}${g.archived?' <span class="tag">archiwum</span>':''}</h3>
        <span class="tag">${esc(g.cat)}</span></div>
      <div class="hint" style="margin:0 0 8px">${g.packQty!=null?num(g.packQty,g.packQty%1?2:0)+' '+esc(g.unit)+' w opakowaniu':'brak opakowania'}</div>
      <div class="kv"><span>Cena opakowania</span><b>${g.packPrice!=null?zl(g.packPrice):'<span class="tag crit">brak</span>'}</b></div>
      <div class="kv"><span>Cena za ${esc(g.unit)}</span><b class="wylicz">${uc!=null?num(uc,4):'—'}</b></div>
      <div class="kv"><span>Energia w 100 g</span><b class="${hasNutr(g.nutr)?'':'mut'}">${hasNutr(g.nutr)?num(g.nutr.kcal,0)+' kcal':'—'}</b></div>
      <div class="kv"><span>Użyć w recepturach</span><b class="${used?'':'mut'}">${used||'—'}</b></div>
      <div class="acts">${rowActions('ing', g)}</div></div>`;
  }).join('');

  let detail='<div class="card"><div class="empty">Wybierz składnik, żeby zobaczyć jego cenę, wartości odżywcze i historię.</div></div>';
  if(sel){
    const uc = CALC.ingUnitCost(sel.id);
    const pts = histPts(sel.id);
    const zmiany = DB.history.filter(h=>h.ingId===sel.id).sort((a,b)=>b.date.localeCompare(a.date));
    const gr = unitGrams(sel.unit, sel.gPerUnit);
    const kv = (l, v, klasa) => `<div class="kv"><span>${l}</span><b${
      klasa?` class="${klasa}"`:''}>${v}</b></div>`;
    detail = podgladKarta({
      typ:'ing', id:sel.id, nazwa:sel.name,
      podtytul: `${esc(sel.cat)} · rozliczany w ${esc(sel.unit)}${sel.archived?' · w archiwum':''}`,
      kafelki:[{lab:`Cena za ${sel.unit}`, val: uc!=null?num(uc,4):'—', kolor:'var(--marka)'},
               {lab:'Użyć w recepturach', val: CALC.usedBy(sel.id).length}],
      sekcje:[
        {t:'Koszt i cena', html:`
          <div class="kv" style="border-top:1px solid var(--axis);padding-top:9px">
            <span><b>Cena opakowania (netto)</b></span>
            <b>${sel.packPrice!=null?zl(sel.packPrice):'<span class="tag crit">brak</span>'}</b></div>
          ${kv('Opakowanie', sel.packQty!=null
              ? num(sel.packQty, sel.packQty%1?2:0)+' '+esc(sel.unit) : '—')}
          ${kv(`Cena za 1 ${esc(sel.unit)}`, uc!=null?num(uc,4)+' '+DB.settings.currency:'—')}
          ${kv(`Waga 1 ${esc(sel.unit)}`, gr==null?'nie podano':num(gr,gr%1?2:0)+' g',
               gr==null?'mut':'')}
          ${gr ? kv('Cena za 1 kg', uc!=null?zl(uc*1000/gr):'—') : ''}`},
        {t:'Wartości odżywcze', html: nutr100(sel.nutr) + alergBlock(sel.alerg)},
        {t:'Historia ceny', html: (pts.length>1
            ? `<div id="chIngHist">${lineChart(pts, 320, 150)}</div>`
            : '<div class="hint">Brak zapisanych zmian ceny. Pierwszy wpis pojawi się, gdy zmienisz cenę opakowania.</div>')
          + zmiany.slice(0,6).map(h=>{
              const od=(h.from!=null&&h.qty)?h.from/h.qty:null, doo=(h.to!=null&&h.qty)?h.to/h.qty:null;
              const d=(od&&doo)?doo/od-1:null;
              return `<div class="kv"><span>${esc(h.date)} <span class="mut small">${esc(h.note||'')}</span></span>
                <b>${zl(h.from)} → ${zl(h.to)} ${d==null?'':`<span class="tag ${
                  d>0.02?'crit':d<-0.02?'good':''}">${(d>0?'+':'')+pct(d,1)}</span>`}</b></div>`;
            }).join('')},
        {t:'Gdzie używany', html: usedByBlock(sel.id)},
      ],
    });
  }

  return `
  ${paskListy({tytul:'Składniki', licznik:`${active(DB.ingredients).length} aktywnych`,
    klucz:'ing', dodaj:{act:'addIng', lab:'+ Składnik'},
    szukaj:{id:'ingQ', ph:'Szukaj składnika…', val:ingFilter.q, szer:'280px'},
    pola:combo('ingCat','Kategoria…','max-width:200px'),
    info:`${list.length} wyników`})}
  ${listLayout('ing',
    `<div class="tw"><table data-tbl="ing"><thead><tr>
      <th>Nazwa</th><th>Kategoria</th><th class="r">Ilość w op.</th><th>j.m.</th>
      <th class="r">Cena opak.</th><th class="r">Cena / j.m.</th><th class="r">Użyć</th>
    </tr></thead><tbody>${rows||'<tr><td colspan="7" class="empty">Brak wyników</td></tr>'}</tbody></table></div>`,
    cards||'<div class="empty">Brak wyników</div>',
    detail)}`;
}

function editIng(id){
  const g = id ? clone(CALC.ing(id)) : {id:uid('ing'),name:'',cat:'Inne',unit:'g',packQty:1000,packPrice:null};
  const cats=[...new Set(DB.ingredients.map(x=>x.cat))].sort();
  const oldPrice = g.packPrice;
  openDlg(id?'Edytuj składnik':'Nowy składnik', `
    <div class="grid" style="grid-template-columns:1fr 1fr">
      <div style="grid-column:1/-1"><label class="f">Nazwa</label><input id="fName" type="text" value="${esc(g.name)}"></div>
      <div><label class="f">Kategoria</label>${combo('fCat','Kategoria…')}</div>
      <div><label class="f">Jednostka</label>${combo('fUnit','Jednostka…')}</div>
      <div><label class="f">Ilość w opakowaniu</label><input id="fQty" type="number" step="any" value="${g.packQty??''}"></div>
      <div><label class="f">Cena opakowania (netto)</label><input id="fPrice" type="number" step="any" value="${g.packPrice??''}"></div>
      <div><label class="f">Waga 1 jednostki [g]</label>
        <input id="fGram" type="number" step="any" value="${g.gPerUnit??''}" placeholder="${['g','ml'].includes(g.unit)?'1 (z jednostki)':['kg','l'].includes(g.unit)?'1000 (z jednostki)':'np. 2,8 dla arkusza nori'}">
        <div class="small mut" style="margin-top:5px">Potrzebne tylko dla jednostek innych niż g, ml, kg, l. Opakowania wpisz jako 0.</div></div>
      <div style="grid-column:1/-1" class="card" style="background:var(--surface-2);border:0">
        <div class="row" style="justify-content:space-between;margin-bottom:8px">
          <b>Wartości odżywcze w 100 g</b><span class="mut small">jak na etykiecie producenta</span></div>
        <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">
          ${NUTR.map(n=>`<div><label class="f">${esc(n.l)} [${n.u}]</label>
            <input id="fN_${n.k}" type="number" step="any" value="${(g.nutr&&g.nutr[n.k]!=null)?g.nutr[n.k]:''}"></div>`).join('')}
        </div>
      </div>
      <div style="grid-column:1/-1"><label class="f">Alergeny</label>
        <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:2px 10px">
          ${ALERG.map(a=>`<label class="row" style="gap:6px;cursor:pointer;font-size:12px">
            <input type="checkbox" id="fA_${a[0]}" ${(g.alerg||[]).includes(a[0])?'checked':''} style="width:auto;margin:0">
            <span>${esc(a[1])}</span></label>`).join('')}
        </div></div>
      <div style="grid-column:1/-1" class="card" style="background:var(--surface-2);border:0">
        <div class="kv"><span>Cena za jednostkę</span><b id="fCalc">—</b></div>
        <div class="kv"><span>Używany w pozycjach</span><b>${id?CALC.usedBy(id).length:0}</b></div>
      </div>
      ${id?'<div style="grid-column:1/-1"><label class="f">Notatka do zmiany ceny (opcjonalnie)</label><input id="fNote" type="text" placeholder="np. nowy cennik dostawcy, faktura FV/12/2026"></div>':''}
    </div>
    ${strefaRyzykowna(id ? g : null, 'ing')}`,
    [ ...(id?[{label:'Zamień wszędzie…', fn:()=>{ replaceDialog(id); return false; }}]:[]),
      {label:'Anuluj',cls:''},{label:'Zapisz',cls:'pri',fn:()=>{
      const nv = {
        name:val('fName').trim(), cat:val('fCat').trim()||'Inne', unit:val('fUnit').trim()||'szt.',
        packQty:numOrNull('fQty'), packPrice:numOrNull('fPrice'), gPerUnit:numOrNull('fGram'),
        nutr:(()=>{ const o={}; let any=false;
          NUTR.forEach(n=>{ const v=numOrNull('fN_'+n.k); if(v!=null){o[n.k]=v; any=true;} });
          return any?o:null; })(),
        alerg:ALERG.filter(a=>{const e=document.getElementById('fA_'+a[0]); return e&&e.checked;}).map(a=>a[0])
      };
      if(!nv.name){ alert('Podaj nazwę składnika.'); return false; }
      Object.assign(g,nv);
      if(id){
        const idx=DB.ingredients.findIndex(x=>x.id===id);
        DB.ingredients[idx]=g;
        if(oldPrice!==g.packPrice){
          DB.history.push({id:uid('h'), ingId:g.id, date:todayISO(), from:oldPrice, to:g.packPrice,
                           qty:g.packQty, note:(document.getElementById('fNote')||{}).value||''});
        }
      } else DB.ingredients.push(g);
      save(); render();
    }}],
    ()=>{
      wireStrefa('ing', id);
      // Kategoria i jednostka: lista tego, co już w bazie jest, ale WPIS WŁASNY
      // zostaje. Wpisywanie ich z palca było proszeniem się o „Bazowe" obok
      // „bazowe" i o „szt" obok „szt." — a jednostka z literówką przestaje się
      // przeliczać na gramy i cicho psuje skład etykiety.
      fillCombo('fCat', cats.map(c=>({v:c, l:c})), g.cat, null, {wolny:true});
      fillCombo('fUnit', jednostki().map(u=>({v:u, l:u})), g.unit, null, {wolny:true});
      // Podgląd ceny ma nadążać za pisaniem, a wpis własny trafia do ukrytego
      // pola dopiero po zamknięciu listy — więc czytamy to, co widać.
      const jm = () => (document.getElementById('fUnit_q').value.trim() || val('fUnit'));
      const upd=()=>{ const q=numOrNull('fQty'), p=numOrNull('fPrice');
        document.getElementById('fCalc').textContent =
          (q&&p!=null)? num(p/q,4)+' '+DB.settings.currency+' / '+jm() : '—'; };
      ['fQty','fPrice','fUnit_q'].forEach(i=>document.getElementById(i).addEventListener('input',upd));
      upd();
    });
}

/* ============================================================================
   WIDOK: PÓŁPRODUKTY
   ========================================================================== */
function vPrep(){
  const list=archFilter(DB.preps,'prep');
  const sel = SEL.prep ? CALC.prep(SEL.prep) : null;

  after('prep',()=>{
    document.querySelectorAll('[data-pick-prep]').forEach(r=>r.addEventListener('click',e=>{
      if(e.target.closest('button')||e.target.closest('a'))return; SEL.prep=r.dataset.pickPrep; render(); }));
    document.querySelectorAll('[data-edit-prep]').forEach(b=>b.addEventListener('click',()=>editPrep(b.dataset.editPrep)));
    document.querySelector('[data-act="addPrep"]').addEventListener('click',()=>editPrep(null));
  });

  /** linie receptury półproduktu z kosztem i znacznikiem odpadu */
  const skladniki = p => p.items.map(c=>{
    const info = c.kind==='raw' ? {name:c.name, unit:c.unit, unitCost:c.unitCost} : CALC.compInfo(c.refId);
    const suma = lineQty(c), u = esc(info.unit||'');
    return `<div class="kv"><span>${esc(info.name)}
      <span class="mut">${num(c.qty,c.qty%1?2:0)} ${u}${c.waste?` + ${num(c.waste,c.waste%1?2:0)} ${u} odpadu`:''} (${num(suma,suma%1?2:0)})</span>
      </span><b>${zl(suma*(info.unitCost||0))}</b></div>`;
  }).join('');
  const partia = p => p.items.reduce((s,c)=>{
    const info = c.kind==='raw' ? {unitCost:c.unitCost} : CALC.compInfo(c.refId);
    return s + lineQty(c)*(info.unitCost||0); }, 0);
  const zaKilo = p => { const uc=CALC.prepUnitCost(p.id);
    return uc==null ? null : uc*(p.yieldUnit==='g'||p.yieldUnit==='ml'?1000:1); };

  const rows=list.map(p=>{
    const uc=CALC.prepUnitCost(p.id), zk=zaKilo(p);
    return `<tr data-pick-prep="${p.id}" style="cursor:pointer" class="${SEL.prep===p.id?'sel':''} ${p.archived?'arch':''}">
      <td><b>${esc(p.name)}</b>${p.archived?' <span class="tag">archiwum</span>':''}</td>
      <td class="r num">${num(p.yieldQty,p.yieldQty%1?2:0)}</td>
      <td>${esc(p.yieldUnit)}</td>
      <td class="r num">${p.items.length}</td>
      <td class="r num">${uc!=null?num(uc,4):'<span class="tag crit">—</span>'}</td>
      <td class="r num">${zk!=null?zl(zk):'—'}</td>
      <td class="r num mut">${CALC.usedBy(p.id).length||'—'}</td>
      </tr>`;
  }).join('');

  const cards=list.map(p=>{
    const uc=CALC.prepUnitCost(p.id), zk=zaKilo(p), n=CALC.prepNutr(p.id);
    return `<div class="card tcard ${SEL.prep===p.id?'sel':''} ${p.archived?'arch':''}" data-pick-prep="${p.id}">
      <div class="th"><h3>${esc(p.name)}${p.archived?' <span class="tag">archiwum</span>':''}</h3></div>
      <div class="hint" style="margin:0 0 8px">${p.items.length} składników · wydajność ${num(p.yieldQty,p.yieldQty%1?2:0)} ${esc(p.yieldUnit)}</div>
      <div class="kv"><span>Koszt partii</span><b>${zl(partia(p))}</b></div>
      <div class="kv"><span>Koszt za ${esc(p.yieldUnit)}</span><b class="wylicz">${uc!=null?num(uc,4):'—'}</b></div>
      <div class="kv"><span>za 1 kg / 1 l</span><b>${zk!=null?zl(zk):'—'}</b></div>
      <div class="kv"><span>Energia w 100 g</span><b class="${n&&n.grams?'':'mut'}">${n&&n.grams?num(n.nutr.kcal*100/n.grams,0)+' kcal':'—'}</b></div>
      <div class="kv"><span>Użyć w recepturach</span><b class="${CALC.usedBy(p.id).length?'':'mut'}">${CALC.usedBy(p.id).length||'—'}</b></div>
      <div class="acts">${rowActions('prep', p)}</div></div>`;
  }).join('');

  let detail='<div class="card"><div class="empty">Wybierz półprodukt, żeby zobaczyć jego recepturę i koszt.</div></div>';
  if(sel){
    const uc = CALC.prepUnitCost(sel.id), zk = zaKilo(sel), n = CALC.prepNutr(sel.id);
    const na100 = (n && n.grams)
      ? Object.fromEntries(NUTR.map(x=>[x.k, n.nutr[x.k]*100/n.grams])) : null;
    const odpad = sel.items.filter(c=>c.waste>0);
    const kv = (l, v) => `<div class="kv"><span>${l}</span><b>${v}</b></div>`;
    // rozbicie kosztu liczone tak samo, jak przy rolce — od najdroższej pozycji
    const rozbicie = sel.items.map(c=>{
      const info = c.kind==='raw' ? {name:c.name, unitCost:c.unitCost} : CALC.compInfo(c.refId);
      return {name:info.name, cost:lineQty(c)*(info.unitCost||0)};
    }).filter(r=>r.cost>0).sort((a,b)=>b.cost-a.cost);
    detail = podgladKarta({
      typ:'prep', id:sel.id, nazwa:sel.name,
      podtytul: `wydajność ${num(sel.yieldQty, sel.yieldQty%1?2:0)} ${esc(sel.yieldUnit)} · ${
        sel.items.length} składników${sel.note?' · '+esc(sel.note):''}`,
      kafelki:[{lab:`Koszt za ${sel.yieldUnit}`, val: uc!=null?num(uc,4):'—', kolor:'var(--marka)'},
               {lab:'za 1 kg / 1 l', val: zk!=null?zl(zk):'—'}],
      sekcje:[
        {t:'Skład', html: (skladniki(sel) || '<div class="empty">Brak składników</div>')
          + (odpad.length?`<div class="alert warn" style="margin-top:10px"><div class="ic">i</div><div class="txt">
              Odpad wchodzi do kosztu, ale nie do wartości odżywczych — dlatego kilogram surowca
              potrafi dać pół kilograma produktu w tej samej cenie.</div></div>`:'')},
        {t:'Koszt i cena', html:`
          <div class="kv" style="border-top:1px solid var(--axis);padding-top:9px">
            <span><b>Koszt partii (netto)</b></span><b>${zl(partia(sel))}</b></div>
          ${kv('Wydajność', num(sel.yieldQty, sel.yieldQty%1?2:0)+' '+esc(sel.yieldUnit))}
          ${kv(`Koszt za 1 ${esc(sel.yieldUnit)}`,
               uc!=null?num(uc,4)+' '+DB.settings.currency:'—')}
          ${kv('Koszt za 1 kg / 1 l', zk!=null?zl(zk):'—')}`},
        {t:'Rozbicie kosztu', html:`<div id="chPrepBreak">${rozbicie.length
          ? barChartCost(rozbicie, 330) : '<div class="empty">Brak pozycji</div>'}</div>`},
        {t:'Wartości odżywcze', html:
          (na100 ? nutr100(na100)
                 : '<div class="empty">Nie da się policzyć — brak tabeli przy którymś ze składników albo wagi jednostki.</div>')
          + (n && n.missing && n.missing.length
             ? `<div class="hint">Brak danych: <b>${esc(n.missing.join(', '))}</b></div>` : '')
          + alergBlock(CALC.prepAlerg(sel.id))},
        {t:'Gdzie używany', html: usedByBlock(sel.id)},
      ],
    });
  }

  return paskListy({tytul:'Półprodukty', licznik:`${active(DB.preps).length} aktywnych`,
    klucz:'prep', dodaj:{act:'addPrep', lab:'+ Półprodukt'}}) + `
  <div class="banner">Półprodukt to coś, co przygotowujesz z kilku składników i potem zużywasz na wagę — ryż z zaprawą, sos spicy, sałatka.
    Aplikacja liczy jego koszt za jednostkę i podstawia go automatycznie do receptur. <b>Każdy składnik ma dwie ilości: tę, która trafia do produktu, i odpad. Odpad kosztuje, ale nie wchodzi do wartości odżywczych.</b></div>
  ${listLayout('prep',
    `<div class="tw"><table data-tbl="prep"><thead><tr><th>Nazwa</th><th class="r">Wydajność</th><th>j.m.</th>
      <th class="r">Składników</th><th class="r">Koszt / j.m.</th><th class="r">za 1 kg / 1 l</th><th class="r">Użyć</th>
      </tr></thead>
      <tbody>${rows||'<tr><td colspan="7" class="empty">Brak półproduktów</td></tr>'}</tbody></table></div>`,
    cards||'<div class="empty">Brak półproduktów.</div>',
    detail)}`;
}

function editPrep(id){
  const p = id ? clone(CALC.prep(id)) : {id:uid('prep'),name:'',yieldQty:1000,yieldUnit:'g',note:'',items:[]};
  const draw=()=>{
    const body=document.getElementById('prepComps');
    body.innerHTML = p.items.map((c,i)=>{
      const info = c.kind==='raw' ? {name:c.name,unit:c.unit,unitCost:c.unitCost} : CALC.compInfo(c.refId);
      const suma = lineQty(c);
      // pozycja spoza bazy nie ma czego wybierać — zostaje nazwą wpisaną ręcznie
      return `<div class="compline wst ${c.kind==='raw'||c.refId?'':'pusty'}">
        <div>${c.kind==='raw'
          ? `${esc(info.name)} <span class="tag">poza bazą</span>`
          : combo('pC'+i, 'Szukaj składnika lub półproduktu…')}
          <span class="mut">(${num(suma, suma%1?2:0)})</span></div>
        <input type="number" step="any" value="${c.qty??''}" data-q="${i}" title="Ile trafia do produktu" placeholder="ilość">
        <input type="number" step="any" value="${c.waste||''}" data-w="${i}" placeholder="0" title="Ile się wyrzuca — kosztuje, ale nie odżywia">
        <span class="mut small">${esc(info.unit||'')}</span>
        <span class="cost">${zl(suma*(info.unitCost||0))}</span>
        <button type="button" class="btn sm danger" data-rm="${i}">✕</button></div>`;
    }).join('') || '<div class="empty" style="padding:16px">Brak składników — kliknij „+ Dodaj składnik”</div>';
    const inUseP2 = new Set(p.items.map(c=>c.refId));
    const pickP2 = x=>!x.archived || inUseP2.has(x.id);
    const opcjeP = [PUSTY_WYBOR,
      ...DB.ingredients.filter(pickP2).map(g=>({v:'ing:'+g.id, l:`${g.name} (${g.cat})`})),
      ...DB.preps.filter(x=>x.id!==p.id).filter(pickP2).map(x=>({v:'prep:'+x.id, l:`◍ ${x.name}`}))];
    p.items.forEach((c,i)=>{
      if(c.kind === 'raw') return;
      fillCombo('pC'+i, opcjeP, c.refId ? c.kind+':'+c.refId : '', v=>{
        const [k,rid] = v ? v.split(':') : ['',''];
        c.kind = k || 'ing'; c.refId = rid; setTimeout(draw,0);
      });
    });
    body.querySelectorAll('[data-q]').forEach(inp=>inp.addEventListener('input',()=>{ p.items[+inp.dataset.q].qty=parseFloat(inp.value)||0; drawTot(); }));
    body.querySelectorAll('.compline.wst > div:first-child .mut').forEach((el,i)=>{
      const s=lineQty(p.items[i]); el.textContent='('+num(s, s%1?2:0)+')'; });
    body.querySelectorAll('[data-rm]').forEach(b=>b.addEventListener('click',()=>{ p.items.splice(+b.dataset.rm,1); draw(); }));
    body.querySelectorAll('[data-w]').forEach(x=>x.addEventListener('input',()=>{
      p.items[+x.dataset.w].waste=parseFloat(x.value)||0; drawTot(); }));
    drawTot();
  };
  const drawTot=()=>{
    let tot=0;
    p.items.forEach(c=>{ const info=c.kind==='raw'?{unitCost:c.unitCost}:CALC.compInfo(c.refId); tot+=lineQty(c)*(info.unitCost||0); });
    const y=numOrNull('pYield')||1;
    document.getElementById('pTot').textContent=zl(tot);
    document.getElementById('pUnit').textContent=num(tot/y,4)+' '+DB.settings.currency+'/'+val('pYUnit');
    const kc=document.getElementById('pKcal');
    if(kc){
      const r=CALC.prepNutr(Object.assign({}, p, {yieldQty:y, yieldUnit:val('pYUnit'), gPerUnit:numOrNull('pGram')}));
      const gr=r?r.grams:null;
      kc.textContent = (r && gr) ? num(r.nutr.kcal*100/gr,0)+' kcal' : '—';
    }
    // odśwież koszty w liniach
    document.querySelectorAll('#prepComps .compline').forEach((el,i)=>{
      const c=p.items[i]; const info=c.kind==='raw'?{unitCost:c.unitCost}:CALC.compInfo(c.refId);
      el.querySelector('.cost').textContent=zl(lineQty(c)*(info.unitCost||0));
      const sum=el.querySelector('div:first-child .mut');
      if(sum){ const s=lineQty(c); sum.textContent='('+num(s, s%1?2:0)+')'; }
    });
  };
  openDlg(id?'Edytuj półprodukt':'Nowy półprodukt',`
    <div class="grid" style="grid-template-columns:2fr 1fr 1fr">
      <div><label class="f">Nazwa</label><input id="pName" type="text" value="${esc(p.name)}"></div>
      <div><label class="f">Wydajność</label><input id="pYield" type="number" step="any" value="${p.yieldQty}"></div>
      <div><label class="f">Jednostka</label><input id="pYUnit" type="text" value="${esc(p.yieldUnit)}"></div>
      <div><label class="f">Waga 1 jednostki [g]</label><input id="pGram" type="number" step="any" value="${p.gPerUnit??''}" placeholder="tylko dla jednostek innych niż g/ml/kg/l"></div>
      <div style="grid-column:1/-1"><label class="f">Notatka</label><input id="pNote" type="text" value="${esc(p.note||'')}"></div>
    </div>
    <h3 style="margin:16px 0 8px">Składniki</h3>
    <div class="compline wst" style="margin-bottom:4px">
    <div class="mut small">Składnik <span class="mut">(razem)</span></div>
    <div class="mut small">ilość</div><div class="mut small">odpad</div>
    <div class="mut small">j.m.</div><div class="mut small" style="text-align:right">koszt</div><div></div>
  </div>
  <div id="prepComps"></div>
    <div class="row" style="margin-top:8px">
      <button type="button" class="btn sm" id="pAddBtn">+ Dodaj składnik</button></div>
    <div class="card" style="background:var(--surface-2);border:0;margin-top:14px">
      <div class="kv"><span>Koszt całej partii</span><b id="pTot">—</b></div>
      <div class="kv"><span>Koszt jednostkowy</span><b id="pUnit" class="wylicz">—</b></div>
      <div class="kv"><span>Energia w 100 g gotowego</span><b id="pKcal">—</b></div>
      <div class="hint" style="margin-top:6px"><b>Ilość</b> trafia do produktu i liczy się do wartości odżywczych.
        <b>Odpad</b> tylko kosztuje. W nawiasie przy nazwie widać, ile surowca schodzi razem.
        Ogórek krojony: ilość 500 g, odpad 500 g, wydajność 500 g.</div>
    </div>
    ${strefaRyzykowna(id ? p : null, 'prep')}`,
    [ ...(id?[{label:'Zamień wszędzie…', fn:()=>{ replaceDialog(id); return false; }}]:[]),
      {label:'Anuluj'},{label:'Zapisz',cls:'pri',fn:()=>{
      p.name=val('pName').trim(); p.yieldQty=numOrNull('pYield')||1; p.yieldUnit=val('pYUnit').trim()||'g'; p.note=val('pNote');
      p.gPerUnit=numOrNull('pGram');
      if(!p.name){ alert('Podaj nazwę.'); return false; }
      if(id){ const i=DB.preps.findIndex(x=>x.id===id); DB.preps[i]=p; } else DB.preps.push(p);
      save(); render();
    }}],
    ()=>{
      wireStrefa('prep', id);
      document.getElementById('pAddBtn').addEventListener('click',()=>{
        p.items.push({kind:'ing', refId:'', qty:null, waste:0}); draw();
        const q=document.getElementById('pC'+(p.items.length-1)+'_q'); if(q) q.focus(); });
      ['pYield','pYUnit'].forEach(i=>document.getElementById(i).addEventListener('input',drawTot));
      draw();
    });
}

/* ============================================================================
   WIDOK: ROLKI
   ========================================================================== */
let itemQ='';
function vItems(){
  const szukaj = bezOgonkow(itemQ.trim());
  const list=archFilter(DB.items,'items')
    .filter(i=>!szukaj || bezOgonkow(itName(i)).includes(szukaj));
  const sel = SEL.item ? CALC.item(SEL.item) : null;

  after('items',()=>{
    const q=document.getElementById('itQ');
    q.addEventListener('input',()=>{itemQ=q.value;const s=q.selectionStart;render();const n=document.getElementById('itQ');n.focus();n.setSelectionRange(s,s);});
    document.querySelectorAll('[data-pick-item]').forEach(r=>r.addEventListener('click',e=>{
      if(e.target.closest('button'))return; SEL.item=r.dataset.pickItem; render();
    }));
    document.querySelector('[data-act="addItem2"]').addEventListener('click',()=>editItem(null));
    document.querySelector('[data-act="pdfItems"]').addEventListener('click',()=>pdfReceptury());
    document.querySelectorAll('[data-edit-item]').forEach(b=>b.addEventListener('click',()=>editItem(b.dataset.editItem)));
    if(sel){
      const c=CALC.itemCalc(sel);
      const el=document.getElementById('chBreak'); if(el) wireChart(el,c.rows,r=>
        `<b>${esc(r.name)}</b>${num(r.qty,r.qty%1?3:0)} ${esc(r.unit||'')} × ${num(r.unitCost,4)} = ${zl(r.cost)}<br><span class="mut">${pct(r.cost/c.net,1)} kosztu pozycji</span>`);
    }
  });

  DND.items = (od, doo)=>{ if(przestawPoId(DB.items, od, doo)){ save(); render(); } };
  const rows=list.map((i,ix)=>{
    const c=CALC.itemCalc(i), st=CALC.status(c.fc);
    const poprz = ix>0 ? list[ix-1].id : '', nast = ix<list.length-1 ? list[ix+1].id : '';
    return `<tr data-pick-item="${i.id}" data-di="${i.id}" ${ORD.items?'draggable="true"':''}
        style="cursor:${ORD.items?'grab':'pointer'}" class="${SEL.item===i.id?'sel':''} ${i.archived?'arch':''}">
      <td>${ordCell(DB.items.indexOf(i)+1, poprz?`${i.id}|${poprz}`:'', nast?`${i.id}|${nast}`:'', ORD.items)}</td>
      <td data-sv="${esc(itName(i))}">${
        katRolki(i)?`<span class="mut">${esc(katRolki(i).name)}</span> `:''}<b>${esc(i.name)}</b>${i.archived?' <span class="tag">archiwum</span>':''}${c.missing.length?' <span class="tag crit">brak cen</span>':''}</td>
      <td class="r num">${i.pieces}</td>
      <td class="r num">${zl(c.net)}</td>
      <td class="r num">${zl(c.perPiece)}</td>
      <td class="r num">${c.priceGross?zl(c.priceGross):'<span class="tag warn">brak</span>'}</td>
      <td class="r"><span class="tag ${st==='none'?'':st}">${pct(c.fc)}</span></td>
      <td class="r num">${c.margin!=null?zl(c.margin):'—'}</td>
      </tr>`;
  }).join('');

  let detail='<div class="card"><div class="empty">Wybierz rolkę z listy, żeby zobaczyć jej skład i rentowność.</div></div>';
  if(sel){
    const c = CALC.itemCalc(sel);
    // skład idzie w kolejności nakładania na matę, nie od najdroższego składnika —
    // ta sama kolejność co w recepturze na kartce; od kosztu jest wykres niżej
    const wgKosztu = {}; c.rows.forEach(r=>{ wgKosztu[r.refId] = r; });
    const sklad = (sel.comps||[]).map(k=>wgKosztu[k.refId]).filter(Boolean)
      .map(r=>({n:r.name, opis:`${num(r.qty, r.qty%1?3:0)} ${r.unit||''}`.trim(), koszt:r.cost}));
    const polprodukty = c.rows.filter(r=>r.kind === 'prep').reduce((a,r)=>a+r.cost, 0);
    detail = podgladPozycji({
      typ:'item', id:sel.id, nazwa:itName(sel), photo:sel.photo, c,
      podtytul:`${sel.pieces} kawałków · ${sklad.length} składników`,
      sklad:[{tytul:null, pozycje:sklad}],
      wTym: polprodukty>0 ? {l:'w tym półprodukty', v:zl(polprodukty), mut:true} : null,
      chan: chanTable(sel, (o,ch)=>CALC.itemCalc(o,ch)),
      wykresId:'chBreak', wykresRows:c.rows,
      nutr: nutrBlock(CALC.itemNutr(sel), 'cała rolka'),
    });
  }

  const cards=list.map(i=>{
    const c=CALC.itemCalc(i), st=CALC.status(c.fc);
    return `<div class="card tcard ${SEL.item===i.id?'sel':''} ${i.archived?'arch':''}" data-pick-item="${i.id}">
      ${i.photo?`<img class="hero" src="${i.photo}" alt="${esc(itName(i))}">`:''}
      <div class="th"><h3>${esc(itName(i))}${i.archived?' <span class="tag">archiwum</span>':''}</h3>
        <span class="tag ${st==='none'?'':st}">${pct(c.fc)}</span></div>
      <div class="hint" style="margin:0 0 8px">${i.pieces} kawałków${c.missing.length?' · <span class="tag crit">brak cen</span>':''}</div>
      <div class="kv"><span>Koszt</span><b>${zl(c.net)}</b></div>
      <div class="kv"><span>Koszt kawałka</span><b>${zl(c.perPiece)}</b></div>
      <div class="kv"><span>Cena (${esc(chanLabel(CHAN))})</span><b>${c.priceGross?zl(c.priceGross):'<span class="tag warn">brak</span>'}</b></div>
      <div class="kv"><span>Marża netto</span><b>${c.margin!=null?zl(c.margin):'—'}</b></div>
      <div class="acts">${rowActions('items', i)}</div></div>`;
  }).join('');

  return paskListy({tytul:'Rolki', licznik:`${active(DB.items).length} aktywnych`,
    klucz:'items', kanal:true, kolejnosc:true,
    szukaj:{id:'itQ', ph:'Szukaj rolki…', val:itemQ},
    akcje:'<button class="btn" data-act="pdfItems" title="Receptury wszystkich rolek na kartkę">⎙ PDF</button>',
    dodaj:{act:'addItem2', lab:'+ Rolka'}}) + `
  ${ordHint('items','zwijania rolek')}
  ${listLayout('items',
    `<div class="tw"><table data-tbl="items" ${ORD.items?'data-no-sort-now':''}>
      <thead><tr><th data-ordth title="Kolejność zwijania">#</th><th>Nazwa</th><th class="r">Kaw.</th><th class="r">Koszt</th>
      <th class="r">Koszt/kaw.</th><th class="r">Cena</th><th class="r">Food cost</th><th class="r">Marża</th>
      </tr></thead><tbody data-dnd="items">${rows||'<tr><td colspan="8" class="empty">Brak wyników</td></tr>'}</tbody></table></div>`,
    cards||'<div class="empty">Brak wyników</div>',
    detail)}`;
}

function editItem(id){
  const it = id ? clone(CALC.item(id))
    : {id:uid('it'), name:'', cat:'', pieces:8, comps:[], photo:null,
       prices:{vending:null, dostawa:null}, vats:Object.assign({}, DB.settings.vats)};
  migrateChannels(it);
  const draw=()=>{
    const body=document.getElementById('itComps');
    body.dataset.dnd = 'itComps';                       // kolejność = kolejność nakładania
    body.innerHTML = it.comps.map((c,i)=>{
      const info = c.refId ? CALC.compInfo(c.refId) : {name:'', unit:'', unitCost:null};
      return `<div class="compline ord ${c.refId?'':'pusty'}" data-di="${i}" draggable="true">
        ${ordCell(i+1, i>0?`${i}|${i-1}`:'', i<it.comps.length-1?`${i}|${i+1}`:'', true)}
        <div>${combo('iC'+i, 'Szukaj składnika lub półproduktu…')}${
          c.refId && info.unitCost==null?' <span class="tag crit">brak ceny</span>':''}</div>
        <input type="number" step="any" value="${c.qty??''}" data-q="${i}" placeholder="ilość">
        <span class="mut small">${esc(info.unit||'')}</span>
        <span class="cost">${zl((c.qty||0)*(info.unitCost||0))}</span>
        <button type="button" class="btn sm danger" data-rm="${i}">✕</button></div>`;
    }).join('') || '<div class="empty" style="padding:16px">Brak składników — kliknij „+ Dodaj składnik”</div>';
    // każdy wiersz sam pyta, co w nim stoi — pozycję można też podmienić bez kasowania
    const inUse = new Set(it.comps.map(c=>c.refId));
    const pick = x=>!x.archived || inUse.has(x.id);
    const opcje = [PUSTY_WYBOR,
      ...DB.preps.filter(pick).map(p=>({v:p.id, l:`◍ ${p.name}`})),
      ...DB.ingredients.filter(pick).map(g=>({v:g.id, l:`${g.name} — ${g.cat}`}))];
    it.comps.forEach((c,i)=>fillCombo('iC'+i, opcje, c.refId||'',
      v=>{ c.refId=v; setTimeout(draw,0); }));
    body.querySelectorAll('[data-q]').forEach(inp=>inp.addEventListener('input',()=>{ it.comps[+inp.dataset.q].qty=parseFloat(inp.value)||0; recalc(); }));
    body.querySelectorAll('[data-rm]').forEach(b=>b.addEventListener('click',()=>{ it.comps.splice(+b.dataset.rm,1); draw(); }));
    wireDnd(body.parentElement, (od,doo)=>{ if(przestawIndeks(it.comps, od, doo)) draw(); });
    recalc();
  };
  const recalc=()=>{
    it.pieces=numOrNull('iPieces')||1;
    CHANNELS.forEach(ch=>{ it.prices[ch.k]=numOrNull('iP_'+ch.k);
                           it.vats[ch.k]=(numOrNull('iV_'+ch.k)??(ch.vat*100))/100; });
    const c=CALC.itemCalc(it);
    document.querySelectorAll('#itComps .compline').forEach((el,i)=>{
      const info=CALC.compInfo(it.comps[i].refId);
      el.querySelector('.cost').textContent=zl((it.comps[i].qty||0)*(info.unitCost||0));
    });
    document.getElementById('iNet').textContent=zl(c.net);
    document.getElementById('iPer').textContent=zl(c.perPiece);
    document.getElementById('iFc').textContent=pct(c.fc);
    document.getElementById('iFc').style.color = c.fc==null?'':CALC.status(c.fc)==='crit'?'var(--crit-ink)':CALC.status(c.fc)==='warn'?'var(--warn-ink)':'var(--good-ink)';
    document.getElementById('iMar').textContent=c.margin!=null?zl(c.margin):'—';
    document.getElementById('iSug').textContent=c.suggested?zl(c.suggested):'—';
  };
  openDlg(id?'Edytuj rolkę':'Nowa rolka',`
    <div class="grid" style="grid-template-columns:2fr 1fr 1fr 1fr">
      <div><label class="f">Kategoria</label>${combo('iKat','— bez kategorii —')}</div>
      <div><label class="f">Nazwa</label><input id="iName" type="text" value="${esc(it.name)}"
        placeholder="sama nazwa, bez kategorii"></div>
      <div><label class="f">Liczba kawałków</label><input id="iPieces" type="number" step="1" value="${it.pieces}"></div>
      ${CHANNELS.map(ch=>`
      <div><label class="f">${esc(ch.l)} — cena brutto</label>
        <input id="iP_${ch.k}" type="number" step="any" value="${it.prices[ch.k]??''}"></div>
      <div><label class="f">${esc(ch.l)} — VAT %</label>
        <input id="iV_${ch.k}" type="number" step="any" value="${num((it.vats[ch.k]??ch.vat)*100,0)}"></div>`).join('')}
    </div>
    <div style="margin-top:14px">${photoField('iPhoto','iPhotoIn','Zdjęcie rolki')}</div>
    <h3 style="margin:16px 0 4px">Receptura</h3>
    <div class="hint" style="margin-bottom:8px">Kolejność wierszy to kolejność nakładania na matę —
      przeciągnij za ⠿ albo przestaw strzałkami.</div>
    <div id="itComps"></div>
    <div class="row" style="margin-top:8px">
      <button type="button" class="btn sm" id="iAddBtn">+ Dodaj składnik</button></div>
    <div class="card" style="background:var(--surface-2);border:0;margin-top:14px">
      <div class="kv"><span>Koszt netto</span><b id="iNet">—</b></div>
      <div class="kv"><span>Koszt 1 kawałka</span><b id="iPer">—</b></div>
      <div class="kv"><span>Food cost</span><b id="iFc">—</b></div>
      <div class="kv"><span>Marża netto</span><b id="iMar">—</b></div>
      <div class="kv"><span>Sugerowana cena przy ${pct(DB.settings.targetFc,0)}</span><b id="iSug" class="wylicz">—</b></div>
    </div>
    ${strefaRyzykowna(id ? it : null, 'items')}`,
    [ {label:'Anuluj'},
      {label:'Zapisz',cls:'pri',fn:()=>{
        it.name=val('iName').trim(); it.catId=val('iKat')||null; recalc();
        if(!it.name){ alert('Podaj nazwę.'); return false; }
        if(id){ const i=DB.items.findIndex(x=>x.id===id); DB.items[i]=it; } else { DB.items.push(it); SEL.item=it.id; }
        save(); render();
      }}],
    ()=>{
      wireStrefa('items', id, ()=>{ if(SEL.item===id) SEL.item=null; });
      document.getElementById('iAddBtn').addEventListener('click',()=>{
        it.comps.push({refId:'', qty:null}); draw();
        const q=document.getElementById('iC'+(it.comps.length-1)+'_q'); if(q) q.focus(); });
      ['iPieces'].concat(CHANNELS.flatMap(ch=>['iP_'+ch.k,'iV_'+ch.k]))
        .forEach(i=>document.getElementById(i).addEventListener('input',recalc));
      fillCombo('iKat', [{v:'', l:'— bez kategorii —', pin:true}]
        .concat((DB.cats||[]).map(k=>({v:k.id, l:k.name + ' (' + k.code + ')'}))), it.catId||'');
      wirePhoto('iPhoto','iPhotoIn',it);
      draw();
    });
}

/** tabela wartości odżywczych: na 100 g i na porcję */
function nutrBlock(res, porcja){
  const braki = res.missing.length
    ? `<div class="alert warn" style="margin-top:10px"><div class="ic">?</div><div class="txt">Brak tabeli odżywczej: <b>${esc(res.missing.join(', '))}</b> — wartości poniżej są zaniżone.</div></div>` : '';
  const bezMasy = res.noMass.length
    ? `<div class="alert warn" style="margin-top:10px"><div class="ic">?</div><div class="txt">Brak wagi jednostki: <b>${esc(res.noMass.filter(n=>!/tacka|pałeczk|opłata/i.test(n)).join(', ')||'—')}</b>.</div></div>` : '';
  const al = res.alerg.length
    ? `<div class="kv" style="margin-top:10px"><span>Alergeny</span><b>${res.alerg.map(a=>esc(ALERG_NAME[a]||a)).join(', ')}</b></div>`
    : '<div class="hint" style="margin-top:10px">Żaden składnik nie ma zadeklarowanego alergenu.</div>';
  if(!(res.mass>0)) return `<div class="empty">Nie da się policzyć — brak wag jednostek.</div>${bezMasy}${al}`;
  const f=100/res.mass;
  const kom=(v,n)=> n.k==='kcal'
    ? `${num(v*4.184,0)} kJ / ${num(v,0)} kcal`
    : `${num(v, v<1?2:1)} ${n.u}`;
  const rows=NUTR.map(n=>`<tr><td>${n.sub?'<span class="mut">w tym '+esc(n.l.replace('w tym ',''))+'</span>':esc(n.l)}</td>
      <td class="r num">${kom((res.nutr[n.k]||0)*f, n)}</td>
      <td class="r num">${kom(res.nutr[n.k]||0, n)}</td></tr>`).join('');
  return `<div class="tw"><table><thead><tr><th>Wartość odżywcza</th><th class="r">w 100 g</th><th class="r">${esc(porcja)}</th></tr></thead>
    <tbody>${rows}</tbody></table></div>
    <div class="hint">Masa porcji: <b>${num(res.mass,0)} g</b></div>${braki}${bezMasy}${al}`;
}

/* ---------------------------------------------------------------------------
   WYDRUKI: kartka „co z czego"
   Rolki i zestawy drukują się tak samo — numer, nazwa, miniatura i wcięta lista
   z ilościami w nawiasie. Różni je tylko to, co wchodzi na listę, więc układ
   siedzi w jednym miejscu.
   ------------------------------------------------------------------------- */
/** Ile kolumn dla sekcji o `n` kartach, przy suficie `cap`.

    Najpierw najmniej rzędów — im mniej, tym mniej miejsca w pionie. Przy remisie
    wygrywa układ równy: sześć kafelków w trzech kolumnach to dwa pełne rzędy,
    a w czterech — rząd czterech i rząd dwóch, z dziurą po prawej. Osiem kafelków
    daje przy tej regule dwa rzędy po cztery. */
function kolumnySekcji(n, cap){
  const maks = Math.max(1, Math.min(cap, n));
  let naj = 1, najRzedow = n;
  for(let k=1; k<=maks; k++){
    const rzedow = Math.ceil(n / k);
    const rowno = n % k === 0;
    const lepiej = rzedow < najRzedow
                || (rzedow === najRzedow && rowno && n % naj !== 0);
    if(lepiej){ naj = k; najRzedow = rzedow; }
  }
  return naj;
}

function pdfKarty(o){
  const kartyDla = poziom => {
  let sekcja = null, nr = 0;
  return o.pozycje.map(p=>{
    // Nazwa po lewej, liczba w swojej kolumnie po prawej, jednostka w jeszcze jednej.
    // Kropki prowadzą oko przez pustkę między nimi — bez nich przy długiej nazwie
    // i krótkiej liczbie wiersz się rozpada. Liczba nie musi być wytłuszczona: stoi
    // tam, gdzie oko jej szuka, więc nie musi się przebijać krojem.
    // Kolumnę jednostki rezerwujemy tylko wtedy, gdy w tej karcie w ogóle jest jednostka —
    // w Pakowaniu żaden wiersz jej nie ma i pusty pasek zjadałby szerokość wąskiej kolumny.
    const maJm = p.wiersze.some(w=>w.jm), maJm2 = p.wiersze.some(w=>w.q2);
    // Kolumna liczb dostaje szerokość najdłuższej liczby W TEJ karcie, a nie sztywne
    // 2,6em. Przy jednocyfrowych ilościach sufit zostawiał między kropkami a cyfrą
    // wielką dziurę — kropki kończyły się w połowie drogi i wiersz się rozpadał.
    const szer = pole => Math.max(1, ...p.wiersze.map(w=>String(w[pole] ?? '').length));
    const wiersze = p.wiersze.length
      ? p.wiersze.map(w=>!w.n && !w.q ? '<div class="w">&nbsp;</div>'
          : `<div class="w"><span class="nm">${esc(w.n)}</span><span class="krop"></span>` +
            `<span class="il">${esc(w.q)}</span>` +
            (maJm ? `<span class="jm">${esc(w.jm || '')}</span>` : '') +
            (maJm2 ? `<span class="il2">${esc(w.q2 || '')}</span>` +
                     `<span class="jm2">${esc(w.jm2 || '')}</span>` : '') + '</div>').join('')
      : `<div class="q">${esc(o.puste || 'brak pozycji')}</div>`;
    // nowa sekcja zaczyna własną numerację
    if(p.sekcja !== sekcja){ sekcja = p.sekcja; nr = 0; }
    nr++;
    const nazwa = skrocPierwszy(p.name || '', poziom);
    return {sekcja: p.sekcja || null, dlugie: nazwa.length > 14, html: `<section class="rolka">
      <h2>${o.numery===false?'':`<span class="nr">${nr}.</span> `}${esc(nazwa)}</h2>
      <div class="skl" style="--ilw:${szer('q')}ch${maJm?`;--jmw:${szer('jm')}ch`:''}${
        maJm2?`;--ilw2:${szer('q2')}ch;--jm2w:${szer('jm2')}ch`:''}">${wiersze}</div>
    </section>`};
  });
  };

  // Sekcje idą jedna pod drugą, każda z własną siatką — dzięki temu automaty mogą
  // stać w trzech kolumnach, a zestawy w czterech, jeśli tak wychodzi im równiej.
  // 14 znaków to próg z obserwacji: krótsze nazwy mieszczą się w jednej linii kafelka
  // przy każdej liczbie kolumn, dłuższe potrafią się złamać i wtedy rezerwa jest potrzebna
  const grupyDla = poziom => {
    const grupy = [];
    kartyDla(poziom).forEach(k=>{
      const ost = grupy[grupy.length-1];
      if(ost && ost.sekcja === k.sekcja){ ost.karty.push(k.html); ost.dlugie = ost.dlugie || k.dlugie; }
      else grupy.push({sekcja:k.sekcja, karty:[k.html], dlugie:k.dlugie});
    });
    return grupy;
  };
  const siatki = (cap, poziom) => grupyDla(poziom).map(g=>
    `${g.sekcja ? `<h2 class="sekcja">${esc(g.sekcja)}</h2>` : ''}
     <div class="siatka${o.ramki && g.dlugie ? ' dlugie' : ''}"
          style="column-count:${kolumnySekcji(g.karty.length, cap)}">
       ${g.karty.join('')}</div>`).join('');

  const styl = () => `
    /* 1 px luzu z prawej: bez tego ramka ostatniej kolumny leży dokładnie na
       krawędzi pola zadruku i przy rasteryzacji znika */
    .siatka{column-gap:6mm;padding-right:1px}
    .siatka + h2.sekcja{margin-top:.6em}
    .rolka{break-inside:${o.lamliwe?'auto':'avoid'};
      page-break-inside:${o.lamliwe?'auto':'avoid'};margin:0 0 ${o.ramki?'.8em':'1.1em'}}
    ${o.ramki?`.rolka{border:1px solid #c9c9c9;border-radius:7px;padding:.5em .65em .6em}
    .rolka .skl{margin-left:.2em}
    /* Dwie linie rezerwy na nazwę — ale tylko w sekcjach, gdzie nazwa realnie
       może się złamać. Sekcja tytułowana kodami („ZAB”) nigdy się nie łamie,
       więc pusta druga linia byłaby w każdym kafelku zmarnowanym wierszem. */
    .siatka.dlugie .rolka h2{min-height:2.5em}`:''}
    h2.sekcja{column-span:all;font-size:1.05em;margin:.3em 0 .5em;padding-bottom:.15em;
      border-bottom:1px solid #ddd}
    h2.sekcja:first-child{margin-top:0}
    /* nazwa karty może się złamać — to jeden nagłówek, nie rytm listy;
       gdyby i ona nie mogła, długa nazwa automatu zbijałaby pismo do minimum */
    .rolka h2{font-size:.96em;margin:0 0 .15em;line-height:1.25}
    .rolka .nr{color:#BD172F;font-weight:700}
    .rolka .skl{margin-left:1.5em;font-size:.86em;color:#333}
    .rolka .skl .w{display:flex;align-items:baseline;gap:.3em;padding:.06em 0;white-space:nowrap}
    .rolka .skl .nm{flex:none}
    /* Rozciągliwa kreska kropkowana — jedyne, co w wierszu może się zwężać, i to aż
       do zera. Gdy nazwa jest długa, wolimy stracić kropki niż przesunąć liczbę:
       brak kreski to drobiazg, przesunięta liczba to zepsuta kolumna. */
    .rolka .skl .krop{flex:1 1 auto;min-width:0;border-bottom:1px dotted #c2beb7;
      transform:translateY(-.24em)}
    .rolka .skl .il{flex:none;min-width:var(--ilw,2.6em);text-align:right;
      font-variant-numeric:tabular-nums;color:#111}
    /* jednostka też dostaje szerokość z zawartości karty — sztywna kolumna albo
       zjadała miejsce przy „g”, albo pękała przy „opak.” i wiersz wystawał poza kafelek */
    .rolka .skl .jm{flex:none;min-width:var(--jmw,2.4em);color:#666;font-size:.94em;white-space:nowrap}
    /* druga para liczba+jednostka (opakowania, partie) — własne kolumny, jak pierwsza */
    .rolka .skl .il2{flex:none;min-width:var(--ilw2,2.4em);text-align:right;
      font-variant-numeric:tabular-nums;color:#777;font-size:.94em;margin-left:.5em}
    .rolka .skl .jm2{flex:none;min-width:var(--jm2w,2.6em);color:#999;font-size:.94em;white-space:nowrap}
    .rolka .q{color:#888;white-space:nowrap;font-variant-numeric:tabular-nums}`;

  // tytuł siedzi już w główce dokumentu — tu zostaje sama treść;
  // `kol` jest sufitem, a nie sztywną liczbą — każda sekcja liczy swoją
  const buduj = (kol, px, poziom) => dokumentDruku(o.tytul, styl(), siatki(kol, poziom||0), px);
  const cap = o.maxKol || DB.settings.pdfMaxCols;

  // Najpierw pełne nazwy. Jeśli przy dobranym układzie któraś łamie się na dwie linie,
  // skracamy pierwszy wyraz i szukamy układu jeszcze raz — krótsze tytuły to niższe
  // kafelki, więc pismo zwykle przy okazji rośnie. Dwa podejścia i koniec: „Śre.” i „Ś.”.
  //
  // Tylko w kafelkach. Na kartce z recepturami tytuł ma całą szerokość kolumny i złamanie
  // go nie boli, a „Hos. Rzodkiew Takuan” byłoby gorsze od pełnej nazwy w dwóch liniach.
  let poziom = 0;
  let uklad = dopasujDruk((k,px)=>buduj(k,px,0), cap, DB.settings.pdfMinFont);
  if(o.ramki) for(let p=1; p<=2; p++){
    if(!maLamaneTytuly(buduj(uklad.kol, uklad.px, poziom))) break;
    poziom = p;
    uklad = dopasujDruk((k,px)=>buduj(k,px,p), cap, DB.settings.pdfMinFont);
  }

  zrobPdf(buduj(uklad.kol, uklad.px, poziom), o.plik, stopkaDruku(o.tytul));
}

/* ---------------------------------------------------------------------------
   WYDRUKI Z PULPITU
   Te same dane, które kuchnia widzi na ekranie, tylko na kartce — bo przy macie
   nikt nie odblokowuje telefonu mokrymi rękami. Zawsze dotyczą wybranego dnia.
   ------------------------------------------------------------------------- */
function dzienDoDruku(z){
  if(z) return {z, r: zalRozpiska(z)};        // wydruk wprost z załadunku
  const d = daneDnia(DAY);
  if(!d.z){
    alert('Do dnia „' + dzienNazwa(DAY) + '" nie jest przypisany żaden załadunek —\n'
      + 'nie ma czego drukować. Przypisz załadunek w planie tygodnia.');
    return null;
  }
  return d;
}
/* Kartki nie drukuje się codziennie, więc w tytule stoi nazwa załadunku, a nie data —
   „Rolki · Dni robocze" wisi na ścianie tak długo, jak długo obowiązuje ten załadunek. */
const dzienTytul = (co, d) => co + ' · ' + d.z.name;
const dzienPlik  = (co, d) => co + '-' +
  (bezOgonkow(d.z.name).replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'') || 'zaladunek');

/** Przygotowanie: półprodukty i surowce na dany dzień. */
function pdfPrzygotowanie(z){
  const d = dzienDoDruku(z); if(!d) return;
  const pp = Object.keys(d.r.polprodukty).map(id=>{
    const p = CALC.prep(id); if(!p) return null;
    const ile = d.r.polprodukty[id];
    return {n: p.name, q: ilosc(ile), jm: p.yieldUnit || '',
            q2: p.yieldQty ? num(ile/p.yieldQty, 2) : '', jm2: p.yieldQty ? 'partii' : ''};
  }).filter(Boolean);
  // składniki po alfabecie — z kartką idzie się do lodówki, nie po recepturze
  const skl = Object.keys(d.r.skladniki).map(id=>{
    const ile = d.r.skladniki[id];
    if(id.indexOf('raw:') === 0)
      return {n: id.slice(4) + ' (poza bazą)', q: ilosc(ile), jm: '', q2: ''};
    const g = CALC.ing(id); if(!g) return null;
    return {n: g.name, q: ilosc(ile), jm: g.unit || '',
            q2: g.packQty ? num(ile/g.packQty, 2) : '', jm2: g.packQty ? 'opak.' : ''};
  }).filter(Boolean).sort((a,b)=>a.n.localeCompare(b.n, 'pl'));
  pdfKarty({
    tytul: dzienTytul('Przygotowanie', d), plik: dzienPlik('przygotowanie', d),
    lamliwe: true, numery: false,
    pozycje: [{name:'Półprodukty', wiersze:pp}, {name:'Składniki', wiersze:skl}]
  });
}

/** Rolki do zwinięcia — w kolejności zwijania. */
function pdfDzienRolki(z){
  const d = dzienDoDruku(z); if(!d) return;
  const poz = id => { const i = DB.items.findIndex(x=>x.id===id); return i<0 ? 1e9 : i; };
  const rolki = Object.keys(d.r.rolki).sort((a,b)=>poz(a)-poz(b)).map(id=>{
    const it = CALC.item(id), kaw = d.r.rolki[id];
    return {id, n: it ? it.name : '⚠ brak rolki', kaw,
            rolek: it ? kaw/(it.pieces||1) : null, brak: !it};
  });
  // karta na kategorię, na dole suma pośrednia — kucharz odhacza grupami
  const pozycje = rolkiWgKategorii(rolki).map(g=>({
    name: (g.kat ? g.kat.name : 'Bez kategorii')
          + (g.rolki.some(x=>x.rolek!=null) ? ' · ' + num(g.rolek, g.rolek%1 ? 1 : 0) : ''),
    wiersze: g.rolki.map(x=>({n: x.n,
      q: x.rolek==null ? ilosc(x.kaw) : num(x.rolek, x.rolek%1 ? 1 : 0),
      jm: x.rolek==null ? 'kaw.' : ''}))
  }));
  pdfKarty({tytul: dzienTytul('Rolki', d), plik: dzienPlik('rolki', d), numery: false, puste: 'nic do zwinięcia', pozycje});
}

/** Zestawy do złożenia. */
function pdfDzienZestawy(z){
  const d = dzienDoDruku(z); if(!d) return;
  const w = DB.sets.filter(s=>d.r.zestawy[s.id])
    .map(s=>({n: s.name, q: String(d.r.zestawy[s.id])}));
  pdfKarty({tytul: dzienTytul('Zestawy', d), plik: dzienPlik('zestawy', d), lamliwe: true, numery: false, puste: 'nic do złożenia',
            pozycje: [{name:'Do złożenia', wiersze:w}]});
}

/** Pakowanie: ta sama macierz z dwóch stron — kafelek na automat i kafelek na zestaw. */
function pdfPakowanie(z){
  const d = dzienDoDruku(z); if(!d) return;
  const V = DB.vending, maszyny = active(DB.machines);
  const per = maszyny.map(m=>{
    const wg = {};
    for(let n=1; n<=V.slots; n++){
      if(!slotOn(d.z, m.id, n)) continue;
      const s = slotSet(n); if(!s) continue;
      wg[s.id] = (wg[s.id]||0) + 1;
    }
    return {m, wg};
  });
  const kolejnosc = DB.sets.map(s=>s.id).filter(id=>per.some(x=>x.wg[id]));

  const kafleMaszyn = per.map(({m, wg})=>({
    sekcja: 'Automaty',
    // Na kartce liczy się rozpoznanie w pół sekundy, a nie pełna nazwa z adresem.
    // Kod jest krótki i jednakowej długości, więc kafelki przestają się rozjeżdżać
    // na dwie linie — i mieszczą się gęściej, co podnosi stopień pisma.
    name: m.code || m.name,
    wiersze: kolejnosc.filter(id=>wg[id]).map(id=>{
      const s = CALC.set(id);
      return {n: s ? s.name : id, q: String(wg[id])};
    })
  }));
  const kafleZestawow = kolejnosc.map(id=>{
    const s = CALC.set(id);
    return {
      sekcja: 'Zestawy',
      name: s ? s.name : id,
      wiersze: per.filter(x=>x.wg[id]).map(x=>({n: x.m.code || x.m.name, q: String(x.wg[id])}))
    };
  });

  // Kafelki w sekcji mają mieć jeden rozmiar — łatwiej porównać wzrokiem, ile
  // gdzie jedzie. Brakujące wiersze dopychamy pustymi.
  const wyrownaj = lista => {
    const max = lista.reduce((a,x)=>Math.max(a, x.wiersze.length), 0);
    lista.forEach(x=>{ while(x.wiersze.length < max) x.wiersze.push({n:'', q:''}); });
    return lista;
  };
  pdfKarty({tytul: dzienTytul('Pakowanie', d), plik: dzienPlik('pakowanie', d),
            ramki: true, puste: 'nic nie jedzie',
            // w kafelku stoi kod albo nazwa i jedna cyfra — zmieści się ich w rzędzie
            // więcej niż wierszy tekstu na kartce z recepturą
            maxKol: 4,
            pozycje: wyrownaj(kafleMaszyn).concat(wyrownaj(kafleZestawow))});
}

const PDF_DNIA = {dPrep:pdfPrzygotowanie, dRolki:pdfDzienRolki,
                  dZest:pdfDzienZestawy, dPack:pdfPakowanie};

/** Receptury rolek: składniki w kolejności nakładania, z gramaturami. */
function pdfReceptury(){
  const lista = active(DB.items);
  pdfKarty({
    tytul: 'Receptury rolek',
    plik: 'receptury-rolek',
    puste: 'brak receptury',
    pozycje: lista.map(it=>({
      name: itName(it),
      wiersze: (it.comps||[]).map(c=>{
        const info = CALC.compInfo(c.refId);
        return {n: info.name,
                q: num(c.qty||0, (c.qty||0)%1?2:0), jm: info.unit || ''};
      })
    }))
  });
}

/** Skład zestawów: najpierw rolki w kawałkach, potem dodatki. */
function pdfZestawy(){
  const lista = active(DB.sets);
  pdfKarty({
    tytul: 'Skład zestawów',
    plik: 'sklad-zestawow',
    puste: 'zestaw pusty',
    // Tylko rolki — dodatki pakuje się z listy w Pakowaniu, nie z tej kartki.
    // Kolejność jak na liście rolek, żeby na wszystkich zestawach szło się tak
    // samo: z góry na dół, w tej kolejności co zwijanie.
    pozycje: lista.map(s=>{
      const poz = id => { const i = DB.items.findIndex(x=>x.id===id); return i<0 ? 1e9 : i; };
      return {
        name: s.name,
        wiersze: (s.entries||[]).slice()
          .sort((a,b)=>poz(a.itemId)-poz(b.itemId))
          .map(e=>{
            const it = CALC.item(e.itemId);
            return {n: it ? itNameK(it) : '⚠ brak rolki', q: String(e.pieces||0)};
          })
      };
    })
  });
}

/* ============================================================================
   ETYKIETY NA OPAKOWANIA
   Do tej pory każda etykieta była osobnym plikiem w Wordzie, przepisywanym
   ręcznie po każdej zmianie w zestawie. Stąd rozjazdy: raz „6 x futomaki łosoś
   pieczony", raz „6 x łosoś pieczony", a w dwóch plikach blok na dole stał
   o 3 mm wyżej niż w pozostałych. Teraz skład bierze się z tego samego miejsca
   co food cost, więc etykieta nie może się rozminąć z recepturą.

   Co jest nienaruszalne: 90 x 130 mm i margines 7 mm. To wymiar naklejki
   z rolki, a nie decyzja projektowa.
   ========================================================================== */

/** Kategorie, których na etykiecie nie wypisujemy. Ryż i nori są w każdej rolce
    bez wyjątku, a tacka i pałeczki nie są jedzeniem — jedno i drugie tylko
    zabiera miejsce na liście, którą ktoś ma naprawdę przeczytać. */
function etykPomijane(){
  return String(DB.settings.etykPomin ?? ETYK.pominDom)
    .split(',').map(x=>bezOgonkow(x).trim()).filter(Boolean);
}
/** Czy ta pozycja ma zniknąć z etykiety. Lista z ustawień trafia i w KATEGORIĘ,
    i w NAZWĘ — jedno pole zamiast dwóch, bo z punktu widzenia czytającego to
    jedna decyzja: „tego na naklejce nie chcę". Ogonki nie mają znaczenia,
    żeby „Sól" i „sol" znaczyły to samo. */
function etykPominiety(pomin, nazwa, kat){
  return pomin.includes(bezOgonkow(nazwa).trim())
      || pomin.includes(bezOgonkow(kat).trim());
}
/** Skład etykiety to SKŁADNIKI ZASADNICZE, nie półprodukty.

    „Ryż gotowany" i „Ogórek krojony" to nazwy z naszej kuchni — mówią, na jakim
    etapie przygotowania jest towar, a nie co klient je. Półprodukt rozkłada się
    więc na to, z czego jest zrobiony, i to samo dzieje się z półproduktem
    w półprodukcie.

    Liczymy przy okazji MASĘ każdego składnika w całym zestawie, bo skład na
    etykiecie idzie malejąco według masy — tak samo, jak na każdym opakowaniu
    w sklepie. Bez tego kolejność byłaby przypadkowa i nic by nie mówiła.

    Mnożnik niesie ilość: pozycja rolki liczy się przez `kawałki/kawałki w rolce`,
    a wejście w półprodukt dzieli przez jego wydajność. Dzięki temu 110 g ryżu
    gotowanego wnosi tyle ryżu suchego i zaprawy, ile naprawdę w nim jest.

    Nazwy idą DOKŁADNIE tak, jak brzmią w aplikacji — żadnego zmieniania
    wielkości liter po drodze. Każda „poprawka" robiłaby z jednej nazwy dwie:
    tę z ekranu i tę z naklejki. */
function etykMasy(st){
  const pomin = etykPomijane();
  const masy = [];                                   // {nazwa, g, znana}
  const dodaj = (nazwa, g) => {
    if(!nazwa) return;
    const byl = masy.find(x => x.nazwa === nazwa);   // ten sam składnik stoi RAZ,
    if(byl){                                         // choćby wchodził pięcioma drogami
      if(g == null) return;
      byl.g += g; byl.znana = true;
      return;
    }
    masy.push({nazwa, g: g || 0, znana: g != null});
  };
  const idz = (lista, mnoznik, gleb, sciezka) => {
    for(const c of (lista || [])){
      const q = (c.qty || 0) * mnoznik;
      if(!(q > 0)) continue;
      // pozycja wpisana wprost w półprodukcie — nie ma jej w Składnikach,
      // więc nie ma też kategorii; dostaje własną, żeby dało się ją pominąć
      if(c.kind === 'raw'){
        if(!etykPominiety(pomin, c.name, 'Surowiec')) dodaj(c.name, masa(q, c.unit, c.gPerUnit));
        continue;
      }
      const info = CALC.compInfo(c.refId);
      if(info.kind === 'missing') continue;
      if(etykPominiety(pomin, info.name, info.cat)) continue;
      if(info.kind === 'prep'){
        const pr = CALC.prep(c.refId);
        // Półprodukt wskazujący sam na siebie zapętliłby rozkładanie.
        if(pr && pr.yieldQty && gleb < ETYK.glebokosc && sciezka.indexOf(c.refId) < 0)
          idz(pr.items, q / pr.yieldQty, gleb + 1, sciezka.concat(c.refId));
        else
          dodaj(info.name, masa(q, pr && pr.yieldUnit, pr && pr.gPerUnit));
        continue;
      }
      const g = CALC.ing(c.refId);
      dodaj(info.name, masa(q, g && g.unit, g && g.gPerUnit));
    }
  };
  for(const e of (st.entries || [])){
    const it = CALC.item(e.itemId);
    if(!it || !it.pieces) continue;
    idz(it.comps, (e.pieces || 0) / it.pieces, 0, []);
  }
  idz(st.comps, 1, 0, []);
  // Malejąco po masie. Składnik bez przelicznika na gramy nie ma jak stanąć
  // w kolejce, więc idzie na koniec — ale ZOSTAJE: na etykiecie z jedzeniem
  // przemilczenie składnika jest gorsze niż jego niepewne miejsce.
  return masy
    .map((x, i) => ({...x, i}))
    .sort((a, b) => (a.znana !== b.znana) ? (a.znana ? -1 : 1)
                  : (b.g !== a.g ? b.g - a.g : a.i - b.i));
}
/** Masa jednej pozycji w gramach; `null`, gdy nie ma z czego jej policzyć. */
function masa(qty, unit, gPerUnit){
  const g = unitGrams(unit, gPerUnit);
  return g == null ? null : qty * g;
}
/** Etykieta ma dwa bloki i każdy odpowiada na inne pytanie.

    Pierwszy — CO JEST W PUDEŁKU: ilość krążków i nazwa rolki, ciągiem,
    rozdzielone kropką. Kto otwiera opakowanie, chce policzyć kawałki, a nie
    czytać recepturę.

    Drugi — Z CZEGO TO JEST: wszystkie składniki całego zestawu, każdy raz,
    malejąco według masy. To jest ta część, którą czyta się przy alergii,
    i dlatego nie jest rozbita na rolki: przy ośmiu rolkach ta sama sałata
    stałaby na liście pięć razy i nikt by tego nie przeczytał do końca. */
function etykTresc(st){
  const poz = id => { const i = DB.items.findIndex(x => x.id === id); return i < 0 ? 1e9 : i; };
  const rolki = (st.entries || []).slice()
    .sort((a, b) => poz(a.itemId) - poz(b.itemId))
    .map(e => {
      const it = CALC.item(e.itemId);
      return it ? `${e.pieces || 0} x ${itName(it)}` : '⚠ brak rolki';
    });
  return {rolki, sklad: etykMasy(st).map(x => x.nazwa)};
}
/** Tekst z ustawień: **pogrubienie** działa, reszta jest zwykłym tekstem.
    Escape idzie PIERWSZY, więc gwiazdki nie przemycą znacznika. */
function etykAkapit(txt){
  return esc(String(txt||'')).replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
}
function etykStrona(st){
  const t = etykTresc(st);
  return `<section class="et">
    <h1>${esc(st.name)}</h1>
    ${t.rolki.length ? `<div class="rolki">${esc(t.rolki.join(' · '))}</div>` : ''}
    ${t.sklad.length ? `<div class="sklad"><b>Skład:</b> ${esc(t.sklad.join(', '))}.</div>` : ''}
    <div class="luz"></div>
    <div class="dol">
      <p>${etykAkapit(DB.settings.etykAlerg ?? ETYK.alergDom)}</p>
      <p>${etykAkapit(DB.settings.etykPrzechow ?? ETYK.przechowDom)}</p>
    </div></section>`;
}
/** Style etykiety. Wszystko pod `.etyk`, żeby ten sam arkusz mógł zmierzyć
    etykietę w sondzie wewnątrz aplikacji i narysować ją w dokumencie do druku —
    inaczej sonda mierzyłaby coś innego, niż wyjdzie z drukarki. */
function etykCss(pt, wysokosc){
  const wys = wysokosc === 'auto' ? 'auto'
            : (ETYK.wysMm - 2*ETYK.margMm - 0.1).toFixed(1) + 'mm';
  return `.etyk{font:${(+pt).toFixed(2)}pt/${ETYK.interlinia} ${ETYK.krojCss};color:#000;
      font-variant-numeric:normal;-webkit-font-smoothing:antialiased}
    .etyk .et{box-sizing:border-box;height:${wys};padding-top:${ETYK.pasGoryMm}mm;
      display:flex;flex-direction:column}
    .etyk h1{font-size:${ETYK.tytulPt}pt;line-height:1.2;font-weight:700;
      text-align:center;margin:0;letter-spacing:-.01em}
    .etyk .rolki{margin:${ETYK.poTytulePt}pt 0 0}
    .etyk .sklad{margin:${ETYK.miedzyAkap} 0 0;text-align:justify}
    .etyk .luz{flex:1 1 auto;min-height:0}
    .etyk .dol p{margin:0;text-align:justify}
    .etyk .dol p+p{margin-top:${ETYK.miedzyAkap}}`;
}
/** @page bez marginesu = marginesy ustawia Gotenberg (tak jak w A4).
    Z marginesem = drukujemy z przeglądarki, bo serwera nie ma i nikt inny
    ich nie poda. Jedno i drugie daje tę samą kartkę; dwa razy policzone
    marginesy dałyby dwie różne. */
function etykDokument(sety, pt, zMarginesem){
  return `<!doctype html><html lang="pl"><head><meta charset="utf-8">
  <title>Etykiety</title>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Lato:wght@400;700&display=swap">
  <style>
    @page{size:${ETYK.szerMm}mm ${ETYK.wysMm}mm${zMarginesem?`;margin:${ETYK.margMm}mm`:''}}
    html,body{margin:0;padding:0}
    ${etykCss(pt)}
    .etyk .et{page-break-after:always;break-after:page}
    .etyk .et:last-child{page-break-after:auto;break-after:auto}
  </style></head><body class="etyk">${sety.map(etykStrona).join('')}</body></html>`;
}
/** Największe pismo, przy którym MIEŚCI SIĘ KAŻDA etykieta z partii.
    Jedno dla wszystkich, bo etykiety z jednej rolki ogląda się obok siebie
    i różne wielkości pisma widać od razu.

    Mierzymy w tym dokumencie, nie w ukrytej ramce — tutaj krój jest już
    wczytany. Jeżeli mierzy Aptos (Twój Windows z Office'em), a serwer rysuje
    Latem, różnica to 1,8% — mniej niż jedno słowo w linijce. */
function etykDopasujPt(sety){
  const dost = (ETYK.wysMm - 2*ETYK.margMm) / 25.4 * 96;      // px, CSS mm = 96/25.4
  const sonda = document.createElement('div');
  sonda.className = 'etyk';
  sonda.style.cssText = 'position:fixed;left:-9999px;top:0;visibility:hidden;'
    + 'width:' + (ETYK.szerMm - 2*ETYK.margMm) + 'mm';
  const styl = document.createElement('style');
  sonda.innerHTML = sety.map(etykStrona).join('');
  document.body.appendChild(styl);
  document.body.appendChild(sonda);
  let pt = ETYK.tekstPt;
  try{
    const mierz = p => {
      styl.textContent = etykCss(p, 'auto').replace(/\.etyk/g, '.etsonda');
      sonda.className = 'etsonda';
      return Math.max(0, ...[...sonda.querySelectorAll('.et')]
        .map(e=>e.getBoundingClientRect().height));
    };
    while(pt > ETYK.minPt && mierz(pt) > dost) pt = Math.round((pt - 0.25) * 100) / 100;
  }catch(e){ /* gdyby przeglądarka nie dała zmierzyć — zostaje rozmiar z etykiet Worda */ }
  sonda.remove(); styl.remove();
  return pt;
}
/** Nazwa pliku z nazwy zestawu: serwer i tak przepuszcza tylko [A-Za-z0-9-_],
    więc „Duży mieszany" bez tego zostałoby „Duymieszany". */
function plikNazwa(t){
  return (bezOgonkow(String(t||'')).replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'') || 'etykieta');
}
/** Każdy zestaw to OSOBNY plik PDF — drukarka etykiet dostaje jeden plik na
    wzór, a nie stos stron do rozcinania. Jeden zestaw wychodzi pojedynczym
    PDF-em, kilka — ZIP-em z osobnymi plikami w środku.

    Pismo dobieramy RAZ dla całej partii, mimo że pliki są osobne: etykiety
    z jednej rolki ogląda się obok siebie i różne wielkości pisma widać od razu.

    Bez serwera nie ma czym zrobić ani PDF-u, ani paczki. Zostaje okno
    drukowania z jednym dokumentem — i uczciwe powiedzenie, że to nie to samo. */
async function pdfEtykiety(sety, nazwa){
  const lista = (sety||[]).filter(Boolean);
  if(!lista.length){ alert('Nie ma czego drukować — lista zestawów jest pusta.'); return; }
  const pt = etykDopasujPt(lista);
  if(lista.length === 1){
    // Bez serwera dokument idzie do okna drukowania, więc marginesy musi nieść CSS.
    // `await`, choć nikt na wynik nie czeka: bez niego obietnica tej funkcji
    // kończy się, zanim serwer w ogóle odpowie, i wołający nie ma jak poznać,
    // że wydruk się skończył.
    await zrobPdf(etykDokument(lista, pt, !SRV.on), nazwa, null, 'etykieta');
    return;
  }
  const pliki = lista.map((z, i) => ({
    name: String(i+1).padStart(2,'0') + ' ' + z.name,
    html: etykDokument([z], pt, false),
  }));
  if(await zrobZip(pliki, nazwa, 'etykieta')) return;
  if(!confirm('Bez serwera nie da się zrobić osobnych plików PDF.\n\n'
    + 'Otworzyć okno drukowania ze wszystkimi etykietami w jednym dokumencie?')) return;
  drukujOkno(etykDokument(lista, pt, true));
}
/** Podgląd etykiety w panelu zestawu — ta sama treść, co na wydruku.
    Bez tego jedyną drogą do sprawdzenia, co się wydrukuje, byłby wydruk. */
function etykPodglad(st){
  const t = etykTresc(st);
  if(!t.rolki.length && !t.sklad.length)
    return '<div class="empty">Zestaw nie ma pozycji</div>';
  // Kolejność składu niesie informację tylko wtedy, gdy KAŻDY składnik da się
  // zważyć. Ten, który nie ma przelicznika na gramy, ląduje na końcu listy nie
  // dlatego, że jest go najmniej — i lepiej, żeby było to powiedziane wprost.
  const bezMasy = etykMasy(st).filter(x => !x.znana).map(x => x.nazwa);
  return `<div class="etpod">
      <div class="etpod-t">${esc(st.name)}</div>
      ${t.rolki.length ? `<p class="etpod-r">${esc(t.rolki.join(' · '))}</p>` : ''}
      ${t.sklad.length ? `<p class="etpod-s"><b>Skład:</b> ${esc(t.sklad.join(', '))}.</p>` : ''}
    </div>
    ${bezMasy.length ? `<div class="alert warn" style="margin-top:10px"><div class="ic">?</div>
      <div class="txt">${mnoga(bezMasy.length, 'Składnik', 'Składniki', 'Składników')}
      <b>${esc(bezMasy.join(', '))}</b> ${mnoga(bezMasy.length, 'nie ma', 'nie mają', 'nie ma')}
      przelicznika na gramy, więc ${bezMasy.length===1?'stoi':'stoją'} na końcu składu —
      nie dlatego, że ${bezMasy.length===1?'jest go':'jest ich'} najmniej. Masę uzupełnisz
      w Składnikach, w polu <b>gramatura jednostki</b>.</div></div>` : ''}
    <div class="hint" style="margin-top:8px">90 × 130 mm · skład idzie
      <b>malejąco według masy</b> w całym zestawie, każdy składnik raz,
      półprodukty rozłożone na to, z czego są zrobione · blok o alergenach
      i przechowywaniu dokłada się na dole · treść akapitów i listę pomijanych
      zmienisz w <b>Ustawieniach</b>.</div>`;
}

/* ============================================================================
   WIDOK: ZESTAWY
   ========================================================================== */
/* ---------------------------------------------------------------------------
   PODGLĄD POZYCJI
   Rolka i zestaw to dwa różne byty, ale patrzy się na nie tak samo: co to jest,
   z czego się składa, ile kosztuje i ile na tym zostaje. Dlatego oba podglądy
   składa JEDNA funkcja — inaczej po kilku zmianach zakres i kolejność informacji
   rozjechałyby się i przeskakiwanie między listami zaczęłoby męczyć.
   ------------------------------------------------------------------------- */
/** Szkielet podglądu — ten sam dla składnika, półproduktu, rolki i zestawu:
    nazwa i Edytuj, podtytuł, zdjęcie (jeśli jest), dwa kafelki, potem sekcje
    w stałej kolejności. Sekcja, której dla danego bytu nie ma sensu pokazywać,
    po prostu nie wchodzi na listę — reszta zostaje na swoim miejscu. */
function podgladKarta(o){
  return `<div class="card">
    <div class="row" style="justify-content:space-between"><h2>${esc(o.nazwa)}</h2>
      <span class="row" style="gap:6px">${o.akcje || ''}
        <button class="btn sm pri" data-edit-${o.typ}="${esc(o.id)}">Edytuj</button></span></div>
    <div class="hint">${o.podtytul || '&nbsp;'}</div>
    ${o.opis ? `<div class="opis">${esc(o.opis)}</div>` : ''}
    ${o.photo?`<img class="hero" src="${o.photo}" alt="${esc(o.nazwa)}">`:''}
    <div class="tiles" style="grid-template-columns:1fr 1fr;gap:8px;margin-bottom:6px">
      ${o.kafelki.map(k=>`<div class="tile sm">
        <div class="lab">${esc(k.lab)}</div>
        <div class="val"${k.kolor?` style="color:${k.kolor}"`:''}>${k.val}</div>
      </div>`).join('')}
    </div>
    ${o.sekcje.filter(Boolean).map(s=>sekcjaBlok(s.t, s.html)).join('')}
  </div>`;
}

function podgladPozycji(o){
  const c = o.c;
  const kolorFc = c.fc==null ? 'var(--muted)'
    : CALC.status(c.fc)==='crit' ? 'var(--crit-ink)'
    : CALC.status(c.fc)==='warn' ? 'var(--warn-ink)' : 'var(--good-ink)';
  const kv = (l, v, klasa) => `<div class="kv"><span>${l}</span><b${klasa?` class="${klasa}"`:''}>${v}</b></div>`;
  const poz = w => `<div class="kv"><span>${esc(w.n)}${w.opis
      ? ` <span class="mut">${esc(w.opis)}</span>` : ''}</span><b>${zl(w.koszt)}</b></div>`;

  return podgladKarta({
    typ:o.typ, id:o.id, nazwa:o.nazwa, photo:o.photo, opis:o.opis, akcje:o.akcje,
    podtytul: `${o.podtytul} · ${esc(chanLabel(CHAN))} · VAT ${pct(c.vat,0)}`,
    kafelki:[{lab:'Food cost', val:pct(c.fc), kolor:kolorFc},
             {lab:'Marża netto', val:c.margin!=null?zl(c.margin):'—'}],
    sekcje:[
      {t:'Skład', html: (o.sklad.length ? o.sklad.map(g=>`${g.tytul
          ? `<div class="kv" style="border-top:1px solid var(--grid);margin-top:6px;padding-top:9px">
               <span class="mut small">${esc(g.tytul)}</span><b class="mut">${zl(g.suma)}</b></div>`
          : ''}${g.pozycje.map(poz).join('')}`).join('')
        : '<div class="empty">Brak pozycji</div>') + (o.ostrzezenie || '')},
      o.etykieta ? {t:'Etykieta na opakowanie', html:o.etykieta} : null,
      {t:'Koszt i cena', html:`
        <div class="kv" style="border-top:1px solid var(--axis);padding-top:9px">
          <span><b>Koszt razem (netto)</b></span><b>${zl(c.net)}</b></div>
        ${o.wTym ? kv(o.wTym.l, o.wTym.v, o.wTym.mut ? 'mut' : '') : ''}
        ${kv('Koszt 1 kawałka', c.perPiece!=null?zl(c.perPiece):'—')}
        ${kv(`Cena brutto (${esc(chanLabel(CHAN))})`, c.priceGross?zl(c.priceGross):'—')}
        ${kv(`Cena 1 kawałka (${esc(chanLabel(CHAN))})`,
             c.priceGross && c.pieces ? zl(c.priceGross/c.pieces) : '—')}
        ${(o.dodatkowe||[]).map(w=>kv(w.l, w.v, w.mut?'mut':'')).join('')}`},
      {t:'Ceny i food cost w kanałach', html: o.chan +
        (c.missing.length?`<div class="alert crit" style="margin-top:12px"><div class="ic">!</div>
          <div class="txt">Brakujące dane: <b>${esc(c.missing.join(', '))}</b>. Koszt jest zaniżony,
          więc food cost tej pozycji jest za niski — nie wchodzi do średniej.</div></div>`:'')},
      {t:'Rozbicie kosztu', html:`<div id="${o.wykresId}">${o.wykresRows.length
        ? barChartCost(o.wykresRows, 330) : '<div class="empty">Brak pozycji</div>'}</div>`},
      {t:'Wartości odżywcze', html: o.nutr},
      {t:'Gdzie używany', html: o.gdzie || usedByBlock(o.id)},
    ],
  });
}

function setBreakRows(c){
  return c.parts.map(p=>({name:p.name,cost:p.cost}))
    .concat(c.extra.rows.map(r=>({name:r.name,cost:r.cost})))
    .filter(r=>r.cost>0).sort((a,b)=>b.cost-a.cost);
}
function vSets(){
  const sel = SEL.set ? CALC.set(SEL.set) : null;
  const noExtra = active(DB.sets).filter(s=>!(s.comps||[]).length);
  after('sets',()=>{
    document.querySelectorAll('[data-pick-set]').forEach(r=>r.addEventListener('click',e=>{
      if(e.target.closest('button'))return; SEL.set=r.dataset.pickSet; render(); }));
    document.querySelector('[data-act="addSet2"]').addEventListener('click',()=>editSet(null));
    document.querySelector('[data-act="pdfSets"]').addEventListener('click',()=>pdfZestawy());
    document.querySelector('[data-act="etykSets"]').addEventListener('click',
      ()=>pdfEtykiety(active(DB.sets), 'etykiety-zestawow'));
    const et1 = document.querySelector('[data-act="etykSet"]');
    if(et1) et1.addEventListener('click',()=>{ const z=CALC.set(et1.dataset.id);
      if(z) pdfEtykiety([z], 'etykieta-' + plikNazwa(z.name)); });
    document.querySelectorAll('[data-edit-set]').forEach(b=>b.addEventListener('click',()=>editSet(b.dataset.editSet)));
    if(sel){ const c=CALC.setCalc(sel);
      const el=document.getElementById('chSetBreak'); if(el) wireChart(el,setBreakRows(c),r=>`<b>${esc(r.name)}</b>${zl(r.cost)} · ${pct(r.cost/c.net)} kosztu zestawu`);
    }
  });
  DND.sets = (od, doo)=>{ if(przestawPoId(DB.sets, od, doo)){ save(); render(); } };
  const lista = archFilter(DB.sets,'sets');
  const rows=lista.map((s,ix)=>{
    const c=CALC.setCalc(s), st=CALC.status(c.fc);
    const poprz = ix>0 ? lista[ix-1].id : '', nast = ix<lista.length-1 ? lista[ix+1].id : '';
    return `<tr data-pick-set="${s.id}" data-di="${s.id}" ${ORD.sets?'draggable="true"':''}
        style="cursor:${ORD.sets?'grab':'pointer'}" class="${SEL.set===s.id?'sel':''} ${s.archived?'arch':''}">
      <td>${ordCell(DB.sets.indexOf(s)+1, poprz?`${s.id}|${poprz}`:'', nast?`${s.id}|${nast}`:'', ORD.sets)}</td>
      <td><b>${esc(s.name)}</b>${s.archived?' <span class="tag">archiwum</span>':''}${c.missing.length?' <span class="tag crit">braki</span>':''}</td>
      <td class="r num">${c.pieces}</td>
      <td class="r num">${zl(c.net)}</td>
      <td class="r num ${c.packaging?'':'mut'}">${c.packaging?zl(c.packaging):'<span class="tag warn">brak</span>'}</td>
      <td class="r num">${c.priceGross?zl(c.priceGross):'—'}</td>
      <td class="r"><span class="tag ${st==='none'?'':st}">${pct(c.fc)}</span></td>
      <td class="r num">${c.margin!=null?zl(c.margin):'—'}</td>
      <td class="r num mut">${c.discount!=null?pct(c.discount,0):'—'}</td>
      </tr>`;
  }).join('');

  let detail='<div class="card"><div class="empty">Wybierz zestaw, żeby zobaczyć jego skład i rentowność.</div></div>';
  if(sel){
    const c = CALC.setCalc(sel);
    detail = podgladPozycji({
      typ:'set', id:sel.id, nazwa:sel.name, photo:sel.photo, c, opis:sel.opis,
      etykieta: etykPodglad(sel),
      akcje:`<button class="btn sm" data-act="etykSet" data-id="${esc(sel.id)}"
               title="Etykieta tego zestawu, 90 × 130 mm">⎙ Etykieta</button>`,
      podtytul:`${c.pieces} kawałków · ${c.parts.length} rolek`,
      sklad:[
        {tytul:null, pozycje:c.parts.map(p=>({n:p.name, opis:`× ${p.pieces} kaw.`, koszt:p.cost}))},
        ...(c.extra.rows.length ? [{tytul:'Dodatki', suma:c.extra.total,
          pozycje:c.extra.rows.map(r=>({n:r.name,
            opis:`${num(r.qty, r.qty%1?2:0)} ${r.unit||''}`.trim(), koszt:r.cost}))}] : []),
      ],
      ostrzezenie: c.extra.rows.length ? '' :
        `<div class="alert warn" style="margin-top:10px"><div class="ic">?</div>
         <div class="txt">Ten zestaw nie ma żadnych dodatków — <b>tacka, pałeczki, sos, imbir</b>
         nie są policzone, więc food cost jest zaniżony.</div></div>`,
      wTym: {l:'w tym dodatki', v: c.packaging?zl(c.packaging):'—', mut:!c.packaging},
      dodatkowe:[
        {l:`Suma cen à la carte (${esc(chanLabel(CHAN))})`, v: zl(c.alaCarte)},
        {l:'Rabat zestawu', v: c.discount!=null?pct(c.discount,1):'—', mut:true},
      ],
      chan: chanTable(sel, (o,ch)=>CALC.setCalc(o,ch)),
      // zestawu nie ma w żadnej recepturze — „używa" go układ szafek w automatach
      gdzie: (()=>{ const szafki = Object.keys(DB.vending.layout||{})
                      .filter(n=>DB.vending.layout[n]===sel.id)
                      .sort((a,b)=>a-b);
        if(!szafki.length) return '<div class="hint">Nieprzypisany do żadnej szafki — '
          + 'ten zestaw nigdzie nie jedzie. Układ szafek ustawiasz w Automatach.</div>';
        return `<div class="kv"><span>Szafek w automacie</span><b>${szafki.length}</b></div>
          <div class="kv"><span>Numery</span><b>${szafki.join(', ')}</b></div>
          <div class="kv"><span>Na ${active(DB.machines).length} automatów</span>
            <b>${szafki.length * active(DB.machines).length} szt.</b></div>`; })(),
      wykresId:'chSetBreak', wykresRows: setBreakRows(c),
      nutr: nutrBlock(CALC.setNutr(sel), 'cały zestaw'),
    });
  }
  const cards=archFilter(DB.sets,'sets').map(s=>{
    const c=CALC.setCalc(s), st=CALC.status(c.fc);
    return `<div class="card tcard ${SEL.set===s.id?'sel':''} ${s.archived?'arch':''}" data-pick-set="${s.id}">
      ${s.photo?`<img class="hero" src="${s.photo}" alt="${esc(s.name)}">`:''}
      <div class="th"><h3>${esc(s.name)}${s.archived?' <span class="tag">archiwum</span>':''}</h3>
        <span class="tag ${st==='none'?'':st}">${pct(c.fc)}</span></div>
      <div class="hint" style="margin:0 0 8px">${c.pieces} kawałków · ${c.parts.length} rolek${c.missing.length?' · <span class="tag crit">braki</span>':''}</div>
      <div class="kv"><span>Koszt</span><b>${zl(c.net)}</b></div>
      <div class="kv"><span>w tym dodatki</span><b class="${c.packaging?'':'mut'}">${c.packaging?zl(c.packaging):'—'}</b></div>
      <div class="kv"><span>Cena (${esc(chanLabel(CHAN))})</span><b>${c.priceGross?zl(c.priceGross):'<span class="tag warn">brak</span>'}</b></div>
      <div class="kv"><span>Marża netto</span><b>${c.margin!=null?zl(c.margin):'—'}</b></div>
      <div class="kv"><span>Rabat vs à la carte</span><b class="mut">${c.discount!=null?pct(c.discount,0):'—'}</b></div>
      <div class="acts">${rowActions('sets', s)}</div></div>`;
  }).join('');

  return paskListy({tytul:'Zestawy', licznik:`${active(DB.sets).length} aktywnych`,
    klucz:'sets', kanal:true, kolejnosc:true,
    akcje:'<button class="btn" data-act="pdfSets" title="Skład wszystkich zestawów na kartkę">⎙ PDF</button>'
      + '<button class="btn" data-act="etykSets" title="Etykiety na opakowania, 90 × 130 mm — '
      + 'osobny plik PDF na każdy aktywny zestaw, spakowane w ZIP">⎙ Etykiety</button>',
    dodaj:{act:'addSet2', lab:'+ Zestaw'}}) + `
  ${noExtra.length?`<div class="banner"><b>${noExtra.length} z ${DB.sets.length} zestawów nie ma żadnych dodatków.</b>
    Tacka, pałeczki, sos i imbir potrafią dołożyć kilkanaście punktów procentowych food costu — najmocniej przy tanich zestawach.
    Dopiszesz je w edytorze zestawu, w sekcji <b>Dodatki</b>.</div>`:''}
  ${ordHint('sets','zestawów')}
  ${listLayout('sets',
    `<div class="tw"><table data-tbl="sets" ${ORD.sets?'data-no-sort-now':''}>
      <thead><tr><th data-ordth title="Kolejność">#</th><th>Zestaw</th><th class="r">Kaw.</th><th class="r">Koszt</th>
      <th class="r">Dodatki</th><th class="r">Cena</th><th class="r">Food cost</th><th class="r">Marża</th><th class="r">Rabat</th>
      </tr></thead><tbody data-dnd="sets">${rows||'<tr><td colspan="9" class="empty">Brak zestawów</td></tr>'}</tbody></table></div>`,
    cards||'<div class="empty">Brak zestawów</div>',
    detail)}`;
}

function editSet(id){
  const st = id ? clone(CALC.set(id))
    : {id:uid('set'), name:'', entries:[], comps:[], photo:null, opis:'',
       prices:{vending:null, dostawa:null}, vats:Object.assign({}, DB.settings.vats)};
  migrateChannels(st);
  st.comps = st.comps||[];
  delete st.pack;
  const draw=()=>{
    const b1=document.getElementById('setEntries');
    b1.dataset.dnd = 'setEntries';
    b1.innerHTML = st.entries.map((e,i)=>{
      const it=CALC.item(e.itemId);
      const per = it? CALC.itemCalc(it).perPiece : 0;
      return `<div class="compline ord ${e.itemId?'':'pusty'}" data-di="${i}" draggable="true">
        ${ordCell(i+1, i>0?`${i}|${i-1}`:'', i<st.entries.length-1?`${i}|${i+1}`:'', true)}
        <div>${combo('sE'+i, 'Szukaj rolki…')}${
          e.itemId && !it ? ' <span class="tag crit">brak w bazie</span>':''}</div>
        <input type="number" step="1" value="${e.pieces??''}" data-e="${i}" placeholder="kaw.">
        <span class="mut small">kaw.</span>
        <span class="cost">${zl(per*(e.pieces||0))}</span>
        <button type="button" class="btn sm danger" data-rme="${i}">✕</button></div>`;
    }).join('') || '<div class="empty" style="padding:14px">Brak rolek — kliknij „+ Dodaj rolkę”</div>';
    const usedIt = new Set(st.entries.map(x=>x.itemId));
    const opcjeRolek = [PUSTY_WYBOR, ...DB.items.filter(i=>!i.archived||usedIt.has(i.id))
      .map(i=>({v:i.id, l:itName(i)}))];
    st.entries.forEach((e,i)=>fillCombo('sE'+i, opcjeRolek, e.itemId||'',
      v=>{ e.itemId=v; setTimeout(draw,0); }));
    b1.querySelectorAll('[data-e]').forEach(inp=>inp.addEventListener('input',()=>{ st.entries[+inp.dataset.e].pieces=parseInt(inp.value)||0; recalc(); }));
    b1.querySelectorAll('[data-rme]').forEach(x=>x.addEventListener('click',()=>{ st.entries.splice(+x.dataset.rme,1); draw(); }));
    wireDnd(b1.parentElement, (od,doo)=>{ if(przestawIndeks(st.entries, od, doo)) draw(); });

    const b2=document.getElementById('setComps');
    b2.dataset.dnd = 'setComps';
    b2.innerHTML = st.comps.map((c,i)=>{
      const info = c.refId ? CALC.compInfo(c.refId) : {name:'', unit:'', unitCost:null};
      return `<div class="compline ord ${c.refId?'':'pusty'}" data-di="${i}" draggable="true">
        ${ordCell(i+1, i>0?`${i}|${i-1}`:'', i<st.comps.length-1?`${i}|${i+1}`:'', true)}
        <div>${combo('sC'+i, 'Szukaj dodatku…')}${
          c.refId && info.unitCost==null?' <span class="tag crit">brak ceny</span>':''}</div>
        <input type="number" step="any" value="${c.qty??''}" data-c="${i}" placeholder="ilość">
        <span class="mut small">${esc(info.unit||'')}</span>
        <span class="cost">${zl((c.qty||0)*(info.unitCost||0))}</span>
        <button type="button" class="btn sm danger" data-rmc="${i}">✕</button></div>`;
    }).join('') || '<div class="empty" style="padding:14px">Brak dodatków — kliknij „+ Dodaj dodatek”</div>';
    const usedC2 = new Set(st.comps.map(c=>c.refId));
    const opcjeDod = [PUSTY_WYBOR,
      ...DB.ingredients.filter(g=>!g.archived||usedC2.has(g.id)).map(g=>{
        const uc = CALC.ingUnitCost(g.id);
        return {v:g.id, l:`${g.name} — ${g.cat}${uc!=null?' · '+num(uc,4)+'/'+g.unit:' · brak ceny'}`}; }),
      ...DB.preps.filter(p=>!p.archived||usedC2.has(p.id)).map(p=>({v:p.id, l:`◍ ${p.name}`}))];
    st.comps.forEach((c,i)=>fillCombo('sC'+i, opcjeDod, c.refId||'',
      v=>{ c.refId=v; setTimeout(draw,0); }));
    b2.querySelectorAll('[data-c]').forEach(inp=>inp.addEventListener('input',()=>{ st.comps[+inp.dataset.c].qty=parseFloat(inp.value)||0; recalc(); }));
    b2.querySelectorAll('[data-rmc]').forEach(x=>x.addEventListener('click',()=>{ st.comps.splice(+x.dataset.rmc,1); draw(); }));
    wireDnd(b2.parentElement, (od,doo)=>{ if(przestawIndeks(st.comps, od, doo)) draw(); });
    recalc();
  };
  const recalc=()=>{
    CHANNELS.forEach(ch=>{ st.prices[ch.k]=numOrNull('sP_'+ch.k);
                           st.vats[ch.k]=(numOrNull('sV_'+ch.k)??(ch.vat*100))/100; });
    const c=CALC.setCalc(st);
    document.getElementById('sExtraTot').textContent = zl(c.extra.total);
    document.querySelectorAll('#setEntries .compline').forEach((el,i)=>{
      const it=CALC.item(st.entries[i].itemId); const per=it?CALC.itemCalc(it).perPiece:0;
      el.querySelector('.cost').textContent=zl(per*(st.entries[i].pieces||0)); });
    document.querySelectorAll('#setComps .compline').forEach((el,i)=>{
      const info=CALC.compInfo(st.comps[i].refId);
      el.querySelector('.cost').textContent=zl((st.comps[i].qty||0)*(info.unitCost||0)); });
    document.getElementById('sNet').textContent=zl(c.net);
    document.getElementById('sPieces').textContent=c.pieces+' kaw.';
    document.getElementById('sFc').textContent=pct(c.fc);
    document.getElementById('sFc').style.color=c.fc==null?'':CALC.status(c.fc)==='crit'?'var(--crit-ink)':CALC.status(c.fc)==='warn'?'var(--warn-ink)':'var(--good-ink)';
    document.getElementById('sMar').textContent=c.margin!=null?zl(c.margin):'—';
    document.getElementById('sSug').textContent=c.suggested?zl(c.suggested):'—';
    document.getElementById('sAla').textContent=zl(c.alaCarte)+(c.discount!=null?' (rabat '+pct(c.discount,0)+')':'');
  };
  openDlg(id?'Edytuj zestaw':'Nowy zestaw',`
    <div class="grid" style="grid-template-columns:2fr 1fr 1fr">
      <div><label class="f">Nazwa</label><input id="sName" type="text" value="${esc(st.name)}"></div>
      ${CHANNELS.map(ch=>`
      <div><label class="f">${esc(ch.l)} — cena brutto</label>
        <input id="sP_${ch.k}" type="number" step="any" value="${st.prices[ch.k]??''}"></div>
      <div><label class="f">${esc(ch.l)} — VAT %</label>
        <input id="sV_${ch.k}" type="number" step="any" value="${num((st.vats[ch.k]??ch.vat)*100,0)}"></div>`).join('')}
    </div>
    <div style="margin-top:12px">
      <label class="f">Opis zestawu</label>
      <textarea id="sOpis" rows="3" maxlength="${OPIS_MAX}"
        placeholder="Co jest w zestawie i dla kogo — tekst, który zobaczysz w panelu."
        >${esc(st.opis || '')}</textarea>
      <div class="hint" id="sOpisLicz" style="margin-top:4px"></div>
    </div>
    <div style="margin-top:14px">${photoField('sPhoto','sPhotoIn','Zdjęcie zestawu')}</div>
    <h3 style="margin:16px 0 8px">Rolki w zestawie</h3>
    <div id="setEntries"></div>
    <div class="row" style="margin-top:8px">
      <button type="button" class="btn sm" id="sAddBtn">+ Dodaj rolkę</button></div>
    <h3 style="margin:18px 0 8px">Dodatki</h3>
    <div class="hint" style="margin-bottom:8px">Wszystko poza rolkami: tacka, pałeczki, sos w saszetce, imbir, wasabi, opłata SUP, serwetki.</div>
    <div id="setComps"></div>
    <div class="row" style="margin-top:8px">
      <button type="button" class="btn sm" id="sAddCBtn">+ Dodaj dodatek</button></div>
    <div class="kv" style="margin-top:4px"><span class="small mut">Koszt dodatków</span><b id="sExtraTot">—</b></div>
    <div class="card" style="background:var(--surface-2);border:0;margin-top:14px">
      <div class="kv"><span>Koszt zestawu</span><b id="sNet">—</b></div>
      <div class="kv"><span>Kawałków</span><b id="sPieces">—</b></div>
      <div class="kv"><span>Food cost</span><b id="sFc">—</b></div>
      <div class="kv"><span>Marża netto</span><b id="sMar">—</b></div>
      <div class="kv"><span>Suma cen à la carte</span><b id="sAla">—</b></div>
      <div class="kv"><span>Sugerowana cena przy ${pct(DB.settings.targetFc,0)}</span><b id="sSug" class="wylicz">—</b></div>
    </div>
    ${strefaRyzykowna(id ? st : null, 'sets')}`,
    [ {label:'Anuluj'},
      {label:'Zapisz',cls:'pri',fn:()=>{
        st.name=val('sName').trim();
        // `maxlength` pilnuje pisania i wklejania, ale przycięcie przy zapisie kosztuje
        // jedną linijkę i domyka sprawę także wtedy, gdy tekst wejdzie inną drogą.
        st.opis=val('sOpis').trim().slice(0, OPIS_MAX);
        recalc();
        if(!st.name){ alert('Podaj nazwę.'); return false; }
        if(id){ const i=DB.sets.findIndex(x=>x.id===id); DB.sets[i]=st; } else { DB.sets.push(st); SEL.set=st.id; }
        save(); render();
      }}],
    ()=>{
      wireStrefa('sets', id, ()=>{ if(SEL.set===id) SEL.set=null; });
      document.getElementById('sAddBtn').addEventListener('click',()=>{
        st.entries.push({itemId:'', pieces:null}); draw();
        const q=document.getElementById('sE'+(st.entries.length-1)+'_q'); if(q) q.focus(); });
      document.getElementById('sAddCBtn').addEventListener('click',()=>{
        st.comps.push({refId:'', qty:null}); draw();
        const q=document.getElementById('sC'+(st.comps.length-1)+'_q'); if(q) q.focus(); });
      CHANNELS.flatMap(ch=>['sP_'+ch.k,'sV_'+ch.k])
        .forEach(i=>document.getElementById(i).addEventListener('input',recalc));
      wirePhoto('sPhoto','sPhotoIn',st);
      licznikZnakow('sOpis', 'sOpisLicz', OPIS_MAX);
      draw();
    });
}


/* ============================================================================
   WIDOK: AUTOMATY VENDINGOWE
   ========================================================================== */
function vVend(){
  const V = DB.vending;
  const maszyny = archFilter(DB.machines,'mach');
  const czynne = active(DB.machines).length;
  const sel = SEL.mach ? DB.machines.find(m=>m.id===SEL.mach) : null;

  // co siedzi w szafkach — liczone zawsze w kanale Vending
  const szafki = [];
  for(let n=1;n<=V.slots;n++){
    const s = slotSet(n);
    szafki.push({n, s, c: s ? CALC.setCalc(s,'vending') : null});
  }
  const pelne = szafki.filter(x=>x.s);
  const wartosc = pelne.reduce((a,x)=>a+(x.c.priceGross||0),0);
  const koszt   = pelne.reduce((a,x)=>a+x.c.net,0);
  const netto   = pelne.reduce((a,x)=>a+(x.c.priceNet||0),0);
  const fcAvg   = netto>0 ? koszt/netto : null;
  const braki   = szafki.filter(x=>!x.s).map(x=>x.n);

  // ile sztuk każdego zestawu w jednym automacie
  const zliczone = {};
  pelne.forEach(x=>{ zliczone[x.s.id] = (zliczone[x.s.id]||0)+1; });
  const podsum = Object.keys(zliczone).map(id=>{
    const s = CALC.set(id), c = CALC.setCalc(s,'vending'), n = zliczone[id];
    return {s, n, koszt:c.net*n, wartosc:(c.priceGross||0)*n, fc:c.fc};
  }).sort((a,b)=>b.n-a.n);

  after('vend',()=>{
    document.querySelector('[data-act="addMach"]').addEventListener('click',()=>editMach(null));
    document.querySelectorAll('[data-edit-mach]').forEach(b=>b.addEventListener('click',()=>editMach(b.dataset.editMach)));
    document.querySelectorAll('[data-pick-mach]').forEach(r=>r.addEventListener('click',e=>{
      if(e.target.closest('button')||e.target.closest('a'))return; SEL.mach=r.dataset.pickMach; render(); }));
    const opcje = [{v:'', l:'— pusta szafka —', pin:true},
      ...active(DB.sets).map(s=>{ const c=CALC.setCalc(s,'vending');
        return {v:s.id, l:`${s.name} · ${c.priceGross?zl(c.priceGross):'brak ceny'}`}; })];
    for(let n=1;n<=V.slots;n++){
      fillCombo('slot'+n, opcje, V.layout[String(n)]||'',
        v=>{ if(!canEdit()) return;
             if(v) V.layout[String(n)]=v; else delete V.layout[String(n)];
             save(); render(); });
    }
    const wy=document.getElementById('vendClear');
    if(wy) wy.addEventListener('click',()=>{
      if(!confirm('Wyczyścić przypisanie wszystkich '+V.slots+' szafek?')) return;
      V.layout={}; save(); render();
    });
  });

  const kolumna = (od, doo) => `
    <div><div class="hint" style="margin-bottom:8px"><b>Kolumna ${od===1?1:2}</b> · szafki ${od}–${doo}</div>
    ${szafki.filter(x=>x.n>=od&&x.n<=doo).map(x=>`
      <div class="lock ${x.s?'':'pusta'}">
        <div class="no">${x.n}</div>
        ${combo('slot'+x.n, 'Wybierz zestaw…')}
        <div class="num">${x.c&&x.c.priceGross?zl(x.c.priceGross):'<span class="mut">—</span>'}</div>
        <div class="num mut">${x.c?zl(x.c.net):'—'}</div>
        <div class="num">${x.c?`<span class="tag ${CALC.status(x.c.fc)==='none'?'':CALC.status(x.c.fc)}">${pct(x.c.fc,0)}</span>`:''}</div>
      </div>`).join('')}</div>`;

  const rows = maszyny.map(m=>`
    <tr data-pick-mach="${m.id}" style="cursor:pointer" class="${SEL.mach===m.id?'sel':''} ${m.archived?'arch':''}">
      <td>${esc(m.code||'—')}</td>
      <td><b>${esc(m.name)}</b>${m.archived?' <span class="tag">archiwum</span>':''}</td>
      <td class="mut small">${esc(m.addr||'')}</td>
      <td class="mut small">${m.serial ? esc(m.serial)
        : '<span title="Bez numeru nie rozpoznamy sprzedaży z tego automatu">—</span>'}</td>
      <td class="mut small">${esc(m.note||'')}</td>
      </tr>`).join('');

  const cards = maszyny.map(m=>`
    <div class="card tcard ${SEL.mach===m.id?'sel':''} ${m.archived?'arch':''}" data-pick-mach="${m.id}">
      <div class="th"><h3>${esc(m.name)}${m.archived?' <span class="tag">archiwum</span>':''}</h3></div>
      <div class="hint" style="margin:0 0 8px">${esc(m.addr||'')}</div>
      ${m.note?`<div class="kv"><span class="mut small">${esc(m.note)}</span><b></b></div>`:''}
      <div class="acts">${rowActions('mach', m)}</div></div>`).join('');

  let detail='<div class="card"><div class="empty">Wybierz automat, żeby zobaczyć szczegóły.</div></div>';
  if(sel){
    detail=`<div class="card">
      <div class="row" style="justify-content:space-between"><h2>${esc(sel.name)}</h2>
        <button class="btn sm pri" data-edit-mach="${sel.id}">Edytuj</button></div>
      <div class="hint">${esc(sel.addr||'')}</div>
      <div class="tiles" style="grid-template-columns:1fr;gap:8px;margin:12px 0">
        <div class="tile" style="padding:10px 12px"><div class="lab">Kod automatu</div>
          <div class="val num" style="font-size:28px;letter-spacing:.06em">${esc(sel.code||'—')}</div>
          <div class="sub2">identyfikuje maszynę na stronie załadunku i w wersji mobilnej</div></div>
      </div>
      ${sel.note?`<div class="kv"><span>Notatka</span><b class="mut">${esc(sel.note)}</b></div>`:''}
      <div class="kv"><span>Szafek</span><b>${V.slots} (2 × ${V.perCol})</b></div>
      <div class="hint" style="margin-top:10px">Układ szafek, wartość i koszt załadunku są wspólne
        dla wszystkich automatów — liczby znajdziesz nad układem.</div>
    </div>`;
  }

  return paskListy({tytul:'Automaty', licznik:`${czynne} czynnych · ${czynne*V.slots} szafek razem`,
    klucz:'mach', dodaj:{act:'addMach', lab:'+ Automat'}}) + `

  <div class="banner"><b>Wszystkie automaty mają ten sam układ szafek.</b>
    Dwie kolumny po ${V.perCol}: szafki 1–${V.perCol} i ${V.perCol+1}–${V.slots}.
    Zmiana przypisania działa od razu na wszystkich ${czynne} maszynach.
    Ceny i food cost liczone są w kanale <b>Vending</b>, niezależnie od przełącznika w innych widokach.</div>

  <div class="tiles" style="margin-bottom:12px">
    <div class="tile"><div class="lab">Zapełnionych szafek</div>
      <div class="val num">${pelne.length} / ${V.slots}</div>
      <div class="sub2">${braki.length?('puste: '+braki.join(', ')):'komplet'}</div></div>
    <div class="tile"><div class="lab">Wartość jednego automatu</div>
      <div class="val num">${zl(wartosc)}</div><div class="sub2">brutto, ceny vendingowe</div></div>
    <div class="tile"><div class="lab">Koszt jednego załadunku</div>
      <div class="val num">${zl(koszt)}</div><div class="sub2">netto, same składniki</div></div>
    <div class="tile"><div class="lab">Food cost załadunku</div>
      <div class="val num" style="color:${fcAvg==null?'var(--muted)':CALC.status(fcAvg)==='crit'?'var(--crit-ink)':CALC.status(fcAvg)==='warn'?'var(--warn-ink)':'var(--good-ink)'}">${pct(fcAvg)}</div>
      <div class="sub2">ważony wartością</div></div>
    <div class="tile"><div class="lab">Wszystkie ${czynne} automaty</div>
      <div class="val num">${zl(wartosc*czynne)}</div><div class="sub2">koszt ${zl(koszt*czynne)}</div></div>
  </div>

  <div class="card" style="margin-bottom:12px">
    <div class="row" style="justify-content:space-between;margin-bottom:12px">
      <h2 style="margin:0">Układ szafek</h2>
      <button class="btn sm" id="vendClear">Wyczyść wszystkie</button></div>
    <div class="lockers">${kolumna(1,V.perCol)}${kolumna(V.perCol+1,V.slots)}</div>
  </div>

  ${podsum.length?`<div class="card" style="margin-bottom:12px">
    <h2 style="margin:0 0 10px">Zestawy w jednym automacie</h2>
    <div class="tw"><table data-tbl="vendsum"><thead><tr><th>Zestaw</th><th class="r">Szafek</th>
      <th class="r">Wartość</th><th class="r">Koszt</th><th class="r">Food cost</th>
      <th class="r">Na ${czynne} automatów</th></tr></thead><tbody>
      ${podsum.map(r=>`<tr><td>${esc(r.s.name)}</td><td class="r num">${r.n}</td>
        <td class="r num">${zl(r.wartosc)}</td><td class="r num mut">${zl(r.koszt)}</td>
        <td class="r"><span class="tag ${CALC.status(r.fc)==='none'?'':CALC.status(r.fc)}">${pct(r.fc)}</span></td>
        <td class="r num">${r.n*czynne} szt · ${zl(r.wartosc*czynne)}</td></tr>`).join('')}
    </tbody></table></div></div>`:''}

  <h2 style="margin:18px 0 10px">Lista automatów</h2>
  ${listLayout('mach',
    `<div class="tw"><table data-tbl="mach"><thead><tr><th>Kod</th><th>Automat</th><th>Adres</th>
      <th title="Numer, którym automat podpisuje się w mailu o sprzedaży">Nr seryjny</th><th>Notatka</th>
      </tr></thead><tbody>${rows||'<tr><td colspan="5" class="empty">Brak automatów</td></tr>'}</tbody></table></div>`,
    cards||'<div class="empty">Brak automatów</div>',
    detail)}`;
}

function editMach(id){
  const m = id ? clone(DB.machines.find(x=>x.id===id)) : {id:uid('aut'), name:'', addr:'', note:''};
  openDlg(id?'Edytuj automat':'Nowy automat',`
    <div class="grid">
      <div><label class="f">Kod</label>
        <input id="mCode" type="text" value="${esc(m.code||'')}" maxlength="12"
               style="text-transform:uppercase;letter-spacing:.06em;font-weight:600"
               placeholder="np. ZAB albo KAU GAL">
        <div class="small mut" style="margin-top:5px">Krótki, unikalny. Po nim rozpoznasz automat
          na stronie załadunku, w telefonie i na wydruku Pakowania. <b>Spacja jest dozwolona</b> —
          przy dwóch automatach tej samej sieci „KAU GAL" i „KAU NOR" czyta się lepiej niż „KA2".</div></div>
      <div><label class="f">Nazwa</label><input id="mName" type="text" value="${esc(m.name)}"></div>
      <div><label class="f">Adres</label><input id="mAddr" type="text" value="${esc(m.addr||'')}"></div>
      <div style="grid-column:1/-1"><label class="f">Numer seryjny</label>
        <input id="mSerial" type="text" value="${esc(m.serial||'')}" maxlength="32"
               style="letter-spacing:.04em;font-weight:600" placeholder="np. SM-0241-26">
        <div class="small mut" style="margin-top:5px">Numer, którym automat podpisuje się
          w mailu o sprzedaży — stoi w temacie, zaraz po słowie „MultiVend". Po nim aplikacja
          rozpozna, z którego automatu przyszła sprzedaż. Adresu z tematu do tego nie użyjemy:
          to napis od operatora, a jedna literówka po jego stronie przypisałaby sprzedaż
          w niewłaściwe miejsce, po cichu.</div></div>
      <div><label class="f">Notatka</label><input id="mNote" type="text" value="${esc(m.note||'')}"
        placeholder="np. godziny dostępu, kontakt do obsługi obiektu"></div>
      <div><label class="f">Kolor na wykresach</label>
        <input id="mKolor" type="color" class="kolorpole-auto"
               value="${esc(m.kolor || kolorAutomatu(m, Math.max(0, active(DB.machines).indexOf(m))))}">
        <div class="small mut" style="margin-top:5px">Tym kolorem automat rysuje się na
          wykresach sprzedaży. Pole pokazuje kolor, który ma teraz — także wtedy, gdy nikt go
          jeszcze nie wybierał i przyszedł z palety.</div></div>
    </div>
    <div class="hint" style="margin-top:10px">Układ szafek jest wspólny dla wszystkich automatów — ustawiasz go raz, wyżej.</div>
    ${strefaRyzykowna(id ? m : null, 'mach')}`,
    [ {label:'Anuluj'},
      {label:'Zapisz',cls:'pri',fn:()=>{
        m.name=val('mName').trim(); m.addr=val('mAddr').trim(); m.note=val('mNote').trim();
        // spacja wolno, ale jedna i nie na brzegach — inaczej „ZAB " i „ZAB" byłyby
        // dwoma różnymi kodami, których nikt nie odróżni wzrokiem
        m.code=val('mCode').replace(/\s+/g,' ').trim().toUpperCase();
        // Numer seryjny bez spacji i wersalikami — w mailu stoi jako „SM-0241-26", a wpisany
        // z małej albo ze spacją nie dopasowałby się do niczego i nikt by nie wiedział czemu.
        m.serial=val('mSerial').replace(/\s+/g,'').trim().toUpperCase() || null;
        m.kolor=val('mKolor') || null;
        if(!m.name){ alert('Podaj nazwę automatu.'); return false; }
        if(!m.code){ alert('Podaj kod automatu — bez niego nie rozpoznasz go na stronie załadunku.'); return false; }
        const kolizja = DB.machines.find(x=>x.id!==m.id && (x.code||'').toUpperCase()===m.code);
        if(kolizja){ alert('Kod „'+m.code+'” ma już automat „'+kolizja.name+'”. Kody muszą być unikalne.'); return false; }
        // Dwa automaty z tym samym numerem seryjnym znaczyłyby, że sprzedaż nie ma jak
        // trafić do właściwego — a to jest cichy błąd, więc łapiemy go przy wpisywaniu.
        if(m.serial){
          const dubel = DB.machines.find(x=>x.id!==m.id && (x.serial||'') === m.serial);
          if(dubel){ alert('Numer „'+m.serial+'” ma już automat „'+dubel.name
            +'”. Po numerze seryjnym rozpoznajemy sprzedaż, więc musi być unikalny.'); return false; }
        }
        if(id){ const i=DB.machines.findIndex(x=>x.id===id); DB.machines[i]=m; }
        else { DB.machines.push(m); SEL.mach=m.id; }
        save(); render();
      }}],
    ()=>wireStrefa('mach', id, ()=>{ if(SEL.mach===id) SEL.mach=null; }));
}


/* ============================================================================
   WIDOK: ZAŁADUNKI
   Jeden załadunek to nazwany plan obejmujący wszystkie automaty naraz.
   Zielona szafka jedzie w trasę, czerwona zostaje.
   ========================================================================== */
function vLoad(){
  const lista = archFilter(DB.loads,'load');
  const sel = SEL.load ? DB.loads.find(z=>z.id===SEL.load) : null;
  const maszyny = active(DB.machines);
  const V = DB.vending;

  after('load',()=>{
    if(!sel){
      const opcje = [{v:'', l:'— brak —', pin:true},
        ...active(DB.loads).map(z=>({v:z.id, l:z.name}))];
      DNI.forEach(d=>fillCombo('dz_'+d.k, opcje, (DB.week||{})[d.k]||'',
        v=>{ if(!canEdit()) return; ustawDzien(d.k, v); save(); render(); }));
    }
    document.querySelector('[data-act="addLoad"]').addEventListener('click',()=>editLoad(null));
    document.querySelectorAll('[data-edit-load]').forEach(b=>b.addEventListener('click',()=>editLoad(b.dataset.editLoad)));
    document.querySelectorAll('[data-pick-load]').forEach(r=>r.addEventListener('click',e=>{
      if(e.target.closest('button')||e.target.closest('a'))return;
      // Wybór załadunku podmienia CAŁY ekran (siatka szafek i rozpiska zamiast listy),
      // więc to zejście głębiej, a nie zaznaczenie wiersza — i „wstecz" ma z niego wracać.
      SEL.load = r.dataset.pickLoad; zapiszHistorie(true); render(); }));
    document.querySelectorAll('[data-slot]').forEach(b=>b.addEventListener('click',()=>{
      if(!canEdit() || !sel) return;
      const [mid, n] = b.dataset.slot.split('|');
      setSlotOn(sel, mid, n, !slotOn(sel, mid, n));
      save(); render();
    }));
    document.querySelectorAll('[data-mach-all]').forEach(b=>b.addEventListener('click',()=>{
      if(!canEdit() || !sel) return;
      const [mid, tryb] = b.dataset.machAll.split('|');
      for(let n=1;n<=V.slots;n++)
        setSlotOn(sel, mid, n, tryb==='on' && !!DB.vending.layout[String(n)]);
      save(); render();
    }));
    const wsz=document.getElementById('zalAll'), zad=document.getElementById('zalNone');
    if(wsz) wsz.addEventListener('click',()=>{ maszyny.forEach(m=>{
      for(let n=1;n<=V.slots;n++) setSlotOn(sel,m.id,n,!!DB.vending.layout[String(n)]); }); save(); render(); });
    if(zad) zad.addEventListener('click',()=>{ maszyny.forEach(m=>{
      for(let n=1;n<=V.slots;n++) setSlotOn(sel,m.id,n,false); }); save(); render(); });
  });

  const rows = lista.map(z=>{
    const s = zalSuma(z);
    return `<tr data-pick-load="${z.id}" style="cursor:pointer" class="${SEL.load===z.id?'sel':''} ${z.archived?'arch':''}">
      <td><b>${esc(z.name)}</b>${z.archived?' <span class="tag">archiwum</span>':''}</td>
      <td>${dniZaladunku(z).length?esc(dniLabel(dniZaladunku(z)))
        :'<span class="mut small">—</span>'}</td>
      <td class="r num">${s.szt}</td>
      <td class="r num">${zl(s.wartosc)}</td>
      <td class="r num mut">${zl(s.koszt)}</td>
      </tr>`;
  }).join('');

  const cards = lista.map(z=>{
    const s = zalSuma(z);
    return `<div class="card tcard ${SEL.load===z.id?'sel':''} ${z.archived?'arch':''}" data-pick-load="${z.id}">
      <div class="th"><h3>${esc(z.name)}${z.archived?' <span class="tag">archiwum</span>':''}</h3>
        ${dniZaladunku(z).length?`<b>${esc(dniLabel(dniZaladunku(z)))}</b>`:''}</div>
      <div class="kv"><span>Szafek do załadowania</span><b>${s.szt}</b></div>
      <div class="kv"><span>Wartość</span><b>${zl(s.wartosc)}</b></div>
      <div class="kv"><span>Koszt netto</span><b class="mut">${zl(s.koszt)}</b></div>
      <div class="acts">${rowActions('load', z)}</div></div>`;
  }).join('');

  if(!sel){
    return paskListy({tytul:'Załadunki', licznik:`${active(DB.loads).length} zaplanowanych`,
      klucz:'load', dodaj:{act:'addLoad', lab:'+ Załadunek'}}) + `
    <div class="banner">Załadunek to nazwany plan obejmujący <b>wszystkie ${maszyny.length} automaty naraz</b>.
      Przy każdej szafce decydujesz, czy jedzie w trasę. Załadunki standardowe przypisujesz
      do dni tygodnia — <b>każdy dzień może należeć tylko do jednego</b>.</div>

    <div class="card" style="margin-bottom:12px">
      <h2 style="margin:0 0 4px">Tydzień</h2>
      <div class="hint" style="margin-bottom:12px">Wybierz, który załadunek jedzie w dany dzień.
        Jeden dzień to jeden załadunek — przypisanie go tutaj zabiera go z poprzedniego dnia sam z siebie.</div>
      <div class="tiles" style="grid-template-columns:repeat(7,1fr);gap:8px">
        ${DNI.map(d=>{ const z=zaladunekNaDzien(d.k);
          return `<div class="tile" style="padding:10px 8px;${z?'':'border-style:dashed'}">
            <div class="lab">${esc(d.pl)}</div>
            <div style="margin:6px 0 4px">${combo('dz_'+d.k,'— brak —')}</div>
            <div class="sub2">${z?`${zalSuma(z).szt} szafek · ${zl(zalSuma(z).wartosc)}`:'wolny'}</div>
          </div>`; }).join('')}
      </div>
      ${DNI.filter(d=>!zaladunekNaDzien(d.k)).length
        ? `<div class="hint" style="margin-top:10px">Bez załadunku:
            <b>${DNI.filter(d=>!zaladunekNaDzien(d.k)).map(d=>d.pl).join(', ')}</b>.</div>`
        : '<div class="hint" style="margin-top:10px">Każdy dzień tygodnia ma swój załadunek.</div>'}
    </div>
    ${VMODE.load==='cards'
      ? `<div class="tiles-grid" style="margin-bottom:12px">${cards||'<div class="empty">Brak załadunków — utwórz pierwszy.</div>'}</div>`
      : `<div class="tw" style="margin-bottom:12px"><table data-tbl="load"><thead><tr><th>Nazwa</th><th>Dni</th><th class="r">Szafek</th>
          <th class="r">Wartość</th><th class="r">Koszt</th></tr></thead>
          <tbody>${rows||'<tr><td colspan="5" class="empty">Brak załadunków</td></tr>'}</tbody></table></div>`}
    ${tabeleTygodnia()}`;
  }

  // --- wybrany załadunek: siatka wszystkich automatów ---
  const ogolem = zalSuma(sel);
  const kolumna = (m, od, doo) => `<div>${Array.from({length:doo-od+1},(_,i)=>od+i).map(n=>{
    const s = slotSet(n), on = slotOn(sel, m.id, n);
    const klasa = !s ? 'pusty' : (on ? 'pelny' : 'wylaczony');
    return `<button type="button" class="slot ${klasa}" style="margin-bottom:8px"
        ${s?`data-slot="${m.id}|${n}"`:''} title="${s?esc(s.name):'szafka bez przypisanego zestawu'}">
      <span class="nr">${n}</span>
      <span class="nm">${s?esc(s.name):'—'}</span>
    </button>`;
  }).join('')}</div>`;

  const pelny = pelnyAutomat();
  const kafleAutomatow = maszyny.map(m=>{
    const s = zalSuma(sel, m.id);
    const proc = pelny.wartosc>0 ? s.wartosc/pelny.wartosc : null;
    return `<div class="card" style="padding:12px">
      <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:10px">
        <div><b>${esc(m.name)}</b>
          <div class="hint" style="margin:2px 0 0">${s.szt} z ${pelny.szt} szafek · ${zl(s.wartosc)}
            <b style="color:${proc==null?'var(--muted)':proc>=0.999?'var(--good-ink)':proc>=0.5?'var(--ink-2)':'var(--warn-ink)'}"
               title="udział w wartości pełnego załadunku (${zl(pelny.wartosc)})">${proc==null?'—':pct(proc,0)}</b>
            pełnego</div></div>
        <div class="row" style="gap:4px">
          <button class="btn sm" data-mach-all="${m.id}|on" title="Zaznacz wszystkie szafki">✓</button>
          <button class="btn sm" data-mach-all="${m.id}|off" title="Odznacz wszystkie szafki">✕</button>
        </div></div>
      <div class="zal-cols">${kolumna(m,1,V.perCol)}${kolumna(m,V.perCol+1,V.slots)}</div>
    </div>`;
  }).join('');


  return `<div class="topbar"><h1>${esc(sel.name)}</h1>
    <span class="sub">${dniZaladunku(sel).length?esc(dniLabel(dniZaladunku(sel))):'nieprzypisany do żadnego dnia'}</span>
    <div class="spacer"></div>
    <button class="btn" data-edit-load="${sel.id}">Edytuj</button>
    <button class="btn" id="zalAll">Zaznacz wszystko</button>
    <button class="btn" id="zalNone">Odznacz wszystko</button>
    <button class="btn pri" data-act="addLoad">+ Załadunek</button></div>

  <div class="row" style="margin-bottom:12px">
    ${sel.note?`<span class="mut small">${esc(sel.note)}</span>`:''}
    <div class="spacer"></div>
    <span class="mut small">Wydruki:</span>
    ${[['dPrep','Przygotowanie'],['dRolki','Rolki'],['dZest','Zestawy'],['dPack','Pakowanie']]
      .map(([k,n])=>`<button class="btn sm" data-pdf="${k}|${sel.id}"
        title="Kartka dla załadunku „${esc(sel.name)}”">⎙ ${n}</button>`).join('')}</div>

  <div class="tiles" style="margin-bottom:12px">
    <div class="tile"><div class="lab">Szafek do załadowania</div>
      <div class="val num">${ogolem.szt}</div><div class="sub2">z ${maszyny.length*V.slots} możliwych</div></div>
    <div class="tile"><div class="lab">Wartość załadunku</div>
      <div class="val num">${zl(ogolem.wartosc)}</div><div class="sub2">brutto, ceny vendingowe</div></div>
    <div class="tile"><div class="lab">Koszt wytworzenia</div>
      <div class="val num">${zl(ogolem.koszt)}</div><div class="sub2">netto, same składniki</div></div>
    <div class="tile"><div class="lab">Zestawów do zrobienia</div>
      <div class="val num">${ogolem.szt}</div>
      <div class="sub2">${Object.keys(ogolem.wgZestawu).length} rodzajów</div></div>
  </div>

  <div class="zal-grid" style="margin-bottom:18px">${kafleAutomatow||'<div class="empty">Brak czynnych automatów.</div>'}</div>

  ${rozpiskaHtml(sel)}`;
}

function editLoad(id){
  const z = id ? clone(DB.loads.find(x=>x.id===id)) : nowyZaladunek('');
  openDlg(id?'Edytuj załadunek':'Nowy załadunek',`
    <div class="grid">
      <div><label class="f">Nazwa</label><input id="zName" type="text" value="${esc(z.name)}"
        placeholder="np. Dni robocze, Weekend"></div>
      <div><label class="f">Notatka</label>
        <input id="zNote" type="text" value="${esc(z.note||'')}" placeholder="np. kto jedzie, kolejność objazdu"></div>
    </div>
    <div class="hint" style="margin-top:10px">${id
      ? 'Dni tygodnia przypisujesz w planie tygodnia, na liście załadunków.'
      : 'Na start zaznaczone będą wszystkie szafki, które mają przypisany zestaw. Odznaczysz je klikając w siatce.'}</div>
    ${strefaRyzykowna(id ? z : null, 'load')}`,
    [ {label:'Anuluj'},
      {label:'Zapisz',cls:'pri',fn:()=>{
        z.name=val('zName').trim(); z.note=val('zNote').trim();
        if(!z.name){ alert('Podaj nazwę załadunku.'); return false; }
        if(id){ const i=DB.loads.findIndex(x=>x.id===id); DB.loads[i]=z; }
        else { DB.loads.push(z); SEL.load=z.id; }
        save(); render();
      }}],
    ()=>wireStrefa('load', id, ()=>{ SEL.load=null; }));
}


/** Rozpiska produkcyjna: co zapakować, co zwinąć, co przygotować, co wyjąć z lodówki. */
function rozpiskaHtml(z){
  const r = zalRozpiska(z);
  const nic = !Object.keys(r.zestawy).length;
  if(nic) return `<div class="card"><h2 style="margin:0 0 6px">Do przygotowania</h2>
    <div class="empty">Żadna szafka nie jest zaznaczona.</div></div>`;

  const zestawy = Object.keys(r.zestawy).map(id=>{
    const s=CALC.set(id), c=CALC.setCalc(s,'vending'), n=r.zestawy[id];
    return {nazwa:s.name, n, wartosc:(c.priceGross||0)*n, koszt:c.net*n};
  }).filter(x=>x.nazwa).sort((a,b)=>b.n-a.n);

  const rolki = Object.keys(r.rolki).map(id=>{
    const it=CALC.item(id), kaw=r.rolki[id];
    if(!it) return {nazwa:'⚠ brak rolki ('+id+')', kaw, rolek:null, naRolke:null, koszt:0, brak:true};
    const c=CALC.itemCalc(it,'vending');
    return {nazwa:itName(it), kaw, rolek:kaw/(it.pieces||1), naRolke:it.pieces, koszt:c.perPiece*kaw};
  }).sort((a,b)=>b.kaw-a.kaw);

  const polprodukty = Object.keys(r.polprodukty).map(id=>{
    const p=CALC.prep(id); if(!p) return null;
    const ile=r.polprodukty[id], uc=CALC.prepUnitCost(id);
    return {nazwa:p.name, ile, jm:p.yieldUnit, partii:ile/(p.yieldQty||1), koszt:(uc||0)*ile};
  }).filter(Boolean).sort((a,b)=>b.koszt-a.koszt);

  const skladniki = Object.keys(r.skladniki).map(id=>{
    if(id.indexOf('raw:')===0)
      return {nazwa:id.slice(4)+' (poza bazą)', ile:r.skladniki[id], jm:'', koszt:null, opak:null};
    const g=CALC.ing(id); if(!g) return null;
    const ile=r.skladniki[id], uc=CALC.ingUnitCost(id);
    return {nazwa:g.name, ile, jm:g.unit, koszt:uc==null?null:uc*ile,
            opak:(g.packQty?ile/g.packQty:null)};
  }).filter(Boolean).sort((a,b)=>(b.koszt||0)-(a.koszt||0));

  const sumaSkl = skladniki.reduce((a,x)=>a+(x.koszt||0),0);
  const il = (v)=>num(v, v%1 ? 2 : 0);

  return `<div class="card">
    <h2 style="margin:0 0 4px">Do przygotowania</h2>
    <div class="hint" style="margin-bottom:14px">Wszystko przeliczone w dół z zaznaczonych szafek:
      z zestawów na rolki, z rolek na półprodukty i surowe składniki.
      Zapotrzebowanie na składniki uwzględnia odpad z półproduktów.</div>

    <h3 style="margin:0 0 6px">Zestawy do zapakowania</h3>
    <div class="tw"><table data-tbl="rzest"><thead><tr><th>Zestaw</th><th class="r">Sztuk</th>
      <th class="r">Wartość</th><th class="r">Koszt</th></tr></thead><tbody>
      ${zestawy.map(x=>`<tr><td>${esc(x.nazwa)}</td><td class="r num">${x.n}</td>
        <td class="r num">${zl(x.wartosc)}</td><td class="r num mut">${zl(x.koszt)}</td></tr>`).join('')}
      </tbody></table></div>

    <h3 style="margin:18px 0 6px">Rolki do zwinięcia</h3>
    <div class="tw"><table data-tbl="rrol"><thead><tr><th>Rolka</th><th class="r">Kawałków</th>
      <th class="r">Rolek</th><th class="r">Koszt</th></tr></thead><tbody>
      ${rolki.map(x=>`<tr><td>${esc(x.nazwa)}
        ${x.brak?'<span class="tag crit">brak w bazie</span>':`<span class="mut small">${x.naRolke} kaw./rolkę</span>`}</td>
        <td class="r num">${il(x.kaw)}</td>
        <td class="r num">${rolekHtml(x.rolek)}</td>
        <td class="r num mut">${x.brak?'—':zl(x.koszt)}</td></tr>`).join('')}
      </tbody></table></div>

    ${polprodukty.length?`<h3 style="margin:18px 0 6px">Półprodukty do zrobienia</h3>
    <div class="tw"><table data-tbl="rpp"><thead><tr><th>Półprodukt</th><th class="r">Ilość</th>
      <th class="r">Partii</th><th class="r">Koszt</th></tr></thead><tbody>
      ${polprodukty.map(x=>`<tr><td>${esc(x.nazwa)}</td>
        <td class="r num">${il(x.ile)} ${esc(x.jm)}</td>
        <td class="r num">${num(x.partii,2)}</td>
        <td class="r num mut">${zl(x.koszt)}</td></tr>`).join('')}
      </tbody></table></div>`:''}

    <h3 style="margin:18px 0 6px">Składniki do wydania</h3>
    <div class="tw"><table data-tbl="rskl"><thead><tr><th>Składnik</th><th class="r">Ilość</th>
      <th class="r">Opakowań</th><th class="r">Koszt</th></tr></thead><tbody>
      ${skladniki.map(x=>`<tr><td>${esc(x.nazwa)}</td>
        <td class="r num">${il(x.ile)} ${esc(x.jm||'')}</td>
        <td class="r num mut">${x.opak==null?'—':num(x.opak,2)}</td>
        <td class="r num mut">${x.koszt==null?'<span class="tag crit">brak ceny</span>':zl(x.koszt)}</td></tr>`).join('')}
      <tr class="suma"><td>Razem</td><td></td><td></td><td class="r num">${zl(sumaSkl)}</td></tr>
      </tbody></table></div>
    <div class="hint">Suma kosztu składników zgadza się z kosztem wytworzenia załadunku —
      to ta sama liczba policzona z drugiej strony.</div>
  </div>`;
}


/* ============================================================================
   WIDOKI DNIA (grupa „Pulpit")
   Wszystkie pokazują ten sam dzień z różnych stron: co przygotować,
   co zwinąć, co spakować i czy starczy zapasów.
   ========================================================================== */

/** wspólny pasek wyboru dnia; `wireDay` podpina go po przerysowaniu */
/* ---------- skład pojedynczej sztuki jako osobna podstrona ---------- */
/* Kucharzowi w trakcie zmiany nie jest potrzebna rozpiska całego załadunku, tylko
   przypomnienie: z czego składa się JEDEN półprodukt, JEDNA rolka, JEDEN zestaw.
   Stąd osobny ekran, a nie rozwijany wiersz — mieści się na telefonie i da się
   wejść w niego głębiej (z rolki w półprodukt) bez gubienia drogi powrotnej. */
let PODGLAD = null;      // {typ:'pp'|'rol'|'zst', id}

function otworzSklad(typ, id){
  PODGLAD = {typ, id};
  VIEW = 'dSklad';
  zapiszHistorie(true); render(); window.scrollTo(0,0);
}
/* Wyjście ze składu idzie WYŁĄCZNIE przez historię: „wstecz" w przeglądarce albo na
   dolnym pasku telefonu. Własny klawisz „← Wróć" robił dokładnie to samo, tylko drugim
   sposobem i w drugim miejscu — a wtedy trzeba pamiętać, że oba istnieją, i pilnować,
   żeby się nie rozjechały. Historia odtwarza pełny stan każdego ekranu (składu, automatu
   u Kierowcy, dnia), więc nie ma czego dokładać. */

/** nazwa jako odnośnik do składu */
function skladLink(typ, id, txt){
  return `<a href="#" data-sklad="${typ}:${esc(id)}">${esc(txt)}</a>`;
}
function dayBar(){
  const d = daneDnia(DAY);
  return `<div class="card" style="padding:12px;margin-bottom:12px">
    <div class="daybar">
      <button class="btn sm" data-day="-1">‹</button>
      <span class="datawyb">${esc(dataDluga(DAY))}
        <input type="date" id="dayPick" value="${esc(DAY)}" aria-label="Wybierz dzień"></span>
      <button class="btn sm" data-day="1">›</button>
      <button class="btn sm" data-day="today">Dziś</button>
      <div class="spacer"></div>
      ${d.z
        ? `<span class="mut small">załadunek</span> <b>${esc(d.z.name)}</b>`
        : '<span class="tag crit">brak załadunku na ten dzień</span>'}
    </div>
  </div>`;
}
function wireDay(root){
  const pick = root.querySelector('#dayPick');
  if(pick){
    pick.addEventListener('change',()=>{ DAY = pick.value || todayISO(); render(); });
    // Pole daty leży niewidoczne na napisie: klik w „piątek 07.08.2026" ma otworzyć
    // kalendarz przeglądarki, a nie postawić kursor w polu, którego nie widać.
    pick.addEventListener('click',()=>{ if(pick.showPicker) try{ pick.showPicker(); }catch(e){} });
  }
  root.querySelectorAll('[data-day]').forEach(b=>b.addEventListener('click',()=>{
    DAY = b.dataset.day==='today' ? todayISO() : przesunDate(DAY, parseInt(b.dataset.day,10));
    render();
  }));
  root.querySelectorAll('[data-pdf]').forEach(b=>b.addEventListener('click',()=>{
    const [klucz, loadId] = b.dataset.pdf.split('|');
    const f = PDF_DNIA[klucz];
    if(f) f(loadId ? DB.loads.find(z=>z.id===loadId) : null);
  }));
  root.querySelectorAll('[data-sklad]').forEach(a=>a.addEventListener('click',e=>{
    e.preventDefault();
    const i = a.dataset.sklad.indexOf(':');
    otworzSklad(a.dataset.sklad.slice(0,i), a.dataset.sklad.slice(i+1));
  }));
  root.querySelectorAll('[data-packgroup] button').forEach(b=>b.addEventListener('click',()=>{
    PACK_TRYB = b.dataset.pt; render();
  }));
  root.querySelectorAll('[data-kier]').forEach(b=>b.addEventListener('click',e=>{
    e.preventDefault();
    const id = b.dataset.kier;
    // Kliknięcie w ten sam automat drugi raz zwija go z powrotem do listy — to jedyne
    // wyjście „w bok"; z powrotu w głąb wychodzi się historią.
    KIER = (id && id!==KIER) ? id : null;
    zapiszHistorie(true); render(); window.scrollTo(0,0);
  }));
}
/** nagłówek + pasek dnia + komunikat, gdy dzień nie ma załadunku */
function dzienRama(tytul, podtytul, tresc, pdf){
  const d = daneDnia(DAY);
  return `<div class="topbar"><h1>${esc(tytul)}</h1>
    <span class="sub">${esc(podtytul||'')}</span>
    ${pdf?`<div class="spacer"></div>
      <button class="btn sm" data-pdf="${pdf}" title="Wydruk na jedną kartkę">⎙ PDF</button>`:''}</div>
  ${dayBar()}
  ${d.z ? tresc(d) : `<div class="card"><div class="empty">
    Do dnia „${esc(dzienNazwa(DAY))}" nie jest przypisany żaden załadunek.${canEdit()
      ? '<br><a href="#" data-go="load">Ustaw plan tygodnia</a>' : ''}</div></div>`}`;
}

const ilosc = v => num(v, v%1 ? 2 : 0);

/** Liczba rolek do zwinięcia. Niepełna jest czerwona — i to jest jedyne miejsce,
    w którym o tym decydujemy.

    Rolka zwija się w całości. „2,5 rolki" znaczy, że pół trzeba będzie wyrzucić albo
    dołożyć, czyli że liczba zestawów w automatach jest ustawiona niepraktycznie. To nie
    błąd programu, tylko decyzja do poprawienia — więc liczba mówi to sama, wszędzie tak
    samo: w rozpisce załadunku, na kafelkach dnia, na liście rolek i w tabeli tygodnia. */
function rolekHtml(v, pusty){
  if(v == null) return pusty === undefined ? '—' : pusty;
  if(!(v % 1)) return num(v, 0);
  return `<span class="ulamek" title="Niepełna rolka — lepiej dobrać liczbę zestawów tak, `
       + `żeby schodziły całe rolki">${num(v, 1)}</span>`;
}

/* ---------- Pulpit: data i wejście do ekranów dnia ---------- */
function vPulpit(){
  const d = daneDnia(DAY);
  const r = d.r;
  const rolek = r ? Object.keys(r.rolki).reduce((a,id)=>{
    const it = CALC.item(id);
    return a + (it ? r.rolki[id]/(it.pieces||1) : 0);
  },0) : 0;
  const zestawow = r ? Object.keys(r.zestawy).reduce((a,k)=>a+r.zestawy[k],0) : 0;

  // Ten sam znak co przy zakładce w menu — kafelek Pulpitu i pozycja menu prowadzą
  // w to samo miejsce, więc nie ma powodu, żeby wyglądały na dwie różne rzeczy.
  // Wcześniej były to glify blokowe z Unicode: rysowane systemowym krojem zapasowym,
  // czyli inaczej na każdym komputerze, i powtarzały się między sobą.
  const kafle = [
    {v:'dPrep',  ic:'mata', t:'Przygotowanie', o:'półprodukty i składniki',
     n: r ? Object.keys(r.polprodukty).length : 0, jm:'półproduktów'},
    {v:'dRolki', ic:'rolka', t:'Rolki', o:'do zwinięcia',
     n: rolekHtml(rolek), jm:'rolek'},
    {v:'dZest',  ic:'taca', t:'Zestawy', o:'do złożenia',
     n: zestawow, jm:'sztuk'},
    {v:'dPack',  ic:'karton', t:'Pakowanie', o:'podział na automaty',
     n: active(DB.machines).length, jm:'automatów'},
    {v:'driver', ic:'auto', t:'Kierowca', o:'trasa i numery szafek',
     n: d.z ? zalSuma(d.z).szt : 0, jm:'szafek'},
    {v:'stock',  ic:'waga', t:'Kontrola zasobów', o:'jutro i pojutrze',
     n: null, jm:''}
  ];

  /** Miniatura miesiąca: cały miesiąc na jednym kafelku, z zaznaczonymi dniami,
      w których zalogowana osoba ma zmianę. Bez zalogowania pokazujemy dni, w których
      czegoś brakuje — bo wtedy patrzy na to ktoś, kto grafik układa, a nie w nim stoi. */
  const miniGrafik = () => {
    const ja = mojaOsoba();
    const ym = DAY.slice(0,7);
    const dzis = todayISO();
    const dni = dniMiesiaca(ym);
    const moj = iso => zmianyDnia(iso).some(z=>zapisy(iso, z.id).osoby.indexOf(ja.id) >= 0);
    const brak = iso => zmianyDnia(iso).some(z=>obsada(iso, z).wolne > 0);
    const zazn = ja ? moj : brak;
    // Pięć tygodni licząc od BIEŻĄCEGO, nie od pierwszego dnia miesiąca. Miesiąc to
    // podział księgowy, a nie sposób, w jaki się pracuje: 28 sierpnia interesuje mnie
    // wrzesień, a nie to, co było 3 sierpnia. Pierwszy wiersz to zawsze ten tydzień,
    // w którym stoimy — dzień dzisiejszy siedzi w nim pod podkreśleniem.
    const start = poniedzialek(dzis);
    const komorki = Array.from({length: 35}, (_, i)=>przesunISO(start, i));
    // Granica miesiąca: kreska tam, gdzie naprawdę przebiega. Pierwszy dzień miesiąca
    // dostaje kreskę z lewej, a jeśli wypada w poniedziałek — cały wiersz dostaje ją
    // od góry, bo granica idzie wtedy nad rzędem, nie w jego środku.
    const granica = new Set();
    komorki.forEach((iso, i)=>{
      if(iso.slice(8) !== '01') return;
      if(i % 7 === 0) for(let j = i; j < i + 7 && j < komorki.length; j++) granica.add(j + '|gora');
      else granica.add(i + '|lewa');
    });
    const kratki = komorki.map((iso, i)=>`<div class="${zazn(iso)?'jest':''} ${
        iso===dzis?'dzis':''} ${iso < dzis?'byl':''} ${
        granica.has(i + '|lewa') ? 'granica-lewa' : ''} ${
        granica.has(i + '|gora') ? 'granica-gora' : ''}"
          title="${esc(dataDluga(iso))}">${+iso.slice(8)}</div>`).join('');
    // Godzin, liczby zmian i nazwy miesiąca tu nie ma: to wszystko jest w Grafiku,
    // o jedno kliknięcie dalej. Kafelek odpowiada na jedno pytanie — w które dni stoję.
    const opisGraf = ja ? 'twoje zmiany' : 'dni bez kompletu';
    return `<a class="card karta-graf" href="#" data-go="graf" title="${esc(opisGraf)}">
      <div class="row" style="justify-content:space-between;align-items:flex-start">
        <div><b style="font-size:15px">Grafik</b>
          <div class="hint" style="margin:2px 0 0">${esc(opisGraf)}</div></div>
        <span class="ic-big">${ikona('kalendarz', 22)}</span>
      </div>
      <div class="minimc">${DNI.map(d=>`<div class="dn">${esc(d.l)}</div>`).join('')}${kratki}</div>
    </a>`;
  };

  return `<div class="topbar"><h1>Pulpit</h1>
    <span class="sub">${esc(dataDluga(DAY))}</span></div>
  ${dayBar()}
  ${d.z ? '' : `<div class="banner">Do tego dnia nie jest przypisany żaden załadunek —
    ekrany dnia będą puste.${canEdit()
      ? ' <a href="#" data-go="load">Ustaw plan tygodnia</a>' : ''}</div>`}
  <div class="pulpit">
    ${miniGrafik()}
    ${kartaSprzedazyPulpitu()}
    ${kafle.map(k=>`<a class="card" href="#" data-go="${k.v}" title="${esc(k.o)}">
      <div class="row" style="justify-content:space-between;align-items:flex-start">
        <div><b style="font-size:15px">${esc(k.t)}</b>
          <div class="hint" style="margin:2px 0 0">${esc(k.o)}</div></div>
        <span class="ic-big">${ikona(k.ic, 22)}</span>
      </div>
      <div class="val num" style="margin-top:10px">${k.n==null?'—':k.n}</div>
      <div class="sub2">${esc(k.jm)}</div>
    </a>`).join('')}
  </div>`;
}

/* ---------------------------------------------------------------------------
   SPRZEDAŻ NA PULPICIE
   Kafelek widzi wyłącznie właściciel i administrator — to są kwoty, a Pulpit ogląda
   też pracownik, któremu serwer wycina z bazy każdą cenę. Ukrycie jest po obu
   stronach: bez roli zarządu kafelek w ogóle się nie rysuje, a danych i tak nie ma
   skąd wziąć, bo `/api/sprzedaz` odpowiada tylko zarządowi.
   ------------------------------------------------------------------------- */
/** Sprzedaż to kwoty, a kwot nie ma bez serwera (skąd je wziąć) i bez roli zarządu
    (komu je pokazać). Jedno pytanie zadawane w trzech miejscach: kafelek, pozycja
    w menu, ekran. */
function maSprzedaz(){
  return !!(SRV.on && SRV.user && ZARZAD.indexOf(SRV.user.role) >= 0);
}

/** Zakres, którego potrzebuje kafelek: 30 dni wstecz od dnia z paska. */
function zakresPulpitu(){
  const doo = DAY || todayISO();
  return {od: przesunISO(doo, -29), doo: doo};
}

async function wczytajSprzedazPulpit(){
  const z = zakresPulpitu(), klucz = z.od + '|' + z.doo;
  if(SPRZ_PUL_KLUCZ === klucz) return;
  if(!(SRV.on && SRV.user && ZARZAD.indexOf(SRV.user.role) >= 0)){
    SPRZ_PUL = {}; SPRZ_PUL_KLUCZ = klucz; return;
  }
  try{
    const r = await fetch('/api/sprzedaz?od=' + z.od.slice(0,7) + '&do=' + z.doo.slice(0,7));
    SPRZ_PUL = r.ok ? ((await r.json()).sprzedaz || {}) : {};
    SPRZ_PUL_BLAD = r.ok ? null : 'Nie udało się wczytać sprzedaży.';
  }catch(e){ SPRZ_PUL = {}; SPRZ_PUL_BLAD = 'Brak połączenia z serwerem.'; }
  SPRZ_PUL_KLUCZ = klucz;
}

/** Sumy kwot: wiersz na automat, kolumna na okno czasu.

    Okna liczą się WSTECZ OD DNIA Z PASKA, nie od dzisiaj — Pulpit cały jest o wybranym
    dniu i kafelek nie ma powodu mówić o czym innym niż reszta ekranu. */
function sumySprzedazyPulpit(){
  const koniec = DAY || todayISO();
  const wczoraj = przesunISO(koniec, -1);
  const pusty = ()=>({dzien: 0, poprz: 0, d7: 0, d30: 0});
  const wg = {}, razem = pusty(), nier = pusty();
  let ileNier = 0;
  Object.keys(SPRZ_PUL || {}).forEach(k=>{
    const w = SPRZ_PUL[k];
    if(!w || !w.czas) return;
    const iso = isoSprzedazy(w.czas), kwota = w.kwota || 0;
    if(iso > koniec || iso < przesunISO(koniec, -29)) return;
    const mid = w.maszyna || null;
    const cel = mid ? (wg[mid] || (wg[mid] = pusty())) : null;
    const dodaj = (c)=>{
      c.d30 += kwota;
      if(iso > przesunISO(koniec, -7)) c.d7 += kwota;
      if(iso === koniec) c.dzien += kwota;
      if(iso === wczoraj) c.poprz += kwota;
    };
    /* Sprzedaż bez rozpoznanego automatu liczy się w KAŻDYM oknie tak samo jak reszta —
       inaczej wiersz „Nierozpoznane" miałby kreskę w kolumnie „dziś", a suma pod spodem
       i tak by ją zawierała, i kolumna przestawałaby się zgadzać. */
    dodaj(cel || nier);
    if(!cel) ileNier++;
    dodaj(razem);
  });
  const wiersze = active(DB.machines).map(m=>Object.assign(
    {kod: m.code || m.name, nazwa: m.name}, wg[m.id] || pusty()));
  return {koniec, wczoraj, wiersze, razem, nier, ileNier};
}

/** Kafelek sprzedaży na Pulpicie: utarg dnia dużą liczbą, tydzień i miesiąc pod kreską.
    Prowadzi na własny ekran — tak samo, jak kafelek Grafiku prowadzi na kalendarz. */
function kartaSprzedazyPulpitu(){
  if(!maSprzedaz()) return '';
  const z = zakresPulpitu(), klucz = z.od + '|' + z.doo;
  if(SPRZ_PUL_KLUCZ !== klucz){
    after('dHome', async ()=>{ await wczytajSprzedazPulpit(); render(); });
    return `<a class="card" id="pulSprzedaz" href="#" data-go="dSprzedaz">
      <div class="empty">Wczytuję sprzedaż…</div></a>`;
  }
  const s = sumySprzedazyPulpit();
  // Przy dniu dzisiejszym „dziś" jest dokładne; przy każdym innym byłoby kłamstwem,
  // więc wtedy pod liczbą stoi data.
  const nazwaDnia = s.koniec === todayISO() ? 'dziś' : dataKrotko(s.koniec);
  return `<a class="card" id="pulSprzedaz" href="#" data-go="dSprzedaz" title="utarg automatów">
    <div class="row" style="justify-content:space-between;align-items:flex-start">
      <div><b style="font-size:15px">Sprzedaż</b>
        <div class="hint" style="margin:2px 0 0">utarg automatów</div></div>
      <span class="ic-big">${ikona('kasa', 22)}</span>
    </div>
    <div class="val num" style="margin-top:10px">${zl(s.razem.dzien)}</div>
    <div class="sub2">${esc(nazwaDnia)}</div>
    <div class="okna">
      <div><span class="lab">7 dni</span><b class="num">${zl(s.razem.d7)}</b></div>
      <div><span class="lab">30 dni</span><b class="num">${zl(s.razem.d30)}</b></div>
    </div>
  </a>`;
}

/** Ekran „Sprzedaż" w sekcji Pulpit: ten sam dzień z paska, co reszta Pulpitu,
    i rozbicie utargu na automaty.

    Wykresy i raport zostają w Analizach — tam się szuka prawidłowości, tutaj odpowiedzi
    na jedno pytanie: ile dziś zeszło i z którego automatu. */
function vSprzedazDnia(){
  const ramka = tresc => `<div class="topbar"><h1>Sprzedaż</h1>
    <span class="sub">utarg automatów</span></div>
  ${dayBar()}
  <div id="ekrSprzedaz">${tresc}</div>`;
  if(!maSprzedaz()) return ramka(`<div class="card"><div class="empty">
    Sprzedaż widzi właściciel i administrator.</div></div>`);
  const z = zakresPulpitu(), klucz = z.od + '|' + z.doo;
  if(SPRZ_PUL_KLUCZ !== klucz){
    after('dSprzedaz', async ()=>{ await wczytajSprzedazPulpit(); render(); });
    return ramka(`<div class="card"><div class="empty">Wczytuję sprzedaż…</div></div>`);
  }
  const s = sumySprzedazyPulpit();
  const dzis = todayISO();
  const nazwaDnia = s.koniec === dzis ? 'dziś' : dataKrotko(s.koniec);
  const nazwaPoprz = s.koniec === dzis ? 'wczoraj' : dataKrotko(s.wczoraj);
  const kwota = v => v ? zl(v) : '<span class="mut">—</span>';
  return ramka(`${SPRZ_PUL_BLAD ? `<div class="banner">${esc(SPRZ_PUL_BLAD)}</div>` : ''}
  <div class="card">
    <div class="tiles">
      <div class="tile"><div class="lab">${esc(nazwaDnia)}</div>
        <div class="val num">${zl(s.razem.dzien)}</div></div>
      <div class="tile"><div class="lab">7 dni</div>
        <div class="val num">${zl(s.razem.d7)}</div></div>
      <div class="tile"><div class="lab">30 dni</div>
        <div class="val num">${zl(s.razem.d30)}</div></div>
    </div>
  </div>
  <div class="card" style="margin-top:12px">
    <h2>Po automatach</h2>
    <div class="tw przyklej"><table data-tbl="pulSprz" data-no-sort-now><thead><tr>
      <th>Automat</th><th class="r">${esc(nazwaDnia)}</th><th class="r">${esc(nazwaPoprz)}</th>
      <th class="r">7 dni</th><th class="r">30 dni</th></tr></thead><tbody>
    ${s.wiersze.map(w=>`<tr><td>${esc(w.kod)}
        <span class="mut small">${esc(w.nazwa)}</span></td>
      <td class="r num">${kwota(w.dzien)}</td><td class="r num">${kwota(w.poprz)}</td>
      <td class="r num">${kwota(w.d7)}</td><td class="r num">${kwota(w.d30)}</td></tr>`).join('')}
    ${s.ileNier ? `<tr><td><span class="mut">Nierozpoznane</span>
        <span class="mut small">${s.ileNier} sprzedaży bez automatu</span></td>
      <td class="r num mut">${kwota(s.nier.dzien)}</td>
      <td class="r num mut">${kwota(s.nier.poprz)}</td>
      <td class="r num mut">${kwota(s.nier.d7)}</td>
      <td class="r num mut">${kwota(s.nier.d30)}</td></tr>` : ''}
    <tr class="suma"><td>Razem</td>
      <td class="r num">${kwota(s.razem.dzien)}</td><td class="r num">${kwota(s.razem.poprz)}</td>
      <td class="r num">${kwota(s.razem.d7)}</td><td class="r num">${kwota(s.razem.d30)}</td></tr>
  </tbody></table></div>
    <div style="margin-top:12px"><a href="#" data-go="sprzedaz">Wykresy i raport</a></div>
  </div>`);
}

/* ---------- Skład: receptura jednej sztuki ---------- */
function vSklad(){
  if(!PODGLAD) return vPulpit();
  const {typ, id} = PODGLAD;

  /** nazwa komponentu; półprodukt jest odnośnikiem, żeby dało się wejść głębiej */
  const nazwaKomp = (refId) => {
    const info = CALC.compInfo(refId);
    return CALC.prep(refId)
      ? `${skladLink('pp', refId, info.name)} <span class="tag">półprodukt</span>`
      : esc(info.name);
  };
  const rama = (tytul, pod, tresc) => `<div class="topbar">
      <h1>${tytul}</h1>
      <span class="sub">${esc(pod||'')}</span></div>${tresc}`;
  /** zdjęcie nad składem — kucharz od razu widzi, co ma wyjść */
  const zdjecie = (src, alt) => src
    ? `<img class="hero" src="${src}" alt="${esc(alt)}" style="max-width:420px;margin-bottom:12px">`
    : '';

  if(typ === 'pp'){
    const p = CALC.prep(id);
    if(!p) return rama('Skład', '', '<div class="card"><div class="empty">Nie ma już takiego półproduktu.</div></div>');
    const jestOdpad = p.items.some(c=>(c.waste||0) > 0);
    return rama(esc(p.name), `półprodukt · wydajność ${ilosc(p.yieldQty)} ${esc(p.yieldUnit||'')}`,
      `<div class="card"><div class="tw"><table data-tbl="skl"><thead><tr><th>Składnik</th>
        <th class="r">Ilość</th>${jestOdpad?'<th class="r">Odpad</th><th class="r">Razem</th>':''}
        </tr></thead><tbody>
        ${p.items.length?p.items.map(c=>{
          const info = c.kind==='raw' ? {name:c.name+' (poza bazą)', unit:c.unit||''} : CALC.compInfo(c.refId);
          const jm = esc(info.unit||'');
          return `<tr><td>${c.kind==='raw'?esc(info.name):nazwaKomp(c.refId)}</td>
            <td class="r num">${ilosc(c.qty||0)} ${jm}</td>
            ${jestOdpad?`<td class="r num mut">${(c.waste||0)>0?ilosc(c.waste)+' '+jm:'—'}</td>
              <td class="r num">${ilosc((c.qty||0)+(c.waste||0))} ${jm}</td>`:''}</tr>`;
        }).join(''):`<tr><td colspan="${jestOdpad?4:2}" class="empty">Ten półprodukt nie ma receptury.</td></tr>`}
      </tbody></table></div>
      ${p.note?`<div class="hint" style="margin-top:10px">${esc(p.note)}</div>`:''}</div>`);
  }

  if(typ === 'rol'){
    const it = CALC.item(id);
    if(!it) return rama('Skład', '', '<div class="card"><div class="empty">Nie ma już takiej rolki.</div></div>');
    const kaw = it.pieces||1;
    return rama(esc(itName(it)), `rolka · ${kaw} kawałków`,
      `${zdjecie(it.photo, it.name)}<div class="card"><div class="tw"><table data-tbl="skl">
        <thead><tr><th data-ordth title="Kolejność nakładania">#</th><th>Składnik</th>
        <th class="r">Na rolkę</th></tr></thead><tbody>
        ${(it.comps||[]).length?(it.comps||[]).map((c,i)=>{
          const info = CALC.compInfo(c.refId), jm = esc(info.unit||'');
          return `<tr><td class="num mut">${i+1}</td><td>${nazwaKomp(c.refId)}</td>
            <td class="r num">${ilosc(c.qty||0)} ${jm}</td></tr>`;
        }).join(''):'<tr><td colspan="3" class="empty">Ta rolka nie ma receptury.</td></tr>'}
      </tbody></table></div>
      ${it.note?`<div class="hint" style="margin-top:10px">${esc(it.note)}</div>`:''}</div>`);
  }

  const s = CALC.set(id);
  if(!s) return rama('Skład', '', '<div class="card"><div class="empty">Nie ma już takiego zestawu.</div></div>');
  const kaw = (s.entries||[]).reduce((a,e)=>a+(e.pieces||0),0);
  return rama(esc(s.name), `zestaw · ${kaw} kawałków`,
    `${zdjecie(s.photo, s.name)}<div class="card" style="margin-bottom:12px">
      <h2 style="margin:0 0 10px">Rolki</h2>
      <div class="tw"><table data-tbl="sklR">
        <thead><tr><th data-ordth title="Kolejność układania">#</th><th>Rolka</th>
        <th class="r">Kawałków</th><th class="r">Rolek</th></tr></thead><tbody>
        ${(s.entries||[]).length?(s.entries||[]).map((e,i)=>{
          const it = CALC.item(e.itemId);
          const rolek = it ? (e.pieces||0)/(it.pieces||1) : null;
          return `<tr><td class="num mut">${i+1}</td>
            <td>${it ? skladLink('rol', e.itemId, itName(it))
                     : `⚠ brak rolki (${esc(e.itemId)}) <span class="tag crit">brak w bazie</span>`}</td>
            <td class="r num">${ilosc(e.pieces||0)}</td>
            <td class="r num mut">${rolek==null?'—':num(rolek,2)}</td></tr>`;
        }).join(''):'<tr><td colspan="4" class="empty">Ten zestaw nie ma rolek.</td></tr>'}
      </tbody></table></div></div>
    <div class="card"><h2 style="margin:0 0 10px">Dodatki</h2>
      <div class="tw"><table data-tbl="sklD"><thead><tr><th>Pozycja</th>
        <th class="r">Ilość</th></tr></thead><tbody>
        ${(s.comps||[]).length?(s.comps||[]).map(c=>{
          const info = CALC.compInfo(c.refId);
          return `<tr><td>${nazwaKomp(c.refId)}</td>
            <td class="r num">${ilosc(c.qty||0)} ${esc(info.unit||'')}</td></tr>`;
        }).join(''):'<tr><td colspan="2" class="empty">Bez dodatków.</td></tr>'}
      </tbody></table></div>
      ${s.note?`<div class="hint" style="margin-top:10px">${esc(s.note)}</div>`:''}</div>`);
}

/* ---------- Przygotowanie: półprodukty i składniki ---------- */
function vDzienPrzygotowanie(){
  return dzienRama('Przygotowanie', 'półprodukty i składniki na wybrany dzień', d=>{
    const pp = Object.keys(d.r.polprodukty).map(id=>{
      const p=CALC.prep(id); if(!p) return null;
      const ile=d.r.polprodukty[id];
      return {id, n:p.name, ile, jm:p.yieldUnit, partii:ile/(p.yieldQty||1)};
    }).filter(Boolean).sort((a,b)=>b.ile-a.ile);

    const skl = Object.keys(d.r.skladniki).map(id=>{
      if(id.indexOf('raw:')===0) return {n:id.slice(4)+' (poza bazą)', ile:d.r.skladniki[id], jm:'', opak:null};
      const g=CALC.ing(id); if(!g) return null;
      const ile=d.r.skladniki[id];
      return {n:g.name, ile, jm:g.unit, opak:g.packQty?ile/g.packQty:null};
    }).filter(Boolean).sort((a,b)=>b.ile-a.ile);

    return `<div class="tiles" style="margin-bottom:12px">
      <div class="tile"><div class="lab">Półproduktów</div><div class="val num">${pp.length}</div></div>
      <div class="tile"><div class="lab">Składników</div><div class="val num">${skl.length}</div></div>
    </div>
    ${pp.length?`<div class="card" style="margin-bottom:12px"><h2 style="margin:0 0 4px">Półprodukty do zrobienia</h2>
      <div class="hint" style="margin-bottom:10px">Kliknij nazwę, żeby zobaczyć recepturę półproduktu.</div>
      <div class="tw"><table data-tbl="dpp"><thead><tr><th>Półprodukt</th><th class="r">Ilość</th>
        <th class="r">Partii</th></tr></thead><tbody>
        ${pp.map(x=>`<tr><td>${skladLink('pp', x.id, x.n)}</td>
          <td class="r num">${ilosc(x.ile)} ${esc(x.jm)}</td>
          <td class="r num">${num(x.partii,2)}</td></tr>`).join('')}
      </tbody></table></div></div>`:''}
    <div class="card"><h2 style="margin:0 0 10px">Składniki do wydania</h2>
      <div class="tw"><table data-tbl="dskl"><thead><tr><th>Składnik</th><th class="r">Ilość</th>
        <th class="r">Opakowań</th></tr></thead><tbody>
        ${skl.map(x=>`<tr><td>${esc(x.n)}</td><td class="r num">${ilosc(x.ile)} ${esc(x.jm||'')}</td>
          <td class="r num mut">${x.opak==null?'—':num(x.opak,2)}</td></tr>`).join('')}
      </tbody></table></div></div>`;
  }, 'dPrep');
}

/** Rolki pogrupowane po kategoriach, w kolejności zwijania wewnątrz grupy.
    Zwraca [{kat, rolki:[...], rolek, kaw}] — kategorie w kolejności z ustawień,
    „bez kategorii" na końcu, bo to reszta, a nie pełnoprawna grupa. */
function rolkiWgKategorii(rolki){
  const grupy = [];
  const dodaj = (kat, r) => {
    let g = grupy.find(x=>x.kat === kat);
    if(!g){ g = {kat, rolki:[], rolek:0, kaw:0}; grupy.push(g); }
    g.rolki.push(r); g.rolek += (r.rolek||0); g.kaw += r.kaw;
  };
  (DB.cats||[]).forEach(k=>{
    rolki.filter(r=>{ const it = CALC.item(r.id); return it && it.catId === k.id; })
         .forEach(r=>dodaj(k, r));
  });
  rolki.filter(r=>{ const it = CALC.item(r.id); return !it || !it.catId
                    || !(DB.cats||[]).some(k=>k.id===it.catId); })
       .forEach(r=>dodaj(null, r));
  return grupy;
}

/* ---------- Rolki na dany dzień ---------- */
function vDzienRolki(){
  return dzienRama('Rolki', 'do zwinięcia na wybrany dzień', d=>{
    // rolka skasowana, a wciąż wpisana w zestaw — pokazujemy zamiast po cichu gubić
    // kolejność zwijania z listy rolek, nie „od największej ilości"
    const poz = id => { const i = DB.items.findIndex(x=>x.id===id); return i<0 ? 1e9 : i; };
    const rolki = Object.keys(d.r.rolki).map(id=>{
      const it=CALC.item(id), kaw=d.r.rolki[id];
      if(!it) return {id, n:'⚠ brak rolki ('+id+')', kaw, rolek:null, naRolke:null, brak:true};
      // n — pelna nazwa (poza grupa), nk — sama nazwa (pod naglowkiem kategorii)
      return {id, n:itName(it), nk:it.name, kaw, rolek:kaw/(it.pieces||1), naRolke:it.pieces};
    }).sort((a,b)=>poz(a.id)-poz(b.id));
    const rol = rolki.reduce((a,x)=>a+(x.rolek||0),0);
    const grupy = rolkiWgKategorii(rolki);
    let nr = 0;
    return `<div class="tiles" style="margin-bottom:12px">
      <div class="tile"><div class="lab">Rolek do zwinięcia</div><div class="val num">${rolekHtml(rol)}</div>
        <div class="sub2">${rolki.length} rodzajów${rolki.some(x=>x.brak)?' · <b style="color:var(--crit-ink)">brakujące w bazie</b>':''}</div></div>
      ${grupy.map(g=>`<div class="tile"><div class="lab">${esc(g.kat?g.kat.name:'Bez kategorii')}</div>
        <div class="val num">${rolekHtml(g.rolek)}</div>
        <div class="sub2">${g.rolki.length} rodzajów</div></div>`).join('')}
    </div>
    <div class="card">
      <div class="hint" style="margin-bottom:10px">Kliknij nazwę rolki, żeby zobaczyć jej recepturę.
        Lista idzie kategoriami, w kolejności zwijania.</div>
      <div class="tw"><table data-tbl="drol" data-no-sort-now>
      <thead><tr><th>#</th><th>Rolka</th><th class="r">Rolek</th></tr></thead><tbody>
      ${grupy.map(g=>`
        <tr class="grp"><td colspan="2">${esc(g.kat ? g.kat.name : 'Bez kategorii')}</td>
          <td class="r num">${g.rolki.some(x=>x.rolek!=null)
            ? rolekHtml(g.rolek) : ''}</td></tr>
        ${g.rolki.map(x=>`<tr><td class="num mut">${++nr}</td><td>${x.brak
            ? `${esc(x.n)} <span class="tag crit">brak w bazie</span>`
            : skladLink('rol', x.id, g.kat ? (x.nk||x.n) : x.n)}</td>
          <td class="r num">${rolekHtml(x.rolek)}</td></tr>`).join('')}`).join('')}
    </tbody></table></div></div>`;
  }, 'dRolki');
}

/* ---------- Zestawy na dany dzień ---------- */
function vDzienZestawy(){
  return dzienRama('Zestawy', 'do złożenia na wybrany dzień', d=>{
    const zest = Object.keys(d.r.zestawy).map(id=>{
      const s=CALC.set(id); if(!s) return null;
      return {id, n:s.name, szt:d.r.zestawy[id]};
    }).filter(Boolean).sort((a,b)=>DB.sets.findIndex(x=>x.id===a.id) - DB.sets.findIndex(x=>x.id===b.id));
    const szt = zest.reduce((a,x)=>a+x.szt,0);
    return `<div class="tiles" style="margin-bottom:12px">
      <div class="tile"><div class="lab">Zestawów</div><div class="val num">${szt}</div>
        <div class="sub2">${zest.length} rodzajów</div></div>
    </div>
    <div class="card">
      <div class="hint" style="margin-bottom:10px">Kliknij nazwę zestawu, żeby zobaczyć, z czego się składa jedna sztuka.</div>
      <div class="tw"><table data-tbl="dzest">
      <thead><tr><th data-ordth title="Kolejność">#</th><th>Zestaw</th>
      <th class="r">Sztuk</th></tr></thead><tbody>
      ${zest.map((x,i)=>`<tr><td class="num mut">${i+1}</td><td>${skladLink('zst', x.id, x.n)}</td>
        <td class="r num">${x.szt}</td></tr>`).join('')}
    </tbody></table></div></div>`;
  }, 'dZest');
}

/* ---------- Pakowanie: zestawy w rozbiciu na automaty ---------- */
/* Ta sama macierz z dwóch stron: „Automaty" to kafelek na maszynę z listą zestawów,
   „Zestawy" to kafelek na zestaw z listą maszyn. Pierwsze pomaga ładować wózek
   pod konkretną maszynę, drugie — odliczyć jeden zestaw na całą trasę. */
let PACK_TRYB = 'mach';
function packPills(){
  return `<div class="pill-group" data-packgroup>
    <button type="button" data-pt="mach" class="${PACK_TRYB==='mach'?'on':''}">▥ Automaty</button>
    <button type="button" data-pt="sets" class="${PACK_TRYB==='sets'?'on':''}">▦ Zestawy</button>
  </div>`;
}
function vDzienPakowanie(){
  return dzienRama('Pakowanie', 'zestawy w rozbiciu na automaty', d=>{
    const V = DB.vending, maszyny = active(DB.machines);
    const ile = (m) => {                       // ile sztuk którego zestawu jedzie do tej maszyny
      const wg = {};
      for(let n=1;n<=V.slots;n++){
        if(!slotOn(d.z, m.id, n)) continue;
        const s = slotSet(n); if(!s) continue;
        wg[s.id] = (wg[s.id]||0)+1;
      }
      return wg;
    };
    const perMaszyna = maszyny.map(m=>({m, wg:ile(m)}));

    const kafleMaszyn = perMaszyna.map(({m, wg})=>{
      const szt = Object.keys(wg).reduce((a,k)=>a+wg[k],0);
      return `<div class="card" style="padding:14px">
        <div class="row dz-head" style="justify-content:space-between;align-items:flex-start;margin-bottom:10px">
          <div><b>${esc(m.name)}</b></div>
          <div class="licz" style="text-align:right"><b>${szt}</b><div class="hint">sztuk</div></div>
        </div>
        ${Object.keys(wg).map(id=>{ const s=CALC.set(id);
          return `<div class="kv"><span>${esc(s?s.name:id)}</span><span>× ${wg[id]}</span></div>`; }).join('')
          || '<div class="hint">Nic do załadowania.</div>'}
      </div>`;
    }).join('');

    // ten sam podział widziany od strony zestawu
    const zestawy = Object.keys(zalSuma(d.z).wgZestawu);
    const kafleZestawow = zestawy.map(id=>{
      const s = CALC.set(id);
      const per = perMaszyna.map(x=>({m:x.m, n:x.wg[id]||0})).filter(x=>x.n>0);
      const szt = per.reduce((a,x)=>a+x.n,0);
      return `<div class="card" style="padding:14px">
        <div class="row dz-head" style="justify-content:space-between;align-items:flex-start;margin-bottom:10px">
          <div>${skladLink('zst', id, s?s.name:id)}
            <div class="hint" style="margin:2px 0 0">${per.length} z ${maszyny.length} automatów</div></div>
          <div class="licz" style="text-align:right"><b>${szt}</b><div class="hint">sztuk</div></div>
        </div>
        ${per.map(x=>`<div class="kv"><span class="nazwa-auto" title="${esc(x.m.name)}">${
          esc(x.m.name || x.m.code || '—')}</span>
          <span style="white-space:nowrap">× ${x.n}</span></div>`).join('')
          || '<div class="hint">Ten zestaw dziś nigdzie nie jedzie.</div>'}
      </div>`;
    }).join('');
    const og = zalSuma(d.z);
    // Wyjazd zamyka pracę w kuchni, więc pasek stoi na końcu ekranu — pod tym, co
    // trzeba było zapakować, a nie nad tym. Zaglądając tu z pytaniem „czy już
    // wyjechali", i tak trafia się w to samo miejsce, w którym się rejestruje.
    return `<div class="tiles" style="margin-bottom:12px">
      <div class="tile"><div class="lab">Zestawów do zapakowania</div><div class="val num">${og.szt}</div>
        <div class="sub2">${Object.keys(og.wgZestawu).length} rodzajów</div></div>
      <div class="tile"><div class="lab">Automatów</div><div class="val num">${maszyny.length}</div></div>
    </div>
    <div class="row" style="margin-bottom:12px">${packPills()}</div>
    <div class="tiles-grid">${PACK_TRYB==='mach'
      ? (kafleMaszyn || '<div class="empty">Brak czynnych automatów.</div>')
      : (kafleZestawow || '<div class="empty">Żadna szafka nie jest zaznaczona.</div>')}</div>
    <div class="card" style="margin-top:12px">${paskZdarzenia(d.iso, 'wyjazd', '', true)}</div>`;
  }, 'dPack');
}

/* ---------- Kierowca: co dokładnie i do której szafki ---------- */
let KIER = null;
function vKierowca(){
  return dzienRama('Kierowca', 'trasa i numery szafek', d=>{
    const V = DB.vending, maszyny = active(DB.machines);
    const wybrana = KIER ? maszyny.find(m=>m.id===KIER) : null;

    /** siatka szafek jednej maszyny — bez klikania, sam podgląd załadunku */
    const kolumna = (m, od, doo, duza) => `<div>${Array.from({length:doo-od+1},(_,i)=>od+i).map(n=>{
      const s = slotSet(n), on = slotOn(d.z, m.id, n);
      const klasa = !s ? 'pusty' : (on ? 'pelny' : 'wylaczony');
      return `<div class="slot ${klasa} ${duza?'':'maly'}"
          style="margin-bottom:${duza?8:5}px;cursor:default"
          title="${s?esc(s.name):'szafka bez przypisanego zestawu'}">
        <span class="nr">${n}</span>
        <span class="nm">${s?esc(s.name):'—'}</span>
      </div>`;
    }).join('')}</div>`;

    if(wybrana){
      const szafki = [];
      for(let n=1;n<=V.slots;n++){
        if(!slotOn(d.z, wybrana.id, n)) continue;
        const s = slotSet(n); if(!s) continue;
        szafki.push({n, s});
      }
      const wg = {};
      szafki.forEach(x=>{ (wg[x.s.id] = wg[x.s.id]||{s:x.s, nry:[]}).nry.push(x.n); });

      return `<div class="card" style="margin-bottom:12px">
        <div class="row dz-head kier-head" style="justify-content:space-between;align-items:center;margin-bottom:12px">
          <h2 style="margin:0">${esc(wybrana.name)}</h2>
          <div class="licz" style="text-align:right"><div class="val num">${szafki.length}</div></div>
        </div>
        <div class="zal-cols">${kolumna(wybrana,1,V.perCol,true)}${kolumna(wybrana,V.perCol+1,V.slots,true)}</div>
      </div>
      <div class="card" style="margin-bottom:12px">${
        paskZdarzenia(d.iso, 'automat', wybrana.id, true)}</div>
      <div class="card"><h2 style="margin:0 0 4px">Co i gdzie włożyć</h2>
        <div class="hint" style="margin-bottom:10px">Numery szafek dla każdego zestawu.</div>
        <div class="tw"><table data-tbl="kier"><thead><tr><th>Zestaw</th>
          <th class="r">Sztuk</th><th>Szafki</th></tr></thead><tbody>
          ${Object.keys(wg).length?Object.keys(wg).map(id=>`<tr>
            <td>${esc(wg[id].s.name)}</td>
            <td class="r num">${wg[id].nry.length}</td>
            <td>${wg[id].nry.join(', ')}</td></tr>`).join('')
            :'<tr><td colspan="3" class="empty">Ten automat nie ma dziś nic do załadowania.</td></tr>'}
        </tbody></table></div></div>`;
    }

    const og = zalSuma(d.z);
    return `<div class="tiles" style="margin-bottom:12px">
      <div class="tile"><div class="lab">Szafek w trasie</div><div class="val num">${og.szt}</div>
        <div class="sub2">${maszyny.length} automatów</div></div>
      <div class="tile"><div class="lab">Zestawów</div>
        <div class="val num">${Object.keys(og.wgZestawu).length}</div><div class="sub2">rodzajów</div></div>
    </div>
    <div class="hint" style="margin-bottom:10px">Kliknij automat, żeby zobaczyć powiększony układ i numery szafek.</div>
    <div class="zal-grid">${maszyny.map(m=>{
      const s = zalSuma(d.z, m.id);
      // Kafelek jest odnośnikiem, więc przycisk nie może stać w jego środku —
      // zagnieżdżona klikalność znaczy, że nigdy nie wiadomo, co się właśnie nacisnęło.
      // Pasek rejestracji leży POD kafelkiem, w tej samej komórce siatki.
      return `<div class="zal-poz">
        <a class="card" href="#" data-kier="${m.id}" style="padding:12px;display:block;
            text-decoration:none;color:inherit">
          <div class="row dz-head kier-head" style="justify-content:space-between;align-items:center;margin-bottom:10px">
            <b>${esc(m.name)}</b>
            <div class="licz" style="text-align:right"><b>${s.szt}</b></div>
          </div>
          <div class="zal-cols">${kolumna(m,1,V.perCol,false)}${kolumna(m,V.perCol+1,V.slots,false)}</div>
        </a>
        ${paskZdarzenia(d.iso, 'automat', m.id, false)}
      </div>`;
    }).join('')||'<div class="empty">Brak czynnych automatów.</div>'}</div>`;
  });
}

/* ---------- Kontrola zasobów: jutro i pojutrze ---------- */
function vZasoby(){
  const dni = [0,1,2].map(n=>{
    const iso = przesunDate(DAY, n);
    return {iso, etykieta: n===0?'wybrany dzień':(n===1?'jutro':'pojutrze'), ...daneDnia(iso)};
  });
  const przyszle = dni.slice(1);

  const zbierz = (pole) => {
    const klucze = new Set();
    przyszle.forEach(d=>{ if(d.r) Object.keys(d.r[pole]).forEach(k=>klucze.add(k)); });
    return [...klucze].map(k=>{
      const per = przyszle.map(d=>d.r ? (d.r[pole][k]||0) : 0);
      return {k, per, razem: per.reduce((a,b)=>a+b,0)};
    });
  };

  const skl = zbierz('skladniki').map(x=>{
    if(x.k.indexOf('raw:')===0) return {...x, n:x.k.slice(4)+' (poza bazą)', jm:'', opak:null};
    const g=CALC.ing(x.k); if(!g) return null;
    return {...x, n:g.name, jm:g.unit, opak:g.packQty?x.razem/g.packQty:null};
  }).filter(Boolean).sort((a,b)=>b.razem-a.razem);

  const pp = zbierz('polprodukty').map(x=>{
    const p=CALC.prep(x.k); if(!p) return null;
    return {...x, n:p.name, jm:p.yieldUnit, partii:x.razem/(p.yieldQty||1)};
  }).filter(Boolean).sort((a,b)=>b.razem-a.razem);

  const brakZal = przyszle.filter(d=>!d.z);

  return `<div class="topbar"><h1>Kontrola zasobów</h1>
    <span class="sub">czy starczy na jutro i pojutrze</span></div>
  ${dayBar()}
  <div class="tiles" style="margin-bottom:12px">
    ${przyszle.map(d=>`<div class="tile"><div class="lab">${esc(d.etykieta)} · ${esc(dzienNazwa(d.iso))}</div>
      <div class="val num" style="font-size:18px">${d.z?esc(d.z.name):'—'}</div>
      <div class="sub2">${d.z?zalSuma(d.z).szt+' szafek':'brak załadunku'}</div></div>`).join('')}
    <div class="tile"><div class="lab">Pozycji do sprawdzenia</div>
      <div class="val num">${skl.length}</div>
      <div class="sub2">${pp.length} półproduktów</div></div>
  </div>
  ${brakZal.length?`<div class="banner"><b>${brakZal.map(d=>d.etykieta).join(' i ')}</b>
    bez przypisanego załadunku — zapotrzebowanie jest niepełne.
    <a href="#" data-go="load">Uzupełnij plan tygodnia</a></div>`:''}

  <div class="card" style="margin-bottom:12px"><h2 style="margin:0 0 4px">Składniki</h2>
    <div class="hint" style="margin-bottom:10px">Ile zejdzie w ciągu najbliższych dwóch dni.
      Kolumna „opakowań" mówi, ile trzeba mieć na stanie.</div>
    <div class="tw przyklej"><table data-tbl="zskl"><thead><tr><th>Składnik</th>
      ${przyszle.map(d=>`<th class="r">${esc(d.etykieta)}</th>`).join('')}
      <th class="r">Razem</th><th class="r">Opakowań</th></tr></thead><tbody>
      ${skl.length?skl.map(x=>`<tr><td>${esc(x.n)}</td>
        ${x.per.map(v=>`<td class="r num ${v?'':'mut'}">${v?ilosc(v):'—'}</td>`).join('')}
        <td class="r num">${ilosc(x.razem)} ${esc(x.jm||'')}</td>
        <td class="r num mut">${x.opak==null?'—':num(x.opak,2)}</td></tr>`).join('')
        :'<tr><td colspan="5" class="empty">Brak zapotrzebowania — sprawdź plan tygodnia.</td></tr>'}
    </tbody></table></div></div>

  ${pp.length?`<div class="card"><h2 style="margin:0 0 10px">Półprodukty</h2>
    <div class="tw przyklej"><table data-tbl="zpp"><thead><tr><th>Półprodukt</th>
      ${przyszle.map(d=>`<th class="r">${esc(d.etykieta)}</th>`).join('')}
      <th class="r">Razem</th><th class="r">Partii</th></tr></thead><tbody>
      ${pp.map(x=>`<tr><td>${esc(x.n)}</td>
        ${x.per.map(v=>`<td class="r num ${v?'':'mut'}">${v?ilosc(v):'—'}</td>`).join('')}
        <td class="r num">${ilosc(x.razem)} ${esc(x.jm)}</td>
        <td class="r num">${num(x.partii,2)}</td></tr>`).join('')}
    </tbody></table></div></div>`:''}`;
}

/* ============================================================================
   WIDOK: FINANSE ZAŁADUNKÓW
   ========================================================================== */
/* ---------------------------------------------------------------------------
   TYDZIEŃ DZIEŃ PO DNIU
   Suma tygodniowa mówi, ile trzeba kupić. Rozbicie na dni mówi, kiedy trzeba to
   zrobić — a to dwie różne decyzje. Poniedziałek z dwoma automatami i piątek
   z sześcioma to ta sama suma tygodniowa i zupełnie inny dzień w kuchni.
   ------------------------------------------------------------------------- */
/** [{id, n, dni:[7], razem}] w kolejności z listy — ta sama, co przy zwijaniu */
function tydzienPozycji(dni, pole, nazwa, ile, kolejnosc){
  const mapa = {};
  dni.forEach((x, i)=>{
    if(!x.r) return;
    Object.keys(x.r[pole]).forEach(id=>{
      const w = mapa[id] || (mapa[id] = {id, n:nazwa(id), dni:DNI.map(()=>0), razem:0});
      const v = ile(id, x.r[pole][id]);
      w.dni[i] += v; w.razem += v;
    });
  });
  const poz = id => { const i = kolejnosc.findIndex(x=>x.id===id); return i<0 ? 1e9 : i; };
  return Object.keys(mapa).map(id=>mapa[id]).sort((a,b)=>poz(a.id)-poz(b.id));
}
/** suma po dniach dla dowolnego zbioru wierszy */
function sumaDni(wiersze){
  return DNI.map((d, i)=>wiersze.reduce((a, w)=>a + w.dni[i], 0));
}

/** Obie tabele tygodniowe naraz — rolki grupami i zestawy. Stoją w Załadunkach,
    bo to tam układa się plan tygodnia i tam pyta się „ile tego wyjdzie". */
function tabeleTygodnia(){
  const dni = finanseTygodnia().dni;
  // pusta komórka zamiast zera — zero w tabeli to szum, a nie informacja
  const kom = v => v ? num(v, v%1 ? 1 : 0) : '<span class="mut">—</span>';
  // pusta komórka zamiast zera — tu zero znaczy „tego dnia nic nie schodzi"
  const komR = v => !v ? '<span class="mut">—</span>' : rolekHtml(v);
  const rolki = tydzienPozycji(dni, 'rolki',
    id => { const it = CALC.item(id); return it ? itName(it) : '⚠ brak rolki'; },
    (id, kaw) => { const it = CALC.item(id); return it ? kaw/(it.pieces||1) : 0; },
    DB.items);
  rolki.forEach(w=>{ const it = CALC.item(w.id); w.nk = it ? it.name : w.n;
                     w.rolek = w.razem; w.kaw = 0; });
  const grupy = rolkiWgKategorii(rolki);
  const zest = tydzienPozycji(dni, 'zestawy',
    id => { const s = CALC.set(id); return s ? s.name : '⚠ brak zestawu'; },
    (id, szt) => szt, DB.sets);

  return `<div class="card" style="margin-bottom:12px"><h2 style="margin:0 0 4px">Rolki dzień po dniu</h2>
    <div class="hint" style="margin-bottom:10px">Ile rolek każdej kategorii schodzi którego dnia.
      Liczba przy nazwie kategorii to suma grupy w tym dniu.
      <b class="ulamek">Czerwone</b> to niepełne rolki — warto dobrać liczbę zestawów tak,
      żeby schodziły całe.</div>
    <div class="tw przyklej"><table data-tbl="finRol" data-no-sort-now>
      <thead><tr><th>Rolka</th>${DNI.map(d=>`<th class="r">${esc(d.l)}</th>`).join('')}
        <th class="r">Razem</th></tr></thead><tbody>
      ${rolki.length ? grupy.map(g=>`
        <tr class="grp"><td>${esc(g.kat ? g.kat.name : 'Bez kategorii')}</td>
          ${sumaDni(g.rolki).map(v=>`<td class="r num">${komR(v)}</td>`).join('')}
          <td class="r num">${komR(g.rolki.reduce((a,w)=>a+w.razem,0))}</td></tr>
        ${g.rolki.map(w=>`<tr><td>${esc(g.kat ? (w.nk||w.n) : w.n)}</td>
          ${w.dni.map(v=>`<td class="r num">${komR(v)}</td>`).join('')}
          <td class="r num">${komR(w.razem)}</td></tr>`).join('')}`).join('')
        : `<tr><td colspan="${DNI.length + 2}" class="empty">Plan tygodnia jest pusty.</td></tr>`}
      ${rolki.length ? `<tr class="suma"><td>Razem</td>
        ${sumaDni(rolki).map(v=>`<td class="r num">${komR(v)}</td>`).join('')}
        <td class="r num">${komR(rolki.reduce((a,w)=>a+w.razem,0))}</td></tr>` : ''}
    </tbody></table></div>
  </div>

  <div class="card" style="margin-bottom:12px"><h2 style="margin:0 0 4px">Zestawy dzień po dniu</h2>
    <div class="hint" style="margin-bottom:10px">Ile sztuk którego zestawu jedzie którego dnia.</div>
    <div class="tw przyklej"><table data-tbl="finZD" data-no-sort-now>
      <thead><tr><th>Zestaw</th>${DNI.map(d=>`<th class="r">${esc(d.l)}</th>`).join('')}
        <th class="r">Razem</th></tr></thead><tbody>
      ${zest.length ? zest.map(w=>`<tr><td>${esc(w.n)}</td>
          ${w.dni.map(v=>`<td class="r num">${kom(v)}</td>`).join('')}
          <td class="r num">${kom(w.razem)}</td></tr>`).join('')
        : `<tr><td colspan="${DNI.length + 2}" class="empty">Plan tygodnia jest pusty.</td></tr>`}
      ${zest.length ? `<tr class="suma"><td>Razem</td>
        ${sumaDni(zest).map(v=>`<td class="r num">${kom(v)}</td>`).join('')}
        <td class="r num">${kom(zest.reduce((a,w)=>a+w.razem,0))}</td></tr>` : ''}
    </tbody></table></div>
  </div>`;
}

function vFinanse(){
  const f = finanseTygodnia();
  const mies = x => x * TYG_W_MIES;
  const marzaT = f.suma.netto - f.suma.koszt;

  const doWykresu = mnoznik => f.perM.filter(x=>x.wartosc>0)
    .map(x=>({name:x.m.name, cost:x.wartosc*mnoznik}));
  after('fin',()=>{
    const t = document.getElementById('chFinT');
    if(t) wireChart(t, doWykresu(1), r=>`<b>${esc(r.name)}</b>${zl(r.cost)} brutto na tydzień`);
    const m = document.getElementById('chFinM');
    if(m) wireChart(m, doWykresu(TYG_W_MIES),
      r=>`<b>${esc(r.name)}</b>${zl(r.cost)} brutto na miesiąc (${DNI_MIES} dni)`);
  });

  const wierszeMaszyn = f.perM.map(x=>{
    const netto = x.netto;
    return `<tr>
      <td>${esc(x.m.name)}${x.szt?'':' <span class="tag warn">nic nie jedzie</span>'}</td>
      <td class="r num">${x.szt}</td>
      <td class="r num">${zl(x.wartosc)}</td>
      <td class="r num mut">${zl(x.koszt)}</td>
      <td class="r num">${zl(netto - x.koszt)}</td>
      <td class="r"><span class="tag ${CALC.status(fcZ(x.koszt, x.netto))==='none'?''
        :CALC.status(fcZ(x.koszt, x.netto))}">${pct(fcZ(x.koszt, x.netto))}</span></td>
      <td class="r num">${Math.round(mies(x.szt))}</td>
      <td class="r num">${zl(mies(x.wartosc))}</td>
      <td class="r num">${zl(mies(netto - x.koszt))}</td></tr>`;
  }).join('');

  const wierszeDni = f.dni.map(x=>`<tr>
      <td>${esc(x.d.pl)}</td>
      <td>${x.z ? `<a href="#" data-go="load:${x.z.id}">${esc(x.z.name)}</a>`
                : '<span class="tag warn">brak załadunku</span>'}</td>
      <td class="r num">${x.szt}</td>
      <td class="r num">${zl(x.wartosc)}</td>
      <td class="r num mut">${zl(x.koszt)}</td></tr>`).join('');

  const wierszeZestawow = f.zestawy.map(x=>{
    const udzial = f.suma.wartosc>0 ? x.wartosc/f.suma.wartosc : null;
    return `<tr>
      <td>${esc(x.name)}</td>
      <td class="r num">${x.szt}</td>
      <td class="r num">${zl(x.wartosc)}</td>
      <td class="r num mut">${udzial==null?'—':pct(udzial,1)}</td>
      <td class="r num">${Math.round(mies(x.szt))}</td>
      <td class="r num">${zl(mies(x.wartosc))}</td></tr>`;
  }).join('');

  return `<div class="topbar"><h1>Załadunki</h1>
    <span class="sub">wolumen tygodniowy i miesięczny · ceny vendingowe</span></div>

  ${f.dniBezZaladunku ? `<div class="banner"><b>${f.dniBezZaladunku}</b> ${f.dniBezZaladunku===1
      ? 'dzień tygodnia nie ma przypisanego załadunku' : 'dni tygodnia nie ma przypisanego załadunku'} —
    wolumen jest o tyle zaniżony. <a href="#" data-go="load">Uzupełnij plan tygodnia</a></div>` : ''}

  <div class="tiles" style="margin-bottom:12px">
    <div class="tile"><div class="lab">Szafek na tydzień</div><div class="val num">${f.suma.szt}</div>
      <div class="sub2">${Math.round(mies(f.suma.szt))} na miesiąc</div></div>
    <div class="tile"><div class="lab">Wartość tygodniowa</div>
      <div class="val num">${zl(f.suma.wartosc)}</div><div class="sub2">brutto</div></div>
    <div class="tile"><div class="lab">Wartość miesięczna</div>
      <div class="val num">${zl(mies(f.suma.wartosc))}</div>
      <div class="sub2">${DNI_MIES} dni · tydzień × ${num(TYG_W_MIES,2)}</div></div>
    <div class="tile"><div class="lab">Koszt surowca</div>
      <div class="val num">${zl(mies(f.suma.koszt))}</div><div class="sub2">netto, na miesiąc</div></div>
    <div class="tile"><div class="lab">Marża miesięczna</div>
      <div class="val num">${zl(mies(marzaT))}</div>
      <div class="sub2">food cost ${pct(fcZ(f.suma.koszt, f.suma.netto))}</div></div>
  </div>

  <div class="banner">To wolumen <b>załadowany</b>, nie sprzedany — mówi, ile towaru wjeżdża
    do maszyn przy obecnym planie tygodnia. Sprzedaż będzie niższa o to, co nie zejdzie.</div>

  <div class="card" style="margin-bottom:12px"><h2 style="margin:0 0 4px">Automaty</h2>
    <div class="hint" style="margin-bottom:10px">Miesiąc liczymy jako ${DNI_MIES} dni,
      czyli tydzień × ${num(TYG_W_MIES,2)}.</div>
    <div class="tw przyklej"><table data-tbl="finM"><thead><tr><th>Automat</th>
      <th class="r">Szafek/tydz.</th><th class="r">Wartość/tydz.</th><th class="r">Koszt/tydz.</th>
      <th class="r">Marża/tydz.</th><th class="r">Food cost</th>
      <th class="r">Szafek/mies.</th><th class="r">Wartość/mies.</th><th class="r">Marża/mies.</th>
      </tr></thead><tbody>
      ${wierszeMaszyn || '<tr><td colspan="9" class="empty">Brak czynnych automatów.</td></tr>'}
      <tr class="suma"><td>Razem</td>
        <td class="r num">${f.suma.szt}</td>
        <td class="r num">${zl(f.suma.wartosc)}</td>
        <td class="r num">${zl(f.suma.koszt)}</td>
        <td class="r num">${zl(marzaT)}</td>
        <td class="r"><span class="tag ${CALC.status(fcZ(f.suma.koszt, f.suma.netto))==='none'?''
          :CALC.status(fcZ(f.suma.koszt, f.suma.netto))}">${pct(fcZ(f.suma.koszt, f.suma.netto))}</span></td>
        <td class="r num">${Math.round(mies(f.suma.szt))}</td>
        <td class="r num">${zl(mies(f.suma.wartosc))}</td>
        <td class="r num">${zl(mies(marzaT))}</td></tr>
    </tbody></table></div>
  </div>

  ${f.perM.some(x=>x.wartosc>0)?`<div class="grid"
    style="grid-template-columns:repeat(auto-fit,minmax(360px,1fr));margin-bottom:12px">
    <div class="card"><h2 style="margin:0 0 2px">Wartość tygodniowa</h2>
      <div class="hint" style="margin-bottom:8px">brutto, ceny vendingowe</div>
      <div id="chFinT">${barChartCost(doWykresu(1), 480)}</div></div>
    <div class="card"><h2 style="margin:0 0 2px">Wartość miesięczna</h2>
      <div class="hint" style="margin-bottom:8px">${DNI_MIES} dni, czyli tydzień × ${num(TYG_W_MIES,2)}</div>
      <div id="chFinM">${barChartCost(doWykresu(TYG_W_MIES), 480)}</div></div>
  </div>`:''}

  <div class="card" style="margin-bottom:12px"><h2 style="margin:0 0 10px">Tydzień dzień po dniu</h2>
    <div class="tw"><table data-tbl="finD"><thead><tr><th>Dzień</th><th>Załadunek</th>
      <th class="r">Szafek</th><th class="r">Wartość</th><th class="r">Koszt</th>
      </tr></thead><tbody>${wierszeDni}</tbody></table></div></div>

  <div class="card"><h2 style="margin:0 0 10px">Zestawy w tygodniu</h2>
    <div class="tw przyklej"><table data-tbl="finZ"><thead><tr><th>Zestaw</th>
      <th class="r">Sztuk/tydz.</th><th class="r">Wartość/tydz.</th><th class="r">Udział</th>
      <th class="r">Sztuk/mies.</th><th class="r">Wartość/mies.</th>
      </tr></thead><tbody>
      ${wierszeZestawow || '<tr><td colspan="6" class="empty">Plan tygodnia jest pusty.</td></tr>'}
    </tbody></table></div></div>`;
}

/* ============================================================================
   WIDOK: HISTORIA CEN
   ========================================================================== */
let histIng='';

/* ============================================================================
   WIDOK: GRAFIK — KALENDARZ
   ========================================================================== */
/* `zazn` to zaznaczone dni, `kotwica` — punkt, od którego Shift liczy zakres.
   Trybu zaznaczania nie ma: klik zaznacza jeden dzień, Ctrl dokłada, Shift bierze
   zakres. Tak działa każda lista plików i każdy arkusz, więc nie ma czego się uczyć. */
const GRAF = {mies:null, tryb:'mies', dzien:null, edytTydz:null,
              zazn:[], kotwica:null, komunikat:null, tylkoJa:false};

/** Czy tę osobę pokazujemy pod nazwiskiem, czy tylko jako zajęte miejsce.

    Przy pełnej obsadzie miesiąc to ściana skrótów i znalezienie w niej własnych dni
    zajmuje chwilę — od tego jest „Tylko ja". Ale ukryta osoba NIE MOŻE zniknąć z układu:
    zmiana skróciłaby się o jeden wiersz i cały kalendarz podskakiwałby przy każdym
    przełączeniu. Zostaje więc szary prostokąt tej samej wielkości: „tu ktoś stoi,
    ale nie ty". Wolne miejsce ma obrys i puste wnętrze, więc jednego z drugim
    nie da się pomylić. */
function ukrytaOsoba(osId){
  if(!GRAF.tylkoJa) return false;
  const ja = mojaOsoba();
  return !ja || osId !== ja.id;
}
function dataKrotko(iso){ return iso.slice(8) + '.' + iso.slice(5,7); }

/** Ile zmian w najbliższych dwóch tygodniach nie ma kompletu. To liczba przy
    zakładce — ma kłuć w oczy, dopóki ktoś się tym nie zajmie. */
function brakiGrafiku(){
  let n = 0;
  for(let i=0; i<14; i++){
    const iso = przesunISO(todayISO(), i);
    zmianyDnia(iso).forEach(z=>{ if(obsada(iso, z).wolne > 0) n++; });
  }
  return n;
}

const MIES_PL = ['styczeń','luty','marzec','kwiecień','maj','czerwiec','lipiec',
                 'sierpień','wrzesień','październik','listopad','grudzień'];
function miesLabel(ym){ return MIES_PL[+ym.slice(5,7) - 1] + ' ' + ym.slice(0,4); }
function przesunMies(ym, o){
  let r = +ym.slice(0,4), m = +ym.slice(5,7) - 1 + o;
  r += Math.floor(m / 12); m = ((m % 12) + 12) % 12;
  return r + '-' + String(m + 1).padStart(2,'0');
}
function dataPl(iso){
  return new Date(iso+'T00:00:00Z').toLocaleDateString('pl-PL',
    {weekday:'long', day:'numeric', month:'long', timeZone:'UTC'});
}
/** „I zmiana" w komórce kalendarza to w 80% słowo „zmiana" — zostaje sam wyróżnik. */
function skrotZmiany(n){
  return String(n||'').replace(/\s*zmian[ay]?\s*/i,'').trim() || String(n||'');
}

function vGrafik(){
  if(!GRAF.dzien) GRAF.dzien = todayISO();
  if(!GRAF.mies)  GRAF.mies  = todayISO().slice(0,7);
  const dzis = todayISO();
  const mojaOs = mojaOsoba();
  const men = mozeGrafik();
  const tydzKlucz = isoTydzien(GRAF.dzien);

  after('graf',()=>{
    document.querySelectorAll('[data-graf-dzien]').forEach(el=>el.addEventListener('click',e=>{
      wybierzDzien(el.dataset.grafDzien, e.shiftKey, e.ctrlKey || e.metaKey);
    }));
    document.querySelectorAll('[data-zazn-akcja]').forEach(b=>b.addEventListener('click',()=>{
      GRAF.zazn = [GRAF.dzien]; GRAF.komunikat = null; render();
    }));
    document.querySelectorAll('[data-zb]').forEach(b=>b.addEventListener('click',()=>{
      const [co, i] = b.dataset.zb.split('|');
      akcjaZbiorcza(co, b.dataset.zbNazwa, mojaOs);
    }));
    const pk = document.getElementById('grafPrev'), nx = document.getElementById('grafNext'),
          dz = document.getElementById('grafDzis');
    if(pk) pk.addEventListener('click',()=>{ przesunWidok(-1); render(); });
    if(nx) nx.addEventListener('click',()=>{ przesunWidok(1);  render(); });
    if(dz) dz.addEventListener('click',()=>{ GRAF.dzien = dzis; GRAF.mies = dzis.slice(0,7); render(); });
    document.querySelectorAll('[data-graf-tryb]').forEach(b=>b.addEventListener('click',()=>{
      GRAF.tryb = b.dataset.grafTryb; render();
    }));
    document.querySelectorAll('[data-graf-kogo]').forEach(b=>b.addEventListener('click',()=>{
      GRAF.tylkoJa = b.dataset.grafKogo === '1'; render();
    }));
    wireAkcjeZmian();
    const zt = document.getElementById('grafZmienTydz');
    if(zt) zt.addEventListener('click',()=>{
      // Kopiujemy szablon Z ZACHOWANIEM identyfikatorów zmian: klucz zapisu to
      // „data|id zmiany", a data należy do jednego tygodnia, więc kolizji nie ma.
      // Dzięki temu zapisy zrobione przed wyodrębnieniem tygodnia nie znikają —
      // i wracają nietknięte, gdy menedżer się rozmyśli i przywróci szablon.
      DB.shiftWeeks[tydzKlucz] = clone(DB.shiftTpl);
      save(); GRAF.edytTydz = tydzKlucz; go('grafSzab');
    });
    const pt = document.getElementById('grafPrzywroc');
    if(pt) pt.addEventListener('click',()=>{
      if(!confirm('Przywrócić szablon dla tygodnia '+tydzKlucz+'?\n\n'
        +'Ten tydzień zacznie znowu chodzić wg szablonu. Zapisy na zmiany dodane '
        +'tylko w tym tygodniu przestaną być widoczne.')) return;
      delete DB.shiftWeeks[tydzKlucz]; save(); render();
    });
    const et = document.getElementById('grafEdytTydz');
    if(et) et.addEventListener('click',()=>{ GRAF.edytTydz = tydzKlucz; go('grafSzab'); });
  });

  // Jeden pasek na wszystko: strzałki po obu stronach nazwy okresu, „Dziś" zaraz obok,
  // a po prawej godziny i przełącznik widoku. Dwa paski jeden pod drugim zabierały
  // dwa razy tyle wysokości i za każdym razem trzeba było szukać, w którym co siedzi.
  const tydzView = GRAF.tryb === 'tydz';
  const pn = poniedzialek(GRAF.dzien);
  const dniOkresu = tydzView ? DNI.map((d, i)=>przesunISO(pn, i)) : dniMiesiaca(GRAF.mies);
  const licz = godzinyDni(mojaOs ? mojaOs.id : null, dniOkresu);
  const tytul = tydzView ? 'Tydzień ' + (+tydzKlucz.slice(6)) : miesLabel(GRAF.mies);
  const podtytul = tydzView
    ? dataKrotko(pn) + '–' + dataKrotko(przesunISO(pn, 6))
    : '';

  const naglowek = `
    <div class="topbar grafbar">
      <button class="btn sm" id="grafPrev" title="Wstecz">‹</button>
      <h1 style="min-width:0">${esc(tytul)}</h1>
      <button class="btn sm" id="grafNext" title="Dalej">›</button>
      <button class="btn sm" id="grafDzis">Dziś</button>
      ${podtytul ? `<span class="sub">${esc(podtytul)}</span>` : ''}
      ${tydzView ? `${czyNadpisany(GRAF.dzien)
          ? '<span class="tag warn">własne zmiany</span>'
          : '<span class="tag">wg szablonu</span>'}
        ${men ? (czyNadpisany(GRAF.dzien)
          ? `<button class="btn sm" id="grafEdytTydz">Edytuj tydzień</button>
             <button class="btn sm" id="grafPrzywroc">Przywróć szablon</button>`
          : `<button class="btn sm" id="grafZmienTydz">Zmień ten tydzień</button>`) : ''}` : ''}
      <div class="spacer" style="flex:1"></div>
      <span class="godzsuma" title="${mojaOs ? 'Twoje godziny w tym okresie'
          : 'Wszystkie godziny w tym okresie'}">
        ${mojaOs ? '' : '<span class="mut">razem</span> '}<b>${godz(licz.godziny)}</b>
        <span class="mut">(${licz.dni} ${licz.dni === 1 ? 'dzień' : 'dni'})</span></span>
      ${mojaOs ? `<div class="pill-group">
        <button type="button" data-graf-kogo="0" class="${GRAF.tylkoJa?'':'on'}">Wszyscy</button>
        <button type="button" data-graf-kogo="1" class="${GRAF.tylkoJa?'on':''}">Tylko ja</button>
      </div>` : ''}
      <div class="pill-group">
        <button type="button" data-graf-tryb="mies" class="${GRAF.tryb==='mies'?'on':''}">Miesiąc</button>
        <button type="button" data-graf-tryb="tydz" class="${GRAF.tryb==='tydz'?'on':''}">Tydzień</button>
      </div>
    </div>`;

  const panel = panelDni(mojaOs, men);

  if(tydzView){
    const kol = DNI.map((d,i)=>{
      const iso = przesunISO(pn, i);
      const zm = zmianyDnia(iso);
      return `<div class="kol ${iso===dzis?'dzis':''} ${iso<dzis?'przeszly':''} ${
        (GRAF.zazn.length ? GRAF.zazn.indexOf(iso) >= 0 : iso === GRAF.dzien) ? 'zaz':''}">
        <h3 data-graf-dzien="${iso}" style="cursor:pointer">${esc(d.pl)}
          <span class="mut">${iso.slice(8)}.${iso.slice(5,7)}</span></h3>
        ${zm.length ? zm.map(z=>kartaZmiany(iso, z, mojaOs, men, true)).join('')
                    : '<div class="small mut">wolne</div>'}
      </div>`;
    }).join('');
    // Panelu pod spodem tu nie ma: w tygodniu zapisujesz się wprost w dniu, więc
    // panel robił drugą drogą dokładnie to samo — i to tę wolniejszą.
    const ym = GRAF.dzien.slice(0,7);
    return naglowek + `<div class="tyg">${kol}</div>` + tabelaGodzin(ym, men);
  }

  // --- siatka miesiąca ---
  const start = poniedzialek(GRAF.mies + '-01');
  const koniec = przesunMies(GRAF.mies, 1) + '-01';
  const komorki = [];
  for(let iso = start; iso < koniec || komorki.length % 7; iso = przesunISO(iso, 1)){
    komorki.push(iso);
    if(komorki.length > 42) break;
  }
  let wiersze = '';
  for(let i = 0; i < komorki.length; i += 7){
    wiersze += '<tr>' + komorki.slice(i, i+7).map(iso=>{
      const poza = iso.slice(0,7) !== GRAF.mies;
      const paski = zmianyDnia(iso).map(z=>{
        const o = obsada(iso, z);
        const ja = mojaOs && o.osoby.indexOf(mojaOs.id) >= 0;
        // Skróty przypisanych zamiast liczby, a wolne miejsce — puste miejsce po
        // plakietce. Ułamek „1/2" trzeba było przeczytać i przeliczyć, a przy okazji
        // rozpychał kafelki dnia na różne szerokości. Pusty prostokąt mówi „tu ktoś
        // ma stanąć i jeszcze nie stoi" jednym spojrzeniem na cały miesiąc.
        const kto = o.osoby.map(id=>ukrytaOsoba(id)
            ? '<span class="kod inna" title="ktoś inny"></span>'
            : skrotHtml(osoba(id))).join('')
          + '<span class="kod wolne"></span>'.repeat(o.wolne);
        return `<div class="zm ${stanZmiany(iso, o)}${ja?' ja':''}">
          <span>${esc(skrotZmiany(z.name))}</span>
          ${kto ? `<span class="ludzie">${kto}</span>` : ''}</div>`;
      }).join('');
      const zazn = GRAF.zazn.length ? GRAF.zazn.indexOf(iso) >= 0 : iso === GRAF.dzien;
      return `<td data-graf-dzien="${iso}" class="${poza?'poza':''} ${iso===dzis?'dzis':''} ${
        iso<dzis?'przeszly':''} ${zazn?'zaz':''}">
        <div class="dn">${+iso.slice(8)}</div>${paski}
        ${czyNadpisany(iso) && dniKod(iso)==='pn' ? '<span class="nadp">tydzień zmieniony</span>' : ''}
      </td>`;
    }).join('') + '</tr>';
  }

  return naglowek + `
    <table class="kal"><thead><tr>${DNI.map(d=>
      `<th><span class="dl">${esc(d.pl)}</span><span class="dk">${esc(d.l)}</span></th>`).join('')}</tr></thead>
    <tbody>${wiersze}</tbody></table>` + panel + tabelaGodzin(GRAF.mies, men);
}

/** Nazwa stanu zmiany — ta sama logika koloruje pasek w kalendarzu i ramkę kafelka. */
/** Kolor zmiany odpowiada na jedno pytanie: czy jest komplet.

    Zielony — jest. Czerwony — brakuje ludzi. Szary — dzień już był, więc nic z tym
    nie zrobisz. Wcześniej czerwień znaczyła „za mniej niż trzy dni", przez co grafik
    na przyszły miesiąc wyglądał na uporządkowany, choć nie stał na nim nikt. */
function stanZmiany(iso, o){
  if(iso < todayISO()) return 'minione';
  return o.pelna ? 'pelna' : 'brak';
}

/** Godziny w wyświetlanym miesiącu.

    Pracownik dostaje jedną liczbę — swoją. Menedżer dostaje wszystkich, którzy
    się wpisali, bo układanie grafiku to w praktyce pilnowanie, żeby godziny
    rozłożyły się równo, a nie żeby ktoś zebrał trzy razy tyle co reszta. */
/** Zestawienie dla menedżera — pod kalendarzem, nie nad nim: najpierw się patrzy,
    kto gdzie stoi, a dopiero potem sprawdza, czy godziny rozłożyły się równo. */
function tabelaGodzin(ym, men){
  if(!men) return '';
  const lista = godzinyMiesiaca(ym);
  const suma = lista.reduce((a,w)=>a + w.wgrafiku, 0);
  const wiersze = lista.map(w=>`<tr>
      <td>${skrotHtml(w.os)} ${esc(w.os.name || w.os.email || '?')}</td>
      <td class="r num">${godz(w.wgrafiku)}</td>
      <td class="r num mut">${w.zmian}</td>
    </tr>`).join('');

  return `<div class="card" style="margin-top:12px">
    <h2 style="margin:0 0 2px">Godziny · ${esc(miesLabel(ym))}</h2>
    <div class="hint">Wszyscy, którzy zapisali się w tym miesiącu, od największej liczby godzin.</div>
    <div class="tw"><table class="osoby-tab" data-tbl="godz"><thead><tr>
      <th>Osoba</th><th class="r">Godziny</th><th class="r">Zmian</th>
    </tr></thead><tbody>${wiersze
      || '<tr><td colspan="3" class="empty">Nikt się jeszcze nie zapisał</td></tr>'}</tbody></table></div>
    ${lista.length ? `<div class="kv" style="margin-top:8px"><span>Razem w grafiku</span>
      <b>${godz(suma)}</b></div>` : ''}
  </div>`;
}

/** Wpis na wszystkie zaznaczone dni naraz.

    Dni, w których zmiany o tej nazwie nie ma albo nie ma już wolnego miejsca, są
    pomijane — i wymieniane z daty. Cichy „zapisano 4 z 6" byłby gorszy od braku
    funkcji: człowiek wychodzi z przekonaniem, że stoi w sześciu dniach. */
async function akcjaZbiorcza(co, nazwa, mojaOs){
  if(!GRAF.zazn.length){ alert('Najpierw zaznacz dni w kalendarzu.'); return; }
  if(!nazwa){ alert('Nie wiadomo, o którą zmianę chodzi.'); return; }

  if(co === 'kto'){
    const wolni = active(DB.staff);
    openDlg('Wpisz na ' + GRAF.zazn.length + ' dni · ' + nazwa, `
      <div class="grid" style="grid-template-columns:1fr">
        <div>${combo('zbOs','— wybierz —')}</div>
        <div class="small mut">${GRAF.zazn.map(dataKrotko).join(', ')}</div>
      </div>`,
      [{label:'Anuluj'},
       {label:'Wpisz', cls:'pri', fn:()=>{
         const id = val('zbOs');
         if(!id){ alert('Wybierz osobę z listy.'); return false; }
         zbiorczo(nazwa, id, true);
       }}],
      ()=>fillCombo('zbOs', [PUSTY_WYBOR,
          ...wolni.map(p=>({v:p.id, l:(p.name || p.email || '?') + (p.code ? ' · ' + p.code : '')}))], ''));
    return;
  }

  if(!mojaOs && !(SRV.on && SRV.user)){
    alert('Nie wiadomo, kim jesteś — zapisy działają po zalogowaniu.'); return;
  }
  await zbiorczo(nazwa, null, co === 'on');
}

/** `osId === null` znaczy „ja". Wynik streszczamy w pasku, nie w okienku —
    lista pominiętych dat bywa długa, a okienko trzeba zamknąć, zanim się ją przeczyta. */
async function zbiorczo(nazwa, osId, on){
  const dni = GRAF.zazn.slice();
  const ciało = {op:'batch', days:dni, shiftName:nazwa, on:!!on};
  if(osId) ciało.person = osId;

  let wynik = null;
  if(SRV.on && SRV.user){
    wynik = await SRV.zbiorczo(ciało);
    if(typeof wynik === 'string'){ alert(wynik); return; }
  }else{
    const kto = osId || (mojaOsoba() || osobaZMaila(mojEmail(), true) || {}).id;
    if(!kto){ alert('Nie wiadomo, kogo wpisać.'); return; }
    const zrobione = [], pominiete = [];
    dni.forEach(iso=>{
      const z = zmianyDnia(iso).find(x=>x.name === nazwa);
      if(!z || !wpis(iso, z, kto, on)) pominiete.push(iso); else zrobione.push(iso);
    });
    save();
    wynik = {zrobione, pominiete};
  }

  const ile = wynik.zrobione.length;
  GRAF.komunikat = (on
      ? `Wpisano na <b>${ile}</b> z ${dni.length} dni.`
      : `Wypisano z <b>${ile}</b> z ${dni.length} dni.`)
    + (wynik.pominiete.length
        ? ` Pominięte (brak miejsca albo nie ma tej zmiany): <b>${
            wynik.pominiete.map(dataKrotko).join(', ')}</b>.`
        : '');
  // Zaznaczenie znika po wykonaniu — zostawione świeciłoby dalej i przy następnym
  // kliknięciu w przycisk zadziałałoby drugi raz na te same dni. Które dni odpadły,
  // mówi komunikat; jest przy panelu tak długo, aż klikniesz w kalendarz.
  GRAF.zazn = [GRAF.dzien];
  render();
}

/** Panel pod kalendarzem.

    Przy jednym dniu pokazuje ten dzień z nazwiskami — tak jak zawsze. Przy kilku
    zaznaczonych **znika data**, bo nie chodzi już o żaden konkretny dzień, i przyciski
    działają na całe zaznaczenie. Wcześniej panel zawsze pokazywał ostatnio kliknięty
    dzień, więc zapis z zaznaczonymi pięcioma dniami wchodził tylko na jeden — i wyglądało
    to jak awaria, choć każda część z osobna działała. */
function panelDni(mojaOs, men){
  const dni = GRAF.zazn.length ? GRAF.zazn : [GRAF.dzien];
  // na telefonie nie ma Ctrl-a ani Shifta, więc podpowiedź byłaby tam tylko szumem
  const podpowiedz = '<span class="mut klawisze">Ctrl+klik dokłada dzień, Shift+klik bierze zakres.</span>';
  const kom = GRAF.komunikat ? `<div class="banner" style="margin:0 0 12px">${GRAF.komunikat}</div>` : '';

  if(dni.length === 1){
    const iso = dni[0], zm = zmianyDnia(iso);
    return `<div class="card" style="margin-top:12px">
      <h2 style="margin:0 0 2px">${esc(dataPl(iso))}</h2>
      <div class="hint">${zm.length
        ? 'Jest miejsce — zapisujesz się od ręki. Gdy komplet, poproś kogoś ze składu, żeby się wypisał. '
        : 'Tego dnia szablon nie przewiduje żadnej zmiany. '}${podpowiedz}</div>
      ${kom}
      ${zm.map(z=>kartaZmiany(iso, z, mojaOs, men)).join('') || '<div class="empty">Dzień wolny</div>'}
    </div>`;
  }

  // Zmiany łączymy po NAZWIE — „I zmiana" w każdym z dni to inny wpis w bazie,
  // a w tygodniu z własnym układem także inne id. Nazwa jest tym, co użytkownik ma w głowie.
  const nazwy = [];
  dni.forEach(iso=>zmianyDnia(iso).forEach(z=>{
    if(z.name && nazwy.indexOf(z.name) < 0) nazwy.push(z.name);
  }));

  const karty = nazwy.map(nazwa=>{
    let ile = 0, wolne = 0, moje = 0;
    const godziny = new Set();
    dni.forEach(iso=>{
      const z = zmianyDnia(iso).find(x=>x.name === nazwa);
      if(!z) return;
      ile++;
      godziny.add((z.from||'?') + '–' + (z.to||'?'));
      const o = obsada(iso, z);
      if(o.wolne) wolne++;
      if(mojaOs && o.osoby.indexOf(mojaOs.id) >= 0) moje++;
    });
    const stan = wolne ? '' : 'pelna';
    return `<div class="zmk ${stan}">
      <div class="th"><b>${esc(nazwa)}</b>
        <span class="mut small">${godziny.size === 1 ? esc([...godziny][0]) : 'różne godziny'}</span>
        <span class="spacer" style="flex:1"></span>
        <span class="tag">jest w ${ile} z ${dni.length} dni</span></div>
      <div class="kv"><span>Wolne miejsce</span><b>${wolne} z ${ile} dni</b></div>
      ${mojaOs ? `<div class="kv"><span>Stoisz</span><b>${moje} z ${ile} dni</b></div>` : ''}
      <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;align-items:center">
        ${mojaOs && mogeSam() ? `<button class="btn sm ${wolne?'pri':''}" data-zb="on" data-zb-nazwa="${esc(nazwa)}"
            ${wolne?'':'disabled title="Nigdzie nie ma miejsca"'}>Zapisz mnie${
            wolne ? ' na ' + wolne + ' dni' : ''}</button>
          <button class="btn sm" data-zb="off" data-zb-nazwa="${esc(nazwa)}"
            ${moje?'':'disabled'}>Wypisz mnie${moje ? ' z ' + moje + ' dni' : ''}</button>` : ''}
        ${men ? `<button class="btn sm" data-zb="kto" data-zb-nazwa="${esc(nazwa)}"
            ${wolne?'':'disabled'}>Wpisz osobę…</button>` : ''}
      </div>
    </div>`;
  }).join('');

  return `<div class="card" style="margin-top:12px">
    <div style="display:flex;align-items:baseline;gap:8px;flex-wrap:wrap">
      <h2 style="margin:0">Ustawiasz ${dni.length} dni</h2>
      <span class="spacer" style="flex:1"></span>
      <button class="btn sm" data-zazn-akcja="czysc">Odznacz</button></div>
    <div class="hint">${dni.map(dataKrotko).join(' · ')} &nbsp; ${podpowiedz}</div>
    ${kom}
    ${karty || '<div class="empty">W zaznaczonych dniach nie ma żadnej zmiany</div>'}
  </div>`;
}

/** Klik w dzień. Zwykły zaznacza jeden, Ctrl dokłada albo zdejmuje, Shift bierze
    zakres od kotwicy. Kotwicy nie rusza Shift — dzięki temu można poprawiać zakres
    kilka razy z rzędu, tak jak w każdej liście. */
function wybierzDzien(iso, shift, ctrl){
  if(shift && GRAF.kotwica){
    const od = GRAF.kotwica < iso ? GRAF.kotwica : iso;
    const doo = GRAF.kotwica < iso ? iso : GRAF.kotwica;
    GRAF.zazn = [];
    for(let d = od; d <= doo; d = przesunISO(d, 1)) GRAF.zazn.push(d);
  }else if(ctrl){
    const i = GRAF.zazn.indexOf(iso);
    if(i < 0) GRAF.zazn.push(iso); else GRAF.zazn.splice(i, 1);
    GRAF.zazn.sort();
    GRAF.kotwica = iso;
  }else{
    GRAF.zazn = [iso];
    GRAF.kotwica = iso;
    GRAF.dzien = iso;
    if(GRAF.tryb === 'mies') GRAF.mies = iso.slice(0, 7);
  }
  GRAF.komunikat = null;
  render();
}

function przesunWidok(o){
  if(GRAF.tryb === 'mies'){
    GRAF.mies = przesunMies(GRAF.mies, o);
    // zaznaczony dzień idzie razem z widokiem, żeby panel pod kalendarzem nie został w tyle
    GRAF.dzien = GRAF.mies + '-' + GRAF.dzien.slice(8);
    if(GRAF.dzien.slice(0,7) !== GRAF.mies) GRAF.dzien = GRAF.mies + '-01';
  }else{
    GRAF.dzien = przesunISO(GRAF.dzien, 7 * o);
    GRAF.mies = GRAF.dzien.slice(0,7);
  }
}

/** Jedna zmiana: godziny, kto stoi, i przycisk do wejścia albo wyjścia. Ten sam
    kafelek jedzie w widoku tygodnia i w panelu dnia — inaczej dwie listy rozjechałyby
    się przy pierwszej zmianie wymagań. */
/** Plakietka osoby wielkości przycisku, z krzyżykiem w środku, gdy wolno wypisać.
    Ten sam element w kolumnie tygodnia niesie tożsamość, kolor i akcję naraz. */
function plakietkaOs(osId, iso, zid, moznaUsunac){
  const o = osoba(osId), k = osobaKolor(o);
  return `<span class="osgrp"><span class="osbtn" style="background:${k};color:${kontrastNa(k)}"
    data-tip="${esc(o ? (o.name || o.email || '') : 'usunięta')}">${esc(osobaSkrot(o))}</span>${
    moznaUsunac ? `<button class="btn xbtn" title="Wypisz z tej zmiany"
      data-graf-wypisz="${iso}|${zid}|${osId}">✕</button>` : ''}</span>`;
}

function kartaZmiany(iso, z, mojaOs, men, kompakt){
  const o = obsada(iso, z);
  // Na wstecz nikt się nie zapisuje sam — ale kto układa grafik, musi móc poprawić,
  // kto naprawdę stał, bo grafik bywa uzupełniany po fakcie. Serwer pilnuje tego
  // samego: zapis pracownika na miniony dzień odbija się błędem.
  const minione = iso < todayISO();
  const jestem = mojaOs && o.osoby.indexOf(mojaOs.id) >= 0;
  const stan = stanZmiany(iso, o);
  // Ułamek zniknął także tutaj: skład widać pod spodem — tyle plakietek, ilu ludzi,
  // tyle pustych miejsc, ile zostało. Liczenie tego drugi raz w nagłówku niczego
  // nie dodawało, a dokładało trzeci element do wiersza, który i tak się zawijał.
  const naglowek = `<div class="th"><b>${esc(z.name)}</b>
      <span class="mut small">${esc(z.from||'')}–${esc(z.to||'')}</span></div>`;

  // Jedno wolne miejsce = jeden klawisz. Wcześniej „Zapisz się" znikało, gdy na zmianie
  // stanął ktokolwiek — choć miejsce było dalej wolne. Skład mówi teraz to samo co siatka
  // miesiąca: tyle miejsc, ile ich zostało, i widać, które są czyje.
  const mogeSie = mojaOs && !minione && !jestem && mogeSam();
  const wolneMiejsca = Array.from({length: o.wolne}, ()=>`<span class="osgrp">${mogeSie
      ? `<button class="btn sm" data-graf-ja="${iso}|${z.id}|1">Zapisz się</button>`
      : '<span class="osbtn wolne"></span>'}${men
      ? `<button class="btn plusbtn" title="Dopisz inną osobę"
           data-graf-dodaj="${iso}|${z.id}">+</button>` : ''}</span>`).join('');

  // Panel dnia i kolumna tygodnia to ten sam skład, więc rysuje go jeden kod. Różnica
  // jest wyłącznie w szerokości: wąska kolumna ustawia miejsca w słupek (klasa `waska`),
  // szeroki panel — w rząd. Nazwiska tu nie ma: skrót mówi, kto to, a pełną listę
  // z godzinami widać pod kalendarzem.
  return `<div class="zmk ${stan} ${kompakt?'waska':''}">${naglowek}
    <div class="sklad">
      ${o.osoby.map(id=>{
        const zKlawiszem = men || (mojaOs && id === mojaOs.id && !minione && mogeSam());
        // Ukryta osoba zostawia po sobie miejsce co do piksela: także to po klawiszu,
        // który przy niej stał. Inaczej szary prostokąt byłby szerszy od plakietki obok
        // i rząd przestałby się zgadzać.
        return ukrytaOsoba(id)
          ? `<span class="osgrp"><span class="osbtn inna" title="ktoś inny"></span>${
              zKlawiszem ? '<span class="xbtn puste"></span>' : ''}</span>`
          : plakietkaOs(id, iso, z.id, zKlawiszem); }).join('')}
      ${wolneMiejsca}
      ${!o.osoby.length && !o.wolne ? '<span class="small mut">nikt się nie zapisał</span>' : ''}
    </div>
  </div>`;
}

function wireAkcjeZmian(){
  document.querySelectorAll('[data-graf-wypisz]').forEach(b=>b.addEventListener('click',()=>{
    const [iso, zid, osId] = b.dataset.grafWypisz.split('|');
    const z = zmianyDnia(iso).find(x=>x.id===zid);
    if(!z) return;
    grafZapis({op:'set', date:iso, shift:zid, person:osId, on:false},
              ()=>{ wpis(iso, z, osId, false); });
  }));
  document.querySelectorAll('[data-graf-ja]').forEach(b=>b.addEventListener('click',()=>{
    const [iso, zid, on] = b.dataset.grafJa.split('|');
    zapiszZgloszenie(iso, zid, on==='1');
  }));
  document.querySelectorAll('[data-graf-dodaj]').forEach(b=>b.addEventListener('click',()=>{
    const [iso, zid] = b.dataset.grafDodaj.split('|');
    dopiszOsobe(iso, zid);
  }));
}

/* ---------------------------------------------------------------------------
   Jedno wejście do zapisów grafiku. W trybie serwerowym idzie przez /api/shift,
   z pliku na dysku — prosto do bazy w przeglądarce. Widoki nie muszą wiedzieć,
   który to tryb; dzięki temu ta sama ścieżka działa u pracownika i u menedżera.
   ------------------------------------------------------------------------- */
async function grafZapis(ciało, lokalnie){
  if(SRV.on && SRV.user){
    const err = await SRV.zgloszenie(ciało);
    if(err){ alert(err); return false; }
    render(); return true;
  }
  if(lokalnie() === false) return false;
  save(); render(); return true;
}

/** Rejestracja zdarzenia dnia. W trybie serwerowym idzie przez /api/zdarzenie —
    tą samą wąską drogą co grafik i z tego samego powodu: klika to pracownik, a jego
    konto nie zapisuje bazy. */
async function zapiszZdarzenie(iso, rodzaj, mid, on){
  if(SRV.on && SRV.user){
    const err = await SRV.rejestruj({rodzaj, date: iso, machine: mid || undefined, on: !!on});
    if(err){ alert(err); return; }
    render(); return;
  }
  const k = kluczZdarzenia(iso, rodzaj, mid);
  DB.zdarzenia = DB.zdarzenia || {};
  if(on){
    const o = mojaOsoba();
    DB.zdarzenia[k] = {osoba: o ? o.id : null, czas: Math.floor(Date.now()/1000)};
  }else{
    delete DB.zdarzenia[k];
  }
  save(); render();
}

/** Jedna linia rejestracji: co, a po prawej stan. Ten sam komponent dla wyjazdu
    i dla automatu — różni je wyłącznie etykieta. */
function paskZdarzenia(iso, rodzaj, mid, glowny){
  const w = zdarzenie(iso, rodzaj, mid);
  const klucz = esc(rodzaj + '|' + (mid||''));
  // Etykieta pojawia się dopiero przy zapisie. Dopóki go nie ma, całą treść niesie
  // przycisk — a „Zatowarowano" obok przycisku „Zatowarowano" to ta sama informacja
  // powiedziana dwa razy (wytyczne, rozdział 8).
  if(!w){
    if(!mogeSam()) return '<div class="rej"><span class="mut">niezarejestrowane</span></div>';
    // Czerwień to akcja główna EKRANU. Na Pakowaniu taki przycisk jest jeden, więc
    // wolno mu ją nosić; u kierowcy stoi ich sześć obok siebie i czerwona ściana
    // zasłoniłaby wszystko inne — dokładnie jak przy „Zapisz się" w widoku tygodnia.
    return `<div class="rej"><button class="btn sm ${glowny?'pri':''}" data-rej="${klucz}">${
      rodzaj === 'wyjazd' ? 'Zarejestruj wyjazd' : 'Zatowarowano'}</button></div>`;
  }
  const o = osoba(w.osoba);
  return `<div class="rej"><span class="lab">${esc(ZDARZENIA_PL[rodzaj])}</span>
    <span class="stan"><span class="czas">${esc(czasZdarzenia(w, iso))}</span>
      <span class="kto">${esc(o ? (o.name || o.email || '—') : '—')}</span>${
      mogeCofnac(w) ? `<button class="btn xbtn" title="Cofnij rejestrację"
        data-rej-cofnij="${klucz}">✕</button>` : ''}</span></div>`;
}

function wireRejestr(root){
  root.querySelectorAll('[data-rej]').forEach(b=>b.addEventListener('click',e=>{
    e.preventDefault(); e.stopPropagation();
    const [rodzaj, mid] = b.dataset.rej.split('|');
    zapiszZdarzenie(DAY, rodzaj, mid, true);
  }));
  root.querySelectorAll('[data-rej-cofnij]').forEach(b=>b.addEventListener('click',e=>{
    e.preventDefault(); e.stopPropagation();
    const [rodzaj, mid] = b.dataset.rejCofnij.split('|');
    zapiszZdarzenie(DAY, rodzaj, mid, false);
  }));
}

/** Własny wpis — „zapisuję się" / „wypisuję się". */
async function zapiszZgloszenie(iso, sid, on){
  const o = mojaOsoba();
  if(!o && !(SRV.on && SRV.user)){
    alert('Nie wiadomo, kim jesteś — zapisy działają po zalogowaniu.'); return;
  }
  const z = zmianyDnia(iso).find(x=>x.id===sid);
  await grafZapis({op:'self', date:iso, shift:sid, on:!!on}, ()=>{
    if(!wpis(iso, z, (o || osobaZMaila(mojEmail(), true)).id, on)){
      alert('Na tej zmianie nie ma już wolnego miejsca.'); return false;
    }
  });
}

/** Wpisanie kogoś przez osobę układającą grafik. Lista to posiadacze kont —
    kto ma konto, ten może stanąć w grafiku, i nikt poza tym. */
function dopiszOsobe(iso, zid){
  const z = zmianyDnia(iso).find(x=>x.id===zid);
  if(!z) return;
  const o = obsada(iso, z);
  if(!o.wolne){ alert('Na tej zmianie nie ma wolnego miejsca — najpierw kogoś wypisz.'); return; }
  const wolni = active(DB.staff).filter(p=>o.osoby.indexOf(p.id) < 0);
  openDlg('Dopisz do zmiany · ' + z.name, `
    <div class="grid" style="grid-template-columns:1fr">
      <div>${combo('doOs','— wybierz —')}</div>
      <div class="small mut">Wolnych miejsc: <b>${o.wolne}</b>.</div>
      <div class="small mut">Na liście są osoby, które mają konto w aplikacji.
        Kogoś, kogo tu nie ma, dodaj najpierw w <b>Narzędzia → Użytkownicy</b>.</div>
    </div>`,
    [{label:'Anuluj'},
     {label:'Dopisz', cls:'pri', fn:()=>{
       const id = val('doOs');
       if(!id){ alert('Wybierz osobę z listy.'); return false; }
       grafZapis({op:'set', date:iso, shift:z.id, person:id, on:true}, ()=>{
         if(!wpis(iso, z, id, true)){
           alert('Ktoś właśnie zajął ostatnie miejsce.'); return false;
         }
       });
     }}],
    ()=>fillCombo('doOs', [PUSTY_WYBOR,
        ...wolni.map(p=>({v:p.id, l:(p.name || p.email || '?') + (p.code ? ' · ' + p.code : '')}))], ''));
}

/* ============================================================================
   WIDOK: SZABLON ZMIAN
   ========================================================================== */
function vGrafikSzablon(){
  const tydz = GRAF.edytTydz;
  const zrodlo = tydz ? (DB.shiftWeeks[tydz] || null) : DB.shiftTpl;
  if(tydz && !zrodlo){ GRAF.edytTydz = null; return vGrafikSzablon(); }

  after('grafSzab',()=>{
    document.querySelectorAll('[data-zm-pole]').forEach(el=>el.addEventListener('change',()=>{
      const [dk, i, pole] = el.dataset.zmPole.split('|');
      const z = zrodlo[dk][+i];
      if(!z) return;
      z[pole] = pole==='slots' ? Math.max(0, Math.round(+el.value || 0)) : el.value;
      save(); render();
    }));
    document.querySelectorAll('[data-zm-add]').forEach(b=>b.addEventListener('click',()=>{
      const dk = b.dataset.zmAdd;
      zrodlo[dk] = zrodlo[dk] || [];
      // pusty wiersz do wypełnienia — tak samo jak przy dodawaniu składnika
      zrodlo[dk].push({id: uid('zm'), name:'', from:'', to:'', slots:1});
      save(); render();
    }));
    document.querySelectorAll('[data-zm-del]').forEach(b=>b.addEventListener('click',()=>{
      const [dk, i] = b.dataset.zmDel.split('|');
      const z = zrodlo[dk][+i];
      if(z && z.name && !confirm('Usunąć zmianę „'+z.name+'"?\n\nZapisy na nią przepadną.')) return;
      zrodlo[dk].splice(+i, 1); save(); render();
    }));
    document.querySelectorAll('[data-zm-kopiuj]').forEach(b=>b.addEventListener('click',()=>{
      const dk = b.dataset.zmKopiuj;
      DNI.forEach(d=>{ if(d.k!==dk) zrodlo[d.k] = clone(zrodlo[dk]).map(z=>({...z, id: uid('zm')})); });
      save(); render();
    }));
    const wr = document.getElementById('szabWroc');
    if(wr) wr.addEventListener('click',()=>{ GRAF.edytTydz = null; go('graf'); });
    const us = document.getElementById('szabUsun');
    if(us) us.addEventListener('click',()=>{
      if(!confirm('Przywrócić szablon dla tygodnia '+tydz+'?')) return;
      delete DB.shiftWeeks[tydz]; save(); GRAF.edytTydz = null; go('graf');
    });
  });

  const sumaSlotow = DNI.reduce((s,d)=>s + (zrodlo[d.k]||[]).reduce((a,z)=>a + (z.slots||0), 0), 0);
  const karty = DNI.map(d=>{
    const lista = zrodlo[d.k] || [];
    const wiersze = lista.map((z,i)=>`
      <div class="zmline ${z.name?'':'pusty'}">
        <input type="text" value="${esc(z.name||'')}" placeholder="nazwa zmiany"
               data-zm-pole="${d.k}|${i}|name">
        ${polePory(z.from, `data-zm-pole="${d.k}|${i}|from"`)}
        ${polePory(z.to,   `data-zm-pole="${d.k}|${i}|to"`)}
        <input type="number" min="0" step="1" value="${z.slots||0}" data-zm-pole="${d.k}|${i}|slots"
               title="liczba osób na tej zmianie">
        <button class="btn sm danger" data-zm-del="${d.k}|${i}" title="Usuń zmianę">✕</button>
      </div>`).join('');
    return `<div class="card">
      <div style="display:flex;align-items:baseline;gap:8px">
        <h2 style="margin:0">${esc(d.pl)}</h2>
        <span class="tag">${lista.reduce((a,z)=>a+(z.slots||0),0)} os.</span>
      </div>
      <div class="hint" style="margin:6px 0 10px">nazwa · od · do · ile osób</div>
      ${wiersze || '<div class="small mut" style="margin-bottom:8px">dzień wolny</div>'}
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        <button class="btn sm" data-zm-add="${d.k}">+ Zmiana</button>
        ${lista.length ? `<button class="btn sm" data-zm-kopiuj="${d.k}"
          title="Skopiuj układ tego dnia na pozostałe dni tygodnia">Skopiuj na resztę</button>` : ''}
      </div>
    </div>`;
  }).join('');

  const nadpisania = Object.keys(DB.shiftWeeks||{}).sort();

  return `
  <div class="topbar"><h1>${tydz ? 'Zmiany w tygodniu ' + esc(tydz) : 'Szablon zmian'}</h1>
    <span class="sub">${sumaSlotow} osobozmian w tygodniu</span>
    <div class="spacer" style="flex:1"></div>
    ${tydz ? `<button class="btn sm danger" id="szabUsun">Przywróć szablon</button>` : ''}
    <button class="btn" id="szabWroc">← Grafik</button></div>

  <div class="banner">${tydz
    ? `Te ustawienia dotyczą <b>wyłącznie tygodnia ${esc(tydz)}</b>. Reszta miesiąca dalej
       chodzi wg szablonu. „Przywróć szablon" kasuje ten wyjątek razem z zapisami na niego.`
    : `Szablon obowiązuje <b>we wszystkich tygodniach</b>, także tych za pół roku — kalendarz
       wypełnia się nim sam. Jeden tydzień da się ustawić inaczej: w kalendarzu kliknij
       <b>Zmień ten tydzień</b>.`}</div>

  <div class="szabgrid">${karty}</div>

  ${!tydz && nadpisania.length ? `<div class="card" style="margin-top:12px">
    <h2 style="margin:0 0 2px">Tygodnie ustawione inaczej</h2>
    <div class="hint">Te tygodnie nie słuchają szablonu.</div>
    ${nadpisania.map(t=>`<div class="kv"><span>${esc(t)}</span>
      <b>${DNI.reduce((s,d)=>s+(DB.shiftWeeks[t][d.k]||[]).reduce((a,z)=>a+(z.slots||0),0),0)} os.</b></div>`).join('')}
  </div>` : ''}`;
}

function vHist(){
  const withHist=[...new Set(DB.history.map(h=>h.ingId))];
  if(!histIng && withHist.length) histIng=withHist[0];
  const pts = DB.history.filter(h=>h.ingId===histIng)
    .sort((a,b)=>a.date.localeCompare(b.date))
    .map(h=>({d:h.date, v:(h.to!=null&&h.qty)?h.to/h.qty:0, raw:h}));
  const g = CALC.ing(histIng);
  if(g && pts.length){ pts.unshift({d:pts[0].raw.date, v:(pts[0].raw.from!=null&&pts[0].raw.qty)?pts[0].raw.from/pts[0].raw.qty:0, raw:pts[0].raw}); }

  after('hist',()=>{
    fillCombo('hIng', withHist.map(i=>{const x=CALC.ing(i); return {v:i, l:x?x.name:i};}), histIng,
      v=>{ histIng=v; render(); });
    const el=document.getElementById('chHist'); if(el) wireChart(el,pts,p=>`<b>${esc(p.d)}</b>${num(p.v,4)} ${DB.settings.currency}/${esc(g?g.unit:'')}`);
  });

  const rows=[...DB.history].sort((a,b)=>b.date.localeCompare(a.date)).map(h=>{
    const gg=CALC.ing(h.ingId);
    const from = (h.from!=null&&h.qty)?h.from/h.qty:null, to=(h.to!=null&&h.qty)?h.to/h.qty:null;
    const d = (from&&to)? to/from-1 : null;
    return `<tr><td>${esc(h.date)}</td><td>${esc(gg?gg.name:h.ingId)}</td>
      <td class="r num">${h.from!=null?zl(h.from):'—'}</td><td class="r num">${h.to!=null?zl(h.to):'—'}</td>
      <td class="r"><span class="tag ${d==null?'':d>0.02?'crit':d<-0.02?'good':''}">${d==null?'—':(d>0?'+':'')+pct(d,1)}</span></td>
      <td class="mut small">${esc(h.note||'')}</td></tr>`;
  }).join('');

  return `<div class="topbar"><h1>Historia cen</h1><span class="sub">${DB.history.length} zmian</span></div>
  ${DB.history.length?'':'<div class="banner">Historia zapisuje się automatycznie za każdym razem, gdy zmienisz cenę opakowania w zakładce <b>Składniki</b>. Na start jest pusta — pierwszy wpis pojawi się po pierwszej aktualizacji cennika.</div>'}
  ${withHist.length?`<div class="card" style="margin-bottom:12px"><div class="row" style="margin-bottom:10px">
      <label class="f" style="margin:0">Składnik</label>
      ${combo('hIng','Szukaj składnika…','max-width:280px')}</div>
    <div id="chHist">${lineChart(pts)}</div></div>`:''}
  <div class="tw"><table data-tbl="hist"><thead><tr><th>Data</th><th>Składnik</th><th class="r">Cena przed</th><th class="r">Cena po</th>
    <th class="r">Zmiana</th><th>Notatka</th></tr></thead>
    <tbody>${rows||'<tr><td colspan="6" class="empty">Brak zapisanych zmian cen</td></tr>'}</tbody></table></div>`;
}

/* ============================================================================
   WIDOK: SYMULACJA
   ========================================================================== */
let simState={};
function vSim(){
  after('sim',()=>{
    fillCombo('simIng', active(DB.ingredients).filter(g=>g.packPrice!=null).map(g=>({v:g.id, l:g.name})),
      simState.ing);
    document.getElementById('simRun').addEventListener('click',()=>{
      simState={ing:val('simIng'), pct:parseFloat(val('simPct'))||0}; render();
    });
    document.getElementById('simAll').addEventListener('click',()=>{ simState={ing:'*',pct:parseFloat(val('simPct'))||0}; render(); });
    document.getElementById('simClear').addEventListener('click',()=>{ simState={}; render(); });
  });

  let result='';
  if(simState.pct){
    const backup=clone(DB.ingredients);
    DB.ingredients.forEach(g=>{ if((simState.ing==='*'||g.id===simState.ing) && g.packPrice!=null) g.packPrice*=(1+simState.pct/100); });
    const after_=DB.items.map(i=>({i, c:CALC.itemCalc(i)})).concat();
    const afterSets=DB.sets.map(s=>({s,c:CALC.setCalc(s)}));
    DB.ingredients=backup;
    const before=DB.items.map(i=>({i,c:CALC.itemCalc(i)}));
    const beforeSets=DB.sets.map(s=>({s,c:CALC.setCalc(s)}));

    const setRows=afterSets.map((a,k)=>{
      const b=beforeSets[k];
      return {label:a.s.name, v:a.c.fc||0, st:CALC.status(a.c.fc), before:b.c, after:a.c, go:{v:'sets',id:a.s.id}};
    }).filter(r=>r.v>0).sort((x,y)=>y.v-x.v);

    after('sim',()=>{ const el=document.getElementById('chSim'); if(el) wireChart(el,setRows,r=>
      `<b>${esc(r.label)}</b>food cost ${pct(r.before.fc)} → <b style="display:inline">${pct(r.after.fc)}</b><br>
       koszt ${zl(r.before.net)} → ${zl(r.after.net)}<br><span class="mut">marża ${zl(r.before.margin)} → ${zl(r.after.margin)}</span>`); });

    const worst = after_.map((a,k)=>({name:itName(a.i), b:before[k].c, a:a.c}))
      .filter(x=>x.a.fc!=null).sort((x,y)=>(y.a.fc-y.b.fc)-(x.a.fc-x.b.fc)).slice(0,10);
    const gname = simState.ing==='*'?'wszystkich składników':(CALC.ing(simState.ing)||{}).name;
    const totB=beforeSets.reduce((s,x)=>s+x.c.net,0), totA=afterSets.reduce((s,x)=>s+x.c.net,0);

    result=`<div class="grid" style="grid-template-columns:1fr 1fr;margin-top:14px">
      <div class="card"><h2>Wpływ na zestawy</h2>
        <div class="hint">Cena <b>${esc(gname)}</b> zmieniona o ${simState.pct>0?'+':''}${simState.pct}%. Najedź na słupek, żeby zobaczyć „przed → po”.</div>
        <div id="chSim">${setRows.length?barChartFc(setRows,{width:640}):'<div class="empty">Brak danych</div>'}</div></div>
      <div class="card"><h2>Najbardziej dotknięte rolki</h2>
        <div class="hint">Suma kosztu wszystkich zestawów: ${zl(totB)} → <b>${zl(totA)}</b> (${(totA-totB)>=0?'+':''}${zl(totA-totB)})</div>
        <div class="tw" style="border:0"><table data-tbl="sim"><thead><tr><th>Rolka</th><th class="r">FC przed</th><th class="r">FC po</th><th class="r">Δ</th></tr></thead>
        <tbody>${worst.map(w=>`<tr><td>${esc(w.name)}</td><td class="r num">${pct(w.b.fc)}</td>
          <td class="r num">${pct(w.a.fc)}</td>
          <td class="r"><span class="tag ${(w.a.fc-w.b.fc)>0.005?'crit':''}">${(w.a.fc-w.b.fc)>=0?'+':''}${pct(w.a.fc-w.b.fc,1)}</span></td></tr>`).join('')
          ||'<tr><td colspan="4" class="empty">Brak zmian</td></tr>'}</tbody></table></div></div>
    </div>`;
  }

  return `<div class="topbar"><h1>Symulacja „co jeśli”</h1><span class="sub">sprawdź wpływ podwyżki cen zanim uderzy w marżę</span></div>
  <div class="card"><div class="row">
    <div style="flex:1;min-width:220px"><label class="f">Składnik</label>
      ${combo('simIng','Szukaj składnika…')}</div>
    <div style="width:150px"><label class="f">Zmiana ceny %</label><input id="simPct" type="number" step="any" value="${simState.pct??10}"></div>
    <div style="align-self:flex-end;display:flex;gap:8px">
      <button class="btn pri" id="simRun">Przelicz</button>
      <button class="btn" id="simAll">Podnieś wszystko</button>
      <button class="btn" id="simClear">Wyczyść</button></div>
  </div></div>
  ${result}`;
}

/* ============================================================================
   WIDOK: UŻYTKOWNICY (tylko właściciel, tylko tryb serwerowy)
   ========================================================================== */
let USERS = null;

async function loadUsers(){
  try{
    const r = await fetch('/api/users');
    if(!r.ok){ USERS=[]; return; }
    const j = await r.json();
    USERS = j.users || [];
  }catch(e){ USERS = []; }
}

async function userApi(path, body){
  const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'},
                              body:JSON.stringify(body)});
  const j = await r.json().catch(()=>({}));
  return r.ok ? null : (j.error || ('Błąd '+r.status));
}

/* Kolejność ma znaczenie: od pełnych praw do samego patrzenia. Tak wychodzi lista
   ról na ekranie Użytkowników i tak układa się rozwijana lista w edytorze konta. */
const ROLE_PL = {owner:'właściciel', admin:'administrator', staff:'pracownik', viewer:'podgląd'};
const ROLE_DESC = {
  owner:'Wszystko. Jego konta nikt inny nie usunie ani nie zdegraduje — także administrator.',
  admin:'To samo co właściciel: ceny, receptury, grafik i konta. Nie rusza tylko konta właściciela.',
  staff:'Panel dnia, grafik i receptury z gramaturami. Zapisuje się na zmiany. Cen nie widzi '
       +'wcale — serwer wysyła mu bazę już bez nich, więc nie ma ich nawet w konsoli.',
  viewer:'To samo co pracownik, ale niczego nie zmienia — nawet własnego wpisu w grafiku. '
        +'Na tablet w kuchni: sprawdzić, kto jutro stoi, i zajrzeć w recepturę.',
};
/* WYJĄTEK od zasady „kolory statusu znaczą stan". Rola nie jest stanem, ale na ekranie
   Użytkowników jest tematem: cztery zakresy uprawnień trzeba od siebie odróżnić jednym
   spojrzeniem, a lista kont jest jedynym miejscem, gdzie te słowa w ogóle występują —
   nie stoją obok food costu ani obsady zmian, więc nie da się ich z nimi pomylić.
   Poza tym ekranem rola jest zwykłym tekstem.

   Dwa górne poziomy są pokolorowane, bo one zapisują; dwa dolne zostają szare — czerwona
   plakietka przy najzwyklejszym koncie w lokalu czytałaby się jak ostrzeżenie. */
const ROLE_CLS = {owner:'good', admin:'warn', staff:'', viewer:''};

function vUsers(){
  if(USERS === null){
    after('users', async ()=>{ await loadUsers(); render(); });
    return `<div class="topbar"><h1>Użytkownicy</h1></div>
            <div class="card"><div class="empty">Wczytuję konta…</div></div>`;
  }
  document.getElementById('cUsers').textContent = USERS.length;

  after('users',()=>{
    document.querySelector('[data-act="addUser"]').addEventListener('click',()=>editUser(null));
    document.querySelectorAll('[data-edit-user]').forEach(b=>
      b.addEventListener('click',()=>editUser(b.dataset.editUser)));

  });

  const ym = todayISO().slice(0,7);
  const rows = USERS.map(u=>{
    const me = SRV.user && SRV.user.email === u.email;
    const cls = ROLE_CLS[u.role] || '';
    const os = osobaZMaila(u.email, false);
    const g = os ? godzinyOsoby(os.id, ym) : {wgrafiku:0, zmian:0};
    return `<tr>
      <td>${os && os.name ? '<b>'+esc(os.name)+'</b>'
              : '<span class="mut" title="Konto bez wpisu w grafiku">—</span>'}</td>
      <td>${os ? skrotHtml(os) : '<span class="mut">—</span>'}</td>
      <td>${esc(u.email)}${me?' <span class="tag" style="margin-left:6px">to Ty</span>':''}</td>
      <td><span class="tag ${cls}">${esc(ROLE_PL[u.role]||u.role)}</span></td>
      <td class="r num">${g.wgrafiku ? godz(g.wgrafiku) : '<span class="mut">—</span>'}</td>
      <td class="r mut">${u.created?esc(new Date(u.created*1000).toLocaleDateString('pl-PL')):'—'}</td>
      <td class="r">
        <button class="btn sm" data-edit-user="${esc(u.email)}">Edytuj</button>
      </td></tr>`;
  }).join('');

  return `
  <div class="topbar"><h1>Użytkownicy</h1><span class="sub">${USERS.length} kont ·
    godziny za ${esc(miesLabel(ym))}</span>
    <div class="spacer"></div>
    <button class="btn pri" data-act="addUser">+ Konto</button></div>

  <div class="tw"><table class="osoby-tab" data-tbl="users"><thead><tr>
    <th>Osoba</th><th>Skrót</th><th>E-mail</th><th>Rola</th>
    <th class="r" title="W bieżącym miesiącu; pełne zestawienie jest w Grafiku">Godziny</th>
    <th class="r">Dodane</th><th data-nosort></th>
  </tr></thead><tbody>${rows||'<tr><td colspan="7" class="empty">Brak kont</td></tr>'}</tbody></table></div>

  <div class="card" style="margin-top:12px"><h2>Role</h2>
    <div class="hint">Co która rola może zrobić</div>
    <div class="tiles-grid" style="margin-top:8px;grid-template-columns:repeat(auto-fit,minmax(200px,1fr))">
      ${Object.keys(ROLE_PL).map(r=>`
        <div>
          <span class="tag ${ROLE_CLS[r]||''}">${esc(ROLE_PL[r])}</span>
          <div class="small mut" style="margin-top:5px">${esc(ROLE_DESC[r])}</div>
        </div>`).join('')}
    </div>
    <div class="small mut" style="margin-top:12px">
      Nie da się odebrać uprawnień ani usunąć konta samemu sobie — dzięki temu zawsze
      zostaje ktoś, kto może zarządzać kontami.
    </div>
  </div>`;
}

function editUser(email){
  const u = email ? USERS.find(x=>x.email===email) : null;
  const me = u && SRV.user && SRV.user.email === u.email;
  const os = u ? osobaZMaila(u.email, false) : null;
  const kolorAkt = os && os.color ? os.color : '';
  // Kolor to podpis człowieka na kalendarzu — warto wiedzieć, że ktoś już się nim podpisuje.
  const zajete = {};
  active(DB.staff || []).forEach(x=>{
    if(!x.color || (os && x.id === os.id)) return;
    if(!zajete[x.color]) zajete[x.color] = x.name || x.email || '';
  });
  openDlg(u ? 'Edytuj konto' : 'Nowe konto', `
    <div class="grid" style="grid-template-columns:1fr 1fr">
      <div><label class="f">E-mail</label>
        <input id="uMail" type="email" value="${esc(u?u.email:'')}" ${u?'disabled':''}
               placeholder="kucharz@lokal.pl"></div>
      <div><label class="f">Rola</label>
        <select id="uRole" ${me?'disabled':''}>
          ${Object.keys(ROLE_PL).map(r=>
            `<option value="${r}" ${(u?u.role:'staff')===r?'selected':''}>${esc(ROLE_PL[r])}</option>`).join('')}
        </select>
        ${me?'<div class="small mut" style="margin-top:5px">Nie możesz zmienić własnej roli.</div>':''}</div>
      <div style="grid-column:1/-1" class="small mut" id="uOpisRoli">${esc(ROLE_DESC[u?u.role:'staff']||'')}</div>
      <div style="grid-column:1/-1">
        <label class="f">${u?'Nowe hasło (zostaw puste, żeby nie zmieniać)':'Hasło'}</label>
        <input id="uPass" type="password" autocomplete="new-password" placeholder="minimum 8 znaków"></div>
      <div style="grid-column:1/-1" class="small mut">
        Hasło zapisujemy wyłącznie w postaci zaszyfrowanej — nie da się go później odczytać,
        można je tylko ustawić na nowo.
      </div>
      ${u && !me ? `<div style="grid-column:1/-1"><div class="ryzyko">
        <div class="txt"><b>Usunięcie konta</b>
          <div class="hint">Ta osoba straci dostęp natychmiast. Dane lokalu i jej godziny
            w grafiku zostają nietknięte.</div></div>
        <div class="row"><button type="button" class="btn sm danger" id="uUsun">Usuń konto</button></div>
      </div></div>` : ''}

      <div style="grid-column:1/-1;border-top:1px solid var(--grid);padding-top:12px">
        <b style="font-size:13px">W grafiku</b>
        <div class="small mut" style="margin-top:3px">Tak ta osoba będzie podpisana na kalendarzu.</div>
      </div>
      <div><label class="f">Imię i nazwisko</label>
        <input id="uNazwa" type="text" value="${esc(os && os.name ? os.name : '')}"
               placeholder="${esc(u ? u.email.split('@')[0] : 'Ania Kowalska')}"></div>
      <div><label class="f">Skrót (do 6 znaków)</label>
        <input id="uSkrot" type="text" maxlength="6" value="${esc(os && os.code ? os.code : '')}"
               style="letter-spacing:.06em;font-weight:600" placeholder="np. MarPro">
        <div class="small mut" style="margin-top:4px">Puste — weźmiemy początek imienia.</div></div>
      <div><label class="f">Znak na telefonie (1 litera)</label>
        <input id="uZnak" type="text" maxlength="1" value="${esc(os && os.znak ? os.znak : '')}"
               style="letter-spacing:.06em;font-weight:700;text-align:center;max-width:90px">
        <div class="small mut" id="uZnakInfo" style="margin-top:4px"></div></div>
      <div style="grid-column:1/-1"><label class="f">Kolor</label>
        <div class="kolorwiersz">
          <div id="uKolory" class="kolorsiatka">
            ${KOLORY_OSOB.map(k=>`
              <div class="kolorpole">
                <button type="button" class="kolorbtn ${k.v===kolorAkt?'on':''}" data-kolor="${k.v}"
                  title="${esc(k.l)}${zajete[k.v] ? ' — ma go już ' + esc(zajete[k.v]) : ''}"
                  style="background:${k.v}"></button>
                <span class="kolorznak ${zajete[k.v] ? '' : 'pusty'}"></span>
              </div>`).join('')}
          </div>
          <div class="kolorpodglad">
            <span class="small mut">Podgląd</span>
            <div class="plakietki" id="uPodglad"></div>
            <button type="button" class="btn sm" id="uBezKoloru">Bez koloru</button>
          </div>
        </div>
        <div class="small mut" style="margin-top:7px">Szesnaście odcieni rozłożonych równo
          po kole barw, co drugi ciemniejszy — żeby sąsiednie różniły się także jasnością,
          a więc i na wydruku, i przy niedowidzeniu barw. Bez szarości i bez firmowej
          czerwieni: te znaczą w aplikacji co innego. Szara kreska pod próbką znaczy, że ten
          kolor nosi już ktoś inny — wybrać go można, ale dwie takie same plakietki na jednej
          zmianie trudno rozróżnić.</div></div>
    </div>`,
    [{label:'Anuluj'},
     {label:'Zapisz', cls:'pri', fn:async ()=>{
       const em = (u ? u.email : val('uMail').trim().toLowerCase());
       const pw = val('uPass');
       const role = val('uRole');
       if(!em || em.indexOf('@')<0){ alert('Podaj poprawny adres e-mail.'); return false; }
       if(!u && pw.length < 8){ alert('Hasło musi mieć co najmniej 8 znaków.'); return false; }
       if(u && pw && pw.length < 8){ alert('Hasło musi mieć co najmniej 8 znaków.'); return false; }
       const err = u
         ? await userApi('/api/users/update', {email:em, role: me?undefined:role,
                                              password: pw||undefined})
         : await userApi('/api/users', {email:em, role, password:pw});
       if(err){ alert(err); return; }
       // Skrót i kolor to dane grafiku, nie konta — siedzą w bazie lokalu, żeby widział
       // je każdy, kto ogląda kalendarz, a nie tylko właściciel z dostępem do listy kont.
       // Skrót zostaje taki, jak go ktoś wpisał. Wersaliki na siłę robiły z „MarPro"
       // → „MARPRO", a to jest czyjś podpis na kalendarzu, nie kod z bazy.
       const nazwa = val('uNazwa').trim(), skrot = val('uSkrot').trim().slice(0,6);
       const znak = val('uZnak').trim().slice(0,1);
       const kolor = document.querySelector('#uKolory .kolorbtn.on');
       const kolorV = kolor ? kolor.dataset.kolor : '';
       if(nazwa || skrot || znak || kolorV || osobaZMaila(em, false)){
         const o = osobaZMaila(em, true);
         o.name = nazwa || o.name || em.split('@')[0];
         o.code = skrot || null;
         o.znak = znak || null;                 // puste = licz z pierwszej litery skrótu
         o.color = kolorV || null;
         save();
       }
       await loadUsers(); render();
     }}],
    ()=>{
      const sel = document.getElementById('uRole'), opis = document.getElementById('uOpisRoli');
      if(sel && opis) sel.addEventListener('change',()=>{ opis.textContent = ROLE_DESC[sel.value]||''; });

      /* Podgląd, a nie wyobraźnia: próbka koloru to kwadrat, a plakietka to napis na
         kolorze — dopiero na niej widać, czy skrót się czyta. Pokazujemy WSZYSTKIE trzy
         postacie, w jakich plakietka stoi na ekranie: wąską z siatki miesiąca, tę z obsady
         zmiany i jednoliterową z telefonu. Ta trzecia jest tu najważniejsza, bo to o nią
         chodzi w polu obok, a nigdzie indziej w tym oknie jej nie widać. */
      const odswiezPodglad = ()=>{
        const cel = document.getElementById('uPodglad');
        if(!cel) return;
        const wyb = document.querySelector('#uKolory .kolorbtn.on');
        const k = (wyb && wyb.dataset.kolor) || KOLOR_DOMYSLNY;
        const dane = {code: val('uSkrot').trim().slice(0,6),
                      znak: val('uZnak').trim().slice(0,1),
                      name: val('uNazwa').trim(),
                      email: (u ? u.email : val('uMail')) || ''};
        const podpis = osobaSkrot(dane), litera = osobaZnak(dane);
        const styl = `background:${k};color:${kontrastNa(k)}`;
        // `data-tip`, nie `title` — plakietka w całej aplikacji nosi nasz dymek,
        // a nie żółte pudełko systemu
        const tip = esc(val('uNazwa').trim() || (u ? u.email : val('uMail')) || '');
        cel.innerHTML = `<span class="kod" data-tip="${tip}" style="${styl};width:54px;`
          + `line-height:1.3;padding:0;display:inline-flex;align-items:center;`
          + `justify-content:center;overflow:hidden">${esc(podpis)}</span>`
          + `<span class="kod" data-tip="${tip}" style="${styl};width:14px;height:15px;`
          + `line-height:1;padding:0;border-radius:3px;font-size:9.5px;display:inline-flex;`
          + `align-items:center;justify-content:center">${esc(litera)}</span>`
          + `<span class="osbtn" data-tip="${tip}" style="${styl}">${esc(podpis)}</span>`;

        /* Ta sama litera u dwóch osób znaczy, że na telefonie nie da się ich rozróżnić —
           dokładnie ten problem, dla którego to pole powstało. Nie blokujemy (dwie osoby
           na jednej zmianie to nie to samo, co dwie osoby w firmie), ale ma to być widać
           PRZED zapisaniem, a nie dopiero w kalendarzu. */
        /* W pustym polu stoi litera, która pójdzie sama ze skrótu — szara, więc widać,
           że to podpowiedź, a nie wpis. Sztywne „M" kłamałoby przy każdym innym imieniu. */
        const pz = document.getElementById('uZnak');
        if(pz) pz.placeholder = osobaSkrot(dane).slice(0, 1).toUpperCase();

        const info = document.getElementById('uZnakInfo');
        if(!info) return;
        const mail = (u ? u.email : val('uMail')).trim().toLowerCase();
        const kolizja = (DB.staff || []).filter(x=>x && x.id !== (os && os.id)
            && String(x.email || '').toLowerCase() !== mail
            && osobaZnak(x).toLowerCase() === litera.toLowerCase())
          .map(x=>x.name || x.email).slice(0, 3);
        info.classList.toggle('uwaga-txt', !!kolizja.length);
        info.textContent = kolizja.length
          ? 'Ten znak nosi już ' + kolizja.join(', ') + ' — na telefonie będą nie do odróżnienia.'
          : 'Puste — weźmiemy pierwszą literę skrótu. Tym znakiem osoba jest podpisana'
            + ' w kalendarzu na telefonie.';
      };
      document.querySelectorAll('#uKolory .kolorbtn').forEach(b=>b.addEventListener('click',()=>{
        document.querySelectorAll('#uKolory .kolorbtn').forEach(x=>x.classList.remove('on'));
        b.classList.add('on');
        odswiezPodglad();
      }));
      const bez = document.getElementById('uBezKoloru');
      if(bez) bez.addEventListener('click',()=>{
        document.querySelectorAll('#uKolory .kolorbtn').forEach(x=>x.classList.remove('on'));
        odswiezPodglad();
      });
      ['uSkrot','uNazwa','uZnak'].forEach(id=>{
        const p = document.getElementById(id);
        if(p) p.addEventListener('input', odswiezPodglad);
      });
      odswiezPodglad();
      // Kasowanie mieszka tam, gdzie edycja — nie w wierszu listy. Krzyżyk przy każdym
      // wierszu stoi milimetry od „Edytuj", a robi rzecz nieodwracalną.
      const us = document.getElementById('uUsun');
      if(us) us.addEventListener('click', async ()=>{
        if(!confirm('Usunąć konto ' + u.email + '?\n\nTa osoba straci dostęp natychmiast. '
          + 'Dane lokalu zostają nietknięte.')) return;
        const err = await userApi('/api/users/delete', {email:u.email});
        if(err){ alert(err); return; }
        DLG.close(); await loadUsers(); render();
      });
    });
}

/* ============================================================================
   WIDOK: SPRZEDAŻ — co automaty naprawdę sprzedały

   Dane NIE siedzą w bazie aplikacji, tylko w osobnych plikach miesięcznych na serwerze
   (patrz `server.py`). Baza leci do przeglądarki przy każdym wczytaniu, a sprzedaż rośnie
   o kilkadziesiąt wpisów dziennie — doklejona do katalogu receptur zdusiłaby ją w rok.
   Dlatego ten jeden ekran dociąga swój miesiąc osobnym żądaniem, na żądanie.
   ========================================================================== */
let SPRZ_MIES = null, SPRZ = null, SPRZ_BLAD = null, SPRZ_WYNIK = null;

/* Wykresy mają WŁASNY zakres i własne dane, liczone zawsze od dzisiaj — pasek miesiąca
   u góry ekranu rządzi tabelami. Dwa sterowania czasem na jednym ekranie brzmią jak
   pomyłka, ale pytania są dwa różne: „ile poszło w marcu" i „jak idzie ostatnio". */
let SPRZ_ZAKRES = {mies: 365, dzien: 30, tydz: 365, raport: 365};
/* Sprzedaż na Pulpicie: trzymamy WPISY z ostatnich 30 dni wstecz od dnia z paska.
   `klucz` to zakres, dla którego zostały pobrane — zmiana dnia na pasku przestawia
   zakres i wtedy trzeba pobrać na nowo, ale przełączanie się między ekranami już nie. */
let SPRZ_PUL = null, SPRZ_PUL_KLUCZ = null, SPRZ_PUL_BLAD = null;

/* Raport: układ ('aut' — automat w dniach tygodnia, 'dzien' — dzień w automatach),
   który automat ('' = wszystkie razem) i który dzień tygodnia. */
let SPRZ_RAPORT = {wg: 'aut', automat: '', dzien: 0};
let SPRZ_WYK = null;                 // SUROWE wpisy z ostatnich 14 miesięcy
let SPRZ_RESIZE = false;             // nasłuch zmiany szerokości zakładamy raz

/** Przełącznik zakresu — ten sam przy obu wykresach. */
function paskZakresu(ktory){
  const opcje = [[7, '7 dni'], [30, 'miesiąc'], [365, 'rok']];
  return `<div class="pill-group" data-zakres="${ktory}">${opcje.map(([v, n])=>
    `<button type="button" data-z="${v}" class="${SPRZ_ZAKRES[ktory]===v?'on':''}">${n}</button>`
  ).join('')}</div>`;
}

/** Oś pionowa: krok w okrągłych liczbach, zakres wpasowany w dane.

    Dwie decyzje naraz.

    **Krok z rodziny 1 / 2 / 5 × 10ⁿ**, dobrany tak, żeby wypadły trzy albo cztery linie.
    Dzieląc zamiast tego zakres na równe części, dostawaliśmy podziałki w rodzaju 32 231 —
    liczbę, której nikt nie czyta, bo nie da się jej z niczym porównać.

    **Oś nie musi zaczynać się od zera.** Sprzedaż lokalu chodzi między czterdziestoma
    a osiemdziesięcioma tysiącami; oś od zera zajmuje wtedy połowę wysokości pustką,
    a różnice — czyli to, po co się na wykres patrzy — spłaszcza. Dół i górę zaokrąglamy
    do kroku, więc podziałki zostają okrągłe mimo przesuniętego początku. */
function skalaOs(min, max){
  if(!isFinite(min) || !isFinite(max)) return null;
  if(max === min){                       // jedna wartość — dajemy jej trochę oddechu
    const k = Math.pow(10, Math.floor(Math.log10(Math.abs(max) || 1)));
    return {krok: k, dol: max - k, gora: max + k};
  }
  const rzad = Math.pow(10, Math.floor(Math.log10(max - min)));
  let zapas = null;
  for(const m of [0.1, 0.2, 0.5, 1, 2, 5, 10]){
    const krok = m * rzad;
    const dol = Math.floor(min / krok) * krok, gora = Math.ceil(max / krok) * krok;
    const ile = Math.round((gora - dol) / krok);
    if(ile >= 3 && ile <= 5) return {krok, dol, gora};
    if(ile >= 2 && !zapas) zapas = {krok, dol, gora};
  }
  return zapas || {krok: rzad, dol: Math.floor(min / rzad) * rzad,
                   gora: Math.ceil(max / rzad) * rzad};
}

/** Kolor automatu: wybrany w edycji, a jak nie wybrano — z palety, według pozycji. */
function kolorAutomatu(m, i){
  return m.kolor || KOLORY_SERII[i % KOLORY_SERII.length];
}

const DNI_TYG = ['pn', 'wt', 'śr', 'cz', 'pt', 'so', 'nd'];

/** Średnia sprzedaż w poszczególne dni tygodnia.

    Siedem punktów zamiast osi czasu: pytanie brzmi „ile schodzi w sobotę, a ile we
    wtorek", a nie „jak było w minionym tygodniu". Dzielimy przez liczbę TYCH dni,
    które naprawdę znamy — automat postawiony w środę nie miał jeszcze poniedziałku
    i zaniżałby sobie średnią, gdyby liczyć wszystkie dni zakresu. */
function srednieDniTygodnia(dzienne, zakres, pierwszy, pierwszyLokal){
  const koniec = todayISO(), start = przesunISO(koniec, -(zakres - 1));
  const dni = [];
  for(let iso = start; iso <= koniec; iso = przesunISO(iso, 1)) dni.push(iso);
  const nrDnia = iso => (new Date(iso + 'T12:00:00').getDay() + 6) % 7;

  const licz = (mid, od)=>{
    const suma = [0,0,0,0,0,0,0], ile = [0,0,0,0,0,0,0];
    dni.forEach(iso=>{
      if(!od || iso < od) return;
      const n = nrDnia(iso), d = dzienne[iso];
      ile[n]++;
      if(!d) return;
      suma[n] += (mid == null ? Object.keys(d).reduce((a,x)=>a + d[x], 0) : (d[mid] || 0));
    });
    return suma.map((s,n)=>ile[n] ? s / ile[n] : null);
  };
  return {
    opisy: DNI_TYG,
    razem: licz(null, pierwszyLokal),
    dla: mid => licz(mid, pierwszy[mid])
  };
}

/** Okno kroczące policzone NA KAŻDY DZIEŃ zakresu.

    Oba wykresy pokazują to samo w osi poziomej — kolejne dni — a różnią się tym, co
    liczą w oknie: „Sprzedaż miesięczna" sumuje trzydzieści dni wstecz, „Sprzedaż
    dzienna" uśrednia siedem. Miesiąc kalendarzowy jako słupek nie mówił nic: dwanaście
    punktów w roku, z których ostatni jest zawsze niepełny.

    **Linia zaczyna się dopiero przy PEŁNYM oknie.** Suma z trzydziestu dni policzona
    w trzecim dniu istnienia automatu jest sumą z trzech dni i rysuje wzniesienie, którego
    nie było — a wykres kroczący czyta się właśnie po nachyleniu. Zamiast tego zostawiamy
    tam pustkę: nie wiemy, i tyle. */
function pierwszeDni(dzienne){
  const pierwszy = {}, dostepne = Object.keys(dzienne).sort();
  dostepne.forEach(iso=>Object.keys(dzienne[iso]).forEach(mid=>{
    if(!pierwszy[mid]) pierwszy[mid] = iso; }));
  return {pierwszy, lokal: dostepne.length ? dostepne[0] : null};
}

function oknaKroczace(dzienne, zakres, okno, srednia){
  const koniec = todayISO(), start = przesunISO(koniec, -(zakres - 1));
  const p = pierwszeDni(dzienne), pierwszy = p.pierwszy, pierwszyLokal = p.lokal;

  let dni = [];
  for(let iso = start; iso <= koniec; iso = przesunISO(iso, 1)) dni.push(iso);

  const suma = (iso, mid)=>{
    let s = 0;
    for(let k = 0; k < okno; k++){
      const d = dzienne[przesunISO(iso, -k)];
      if(d) s += (mid == null
        ? Object.keys(d).reduce((a,x)=>a + d[x], 0)
        : (d[mid] || 0));
    }
    return srednia ? s / okno : s;
  };
  const pelne = (iso, od)=> od && przesunISO(iso, -(okno - 1)) >= od;

  /* Zakres przycinamy do tego, co naprawdę mamy. Wybrany rok, z którego znamy trzy
     miesiące, rysowany w całości to trzy czwarte pustego panelu i dane ściśnięte
     w rogu — a szerokość jest tu tym, co pozwala cokolwiek odczytać. Pierwszy dzień
     z pełnym oknem dla całego lokalu jest najwcześniejszym, jaki w ogóle da się
     narysować: automat nie może mieć pełnego okna wcześniej niż lokal. */
  const doRysowania = dni.map(iso=>pelne(iso, pierwszyLokal));
  const od = doRysowania.indexOf(true);
  const do_ = doRysowania.lastIndexOf(true);
  dni = od < 0 ? [] : dni.slice(od, do_ + 1);

  return {
    dni: dni,
    opisy: dni.map(iso=>iso.slice(8) + '.' + iso.slice(5,7)),
    razem: dni.map(iso=>suma(iso, null)),
    dla: mid => dni.map(iso=>pelne(iso, pierwszy[mid]) ? suma(iso, mid) : null)
  };
}

/* Bierzemy dwa miesiące, nie jeden. Suma z ostatnich trzydziestu dni policzona
   pierwszego dnia miesiąca sięga w poprzedni — bez niego wykres narastający zaczynałby
   każdy miesiąc od zera i pokazywał wzrost, którego nie ma. */
async function wczytajSprzedaz(ym){
  if(!(SRV.on && SRV.user)){ SPRZ = {}; SPRZ_BLAD = 'lokalnie'; return; }
  const miesiac = async (m)=>{
    const r = await fetch('/api/sprzedaz?ym=' + encodeURIComponent(m));
    const j = await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(j.error || ('Błąd ' + r.status));
    return j.sprzedaz || {};
  };
  try{
    const [poprzedni, biezacy] = await Promise.all([miesiac(przesunMies(ym, -1)), miesiac(ym)]);
    SPRZ = Object.assign({}, poprzedni, biezacy); SPRZ_BLAD = null;
  }catch(e){ SPRZ = {}; SPRZ_BLAD = e.message || 'Brak połączenia z serwerem.'; }
  // Wykresy patrzą rok wstecz i zawsze od dzisiaj, więc mają własny zbiór. Trzynaście
  // miesięcy idzie JEDNYM żądaniem — inaczej byłoby ich trzynaście.
  if(!SPRZ_WYK){
    const dzis = todayISO().slice(0,7);
    try{
      // Czternaście miesięcy, nie trzynaście: okno kroczące najstarszego rysowanego dnia
      // sięga jeszcze miesiąc wstecz, a bez tych danych zaczynałoby się od niepełnej sumy.
      const r = await fetch('/api/sprzedaz?od=' + przesunMies(dzis, -14) + '&do=' + dzis);
      SPRZ_WYK = r.ok ? ((await r.json()).sprzedaz || {}) : {};
    }catch(e){ SPRZ_WYK = {}; }
  }
}

/** Dzień sprzedaży liczony po czasie LOKALNYM.

    `toISOString()` daje czas uniwersalny, czyli latem o dwie godziny wcześniejszy —
    sprzedaż z pierwszej w nocy lądowała przez to w dniu poprzednim. Serwer dzieli pliki
    po czasie lokalnym i człowiek patrzy na zegar tak samo, więc przeglądarka nie ma
    powodu robić inaczej. */
function isoSprzedazy(czas){
  const d = new Date(czas * 1000);
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0')
         + '-' + String(d.getDate()).padStart(2, '0');
}

/** Sprzedaż rozpisana na dni i automaty: {'2026-08-01': {'aut-x': 128.5}}. */
function dzienneSprzedazy(wpisy){
  const d = {};
  Object.keys(wpisy).forEach(k=>{
    const w = wpisy[k];
    if(!w || w.nieznane || !w.maszyna || !w.czas) return;
    const iso = isoSprzedazy(w.czas);
    const dz = d[iso] || (d[iso] = {});
    dz[w.maszyna] = (dz[w.maszyna] || 0) + (w.kwota || 0);
  });
  return d;
}

/** Wykres o DWÓCH skalach: cały lokal u góry, automaty niżej.

    Suma jest kilka razy wyższa od pojedynczego automatu. Na jednej skali przygniata je
    do dolnego centymetra wykresu i o automatach nie da się już nic powiedzieć — a to
    właśnie one są tu ciekawe. Więc suma dostaje własny pas i własną oś. Wspólna zostaje
    oś pozioma i to ona pozwala oba pasy czytać razem.

    Szerokość bierzemy z KONTENERA, nie ze stałej: jedna jednostka SVG to wtedy jeden
    piksel, więc na telefonie pismo nie maleje i wykres nie wystaje poza kartę. */
function wykresPasy(el, opisy, razem, serie){
  const waski = el.clientWidth < 560;
  const W = Math.max(280, el.clientWidth);
  const H = waski ? 300 : 360;
  const PL = waski ? 42 : 60, PB = 26;
  /* Przy liniach stoją WYŁĄCZNIE kody automatów — nigdy nazwy ani adresy. Nazwa bywa
     długa („Kaufland, Norymberska") i albo wychodzi poza kartę, albo trzeba ją uciąć
     w połowie; ucięta nazwa jest gorsza od kodu, bo kod jest krótki, jednoznaczny
     i ten sam, którym automat podpisany jest na załadunku i w tabelach. */
  const najdluzszy = serie.reduce((n, ser)=>Math.max(n, (ser.kod || '').length), 5);
  const PR = waski ? 46 : Math.min(110, 24 + najdluzszy * 8);
  const GORA_H = Math.round((H - PB) * 0.34), PRZERWA = 30;
  const DOL_Y = GORA_H + PRZERWA;

  const X = i => PL + (opisy.length < 2 ? 0.5 : i / (opisy.length - 1)) * (W - PL - PR);
  const zakres = t => { const l = t.filter(v=>v != null);
                        return l.length ? skalaOs(Math.min(...l), Math.max(...l)) : null; };
  const sG = zakres(razem);
  const sD = zakres(serie.reduce((a,s)=>a.concat(s.wartosci), []));
  if(!sG || !sD) return '<div class="wykbrak">W tym zakresie nie ma jeszcze sprzedaży.</div>';
  const YG = v => 12 + (1 - (v - sG.dol) / (sG.gora - sG.dol)) * (GORA_H - 12);
  const YD = v => DOL_Y + (1 - (v - sD.dol) / (sD.gora - sD.dol)) * (H - PB - DOL_Y);

  let s = `<svg class="wykres" viewBox="0 0 ${W} ${H}" width="100%" height="${H}"
    role="img" aria-label="Sprzedaż: cały lokal u góry, automaty niżej">`;
  // Podpisów „cały lokal" i „automaty" nie ma celowo: linia sumy jest podpisana „Razem",
  // a każdy automat własną nazwą — nagłówek nad pasem powtarzałby to trzeci raz.
  const os = (Y, sk)=>{
    let t = '';
    for(let v = sk.dol; v <= sk.gora + 1e-6; v += sk.krok)
      t += `<line class="gl" x1="${PL}" y1="${Y(v).toFixed(1)}" x2="${W-PR}" y2="${Y(v).toFixed(1)}"/>
            <text x="${PL-7}" y="${(Y(v)+4).toFixed(1)}" text-anchor="end"
              font-size="${waski?10:11}">${Math.round(v).toLocaleString('pl-PL')}</text>`;
    return t;
  };
  s += os(YG, sG) + os(YD, sD);
  // Kreska rozdzielająca stoi tuż pod górnym pasem, nie w połowie przerwy — inaczej
  // wchodziła pod podpis „AUTOMATY".
  s += `<line class="przedzial" x1="${PL}" y1="${(DOL_Y - PRZERWA + 8).toFixed(1)}"
          x2="${W-PR}" y2="${(DOL_Y - PRZERWA + 8).toFixed(1)}"/>`;

  const co = Math.max(1, Math.ceil(opisy.length / (waski ? 4 : 9)));
  opisy.forEach((o,i)=>{ if(i % co === 0 || i === opisy.length - 1)
    s += `<text x="${X(i).toFixed(1)}" y="${H-8}" text-anchor="middle"
            font-size="${waski?10:11}">${esc(o)}</text>`; });

  /* Przerwa w danych przerywa linię: po pustym koszyku zaczynamy nowy odcinek, zamiast
     przeciągać kreskę przez miejsce, o którym nic nie wiemy. Pojedynczy punkt otoczony
     pustką dostaje kropkę — inaczej nie byłoby go widać wcale. */
  const linia = (w, Y, kolor, gr)=>{
    let d = '', kropki = '', pisz = false;
    w.forEach((v,i)=>{
      if(v == null){ pisz = false; return; }
      d += (pisz ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1) + ' ';
      if(!pisz && (i === w.length - 1 || w[i+1] == null))
        kropki += `<circle cx="${X(i).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="${gr}" fill="${kolor}"/>`;
      pisz = true;
    });
    return `<path d="${d.trim()}" fill="none" stroke="${kolor}" stroke-width="${gr}"
       stroke-linejoin="round" stroke-linecap="round"/>` + kropki;
  };
  s += linia(razem, YG, 'var(--ink)', 2.2);
  serie.forEach(ser=>{ s += linia(ser.wartosci, YD, ser.kolor, 1.8); });

  /* Legenda stoi przy swojej linii: podpis startuje na wysokości ostatniej wartości,
     a gdy dwa wypadłyby na sobie — rozsuwamy je i dorysowujemy cienką łączkę z powrotem
     do linii. Podpis pod wykresem zmuszałby do szukania koloru w drugim miejscu. */
  const ostatni = w => { for(let i = w.length - 1; i >= 0; i--) if(w[i] != null) return i;
                         return -1; };
  const H_MIN = waski ? 13 : 16;
  const rozsun = (lista, gorna, dolna)=>{
    lista.sort((a,b)=>a.y - b.y);
    for(let i = 1; i < lista.length; i++)
      if(lista[i].y - lista[i-1].y < H_MIN) lista[i].y = lista[i-1].y + H_MIN;
    const nad = lista.length ? lista[lista.length-1].y - dolna : 0;
    if(nad > 0) lista.forEach(e=>e.y = Math.max(gorna, e.y - nad));
    return lista;
  };
  const podpis = e =>
    `<path class="laczka" d="M${e.x.toFixed(1)} ${e.yl.toFixed(1)}
       L${W-PR+4} ${e.y.toFixed(1)}" fill="none" stroke="${e.kolor}"/>
     <text class="opis" x="${W-PR+10}" y="${(e.y+4).toFixed(1)}"
       font-size="${waski?10:12}" fill="${e.kolor}">${esc(e.tekst)}</text>`;
  const or = ostatni(razem);
  if(or >= 0) rozsun([{y: YG(razem[or]), yl: YG(razem[or]), x: X(or),
    kolor: 'var(--ink)', tekst: 'Razem'}], 12, GORA_H).forEach(e=>s += podpis(e));
  rozsun(serie.map(ser=>{ const i = ostatni(ser.wartosci);
      return {y: YD(ser.wartosci[i]), yl: YD(ser.wartosci[i]), x: X(i),
              kolor: ser.kolor, tekst: ser.kod};
    }), DOL_Y, H - PB).forEach(e=>s += podpis(e));

  return s + '</svg>';
}

/** Raport sprzedaży: ta sama liczba, oglądana z dwóch stron.

    **Komórka to liczba na JEDEN dzień, a nie suma za cały zakres.** Bierzemy każdy
    poniedziałek z zakresu osobno — ile sztuk tego zestawu zeszło tego dnia — i z tych
    liczb podajemy trzy naraz: **mediana / średnia / maksimum**.

    Trzy zamiast przełącznika, bo one odpowiadają na trzy różne pytania i patrzy się na nie
    razem: mediana mówi, ile schodzi w typowy dzień, średnia — ile wychodzi w rozliczeniu,
    maksimum — na ile trzeba być przygotowanym. Przełącznik kazał je oglądać po kolei
    i porównywać z pamięci.

    **Dzień, w którym nic nie zeszło, liczy się jako zero.** Bez tego mediana i średnia
    poszłyby w górę. Nie liczymy natomiast dni sprzed pierwszej sprzedaży automatu — wtedy
    jeszcze nie stał i nie ma o czym mówić.

    **Dwa układy tej samej tabeli.** „Wg automatów" bierze jeden automat i rozkłada go na
    dni tygodnia — pytanie brzmi „jak ten automat pracuje w tygodniu". „Wg dni tygodnia"
    bierze jeden dzień i rozkłada go na automaty — „co ładować na poniedziałek i gdzie".
    Te same liczby, przecięte w poprzek: raz wierszem, raz kolumną. */
const DNI_TYG_PELNE = ['poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek',
                       'sobota', 'niedziela'];

function statZ(probka, ktora){
  if(!probka.length) return null;
  if(ktora === 'maks') return Math.max.apply(null, probka);
  if(ktora === 'sr') return probka.reduce((a,b)=>a + b, 0) / probka.length;
  const s = probka.slice().sort((a,b)=>a - b), i = s.length >> 1;
  return s.length % 2 ? s[i] : (s[i-1] + s[i]) / 2;
}

/** Trzy liczby jednej komórki. `null`, gdy nie ma z czego liczyć — a to znaczy, że automatu
    wtedy nie było, a nie że sprzedał zero. */
function trojka(probka){
  if(!probka || !probka.length) return null;
  return {med: statZ(probka, 'med'), sr: statZ(probka, 'sr'), maks: statZ(probka, 'maks')};
}

/** Surowe liczby dla jednego automatu (`mid`) albo dla wszystkich razem (`null`):
    dla każdego zestawu siedem tablic — po jednej liczbie na każdy poniedziałek,
    wtorek… z zakresu. Statystykę liczy się dopiero z nich. */
function zbierzRaport(mid){
  const zakres = SPRZ_ZAKRES.raport;
  const koniec = todayISO(), start = przesunISO(koniec, -(zakres - 1));
  const dni = {}, zestawy = {};
  let bezAutomatu = 0, pierwszy = null;
  Object.keys(SPRZ_WYK || {}).forEach(k=>{
    const w = SPRZ_WYK[k];
    if(!w || !w.czas || !w.zestaw) return;
    const iso = isoSprzedazy(w.czas);
    if(iso < start || iso > koniec) return;
    if(!w.maszyna) bezAutomatu++;
    if(mid && w.maszyna !== mid) return;
    const d = dni[iso] || (dni[iso] = {});
    d[w.zestaw] = (d[w.zestaw] || 0) + 1;
    zestawy[w.zestaw] = true;
    if(!pierwszy || iso < pierwszy) pierwszy = iso;
  });

  const nrDnia = iso => (new Date(iso + 'T12:00:00').getDay() + 6) % 7;
  const lista = Object.keys(zestawy);
  const pusta = ()=>[[],[],[],[],[],[],[]];
  const proby = {};
  lista.forEach(z=>proby[z] = {dzien: pusta(), suma: 0});
  const razemDzien = pusta();
  let ileDni = 0;
  for(let iso = pierwszy; pierwszy && iso <= koniec; iso = przesunISO(iso, 1)){
    const n = nrDnia(iso), d = dni[iso] || {};
    let suma = 0;
    ileDni++;
    lista.forEach(z=>{
      const v = d[z] || 0;
      proby[z].dzien[n].push(v); proby[z].suma += v;
      suma += v;
    });
    razemDzien[n].push(suma);
  }
  return {start: start, koniec: koniec, dni: zakres, pierwszy: pierwszy, ileDni: ileDni,
          ileDnia: razemDzien.map(p=>p.length), proby: proby, lista: lista,
          razemDzien: razemDzien, bezAutomatu: bezAutomatu};
}

const nazwaZestawu = zid => { const s = CALC.set(zid);
  return s ? s.name : '⚠ brak zestawu (' + zid + ')'; };

/* Kolejność wierszy bierze się z łącznej sprzedaży — to jedyna liczba, która porządkuje
   tabelę tak samo bez względu na to, na którą z trzech miar się patrzy. */
const posortuj = w => w.sort((a,b)=>b.suma - a.suma);

/** Układ „wg automatów": jeden automat (albo wszystkie razem), kolumny to dni tygodnia. */
function daneRaportu(mid){
  const z = zbierzRaport(mid);
  const wiersze = posortuj(z.lista.map(zid=>({
    nazwa: nazwaZestawu(zid), suma: z.proby[zid].suma,
    d: z.proby[zid].dzien.map(trojka)})));
  return Object.assign({}, z, {
    naglowki: DNI_TYG.slice(),
    wiersze: wiersze});
}

/** Układ „wg dni tygodnia": jeden dzień, kolumny to automaty. */
function daneRaportuDnia(n){
  const masz = active(DB.machines);
  const wg = masz.map(m=>zbierzRaport(m.id));
  const all = zbierzRaport(null);
  // Zestaw, którego ten automat nie sprzedał ANI RAZU, ma w tej kolumnie zero, a nie kreskę —
  // bo automat stał i mógł go sprzedać. Kreska zostaje dla automatu, którego wtedy nie było.
  const kom = (x, zid) => !x.ileDnia[n] ? null
    : trojka(x.proby[zid] ? x.proby[zid].dzien[n] : new Array(x.ileDnia[n]).fill(0));
  const wiersze = posortuj(all.lista.map(zid=>({
    nazwa: nazwaZestawu(zid),
    suma: all.proby[zid].dzien[n].reduce((a,b)=>a + b, 0),
    d: wg.map(x=>kom(x, zid))})));
  return Object.assign({}, all, {
    naglowki: masz.map(m=>m.code || m.name),
    wiersze: wiersze});
}

/** Sztuki są całkowite, a mediana z parzystej liczby dni bywa połówką — przecinek stawiamy
    więc tam, gdzie coś się naprawdę dzieli. */
const liczbaRap = v => Number.isInteger(v) ? String(v) : num(v, 1);

/** Średnia ZAWSZE z jednym miejscem po przecinku, także „4,0" i „0,0".

    To ona jest kolumną, po której przebiega się wzrokiem, a kolumna liczb czyta się po
    długości: „4" obok „4,2" wygląda na krótsze, czyli mniejsze. Zero po przecinku niczego
    nie udaje — mówi, że średnia wyszła równa. */
const srRap = v => num(v, 1);

/** Komórka: mediana, średnia, maksimum — ale w kolorze tekstu tylko ŚRODKOWA.

    Oko trzyma się jednej kolumny liczb i po niej przebiega tabelę; mediana i maksimum stoją
    przy niej ciszej i doczytuje się je dopiero tam, gdzie coś się nie zgadza. Trzy jednakowo
    mocne liczby w komórce dają ścianę cyfr, przez którą nie widać żadnej.

    Bez spacji wokół ukośników: „1/1,2/2" trzyma się kupy jako jedna wartość, „1 / 1,2 / 2"
    rozpada się na trzy i sąsiednie kolumny zaczynają się zlewać. */
function komRap(t){
  if(t == null) return '<span class="mut">—</span>';
  const cicho = t.maks ? '' : ' mut';
  return `<span class="rapkom"><span class="mut l">${liczbaRap(t.med)}/</span>`
       + `<span class="s${cicho}">${srRap(t.sr)}</span>`
       + `<span class="mut p">/${liczbaRap(t.maks)}</span></span>`;
}

/** Jedna tabela raportu. Kolumny opisuje `naglowki`, więc ten sam kod rysuje oba układy. */
function tabelaRaportu(t, klucz){
  return `<div class="tw przyklej"><table class="raport" data-tbl="${klucz}"
      data-no-sort-now><thead><tr>
      <th>Zestaw</th>${t.naglowki.map(o=>`<th class="k">${esc(o)}</th>`).join('')}
    </tr></thead><tbody>
    ${t.wiersze.map(w=>`<tr><td>${esc(w.nazwa)}</td>
      ${w.d.map(v=>`<td class="k num">${komRap(v)}</td>`).join('')}</tr>`).join('')}
  </tbody></table></div>`;
}

const wgDni = () => SPRZ_RAPORT.wg === 'dzien';

/** Nazwa pliku PDF, w której widać, co jest w środku.

    W folderze Pobrane leży kilkanaście takich kartek i po samym „raporcie sprzedaży" nie da
    się ich odróżnić — a różnią się układem i okresem, czyli wszystkim, co decyduje o liczbach.
    Data na końcu jest końcem zakresu (raport zawsze liczy wstecz od dzisiaj) i przy okazji
    sprawia, że wczorajszy plik nie robi się „(1)".

    Bez ogonków i bez spacji: nazwa pliku wędruje przez maile, pendrive'y i Windows. */
const OKRES_PLIK = {7: '7dni', 30: 'miesiac', 365: 'rok'};
function nazwaPlikuRaportu(){
  return ['raport-sprzedazy',
          wgDni() ? 'wg-dni-tygodnia' : 'wg-automatow',
          OKRES_PLIK[SPRZ_ZAKRES.raport] || (SPRZ_ZAKRES.raport + 'dni'),
          todayISO()].join('-');
}

/** Pasek nad tabelą: układ i wybór z listy. */
function paskRaportu(){
  const opcje = wgDni()
    ? DNI_TYG_PELNE.map((d,n)=>`<option value="${n}" ${SPRZ_RAPORT.dzien === n ? 'selected' : ''}
        >${esc(d)}</option>`).join('')
    : `<option value="">Wszystkie automaty razem</option>` + active(DB.machines).map(m=>
        `<option value="${esc(m.id)}" ${SPRZ_RAPORT.automat === m.id ? 'selected' : ''}
        >${esc(m.code ? m.code + ' · ' + m.name : m.name)}</option>`).join('');
  return `<div class="row" style="gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px">
      <div class="pill-group" data-wg>
        <button type="button" data-w="aut" class="${wgDni() ? '' : 'on'}">wg automatów</button>
        <button type="button" data-w="dzien" class="${wgDni() ? 'on' : ''}">wg dni tygodnia</button>
      </div>
      <select id="rapAut" style="width:auto;min-width:210px">${opcje}</select>
    </div>`;
}

/** Raport na ekranie: jedna tabela w wybranym układzie. */
function raportTygodnia(){
  const dzien = wgDni();
  const mid = dzien ? null : (SPRZ_RAPORT.automat || null);
  const r = dzien ? daneRaportuDnia(SPRZ_RAPORT.dzien) : daneRaportu(mid);
  const aut = mid ? active(DB.machines).find(x=>x.id === mid) : null;
  const co = dzien ? 'w ' + (SPRZ_RAPORT.dzien === 2 ? 'jedną środę'
      : SPRZ_RAPORT.dzien === 5 ? 'jedną sobotę'
      : SPRZ_RAPORT.dzien === 6 ? 'jedną niedzielę'
      : 'jeden ' + DNI_TYG_PELNE[SPRZ_RAPORT.dzien])
    : 'w jeden dzień — ' + (aut ? (aut.code || aut.name) : 'wszystkie automaty');
  if(!r.wiersze.length)
    return paskRaportu() + '<div class="wykbrak">W tym zakresie nie ma tu jeszcze sprzedaży.</div>';
  return paskRaportu() + tabelaRaportu(r, 'sprzRaport') +
    `<div class="hint" style="margin-top:8px">W każdej komórce mediana / <b>średnia</b> /
      maksimum sprzedanych sztuk ${esc(co)}, z ostatnich ${r.dni} dni
      (od ${esc(dataKrotko(r.pierwszy))}). Dzień bez sprzedaży liczy się jako zero;
      dni sprzed pierwszej sprzedaży nie liczymy.</div>` +
    (r.bezAutomatu && !mid ? `<div class="hint"><b>${r.bezAutomatu}</b> sprzedaży w tym
      zakresie nie ma rozpoznanego automatu — nie wchodzą do żadnej kolumny.</div>` : '');
}

/** Ten sam raport na kartkę — wszystkie przekroje naraz, sekcja po sekcji.

    Na ekranie wybiera się jeden automat albo jeden dzień, bo ekran jest do oglądania;
    kartka idzie do kuchni jedna i ma odpowiadać na pytanie o każdy z nich, więc drukujemy
    wszystkie po kolei. Układ jest ten, który stoi na ekranie.

    Tabela, nie kafelki: porównuje się tu liczby w dwóch kierunkach naraz — wzdłuż wiersza
    i wzdłuż kolumny — a do tego trzeba siatki. Stopnia pisma nie dobieramy pomiarem jak
    w kafelkach: przy dłuższej liście zestawów tabela schodzi na drugą stronę z powtórzoną
    główką. Ściskanie pisma kupiłoby jedną stronę kosztem czytelności wszystkich. */
function pdfRaportTygodnia(){
  const dzien = wgDni();
  const zbiorczy = dzien ? daneRaportuDnia(SPRZ_RAPORT.dzien) : daneRaportu(null);
  if(!zbiorczy.wiersze.length){
    alert('W tym zakresie nie ma jeszcze sprzedaży — nie ma czego drukować.');
    return;
  }
  const data = iso => iso.slice(8) + '.' + iso.slice(5,7) + '.' + iso.slice(0,4);
  const tytul = 'Raport sprzedaży · zestawy '
    + (dzien ? 'w automatach, dzień po dniu' : 'w dniach tygodnia');
  const styl = `
    .sub{margin:-.5em 0 1em}
    /* Sekcja trzyma się kupy: nagłówek nigdy nie zostaje sam na dole strony, a krótka
       tabela nie pęka w pół. Dłuższa niż strona pęknie — i dobrze. */
    .sek{break-inside:avoid;page-break-inside:avoid;margin:0 0 1.4em}
    .sek h2{font-size:1.02em;margin:0 0 .35em;padding-bottom:.2em;
      border-bottom:1px solid #1D1D1B;text-transform:uppercase;letter-spacing:.06em}
    .sek h2 span{text-transform:none;letter-spacing:0;font-weight:400;color:#8A8781;
      font-size:.88em}
    .pusto,.uwaga{color:#8A8781;margin:.2em 0 0}
    table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
    thead{display:table-header-group}        /* główka wraca na każdej stronie */
    th,td{padding:.32em .4em;border-bottom:1px solid #E3E0DA;text-align:center;
      white-space:nowrap}
    th:first-child,td:first-child{text-align:left;white-space:normal}
    /* Średnia dokładnie w osi kolumny — tak samo jak na ekranie. */
    .kom{display:grid;grid-template-columns:1fr auto 1fr;align-items:baseline}
    .kom .l{text-align:right}
    .kom .p{text-align:left}
    thead th{border-bottom:1.5px solid #1D1D1B;font-weight:600;font-size:.92em;
      text-transform:uppercase;letter-spacing:.06em;color:#8A8781}
    thead th:first-child{color:#1D1D1B}
    tbody tr:last-child td{border-bottom:0}
    /* Średnia w kolorze tekstu, mediana i maksimum ciszej — tak samo jak na ekranie. */
    .cicho{color:#8A8781}
    tr{break-inside:avoid;page-break-inside:avoid}`;

  const sekcje = dzien
    ? DNI_TYG_PELNE.map((d,n)=>Object.assign({kod: d, nazwa: ''}, daneRaportuDnia(n)))
    : active(DB.machines).map(m=>Object.assign({kod: m.code || m.name, nazwa: m.name},
        daneRaportu(m.id))).concat([Object.assign(
        {kod: 'Wszystkie automaty razem', nazwa: ''}, daneRaportu(null))]);
  const licz = t => t == null ? '<span class="cicho">—</span>'
    : `<span class="kom"><span class="cicho l">${liczbaRap(t.med)}/</span>`
      + `<span class="${t.maks ? '' : 'cicho'}">${srRap(t.sr)}</span>`
      + `<span class="cicho p">/${liczbaRap(t.maks)}</span></span>`;
  const tab = s=>`<section class="sek">
      <h2>${esc(s.kod)}${s.nazwa ? ` <span>${esc(s.nazwa)}</span>` : ''}</h2>
      ${!s.wiersze.length ? '<p class="pusto">W tym zakresie nic tu nie zeszło.</p>'
      : `<table><thead><tr><th>Zestaw</th>
      ${s.naglowki.map(o=>`<th>${esc(o)}</th>`).join('')}</tr></thead><tbody>
    ${s.wiersze.map(w=>`<tr><td>${esc(w.nazwa)}</td>
      ${w.d.map(v=>`<td>${licz(v)}</td>`).join('')}</tr>`).join('')}
  </tbody></table>`}</section>`;
  const tresc = `<div class="sub">W każdej komórce mediana / <b>średnia</b> / maksimum
      sprzedanych sztuk w jeden dzień,
      ${dzien ? 'dzień tygodnia po dniu, w kolumnach automaty'
              : 'automat po automacie, w kolumnach dni tygodnia'} ·
      z ostatnich ${zbiorczy.dni} dni
      (${esc(data(zbiorczy.start))} – ${esc(data(zbiorczy.koniec))}) · dzień bez sprzedaży
      liczy się jako zero, dni sprzed pierwszej sprzedaży automatu nie liczymy</div>
    ${sekcje.map(tab).join('')}
    ${zbiorczy.bezAutomatu ? `<p class="uwaga">${zbiorczy.bezAutomatu} sprzedaży nie ma
      rozpoznanego automatu — nie wchodzą do żadnej kolumny.</p>` : ''}`;
  /* Siedem kolumn po trzy liczby mieści się na A4 co do milimetra — ale dopiero bez spacji
     przy ukośnikach. Ze spacjami trzeba było schodzić o stopień pisma niżej. */
  zrobPdf(dokumentDruku(tytul, styl, tresc, 13), nazwaPlikuRaportu(), stopkaDruku(tytul));
}

/** Wstawia oba wykresy w ich karty. Wołane po narysowaniu ekranu i przy zmianie
    szerokości okna — bo szerokość jest tu daną wejściową, a nie ozdobą. */
function rysujWykresySprzedazy(){
  const dzienne = dzienneSprzedazy(SPRZ_WYK || {});
  const p = pierwszeDni(dzienne);
  const zrodlo = {
    mies:  ()=>oknaKroczace(dzienne, SPRZ_ZAKRES.mies, 30, false),
    dzien: ()=>oknaKroczace(dzienne, SPRZ_ZAKRES.dzien, 7, true),
    tydz:  ()=>srednieDniTygodnia(dzienne, SPRZ_ZAKRES.tydz, p.pierwszy, p.lokal)
  };
  [['mies', 'wykMies'], ['dzien', 'wykDzien'], ['tydz', 'wykTydz']].forEach(([ktory, id])=>{
    const el = document.getElementById(id);
    if(!el) return;
    const w = zrodlo[ktory]();
    const serie = active(DB.machines).map((m,i)=>({
        kod: m.code || m.name, kolor: kolorAutomatu(m, i), wartosci: w.dla(m.id)}))
      .filter(s=>s.wartosci.some(v=>v != null));
    el.innerHTML = serie.length ? wykresPasy(el, w.opisy, w.razem, serie)
      : '<div class="wykbrak">W tym zakresie nie ma jeszcze pełnego okna.</div>';
  });
}

/* Kolory serii na wykresie: same ciemne odcienie z palety osób, bo cienka linia w jasnym
   kolorze ginie na białym tle. Palety nie liczymy drugi raz — tamta jest już dobrana tak,
   żeby sąsiednie kolory dało się rozróżnić. Tu nie ma plakietek osób, więc nie ma czego
   z czym pomylić.

   Kolejność NIE jest kolejnością z koła barw. Sześć kolejnych odcieni z koła to sześć
   sąsiadów — brąz, musztarda, mech, butelka — i na cienkich liniach zlewają się w jedno.
   Bierzemy więc co trzeci kawałek koła: brąz, butelkowy, granatowy, śliwkowy, mchowy,
   petrolowy. Przy sześciu automatach każde dwie sąsiednie linie dzieli około stu stopni.

   Kolor bierze się z POZYCJI automatu na liście, a legenda stoi przy wykresie — gdy
   kolejność się zmieni, legenda zmieni się razem z nią i nic nie zacznie po cichu kłamać. */
const KOLORY_SERII = ['#924300', '#04673F', '#085F88', '#8F328E', '#4A6102', '#0C6465',
                     '#514DAF', '#705600'];

/* ---------------------------------------------------------------------------
   ZAKUPY: faktury zakupowe z KSeF

   Automatyzacja w n8n pobiera faktury i wysyła gotowe wiersze na `/api/zakupy`.
   Aplikacja robi z nimi trzy rzeczy i tylko trzy:

   1. POZNAJE DOSTAWCÓW po NIP-ie z numeru KSeF, a nie po nazwie — nazwa bywa raz
      „MAKRO", raz „MAKRO Cash and Carry Polska S.A.". Dostawców spoza towaru (serwis
      auta, telefon) oznaczamy jako pomijanych i wtedy serwer nie zapisuje ich faktur.
   2. DOPASOWUJE nazwę fakturową do składnika — raz, na zawsze, razem z przelicznikiem
      opakowania: „Glony Nori 280g,100ark." to 100 arkuszy, a nie jedna sztuka.
   3. PROPONUJE CENY ze średniej ważonej ilością. Zatwierdza człowiek, nigdy aplikacja.

   Pomijanie ma trzy poziomy, bo „zakup incydentalny" znaczy trzy różne rzeczy:
   nazwa, która nigdy nie jest składnikiem (frytura, rękawice); nazwa u DANEGO dostawcy
   (ryż z MAKRO, gdy stałym dostawcą są Kuchnie Świata); i pojedyncza dostawa (pomyłka,
   zwrot, cena z kosmosu). Bez środkowego poziomu pomijanie nazwy wywaliłoby ryż
   w całości, a pomijanie dostaw kazałoby klikać to samo co miesiąc.
   ------------------------------------------------------------------------- */
let ZAK = null, ZAK_KLUCZ = null, ZAK_BLAD = null, ZAK_ZAKRES = 90;
/* Zaznaczeni dostawcy (NIP-y). Po imporcie roku lista potrafi mieć kilkadziesiąt pozycji,
   z czego połowa to prąd, telefon i serwis auta — odklikiwanie ich pojedynczo, każdego
   z osobnym pytaniem o sprzątanie, jest robotą na kwadrans. Zaznaczenie żyje tylko
   w pamięci ekranu: to wybór na teraz, a nie ustawienie lokalu. */
let ZAK_ZAZN = [];

/* Zaznaczone pozycje fakturowe (klucze nazw). Po imporcie roku „Do dopasowania" potrafi
   mieć kilkadziesiąt nazw, z czego połowa to rękawice, worki i folia — a każda z nich
   pyta o to samo. Zaznaczenie żyje w pamięci ekranu, tak samo jak przy dostawcach. */
let ZAK_ZAZN_POZ = [];

/** Ceny liczymy z okna, które właściciel ustawia w Ustawieniach. Czternaście dni
    to domyślna wartość: dość, żeby złapać dwie–trzy dostawy, za mało, żeby zeszłomiesięczna
    promocja trzymała cenę w dół. */
function zakOkno(){ return Math.max(1, DB.settings.oknoZakupow || 14); }
function zakZakres(){
  const doo = todayISO();
  return {od: przesunISO(doo, -(ZAK_ZAKRES - 1)), doo: doo};
}

async function wczytajZakupy(){
  const z = zakZakres(), klucz = z.od + '|' + z.doo;
  if(ZAK_KLUCZ === klucz) return;
  if(!(SRV.on && SRV.user && ZARZAD.indexOf(SRV.user.role) >= 0)){
    ZAK = {}; ZAK_KLUCZ = klucz; return;
  }
  try{
    const r = await fetch('/api/zakupy?od=' + z.od.slice(0,7) + '&do=' + z.doo.slice(0,7));
    ZAK = r.ok ? ((await r.json()).zakupy || {}) : {};
    ZAK_BLAD = r.ok ? null : 'Nie udało się wczytać zakupów.';
  }catch(e){ ZAK = {}; ZAK_BLAD = 'Brak połączenia z serwerem.'; }
  ZAK_KLUCZ = klucz;
}

/** Wpisy z wybranego zakresu, każdy ze swoim kluczem — potrzebnym do pomijania
    pojedynczej dostawy. */
function zakLista(){
  const z = zakZakres();
  return Object.keys(ZAK || {}).map(k=>Object.assign({id: k}, ZAK[k]))
    .filter(w=>w && w.data >= z.od && w.data <= z.doo)
    .sort((a,b)=>b.data.localeCompare(a.data));
}

/** Stan pojedynczej pozycji faktury. Kolejność ma znaczenie: pominięcie wygrywa
    z dopasowaniem, bo pomija się właśnie to, co skądinąd dałoby się dopasować. */
function zakStanPoz(w){
  const Z = DB.zakupy;
  if(Z.pomijanePoz[w.id] || Z.pomijane[w.klucz] || Z.pomijaneU[w.klucz + '|' + w.nip])
    return 'pominieta';
  return Z.dopasowania[w.klucz] ? 'dopasowana' : 'nowa';
}

/** Pozycje zgrupowane po nazwie fakturowej — bo dopasowuje się nazwę, nie dostawę. */
function zakGrupy(){
  const wg = {};
  zakLista().forEach(w=>{
    const g = wg[w.klucz] || (wg[w.klucz] = {klucz: w.klucz, opis: w.opis, jm: w.jm,
      wiersze: [], nipy: {}, pominietych: 0});
    g.wiersze.push(w);
    g.nipy[w.nip] = w.dostawca || g.nipy[w.nip] || '';
    if(zakStanPoz(w) === 'pominieta') g.pominietych++;
  });
  return Object.keys(wg).map(k=>{
    const g = wg[k], Z = DB.zakupy;
    g.dop = Z.dopasowania[k] || null;
    g.ostatnia = g.wiersze[0];
    g.stan = Z.pomijane[k] || g.pominietych === g.wiersze.length ? 'pominieta'
           : (g.dop ? 'dopasowana' : 'nowa');
    return g;
  }).sort((a,b)=>b.ostatnia.data.localeCompare(a.ostatnia.data));
}

/** Licznik przy pozycji w menu: ile nazw czeka na decyzję. */
function zakDoZrobienia(){
  if(!ZAK) return 0;
  return zakGrupy().filter(g=>g.stan === 'nowa').length;
}

/** Dostawcy: ci, których faktury mamy, plus ci, których świadomie pomijamy. */
function zakDostawcy(){
  const wg = {};
  zakLista().forEach(w=>{
    const d = wg[w.nip] || (wg[w.nip] = {nip: w.nip, nazwa: '', faktury: {}, pozycji: 0, ostatnia: ''});
    if(w.dostawca) d.nazwa = w.dostawca;
    d.faktury[w.id.split('|')[0]] = 1;
    d.pozycji++;
    if(w.data > d.ostatnia) d.ostatnia = w.data;
  });
  (DB.zakupy.pomijaniNip || []).forEach(nip=>{
    if(!wg[nip]) wg[nip] = {nip: nip, nazwa: (DB.zakupy.dostawcy[nip] || {}).nazwa || '',
                            faktury: {}, pozycji: 0, ostatnia: ''};
  });
  return Object.keys(wg).map(nip=>{
    const d = wg[nip];
    d.ileFaktur = Object.keys(d.faktury).length;
    d.pomijany = (DB.zakupy.pomijaniNip || []).indexOf(nip) >= 0;
    if(!d.nazwa) d.nazwa = (DB.zakupy.dostawcy[nip] || {}).nazwa || '';
    return d;
  }).sort((a,b)=>b.pozycji - a.pozycji);
}

/** Propozycje cen: średnia ważona ILOŚCIĄ z okna.

    Ważona, a nie zwykła — dostawa 20 kg musi liczyć się dziesięć razy mocniej niż 2 kg,
    bo tyle właśnie kosztowała. Liczymy w jednostkach SKŁADNIKA, nie faktury: ten sam
    majonez przychodzi raz w słoiku 450 g, raz w wiadrze 2256 g i tylko po przeliczeniu
    na gramy da się je dodać do siebie. */
function zakPropozycje(){
  const okno = zakOkno(), od = przesunISO(todayISO(), -(okno - 1));
  const wg = {};
  zakLista().forEach(w=>{
    if(w.data < od || zakStanPoz(w) !== 'dopasowana') return;
    const d = DB.zakupy.dopasowania[w.klucz];
    const ile = (w.ilosc || 0) * (d.przelicz || 1);
    const wart = w.wartosc != null ? w.wartosc : (w.cena || 0) * (w.ilosc || 0);
    if(!ile || !wart) return;
    const c = wg[d.ing] || (wg[d.ing] = {wartosc: 0, ilosc: 0, dostaw: 0, nazwy: {}});
    c.wartosc += wart; c.ilosc += ile; c.dostaw++; c.nazwy[w.opis] = 1;
  });
  return Object.keys(wg).map(id=>{
    const g = CALC.ing(id), c = wg[id];
    if(!g || !c.ilosc || !g.packQty) return null;
    const jedn = c.wartosc / c.ilosc;
    const cena = jedn >= 1 ? Math.round(jedn * g.packQty * 100) / 100
                           : Math.round(jedn * g.packQty * 10000) / 10000;
    const teraz = g.packPrice;
    // Różnica poniżej pół procenta to szum zaokrągleń, a nie zmiana ceny — takiej
    // nie warto podsuwać do zatwierdzenia, bo tonie w niej ta prawdziwa.
    const roznica = teraz ? (cena - teraz) / teraz : null;
    return {ing: g, dostaw: c.dostaw, ilosc: c.ilosc, jedn: jedn, cena: cena,
            teraz: teraz, roznica: roznica, nazwy: Object.keys(c.nazwy),
            zmiana: teraz == null || Math.abs(roznica) >= 0.005};
  }).filter(Boolean).sort((a,b)=>Math.abs(b.roznica || 9) - Math.abs(a.roznica || 9));
}

function zakZatwierdz(p, automat){
  const g = DB.ingredients.find(x=>x.id === p.ing.id);
  if(!g) return;
  const stara = g.packPrice;
  g.packPrice = p.cena;
  // Ten sam wpis, co przy ręcznej zmianie ceny w Składnikach — historia cen nie może
  // mieć dwóch rodzajów wpisów, bo wtedy przestaje być jedną historią. Automat
  // dopisuje do notatki, że nikt tego nie klikał: bez tego za pół roku nie da się
  // odróżnić ceny zatwierdzonej świadomie od wpisanej przez próg.
  DB.history.push({id: uid('h'), ingId: g.id, date: todayISO(), from: stara, to: g.packPrice,
    qty: g.packQty,
    note: 'Zakupy KSeF' + (automat ? ' (automat do ' + num(zakAuto(), zakAuto() % 1 ? 1 : 0)
        + '%)' : '') + ': ' + p.nazwy.join(', ') + ' — ' + p.dostaw + ' '
        + mnoga(p.dostaw, 'dostawa', 'dostawy', 'dostaw') + ' z ' + zakOkno() + ' dni'});
  if(!automat){ save(); render(); }
}

/** Próg, do którego cena wpisuje się sama (w procentach). 0 = nic automatycznie. */
function zakAuto(){
  const v = DB.settings.autoCenaProc;
  return Math.max(0, Math.min(100, v == null ? 3 : v));
}

/** Drobne zmiany wpisujemy same; te większe czekają na człowieka.

    Trzy procent to nie jest „mało" w oderwaniu — to jest tyle, ile cena towaru potrafi
    zafalować między dostawami bez żadnego powodu po stronie dostawcy. Klikanie
    „Zatwierdź" przy każdym takim drgnieniu kończy się tym, że przestaje się czytać
    także te prawdziwe. Próg siedzi w Ustawieniach, a zero go wyłącza.

    Nowej ceny (gdy w bazie nie ma żadnej) automat NIE wpisuje: nie ma od czego liczyć
    procentu, więc nie ma czego porównać z progiem. Taka pozycja czeka na człowieka.

    Zwraca liczbę wpisanych cen. Woła się PO renderze — zapis bazy w trakcie rysowania
    wszedłby renderowi w drogę. */
function zakAutoZatwierdz(){
  const prog = zakAuto();
  if(!prog) return 0;
  const gotowe = zakPropozycje().filter(p=>p.zmiana && p.teraz != null && p.roznica != null
    && Math.abs(p.roznica) <= prog / 100);
  gotowe.forEach(p=>zakZatwierdz(p, true));
  if(gotowe.length) save();
  return gotowe.length;
}

/** Podpowiedzi składnika dla nazwy fakturowej.

    Nazwy z faktur są skrócone do granic czytelności: „P MC ŁOS.ATL.FIL.TR.E 1-1,5,0K"
    to łosoś, „MLEKOV.SER.NIE TYLKO SUSHI 1KG" to serek. Człowiek rozpoznaje je po
    fragmencie, nie po całym słowie — więc dopasowujemy PRZEDROSTKIEM: „los" trafia
    w „Łosoś", „ser" w „Serek". Trzy znaki to próg, poniżej którego trafień robi się
    tyle, że przestają być podpowiedzią. Trafienie całym słowem liczy się mocniej,
    bo „CUKIER" w „DIAM.CUKIER 25KG" to co innego niż wspólne trzy litery.

    Podpowiedź trzeba KLIKNĄĆ — nie podstawiamy jej do pola. Źle podstawiony składnik
    wpisałby cenę cudzego towaru, a pole wyglądałoby na wypełnione świadomie i nikt
    by tego nie sprawdził. */
function zakPodpowiedzi(opis){
  const tekst = bezOgonkow(opis);
  const czlony = tekst.replace(/[^a-z0-9]+/g, ' ').split(' ').filter(x=>x.length >= 3);
  // Wersja bez żadnych separatorów. Faktura pisze „Tacka HP-11", baza „Tacka HP11" —
  // myślnik rozbija człon na „hp" i „11", a oba są za krótkie, żeby cokolwiek znaczyć.
  const sklejone = tekst.replace(/[^a-z0-9]+/g, '');
  if(!czlony.length && !sklejone) return [];
  const wynik = [];
  active(DB.ingredients).forEach(ing=>{
    const slowa = bezOgonkow(ing.name).replace(/[^a-z0-9]+/g, ' ').split(' ')
      .filter(x=>x.length >= 3);
    if(!slowa.length) return;
    let punkty = 0, trafienie = '';
    slowa.forEach(s=>{
      let naj = 0, czym = '';
      // Całe słowo składnika stojące gdzieś w nazwie fakturowej to najmocniejsze,
      // co może się zdarzyć — „hp11" w „TackaHP1126x19cm".
      if(sklejone.indexOf(s) >= 0){ naj = s.length + 3; czym = s; }
      czlony.forEach(c=>{
        let i = 0;
        while(i < s.length && i < c.length && s[i] === c[i]) i++;
        // Przedrostek musi pokrywać WIĘCEJ niż połowę słowa składnika. Bez tego
        // „SUSHI" trafiało w „suszony", a „CUKIER" w „Cuknia tempura": trzy wspólne
        // litery na sześciu czy siedmiu to nie podobieństwo, tylko przypadek.
        // Ostro powyżej połowy, a nie „co najmniej": „cuk" z „cuknia" to równo połowa
        // i właśnie ten przypadek podsuwał cukinię do cukru.
        if(i < 3 || i <= s.length / 2) return;
        const pkt = (i === s.length && i === c.length) ? i + 3 : i;
        if(pkt > naj){ naj = pkt; czym = c.slice(0, i); }
      });
      if(naj){ punkty += naj; if(czym.length > trafienie.length) trafienie = czym; }
    });
    if(punkty >= 3) wynik.push({ing: ing, punkty: punkty, trafienie: trafienie});
  });
  return wynik.sort((a, b)=>b.punkty - a.punkty
      || a.ing.name.localeCompare(b.ing.name, 'pl')).slice(0, 3);
}

/* ---------- okna dialogowe ---------- */

/** Wszystkie dostawy jednej pozycji fakturowej — pełny zapis wiersza.

    Przy dopasowaniu trzeba widzieć to, co stoi na papierze: cenę netto i brutto, opust
    i obie wartości. Sama cena jednostkowa nie wystarcza, żeby rozpoznać pozycję i ustawić
    przelicznik — „46,50 za op" znaczy co innego przy paczce 100 arkuszy, a co innego
    przy dziesięciu.

    Brutto liczymy tylko wtedy, gdy faktura go nie przyniosła (starsze wpisy sprzed
    pełnego zapisu) — i wtedy stoi przygaszone, z podpowiedzią skąd się wzięło. */
function tabelaDostaw(g, zPominieciem){
  if(!g || !g.wiersze.length) return '<div class="empty">Brak dostaw w tym zakresie.</div>';
  const maOpust = g.wiersze.some(w=>w.opust != null && w.opust !== 0);
  /* Kolumna dostawcy tylko wtedy, gdy dostawca się zmienia. Przy jednym dostawcy to
     siedem razy ta sama nazwa, a wtedy „Pomiń" nie mieści się w oknie i wychodzi poza
     kadr. Jedna nazwa idzie do nagłówka nad tabelą. */
  const nazwy = {};
  g.wiersze.forEach(w=>{ nazwy[w.dostawca || w.nip] = 1; });
  const dostawcy = Object.keys(nazwy);
  const maDost = dostawcy.length > 1;
  const kwota = v => v == null ? '<span class="mut">—</span>' : zl(v);
  const brutto = (w, netto, pole)=>{
    if(w[pole] != null) return zl(w[pole]);
    if(netto == null || w.vat == null) return '<span class="mut">—</span>';
    return `<span class="mut" title="Policzone z netto i stawki VAT — faktura nie przyniosła`
         + ` tej kwoty">${zl(netto * (1 + w.vat / 100))}</span>`;
  };
  return `${maDost ? '' : `<div class="hint" style="margin-bottom:6px">Dostawca:
      <b>${esc(dostawcy[0] || '—')}</b></div>`}
    <div class="tw" style="max-height:230px;overflow:auto"><table class="tabdost"><thead><tr>
      <th>Data</th>${maDost ? '<th>Dostawca</th>' : ''}<th class="r">Ilość</th>
      <th class="r">Cena netto</th><th class="r">Cena brutto</th>
      ${maOpust ? '<th class="r">Opust</th>' : ''}
      <th class="r">Wartość netto</th><th class="r">Wartość brutto</th>
      <th class="r">VAT</th>${zPominieciem ? '<th></th>' : ''}</tr></thead><tbody>
    ${g.wiersze.map(w=>{
      const pom = zakStanPoz(w) === 'pominieta';
      return `<tr class="${pom ? 'mut' : ''}"><td>${esc(dataKrotko(w.data))}</td>
        ${maDost ? `<td class="d" title="${esc(w.dostawca || w.nip)}">${
          esc(w.dostawca || w.nip)}</td>` : ''}
        <td class="r num">${num(w.ilosc || 0, (w.ilosc || 0) % 1 ? 2 : 0)} ${esc(w.jm || '')}</td>
        <td class="r num">${kwota(w.cena)}</td>
        <td class="r num">${brutto(w, w.cena, 'cenaB')}</td>
        ${maOpust ? `<td class="r num">${w.opust ? zl(w.opust) : '<span class="mut">—</span>'}</td>` : ''}
        <td class="r num">${kwota(w.wartosc)}</td>
        <td class="r num">${brutto(w, w.wartosc, 'wartoscB')}</td>
        <td class="r num">${w.vat == null ? '<span class="mut">—</span>'
          : num(w.vat, w.vat % 1 ? 1 : 0) + '%'}</td>
        ${zPominieciem ? `<td class="r"><button class="btn sm" data-zakpoz="${esc(w.id)}">${
          DB.zakupy.pomijanePoz[w.id] ? 'Przywróć' : 'Pomiń'}</button></td>` : ''}</tr>`;
    }).join('')}
  </tbody></table></div>`;
}

function dlgZakDopasuj(klucz){
  const g = zakGrupy().find(x=>x.klucz === klucz);
  if(!g) return;
  const dop = g.dop || {};
  const podp = dop.ing ? [] : zakPodpowiedzi(g.opis);
  /* Cena, którą podstawiamy nowemu składnikowi: średnia ważona z okna, jeśli w oknie
     są dostawy, a jak nie — ostatnia. Pierwszy import wciąga rok wstecz i wtedy okno
     bywa puste, a zakładanie składnika bez ceny nie ma sensu. */
  const zOkna = ()=>{
    const od = przesunISO(todayISO(), -(zakOkno() - 1));
    let w = 0, il = 0;
    g.wiersze.forEach(x=>{
      if(x.data < od || zakStanPoz(x) === 'pominieta' || !x.ilosc) return;
      w += x.wartosc != null ? x.wartosc : (x.cena || 0) * x.ilosc; il += x.ilosc;
    });
    return il ? {cena: w / il, dostaw: true} : {cena: g.ostatnia.cena, dostaw: false};
  };
  const cats = [...new Set(DB.ingredients.map(x=>x.cat).filter(Boolean))].sort();
  let recznaIlosc = false;

  const tryb = ()=>(document.querySelector('[name="zdTryb"]:checked') || {}).value || 'jest';
  const przelicznik = ()=>parseFloat(val('zdPrzel')) || 0;

  const podglad = ()=>{
    const e = document.getElementById('zdPodglad');
    if(!e) return;
    const nowy = tryb() === 'nowy';
    const blokJest = document.getElementById('zdBlokJest');
    const blokNowy = document.getElementById('zdBlokNowy');
    if(blokJest) blokJest.style.display = nowy ? 'none' : '';
    if(blokNowy) blokNowy.style.display = nowy ? '' : 'none';
    const przel = przelicznik();
    // Opakowanie nowego składnika to domyślnie JEDNA jednostka z faktury: kilogram
    // łososia to 1000 g za tyle, ile kosztuje kilogram. Dopóki nikt nie ruszy pola,
    // idzie za przelicznikiem — bo to ta sama liczba i przepisywanie jej ręcznie
    // byłoby proszeniem się o literówkę.
    if(nowy && !recznaIlosc && przel){
      const q = document.getElementById('zdQty');
      if(q) q.value = przel;
    }
    if(nowy){
      /* Ta sama nazwa dwa razy to nie błąd — bywa „Sezam" i „Sezam Biały" — ale drugi
         „Tacka HP07" z inną ceną to koniec z jedną prawdą o koszcie. Ostrzegamy przed
         zapisaniem, nie po; nie blokujemy, tak samo jak przy zajętej literze osoby. */
      const info = document.getElementById('zdNazwaInfo');
      const nazwa = val('zdNazwa').trim().toLowerCase();
      const juz = nazwa && active(DB.ingredients).find(x=>(x.name || '').trim().toLowerCase() === nazwa);
      if(info){
        info.textContent = juz ? 'Składnik „' + juz.name + '" już jest — może chodzi o dopasowanie do niego?' : '';
        info.classList.toggle('uwaga-txt', !!juz);
      }
      const z = zOkna(), q = parseFloat(val('zdQty')) || przel;
      const jedn = przel ? z.cena / przel : null;
      const c = document.getElementById('zdCena');
      // Ta sama zasada, co przy propozycjach cen: złotówki mają dwa miejsca, a grosze
      // za gram cztery — inaczej w polu ceny opakowania stoi 519,9302 zł.
      if(c && !c.dataset.reczne && jedn != null && q){
        const w = jedn * q;
        c.value = w >= 1 ? Math.round(w * 100) / 100 : Math.round(w * 10000) / 10000;
      }
      e.innerHTML = jedn == null ? '<span class="mut">Podaj przelicznik.</span>'
        : 'Cena z faktur: <b>' + zl(z.cena) + '/' + esc(g.jm || 'jm') + '</b>'
          + (z.dostaw ? ' (średnia ważona z ' + zakOkno() + ' dni)' : ' (ostatnia dostawa)')
          + ' → <b>' + num(jedn, jedn < 1 ? 5 : 2) + ' ' + esc(DB.settings.currency) + '/'
          + esc((document.getElementById('zdUnit_q')||{}).value.trim() || val('zdUnit') || 'jm') + '</b>';
      return;
    }
    const id = val('zdIng');
    const ing = id ? CALC.ing(id) : null;
    if(!ing || !przel){ e.innerHTML = '<span class="mut">Wybierz składnik i podaj przelicznik.</span>'; return; }
    const cena = g.ostatnia.cena, jedn = cena / przel;
    e.innerHTML = '1 ' + esc(g.jm || 'jm') + ' = <b>' + num(przel, przel % 1 ? 2 : 0) + ' '
      + esc(ing.unit) + '</b> → ostatnia dostawa <b>' + zl(cena) + '/' + esc(g.jm || 'jm')
      + '</b> to <b>' + num(jedn, jedn < 1 ? 5 : 2) + ' ' + esc(DB.settings.currency) + '/'
      + esc(ing.unit) + '</b>'
      + (ing.packQty ? ' — opakowanie ' + num(ing.packQty, 0) + ' ' + esc(ing.unit)
          + ' za <b>' + zl(jedn * ing.packQty) + '</b>, w bazie '
          + (ing.packPrice != null ? zl(ing.packPrice) : '—') : '');
  };

  openDlg('Dopasuj pozycję do składnika', `
    <div class="hint" style="margin-bottom:10px">Pozycja z faktury:
      <b>${esc(g.opis)}</b> — ${g.wiersze.length} ${mnoga(g.wiersze.length,
        'dostawa', 'dostawy', 'dostaw')}, jednostka <b>${esc(g.jm || '—')}</b>.</div>
    <div class="row" style="gap:16px;margin-bottom:12px">
      <label class="row" style="gap:6px;flex-wrap:nowrap"><input type="radio" name="zdTryb"
        value="jest" checked><span>Istniejący składnik</span></label>
      <label class="row" style="gap:6px;flex-wrap:nowrap"><input type="radio" name="zdTryb"
        value="nowy"><span>Nowy składnik z tej pozycji</span></label>
    </div>
    <div id="zdBlokJest">
      <label class="f">Składnik</label>
      ${combo('zdIng', 'Szukaj składnika…')}
      ${!dop.ing && podp.length ? `<div class="hint" id="zdPodp" style="margin-top:6px">
        Podpowiedź z nazwy fakturowej: ${podp.map(x=>`<button class="btn sm"
          data-zdpodp="${esc(x.ing.id)}" title="wspólny fragment: ${esc(x.trafienie)}"
          style="margin-right:6px">${esc(x.ing.name)}</button>`).join('')}</div>` : ''}
    </div>
    <div class="hint" style="margin-top:12px">Wszystkie dostawy tej pozycji
      — <b>${g.wiersze.length}</b> ${mnoga(g.wiersze.length,
        'wiersz', 'wiersze', 'wierszy')} z faktur:</div>
    ${tabelaDostaw(g, false)}
    <div id="zdBlokNowy" style="display:none">
      <div class="grid" style="grid-template-columns:2fr 1fr">
        <div><label class="f">Nazwa składnika</label>
          <input id="zdNazwa" type="text" value="${esc(g.opis)}">
          <div class="hint" id="zdNazwaInfo" style="margin-top:4px"></div></div>
        <div><label class="f">Kategoria</label>${combo('zdKat','Kategoria…')}</div>
      </div>
      <div class="grid" style="grid-template-columns:1fr 1fr 1fr;margin-top:8px">
        <div><label class="f">Jednostka</label>${combo('zdUnit','Jednostka…')}</div>
        <div><label class="f">Ile w opakowaniu</label>
          <input id="zdQty" type="number" step="any" min="0" value="1"></div>
        <div><label class="f">Cena opakowania</label>
          <input id="zdCena" type="number" step="any" min="0"></div>
      </div>
      <div class="hint" style="margin-top:6px">Nazwa z faktury bywa skrótem magazynowym
        („P MC ŁOS.ATL.FIL.TR.E") — popraw ją na taką, jaką chcesz widzieć w recepturach.
        Cena liczy się z faktur i możesz ją nadpisać.</div>
    </div>
    <label class="f" style="margin-top:10px">Ile jednostek składnika w jednej ${esc(g.jm || 'jednostce')} z faktury</label>
    <input id="zdPrzel" type="number" step="any" min="0" value="${dop.przelicz ?? 1}">
    <div class="hint" style="margin-top:6px">Kilogram łososia to <b>1000</b> gramów, paczka nori
      „280g,100ark." to <b>100</b> arkuszy, opakowanie krewetek „20szt" to <b>20</b> sztuk.
      Gdy jednostki są te same — zostaw <b>1</b>.</div>
    <div id="zdPodglad" class="hint" style="margin-top:10px;padding-top:10px;border-top:1px solid var(--grid)"></div>`,
    [ ...(g.dop ? [{label: 'Odepnij', fn: ()=>{
        delete DB.zakupy.dopasowania[klucz]; save(); render(); }}] : []),
      {label: 'Anuluj', cls: ''},
      {label: 'Zapisz', cls: 'pri', fn: ()=>{
        const przel = przelicznik();
        if(!przel || przel <= 0){ alert('Podaj przelicznik większy od zera.'); return false; }
        let id;
        if(tryb() === 'nowy'){
          const nazwa = val('zdNazwa').trim();
          const q = parseFloat(val('zdQty')), c = parseFloat(val('zdCena'));
          if(!nazwa){ alert('Podaj nazwę składnika.'); return false; }
          if(!q || q <= 0){ alert('Podaj, ile jednostek jest w opakowaniu.'); return false; }
          // Składnik zakładamy dokładnie takim samym obiektem, jaki robi edytor
          // w Składnikach — inaczej powstałby drugi rodzaj składnika, różniący się
          // tym, którędy wszedł do bazy.
          const ing = {id: uid('ing'), name: nazwa, cat: val('zdKat').trim() || 'Inne',
                       unit: val('zdUnit').trim() || 'szt.', packQty: q,
                       packPrice: isNaN(c) ? null : c, gPerUnit: null, nutr: null, alerg: []};
          DB.ingredients.push(ing);
          id = ing.id;
        } else {
          id = val('zdIng');
          if(!id){ alert('Wybierz składnik.'); return false; }
        }
        DB.zakupy.dopasowania[klucz] = {ing: id, przelicz: przel};
        // Dopasowanie znaczy „to jest towar" — pominięcie tej samej nazwy byłoby
        // sprzecznością, więc znika razem z zapisem.
        delete DB.zakupy.pomijane[klucz];
        save(); render();
      }}],
    ()=>{
      const opcje = [PUSTY_WYBOR].concat(active(DB.ingredients).map(x=>({v: x.id,
        l: x.name + ' (' + x.unit + ')'})));
      fillCombo('zdIng', opcje, dop.ing || '', podglad);
      fillCombo('zdKat', cats.map(c=>({v:c, l:c})), 'Inne', null, {wolny:true});
      fillCombo('zdUnit', jednostki().map(u=>({v:u, l:u})), g.jm || 'g', podglad, {wolny:true});
      // Podpowiedź tylko podstawia wybór do listy — dalej trzeba podać przelicznik
      // i zapisać, więc nic nie dzieje się za plecami człowieka.
      document.querySelectorAll('[data-zdpodp]').forEach(b=>b.addEventListener('click', ()=>{
        fillCombo('zdIng', opcje, b.dataset.zdpodp, podglad);
        podglad();
      }));
      ['zdPrzel', 'zdQty', 'zdUnit_q', 'zdNazwa'].forEach(x=>{
        const e = document.getElementById(x);
        if(e) e.addEventListener('input', podglad);
      });
      const q = document.getElementById('zdQty');
      if(q) q.addEventListener('input', ()=>{ recznaIlosc = true; });
      const c = document.getElementById('zdCena');
      if(c) c.addEventListener('input', ()=>{ c.dataset.reczne = '1'; });
      document.querySelectorAll('[name="zdTryb"]').forEach(r=>r.addEventListener('change', podglad));
      podglad();
    });
}

function dlgZakPomin(klucz){
  const g = zakGrupy().find(x=>x.klucz === klucz);
  if(!g) return;
  const nipy = Object.keys(g.nipy);
  openDlg('Pomiń pozycję', `
    <div class="hint" style="margin-bottom:10px">Pozycja z faktury: <b>${esc(g.opis)}</b>.
      Pominięte pozycje nie liczą się do cen składników i nie proszą się o dopasowanie.</div>
    <label class="row" style="gap:8px;align-items:flex-start;margin-bottom:10px;flex-wrap:nowrap">
      <input type="radio" name="zpTryb" value="nazwa" checked style="margin-top:3px;flex:none">
      <span style="flex:1;min-width:0"><b>Zawsze, u każdego dostawcy</b>
        <div class="hint">To nigdy nie jest składnik receptury — frytura, rękawice, worki.</div></span></label>
    <label class="row" style="gap:8px;align-items:flex-start;margin-bottom:10px;flex-wrap:nowrap">
      <input type="radio" name="zpTryb" value="dostawca" style="margin-top:3px;flex:none">
      <span style="flex:1;min-width:0"><b>Tylko u tego dostawcy</b>
        <div class="hint">Towar jest nasz, ale ten dostawca jest awaryjny — jak ryż z MAKRO,
          gdy stałym dostawcą są Kuchnie Świata. U pozostałych liczy się dalej.</div>
        <select id="zpNip" style="margin-top:6px;width:100%">
          ${nipy.map(n=>`<option value="${esc(n)}">${esc(g.nipy[n] || n)} (${esc(n)})</option>`).join('')}
        </select></span></label>
    <div class="hint">Pojedynczą dostawę — pomyłkę albo cenę z kosmosu — pomija się
      na liście dostaw tej pozycji.</div>`,
    [{label: 'Anuluj', cls: ''},
     {label: 'Pomijaj', cls: 'pri', fn: ()=>{
       const tryb = (document.querySelector('[name="zpTryb"]:checked') || {}).value;
       if(tryb === 'dostawca') DB.zakupy.pomijaneU[klucz + '|' + val('zpNip')] = true;
       else { DB.zakupy.pomijane[klucz] = true; delete DB.zakupy.dopasowania[klucz]; }
       save(); render();
     }}]);
}

/** Lista dostaw jednej pozycji — tu widać, dlaczego średnia wyszła taka, a nie inna,
    i stąd pomija się pojedynczy wiersz. */
function dlgZakDostawy(klucz){
  const g = zakGrupy().find(x=>x.klucz === klucz);
  if(!g) return;
  const rysuj = ()=>{
    const c = document.getElementById('zdlBody');
    if(!c) return;
    c.innerHTML = tabelaDostaw(g, true);
    c.querySelectorAll('[data-zakpoz]').forEach(b=>b.addEventListener('click',()=>{
      const id = b.dataset.zakpoz;
      if(DB.zakupy.pomijanePoz[id]) delete DB.zakupy.pomijanePoz[id];
      else DB.zakupy.pomijanePoz[id] = true;
      save(); rysuj();
    }));
  };
  openDlg('Dostawy: ' + g.opis,
    `<div class="hint" style="margin-bottom:10px">Pominięta dostawa nie liczy się do ceny.
      Tak wyrzuca się pomyłkę albo jednorazową cenę, nie ruszając reszty.</div>
     <div id="zdlBody"></div>`,
    [{label: 'Zamknij', cls: 'pri', fn: ()=>{ render(); }}], rysuj);
}

/** Wgranie paczek eksportowych z KSeF wprost z przeglądarki.

    Bez tego okna paczkę trzeba było wnieść na serwer (scp, konsola, polecenie) — czyli
    zejść z aplikacji do powłoki po to, żeby zrobić rzecz, która jest częścią zwykłej
    pracy z zakupami.

    Okno przyjmuje OD RAZU WIELE PACZEK, bo tak wygląda import roku: dwanaście miesięcy,
    każdy z własnym kluczem. Pierwsza wersja brała pierwszy napotkany `.json` jako klucz
    do wszystkiego i sklejała ze sobą pliki różnych miesięcy — openssl mówił wtedy
    „bad decrypt", i miał rację. Pliki grupujemy więc po nazwie bazowej: `ksef-2026-03`
    to jedna paczka, jej części i jej klucz. */
function grupyPaczek(pliki){
  const bazowa = n => String(n)
    .replace(/-cz\d+\.zip\.aes$/i, '')
    .replace(/\.zip\.aes$/i, '')
    .replace(/-klucz\.json$/i, '')
    .replace(/\.json$/i, '')
    .replace(/\.zip$/i, '');
  const wg = {};
  pliki.forEach(f=>{
    const k = bazowa(f.name);
    const g = wg[k] || (wg[k] = {nazwa: k, czesci: [], klucz: null});
    if(/\.json$/i.test(f.name)) g.klucz = f;
    else g.czesci.push(f);
  });
  const grupy = Object.keys(wg).sort((a, b)=>a.localeCompare(b, 'pl', {numeric: true}))
    .map(k=>wg[k]);
  grupy.forEach(g=>g.czesci.sort((a, b)=>a.name.localeCompare(b.name, 'pl', {numeric: true})));
  // Jeden klucz i jedna paczka nazwana inaczej — częsty przypadek przy ręcznym
  // przekładaniu plików. Skoro klucz jest dokładnie jeden, nie ma czego mylić.
  const bezKlucza = grupy.filter(g=>g.czesci.length && !g.klucz);
  const same = grupy.filter(g=>!g.czesci.length && g.klucz);
  if(bezKlucza.length === 1 && same.length === 1){
    bezKlucza[0].klucz = same[0].klucz;
    return grupy.filter(g=>g.czesci.length);
  }
  return grupy.filter(g=>g.czesci.length);
}

function dlgZakPaczka(){
  const wybrane = ()=>[...((document.getElementById('zpPliki') || {}).files || [])];

  const pokazPliki = ()=>{
    const lista = document.getElementById('zpLista');
    if(!lista) return;
    const grupy = grupyPaczek(wybrane());
    if(!grupy.length){ lista.innerHTML = ''; return; }
    lista.innerHTML = `<b>${grupy.length}</b> ${grupy.length === 1 ? 'paczka' : 'paczki'} do wczytania:
      <div class="tw" style="margin-top:6px"><table><tbody>
      ${grupy.map(g=>`<tr><td>${esc(g.nazwa)}</td>
        <td class="r">${g.czesci.length} ${g.czesci.length === 1 ? 'część' : 'części'}</td>
        <td>${g.klucz ? '<span class="mut">klucz: ' + esc(g.klucz.name) + '</span>'
          : (g.czesci.some(f=>/\.aes$/i.test(f.name))
             ? '<span class="uwaga-txt">brak klucza</span>'
             : '<span class="mut">bez szyfrowania</span>')}</td></tr>`).join('')}
      </tbody></table></div>`;
  };

  const wczytaj = async (przycisk)=>{
    const wynik = document.getElementById('zpWynik');
    const grupy = grupyPaczek(wybrane());
    if(!grupy.length){ alert('Wybierz pliki paczek.'); return; }
    const napis = przycisk.textContent;
    przycisk.disabled = true;
    // Lista plików zwija się do jednej linijki: od tej chwili patrzy się na wyniki,
    // a nie na to, co się wybrało.
    const lista = document.getElementById('zpLista');
    if(lista) lista.innerHTML = '<b>' + grupy.length + '</b> '
      + (grupy.length === 1 ? 'paczka' : 'paczki') + ' — wynik poniżej.';
    const b64 = f => new Promise((ok, zle)=>{
      const r = new FileReader();
      r.onload = ()=>ok(String(r.result).split(',')[1] || '');
      r.onerror = ()=>zle(new Error('Nie udało się odczytać pliku ' + f.name));
      r.readAsDataURL(f);
    });
    const wyniki = [];
    // Paczka po paczce, a nie wszystkie naraz: każda ma własny klucz, a błąd jednej
    // nie ma prawa zabrać pozostałych.
    for(let n = 0; n < grupy.length; n++){
      const g = grupy[n];
      przycisk.textContent = 'Wczytuję ' + (n + 1) + ' z ' + grupy.length + '…';
      wynik.innerHTML = `<span class="mut">Wysyłam <b>${esc(g.nazwa)}</b>
        (${n + 1} z ${grupy.length})…</span>`;
      try{
        const tresc = {
          czesci: await Promise.all(g.czesci.map(async f=>({nazwa: f.name, b64: await b64(f)}))),
          klucz: g.klucz ? JSON.parse(await g.klucz.text()) : null
        };
        const r = await fetch('/api/zakupy/paczka', {method: 'POST',
          headers: {'Content-Type': 'application/json'}, body: JSON.stringify(tresc)});
        const o = await r.json();
        wyniki.push(r.ok ? Object.assign({paczka: g.nazwa}, o)
                         : {paczka: g.nazwa, blad: o.error || 'Nie udało się.'});
      }catch(e){
        wyniki.push({paczka: g.nazwa, blad: e.message || String(e)});
      }
      wynik.innerHTML = tabelaWynikow(wyniki, grupy.length);
    }
    ZAK_KLUCZ = null;                    // księgi się zmieniły — ekran ma to pokazać
    przycisk.disabled = false; przycisk.textContent = napis;
  };

  /** Liczby, a nie „gotowe": powtórzenia i pominięcia są tu normalne (paczkę wolno
      wczytać drugi raz), więc muszą być widoczne, żeby nie wyglądały na błąd. */
  const tabelaWynikow = (wyniki, ile)=>{
    const suma = wyniki.reduce((a, w)=>({
      przyjete: a.przyjete + (w.przyjete || 0),
      powtorzone: a.powtorzone + (w.powtorzone || 0),
      pominieci: a.pominieci + (w.pominieci || 0),
      bezNumeru: a.bezNumeru + ((w.bezNumeru || []).length),
      bledow: a.bledow + (w.blad ? 1 : 0)
    }), {przyjete: 0, powtorzone: 0, pominieci: 0, bezNumeru: 0, bledow: 0});
    return `<div class="tw"><table><thead><tr><th>Paczka</th><th class="r">Przyjęte</th>
        <th class="r">Powtórzone</th><th class="r">Pomijani</th><th>Uwagi</th></tr></thead><tbody>
      ${wyniki.map(w=>`<tr><td>${esc(w.paczka)}</td>
        ${w.blad ? `<td colspan="3" class="uwaga-txt">${esc(w.blad)}</td><td></td>`
          : `<td class="r num">${w.przyjete}</td><td class="r num">${w.powtorzone}</td>
             <td class="r num">${w.pominieci}</td>
             <td class="${(w.bezNumeru || []).length ? 'uwaga-txt' : 'mut'}">${
               (w.bezNumeru || []).length ? w.bezNumeru.length + ' faktur bez numeru KSeF'
                                          : w.pozycji + ' pozycji'}</td>`}</tr>`).join('')}
      <tr class="suma"><td>Razem${wyniki.length < ile ? ' (' + wyniki.length + ' z ' + ile + ')' : ''}</td>
        <td class="r num">${suma.przyjete}</td><td class="r num">${suma.powtorzone}</td>
        <td class="r num">${suma.pominieci}</td>
        <td class="${suma.bledow || suma.bezNumeru ? 'uwaga-txt' : 'mut'}">${
          suma.bledow ? suma.bledow + ' paczek z błędem' :
          (suma.bezNumeru ? suma.bezNumeru + ' faktur bez numeru' : 'bez uwag')}</td></tr>
    </tbody></table></div>`;
  };

  openDlg('Wgraj paczki z KSeF', `
    <div class="hint">Paczka z eksportu KSeF to <b>ZIP zaszyfrowany AES-256-CBC</b>, pocięty
      na części (<b>…cz01.zip.aes</b>), z osobnym plikiem klucza (<b>…-klucz.json</b>).
      Można wskazać <b>od razu wiele miesięcy</b> — pliki rozdzielą się po nazwie i każda
      paczka pójdzie ze swoim kluczem. Zwykły ZIP wchodzi bez klucza.</div>
    <div style="margin-top:10px"><input type="file" id="zpPliki" multiple></div>
    <div id="zpLista" class="hint" style="margin-top:8px"></div>
    <div id="zpWynik" style="margin-top:12px"></div>
    <div class="hint" style="margin-top:10px">Tę samą paczkę można wczytać drugi raz —
      klucz (numer KSeF + numer pozycji) nie wpuści niczego dwa razy.</div>`,
    [{label: 'Zamknij', cls: '', fn: ()=>{ render(); }},
     {label: 'Wczytaj', cls: 'pri', fn: function(){
       const b = [...document.querySelectorAll('#dlgFoot .btn')]
         .find(x=>x.textContent.indexOf('Wczytuj') >= 0 || x.textContent.indexOf('Wczytaj') >= 0);
       wczytaj(b);
       return false;                    // okno zostaje — na nim pokazujemy wynik
     }}],
    ()=>{
      const we = document.getElementById('zpPliki');
      if(we) we.addEventListener('change', pokazPliki);
    });
}

/* ---------- ekran ---------- */

function vZakupy(){
  const ramka = tresc => `<div class="topbar"><h1>Zakupy</h1>
    <span class="sub">faktury z KSeF</span></div><div id="ekrZakupy">${tresc}</div>`;
  // Dwa różne powody pustego ekranu i dwa różne zdania: bez serwera faktur nie ma
  // skąd wziąć, a bez roli zarządu nie ma komu ich pokazać.
  if(!(SRV.on && SRV.user))
    return ramka(`<div class="card"><div class="empty">Faktury przychodzą z KSeF na serwer —
      w trybie bez serwera nie ma ich skąd wziąć.</div></div>`);
  if(ZARZAD.indexOf(SRV.user.role) < 0)
    return ramka(`<div class="card"><div class="empty">
      Zakupy widzi właściciel i administrator.</div></div>`);
  const z = zakZakres(), klucz = z.od + '|' + z.doo;
  if(ZAK_KLUCZ !== klucz){
    after('zakupy', async ()=>{ await wczytajZakupy(); render(); });
    return ramka(`<div class="card"><div class="empty">Wczytuję zakupy…</div></div>`);
  }
  const grupy = zakGrupy(), dostawcy = zakDostawcy(), prop = zakPropozycje();
  // Zaznaczenie przycinamy do tego, co widać: po zmianie zakresu albo po sprzątnięciu
  // dostawcy jego NIP znika z listy, a zaznaczenie duchów niczego by nie zrobiło.
  const zazn = ZAK_ZAZN.filter(n=>dostawcy.some(d=>d.nip === n));
  ZAK_ZAZN = zazn;
  const zaznDost = dostawcy.filter(d=>zazn.indexOf(d.nip) >= 0);
  const doPomin = zaznDost.filter(d=>!d.pomijany), doPrzywr = zaznDost.filter(d=>d.pomijany);
  const paskZaznaczenia = zazn.length ? `<div class="row"
      style="gap:8px;align-items:center;margin-top:10px;flex-wrap:wrap">
    <b>Zaznaczono ${zazn.length} ${zazn.length === 1 ? 'dostawcę' : 'dostawców'}</b>
    <span class="spacer" style="flex:1"></span>
    ${doPomin.length ? `<button class="btn sm pri" data-zpomin-grupa>Pomijaj ${
      doPomin.length === zazn.length ? 'zaznaczonych' : doPomin.length}</button>` : ''}
    ${doPrzywr.length ? `<button class="btn sm" data-zprzywroc-grupa>Przywróć ${
      doPrzywr.length === zazn.length ? 'zaznaczonych' : doPrzywr.length}</button>` : ''}
    <button class="btn sm" data-zodznacz>Odznacz</button></div>` : '';
  const zaznP = ZAK_ZAZN_POZ.filter(k=>grupy.some(g=>g.klucz === k));
  ZAK_ZAZN_POZ = zaznP;
  const zaznGr = grupy.filter(g=>zaznP.indexOf(g.klucz) >= 0);
  const pozPomin = zaznGr.filter(g=>g.stan !== 'pominieta');
  const pozPrzywr = zaznGr.filter(g=>g.stan === 'pominieta');
  const paskPozycji = zaznP.length ? `<div class="row"
      style="gap:8px;align-items:center;margin:10px 0;flex-wrap:wrap">
    <b>Zaznaczono ${zaznP.length} ${mnoga(zaznP.length, 'pozycję', 'pozycje', 'pozycji')}</b>
    <span class="spacer" style="flex:1"></span>
    ${pozPomin.length ? `<button class="btn sm pri" data-zpompoz-grupa>Pomijaj ${
      pozPomin.length === zaznP.length ? 'zaznaczone' : pozPomin.length}</button>` : ''}
    ${pozPrzywr.length ? `<button class="btn sm" data-zprzywpoz-grupa>Przywróć ${
      pozPrzywr.length === zaznP.length ? 'zaznaczone' : pozPrzywr.length}</button>` : ''}
    <button class="btn sm" data-zodznaczpoz>Odznacz</button></div>` : '';
  const doZrobienia = grupy.filter(g=>g.stan === 'nowa');
  const doZmiany = prop.filter(p=>p.zmiana);
  const wiersze = zakLista();

  after('zakupy', ()=>{
    // Automat wpisuje ceny po renderze, nie w jego trakcie: zapis bazy w środku
    // rysowania wszedłby renderowi w drogę, a on i tak przerysuje ekran po zmianie.
    if(zakAutoZatwierdz()){ render(); return; }
    const m = document.getElementById('main');
    m.querySelectorAll('[data-zdop]').forEach(b=>b.addEventListener('click',
      ()=>dlgZakDopasuj(b.dataset.zdop)));
    m.querySelectorAll('[data-zpom]').forEach(b=>b.addEventListener('click',
      ()=>dlgZakPomin(b.dataset.zpom)));
    m.querySelectorAll('[data-zdost]').forEach(b=>b.addEventListener('click',
      ()=>dlgZakDostawy(b.dataset.zdost)));
    m.querySelectorAll('[data-zwroc]').forEach(b=>b.addEventListener('click',()=>{
      zakPrzywrocPozycje([b.dataset.zwroc]);
      save(); render();
    }));
    m.querySelectorAll('[data-zpozsel]').forEach(c=>c.addEventListener('change',()=>{
      const k = c.dataset.zpozsel;
      ZAK_ZAZN_POZ = c.checked ? ZAK_ZAZN_POZ.concat([k]) : ZAK_ZAZN_POZ.filter(x=>x !== k);
      render();
    }));
    m.querySelectorAll('[data-zpozall]').forEach(c=>c.addEventListener('change',()=>{
      const klucze = zakGrupy().filter(g=>g.stan === c.dataset.zpozall).map(g=>g.klucz);
      ZAK_ZAZN_POZ = c.checked
        ? ZAK_ZAZN_POZ.concat(klucze.filter(k=>ZAK_ZAZN_POZ.indexOf(k) < 0))
        : ZAK_ZAZN_POZ.filter(k=>klucze.indexOf(k) < 0);
      render();
    }));
    const odznP = m.querySelector('[data-zodznaczpoz]');
    if(odznP) odznP.addEventListener('click',()=>{ ZAK_ZAZN_POZ = []; render(); });
    const grupPomP = m.querySelector('[data-zpompoz-grupa]');
    if(grupPomP) grupPomP.addEventListener('click',()=>dlgZakPomijajPozycje());
    // Przywrócenie niczego nie kasuje — tak samo jak u dostawców, idzie bez pytania.
    const grupPrzP = m.querySelector('[data-zprzywpoz-grupa]');
    if(grupPrzP) grupPrzP.addEventListener('click',()=>{
      zakPrzywrocPozycje(ZAK_ZAZN_POZ);
      ZAK_ZAZN_POZ = [];
      save(); render();
    });
    m.querySelectorAll('[data-znip]').forEach(b=>b.addEventListener('click',()=>zakDostawcaTryb(b.dataset.znip)));
    m.querySelectorAll('[data-znipsel]').forEach(c=>c.addEventListener('change',()=>{
      const nip = c.dataset.znipsel;
      ZAK_ZAZN = c.checked ? ZAK_ZAZN.concat([nip]) : ZAK_ZAZN.filter(x=>x !== nip);
      render();
    }));
    const wszyscy = m.querySelector('[data-znipall]');
    if(wszyscy) wszyscy.addEventListener('change',()=>{
      ZAK_ZAZN = wszyscy.checked ? zakDostawcy().map(d=>d.nip) : [];
      render();
    });
    const odzn = m.querySelector('[data-zodznacz]');
    if(odzn) odzn.addEventListener('click',()=>{ ZAK_ZAZN = []; render(); });
    const grupPom = m.querySelector('[data-zpomin-grupa]');
    if(grupPom) grupPom.addEventListener('click',()=>dlgZakPomijajWielu());
    // Przywrócenie niczego nie kasuje, więc nie ma o co pytać.
    const grupPrz = m.querySelector('[data-zprzywroc-grupa]');
    if(grupPrz) grupPrz.addEventListener('click',()=>{
      DB.zakupy.pomijaniNip = (DB.zakupy.pomijaniNip || []).filter(n=>ZAK_ZAZN.indexOf(n) < 0);
      ZAK_ZAZN = [];
      save(); render();
    });
    m.querySelectorAll('[data-zzat]').forEach(b=>b.addEventListener('click',()=>{
      const p = zakPropozycje().find(x=>x.ing.id === b.dataset.zzat);
      if(p) zakZatwierdz(p);
    }));
    const bp = m.querySelector('[data-zpaczka]');
    if(bp) bp.addEventListener('click', ()=>dlgZakPaczka());
    m.querySelectorAll('[data-zzakres] button').forEach(b=>b.addEventListener('click',()=>{
      ZAK_ZAKRES = +b.dataset.z; ZAK_KLUCZ = null; render();
    }));
  });

  const kartaProp = `<div class="card" style="margin-top:12px">
    <div class="row" style="justify-content:space-between;align-items:baseline">
      <h2 style="margin:0">Ceny do zatwierdzenia</h2>
      <span class="hint">średnia ważona ilością z ${zakOkno()} dni${zakAuto()
        ? ', zmiany do ' + num(zakAuto(), zakAuto() % 1 ? 1 : 0) + '% wpisują się same'
        : ''}</span>
    </div>
    ${doZmiany.length ? `<div class="tw"><table><thead><tr>
        <th>Składnik</th><th class="r">Dostaw</th><th class="r">Z faktur</th>
        <th class="r">W bazie</th><th class="r">Różnica</th><th></th></tr></thead><tbody>
      ${doZmiany.map(p=>`<tr><td>${esc(p.ing.name)}
          <span class="mut small">${esc(p.nazwy.join(', '))}</span></td>
        <td class="r num">${p.dostaw}</td>
        <td class="r num"><b>${zl(p.cena)}</b>
          <span class="mut small">za ${num(p.ing.packQty, 0)} ${esc(p.ing.unit)}</span></td>
        <td class="r num">${p.teraz != null ? zl(p.teraz) : '<span class="mut">—</span>'}</td>
        <td class="r num">${p.roznica == null ? '<span class="mut">nowa</span>'
          : `<span class="${p.roznica > 0 ? 'uwaga-txt' : ''}">${p.roznica > 0 ? '+' : ''}${
             num(p.roznica * 100, 1)}%</span>`}</td>
        <td class="r"><button class="btn sm pri" data-zzat="${esc(p.ing.id)}">Zatwierdź</button></td>
      </tr>`).join('')}
    </tbody></table></div>` : `<div class="empty" style="margin-top:8px">
      ${prop.length ? 'Ceny z faktur zgadzają się z bazą.' : 'Brak dopasowanych zakupów w oknie ' + zakOkno() + ' dni.'}
    </div>`}
    ${prop.length - doZmiany.length > 0 ? `<div class="hint" style="margin-top:8px">${
      prop.length - doZmiany.length} ${prop.length - doZmiany.length === 1 ? 'składnik zgadza się'
        : 'składników zgadza się'} z bazą — bez zmian.</div>` : ''}
  </div>`;

  const wiersz = g => `<tr><td class="c"><input type="checkbox" data-zpozsel="${esc(g.klucz)}"
      ${zaznP.indexOf(g.klucz) >= 0 ? 'checked' : ''}></td>
    <td class="n">${esc(g.opis)}
      <span class="mut small">${Object.keys(g.nipy).map(n=>esc(g.nipy[n] || n)).join(', ')}</span></td>
    <td class="r"><a href="#" data-zdost="${esc(g.klucz)}">${g.wiersze.length} ${
      mnoga(g.wiersze.length, 'dostawa', 'dostawy', 'dostaw')}</a></td>
    <td class="r num">${g.ostatnia.cena != null ? zl(g.ostatnia.cena) : '—'}
      <span class="mut small">za ${esc(g.jm || 'jm')}</span></td>
    <td>${g.dop ? `<b>${esc((CALC.ing(g.dop.ing) || {}).name || '—')}</b>
        <span class="mut small">× ${num(g.dop.przelicz, g.dop.przelicz % 1 ? 2 : 0)}${
          g.pominietych ? ', ' + g.pominietych + ' poza ceną' : ''}</span>`
      : '<span class="mut">—</span>'}</td>
    <td class="r">${g.stan === 'pominieta'
      ? `<button class="btn sm" data-zwroc="${esc(g.klucz)}">Przywróć</button>`
      : `<button class="btn sm" data-zdop="${esc(g.klucz)}">${g.dop ? 'Zmień' : 'Dopasuj'}</button>
         <button class="btn sm" data-zpom="${esc(g.klucz)}">Pomiń</button>`}</td></tr>`;

  /* `stan` steruje główkowym polem wyboru: zaznacza całą sekcję, a nie zapamiętaną
     listę — po pominięciu pozycja przechodzi do innej sekcji i lista by skłamała. */
  const kolumnyPoz = `<colgroup><col style="width:34px"><col>
      <col style="width:104px"><col style="width:160px">
      <col style="width:180px"><col style="width:168px"></colgroup>`;
  const tabela = (lista, pusto, stan) => lista.length
    ? `<div class="tw"><table class="tabpoz">${kolumnyPoz}<thead><tr>
        <th class="c"><input type="checkbox" data-zpozall="${stan}"
          ${lista.every(g=>zaznP.indexOf(g.klucz) >= 0) ? 'checked' : ''}></th>
        <th>Pozycja z faktury</th><th class="r">Dostaw</th>
        <th class="r">Ostatnia cena</th><th>Składnik</th><th></th></tr></thead>
        <tbody>${lista.map(wiersz).join('')}</tbody></table></div>`
    : `<div class="empty">${pusto}</div>`;

  return ramka(`${ZAK_BLAD ? `<div class="banner">${esc(ZAK_BLAD)}</div>` : ''}
  <div class="card">
    <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:10px">
      <span class="hint">Faktury wpadają z KSeF przez n8n. Aplikacja niczego nie zmienia
        w cenach sama — proponuje, zatwierdzasz Ty.</span>
      <span class="row" style="gap:8px">
      <button class="btn sm" data-zpaczka>Wgraj paczki…</button>
      <span class="seg" data-zzakres>${[30, 90, 365].map(d=>
        `<button class="btn sm ${ZAK_ZAKRES === d ? 'pri' : ''}" data-z="${d}">${
          d === 365 ? 'rok' : d + ' dni'}</button>`).join('')}</span></span>
    </div>
    <div class="tiles">
      <div class="tile"><div class="lab">Pozycji</div><div class="val num">${wiersze.length}</div></div>
      <div class="tile"><div class="lab">Do dopasowania</div>
        <div class="val num ${doZrobienia.length ? 'uwaga-txt' : ''}">${doZrobienia.length}</div></div>
      <div class="tile"><div class="lab">Cen do zatwierdzenia</div>
        <div class="val num">${doZmiany.length}</div></div>
    </div>
  </div>
  ${kartaProp}
  <div class="card" style="margin-top:12px"><h2>Pozycje faktur</h2>
    ${paskPozycji}
    ${sekcjaBlok('Do dopasowania (' + doZrobienia.length + ')',
      tabela(doZrobienia, 'Wszystko rozpoznane.', 'nowa'))}
    ${sekcjaBlok('Dopasowane (' + grupy.filter(g=>g.stan === 'dopasowana').length + ')',
      tabela(grupy.filter(g=>g.stan === 'dopasowana'), 'Nic jeszcze nie dopasowane.', 'dopasowana'))}
    ${sekcjaBlok('Pominięte (' + grupy.filter(g=>g.stan === 'pominieta').length + ')',
      tabela(grupy.filter(g=>g.stan === 'pominieta'), 'Nic nie pominięte.', 'pominieta'))}
  </div>
  <div class="card" style="margin-top:12px"><h2>Dostawcy</h2>
    <div class="hint">Dostawcę poznajemy po NIP-ie z numeru KSeF, nie po nazwie.
      Pomijany dostawca w ogóle nie trafia do bazy — jego faktury odpadają już na serwerze.</div>
    ${paskZaznaczenia}
    <div class="tw" style="margin-top:10px"><table><thead><tr>
      <th class="c"><input type="checkbox" data-znipall
        ${dostawcy.length && zazn.length === dostawcy.length ? 'checked' : ''}></th>
      <th>Dostawca</th><th>NIP</th>
      <th class="r">Faktur</th><th class="r">Pozycji</th><th class="r">Ostatnia</th><th></th>
      </tr></thead><tbody>
      ${dostawcy.map(d=>`<tr class="${d.pomijany ? 'mut' : ''}">
        <td class="c"><input type="checkbox" data-znipsel="${esc(d.nip)}"
          ${zazn.indexOf(d.nip) >= 0 ? 'checked' : ''}></td>
        <td>${esc(d.nazwa || '—')}</td><td class="num">${esc(d.nip)}</td>
        <td class="r num">${d.ileFaktur || '—'}</td><td class="r num">${d.pozycji || '—'}</td>
        <td class="r">${d.ostatnia ? esc(dataKrotko(d.ostatnia)) : '—'}</td>
        <td class="r"><button class="btn sm" data-znip="${esc(d.nip)}">${
          d.pomijany ? 'Przywróć' : 'Pomijaj'}</button></td></tr>`).join('')
        || '<tr><td colspan="7"><div class="empty">Żadnych faktur w tym zakresie.</div></td></tr>'}
    </tbody></table></div>
  </div>`);
}

/** Przywrócenie pozycji: zdejmuje wszystkie trzy poziomy pomijania naraz.

    Człowiek pominął nazwę, potem u jednego dostawcy, potem jedną dostawę — a klika
    „Przywróć" raz i oczekuje, że pozycja wróci cała. Zdejmowanie po jednym poziomie
    zostawiałoby ją pominiętą bez widocznego powodu. */
function zakPrzywrocPozycje(klucze){
  const grupy = zakGrupy();
  klucze.forEach(k=>{
    delete DB.zakupy.pomijane[k];
    Object.keys(DB.zakupy.pomijaneU).forEach(x=>{
      if(x.indexOf(k + '|') === 0) delete DB.zakupy.pomijaneU[x];
    });
    (grupy.find(g=>g.klucz === k) || {wiersze: []}).wiersze
      .forEach(w=>delete DB.zakupy.pomijanePoz[w.id]);
  });
}

/** Pomijanie wielu pozycji naraz — jedno pytanie zamiast kilkunastu.

    Grupowo pomijamy zawsze na poziomie NAZWY, u każdego dostawcy. Poziom „tylko u tego
    dostawcy" jest z natury pojedynczą decyzją — dotyczy jednej nazwy u jednego dostawcy
    i przy dziesięciu zaznaczonych pozycjach nie da się o niego sensownie zapytać jednym
    oknem. Zbiorowo wyrzuca się to, co nigdy nie jest składnikiem: rękawice, worki, folię.

    Ksiąg tu nie sprzątamy — inaczej niż przy dostawcach. Pominięta pozycja zostaje
    w zakupach (widać ją w sekcji „Pominięte"), tylko nie liczy się do cen. Faktura od
    pomijanego dostawcy nie wchodzi w ogóle, więc tam sprzątanie ma sens. */
function dlgZakPomijajPozycje(){
  const grupy = zakGrupy().filter(g=>ZAK_ZAZN_POZ.indexOf(g.klucz) >= 0 && g.stan !== 'pominieta');
  if(!grupy.length) return;
  const zDop = grupy.filter(g=>g.dop);
  openDlg('Pomijać te pozycje?', `
    <div class="hint">Nie będą się liczyły do cen składników ani prosiły o dopasowanie —
      u żadnego dostawcy. Tak wyrzuca się to, co nigdy nie jest składnikiem receptury:
      rękawice, worki, folię, fryturę.</div>
    <div class="tw" style="max-height:260px;overflow:auto;margin-top:10px"><table><tbody>
      ${grupy.map(g=>`<tr><td>${esc(g.opis)}
          <span class="mut small">${Object.keys(g.nipy).map(x=>esc(g.nipy[x] || x)).join(', ')}</span></td>
        <td class="r num">${g.wiersze.length} ${mnoga(g.wiersze.length,
          'dostawa', 'dostawy', 'dostaw')}</td>
        <td>${g.dop ? `<span class="uwaga-txt small"
          title="Dopasowanie, które zostanie zdjęte">${esc((CALC.ing(g.dop.ing)
          || {}).name || '—')}</span>` : ''}</td></tr>`).join('')}
    </tbody></table></div>
    ${zDop.length ? `<div class="hint uwaga-txt" style="margin-top:10px">${zDop.length} ${
      mnoga(zDop.length, 'z nich ma dopasowanie', 'z nich mają dopasowanie',
        'z nich ma dopasowanie')} do składnika — pominięcie je zdejmie.
      Sam składnik i jego cena zostają.</div>` : ''}
    <div class="hint" style="margin-top:10px">Pozycje zostaną w zakupach, w sekcji
      „Pominięte" — stamtąd wraca się jednym kliknięciem.</div>`,
    [{label: 'Anuluj', cls: ''},
     {label: 'Pomijaj', cls: 'pri', fn: ()=>{
       grupy.forEach(g=>{
         DB.zakupy.pomijane[g.klucz] = true;
         delete DB.zakupy.dopasowania[g.klucz];
       });
       ZAK_ZAZN_POZ = [];
       save(); render();
     }}]);
}

/** Pomijanie wielu dostawców naraz — jedno pytanie zamiast kilkunastu.

    Pytamy raz, ale o obie rzeczy: o samo pomijanie i o sprzątnięcie tego, co już wpadło.
    Sprzątanie idzie po jednym NIP-ie, bo tak wygląda trasa na serwerze; gdyby któreś
    się nie udało, mówimy które, zamiast zgłaszać ogólne „nie wyszło". */
function dlgZakPomijajWielu(){
  const dostawcy = zakDostawcy().filter(d=>ZAK_ZAZN.indexOf(d.nip) >= 0 && !d.pomijany);
  if(!dostawcy.length) return;
  const pozycji = dostawcy.reduce((a, d)=>a + (d.pozycji || 0), 0);
  openDlg('Pomijać tych dostawców?', `
    <div class="hint">Ich faktury nie będą wchodziły do bazy — ani teraz, ani przy kolejnych
      importach. Tak wyrzuca się serwis auta, telefon czy czynsz: wszystko, co nie jest
      towarem do kuchni.</div>
    <div class="tw" style="margin-top:10px"><table><tbody>
      ${dostawcy.map(d=>`<tr><td>${esc(d.nazwa || '—')}</td>
        <td class="num mut">${esc(d.nip)}</td>
        <td class="r num">${d.pozycji || 0}</td></tr>`).join('')}
    </tbody></table></div>
    ${pozycji ? `<label class="row" style="gap:8px;align-items:flex-start;margin-top:12px;flex-wrap:nowrap">
      <input type="checkbox" id="zgSprzataj" checked style="margin-top:3px;flex:none">
      <span style="flex:1;min-width:0">Usuń też <b>${pozycji}</b> ${pozycji === 1
        ? 'pozycję' : 'pozycji'}, które już wpadły<div class="hint">Same faktury zostają
        w księgowości — my trzymamy tylko numer KSeF, więc nic nie ginie bezpowrotnie.</div>
      </span></label>` : ''}
    <div id="zgWynik" style="margin-top:10px"></div>`,
    [{label: 'Anuluj', cls: ''},
     {label: 'Pomijaj', cls: 'pri', fn: function(){
       const sprzataj = (document.getElementById('zgSprzataj') || {}).checked;
       const lista = DB.zakupy.pomijaniNip || (DB.zakupy.pomijaniNip = []);
       dostawcy.forEach(d=>{
         if(lista.indexOf(d.nip) < 0) lista.push(d.nip);
         DB.zakupy.dostawcy[d.nip] = {nazwa: d.nazwa || ''};
       });
       ZAK_ZAZN = [];
       save();
       if(!sprzataj){ render(); return; }
       const wynik = document.getElementById('zgWynik');
       wynik.innerHTML = '<span class="mut">Sprzątam księgi…</span>';
       (async ()=>{
         const bledy = [];
         for(const d of dostawcy){
           try{
             const r = await fetch('/api/zakupy/sprzataj', {method: 'POST',
               headers: {'Content-Type': 'application/json'},
               body: JSON.stringify({nip: d.nip})});
             if(!r.ok) bledy.push(d.nazwa || d.nip);
           }catch(e){ bledy.push(d.nazwa || d.nip); }
         }
         ZAK_KLUCZ = null;
         if(bledy.length){
           wynik.innerHTML = `<div class="uwaga-txt">Nie udało się sprzątnąć ksiąg
             u: ${bledy.map(esc).join(', ')}. Pomijanie i tak zostało zapisane.</div>`;
           return;
         }
         DLG.close();
         render();
       })();
       return false;                    // okno zostaje, dopóki sprzątanie trwa
     }}]);
}

/** Przełączenie dostawcy: pomijany ↔ towar. Przy pomijaniu proponujemy sprzątnięcie
    tego, co już wpadło — nie jest konieczne (pomijany i tak nie liczy się do cen),
    ale trzymanie dwóch lat faktur za serwis auta nie ma sensu. */
function zakDostawcaTryb(nip){
  const d = zakDostawcy().find(x=>x.nip === nip);
  if(!d) return;
  const lista = DB.zakupy.pomijaniNip || (DB.zakupy.pomijaniNip = []);
  if(lista.indexOf(nip) >= 0){
    DB.zakupy.pomijaniNip = lista.filter(x=>x !== nip);
    save(); render();
    return;
  }
  openDlg('Pomijać tego dostawcę?', `
    <div class="hint">Faktury od <b>${esc(d.nazwa || nip)}</b> (NIP ${esc(nip)}) nie będą
      wchodziły do bazy. Tak wyrzuca się serwis auta, telefon czy czynsz — wszystko, co
      nie jest towarem do kuchni.</div>
    <label class="row" style="gap:8px;align-items:flex-start;margin-top:12px;flex-wrap:nowrap">
      <input type="checkbox" id="zdSprzataj" checked style="margin-top:3px;flex:none">
      <span style="flex:1;min-width:0">Usuń też <b>${d.pozycji}</b> ${d.pozycji === 1 ? 'pozycję' : 'pozycji'},
        które już wpadły<div class="hint">Same faktury zostają w księgowości — my trzymamy
          tylko numer KSeF, więc nic nie ginie bezpowrotnie.</div></span></label>`,
    [{label: 'Anuluj', cls: ''},
     {label: 'Pomijaj', cls: 'pri', fn: ()=>{
       lista.push(nip);
       DB.zakupy.dostawcy[nip] = {nazwa: d.nazwa || ''};
       const sprzataj = (document.getElementById('zdSprzataj') || {}).checked;
       save();
       if(sprzataj && d.pozycji){
         fetch('/api/zakupy/sprzataj', {method: 'POST',
           headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nip: nip})})
           .then(()=>{ ZAK_KLUCZ = null; render(); })
           .catch(()=>{ ZAK_KLUCZ = null; render(); });
       } else render();
     }}]);
}

function vSprzedaz(){
  if(!SPRZ_MIES) SPRZ_MIES = todayISO().slice(0,7);
  if(SPRZ === null){
    after('sprzedaz', async ()=>{ await wczytajSprzedaz(SPRZ_MIES); render(); });
    return `<div class="topbar"><h1>Sprzedaż</h1></div>
            <div class="card"><div class="empty">Wczytuję sprzedaż…</div></div>`;
  }

  after('sprzedaz',()=>{
    const idz = async (o)=>{ SPRZ_MIES = przesunMies(SPRZ_MIES, o);
                             SPRZ = null; SPRZ_WYNIK = null; render(); };
    const p = document.getElementById('sprzPrev'), n = document.getElementById('sprzNext'),
          t = document.getElementById('sprzDzis');
    if(p) p.addEventListener('click',()=>idz(-1));
    if(n) n.addEventListener('click',()=>idz(1));
    if(t) t.addEventListener('click',()=>{ SPRZ_MIES = todayISO().slice(0,7);
                                           SPRZ = null; SPRZ_WYNIK = null; render(); });
    document.querySelectorAll('[data-zakres] button').forEach(b=>b.addEventListener('click',()=>{
      SPRZ_ZAKRES[b.closest('[data-zakres]').dataset.zakres] = +b.dataset.z;
      render();
    }));
    const pr = document.querySelector('[data-act="pdfRaport"]');
    if(pr) pr.addEventListener('click',()=>pdfRaportTygodnia());
    const ra = document.getElementById('rapAut');
    if(ra) ra.addEventListener('change',()=>{
      if(wgDni()) SPRZ_RAPORT.dzien = +ra.value; else SPRZ_RAPORT.automat = ra.value;
      render(); });
    document.querySelectorAll('[data-wg] button').forEach(b=>b.addEventListener('click',()=>{
      SPRZ_RAPORT.wg = b.dataset.w; render(); }));
    rysujWykresySprzedazy();
    /* Szerokość karty jest tu daną wejściową, nie ozdobą — po obróceniu telefonu wykres
       trzeba przeliczyć. Nasłuch zakładamy raz, bo `after` wraca przy każdym rysowaniu. */
    if(!SPRZ_RESIZE){
      SPRZ_RESIZE = true;
      let czeka = null;
      addEventListener('resize', ()=>{
        clearTimeout(czeka);
        czeka = setTimeout(()=>{ if(VIEW === 'sprzedaz') rysujWykresySprzedazy(); }, 150);
      });
    }

    /* Dopasowanie idzie po WSZYSTKICH miesiącach, nie po tym z ekranu: numer seryjny
       wpisany dzisiaj odblokowuje też sprzedaże sprzed pół roku, a szukanie ich
       miesiąc po miesiącu byłoby robotą, którą komputer robi w sekundę. Dlatego
       podsumowanie stoi pod paskiem miesiąca, a nie w karcie „Nierozpoznane" —
       karta po udanym dopasowaniu potrafi zniknąć razem z odpowiedzią. */
    const dop = document.getElementById('sprzDopasuj');
    if(dop) dop.addEventListener('click', async ()=>{
      dop.disabled = true; dop.textContent = 'Dopasowuję…';
      try{
        const r = await fetch('/api/sprzedaz/dopasuj', {method: 'POST'});
        const j = await r.json().catch(()=>({}));
        SPRZ_WYNIK = !r.ok ? (j.error || ('Błąd ' + r.status))
          : j.przypisane ? `Przypisano ${j.przypisane} z ${j.sprawdzone} nierozpoznanych sprzedaży.`
            + (j.zostalo ? ` Zostało ${j.zostalo} — patrz kolumna „Dlaczego".` : '')
          : `Sprawdzone: ${j.sprawdzone}. Nic się nie zmieniło — dalej brakuje tej samej informacji.`;
      }catch(e){ SPRZ_WYNIK = 'Brak połączenia z serwerem.'; }
      SPRZ = null; render();
    });
  });

  /* `SPRZ` niesie DWA miesiące — bieżący i poprzedni — bo kolumny „7 dni" i „30 dni"
     w tabeli dni sięgają wstecz za pierwszy dzień miesiąca. Wszystko inne na tym ekranie
     dotyczy jednak MIESIĄCA Z PASKA, więc liczymy to z jednego miesiąca. Bez tego filtra
     kafelki pokazywały sumę dwóch miesięcy pod nazwą jednego, a kolumna „zeszło %"
     dzieliła dwumiesięczną sprzedaż przez jednomiesięczny załadunek. */
  const wpisy = Object.keys(SPRZ).map(k=>SPRZ[k])
    .filter(w=>w && w.czas && isoSprzedazy(w.czas).slice(0, 7) === SPRZ_MIES);
  const znane = wpisy.filter(w=>!w.nieznane);
  const nieznane = wpisy.filter(w=>w.nieznane);
  // Do okien kroczących w tabeli potrzebny jest też poprzedni miesiąc.
  const wpisyZOknem = Object.keys(SPRZ).map(k=>SPRZ[k]).filter(w=>w && w.czas && !w.nieznane);

  /* Cena z naszego cennika dla kanału Vending. Kwota od ELDRUT-a i ta cena nie muszą się
     zgadzać — kody rabatowe istnieją, a operator ich nie raportuje. To nie jest usterka,
     więc nie malujemy jej na czerwono; różnica jest informacją, a nie ostrzeżeniem. */
  const cena = (zid)=>{ const s = CALC.set(zid); if(!s) return null;
                        const c = CALC.setCalc(s, 'vending'); return c ? (c.priceGross || 0) : null; };
  const sumaEldrut = znane.reduce((a,w)=>a + (w.kwota || 0), 0);
  const sumaCennik = znane.reduce((a,w)=>a + (cena(w.zestaw) || 0), 0);

  const grupuj = (klucz)=>{
    const g = {};
    znane.forEach(w=>{ const k = klucz(w); if(!k) return;
      const x = g[k] || (g[k] = {n:0, eldrut:0, cennik:0});
      x.n++; x.eldrut += (w.kwota || 0); x.cennik += (cena(w.zestaw) || 0); });
    return g;
  };
  /* Sprzedaże zbiorcze zniekształcają podział na zestawy — nie na tyle, żeby je ukrywać,
     ale na tyle, żeby o tym napisać. Milczenie znaczyłoby, że liczby są dokładniejsze,
     niż są naprawdę. */
  const zbiorcze = wpisy.filter(w=>Array.isArray(w.szafki) && w.szafki.length > 1);
  const wgAutomatu = grupuj(w=>w.maszyna);
  const wgZestawu = grupuj(w=>w.zestaw);

  // Ile szafek załadowaliśmy w tym miesiącu — do zestawienia z tym, ile z nich zeszło.
  const zaladowane = {};
  const ost = new Date(Date.UTC(+SPRZ_MIES.slice(0,4), +SPRZ_MIES.slice(5,7), 0))
    .toISOString().slice(0,10);
  for(let iso = SPRZ_MIES + '-01'; iso <= ost; iso = przesunISO(iso, 1)){
    const z = zaladunekNaDate(iso); if(!z) continue;
    active(DB.machines).forEach(m=>{
      zaladowane[m.id] = (zaladowane[m.id] || 0) + zalSuma(z, m.id).szt; });
  }

  /* Dzień po dniu: suma dla każdego automatu i dla całego dnia. Do okien kroczących
     potrzebujemy też dni sprzed początku miesiąca — stąd drugi, dłuższy szereg. */
  const dzienna = {};
  wpisyZOknem.forEach(w=>{
    const iso = isoSprzedazy(w.czas);
    const d = dzienna[iso] || (dzienna[iso] = {suma: 0, szt: 0, wg: {}});
    d.suma += (w.kwota || 0); d.szt++;
    if(w.maszyna) d.wg[w.maszyna] = (d.wg[w.maszyna] || 0) + (w.kwota || 0);
  });
  const dzienSumy = (iso)=> (dzienna[iso] || {suma: 0}).suma;

  const ostatniDnia = new Date(Date.UTC(+SPRZ_MIES.slice(0,4), +SPRZ_MIES.slice(5,7), 0))
    .toISOString().slice(0,10);
  const koniec = ostatniDnia < todayISO() ? ostatniDnia : todayISO();
  const dni = [];
  for(let iso = SPRZ_MIES + '-01'; iso <= koniec; iso = przesunISO(iso, 1)){
    // Okno kroczące do kolumn „7 dni" i „30 dni" w tabeli: ten dzień i sześć
    // (albo dwadzieścia dziewięć) poprzednich.
    let s7 = 0, s30 = 0;
    for(let k = 0; k < 30; k++){
      const p = przesunISO(iso, -k), dp = dzienna[p];
      const v = dp ? dp.suma : 0;
      s30 += v; if(k < 7) s7 += v;
    }
    const d = dzienna[iso] || {suma: 0, szt: 0, wg: {}};
    dni.push({iso, suma: d.suma, szt: d.szt, wg: d.wg, s7, s30});
  }

  const godziny = Array.from({length:24}, ()=>0);
  wpisy.forEach(w=>{ if(w.czas) godziny[new Date(w.czas * 1000).getHours()]++; });
  const szczyt = Math.max(1, ...godziny);

  const wierszAut = active(DB.machines).map(m=>{
    const x = wgAutomatu[m.id] || {n:0, eldrut:0, cennik:0};
    const zal = zaladowane[m.id] || 0;
    return `<tr><td>${esc(m.name)} <span class="mut small">${esc(m.code||'')}</span></td>
      <td class="r num">${x.n || '<span class="mut">—</span>'}</td>
      <td class="r num mut">${zal || '<span class="mut">—</span>'}</td>
      <td class="r num">${zal ? pct(x.n / zal, 0) : '<span class="mut">—</span>'}</td>
      <td class="r num">${x.cennik ? zl(x.cennik) : '<span class="mut">—</span>'}</td>
      <td class="r num">${x.eldrut ? zl(x.eldrut) : '<span class="mut">—</span>'}</td></tr>`;
  }).join('');

  const wierszZest = Object.keys(wgZestawu).map(zid=>{
    const s = CALC.set(zid), x = wgZestawu[zid];
    return {n: s ? s.name : '⚠ brak zestawu (' + zid + ')', x};
  }).sort((a,b)=>b.x.n - a.x.n).map(({n, x})=>`<tr><td>${esc(n)}</td>
      <td class="r num">${x.n}</td>
      <td class="r num">${zl(x.cennik)}</td>
      <td class="r num">${zl(x.eldrut)}</td></tr>`).join('');

  const pasek = `<div class="row" style="margin-bottom:12px;gap:6px;align-items:center">
    <button class="btn sm" id="sprzPrev" title="Poprzedni miesiąc">‹</button>
    <b style="font-size:15px">${esc(miesLabel(SPRZ_MIES))}</b>
    <button class="btn sm" id="sprzNext" title="Następny miesiąc">›</button>
    <button class="btn sm" id="sprzDzis">Dziś</button></div>`;

  if(SPRZ_BLAD === 'lokalnie') return `<div class="topbar"><h1>Sprzedaż</h1></div>${pasek}
    <div class="card"><div class="empty">Sprzedaż jest zapisywana na serwerze — z pliku
      otwartego z dysku nie ma jej skąd wziąć.</div></div>`;
  if(SPRZ_BLAD) return `<div class="topbar"><h1>Sprzedaż</h1></div>${pasek}
    <div class="card"><div class="empty">${esc(SPRZ_BLAD)}</div></div>`;

  return `<div class="topbar"><h1>Sprzedaż</h1>
    <span class="sub">co automaty naprawdę sprzedały, wprost z ich raportów</span></div>
  ${pasek}
  ${SPRZ_WYNIK ? `<div class="hint" style="margin:-6px 0 12px">${esc(SPRZ_WYNIK)}</div>` : ''}

  <div class="tiles" style="margin-bottom:12px">
    <div class="tile"><div class="lab">Sprzedanych zestawów</div>
      <div class="val num">${znane.length}</div>
      <div class="sub2">${nieznane.length ? nieznane.length + ' nierozpoznanych' : 'wszystkie rozpoznane'}</div></div>
    <div class="tile"><div class="lab">Wg cennika</div><div class="val num">${zl(sumaCennik)}</div>
      <div class="sub2">tyle miało wpłynąć</div></div>
    <div class="tile"><div class="lab">Wg automatów</div><div class="val num">${zl(sumaEldrut)}</div>
      <div class="sub2">tyle zaraportowały</div></div>
    <div class="tile"><div class="lab">Różnica</div>
      <div class="val num">${zl(sumaEldrut - sumaCennik)}</div>
      <div class="sub2">rabaty i zmiany cen</div></div>
  </div>

  <div class="card" style="margin-bottom:12px"><h2 style="margin:0 0 4px">O której schodzi towar</h2>
    <div class="hint" style="margin-bottom:10px">Rozkład godzinowy wszystkich sprzedaży
      w miesiącu. Pomaga ustawić porę wyjazdu.</div>
    <div class="godziny">${godziny.map(g=>`<div style="height:${Math.round(g / szczyt * 100)}%"
      data-tip="${g} sprzedaży"></div>`).join('')}</div>
    <div class="godziny-opis">${godziny.map((g,h)=>`<span>${h % 3 === 0 ? h : ''}</span>`).join('')}</div>
  </div>

  <div class="card" style="margin-bottom:12px">
    <div class="row" style="justify-content:space-between;align-items:baseline;flex-wrap:wrap">
      <h2 style="margin:0 0 4px">Sprzedaż miesięczna</h2>${paskZakresu('mies')}</div>
    <div class="hint" style="margin-bottom:10px">Dla każdego dnia — <b>suma z ostatnich
      30 dni</b>. Miesiąc kroczący, nie kalendarzowy: widać, czy sprzedaż rośnie, czy siada,
      bez czekania do pierwszego. U góry cały lokal, niżej automaty; <b>skale są osobne</b>,
      bo suma jest kilka razy wyższa. Linia zaczyna się tam, gdzie okno jest już pełne.</div>
    <div id="wykMies"></div>
  </div>

  <div class="card" style="margin-bottom:12px">
    <div class="row" style="justify-content:space-between;align-items:baseline;flex-wrap:wrap">
      <h2 style="margin:0 0 4px">Sprzedaż dzienna</h2>${paskZakresu('dzien')}</div>
    <div class="hint" style="margin-bottom:10px">Dla każdego dnia — <b>średnia dzienna
      z ostatnich 7 dni</b>. Tydzień wygładza różnicę między weekendem a wtorkiem, więc
      zostaje sam kierunek. Ten sam podział skal: cały lokal u góry, automaty niżej.</div>
    <div id="wykDzien"></div>
  </div>

  <div class="card" style="margin-bottom:12px">
    <div class="row" style="justify-content:space-between;align-items:baseline;flex-wrap:wrap">
      <h2 style="margin:0 0 4px">Sprzedaż w dniach tygodnia</h2>${paskZakresu('tydz')}</div>
    <div class="hint" style="margin-bottom:10px">Średnia sprzedaż w poszczególne dni tygodnia —
      ile schodzi w sobotę, a ile we wtorek. Dzielimy przez liczbę tych dni, które naprawdę
      znamy, więc automat postawiony w środę nie zaniża sobie poniedziałku.</div>
    <div id="wykTydz"></div>
  </div>

  <div class="card" style="margin-bottom:12px">
    <div class="row" style="justify-content:space-between;align-items:baseline;flex-wrap:wrap">
      <h2 style="margin:0 0 4px">Raport sprzedaży</h2>
      <div class="row" style="gap:8px">${paskZakresu('raport')}
        <button class="btn" data-act="pdfRaport"
          title="Ten sam raport na kartkę">⎙ PDF</button></div></div>
    <div class="hint" style="margin-bottom:10px">Ile sztuk zestawu schodzi <b>w jeden
      poniedziałek, jeden wtorek, jedną sobotę</b> — a nie ile ich zeszło przez cały zakres.
      Każdy taki dzień z zakresu liczy się osobno, a w komórce stoją trzy liczby z tych dni:
      mediana / <b>średnia</b> / maksimum. <b>Sztuki, nie złotówki.</b> Przełącznik obraca tabelę: <b>wg
      automatów</b> rozkłada jeden automat na dni tygodnia, <b>wg dni tygodnia</b> rozkłada
      jeden dzień na automaty. Wydruk niesie wszystkie przekroje po kolei.</div>
    ${raportTygodnia()}
  </div>

  <div class="card" style="margin-bottom:12px"><h2 style="margin:0 0 4px">Sprzedaż dnia po automatach</h2>
    <div class="tw przyklej"><table data-tbl="sprzDni" data-no-sort-now><thead><tr>
      <th>Dzień</th>
      ${active(DB.machines).map(m=>`<th class="r" title="${esc(m.name)}">${esc(m.code || m.name)}</th>`).join('')}
      <th class="r">Razem</th><th class="r">7 dni</th><th class="r">30 dni</th>
    </tr></thead><tbody>${[...dni].reverse().map(d=>`<tr>
      <td>${esc(dataKrotko(d.iso))} <span class="mut small">${esc(dzienNazwa(d.iso))}</span></td>
      ${active(DB.machines).map(m=>`<td class="r num">${
        d.wg[m.id] ? zl(d.wg[m.id]) : '<span class="mut">—</span>'}</td>`).join('')}
      <td class="r num">${d.suma ? zl(d.suma) : '<span class="mut">—</span>'}</td>
      <td class="r num mut">${zl(d.s7)}</td>
      <td class="r num mut">${zl(d.s30)}</td></tr>`).join('') ||
      `<tr><td colspan="${active(DB.machines).length + 4}" class="empty">Ten miesiąc jeszcze
        nie nadszedł.</td></tr>`}</tbody></table></div></div>

  <div class="card" style="margin-bottom:12px"><h2 style="margin:0 0 4px">Automat po automacie</h2>
    <div class="hint" style="margin-bottom:10px">„Załadowano" to suma szafek wysłanych w tym
      miesiącu; „zeszło" mówi, jaka ich część znalazła kupca. Kwota z cennika i kwota
      z automatu różnią się o rabaty, których operator nie raportuje.</div>
    <div class="tw"><table data-tbl="sprzAut"><thead><tr><th>Automat</th>
      <th class="r">Sprzedano</th><th class="r">Załadowano</th><th class="r">Zeszło</th>
      <th class="r">Wg cennika</th><th class="r">Wg automatu</th>
    </tr></thead><tbody>${wierszAut}</tbody></table></div></div>

  <div class="card"><h2 style="margin:0 0 4px">Zestaw po zestawie</h2>
    ${zbiorcze.length ? `<div class="hint" style="margin-bottom:10px">Sprzedaży objętych
      <b>kilkoma szafkami naraz</b>: ${zbiorcze.length} — jeden klient zapłacił raz za kilka
      zestawów. Cała kwota liczy się przy pierwszej szafce z listy, więc pozostałe zestawy
      mają o tyle mniej. Rozdzielenie wymaga cen z załadunku i poczeka, aż menu w automatach
      zgodzi się z aplikacją.</div>` : ''}
    <div class="tw"><table data-tbl="sprzZest"><thead><tr><th>Zestaw</th>
      <th class="r">Sprzedano</th><th class="r">Wg cennika</th><th class="r">Wg automatu</th>
    </tr></thead><tbody>${wierszZest ||
      '<tr><td colspan="4" class="empty">W tym miesiącu nic się nie sprzedało.</td></tr>'}</tbody></table></div></div>

  ${nieznane.length ? `<div class="card" style="margin-top:12px">
    <div class="row" style="justify-content:space-between;align-items:baseline;flex-wrap:wrap">
      <h2 style="margin:0 0 4px">Nierozpoznane</h2>
      <button class="btn sm" id="sprzDopasuj">Dopasuj ponownie</button></div>
    <div class="hint" style="margin-bottom:10px">Te sprzedaże naprawdę się wydarzyły i pieniądze
      wpłynęły — nie umiemy tylko powiedzieć, czego dotyczą. Nie wyrzucamy ich; najczęstsza
      przyczyna to brak numeru seryjnego przy automacie albo szafka bez przypisanego zestawu.</div>
    <div class="tw"><table data-tbl="sprzNiezn"><thead><tr><th>Kiedy</th><th>Numer seryjny</th>
      <th class="r">Szafka</th><th class="r">Kwota</th><th>Dlaczego</th>
    </tr></thead><tbody>${nieznane.sort((a,b)=>b.czas - a.czas).slice(0,50).map(w=>`<tr>
      <td>${esc(new Date(w.czas * 1000).toLocaleString('pl-PL'))}</td>
      <td>${esc(w.serial || '—')}</td>
      <td class="r num">${w.szafka == null ? '—' : w.szafka}</td>
      <td class="r num">${w.kwota == null ? '—' : zl(w.kwota)}</td>
      <td class="mut small">${esc(w.nieznane)}</td></tr>`).join('')}</tbody></table></div></div>` : ''}`;
}

/* ============================================================================
   WIDOK: WYJAZDY — rejestr wyjazdów z kuchni i zatowarowań automatów
   ========================================================================== */
let REJ_MIES = null;

function vRejestr(){
  if(!REJ_MIES) REJ_MIES = todayISO().slice(0,7);
  const maszyny = active(DB.machines);

  after('rejestr',()=>{
    const p = document.getElementById('rejPrev'), n = document.getElementById('rejNext'),
          t = document.getElementById('rejDzis');
    if(p) p.addEventListener('click',()=>{ REJ_MIES = przesunMies(REJ_MIES,-1); render(); });
    if(n) n.addEventListener('click',()=>{ REJ_MIES = przesunMies(REJ_MIES, 1); render(); });
    if(t) t.addEventListener('click',()=>{ REJ_MIES = todayISO().slice(0,7); render(); });
  });

  /* Wszystkie dni miesiąca, od najnowszego — także te bez jednej rejestracji, bo to
     one są tu najciekawsze: dzień, w którym nikt nic nie odhaczył, ma być widać, a nie
     zniknąć z listy. Dni z przyszłości pomijamy — jeszcze nie nadeszły.

     Dzień bez załadunku to co innego niż dzień zapomniany: nic tam nie jechało, więc
     nie ma czego rejestrować i nie liczymy braków. Inaczej sobota bez dostawy udawałaby
     sześć przeoczeń. */
  const dzis = todayISO();
  const ostatni = new Date(Date.UTC(+REJ_MIES.slice(0,4), +REJ_MIES.slice(5,7), 0))
    .toISOString().slice(0,10);
  const dni = [];
  for(let iso = (ostatni < dzis ? ostatni : dzis); iso >= REJ_MIES + '-01';
      iso = przesunISO(iso, -1)){
    if(iso.slice(0,7) === REJ_MIES) dni.push(iso);
  }

  const kom = (iso, rodzaj, mid) => {
    const w = zdarzenie(iso, rodzaj, mid);
    if(!w) return '<span class="mut">—</span>';
    const o = osoba(w.osoba);
    return `<span class="czas" data-tip="${esc(o ? (o.name || o.email || '') : 'usunięta')}"
      >${esc(czasZdarzenia(w, iso))}</span>`;
  };

  /* Kto tego dnia stał na I zmianie. To JEST grafik, więc plakietka należy jej się
     wprost — inaczej niż na pasku rejestracji, gdzie osoba jest zwykłym napisem.
     Rozdział 4 wytycznych: plakietka przysługuje osobie w grafiku, i tylko jej.

     Zmianę bierzemy po NAZWIE, nie po identyfikatorze: ten bywa inny w każdym tygodniu
     wyodrębnionym z szablonu, a „I zmiana" znaczy to samo w każdym z nich. */
  const pierwszaZmiana = (iso) => {
    const z = zmianyDnia(iso).find(x => x.name === 'I zmiana');
    if(!z) return '<span class="mut">—</span>';
    const osoby = zapisy(iso, z.id).osoby;
    if(!osoby.length) return '<span class="mut">—</span>';
    return `<span class="plakietki">${osoby.map(id => skrotHtml(osoba(id))).join('')}</span>`;
  };

  const zJazda = dni.filter(iso => !!zaladunekNaDate(iso));
  const wyjazdow = dni.filter(iso => zdarzenie(iso, 'wyjazd', '')).length;
  const zatowarowan = dni.reduce((a, iso) =>
    a + maszyny.filter(m => zdarzenie(iso, 'automat', m.id)).length, 0);
  const komplety = zJazda.filter(iso =>
    maszyny.length && maszyny.every(m => zdarzenie(iso, 'automat', m.id))).length;

  const wiersze = dni.map(iso => {
    const jedzie = !!zaladunekNaDate(iso);
    const dzien = `<td>${esc(dataKrotko(iso))}
      <span class="mut small">${esc(dzienNazwa(iso))}</span></td>`;
    if(!jedzie) return `<tr class="nieczynny">${dzien}
      <td colspan="${maszyny.length + 3}" class="mut small">bez załadunku</td></tr>`;
    const braki = maszyny.filter(m => !zdarzenie(iso, 'automat', m.id)).length;
    return `<tr>${dzien}
      <td>${pierwszaZmiana(iso)}</td>
      <td class="r num">${kom(iso, 'wyjazd', '')}</td>
      ${maszyny.map(m => `<td class="r num">${kom(iso, 'automat', m.id)}</td>`).join('')}
      <td class="r num">${braki ? `<span class="ulamek">${braki}</span>` : '<span class="mut">—</span>'}</td>
    </tr>`;
  }).join('');

  return `<div class="topbar"><h1>Wyjazdy</h1>
    <span class="sub">kiedy samochód wyjechał i o której automat został zatowarowany</span></div>

  <div class="row" style="margin-bottom:12px;gap:6px;align-items:center">
    <button class="btn sm" id="rejPrev" title="Poprzedni miesiąc">‹</button>
    <b style="font-size:15px">${esc(miesLabel(REJ_MIES))}</b>
    <button class="btn sm" id="rejNext" title="Następny miesiąc">›</button>
    <button class="btn sm" id="rejDzis">Dziś</button>
  </div>

  <div class="tiles" style="margin-bottom:12px">
    <div class="tile"><div class="lab">Wyjazdów</div><div class="val num">${wyjazdow}</div>
      <div class="sub2">dni z zarejestrowanym wyjazdem</div></div>
    <div class="tile"><div class="lab">Zatowarowań</div><div class="val num">${zatowarowan}</div>
      <div class="sub2">${maszyny.length} automatów w trasie</div></div>
    <div class="tile"><div class="lab">Dni z kompletem</div><div class="val num">${komplety}</div>
      <div class="sub2">z ${zJazda.length} dni z załadunkiem</div></div>
  </div>

  <div class="card">
    <div class="hint" style="margin-bottom:10px">Godzina to moment kliknięcia, wzięty z zegara
      serwera. Najedź na nią, żeby zobaczyć, kto zarejestrował. „I zmiana" pokazuje, kto tego
      dnia był w kuchni. Ostatnia kolumna liczy automaty, których nikt nie odhaczył — dni,
      w których nic nie jechało, nie mają czego mieć.</div>
    <div class="tw przyklej"><table data-tbl="rejestr" data-no-sort-now><thead><tr>
      <th>Dzień</th><th>I zmiana</th><th class="r">Wyjazd</th>
      ${maszyny.map(m=>`<th class="r" title="${esc(m.name)}">${esc(m.code || m.name)}</th>`).join('')}
      <th class="r" title="Automaty bez rejestracji">Braki</th>
    </tr></thead><tbody>${wiersze ||
      `<tr><td colspan="${maszyny.length + 4}" class="empty">Ten miesiąc jeszcze
        nie nadszedł.</td></tr>`}</tbody></table></div>
  </div>`;
}

/* ============================================================================
   WIDOK: USTAWIENIA
   ========================================================================== */
function vSet(){
  after('set',()=>{
    const bytes=new Blob([JSON.stringify(DB)]).size;
    const ph=DB.items.filter(i=>i.photo).length+DB.sets.filter(s=>s.photo).length;
    document.getElementById('dataSize').textContent=kb(bytes)+(bytes>4194304?' ⚠':'');
    document.getElementById('photoCount').textContent=ph+' z '+(DB.items.length+DB.sets.length);
    licznikZnakow('sEtykAlerg','sEtykAlergLicz',ETYK_TXT_MAX);
    licznikZnakow('sEtykPrzechow','sEtykPrzechowLicz',ETYK_TXT_MAX);
    const zapiszUstawienia = ()=>{
      DB.settings.targetFc=(parseFloat(val('sTarget'))||30)/100;
      DB.settings.alertFc=(parseFloat(val('sAlert'))||35)/100;
      DB.settings.vats = DB.settings.vats||{};
      CHANNELS.forEach(ch=>{ DB.settings.vats[ch.k]=(parseFloat(val('sVatD_'+ch.k))||ch.vat*100)/100; });
      DB.settings.currency=val('sCur')||'zł';
      DB.settings.roundTo=parseFloat(val('sRound'));
      DB.settings.pdfMinFont=Math.min(20, Math.max(6, parseFloat(val('sPdfFont'))||11));
      DB.settings.pdfMaxCols=Math.min(6, Math.max(1, parseInt(val('sPdfCols'),10)||3));
      DB.settings.oknoZakupow=Math.min(365, Math.max(1, parseInt(val('sOknoZak'),10)||14));
      DB.settings.autoCenaProc=Math.min(100, Math.max(0, parseFloat(val('sAutoCena'))||0));
      // Puste pole znaczy „nic tu nie drukuj", a nie „wróć do domyślnego" — inaczej
      // nie dałoby się zdjąć akapitu z etykiety.
      DB.settings.etykAlerg=val('sEtykAlerg').slice(0, ETYK_TXT_MAX);
      DB.settings.etykPrzechow=val('sEtykPrzechow').slice(0, ETYK_TXT_MAX);
      DB.settings.etykPomin=val('sEtykPomin');
      save(); render();
    };
    ['saveSet','saveSet2'].forEach(id=>{
      const b = document.getElementById(id);
      if(b) b.addEventListener('click', zapiszUstawienia);
    });
    /* Sprzedaż nie mieszka w bazie — leży w osobnych plikach miesięcznych na serwerze.
       Eksport bez niej był kopią zapasową z dziurą dokładnie w miejscu pieniędzy, więc
       dociągamy ją tutaj i doklejamy jako `sprzedaz`. Jeden przycisk, jeden plik: dwa
       eksporty obok siebie znaczyłyby, że za każdym razem trzeba pamiętać, który jest
       ten pełny. */
    document.getElementById('expJson').addEventListener('click', async (e)=>{
      const b = e.currentTarget, napis = b.textContent;
      const plik = Object.assign({}, DB);
      if(SRV.on && SRV.user && !bezCen()){
        b.disabled = true; b.textContent = 'Zbieram sprzedaż…';
        let blad = null;
        try{
          const r = await fetch('/api/sprzedaz/eksport');
          if(r.ok) plik.sprzedaz = (await r.json()).sprzedaz || {};
          else blad = 'Błąd ' + r.status;
        }catch(err){ blad = 'brak połączenia'; }
        b.disabled = false; b.textContent = napis;
        // Plik bez sprzedaży wygląda tak samo jak pełny. Milczenie zrobiłoby z niego
        // kopię zapasową, która zawodzi dopiero wtedy, gdy jest potrzebna.
        if(blad && !confirm('Nie udało się pobrać sprzedaży z serwera (' + blad
            + ').\n\nZapisać plik bez niej?')) return;
      }
      download('sushi-planner-dane.json', JSON.stringify(plik, null, 1), 'application/json');
    });
    /* Osobny przycisk na samą sprzedaż. „Eksport JSON" niesie ją razem z bazą i to
       zostaje — ale plik bazy waży ponad megabajt, a do wysłania komuś albo policzenia
       poza aplikacją potrzebna jest sama sprzedaż. Dwa przyciski, dwie różne rzeczy;
       podpis nad nimi mówi, że ten pierwszy zawiera jedno i drugie. */
    const eSprz = document.getElementById('expSprz');
    if(eSprz) eSprz.addEventListener('click', async ()=>{
      const napis = eSprz.textContent;
      eSprz.disabled = true; eSprz.textContent = 'Zbieram…';
      try{
        const r = await fetch('/api/sprzedaz/eksport');
        if(!r.ok) throw new Error('Błąd ' + r.status);
        download('sushi-planner-sprzedaz.json',
                 JSON.stringify(await r.json(), null, 1), 'application/json');
      }catch(err){ alert('Nie udało się pobrać sprzedaży: ' + (err.message || err)); }
      eSprz.disabled = false; eSprz.textContent = napis;
    });
    document.getElementById('expCsv').addEventListener('click',exportCsv);
    document.getElementById('impJson').addEventListener('change',e=>{
      const f=e.target.files[0]; if(!f)return;
      const r=new FileReader();
      r.onload=()=>{ try{ const d=JSON.parse(r.result);
        if(!d.ingredients||!d.items) throw 0;
        // Sprzedaż z pliku NIE wchodzi do bazy — inaczej wróciłaby tam, skąd ją celowo
        // wyprowadziliśmy, i pojechałaby do każdej przeglądarki przy każdym wczytaniu.
        // Nie jest to strata: sprzedaż odtwarza się ze skrzynki, a klucz po Message-ID
        // pilnuje, żeby ponowny import niczego nie zdublował.
        const miala = !!d.sprzedaz; delete d.sprzedaz;
        DB=d; load2(); save(); render();
        alert('Wczytano dane.' + (miala ? '\n\nSprzedaż z pliku pominięta — wraca z maili '
          + 'przez n8n, a nie z kopii bazy.' : ''));
      }catch(err){ alert('Nieprawidłowy plik.'); } };
      r.readAsText(f);
    });
    // kategorie rolek: zapis po opuszczeniu pola, nie po każdym znaku
    document.querySelectorAll('[data-katn]').forEach(inp=>inp.addEventListener('change',()=>{
      const k = DB.cats.find(x=>x.id===inp.dataset.katn); if(!k) return;
      const v = inp.value.trim();
      if(!v){ alert('Kategoria musi mieć nazwę.'); render(); return; }
      k.name = v; save(); render();
    }));
    document.querySelectorAll('[data-katc]').forEach(inp=>inp.addEventListener('change',()=>{
      const k = DB.cats.find(x=>x.id===inp.dataset.katc); if(!k) return;
      const v = inp.value.trim().toUpperCase();
      if(!v){ alert('Kategoria musi mieć kod — to on stoi przy nazwie tam, gdzie mało miejsca.'); render(); return; }
      if(DB.cats.some(x=>x.id!==k.id && (x.code||'').toUpperCase()===v)){
        alert('Kod „'+v+'” ma już inna kategoria. Kody muszą być unikalne.'); render(); return; }
      k.code = v; save(); render();
    }));
    document.querySelectorAll('[data-katrm]').forEach(b=>b.addEventListener('click',()=>{
      const id = b.dataset.katrm;
      if(DB.items.some(i=>i.catId===id)){ alert('Ta kategoria jest w użyciu.'); return; }
      DB.cats = DB.cats.filter(k=>k.id!==id); save(); render();
    }));
    const kdod = document.getElementById('katAdd');
    if(kdod) kdod.addEventListener('click',()=>{
      DB.cats = DB.cats || [];
      DB.cats.push({id:uid('kat'), name:'Nowa kategoria', code:nowyKodKategorii('Nowa kategoria')});
      save(); render();
    });
    const ssv=document.getElementById('supaSave');
    if(ssv) ssv.addEventListener('click',()=>{ SUPA.configure(val('supaUrl').trim(), val('supaKey').trim()); });
    const ssql=document.getElementById('supaSql');
    if(ssql) ssql.addEventListener('click',()=>{
      openDlg('Schemat bazy Supabase','<p class="small mut">Wklej to w Supabase → SQL Editor → Run. Tworzy tabele, role i zabezpieczenia (RLS).</p>'
        +'<textarea id="sqlBox" rows="22" style="font-family:ui-monospace,monospace;font-size:11px">'+esc(SQL)+'</textarea>',
        [{label:'Kopiuj',cls:'pri',fn:()=>{ document.getElementById('sqlBox').select(); document.execCommand('copy'); return false; }},{label:'Zamknij'}]);
    });
    const sb=document.getElementById('supaLogin'); if(sb) sb.addEventListener('click',()=>SUPA.login(val('supaMail'),val('supaPass')));
    const so=document.getElementById('supaOut'); if(so) so.addEventListener('click',()=>SUPA.logout());
    const sr=document.getElementById('srvReload'); if(sr) sr.addEventListener('click',async()=>{ await SRV.pull(); render(); });
    const sx=document.getElementById('srvOut'); if(sx) sx.addEventListener('click',()=>SRV.logout());
  });

  return `<div class="topbar"><h1>Ustawienia</h1></div>
  <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(340px,1fr))">
    <div class="card"><h2>Progi i podatki</h2><div class="hint">Sterują sugerowaną ceną i kolorami alertów.</div>
      <div class="grid" style="grid-template-columns:1fr 1fr">
        <div><label class="f">Docelowy food cost %</label><input id="sTarget" type="number" step="any" value="${Math.round(DB.settings.targetFc*1000)/10}"></div>
        <div><label class="f">Próg alertu %</label><input id="sAlert" type="number" step="any" value="${Math.round(DB.settings.alertFc*1000)/10}"></div>
        ${CHANNELS.map(ch=>`<div><label class="f">VAT % — ${esc(ch.l)}</label>
          <input id="sVatD_${ch.k}" type="number" step="any" value="${num((DB.settings.vats&&DB.settings.vats[ch.k]!=null?DB.settings.vats[ch.k]:ch.vat)*100,0)}"></div>`).join('')}
        <div><label class="f">Waluta</label><input id="sCur" type="text" value="${esc(DB.settings.currency)}"></div>
        <div style="grid-column:1/-1"><label class="f">Zaokrąglanie sugerowanej ceny</label>
          <select id="sRound">
            <option value="0.9" ${DB.settings.roundTo===0.9?'selected':''}>do końcówki ,90 (np. 28,90)</option>
            <option value="1" ${DB.settings.roundTo===1?'selected':''}>do pełnych złotych</option>
            <option value="0.5" ${DB.settings.roundTo===0.5?'selected':''}>do 50 gr</option>
            <option value="0" ${DB.settings.roundTo===0?'selected':''}>bez zaokrąglania</option>
          </select></div>
      </div>
      <h3 style="margin:16px 0 6px">Wydruki PDF</h3>
      <div class="hint" style="margin-bottom:8px">Aplikacja szuka największego pisma, przy którym
        wydruk mieści się na jednej stronie. Poniżej minimum nie zejdzie — wtedy woli dołożyć stronę.</div>
      <div class="grid" style="grid-template-columns:1fr 1fr">
        <div><label class="f">Minimalna czcionka (px)</label>
          <input id="sPdfFont" type="number" step="0.5" min="6" max="20"
            value="${num(DB.settings.pdfMinFont, DB.settings.pdfMinFont%1?1:0)}"></div>
        <div><label class="f">Maksymalnie kolumn</label>
          <input id="sPdfCols" type="number" step="1" min="1" max="6"
            value="${DB.settings.pdfMaxCols}"></div>
      </div>
      <h3 style="margin:16px 0 6px">Ceny z faktur</h3>
      <div class="hint" style="margin-bottom:8px">Z ilu dni wstecz liczyć cenę składnika, gdy
        aplikacja proponuje ją na podstawie zakupów. Liczy średnią <b>ważoną ilością</b> —
        dostawa 20 kg waży w niej dziesięć razy tyle, co dostawa 2 kg. Krótsze okno szybciej
        łapie podwyżkę, dłuższe mniej się chwieje przy jednej nietypowej fakturze.<br>
        Drugi próg mówi, jak dużą zmianę aplikacja przyjmuje bez pytania. Cena towaru
        faluje między dostawami o kilka procent bez żadnego powodu po stronie dostawcy,
        a klikanie „Zatwierdź" przy każdym takim drgnieniu kończy się tym, że przestaje
        się czytać także te prawdziwe. <b>Nowej ceny automat nie wpisze</b> — bez ceny
        w bazie nie ma od czego liczyć procentu.</div>
      <div class="grid" style="grid-template-columns:1fr 1fr">
        <div><label class="f">Okno cen z zakupów (dni)</label>
          <input id="sOknoZak" type="number" step="1" min="1" max="365"
            value="${DB.settings.oknoZakupow}"></div>
        <div><label class="f">Automat przyjmuje zmianę do (%)</label>
          <input id="sAutoCena" type="number" step="0.5" min="0" max="100"
            value="${zakAuto()}">
          <div class="hint" style="margin-top:4px">0 wyłącza automat — wtedy każda cena
            czeka na kliknięcie.</div></div>
      </div>
      <div style="margin-top:12px"><button class="btn pri" id="saveSet">Zapisz ustawienia</button></div></div>

    <div class="card"><h2>Etykiety na opakowania</h2>
      <div class="hint">Naklejka 90 × 130 mm z rolki — <b>tego formatu ani marginesu
        aplikacja nie zmienia</b>. Skład bierze się z zestawu, więc etykieta nie może
        się rozminąć z recepturą. Drukujesz je w <b>Zestawach</b>: „⎙ Etykiety" robi
        komplet — <b>osobny plik PDF na każdy zestaw</b>, spakowane w jeden ZIP;
        przycisk w panelu zestawu robi pojedynczy plik.</div>
      <div style="margin-top:10px">
        <label class="f">Akapit o alergenach</label>
        <textarea id="sEtykAlerg" rows="4" maxlength="${ETYK_TXT_MAX}">${esc(DB.settings.etykAlerg ?? ETYK.alergDom)}</textarea>
        <div class="hint" id="sEtykAlergLicz" style="margin-top:4px"></div>
      </div>
      <div style="margin-top:10px">
        <label class="f">Akapit o przechowywaniu</label>
        <textarea id="sEtykPrzechow" rows="3" maxlength="${ETYK_TXT_MAX}">${esc(DB.settings.etykPrzechow ?? ETYK.przechowDom)}</textarea>
        <div class="hint" id="sEtykPrzechowLicz" style="margin-top:4px"></div>
      </div>
      <div class="hint" style="margin-top:6px">Tekst między <b>**gwiazdkami**</b> wyjdzie
        pogrubiony. Puste pole znaczy, że tego akapitu na etykiecie nie będzie.</div>
      <div style="margin-top:12px">
        <label class="f">Pomijane na etykiecie</label>
        <input id="sEtykPomin" type="text" value="${esc(DB.settings.etykPomin ?? ETYK.pominDom)}">
        <div class="hint" style="margin-top:4px">Po przecinku — <b>kategorie albo nazwy</b>
          składników (ogonki nie mają znaczenia). Ryż i nori są w każdej rolce, a tacka
          i pałeczki nie są jedzeniem — jedno i drugie zabierałoby miejsce na liście, którą
          ktoś ma naprawdę przeczytać.<br>
          Skład to <b>pełny wykaz składników całego zestawu</b>, malejąco według masy,
          każdy raz — półprodukty rozłożone na to, z czego są zrobione, więc stoi tam
          „Ryż", a nie „Ryż gotowany". Domyślnie pomijamy wyłącznie opakowania, bo tego
          się nie je.</div>
      </div>
      <div style="margin-top:12px"><button class="btn pri" id="saveSet2">Zapisz ustawienia</button></div></div>

    <div class="card"><h2>Kategorie rolek</h2>
      <div class="hint">Kategoria to pierwszy człon nazwy — Hosomaki, Uramaki, Futomaki.
        Kod pokazuje się tam, gdzie na pełną nazwę nie ma miejsca.</div>
      <div style="margin-top:10px">
        <div class="compline" style="grid-template-columns:1fr 90px 84px 32px">
          <span class="mut small">Nazwa</span><span class="mut small">Kod</span>
          <span class="mut small">Użycie</span><span></span></div>
        ${(DB.cats||[]).map(k=>{
          const uzyc = DB.items.filter(x=>x.catId===k.id).length;
          return `<div class="compline" style="grid-template-columns:1fr 90px 84px 32px">
            <input type="text" value="${esc(k.name)}" data-katn="${k.id}">
            <input type="text" value="${esc(k.code||'')}" data-katc="${k.id}" maxlength="4"
              style="text-transform:uppercase">
            <span class="mut small">${uzyc} ${uzyc===1?'rolka':'rolek'}</span>
            <button type="button" class="btn sm danger" data-katrm="${k.id}"
              ${uzyc?'disabled title="Kategoria jest w użyciu"':''}>✕</button></div>`;
        }).join('') || '<div class="empty" style="padding:12px">Brak kategorii</div>'}
      </div>
      <div style="margin-top:10px"><button class="btn sm" id="katAdd">+ Kategoria</button></div></div>

    <div class="card"><h2>Dane</h2><div class="hint">Kopia zapasowa i przenoszenie między urządzeniami.${
      SRV.on && !bezCen() ? ' Eksport JSON bierze <b>także sprzedaż z automatów</b>, wszystkie miesiące.' : ''}</div>
      <div class="row" style="margin-bottom:10px">
        <button class="btn" id="expJson">↓ Eksport JSON</button>
        ${SRV.on && !bezCen() ? '<button class="btn" id="expSprz" title="Sama sprzedaż, '
          + 'wszystkie miesiące, razem z listą automatów i układem szafek. Mały plik — '
          + 'do wysłania albo policzenia poza aplikacją.">↓ Eksport sprzedaży</button>' : ''}
        <button class="btn" id="expCsv">↓ Eksport CSV (Excel)</button>
        <!-- Pole wyboru pliku rysuje przeglądarka i wygląda inaczej w każdej z nich:
             szary klawisz systemowy obok „Nie wybrano pliku". Chowamy je, a klikalną
             częścią zostaje etykieta, czyli nasz zwykły przycisk. -->
        <label class="btn" for="impJson">↑ Import JSON</label>
        <input type="file" id="impJson" accept="application/json,.json" class="plikukryty"></div>
      <div class="kv" style="margin-top:12px"><span>Rozmiar danych</span><b id="dataSize">—</b></div>
      <div class="kv"><span>Zdjęcia</span><b id="photoCount">—</b></div>
      <div class="small mut" style="margin-top:10px">Dane w trybie lokalnym są zapisywane w tej przeglądarce${STORAGE_OK?'':' <b>— niedostępne w tej karcie, koniecznie eksportuj plik</b>'}. Do pracy zespołowej podłącz Supabase.</div></div>

    ${SRV.on?`<div class="card"><h2>Serwer</h2>
      <div class="hint">Aplikacja działa na Twoim serwerze — dane są wspólne dla wszystkich kont.</div>
      <div class="kv"><span>Zalogowany</span><b>${esc(SRV.user?SRV.user.email:'—')}</b></div>
      <div class="kv"><span>Rola</span><b>${SRV.user?({owner:'właściciel',chef:'kucharz',viewer:'tylko podgląd'}[SRV.user.role]||SRV.user.role):'—'}</b></div>
      <div class="kv"><span>Wersja danych</span><b>#${SRV.rev}</b></div>
      <div class="kv"><span>Ostatni zapis</span><b>${SRV.updatedAt?esc(new Date(SRV.updatedAt*1000).toLocaleString('pl-PL')):'—'}</b></div>
      <div class="kv"><span>Zapisał</span><b>${esc(SRV.updatedBy||'—')}</b></div>
      <div class="kv"><span>Wersja aplikacji</span><b>${esc(SRV.version||'—')}${SRV.commit?' <span class="mut">'+esc(SRV.commit)+'</span>':''}</b></div>
      <div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn" id="srvReload" title="Pobiera z serwera najnowszą wersję danych.
Przydaje się, gdy ktoś inny właśnie coś zmienił, a Ty masz otwartą starszą wersję.">Pobierz dane z serwera</button></div>
      <div class="small mut" style="margin-top:12px">Konta zakładasz w <b>Narzędzia → Użytkownicy</b>.<br>
        Aktualizacje instalują się same raz na dobę; ręcznie: <code>sushi-update</code></div>
    </div>`:`<div class="card"><h2>Supabase — praca zespołowa</h2>
      <div class="hint">Wspólna baza w chmurze, logowanie i role. Konto darmowe wystarczy.</div>
      <ol class="small" style="color:var(--ink-2);padding-left:18px;margin:0 0 12px">
        <li>Załóż projekt na <a class="zew" href="https://supabase.com" target="_blank" rel="noopener">supabase.com</a></li>
        <li>Kliknij „Pokaż schemat SQL” i wklej go w SQL Editor</li>
        <li>Skopiuj z Settings → API: <b>Project URL</b> i klucz <b>anon public</b></li>
        <li>Wklej je poniżej i zapisz</li>
      </ol>
      <button class="btn sm" id="supaSql" style="margin-bottom:12px">Pokaż schemat SQL</button>
      <label class="f">Project URL</label><input id="supaUrl" type="text" value="${esc(SUPA.url||'')}" placeholder="https://xxxx.supabase.co">
      <label class="f" style="margin-top:8px">Anon key</label><input id="supaKey" type="text" value="${esc(SUPA.key||'')}" placeholder="eyJhbGciOi…">
      <div style="margin-top:10px"><button class="btn pri" id="supaSave">Podłącz</button></div>
      ${SUPA.ready?`<div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--grid)">
        ${SUPA.user?`<div class="row"><span class="tag good">zalogowany: ${esc(SUPA.user.email)}</span>
             <button class="btn sm" id="supaOut">Wyloguj</button></div>`
          :`<label class="f">E-mail</label><input id="supaMail" type="email">
            <label class="f" style="margin-top:8px">Hasło</label><input id="supaPass" type="password">
            <div style="margin-top:10px"><button class="btn pri" id="supaLogin">Zaloguj / załóż konto</button></div>`}
      </div>`:''}
    </div>`}

  </div>`;
}

/** dane z serwera, importu i Supabase — ta sama migracja co przy starcie lokalnym */
function load2(){ migrateAll(); }

/* ============================================================================
   PODMIANA SKŁADNIKA W CAŁYM MENU
   ========================================================================== */
function replaceDialog(fromId){
  const from = CALC.ing(fromId) || CALC.prep(fromId);
  if(!from) return;
  const occ = occurrences(fromId);
  const kandydaci = [
    ...DB.preps.filter(x=>x.id!==fromId && !x.archived).map(x=>({id:x.id,name:'◍ '+x.name,unit:x.yieldUnit})),
    ...DB.ingredients.filter(x=>x.id!==fromId && !x.archived).map(x=>({id:x.id,name:x.name,unit:x.unit})),
  ];

  if(!occ.length){
    alert('„'+from.name+'” nie występuje w żadnej recepturze ani zestawie — nie ma czego podmieniać.');
    return;
  }

  const przelicz = () => {
    const toId = val('rpTo'), f = parseFloat(val('rpF'));
    const cel = CALC.compInfo(toId);
    const info = document.getElementById('rpInfo');
    if(!toId || !isFinite(f) || f<=0){ info.innerHTML='<div class="empty">Podaj poprawny przelicznik.</div>'; return; }

    // policz koszty przed i po, bez zapisywania
    const przed = DB.items.map(i=>({id:i.id, name:itName(i), v:CALC.itemCalc(i).net}));
    const kopia = clone({items:DB.items, preps:DB.preps, sets:DB.sets});
    const wynik = replaceEverywhere(fromId, toId, f);
    const zepsute = prepsBroken();
    const po = DB.items.map(i=>({id:i.id, name:itName(i), v:CALC.itemCalc(i).net}));
    DB.items = kopia.items; DB.preps = kopia.preps; DB.sets = kopia.sets;   // cofnięcie
    const n = wynik.zmienione;

    const zmiany = przed.map((x,k)=>({name:x.name, przed:x.v, po:po[k].v}))
                        .filter(x=>Math.abs(x.po-x.przed) > 0.0001)
                        .sort((a,b)=>Math.abs(b.po-b.przed)-Math.abs(a.po-a.przed));
    const sumPrzed = przed.reduce((s,x)=>s+x.v,0), sumPo = po.reduce((s,x)=>s+x.v,0);

    info.innerHTML = `
      ${zepsute?`<div class="alert crit"><div class="ic">!</div><div class="txt">
        Ta podmiana zapętliłaby półprodukt — nie da się jej wykonać.</div></div>`:''}
      <div class="kv"><span>Do podmiany</span><b>${n} wystąpień</b></div>
      ${wynik.pominiete?`<div class="kv"><span>Pominięte (wnętrze półproduktu)</span>
        <b class="mut">${wynik.pominiete}</b></div>`:''}
      <div class="kv"><span>Nowa cena jednostkowa</span>
        <b>${cel.unitCost!=null?num(cel.unitCost,4)+' '+DB.settings.currency+'/'+esc(cel.unit||''):'brak ceny'}</b></div>
      <div class="kv"><span>Rolek ze zmienionym kosztem</span><b>${zmiany.length}</b></div>
      <div class="kv"><span>Suma kosztów rolek</span>
        <b>${zl(sumPrzed)} → <span style="color:${sumPo>sumPrzed?'var(--crit-ink)':'var(--good-ink)'}">${zl(sumPo)}</span></b></div>
      ${zmiany.length?`<h3 style="margin:14px 0 6px">Najbardziej dotknięte</h3>
        <div class="tw" style="border:0"><table><thead><tr><th>Rolka</th><th class="r">Przed</th><th class="r">Po</th><th class="r">Δ</th></tr></thead>
        <tbody>${zmiany.slice(0,12).map(x=>`<tr><td>${esc(x.name)}</td>
          <td class="r num">${zl(x.przed)}</td><td class="r num">${zl(x.po)}</td>
          <td class="r num" style="color:${x.po>x.przed?'var(--crit-ink)':'var(--good-ink)'}">${(x.po-x.przed>=0?'+':'')}${zl(x.po-x.przed)}</td></tr>`).join('')}
        </tbody></table></div>`:''}`;
  };

  openDlg('Zamień „'+from.name+'” w całym menu', `
    <div class="banner">Znaleziono <b>${occ.length}</b> wystąpień:
      ${esc([...new Set(occ.map(o=>o.where))].join(', '))}.
      Podmiana dotknie wszystkich naraz — poniżej widzisz, co się stanie z kosztami.</div>
    <div class="grid" style="grid-template-columns:2fr 1fr">
      <div><label class="f">Zamień na</label>
        ${combo('rpTo','Szukaj zamiennika…')}</div>
      <div><label class="f">Przelicznik ilości</label>
        <input id="rpF" type="number" step="any" value="1">
        <div class="small mut" style="margin-top:5px">1 = bez zmian, 0,5 = połowa</div></div>
    </div>
    <div style="margin-top:12px"><label class="row" style="gap:6px;cursor:pointer">
      <input type="checkbox" id="rpArch" checked style="width:auto">
      <span class="small">Po podmianie przenieś „${esc(from.name)}” do archiwum</span></label></div>
    <div id="rpInfo" style="margin-top:14px"></div>`,
    [{label:'Anuluj'},
     {label:'Zamień', cls:'pri', fn:()=>{
       const toId=val('rpTo'), f=parseFloat(val('rpF'));
       if(!toId || !isFinite(f) || f<=0){ alert('Podaj poprawny przelicznik.'); return false; }
       const cel = CALC.compInfo(toId);
       const doZmiany = occ.length - skipsForCycle(fromId, toId).length;
       if(!confirm('Zamienić '+doZmiany+' wystąpień „'+from.name+'” na „'+cel.name+'”'
           +(f!==1?(' z przelicznikiem ×'+num(f,3)):'')+'?')) return false;
       const kopia = clone({items:DB.items, preps:DB.preps, sets:DB.sets});
       replaceEverywhere(fromId, toId, f);
       if(prepsBroken()){
         DB.items=kopia.items; DB.preps=kopia.preps; DB.sets=kopia.sets;
         alert('Przerwano: ta podmiana zapętliłaby półprodukt. Nic nie zostało zmienione.');
         return false;
       }
       if(document.getElementById('rpArch').checked) from.archived = todayISO();
       save(); render();
     }}],
    ()=>{
      fillCombo('rpTo', kandydaci.map(k=>({v:k.id, l:k.name})), null, przelicz);
      document.getElementById('rpF').addEventListener('input',przelicz);
      przelicz();
    });
}

/* ============================================================================
   AKTUALIZACJA Z POZIOMU APLIKACJI (tylko właściciel)
   ========================================================================== */
function updBox(html){ const el=document.getElementById('updBody'); if(el) el.innerHTML=html; }
function updLog(txt){
  return `<pre style="background:var(--plane);border:1px solid var(--border);border-radius:7px;
    padding:10px 12px;font-size:12px;line-height:1.5;white-space:pre-wrap;word-break:break-word;
    max-height:260px;overflow:auto;margin:0">${esc(txt||'(brak wyjścia)')}</pre>`;
}

async function updateDialog(){
  openDlg('Aktualizacja aplikacji',
    `<div id="updBody"><div class="empty">Sprawdzam, czy jest nowa wersja…</div></div>`,
    [{label:'Zamknij'}]);
  let j;
  try{
    const r = await fetch('/api/update/check');
    if(r.status===403){ updBox('<div class="alert crit"><div class="ic">!</div><div class="txt">Tylko właściciel może aktualizować.</div></div>'); return; }
    j = await r.json();
  }catch(e){
    updBox('<div class="alert crit"><div class="ic">!</div><div class="txt">Brak połączenia z serwerem.</div></div>');
    return;
  }

  const head = `<div class="kv"><span>Zainstalowana wersja</span>
      <b>${esc(j.version||'—')}${j.commit?' <span class="mut">'+esc(j.commit)+'</span>':''}</b></div>`;

  if(j.busy){
    updBox(head + '<div class="alert warn" style="margin-top:10px"><div class="ic">?</div>'
      + '<div class="txt">Aktualizacja właśnie trwa. Poczekaj chwilę i sprawdź ponownie.</div></div>');
    return;
  }
  if(j.ok === false){
    updBox(head
      + '<div class="alert crit" style="margin-top:10px"><div class="ic">!</div>'
      + '<div class="txt">Nie udało się sprawdzić aktualizacji. Szczegóły poniżej — '
      + 'najczęstsza przyczyna to brak połączenia z GitHubem albo niedokończona instalacja.</div></div>'
      + '<h3 style="margin:14px 0 6px">Odpowiedź serwera</h3>' + updLog(j.output));
    return;
  }
  if(!j.available){
    updBox(head
      + '<div class="alert info" style="margin-top:10px"><div class="ic">i</div>'
      + '<div class="txt">Masz najnowszą wersję — nie ma czego instalować.</div></div>'
      + '<h3 style="margin:14px 0 6px">Odpowiedź serwera</h3>' + updLog(j.output));
    return;
  }

  updBox(head
    + '<div class="alert warn" style="margin-top:10px"><div class="ic">?</div>'
    + '<div class="txt"><b>Jest nowa wersja.</b> Instalacja potrwa kilkanaście sekund i na ten czas '
    + 'aplikacja będzie niedostępna. Dane, ceny i receptury zostają nietknięte, a gdyby nowa wersja '
    + 'nie wstała, serwer sam wróci do obecnej.</div></div>'
    + '<h3 style="margin:14px 0 6px">Co się zmieni</h3>' + updLog(j.output)
    + '<div style="margin-top:14px"><button class="btn pri" id="updGo">Zainstaluj teraz</button></div>');

  document.getElementById('updGo').addEventListener('click', runUpdate);
}

async function runUpdate(){
  updBox('<div class="empty">Uruchamiam aktualizację…</div>');
  try{
    const r = await fetch('/api/update/run', {method:'POST'});
    if(!r.ok){
      const e = await r.json().catch(()=>({}));
      updBox('<div class="alert crit"><div class="ic">!</div><div class="txt">'
        + esc(e.error||('Błąd '+r.status)) + '</div></div>');
      return;
    }
  }catch(e){
    updBox('<div class="alert crit"><div class="ic">!</div><div class="txt">Nie udało się uruchomić aktualizacji.</div></div>');
    return;
  }

  // serwer w trakcie restartu przestaje odpowiadać — to normalne, czekamy
  const start = Date.now();
  let lastLog = '';
  while(Date.now() - start < 180000){
    await new Promise(r=>setTimeout(r, 2000));
    let st = null;
    try{ const r = await fetch('/api/update/status'); if(r.ok) st = await r.json(); }
    catch(e){ /* restart w toku */ }

    const czekam = Math.round((Date.now()-start)/1000);
    if(!st){
      updBox('<div class="empty">Serwer się restartuje… (' + czekam + ' s)</div>'
             + (lastLog ? '<h3 style="margin:14px 0 6px">Log</h3>' + updLog(lastLog) : ''));
      continue;
    }
    lastLog = st.log || lastLog;
    if(st.busy){
      updBox('<div class="empty">Instaluję… (' + czekam + ' s)</div>'
             + '<h3 style="margin:14px 0 6px">Log</h3>' + updLog(lastLog));
      continue;
    }
    // skończone
    const zmiana = /Zaktualizowano do/.test(lastLog);
    const wycofane = /wycofana/.test(lastLog);
    updBox(`<div class="alert ${wycofane?'crit':'info'}"><div class="ic">${wycofane?'!':'i'}</div>
        <div class="txt">${wycofane
          ? 'Nowa wersja nie wstała i została <b>wycofana</b>. Działa poprzednia, dane nietknięte.'
          : zmiana ? 'Gotowe. Zainstalowana wersja: <b>'+esc(st.version||'?')+'</b>.'
                   : 'Zakończono.'}</div></div>
        <h3 style="margin:14px 0 6px">Log</h3>${updLog(lastLog)}
        <div style="margin-top:14px"><button class="btn pri" id="updReload">Odśwież aplikację</button></div>`);
    const rb = document.getElementById('updReload');
    if(rb) rb.addEventListener('click', ()=>location.reload());
    return;
  }
  updBox('<div class="alert warn"><div class="ic">?</div><div class="txt">Aktualizacja trwa dłużej niż zwykle. '
    + 'Odśwież stronę za chwilę i sprawdź wersję w Ustawieniach.</div></div>');
}

/* ============================================================================
   EKSPORT
   ========================================================================== */
function download(name, content, type){
  const b=new Blob([content],{type:type||'text/plain;charset=utf-8'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(b); a.download=name;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
function csvCell(v){ const s=String(v==null?'':v).replace(/"/g,'""'); return /[";\n]/.test(s)?'"'+s+'"':s; }
function exportCsv(){
  const L=[];
  L.push(['SKŁADNIKI'].join(';'));
  L.push(['Nazwa','Kategoria','j.m.','Ilość w op.','Cena opak.','Cena/j.m.'].join(';'));
  DB.ingredients.forEach(g=>L.push([g.name,g.cat,g.unit,g.packQty,g.packPrice,CALC.ingUnitCost(g.id)].map(csvCell).join(';')));
  L.push('');L.push(['ROLKI'].join(';'));
  L.push(['Nazwa','Kawałki','Koszt netto','Koszt/kawałek','Cena brutto','Food cost %','Marża netto','Sugerowana cena'].join(';'));
  DB.items.forEach(i=>{const c=CALC.itemCalc(i);
    L.push([itName(i),i.pieces,c.net,c.perPiece,
      ...CHANNELS.flatMap(ch=>{const x=CALC.itemCalc(i,ch.k);
        return [x.priceGross,x.fc!=null?x.fc*100:'',x.margin,x.suggested];})].map(csvCell).join(';'));});
  L.push('');L.push(['RECEPTURY'].join(';'));
  L.push(['Rolka','Składnik','Ilość','j.m.','Cena/j.m.','Koszt'].join(';'));
  DB.items.forEach(i=>{const c=CALC.itemCalc(i);
    c.rows.forEach(r=>L.push([itName(i),r.name,r.qty,r.unit,r.unitCost,r.cost].map(csvCell).join(';')));});
  L.push('');L.push(['ZESTAWY'].join(';'));
  L.push(['Zestaw','Kawałki','Koszt','Cena brutto','Food cost %','Marża netto','Rabat %','Sugerowana cena'].join(';'));
  DB.sets.forEach(s=>{const c=CALC.setCalc(s);
    L.push([s.name,c.pieces,c.net,
      ...CHANNELS.flatMap(ch=>{const x=CALC.setCalc(s,ch.k);
        return [x.priceGross,x.fc!=null?x.fc*100:'',x.margin,x.discount!=null?x.discount*100:'',x.suggested];})].map(csvCell).join(';'));});
  download('sushi-planner-'+todayISO()+'.csv','﻿'+L.join('\n'),'text/csv;charset=utf-8');
}

/* ============================================================================
   DIALOG
   ========================================================================== */
const DLG=document.getElementById('dlg');
let DLG_PODMIANA = false;
DLG.addEventListener('close', ()=>{ if(!DLG_PODMIANA) warstwaZamknieta(); });
function val(id){ const e=document.getElementById(id); return e?e.value:''; }

/* Ile znaków mieści opis zestawu. Limit jest po to, żeby opis został opisem: pole bez
   granicy zamienia się w notatnik, a wtedy panel przestaje się mieścić na ekranie. */
const OPIS_MAX = 1000;
/** Akapity z etykiety. 600 znaków to z zapasem tyle, ile mieści się na dole
    naklejki 90 × 130 mm przy czytelnym piśmie — dłuższy tekst nie zostałby
    przycięty, tylko zjadłby miejsce liście składników. */
const ETYK_TXT_MAX = 600;

/** Licznik znaków pod polem tekstowym.

    Sygnałem uwagi robi się dopiero przy samym limicie — licznik krzyczący od pierwszej
    litery uczy się ignorować, a wtedy nie mówi nic także wtedy, kiedy naprawdę trzeba.
    Do tego `maxlength` i tak nie pozwoli napisać więcej, więc to informacja, nie alarm. */
function licznikZnakow(poleId, licznikId, limit){
  const pole = document.getElementById(poleId), licz = document.getElementById(licznikId);
  if(!pole || !licz) return;
  const odswiez = ()=>{
    const n = pole.value.length;
    licz.textContent = n + ' / ' + limit + (n >= limit ? ' — to już maksimum' : '');
    licz.classList.toggle('uwaga-txt', n >= limit);
  };
  pole.addEventListener('input', odswiez);
  odswiez();
}
function numOrNull(id){ const v=val(id); return v===''||v==null?null:parseFloat(v); }
function openDlg(title, body, buttons, onOpen){
  document.getElementById('dlgTitle').textContent=title;
  const cialo=document.getElementById('dlgBody');
  cialo.innerHTML=body;
  /* Okno stoi w <form method="dialog">, więc <button> BEZ atrybutu `type` jest
     przyciskiem wysyłającym formularz — a to zamyka okno. Przyciski stopki dostają
     `type='button'` niżej, ale treść przychodzi tu gotowym HTML-em i o tej pułapce
     trzeba było pamiętać przy każdym oknie z osobna. Nie trzeba: robimy to raz, tutaj.
     Przycisk, który MA zamykać, może nadal zadeklarować type="submit" wprost. */
  cialo.querySelectorAll('button:not([type])').forEach(b=>b.type='button');
  const f=document.getElementById('dlgFoot'); f.innerHTML='';
  (buttons||[]).forEach((b,i)=>{
    const el=document.createElement('button');
    el.className='btn '+(b.cls||''); el.textContent=b.label; el.type='button';
    el.addEventListener('click',()=>{ if(b.fn){ if(b.fn()===false) return; } DLG.close(); });
    f.appendChild(el);
  });
  const bylo = DLG.open;
  // Okno otwarte z wnętrza innego okna zajmuje jego miejsce, więc nie zdejmujemy
  // wpisu warstwy ani nie dokładamy drugiego — inaczej „wstecz" trzeba by nacisnąć
  // dwa razy, żeby wyjść z jednego okna.
  if(bylo){ DLG_PODMIANA = true; DLG.close(); DLG_PODMIANA = false; }
  DLG.showModal();
  if(!bylo) warstwaOtwarta('dlg');
  if(onOpen) onOpen();
}

/* ============================================================================
   SUPABASE (opcjonalnie)
   ========================================================================== */
const SQL = `-- Sushi Planner — schemat bazy dla Supabase
create table if not exists workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null default 'Mój lokal',
  data jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists members (
  workspace_id uuid references workspaces(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  role text not null default 'staff' check (role in ('owner','admin','staff','viewer')),
  primary key (workspace_id, user_id)
);

alter table workspaces enable row level security;
alter table members  enable row level security;

-- każdy widzi tylko workspace, do którego należy
create policy "read own workspace" on workspaces for select
  using (exists (select 1 from members m where m.workspace_id = workspaces.id and m.user_id = auth.uid()));

-- zapisywać może właściciel i kucharz (viewer tylko czyta)
create policy "write own workspace" on workspaces for update
  using (exists (select 1 from members m where m.workspace_id = workspaces.id
                 and m.user_id = auth.uid() and m.role in ('owner','admin')));

create policy "read members" on members for select using (user_id = auth.uid());

-- pierwszy zalogowany użytkownik zakłada workspace i zostaje właścicielem
create or replace function bootstrap_workspace() returns uuid
language plpgsql security definer as $$
declare wid uuid;
begin
  select workspace_id into wid from members where user_id = auth.uid() limit 1;
  if wid is null then
    insert into workspaces(name) values ('Mój lokal') returning id into wid;
    insert into members(workspace_id, user_id, role) values (wid, auth.uid(), 'owner');
  end if;
  return wid;
end $$;`;

const SUPA = {
  url:'', key:'', client:null, ready:false, on:false, user:null, wid:null, timer:null,
  async configure(url,key){
    this.url=url; this.key=key;
    if(!url||!key){ this.ready=false; this.on=false; badge(); render(); return; }
    try{
      const m = await import('https://esm.sh/@supabase/supabase-js@2');
      this.client = m.createClient(url,key);
      this.ready = true;
      const {data} = await this.client.auth.getSession();
      this.user = data.session ? data.session.user : null;
      if(this.user) await this.afterLogin();
    }catch(e){
      alert('Nie udało się połączyć z Supabase: '+e.message+'\n\nSprawdź adres, klucz i połączenie z internetem.');
      this.ready=false;
    }
    badge(); render();
  },
  async login(email,pass){
    if(!this.client) return;
    let r = await this.client.auth.signInWithPassword({email,password:pass});
    if(r.error){
      r = await this.client.auth.signUp({email,password:pass});
      if(r.error){ alert('Błąd logowania: '+r.error.message); return; }
      if(!r.data.session){ alert('Konto założone. Potwierdź adres e-mail i zaloguj się ponownie.'); return; }
    }
    this.user = r.data.user || (r.data.session&&r.data.session.user);
    await this.afterLogin(); badge(); render();
  },
  async logout(){ if(this.client) await this.client.auth.signOut(); this.user=null; this.on=false; badge(); render(); },
  async afterLogin(){
    const {data,error} = await this.client.rpc('bootstrap_workspace');
    if(error){ alert('Brak schematu bazy? Uruchom SQL z przycisku „Pokaż schemat SQL”.\n\n'+error.message); return; }
    this.wid = data;
    const w = await this.client.from('workspaces').select('data,updated_at').eq('id',this.wid).single();
    if(w.data && w.data.data && w.data.data.ingredients){
      if(confirm('W chmurze są zapisane dane. Wczytać je (Tak) czy nadpisać danymi z tej przeglądarki (Anuluj)?')){
        DB = w.data.data; load2(); safeSet(JSON.stringify(DB));
      } else { this.on=true; await this.push(); }
    }
    this.on = true; badge();
  },
  async push(){
    if(!this.on||!this.client||!this.wid) return;
    clearTimeout(this.timer);
    this.timer=setTimeout(async()=>{
      const {error}=await this.client.from('workspaces').update({data:DB,updated_at:new Date().toISOString()}).eq('id',this.wid);
      badge(error?'błąd zapisu':null);
    },700);
  }
};
function badge(msg){
  const b=document.getElementById('syncBadge');
  if(msg){ b.className = msg==='zapisywanie…'?'tag':'tag crit'; b.textContent=msg; return; }
  if(SRV.on&&SRV.user){
    b.className='tag good';
    b.textContent=(SRV.user.role==='viewer'?'podgląd: ':'serwer: ')+SRV.user.email.split('@')[0];
    b.title = SRV.updatedAt ? 'ostatni zapis: '+new Date(SRV.updatedAt*1000).toLocaleString('pl-PL')
                              +(SRV.updatedBy?' — '+SRV.updatedBy:'') : '';
    return;
  }
  if(SRV.on){ b.className='tag warn'; b.textContent='zaloguj się'; return; }
  if(SUPA.on&&SUPA.user){ b.className='tag good'; b.textContent='chmura: '+SUPA.user.email.split('@')[0]; }
  else if(SUPA.ready){ b.className='tag warn'; b.textContent='zaloguj się'; }
  else { b.className='tag'; b.textContent='tryb lokalny'; }
}

/* ============================================================================
   TRYB SERWEROWY (własny serwer, np. na mikr.us)
   ========================================================================== */
const SRV = {
  on:false, user:null, rev:0, timer:null, saving:false, dirty:false,
  updatedAt:null, updatedBy:null, version:null, commit:null,

  async detect(){
    // plik otwarty lokalnie (file://) — nie ma czego wykrywać
    if(location.protocol!=='http:' && location.protocol!=='https:') return false;
    try{
      const r = await fetch('/api/me', {headers:{'Accept':'application/json'}});
      if(r.status!==200 && r.status!==401) return false;
      const j = await r.json();
      if(j.mode!=='server') return false;
      this.on = true; this.user = j.user || null;
      this.version = j.version || null; this.commit = j.commit || null;
      return true;
    }catch(e){ return false; }
  },

  async login(email, pass){
    const r = await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email,password:pass})});
    const j = await r.json().catch(()=>({}));
    if(!r.ok) return j.error || 'Nie udało się zalogować.';
    this.user = j.user;
    USERS = null;
    await this.pull(true);
    return null;
  },

  async logout(){
    try{ await fetch('/api/logout',{method:'POST'}); }catch(e){}
    this.user = null; location.reload();
  },

  /** pobiera dane z serwera; first=true przy starcie (pusta baza → wysyłamy seed) */
  async pull(first){
    const r = await fetch('/api/data');
    if(r.status===401){ this.user=null; showLogin(); return; }
    const j = await r.json();
    this.rev = j.rev || 0;
    this.updatedAt = j.updatedAt; this.updatedBy = j.updatedBy;
    if(j.data && j.data.ingredients){
      DB = j.data; load2(); safeSet(JSON.stringify(DB));
    }else if(first && canEdit()){
      await this.pushNow();      // pierwsze uruchomienie — zasiew danymi z arkusza
    }
    badge();
  },

  /** Zgłoszenie na zmianę osobnym, wąskim endpointem.

      Pracownik nie może wysłać PUT /api/data — miałby wtedy w rękach całą bazę,
      łącznie z cenami. Wysyła więc sam fakt „chcę / nie chcę" na konkretny dzień
      i zmianę, a serwer dokleja tożsamość z ciasteczka i zwraca zaktualizowane zapisy.

      Menedżer idzie tą samą drogą i to nie jest kosmetyka: gdyby zapisywał grafik
      całym PUT-em, każde zgłoszenie pracownika unieważniałoby `rev` w jego otwartej
      karcie i wyskakiwałoby okienko o konflikcie. Tu każda odpowiedź przynosi
      świeży `rev`, a operacje ruszają wyłącznie swój wiersz zapisów. */
  /** Rejestracja zdarzenia dnia. Odpowiedź przynosi świeży `rev`, więc otwarta od rana
      karta menedżera nie wita go potem okienkiem o konflikcie. */
  async rejestruj(ciało){
    try{
      const r = await fetch('/api/zdarzenie',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify(ciało)});
      const j = await r.json().catch(()=>({}));
      if(!r.ok) return j.error || ('Błąd '+r.status);
      this.rev = j.rev;
      DB.zdarzenia = j.zdarzenia || {};
      DB.staff     = j.staff || [];
      safeSet(JSON.stringify(DB));
      badge();
      return null;
    }catch(e){ return 'Brak połączenia z serwerem.'; }
  },

  async zgloszenie(ciało){
    try{
      const r = await fetch('/api/shift',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify(ciało)});
      const j = await r.json().catch(()=>({}));
      if(!r.ok) return j.error || ('Błąd '+r.status);
      this.rev = j.rev;
      DB.signups = j.signups || {};
      DB.staff   = j.staff || [];
      safeSet(JSON.stringify(DB));
      badge();
      return null;
    }catch(e){ return 'Brak połączenia z serwerem.'; }
  },

  /** Wpis na wiele dni jednym żądaniem. Serwer sam pomija dni bez miejsca i oddaje
      obie listy — inaczej pięć osobnych żądań mogłoby przejść w połowie i nikt by
      nie wiedział, w połowie których. */
  async zbiorczo(ciało){
    try{
      const r = await fetch('/api/shift',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify(ciało)});
      const j = await r.json().catch(()=>({}));
      if(!r.ok) return j.error || ('Błąd '+r.status);
      this.rev = j.rev;
      DB.signups = j.signups || {};
      DB.staff   = j.staff || [];
      safeSet(JSON.stringify(DB));
      badge();
      return {zrobione: j.zrobione || [], pominiete: j.pominiete || []};
    }catch(e){ return 'Brak połączenia z serwerem.'; }
  },

  push(){
    if(!this.on || !this.user || !canEdit()) return;
    this.dirty = true;
    clearTimeout(this.timer);
    this.timer = setTimeout(()=>this.pushNow(), 600);
  },

  async pushNow(){
    if(this.saving){ this.dirty = true; return; }
    this.saving = true; this.dirty = false;
    badge('zapisywanie…');
    try{
      const r = await fetch('/api/data',{method:'PUT',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({rev:this.rev, data:DB})});
      const j = await r.json().catch(()=>({}));
      if(r.status===409){
        this.saving = false;
        if(confirm('Ktoś inny zapisał zmiany w międzyczasie'
          +(j.updatedBy?' ('+j.updatedBy+')':'')+'.\n\n'
          +'OK — wczytaj wersję z serwera i porzuć swoje ostatnie zmiany.\n'
          +'Anuluj — nadpisz wersję z serwera swoją.')){
          await this.pull(); render();
        }else{
          this.rev = j.rev; await this.pushNow(); render();
        }
        return;
      }
      if(r.status===403){ alert('Twoje konto ma tylko podgląd.'); this.saving=false; badge(); return; }
      if(!r.ok) throw new Error(j.error||('HTTP '+r.status));
      this.rev = j.rev; this.updatedAt = j.updatedAt; this.updatedBy = j.updatedBy;
      this.saving = false; badge();
      if(this.dirty) this.push();
    }catch(e){
      this.saving = false;
      badge('brak połączenia');
      console.error('Zapis nieudany:', e);
    }
  },
};

function showLogin(msg){
  if(document.getElementById('loginWrap')) return;
  const el=document.createElement('div');
  el.className='login-wrap'; el.id='loginWrap';
  el.innerHTML=`<form class="login-box" id="loginForm">
    <div class="brand" style="display:flex;align-items:center;gap:8px">
      <span style="display:block;width:26px;height:26px;color:var(--marka)">${znakHtml()}</span>
      <div><b style="font-size:15px">Sushi Planner</b><small style="display:block;color:var(--muted);font-size:11px">Noto Sushi</small></div>
    </div>
    <label class="f">E-mail</label><input id="lgMail" type="email" autocomplete="username" required>
    <label class="f" style="margin-top:10px">Hasło</label><input id="lgPass" type="password" autocomplete="current-password" required>
    <div id="lgErr" class="small" style="color:var(--crit-ink);margin-top:10px;min-height:18px">${esc(msg||'')}</div>
    <button class="btn pri" id="lgBtn" type="submit" style="width:100%;margin-top:4px">Zaloguj</button>
    <div class="small mut" style="margin-top:14px;line-height:1.45">Konta zakłada właściciel na serwerze komendą
      <code>python3 server.py adduser</code>.</div>
  </form>`;
  document.body.appendChild(el);
  document.getElementById('lgMail').focus();
  document.getElementById('loginForm').addEventListener('submit', async e=>{
    e.preventDefault();
    const b=document.getElementById('lgBtn'); b.disabled=true; b.textContent='Logowanie…';
    const err = await SRV.login(document.getElementById('lgMail').value.trim(),
                                document.getElementById('lgPass').value);
    if(err){ document.getElementById('lgErr').textContent=err; b.disabled=false; b.textContent='Zaloguj'; return; }
    el.remove();
    document.body.classList.toggle('ro', !canEdit());
    badge(); render();
  });
}

/* ============================================================================
   START
   ========================================================================== */
document.addEventListener('click',e=>{
  const b=e.target.closest('[data-act]'); if(!b) return;
  if(b.dataset.act==='addItem') editItem(null);
  if(b.dataset.act==='addSet') editSet(null);
});
(async ()=>{
  // znak firmowy wchodzi raz, przy starcie — potem już tylko się przemalowuje motywem
  const gniazdo = document.getElementById('brandLogo');
  if(gniazdo) gniazdo.innerHTML = logoHtml();
  const znakMenu = document.getElementById('brandZnak');
  if(znakMenu) znakMenu.innerHTML = znakHtml();
  const znakPaska = document.getElementById('burgerZnak');
  if(znakPaska) znakPaska.innerHTML = znakHtml();
  // znaki zakładek wchodzą raz — potem tylko dziedziczą kolor po stanie zakładki
  document.querySelectorAll('.nav[data-ik]').forEach(b=>{
    b.insertAdjacentHTML('afterbegin', '<span class="ic">' + ikona(b.dataset.ik) + '</span>');
    b.title = b.querySelector('.lbl').textContent;
    b.setAttribute('aria-label', b.title);
  });
  // Na ekranie węższym niż ~1000 px pasek startuje zwinięty, o ile nikt wcześniej
  // nie zdecydował inaczej. Telefon położony i mały laptop mają wtedy o 154 px więcej
  // na treść — a to jest różnica między kalendarzem, który się mieści, a takim, który
  // się rozjeżdża. Wybór człowieka jest ważniejszy, więc zapisany zostaje uszanowany.
  try{
    const zapis = localStorage.getItem(MENU_KEY);
    ustawMenuIkony(zapis === null ? innerWidth < 1000 : zapis === '1');
  }catch(e){ malujMenuTog(); }
  load();
  await SRV.detect();
  if(SRV.on){
    if(SRV.user){ await SRV.pull(true); }
    document.body.classList.toggle('ro', !canEdit());
  }
  // Adres z paska wygrywa z widokiem domyślnym: link wysłany koledze albo zakładka
  // mają otworzyć to samo miejsce, a nie Pulpit.
  const zAdresu = stanZAdresu(location.hash);
  if(zAdresu) przywrocStan(Object.assign({n:0}, zAdresu));
  badge(); render();
  zapiszHistorie(false);
  if(SRV.on && !SRV.user) showLogin();
  // odświeżanie co minutę, gdy karta jest aktywna — żeby widzieć zmiany kucharzy
  setInterval(async ()=>{
    if(!SRV.on || !SRV.user || SRV.saving || document.hidden) return;
    const before = SRV.rev;
    try{ await SRV.pull(); }catch(e){ return; }
    if(SRV.rev !== before) render();
  }, 60000);
})();

