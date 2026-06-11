# SolRatio — Roadmap dell'edizione di riferimento

> Aggiornata con la v4.2.1. Le roadmap storiche delle versioni precedenti
> restano consultabili nei tag e nel `CHANGELOG.md`.

## Posizionamento (open-core)

**SolRatio v4.2.x è la Community/Reference Edition**: una base citabile e
riproducibile del metodo (ray-tracing dell'irradianza al suolo + curve di resa
Laub 2022), depositata su Zenodo con DOI. Questa edizione riceve **manutenzione
di correttezza e riproducibilità** — fix di bug, chiarimenti documentali,
aggiornamenti della technical note — e non nuove funzionalità.

Lo sviluppo di nuove funzionalità — modellazione 3D dei pali di sostegno,
bilancio idrico/evapotraspirazione, resa energetica DC/AC, geometrie di campo
reali (KML), interfaccia web multi-utente — prosegue nella linea prodotto
hosted **SolRatio Pro** e non è pianificato per il rilascio in questo
repository.

## v4.2.x (manutenzione)

- Fix di correttezza segnalati dagli utenti (issue GitHub benvenute).
- Riproducibilità: mantenimento del gate di regressione (Sample N-S 84.1 /
  Sample_EW 79.2, ±0.2 pp) su Windows e Linux.
- Eventuali estensioni della technical note (errata, chiarimenti).

## Obiettivo aperto — validazione sperimentale (cross-cutting)

La validazione attuale è code-to-code (vs bifacial_radiance ufficiale).
Il confronto con **misure PAR/DLI in campo** da impianti agrivoltaici
strumentati resta l'obiettivo scientifico aperto di maggior valore:
collaborazioni con gruppi sperimentali e dataset anonimizzati condivisi via
issue/pull-request sono benvenuti, e verranno incorporati in un'appendice di
validazione dedicata.
