# SolRatio v4.2.0

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19959581.svg)](https://doi.org/10.5281/zenodo.19959581)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Modello di irradianza al suolo e stima delle rese colturali per impianti agrivoltaici a tracker monoassiale.**

SolRatio Ã¨ uno strumento integrato che combina la simulazione della radiazione solare disponibile per le colture sottostanti ai pannelli fotovoltaici (tramite ray-tracing 3D fisicamente accurato Radiance + bifacial_radiance) con le curve dose-risposta di Laub et al. (2022) per la stima delle rese colturali in regime di ombreggiamento agrivoltaico. Fornisce profili spaziali e temporali di PAR e DLI, e il coefficiente agrivoltaico K_agv per nove categorie colturali, necessari alla verifica dei requisiti agronomici previsti dalle Linee Guida MiTE (D.M. 436/2023) e alla valutazione della compatibilitÃ  tra produzione energetica e produzione agricola.

---

## Caratteristiche

- Simulazione oraria 3D ray-tracing (8760 ore/anno) con motore Radiance
- Geometria configurabile: tracker monoassiale, pitch, larghezza modulo, altezza minima, slope terreno
- Backtracking + tilt fisso supportati (modalitÃ  configurabile)
- Trasmittanza pannello (tau) modellata via materiale Radiance `trans` per pannelli semitrasparenti
- Effetto bordo calcolato direttamente da BR sui pitch fisici della scena
- Curve di resa colturale Laub et al. 2022 (9 colture) con calcolo K_agv
- Output: report Excel multi-foglio + report PDF di sintesi
- Interfaccia Excel/VBA per gestione progetti senza scrivere codice
- Validazione vs bifacial_radiance ufficiale: MBE < 1%, RÂ² > 0.998

---

## Requisiti

### Software esterno (non installabile via pip)

- **Radiance â‰¥ 5.4** â€” i comandi `gendaylit`, `oconv`, `rtrace` devono essere nel PATH di sistema. [Download](https://www.radiance-online.org/)

### Python

- Python â‰¥ 3.10
- Pacchetti: `bifacial_radiance`, `pvlib`, `numpy`, `pandas`, `openpyxl`, `lxml` (vedi `requirements.txt`)

### Sistema operativo

Sviluppato e testato su Windows 11. Compatibile in linea di principio con Linux/macOS dove Radiance Ã¨ disponibile, ma il workflow Excel/VBA richiede Microsoft Excel.

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

Nella cartella `progetti/` Ã¨ incluso un progetto **`Sample`** dimostrativo, basato su una localitÃ  di pianura padana (lat 45.30Â°N, lon 9.34Â°E), con dati meteorologici PVGIS-SARAH3 giÃ  scaricati. Per creare un nuovo progetto: duplica la cartella `Sample`, rinominala, modifica i parametri nel foglio Excel, scarica i dati PVGIS della tua localitÃ  da [PVGIS](https://re.jrc.ec.europa.eu/pvg_tools/it/) e sostituiscili nella tua cartella.

---

## Struttura del repository

```
SolRatio/
â”œâ”€â”€ engine/                          # Codice sorgente
â”‚   â”œâ”€â”€ VERSION                      # Versione corrente: "4.1.0"
â”‚   â”œâ”€â”€ calcola_br.py                # Entry point principale
â”‚   â”œâ”€â”€ br_engine.py                 # Motore bifacial_radiance
â”‚   â”œâ”€â”€ solratio_core.py             # Funzioni core (PAR, DLI, zone, statistiche)
â”‚   â”œâ”€â”€ solratio_excel.py            # I/O Excel (lettura parametri, scrittura risultati)
â”‚   â”œâ”€â”€ solratio_edge.py             # Effetto bordo perimetrale
â”‚   â”œâ”€â”€ solratio_yield.py            # Curve di resa colturale (Laub et al. 2022)
â”‚   â”œâ”€â”€ solratio_pdf.py              # Generazione report PDF
â”‚   â”œâ”€â”€ solratio_sensitivity.py      # Analisi di sensitivitÃ  parametrica
â”‚   â”œâ”€â”€ validazione_br.py            # Confronto SR vs BR ufficiale
â”‚   â”œâ”€â”€ check_environment.py         # Verifica dipendenze
â”‚   â”œâ”€â”€ SolRatio_Calcolo.bas         # Modulo VBA per Excel launcher
â”‚   â””â”€â”€ test/                        # Batteria di test automatica
â”œâ”€â”€ documentazione/                  # Docs tecnica (architettura, formule, roadmap)
â”œâ”€â”€ progetti/                        # Progetti utente (input + output)
â”œâ”€â”€ analisi/                         # Output di analisi cross-progetto
â”œâ”€â”€ requirements.txt
â”œâ”€â”€ LICENSE                          # Apache 2.0
â”œâ”€â”€ CITATION.cff                     # Metadati di citazione
â””â”€â”€ README.md                        # Questo file
```

---

## Documentazione

Documentazione tecnica nella cartella `documentazione/`:

- `ARCHITETTURA.md` â€” struttura moduli e responsabilitÃ 
- `architettura_br_engine.md` â€” pipeline di calcolo del motore BR
- `FORMULE.md` â€” formule fisiche implementate
- `PARAMETRI_RADIANCE.md` â€” parametri rtrace e loro effetto
- `CHANGELOG.md` â€” storico delle versioni
- `ROADMAP.md` â€” sviluppi futuri
- `introduzione_solratio_relazione.md` â€” descrizione del modello in linguaggio non-tecnico

---

## Validazione

Il modello Ã¨ validato confrontando i risultati con il workflow ufficiale di bifacial_radiance (NREL) sullo stesso progetto, stessi parametri, stessi dati meteorologici. Risultati su una localitÃ  di pianura padana (lat 45.30Â°N, lon 9.34Â°E, dati PVGIS-SARAH3 2005-2023):

| Giorno | MBE | RMSE | RÂ² |
|--------|-----|------|----|
| 21 marzo (equinozio) | +0.54% | 0.80% | 0.9982 |
| 21 giugno (solstizio) | +0.42% | 0.49% | 0.9989 |

Lo scostamento residuo Ã¨ rumore numerico intrinseco di Radiance (stocasticitÃ  ambient sampling). Script: `engine/validazione_br.py`.

---

## Limitazioni note di v4.1.2

- **Pali di sostegno**: non sono modellati nella scena Radiance. Saranno aggiunti come oggetti cilindrici 3D in v4.2.
- **ModalitÃ  multi-anno (variabilitÃ  interannuale P10/P50/P90)**: prevista per v4.2.
- **Ottimizzazione pitch**: rimossa (K_agv Ã¨ monotonicamente crescente con pitch, l'ottimo Ã¨ banale). L'ottimizzazione utile Ã¨ quella di H_min (altezza minima da terra), inclusa in v4.1.
- **Bifacciale (faccia posteriore moduli)**: non calcolata; si valuti per v4.3.
- **Numero minimo di file in scena Radiance** (`n_rows`): per simulazioni accurate del pitch centrale di un impianto medio-grande, usare `n_ext â‰¥ 3` (`n_rows â‰¥ 7`). Con n_rows < 7 la radiazione Ã¨ sovrastimata di 1-5% (sole basso). Vedi `documentazione/PARAMETRI_RADIANCE.md` per la tabella di riferimento.

---

## Come citare

Se usi SolRatio in lavori pubblici (relazioni tecniche, articoli, presentazioni), puoi citarlo come:

> Pesavento, S. (2026). *SolRatio: Modello di irradianza al suolo e stima delle rese colturali per impianti agrivoltaici a tracker monoassiale* (v4.2.0). Zenodo. https://doi.org/10.5281/zenodo.20277335

**DOI:**
- **Concept DOI** (sempre-ultima-versione): [`10.5281/zenodo.19959581`](https://doi.org/10.5281/zenodo.19959581) â€” usalo per citare "SolRatio" in generale
- **Versione v4.2.0** (immutabile, raccomandata): [`10.5281/zenodo.20277335`](https://doi.org/10.5281/zenodo.20277335) â€” usalo per citare la versione esatta che hai scaricato

DOI versioni precedenti:
- v4.1.1: [`10.5281/zenodo.19960929`](https://doi.org/10.5281/zenodo.19960929)
- v4.1.0: [`10.5281/zenodo.19959582`](https://doi.org/10.5281/zenodo.19959582) â€” contiene il bug STEP 5 risolto in v4.1.1, **non raccomandato per nuove citazioni**

Vedi `CITATION.cff` per i metadati completi.

---

## Licenza

Apache License 2.0 â€” vedi [LICENSE](LICENSE).

In sintesi: puoi usare, modificare, distribuire e integrare SolRatio in software commerciale, mantenendo l'attribuzione e includendo una copia della licenza. La licenza include una clausola esplicita di concessione dei diritti di brevetto.

---

## Autore

**Stefano Pesavento, PhD** â€” Independent researcher

Per segnalazioni di bug, suggerimenti, contributi: aprire una issue sul repository GitHub.

---

## Riferimenti scientifici

- **Radiance** â€” Ward, G. (1994). *The RADIANCE lighting simulation and rendering system*. SIGGRAPH '94.
- **bifacial_radiance** â€” Ayala Pelaez, S. & Deline, C. (2020). *bifacial_radiance: a Python package for modeling bifacial solar photovoltaic systems*. JOSS, 5(50).
- **pvlib** â€” Holmgren, W., Hansen, C., Mikofski, M. (2018). *pvlib python: a python package for modeling solar energy systems*. JOSS, 3(29).
- **Modello Perez** â€” Perez, R. et al. (1990). *Modeling daylight availability and irradiance components from direct and global irradiance*. Solar Energy, 44(5).
- **Curve di resa Laub** â€” Laub, M. et al. (2022). *Contrasting yield responses at varying levels of shade suggest different suitability of crops for dual land-use systems*. Agronomy for Sustainable Development, 42:51.
- **PAR fraction (Jacovides)** â€” Jacovides, C.P. et al. (2004). *Comparative study of various correlations in estimating hourly diffuse fraction of global solar radiation*. Renewable Energy, 31(15).
