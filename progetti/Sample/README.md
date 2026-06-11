# Progetto Sample — esempio di uso SolRatio

Questa cartella contiene un **progetto dimostrativo** completo, pronto all'uso, per
verificare l'installazione di SolRatio e per servire da template per i tuoi progetti.

## Cosa contiene

| File | Cosa è |
|------|--------|
| `SolRatio_progetto.xlsm` | Foglio Excel con i parametri dell'impianto agrivoltaico (geometria tracker, ottica, sito, parametri Radiance) e il pulsante VBA per lanciare il calcolo |
| `PVGIS_45.3000_9.3400_2005_2023.csv` | Serie storica oraria di irradianza GHI/DNI/DHI da PVGIS-SARAH3 per la località esempio (pianura padana, lat 45.30°N, lon 9.34°E), anni 2005-2023 |
| `PVGIS_45.3000_9.3400_TMY.epw` | Anno meteorologico tipo (TMY composito mese-per-mese) generato automaticamente alla prima esecuzione |

## Come eseguire il progetto

### Da Excel (consigliato)

1. Apri `SolRatio_progetto.xlsm` con Microsoft Excel + macro abilitate
2. Vai sul foglio `Launcher` e clicca il pulsante "Calcola"
3. Attendi 5-10 minuti (il motore Radiance simula 8760 ore con ray-tracing 3D)
4. Apri i file di output che vengono creati nella stessa cartella:
   - `risultati_Sample.xlsx` — fogli Excel con tutti i KPI per zona/mese/coltura
   - `report_SolRatio_Sample.pdf` — report PDF di sintesi

### Da riga di comando

Dalla cartella radice del repository SolRatio:

```cmd
python engine\calcola_br.py "progetti\Sample\SolRatio_progetto.xlsm"
```

## Come creare un nuovo progetto a partire da Sample

1. **Duplica** questa cartella `Sample/` e rinominala con il nome del tuo progetto
2. **Modifica i parametri** nel foglio `Parametri` di `SolRatio_progetto.xlsm`:
   - Coordinate del sito (B4 = lat, B5 = lon)
   - Slope terreno (B6 = pendenza %, B7 = azimut discesa)
   - Geometria tracker (B14-B20: azimut asse, pitch, W, H_min, beta_max,
     modalità tracker, theta_fix)
   - Ottica (B23 = trasmittanza tau, B24 = albedo; opzionali: B25 =
     tau_diff, B26 = fattore bifaccialità)
   - Effetto bordo (B30 = larghezza blocco, B31 = lunghezza tracker, B32 = SAU esterna)
   - Parametri Radiance (B48-B51) lasciali ai default per la prima prova
3. **Aggiorna il titolo** nella cella A1 del foglio Parametri (per identificare il progetto nei report)
4. **Scarica i tuoi dati PVGIS** per le coordinate del sito da
   [PVGIS](https://re.jrc.ec.europa.eu/pvg_tools/it/) → "Hourly data" → seleziona
   `PVGIS-SARAH3` come database di riferimento, scarica come CSV con tutti gli anni
   disponibili. Sostituisci il file `PVGIS_*_*.csv` nella tua cartella di progetto.
5. Lancia il calcolo (vedi sopra)

## Parametri del progetto Sample

I parametri di `SolRatio_progetto.xlsm` rappresentano una configurazione tipo
agrivoltaico in pianura padana:

- Sito: lat 45.30°N, lon 9.34°E (località geografica generica della pianura padana)
- Tracker monoassiale orientato N-S (azimut asse 180°)
- Pitch ~5 m, larghezza modulo ~1 m, altezza minima da terra ~2 m
- Backtracking attivo, β_max 60°
- Pannelli opachi (tau = 0)
- Albedo terreno 0.23 (erba/pascolo)

Sono parametri di partenza realistici per un agrivoltaico standard. Per i tuoi
progetti reali andranno sostituiti con i valori del sito specifico.

## Auto-update label versione (v4.2+)

A partire da SolRatio v4.2, il file `SolRatio_progetto.xlsm` può aggiornare
automaticamente la cella `A1` del foglio Launcher con la versione corrente
letta da `engine/VERSION`. Per attivare la feature in un progetto esistente:

1. Apri `SolRatio_progetto.xlsm` con Excel (macro abilitate)
2. `Alt+F11` per aprire l'editor VBA
3. `File → Importa file…` → seleziona `engine/SolRatio_VersionLabel.bas`
4. Doppio click su `ThisWorkbook` nel pannello Progetto VBA, incolla:
   ```vba
   Private Sub Workbook_Open()
       On Error Resume Next
       UpdateVersionLabelFromFile
   End Sub
   ```
5. `Ctrl+S` per salvare. Chiudi e riapri: la cella `A1` mostrerà
   `SOLRATIO AGRIVOLTAICO - Launcher vX.Y.Z` con la versione corrente.

Comportamento: silent-fail se `engine/VERSION` non è raggiungibile, niente
prompt "Salvare?" alla chiusura, idempotente.

## Validazione del progetto Sample

Questa configurazione (con coordinate di pianura padana) è stata usata come
caso di validazione di SolRatio v4.x vs il workflow ufficiale di
`bifacial_radiance` (NREL) su due giornate rappresentative (misure v4.3.0,
Radiance 6.0, 2026-06-11):

| Indicatore | 21 marzo (equinozio) | 21 giugno (solstizio) |
|------------|----------------------|------------------------|
| MBE | +0.0% | −0.0% |
| RMSE | 0.0% | 0.1% |
| R² | 1.0000 | 0.9999 |

Dalla v4.3.0 la validazione include anche un riferimento indipendente col
workflow nativo `set1axis` (scarto −0.1/−0.4 pp sul rapporto suolo/GHI
giornaliero). Per dettagli vedi `documentazione/CHANGELOG.md` e
`engine/validazione_br.py`.
