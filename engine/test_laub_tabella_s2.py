"""
test_laub_tabella_s2.py  |  SolRatio v4.3.1
=============================================
Le curve di resa di LAUB_COEFFICIENTS contro la Table S2 di Laub et al. (2022).

La Table S2 del materiale supplementare dà la resa prevista dal modello finale
dell'articolo per 9 gruppi colturali a RSR 5, 10, ..., 90 %: 162 valori, copiati
in engine/laub_2022_table_s2.csv. La tolleranza di 0.1 punti percentuali copre
l'arrotondamento a 0.1 con cui la tabella pubblica le rese (+/-0.05) e quello
dei coefficienti a quattro decimali: con i coefficienti della v4.3.1 lo scarto
massimo misurato è 0.071 punti (leguminose da granella a RSR 25 %). Con quelli
della v4.3.0 tutti e nove i gruppi uscivano dalla tolleranza (tuberi fino a
19.87 punti a RSR 45 %, cereali C3 fino a 11.08 a RSR 35 %).

Uso, dalla radice del repository (non richiede pytest né Radiance):
    python engine/test_laub_tabella_s2.py
oppure
    python -m pytest engine/test_laub_tabella_s2.py
"""
import csv
import os
import sys

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE_DIR)

from solratio_core import LAUB_COEFFICIENTS, laub_yield  # noqa: E402

TABELLA = os.path.join(ENGINE_DIR, 'laub_2022_table_s2.csv')
TOLLERANZA_PUNTI = 0.1

# etichetta della Table S2 -> chiave di LAUB_COEFFICIENTS
GRUPPO = {
    'Berries': 'bacche', 'Fruits': 'frutta', 'Fruity vegetables': 'ortaggi_frutto',
    'Forages': 'foraggere', 'Leafy vegetables': 'ortaggi_foglia',
    'Tubers/root crops': 'tuberi_radici', 'C3 cereals': 'cereali_C3',
    'Grain legumes': 'leguminose_granella', 'Maize': 'mais',
}


def _tabella():
    """(chiave del gruppo, RSR %, resa prevista %) per ogni riga della Table S2."""
    with open(TABELLA, encoding='utf-8', newline='') as f:
        righe = csv.DictReader(r for r in f if not r.startswith('#'))
        return [(GRUPPO[r['crop_type']], int(r['rsr_pct']), float(r['prediction_pct']))
                for r in righe]


def test_la_tabella_ha_162_valori_18_per_gruppo():
    righe = _tabella()
    assert len(righe) == 162, len(righe)
    for chiave in GRUPPO.values():
        rsr = sorted(r for g, r, _ in righe if g == chiave)
        assert rsr == list(range(5, 91, 5)), (chiave, rsr)
    assert set(GRUPPO.values()) == set(LAUB_COEFFICIENTS)


def test_le_curve_riproducono_la_tabella_s2():
    fuori = []
    for gruppo in GRUPPO.values():
        scarti = [(rsr, pubblicata, float(laub_yield(rsr / 100.0, gruppo)))
                  for g, rsr, pubblicata in _tabella() if g == gruppo]
        rsr, pubblicata, calcolata = max(scarti, key=lambda s: abs(s[2] - s[1]))
        if abs(calcolata - pubblicata) > TOLLERANZA_PUNTI:
            fuori.append(f'{gruppo} a RSR {rsr} %: la curva dà {calcolata:.2f} %, '
                         f'la Table S2 {pubblicata} %')
    assert not fuori, ('scarto massimo oltre %.1f punti:\n  ' % TOLLERANZA_PUNTI
                       + '\n  '.join(fuori))


if __name__ == '__main__':
    esito = 0
    for prova in (test_la_tabella_ha_162_valori_18_per_gruppo,
                  test_le_curve_riproducono_la_tabella_s2):
        try:
            prova()
            print(f'OK    {prova.__name__}')
        except AssertionError as e:
            esito = 1
            print(f'ROSSA {prova.__name__}\n{e}')
    sys.exit(esito)
