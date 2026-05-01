# SolRatio v4.1.0 — Riferimento formule

## Conversioni fondamentali

### Radianza Radiance → Irradianza [W/m²]

rtrace in modo `-I` restituisce radianza spettrale RGB. Conversione:

```
IRR = 179 × (0.265·R + 0.670·G + 0.065·B)   [W/m²]
```

- 179 lm/W = efficacia luminosa standard CIE
- Coefficienti RGB = pesi luminanza CIE 1931 (Y = 0.265R + 0.670G + 0.065B)

### Irradianza → PAR [µmol/m²/s]

```
PAR_mol = IRR × par_frac × W_TO_UMOL
```

- `par_frac` = frazione PAR della radiazione solare (variabile, ~0.43-0.48)
- `W_TO_UMOL` = 4.57 µmol/J (fattore di conversione W → µmol/s per PAR)

### PAR → DLI [mol/m²/d]

```
DLI_h = PAR_mol × 3600 / 1e6    [mol/m²] per ora
DLI_d = Σ(DLI_h)                 [mol/m²/d] somma giornaliera
```

## PAR_FRAC — Jacovides et al. (2004)

La frazione PAR della radiazione solare globale varia con le condizioni
atmosferiche. Il metodo Jacovides usa il clearness index kt:

```
kt = GHI / (I₀ × cos(θz))
```

dove I₀ è l'irradianza extraterrestre e θz lo zenith angle.

```
par_frac(kt) = 0.512 - 0.175·kt        per kt ≤ 0.50
             = 0.512 - 0.175·0.50       per kt > 0.50 (saturazione)
```

Range tipico: 0.43 (cielo sereno, kt alto) — 0.48 (cielo coperto, kt basso).
Media annua Italia centrale: ~0.45.

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

Relazione empirica da Laub et al. (2022), specifica per coltura:

```
K_agv = (a₀ + a₁·RSR + a₂·RSR² + a₃·RSR³) / 100
```

dove a₀, a₁, a₂, a₃ sono coefficienti polinomiali per coltura (in `LAUB_COEFFICIENTS`).

9 colture disponibili: bacche, frutta, ortaggi da frutto, foraggere, ortaggi da
foglia, tuberi/radici, cereali C3, leguminose granella, mais (C4).


## Geometria tracker e angoli

### Angolo tracker (pvlib singleaxis)

```
θ_tracker = f(zenith, azimuth, axis_azimuth, beta_max, GCR, backtrack)
```

- Con backtracking: θ limitato per evitare ombreggiamento reciproco
- Senza backtracking: θ = min(ideal_angle, beta_max)

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
strip_width = P95(d_ombra) su tutte le ore diurne annuali
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
- Direzione (0, 0, 1): coseno-pesata, misura irradianza su piano orizzontale
- n_points punti equispaziati nel pitch: x = j × pitch/(n_points-1), j = 0..n_points-1
