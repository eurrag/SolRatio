# SolRatio — Architettura br_engine (v4.2.1)

> Documento nato con la v4.1.0; la pipeline sotto descritta resta valida.
> Le estensioni della linea v4.2 sono riassunte in fondo
> ("Aggiornamenti v4.2.x") e dettagliate nella technical note.

## Panoramica

`br_engine.py` implementa il motore di calcolo dell'irradianza al suolo per impianti agrivoltaici con tracker monoassiale. Utilizza bifacial_radiance v0.5.1 (wrapper NREL per Radiance) per la simulazione 3D ray-tracing ora-per-ora.

Sostituisce il motore analitico di v3.3.x (pvlib view-factor + shadow + decomposizione Perez) con una simulazione fisicamente accurata basata su gendaylit/rtrace.


## Pipeline di calcolo

La funzione principale `run_annual()` esegue questa sequenza:

1. **Setup ambiente Radiance** — Crea una directory temporanea, inizializza `RadianceObj`, legge il file EPW, imposta albedo e modulo fotovoltaico.

2. **Calcolo angoli tracker** — Usa `pvlib.tracking.singleaxis()` con apparent_zenith per calcolare il theta (angolo di rotazione del tracker) per ciascuna delle 8760 ore. Il theta determina tilt e azimuth della scena: `tilt = |theta|`, `azimuth = 90° se theta >= 0, 270° altrimenti`.

3. **Filtro ore diurne** — Seleziona le ore con `apparent_elevation > 2°` e `GHI > 20 W/m²`. Opzionalmente filtra su giorni campione (`sample_days`).

4. **Pre-generazione scene** — Per ogni theta unico, chiama `rad.makeScene()` con un `radname` univoco (`sr4_{i:04d}`) e cacha i percorsi dei file `.rad` risultanti. Questo evita di ricreare la geometria ad ogni ora. Il radname unico è necessario perché bifacial_radiance genera nomi file con tilt arrotondato a intero (`tilt:0.0f`), causando sovrascritture tra theta diversi con lo stesso tilt intero.

5. **Generazione sky file** — Per ogni ora diurna, scrive un file `.rad` contenente il comando `gendaylit` con DNI, DHI, posizione solare e la ground string (emisfero terreno + piano suolo con albedo).

6. **Costruzione octree e rtrace** — Worker paralleli (`ThreadPoolExecutor`, 80% CPU, max 28) eseguono per ogni ora:
   - `oconv` (materialfiles + skyfile + radfiles) → file `.oct` (octree)
   - `rtrace` con parametri configurabili → irradianza nei punti sensore

7. **Parsing risultati** — L'output rtrace in formato `-oovs` (tab-separated, colonne 3-5 = RGB) viene convertito in irradianza con la formula `(r + g + b) / 3.0` [W/m²], identica alla convenzione bifacial_radiance.

8. **Simulazione cielo aperto** — Secondo passaggio rtrace con solo sky+ground (senza pannelli), un singolo punto sensore per ora. Serve come riferimento per il calcolo della PAR relativa.


## Confronto con workflow bifacial_radiance standard

| Aspetto | BR ufficiale | SR v4 |
|---------|-------------|-------|
| Scene | `makeScene()` ad ogni ora | Pre-cache per theta unici |
| Sky | `gendaylit2manual()` | Scrittura manuale file `.rad` |
| Octree | `makeOct()` → `getfilelist()` | `oconv` con `_popen` (lista, no shell) |
| Ordine file oconv | materialfiles + skyfiles + radfiles | Identico (allineato) |
| rtrace | Interno ad AnalysisObj | Subprocess diretto |
| Parallelismo | Nessuno (sequenziale) | ThreadPoolExecutor (80% CPU) |
| Risultato | Equivalente (MBE < 1%, R² > 0.998) | Equivalente |


## Parametri rtrace

Configurabili dal foglio Excel Parametri (celle B48-B50; B51 = override del numero di file in scena, vedi PARAMETRI_RADIANCE.md). I default nel codice corrispondono alla modalità `accuracy='low'` di bifacial_radiance:

| Parametro | Cella | Default | Significato |
|-----------|-------|---------|-------------|
| `-ab` (ambient bounces) | B48 | 2 | Numero di rimbalzi luce indiretta |
| `-ad` (ambient divisions) | B49 | 2048 | Campioni per integrazione emisferica |
| `-as` (ambient super-samples) | B50 | 256 | Super-campionamento zone ad alta varianza |

Parametri fissi: `-aa .1 -ar 256 -h -oovs -I` (modo irradianza).

Ridurre ab/ad/as accelera la simulazione ma aumenta il rumore. La validazione è stata eseguita con i default (ab=2, ad=2048, as=256).


## Sensori al suolo

I punti sensore sono distribuiti uniformemente lungo l'asse x (perpendicolare alle file di pannelli), a y=0, z=0.05m:

- **Profilo centrale**: x = 0 .. pitch, `n_points` punti (default 51). Rappresenta il campo infinito (fila centrale della scena).
- **Profili edge** (se `n_ext > 0`): pitch addizionali dalla fila centrale verso il bordo dell'impianto.
- **Fascia esterna**: oltre l'ultima fila, larghezza calcolata dal P95 della distanza d'ombra.

Tutti i profili sono in un unico batch rtrace per ora (zero overhead aggiuntivo).


## Costruzione scena Radiance

La scena 3D è composta da:

- **Modulo fotovoltaico**: rettangolo opaco (`glass=False`), dimensioni `module_length × W`. `module_length = 30m` (abbastanza lungo da rendere trascurabili gli effetti 3D longitudinali).
- **Array**: `nMods=1`, `nRows = 2·n_ext + 1` file. La fila centrale è all'origine (y=0).
- **Cielo**: generato da `gendaylit` con DNI/DHI/posizione solare.
- **Suolo**: emisfero terreno (glow + source) + disco fisico (ring) con albedo specificato.


## Formato output

`run_annual()` restituisce un dizionario con:

```
IRR_hourly          (n_ok, n_points)    W/m² per ora per punto
IRR_daily_cum       (n_points,)         Wh/m² cumulato
IRR_opensky         (8760,)             W/m² cielo aperto per ora
daylight_indices    (n_ok,)             Indici 0..8759 ore simulate
edge_irr            dict                Profili bordo (se n_ext > 0)
tracker_theta       (8760,)             Angolo tracker per ora [°]
ghi_arr             (8760,)             GHI da EPW [W/m²]
ghi_annual          float               GHI annuo totale [Wh/m²]
```


## Adattamento hardware

Il numero di worker si adatta automaticamente al numero di core CPU:

```
n_workers = max(2, min(int(n_cpu × 0.8), 28))
```

Minimo 2 worker, massimo 28, tipicamente 80% dei core disponibili. Non richiede configurazione.


## Validazione

Script: `engine/validazione_br.py`. Esegue due simulazioni indipendenti sullo stesso progetto e confronta i profili di irradianza punto-per-punto:

- **Parte A**: workflow SR v4 (cache scene + parallelizzazione)
- **Parte B**: workflow BR ufficiale (`gendaylit2manual` → `makeScene` → `makeOct` → rtrace, sequenziale)

Risultati su località esempio (lat 45.30°N, lon 9.34°E) (2026-04-10):

| Giorno campione | MBE | RMSE | R² |
|-----------------|-----|------|----|
| 21 marzo (equinozio) | +0.54% | 0.80% | 0.9982 |
| 21 giugno (solstizio) | +0.42% | 0.49% | 0.9989 |

Il residuo ~0.5% è attribuibile alla stocasticità dell'ambient sampling di
Radiance. Riverificato sulla v4.2.1 (Radiance 6.0, 2026-06-11): R² ≥ 0.9985,
RMSE ≤ 0.2% su entrambe le giornate.


## Aggiornamenti v4.2.x

- **axis_azimuth arbitrario**: sensori in frame locale (u,v,w) ancorato
  all'asse tracker, rotazione φ = axis_azimuth − 180°; scene azimuth derivato
  coerentemente. Per axis_azimuth = 180° il comportamento coincide col v4.1.
- **Materiali pannello**: `trans` per trasmittanza speculare (τ) e BRTDfunc
  per la componente Lambertiana addizionale (τ_diff).
- **Terreno in pendenza**: componenti lungo/trasversale derivate da pendenza %
  e azimut di discesa; ground plane realmente inclinato (rotazione di Rodrigues
  attorno all'asse) e sensori riposizionati sul piano reale.
- **Cache scene .oct** (`_scene_cache.py`): attiva quando gli angoli unici di
  tracker sono ≤ 200 (validazione single-day, tilt fisso); dalla v4.2.1 gli
  octree sono compilati con `oconv -f` (frozen, self-contained) e il riuso
  cross-run è affidabile.
- **Header EPW in UTC** (v4.2.1): coerente coi timestamp PVGIS; il vecchio
  `round(lon/15)` anticipava la posizione solare di ~40 minuti.


## Log di esecuzione

I `print()` in `run_annual()` forniscono il monitoraggio in tempo reale nella finestra comandi: parametri caricati, numero scene/ore, progresso percentuale con ETA, tempi, conteggio errori. Sono protetti da un commento esplicito nel codice che ne vieta la rimozione.
