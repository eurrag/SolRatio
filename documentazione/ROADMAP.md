# SolRatio — Roadmap e bug noti

## Stato attuale (v4.1.1, 2026-05-01)

Patch di correttezza scientifica della pipeline di validazione vs BR ufficiale
NREL: corretto il mismatch di dimensione scena tra `run_annual()` e
`_run_br_official()` quando l'override `br_n_rows` è impostato. Aggiunto
warning a runtime in `br_engine.run_annual()` quando `n_rows < 7`, e
documentazione esplicita della raccomandazione minima n_ext ≥ 3 per uso
di routine. Pipeline di validazione torna a MBE ~0%, R² > 0.999.

Vedi `CHANGELOG.md` per i dettagli completi delle modifiche v4.1.1.

## Stato precedente (v4.1.0, 2026-05-01)

Prima release pubblica con DOI Zenodo. Motore BR validato, infrastruttura di
rilascio completa (LICENSE Apache 2.0, README, requirements, CITATION.cff,
.zenodo.json), nuove feature applicative implementate (tau via materiale Radiance
trans, ottimizzazione H_min via curva di Pareto, slope L3 con sensori sul piano
inclinato), pali rimossi dal flusso (rimandati a v4.2 con modellazione 3D).

Vedi `CHANGELOG.md` per i dettagli delle modifiche v4.1.0.

## Stato precedente (v4.0.0, 2026-04-10)

Il motore BR è funzionante per simulazione annuale con output Excel e PDF.
I test effettuati sono sul progetto località esempio (lat 45.30°N, lon 9.34°E).

### Bug noti

Nessun bug noto al momento. I seguenti bug sono stati risolti durante lo
sviluppo (dettagli nel CHANGELOG):

- [RISOLTO] Parsing rtrace `-oovs` (leggeva coordinate come RGB)
- [RISOLTO] Shape mismatch n_all vs 8760
- [RISOLTO] UnboundLocalError n_ext con br_n_rows manuale
- [RISOLTO] TMY anno singolo invece di composito mese-per-mese
- [RISOLTO] Riferimento open sky da GHI (ora da simulazione BR)
- [RISOLTO] Effetto bordo misto SR/BR (ora tutto BR)


## Stato delle verifiche TODO precedenti (chiusura v4.0.0 → v4.1.0)

I TODO della v4.0.0 sono stati chiusi (completati o riformulati) in v4.1.0:

- [✓] ~~Validazione vs v3.3.4~~: superato — v3.x è dichiarato deprecato. Riferimento
  scientifico per la validazione è ora `bifacial_radiance` ufficiale (NREL),
  con cui v4 è allineato a MBE<1%, R²>0.998 (località esempio (lat 45.30°N, lon 9.34°E)).
- [parziale] **Test su progetti multipli**: già eseguito un primo round su progetto
  Sample (Pianura Padana, lat 45.30°N), e batteria test_battery (47 test, 45 OK + 2 SKIP). Da estendere con un
  test specifico al rilascio v4.1.0 sui progetti reali con tau/H_min/L3 attivi.
- [da fare al rilascio] **Verifica ΔK_agv effetto bordo positivo** su almeno 2
  progetti diversi.
- [da fare al rilascio] **Verifica PAR relativa ≤ 1.0** sui report v4.1.0.
- [✓] **Diagnostica errori rtrace**: implementata in v4.1.0 (warning se errori > 1%
  delle ore, con elenco cause probabili).
- [da fare] **Forzatura nRows dispari**: validazione input br_n_rows ancora aperta.
- [✓] **Trasmittanza pannello (tau)**: implementata in v4.1.0 via materiale
  Radiance `trans` (vedi CHANGELOG v4.1.0).
- [✓ parziale] **Pendenza terreno**: implementato slope L3 per i sensori +
  groundplane abbassato dinamicamente. Resta aperto L3 completo con polygon
  ground inclinato per slope > 15% (rimandato a v4.2).


## Sviluppi futuri

### v4.2 — Pali, multi-anno, ground inclinato

- **Pali nella scena Radiance**: reintegrare i pali di sostegno come oggetti
  cilindrici nella scena BR (in v4.0.0 erano gestiti analiticamente con
  post-shadow; in v4.1.0 sono stati rimossi dal flusso, codice conservato
  dormiente). Richiede: oggetti cilindrici Radiance posizionati sull'asse tracker
  con spaziatura B22, riattivazione delle call sites commentate in
  `calcola_br.py`, `solratio_edge.py`, `solratio_pdf.py`, `solratio_excel.py`.

- **Modalità multi-anno**: eseguire la simulazione su tutti gli anni PVGIS
  (non solo TMY) e calcolare statistiche inter-annuali (P10/P50/P90 di K_agv).
  Permette di stimare la variabilità climatica del sito.

- **Ground plane inclinato (L3 completo)**: in v4.1.0 i sensori sono già
  posizionati sul piano terreno (L3 parziale), ma il ground geometrico
  Radiance (`groundplane ring`) resta orizzontale. Per slope > 15% può
  introdurre artefatti nell'albedo riflessa. Soluzione: sostituire ring
  con polygon inclinato secondo slope_pct/slope_azimuth.

- **Cache scene persistente**: salvare le scene pre-generate (.oct) su disco
  per evitare ri-generazione tra run successive sullo stesso progetto.

- **Layout cartella progetto standardizzato**: separare input e output in
  sottocartelle dedicate per migliorare la leggibilità di progetti maturi.
  Struttura proposta:
  ```
  <progetto>/
  ├── SolRatio_progetto.xlsm        (rimane in root: punto d'ingresso)
  ├── input/
  │   ├── PVGIS_<lat>_<lon>_*.csv  (meteo grezzo)
  │   └── PVGIS_<lat>_<lon>_TMY.epw (EPW generato)
  └── test/
      ├── optimization_*.xlsx       (curva K_agv vs H_min)
      ├── optimization_*.png        (grafico)
      ├── validazione_*.csv         (confronto SR vs BR ufficiale)
      └── risultati_*.xlsx          (output principale BR)
  ```
  Richiede:
  - Funzione `find_pvgis_csv()` con fallback root → `input/`
    in `br_engine.pvgis_to_epw()` e `validazione_br.py`
  - Aggiornamento path output in `solratio_optimization.py`,
    `validazione_br.py`, `calcola_br.py`
  - Aggiornamento Launcher Excel (VBA) per nuovi path relativi
  - Migrazione automatica progetti esistenti (script `migrate_project_layout.py`
    che sposta i file e mantiene retrocompatibilità con layout v4.1.x)
  - Aggiornamento `_template/` e `Sample/` come riferimento
  - Aggiornamento docs: `ARCHITETTURA.md`, README di Sample, README principale

- **Script di release automatico** (`_PREPARA_RELEASE.bat` + `bump_version.py`):
  automatizzare la procedura di patch/release. Funzionalità:
  - Chiede nuova versione interattivamente (es. `4.1.2`, `4.2.0`)
  - Aggiorna `engine/VERSION`
  - Sostituisce stringa versione in tutti i file `.py` (header docstring,
    `__version__`, print statement runtime, descrizioni argparse)
  - Aggiorna `CITATION.cff` (`version`, `date-released`)
  - Apre `documentazione/CHANGELOG.md` con un template della nuova sezione
    da compilare a mano
  - Verifica coerenza con `check_environment.py` post-bump
  - Stampa istruzioni passo-passo per: commit, tag, push, GitHub release,
    Zenodo DOI, aggiornamento CITATION con DOI versione
  Riduce il rischio di dimenticare un file da bumpare e accelera il rilascio
  di patch successive.

### v4.3 — Funzionalità avanzate

- **Pannelli semi-trasparenti avanzati**: in v4.1.0 è già supportato `tau`
  via materiale Radiance `trans` (mappatura semplice per pannelli a vetro
  convenzionali, `tspec=1.0`). Per pannelli organici o thin-film con
  trasmissione diffusa, estendere a materiali `BRTDfunc` o `prism2` con
  taratura sperimentale.

- **Trade-off costo-resa H_min (formulazione B)**: estendere
  `solratio_optimization.py` con funzione di costo strutturale
  `cost(H_min)` parametrizzata su €/m altezza, e ottimizzazione
  `argmax K_agv − λ · cost(H_min)` con lambda configurabile dal foglio
  Parametri.

- **Bifacciale**: estendere il modello per calcolare l'irradianza sulla faccia
  posteriore dei moduli fotovoltaici (per produzione e