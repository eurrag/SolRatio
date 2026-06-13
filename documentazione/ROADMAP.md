# SolRatio — Roadmap dell'edizione di riferimento

> Aggiornata con la v4.3.0. Le roadmap storiche delle versioni precedenti
> restano consultabili nei tag e nel `CHANGELOG.md`.

## Posizionamento (open-core)

**SolRatio v4.3.x è la Community/Reference Edition**: una base citabile e
riproducibile del metodo (ray-tracing dell'irradianza al suolo + curve di resa
Laub 2022), depositata su Zenodo con DOI. Questa edizione riceve **manutenzione
di correttezza e riproducibilità** — correzione di bug, chiarimenti documentali,
aggiornamenti della technical note — e non nuove funzionalità.

Lo sviluppo di nuove funzionalità — modellazione 3D dei pali di sostegno,
bilancio idrico/evapotraspirazione, resa energetica DC/AC, geometrie di campo
reali (KML), interfaccia web multi-utente — prosegue nella linea di prodotto **SolRatio Pro**, erogata come servizio
gestito, e non è previsto per il rilascio in questo repository.

## v4.3.x (manutenzione)

- Correzione degli errori segnalati dagli utenti (le segnalazioni tramite issue su GitHub sono benvenute).
- Riproducibilità: mantenimento del gate di regressione (Sample N-S 57.5 /
  Sample_EW 55.3, ±0.2 pp, riferimenti v4.3.0) su Windows e Linux.
- Eventuali estensioni della technical note (errata corrige, chiarimenti).

## Obiettivo aperto — validazione sperimentale (cross-cutting)

La validazione attuale è di tipo code-to-code (rispetto a bifacial_radiance
ufficiale), integrata da un riferimento indipendente basato sul workflow
nativo `set1axis` (v4.3.0).
Il confronto con **misure PAR/DLI in campo** da impianti agrivoltaici
strumentati resta l'obiettivo scientifico aperto di maggior valore:
le collaborazioni con gruppi sperimentali e i dataset anonimizzati,
condivisi tramite issue o pull request, sono benvenuti e verranno
integrati in un'appendice di validazione dedicata.
