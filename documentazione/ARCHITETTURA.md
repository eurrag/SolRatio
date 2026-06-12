# SolRatio v4.3.0 — Architettura tecnica

> Edizione di riferimento (Community/Reference Edition). Questo documento
> descrive la struttura e le responsabilità dei moduli del perimetro
> pubblico; il flusso di calcolo è illustrato in `architettura_br_engine.md`
> e nella technical note (§3).

## Struttura

```
SolRatio/
├── engine/
│   ├── VERSION                   # fonte unica della versione (letta da Python e VBA)
│   ├── calcola_br.py             # entry point: parametri → meteo → run_annual → output
│   ├── br_engine.py              # motore bifacial_radiance: PVGIS→EPW, scena, rtrace parallelo
│   ├── _scene_cache.py           # cache octree .oct (frozen, per workflow ≤200 angoli unici)
│   ├── solratio_core.py          # fisica: solare/tracker, VF, ombre, Perez, PAR/DLI, zone, self-test
│   ├── solratio_excel.py         # read_parameters + scrittura workbook risultati (8 fogli, +Bifacciale se b_f>0)
│   ├── solratio_edge.py          # effetto bordo perimetrale, correzione FC_NS
│   ├── solratio_yield.py         # curve Laub 2022 → K_agv per coltura/zona/campo
│   ├── solratio_pdf.py           # report PDF di sintesi (reportlab + matplotlib)
│   ├── solratio_multiyear.py     # modalità multi-anno, quantili P10/P50/P90
│   ├── solratio_bifacial.py      # energia bifacciale beta-tier (view-factor)
│   ├── validazione_br.py         # confronto code-to-code SR vs bifacial_radiance ufficiale
│   ├── check_environment.py      # verifica dipendenze (Python + binari Radiance)
│   ├── SolRatio_Calcolo.bas      # VBA: launcher Excel (Calcola / Verifica / Test Python)
│   └── SolRatio_VersionLabel.bas # VBA: auto-update label versione (Workbook_Open)
├── progetti/Sample/              # progetto dimostrativo N-S (benchmark di validazione + gate)
├── progetti/Sample_EW/           # variante E-W (gate + confronto axis_azimuth)
├── _smoke_check_kagv.py          # verifica K_agv del gate
├── _smoke_regression.bat / .sh   # smoke di regressione (Windows / Linux-macOS)
└── documentazione/               # questa cartella
```

## Responsabilità dei moduli

| Modulo | Input | Output | Note |
|---|---|---|---|
| `calcola_br` | `SolRatio_progetto.xlsm` | `risultati_*.xlsx`, `report_*.pdf`, `.br_done` | orchestrazione end-to-end; gestione errori con `br_error.txt` |
| `br_engine` | parametri, CSV PVGIS | EPW (TMY, header UTC), array irradianza orari | `pvgis_to_epw`, `run_annual`; rtrace in parallelo; cache .oct frozen |
| `solratio_core` | parametri, meteo | tracker theta, VF/ombre, PAR/DLI, statistiche zone | nessuna dipendenza da openpyxl; `self_test()` all'avvio |
| `solratio_excel` | workbook, risultati | fogli: Riepilogo, Parametri, PAR_DLI_Profilo, Profilo_PAR_Spaziale, DLI_Percentili, Heatmap_PAR, Resa_Colturale, Effetto_Bordo (+Bifacciale) | `read_parameters` valida i parametri con messaggi espliciti |
| `solratio_edge` | profili perimetrali | FC_NS, K_agv impianto | technical note §2.6 |
| `solratio_yield` | statistiche PAR/DLI | K_agv per 9 colture | curve Laub 2022 (fit Table S2) |
| `solratio_pdf` | parametri + statistiche | PDF di sintesi | fallback senza matplotlib |
| `solratio_multiyear` | xlsm + `--years` | `multiyear_results.csv`, `multiyear_quantiles.json` | un run annuale per anno; resume |
| `solratio_bifacial` | `bifaciality_factor>0` | foglio Bifacciale | POA back = 0.5·albedo·GHI (beta tier) |
| `validazione_br` | xlsm | `validazione_*.csv`, metriche MBE/RMSE/R² | due giornate campione (21/3, 21/6) |

## Flusso end-to-end

1. `read_parameters` legge e valida il foglio `Parametri`;
2. `pvgis_to_epw` compone il TMY mese-per-mese dal CSV PVGIS (header EPW in UTC);
3. `run_annual` costruisce la scena, calcola gli angoli tracker (8760 h),
   filtra le ore diurne, esegue `rtrace` in parallelo, restituisce i profili
   (centrale, bordo, esterno) e il riferimento cielo aperto;
4. post-processing: PAR (Jacovides), DLI, statistiche mensili per zona;
5. resa colturale: K_agv(RSR) per coltura, aggregazione di campo con FC_NS;
6. scrittura `risultati_*.xlsx` + `report_SolRatio_*.pdf`.
