# Roadmap supporto terreno in pendenza (slope) per SolRatio v4+

Documento tecnico di pianificazione. Stato al 2026-04-15.

## Contesto

Il modello SolRatio v4 legge i parametri di pendenza terreno dal foglio
`Parametri` del progetto:

- `B6` = slope_pct (pendenza %)
- `B7` = slope_azimuth (azimut della linea di max pendenza, deg)

e li espande in `solratio_excel.py:191` in grandezze geometriche derivate:

- `slope_angle` (deg) — inclinazione del terreno rispetto all'orizzontale
- `slope_cross_deg` (deg) — componente trasversale rispetto all'asse tracker
- `axis_tilt_deg` — componente assiale (da implementare se mancante)

Il motore ray-tracing `br_engine.py` tuttavia **non propaga** queste grandezze alla
scena Radiance ne' alla chiamata `pvlib.tracking.singleaxis()` (vedi bug hardcoded
`axis_tilt=0` a riga 278). La batteria di test ha evidenziato il problema: i 4 test
slope danno output indistinguibile.

## Obiettivo finale

Supportare correttamente la simulazione DLI/Kagv su terreni in pendenza fino a
~15-20%, con precisione equivalente al ramo analitico v3 (MBE<5% vs misura reale).

## Piano a livelli incrementali

### Livello 1 — Tracker angles — COMPLETATO (2026-04-14)

**Scope:** propagare slope ai parametri `axis_tilt` e `cross_axis_tilt` di pvlib
singleaxis. La geometria della scena Radiance resta su piano orizzontale.

**Implementazione effettiva:**

1. `solratio_core.py:compute_slope_components()` gia' calcolava `slope_along_deg`
   e `slope_cross_deg`. Questi valori sono salvati in `p` da `solratio_excel.py`.

2. In `br_engine.py` (~riga 288): propagati a `pvlib.tracking.singleaxis()`:
   ```python
   _axis_tilt = p.get('slope_along_deg', 0.0)
   _cross_axis_tilt = p.get('slope_cross_deg', 0.0)
   tracker_res = pvlib_tracking.singleaxis(
       ..., axis_tilt=_axis_tilt, cross_axis_tilt=_cross_axis_tilt, ...)
   ```

3. In `solratio_excel.py`: stessa propagazione nelle due chiamate a singleaxis
   (~riga 570 e ~riga 845).

**Risultati batteria test (4 casi slope):**

| Test           | slope_along | slope_cross | DLI P50 |
|----------------|-------------|-------------|---------|
| slope_8pct_S   | +4.57       | 0.00        | 20.1    |
| slope_15pct_S  | +8.53       | 0.00        | 20.0    |
| slope_15pct_N  | -8.53       | 0.00        | 20.6    |
| slope_15pct_E  | +0.00       | -8.53       | 20.3    |

Risultati differenziati e fisicamente coerenti (N > E > S).

### Livello 2 — Quote per-fila nella scena BR — COMPLETATO (2026-04-15)

**Scope:** le posizioni verticali (Z) delle file sono calcolate rispetto a un
piano di terreno inclinato. L'altezza hub di ciascuna fila dipende dalla sua
posizione lungo la componente trasversale della pendenza (cross-axis).

**Implementazione effettiva in `br_engine.py`:**

L2 si attiva solo quando `slope_cross_deg != 0` (pendenza trasversale all'asse
tracker). Per N-S tracker: slope S/N = solo L1, slope E/W = L1+L2.

1. Scena generata con `nRows=1` (singola fila centro) via `rad.makeScene()`.

2. Lettura del file `.rad` generato da BR per estrarre i comandi `!xform`
   originali (contengono tilt, hub height, posizionamento modulo).

3. Composizione di un wrapper `.rad` multi-row: per ogni fila, il comando
   `!xform` originale viene esteso con `-t DX 0 DZ` prima del filename.
   `xform` applica le trasformazioni L-to-R, quindi l'offset e' applicato
   per ultimo (dopo tilt + hub height). Ogni riga del wrapper e' un singolo
   `!xform` → nessun annidamento, `oconv` lo gestisce correttamente.

   ```
   !xform [opts_BR] file.rad                          # fila centro
   !xform [opts_BR] -t -5.0 0 0.75 file.rad          # fila -1
   !xform [opts_BR] -t  5.0 0 -0.75 file.rad         # fila +1
   !xform [opts_BR] -t -10.0 0 1.50 file.rad         # fila -2
   ```

4. DZ clamp: `|dz| <= clearance - 0.02m` per evitare che pannelli scendano
   sotto il ground plane Z=-0.01.

5. Sensori restano su Z=0.05 (ground Radiance piatto). L'effetto L2 e'
   catturato dalle file a quote diverse che proiettano ombre differenti.
   I sensori NON seguono il terreno (quello sarebbe L3).

**Approcci scartati durante il debug:**

- **z_shift globale**: alzare tutta la scena per mantenere sensori sopra ground
  → pannelli troppo alti, DLI gonfiato del 44%.
- **Subprocess pre-flatten**: `xform base.rad` per risolvere `!xform` annidati
  → lento (3700 subprocess per scena), hang su Windows.
- **Wrapper su file con `!xform` annidati**: `!xform wrapper.rad` dove wrapper
  contiene `!xform scene.rad` che a sua volta contiene `!xform module.rad`
  → `oconv` non processa il secondo livello su Windows.

**Risultati:** slope_15pct_E con L2 attivo: DLI=20.3, trasmissione=67.8%,
0 errori. Non-regressione sugli altri 3 test (solo L1) confermata.

### Livello 3 — Rigoroso (stimato: 1 settimana, alta complessita')

**Scope:** terreno inclinato come oggetto Radiance reale + proiezioni corrette
per tutti i KPI.

**Modifiche:**

1. Ground come `polygon` Radiance inclinato, non piu' `cube` orizzontale
2. Tutti i sensori proiettati sul piano reale del terreno (normale al terreno)
3. Ricalcolo di FC_NS (formula analitica in `solratio_edge.py`) tenendo conto
   dello slope: l'orizzonte est/ovest non e' simmetrico su terreno pendente
4. Gestione del sole rispetto al piano del terreno per i calcoli di primavera/
   estate che usano l'elevazione solare
5. Supporto slope sia assiale sia trasversale contemporaneo

**Target di qualita':** MBE <5% rispetto a misure in campo su siti reali con
pendenza nota (cercare paper/dataset open: CEA-INES Grenoble, Fraunhofer ISE
agrivoltaico su versanti alpini).

## Stato attuale e priorita'

**Completato (v4.0.0):** Livello 1 + Livello 2. I test slope della batteria
producono risultati differenziati e fisicamente coerenti. La precisione e'
adeguata per pendenze fino a ~15-20%.

**Possibile miglioramento:** aggiungere test con slope diagonale (es. 15% SE)
per validare L1+L2 simultanei con entrambe le componenti non-zero.

**Lungo termine (v5+):** Livello 3. Solo se emergono casi d'uso commerciali su
pendii importanti (>15%) che non si riescono a gestire con L2.

## Note aggiuntive

- pvlib dispone di tutti gli strumenti per L1 (vedi `pvlib.tracking.singleaxis()`
  con `cross_axis_tilt`). Seguire la preferenza pvlib del progetto.
- bifacial_radiance ha esempi con tilted ground ma sono scarsamente documentati;
  eventualmente contattare NREL o cercare su github issues.
- Un pre-requisito utile per L2 e' rifattorizzare `br_engine.py` estraendo la
  costruzione della scena in una funzione dedicata, cosi' L2 tocca solo quella.
