# SolRatio — Changelog

## v4.1.0 (2026-05-01) — Prima release pubblica

Versione preparata per pubblicazione open source con DOI Zenodo.
Aggiunte feature applicative (slope L3, trasmittanza pannello, ottimizzazione H_min)
e infrastruttura di rilascio (LICENSE, README, requirements, metadati di citazione).

### Nuove funzionalità

- **Slope L3 — sensori sul piano terreno inclinato + groundplane dinamico**:
  i punti sensore di tutti i profili (centrale, edge, outer) sono ora posizionati
  sul piano terreno reale invece che su z fissa: `z = z0 + x · tan(slope_cross)`.
  La normale del raggio resta verticale (0,0,1) per misurare irradianza orizzontale,
  coerente con la convenzione DLI agronomica. In aggiunta a L1 (axis_tilt/cross_axis_tilt
  propagati a pvlib singleaxis) e L2 (quote per-fila nella scena Radiance).
  Print di diagnostica `Slope L3: sensori sul piano terreno (dz/m=..., z_sensori in [...]m, ground a z=...m)`.
  Per slope_cross negativi (sensori che scenderebbero sotto z=0), il
  `groundplane ring` Radiance viene **abbassato dinamicamente** sotto il sensore
  più basso (margine di 10 cm), evitando il bug per cui i raggi colpirebbero
  il ground orizzontale dal basso restituendo zero.
  *Limitazione residua*: il ground resta geometricamente orizzontale (a quota
  abbassata). Per slope > 15% e applicazioni dove l'albedo riflessa conta,
  l'L3 completo con polygon ground inclinato è in roadmap v4.2.
- **Trasmittanza pannello (`tau`) via materiale Radiance `trans`**: pannelli semitrasparenti
  modellati con materiale Radiance custom. Implementazione: nuova funzione
  `_apply_tau_material()` in `br_engine.py` che, se `tau > 0`, sostituisce il materiale
  opaco di default di bifacial_radiance (`Metal_Grey` o `black`) nel file
  `objects/sr_module.rad` con un materiale `sr_panel_trans` definito in
  `materials/sr_panel_trans.rad`. Mappatura: `trans=tau, tspec=1.0 (vetro), spec=0.05`,
  `R=G=B=1-tau-spec`. Range supportato: `tau=0` (opaco, default — comportamento
  identico a v4.0.0) fino a `tau=1` (trasparente). Calibrato per pannelli a vetro
  convenzionali; per pannelli a film sottile od organici modificare `tspec` < 1.0.
  Da impostare nella cella B23 del foglio Parametri.
- **Ottimizzazione H_min — curva di Pareto**: nuovo modulo
  `engine/solratio_optimization.py` con quattro funzioni pubbliche:
  `optimize_hmin()` (loop esterno sui valori H_min in [0.5, 4.0] m, default step 0.5
  → 8 valori per default, copre da impianti bassi/statici a tracker alti;
  ciascuno → simulazione BR completa via `subprocess` su `calcola_br.py` con
  copia temporanea del progetto Excel a H_min variato; lettura K_agv per coltura
  target dal foglio `Resa_Colturale` del file `risultati_*.xlsx` generato),
  `find_min_hmin_above_threshold()` (ricerca automatica del minimo H_min sopra soglia
  agronomica, con interpolazione lineare tra punti), `write_optimization_excel()` /
  `plot_optimization_curve()` (output Excel + grafico PNG). Disponibile anche come
  CLI standalone: `python engine/solratio_optimization.py <progetto.xlsm> --crop frumento --target 0.95`.
  L'approccio subprocess garantisce coerenza esatta con il flusso normale (zero
  duplicazione di logica K_agv). Sostituisce definitivamente l'ottimizzazione
  del pitch (rimossa: K_agv è monotono crescente con pitch, ottimo banale).

### Cambi di scope

- **Pali rimossi dal flusso v4.1.0**: il trattamento analitico post-shadow dei pali
  (modulo `compute_post_shadow`) è disabilitato in tutti i flussi (Excel, PDF, calcoli).
  Il codice è conservato in stato dormiente (commenti nelle call sites) per facilitare
  la riattivazione in v4.2 con integrazione completa nella scena Radiance 3D
  (cilindri verticali sull'asse tracker).
- **Ottimizzazione pitch rimossa definitivamente**: K_agv è monotonicamente crescente
  con il pitch, l'ottimo è banalmente il pitch massimo testato. Sostituita
  dall'ottimizzazione di H_min, che è il vero parametro di leva agronomica.

### Strumenti di rilascio

- **Orchestratore di release** (`engine/test/release_orchestrator.py` +
  `_LANCIA_RELEASE_TEST.bat`): coordina i check necessari prima di taggare
  una nuova versione. Pipeline a 5 step: (1) pre-flight (ambiente, coerenza
  VERSION↔docstring, import sanità, file rilascio, ORCID), (2) smoke regression
  (run baseline con tau=0/slope=0, confronto con baseline_kagv configurabile),
  (3) feature tests (tau=0.30, slope=10%, optimize_hmin), (4) batteria estesa
  47 test (opzionale, --full), (5) validazione vs BR ufficiale (opzionale,
  --full). Modalità `--quick` (~25 min) o `--full` (~3 ore). Produce
  report Markdown in `analisi/release_report_v<version>_<timestamp>.md` con
  decisione go/no-go ed exit code per integrazione CI/CD.

### Uniformazione K_agv in PERCENTUALE (0-100) ovunque

**Breaking change** rispetto al formato v4.0.x: tutti i valori K_agv mostrati
all'utente (Excel, PDF, console) sono ora espressi in **percentuale 0-100**
invece di frazione 0-1. Internamente il dict `kagv` resta in frazione (per
compatibilità con la formula Y_rel = K_agv × 100), ma TUTTI i punti di
display moltiplicano per 100 prima di scrivere/stampare.

Motivazione: il foglio `Resa_Colturale` di v4.0.x mostrava SAU come "K_agv"
in frazione (es. 0.84) e le altre zone come "Resa %" (es. 88), creando
confusione quando si confrontavano celle di righe diverse. Adesso tutti i
valori sono nella stessa scala (0-100) con etichetta `(%)` esplicita.

Punti modificati:
- `solratio_yield.write_resa_colturale`: SAU mostra K_agv × 100 (label "K_agv (%)"),
  altre zone Resa % invariate. Tutti formato `'0.0'` (1 decimale).
- `solratio_yield.update_resa_with_edge`: K_agv inf/imp × 100, label "K_agv inf (%)",
  "K_agv imp (%)".
- `solratio_pdf.py` PDF report (Pag. 3): tabella K_agv per coltura in %, header
  "K_agv SAU (%)" / "K_agv Centr. (%)", soglie color-coded a 80/100 (era 0.80/1.0).
  Tabella effetto bordo: "K_agv inf (%)", "K_agv imp. (%)", "dK (%)".
- `calcola_br.py` riepilogo console: "K_agv SAU%" e "K_agv Centr%" con format `.1f`.
- `solratio_optimization.py`: `KAGV_TARGET_DEFAULT = 95.0` (era 0.95). Tutte le
  letture/scritture in %. Header Excel "K_agv SAU (%) Mar-Set", grafico con
  asse Y in %, soglia "Soglia 95.0%". Default `--target 95` (era 0.95).
- `release_orchestrator.py` step 2-3: print K_agv in % con format `.2f`.
- Glossario PDF: definizione `K_agv` aggiornata da "0-1" a "%".

Compatibilità con v4.0.x:
- I file `.xlsx` di risultati generati da v4.0.x non sono più letti
  correttamente da `solratio_optimization.py` (leggerebbe SAU come 0.84
  invece di 84.0). Per ri-elaborare progetti v4.0.x rieseguire
  `calcola_br.py` con v4.1.0.

### Comunicazione percentili interannuali

- **Percentili P10/P90 mostrati come "--" in modalità TMY mono-anno**: in v4.x
  la simulazione gira su un singolo anno meteorologico tipo (TMY composito
  mese-per-mese da PVGIS), quindi la distribuzione interannuale ha un solo
  campione e P10/P50/P90 risulterebbero matematicamente identici. Per evitare
  di mostrare informazione ridondante e potenzialmente fuorviante:
  - `compute_monthly_stats()` rileva ora `n_years_m < 2` per ogni mese e
    imposta `p10`/`p90` come array di `NaN` (mantiene `p50` e `mean` validi).
  - `num_cell()` (utility writer Excel) interpreta NaN come stringa `"--"`
    in italico grigio, distinguendola visivamente dai valori numerici reali.
  - Il sottotitolo del foglio `DLI_Percentili` adatta dinamicamente la legenda:
    spiega c