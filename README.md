# SolRatio v4.1.2

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19959587.svg)](https://doi.org/10.5281/zenodo.19959587)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Modello di irradianza al suolo e stima delle rese colturali per impianti agrivoltaici a tracker monoassiale.**

SolRatio è uno strumento integrato che combina la simulazione della radiazione solare disponibile per le colture sottostanti ai pannelli fotovoltaici (tramite ray-tracing 3D fisicamente accurato Radiance + bifacial_radiance) con le curve dose-risposta di Laub et al. (2022) per la stima delle rese colturali in regime di ombreggiamento agrivoltaico. Fornisce profili spaziali e temporali di PAR e DLI, e il coefficiente agrivoltaico K_agv per nove categorie colturali, necessari alla verifica dei requisiti agronomici previsti dalle Linee Guida MiTE (D.M. 436/2023) e alla valutazione della compatibilità tra produzione energetica e produzione agricola.

---

## Caratteristiche

- Simulazione oraria 3D ray-tracing (8760 ore/anno) con motore Radiance
- Geometria configurabile: tracker monoassiale, pitch, larghezza modulo, altezza minima, slope terreno
- Backtracking + tilt fisso supportati (modalità configurabile)
- Trasmittanza pannello (tau) modellata via materiale Radiance `trans` per pannelli semitrasparenti
- Effetto bordo calcolato direttamente da BR sui pitch fisici della scena
- Curve di resa colturale Laub et al. 2022 (9 colture) con calcolo K_agv
- Output: report Excel multi-foglio + report PDF di sintesi
- Interfaccia Excel/VBA per gestione progetti senza scrivere codice
- Validazione vs bifacial_radiance ufficiale: MBE < 1%, R² > 0.998

---

## Requisiti

### Software esterno (non installabile via pip)

- **Radiance ≥ 5.4** — i comandi `gendaylit`, `oconv`, `rtrace` devono essere nel PATH di sistema. [Download](https://www.radiance-online.org/)

### Python

- Python ≥ 3.10
- Pacchetti: `bifacial_radiance`, `pvlib`, `numpy`, `pandas`, `openpyxl`, `lxml` (vedi `requirements.txt`)

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

### Da riga di comando

```cmd
python engine\calcola_br.py "progetti\Sample\SolRatio_progetto.xlsm"
```

### Da Excel (consigliato per uso ricorrente)

1. Apri `SolRatio_progetto.xlsm` con Excel + macro abilitate
2. Compila i parametri nel foglio `Parametri` (geometria, ottica, sito)
3. Premi il pulsante "Calcola" sul foglio `Launcher`
4. I risultati vengono scritti in `risultati_<progetto>.xlsx` e `report_SolRatio_<progetto>.pdf` nella stessa cartella

### Esempi inclusi

Nella cartella `progetti/` è incluso un progetto **`Sample`** dimostrativo, basato su una località di pianura padana (lat 45.30°N, lon 9.34°E), con dati meteorologici PVGIS-SARAH3 già scaricati. Per creare un nuovo progetto: duplica la cartella `Sample`, rinominala, modifica i parametri nel foglio Excel, scarica i dati PVGIS della tua località da [PVGIS](https://re.jrc.ec.europa.eu/pvg_tools/it/) e sostituiscili nella tua cartella.

---

## Struttura del repository

```
SolRatio/
├── engine/                          # Codice sorgente
│   ├── VERSION                      # Versione corrente: "4.1.0"
│   ├── calcola_br.py                # Entry point principale
│   ├── br_engine.py                 # Motore bifacial_radiance
│   ├── solratio_core.py             # Funzioni core (PAR, DLI, zone, statistiche)
│   ├── solratio_excel.py            # I/O Excel (lettura parametri, scrittura risultati)
│   ├── solratio_edge.py             # Effetto bordo perimetrale
│   ├── solratio_yield.py            # Curve di resa colturale (Laub et al. 2022)
│   ├── solratio_pdf.py              # Generazione report PDF
│   ├── solratio_sensitivity.py      # Analisi di sensitività parametrica
│   ├── validazione_br.py            # Confronto SR vs BR ufficiale
│   ├── check_environment.py         # Verifica dipendenze
│   ├── SolRatio_Calcolo.bas         # Modulo VBA per Excel launcher
│   └── test/                        # Batteria di test automatica
├── documentazione/                  # Docs tecnica (architettura, formule, roadmap)
├── progetti/                        # Progetti utente (input + output)
├── analisi/                         # Output di analisi cross-progetto
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
- `PARAMETRI_RADIANCE.md` — parametri rtrace e loro effetto
- `CHANGELOG.md` — storico delle versioni
- `ROADMAP.md` — sviluppi futuri
- `introduzione_solratio_relazione.md` — descrizione del modello in linguaggio non-tecnico

---

## Validazione

Il modello è validato confrontando i risultati con il workflow ufficiale di bifacial_radiance (NREL) sullo stesso progetto, stessi parametri, stessi dati meteorologici. Risultati su una località di pianura padana (lat 45.30°N, lon 9.34°E, dati PVGIS-SARAH3 2005-2023):

| Giorno | MBE | RMSE | R² |
|--------|-----|------|----|
| 21 marzo (equinozio) | +0.54% | 0.80% | 0.9982 |
| 21 giugno (solstizio) | +0.42% | 0.49% | 0.9989 |

Lo scostamento residuo è rumore numerico intrinseco di Radiance (stocasticità ambient sampling). Script: `engine/validazione_br.py`.

---

## Limitazioni note di v4.1.2

- **Pali di sostegno**: non sono modellati nella scena Radiance. Saranno aggiunti come oggetti cilindrici 3D in v4.2.
- **Modalità multi-anno (variabilità interannuale P10/P50/P90)**: prevista per v4.2.
- **Ottimizzazione pitch**: rimossa (K_agv è monotonicamente crescente con pitch, l'ottimo è banale). L'ottimizzazione utile è quella di H_min (altezza minima da terra), inclusa in v4.1.
- **Bifacciale (faccia posteriore moduli)**: non calcolata; si valuti per v4.3.
- **Numero minimo di file in scena Radiance** (`n_rows`): per simulazioni accurate del pitch centrale di un impianto medio-grande, usare `n_ext ≥ 3` (`n_rows ≥ 7`). Con n_rows < 7 la radiazione è sovrastimata di 1-5% (sole basso). Vedi `documentazione/PARAMETRI_RADIANCE.md` per la tabella di riferimento.

---

## Come citare

Se usi SolRatio in lavori pubblici (relazioni tecniche, articoli, presentazioni), puoi citarlo come:

> Pesavento, S. (2026). *SolRatio: Modello di irradianza al suolo e stima delle rese colturali per impianti agrivoltaici a tracker monoassiale* (v4.1.1). Zenodo. https://doi.org/10.5281/zenodo.19960929

**DOI:**
- **Concept DOI** (sempre-ultima-versione): [`10.5281/zenodo.19959587`](https://doi.org/10.5281/zenodo.19959587) — usalo per citare "SolRatio" in generale
- **Versione v4.1.1** (immutabile, raccomandata): [`10.5281/zenodo.19960929`](https://doi.org/10.5281/zenodo.19960929) — usalo per citare la versione esatta che hai scaricato

DOI versione precedente (v4.1.0): [`10.5281/zenodo.19959582`](https://doi.org/10.5281/zenodo.19959582) — contiene il bug STEP 5 risolto in v4.1.1, **non raccomandato per nuove citazioni**.

Vedi `CITATION.cff` per i metadati completi.

---

## Licenza

Apache License 2.0 — vedi [LICENSE](LICENSE).

In sintesi: puoi usare, modificare, distribuire e integrare SolRatio in software commerciale, mantenendo l'attribuzione e includendo una copia della licenza. La licenza include una clausola esplicita di concessione dei diritti di brevetto.

---

## Autore

**Stefano Pesavento, PhD** — Independent researcher

Per segnalazioni di bug, suggerimenti, contributi: aprire una issue sul repository GitHub.

---

## Riferimenti scientifici

- **Radiance** — Ward, G. (1994). *The RADIANCE lighting simulation and rendering system*. SIGGRAPH '94.
- **bifacial_radiance** — Ayala Pelaez, S. & Deline, C. (2020). *bifacial_radiance: a Python package for modeling bifacial solar photovoltaic systems*. JOSS, 5(50).
- **pvlib** — Holmgren, W., Hansen, C., Mikofski, M. (2018). *pvlib python: a python package for modeling solar energy systems*. JOSS, 3(29).
- **Modello Perez** — Perez, R. et al. (1990). *Modeling daylight availability and irradiance components from direct and global irradiance*. Solar Energy, 44(5).
- **Curve di resa Laub** — Laub, M. et al. (2022). *Contrasting yield responses at varying levels of shade suggest different suitability of crops for dual land-use systems*. Agronomy for Sustainable Development, 42:51.
- **PAR fraction (Jacovides)** — Jacovides, C.P. et al. (2004). *Comparative study of various correlations in estimating hourly diffuse fraction of global solar radiation*. Renewable Energy, 31(15).
