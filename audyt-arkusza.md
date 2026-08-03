# Audyt arkusza „Notosushi foodcost 12.2025.xlsx”

Sprawdziłem wszystkie 4 zakładki (Składniki, Ryż, Rolki, Zestawy) — 49 składników, 30 rolek, 13 zestawów.
Poniżej to, co znalazłem, uporządkowane od najbardziej kosztownego.

---

## 1. Dziewięć rolek ma pustą formułę kosztu — food cost pokazuje ~1% zamiast realnego

W zakładce **Rolki**, kolumna F („Koszt”) jest wypełniona tylko dla części wierszy.
Tam gdzie jej brakuje, `SUMIF` sumuje wyłącznie nori z pierwszego wiersza — reszta receptury liczy się jako zero.

| Rolka | Food cost w arkuszu | Faktyczny | Koszt w arkuszu | Faktyczny koszt |
|---|---|---|---|---|
| Uramaki Tuńczyk Tatar Goma | 1,1% | **28,1%** | 0,27 zł | 6,76 zł |
| Uramaki Łosoś Tobiko | 1,1% | **25,8%** | 0,27 zł | 6,20 zł |
| Uramaki Krewetka obtaczana Łosiem | 1,1% | **23,5%** | 0,27 zł | 5,65 zł |
| Uramaki Tilapia Tempura | 1,1% | **18,2%** | 0,27 zł | 4,38 zł |
| Futomaki Kalmar Tempura | 1,2% | **12,8%** | 0,50 zł | 5,21 zł |
| Uramaki Tilapia | 1,1% | **12,6%** | 0,27 zł | 3,04 zł |
| Futomak Tuńczyk Tempura | 1,2% | **9,4%** | 0,50 zł | 3,82 zł |
| Futomak Kurczak Tempura | 1,2% | **8,9%** | 0,50 zł | 3,62 zł |
| Futomak Tuńczyk Tatar | 1,2% | **5,3%** | 0,50 zł | 2,17 zł |

To najgroźniejszy typ błędu w Excelu: nic nie krzyczy, liczba wygląda wiarygodnie, a decyzja cenowa jest podjęta na fikcji.
W aplikacji nie da się go powtórzyć — koszt składnika liczy się zawsze, bo nie ma czegoś takiego jak „komórka bez formuły”.

---

## 2. Zestawy nie zawierają opakowań, sztućców ani dodatków

Tacki HP07–HP36, pałeczki, opłata SUP, sos sojowy, imbir i wasabi **są w arkuszu, ale bez cen i bez powiązania z zestawami**.
Food cost każdego zestawu to dziś wyłącznie koszt samych rolek.

Skala, licząc gramaturami z Twojego arkusza (Zestaw 1, cena 29 zł):

```
koszt rolek                      7,66 zł   →  food cost 28,5%
+ wasabi 40 g                    0,92 zł
+ imbir 1 porcja                 2,40 zł
+ sos sojowy 1 saszetka          1,75 zł
────────────────────────────────────────
razem                           12,72 zł   →  food cost 47,4%
                                              (tacka i pałeczki wciąż niepoliczone)
```

Reguła kciuka do szybkiego szacowania: **każda złotówka opakowania to +3,7 pkt proc. food costu na zestawie za 29 zł**,
+2,7 pkt na zestawie za 40 zł, ale tylko +0,4 pkt na zestawie za 299 zł.
Czyli: opakowania biją głównie w małe zestawy — a to zwykle te, które sprzedają się najczęściej.

> W aplikacji każdy zestaw ma sekcję **„Dodatki i opakowanie”**. Uzupełnij ceny tacek i pałeczek w zakładce Składniki,
> dopisz je do zestawów i dopiero ta liczba jest prawdziwym food costem.

---

## 3. Ryż liczony po cenie ryżu suchego, mimo że masz gotową kalkulację

Zakładka **Ryż** poprawnie liczy koszt ryżu ugotowanego z zaprawą: **4,79 zł/kg**
(3 kg suchego + 0,85 l zaprawy → 6 kg gotowego).

Ale zakładka **Rolki** pobiera cenę z listy Składników, czyli **8,33 zł/kg** — cenę ryżu suchego.
Receptury podają 110–190 g ryżu *ugotowanego*, więc koszt ryżu jest zawyżony o **74%**.

Wpływ na wszystkie 13 zestawów:

| | koszt sumaryczny | zmiana |
|---|---|---|
| tak jak liczy arkusz | 292,29 zł | — |
| po podstawieniu ryżu gotowanego | 255,85 zł | **−36,44 zł (−12,5%)** |

Przykładowo Zestaw 3 spada z 29,0% na 25,1%, a Zestaw 10 z 28,6% na 25,3%.

> To działa **na Twoją korzyść** — masz większy zapas marży, niż myślisz. Ale to nadal błąd:
> zaniża realną rentowność jednych pozycji względem drugich i psuje porównania między nimi.
> W aplikacji ryż jest **półproduktem** (zakładka Półprodukty) i podstawia się automatycznie po właściwej cenie.

---

## 4. „Sylwester 3” odwołuje się do rolki, która nie istnieje

Zestaw zawiera pozycję **Uramaki Vege** — nie ma jej w zakładce Rolki.
Efekt: `#N/A` w kolumnach „Cena zestawu brutto z rolek” i „Obniżka do”, a 10 kawałków wchodzi do zestawu z kosztem zero.
Arkusz deklaruje 168 kawałków, policzonych jest 158.

---

## 5. Jednostki do weryfikacji

Sześć pozycji ma jednostkę `szt.` przy wielkości opakowania, która wygląda na gramy:

| Składnik | W arkuszu | Cena jednostkowa | Skutek |
|---|---|---|---|
| Sezam Biały | 500 szt. / 335 zł | 0,67 zł/szt. | 2 „szt.” sezamu w rolce = 1,34 zł |
| Sezam Czarny | 500 szt. / 435 zł | 0,87 zł/szt. | 2 „szt.” = 1,74 zł |
| Sriracha | 1000 szt. / 75 zł | 0,075 zł/szt. | — |
| Sos Teryaki | 500 szt. / 260 zł | 0,52 zł/szt. | — |
| Sos Kikoman saszetka | 300 szt. / 525 zł | 1,75 zł/szt. | wpływa na kalkulację z punktu 2 |
| Imbir Marynowany | 300 szt. / 720 zł | 2,40 zł/szt. | wpływa na kalkulację z punktu 2 |

Najbardziej podejrzany jest sezam: przy tych stawkach **sam sezam to 45% kosztu** rolki Uramaki Tuńczyk Tatar Goma.
Jeśli to w rzeczywistości gramy, jej food cost spada z 28,1% do ok. 15%.
Warto sprawdzić w fakturach — to jedyna liczba w tym audycie, której nie da się zweryfikować z samego arkusza.

---

## 6. Kruche zakresy formuł — pułapka na przyszłość

Dwie rzeczy, które dziś jeszcze działają, ale zepsują się przy pierwszym dopisanym wierszu:

- `SUMIF($A$2:$A$218; A2; $F$2:$F$184)` w zakładce Rolki — zakres kryterium (218 wierszy) jest dłuższy niż zakres sumowania (184).
- `SUMIF(Rolki!$A$2:$A$208; B2; Rolki!$K$2:$K174)` w zakładce Zestawy — koniec zakresu nie jest zablokowany `$`,
  więc przesuwa się wiersz po wierszu (K174, K175, K177…). Przy dłuższej liście rolek zacznie ucinać dane.

Oba przypadki zawiodą **po cichu** — wynik będzie po prostu za mały.

---

## Podsumowanie: co robić dalej

1. **Uzupełnij ceny opakowań** (tacki, pałeczki, opłata SUP) i dopisz je do zestawów. To jedyna pozycja z tej listy,
   która realnie zjada marżę i nikt jej dziś nie widzi.
2. **Zweryfikuj jednostki** przy sezamie, imbirze i sosach.
3. **Uzupełnij cenę Goma wakame** — jest w recepturze Uramaki Tuńczyk Tatar Goma, liczy się jako 0.
4. **Dodaj Uramaki Vege** albo usuń ją z Sylwestra 3.
5. Rolki z punktu 1 przelicz na nowo — kilka z nich jest wycenionych na podstawie fałszywego food costu.

Wszystkie dane z arkusza są już wgrane do aplikacji i policzone poprawnie — punkty 1, 3 i 4 są tam naprawione automatycznie.
Punkty 2 i 5 wymagają Twoich liczb.

*Audyt: 3 sierpnia 2026*
