# Batteria di test SolRatio v4.1.0

Strumenti per lanciare e analizzare i test di SolRatio: dalla batteria di
sensitività ray-tracing (47 test) all'orchestratore di release che coordina
tutti i check necessari prima di taggare una nuova versione.

## Posizione e convenzioni

- **Script** (qui in `engine/test/`):
  - `release_orchestrator.py` orchestratore di release (NEW v4.1.0):
    coordina tutti gli step di test/validazione necessari per un nuovo tag
    GitHub. Produce un report markdown go/no-go in `analisi/`.
  - `run_battery.py` orchestratore della batteria di sensitività
  - `confronta_KPI.py` aggregatore KPI / generatore grafici
  - Launcher Windows portabili:
    - `_LANCIA_RELEASE_TEST.bat` (NEW v4.1.0): orchestratore release
    - `_LANCIA_BATTERIA.bat`: solo batteria sensitività
    - `_ANALIZZA_KPI.bat`: solo aggregazione KPI

- **Dati dei test** (default in `progetti/test_battery/`):
  ogni cartella contiene un `SolRatio_progetto.xlsm` configurato e, dopo il run,
  `risultati_*.xlsx`, `report_*.pdf`, `br_log.txt`, `br_err.txt`, `.br_done`.

Tutti i percorsi sono auto-rilevati relativamente alla posizione degli script,
quindi spostando l'intero `SolRatio_v4_1_0/` nulla va riconfigurato.

## Orchestratore di release (NEW v4.1.0)

Da usare prima di taggare una nuova versione su GitHub e pubblicarla su Zenodo.

```cmd
_LANCIA_RELEASE_TEST.bat                      :: modalità rapida (~25 min)
_LANCIA_RELEASE_TEST.bat --full               :: tutti gli step (~3 ore)
_LANCIA_RELEASE_TEST.bat --full --skip-battery
_LANCIA_RELEASE_TEST.bat --baseline-kagv 0.8732 --tolerance-pct 0.5
```

Equivalente CLI cross-platform:

```bash
python release_orchestrator.py [--quick|--full]
                                [--baseline-project "<nome cartella>"]
                                [--baseline-kagv <float>] [--tolerance-pct <pct>]
                                [--skip-battery] [--skip-validation]
                                [--output-dir <dir>]
                                [--python <python_exe>]
```

Pipeline:

| Step | Cosa fa | Tempo | Modalità |
|------|---------|-------|----------|
| 1 | Pre-flight: ambiente, coerenza VERSION/docstring, import sanità, file rilascio, ORCID | ~30 sec | quick + full |
| 2 | Smoke regression: run baseline con tau=0/slope=0, confronto con baseline_kagv | ~5 min | quick + full |
| 3 | Feature tests: tau=0.30, slope_pct=10%, optimize_hmin (3 punti) | ~15 min | quick + full |
| 4 | Batteria estesa: 47 test su `progetti/test_battery/` | ~1-2 h | solo --full |
| 5 | Validazione vs BR ufficiale: equinozio + solstizio sul progetto baseline | ~30 min | solo --full |

Output:
- Report Markdown in `analisi/release_report_v<version>_<timestamp>.md`
- Decisione finale: 🟢 GO se 0 FAIL, 🔴 NO-GO altrimenti
- Exit code 0 (GO) o 1 (NO-GO) per integrazione CI/CD

## Struttura cartelle dati

```
test_battery/
  00_BASELINE/                     località esempio (pianura padana), n_sub=4
  01_GEOMETRIA/                    pitch, W, H_min, beta_max, axis_az
  02_TRACKER/                      mode, theta_fix
  03_OTTICA/                       tau (semitrasparenza)
  04_SLOPE/                        pendenza % + azimut
  05_BORDO/                        n_ext + griglia 2D blocco x L_tot
  06_RADIANCE/                     ab, ad, as, n_rows
  99_ANALISI/                      output di confronta_KPI.py
  batteria_log.txt                 log generale generato da run_battery.py
```

47 test in totale: 1 baseline + 11 geometria + 4 tracker + 2 ottica
+ 4 slope + 15 bordo + 10 radiance.

## Uso

### Lancio batteria

Su Windows, doppio click su `_LANCIA_BATTERIA.bat` oppure da terminale:

```cmd
_LANCIA_BATTERIA.bat                 :: lancia tutti i test, resume attivo
_LANCIA_BATTERIA.bat --no-resume     :: ignora .br_done, rifa' tutto
_LANCIA_BATTERIA.bat --only 05_BORDO :: solo test la cui rel-path contiene "05_BORDO"
_LANCIA_BATTERIA.bat --dry-run       :: mostra solo cosa farebbe
_LANCIA_BATTERIA.bat --data "C:\altro\percorso"   :: cartella dati alternativa
```

Equivalente diretto (Linux / macOS):

```bash
python run_battery.py [--no-resume] [--only PATTERN] [--dry-run] [--data DIR]
```

Il run_battery scrive `batteria_log.txt` nella cartella dati e, per ogni test:
`br_log.txt` (stdout), `br_err.txt` (stderr), `.br_done` (sentinella di completamento
con timestamp e durata in secondi). I run gia' completati vengono saltati.

### Analisi KPI

A batteria conclusa, doppio click su `_ANALIZZA_KPI.bat` oppure:

```cmd
_ANALIZZA_KPI.bat
_ANALIZZA_KPI.bat --data "C:\altro\percorso"
```

Genera in `<DATA>/99_ANALISI/`:

- `batteria_KPI.xlsx` con fogli:
  - `Tutti` tutti i KPI di tutti i test
  - un foglio per sezione (`00_BASELINE`, `01_GEOMETRIA`, ...)
  - `Delta_vs_baseline_%` variazione percentuale di ogni KPI rispetto al baseline
- `grafici_sensitivita.pdf`:
  - pagina overview con elenco test e tempi di run
  - una pagina per ciascun gruppo di sweep monovariato (5 KPI in una griglia 2x3)
  - pagina dedicata `slope` (bar plot, 2 variabili)
  - heatmap 2D per la griglia bordo (blocco x L_totale), una per ciascun KPI principale

## Mappa parametri Excel (foglio Parametri)

| Cella | Variabile        | Note                                   |
|-------|------------------|----------------------------------------|
| B4    | lat              | latitudine                             |
| B5    | lon              | longitudine                            |
| B6    | slope_pct        | pendenza terreno %                     |
| B7    | slope_az        | azimut linea di max pendenza           |
| B14   | axis_az          | azimut asse tracker                    |
| B15   | pitch            | passo tra file                         |
| B16   | W                | larghezza modulo (corda chord)         |
| B17   | H_min            | altezza minima al suolo (a beta_max)   |
| B18   | beta_max         | tilt massimo tracker                   |
| B19   | mode             | 1=astronomico, 2=tilt fisso            |
| B20   | theta_fix        | tilt fisso (se mode=2)                 |
| B23   | tau              | semitrasparenza moduli                 |
| B24   | albedo           | albedo terreno                         |
| B30   | larghezza_blocco | dimensione W del blocco impianto       |
| B31   | L_totale         | dimensione L del blocco impianto       |
| B44   | n_ext            | n. estensioni file laterali            |
| B47   | n_sub            | sub-sampling timestep (4=15min, 60=1min) |
| B48   | ab               | Radiance ambient bounces               |
| B49   | ad               | Radiance ambient divisions             |
| B50   | as               | Radiance super-samples                 |
| B51   | n_rows           | numero file modellate                  |

## KPI estratti (da `Riepilogo` di risultati_*.xlsx)

- **DLI annuo per zona** (B19-B24): rif, sotto, bordo, centr, SAU, pitch
- **PARrel P50** (B27-B31): sotto, bordo, centr, SAU, pitch
- **K_agv SAU** (B35-B43, una per coltura): Bacche, Frutta, Ort_frutto, Foraggere,
  Ort_foglia, Tuberi, Cereali_C3, Legum, Mais
- **K_agv impianto** + **FC** (C/D 47-55, per coltura)

## Resume e gestione errori

- Ogni run di successo crea `.br_done` nella cartella del test
- run successivi saltano automaticamente le cartelle con `.br_done`
- per rifare un test specifico: cancella il suo `.br_done`
- per rifare tutto: `--no-resume`
- Ctrl+C: chiude pulito dopo il test corrente, niente sentinelle parziali
- gli errori finiscono in `br_err.txt` (separato dallo stdout) per debug rapido

## Note tecniche

- `run_battery.py` usa `sys.executable`: il subprocess gira con lo stesso Python del padre
- ETA in console basata sui run effettivamente eseguiti nella sessione (non sui SKIP)
- `confronta_KPI.py` usa una mappa esplicita test -> (gruppo, parametro): aggiungere
  un nuovo test richiede una riga in `TEST_GROUPS`
- la griglia bordo e' una matrice 2D pivot blocco x L_tot: per estenderla aggiungere
  test con etichette `blocco_<W>_L<L>` e mapparli a `('bordo_grid', None)`
- il template Riepilogo shifta di 1 riga quando slope>0 (solratio_excel.py:1411
  offset=8 vs 5): confronta_KPI.py usa ancoraggi adattivi (cerca "DLI rif",
  "Sotto-tracker", "Bacche") per leggere le celle giuste in entrambi i layout

## Limitazioni note del motore BR v4 (risultati inaffidabili)

Alcuni parametri presenti 