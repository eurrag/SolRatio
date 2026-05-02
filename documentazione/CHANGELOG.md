# SolRatio — Changelog

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

