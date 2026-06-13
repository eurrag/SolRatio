# Progetto Sample_EW — variante Est-Ovest del progetto Sample

Variante del progetto dimostrativo [`Sample`](../Sample/README.md) con il tracker
orientato **Est-Ovest** (`axis_azimuth = 90°`, foglio `Parametri`, cella B14).
Tutti gli altri parametri (sito, geometria, ottica, effetto bordo, serie PVGIS,
parametri Radiance) sono identici al Sample N-S.

## Finalità

- Studiare la dipendenza dei risultati dall'orientamento dell'asse
  (`axis_azimuth`), la generalizzazione introdotta in v4.2.
- Costituire il secondo progetto del **test di regressione** della release, insieme
  al Sample N-S: il valore di riferimento del K_agv e la tolleranza sono documentati
  nel README principale del repository, sezione *Validazione*.

## Esecuzione

Dalla cartella radice del repository:

```cmd
python engine\calcola_br.py "progetti\Sample_EW\SolRatio_progetto.xlsm"
```

oppure da Excel con il pulsante "Calcola" del foglio `Launcher` (macro abilitate).
I dati meteo PVGIS coincidono con quelli del Sample (medesime coordinate: lat 45.30°N,
lon 9.34°E, località esempio di pianura padana).

## Avvertenza agronomica

Le curve di resa di Laub et al. (2022) sono calibrate su regimi di ombreggiamento
**N-S**: per orientamenti con `|axis_azimuth − 180°| > 30°` (come questo) il motore
emette un avviso a runtime e i K_agv vanno interpretati con cautela. Questo
progetto serve in primo luogo da confronto geometrico e da guardia di regressione,
non da riferimento agronomico per progetti reali E-W.

Per la guida completa all'uso e alla creazione di nuovi progetti vedi
[`progetti/Sample/README.md`](../Sample/README.md).
