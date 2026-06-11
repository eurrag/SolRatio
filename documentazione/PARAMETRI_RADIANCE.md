# Parametri Radiance — Guida al tuning

## Panoramica

SolRatio usa Radiance rtrace in modalità irradianza (`-I`) per calcolare
l'irradianza al suolo sotto un impianto agrivoltaico a tracker mono-assiale.
I tre parametri principali controllano il trade-off accuratezza/velocità.


## Parametri configurabili (foglio Parametri)

### `-ab` — Ambient Bounces (cella B48)

Numero massimo di rimbalzi di luce indiretta che rtrace simula.

| Valore | Significato | Tempo relativo | Quando usare |
|--------|-------------|----------------|--------------|
| 0 | Solo luce diretta, nessun rimbalzo | 1× (più veloce) | Test rapidi, debug. Sottostima la diffusa. |
| **1** | **1 rimbalzo (default)** | **2-3×** | **Uso standard. Cattura la maggior parte della diffusa e la riflessione suolo→pannello→suolo.** |
| 2 | 2 rimbalzi | 5-8× | Maggiore accuratezza per scene complesse, albedo alto. |
| 3 | 3 rimbalzi | 10-20× | Massima accuratezza. Raramente necessario per agrivoltaico. |

Effetto fisico: con `-ab 0` la luce colpisce il suolo una sola volta (dal cielo).
Con `-ab 1`, la luce che rimbalza dal suolo e colpisce il retro del pannello
viene poi riflessa nuovamente verso il suolo (inter-row reflection). Questo è il
contributo dominante per l'accuratezza in agrivoltaico.

Raccomandazione: **ab=1** per simulazioni di routine; **ab=2** per validazione
o quando l'albedo è alto (> 0.4, es. neve, teli riflettenti).


### `-ad` — Ambient Divisions (cella B49)

Numero di raggi campione per l'emisfera superiore in ogni punto di calcolo
dell'irradianza indiretta.

| Valore | Qualità | Tempo relativo | Quando usare |
|--------|---------|----------------|--------------|
| 128 | Bassa | 0.5× | Test rapidi |
| 512 | Media | 0.8× | Simulazioni preliminari |
| **1024** | **Standard (default)** | **1×** | **Uso standard** |
| 2048 | Alta | 1.5× | Validazione |
| 4096 | Massima | 3× | Benchmark di riferimento |

Effetto fisico: `-ad` controlla il campionamento dell'emisfera diffusa.
Più raggi = meno rumore nel risultato, ma più tempo di calcolo. Con valori
troppo bassi, l'irradianza diffusa sotto i pannelli presenta rumore casuale.

Raccomandazione: **ad=1024** per uso standard. Aumentare a 2048-4096 solo
per simulazioni di benchmark o validazione. Per test rapidi, 128-512 basta.


### `-as` — Ambient Super-samples (cella B50)

Numero di raggi aggiuntivi nelle regioni dell'emisfera dove il campionamento
iniziale (`-ad`) rileva elevata varianza.

| Valore | Comportamento | Quando usare |
|--------|---------------|--------------|
| 32 | Super-sampling minimo | Test rapidi |
| **128** | **Standard (default)** | **Uso standard** |
| 256 | Conservativo | Scene complesse |
| 512 | Massimo | Benchmark |

Effetto fisico: `-as` raffina il campionamento dove c'è forte contrasto
(es. transizione ombra/luce al bordo del pannello). Migliora la precisione
del profilo spaziale senza rallentare significativamente le zone uniformi.

Raccomandazione: **as=128** per uso standard. Valori > 256 hanno rendimenti
decrescenti.


### `br_n_rows` — Numero file scena (cella B51)

Numero totale di file tracker nella scena Radiance.

| Valore | Significato |
|--------|-------------|
| **0** | Auto: `2 × n_ext + 1` (default). Usa il parametro n_ext (B44). |
| 3 | Minimo: 1 fila centrale + 1 per lato |
| 5 | Standard con n_ext=2 |
| 7 | Aumentato (n_ext=3 equivalente) |
| 9+ | Per impianti molto grandi o validazione |

Regola: deve essere **dispari** (fila centrale simmetrica). Se pari, viene
calcolato `n_ext = (n_rows-1)//2` con arrotondamento.

Effetto: più file = scena più realistica (più inter-row reflections, ombra
cumulativa). Per il pitch centrale, oltre 7 file il guadagno è trascurabile.
Per l'effetto bordo, il numero di file determina quanti profili edge vengono
calcolati.

### Raccomandazione minima n_rows (v4.1.1)

Misurazioni empiriche su progetto pianura padana (lat 45.30°N, pitch=5m,
W=2.38m, H=3.13m) confrontando SolRatio v4 con bifacial_radiance ufficiale
NREL come reference:

| n_rows | n_ext | Bias eq. (21 mar) | Bias solst. (21 giu) | Uso consigliato |
|-------:|------:|------------------:|---------------------:|-----------------|
| 4      | 1     | +4.5%             | +1.2%                | Sconsigliato (sotto-stima inter-row) |
| 5      | 2     | +1-2% (stimato)   | <1%                  | Test rapidi, debug |
| **7**  | **3** | **<1%**           | **<0.5%**            | **Uso routine, default raccomandato** |
| 9      | 4     | <0.5%             | <0.3%                | Benchmark, pubblicazioni |
| 11+    | 5+    | <0.3% (asintoto)  | <0.2%                | Validazione di riferimento |

**Causa fisica**: con sole basso (equinozio, mattina/sera), la luce arriva
con angoli obliqui e le file lontane dal pitch centrale intercettano una
porzione significativa di raggi diretti e diffusi che altrimenti
raggiungerebbero il terreno. Una scena con poche file simula implicitamente
un campo agrivoltaico piccolo (es. 4 file = pilota di pochi tracker), dove
il pitch centrale "vede" meno ombreggiamento mutuo. Per simulare il
comportamento di un pitch interno a un impianto medio-grande (10+ file)
serve usare n_ext ≥ 3.

A partire da v4.1.1, `br_engine.run_annual()` emette un avviso a runtime
quando `n_rows < 7`, ricordando di aumentare n_ext per simulazioni accurate.
La pipeline di validazione `validazione_br.py` è stata corretta per usare
la stessa scena di `run_annual` (rispetta `br_n_rows` se impostato).


## Parametri rtrace fissi (non configurabili)

| Flag | Valore | Descrizione |
|------|--------|-------------|
| `-I` | — | Modalità irradianza (input = punto + direzione, output = irradianza) |
| `-aa` | 0.1 | Accuratezza ambient (soglia di errore) |
| `-ar` | 256 | Risoluzione ambient (suddivisione spaziale) |
| `-h` | — | Nessun header nell'output |

Questi valori sono adeguati per agrivoltaico e non richiedono tuning.


## Profili di tempo tipici

Riferimento: località esempio (lat 45.30°N, lon 9.34°E) (lat 45.27°, 51 punti, 5 file, TMY ~4000 ore
diurne, 25 workers su 32 CPU).

| Configurazione | ab | ad | as | Tempo stimato |
|----------------|----|----|-----|---------------|
| Test rapido | 0 | 128 | 32 | ~1 min |
| Standard | 1 | 1024 | 128 | ~5 min |
| Alta qualità | 2 | 2048 | 256 | ~15-25 min |
| Benchmark | 3 | 4096 | 512 | ~45-90 min |

Il tempo scala linearmente con: n_ore_diurne × n_total_points × (1 + ab overhead).
L'overhead per l'effetto bordo (sensori aggiuntivi nel batch) aggiunge ~10-20%
al tempo base, proporzionale al numero di edge pitches.


## Conversione output rtrace → irradianza

rtrace in modo `-I` restituisce radianza spettrale (R, G, B) in W/sr/m².
La conversione a irradianza [W/m²] è:

```
IRR = 179 × (0.265 × R + 0.670 × G + 0.065 × B)
```

dove 179 lm/W è l'efficacia luminosa standard e i coefficienti RGB sono i
pesi per la luminanza CIE. Con `-I` e sensori che puntano verso l'alto
(direzione 0 0 1), il risultato è l'irradianza totale incidente sulla
superficie orizzontale.
