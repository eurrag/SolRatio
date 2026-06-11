"""
solratio_bifacial.py  |  SolRatio v4.3.0
========================================================================
Modulo bifacciale: estende il calcolo SolRatio alla produzione PV
"front + bifaciality_factor × rear" per pannelli bifacciali.

Scope β confermato dall'utente (decisione D4 del 2026-05-02):
- Calcolo di POA_back (irradianza posteriore moduli) via bifacial_radiance
- Calcolo della produzione PV totale = POA_front + bifaciality_factor × POA_back
- Output: nuove sezioni "Produzione bifacciale" in Excel/PDF
- Niente LCOE / business case (rinviato a v4.4 — Economia)

API
---

    bifacial_yield(p, br_result, module_efficiency=0.21, bifaciality_factor=0.7)
        → dict con POA_front_avg, POA_back_avg, energy_kwh, ecc.

    add_bifacial_to_excel(wb_out, bifacial_data, p)
        → aggiunge un foglio "Bifacciale" al workbook risultati

Note di design
--------------
Il modulo è ATTIVO solo se p['bifaciality_factor'] > 0. Con
bifaciality_factor=0 (default per moduli monofacciali) il calcolo
restituisce front-only ed è bit-per-bit identico al monofacciale.

Limitazioni (v4.3.0 — modello dichiaratamente semplificato)
------------------------------------------------------------
- POA_front ≈ GHI (proxy): il POA reale di un tracker e' tipicamente
  superiore al GHI del 20-35%. energy_front/energy_total sono quindi
  stime per difetto.
- POA_back ≈ 0.5 · albedo · GHI (view factor standard tracker), NON
  una simulazione Radiance dedicata con sensori posteriori.
- Conseguenza algebrica: il guadagno bifacciale percentuale e' la
  COSTANTE 100 · bf · 0.5 · albedo (es. bf=0.7, albedo=0.23 → +8.05%),
  indipendente da geometria e sito. Un calcolo POA reale (pvlib
  get_total_irradiance sugli angoli tracker, o run Radiance dedicato)
  e' nella linea prodotto hosted.
- La produzione PV usa una formula semplificata
  Energia_PV_anno [kWh] = (POA_front_avg + bf × POA_back_avg)
                         × Area_modulo × η_modulo × ore_anno
  senza propagazione di temperatura del modulo, perdite di sistema,
  inverter, soiling. L'estensione a un PVWatts-like è prevista per
  v4.4 con LCOE.
"""
from __future__ import annotations

from typing import Mapping
import numpy as np


# Default sensati per una valutazione preliminare.
DEFAULT_MODULE_EFFICIENCY = 0.21          # 21% efficienza modulo monofacciale moderno (PERC)
DEFAULT_BIFACIALITY_FACTOR = 0.0           # 0 = monofacciale; 0.65-0.85 tipico bifacciale moderno


def bifacial_yield(
    p: Mapping,
    br_result: Mapping,
    module_efficiency: float = DEFAULT_MODULE_EFFICIENCY,
    bifaciality_factor: float | None = None,
) -> dict:
    """
    Stima della produzione PV bifacciale dal risultato BR.

    Parameters
    ----------
    p : dict
        Parametri progetto (lat, lon, pitch, W, ecc.). Se contiene la
        chiave `bifaciality_factor`, viene usata come default.
    br_result : dict
        Output di `br_engine.run_annual()`. Deve contenere almeno
        `'IRR_hourly'` (n_ore × n_punti, W/m²) e `'ghi_arr'`.
    module_efficiency : float, default 0.21
        Efficienza modulo PV (frazione, 0-1).
    bifaciality_factor : float | None
        Fattore di bifacialità (POA_back contributo / POA_front contributo).
        0 = monofacciale; tipico 0.65-0.85 per bifacciali moderni.
        Se None, prende `p['bifaciality_factor']` o 0 di default.

    Returns
    -------
    dict
        - poa_front_avg_wm2  : POA front mediato su SAU+ore [W/m²]
        - poa_back_avg_wm2   : POA back mediato (stimato) [W/m²]
        - poa_total_avg_wm2  : front + bf × back [W/m²]
        - energy_front_kwh_m2: produzione monofacciale [kWh/m² annuo]
        - energy_total_kwh_m2: produzione bifacciale [kWh/m² annuo]
        - bifacial_gain_pct  : guadagno percentuale rispetto a monofacciale
    """
    if bifaciality_factor is None:
        bifaciality_factor = float(p.get('bifaciality_factor',
                                         DEFAULT_BIFACIALITY_FACTOR))

    irr_hourly = np.asarray(br_result['IRR_hourly'])  # (n_ore, n_pts)
    n_ore = irr_hourly.shape[0]

    # POA front: assumendo che IRR_hourly sia il POA orizzontale dei sensori
    # ground-level. Per il front del pannello servirebbe un calcolo POA con
    # tilt del modulo. Per semplicità v4.2.0, usiamo il GHI diurno come proxy
    # del front: questa è una semplificazione e va affinata in v4.2.x.
    ghi_arr = np.asarray(br_result.get('ghi_arr', []))
    daylight_indices = np.asarray(br_result.get('daylight_indices', []))
    if len(ghi_arr) == 0 or len(daylight_indices) == 0:
        raise ValueError("br_result manca di 'ghi_arr' o 'daylight_indices'")
    poa_front_hourly = ghi_arr[daylight_indices]
    poa_front_avg = float(poa_front_hourly.mean()) if len(poa_front_hourly) else 0.0

    # POA back: stima approssimata dall'IRR al suolo + albedo + view factor.
    # Per il calcolo completo serve un secondo run BR con sensori a quota
    # hub-W*sin(tilt)-0.05 e normale -Z. Qui usiamo una approssimazione
    # POA_back ≈ 0.5 * albedo * GHI (view factor standard tracker)
    # Da affinare in v4.2.x con calcolo Radiance dedicato.
    albedo = float(p.get('albedo', 0.23))
    poa_back_avg = 0.5 * albedo * poa_front_avg

    poa_total_avg = poa_front_avg + bifaciality_factor * poa_back_avg

    # Energia annua per m² modulo
    # (assumiamo n_ore_giorno come fattore di moltiplicazione, semplificato)
    hours_with_sun = n_ore  # ore diurne effettivamente simulate
    energy_front_kwh_m2 = (poa_front_avg * module_efficiency * hours_with_sun) / 1000.0
    energy_total_kwh_m2 = (poa_total_avg * module_efficiency * hours_with_sun) / 1000.0
    bifacial_gain_pct = (
        100.0 * (energy_total_kwh_m2 - energy_front_kwh_m2) / energy_front_kwh_m2
        if energy_front_kwh_m2 > 0 else 0.0
    )

    return {
        "bifaciality_factor": bifaciality_factor,
        "albedo": albedo,
        "module_efficiency": module_efficiency,
        "n_hours_simulated": int(hours_with_sun),
        "poa_front_avg_wm2": round(poa_front_avg, 1),
        "poa_back_avg_wm2": round(poa_back_avg, 1),
        "poa_total_avg_wm2": round(poa_total_avg, 1),
        "energy_front_kwh_m2": round(energy_front_kwh_m2, 1),
        "energy_total_kwh_m2": round(energy_total_kwh_m2, 1),
        "bifacial_gain_pct": round(bifacial_gain_pct, 2),
    }


def add_bifacial_to_excel(wb_out, bifacial_data: dict, p: Mapping) -> None:
    """
    Aggiunge un foglio "Bifacciale" al workbook openpyxl `wb_out`.

    Se `bifaciality_factor=0` (monofacciale), la sezione mostra
    solo la produzione monofacciale (no guadagno).
    """
    if "Bifacciale" in wb_out.sheetnames:
        del wb_out["Bifacciale"]
    ws = wb_out.create_sheet("Bifacciale")

    rows = [
        ("Produzione PV - calcolo bifacciale (v4.2.0)", ""),
        ("", ""),
        ("Parametri", ""),
        ("Albedo terreno", bifacial_data.get("albedo", "")),
        ("Efficienza modulo η", bifacial_data.get("module_efficiency", "")),
        ("Fattore bifacialità", bifacial_data.get("bifaciality_factor", "")),
        ("Ore simulate", bifacial_data.get("n_hours_simulated", "")),
        ("", ""),
        ("Irradianze medie [W/m²]", ""),
        ("POA front (modulo)", bifacial_data.get("poa_front_avg_wm2", "")),
        ("POA back (retro stimato)", bifacial_data.get("poa_back_avg_wm2", "")),
        ("POA totale bifacciale", bifacial_data.get("poa_total_avg_wm2", "")),
        ("", ""),
        ("Produzione [kWh/m²·anno]", ""),
        ("Front-only (monofacciale)", bifacial_data.get("energy_front_kwh_m2", "")),
        ("Bifacciale totale", bifacial_data.get("energy_total_kwh_m2", "")),
        ("Guadagno bifacciale %", bifacial_data.get("bifacial_gain_pct", "")),
        ("", ""),
        ("Note (modello semplificato)", ""),
        ("- POA front stimato col GHI (proxy: sottostima il POA tracker)", ""),
        ("- POA back stimato come 0.5 · albedo · GHI (approssimazione)", ""),
        ("- Guadagno % = 100·bf·0.5·albedo: costante per costruzione", ""),
        ("- Calcolo POA reale (pvlib/Radiance): linea prodotto hosted", ""),
    ]
    for r, (label, val) in enumerate(rows, start=1):
        ws.cell(row=r, column=1, value=label)
        ws.cell(row=r, column=2, value=val)
    ws.column_dimensions['A'].width = 40
    ws.column_dimensions['B'].width = 20
