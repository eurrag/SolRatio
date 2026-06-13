# Progetto Sample — esempio d'uso di SolRatio

Questa cartella contiene un **progetto dimostrativo** completo e immediatamente
utilizzabile, utile a verificare l'installazione di SolRatio e a fungere da
modello per i progetti dell'utente.

## Contenuto

| File | Descrizione |
|------|--------|
| `SolRatio_progetto.xlsm` | Foglio Excel con i parametri dell'impianto agrivoltaico (geometria tracker, ottica, sito, parametri Radiance) e il pulsante VBA per avviare il calcolo |
| `PVGIS_45.3000_9.3400_2005_2023.csv` | Serie storica oraria di irradianza GHI/DNI/DHI da PVGIS-SARAH3 per la località esempio (pianura padana, lat 45.30°N, lon 9.34°E), anni 2005-2023 |
| `PVGIS_45.3000_9.3400_TMY.epw` | Anno meteorologico tipo (TMY composito mese-per-mese) generato automaticamente alla prima esecuzione |

## Esecuzione del progetto

### Da Excel (consigliato)

1. Aprire `SolRatio_progetto.xlsm` con Microsoft Excel e le macro abilitate
2. Aprire il foglio `Launcher` e premere il pulsante "Calcola"
3. Attendere 5-10 minuti (il motore Radiance simula 8760 ore con ray-tracing 3D)
4. Aprire i file di output creati nella stessa cartella:
   - `risultati_Sample.xlsx` — fogli Excel con tutti i KPI per zona/mese/coltura
   - `report_SolRatio_Sample.pdf` — report PDF di sintesi

### Da riga di comando

Dalla cartella radice del repository SolRatio:

```cmd
python engine\calcola_br.py "progetti\Sample\SolRatio_progetto.xlsm"
```

## Creazione di un nuovo progetto a partire da Sample

1. **Duplicare** questa cartella `Sample/` e rinominarla con il nome del proprio progetto
2. **Modificare i parametri** nel foglio `Parametri` di `SolRatio_progetto.xlsm`:
   - Coordinate del sito (B4 = lat, B5 = lon)
   - Slope terreno (B6 = pendenza %, B7 = azimut discesa)
   - Geometria tracker (B14-B20: azimut asse, pitch, W, H_min, beta_max,
     modalità tracker, theta_fix)
   - Ottica (B23 = trasmittanza tau, B24 = albedo; opzionali: B25 =
     tau_diff, B26 = fattore bifaccialità)
   - Effetto bordo (B30 = larghezza blocco, B31 = lunghezza tracker, B32 = SAU esterna)
   - Parametri Radiance (B48-B51): lasciarli ai valori predefiniti per la prima prova
3. **Aggiornare il titolo** nella cella A1 del foglio Parametri (per identificare il progetto nei report)
4. **Scaricare i dati PVGIS** per le coordinate del sito da
   [PVGIS](https://re.jrc.ec.europa.eu/pvg_tools/it/) → "Hourly data" → selezionare
   `PVGIS-SARAH3` come database di riferimento e scaricare il CSV con tutti gli anni
   disponibili. Sostituire quindi il file `PVGIS_*_*.csv` nella propria cartella di progetto.
5. Avviare il calcolo (vedi sopra)

## Parametri del progetto Sample

I parametri di `SolRatio_progetto.xlsm` rappresentano una configurazione tipo
agrivoltaico in pianura padana:

- Sito: lat 45.30°N, lon 9.34°E (località geografica generica della pianura padana)
- Tracker monoassiale orientato N-S (azimut asse 180°)
- Pitch ~5 m, larghezza modulo ~1 m, altezza minima da terra ~2 m
- Backtracking attivo, β_max 60°
- Pannelli opachi (tau = 0)
- Albedo terreno 0.23 (erba/pascolo)

Sono parametri di partenza realistici per un impianto agrivoltaico standard. Nei
progetti reali andranno sostituiti con i valori del sito specifico.

## Aggiornamento automatico dell'etichetta di versione (v4.2+)

A partire da SolRatio v4.2, il file `SolRatio_progetto.xlsm` può aggiornare
automaticamente la cella `A1` del foglio Launcher con la versione corrente
letta da `engine/VERSION`. Per attivare la funzionalità in un progetto esistente:

1. Aprire `SolRatio_progetto.xlsm` con Excel (macro abilitate)
2. Premere `Alt+F11` per aprire l'editor VBA
3. `File → Importa file…` → selezionare `engine/SolRatio_VersionLabel.bas`
4. Fare doppio clic su `ThisWorkbook` nel pannello Progetto VBA e incollare:
   ```vba
   Private Sub Workbook_Open()
       On Error Resume Next
       UpdateVersionLabelFromFile
   End Sub
   ```
5. Premere `Ctrl+S` per salvare. Chiudere e riaprire il file: la cella `A1`
   mostrerà `SOLRATIO AGRIVOLTAICO - Launcher vX.Y.Z` con la versione corrente.

Comportamento: in caso di `engine/VERSION` non raggiungibile l'operazione
fallisce senza segnalazione; non viene mostrata la richiesta "Salvare?" alla
chiusura; il comportamento è idempotente.

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
