# SolRatio — Roadmap e bug noti

## Stato attuale (v4.1.0, 2026-05-01)

Prima release pubblica con DOI Zenodo. Motore BR validato, infrastruttura di
rilascio completa (LICENSE Apache 2.0, README, requirements, CITATION.cff,
.zenodo.json), nuove feature applicative implementate (tau via materiale Radiance
trans, ottimizzazione H_min via curva di Pareto, slope L3 con sensori sul piano
inclinato), pali rimossi dal flusso (rimandati a v4.2 con modellazione 3D).

Vedi `CHANGELOG.md` per i dettagli delle modifiche v4.1.0.

## Stato precedente (v4.0.0, 2026-04-10)

Il motore BR è funzionante per simulazione annuale con output Excel e PDF.
I test effettuati sono sul progetto località esempio (lat 45.30°N, lon 9.34°E).

### Bug noti

Nessun bug noto al momento. I seguenti bug sono stati risolti durante lo
sviluppo (dettagli nel CHANGELOG):

- [RISOLTO] Parsing rtrace `-oovs` (leggeva coordinate come RGB)
- [RISOLTO] Shape mismatch n_all vs 8760
- [RISOLTO] UnboundLocalError n_ext con br_n_rows manuale
- [RISOLTO] TMY anno singolo invece di composito mese-per-mese
- [RISOLTO] Riferimento open sky da GHI (ora da simulazione BR)
- [RISOLTO] Effetto bordo misto SR/BR (ora tutto BR)


## Stato delle verifiche TODO precedenti (chiusura v4.0.0 → v4.1.0)

I TODO della v4.0.0 sono stati chiusi (completati o riformulati) in v4.1.0:

- [✓] ~~Validazione vs v3.3.4~~: superato — v3.x è dichiarato deprecato. Riferimento
  scientifico per la validazione è ora `bifacial_radiance` ufficiale (NREL),
  con cui v4 è allineato a MBE<1%, R²>0.998 (località esempio (lat 45.30°N, lon 9.34°E)).
- [parziale] **Test su progetti multipli**: già eseguito un primo round su progetto
  Sample (Pianura Padana, lat 45.30°N), e batteria test_battery (47 test, 45 OK + 2 SKIP). Da estendere con un
  test specifico al rilascio v4.1.0 sui progetti reali con tau/H_min/L3 attivi.
- [da fare al rilascio] **Verifica ΔK_agv effetto bordo positivo** su almeno 2
  progetti diversi.
- [da fare al rilascio] **Verifica PAR relativa ≤ 1.0** sui report v4.1.0.
- [✓] **Diagnostica errori rtrace**: implementata in v4.1.0 (warning se errori > 1%
  delle ore, con elenco cause probabili).
- [da fare] **Forzatura nRows dispari**: validazione input br_n_rows ancora aperta.
- [✓] **Trasmittanza pannello (tau)**: implementata in v4.1.0 via materiale
  Radiance `trans` (vedi CHANGELOG v4.1.0).
- [✓ parziale] **Pendenza terreno**: implementato slope L3 per i sensori +
  groundplane abbassato dinamicamente. Resta aperto L3 completo con polygon
  ground inclinato per slope > 15% (rimandato a v4.2).


## Sviluppi futuri

### v4.2 — Pali, multi-anno, ground inclinato

- **Pali nella scena Radiance**: reintegrare i pali di sostegno come oggetti
  cilindrici nella scena BR (in v4.0.0 erano gestiti analiticamente con
  post-shadow; in v4.1.0 sono stati rimossi dal flusso, codice conservato
  dormiente). Richiede: oggetti cilindrici Radiance posizionati sull'asse tracker
  con spaziatura B22, riattivazione delle call sites commentate in
  `calcola_br.py`, `solratio_edge.py`, `solratio_pdf.py`, `solratio_excel.py`.

- **Modalità multi-anno**: eseguire la simulazione su tutti gli anni PVGIS
  (non solo TMY) e calcolare statistiche inter-annuali (P10/P50/P90 di K_agv).
  Permette di stimare la variabilità climatica del sito.

- **Ground plane inclinato (L3 completo)**: in v4.1.0 i sensori sono già
  posizionati sul piano terreno (L3 parziale), ma il ground geometrico
  Radiance (`groundplane ring`) resta orizzontale. Per slope > 15% può
  introdurre artefatti nell'albedo riflessa. Soluzione: sostituire ring
  con polygon inclinato secondo slope_pct/slope_azimuth.

- **Cache scene persistente**: salvare le scene pre-generate (.oct) su disco
  per evitare ri-generazione tra run successive sullo stesso progetto.

### v4.3 — Funzionalità avanzate

- **Pannelli semi-trasparenti avanzati**: in v4.1.0 è già supportato `tau`
  via materiale Radiance `trans` (mappatura semplice per pannelli a vetro
  convenzionali, `tspec=1.0`). Per pannelli organici o thin-film con
  trasmissione diffusa, estendere a materiali `BRTDfunc` o `prism2` con
  taratura sperimentale.

- **Trade-off costo-resa H_min (formulazione B)**: estendere
  `solratio_optimization.py` con funzione di costo strutturale
  `cost(H_min)` parametrizzata su €/m altezza, e ottimizzazione
  `argmax K_agv − λ · cost(H_min)` con lambda configurabile dal foglio
  Parametri.

- **Bifacciale**: estendere il modello per calcolare l'irradianza sulla faccia
  posteriore dei moduli fotovoltaici (per produzione e