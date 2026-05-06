# Piano di sviluppo SolRatio v4.2

**Data:** 2026-05-02
**Stato di partenza:** v4.1.2 (rilasciata, DOI Zenodo `10.5281/zenodo.19959587`)
**Riferimento scope:** `documentazione/ROADMAP.md` § "v4.2" e § "v4.3" — con
**riassegnazioni richieste dall'utente il 2026-05-02**:

> _"sposta i pali alla versione 4.3 e anticipa alla versione 4.2 quello che è
> previsto per la 4.3"_
>
> _"il trade-off costo H_min spostalo alla 4.4"_

Quindi:

- **v4.2** (cartella nuova `SolRatio_v4_2/`): include i 7 item v4.2 originali
  meno i pali, **più** Pannelli BRTDfunc e Bifacciale (anticipati da v4.3).
- **v4.3**: Pali nella scena Radiance (3D).
- **v4.4**: Trade-off costo-resa H_min (formulazione B) + LCOE.

La ROADMAP.md va aggiornata di conseguenza (vedi §10).

**Decisioni utente registrate (2026-05-02):**

- **D1**: cartella nuova `SolRatio_v4_2/` (copia da v4.1).
- **D2**: singola release `v4.2.0` con tutti i 9 item.
- **D3**: ok aggiunta `validazione_<feature>.csv` per feature scientifiche.
- **D4**: Bifacciale = scope **β** (energia PV bifacciale, no LCOE).
- **D5**: Pannelli avanzati = scope **α** (BRTDfunc spec/diff, no prism2/BSDF).
- **D6**: Trade-off costo H_min **spostato a v4.4** (esce da v4.2).
- **D7**: Multi-anno = strategia **A** (sequenziale + incrementale + flag `--years`).

---

## 1. Scopo del documento

Operativizzare gli item v4.2 in un piano di esecuzione con: ordine, file
impattati, criteri di accettazione, stima di tempo. Le decisioni di scope
(D1-D7) sono **risolte e registrate al §3**: il piano è esecutivo.

---

## 2. Scope confermato

### v4.2 (9 item)

| # | Item | Tipo | Origine ROADMAP |
|---|------|------|-----------------|
| 2  | Modalità multi-anno (P10/P50/P90) | Feature scientifica | v4.2 originale |
| 3  | Ground plane inclinato (L3 completo) | Feature scientifica | v4.2 originale |
| 4  | Cache scene `.oct` persistente | Performance | v4.2 originale |
| 5  | Layout cartella progetto standardizzato | Refactor | v4.2 originale |
| 6  | Script release end-to-end | Tooling/DevX | v4.2 originale |
| 7  | Frame coordinate sensori per `axis_azimuth` arbitrario | Refactor architetturale | v4.2 originale |
| 8  | Auto-update label versione Excel (VBA) | Tooling/DevX | v4.2 originale |
| 9  | Pannelli semi-trasparenti avanzati (BRTDfunc) | Feature scientifica | _anticipato da v4.3_ |
| 11 | Bifacciale (energia PV front+rear) | Feature scientifica | _anticipato da v4.3_ |

### v4.3 (Pali)

| # | Item | Tipo |
|---|------|------|
| 1 | Pali nella scena Radiance (3D) | Feature scientifica |

### v4.4 (Economia)

| # | Item | Tipo |
|---|------|------|
| 10 | Trade-off costo-resa H_min (formulazione B) + LCOE | Feature economica |

---

## 3. Decisioni risolte

| ID | Decisione | Scelta | Note |
|----|-----------|--------|------|
| D1 | Cartella di lavoro | Nuova `SolRatio_v4_2/` | Copia da `SolRatio_v4_1/`, archivia v4.1 in `_archivio_versioni/` al primo bump v4.2.0 |
| D2 | Strategia release | Singola `v4.2.0` con tutti i 9 item | No release intermedia v4.1.3 |
| D3 | Sample come benchmark | OK validazione_<feature>.csv | Aggiungo entry in `engine/test/run_battery.py` per ogni feature |
| D4 | Bifacciale, scope | β — energia PV bifacciale | Front + `bifaciality_factor` × rear; aggiorna sezioni "Produzione" Excel/PDF; no LCOE |
| D5 | Pannelli avanzati | α — BRTDfunc spec/diff | Retrocompat con `τ_diff=0`; no prism2/BSDF |
| D6 | Trade-off costo H_min | **Spostato a v4.4** | Esce da v4.2; v4.4 = "Economia" |
| D7 | Multi-anno | A — sequenziale + incrementale | Flag `--years 3|tmy|all|2010,2015,2020`; salvataggio parziale per resilienza |

---

## 4. Ordine di esecuzione consigliato

### Fase 1 — Quick wins (basso rischio, alto valore quotidiano)

Obiettivo: chiudere in ~1-1.5 giornate gli item che non toccano la fisica
del modello e che riducono attrito quotidiano. Per D2 entrano nella
release unica `v4.2.0`.

#### 1.1 — Auto-update label versione Excel via VBA (item 8)

- **File**: `progetti/Sample/SolRatio_progetto.xlsm` (modulo `ThisWorkbook`),
  `progetti/_template/SolRatio_progetto.xlsm`.
- **Pre-step**: aprire l'Excel e verificare nome foglio Launcher e cella label.
- **Test**: bumpare `engine/VERSION` → `4.1.3-test`, aprire l'Excel, label
  deve mostrare `SolRatio v4.1.3-test`, niente prompt "Salvare?".
- **Stima**: 30 min + 15 min di doc.

#### 1.2 — Script release end-to-end (item 6)

- **File nuovi**: `engine/release_helper.py` (CLI), `_NUOVA_VERSIONE.bat`.
- **Pre-step**: verificare `gh` CLI installata.
- **Approccio incrementale**:
  - **Step A**: `release_helper.py bump --new-version X.Y.Z` (i 9 step base).
  - **Step B**: aggiunta polling Zenodo + `update-doi`.
- **Test**: dry-run, fail-fast su working copy sporca, rollback con `git checkout`.
- **Stima**: 2-3h fase A + 1h fase B.

#### 1.3 — Cache scene `.oct` persistente (item 4)

- **File**: `engine/br_engine.py`, eventualmente nuovo `engine/_scene_cache.py`.
- **Strategia**: hash sui parametri scena rilevanti → `<hash>.oct` in
  `<progetto>/.cache/scenes/`. Cache hit salta `oconv`/scena rebuild.
- **Test**: run a freddo vs caldo (atteso speedup ≥ 50% sulla scena);
  cambio parametro → cache miss; cache invalidata correttamente al cambio
  versione.
- **Stima**: 2-3h.

### Fase 2 — Refactor architetturali

Obiettivo: pulire il codice in modo da abilitare le feature scientifiche con
minor rischio. Pre-condizione per Fase 3.

#### 2.1 — Generalizzazione frame coordinate sensori (item 7)

- **File**: `engine/br_engine.py`, `engine/validazione_br.py`,
  `engine/solratio_edge.py` (verifica), `engine/solratio_yield.py` (warning E-W).
- **Implementazione**: frame `(u,v,w)` ancorato al tracker, rotazione
  `axis_azimuth - 180°` (vedi ROADMAP §"Generalizzazione frame…").
- **Test di non-regressione**: con `axis_azimuth=180°` risultati
  bit-per-bit identici ai CSV `validazione_*.csv` correnti.
- **Test di validazione**: vs BR ufficiale per `axis_azimuth ∈ {180°, 90°, 135°}`,
  atteso MBE<1%, R²>0.99.
- **Doc**: sezione FORMULE.md + nota README "limitazioni asse E-W".
- **Stima**: 1 giornata.

#### 2.2 — Layout cartella progetto standardizzato (item 5)

- **File**: `engine/br_engine.py / pvgis_to_epw()`, `engine/validazione_br.py`,
  `engine/solratio_optimization.py`, `engine/calcola_br.py`, VBA Launcher,
  `_template/`, `Sample/`. Nuovo: `engine/migrate_project_layout.py`.
- **Test**: K_agv SAU = 84.00% sul Sample post-riorganizzazione; layout
  vecchio (PVGIS in root) ancora letto correttamente.
- **Stima**: 0.5-1 giornata.

### Fase 3 — Feature scientifiche

Obiettivo: estendere il modello a casi d'uso non coperti in v4.1.
Chiude la release `v4.2.0`.

#### 3.1 — Modalità multi-anno + P10/P50/P90 (item 2)

- **File**: `engine/br_engine.py / pvgis_to_epw()` (multi-anno);
  nuovo `engine/solratio_multiyear.py` (aggregazione P10/P50/P90);
  `engine/solratio_excel.py`, `engine/solratio_pdf.py` (sezione "Variabilità").
- **CLI**: `--years all|2010,2015,2020|tmy`.
- **Salvataggio incrementale**: ogni anno scrive parziale, riprendibile.
- **Test**: anno singolo TMY identico a oggi; 3 anni → P10/P50/P90 coerenti.
- **Stima**: 1.5-2 giornate.

#### 3.2 — Ground plane inclinato (L3 completo) (item 3)

- **File**: `engine/br_engine.py` — sostituire `groundplane ring` con polygon
  inclinato secondo `slope_pct/slope_azimuth`. Pre-condizione: item 7.
- **Test**: slope=0% identico al ring; slope=10% Δ entro 1-2% K_agv;
  slope=20% Δ documentata.
- **Stima**: 0.5-1 giornata.

#### 3.3 — Pannelli semi-trasparenti avanzati BRTDfunc (item 9)

- **Scope (D5 α confermato)**: materiale `BRTDfunc` con `tau_spec` e
  `tau_diff` letti da Parametri Excel (estensione del `tau` corrente
  che ha solo componente speculare).
- **File**: `engine/br_engine.py` (definizione materiale Radiance);
  foglio Parametri Excel (nuove celle `tau_spec`, `tau_diff`);
  `engine/solratio_excel.py` (lettura nuovi parametri).
- **Test**: con `tau_diff=0` deve coincidere col `tau` puro corrente
  (retrocompatibilità bit-per-bit). Con `tau_spec=0.7, tau_diff=0.3`
  confronto vs bifacial_radiance reference.
- **Stima**: 0.5-1 giornata.

#### 3.4 — Bifacciale (item 11)

- **Scope (D4 β confermato)**: produzione PV bifacciale = front +
  `bifaciality_factor` × rear con `bifaciality_factor` configurabile
  (default 0.7 per moduli bifacciali moderni, 0 per monofacciali).
  Niente LCOE/business case.
- **File**: nuovo modulo `engine/solratio_bifacial.py` (calcolo POA
  posteriore via bifacial_radiance, già supportato dalla libreria);
  `engine/calcola_br.py` (chiamata opzionale via flag);
  `engine/solratio_excel.py` (sezione "Produzione bifacciale" output);
  `engine/solratio_pdf.py` (sezione "Producibilità bifacciale");
  foglio Parametri Excel (nuova sezione "Modulo bifacciale" con
  `bifaciality_factor`, `albedo` esistente da rivedere).
- **Test**: con `bifaciality_factor=0` produzione identica a monofacciale
  (regressione bit-per-bit); con `bifaciality_factor=0.7` differenze
  attese ~5-15% su pitch tipici (cross-check con letteratura).
- **Stima**: 2-3 giornate.

> **Nota — Trade-off costo H_min spostato a v4.4** (era item 10).
> v4.4 sarà la prima release "economica": include sia il trade-off
> `argmax K_agv − λ·cost(H_min)` sia LCOE bifacciale (estensione
> naturale di item 11 + 10).

---

## 5. Stima complessiva

| Fase | Item | Stima |
|------|------|-------|
| 1 | 8, 6, 4 | 1-1.5 giornate |
| 2 | 7, 5 | 1.5-2 giornate |
| 3 | 2, 3, 9, 11 | 4.5-7 giornate |
| **Totale v4.2** | 9 item | **7-10.5 giornate effettive — release singola `v4.2.0`** |

(Rispetto alla bozza precedente: -1 giornata per spostamento item 10 a v4.4.)

---

## 6. Strategia di test e release

- Commit atomici per ciascun item nella nuova cartella `SolRatio_v4_2/`.
- Dopo ogni fase, `engine/test/run_battery.py` (47 test correnti, da estendere).
- Dopo Fase 2: `release_orchestrator.py --quick` (validazione vs BR ufficiale).
- Dopo Fase 3: aggiornamento "Sample di riferimento" con doppio numero
  (mantenere K_agv SAU = 84.00% mono per regressione, aggiungere
  produzione bifacciale come nuovo KPI a fianco).
- Release finale unica `v4.2.0` via `release_helper.py bump 4.2.0` (item 6
  della Fase 1) + procedura GitHub/Zenodo + archiviazione `SolRatio_v4_1/`.

---

## 7. Rischi noti

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| Frame coord (item 7) introduce regressioni invisibili | Alto | Test bit-per-bit con `axis_azimuth=180°` come gate prima del merge |
| Bifacciale (item 11) tocca PDF/Excel a tutto tondo | Medio-alto | Implementare prima il calcolo (modulo isolato), poi propagare a UI in commit separato |
| Multi-anno (item 2) richiede 10-14h per Sample | Basso | Salvataggio incrementale, primo test su 3 anni |
| Layout standardizzato (item 5) rompe Excel di progetti esistenti | Medio | `migrate_project_layout.py` con dry-run + retrocompatibilità |
| BRTDfunc (item 9) divergenza vs bifacial_radiance ufficiale | Medio | Validazione esplicita con run cross-check, retrocompat. con `tau_diff=0` |
| OneDrive sync confonde git su `SolRatio_v4_2/engine/` | Basso ma osservato | Lavorare via Read/Write/Edit (path Windows), `git add -A` esplicito; in alternativa lavorare in cartella locale fuori OneDrive |
| Copia `SolRatio_v4_1/` → `SolRatio_v4_2/` perde riferimenti git | Basso | Mantenere remote `origin` come `SolRatio_v4_1/.git`; documentare procedura archivio |

---

## 8. Procedura operativa (decisioni risolte → esecuzione)

1. **Setup cartella v4.2**: copia `SolRatio_v4_1/` → `SolRatio_v4_2/`
   (preservando `.git`), aggiungo questo `PIANO_v4.2.md` anche nella
   nuova cartella, archivio `SolRatio_v4_1/` solo a fine release.
2. **Aggiornamento ROADMAP** in `SolRatio_v4_2/documentazione/ROADMAP.md`:
   - sposto Pali da v4.2 a v4.3,
   - sposto BRTDfunc + Bifacciale da v4.3 a v4.2,
   - creo nuova sezione v4.4 con Trade-off costo H_min + LCOE,
   - rimuovo i 3 item v4.3 originali ormai migrati altrove.
3. **Apro task list dedicata** per i 9 item v4.2 + setup + ROADMAP.
4. **Parto da Fase 1 → 1.1 (label Excel VBA)** come primo deliverable.
5. **Procedo in autonomia** per item, committando a ogni completamento
   con messaggio coerente. Mi fermo solo:
   - a fine Fase 1 (verifica con te prima di toccare il motore),
   - a fine Fase 2 (validazione vs BR ufficiale prima di Fase 3),
   - su qualsiasi dubbio non coperto da questo piano.

---

## 9. Note su decisioni già implicite

- `H_min` formulazione A (curva K_agv pura) è **già rilasciata** in v4.1.0
  (CHANGELOG: _"ottimizzazione H_min via curva di Pareto"_). Quindi
  l'item 10 è davvero solo l'aggiunta del trade-off costo (formulazione B).
- `tau` semplice (`trans` Radiance) è **già rilasciato** in v4.1.0.
  L'item 9 estende a `BRTDfunc` per separare specular vs diffuse.

---

## 10. Aggiornamento ROADMAP.md proposto

Riscrivere le sezioni di sviluppo futuro come:

**v4.2 — Multi-anno, ground inclinato, bifacciale, BRTDfunc** (9 item):
Modalità multi-anno, Ground plane inclinato, Cache scene `.oct`,
Layout cartella, Script release, Frame coord, Auto-update label Excel,
**Pannelli BRTDfunc** (anticipato), **Bifacciale** (anticipato).

**v4.3 — Pali nella scena Radiance**: spostato qui il trattamento
3D dei pali di sostegno.

**v4.4 — Economia (LCOE + trade-off costo H_min)**: spostato qui il
trade-off `argmax K_agv − λ·cost(H_min)`, accorpato all'estensione
LCOE bifacciale (era pieno-γ del bifacciale, anch'esso tolto da v4.2).

I 3 item rimanenti v4.3 originali sono migrati: Pannelli avanzati →
v4.2 (limitato a BRTDfunc), Bifacciale → v4.2 (limitato a β-energia),
Trade-off costo H_min → v4.4.
