# SolRatio v4.1.0 — Modello di irradianza al suolo e stima delle rese colturali per impianti agrivoltaici

## Descrizione del modello

SolRatio è uno strumento integrato di simulazione dell'irradianza solare al suolo e di stima delle rese colturali in impianti agrivoltaici con tracker monoassiale. Il modello combina il calcolo della radiazione disponibile per le colture sottostanti ai pannelli fotovoltaici (tramite ray-tracing 3D) con le curve dose-risposta della letteratura scientifica (Laub et al., 2022) per stimare il coefficiente agrivoltaico K_agv per nove categorie colturali, fornendo i dati necessari alla verifica dei requisiti agronomici previsti dalle Linee Guida MiTE (D.M. 436/2023) e alla valutazione della compatibilità tra produzione energetica e produzione agricola.

La versione 4.1.0 adotta un motore di calcolo basato su ray-tracing tridimensionale tramite Radiance (LBNL) e il framework bifacial_radiance (NREL), sostituendo il precedente approccio analitico con una simulazione fisicamente rigorosa della propagazione della luce nella scena dell'impianto. Rispetto alla versione 4.0.0 sono stati introdotti il supporto a pannelli semitrasparenti (parametro tau via materiale Radiance trans), il posizionamento dei sensori sul piano terreno per terreni in pendenza (slope L3), l'ottimizzazione automatica dell'altezza minima da terra rispetto a soglie agronomiche, e la diagnostica esplicita degli errori di ray-tracing.

## Dati di input

Il modello richiede i seguenti dati di progetto, inseriti in un foglio di calcolo Excel:

- coordinate geografiche del sito (latitudine, longitudine);
- geometria dell'impianto: interasse tra le file (pitch), larghezza del modulo, altezza minima da terra, inclinazione massima del tracker;
- proprietà ottiche: albedo del terreno, trasmittanza del modulo (se semitrasparente);
- configurazione tracker: modalità di backtracking, azimut dell'asse;
- parametri del campo: numero di file simulato, superficie agricola utile (SANU).

I dati meteorologici (irradianza globale, diretta e diffusa su base oraria) vengono acquisiti automaticamente dal database PVGIS-SARAH3 del JRC (Commissione Europea) per il periodo richiesto. Da questi viene costruito un anno meteorologico tipo (TMY) selezionando, per ciascun mese, l'anno con irradianza globale più prossima alla mediana del periodo.

## Metodologia di calcolo

La simulazione opera su base oraria per le 8760 ore dell'anno tipo, limitandosi alle ore diurne con irradianza significativa (GHI > 20 W/m² ed elevazione solare > 2°), tipicamente nell'ordine di 4000 ore.

Per ciascuna ora il modello:

1. calcola l'angolo di rotazione del tracker in funzione della posizione solare, applicando l'algoritmo di backtracking per evitare l'ombreggiamento reciproco tra le file;
2. genera la scena tridimensionale dell'impianto (pannelli, suolo, cielo) corrispondente alla configurazione geometrica dell'ora;
3. costruisce il cielo luminoso con il programma gendaylit (modello Perez) a partire dai valori orari di irradianza diretta normale (DNI) e diffusa orizzontale (DHI);
4. esegue il tracciamento dei raggi (rtrace) su una griglia di punti sensore al livello del suolo, distribuiti uniformemente nell'interasse tra due file adiacenti;
5. ripete la simulazione in condizioni di cielo aperto (senza pannelli) per ottenere il riferimento di irradianza indisturbata.

Il rapporto tra irradianza sotto i pannelli e irradianza in cielo aperto fornisce, ora per ora, la frazione di luce disponibile per le colture. Questo dato viene integrato per ottenere i profili giornalieri, mensili e annuali della radiazione al suolo e del DLI (Daily Light Integral), parametro chiave per la valutazione agronomica.

## Motore di calcolo e riferimenti

Il motore utilizza i seguenti software e librerie scientifiche validati dalla comunità internazionale:

- **Radiance** (Lawrence Berkeley National Laboratory): sistema di riferimento per la simulazione della luce naturale, utilizzato da oltre 30 anni in ambito architettonico, energetico e illuminotecnico;
- **bifacial_radiance v0.5.1** (National Renewable Energy Laboratory): framework Python per la simulazione di impianti fotovoltaici bifacciali mediante Radiance, sviluppato e mantenuto da NREL;
- **pvlib** (Sandia National Laboratories): libreria per il calcolo della posizione solare, degli angoli di incidenza e dell'algoritmo di backtracking.

I parametri di simulazione Radiance adottati corrispondono alla configurazione standard di bifacial_radiance (2 rimbalzi ambientali, 2048 divisioni emisferiche, 256 super-campioni), garantendo un buon compromesso tra accuratezza e tempo di calcolo.

## Validazione

Il modello è stato validato confrontando i risultati con quelli ottenuti dal workflow ufficiale di bifacial_radiance applicato alla stessa scena e agli stessi parametri. La validazione, condotta su due giornate rappresentative (equinozio di primavera e solstizio d'estate), ha prodotto i seguenti risultati:

| Indicatore      | 21 marzo   | 21 giugno  |
|-----------------|------------|------------|
| MBE (bias medio)| +0.54%    | +0.42%     |
| RMSE            | 0.80%      | 0.49%      |
| R²              | 0.9982     | 0.9989     |

Lo scostamento medio inferiore all'1% e il coefficiente di determinazione superiore a 0.998 confermano l'allineamento sostanziale tra SolRatio e l'implementazione NREL di riferimento.

## Output

Il modello produce un foglio di calcolo dei risultati contenente:

- profilo spaziale dell'irradianza media annua al suolo lungo la sezione trasversale dell'interasse;
- irradianza cumulata annua per punto (Wh/m²) e DLI medio mensile (mol/m²/giorno);
- mappa oraria dell'irradianza per ciascun punto della griglia;
- analisi dell'effetto bordo dell'impianto, con quantificazione dell'irradianza nelle fasce esterne;
- confronto con le soglie agronomiche per la coltura di riferimento selezionata.
