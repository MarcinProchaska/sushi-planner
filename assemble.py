#!/usr/bin/env python3
"""Składa sushi-planner.html z trzech źródeł.

    template.html  (CSS + silnik)   ─┐
    part2.js       (widoki)          ├─► sushi-planner.html
    seed.json      (dane startowe)  ─┘

`sushi-planner.html` jest plikiem GENEROWANYM — nigdy nie edytuj go ręcznie.
Zmieniasz źródło, uruchamiasz `python3 assemble.py`.

Znaczniki w szablonie: `/*SEED*/` i `/*PART2*/`, każdy dokładnie raz. Sprawdzamy to przed
zapisem — ta sama dyscyplina, co przy skryptach łatających: jeżeli wzorzec nie pasuje
dokładnie raz, przerywamy, zamiast zapisywać plik „w ciemno".

`seed.json` wstawiamy jako TEKST, a nie przez `json.dumps`: ponowna serializacja zmieniłaby
formatowanie i każde złożenie dawałoby inny plik, choć dane byłyby te same.
"""
import json
import os
import sys

BAZA = os.path.dirname(os.path.abspath(__file__))


def wczytaj(nazwa):
    with open(os.path.join(BAZA, nazwa), encoding='utf-8') as f:
        return f.read()


def bez_ostatniego_entera(tekst):
    """Zdejmuje DOKŁADNIE jeden znak końca linii — ten, który edytor dokłada na końcu
    pliku. `rstrip` zjadłby też puste linie należące do treści i złożony plik różniłby
    się od poprzedniego o bajt, bez żadnej zmiany w kodzie."""
    return tekst[:-1] if tekst.endswith('\n') else tekst


def wstaw(tekst, znacznik, tresc):
    ile = tekst.count(znacznik)
    if ile != 1:
        sys.exit('Znacznik %s występuje %d razy, a ma dokładnie raz.' % (znacznik, ile))
    return tekst.replace(znacznik, tresc)


def main():
    szablon = wczytaj('template.html')
    part2 = bez_ostatniego_entera(wczytaj('part2.js'))
    seed = bez_ostatniego_entera(wczytaj('seed.json'))

    # Dane startowe muszą być poprawnym JSON-em — inaczej aplikacja wywali się przy
    # pierwszym wczytaniu, a to jedyne miejsce, w którym da się to sprawdzić tanio.
    try:
        json.loads(seed)
    except ValueError as e:
        sys.exit('seed.json nie jest poprawnym JSON-em: %s' % e)

    wynik = wstaw(szablon, '/*SEED*/', seed)
    wynik = wstaw(wynik, '/*PART2*/', part2)

    sciezka = os.path.join(BAZA, 'sushi-planner.html')
    # Przekierowanie „>" pisze PRZEZ dowiązanie symboliczne — stąd usunięcie przed zapisem.
    if os.path.islink(sciezka):
        os.unlink(sciezka)
    with open(sciezka, 'w', encoding='utf-8') as f:
        f.write(wynik)
    print('sushi-planner.html: %d bajtów' % len(wynik.encode('utf-8')))


if __name__ == '__main__':
    main()
