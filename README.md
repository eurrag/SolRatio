# SolRatio v4.2.0

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19959581.svg)](https://doi.org/10.5281/zenodo.19959581)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Modello di irradianza al suolo e stima delle rese colturali per impianti agrivoltaici a tracker monoassiale.**

SolRatio è uno strumento integrato che combina la simulazione della radiazione solare disponibile per le colture sottostanti ai pannelli fotovoltaici (tramite ray-tracing 3D fisicamente accurato Radiance + bifacial_radiance) con le curve dose-risposta di Laub et al. (2022) per la stima delle rese colturali in regime di ombreggiamento agrivoltaico. Fornisce profili spaziali e temporali di PAR e DLI, e il coefficiente agrivoltaico K_agv per nove categorie colturali, necessari alla verifica dei requisiti agronomici previsti dalle Linee Guida MASE (D.M. 436/2023) e alla valutazione della compatibilità tra produzione energetica e produzione agricola.

---

## Caratteristiche

- Simulazione oraria 3D ray-tracing (8760 ore/anno) con motore Radiance
- Geometria configurabile: tracker monoassiale, pitch, larghezza modulo, altezza minima, slope terreno (axis e cross-axis)
- Tracker `axis_azimuth` arbitrario (N-S, E-W, qualsiasi orientamento) con warning agronomico per deviazioni >30° da N-S
- Backtracking + tilt fisso supportati (modalità configurabile)
- Trasmittanza pannello (`tau`) modellata via materiale Radiance `trans` per pannelli semitrasparenti; componente diffusa (`tau_diff`, BRTDfunc — alpha tier) opzionale per moduli a trasmissione mista
- Bifacciale single-axis (beta tier): calcolo dell'energia PV con `bifaciality_factor` su POA frontale + POA posteriore (view-factor)
- Modalità multi-anno con quantili P10/P50/P90 e media/stddev dei KPI principali
- Cache persistente delle scene Radiance (.oct) per workflow validazione e fixed-tilt
- Effetto bordo calcolato direttamente da BR sui pitch fisici della scena
- Curve di resa colturale Laub et al. (2022) — 9 colture — con calcolo K_agv di campo
- Output: report Excel multi-foglio + report PDF di sintesi
- Interfaccia Excel/VBA per gestione progetti senza scrivere codice; auto-update della label di versione via `Workbook_Open()`
- Sweep parametrico 2D `H_min × axis_azimuth` (`orchestratore_sweep.py`) per analisi di sensibilità del K_agv di campo
- Script di release end-to-end (`release_helper.py`) per automatizzare bump versione, DOI Zenodo, smoke test
- Validazione vs bifacial_radiance ufficiale: MBE < 1%, R² > 0.998 (Sample N-S, due giornate rappresentative)

---

## Requisiti

### Software esterno (non installabile via pip)

- **Radiance ≥ 5.4** — i comandi `gendaylit`, `oconv`, `rtrace` devono essere nel PATH di sistema. [Download](https://www.radiance-online.org/)

### Python

- Python ≥ 3.10
- Pacchetti: `bifacial_radiance`, `pvlib`, `numpy`, `pandas`, `openpyxl`, `lxml`, `matplotlib`, `reportlab` (vedi `requirements.txt`)

### Sistema operativo

Sviluppato e testato su Windows 11. Compatibile in linea di principio con Linux/macOS dove Radiance è disponibile, ma il workflow Excel/VBA richiede Microsoft Excel.

---

## Installazione

```cmd
git clone https://github.com/eurrag/SolRatio.git
cd SolRatio
pip install -r requirements.txt
python engine\check_environment.py
```

L'ultimo comando verifica che tutte le dipendenze siano installate correttamente, comprese quelle Radiance esterne.

---

## Uso rapido

### Da riga di comando (singolo progetto)

```cmd
python engine\calcola_br.py "progetti\Sample\SolRatio_progetto.xlsm"
```

### Da Excel (consigliato per uso ricorrente)

1. Apri `SolRatio_progetto.xlsm` con Excel + macro abilitate
2. Compila i parametri nel foglio `Parametri` (geometria, ottica, sito)
3. Premi il pulsante "Calcola" sul foglio `Launcher`
4. I risultati vengono scritti in `risultati_<progetto>.xlsx` e `report_SolRatio_<progetto>.pdf` nella stessa cartella

### Multi-anno (P10/P50/P90)

```cmd
python engine\solratio_multiyear.py "progetti\Sample\SolRatio_progetto.xlsm" --years tmy
python engine\solratio_multiyear.py "progetti\Sample\SolRatio_progetto.xlsm" --years 3
python engine\solratio_multiyear.py "progetti\Sample\SolRatio_progetto.xlsm" --years 2010,2015,2020
```

Output: `multiyear_results.csv` + `multiyear_quantiles.json` nella cartella del progetto.

### Sweep parametrico 2D

```cmd
_lancia_sweep.bat
```

Esegue 9 H_min × 5 axis_azimuth = 45 simulazioni del Sample; produce `results.csv`, `heatmap_kagv.png`, `curves_kagv.png` in `analisi/sweep_<timestamp>/`. Resume da run interrotti via `--resume <timestamp>`.

### Esempi inclusi

Nella cartella `progetti/` sono inclusi:

- `Sample/` — progetto dimostrativo N-S su pianura padana (lat 45.30°N, lon 9.34°E), con dati meteorologici PVGIS-SARAH3 già scaricati. Usato come benchmark di validazione.
- `Sample_EW/` — variante E-W del precedente, utile per studiare la dipendenza dal `axis_azimuth`.

Per creare un nuovo progetto: duplica una delle cartelle, rinominala, modifica i parametri nel foglio Excel, scarica i dati PVGIS della tua località da [PVGIS](https://re.jrc.ec.europa.eu/pvg_tools/it/) e sostituiscili nella tua cartella.

---

## Struttura del repository

```
SolRatio/
├── engine/                          # Codice sorgente
│   ├── VERSION                      # Versione corrente: "4.2.0"
│   ├── calcola_br.py                # Entry point principale
│   ├── br_engine.py                 # Motore bifacial_radiance (con tau_diff, slope L2/L3, cache .oct)
│   ├── _scene_cache.py              # Cache persistente delle scene Radiance octree
│   ├── solratio_core.py             # Funzioni core (PAR, DLI, zone, statistiche)
│   ├── solratio_excel.py            # I/O Excel (lettura parametri, scrittura risultati)
│   ├── solratio_edge.py             # Effetto bordo perimetrale
│   ├── solratio_yield.py            # Curve di resa colturale (Laub et al. 2022)
│   ├── solratio_pdf.py              # Generazione report PDF
│   ├── solratio_optimization.py     # Ottimizzazione H_min (curva K_agv vs H_min)
│   ├── solratio_multiyear.py        # Modalità multi-anno + quantili P10/P50/P90
│   ├── solratio_bifacial.py         # Calcolo energia PV bifacciale (beta tier)
│   ├── solratio_sensitivity.py      # Analisi di sensitività parametrica
│   ├── validazione_br.py            # Confronto SR vs BR ufficiale
│   ├── check_environment.py         # Verifica dipendenze
│   ├── migrate_project_layout.py    # Migrazione progetti al layout standardizzato (input/)
│   ├── release_helper.py            # CLI release: bump, update-doi, status
│   ├── orchestratore_sweep.py       # Sweep parametrico 2D H_min × axis_azimuth
│   ├── plot_profilo_pitch.py        # Plot PAR(x/pitch) da risultati Excel
│   ├── SolRatio_Calcolo.bas         # Modulo VBA Excel launcher (Calcola)
│   ├── SolRatio_VersionLabel.bas    # Modulo VBA auto-update label versione
│   └── test/                        # Batteria di test automatica
├── documentazione/                  # Docs tecnica (architettura, formule, roadmap, technical note)
├── progetti/
│   ├── Sample/                      # Progetto demo N-S (benchmark validazione)
│   └── Sample_EW/                   # Progetto demo E-W (sweep axis_azimuth)
├── analisi/                         # Output di analisi cross-progetto e sweep
├── _NUOVA_VERSIONE.bat              # Orchestratore release end-to-end
├── _lancia_sweep.bat                # Launcher sweep parametrico
├── _lancia_test_slope.bat           # Launcher battery test slope L2+L3
├── _smoke_regression_v42.bat        # Smoke test bit-per-bit
├── requirements.txt
├── LICENSE                          # Apache 2.0
├── CITATION.cff                     # Metadati di citazione
└── README.md                        # Questo file
```

---

## Documentazione

Documentazione tecnica nella cartella `documentazione/`:

- `ARCHITETTURA.md` — struttura moduli e responsabilità
- `architettura_br_engine.md` — pipeline di calcolo del motore BR
- `FORMULE.md` — formule fisiche implementate
- `PARAMETRI_RADIANCE.md` — parametri rtrace e loro effetto (incluse linee guida `n_rows`)
- `PIANO_v4.2.md` — piano dei 9 item del rilascio v4.2
- `CHANGELOG.md` — storico delle versioni
- `ROADMAP.md` — sviluppi futuri (v4.3, v4.4, v4.5+)
- `introduzione_solratio_relazione.md` — descrizione del modello in linguaggio non-tecnico
- `SolRatio_technical_note.md` — technical note in inglese (con abstract in italiano), descrive modello, architettura, validazione e esempio applicativo

---

## Validazione

Il modello è validato confrontando i risultati con il workflow ufficiale di bifacial_radiance (NREL) sullo stesso progetto, stessi parametri, stessi dati meteorologici. Risultati su una località di pianura padana (lat 45.30°N, lon 9.34°E, dati PVGIS-SARAH3 2005-2023), `n_rows = 7`:

| Giorno | MBE | RMSE | R² |
|--------|-----|------|----|
| 21 marzo (equinozio) | +0.54% | 0.80% | 0.9982 |
| 21 giugno (solstizio) | +0.42% | 0.49% | 0.9989 |

Lo scostamento residuo è rumore numerico intrinseco di Radiance (stocasticità ambient sampling). Script: `engine/validazione_br.py`.

Test di regressione bit-per-bit nel workflow di rilascio: il *Sample* deve riprodurre K_agv = 84.00% per Cereali C3 con tutte le feature secondarie disabilitate (`axis_azimuth = 180°`, `tau_diff = 0`, `bifaciality_factor = 0`, scene cache off). Ogni release candidate deve passare questo gate.

---

## Limitazioni note di v4.2.0

- **Pali di sostegno**: non ancora modellati nella scena Radiance. Spostati alla v4.3 (3D rendering dei pali e calibrazione contro misure in campo). Codice dormiente conservato in `solratio_yield.py` e `solratio_core.py`.
- **Bifacciale POA posteriore**: in v4.2.0 stimato con un view-factor semplificato (`0.5 · albedo · GHI`); simulazione Radiance dedicata con sensori posteriori prevista per v4.2.x.
- **Resa PV bifacciale**: calcolo moltiplicativo, non propaga temperatura del modulo, perdite di sistema, sporcamento. Modello PVWatts-like + LCOE previsto per v4.4 (prima release "economica").
- **Cache scene .oct**: per il flusso annuale standard (~3900 angoli unici di tracker) la cache è automaticamente disattivata e si applica il flusso legacy v4.1 bit-per-bit. Effettiva nei workflow di validazione single-day con tilt fisso. Mitigazioni (round tracker a 0.1°, cache lazy, location fuori da OneDrive) previste per v4.2.x.
- **Trasmissione semitrasparente avanzata**: `prism2` e BSDF (`.xml`) non supportati; previsti per v4.5+.
- **Validazione sperimentale**: la validazione attuale è code-to-code vs bifacial_radiance ufficiale, non code-to-measurement. Confronto con misure PAR/DLI in campo è obiettivo cross-cutting (vedi ROADMAP).
- **Curve di resa Laub (2022)**: calibrate su regimi di ombreggiamento N-S. Warning runtime se `|axis_azimuth − 180°| > 30°` — applicazione a configurazioni E-W scientificamente delicata.
- **Numero minimo di file in scena Radiance** (`n_rows`): per simulazioni accurate del pitch centrale di un impianto medio-grande, usare `n_ext ≥ 3` (`n_rows ≥ 7`); per benchmark e pubblicazioni scientifiche `n_ext ≥ 4` (`n_rows ≥ 9`). Con `n_rows < 7` la radiazione è sovrastimata di 1–5% al sole basso. Vedi `documentazione/PARAMETRI_RADIANCE.md`.

---

## Roadmap

Sviluppi pianificati (dettaglio in `documentazione/ROADMAP.md`):

- **v4.2.x** — patch release: root-cause del bug Windows nested-popen della cache .oct, test su slope significativi, riduzione opzionale degli angoli tracker unici, cache lazy in-worker, simulazione Radiance per POA posteriore bifacciale.
- **v4.3** — rendering 3D dei pali di sostegno nella scena Radiance + calibrazione contro misure in campo.
- **v4.4** — release "economica": LCOE e trade-off costo H_min vs K_agv, ottimizzazione cost-optimal dell'altezza.
- **v4.5+** — estensione dei materiali a trasmissione parziale con `prism2` e BSDF (`.xml`).
- **Obiettivo cross-cutting** — validazione sperimentale: confronto con misure PAR/DLI da impianti agrivoltaici strumentati. Collaborazioni con gruppi sperimentali sono benvenute.

---

## Come citare

Se usi SolRatio in lavori pubblici (relazioni tecniche, articoli, presentazioni), puoi citarlo come:

> Pesavento, S. (2026). *SolRatio: Modello di irradianza al suolo e stima delle rese colturali per impianti agrivoltaici a tracker monoassiale* (v4.2.0). Zenodo. https://doi.org/10.5281/zenodo.20277335

**DOI:**

- **Concept DOI** (sempre-ultima-versione): [`10.5281/zenodo.19959581`](https://doi.org/10.5281/zenodo.19959581) — usalo per citare "SolRatio" in generale
- **Versione v4.2.0** (immutabile, raccomandata): [`10.5281/zenodo.20277335`](https://doi.org/10.5281/zenodo.20277335) — usalo per citare la versione esatta che hai scaricato

DOI versioni precedenti:

- v4.1.2: [`10.5281/zenodo.19982399`](https://doi.org/10.5281/zenodo.19982399)
- v4.1.1: [`10.5281/zenodo.19960929`](https://doi.org/10.5281/zenodo.19960929)
- v4.1.0: [`10.5281/zenodo.19959582`](https://doi.org/10.5281/zenodo.19959582) — contiene il bug STEP 5 risolto in v4.1.1, **non raccomandato per nuove citazioni**

Vedi `CITATION.cff` per i metadati completi e `documentazione/SolRatio_technical_note.md` per la descrizione completa del modello.

---

## Licenza

Apache License 2.0 — vedi [LICENSE](LICENSE).

In sintesi: puoi usare, modificare, distribuire e integrare SolRatio in software commerciale, mantenendo l'attribuzione e includendo una copia della licenza. La licenza include una clausola esplicita di concessione dei diritti di brevetto.

---

## Autore

**Stefano Pesavento, PhD** — Independent researcher
ORCID: [0009-0008-0720-4539](https://orcid.org/0009-0008-0720-4539)

Per segnalazioni di bug, suggerimenti, contributi: aprire una issue sul repository GitHub.

---

## Riferimenti scientifici

- **Radiance** — Ward, G. (1994). *The RADIANCE lighting simulation and rendering system*. SIGGRAPH '94. https://doi.org/10.1145/192161.192286
- **bifacial_radiance** — Ayala Pelaez, S. & Deline, C. (2020). *bifacial_radiance: a Python package for modeling bifacial solar photovoltaic systems*. Zenodo. https://doi.org/10.5281/zenodo.4767317
- **pvlib** — Holmgren, W., Hansen, C., Mikofski, M. (2018). *pvlib python: a python package for modeling solar energy systems*. JOSS, 3(29), 884. https://doi.org/10.21105/joss.00884
- **Modello Perez** — Perez, R., Seals, R., Michalsky, J. (1993). *All-weather model for sky luminance distribution — preliminary configuration and validation*. Solar Energy, 50(3), 235–245.
- **Curve di resa Laub** — Laub, M. et al. (2022). *Contrasting yield responses at varying levels of shade suggest different suitability of crops for dual land-use systems*. Agronomy for Sustainable Development, 42:51. https://doi.org/10.1007/s13593-022-00783-7
- **PAR fraction (Jacovides)** — Jacovides, C.P. et al. (2004). *Comparative study of various correlations in estimating hourly diffuse fraction of global solar radiation*. Renewable Energy, 31(15), 2492–2504.
- **PVGIS / SARAH** — Huld, T., Müller, R., Gambardella, A. (2012). *A new solar radiation database for estimating PV performance in Europe and Africa*. Solar Energy, 86(6), 1803–1815. https://doi.org/10.1016/j.solener.2012.03.006
- **Agrivoltaico — riferimenti fondazionali** — Goetzberger & Zastrow (1982); Dupraz et al. (2011); Marrou et al. (2013); Trommsdorff et al. (2021). Riferimenti completi in `documentazione/SolRatio_technical_note.md`.
