# SolRatio — Roadmap e bug noti

## Stato attuale (v4.1.2, 2026-05-02)

Patch cumulativa con piccoli fix di sviluppo. Correzioni principali:
- Fix regex R² nell'orchestratore (`release_orchestrator.py`): la regex
  precedente catturava per errore il valore di `GCR=0.476` come R²,
  generando NO-GO falsi nello STEP 5. Ora usa word boundary + carattere
  ² obbligatorio (`\bR(?:²|2|\?)...`).
- Aggiornamenti a ROADMAP per pianificare v4.2 (frame coordinate sensori
  generalizzato per `axis_azimuth`, auto-update label versione nei file
  Excel via macro VBA, script di release end-to-end).
- Rimozione di `engine/_br_run.bat` (codice morto con path hardcoded a
  `SolRatio_v4_0_0\engine\br_test_tmp.py`, file non più esistente).
- Esclusione di `_PUBBLICA_AGGIORNAMENTI.bat` (workflow personale) da git.

Nessuna modifica al motore di simulazione SR core (smoke regression v4.1.1
resta valido: K_agv SAU = 84.00% sul Sample).

Vedi `CHANGELOG.md` per i dettagli completi delle modifiche v4.1.2.

## Stato precedente (v4.1.1, 2026-05-01)

Patch di correttezza scientifica della pipeline di validazione vs BR ufficiale
NREL: corretto il mismatch di dimensione scena tra `run_annual()` e
`_run_br_official()` quando l'override `br_n_rows` è impostato. Aggiunto
warning a runtime in `br_engine.run_annual()` quando `n_rows < 7`, e
documentazione esplicita della raccomandazione minima n_ext ≥ 3 per uso
di routine. Pipeline di validazione torna a MBE ~0%, R² > 0.999.

Vedi `CHANGELOG.md` per i dettagli completi delle modifiche v4.1.1.

## Stato precedente (v4.1.0, 2026-05-01)

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

> **Nota — Riassegnazione scope 2026-05-02.** Su decisione utente i pali
> Radiance sono spostati da v4.2 a v4.3, e i 3 item v4.3 originali sono
> redistribuiti: BRTDfunc + Bifacciale anticipati a v4.2 (con scope ridotti
> α e β rispettivamente), Trade-off costo H_min spostato a v4.4. Vedi
> `PIANO_v4.2.md` per il dettaglio operativo.

### v4.2 — Multi-anno, ground inclinato, bifacciale, BRTDfunc (9 item)

- **Modalità multi-anno**: eseguire la simulazione su tutti gli anni PVGIS
  (non solo TMY) e calcolare statistiche inter-annuali (P10/P50/P90 di K_agv).
  Permette di stimare la variabilità climatica del sito. Strategia confermata
  (D7=A): run sequenziale + salvataggio incrementale + flag CLI
  `--years all|tmy|2010,2015,2020`.

- **Ground plane inclinato (L3 completo)**: in v4.1.0 i sensori sono già
  posizionati sul piano terreno (L3 parziale), ma il ground geometrico
  Radiance (`groundplane ring`) resta orizzontale. Per slope > 15% può
  introdurre artefatti nell'albedo riflessa. Soluzione: sostituire ring
  con polygon inclinato secondo slope_pct/slope_azimuth.

- **Cache scene persistente**: salvare le scene pre-generate (.oct) su disco
  per evitare ri-generazione tra run successive sullo stesso progetto.

- **Layout cartella progetto standardizzato**: separare input e output in
  sottocartelle dedicate per migliorare la leggibilità di progetti maturi.
  Struttura proposta:
  ```
  <progetto>/
  ├── SolRatio_progetto.xlsm        (rimane in root: punto d'ingresso)
  ├── input/
  │   ├── PVGIS_<lat>_<lon>_*.csv  (meteo grezzo)
  │   └── PVGIS_<lat>_<lon>_TMY.epw (EPW generato)
  └── test/
      ├── optimization_*.xlsx       (curva K_agv vs H_min)
      ├── optimization_*.png        (grafico)
      ├── validazione_*.csv         (confronto SR vs BR ufficiale)
      └── risultati_*.xlsx          (output principale BR)
  ```
  Richiede:
  - Funzione `find_pvgis_csv()` con fallback root → `input/`
    in `br_engine.pvgis_to_epw()` e `validazione_br.py`
  - Aggiornamento path output in `solratio_optimization.py`,
    `validazione_br.py`, `calcola_br.py`
  - Aggiornamento Launcher Excel (VBA) per nuovi path relativi
  - Migrazione automatica progetti esistenti (script `migrate_project_layout.py`
    che sposta i file e mantiene retrocompatibilità con layout v4.1.x)
  - Aggiornamento `_template/` e `Sample/` come riferimento
  - Aggiornamento docs: `ARCHITETTURA.md`, README di Sample, README principale

- **Script di release end-to-end automatico** (`_NUOVA_VERSIONE.bat` +
  `engine/release_helper.py`): automatizzare l'intera procedura di rilascio
  (patch/minor/major) inclusa la sincronizzazione Git ↔ GitHub ↔ Zenodo.
  Riferimento esperienza: la procedura manuale per v4.1.1 ha richiesto
  ~30 minuti distribuiti su molti passaggi e con rischio di dimenticare
  un file da bumpare o un comando.

  **Prerequisiti da installare prima di costruire lo script:**
  - **GitHub CLI** (`gh`) per creazione release senza browser:
    `winget install --id GitHub.cli` (Windows) o equivalente.
    Login una tantum: `gh auth login`.
  - Python con `requests` (probabilmente già installato).

  **Architettura della pipeline a 14 step:**
  1. Chiede versione nuova (es. `4.1.2`, `4.2.0`) e tipo (patch/minor/major)
  2. Pre-check: ramo git pulito, no modifiche pendenti, VERSION coerente
  3. (opzionale) Esegue orchestrator `--quick` per validare → richiede GO
  4. Apre `CHANGELOG.md` con template della nuova sezione precompilata
     (incluso `git log --oneline <prev>..HEAD` come spunto)
  5. [Pausa interattiva: utente compila descrizione, salva e chiude editor]
  6. `release_helper.py bump --new-version X.Y.Z`:
     - Sostituisce stringa versione in tutti i file `.py`
       (header docstring, `__version__`, print runtime, argparse description)
     - Aggiorna `engine/VERSION`
     - Aggiorna `CITATION.cff` (`version`, `date-released`)
     - Aggiorna `README.md` (titolo + sezione Limitazioni note)
  7. Mostra preview `git diff --stat` e chiede conferma
  8. `git add -A && git commit -m "release vX.Y.Z: ..."`
  9. `git tag -a vX.Y.Z -m "..." && git push origin main vX.Y.Z`
  10. `gh release create vX.Y.Z --title "..." --notes-file <changelog_section>`
  11. Loop polling Zenodo API ogni 30 sec, max 5 min:
      `https://zenodo.org/api/records?q=conceptdoi:<concept>&sort=newest&size=1`
      → estrae DOI nuova versione
  12. `release_helper.py update-doi --doi 10.5281/zenodo.NNNNNNN`:
      aggiorna `CITATION.cff` (campo `doi`) e `README.md` (sezione "Come citare")
  13. `git add CITATION.cff README.md && git commit -m "docs: add DOI for vX.Y.Z" && git push`
  14. Stampa riepilogo: link release GitHub, link DOI Zenodo, tempo totale

  **Tempo totale interventi utente:** ~2 minuti (input versione + scrittura
  CHANGELOG + conferma diff). Tempo totale di esecuzione: ~5 minuti
  (escluso eventuale orchestrator pre-release, che resta opzionale).

  **Stima implementazione:** ~2 ore per versione completa. Si può
  spezzare in due fasi: prima `bump_version.py` (steps 1-9, base),
  poi aggiunta polling Zenodo + DOI auto-update (steps 11-13, avanzato).

  **Cosa NON va automatizzato deliberatamente:**
  - Contenuto del CHANGELOG (atto editoriale che richiede pensiero)
  - Decisione di rilasciare ("è pronto?")
  - Decisione GO/NO-GO sui test pre-release

  **Enhancement al `release_helper.py`: bump-from-CHANGELOG.** Modalità
  in cui lo script legge la nuova versione direttamente dalla prima
  sezione `## v(\d+\.\d+\.\d+)` del CHANGELOG.md, eliminando la necessità
  di passare la versione come argomento CLI. Allinea il workflow alla
  convenzione di tool consolidati (release-please, standard-version,
  semantic-release) dove il CHANGELOG è la fonte autoritativa di intent
  di rilascio. Vantaggi:
  - Single source of truth (no rischio di mismatch CHANGELOG vs CLI arg)
  - Forza la disciplina "documento prima di rilasciare"
  - Estrae anche data automaticamente per `CITATION.cff` (coerenza per
    costruzione)
  - Validazione: errore esplicito se nuova versione < corrente o se
    formato CHANGELOG non parsabile
  Mantenere la modalità esplicita esistente (`bump X.Y.Z`) per
  retrocompatibilità, e aggiungere `bump --from-changelog` (esplicito) e
  `bump X.Y.Z --verify-changelog` (controllo match).

- **Generalizzazione frame coordinate sensori per `axis_azimuth` arbitrario**:
  in v4.1.x il parametro `axis_azimuth` è letto da Excel e passato a pvlib
  per il calcolo degli angoli tracker, ma sia `br_engine.run_annual()` sia
  `validazione_br._run_br_official()` hardcodano la scena Radiance e i
  sensori in convenzione asse nord-sud (`azimuth = 90 if theta>=0 else 270`,
  sensori lungo `x` mondo). Quindi cambiare `axis_azimuth` in Excel ha
  effetto solo sui calcoli pvlib, NON sulla scena → risultati incoerenti
  per qualsiasi azimuth ≠ 180°.

  **Soluzione architetturale**: spostare il posizionamento sensori da
  coordinate mondo a un **frame locale ancorato al tracker**:
  ```
  asse u = parallelo all'asse del tracker (lungo la fila)
  asse v = perpendicolare all'asse (= direzione del pitch)
  asse w = verticale (= z mondo)
  ```
  I sensori sono sempre `(0, j*dv, z0)` nel frame locale, indipendentemente
  dall'orientamento. Si trasformano a coordinate mondo con rotazione
  `axis_azimuth - 180°`:
  ```python
  phi = math.radians(axis_azimuth - 180.0)
  cos_phi, sin_phi = math.cos(phi), math.sin(phi)
  for j in range(n_points):
      v = j * dv
      x_world = v * sin_phi
      y_world = v * cos_phi
      linepts_lines.append(f'{x_world:.6f} {y_world:.6f} {z0:.6f} 0 0 1')
  ```
  E specularmente l'azimuth dei moduli passato a `sceneDict`:
  ```python
  azimuth_module = (axis_azimuth + (90 if theta >= 0 else -90)) % 360
  ```

  **Modifiche richieste:**
  - `engine/br_engine.py`: rotazione coordinate sensori + azimuth scena
  - `engine/validazione_br.py / _run_br_official()`: stessa modifica
    in parallelo (per mantenere coerente il confronto)
  - `engine/solratio_edge.py`: verifica che il calcolo dei profili edge
    funzioni con frame ruotato (probabilmente sì, sono coordinate locali)
  - Test di non-regressione: con `axis_azimuth=180°` deve dare risultati
    bit-per-bit identici all'attuale (i CSV `validazione_*.csv` esistenti
    sono il riferimento)
  - Validazione vs BR ufficiale: rifare con almeno 3 valori di
    `axis_azimuth` (180°, 90°, 135°) → atteso MBE<1% R²>0.99 in tutti

  **Vantaggi:**
  1. Coerenza per qualsiasi `axis_azimuth` (N-S, E-W, NE-SW, ecc.)
  2. Output sempre fisicamente significativo (sensori attraverso il pitch)
  3. Apre la strada a configurazioni miste o orografie vincolate
  4. Architettura pulita per manutenzione futura

  **Stima implementazione: ~1 giornata** (codice + test + validazione +
  doc). Ridotto rispetto alla versione "supporto E-W ad-hoc" perché
  l'approccio architetturale evita casi-particolari hardcoded.

  **Nota agronomica importante per asse E-W:** anche dopo questo fix
  tecnico, l'applicazione delle curve di Laub et al. 2022 a configurazioni
  E-W resta scientificamente delicata. Con asse E-W, l'ombra dei pannelli
  forma strisce N-S quasi-fisse durante l'anno (piccola oscillazione
  stagionale), creando una distribuzione PAR/DLI fortemente bimodale
  (strisce in ombra permanente vs strisce in sole permanente). Le curve
  Laub sono calibrate su regimi di ombra parziale e variabile (tipico
  N-S). L'utente deve essere avvisato di questa limitazione: aggiungere
  warning runtime in `solratio_yield.py` se `axis_azimuth` è fuori dal
  range "N-S ± 30°" (es. 150°-210°), e sezione dedicata in `FORMULE.md`
  con linee guida d'uso (eventualmente: output con doppia popolazione
  "strisce sole" / "strisce ombra" invece di K_agv medio singolo).

- **Auto-update label versione nei file Excel** (Sample, _template, progetti
  utente): macro VBA `Workbook_Open()` che, all'apertura del file Excel,
  legge `engine/VERSION` (file di testo nella root del progetto SolRatio)
  e aggiorna il label "SolRatio vX.Y.Z" nel foglio Launcher in automatico.

  **Motivazione**: evitare il task ricorrente di aggiornare manualmente
  la cella del Launcher a ogni release (problema esistente in tutti i
  progetti — oggi richiede edit manuale in Excel per ogni xlsm). Il file
  `engine/VERSION` è già la single source of truth (aggiornato
  automaticamente da `Versioning/release_helper.py`). L'Excel deve solo
  rifletterlo passivamente.

  **Implementazione VBA proposta** (modulo `ThisWorkbook`):
  ```vba
  Private Sub Workbook_Open()
      On Error GoTo CleanExit  ' Failure silenzioso

      ' Cerca engine/VERSION risalendo la struttura cartelle
      Dim base_path As String
      base_path = ThisWorkbook.Path
      Dim candidates(0 To 3) As String
      candidates(0) = base_path & "\..\..\engine\VERSION"
      candidates(1) = base_path & "\..\engine\VERSION"
      candidates(2) = base_path & "\engine\VERSION"
      candidates(3) = base_path & "\..\..\..\engine\VERSION"

      Dim version_path As String, i As Integer
      For i = 0 To 3
          If Dir(candidates(i)) <> "" Then
              version_path = candidates(i)
              Exit For
          End If
      Next i
      If version_path = "" Then Exit Sub

      ' Leggi versione
      Dim version_text As String, file_num As Integer
      file_num = FreeFile
      Open version_path For Input As #file_num
      Line Input #file_num, version_text
      Close #file_num
      version_text = Trim(version_text)
      If version_text = "" Then Exit Sub

      ' Aggiorna cella solo se diversa (per non sporcare il file)
      Dim ws As Worksheet
      Set ws = Worksheets("Launcher")
      Dim target_cell As Range
      Set target_cell = ws.Range("A1")  ' DA VERIFICARE: indirizzo cella reale

      Dim new_label As String
      new_label = "SolRatio v" & version_text
      If target_cell.Value <> new_label Then
          target_cell.Value = new_label
          ThisWorkbook.Saved = True  ' Evita prompt "Salvare?" alla chiusura
      End If

  CleanExit:
      Exit Sub
  End Sub
  ```

  **Vantaggi:**
  - Zero manutenzione: cambia `engine/VERSION` (anche tramite
    `release_helper.py`), apri il file, label aggiornata
  - Single source of truth: `engine/VERSION` resta autoritativo
  - Funziona per qualsiasi progetto (Sample, _template, progetti privati)
  - Risolve definitivamente il task #39 [POSTICIPATO] (label Launcher manuale)
  - Compatibile con macro già abilitate in SolRatio_progetto.xlsm

  **Lavori da fare in v4.2:**
  1. Verificare cella esatta del label versione nel foglio Launcher
     (es. A1, A3, B2 — da controllare aprendo il file)
  2. Verificare nome esatto del foglio (case-sensitive in VBA: "Launcher")
  3. Aggiungere il codice VBA al modulo `ThisWorkbook` di Sample/SolRatio_progetto.xlsm
  4. Testare apertura: il label deve aggiornarsi automaticamente
  5. Replicare nel `_template` (per nuovi progetti che derivano da template)
  6. Documentare in `progetti/Sample/README.md` il comportamento auto-update
  7. Eventualmente: aggiungere check di versione minima in caso di file
     più vecchi di un certo soglia (warning "questo Excel è di un progetto
     v4.0.x, considerare aggiornamento parametri")

  **Tempo stimato implementazione: ~30 minuti** (incluso test). Bassa
  complessità ma alto valore quotidiano (automazione di un task ricorrente).

- **Pannelli semi-trasparenti avanzati (BRTDfunc, scope α)**: in v4.1.0 è
  già supportato `tau` via materiale Radiance `trans` (mappatura semplice per
  pannelli a vetro convenzionali, `tspec=1.0`). v4.2 estende il modello al
  materiale Radiance `BRTDfunc`, separando la trasmittanza in componente
  speculare `tau_spec` e diffusa `tau_diff` (lette da Parametri Excel).
  Retrocompat con `tau_diff=0` deve coincidere bit-per-bit col `tau` corrente.
  _Anticipato dalla v4.3 originale (su decisione utente 2026-05-02). Le
  estensioni a `prism2` e BSDF `.xml` restano future v4.5+._

- **Bifacciale (energia PV, scope β)**: estendere il modello al calcolo
  della produzione PV bifacciale = `front + bifaciality_factor × rear`,
  con `bifaciality_factor` configurabile (default 0.7 per moduli moderni,
  0 per monofacciali). Output: nuove sezioni "Produzione bifacciale" in
  Excel e PDF. Modulo nuovo `engine/solratio_bifacial.py` (calcolo POA
  posteriore tramite bifacial_radiance). Retrocompat con
  `bifaciality_factor=0`. _Anticipato dalla v4.3 originale. Estensione LCOE
  rimandata a v4.4 (vedi sotto)._

### v4.3 — Pali nella scena Radiance (3D)

- **Pali nella scena Radiance**: reintegrare i pali di sostegno come oggetti
  cilindrici nella scena BR (in v4.0.0 erano gestiti analiticamente con
  post-shadow; in v4.1.0 sono stati rimossi dal flusso, codice conservato
  dormiente). Richiede: oggetti cilindrici Radiance posizionati sull'asse
  tracker con spaziatura B22, riattivazione delle call sites commentate in
  `calcola_br.py`, `solratio_edge.py`, `solratio_pdf.py`, `solratio_excel.py`.
  _Spostato da v4.2 originale a v4.3 su decisione utente 2026-05-02 per dare
  priorità in v4.2 a multi-anno, BRTDfunc e bifacciale._

### v4.4 — Economia (LCOE + trade-off costo H_min)

- **Trade-off costo-resa H_min (formulazione B)**: estendere
  `solratio_optimization.py` con funzione di costo strutturale `cost(H_min)`
  parametrizzata su €/m altezza, e ottimizzazione
  `argmax K_agv − λ · cost(H_min)` con `λ` configurabile dal foglio
  Parametri (sezione "Economia" da introdurre). _Spostato da v4.3
  originale a v4.4 su decisione utente 2026-05-02._

- **LCOE bifacciale (estensione di v4.2 § Bifacciale, scope γ originale)**:
  propagare la produzione PV bifacciale calcolata in v4.2 sul business case
  (LCOE €/MWh, payback). Richiede revisione fogli di sintesi Excel e
  sezione PDF. Si accoppia naturalmente con il trade-off costo H_min in
  un'unica release "economica".

- **Bifacciale avanzato (BSDF moduli)**: per moduli con texture
  posteriore non lambertiana (vetro temperato microstrutturato), caricare
  BSDF `.xml` Radiance e propagare nel calcolo POA back.

