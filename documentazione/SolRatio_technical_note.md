---
title: "SolRatio: A Ground-Irradiance and Crop-Yield Model for Single-Axis Tracker Agrivoltaic Systems"
subtitle: "Technical Note — Version 4.3.0 (Reference Edition)"
author:
  - Stefano Pesavento (ORCID 0009-0008-0720-4539)
date: 2026-06-11
version: v4.3.0
license: Apache-2.0
software_doi_concept: 10.5281/zenodo.19959581
# DOI di versione v4.3.0: assegnato al deposito Zenodo (aggiornare qui).
# v4.2.1 (K_agv in tracking sovrastimati, vedi §2.3): 10.5281/zenodo.20642574
repository: https://github.com/eurrag/SolRatio
keywords:
  - agrivoltaics
  - ground irradiance
  - ray tracing
  - Radiance
  - bifacial_radiance
  - pvlib
  - single-axis tracker
  - photosynthetically active radiation
  - daily light integral
  - crop yield
---

# SolRatio: A Ground-Irradiance and Crop-Yield Model for Single-Axis Tracker Agrivoltaic Systems

**Technical Note — Software version 4.3.0 (Reference Edition)**

Stefano Pesavento (Independent researcher)
ORCID: [0009-0008-0720-4539](https://orcid.org/0009-0008-0720-4539)

Software (concept DOI): [10.5281/zenodo.19959581](https://doi.org/10.5281/zenodo.19959581)
Software (this version, v4.3.0): version DOI assigned at the Zenodo deposit
Repository: <https://github.com/eurrag/SolRatio>

---

## Abstract (English)

SolRatio is an integrated simulation tool that estimates the spatial and temporal distribution of solar irradiance reaching the ground beneath single-axis tracker agrivoltaic systems, and translates that distribution into expected crop-yield coefficients (K_agv) for nine crop categories. The model couples three-dimensional ray tracing using Radiance (LBNL) through the bifacial_radiance framework (NREL) for scene-resolved photometric simulation, the pvlib library (Sandia National Laboratories) for tracker kinematics and backtracking, and the dose-response crop-yield curves of Laub et al. (2022) for the agronomic step. Inputs are read from a parameter-driven Excel workbook; meteorological data are fetched automatically from the PVGIS-SARAH3 database (Joint Research Centre, European Commission) and combined into a representative typical meteorological year. The model has been validated against the official bifacial_radiance workflow on two representative days of the agronomic season at a Po Valley location, returning a mean bias error below 1% and a coefficient of determination of at least 0.997, and — since v4.3.0 — against an additional *independent* reference built with the native bifacial_radiance 1-axis workflow (`set1axis`/`analysis1axisground`, tracker angles computed by pvlib inside the library), agreeing within 0.5 percentage points on the daily ground-to-GHI ratio. Version 4.2.0 introduced a multi-year stochastic mode with P10/P50/P90 quantiles, generalised tracker frame coordinates for arbitrary axis_azimuth, a single-axis bifaciality module, partially-transparent panel materials via Radiance BRTDfunc, and a persistent octree cache; v4.2.1 ("reference edition") pruned maintainer tooling and diagnostic outputs to the minimum reproducible scope. **The present release (v4.3.0) corrects a major defect present from v4.1.0 through v4.2.2: the Radiance scene rotated the panel away from the sun in every tracking hour (a counter-rotated scene), so tracking-mode ground-light estimates of previous releases are overestimated — on the bundled Sample project the regression-gate K_agv for C3 cereals moves from 84.1% to 57.5%. The code-to-code validation shared the scene convention with the engine and was structurally blind to the defect; the independent native-workflow reference was introduced for this reason.** All changes are listed in the repository changelog. This note describes the modelling framework, software architecture, validation outcomes, and an application example comparing north-south and east-west tracker axis orientations at equal geometry.

## Abstract (Italiano)

SolRatio è uno strumento di simulazione integrato che stima la distribuzione spaziale e temporale dell'irradianza solare al suolo sotto impianti agrivoltaici con tracker monoassiale e la converte in coefficienti di resa colturale attesa (K_agv) per nove categorie colturali. Il modello combina tre componenti: ray tracing tridimensionale tramite Radiance (LBNL) attraverso il framework bifacial_radiance (NREL) per la simulazione fotometrica della scena, la libreria pvlib (Sandia National Laboratories) per la cinematica del tracker con backtracking, e le curve dose-risposta di Laub et al. (2022) per la stima della resa. I parametri di ingresso sono letti da un foglio di calcolo Excel; i dati meteorologici vengono scaricati automaticamente dal database PVGIS-SARAH3 (Joint Research Centre, Commissione Europea) e composti in un anno meteorologico tipo. Il modello è stato validato confrontando i risultati con il workflow ufficiale di bifacial_radiance su due giornate rappresentative della stagione agronomica in Pianura Padana, ottenendo un mean bias error inferiore all'1% e un coefficiente di determinazione di almeno 0.997, e — dalla v4.3.0 — anche con un riferimento *indipendente* costruito col workflow nativo 1-axis di bifacial_radiance (`set1axis`/`analysis1axisground`, angoli del tracker calcolati da pvlib all'interno della libreria), con accordo entro 0.5 punti percentuali sul rapporto giornaliero suolo/GHI. La versione 4.2.0 ha introdotto la modalità multi-anno con quantili P10/P50/P90, la generalizzazione del sistema di riferimento del tracker per axis_azimuth arbitrario, un modulo di stima dell'energia bifacciale, materiali per pannelli semitrasparenti via Radiance BRTDfunc e una cache persistente di scene octree; la v4.2.1 ("edizione di riferimento") ha ridotto il perimetro al minimo riproducibile. **La presente release (v4.3.0) corregge un difetto maggiore presente dal v4.1.0 al v4.2.2: la scena Radiance ruotava il pannello dalla parte opposta al sole in ogni ora di tracking (scena contro-ruotata), per cui le stime di luce al suolo in modalità tracking delle versioni precedenti sono sovrastimate — sul progetto Sample incluso il K_agv di gate per i cereali C3 passa da 84.1% a 57.5%. La validazione code-to-code condivideva la convenzione di scena col motore ed era strutturalmente cieca al difetto; il riferimento indipendente col workflow nativo è stato introdotto per questa ragione.** Tutte le modifiche sono elencate nel changelog del repository. Questa nota descrive il framework modellistico, l'architettura software, l'esito della validazione e un esempio applicativo sul confronto fra orientamenti dell'asse tracker (nord-sud ed est-ovest) a parità di geometria.

## Keywords

agrivoltaics; ground irradiance; ray tracing; Radiance; bifacial_radiance; pvlib; single-axis tracker; photosynthetically active radiation; daily light integral; crop yield; PVGIS

---

## 1. Introduction

Agrivoltaic systems combine in situ photovoltaic generation with continued agricultural production on the same parcel of land. The concept was first articulated by Goetzberger and Zastrow (1982) and quantitatively revived by Dupraz et al. (2011), who showed through detailed light- and yield-modelling analyses that the land-equivalent ratio of an agrivoltaic system can exceed unity for several crops. Subsequent experimental work — most notably Marrou et al. (2013) — confirmed the agronomic viability of partial-shade cropping under photovoltaic arrays, and more recent system-design studies (Trommsdorff et al., 2021) have established design principles for combined food and energy production.

The design of agrivoltaic systems must therefore reconcile two objectives that are partially in conflict: maximising the electricity captured by the modules, and preserving sufficient ground-level photosynthetically active radiation (PAR) to sustain crop physiological development. The amount of light that reaches the ground in such systems is highly heterogeneous in both space and time, depending on the geometry of the array (pitch, module width, hub height, axis azimuth, terrain slope), on the operating logic of the tracker (backtracking, maximum tilt), on the optical properties of the modules (opaque vs. semi-transparent, monofacial vs. bifacial), and on the local solar climate. Quantitative tools capable of estimating, at the design stage, the daily light integral (DLI) and its spatial distribution under the array are therefore essential for evaluating agronomic compatibility and for satisfying the regulatory requirements that several European jurisdictions have begun to introduce — in Italy, for example, the Guidelines for Innovative Agrivoltaic Systems issued by the Ministero dell'Ambiente e della Sicurezza Energetica (D.M. 436/2023) prescribe minimum thresholds for the agronomic yield maintained under the array, expressed as a coefficient relative to open-field production for the reference crop.

The existing open-source modelling landscape is fragmented along the two sides of the problem. Tools focused on the electrical side — most prominently pvlib-python (Holmgren et al., 2018) and the bifacial_radiance framework (Ayala Pelaez and Deline, 2020) — capture the photovoltaic energy yield and the back-side plane-of-array irradiance with high fidelity, but offer only limited support for the under-canopy PAR distribution that drives crop physiology. Conversely, tools focused on crop response (canopy models such as DSSAT, STICS, APSIM) model plant development in detail but rely on coarse analytical or empirical proxies for the irradiance environment under the array. Recent ray-tracing-based approaches to agrivoltaic system simulation (e.g. Zainali et al., 2023) have begun to bridge this gap by adapting general-purpose photometric engines to the specific geometry of single-axis tracker arrays. The objective of SolRatio is to provide an open-source, end-user-operable tool that couples a physically rigorous ground-irradiance model — based on three-dimensional ray tracing — with calibrated crop-yield curves, in a workflow that can be operated from a parameter-driven Excel workbook without writing code, and whose outputs are directly usable for regulatory compliance assessment.

This technical note describes version 4.3.0 of the model (the reference edition line). The note is organised as follows: Section 2 presents the modelling framework; Section 3 describes the software architecture and dependencies; Section 4 summarises the validation against the reference bifacial_radiance workflow and the independent native-workflow check; Section 5 illustrates a typical application — the comparison of north-south and east-west tracker axis orientations at equal geometry; Section 6 discusses the known limitations of the current release; Section 7 outlines the planned roadmap; Section 8 concludes.

---

## 2. Modelling framework

### 2.1 Scene geometry and tracker kinematics

The simulated scene is a periodic array of identical rows of single-axis tracking modules. Table 1 lists the user-defined geometric, optical and meteorological parameters with their units and typical operating ranges. Optical and field-extent parameters are described in Sections 2.2–2.6.

**Table 1.** Principal input parameters read from the Excel parameter sheet. Cell references refer to the *Parametri* sheet of `SolRatio_progetto.xlsm`.

| Symbol                         | Description                              | Unit    | Typical range | Excel cell |
| ------------------------------ | ---------------------------------------- | ------- | ------------- | ---------- |
| $\mathrm{lat},\, \mathrm{lon}$ | Site coordinates                         | °       | —             | B4, B5     |
| slope                          | Terrain slope (decomposed internally into along- and across-axis components) | %  | 0–15 | B6 |
| slope azimuth                  | Downhill direction azimuth               | °       | 0–359         | B7         |
| $\mathrm{axis\_azimuth}$       | Tracker axis azimuth (clockwise from N)  | °       | 0–359         | B14        |
| $P$                            | Row pitch                                | m       | 5–15          | B15        |
| $W$                            | Module width                             | m       | 2.0–3.0       | B16        |
| $H_{\min}$                     | Minimum panel-to-ground clearance        | m       | 1.5–4.5       | B17        |
| $\beta_{\max}$                 | Maximum tracker tilt                     | °       | 55–60         | B18        |
| tracker mode                   | 0 = astronomical, 1 = backtracking, 2 = fixed tilt | — | — | B19 |
| $\theta_{\mathrm{fix}}$        | Fixed tilt angle (mode 2 only)           | °       | −60–60        | B20        |
| $\tau$                         | Module specular transmittance            | —       | 0–0.4         | B23        |
| $\rho_{\mathrm{g}}$            | Ground albedo                            | —       | 0.15–0.25     | B24        |
| $\tau_{\mathrm{diff}}$         | Module Lambertian transmittance          | —       | 0–0.2         | B25        |
| $b_{\mathrm{f}}$               | Bifaciality factor                       | —       | 0–0.95        | B26        |
| edge block width               | Edge-effect block width (0 = off)        | m       | —             | B30        |
| $L_{\mathrm{tot}}$             | Total tracker row length                 | m       | —             | B31        |
| external SAU                   | External utilised agricultural area      | m²      | —             | B32        |
| SANU                           | Uncultivated strip flanking each tracker row, per side (SAU = P − 2·SANU) | m | 0–1 | B33 |
| years                          | PVGIS series interval                    | —       | ≥ 3 years     | B41–B42    |
| $n_{\mathrm{ext}}$             | Number of external rows per side         | —       | 2–4           | B44        |
| Radiance params                | `-ab`, `-ad`, `-as`, scene rows override | —       | see docs      | B48–B51    |

The K_agv is computed for all nine Laub (2022) crop categories in every run;
no target-crop cell is required. The module electrical efficiency used by the
bifacial yield estimate is an internal constant of the beta-tier module.

The ground-coverage ratio is $\mathrm{GCR} = W / P$. The hub height $H_{\mathrm{hub}}$ and the instantaneous panel-to-ground clearance follow from the tracker geometry:

$$H_{\mathrm{hub}} = H_{\min} + \frac{W}{2} \sin(\beta_{\max})$$

$$\mathrm{clearance}(\theta) = H_{\mathrm{hub}} - \frac{W}{2} \sin(|\theta|)$$

Tracker rotation angles are computed using the `pvlib.tracking.singleaxis` routine, which implements the standard truncating-tracker model with optional backtracking. The user specifies whether backtracking is active; when active, the tracker angle is truncated to prevent inter-row self-shading, otherwise the tracker follows the ideal sun-tracking angle up to the limit $\beta_{\max}$.

In v4.2.0 the sensor and scene-azimuth conventions have been generalised to support arbitrary `axis_azimuth` values. Sensor positions are computed in a local frame $(u, v, w)$ anchored to the tracker axis, then transformed to world coordinates via a rotation by angle $\varphi = \mathrm{axis\_azimuth} - 180°$.

Since v4.3.0 the Radiance scene is built in the *canonical* bifacial_radiance form (the same normalisation applied internally by `makeScene1axis`): a **constant scene azimuth** $(\mathrm{axis\_azimuth} - 90°) \bmod 360°$ with a **signed tilt** $-\theta$, where $\theta$ is the pvlib tracker rotation angle ($\theta > 0$ = module face towards west). This convention is physically equivalent to mapping $\theta$ to the pvlib `surface_azimuth`/`surface_tilt` pair, with the additional property that the scene frame (row replication direction and ground-sensor transect) does not flip between morning and afternoon hours.

**Historical defect (v4.1.0–v4.2.2, corrected in v4.3.0):** the previous mapping, $(\mathrm{axis\_azimuth} + \mathrm{sign}(\theta) \cdot (-90°)) \bmod 360°$ with unsigned tilt, rotated the panel *away from the sun* in every tracking hour — a counter-rotated scene, not a mirrored one. A counter-rotated panel presents a narrower profile to the beam and casts a smaller shadow, so ground-light estimates in tracking mode were overestimated (regression gate on the bundled Sample: 84.1% vs the corrected 57.5%; the effect is small on overcast days, where the diffuse component dominates, and on fixed-tilt configurations). The code-to-code validation (Section 4) shared this mapping with the engine and was structurally blind to the defect; it was exposed by a convention-independent physical test (measured shadow width versus the analytical face-to-sun expectation with pvlib angles) and confirmed by the independent native-workflow reference of Section 4.3. A runtime warning is emitted when $|\mathrm{axis\_azimuth} - 180°| > 30°$, because the Laub et al. (2022) yield curves are calibrated on north-south shading regimes and their applicability to east-west alignments deserves caution.

### 2.2 Meteorology and sky model

Meteorological data are fetched automatically from the PVGIS-SARAH3 satellite-derived database operated by the Joint Research Centre of the European Commission (Huld et al., 2012). The full multi-year hourly time series of global horizontal irradiance (GHI), direct normal irradiance (DNI), and diffuse horizontal irradiance (DHI) is downloaded for the project coordinates and converted into a typical meteorological year by selecting, for each month, the year whose monthly GHI is closest to the multi-year median. This is a simplified TMY composition rule; the multi-criteria Finkelstein-Schafer statistic used by the official PVGIS TMY service is more rigorous but produces practically equivalent annual aggregates for the agronomic step. The composite year is written in EPW format and used as the reference meteorology for the standard annual simulation. Since v4.2.1 the EPW header declares UTC, consistently with the PVGIS timestamps (the previous `round(lon/15)` declaration shifted the computed solar position by ~40 minutes; the effect on the regression gate is documented in the changelog).

For each diurnal hour, the sky luminance distribution is generated by the Radiance utility `gendaylit`, which implements the all-weather Perez model. The driving inputs are the solar elevation and azimuth (the latter rotated to the Radiance convention as `azimuth_conventional − 180°`), the DNI, the DHI, and the ground albedo. The resulting sky description captures the direct component plus three diffuse components (circumsolar, isotropic, and horizon-brightening) in a physically consistent way, replacing the closed-form decompositions of the predecessor versions.

### 2.3 Ray tracing and sensor sampling

The scene description is composed of three classes of primitives: the module geometries generated by `bifacial_radiance.makeModule`, the ground plane, and the sky. For semi-transparent modules with a user-specified transmittance $\tau$, the module material is overridden from the default opaque definition to a Radiance `trans` material; in v4.2.0 a complementary $\tau_{\mathrm{diff}}$ parameter has been added to support Lambertian diffuse transmission, with the mapping

$$\mathrm{trans} = \tau + \tau_{\mathrm{diff}}, \qquad t_{\mathrm{spec}} = \frac{\tau}{\tau + \tau_{\mathrm{diff}}}$$

Setting $\tau_{\mathrm{diff}} = 0$ (the default) is bit-for-bit identical to v4.1.

Ground-level sensors are positioned at $z = 0.05$ m above the ground plane, on a uniform grid spanning the pitch interval between two adjacent rows. The downward hemisphere irradiance is sampled via Radiance `rtrace -I` with the standard bifacial_radiance simulation parameters (two ambient bounces, 2048 ambient divisions, 256 super-samples; configurable via cells B48–B51). For terrain with non-zero across-axis slope ($\mathrm{slope\_cross} \neq 0$) the ground plane is no longer horizontal: in v4.2.0 it is rendered as a Radiance ring tilted by $\mathrm{slope\_cross}$ around the tracker axis (Rodrigues rotation formula), and sensor positions are recomputed as $z = z_0 + v \tan(\mathrm{slope\_cross})$, preserving the constant 5 cm clearance above the inclined plane at every position.

The raw `rtrace` output (radiance triplets *R*, *G*, *B*) is converted to broadband irradiance using the CIE 1931 luminance weighting and the standard photopic efficacy of 179 lm W⁻¹:

$$E\,[\mathrm{W\,m^{-2}}] = 179 \cdot (0.265\,R + 0.670\,G + 0.065\,B)$$

A parallel open-sky simulation, with the same sky description but with the panels removed, provides the reference irradiance against which the under-panel measurements are normalised.

### 2.4 Spectral and temporal aggregation

Hourly broadband irradiance is converted to PAR using a variable PAR fraction following Jacovides et al. (2004):

$$f_{\mathrm{PAR}}(k_t) = \mathrm{clip}\,(0.500 - 0.082 \cdot k_t,\ 0.42,\ 0.48)$$

$$\mathrm{PAR}\,[\mu\mathrm{mol\,m^{-2}\,s^{-1}}] = E \cdot f_{\mathrm{PAR}} \cdot 4.57$$

where the clearness index $k_t = \mathrm{GHI} / (I_0 \cos\theta_z)$ uses the extraterrestrial irradiance $I_0$ and the solar zenith angle $\theta_z$. The factor 4.57 µmol J⁻¹ converts watts to micromoles per second in the PAR band. Hourly PAR is then integrated over each day to obtain the daily light integral DLI [mol m⁻² d⁻¹], the agronomically relevant aggregator.

The relative PAR transmission at a given ground position *x* and its complement, the radiation stress ratio (RSR), are:

$$\mathrm{PAR}_{\mathrm{rel}}(x) = \frac{\mathrm{DLI}_{\mathrm{under}}(x)}{\mathrm{DLI}_{\mathrm{opensky}}}$$

$$\mathrm{RSR}(x) = 1 - \mathrm{PAR}_{\mathrm{rel}}(x)$$

with RSR ranging from 0 (full sun) to 1 (full shade). RSR is the input to the crop-response stage.

### 2.5 Crop yield response

Crop responses are modelled through the empirical dose-response curves published by Laub et al. (2022), which fit a third-order polynomial in RSR to a meta-analytic dataset of dual-land-use experiments. The functional form is:

$$Y_{\mathrm{rel}}(\mathrm{RSR}) = 10^{\,2 + \alpha\,\mathrm{RSR} + \beta\,\mathrm{RSR}^2}\ [\%], \qquad K_{\mathrm{agv}} = Y_{\mathrm{rel}}/100$$

with two crop-specific coefficients $\alpha, \beta$ (fitted to Laub Table S2 by `curve_fit`, RMSE < 1.6%). Nine crop categories are supported: berries, fruit, fruiting vegetables, forages, leafy vegetables, tubers and roots, C3 cereals, grain legumes, and C4 maize.

### 2.6 Field-level aggregation and edge effects

The point-wise $K_{\mathrm{agv}}$ values are aggregated to a plant-level coefficient by an area-weighted average across spatial zones. The standard agronomic zones — under-tracker, edge, central — are extracted from the pitch profile using the panel half-width and the maximum tracker tilt. An additional outer strip beyond the last row models the spill of direct radiation onto fields adjacent to the array, with a width estimated as the 95th percentile of the across-pitch shadow length over all diurnal hours of the year (capped between $W$ and $5P$).

A longitudinal correction factor *FC_NS* quantifies the extra light reaching the north and south ends of the tracker rows, where the projected shadow no longer fully covers the adjacent strip:

$$d_{\mathrm{NS}}(t) = \frac{H_{\max}}{\tan(\alpha_{\mathrm{sun}})} \cdot \left| \cos(\gamma_{\mathrm{sun}} - \mathrm{axis\_azimuth}) \right|$$

$$f_{\mathrm{trans}} = \frac{\min(2\,d_{\mathrm{NS}},\, L_{\mathrm{tracker}})}{L_{\mathrm{tracker}}}$$

$$\mathrm{FC}_{\mathrm{NS}} = 1 + (1 - \mathrm{PAR}_{\mathrm{rel,SAU}}) \cdot 0.5 \cdot f_{\mathrm{trans}}$$

where $H_{\max} = H_{\mathrm{hub}} + (W/2)\sin(\beta_{\max})$ is the maximum panel height (reached at full tracker tilt), $L_{\mathrm{tracker}}$ is the row length along the axis direction (Table 1), $\alpha_{\mathrm{sun}}$ and $\gamma_{\mathrm{sun}}$ are the solar elevation and azimuth, and PAR_rel,SAU is the field-level relative PAR averaged over the *Superficie Agricola Utilizzata* (SAU), i.e. the utilised agricultural area within the array footprint. The field-level coefficient is then the area- and FC-weighted average across the central rows, the edge rows, the outer strip, and the residual full-sun area beyond the array footprint.

---

## 3. Software architecture

### 3.1 Dependencies and structure

SolRatio is implemented in Python 3.10+. The principal third-party dependencies are:

- `bifacial_radiance` (NREL), wrapping Radiance for bifacial photovoltaic scene simulation;
- `pvlib` (Sandia National Laboratories), for solar position, tracker geometry, and backtracking;
- `pandas` and `numpy` for data manipulation;
- `openpyxl` and `lxml` for Excel I/O;
- `reportlab` for PDF report generation;
- `matplotlib` for diagnostic plotting.

Radiance itself (the rtrace / oconv / gendaylit binaries) must be installed and available on the system PATH. A `check_environment.py` utility verifies that all components are correctly installed.

**Validation pedigree.** SolRatio inherits a physically validated stack. Radiance, the underlying ray-tracer, has been validated against *measured* room illuminances under real skies to within ±10 % — the accuracy of the instruments themselves (Mardaljevic 1995); its `gendaylit` sky uses the Perez all-weather luminance model, itself validated against measured sky luminances (Perez et al. 1993); and `bifacial_radiance`, the PV-specific layer, has been validated by NREL against *field* measurements of rear irradiance and bifacial gain (agreement better than ~2 % absolute on bifacial gain; Ayala Pelaez et al. 2019). An internal reproducibility audit further verifies that SolRatio's custom `rtrace` path reproduces the official `bifacial_radiance` workflow on identical scenes to sub-percent agreement — an *internal-consistency* check that confirms SolRatio uses this validated stack faithfully, rather than re-validating the underlying physics.

The source tree is organised around a thin orchestration layer (`calcola_br.py`) that drives a domain-specific ray-tracing engine (`br_engine.py`), a small set of numerical and post-processing modules (`solratio_core.py`, `solratio_edge.py`, `solratio_yield.py`), I/O adapters (`solratio_excel.py`, `solratio_pdf.py`), and optional analysis layers (`solratio_multiyear.py`, `solratio_bifacial.py`). A complementary VBA module (`SolRatio_Calcolo.bas`) exposes the workflow as a one-click launcher inside the Excel workbook.

### 3.2 Workflow

The end-to-end simulation flow is:

1. The user populates the parameter sheet of `SolRatio_progetto.xlsm` with the project geometry, optical properties, and tracker configuration.
2. `calcola_br.py` reads the parameters and invokes `br_engine.pvgis_to_epw` to fetch the multi-year PVGIS time series and build the composite typical meteorological year.
3. `br_engine.run_annual` constructs the Radiance scene, computes the tracker angles for the 8760 hours of the year, filters diurnal hours (`sun_elevation > 2°` and `GHI > 20 W/m²`), pre-compiles the scene octree for the set of unique tracker angles, generates the per-hour sky description with `gendaylit`, runs `rtrace` in parallel for each diurnal hour, and returns the hourly irradiance arrays for the central, edge, and outer sampling profiles, together with the open-sky reference.
4. The post-processing layer converts broadband irradiance to PAR using the Jacovides variable PAR fraction, computes the DLI, and aggregates by spatial zone and by month.
5. The crop-yield layer evaluates $K_{\mathrm{agv}}(\mathrm{RSR})$ for the selected crop category and the field-level aggregation with the $\mathrm{FC}_{\mathrm{NS}}$ correction.
6. Results are written to a multi-sheet Excel workbook (`risultati_*.xlsx`) and to a PDF report (`report_SolRatio_*.pdf`).

A typical annual simulation on a modern multi-core workstation (eight or more physical cores, 32 GB of RAM, NVMe storage) completes in approximately 1.5–3 minutes, of which roughly 80% is spent in the parallel `rtrace` step. The persistent octree cache reduces the per-hour cost by 30–60% when active — primarily in single-day validation workflows with a fixed tilt — and is automatically bypassed in the standard annual workflow as discussed in Section 6.

### 3.3 New features in v4.2.0

Version 4.2.0 closed the planned v4.2 scope, including three items that had been originally scheduled for v4.3 and were anticipated with reduced scope (the "alpha" tier — specular-only transmission for partially-transparent panels — and the "beta" tier — view-factor-only back-side irradiance for bifacial yield). All additions preserve the v4.1 default behaviour when their associated parameters are set to zero or omitted.

**Scientific extensions**

- **Multi-year stochastic mode and P10/P50/P90 quantiles** (`engine/solratio_multiyear.py`): a sequential orchestrator that, given the available PVGIS multi-year time series, executes one annual simulation per year and aggregates the per-KPI distribution. Output is saved incrementally; runs interrupted mid-way can be resumed.
- **Generalised tracker frame coordinates for arbitrary axis_azimuth**: the sensor and scene transformations have been refactored to support arbitrary tracker azimuth orientations, while remaining bit-for-bit identical to v4.1 for the historical north-south default. A runtime warning is emitted when the deviation from north-south exceeds 30°, because the Laub et al. (2022) yield curves are calibrated on north-south shading regimes.
- **Across-axis slope (L2 / L3 anticipated)**: the row replication for non-zero cross-axis slope is now azimuth-aware, and the Radiance ground plane is genuinely tilted using a Rodrigues rotation around the tracker axis. For $\mathrm{slope\_cross} = 0$ the behaviour reduces to the v4.1 default.
- **Single-axis bifaciality module (beta tier)** (`engine/solratio_bifacial.py`): an additive module that, given the module efficiency and bifaciality factor, computes the total plane-of-array irradiance as $\mathrm{POA}_{\mathrm{total}} = \mathrm{POA}_{\mathrm{front}} + b_{\mathrm{f}} \cdot \mathrm{POA}_{\mathrm{back}}$ and the resulting annual electrical yield. The default $b_{\mathrm{f}} = 0$ preserves monofacial behaviour. The back-side POA is currently estimated using a simplified view-factor model ($0.5 \cdot \rho_{\mathrm{g}} \cdot \mathrm{GHI}$); a dedicated Radiance back-side simulation is planned for v4.2.x.
- **Semi-transparent panel materials via BRTDfunc (alpha tier)**: the `_apply_tau_material` routine now accepts an optional $\tau_{\mathrm{diff}}$ parameter that introduces a Lambertian diffuse component in the transmitted radiation; the mapping to the Radiance `trans` material is given in Section 2.3. Full BSDF (`prism2`, XML) support is planned for v4.5+.

**Engineering improvements**

- **Persistent octree cache** (`engine/_scene_cache.py`): a cache keyed by project geometry that avoids regenerating the Radiance octree for every hour when the number of unique tracker angles is small. The cache is automatically disabled above 200 unique angles to avoid the cost of pre-compilation in the typical annual workflow (~3900 unique angles per year), in which the legacy per-hour path is followed unchanged. The cache is most effective in single-day validation workflows with a fixed tilt.
- **Standardised project folder layout (additive)**: a `find_pvgis_csv` helper searches for the PVGIS input file first in the project root, then in an `input/` subfolder.
- **Excel version label auto-update via VBA**: a `Workbook_Open()` handler reads the `engine/VERSION` file and updates cell `A1` of the Launcher sheet, ensuring that the file always advertises the version actually installed.

---

## 4. Validation

The validation strategy compares SolRatio against the *official* bifacial_radiance workflow — that is, the same ray-tracing engine driven directly without the SolRatio orchestration — applied to the same scene, the same sky description, and the same numerical parameters. Because both pipelines share Radiance as the underlying ray tracer, the residual between them is a measure of the consistency of the SolRatio implementation rather than of the physical accuracy of Radiance itself; the latter is established in the extensive NREL and LBNL literature on Radiance validation.

It is important to emphasise that the validation reported in this section is a *code-to-code* consistency check, not a *code-to-measurement* validation against ground-truth photometric data. Experimental validation against PAR/DLI measurements at instrumented agrivoltaic test sites is identified as a parallel objective in the roadmap (Section 7).

### 4.1 Reference setup

The benchmark scene is the `Sample` project distributed with the repository: a typical Po Valley site at 45.30° N, 9.34° E, with a 4-row demonstration scene (`br_n_rows = 4`), $\mathrm{pitch} = 5.0$ m, $\mathrm{GCR} = 0.476$, $W = 2.38$ m, hub height $3.13$ m ($H_{\min} = 2.1$ m), $\beta_{\max} = 60°$, $\mathrm{axis\_azimuth} = 180°$ (north-south), backtracking on, opaque modules ($\tau = 0$), and a horizontal ground plane ($\mathrm{slope} = 0$). Two representative days are used: the vernal equinox (21 March) and the summer solstice (21 June).

For each day, both pipelines compute the hourly irradiance on the same 51-point sensor grid spanning the pitch interval. The metrics reported are the mean bias error (MBE), the root-mean-square error (RMSE), and the coefficient of determination (R²) between the two hourly time series, evaluated jointly over the sensor grid.

### 4.2 Results

Table 2 reports the validation metrics for both days, jointly evaluated across the 51-point sensor grid and all diurnal hours. The metrics were re-measured with v4.3.0 after the tracking-scene correction (Section 2.3).

**Table 2.** Validation metrics of SolRatio against the official bifacial_radiance workflow on the *Sample* scene (45.30° N, 9.34° E; `br_n_rows` = 4), v4.3.0, Radiance 6.0, 2026-06-11.

| Indicator       | 21 March | 21 June |
| --------------- | -------- | ------- |
| MBE (mean bias) | +0.0%    | −0.0%   |
| RMSE            | 0.0%     | 0.1%    |
| R²              | 1.0000   | 0.9999  |

The mean bias is well below 1% in absolute value on both dates and the coefficient of determination is essentially unity. Independent re-executions return R² ≥ 0.9975: the residual scatter is consistent with the intrinsic stochastic nature of the Radiance Monte Carlo ray tracer (ambient sampling) and with small differences in scene-boundary handling between the two pipelines at low solar elevations.

It must be stressed that this comparison is a *consistency* check: both pipelines build the scene with the same θ→(tilt, azimuth) convention, so a convention error affects both identically and is invisible here — which is precisely how the counter-rotated scene of v4.1.0–v4.2.2 survived this validation (Section 2.3). The independent check of Section 4.3 addresses this structural blindness.

A scene-dimension consistency check was added in v4.1.1 after a debugging session revealed that `validazione_br._run_br_official()` was ignoring the `br_n_rows` parameter while `br_engine.run_annual()` was respecting it; the two pipelines were therefore comparing arrays of seven rows against arrays of four rows, generating a spurious systematic bias of +4.5% on the equinox and +1.2% on the solstice. After the fix the two pipelines simulate identical scenes and the comparison returns the residuals reported above. As a corollary of that investigation, an explicit recommendation has been added to the parameter documentation: `n_ext ≥ 3` (`n_rows ≥ 7`) for routine use, and `n_ext ≥ 4` (`n_rows ≥ 9`) for benchmarking and scientific publications. The bundled Sample project uses `br_n_rows = 4` to keep the regression-gate runtime short; with fewer rows the radiation at the central pitch is somewhat overestimated at grazing sun angles (see `documentazione/PARAMETRI_RADIANCE.md`), which is acceptable for a regression sentinel but should be kept in mind when reading the absolute gate values below.

### 4.3 Independent reference: native 1-axis workflow (added in v4.3.0)

A second, structurally independent check runs the same scene through the *native* bifacial_radiance 1-axis chain — `set1axis` → `gendaylit1axis` → `makeScene1axis` → `makeOct1axis` → `analysis1axisground` — in which the tracker angles are computed by pvlib *inside the library* (`surface_tilt`/`surface_azimuth`) and the ground sensors are positioned by the library itself across one full pitch. No SolRatio code participates in the geometry, so a convention error in the engine cannot propagate to this reference. Because the native workflow fixes its own rtrace parameters (`accuracy='low'`, `-ab 2`) while the engine uses the project-configured ones (the engine default is also `-ab 2`, but the bundled Sample sets `-ab 1` via cell B48), point-by-point profiles are not comparable at the sub-percent level; the comparison metric is the daily ground-to-GHI ratio (spatial mean of the ground irradiance, summed over the day, divided by the daily GHI). Measured agreement on the Sample project (v4.3.0, 2026-06-11): **−0.1 percentage points** on 21 March and **−0.4 percentage points** on 21 June. The same metric evaluated against the historical (counter-rotated) engine showed **+24.3 percentage points** on the clear-sky solstice day — the defect signature — and +0.6 pp on the overcast equinox day, where diffuse light dominates and panel orientation matters little.

### 4.4 Regression gate

A regression gate is also part of the release workflow: the two projects distributed with the repository must reproduce a field-level $K_{\mathrm{agv}}$ for C3 cereals of **57.5%** (*Sample*, north-south) and **55.3%** (*Sample_EW*, east-west), within **±0.2 percentage points** — the Radiance ambient sampling is stochastic and results are not bit-identical between runs. The reference values were measured with v4.3.0 after the tracking-scene correction (the v4.2.1 references were 84.1% and 79.2% on the counter-rotated scene; the v4.1.2 reference was 84.00% with 3995 simulated daylight hours, reduced to 3919 hours by the v4.2.1 UTC correction of the EPW header — the decomposition is documented in the changelog). The gate is exercised by `_smoke_regression.bat` (Windows) and `_smoke_regression.sh` (Linux/macOS); every release candidate must pass it.

---

## 5. Application example: tracker axis orientation and the field-level agrivoltaic coefficient

A natural design question for an agrivoltaic project is the choice of the
tracker axis orientation. North-south axes (the historical default of
single-axis trackers) produce a shading pattern that sweeps the inter-row
ground during the day, while east-west orientations concentrate the shadow
geometry differently; the agronomic consequences are not obvious a priori,
and the Laub et al. (2022) yield curves are calibrated on north-south
regimes (Section 2.5).

The two projects distributed with the repository provide a controlled
comparison: *Sample* (north-south, `axis_azimuth = 180°`) and *Sample_EW*
(east-west, `axis_azimuth = 90°`) are identical in every other parameter
(site, geometry, optics, edge configuration, meteorology). With v4.3.0, the
field-level $K_{\mathrm{agv}}$ for C3 cereals is **57.5%** for the
north-south layout and **55.3%** for the east-west variant: an east-west
penalty of approximately **2.2 percentage points** at equal geometry, driven
by the different spatial distribution of the transmitted light across the
pitch. (With the counter-rotated scene of previous releases the same
comparison read 84.1% vs 79.2%: both values overestimated, and the apparent
orientation penalty inflated to 4.9 points.) The full per-crop comparison is
written to the `Resa_Colturale` sheet of the two result workbooks, and the
same pair of runs constitutes the release regression gate (Section 4.4).

The runtime warning for $|\mathrm{axis\_azimuth} - 180°| > 30°$ applies to
the east-west case: the crop-response step relies on dose-response curves
calibrated on north-south shading regimes, so the 55.3% figure should be
read as a geometric/radiometric result first, and as an agronomic estimate
with the caution discussed in Section 6.


---

## 6. Known limitations

The current release has the following declared limitations.

**No experimental validation against ground-truth PAR/DLI measurements has yet been performed.** The validation in Section 4 is a code-to-code consistency check against the official bifacial_radiance workflow, not a code-to-measurement validation. The underlying Radiance ray tracer has been extensively validated against measured photometric data in the architectural lighting and PV literature, which transfers part of the credibility to SolRatio, but a dedicated agrivoltaic field validation against *in situ* PAR sensors at instrumented test sites is still missing and is identified as a parallel objective in the roadmap (Section 7).

**Posts and structural elements are not rendered in the Radiance scene.** Module supports, posts, and other secondary structures cast shadows on the ground that are not captured by this edition (no dormant code paths are retained); the development of full three-dimensional post modelling continues in the hosted product line.

**The back-side plane-of-array irradiance for bifacial yield is estimated with a simplified view factor model.** In v4.2.0 the back-side POA is approximated as `0.5 · albedo · GHI`, a standard single-axis tracker view-factor estimate. A dedicated Radiance simulation with rear-facing sensors is not included in this edition.

**The persistent octree cache is automatically disabled in the standard annual workflow.** A typical 8760-hour simulation produces approximately 3900 unique tracker angles, making the per-angle pre-compilation step more expensive than the cost savings it would deliver. The cache is therefore active only when the number of unique tracker angles does not exceed 200 — primarily in single-day validation workflows with a fixed tilt. Since v4.2.1 the cached octrees are frozen (self-contained), making their reuse across runs reliable.

**The PV electrical yield calculation in the bifacial module is multiplicative and does not propagate module temperature, system losses, or soiling.** A full electrical model (temperature dependence, system losses) is outside the scope of this edition and is addressed by the hosted product line.

**The crop-yield curves of Laub et al. (2022) are calibrated on north-south shading regimes.** A runtime warning is emitted when $|\mathrm{axis\_azimuth} - 180°| > 30°$, because the response of crops to predominantly east-west shading patterns may differ from the calibration dataset. The north-south / east-west comparison in Section 5 quantifies the geometric effect empirically, but a more rigorous agronomic treatment will require updated dose-response curves from east-west experiments.

---

## 7. Roadmap

**v4.2.x — reference edition (this repository).** The public line is
maintained for correctness and reproducibility: bug fixes, documentation
clarifications, and updates to this technical note. No new modelling
features are planned for the public repository.

**Hosted product line.** The development of new functionality —
three-dimensional post modelling, a complete water balance and
evapotranspiration module, DC/AC energy yield, real field geometries (KML),
and a multi-user web interface — continues in the hosted product *SolRatio
Pro*, which uses this edition as its cited reference engine.

**Cross-cutting objective — Experimental validation.** Comparison against
PAR/DLI ground-truth measurements at instrumented agrivoltaic test sites is
a parallel objective that does not map to a specific version of the
software. Collaboration with experimental groups is actively sought;
anonymised in-field PAR datasets shared by users via the project repository
will be incorporated in a dedicated validation appendix as they become
available.


---

## 8. Conclusions

SolRatio is an open-source modelling tool that addresses the agronomic side of agrivoltaic design through a physically rigorous ray-tracing pipeline integrated with calibrated crop-yield curves. The v4.2 line extended the modelling scope to multi-year stochastic analysis, arbitrary tracker axis orientation, basic bifaciality, semi-transparent modules, and inclined terrain. The v4.3.0 release corrects the counter-rotated tracking scene inherited from v4.1.0 (Section 2.3): tracking-mode ground-light estimates of all previous releases are overestimated and must not be reused, and the regression-gate references have been re-measured accordingly. The episode also reshaped the validation strategy: a consistency check between pipelines that share a geometric convention cannot detect an error in that convention, which is why the independent native-workflow reference of Section 4.3 is now part of the released validation.

Validation against the official bifacial_radiance workflow returns sub-percent mean bias errors and coefficients of determination of at least 0.997 on both equinox and solstice days for a representative Po Valley scene, and the independent native-workflow reference agrees within 0.5 percentage points on the daily ground-to-GHI ratio. Field validation against *in situ* PAR measurements is a parallel objective in the roadmap. The tool is operated through a parameter-driven Excel workbook with one-click launchers, and is released on GitHub under the Apache 2.0 licence; every release is deposited on Zenodo with both a concept DOI and a version-specific DOI for citation.

The public repository is maintained as a citable reference edition (correctness and reproducibility fixes); the development of a complete decision-support tool for agrivoltaic project design continues in the hosted product line, which cites this engine as its reference. Contributions, bug reports, and validation datasets from operating agrivoltaic plants are welcome through the GitHub issue tracker and pull-request workflow of the repository.

---

## 9. Data and code availability

The source code is hosted on GitHub at <https://github.com/eurrag/SolRatio> under the Apache 2.0 licence. Every release is deposited on Zenodo via the automated GitHub-Zenodo connector.

- **Concept DOI** (recommended for general citation, always resolves to the latest version): [10.5281/zenodo.19959581](https://doi.org/10.5281/zenodo.19959581)
- **Version-specific DOI for v4.3.0**: assigned at the Zenodo deposit of this release.
- Version-specific DOI for v4.2.1 (immutable; ⚠ tracking-mode results overestimated, see Section 2.3 — not recommended for new citations): [10.5281/zenodo.20642574](https://doi.org/10.5281/zenodo.20642574)
- Version-specific DOI for v4.2.0 (immutable; same caveat): [10.5281/zenodo.20277335](https://doi.org/10.5281/zenodo.20277335)

The reference *Sample* project used for the validation in Section 4 is included in the repository under `progetti/Sample/`. The east-west variant *Sample_EW* used for the comparison of Section 5 is included under `progetti/Sample_EW/` and exercised, together with *Sample*, by the release regression gate.

This technical note is itself deposited on Zenodo as a stand-alone publication; the placeholder `[DOI_PLACEHOLDER]` in the self-citation of Section 10 (Pesavento, 2026b) will be replaced with the assigned DOI upon deposit.

---

## 10. References

Ayala Pelaez, S., C. Deline, S. M. MacAlpine, B. Marion, J. S. Stein, and R. K. Kostuk (2019). Comparison of bifacial solar irradiance model predictions with field validation. *IEEE Journal of Photovoltaics*, 9(1), 82–88. <https://doi.org/10.1109/JPHOTOV.2018.2877000>

Ayala Pelaez, S., and C. Deline (2020). bifacial_radiance: a python package for modeling bifacial solar photovoltaic systems. *Journal of Open Source Software*, 5(50), 1865. <https://doi.org/10.21105/joss.01865>

Dupraz, C., H. Marrou, G. Talbot, L. Dufour, A. Nogier, and Y. Ferard (2011). Combining solar photovoltaic panels and food crops for optimising land use: Towards new agrivoltaic schemes. *Renewable Energy*, 36(10), 2725–2732. <https://doi.org/10.1016/j.renene.2011.03.005>

Goetzberger, A., and A. Zastrow (1982). On the coexistence of solar-energy conversion and plant cultivation. *International Journal of Solar Energy*, 1(1), 55–69. <https://doi.org/10.1080/01425918208909875>

Holmgren, W. F., C. W. Hansen, and M. A. Mikofski (2018). pvlib python: a python package for modeling solar energy systems. *Journal of Open Source Software*, 3(29), 884. <https://doi.org/10.21105/joss.00884>

Huld, T., R. Müller, and A. Gambardella (2012). A new solar radiation database for estimating PV performance in Europe and Africa. *Solar Energy*, 86(6), 1803–1815. <https://doi.org/10.1016/j.solener.2012.03.006>

Jacovides, C. P., F. S. Tymvios, V. D. Assimakopoulos, and N. A. Kaltsounides (2004). Comparative study of various correlations in estimating hourly diffuse fraction of global solar radiation. *Renewable Energy*, 31(15), 2492–2504. <https://doi.org/10.1016/j.renene.2006.03.009>

Joint Research Centre (n.d.). *PVGIS — Photovoltaic Geographical Information System*. European Commission. <https://re.jrc.ec.europa.eu/pvg_tools/> (accessed 2026-05-19).

Laub, M., L. Pataczek, A. Feuerbacher, S. Zikeli, and P. Högy (2022). Contrasting yield responses at varying levels of shade suggest different suitability of crops for dual land-use systems: a meta-analysis. *Agronomy for Sustainable Development*, 42, 51. <https://doi.org/10.1007/s13593-022-00783-7>

Mardaljevic, J. (1995). Validation of a lighting simulation program under real sky conditions. *Lighting Research & Technology*, 27(4), 181–188.

Marrou, H., L. Guilioni, L. Dufour, C. Dupraz, and J. Wery (2013). Microclimate under agrivoltaic systems: Is crop growth rate affected in the partial shade of solar panels? *Agricultural and Forest Meteorology*, 177, 117–132. <https://doi.org/10.1016/j.agrformet.2013.04.012>

Ministero dell'Ambiente e della Sicurezza Energetica (2023). *Linee Guida in materia di impianti agrivoltaici di natura innovativa* (D.M. 436/2023). Republic of Italy.

Perez, R., R. Seals, and J. Michalsky (1993). All-weather model for sky luminance distribution — preliminary configuration and validation. *Solar Energy*, 50(3), 235–245. <https://doi.org/10.1016/0038-092X(93)90017-I>

Pesavento, S. (2026a). *SolRatio: Modello di irradianza al suolo e stima delle rese colturali per impianti agrivoltaici a tracker monoassiale* (v4.2.0) [Software]. Zenodo. <https://doi.org/10.5281/zenodo.20277335>

Pesavento, S. (2026b). *SolRatio: A Ground-Irradiance and Crop-Yield Model for Single-Axis Tracker Agrivoltaic Systems. Technical Note* (v1.3). Zenodo. https://doi.org/10.5281/zenodo.[DOI_PLACEHOLDER]

Trommsdorff, M., J. Kang, C. Reise, S. Schindele, G. Bopp, A. Ehmann, A. Weselek, P. Högy, and T. Obergfell (2021). Combining food and energy production: Design of an agrivoltaic system applied in arable and vegetable farming in Germany. *Renewable and Sustainable Energy Reviews*, 140, 110694. <https://doi.org/10.1016/j.rser.2020.110694>

Ward, G. J. (1994). The RADIANCE lighting simulation and rendering system. In *Proceedings of SIGGRAPH '94* (pp. 459–472). Association for Computing Machinery. <https://doi.org/10.1145/192161.192286>. Software available at <https://radsite.lbl.gov/radiance/> (Lawrence Berkeley National Laboratory).

Zainali, S., S. A. Lu, S. M. Stridh, A. Avelin, S. Amaducci, M. Colauzzi, and P. E. Campana (2023). Direct and diffuse shading factors modelling for the most representative agrivoltaic system layouts. *Applied Energy*, 339, 120981. <https://doi.org/10.1016/j.apenergy.2023.120981>

---

## Appendix A. Suggested figures (placeholders)

The following figures are recommended for the deposited PDF; placeholders are listed here for the author to generate from the project files.

- **Figure 1**. Geometry of the simulated scene: pitch $P$, module width $W$, hub height $H_{\mathrm{hub}}$, maximum tracker tilt $\beta_{\max}$, with the under-tracker / edge / central sampling zones overlaid. *Suggested source: schematic produced manually or via Inkscape.*
- **Figure 2**. Spatial profile of the annual mean ground $\mathrm{PAR}_{\mathrm{rel}}$ across the pitch for the *Sample* project, with the four agronomic zones marked. *Suggested source: the `Heatmap_PAR` and `PAR_DLI_Profilo` sheets of `risultati_*.xlsx`.*
- **Figure 3**. Validation scatter: hourly SolRatio irradiance versus the official bifacial_radiance reference, for 21 March and 21 June; one panel per date, with the 1:1 line and the regression coefficients overlaid. *Suggested source: `validazione_br.py` output, post-processed.*
- **Figure 4**. Per-crop comparison of the field-level $K_{\mathrm{agv}}$ between the *Sample* (N-S) and *Sample_EW* (E-W) projects. *Suggested source: the `Resa_Colturale` sheets of the two result workbooks.*

---

## Appendix B. Nomenclature

**Acronyms**

| Acronym     | Expansion                                                                |
| ----------- | ------------------------------------------------------------------------ |
| BR          | bifacial_radiance (NREL ray-tracing framework for bifacial PV)           |
| BRTDfunc    | Bidirectional Reflectance/Transmittance Distribution function (Radiance) |
| BSDF        | Bidirectional Scattering Distribution Function                           |
| CIE         | Commission Internationale de l'Éclairage                                 |
| DHI         | Diffuse Horizontal Irradiance [W/m²]                                     |
| DLI         | Daily Light Integral [mol/m²/d]                                          |
| DNI         | Direct Normal Irradiance [W/m²]                                          |
| D.M.        | Decreto Ministeriale (Italian Ministerial Decree)                        |
| EPW         | EnergyPlus Weather (file format)                                         |
| FC_NS       | longitudinal correction factor for north-south end-of-row effect         |
| GCR         | Ground Coverage Ratio                                                    |
| GHI         | Global Horizontal Irradiance [W/m²]                                      |
| JRC         | Joint Research Centre (European Commission)                              |
| K_agv       | Agrivoltaic coefficient (crop-yield ratio under array to open field)     |
| LBNL        | Lawrence Berkeley National Laboratory                                    |
| LCOE        | Levelised Cost of Energy                                                 |
| MASE        | Ministero dell'Ambiente e della Sicurezza Energetica (Italy)             |
| MBE         | Mean Bias Error                                                          |
| NREL        | National Renewable Energy Laboratory (United States)                     |
| P10/P50/P90 | 10th / 50th / 90th percentile (e.g. of inter-annual variability)         |
| PAR         | Photosynthetically Active Radiation [µmol/m²/s]                          |
| POA         | Plane-of-Array (irradiance) [W/m²]                                       |
| PV          | Photovoltaic                                                             |
| PVGIS       | Photovoltaic Geographical Information System (JRC)                       |
| RMSE        | Root-Mean-Square Error                                                   |
| RSR         | Radiation Stress Ratio = 1 − PAR_rel                                     |
| SARAH3      | Surface Solar Radiation Data Set – Heliosat, version 3                   |
| SAU         | Superficie Agricola Utilizzata (utilised agricultural area)              |
| TMY         | Typical Meteorological Year                                              |

**Principal symbols**

| Symbol                  | Meaning                                                | Unit |
| ----------------------- | ------------------------------------------------------ | ---- |
| $E$                     | Broadband irradiance                                   | W/m² |
| $H_{\mathrm{hub}}$      | Tracker hub height                                     | m    |
| $H_{\min}$              | Minimum panel-to-ground clearance                      | m    |
| $H_{\max}$              | Maximum panel height at full tilt                      | m    |
| $k_t$                   | Clearness index                                        | —    |
| $K_{\mathrm{agv}}$      | Agrivoltaic coefficient (crop yield ratio)             | —    |
| $L_{\mathrm{tracker}}$  | Tracker row length along the axis                      | m    |
| $P$                     | Row pitch                                              | m    |
| $W$                     | Module width                                           | m    |
| $\alpha_{\mathrm{sun}}$ | Solar elevation                                        | °    |
| $\beta_{\max}$          | Maximum tracker tilt angle                             | °    |
| $\gamma_{\mathrm{sun}}$ | Solar azimuth                                          | °    |
| $\eta_{\mathrm{mod}}$   | Module electrical efficiency                           | —    |
| $\theta$                | Tracker rotation angle (instantaneous)                 | °    |
| $\theta_z$              | Solar zenith angle                                     | °    |
| $\rho_{\mathrm{g}}$     | Ground albedo                                          | —    |
| $\tau$                  | Module specular transmittance                          | —    |
| $\tau_{\mathrm{diff}}$  | Module Lambertian transmittance                        | —    |
| $\varphi$               | Frame rotation angle ($\mathrm{axis\_azimuth} - 180°$) | °    |

---

*Document version: 1.5 (2026-06-11). Revision history: v1.0 initial draft; v1.1 first internal review (literature, validation framing, formula notation, references); v1.2 second internal review (notation consistency, terminology, table numbering, references, conclusions); v1.3 third internal review (uniform math notation across tables and corpus, Ward 1994 reference, nomenclature appendix, structural cleanup of §1 and §3.3); v1.4 alignment with the v4.2.1 reference edition (pruned scope in §3, corrected Table 1 cell references against the code, UTC EPW header, updated regression gate in §4.2, new application example in §5, open-core roadmap in §7); v1.5 alignment with the v4.3.0 corrective release (counter-rotated tracking scene corrected and documented in §2.3, validation re-measured and independent native-workflow reference added in §4, regression gate and §5 comparison updated, corrected benchmark-scene parameters in §4.1). Prepared from the SolRatio v4.3.0 repository and release artefacts. For corrections and updates, please open an issue at <https://github.com/eurrag/SolRatio/issues>.*
