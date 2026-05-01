# SolRatio — Changelog

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

