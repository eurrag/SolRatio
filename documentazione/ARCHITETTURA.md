# SolRatio v4.1.0 — Architettura tecnica

*Modello integrato di irradianza al suolo e stima delle rese colturali per impianti agrivoltaici a tracker monoassiale.*

## Struttura directory

```
SolRatio_v4_1_0/
├── engine/                          # Codice sorgente
│   ├── VERSION                      # "4.1.0"
│   ├── br_engine.py                 # Motore bifacial_radiance (con tau, slope L3, diagnostica)
│   ├── calcola_br.py                # Entry point orchestrazione
│   ├── solratio_core.py             # Funzioni core (VF, shadow, Perez, DLI, zone)
│   ├── solratio_excel.py            # Lettura parametri + scrittura Excel
│   ├── solratio_edge.py             # Effetto bordo (funzioni ausiliarie)
│   ├── solratio_yield.py            # Curve resa colturale (Laub et al. 2022)
│   ├── solratio_pdf.py              # Report PDF (reportlab)
│   ├── solratio_sensitivity.py      # Analisi sensitività (non usato nel flusso BR)
│   ├── check_environment.py         # Verifica dipendenze (NEW v4.1.0)
│   ├── validazione_br.py            # Confronto SR vs BR ufficiale
│   ├── SolRatio_Calcolo.bas         # Modulo VBA Excel launcher
│   ├── _br_run.bat                   # Lanciatore Windows
│   ├── risultati_template.xlsx      # Template Excel risultati
│   └── test/                        # Batteria di test + orchestratore release
│       ├── release_orchestrator.py  # NEW v4.1.0 — orchestratore release
│       ├── _LANCIA_RELEASE_TEST.bat  # NEW v4.1.0 — launcher Windows
│       ├── run_battery.py           # Batteria sensitività (47 test)
│       ├── confronta_KPI.py         # Aggregatore KPI batteria
│       └── _LANCIA_BATTERIA.bat / _ANALIZZA_KPI.bat   # Launcher Windows
├── progetti/
│   └── <nome_progetto>/
│       ├── SolRatio_progetto.xlsm   # File input (foglio Parametri)
│       ├── PVGIS_*.csv              # Dati meteo PVGIS (serie multi-anno)
│       ├── PVGIS_*.epw              # File EPW generato (TMY composito)
│       ├── risultati_*.xlsx         # Output Excel
│       └── report_SolRatio_*.pdf    # Output PDF
├── documentazione/                  # Questa cartella
├── analisi/                         # Output analisi cross-progetto
├── README.md                        # Punto d'ingresso repository
├── LICENSE                          # Apache 2.0
├── CITATION.cff                     # Metadati citazione GitHub
├── .zenodo.json                     # Metadati Zenodo per DOI
├── requirements.txt                 # Dipendenze Python
└── .gitignore                       # File da escludere dal repo
```

## Moduli e responsabilità

### br_engine.py (motore principale)

Dipendenze: `bifacial_radiance`, `pvlib.tracking`, `numpy`, `pandas`, `subprocess`

Funzioni principali:

| Funzione | Input | Output | Descrizione |
|----------|-------|--------|-------------|
| `pvgis_to_epw()` | CSV PVGIS, lat, lon | EPW path, tmy_info | Converte PVGIS multi-anno in EPW TMY composito mese-per-mese |
| `run_annual()` | params dict, EPW path | dict risultati | Simulazione annuale: scene Radiance, gendaylit per ora, rtrace parallelo |
| `_compute_strip_width_br()` | solpos, params | float [m] | Larghezza fascia esterna dal P95 distanza ombra |
| `_apply_irrPlot_patch()` | — | — | Monkey-patch BR per evitare errore irrPlot senza display |
| `_apply_tau_material()` (v4.1.0) | rad, tau, module_name | — | Sostituisce materiale opaco con `trans` Radiance per pannelli semitrasparenti |

Flusso interno di `run_annual` (v4.1.0):

```
1. Setup workdir temporaneo (senza spazi nel path)
2. Carica EPW → metdata (bifacial_radiance.readWeatherFile)
3. Crea modulo Radiance (makeModule)
3b. Se tau > 0 → _apply_tau_material (override materiale a 'trans')  [v4.1.0]
4. Calcola angoli tracker (pvlib.tracking.singleaxis)
   - Slope L1: propaga axis_tilt e cross_axis_tilt
5. Filtra ore diurne (sole > 2°, GHI > 20 W/m²)
6. Costruisci sensori batch:
   - Centrali: x = 0 .. pitch (n_points punti)
   - Edge:     x = k·P .. (k+1)·P per k=1..n_ext-1
   - Outer:    x = n_ext·P .. n_ext·P + strip_width
   - Slope L3 (v4.1.0): z(x) = z0 + x · tan(slope_cross) per ogni sensore
7. Calcola quota ground dinamica (v4.1.0): se sensori L3 scendono sotto z=-0.01,
   abbassa il groundplane per evitare colpire il ring dal basso
8. Pre-genera scene per theta unici (cache)
   - Slope L2: hub_height per-fila (file a quote diverse)
9. Genera sky file (.rad) per ogni ora diurna
10. Esecuzione parallela: oconv + rtrace per ogni ora
11. Separa risultati per profilo (central, edge_k, outer)
12. Simulazione cielo aperto (sky+ground senza pannelli, 1 punto)
13. Diagnostica errori rtrace (v4.1.0): warning se errori > 1% delle ore diurne
14. Cleanup workdir temporaneo
15. Return dict con IRR_hourly, edge_irr, IRR_opensky, metadati
```

### calcola_br.py (entry point)

Dipendenze: `br_engine`, `solratio_core`, `solratio_excel`, `solratio_yield`,
`solratio_edge` (solo `compute_dns_monthly`, `compute_fc_ns`, `compute_kagv_impianto`)

Flusso:

```
1. Lettura parametri Excel (solratio_excel.read_parameters)
2. PVGIS → EPW (br_engine.pvgis_to_epw)
3. Simulazione BR annuale (br_engine.run_annual)
4. Ricostruzione matrice full (n_all × n_points)
5. PAR_FRAC variabile Jacovides → DLI giornaliero
6. Riferimento cielo aperto da IRR_opensky BR
7. Statistiche mensili (compute_monthly_stats, zone_stats)
8. Scrittura fogli Excel risultati
9. Curve resa colturale (Laub et al. 2022)
10. Effetto bordo BR (post-processing edge_irr da step 3)
11. Report PDF
12. Sentinella .pvlib_done per VBA
```

In v4.1.0 le call sites relative al trattamento pali (`write_impatto_pali`,
sezione PDF Pali, display Pali nei parametri) sono state commentate. Codice
delle funzioni stesse conservato dormiente in `solratio_yield.py` e
`solratio_core.py` per riattivazione futura in v4.2 con scena Radiance 3D.


### check_environment.py (NEW v4.1.0)

Utility di verifica dell'ambiente: controlla che tutti i pacchetti Python
richiesti siano installati con la versione corretta, e che i comandi
Radiance (`gendaylit`, `oconv`, `rtrace`) siano nel PATH di sistema.

Lanciabile come CLI: `python engine/check_environment.py`.

### solratio_core.py (invariato da v3.3.4, parzialmente usato)

Funzioni **usate** in v4.1.0:

| Funzione | Uso in v4 |
|----------|-----------|
| `compute_par_frac()` | PAR_FRAC variabile (Jacovides et al. 2004) |
| `compute_monthly_stats()` | Percentili mensili DLI per profilo |
| `zone_stats()` | Statistiche per zona (sotto-tracker, bordo, centrale, SAU) |
| `zone_masks()` | Maschere zone spaziali |
| `trapz_zone_mean()` | Media integrale trapezoidale per zona |
| `get_pvgis_data()` | Caricamento PVGIS per FC_NS (effetto bordo) |
| `compute_solar_and_tracker()` | Posizioni solari per FC_NS |
| `LAUB_COEFFICIENTS` | Coefficienti resa colturale |

Funzioni **non usate** in v4.1.0 (legacy SR / dormienti):

| Funzione | Motivo |
|----------|--------|
| `compute_vf_matrix()` | Sostituito da ray-tracing BR |
| `compute_shadow_matrix()` | Sostituito da ray-tracing BR |
| `compute_perez_components()` | Sostituito da gendaylit Radiance |
| `compute_irradiance_matrix()` | Sostituito da ray-tracing BR |
| `compute_post_shadow()` | Pali rimandati a v4.2 (modellazione 3D nella scena Radiance) |

### solratio_excel.py

Lettura parametri dal foglio Parametri (.xlsm) e scrittura di tutti i fogli
risultati nel file output .xlsx. In v4.0.0 sono state aggiunte le celle B48-B51
per i parametri Radiance. In v4.1.0 le celle B21/B22 (`d_palo`, `spaziatura_pali`)
sono lette per retrocompatibilità ma ignorate dal flusso (pali fuori scope).

### solratio_edge.py

In v4.1.0, le funzioni di calcolo profili bordo (`compute_edge_profiles`,
`_compute_single_profile`, `panel_axes_edge`, `panel_axes_outer`) **non sono
più chiamate** — sostituite dal ray-tracing BR diretto. L