"""
br_engine.py  |  SolRatio v4.1.1
=================================
Motore di calcolo basato su bifacial_radiance (Radiance ray-tracing).

Sostituisce il motore analitico di v3.3.x (pvlib VF + shadow + Perez)
con simulazione 3D fisicamente accurata via gendaylit/rtrace.

Funzioni principali:
  run_annual(p, epw_path, n_points=51)
    → Simulazione annuale: restituisce matrice IRR oraria + metadati
  run_singleday(p, epw_path, target_month, target_day, n_points=51)
    → Simulazione singolo giorno

Output:
  dict con:
    'IRR_hourly': np.ndarray (n_daylight, n_points)  [W/m²]
    'IRR_daily_cum': np.ndarray (n_points,)  [Wh/m²] cumulato annuo
    'daylight_indices': np.ndarray — indici ore diurne nell'anno (0..8759)
    'metdata': oggetto MetObj di bifacial_radiance
    'x_pts': np.ndarray (n_points,)
    'n_hours_ok': int
    'n_hours_err': int
"""

import os
import sys
import shutil
import tempfile
import warnings
import contextlib
import io
import time as _time
import multiprocessing
import subprocess as _subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

__version__ = '4.1.1'


# ══════════════════════════════════════════════════════════════════════════
# Trasmittanza pannello (tau) — materiale Radiance 'trans'
# ══════════════════════════════════════════════════════════════════════════

def _apply_tau_material(rad, tau, module_name='sr_module'):
    """
    Trasforma il modulo Radiance in semitrasparente usando il materiale 'trans'.

    Override del materiale opaco di default di bifacial_radiance (`Metal_Grey`
    o `black`) con un materiale Radiance `trans` calibrato sulla trasmittanza
    pannello tau (range 0-1).

    Mappatura per pannelli a vetro convenzionali (default):
        trans  = tau         frazione totale di luce trasmessa
        tspec  = 1.0         trasmissione speculare (vetro liscio: raggio passa dritto)
        spec   = 0.05        riflessione speculare frontale (vetro standard)
        R G B  = 1 - tau - spec   diffusione + assorbimento del backsheet

    Per pannelli a film sottile od organici (trasmissione diffusa): impostare
    `tspec` < 1.0 modificando questa funzione.

    Parametri
    ---------
    rad : bifacial_radiance.RadianceObj
        Oggetto Radiance già inizializzato.
    tau : float
        Trasmittanza pannello, 0 (opaco) ≤ tau ≤ 1 (trasparente).
    module_name : str
        Nome modulo passato a makeModule (default 'sr_module').

    Effetti
    -------
    - Modifica il file `objects/<module_name>.rad` sostituendo il riferimento
      al materiale opaco.
    - Crea il file `materials/sr_panel_trans.rad` con la definizione del
      materiale trans.
    - Aggiunge il file ai materialfiles di `rad`, in modo che venga incluso
      in tutte le scene Radiance generate successivamente.

    Raises
    ------
    RuntimeError se non si trova il file modulo o nessun materiale opaco standard.
    """
    if tau <= 0:
        return  # nessuna modifica per pannello opaco (default)
    if tau > 1:
        raise ValueError(f"tau deve essere in [0, 1], ricevuto {tau}")

    NEW_MATERIAL = 'sr_panel_trans'
    objects_dir = os.path.join(rad.path, 'objects')
    materials_dir = os.path.join(rad.path, 'materials')

    # 1. Trova il file modulo .rad (può essere sr_module.rad o varianti)
    if not os.path.isdir(objects_dir):
        raise RuntimeError(f"objects/ non trovato: {objects_dir}")
    candidates = [f for f in os.listdir(objects_dir)
                  if f.startswith(module_name) and f.endswith('.rad')]
    if not candidates:
        raise RuntimeError(f"File modulo .rad non trovato in {objects_dir} "
                           f"(prefisso atteso: '{module_name}')")
    mod_file = os.path.join(objects_dir, candidates[0])

    # 2. Identifica il materiale opaco da sostituire
    with open(mod_file, 'r') as f:
        mod_content = f.read()

    # Idempotenza: se il materiale è già stato sostituito (chiamata multipla
    # nello stesso rad, es. workflow di ottimizzazione), aggiorna solo i
    # parametri del materiale .rad senza ri-sostituire nel modulo.
    already_applied = NEW_MATERIAL in mod_content
    if already_applied:
        print(f'  TAU: materiale già applicato, aggiorno solo i parametri (tau={tau:.2f})')
    else:
        OLD_MATERIAL = None
        for cand_mat in ('Metal_Grey', 'black'):
            if cand_mat in mod_content:
                OLD_MATERIAL = cand_mat
                break
        if OLD_MATERIAL is None:
            raise RuntimeError(
                f"Materiale opaco standard non trovato in {mod_file}. "
                f"Atteso 'Metal_Grey' o 'black'. Contenuto:\n{mod_content[:500]}"
            )

        # 3. Sostituisci il materiale (string replace è safe perché Metal_Grey/black
        #    è univoco nei file modulo standard di bifacial_radiance)
        mod_content_new = mod_content.replace(OLD_MATERIAL, NEW_MATERIAL)
        with open(mod_file, 'w') as f:
            f.write(mod_content_new)

    # 4. Calcola parametri materiale trans
    spec = 0.05                                 # riflessione speculare vetro
    rgb_diff = max(0.0, 1.0 - float(tau) - spec)  # diffusione+assorbimento
    trans_param = float(tau)                    # frazione trasmessa
    tspec = 1.0                                 # trasmissione speculare
    rough = 0.0                                 # superficie liscia

    # 5. Crea file materiale custom
    if not os.path.isdir(materials_dir):
        os.makedirs(materials_dir, exist_ok=True)
    mat_file = os.path.join(materials_dir, f'{NEW_MATERIAL}.rad')
    with open(mat_file, 'w') as f:
        f.write(
            f'# SolRatio v4.1.1 — Materiale pannello semitrasparente\n'
            f'# Trasmittanza tau = {tau:.3f}\n'
            f'# Mappatura: trans=tau, tspec=1.0 (vetro), spec=0.05\n'
            f'# Bilancio: rifl_spec + rifl_diff + trasm = '
            f'{spec:.3f} + {rgb_diff:.3f} + {trans_param:.3f}\n'
            f'\n'
            f'void trans {NEW_MATERIAL}\n'
            f'0\n'
            f'0\n'
            f'7 {rgb_diff:.4f} {rgb_diff:.4f} {rgb_diff:.4f} '
            f'{spec:.4f} {rough:.4f} {trans_param:.4f} {tspec:.4f}\n'
        )

    # 6. Aggiungi il file ai materialfiles (precede i radfiles in oconv)
    if not hasattr(rad, 'materialfiles'):
        rad.materialfiles = []
    if mat_file not in rad.materialfiles:
        rad.materialfiles.append(mat_file)

    if not already_applied:
        print(f'  TAU: pannello semitrasparente attivato  '
              f'(tau={tau:.2f}, materiale Radiance trans)')


# ══════════════════════════════════════════════════════════════════════════
# PVGIS → EPW
# ══════════════════════════════════════════════════════════════════════════

def pvgis_to_epw(pvgis_csv_path, lat, lon, elevation=0):
    """
    Converte CSV PVGIS in EPW con metodo TMY mese-per-mese.
    Per ogni mese seleziona l'anno il cui GHI mensile è più vicino alla
    mediana di quel mese, poi assembla i 12 mesi in un anno sintetico.
    Restituisce (epw_path, tmy_info_str).
    """
    df = pd.read_csv(pvgis_csv_path, parse_dates=['time'])
    df['year'] = df['time'].dt.year
    df['month'] = df['time'].dt.month

    # ── Selezione TMY mese per mese ──────────────────────────────────
    import calendar
    ghi_monthly = df.groupby(['year', 'month'])['ghi'].sum().unstack(fill_value=0)
    years = sorted(df['year'].unique())

    tmy_months = []  # lista di (month, selected_year, DataFrame)
    tmy_years = {}
    ref_year = years[len(years) // 2]  # anno di riferimento per i timestamp

    print('  TMY mese-per-mese:')
    for m in range(1, 13):
        if m not in ghi_monthly.columns:
            continue
        col = ghi_monthly[m]
        median_ghi = col.median()
        best_year = int(col.iloc[(col - median_ghi).abs().argsort()[:1]].index[0])
        tmy_years[m] = best_year

        df_month = df[(df['year'] == best_year) & (df['month'] == m)].copy()
        tmy_months.append((m, best_year, df_month))

        m_name = calendar.month_abbr[m]
        print(f'    {m_name}: anno {best_year} '
              f'(GHI={col[best_year]:.0f} Wh/m², mediana={median_ghi:.0f})')

    # Assembla DataFrame TMY con timestamp normalizzati a ref_year
    frames = []
    for m, sel_year, df_m in tmy_months:
        df_m = df_m.copy()
        # Riscrive i timestamp con l'anno di riferimento
        df_m['time'] = df_m['time'].apply(
            lambda t: t.replace(year=ref_year))
        frames.append(df_m)
    df_tmy = pd.concat(frames, ignore_index=True)
    df_tmy = df_tmy.sort_values('time').reset_index(drop=True)

    n_hours = len(df_tmy)
    if n_hours != 8760:
        print(f'  AVVISO: TMY assemblato ha {n_hours} ore (attese 8760)')
        # Gestisci anno bisestile: rimuovi 29 feb se presente
        if n_hours > 8760:
            df_tmy = df_tmy[~((df_tmy['time'].dt.month == 2) &
                               (df_tmy['time'].dt.day == 29))]
            df_tmy = df_tmy.head(8760).reset_index(drop=True)
            print(f'  Troncato a {len(df_tmy)} ore')

    ghi_tmy = df_tmy['ghi'].sum()
    tmy_info = ', '.join(f'{calendar.month_abbr[m]}={y}'
                         for m, y in sorted(tmy_years.items()))
    print(f'  GHI TMY composito: {ghi_tmy:.0f} Wh/m²')

    tz_offset = round(lon / 15.0)
    city = f'PVGIS_{lat:.4f}_{lon:.4f}'

    headers = [
        f'LOCATION,{city},-,ITA,PVGIS,999999,{lat:.4f},{lon:.4f},{tz_offset:.1f},{elevation:.1f}',
        'DESIGN CONDITIONS,0',
        'TYPICAL/EXTREME PERIODS,0',
        'GROUND TEMPERATURES,0',
        'HOLIDAYS/DAYLIGHT SAVING,No,0,0,0',
        f'COMMENTS 1,TMY composite ({tmy_info}) for SolRatio v{__version__}',
        'COMMENTS 2,',
        'DATA PERIODS,1,1,Data,Sunday, 1/ 1,12/31',
    ]

    data_lines = []
    for i in range(len(df_tmy)):
        row = df_tmy.iloc[i]
        ts = row['time'] if isinstance(row['time'], pd.Timestamp) else pd.Timestamp(row['time'])
        hour = ts.hour + 1
        if hour == 0:
            hour = 24
        ghi_val = max(0, float(row.get('ghi', 0) or 0))
        dni_val = max(0, float(row.get('dni', 0) or 0))
        dhi_val = max(0, float(row.get('dhi', 0) or 0))
        temp = float(row.get('temp_air', 15) or 15)
        ws = max(0, float(row.get('wind_speed', 2) or 2))
        dew_point = temp - 5

        line = (f'{ref_year},{ts.month},{ts.day},{hour},60,'
                f'?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0?0,'
                f'{temp:.1f},{dew_point:.1f},60,101325,'
                f'9999,9999,9999,'
                f'{ghi_val:.0f},{dni_val:.0f},{dhi_val:.0f},'
                f'999999,999999,999999,9999,'
                f'0,{ws:.1f},'
                f'5,5,'
                f'9999,77777,9,999999999,'
                f'999,0.999,999,99,'
                f'999,999,99')
        data_lines.append(line)

    out_dir = os.path.dirname(pvgis_csv_path)
    out_path = os.path.join(out_dir, f'PVGIS_{lat:.4f}_{lon:.4f}_TMY.epw')

    with open(out_path, 'w', newline='\n') as f:
        for h in headers:
            f.write(h + '\n')
        for d in data_lines:
            f.write(d + '\n')

    print(f'  EPW generato: {out_path}')
    return out_path, tmy_info


# ══════════════════════════════════════════════════════════════════════════
# HELPER: STRIP WIDTH PER FASCIA ESTERNA
# ══════════════════════════════════════════════════════════════════════════

def _compute_strip_width_br(solpos, p, percentile=95):
    """Strip width dal P95 della distanza ombra (per fascia esterna bordo)."""
    W = p['W']
    beta_max = p['beta_max']
    H_max = p['H'] + 0.5 * W * np.sin(np.radians(beta_max))
    elev = solpos['apparent_elevation'].values
    valid = elev > 3.0
    if not valid.any():
        return p['pitch']
    tan_elev = np.tan(np.radians(np.clip(elev[valid], 3.0, 90.0)))
    d_shadow = H_max / tan_elev
    strip = float(np.percentile(d_shadow, percentile))
    return float(np.clip(strip, W, 5.0 * p['pitch']))


# ══════════════════════════════════════════════════════════════════════════
# MOTORE BIFACIAL_RADIANCE — SIMULAZIONE ANNUALE
# ══════════════════════════════════════════════════════════════════════════

def _apply_irrPlot_patch():
    """Monkey-patch per BR: evita errore irrPlot su sistemi senza display."""
    try:
        import bifacial_radiance
        if hasattr(bifacial_radiance, 'AnalysisObj'):
            bifacial_radiance.AnalysisObj.irrPlot = lambda *a, **kw: None
    except Exception:
        pass


def run_annual(p, epw_path, n_points=51, sample_days=None):
    """
    Simulazione annuale bifacial_radiance con gendaylit ora-per-ora.

    Parametri:
      p: dict parametri (lat, lon, pitch, W, H, H_min_terra, beta_max,
         GCR, axis_azimuth, backtracking, albedo)
      epw_path: percorso file EPW
      n_points: punti campionamento al suolo (default 51)
      sample_days: set di (month, day) per filtrare giorni, None = tutti

    Restituisce dict:
      'IRR_hourly': np.ndarray (n_daylight_ok, n_points) — W/m² per ora
      'IRR_daily_cum': np.ndarray (n_points,) — Wh/m² cumulato
      'daylight_indices': np.ndarray — indici (0..8759) delle ore diurne ok
      'daylight_timestamps': pd.DatetimeIndex — timestamp delle ore ok
      'metdata': MetObj di bifacial_radiance
      'x_pts': np.ndarray (n_points,)
      'n_hours_ok': int
      'n_hours_err': int
      'ghi_annual': float — GHI annuo totale [Wh/m²]
    """
    import bifacial_radiance as br

    _apply_irrPlot_patch()

    # ══════════════════════════════════════════════════════════════════
    # NOTA: i print() in questa funzione forniscono il log di esecuzione
    # visibile nella finestra comandi. NON rimuoverli negli sviluppi
    # successivi: sono l'unica interfaccia di monitoraggio in tempo reale
    # per l'utente (parametri, progresso %, tempi, errori).
    # ══════════════════════════════════════════════════════════════════

    print('  === SolRatio v4.1.1 — Motore bifacial_radiance ===')

    # ── Work dir senza spazi ─────────────────────────────────────────
    temp_work = tempfile.mkdtemp(prefix='sr_v4_')
    print(f'  Work dir: {temp_work}')

    try:
        rad = br.RadianceObj(name='SolRatio_v4', path=temp_work)

        # ── Carica meteo ─────────────────────────────────────────────
        epw_local = os.path.join(temp_work, os.path.basename(epw_path))
        shutil.copy2(epw_path, epw_local)
        metdata = rad.readWeatherFile(epw_local)
        rad.setGround(p.get('albedo', 0.23))

        # ── GHI annuo ────────────────────────────────────────────────
        ghi_arr = np.array(metdata.ghi if hasattr(metdata, 'ghi') and metdata.ghi is not None
                           else metdata.GHI, dtype=float)
        ghi_annual = float(np.sum(ghi_arr))
        print(f'  GHI annuo EPW: {ghi_annual:.0f} Wh/m² ({ghi_annual/1000:.0f} kWh/m²)')

        # ── Modulo ───────────────────────────────────────────────────
        module_length = 30.0
        # N file scena: se br_n_rows > 0 usa quel valore, altrimenti auto da n_ext
        br_n_rows = p.get('br_n_rows', 0)
        if br_n_rows > 0:
            n_rows = br_n_rows
            n_ext = (n_rows - 1) // 2
        else:
            n_ext = p.get('n_ext', 2)
            n_rows = 2 * n_ext + 1
        if n_rows < 3:
            n_rows = 3
        # ── Warning v4.1.1: n_rows insufficiente sotto-stima inter-row ─
        # Empiricamente (vedi CHANGELOG v4.1.1 e PARAMETRI_RADIANCE.md):
        # con n_rows < 7 la radiazione al pitch centrale è sovra-stimata
        # rispetto a un campo "grande" (asintotico) — bias fino a +4-5%
        # sull'equinozio, ~+1-2% sul solstizio. Ammissibile per test
        # rapidi, ma sconsigliato per simulazioni di routine e
        # benchmark/pubblicazione. Soglie suggerite:
        #   n_ext >= 3 (n_rows >= 7) → uso routine, bias residuo <1%
        #   n_ext >= 4 (n_rows >= 9) → benchmark, asintoto fisico
        if n_rows < 7:
            print(f'  ⚠ AVVISO scena ridotta: n_rows={n_rows} (n_ext={n_ext}). '
                  f'Le file insufficienti sotto-stimano l\'effetto inter-row → '
                  f'la radiazione al pitch centrale può essere sovra-stimata di '
                  f'+1-5% rispetto al limite "campo grande". Raccomandato: '
                  f'n_ext >= 3 (n_rows >= 7) per uso routine, n_ext >= 4 '
                  f'(n_rows >= 9) per benchmark/pubblicazione.')
        _center_row = n_rows // 2
        mod = rad.makeModule(name='sr_module', x=module_length,
                             y=p['W'], glass=False)

        # ── Trasmittanza pannello (v4.1.0) ─────────────────────────────
        # Se tau > 0, sostituisce il materiale opaco di default con
        # un materiale Radiance 'trans' calibrato sulla trasmittanza tau.
        _tau = float(p.get('tau', 0.0))
        if _tau > 0:
            _apply_tau_material(rad, _tau, module_name='sr_module')

        hub_height = p['H']
        print(f'  Hub height: {hub_height:.3f}m')
        print(f'  Scena: {n_rows} file (n_ext={n_ext}), modulo {module_length:.0f}m x {p["W"]:.2f}m')

        # ── Tracker angles (pvlib) ───────────────────────────────────
        # mode (B19): 0=astronomico, 1=backtracking, 2=tilt fisso
        # - mode 0/1: pvlib.tracking.singleaxis con backtrack=False/True
        # - mode 2:   tracker_theta costante = theta_fix (B20) su tutte le ore
        from pvlib import tracking as pvlib_tracking
        import pandas as _pd

        solpos = metdata.solpos
        mode = int(p.get('backtracking', 1))

        if mode == 2:
            # Tilt fisso: niente inseguimento, angolo costante da B20
            theta_fix = float(p.get('theta_fix', 0.0))
            n_steps = len(solpos['apparent_zenith'])
            tracker_theta = np.full(n_steps, theta_fix, dtype=float)
            print(f'  MODE: tilt fisso theta={theta_fix:+.1f}°')
        else:
            # Slope L1: propaga componenti pendenza a pvlib singleaxis
            _axis_tilt = p.get('slope_along_deg', 0.0)
            _cross_axis_tilt = p.get('slope_cross_deg', 0.0)
            tracker_res = pvlib_tracking.singleaxis(
                apparent_zenith=solpos['apparent_zenith'],
                solar_azimuth=solpos['azimuth'],
                axis_tilt=_axis_tilt,
                axis_azimuth=p.get('axis_azimuth', 180.0),
                max_angle=p['beta_max'],
                backtrack=(mode == 1),
                gcr=p['GCR'],
                cross_axis_tilt=_cross_axis_tilt,
            )
            tracker_theta = tracker_res['tracker_theta'].fillna(0).values
            mode_label = "backtracking" if mode == 1 else "astronomico"
            if _axis_tilt != 0.0 or _cross_axis_tilt != 0.0:
                print(f'  MODE: {mode_label}  (slope L1: axis_tilt={_axis_tilt:+.2f}° cross={_cross_axis_tilt:+.2f}°)')
            else:
                print(f'  MODE: {mode_label}')

        sun_elev = solpos['apparent_elevation'].values

        # ── Filtra ore diurne ────────────────────────────────────────
        daylight_mask = (sun_elev > 2.0) & (ghi_arr > 20.0)
        daylight_indices = np.where(daylight_mask)[0]
        n_daylight_full = len(daylight_indices)
        print(f'  Ore diurne: {n_daylight_full} (sole > 2°, GHI > 20 W/m²)')

        # ── Filtra su giorni campione ────────────────────────────────
        if sample_days is not None:
            sample_mask = np.array([
                (metdata.datetime[int(idx)].month,
                 metdata.datetime[int(idx)].day) in sample_days
                for idx in daylight_indices
            ])
            daylight_indices = daylight_indices[sample_mask]
            print(f'  Filtrato a {len(sample_days)} giorni: '
                  f'{len(daylight_indices)} ore')

        n_daylight = len(daylight_indices)

        # ── Linepts per rtrace (batch: central + edge + outer) ────
        compute_edge = p.get('n_file', 0) > 0
        xinc = p['pitch'] / (n_points - 1)

        # Slope L2: componente trasversale della pendenza → file a quote diverse
        _slope_cross_rad = np.radians(p.get('slope_cross_deg', 0.0))
        _tan_slope_cross = np.tan(_slope_cross_rad) if abs(_slope_cross_rad) > 1e-8 else 0.0
        # ── Slope L3 (v4.1.0): sensori sul piano terreno inclinato ───
        # Per slope trasversale all'asse tracker, i sensori vengono
        # posizionati sul piano terreno reale (z = z0 + x * tan(slope_cross))
        # invece che su un piano orizzontale fisso a z=0.05.
        # La normale del raggio resta (0,0,1) per misurare irradianza
        # orizzontale, coerente con la convenzione DLI agronomica.
        # Il ground geometrico Radiance resta orizzontale (groundplane ring):
        # questo è un compromesso che ha effetto trascurabile sulla DLI
        # mediata sulla SAU (il ground influenza solo l'albedo riflessa,
        # non l'ombreggiamento diretto). Per slope > ~15% considerare
        # implementazione L3 completa con ground plane inclinato (v4.2).
        _z0 = 0.05  # quota base sensori (5 cm sopra il terreno locale)

        def _sensor_z(x_local: float) -> float:
            """Quota Z del sensore per la coordinata X locale, dato lo slope L3."""
            return _z0 + float(x_local) * _tan_slope_cross

        linepts_lines = []
        profile_slices = {}

        # Profilo centrale: x = 0 .. pitch
        s0 = 0
        for j in range(n_points):
            x = j * xinc
            linepts_lines.append(f'{x:.6f} 0 {_sensor_z(x):.6f} 0 0 1')
        profile_slices['central'] = (s0, len(linepts_lines))

        # Profili bordo (se N_file > 0)
        strip_width_br = 0.0
        if compute_edge:
            # Pitch edge: k*P .. (k+1)*P per k=1..n_ext-1
            for k in range(1, n_ext):
                s = len(linepts_lines)
                for j in range(n_points):
                    x = k * p['pitch'] + j * xinc
                    linepts_lines.append(f'{x:.6f} 0 {_sensor_z(x):.6f} 0 0 1')
                profile_slices[f'edge_{k}'] = (s, len(linepts_lines))

            # Fascia esterna: n_ext*P .. n_ext*P + strip_width
            strip_width_br = _compute_strip_width_br(solpos, p)
            strip_xinc = strip_width_br / max(n_points - 1, 1)
            s = len(linepts_lines)
            for j in range(n_points):
                x = n_ext * p['pitch'] + j * strip_xinc
                linepts_lines.append(f'{x:.6f} 0 {_sensor_z(x):.6f} 0 0 1')
            profile_slices['outer'] = (s, len(linepts_lines))

            print(f'  Profili bordo: {max(n_ext-1, 0)} edge + 1 outer '
                  f'(strip={strip_width_br:.1f}m)')

        # ── Slope L3: calcolo quota ground per evitare sensori sotto-ground ─
        # Se i sensori inclinati scendono sotto z=-0.01 (default ring),
        # abbassiamo il groundplane sotto il sensore più basso, altrimenti
        # i raggi colpiscono il ground dal basso → irradianza errata.
        if abs(_tan_slope_cross) > 1e-8:
            # Calcola x estremi effettivamente usati (in valore assoluto)
            _x_max_used = (n_ext * p['pitch'] + strip_width_br) if compute_edge \
                          else p['pitch']
            # z_min globale = z al sensore più basso (può essere a x_max o x_min=0)
            _z_at_xmin = _sensor_z(0.0)
            _z_at_xmax = _sensor_z(_x_max_used)
            _z_min_sensors = min(_z_at_xmin, _z_at_xmax)
            # Ground sotto il sensore più basso di 10 cm (margine sicurezza)
            _ground_z = min(-0.01, _z_min_sensors - 0.10)
            print(f'  Slope L3: sensori sul piano terreno '
                  f'(dz/m={_tan_slope_cross:+.4f}, '
                  f'z_sensori in [{_z_min_sensors:.2f}, {max(_z_at_xmin, _z_at_xmax):.2f}]m, '
                  f'ground a z={_ground_z:.2f}m)')
        else:
            _ground_z = -0.01  # default bifacial_radiance

        n_total_points = len(linepts_lines)
        linepts_str = '\n'.join(linepts_lines)
        linepts_bytes = linepts_str.encode()

        # ── Parametri rtrace (da foglio Parametri, celle B48-B50) ────
        br_ab = p.get('br_ab', 2)
        br_ad = p.get('br_ad', 2048)
        br_as = p.get('br_as', 256)
        rtrace_opts = f'-I -ab {br_ab} -aa .1 -ar 256 -ad {br_ad} -as {br_as} -h -oovs'
        print(f'  rtrace: -ab {br_ab} -ad {br_ad} -as {br_as} -oovs')

        from bifacial_radiance.main import _popen

        # ── Pre-genera scene per theta unici ─────────────────────────
        print('  Pre-generazione scene...')
        _devnull = io.StringIO()
        scene_cache = {}
        clearance_cache = {}

        unique_thetas = sorted(set(float(tracker_theta[int(idx)])
                                   for idx in daylight_indices))

        # Slope L2: scena con hub heights per-fila
        _has_slope_scene = abs(_tan_slope_cross) > 1e-8

        for _i_ut, _ut in enumerate(unique_thetas):
            _tilt = abs(_ut)
            _azimuth = 90.0 if _ut >= 0 else 270.0
            _ch = hub_height - 0.5 * p['W'] * np.sin(np.radians(_tilt))
            _ch = max(0.01, _ch)
            clearance_cache[_ut] = _ch
            # radname unico per evitare collisione nomi file
            # (BR usa tilt:0.0f nel filename → theta diversi sovrascrivono)
            _radname = f'sr4_{_i_ut:04d}'

            if _has_slope_scene:
                # L2: genera scena mono-fila (centro), poi replica con dz
                # per-row. Clearance = centro array.
                sceneDict = {
                    'tilt': _tilt, 'pitch': p['pitch'],
                    'clearance_height': _ch,
                    'azimuth': _azimuth,
                    'nMods': 1, 'nRows': 1,
                }
                with contextlib.redirect_stdout(_devnull):
                    _sc = rad.makeScene(module=mod, sceneDict=sceneDict,
                                        radname=_radname)
                _radfiles = rad._getradfiles()
                _scene_rad = [f for f in _radfiles
                              if f.endswith('.rad') and _radname in os.path.basename(f)]
                if _scene_rad:
                    _base_rad = _scene_rad[0]
                    # ── Leggi la scena base (nRows=1) per estrarre i
                    #    comandi !xform originali di BR
                    with open(_base_rad, 'r') as _f:
                        _base_lines = _f.readlines()
                    _xform_cmds = []
                    _other_lines = []
                    for _bl in _base_lines:
                        _bls = _bl.strip()
                        if _bls.startswith('!xform '):
                            _xform_cmds.append(_bls)
                        elif _bls:
                            _other_lines.append(_bls)
                    if _i_ut == 0 and _xform_cmds:
                        print(f'  Base xform: {_xform_cmds[0][:90]}')

                    # ── Wrapper multi-row: componi -t DX 0 DZ DOPO le
                    #    trasformazioni originali (tilt + hub height).
                    #    Ogni riga è un singolo !xform → no nesting.
                    #    xform applica le trasformazioni L→R, quindi
                    #    -t DX 0 DZ in coda = offset applicato per ultimo.
                    _slope_rad = _base_rad.replace('.rad', '_slope.rad')
                    _dz_clamp = _ch - 0.02
                    _n_clamped = 0
                    _out = list(_other_lines)
                    for _ri in range(n_rows):
                        _ro = _ri - _center_row
                        if _ro == 0:
                            _out.extend(_xform_cmds)
                        else:
                            _dx = _ro * p['pitch']
                            _dz = _dx * _tan_slope_cross
                            if _dz < -_dz_clamp:
                                _dz = -_dz_clamp
                                _n_clamped += 1
                            elif _dz > _dz_clamp:
                                _dz = _dz_clamp
                                _n_clamped += 1
                            for _xc in _xform_cmds:
                                # Inserisci -t prima del filename (ultimo token)
                                _parts = _xc.split()
                                _fname = _parts[-1]
                                _opts = _parts[1:-1]
                                _out.append(
                                    '!xform ' + ' '.join(_opts)
                                    + f' -t {_dx:.6f} 0 {_dz:.6f} '
                                    + _fname)
                    if _n_clamped > 0:
                        print(f'    NOTA: {_n_clamped} file con dz clampato '
                              f'(max |dz|={_dz_clamp:.2f}m)')
                    with open(_slope_rad, 'w') as _f:
                        _f.write('\n'.join(_out) + '\n')
                    if _i_ut == 0:
                        print(f'  Slope wrapper: {len(_out)} righe, '
                              f'{n_rows} file')
                    _radfiles = [_slope_rad if f == _base_rad else f
                                 for f in _radfiles]
                _matfiles = list(rad.materialfiles)
                scene_cache[_ut] = (_radfiles, _matfiles)
            else:
                # Nessuna pendenza: scena standard con tutte le file a stessa quota
                sceneDict = {
                    'tilt': _tilt, 'pitch': p['pitch'],
                    'clearance_height': _ch,
                    'azimuth': _azimuth,
                    'nMods': 1, 'nRows': n_rows,
                }
                with contextlib.redirect_stdout(_devnull):
                    _sc = rad.makeScene(module=mod, sceneDict=sceneDict,
                                        radname=_radname)
                _radfiles = rad._getradfiles()
                _matfiles = list(rad.materialfiles)
                scene_cache[_ut] = (_radfiles, _matfiles)

        print(f'  {len(unique_thetas)} scene uniche'
              + (f' (slope L2: dz/row={p["pitch"]*_tan_slope_cross:+.3f}m)'
                 if _has_slope_scene else ''))

        # ── Ground string (albedo) ───────────────────────────────────
        _ground_Rrefl = rad.ground.Rrefl[0]
        _ground_Grefl = rad.ground.Grefl[0]
        _ground_Brefl = rad.ground.Brefl[0]
        _ground_refl = rad.ground.ReflAvg[0]
        _ground_type = rad.ground.ground_type

        _nv = max(_ground_Rrefl, _ground_Grefl, _ground_Brefl)
        if _nv == 0:
            _nv = 1
        # Slope L3: ground a quota dinamica (default -0.01 m, abbassato se
        # sensori inclinati scendono sotto questa quota — vedi calcolo _ground_z)
        _ground_str = (
            f'\nskyfunc glow ground_glow\n0\n0\n4 '
            f'{_ground_Rrefl/_nv} {_ground_Grefl/_nv} {_ground_Brefl/_nv} 0\n'
            '\nground_glow source ground\n0\n0\n4 0 0 -1 180\n'
            f'\nvoid plastic {_ground_type}\n0\n0\n5 '
            f'{_ground_Rrefl:0.3f} {_ground_Grefl:0.3f} {_ground_Brefl:0.3f} 0 0\n'
            f'\n{_ground_type} ring groundplane\n'
            f'0\n0\n8\n0 0 {_ground_z:.4f}\n0 0 1\n0 100'
        )

        _solpos_elev = metdata.solpos['elevation'].values
        _solpos_az = metdata.solpos['azimuth'].values

        skies_dir = os.path.join(temp_work, 'skies')
        os.makedirs(skies_dir, exist_ok=True)

        # ── Prepara task list ────────────────────────────────────────
        print('  Preparazione sky file...')
        task_list = []

        for i, idx in enumerate(daylight_indices):
            idx_int = int(idx)
            theta = float(tracker_theta[idx])

            _dni = float(metdata.dni[idx_int])
            _dhi = float(metdata.dhi[idx_int])
            _sunalt = float(_solpos_elev[idx_int])
            _sunaz = float(_solpos_az[idx_int]) - 180.0
            if _dhi <= 0 or _sunalt <= 0:
                continue

            sky_str = (
                "# sky for gendaylit parallel worker\n"
                f"!gendaylit -ang {_sunalt} {_sunaz}"
                f" -W {_dni} {_dhi} -g {_ground_refl} -O 1 \n"
                "skyfunc glow sky_mat\n0\n0\n4 1 1 1 0\n"
                "\nsky_mat source sky\n0\n0\n4 0 0 1 180\n"
                + _ground_str
            )

            sky_path = os.path.join(skies_dir, f'sky_{i:05d}.rad')
            with open(sky_path, 'w') as f:
                f.write(sky_str)

            radfiles, matfiles = scene_cache[theta]
            # Ordine BR ufficiale: materialfiles + skyfiles + radfiles
            oct_inputs = matfiles + [sky_path] + radfiles

            task_list.append({
                'task_idx': i,
                'hour_idx': idx_int,
                'oct_inputs': oct_inputs,
                'sky_path': sky_path,
            })

        n_tasks = len(task_list)
        print(f'  {n_tasks} ore da simulare')

        # ── Worker function ──────────────────────────────────────────
        def _worker(task):
            """Esegue oconv + rtrace per una singola ora."""
            oct_path = task['sky_path'].replace('.rad', '.oct')

            # oconv (metodo BR ufficiale: _popen con lista, no shell)
            oconv_cmd = ['oconv'] + task['oct_inputs']
            try:
                with open(oct_path, 'w') as f_oct:
                    _popen(oconv_cmd, None, f_oct)
            except Exception:
                return task['task_idx'], task['hour_idx'], None
            if not os.path.exists(oct_path):
                return task['task_idx'], task['hour_idx'], None

            # rtrace
            rtrace_cmd = f'rtrace {rtrace_opts} "{oct_path}"'
            result = _subprocess.run(rtrace_cmd, shell=True,
                                     input=linepts_bytes,
                                     capture_output=True, timeout=60)
            if result.returncode != 0:
                return task['task_idx'], task['hour_idx'], None

            # Parse output (-oovs: tab-separated, cols 3-5 = value RGB)
            lines = result.stdout.decode().strip().split('\n')
            vals = []
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 6:
                    r, g, b = float(parts[3]), float(parts[4]), float(parts[5])
                    irr = (r + g + b) / 3.0  # W/m² (matches BR convention)
                    vals.append(irr)
            if len(vals) != n_total_points:
                return task['task_idx'], task['hour_idx'], None

            # Cleanup oct
            try:
                os.remove(oct_path)
            except Exception:
                pass

            return task['task_idx'], task['hour_idx'], np.array(vals)

        # ── Esecuzione parallela ─────────────────────────────────────
        # Usa fino all'80% dei core disponibili (max 28)
        n_cpu = multiprocessing.cpu_count()
        n_workers = max(2, min(int(n_cpu * 0.8), 28))
        print(f'  Workers: {n_workers} (CPU: {n_cpu})')

        t_start = _time.time()

        # Risultati: lista di (hour_idx, irr_array) per le ore ok
        results_list = []
        n_ok = 0
        n_err = 0

        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = {executor.submit(_worker, t): t for t in task_list}
            for future in as_completed(futures):
                task_idx, hour_idx, vals = future.result()
                if vals is not None:
                    results_list.append((hour_idx, vals))
                    n_ok += 1
                else:
                    n_err += 1

                n_done = n_ok + n_err
                if n_done % 200 == 0 or n_done == n_tasks:
                    elapsed = _time.time() - t_start
                    rate = n_done / elapsed if elapsed > 0 else 1
                    eta = (n_tasks - n_done) / rate if rate > 0 else 0
                    print(f'    [{n_done}/{n_tasks} {n_done/n_tasks*100:.0f}%] '
                          f'{n_ok} ok, {n_err} err | '
                          f'{elapsed/60:.1f}min, ETA {eta/60:.1f}min')

        total_time = _time.time() - t_start
        print(f'\n  Completato in {total_time/60:.1f} minuti')
        print(f'  Ore simulate: {n_ok}/{n_tasks} ({n_err} errori)')

        # ── Diagnostica errori rtrace (v4.1.0) ───────────────────────
        # Warning se gli errori superano l'1% delle ore diurne — soglia
        # tipica al di sopra della quale il run andrebbe verificato.
        if n_tasks > 0:
            err_pct = 100.0 * n_err / n_tasks
            if err_pct > 1.0:
                print(f'  WARNING: {err_pct:.2f}% delle ore in errore rtrace.')
                print(f'           Cause possibili: sole basso al crepuscolo,')
                print(f'           race condition file scena, sky descriptor degenere,')
                print(f'           timeout subprocess. Verificare i log se la')
                print(f'           percentuale aumenta nei run successivi.')
            elif n_err > 0:
                print(f'  RTrace: {err_pct:.2f}% errori ({n_err} ore) — accettabile')

        # ── Ordina risultati per indice orario ───────────────────────
        results_list.sort(key=lambda x: x[0])

        ok_indices = np.array([r[0] for r in results_list])
        results_full = np.array([r[1] for r in results_list])  # (n_ok, n_total_points)

        # ── Separa profili dal batch ─────────────────────────────────
        s, e = profile_slices['central']
        IRR_hourly = results_full[:, s:e]  # (n_ok, n_points) — profilo centrale
        IRR_daily_cum = IRR_hourly.sum(axis=0) if len(IRR_hourly) > 0 else np.zeros(n_points)

        edge_irr = {}
        if compute_edge and len(results_full) > 0:
            for name, (s, e) in profile_slices.items():
                if name != 'central':
                    edge_irr[name] = results_full[:, s:e]
            print(f'  Profili estratti: {list(edge_irr.keys())}')

        x_pts = np.linspace(0, p['pitch'], n_points)

        # ── Simulazione cielo aperto (riferimento, no pannelli) ──
        print('\n  Simulazione cielo aperto (riferimento, no pannelli)...')
        t_os_start = _time.time()

        # Singolo punto sensore (cielo aperto = uguale ovunque).
        # Posizionato sul piano terreno reale (slope L3) per coerenza con
        # i sensori del flusso principale, anche se fisicamente irrilevante:
        # in cielo aperto l'irradianza orizzontale non dipende dalla posizione.
        _os_x = 5.0
        _os_z = _sensor_z(_os_x)
        opensky_linepts = f'{_os_x:.6f} 0 {_os_z:.6f} 0 0 1'.encode()

        def _worker_opensky(task):
            """rtrace con solo sky+ground (no scene geometry)."""
            sky_path = task['sky_path']
            oct_path = sky_path.replace('.rad', '_os.oct')
            try:
                with open(oct_path, 'w') as f_oct:
                    _popen(['oconv', sky_path], None, f_oct)
            except Exception:
                return task['hour_idx'], None
            if not os.path.exists(oct_path):
                return task['hour_idx'], None
            rtrace_cmd = f'rtrace {rtrace_opts} "{oct_path}"'
            res = _subprocess.run(rtrace_cmd, shell=True,
                                   input=opensky_linepts,
                                   capture_output=True, timeout=30)
            try:
                os.remove(oct_path)
            except Exception:
                pass
            if res.returncode != 0:
                return task['hour_idx'], None
            parts = res.stdout.decode().strip().split('\t')
            if len(parts) >= 6:
                r, g, b = float(parts[3]), float(parts[4]), float(parts[5])
                irr = (r + g + b) / 3.0  # W/m² (matches BR convention)
                return task['hour_idx'], irr
            return task['hour_idx'], None

        IRR_opensky = np.zeros(len(ghi_arr))
        n_os_ok = 0

        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = {executor.submit(_worker_opensky, t): t for t in task_list}
            for future in as_completed(futures):
                hour_idx, val = future.result()
                if val is not None:
                    IRR_opensky[hour_idx] = val
                    n_os_ok += 1

        t_os = _time.time() - t_os_start
        print(f'  Cielo aperto: {n_os_ok}/{len(task_list)} ore in {t_os:.0f}s')
        os_mean = IRR_opensky[IRR_opensky > 0].mean() if n_os_ok > 0 else 0
        ghi_mean = ghi_arr[ghi_arr > 20].mean()
        print(f'  IRR open-sky medio: {os_mean:.1f} W/m²  '
              f'(GHI medio diurno: {ghi_mean:.1f} W/m²)')

        # Timestamps corrispondenti
        daylight_timestamps = pd.DatetimeIndex([metdata.datetime[int(i)] for i in ok_indices])

        return {
            'IRR_hourly': IRR_hourly,           # (n_ok, n_points) W/m²
            'IRR_daily_cum': IRR_daily_cum,      # (n_points,) Wh/m²
            'daylight_indices': ok_indices,       # (n_ok,) indici 0..8759
            'daylight_timestamps': daylight_timestamps,
            'metdata': metdata,
            'x_pts': x_pts,
            'n_hours_ok': n_ok,
            'n_hours_err': n_err,
            'ghi_annual': ghi_annual,
            'tracker_theta': tracker_theta,
            'ghi_arr': ghi_arr,
            'IRR_opensky': IRR_opensky,          # (n_all,) W/m² cielo aperto
            'edge_irr': edge_irr if compute_edge else None,
            'strip_width_br': strip_width_br,
            'n_ext_scene': n_ext,                # n_ext effettivo della scena BR
        }

    finally:
        try:
            shutil.rmtree(temp_work)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════
# SIMULAZIONE SINGOLO GIORNO
# ══════════════════════════════════════════════════════════════════════════

def run_singleday(p, epw_path, target_month, target_day, n_points=51):
    """
    Wrappa run_annual con sample_days = singolo giorno.
    """
    sample_days = {(target_month, target_day)}
    return run_annual(p, epw_path, n_points=n_points, sample_days=sample_days)
