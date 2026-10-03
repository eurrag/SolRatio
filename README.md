# SolRatio v4.3.2

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19959581.svg)](https://doi.org/10.5281/zenodo.19959581)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Modello di irradianza al suolo e stima delle rese colturali per impianti agrivoltaici a tracker monoassiale.**

SolRatio è uno strumento integrato che combina la simulazione della radiazione solare disponibile per le colture sottostanti ai pannelli fotovoltaici (tramite ray-tracing 3D fisicamente accurato con Radiance e bifacial_radiance) con le curve dose-risposta di Laub et al. (2022) per la stima delle rese colturali in regime di ombreggiamento agrivoltaico. Fornisce profili spaziali e temporali di PAR e DLI e il coefficiente agrivoltaico K_agv per nove categorie colturali. Tali grandezze sono necessarie alla verifica dei requisiti agronomici previsti dalle Linee Guida ministeriali in materia di impianti agrivoltaici (MiTE, 2022) e dal D.M. 436/2023 sull'agrivoltaico innovativo, nonché alla valutazione della compatibilità tra produzione energetica e produzione agricola.

> **⚠ Correzione (v4.3.1).** I coefficienti delle curve di resa in uso dalla
> v4.1.0 alla v4.3.0, dichiarati adattati alla Table S2 di Laub et al. (2022)
> con RMSE < 1.6%, se ne discostavano fino a 19.9 punti percentuali (tuberi e
> radici) e 11.1 (cereali C3). La v4.3.1 li adatta ai 162 valori della
> tabella (scarto massimo 0.071 punti): **i K_agv delle versioni precedenti
> vanno ricalcolati** (gate Sample, cereali C3: 57.5% → 47.8%); irradianza,
> PAR e DLI non cambiano. Dettagli nel [CHANGELOG](documentazione/CHANGELOG.md).

> **⚠ Correzione maggiore (v4.3.0).** Dal v4.1.0 al v4.2.2 la scena Radiance
> ruotava il pannello dalla parte opposta al sole in ogni ora di tracking: i
> K_agv in modalità tracking delle versioni precedenti **sovrastimano la luce
> al suolo** (gate Sample, coi coefficienti di resa della v4.3.0: 84.1% →
> 57.5%). Chi ha usato risultati in tracking di versioni precedenti deve
> rieseguire le simulazioni. Dettagli nel [CHANGELOG](documentazione/CHANGELOG.md).

> **Edizione di riferimento (open-core).** SolRatio v4.3.x è la *Community /
> Reference Edition*: una base citabile e riproducibile, mantenuta con correzioni di
> correttezza e pensata per la verifica scientifica del metodo. Lo sviluppo di
> nuove funzionalità prosegue nel prodotto hosted **SolRatio Pro**. Le
> rimozioni rispetto alla v4.2.0 sono elencate in modo esplicito nel
> [CHANGELOG](documentazione/CHANGELOG.md).

---

## English summary

SolRatio is an open-source tool that estimates the spatial and temporal
distribution of solar radiation reaching the ground beneath single-axis
tracker agrivoltaic systems (3D ray tracing with Radiance +
bifacial_radiance, hourly over a typical meteorological year built from
PVGIS-SARAH3 data) and converts it into expected crop-yield coefficients
(K_agv) for nine crop categories via the dose-response curves of Laub et
al. (2022). The full technical documentation is in English:
[Technical Note](documentazione/SolRatio_technical_note.md).

**⚠ Correction (v4.3.1):** the crop-yield coefficients used from v4.1.0
through v4.3.0, stated as fitted to Table S2 of Laub et al. (2022) with
RMSE < 1.6%, deviated from that table by up to 19.9 percentage points
(tubers and roots) and 11.1 (C3 cereals). v4.3.1 fits them to the 162
values of the table (maximum deviation 0.071 points): K_agv values of
previous releases must be recomputed (bundled Sample gate, C3 cereals:
57.5% → 47.8%); ground irradiance, PAR and DLI are unchanged.

**⚠ Major correction (v4.3.0):** from v4.1.0 through v4.2.2 the Radiance
tracking scene was counter-rotated with respect to the sun; tracking-mode
ground-light results of all previous releases are overestimated and must
not be reused (bundled Sample gate with the v4.3.0 crop-yield
coefficients: 84.1% → 57.5%). Semi-transparent panel results of v4.2.x
are also affected by a separate material-mapping defect corrected in
v4.3.0.

Validation is two-tiered: a code-to-code comparison against the official
bifacial_radiance workflow (|MBE| < 1%, R² ≥ 0.997 on equinox and
solstice days) plus an independent reference built with the native
bifacial_radiance 1-axis workflow (`set1axis` → `analysis1axisground`),
agreeing within 0.5 percentage points on the daily ground-to-GHI ratio.
A cross-platform regression gate on the two bundled sample projects
(N-S 47.8% / E-W 48.0%, ±0.2 pp) is part of the release workflow.

To cite this software, use the concept DOI
[10.5281/zenodo.19959581](https://doi.org/10.5281/zenodo.19959581)
(see `CITATION.cff`). License: Apache 2.0.

---

## Caratteristiche

- Simulazione oraria 3D ray-tracing (8760 ore/anno) con motore Radiance
- Geometria configurabile: tracker monoassiale, pitch, larghezza modulo, altezza minima, slope terreno (axis e cross-axis)
- Tracker `axis_azimuth` arbitrario (N-S, E-W, qualsiasi orientamento) con avviso agronomico per deviazioni >30° da N-S
- Backtracking + tilt fisso supportati (modalità configurabile)
- Trasmittanza pannello (`tau`) modellata via materiale Radiance `trans` per pannelli semitrasparenti; componente diffusa (`tau_diff`, BRTDfunc — funzionalità in stato alpha) opzionale per moduli a trasmissione mista
- Bifacciale single-axis (funzionalità in stato beta): calcolo dell'energia PV con `bifaciality_factor` su POA frontale + POA posteriore (view-factor)
- Modalità multi-anno con quantili P10/P50/P90 e media/stddev dei KPI principali
- Cache persistente delle scene Radiance (.oct) per workflow validazione e fixed-tilt
- Effetto bordo calcolato direttamente da bifacial_radiance sui pitch fisici della scena
- Curve di resa colturale Laub et al. (2022) — 9 colture — con calcolo K_agv di campo
- Output: report Excel multi-foglio + report PDF di sintesi
- Interfaccia Excel/VBA per gestione progetti senza scrivere codice; aggiornamento automatico dell'etichetta di versione tramite `Workbook_Open()`
- Validazione mediante confronto con bifacial_radiance ufficiale: MBE < 1%, R² ≥ 0.997 (Sample N-S, due giornate rappresentative), oltre a un riferimento indipendente con il workflow nativo `set1axis` (entro 0.5 pp sul rapporto suolo/GHI giornaliero)
- Test di regressione (smoke) multipiattaforma sui progetti Sample N-S ed E-W inclusi

---

## Requisiti

### Software esterno (non installabile via pip)

- **Radiance ≥ 5.4** — i comandi `gendaylit`, `oconv`, `rtrace` devono essere nel PATH di sistema. [Download](https://www.radiance-online.org/)

### Python

- Python ≥ 3.10
- Pacchetti: `bifacial_radiance`, `pvlib`, `numpy`, `pandas`, `openpyxl`, `lxml`, `matplotlib`, `reportlab` (vedi `requirements.txt`)

### Sistema operativo

Sviluppato e testato su Windows 11. Compatibile in linea di principio con Linux/macOS dove Radiance è disponibile, ma il workflow Excel/VBA richiede Microsoft Excel.

### Ambiente di riferimento (riproducibilità)

I vincoli di `requirements.txt` sono minimi (`>=`) per facilitare l'installazione; l'unica eccezione è `bifacial_radiance`, **bloccato a `==0.5.1`** perché il motore dipende dalla normalizzazione di `makeScene1axis` di quella versione (forma canonica della scena di tracking) e include un accorgimento specifico per essa. La garanzia *comportamentale* del rilascio è il test di regressione a **±0.2 punti percentuali** (vedi [Validazione](#validazione)): qualsiasi combinazione di versioni che lo superi riproduce i risultati pubblicati. Per ricreare l'ambiente *esatto* è disponibile `requirements-lock.txt` (`pip install -r requirements-lock.txt`), con le versioni riportate qui sotto.

Configurazione esatta con cui i riferimenti della v4.3.0 sono stati riverificati (Linux/WSL, 2026-06-13):

| componente | versione |
|---|---|
| Python | 3.10.12 |
| Radiance | 6.0a (binari forniti da `pyradiance` 1.2.3) |
| numpy / pandas | 2.2.6 / 2.3.3 |
| pvlib | 0.15.1 |
| bifacial_radiance | 0.5.1 |
| openpyxl / lxml | 3.1.5 / 6.1.1 |
| reportlab / matplotlib | 4.5.1 / 3.10.9 |

Il `K_agv` Cereali C3 di riferimento della v4.3.0 (Sample **57.5 %**, Sample_EW **55.3 %**) è risultato identico — scarto **+0.00 pp**, 3919/3919 ore senza errori — sia nel collaudo completo su Windows 11 (2026-06-12, Radiance 6.0) sia in questa riverifica su Linux/WSL, a conferma della robustezza tra piattaforme.

I riferimenti della v4.3.1 (Sample **47.8 %**, Sample_EW **48.0 %**) sono stati misurati il 2026-09-28 su Linux/WSL con Python 3.10.12, le versioni della tabella e Radiance 6.0.2 (build LBNL): tre run con gli stessi valori di gate, 3919/3919 ore senza errori (fra un run e l'altro il K_agv dei tuberi del Sample è variato di 0.1 punti, 46.8 / 46.7 / 46.8). Nello stesso ambiente la v4.3.0 riproduce i propri riferimenti (57.5 / 55.3) con scarto +0.00 pp. Su Windows la v4.3.1 non è stata rieseguita.

---

## Installazione

```cmd
git clone https://github.com/eurrag/SolRatio.git
cd SolRatio
pip install -r requirements.txt
python engine\check_environment.py
```

L'ultimo comando verifica che tutte le dipendenze siano installate correttamente, compresa la disponibilità dei comandi esterni di Radiance.

---

## Uso rapido

### Da riga di comando (singolo progetto)

```cmd
python engine\calcola_br.py "progetti\Sample\SolRatio_progetto.xlsm"
```

### Da Excel (consigliato per uso ricorrente)

1. Aprire `SolRatio_progetto.xlsm` con Excel + macro abilitate
2. Compilare i parametri nel foglio `Parametri` (geometria, ottica, sito)
3. Premere il pulsante "Calcola" sul foglio `Launcher`
4. I risultati vengono scritti in `risultati_<progetto>.xlsx` e `report_SolRatio_<progetto>.pdf` nella stessa cartella

### Multi-anno (P10/P50/P90)

```cmd
python engine\solratio_multiyear.py "progetti\Sample\SolRatio_progetto.xlsm" --years tmy
python engine\solratio_multiyear.py "progetti\Sample\SolRatio_progetto.xlsm" --years 3
python engine\solratio_multiyear.py "progetti\Sample\SolRatio_progetto.xlsm" --years 2010,2015,2020
```

Output: `multiyear_results.csv` + `multiyear_quantiles.json` nella cartella del progetto.

### Esempi inclusi

Nella cartella `progetti/` sono inclusi:

- `Sample/` — progetto dimostrativo N-S in Pianura Padana (lat 45.30°N, lon 9.34°E), con dati meteorologici PVGIS-SARAH3 già scaricati. Usato come benchmark di validazione.
- `Sample_EW/` — variante E-W del precedente, utile per studiare la dipendenza dal `axis_azimuth`.

Per creare un nuovo progetto: duplicare una delle cartelle, rinominarla, modificare i parametri nel foglio Excel, scaricare dal portale [PVGIS](https://re.jrc.ec.europa.eu/pvg_tools/it/) i dati della località di interesse e sostituirli nella nuova cartella.

---

## Struttura del repository

```
SolRatio/
├── engine/                          # Codice sorgente
│   ├── VERSION                      # Versione corrente: "4.3.2"
│   ├── calcola_br.py                # Entry point principale
│   ├── br_engine.py                 # Motore bifacial_radiance (con tau_diff, slope L2/L3, cache .oct)
│   ├── _scene_cache.py              # Cache persistente delle scene Radiance octree
│   ├── solratio_core.py             # Funzioni core (PAR, DLI, zone, statistiche)
│   ├── solratio_excel.py            # I/O Excel (lettura parametri, scrittura risultati)
│   ├── solratio_edge.py             # Effetto bordo perimetrale
│   ├── solratio_yield.py            # Curve di resa colturale (Laub et al. 2022)
│   ├── solratio_pdf.py              # Generazione report PDF
│   ├── solratio_multiyear.py        # Modalità multi-anno + quantili P10/P50/P90
│   ├── solratio_bifacial.py         # Calcolo energia PV bifacciale (funzionalità in stato beta)
│   ├── validazione_br.py            # Confronto SolRatio vs bifacial_radiance ufficiale
│   ├── check_environment.py         # Verifica dipendenze
│   ├── test_laub_tabella_s2.py      # Curve di resa contro la Table S2 di Laub (senza Radiance)
│   ├── laub_2022_table_s2.csv       # Table S2 di Laub et al. 2022 (CC BY 4.0), letta dalla prova
│   ├── SolRatio_Calcolo.bas         # Modulo VBA Excel launcher (Calcola)
│   └── SolRatio_VersionLabel.bas    # Modulo VBA aggiornamento automatico etichetta versione
├── documentazione/                  # Documentazione tecnica (architettura, formule, roadmap, technical note)
├── progetti/
│   ├── Sample/                      # Progetto demo N-S (benchmark validazione)
│   └── Sample_EW/                   # Progetto demo E-W (confronto axis_azimuth)
├── _smoke_check_kagv.py             # Verifica K_agv del gate (usato dagli smoke)
├── _smoke_regression.bat            # Smoke test di regressione (Windows)
├── _smoke_regression.sh             # Smoke test di regressione (Linux/macOS)
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
- `CHANGELOG.md` — storico delle versioni
- `ROADMAP.md` — posizionamento open-core e manutenzione dell'edizione
- `introduzione_solratio_relazione.md` — descrizione del modello in linguaggio non-tecnico
- `SolRatio_technical_note.md` — technical note in inglese (con abstract in italiano), descrive modello, architettura, validazione ed esempio applicativo

---

## Validazione

Il modello è validato in due modi complementari (script: `engine/validazione_br.py`).

**1) Code-to-code**, rispetto al workflow ufficiale di bifacial_radiance (AnalysisObj) sullo stesso progetto, con gli stessi parametri rtrace e gli stessi dati meteorologici. Risultati sul progetto *Sample* incluso (Pianura Padana, lat 45.30°N lon 9.34°E, dati PVGIS-SARAH3 2005-2023; scena demo con `br_n_rows = 4`), misurati con v4.3.0 (Radiance 6.0, collaudo completo 2026-06-12):

| Giorno | MBE | RMSE | R² |
|--------|-----|------|----|
| 21 marzo (equinozio) | +0.1% | 0.2% | 0.9993 |
| 21 giugno (solstizio) | −0.1% | 0.1% | 0.9999 |

Lo scostamento residuo è rumore numerico intrinseco di Radiance (stocasticità dell'ambient sampling); riesecuzioni indipendenti restituiscono R² ≥ 0.9975.

**2) Riferimento canonico indipendente** (parte D della validazione, introdotta in v4.3.0): la stessa scena è simulata con il workflow nativo 1-axis di bifacial_radiance (`set1axis` → `gendaylit1axis` → `analysis1axisground`), in cui gli angoli del tracker sono calcolati da pvlib all'interno della libreria e i sensori a terra sono posizionati dalla libreria stessa: la geometria non incorpora alcuna convenzione SolRatio. Scarto sul rapporto suolo/GHI giornaliero entro 0.5 pp (misure del collaudo 2026-06-12: −0.3 pp su entrambi i giorni; il valore puntuale varia con il campionamento ambient stocastico). Questo controllo è stato aggiunto dopo la scoperta della scena contro-ruotata (v4.1.0–v4.2.2): la sola validazione code-to-code condivideva la convenzione di scena con il motore ed era cieca per costruzione agli errori di convenzione.

Test di regressione nel workflow di rilascio: i progetti inclusi *Sample* (N-S) e *Sample_EW* (E-W) devono riprodurre un K_agv SAU per Cereali C3 di **47.8%** e **48.0%** rispettivamente (riferimenti misurati con v4.3.1; con i coefficienti di resa della v4.3.0 erano 57.5% e 55.3%), con tolleranza **±0.2 punti percentuali**: l'ambient sampling di Radiance è stocastico e il risultato non è bit-identico tra run. Esecuzione: `_smoke_regression.bat` (Windows) o `./_smoke_regression.sh` (Linux/macOS). Ogni release candidate deve passare questo gate. Dalla v4.3.1 anche le curve di resa hanno una prova propria, senza Radiance: `python engine/test_laub_tabella_s2.py` le confronta con i 162 valori della Table S2 di Laub et al. (2022).

---

## Limitazioni note

- **Pali di sostegno**: non modellati nella scena Radiance in questa edizione.
- **Bifacciale POA posteriore**: stimato con un view-factor semplificato (`0.5 · albedo · GHI`); nessuna simulazione Radiance dedicata dei sensori posteriori.
- **Resa PV bifacciale**: calcolo moltiplicativo di prima approssimazione; non propaga temperatura del modulo, perdite di sistema, sporcamento.
- **Cache scene .oct**: attiva solo quando gli angoli unici di tracker sono ≤ 200 (workflow di validazione single-day e tilt fisso); nel flusso annuale standard (~3900 angoli) è disattivata per scelta progettuale. Da v4.2.1 gli octree in cache sono *frozen* (self-contained): il riuso tra run è affidabile.
- **Workbook risultati senza template di formattazione**: i fogli sono generati interamente da codice, con formattazione essenziale.
- **Trasmissione semitrasparente avanzata**: `prism2` e BSDF (`.xml`) non supportati.
- **Terreni in pendenza**: il modello (componenti lungo/trasversale all'asse, piano terreno realmente inclinato in scena) è implementato e collaudato funzionalmente; una validazione dedicata su pendenze significative non è inclusa in questa edizione.
- **Validazione sperimentale**: la validazione attuale è di tipo code-to-code rispetto a bifacial_radiance ufficiale, non code-to-measurement (si veda la ROADMAP).
- **Curve di resa Laub (2022)**: calibrate su regimi di ombreggiamento N-S. Il software emette un avviso a runtime se `|axis_azimuth − 180°| > 30°`: l'applicazione a configurazioni E-W è scientificamente delicata.
- **Numero minimo di file in scena Radiance** (`n_rows`): per simulazioni accurate del pitch centrale di un impianto medio-grande, usare `n_ext ≥ 3` (`n_rows ≥ 7`); per benchmark e pubblicazioni scientifiche `n_ext ≥ 4` (`n_rows ≥ 9`). Con `n_rows < 7` la radiazione è sovrastimata di 1–5% al sole basso. Vedi `documentazione/PARAMETRI_RADIANCE.md`.

---

## Posizionamento e sviluppi

SolRatio v4.3.x è mantenuta come **edizione di riferimento**: riceve correzioni di
correttezza e riproducibilità, non nuove funzionalità (dettagli in
`documentazione/ROADMAP.md`). Lo sviluppo — modellazione 3D dei pali, bilancio
idrico/ET, resa energetica, geometrie di campo reali, interfaccia web —
prosegue nel prodotto hosted **SolRatio Pro**.

**Obiettivo aperto — validazione sperimentale**: confronto con misure PAR/DLI
da impianti agrivoltaici strumentati. Collaborazioni con gruppi sperimentali
sono benvenute (aprire una issue sul repository).

---

## Come citare

Se si utilizza SolRatio in lavori pubblici (relazioni tecniche, articoli, presentazioni), lo si può citare come segue:

> Pesavento, S. (2026). *SolRatio: Modello di irradianza al suolo e stima delle rese colturali per impianti agrivoltaici a tracker monoassiale* (v4.3.2). Zenodo. https://doi.org/10.5281/zenodo.19959581

**DOI:**

- **Concept DOI** (risolve sempre all'ultima versione): [`10.5281/zenodo.19959581`](https://doi.org/10.5281/zenodo.19959581) — da utilizzare per citare "SolRatio" in generale
- **DOI di versione v4.3.2** (questa edizione di riferimento): [`10.5281/zenodo.23116710`](https://doi.org/10.5281/zenodo.23116710)

DOI versioni precedenti — **⚠ v4.1.0–v4.3.0: coefficienti delle curve di resa non conformi alla Table S2 di Laub, K_agv da ricalcolare** (vedi CHANGELOG v4.3.1); **⚠ v4.1.0–v4.2.1: anche i K_agv in modalità tracking sono sovrastimati** (scena contro-ruotata, vedi CHANGELOG v4.3.0); i record restano immutabili per la riproducibilità storica e **non sono raccomandati per nuove citazioni**:

- v4.3.1: [`10.5281/zenodo.23110857`](https://doi.org/10.5281/zenodo.23110857) — stessi risultati della v4.3.2, che corregge due testi del report e della nota e la LICENSE
- v4.3.0: [`10.5281/zenodo.20683303`](https://doi.org/10.5281/zenodo.20683303)
- v4.2.1: [`10.5281/zenodo.20642574`](https://doi.org/10.5281/zenodo.20642574)
- v4.2.0: [`10.5281/zenodo.20277335`](https://doi.org/10.5281/zenodo.20277335)
- v4.1.2: [`10.5281/zenodo.19982399`](https://doi.org/10.5281/zenodo.19982399)
- v4.1.1: [`10.5281/zenodo.19960929`](https://doi.org/10.5281/zenodo.19960929)
- v4.1.0: [`10.5281/zenodo.19959582`](https://doi.org/10.5281/zenodo.19959582) — contiene anche il bug STEP 5 risolto in v4.1.1

Vedi `CITATION.cff` per i metadati completi e `documentazione/SolRatio_technical_note.md` per la descrizione completa del modello.

---

## Licenza

Apache License 2.0 — vedi [LICENSE](LICENSE).

In sintesi: è consentito usare, modificare, distribuire e integrare SolRatio in software commerciale, a condizione di mantenere l'attribuzione e includere una copia della licenza. La licenza include una clausola esplicita di concessione dei diritti di brevetto.

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
- **PAR fraction (Jacovides)** — Jacovides, C.P. et al. (2003). *Global photosynthetically active radiation and its relationship with global solar radiation in the Eastern Mediterranean basin*. Theoretical and Applied Climatology, 74(3–4), 227–233. https://doi.org/10.1007/s00704-002-0685-5
- **PVGIS / SARAH** — Huld, T., Müller, R., Gambardella, A. (2012). *A new solar radiation database for estimating PV performance in Europe and Africa*. Solar Energy, 86(6), 1803–1815. https://doi.org/10.1016/j.solener.2012.03.006
- **Agrivoltaico — riferimenti fondazionali** — Goetzberger & Zastrow (1982); Dupraz et al. (2011); Marrou et al. (2013); Trommsdorff et al. (2021). Riferimenti completi in `documentazione/SolRatio_technical_note.md`.
