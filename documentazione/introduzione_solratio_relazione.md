# SolRatio — Modello di irradianza al suolo e stima delle rese colturali per impianti agrivoltaici

*Testo introduttivo riutilizzabile nelle relazioni tecniche. Allineato alla
versione 4.3.0 (edizione di riferimento, depositata su Zenodo con DOI).*

## Descrizione del modello

SolRatio è uno strumento integrato di simulazione dell'irradianza solare al
suolo e di stima delle rese colturali in impianti agrivoltaici con tracker
monoassiale. Il modello combina il calcolo della radiazione disponibile per le
colture sottostanti ai pannelli fotovoltaici (tramite ray-tracing 3D) con le
curve dose-risposta della letteratura scientifica (Laub et al., 2022) per
stimare il coefficiente agrivoltaico K_agv per nove categorie colturali,
fornendo i dati necessari alla verifica dei requisiti agronomici previsti
dalle Linee Guida ministeriali in materia di impianti agrivoltaici (MiTE,
giugno 2022) e dal D.M. 436/2023 sull'agrivoltaico innovativo, e alla
valutazione della compatibilità tra produzione energetica e produzione
agricola.

Il motore di calcolo è basato su ray-tracing tridimensionale tramite Radiance
(LBNL) e il framework bifacial_radiance (NREL): una simulazione fisicamente
rigorosa della propagazione della luce nella scena dell'impianto, pannello per
pannello e ora per ora. La versione corrente supporta orientamento arbitrario
dell'asse tracker (nord-sud, est-ovest o intermedio), pannelli semitrasparenti
(componente speculare e diffusa), terreni in pendenza, stima dell'energia
bifacciale e modalità multi-anno con quantili statistici P10/P50/P90.

## Dati di input

Il modello richiede i seguenti dati di progetto, inseriti in un foglio di
calcolo Excel:

- coordinate geografiche del sito (latitudine, longitudine) ed eventuale
  pendenza del terreno con azimut della direzione di discesa;
- geometria dell'impianto: interasse tra le file (pitch), larghezza del
  modulo, altezza minima da terra, inclinazione massima e azimut dell'asse
  del tracker, modalità di funzionamento (astronomico, backtracking o tilt
  fisso);
- proprietà ottiche: albedo del terreno, trasmittanza del modulo (speculare
  ed eventualmente diffusa), fattore di bifaccialità;
- configurazione dell'effetto bordo: dimensioni del blocco, lunghezza delle
  file, superficie agricola esterna, fascia non coltivata lungo le file
  (SANU, per lato);
- intervallo di anni della serie meteorologica e parametri di calcolo
  Radiance.

I dati meteorologici (irradianza globale, diretta e diffusa su base oraria)
vengono acquisiti automaticamente dal database PVGIS-SARAH3 del JRC
(Commissione Europea) per il periodo richiesto. Da questi viene costruito un
anno meteorologico tipo (TMY) selezionando, per ciascun mese, l'anno con
irradianza globale più prossima alla mediana del periodo.

## Metodologia di calcolo

La simulazione opera su base oraria per le 8760 ore dell'anno tipo,
limitandosi alle ore diurne con irradianza significativa (GHI > 20 W/m² ed
elevazione solare > 2°), tipicamente nell'ordine di 4000 ore.

Per ciascuna ora il modello:

1. calcola l'angolo di rotazione del tracker in funzione della posizione
   solare, applicando l'algoritmo di backtracking per evitare
   l'ombreggiamento reciproco tra le file;
2. genera la scena tridimensionale dell'impianto (pannelli, suolo — anche
   inclinato — e cielo) corrispondente alla configurazione geometrica
   dell'ora;
3. costruisce il cielo luminoso con il programma gendaylit (modello Perez) a
   partire dai valori orari di irradianza diretta normale (DNI) e diffusa
   orizzontale (DHI);
4. esegue il tracciamento dei raggi (rtrace) su una griglia di punti sensore
   al livello del suolo, distribuiti uniformemente nell'interasse tra due
   file adiacenti;
5. ripete la simulazione in condizioni di cielo aperto (senza pannelli) per
   ottenere il riferimento di irradianza indisturbata.

Il rapporto tra irradianza sotto i pannelli e irradianza in cielo aperto
fornisce, ora per ora, la frazione di luce disponibile per le colture. Questo
dato viene integrato per ottenere i profili giornalieri, mensili e annuali
della radiazione al suolo e del DLI (Daily Light Integral), parametro chiave
per la valutazione agronomica; le curve dose-risposta di Laub et al. (2022)
lo convertono nel coefficiente agrivoltaico K_agv per ciascuna delle nove
categorie colturali. In modalità multi-anno la catena viene ripetuta per più
anni della serie storica, ottenendo i quantili interannuali P10/P50/P90.

## Motore di calcolo e riferimenti

Il motore utilizza i seguenti software e librerie scientifiche validati dalla
comunità internazionale:

- **Radiance** (Lawrence Berkeley National Laboratory): sistema di riferimento
  per la simulazione della luce naturale, utilizzato da oltre 30 anni in
  ambito architettonico, energetico e illuminotecnico;
- **bifacial_radiance** (National Renewable Energy Laboratory): framework
  Python per la simulazione di impianti fotovoltaici mediante Radiance;
- **pvlib** (Sandia National Laboratories): libreria per il calcolo della
  posizione solare, degli angoli di incidenza e dell'algoritmo di
  backtracking.

## Validazione

Il modello è validato confrontando i risultati con quelli ottenuti dal
workflow ufficiale di bifacial_radiance applicato alla stessa scena e agli
stessi parametri. La validazione, condotta su due giornate rappresentative
(equinozio di primavera e solstizio d'estate), ha prodotto i seguenti
risultati:

| Indicatore      | 21 marzo   | 21 giugno  |
|-----------------|------------|------------|
| MBE (bias medio)| +0.1%     | −0.1%      |
| RMSE            | 0.2%       | 0.1%       |
| R²              | 0.9993     | 0.9999     |

Lo scostamento medio inferiore all'1% e il coefficiente di determinazione
prossimo all'unità (ri-esecuzioni indipendenti: R² ≥ 0.997) confermano
l'allineamento tra SolRatio e l'implementazione NREL di riferimento
(misure con la versione 4.3.0, Radiance 6.0, collaudo completo 2026-06-12). Dalla versione 4.3.0 la
validazione comprende anche un riferimento indipendente costruito col
workflow nativo 1-axis di bifacial_radiance (angoli del tracker calcolati
da pvlib all'interno della libreria), con accordo entro 0.5 punti
percentuali sul rapporto giornaliero suolo/GHI. Ogni release deve inoltre
superare un test di regressione sui due progetti campione inclusi nel
repository (orientamento nord-sud ed est-ovest), con tolleranza dichiarata
di ±0.2 punti percentuali sul K_agv.

## Output

Il modello produce un report PDF di sintesi e un foglio di calcolo dei
risultati contenente:

- riepilogo dei parametri e dei KPI principali (foglio Riepilogo);
- profili spaziali di PAR relativa e DLI lungo l'interasse, mensili e
  stagionali (fogli PAR_DLI_Profilo, Profilo_PAR_Spaziale, Heatmap_PAR);
- DLI medio giornaliero per zona con quantili interannuali (DLI_Percentili);
- resa colturale attesa per zona e per coltura, con medie sulla stagione
  colturale (Resa_Colturale);
- analisi dell'effetto bordo dell'impianto, con il K_agv medio di campo
  (Effetto_Bordo);
- stima dell'energia bifacciale, se attivata (Bifacciale).
