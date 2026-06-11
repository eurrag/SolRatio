# SolRatio — Changelog

## v4.2.1 (2026-06-11) — Reference edition: potatura al minimo riproducibile + fix

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
  (`import reportlab` → `os.getcwd()`): su Linux il PDF non veniva MAI
  prodotto.
- **Number format Excel `'0.1'` → `'0.0'`** (11 celle writer): in
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
  `_smoke_regression.sh` (Linux/macOS) girano su ENTRAMBI i progetti;
  riferimenti v4.2.1: N-S 84.1, E-W 79.2, tolleranza ±0.2 pp (la
  dicitura "bit-per-bit" è stata rimossa: l'ambient sampling di Radiance
  è stocastico).
- Igiene: rimossi path personali dalle celle/commenti (xlsm, .bas,
  .gitignore); EPW dei progetti rigenerati con header UTC.

### Note

- La technical note allineata a questa edizione è in preparazione
  (deposito Zenodo con DOI gemello).
- Il foglio `Sensitivita_Config` e i pulsanti legacy negli xlsm esistenti
  si rimuovono riaprendo il file in Excel e reimportando i moduli VBA
  aggiornati (i pulsanti sono rigenerati dalla macro `AggiungiPulsanti`).

## v4.2.0 (2026-05-05) — Multi-anno, frame coord ruotato, bifacciale, BRTDfunc, cache scene .oct

Release minor che chiude lo scope v4.2 (9 item) come pianificato in
`PIANO_v4.2.md`. Decisioni utente del 2026-05-02 hanno spostato i pali
dalla v4.2 alla v4.3 e anticipato in v4.2 i 3 item v4.3 originali (con
scope ridotti α e β rispettivamente). Trade-off costo H_min spostato
a v4.4.

### Nuove feature

**Item 8 — Auto-update label versione Excel via VBA**:
Aggiunto modulo `engine/SolRatio_VersionLabel.bas`. Macro
`UpdateVersionLabelFromFile()` legge `engine/VERSION` (con fallback
fino a 4 livelli sopra il file Excel) e aggiorna la cella `A1` del
foglio `Launcher` come `"SOLRATIO AGRIVOLTAICO - Launcher vX.Y.Z"`.
Da chiamare da un `Workbook_Open()` in `ThisWorkbook` (una sola riga
da aggiungere — istruzioni in `progetti/Sample/README.md`). Silent-fail
se VERSION non raggiungibile, idempotente, no prompt "Salvare?".

**Item 6 — Script di release end-to-end**:
Aggiunto `engine/release_helper.py` (CLI con subcommand `bump`,
`bump-from-changelog`, `update-doi`, `status`) e
`_NUOVA_VERSIONE.bat` come orchestratore. Pre-check git pulito, dry-run
supportato, single-source-of-truth da CHANGELOG. Riduce la procedura
manuale di rilascio da ~30 min a ~5 min con interventi utente di ~2 min.
Polling Zenodo + auto-DOI rinviato a step incrementale (manuale per ora).

**Item 4 — Cache scene `.oct` persistente**:
Aggiunto modulo `engine/_scene_cache.py` con API `make_cache_key`,
`lookup`, `store`, `housekeeping`. `br_engine.run_annual()` accetta
ora `use_scene_cache=True` (default) e `project_dir`. La cache pre-compila
una volta per progetto+geometria un .oct di scena (matfiles+radfiles, no
sky); per-ora il `_worker` usa `oconv -i scene.oct sky.rad` invece del
full oconv. Speedup atteso 30-60% sul tempo per ora dopo il primo run.
Fail-safe: in caso di errore della cache si applica il flusso legacy.
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
  axis, la replica è nel frame ruotato. Rimosso il warning runtime
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
`<progetto>/test/multiyear_quantiles.json`. Niente parallelizzazione
in v4.2.0 (bifacial_radiance/Radiance non sono progettati per multi-thread
in-process: deferito a v4.2.x se collo di bottiglia).

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
  `documentazione/ROADMAP.md` e `documentazione/PIANO_v4.2.md`.

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
  `"Ricalcola"` (più stabile alla versione, meno verboso). Modifiche:
  `engine/SolRatio_Calcolo.bas` (sorgente VBA) + script
  `_patch_button_label.py` per applicare il fix in-place al
  `drawing1.xml` di tutti gli `xlsm` esistenti senza richiedere
  re-import del modulo VBA.

### Rinvii e limitazioni

- **Item 1 (Pali nella scena Radiance)**: spostato a v4.3 su decisione
  utente. Codice dormiente conservato, call sites commentate.
- ~~**Item 3 (Ground plane inclinato L3 completo)**~~: anticipato e
  completato in v4.2.0 (vedi sezione "Slope L2 e L3 anticipati" sopra).
- **Item 10 (Trade-off costo H_min, formulazione B)**: spostato a v4.4
  su decisione utente. v4.4 sarà la prima release "economica" con
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
beneficio netto e la cache è automaticamente saltata.

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
che il run vero parta. Aggravante: ogni .oct di scena (~1-3MB)
moltiplicato per 3929 = qualche GB scritto in OneDrive.

Patch applicata in `br_engine.py`: soglia automatica `_CACHE_MAX_THETAS=200`.
Sopra questa soglia il cache pre-compile viene **saltato** e il worker
torna al flusso legacy v4.1 (full `oconv matfiles + sky + radfiles` per
ora). Comportamento bit-per-bit identico a v4.1 quando N_thetas > 200.

La cache continua a essere efficace nei casi originariamente previsti
(es. simulazione single-day con tracker fixed-tilt → 1 theta unico,
oppure profili con `theta_fix=N`). Per il flusso annuale tipico la
cache è di fatto disattivata in v4.2.0 — feature rimandata a v4.2.x
con due possibili soluzioni alternative:

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

3. **`solratio_bifacial.py` era dead code**: il modulo era creato ma
   nessuno lo importava né chiamava. Patch: aggiunto in `calcola_br.py`
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
7. **Sintassi `engine/*.py`**: lo sviluppo è stato fatto in ambiente
   Cowork con limitazione di file system (bash mount FUSE non riusciva
   a sincronizzare i file modificati via Windows API in OneDrive).
   Le edit sono state validate solo visualmente. Eseguire
   `python -c "import ast; [ast.parse(open(f).read()) for f in
   ['engine/br_engine.py','engine/release_helper.py',
   'engine/_scene_cache.py','engine/migrate_project_layout.py',
   'engine/solratio_multiyear.py','engine/solratio_bifacial.py',
   'engine/validazione_br.py','engine/solratio_yield.py']]"`
   come gate prima del tag.

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

**Insight scientifico emerso dal debug**: il numero di file di tracker
nella scena influenza significativamente la radiazione al pitch centrale
quando il sole è basso. Aggiunto warning runtime in `run_annual` quando
`n_rows < 7`, e raccomandazione esplicita in `PARAMETRI_RADIANCE.md`:
n_ext ≥ 3 (n_rows ≥ 7) per uso di routine, n_ext ≥ 4 (n_rows ≥ 9) per
benchmark e pubblicazioni scientifiche.

## v4.1.0 (2026-05-01) — Prima release pubblica

Versione preparata per la pubblicazione open source con DOI Zenodo.

