# SolRatio — Changelog

## v4.3.0 (2026-06-11) — Correzione maggiore: scena di tracking contro-ruotata (presente dal v4.1.0)

**La scena Radiance ruotava il pannello dalla parte opposta al sole in ogni
ora di tracking, dal v4.1.0 al v4.2.2.** Un pannello contro-ruotato presenta
al sole un profilo più stretto e proietta un'ombra più piccola: **tutti i
K_agv in modalità tracking delle versioni precedenti sovrastimano la luce al
suolo**. Sui progetti campione il gate passa da 84.1% a **57.5%** (Sample,
N-S) e da 79.2% a **55.3%** (Sample_EW). Il tilt fisso è molto meno
interessato dal difetto (collaudo: 76.3% → 68.7%, residuo dovuto ad
asimmetrie orarie dei dati meteorologici).
Chi ha usato risultati in tracking delle versioni v4.1.0–v4.2.2 deve
rieseguire le simulazioni.

### Perché nessuna validazione lo aveva intercettato

La validazione code-to-code (parte B) costruiva la scena di riferimento con
la *stessa* mappatura theta→azimuth del motore: le due pipeline erano
specchiate allo stesso modo e il confronto era cieco per costruzione. La
prova decisiva è stata fisica e indipendente dalle convenzioni: misura della
larghezza dell'ombra simulata vs formula analitica con angoli pvlib
(faccia-al-sole vs contro-ruotato), confermata da un **riferimento canonico
indipendente** col workflow nativo di bifacial_radiance (`set1axis` →
`analysis1axisground`, angoli calcolati da pvlib dentro la libreria, sensori
posizionati dalla libreria): sul giorno sereno (21/6) il motore storico
sovrastimava il rapporto suolo/GHI giornaliero di **+24.3 punti
percentuali**; sul giorno coperto (21/3, luce quasi tutta diffusa) lo
scarto era +0.6 pp: per questa ragione gli aggregati annui non destavano
sospetti.

### Correzione

- **Scena allineata a pvlib in forma canonica** (la stessa normalizzazione
  di `makeScene1axis`): azimuth di scena **costante** = axis−90° e tilt **con segno**
  −theta (theta>0 = faccia a ovest). Oltre a correggere la contro-rotazione,
  la scena non si ribalta più fra mattina e pomeriggio: file e sensori
  restano nello stesso frame in ogni ora (con nRows pari il ribaltamento
  spostava il contesto di bordo del gap campionato alle ore radenti).
- **Percorso analitico accoppiato** (ombre per VF/fallback e tilt fisso):
  selezione del lato d'ombra dal segno del PSZA pvlib (l'ombra cade dal lato
  opposto al sole) e mezzo-spessore verticale con seno **con segno**.
- **Chiave della cache scene**: tilt con segno + azimuth canonico +
  `sr_compat: 4.3` (tutte le scene pre-correzione sono invalidate).
- **Guida theta_fix nei template**: semantica pvlib (positivo = faccia a
  ovest, negativo = est) — la guida precedente rifletteva la convenzione
  contro-ruotata.

### Rettifica della voce v4.2.2

Il problema noto dichiarato in v4.2.2 (vedi sotto) conteneva **due** errori,
qui rettificati: (1) l'affermazione "gli aggregati simmetrici (incluso il
gate) NON ne risentono" è **vera solo per il tilt fisso e falsa per il
tracking** (la scena non era specchiata ma contro-ruotata: geometria
diversa, non immagine speculare); (2) la diagnosi "il flip del solo azimuth
disallinea i sensori dalle file" era **errata**: il gate a 58.8 misurato
dopo la correzione rifletteva la fisica corretta, non un artefatto (il
valore attuale 57.5 differisce da quel 58.8 perché la correzione definitiva adotta la
forma canonica a azimuth costante, che elimina anche il ribaltamento del
frame mattina/pomeriggio).

### Validazione e riferimenti aggiornati

- Parte B (code-to-code, stessi parametri rtrace): R² = 0.9993 (21/3) e
  0.9999 (21/6) sul Sample (collaudo completo 2026-06-12); ri-esecuzione
  indipendente R² ≥ 0.9975.
- **Nuova parte D**: riferimento canonico `set1axis`/`analysis1axisground`
  nativo (indipendente dalla convenzione di scena del motore) — scarto sul
  K giornaliero suolo/GHI entro 0.5 pp (misure collaudo 2026-06-12:
  −0.3 pp su entrambi i giorni).
- **Corretta anche la mappatura del materiale `trans`** (pannelli
  semitrasparenti, difetto presente dal v4.2.0): il residuo
  1−τ_tot−spec era scritto nel **colore** Radiance, che moltiplica la
  trasmissione → un pannello τ_tot=0.9 trasmetteva ~4% (quasi opaco) e
  rifletteva diffusamente il residuo. Inversione canonica in
  `_apply_tau_material`: trasmissione effettiva = τ+τ_diff esatta;
  chiave cache scene `sr_compat 4.3.1`. I risultati con τ>0 delle
  versioni precedenti non vanno riusati.
- Nuovi riferimenti del gate (±0.2 pp): Sample **57.5**, Sample_EW **55.3**.
  Varianti di collaudo (misure 2026-06-11, riconfermate dal collaudo
  completo 2026-06-12): tilt fisso 68.7, astronomico
  57.4, slope 56.9, bifacciale 57.5, input/ 57.5; col materiale trans
  corretto (2026-06-12): tau=0.2 **59.7**, tau=0.2+tau_diff=0.1 **61.0**
  (col materiale storico erano entrambe 60.2).
  K_agv impianto Cereali C3: Sample 64.9% (l'effetto bordo pesa di più ora
  che il campo interno è più ombreggiato), Sample_EW 63.2%.
- La modalità multi-anno e la batteria dei percorsi d'errore restano
  invariate; tutti i test risultano superati.

### Revisione completa pre-rilascio (5 passate per sottosistema + verifica puntuale)

Prima della pubblicazione della v4.3.0 l'intero codice (~9.500 righe) è
stato sottoposto a nuova revisione; tutti i rilievi sono stati corretti
nella release stessa. I principali (nessuno sposta i riferimenti del gate, ri-misurati
invariati a valle dei fix):

- **Percorso analitico, ombra ovest dei sub-campioni**: il blocco
  anti-aliasing (strategia A) proiettava ancora gli spigoli del pannello
  contro-ruotato (pairing bordi pre-M5 rimasto solo lì: larghezza
  dell'ombra mattutina ridotta di |cos(2·PSZA)|). Il percorso analitico
  non è usato dalla pipeline Radiance di produzione; ora il self-test
  contiene un check A≈B che fallisce con quel pairing (verificato).
- **Normale del terreno inclinato**: segno Y invertito — nullo per assi
  N-S (tutti i casi di collaudo), ring speculare a sensori e file per
  axis_azimuth ruotati (es. E-W) con pendenza trasversale.
- **SAU esterna senza lunghezza file**: B32 compilata con B31 vuota
  mescolava aree per-metro e m² assoluti nel K_agv d'impianto (collassava
  verso il pieno campo): ora errore esplicito alla lettura parametri.
- **TMY e anni parziali (item B2)**: i (anno, mese) con copertura oraria
  incompleta sono esclusi da mediana e selezione (in precedenza pesavano 0 e
  potevano determinare la selezione di un anno errato senza alcuna
  segnalazione); il multi-anno esclude
  gli anni incompleti dai quantili e rifiuta gli EPW parziali.
- **Tilt fisso senza θ_fix (B20)**: ora errore esplicito (in precedenza i
  pannelli risultavano orizzontali senza alcuna segnalazione); modalità tracker etichettata correttamente in
  console anche per B19=0/2.
- **Robustezza**: riscrittura atomica del workbook nel patch dei grafici
  (un crash non corrompe più `risultati_*.xlsx`); cella B43 (CSV PVGIS
  esplicito) onorata nel flusso EPW; timeout su oconv dell'open-sky e
  avviso esplicito sulle ore di riferimento fallite; rimosso il clamp
  legacy sul dz delle repliche in pendenza (file sepolte/sospese per
  pendenze ripide); clamp simmetrico del denominatore d'ombra est;
  validazione B48-B50; CSV vecchio formato → errore chiaro.
- **Coerenza di presentazione (item B13)**: K_agv in formato percentuale
  anche in Riepilogo ed Effetto_Bordo (prima frazione 0.575 e percento
  57.5 convivevano nello stesso workbook); banner metodologico del foglio
  Profilo_PAR_Spaziale aggiornato al ray-tracing (citava la formula
  view-factor del motore v3); testi PDF allineati al modello reale
  (PAR_FRAC variabile Jacovides, materiale trans in scena, modalità
  tracker); decomposizione aree del foglio Effetto_Bordo a n_file−1
  strisce come il calcolo (M6); avviso E-W calcolato sulla retta N-S
  (mod 180); nota esplicita sul guadagno bifacciale costante per
  costruzione (modello proxy dichiarato).
- **Item B12 chiuso**: la handedness della pendenza trasversale è stata
  ricontrollata su scena, sensori, repliche e percorso analitico — tutte
  coerenti (l'unica eccezione era la normale del ring, sopra). Il
  self-test ora la verifica in modo stringente (nuovo check handedness
  slope), insieme alla
  direzione assoluta dell'ombra con θ≠0 (esclude la convenzione
  contro-ruotata) e all'equivalenza fra strategia oraria e sub-campioni.

### Record Zenodo delle versioni precedenti

I depositi v4.2.0 (10.5281/zenodo.20277335) e v4.2.1
(10.5281/zenodo.20642574) restano immutabili come da policy Zenodo; una
nota di correzione sul record rimanda a questa release. Il DOI di versione
della v4.3.0 viene coniato al deposito.

## v4.2.2 (2026-06-11) — Revisione approfondita dell'engine: 14 correzioni + 1 problema noto documentato

> **⚠ RETTIFICA (v4.3.0)**: il problema noto in fondo a questa voce è
> formulato in modo **errato**. La scena non era uno specchio est/ovest ma
> era **contro-ruotata** rispetto al sole; gate e aggregati in tracking
> **erano** interessati dal difetto (sovrastimati di ~20–27 pp sul
> collaudo) e il revert del fix fu una diagnosi sbagliata. Vedi la voce
> v4.3.0.

Revisione sistematica post-pubblicazione (tre passate indipendenti su
pipeline, fisica e I/O, con prova sperimentale di ogni finding prima del
fix). **Il gate di regressione e tutti i K_agv SAU sono invariati**
(84.1 / 79.2 e tutte le varianti di collaudo identiche al decimale);
cambia il K_agv di impianto (effetto bordo): sul progetto Sample
87.2% → 86.9% per Cereali C3.

### Correttezza fisica

- **Aspetto del terreno in pendenza**: l'aspetto di un piano che scende
  verso D è D stessa; il +180° storico calcolava un pendio esposto a sud
  come esposto a nord (verificato con pvlib: beam 160 vs 271 W/m² a
  mezzogiorno invernale). Interessava la decomposizione Perez su piano
  inclinato e il beam della fascia esterna.
- **Angolo di profilo trasversale (fascia esterna)**: la proiezione
  usava |cos(γ−asse)| (= componente longitudinale) al posto di
  |sin(γ−asse)|: con sole a est su file N-S l'ombra trasversale risultava
  ~0 e massima a mezzogiorno — esattamente invertito (contraddiceva il
  percorso ombre principale, già basato su pvlib PSZA).
- **Aggregazione K_agv di impianto**: fra n_file file esistono n_file−1
  strisce di pitch (una striscia era contata due volte); curve di Laub
  applicate punto-per-punto anche a bordo e fascia esterna (la curva è
  concava: applicarla alla PAR media sovrastimava di 0.5–2 pp); distanza
  d_NS della correzione longitudinale ora pesata sul DNI (la media
  aritmetica era dominata dalle code 1/tan(alfa) di alba/tramonto senza
  beam).
- **TMY e 29 febbraio**: la rinormalizzazione dell'anno avveniva prima
  della rimozione del 29/02 → crash (riprodotto con i dati del Sample
  ristretti al 2018-2020); ora il 29/02 è filtrato a monte e un TMY
  diverso da 8760 ore è un errore esplicito.

### Robustezza e cache

- Un'ora rtrace anomala (timeout/output malformato) non abortisce più
  l'intera simulazione (conta come errore di quell'ora).
- Cache scene: tau_diff entra nella chiave (in precedenza un octree con
  materiale obsoleto veniva riusato senza alcuna segnalazione); bbox estesa con terreno
  inclinato (il ring del terreno usciva dal boundary → 100% errori sulle
  ore cache-hit); soglia del test semantico adattiva alla trasmittanza
  (i pannelli semitrasparenti venivano erroneamente classificati come
  "scena senza geometria").
- find_pvgis_csv: con coordinate note si accetta solo il match esatto
  (il fallback restituiva il CSV di un **altro** sito dopo un cambio di
  coordinate, senza alcuna segnalazione).
- Validazione code-to-code: modalità tilt fisso ora confrontata a parità
  di geometria (la pipeline di riferimento inseguiva il sole); il cielo
  di fallback viene registrato nell'octree (prima l'ora usava il cielo
  dell'ora precedente, sommato in silenzio).

### Display e documentazione

- Formati percentuale Excel con i decimali giusti (23.4% e non 23.0%);
  tau_diff e fattore di bifaccialità dichiarati nel Riepilogo e nel PDF
  quando attivi; il PDF non dichiara più parametri rtrace fissi; rimosso
  un ramo morto che citava un foglio non più esistente; etichette del
  foglio Effetto_Bordo con i riferimenti di cella corretti (B30-B32);
  messaggio errato "tau non supportato" eliminato; CLI multi-anno
  case-insensitive; FORMULE.md riconciliato col codice (curve di Laub
  log-quadratiche; coefficienti PAR_FRAC implementati: 0.500-0.082·kt
  con clip [0.42, 0.48] — la nota dichiarava una variante non
  implementata).

### Problema noto documentato (non corretto in questa release)

- **Specchio est/ovest della scena**: la mappatura storica theta→azimuth
  della scena è speculare rispetto alla convenzione pvlib (provato
  sperimentalmente: con tilt fisso verso ovest l'ombra larga compare al
  mattino anziché al pomeriggio). Scena, sensori al suolo e percorso
  analitico sono però co-progettati su questa convenzione: gli aggregati
  simmetrici (incluso il gate) NON ne risentono, mentre l'attribuzione
  oraria est/ovest è scambiata. Un tentativo di correzione del solo
  azimuth disallinea i sensori dalle file (gate 84.1 → 58.8, misurato):
  il riallineamento richiede il redesign accoppiato scena+sensori ed è
  pianificato come intervento dedicato. Si raccomanda cautela interpretativa
  con pendenza trasversale e regimi meteorologici asimmetrici mattina/pomeriggio.

## v4.2.1 (2026-06-11) — Reference edition: potatura al minimo riproducibile + fix

> ⚠ **Avvertenza retrospettiva**: i K_agv in modalità **tracking** di questa
> versione (incluso il gate 84.1/79.2) sono **sovrastimati** per la scena
> contro-ruotata, corretta in v4.3.0. Non riutilizzarli.

Edizione di riferimento citabile: il perimetro è ridotto al "minimo
riproducibile" (pipeline core + validazione + sentinella + esempi), con fix
limitati a ciò che resta. Ogni rimozione è elencata sotto per trasparenza
verso chi usava v4.2.0 (che resta taggata e depositata su Zenodo).

### Rimozioni (codice E output)

- **Analisi di sensitività**: `solratio_sensitivity.py`, fogli
  `Sensitivita_OAT`/`Sensitivita_Morris`, pulsante e Sub VBA dedicati.
- **Tooling di release/QA del maintainer**: `release_helper.py`,
  `_NUOVA_VERSIONE.bat`, `orchestratore_sweep.py`, `plot_profilo_pitch.py`,
  `migrate_project_layout.py`, `engine/test/` (la batteria dipendeva da
  `progetti/test_battery`, mai pubblicato), `_patch_button_label.py`,
  `_test_slope_battery.py`, launcher .bat relativi, `analisi/`,
  `documentazione/PIANO_v4.2.md`.
- **Percorso pali (dormiente dal v4.1.0)**: `compute_post_shadow`,
  `compute_post_impact`, `write_impatto_pali`; il foglio `Impatto_Pali`
  non veniva comunque scritto. Le celle B21/B22 del foglio Parametri non
  sono più lette.
- **Ottimizzazione pitch (inerte)**: `optimize_pitch` e
  `write_pitch_optimization` non avevano alcun chiamante; il parametro
  B45 (`ottimizza_pitch`) non è più letto.
- **Ottimizzazione H_min** (`solratio_optimization.py`, CLI standalone):
  rimossa dall'edizione di riferimento per decisione di perimetro — è
  una funzionalità di supporto alla progettazione, fuori dallo scope
  "minimo riproducibile citabile". La curva K_agv(H_min) resta
  riproducibile manualmente variando B17 tra run successivi.
- **Fogli diagnostici** non descritti dalla technical note né necessari
  alla sentinella: `Calcolo_Solare`, `PAR_RayTracing`, `Profilo_fdir_VF`,
  `Variabilita_DLI`, `DLI_Annuale`, `Riduzione_PAR`, `Validazione_pvlib`.
  Fogli prodotti ora: Riepilogo, Parametri, PAR_DLI_Profilo,
  Profilo_PAR_Spaziale, DLI_Percentili, Heatmap_PAR, Resa_Colturale,
  Effetto_Bordo (+ Bifacciale se `bifaciality_factor > 0`).

### Fix

- **Header EPW dichiara UTC (F1)**: i CSV PVGIS sono UTC ma l'header
  LOCATION dichiarava `round(lon/15)` (=+1 in Italia) → posizione solare
  ~40 min in anticipo sulle irradianze. Effetto misurato sul gate
  (Cereali C3, media Mar-Set): Sample N-S 84.0 → **84.1** (+0.1 pp),
  Sample_EW 79.3 → **79.2** (−0.1 pp); ore diurne simulate 3995 → 3919.
- **Linux: CWD ripristinata dopo la fase ray-tracing**: bifacial_radiance
  fa chdir nella work dir temporanea; alla sua cancellazione il processo
  restava senza directory corrente e la generazione del PDF falliva
  (`import reportlab` → `os.getcwd()`): su Linux il PDF non veniva **mai**
  prodotto. Stesso ripristino nella fase "BR ufficiale" di
  `validazione_br.py` (processi multi-run) + cattura difensiva.
- **Cache scene .oct self-contained (`oconv -f`)**: la scena cachata era
  compilata senza freeze, quindi il riuso in un run successivo richiedeva
  i radfile originali della temp dir (cancellata) → 100% errori rtrace.
  Era la causa radice del bug della cache annotato nella roadmap v4.2.x.
  `CACHE_FORMAT_VERSION` 1→2 (le cache esistenti si rigenerano da sole);
  errore chiaro se zero ore simulate (prima un IndexError criptico).
- **Formato numerico Excel `'0.1'` → `'0.0'`** (11 celle del writer): in
  ECMA-376 l'`1` è un letterale, Excel mostrava l'intero arrotondato
  + ".1" (es. 29.62 → "30.1").
- **PDF "Backtracking: ON" anche in tilt fisso** (`bool(2)`): ora mappa
  a 3 valori identica al foglio Riepilogo.
- Colore della media Mar-Set in Resa_Colturale: doppio ×100 (sempre verde).
- `read_parameters`: GCR/SAU calcolati dopo la validazione (cella vuota →
  messaggio chiaro, non TypeError); avviso sui valori non interpretabili;
  range check `beta_max ∈ (0, 90]`; foglio Parametri mancante → errore
  chiaro. Copia del foglio Parametri senza `max_row=49` hardcoded;
  guardia su GHI annuo nullo. Multiyear: timestamp sintetici di fallback
  su anno non bisestile (col 2020 i mesi si sfalsavano dopo il 29/02).
- **Attribuzione**: footer PDF → Stefano Pesavento, PhD (ORCID
  0009-0008-0720-4539); l'attribuzione precedente era errata.

### Progetti e sentinella

- Aggiunto `progetti/Sample_EW/` (variante E-W, `axis_azimuth=90`),
  promesso da README e technical note ma mai pubblicato; gli smoke
  storici vi puntavano (erano quindi non eseguibili da un clone).
- Smoke di regressione ridefinito: `_smoke_regression.bat` (Windows) e
  `_smoke_regression.sh` (Linux/macOS) vengono eseguiti su **entrambi** i progetti;
  riferimenti v4.2.1: N-S 84.1, E-W 79.2, tolleranza ±0.2 pp (la
  dicitura "bit-per-bit" è stata rimossa: l'ambient sampling di Radiance
  è stocastico).
- Igiene: rimossi path personali dalle celle/commenti (xlsm, .bas,
  .gitignore); EPW dei progetti rigenerati con header UTC.

### Template e fogli di output (rifinitura da collaudo)

- Foglio Parametri: etichetta SANU riscritta ("fascia non coltivata per
  lato, lungo ogni fila" — quella storica suggeriva il perimetro del
  campo); righe dei parametri non modellati (d_palo, spaziatura pali,
  ottimizza pitch) **svuotate** (non eliminate: la lettura è per indirizzo
  di cella); aggiunte le righe-etichetta per i parametri opzionali
  B25 (tau_diff) e B26 (fattore bifaccialità), che il motore leggeva
  ma il template non esponeva.
- Fogli `Profilo_PAR_Spaziale` e `PAR_DLI_Profilo`: titoli, banner e
  intestazioni di colonna ora generati dal codice (prima erano demandati
  a un template di formattazione non distribuito: i dati apparivano
  senza intestazioni).
- vbaProject degli xlsm rigenerato in sessione Excel (moduli reimportati
  dai .bas ripuliti, pulsanti rigenerati senza "Analisi Sensitivita",
  foglio Sensitivita_Config eliminato); Launcher!B3 vuota (il percorso
  Python viene rilevato automaticamente al primo uso).

### Note

- La technical note allineata a questa edizione è in preparazione
  (deposito Zenodo con DOI gemello).
- Il foglio `Sensitivita_Config` e i pulsanti legacy negli xlsm esistenti
  si rimuovono riaprendo il file in Excel e reimportando i moduli VBA
  aggiornati (i pulsanti sono rigenerati dalla macro `AggiungiPulsanti`).

## v4.2.0 (2026-05-05) — Multi-anno, frame coord ruotato, bifacciale, BRTDfunc, cache scene .oct

> ⚠ **Avvertenza retrospettiva**: i K_agv in modalità **tracking** di questa
> versione sono **sovrastimati** (scena contro-ruotata, corretta in v4.3.0);
> inoltre il materiale `trans` qui introdotto era quasi opaco (mappatura
> corretta in v4.3.0): i risultati con τ>0 non vanno riusati.

Release minor che chiude lo scope v4.2 (9 item) come pianificato in
`PIANO_v4.2.md` (file rimosso in v4.2.1). Per decisione di pianificazione del 2026-05-02 i pali
sono stati spostati dalla v4.2 alla v4.3 e i 3 item v4.3 originali sono stati anticipati
in v4.2 (con scope ridotti, rispettivamente α e β). Trade-off costo H_min spostato
a v4.4.

### Nuove funzionalità

**Item 8 — Auto-update label versione Excel via VBA**:
Aggiunto modulo `engine/SolRatio_VersionLabel.bas`. Macro
`UpdateVersionLabelFromFile()` legge `engine/VERSION` (con fallback
fino a 4 livelli sopra il file Excel) e aggiorna la cella `A1` del
foglio `Launcher` come `"SOLRATIO AGRIVOLTAICO - Launcher vX.Y.Z"`.
Da chiamare da un `Workbook_Open()` in `ThisWorkbook` (una sola riga
da aggiungere — istruzioni in `progetti/Sample/README.md`). Fallisce senza
segnalazione se VERSION non è raggiungibile, idempotente, nessuna richiesta "Salvare?".

**Item 6 — Script di release end-to-end**:
Aggiunto `engine/release_helper.py` (CLI con subcommand `bump`,
`bump-from-changelog`, `update-doi`, `status`) e
`_NUOVA_VERSIONE.bat` come orchestratore. Pre-check git pulito, dry-run
supportato, sorgente unica di verità nel CHANGELOG. Riduce la procedura
manuale di rilascio da ~30 min a ~5 min con interventi dell'utente di ~2 min.
Polling Zenodo + auto-DOI rinviato a step incrementale (manuale per ora).

**Item 4 — Cache scene `.oct` persistente**:
Aggiunto modulo `engine/_scene_cache.py` con API `make_cache_key`,
`lookup`, `store`, `housekeeping`. `br_engine.run_annual()` accetta
ora `use_scene_cache=True` (default) e `project_dir`. La cache pre-compila
una volta per progetto+geometria un .oct di scena (matfiles+radfiles, no
sky); per-ora il `_worker` usa `oconv -i scene.oct sky.rad` invece del
full oconv. Accelerazione attesa del 30-60% sul tempo per ora dopo il primo run.
Per sicurezza: in caso di errore della cache si applica il flusso legacy.
Storage: `<progetto>/.cache/scenes/`, housekeeping a 20 file per progetto.

**Item 7 — Generalizzazione frame coordinate sensori per `axis_azimuth`**:
Refactor in `br_engine.py` e `validazione_br.py`. I sensori sono ora
posizionati in un frame locale `(u, v, w)` ancorato al tracker e
trasformati in coordinate mondo via `phi = axis_azimuth - 180°`.
L'azimuth della scena Radiance è calcolato come
`(axis_azimuth + (-90 if theta>=0 else +90)) % 360`. Per
`axis_azimuth=180°` (default storico N-S) il comportamento è
**bit-per-bit identico** alla v4.1. Per qualsiasi altro `axis_azimuth`
(E-W, NE-SW, ecc.) la scena e i sensori sono coerenti tra loro.
Aggiunto warning agronomico in `solratio_yield.py` se
`|axis_azimuth - 180°| > 30°`: le curve di Laub et al. 2022 sono
calibrate su regimi di ombreggiamento N-S e l'applicazione a configurazioni
E-W è scientificamente delicata.

**Item 3 — Slope L2 e L3 anticipati in v4.2.0**:
Il fix del wrapper L2 (replica multi-fila per slope_cross != 0) e del
groundplane L3 (groundplane realmente inclinato) sono stati portati
dentro v4.2.0 invece che rimandati a v4.2.x.

- *L2 axis_azimuth-aware*: l'offset di replica delle file vicine usa ora
  `_local_to_world(_dx)` per trasformare il `_dx` (passo perpendicolare
  al tracker, in coord. locale) in `(dx_world, dy_world)` coerente con
  `axis_azimuth`. Per `axis=180°` la trasformazione è identità. Per altri
  axis, la replica è nel frame ruotato. Rimosso l'avviso a runtime
  precedente (limitazione superata).

- *L3 groundplane inclinato*: il groundplane Radiance non è più orizzontale
  a quota dinamica `_ground_z`, ma un ring inclinato passante per
  l'origine con normale ruotata di `slope_cross_rad` attorno all'asse del
  tracker (formula di Rodrigues):
  `n = (-cos(phi)·sin(slope), -sin(phi)·sin(slope), cos(slope))`.
  I sensori a `z = z0 + v·tan(slope_cross)` restano per costruzione 5cm
  sopra il piano inclinato in ogni posizione, quindi non c'è più bisogno
  del workaround `_ground_z = min(-0.01, z_min_sensors - 0.10)`. Per
  `slope_cross=0` il ring resta orizzontale a `z=-0.01` (bit-per-bit v4.1).

**Item 5 — Layout cartella progetto standardizzato (versione additiva)**:
Aggiunta `find_pvgis_csv(project_dir, lat, lon)` in `br_engine.py` con
fallback ricerca: prima `<progetto>/`, poi `<progetto>/input/`. Aggiunto
script `engine/migrate_project_layout.py` che sposta i file PVGIS in
`input/` e i risultati in `test/` (con `--dry-run` e `--rollback`).
Il bump completo dei path output (`solratio_optimization.py`,
`validazione_br.py`, `calcola_br.py`, VBA Launcher) rimane in v4.2.0
**non ancora applicato** (per non rompere progetti esistenti senza
migrazione esplicita); è previsto come step incrementale v4.2.x dopo
test su progetti reali. I progetti possono già adottare il layout v4.2
(spostando i file in `input/`) e le letture PVGIS continueranno a funzionare.

**Item 2 — Modalità multi-anno + P10/P50/P90 (strategia A)**:
Aggiunto `engine/solratio_multiyear.py`. Orchestrator sequenziale
con flag CLI `--years tmy|all|2010,2015,2020|3`. Per ogni anno richiesto
genera un EPW da PVGIS multi-anno e chiama `run_annual()`. Salvataggio
incrementale a `<progetto>/test/multiyear_results.csv`: il rilancio
riprende dagli anni non ancora completati (resilienza a crash). Aggrega
P10/P50/P90 + media + stddev per ogni KPI numerico in
`<progetto>/test/multiyear_quantiles.json`. Nessuna parallelizzazione
in v4.2.0 (bifacial_radiance/Radiance non sono progettati per il multi-thread
in-process: rinviata a v4.2.x in caso di collo di bottiglia).

**Item 9 — Pannelli BRTDfunc (scope α)**:
`_apply_tau_material()` accetta ora `tau_diff` opzionale (default 0).
Mappatura sul materiale Radiance `trans`: `trans = tau + tau_diff`,
`tspec = tau / (tau + tau_diff)`. Con `tau_diff = 0` la mappatura è
**bit-per-bit identica** alla v4.1.0 (`tspec = 1.0`). Con `tau_diff > 0`,
parte della trasmissione è diffusa Lambert (utile per pannelli
organici o thin-film). `run_annual()` legge `p['tau_diff']` da
parametri (default 0). Le estensioni `prism2` e BSDF `.xml` (scope β/γ
originali) sono rinviate a v4.5+.

**Item 11 — Bifacciale energia PV (scope β)**:
Nuovo modulo `engine/solratio_bifacial.py`. Funzione `bifacial_yield(p,
br_result, module_efficiency, bifaciality_factor)` calcola
`POA_total = POA_front + bifaciality_factor × POA_back` e produzione PV
annua. Default `bifaciality_factor = 0` (monofacciale, retrocompatibile
bit-per-bit). Funzione `add_bifacial_to_excel()` aggiunge un foglio
"Bifacciale" al workbook risultati.

Limitazione v4.2.0: POA_back è stimato semplificato come `0.5 × albedo
× GHI` (view factor standard tracker). Il calcolo Radiance dedicato
con sensori dietro i moduli è rinviato a v4.2.x. La produzione PV usa
una formula moltiplicativa POA × η × ore senza propagazione di
temperatura modulo, perdite di sistema, soiling. Estensione PVWatts-like
+ LCOE in v4.4 (Economia).

### Refactor architetturali

- Frame coordinate sensori (item 7) richiede aggiornamento parallelo
  in `br_engine.py` e `validazione_br.py`. La pipeline di validazione
  vs BR ufficiale resta coerente.
- ROADMAP riorganizzata: v4.2 / v4.3 (Pali) / v4.4 (Economia). Vedi
  `documentazione/ROADMAP.md` e `documentazione/PIANO_v4.2.md` (quest'ultimo
  rimosso in v4.2.1; la roadmap attuale è quella open-core).

### Tool nuovi v4.2.0

**Orchestratore sweep parametrico H_min × axis_azimuth**
(`engine/orchestratore_sweep.py` + `_lancia_sweep.bat`):
sweep 2D che riusa `optimize_hmin` modificando ortogonalmente cella B14
(axis_azimuth) e B17 (H_min) dell'xlsm. Output incrementale dopo ogni
axis_azimuth (resume robusto via `--resume <timestamp>`):
`results.csv` long-format, `heatmap_kagv.png`, `curves_kagv.png` (famiglia
parametrica), `per_azimut/azimut_<XXX>.csv`, `log.txt`. Default griglia
9 H_min × 5 azimuth = 45 run × ~100s ciascuno. Validato su Sample_EW:
emerge che axis E-W (~90°) penalizza il K_agv SAU di ~4.5pt vs N-S, e
H_min ha impatto marginale sul SAU ma forte sull'uniformità Centrale↔Bordo.

**Plot profilo PAR(x/pitch)** (`engine/plot_profilo_pitch.py`): legge il
foglio `Heatmap_PAR` di `risultati_*.xlsx` e genera un PNG a doppio
pannello (curve mensili + media Mar-Set | heatmap mese × posizione) con
bande verticali colorate per le 4 zone (Sotto-tracker, Bordo, Centrale,
Bordo, Sotto-tracker) calcolate da W e beta_max.

### Cosmetica

- **Label pulsante Excel "Ricalcola"**: il pulsante BtnCalcola del foglio
  Launcher è stato semplificato da `"Ricalcola con BR vX.Y.Z"` a
  `"Ricalcola"` (più stabile rispetto al numero di versione e meno prolisso). Modifiche:
  `engine/SolRatio_Calcolo.bas` (sorgente VBA) + script
  `_patch_button_label.py` per applicare il fix in-place al
  `drawing1.xml` di tutti gli `xlsm` esistenti senza richiedere
  re-import del modulo VBA.

### Rinvii e limitazioni

- **Item 1 (Pali nella scena Radiance)**: spostato a v4.3 per decisione
  di pianificazione. Codice dormiente conservato, call sites commentate.
- ~~**Item 3 (Ground plane inclinato L3 completo)**~~: anticipato e
  completato in v4.2.0 (vedi sezione "Slope L2 e L3 anticipati" sopra).
- **Item 10 (Trade-off costo H_min, formulazione B)**: spostato a v4.4
  per decisione di pianificazione. v4.4 sarà la prima release "economica" con
  trade-off + LCOE.

### Cache scene .oct — fix definitivo completato (2026-05-05)

Lo smoke test di `validazione_br` su `Sample_EW` (axis_azimuth=90°,
10 ore = 10 unique tracker_theta → cache attiva) ha prodotto
`rtrace 100% errori`. Indagine sui file scene_*.oct cached ha rivelato
dimensione **esattamente 1.194 byte identica** per tutti i 10 octree:
sintomo di octree con materiali ma senza geometria. Diagnostica iterativa
ha identificato la causa root e portato a un fix robusto.

**Causa root identificata**: il radfile generato da `bifacial_radiance`
contiene `!xform "objects/sr_module.rad"` (comando shell inline). Il file
referenziato a sua volta contiene `!genbox black sr_module ... | xform ...`
(comando shell con pipe). Quando oconv viene lanciato via `subprocess.run`
con `stdin=DEVNULL` su Windows, la **cascata di popen annidato**
(`oconv → popen(xform) → popen(genbox|xform)`) **fallisce silenziosamente**
(rc=0, no stderr, ma scene.oct degenere). Il flusso legacy v4.1 funziona
perché bifacial_radiance usa `_popen(stdin=PIPE)` interno, non
`subprocess.run(stdin=DEVNULL)`.

**Fix applicato in `br_engine.py`** (3 layer):

1. **Pre-flatten dei file modulo**: prima del loop pre-compile, per ogni
   file referenziato da `!xform` (es. `sr_module.rad`), invochiamo
   `xform` standalone (single-popen, funziona su Windows) e sovrascriviamo
   il file con il suo output flat (polygon puri, no più shell command `!`).

2. **Pre-flatten dei radfiles principali**: nel loop pre-compile, per ogni
   radfile sr4_xxx.rad, parsiamo manualmente le righe `!xform ...` ed
   eseguiamo `xform` come comando shell standalone, scrivendo nello stesso
   file un blocco di polygon flat con header materiali (`void plastic black`
   + `void glass stock_glass`). Questo elimina TUTTI i comandi shell `!`
   dal radfile passato a oconv.

3. **Bbox forzata via `oconv -b -100 -100 -1 200`**: il radfile flat passato
   a oconv produce un octree con bbox locale ai pannelli (~30m). Il `sky.rad`
   del worker iniettato via `oconv -i scene.oct sky.rad` contiene
   `groundplane ring 100m` → senza bbox forzata, oconv -i fallisce con
   `boundary does not encompass scene`. Il flag `-b` impone bbox 200m
   centrata sull'origine, sufficiente a contenere sia pannelli che
   groundplane.

**Validazione semantica via rtrace di test (C-pure)**: la soglia bytes
hardcoded sull'oct cached non è affidabile (~1.4KB per 24 polygon con
materiale `black` compatto). Sostituita con verifica funzionale: per ogni
scene.oct cached il pre-compile esegue `oconv -i scene.oct sky_test.rad`
(sky con sole zenit DNI=500) seguito da `rtrace` su un raggio verticale al
centro pannello. Se IRR_test < 100 W/m² (factor 5 sotto open-sky), il
pannello sta bloccando → cache valida. Altrimenti la scena è degenere e
il worker cade sul flusso legacy (fail-safe).

**Warning differenziati** sui fallimenti del pre-compile per facilitare
diagnosi di future regressioni: contatori separati `_n_skip_oconv`,
`_n_skip_rtrace`, `_n_skip_geom` con stampa dettaglio del primo errore di
ogni categoria.

**Verifica post-fix** (Sample_EW, axis=180°, validazione_br):

- Pre-compile: 0 hit + 10 built + 0 skip in 0.9s (era 10 skip prima)
- Worker: 10/10 ore simulate, 0 errori (era 100% errori)
- MBE vs BR ufficiale: +0.3% (21/3) e -0.1% (21/6)
- R² vs BR ufficiale: 0.97 (21/3) e 1.0000 (21/6)
- Sweep 45 run × ~100s = 75min totali (vs 180min stimati senza cache)

**Soglia `_CACHE_MAX_THETAS = 200`**: cache attiva solo per N_thetas
unici ≤ 200 (validazione_br, single-day, tilt fisso). Per il flusso
annuale tipico (3000+ thetas), il pre-compile sarebbe più lento del
beneficio netto e la cache viene automaticamente saltata.

### Fix di runtime (2026-05-04 — release_orchestrator step 3a)

**UnicodeEncodeError su `tau>0`.** Il commento del file Radiance
materiale custom (`materials/sr_panel_trans.rad`) conteneva il carattere
greco `α` (U+03B1) per indicare lo "scope α" del BRTDfunc. Su Python 3.14
Windows, `open(..., 'w')` di default usa cp1252, che non contiene `α` →
`UnicodeEncodeError` ogni volta che si attiva un calcolo con `tau>0`.
Lo step 2 del release_orchestrator (smoke regression con tau=0) passava
perché `_apply_tau_material` ritornava prima di scrivere il file. Step
3a (tau=0.30) lo attivava → crash mascherato dal traceback secondario
sempre in cp1252 al print del traceback originale.

Patch applicata in `br_engine._apply_tau_material`:

- Sostituito `α` con `alpha` nel commento (solo ASCII nei .rad scritti).
- Aggiunto `encoding='utf-8'` esplicito a `open(mat_file, 'w')` per
  evitare ricomparsa del problema con altri caratteri Unicode in futuro.
- Aggiornato il print runtime BRTDfunc da `α` a `alpha` per coerenza.

### Fix di runtime (2026-05-03 — primo smoke test su Windows)

**Cache scene auto-disattivata per N_thetas grandi.** Lo smoke test sul
Sample ha rivelato che `tracker_theta` da pvlib viene prodotto a
precisione float (e.g., 0.001°) → ogni ora di simulazione ha un theta
unico → 3929 thetas unici sul Sample annuale. Il loop di pre-compile
chiama `oconv` 3929 volte sequenzialmente. Stima ~0,3-1s per chiamata
(I/O su `<progetto>/.cache/scenes/` in OneDrive con sync cloud che
serializza le scritture), totale 20-60+ minuti di pre-compile prima
che il run vero parta. Aggravante: ogni .oct di scena (~1-3 MB)
moltiplicato per 3929 comporta alcuni GB scritti su OneDrive.

Patch applicata in `br_engine.py`: soglia automatica `_CACHE_MAX_THETAS=200`.
Sopra questa soglia il cache pre-compile viene **saltato** e il worker
torna al flusso legacy v4.1 (full `oconv matfiles + sky + radfiles` per
ora). Comportamento bit-per-bit identico a v4.1 quando N_thetas > 200.

La cache continua a essere efficace nei casi originariamente previsti
(es. simulazione single-day con tracker fixed-tilt → 1 theta unico,
oppure profili con `theta_fix=N`). Per il flusso annuale tipico la
cache è di fatto disattivata in v4.2.0 — funzionalità rimandata a v4.2.x
con tre possibili soluzioni alternative:

1. Round `tracker_theta` a 0.1° prima di calcolare unique_thetas
   (riduce a ~600 buckets, errore numerico <0.05% sui K_agv).
2. Cache lazy nel worker invece di pre-compile sincrono (ogni ora che
   produce un .oct nuovo lo salva, runs successivi lo riutilizzano).
3. Spostare la cache fuori da OneDrive (es. `%LOCALAPPDATA%\SolRatio\
   cache\<project_hash>\`) per evitare il throttling del sync cloud.

### Fix di review (2026-05-03 sera)

Review completa post-implementazione ha identificato e corretto 3 gap di
integrazione:

1. **`find_pvgis_csv` non era usata da `calcola_br.py`** (la pipeline
   principale): il layout v4.2 con `input/` di fatto NON funzionava col
   flusso standard. Patch: sostituita la `os.listdir(proj_dir)` legacy
   con `find_pvgis_csv(proj_dir, lat, lon)`.

2. **`find_pvgis_csv` non era usata da `validazione_br.py`**: stesso
   problema. Patch identica al punto 1.

3. **`solratio_bifacial.py` era codice morto**: il modulo era stato creato ma
   nessuno lo importava né lo richiamava. Patch: aggiunto in `calcola_br.py`
   un'importazione condizionale + chiamata a `bifacial_yield` +
   `add_bifacial_to_excel` quando `p['bifaciality_factor'] > 0`. Con
   `bifaciality_factor = 0` (default), il blocco `try/except` non viene
   eseguito → comportamento bit-per-bit identico a v4.1.

Aggiunte inoltre validazioni esplicite a livello di lettura Excel
(`solratio_excel.py / read_parameters`):

- `tau_diff` deve essere in [0, 1] (cella B25)
- `tau + tau_diff` deve essere ≤ 1 (vincolo fisico)
- `bifaciality_factor` deve essere in [0, 1] (cella B26)

Errori espliciti su questi vincoli con messaggio sulla cella problematica.

### Test e validazione raccomandati prima del tag definitivo

Le seguenti verifiche sono raccomandate prima del tag definitivo
`v4.2.0` (alcune richiedono Radiance + bifacial_radiance installati
sull'ambiente Windows del rilascio):

1. **Regressione bit-per-bit** sul Sample (lat 45.30°N, lon 9.34°E):
   con `axis_azimuth=180°`, `tau_diff=0`, `bifaciality_factor=0`,
   `use_scene_cache=False` → K_agv SAU = 84.00% atteso (identico a v4.1.2).
2. **Regressione cache scene**: con `use_scene_cache=True` e cache vuota
   il primo run produce cache, il secondo run sullo stesso progetto
   deve dare K_agv identico bit-per-bit + tempi/ora ridotti del ≥30%.
   Nota v4.2.0: cache attiva solo per N_thetas ≤ 200 (validazione_br
   single-day, tilt fisso). Per il flusso annuale tipico (~3900 thetas)
   la cache è automaticamente saltata e il worker usa il flusso legacy
   bit-per-bit identico a v4.1.
3. **Validazione frame coord**: rilanciare `release_orchestrator.py
   --quick` con `axis_azimuth ∈ {180°, 90°, 135°}` → atteso MBE<1% R²>0.99
   in tutti i casi.
4. **Multi-anno smoke**: `python engine/solratio_multiyear.py
   "progetti/Sample/SolRatio_progetto.xlsm" --years 3` → 3 anni
   completati + quantili coerenti (P10 < P50 < P90).
5. **BRTDfunc retrocompat**: con `tau_diff=0` deve dare risultati
   identici a v4.1.2 sullo stesso progetto.
6. **Bifacciale retrocompat**: con `bifaciality_factor=0` deve produrre
   `energy_total = energy_front` e `bifacial_gain = 0%`.
7. **Sintassi `engine/*.py`**: alcune modifiche sono state verificate
   soltanto mediante ispezione visiva, a causa di limitazioni dell'ambiente
   di sviluppo. Si raccomanda di eseguire il seguente controllo di sintassi
   prima del tag:
   `python -c "import ast; [ast.parse(open(f).read()) for f in
   ['engine/br_engine.py','engine/release_helper.py',
   'engine/_scene_cache.py','engine/migrate_project_layout.py',
   'engine/solratio_multiyear.py','engine/solratio_bifacial.py',
   'engine/validazione_br.py','engine/solratio_yield.py']]"`

Smoke regression + i test 1, 5, 6 dovrebbero passare automaticamente
grazie al disegno retrocompatibile (default identici a v4.1.2). I test
2, 3, 4 richiedono validazione manuale con BR ufficiale e Radiance
installati.

## v4.1.2 (2026-05-02) — Fix orchestratore + raffinamenti documentazione

Patch cumulativa di piccoli fix accumulati dopo v4.1.1.

**Fix principale**: regex R² nell'orchestratore (`release_orchestrator.py`)
era troppo permissiva e catturava per errore il valore di `GCR=0.476`
dall'output di `validazione_br.py`, generando falsi NO-GO per STEP 5
anche quando i CSV salvati mostravano R² > 0.99 corretto. Pattern aggiornato
da `R[²\^2\?]?...` a `\bR(?:²|2|\?)...` con word boundary e carattere
² obbligatorio.

**Modifiche minori**:
- ROADMAP aggiornata: stato attuale → v4.1.2; pianificazione v4.2 estesa
  con generalizzazione frame coordinate sensori per `axis_azimuth`
  arbitrario, auto-update label versione nei file Excel via macro VBA
  `Workbook_Open()`, e script di release end-to-end automatico
  (`_NUOVA_VERSIONE.bat` + `release_helper.py`).
- Rimosso `engine/_br_run.bat` (codice morto: path hardcoded a
  `SolRatio_v4_0_0\engine\br_test_tmp.py`, file non più esistente).
- `_PUBBLICA_AGGIORNAMENTI.bat` aggiunto a `.gitignore` (workflow personale
  dell'autore, non parte del software pubblico).

Nessuna modifica al motore di simulazione SR (smoke regression v4.1.1
resta valido: K_agv SAU = 84.00% sul Sample). Validazione vs BR ufficiale
NREL conferma MBE ~0%, R² > 0.99 (i numeri "errati" del run notturno del
2 maggio erano artefatto della regex orchestratore, ora risolto).

## v4.1.1 (2026-05-01) — Fix STEP 5 mismatch scena BR ufficiale

Patch di correttezza scientifica della pipeline di validazione (STEP 5
dell'orchestratore di release).

**Bug risolto**: `validazione_br.py / _run_br_official()` ignorava il
parametro `br_n_rows` letto dal foglio Excel, mentre `br_engine.run_annual()`
lo rispettava. Risultato: le due pipeline confrontavano scene Radiance di
dimensioni diverse (es. 4 file vs 7 file), producendo un bias sistematico
SR > BR ufficiale di +4.5% sull'equinozio e +1.2% sul solstizio (con
tau=0 e slope=0). Dopo il fix le due pipeline simulano la stessa scena
e il confronto torna a MBE ~0.0%, R² > 0.9997.

**Risultato scientifico emerso dal debug**: il numero di file di tracker
nella scena influenza significativamente la radiazione al pitch centrale
quando il sole è basso. Aggiunto un avviso a runtime in `run_annual` quando
`n_rows < 7`, e raccomandazione esplicita in `PARAMETRI_RADIANCE.md`:
n_ext ≥ 3 (n_rows ≥ 7) per uso di routine, n_ext ≥ 4 (n_rows ≥ 9) per
benchmark e pubblicazioni scientifiche.

## v4.1.0 (2026-05-01) — Prima release pubblica

> ⚠ **Avvertenza retrospettiva**: i K_agv in modalità **tracking** delle
> versioni v4.1.x sono **sovrastimati** (scena contro-ruotata introdotta qui,
> corretta in v4.3.0).

Versione preparata per la pubblicazione open source con DOI Zenodo.

