# SolRatio — Riferimento formule (v4.3.0)

## Conversioni fondamentali

### Radianza Radiance → Irradianza [W/m²]

rtrace in modo `-I` restituisce irradianza RGB. Conversione:

```
IRR = (R + G + B) / 3   [W/m²]
```

- Media aritmetica dei tre canali = convenzione di bifacial_radiance per
  l'irradianza broadband (i materiali della scena sono spettralmente neutri).
- NB: la conversione FOTOMETRICA `179 × (0.265·R + 0.670·G + 0.065·B)`
  (lux, pesi luminanza CIE) NON è usata da SolRatio.

### Irradianza → PAR [µmol/m²/s]

```
PAR_mol = IRR × par_frac × W_TO_UMOL
```

- `par_frac` = frazione PAR della radiazione solare (variabile, ~0.42-0.48)
- `W_TO_UMOL` = 4.57 µmol/J (fattore di conversione W → µmol/s per PAR)

### PAR → DLI [mol/m²/d]

```
DLI_h = PAR_mol × 3600 / 1e6    [mol/m²] per ora
DLI_d = Σ(DLI_h)                 [mol/m²/d] somma giornaliera
```

## PAR_FRAC — Jacovides et al. (2003)

La frazione PAR della radiazione solare globale varia con le condizioni
atmosferiche (Jacovides et al. 2003, *Theor. Appl. Climatol.* 74:227-233:
rapporto PAR/globale e sua dipendenza dal cielo nel Mediterraneo
orientale). La parametrizzazione usa il clearness index kt:

```
kt = GHI / (I₀ × cos(θz))
```

dove I₀ è l'irradianza extraterrestre e θz lo zenith angle.

```
par_frac(kt) = clip(0.500 - 0.082·kt, 0.42, 0.48)
```

(parametrizzazione lineare sul clearness index nello spirito di Jacovides
et al. 2003; coefficienti del fit implementato in `compute_par_frac` —
v4.2.2 allinea la documentazione al codice validato).
Range operativo: 0.42-0.43 (cielo sereno, kt alto) — 0.48 (coperto).

Implementazione: `solratio_core.compute_par_frac(ghi, dni_extra, cos_zenith)`


## PAR relativa e RSR

### PAR relativa (trasmissione)

```
PAR_rel(x) = DLI_sotto(x) / DLI_cielo_aperto
```

- `DLI_sotto(x)` = DLI al punto x sotto i pannelli
- `DLI_cielo_aperto` = DLI da simulazione BR senza pannelli (open sky)

Range: 0.0 (ombra totale) — ~1.0 (pieno sole). In v4.1.0 non dovrebbe mai
superare 1.0 grazie al riferimento open sky BR.

### RSR — Radiation Stress Ratio

```
RSR(x) = 1 - PAR_rel(x) = (DLI_ref - DLI_sotto) / DLI_ref
```

- RSR = 0: nessuna riduzione (pieno sole)
- RSR = 1: ombra totale

### K_agv — Coefficiente agrivoltaico

```
K_agv = Y_agv / Y_pieno_sole = f(RSR)
```

Relazione empirica da Laub et al. (2022), specifica per coltura
(fit log-quadratico della Table S2, RMSE < 1.6%):

```
Y_rel(RSR) = 10^(2 + α·RSR + β·RSR²)   [%],  clip a [0, 200]
K_agv      = Y_rel / 100
```

dove α e β sono i due coefficienti per coltura (in `LAUB_COEFFICIENTS`,
implementazione `solratio_core.laub_yield`).

9 colture disponibili: bacche, frutta, ortaggi da frutto, foraggere, ortaggi da
foglia, tuberi/radici, cereali C3, leguminose granella, mais (C4).


## Geometria tracker e angoli

### Angolo tracker (pvlib singleaxis)

```
θ_tracker = f(zenith, azimuth, axis_azimuth, beta_max, GCR, backtrack)
```

- Con backtracking: θ limitato per evitare ombreggiamento reciproco
- Senza backtracking: |θ| ≤ β_max — θ è firmato (negativo al mattino),
  quindi θ = sign(θ_ideale) × min(|θ_ideale|, β_max)

### Hub height e clearance

```
H_mozzo = H_min_terra + (W/2) × sin(β_max)
clearance(θ) = H_mozzo - (W/2) × sin(|θ|)
```

### GCR — Ground Coverage Ratio

```
GCR = W / pitch
```

Range tipico agrivoltaico: 0.25 - 0.50 (vs. 0.40 - 0.60 per fotovoltaico puro).


## Effetto bordo

### Strip width (fascia esterna)

```
d_ombra(t) = H_max / tan(α_sole(t))
H_max = H_mozzo + (W/2)·sin(β_max)
strip_width = P95(d_ombra) su tutte le ore annuali con elevazione solare > 3°
```

Limitata a: `W ≤ strip_width ≤ 5 × pitch`

### FC_NS — Fattore correttivo longitudinale

```
d_NS(t) = H / tan(α_sole) × |cos(γ_sole - axis_azimuth)|
frac_trans = min(2·d_NS, L_tracker) / L_tracker
FC_NS = 1 + (1 - PAR_rel_SAU) × 0.5 × frac_trans
```

Modella il bonus di luce alle estremità N-S delle stringhe tracker, dove
l'ombra proiettata lungo l'asse non raggiunge le colture adiacenti.

### K_agv impianto (media pesata)

```
K_agv_imp = Σ(K_agv_i × Area_i × FC_i) / Σ(Area_i)
```

dove i contributi sono:
- File interne (campo infinito): K_agv_inf × Area_pitch × FC_NS
- File di bordo (edge profiles): K_agv_edge_k × Area_pitch × FC_NS
- Fascia esterna: K_agv_outer × Area_fascia × 1.0 (no FC_NS)
- Pieno campo residuo: K_agv_pieno × Area_pieno × 1.0


## Modello sky Radiance (gendaylit)

Per ogni ora diurna viene generato un cielo Perez tramite:

```
gendaylit -ang <sun_alt> <sun_az> -W <DNI> <DHI> -g <albedo> -O 1
```

- `-ang`: altitudine e azimut solare (azimut Radiance = azimut_convenzionale - 180°)
- `-W`: irradianza diretta normale (DNI) e diffusa orizzontale (DHI) in W/m²
- `-g`: albedo terreno (riflettanza)
- `-O 1`: output tipo 1 (distribuzione luminanza cielo CIE Perez)

Il cielo gendaylit modella la distribuzione angolare della radiazione diffusa
secondo il modello Perez (circumsolare, orizzonte, isotropa) in modo fisicamente
coerente, a differenza della decomposizione analitica usata in v3.3.x.


## Sensori al suolo

I sensori sono punti sulla superficie del terreno che misurano l'irradianza
incidente dall'emisfera superiore (downwelling):

```
x_j  0  0.05  0  0  1     (posizione x_j, y=0, z=5cm, direzione verso l'alto)
```

- z = 0.05 m: leggermente sopra il ground plane per evitare self-intersection
  (su terreno in pendenza la quota segue il piano reale: z = z₀ + v·tan(slope_cross))
- Direzione (0, 0, 1): coseno-pesata, misura irradianza su piano orizzontale
- n_points punti equispaziati nel pitch: x = j × pitch/(n_points-1), j = 0..n_points-1
