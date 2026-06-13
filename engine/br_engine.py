"""
br_engine.py  |  SolRatio v4.3.0
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
from pathlib import Path as _Path

import numpy as np
import pandas as pd

# Cache scene .oct persistente (item 4 di v4.2). Import opzionale —
# l'assenza del modulo non rompe il motore (fallback no-cache).
try:
    from . import _scene_cache as _SR_CACHE
except (ImportError, ValueError):
    try:
        import _scene_cache as _SR_CACHE  # esecuzione come script standalone
    except ImportError:
        _SR_CACHE = None

warnings.filterwarnings('ignore')

def _read_version():
    _vp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'VERSION')
    try:
        with open(_vp, encoding='utf-8') as _f:
            return _f.read().strip()
    except FileNotFoundError:
        return '0.0.0'

__version__ = _read_version()


# ══════════════════════════════════════════════════════════════════════════
# Trasmittanza pannello (tau) — materiale Radiance 'trans'
# ══════════════════════════════════════════════════════════════════════════

def _tau_trans_params(tau, tau_diff=0.0, spec=0.05, Rd=0.0):
    """
    Inversione canonica della mappatura `tau → materiale Radiance trans`.

    Funzione PURA (nessun I/O): isolata da _apply_tau_material per essere
    verificabile analiticamente in self_test_tau() senza ray-tracing.

    Restituisce i 5 parametri distinti del materiale `trans`
    (C, spec, rough, A7, A8). Per la semantica del tipo (refman/m_normal.c):
        trasmissione totale    = C·(1−spec)·A7
        trasmissione speculare = (trasm. totale)·A8
        riflessione diffusa    = C·(1−spec)·(1−A7)
    Con Rd=0 (il non-trasmesso non-speculare è assorbito dalle celle) si
    ottiene trasmissione totale = tau+tau_diff (esatta finché ≤ 1−spec) e
    quota speculare = tau.
    """
    tau = float(tau)
    tau_diff = float(tau_diff)
    tau_total = tau + tau_diff
    rgb_diff = min(1.0, (tau_total + Rd) / (1.0 - spec))   # C (colore)
    trans_param = (tau_total / (tau_total + Rd)) if (tau_total + Rd) > 1e-9 \
        else 0.0                                           # A7: frazione trasmessa
    tspec = (tau / tau_total) if tau_total > 1e-9 else 1.0  # A8: quota speculare
    rough = 0.0                                            # superficie liscia
    return rgb_diff, spec, rough, trans_param, tspec


def self_test_tau(verbose=True):
    """
    Self-test ANALITICO della mappatura materiale `trans` (nessun Radiance).

    Verifica che _tau_trans_params produca parametri tali che, per la semantica
    del tipo `trans`, la trasmissione effettiva = tau+tau_diff e la quota
    speculare = tau. Avrebbe intercettato il bug storico (C = 1−tau_tot−spec →
    un pannello tau_tot=0.9 trasmetteva ~4% invece di 90%). Pura → adatta alla
    CI senza i binari Radiance.
    """
    ok = True
    # Casi FISICI (tau_total ≤ 1−spec = 0.95): trasmissione e speculare esatte.
    physical = [(0.3, 0.0), (0.7, 0.0), (0.7, 0.2), (0.1, 0.05), (0.5, 0.4)]
    for tau, tau_diff in physical:
        tau_total = tau + tau_diff
        C, sp, rough, A7, A8 = _tau_trans_params(tau, tau_diff)
        eff_trans = C * (1.0 - sp) * A7            # trasmissione totale
        eff_spec = eff_trans * A8                  # trasmissione speculare
        eff_drefl = C * (1.0 - sp) * (1.0 - A7)    # riflessione diffusa pannello
        if (abs(eff_trans - tau_total) > 1e-6 or abs(eff_spec - tau) > 1e-6
                or abs(eff_drefl) > 1e-6):
            ok = False
            if verbose:
                print(f'  [FAIL] trans tau={tau} tau_diff={tau_diff}: '
                      f'trasm.tot={eff_trans:.6f} (atteso {tau_total:.6f}), '
                      f'spec={eff_spec:.6f} (atteso {tau:.6f}), '
                      f'drefl={eff_drefl:.6f} (atteso 0)')
    # Caso LIMITE non fisico (tau_total > 0.95): trasmissione cappata a 1−spec,
    # nessuna riflessione diffusa spuria.
    C, sp, rough, A7, A8 = _tau_trans_params(0.7, 0.3)   # tau_total = 1.0
    eff_trans = C * (1.0 - sp) * A7
    eff_drefl = C * (1.0 - sp) * (1.0 - A7)
    if abs(eff_trans - (1.0 - sp)) > 1e-6 or abs(eff_drefl) > 1e-6:
        ok = False
        if verbose:
            print(f'  [FAIL] trans clamp tau_total=1.0: trasm={eff_trans:.6f} '
                  f'(atteso {1.0 - sp:.6f}), drefl={eff_drefl:.6f}')
    if verbose:
        print(f'   Self-test materiale trans: {"PASS" if ok else "FAIL"} '
              f'(6 casi — trasm.tot=tau+tau_diff, spec=tau, drefl=0, +clamp)')
    return ok


def _apply_tau_material(rad, tau, module_name='sr_module', tau_diff=0.0):
    """
    Trasforma il modulo Radiance in semitrasparente usando il materiale 'trans'.

    Override del materiale opaco di default di bifacial_radiance (`Metal_Grey`
    o `black`) con un materiale Radiance `trans` calibrato sulla trasmittanza
    pannello.

    BRTDfunc scope α (v4.2 item 9):
    - `tau` = trasmittanza speculare (raggio passa dritto, comportamento vetro)
    - `tau_diff` = trasmittanza diffusa addizionale (luce sparsa Lambert)
    - Trasmittanza totale = tau + tau_diff (deve essere <= 1)

    Mappatura sul materiale Radiance `trans` (INVERSIONE CANONICA, fix
    2026-06-12 — la mappatura storica metteva il residuo 1−τ_tot−spec nel
    COLORE, che in Radiance moltiplica la trasmissione: un pannello
    τ_tot=0.9 trasmetteva ~4%; vedi commento al punto 4):
        C (R G B) = (tau+tau_diff+Rd) / (1−spec)   colore
        A7 trans  = (tau+tau_diff) / (tau+tau_diff+Rd)
        A8 tspec  = tau / (tau+tau_diff)           frazione speculare
        spec      = 0.05;  Rd = 0 (non-trasmesso → assorbito dalle celle)
    → trasmissione effettiva C·(1−spec)·A7 = tau+tau_diff ESATTA.

    ⚠ I risultati con tau>0 calcolati PRIMA del fix (incluse le sentinelle
    tau/tau_diff 60.2 misurate fino al collaudo del 2026-06-12) sono col
    materiale ~opaco e vanno ricalcolati.

    Parametri
    ---------
    rad : bifacial_radiance.RadianceObj
        Oggetto Radiance già inizializzato.
    tau : float
        Trasmittanza pannello speculare, 0 (opaco) ≤ tau ≤ 1.
    module_name : str
        Nome modulo passato a makeModule (default 'sr_module').
    tau_diff : float, default 0.0
        Trasmittanza pannello diffusa addizionale, 0 ≤ tau_diff ≤ (1-tau).
        Per pannelli organici/thin-film con trasmissione diffusa significativa.

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
    # Valida tau e tau_diff (BRTDfunc scope α)
    tau = float(tau)
    tau_diff = float(tau_diff)
    if tau < 0 or tau_diff < 0:
        raise ValueError(f"tau e tau_diff devono essere >= 0, "
                         f"ricevuti tau={tau}, tau_diff={tau_diff}")
    tau_total = tau + tau_diff
    if tau_total <= 0:
        return  # opaco: nessuna modifica
    if tau_total > 1:
        raise ValueError(
            f"tau + tau_diff = {tau_total} > 1 (impossibile fisicamente). "
            f"Riducre i valori in input."
        )

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

    # 4. Calcola parametri materiale trans — INVERSIONE CANONICA Radiance
    # (fix 2026-06-12, trovato dalla matrice varianti post-correzione R1).
    # Semantica del tipo `trans` (refman/m_normal.c):
    #   rifl. speculare    = spec                       (acromatica)
    #   rifl. diffusa      = C·(1−spec)·(1−A7)
    #   trasm. totale      = C·(1−spec)·A7
    #   trasm. speculare   = trasm.tot·A8
    # dove C = colore RGB e A7/A8 = parametri 6/7. La mappatura storica
    # scriveva C = 1−τ_tot−spec ("diffusione+assorbimento") e A7 = τ_tot:
    # ma C MOLTIPLICA la trasmissione → con τ_tot=0.9 il pannello
    # trasmetteva C·(1−spec)·A7 ≈ 4% invece di 90% (misurato: K_day BRTD
    # identico all'opaco; il riferimento BR-trans della validazione
    # condivideva la stessa mappatura → la consistenza SR≈BR non poteva
    # rilevarlo). Inversione corretta, con Rd = riflettanza diffusa del
    # pannello (scelta: 0 — il non-trasmesso non-speculare è ASSORBITO
    # dalle celle; assorbimento = 1−spec−τ_tot):
    #   C  = (Ts + Td + Rd) / (1 − spec)
    #   A7 = (Ts + Td) / (Ts + Td + Rd)
    #   A8 = Ts / (Ts + Td)
    # Inversione canonica → 5 parametri del materiale (funzione pura
    # _tau_trans_params, verificata in self_test_tau senza ray-tracing).
    rgb_diff, spec, rough, trans_param, tspec = _tau_trans_params(tau, tau_diff)

    # 5. Crea file materiale custom
    if not os.path.isdir(materials_dir):
        os.makedirs(materials_dir, exist_ok=True)
    mat_file = os.path.join(materials_dir, f'{NEW_MATERIAL}.rad')
    # encoding='utf-8' esplicito per evitare UnicodeEncodeError su Windows
    # con cp1252 default. Solo ASCII nei commenti per safety con parser
    # Radiance (oconv); 'alpha' invece di 'α' (greca) che non è in cp1252.
    with open(mat_file, 'w', encoding='utf-8') as f:
        f.write(
            f'# SolRatio v{__version__} -- Materiale pannello semitrasparente (BRTDfunc alpha)\n'
            f'# Trasmittanza speculare tau = {tau:.3f}\n'
            f'# Trasmittanza diffusa  tau_diff = {tau_diff:.3f}\n'
            f'# Trasmittanza totale  tau_total = {tau_total:.3f}\n'
            f'# Mappatura trans (inversione canonica): C={rgb_diff:.3f}, '
            f'A7={trans_param:.3f}, A8={tspec:.3f}\n'
            f'# Bilancio: rifl_spec {spec:.3f} + trasm {tau_total:.3f} '
            f'+ assorbito {max(0.0, 1.0 - spec - tau_total):.3f} = 1\n'
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
        if tau_diff > 0:
            print(f'  TAU: pannello semitrasparente BRTDfunc alpha  '
                  f'(tau_spec={tau:.2f}, tau_diff={tau_diff:.2f}, '
                  f'tau_total={tau_total:.2f})')
        else:
            print(f'  TAU: pannello semitrasparente attivato  '
                  f'(tau={tau:.2f}, materiale Radiance trans)')


# ══════════════════════════════════════════════════════════════════════════
# Layout cartella progetto (v4.2 item 5)
# ══════════════════════════════════════════════════════════════════════════

def find_pvgis_csv(project_dir, lat=None, lon=None):
    """
    Cerca un file PVGIS CSV nella cartella del progetto.

    Supporta sia il layout v4.1.x ("piatto" — file nella root del
    progetto) sia il layout v4.2 standardizzato (file in `<progetto>/input/`).

    Ordine di ricerca:
      1. <project_dir>/PVGIS_*.csv     (layout legacy)
      2. <project_dir>/input/PVGIS_*.csv  (layout v4.2)

    Se `lat` e `lon` sono forniti (in gradi decimali; nel nome file sono
    formattati a 4 decimali, es. `45.3000`), si filtrano i nomi che
    combaciano con `PVGIS_<lat>_<lon>_*.csv`.
    Altrimenti si restituisce il primo CSV PVGIS trovato.

    Returns
    -------
    pathlib.Path | None
        Path al primo file PVGIS CSV trovato, oppure None se nessuno.
    """
    project_dir = _Path(project_dir)
    candidates = [project_dir, project_dir / 'input']

    # M4 (v4.2.2): con lat/lon noti si accetta SOLO il match esatto
    # (su tutte le directory); il fallback generico restituiva il CSV di
    # un ALTRO sito dopo un cambio di coordinate (errore silenzioso) e
    # impediva il download automatico del file corretto.
    if lat is not None and lon is not None:
        pattern = f'PVGIS_{float(lat):.4f}_{float(lon):.4f}_*.csv'
        for d in candidates:
            if d.is_dir():
                matches = sorted(d.glob(pattern))
                if matches:
                    return matches[0]
        return None
    for d in candidates:
        if d.is_dir():
            matches = sorted(d.glob('PVGIS_*.csv'))
            if matches:
                return matches[0]
    return None


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
    ghi_monthly = df.groupby(['year', 'month'])['ghi'].sum().unstack()
    # B2 (v4.3.0): i (anno, mese) con copertura oraria INCOMPLETA (serie
    # troncate/anomale) diventano NaN ed escono da mediana e selezione.
    # Con lo storico fill_value=0 un mese mancante pesava 0 sulla mediana
    # (spostandola in basso) e l'anno parziale poteva essere eletto "anno
    # tipo" in silenzio; il guard 8760 a valle intercettava solo il caso
    # del mese fisicamente corto, non la mediana corrotta.
    hours_monthly = df.groupby(['year', 'month'])['ghi'].count().unstack()
    for _y in ghi_monthly.index:
        for _m in ghi_monthly.columns:
            _exp = calendar.monthrange(int(_y), int(_m))[1] * 24
            _cnt = hours_monthly.loc[_y, _m]
            if pd.isna(_cnt) or _cnt < _exp:
                ghi_monthly.loc[_y, _m] = np.nan
    years = sorted(df['year'].unique())

    tmy_months = []  # lista di (month, selected_year, DataFrame)
    tmy_years = {}
    ref_year = years[len(years) // 2]  # anno di riferimento per i timestamp

    print('  TMY mese-per-mese:')
    for m in range(1, 13):
        if m not in ghi_monthly.columns:
            continue
        col = ghi_monthly[m].dropna()
        if col.empty:
            raise RuntimeError(
                f'TMY: nessun anno con il mese {calendar.month_abbr[m]} '
                f'completo nella serie PVGIS — verificare il CSV.')
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
        # R2 (v4.2.2): rimuove il 29/02 PRIMA della rinormalizzazione:
        # replace(year=non_bisestile) su un 29/02 solleva ValueError
        # (crash riprodotto con dati reali 2018-2020, dossier R2).
        df_m = df_m[~((df_m['time'].dt.month == 2) &
                      (df_m['time'].dt.day == 29))]
        # Riscrive i timestamp con l'anno di riferimento
        df_m['time'] = df_m['time'].apply(
            lambda t: t.replace(year=ref_year))
        frames.append(df_m)
    df_tmy = pd.concat(frames, ignore_index=True)
    df_tmy = df_tmy.sort_values('time').reset_index(drop=True)

    n_hours = len(df_tmy)
    if n_hours != 8760:
        # R2 (v4.2.2): col filtro 29/02 a monte il TMY e' sempre 8760 ore;
        # un conteggio diverso = serie PVGIS incompleta -> errore esplicito
        # (prima: solo AVVISO e EPW corto con effetti non controllati).
        raise RuntimeError(
            f'TMY assemblato con {n_hours} ore (attese 8760): la serie '
            f'PVGIS ha mesi incompleti o anomali — verificare il CSV.')

    ghi_tmy = df_tmy['ghi'].sum()
    tmy_info = ', '.join(f'{calendar.month_abbr[m]}={y}'
                         for m, y in sorted(tmy_years.items()))
    print(f'  GHI TMY composito: {ghi_tmy:.0f} Wh/m²')

    # TZ dell'header LOCATION = 0 (fix F1, backport dalla revisione 2026-06-10):
    # i CSV PVGIS sono in UTC (timestamp HH:10) e il writer NON ri-localizza i
    # timestamp, quindi l'header deve dichiarare UTC. Il vecchio `round(lon/15)`
    # (=+1 per l'Italia) faceva interpretare a bifacial_radiance i timestamp
    # come ora locale -> posizione solare ~40 min in anticipo rispetto alle
    # irradianze (asimmetria mattina/sera). Con TZ=0 e label='right' (default
    # EPW) il solpos e' calcolato a timestamp-30min, coerente col dato orario
    # UTC right-labeled. Sposta i numeri pubblicati: prima/dopo nel CHANGELOG.
    tz_offset = 0
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

    # v4.3.0: NaN gestiti esplicitamente — `nan or default` restituisce
    # nan (truthy) e finiva come testo 'nan' nell'EPW; max(0, nan) -> 0
    # silenzioso per le irradianze.
    def _num(value, default):
        v = float(value if value is not None else default)
        return default if pd.isna(v) else v

    data_lines = []
    for i in range(len(df_tmy)):
        row = df_tmy.iloc[i]
        ts = row['time'] if isinstance(row['time'], pd.Timestamp) else pd.Timestamp(row['time'])
        hour = ts.hour + 1
        if hour == 0:
            hour = 24
        ghi_val = max(0, _num(row.get('ghi', 0), 0))
        dni_val = max(0, _num(row.get('dni', 0), 0))
        dhi_val = max(0, _num(row.get('dhi', 0), 0))
        temp = _num(row.get('temp_air', 15), 15)
        ws = max(0, _num(row.get('wind_speed', 2), 2))
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


def run_annual(p, epw_path, n_points=51, sample_days=None,
               use_scene_cache=True, project_dir=None):
    """
    Simulazione annuale bifacial_radiance con gendaylit ora-per-ora.

    Parametri:
      p: dict parametri (lat, lon, pitch, W, H, H_min_terra, beta_max,
         GCR, axis_azimuth, backtracking, albedo)
      epw_path: percorso file EPW
      n_points: punti campionamento al suolo (default 51)
      sample_days: set di (month, day) per filtrare giorni, None = tutti
      use_scene_cache: True (default) abilita la cache persistente delle
         scene Radiance pre-compilate (.oct senza cielo). Speedup atteso
         30-60% sul tempo per ora dopo il primo run sullo stesso progetto
         con stessa geometria. Fail-safe: in caso di errore della cache
         si applica il flusso legacy (full oconv per ora). v4.2.0+.
      project_dir: cartella radice del progetto in cui creare `.cache/scenes/`.
         Default None → derivata da `Path(epw_path).parent`.

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

    print(f'  === SolRatio v{__version__} — Motore bifacial_radiance ===')

    # ── Cache scene .oct persistente (v4.2 item 4) ───────────────────
    # Pre-compila il .oct di scena (matfiles+radfiles, senza cielo) una
    # sola volta per progetto+geometria. Per ogni ora, oconv -i scene.oct
    # sky.rad linka incrementalmente → speedup 30-60% atteso.
    _cache_dir = None
    if use_scene_cache and _SR_CACHE is not None:
        try:
            _proj_dir = _Path(project_dir) if project_dir else _Path(epw_path).parent
            _cache_dir = _SR_CACHE.get_cache_dir(_proj_dir)
            _stats = _SR_CACHE.stats(_cache_dir)
            print(f'  Cache scene: {_stats.get("n_scenes", 0)} hit-set in '
                  f'{_cache_dir} ({_stats.get("total_size_mb", 0):.1f}MB)')
        except Exception as _exc:
            print(f'  Cache scene: disabilitata ({_exc})')
            _cache_dir = None

    # ── Work dir senza spazi ─────────────────────────────────────────
    temp_work = tempfile.mkdtemp(prefix='sr_v4_')
    print(f'  Work dir: {temp_work}')
    try:
        _cwd_orig = os.getcwd()  # RadianceObj fa chdir in temp_work (vedi finally)
    except OSError:
        # un chiamante precedente (altro run nello stesso processo) ha
        # lasciato la CWD su una directory cancellata: riparti da tmp
        _cwd_orig = tempfile.gettempdir()
        os.chdir(_cwd_orig)

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
            # v4.3.0: ricalcola n_ext dopo il forcing (con br_n_rows=1/2
            # restava 0 e la fascia "outer" partiva da v=0, DENTRO il campo)
            n_ext = (n_rows - 1) // 2
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
                  f'+2-10% rispetto al limite "campo grande" (misure v4.3.0 in '
                  f'PARAMETRI_RADIANCE.md). Raccomandato: n_ext >= 3 '
                  f'(n_rows >= 7) per uso routine, n_ext >= 5 (n_rows >= 11) '
                  f'per benchmark/pubblicazione.')
        _center_row = n_rows // 2
        mod = rad.makeModule(name='sr_module', x=module_length,
                             y=p['W'], glass=False)

        # ── Trasmittanza pannello (v4.1.0 + BRTDfunc α v4.2 item 9) ────
        # Se tau > 0 (e/o tau_diff > 0), sostituisce il materiale opaco
        # di default con un materiale Radiance 'trans' calibrato.
        # tau_diff (default 0) abilita la componente diffusa di
        # trasmissione per pannelli organici/thin-film.
        _tau = float(p.get('tau', 0.0))
        _tau_diff = float(p.get('tau_diff', 0.0))
        if _tau > 0 or _tau_diff > 0:
            _apply_tau_material(rad, _tau, module_name='sr_module',
                                tau_diff=_tau_diff)

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
        # posizionati sul piano terreno reale (z = z0 + v_local * tan(slope_cross))
        # invece che su un piano orizzontale fisso a z=0.05.
        # La normale del raggio resta (0,0,1) per misurare irradianza
        # orizzontale, coerente con la convenzione DLI agronomica.
        # Il ground geometrico Radiance resta orizzontale (groundplane ring):
        # questo è un compromesso che ha effetto trascurabile sulla DLI
        # mediata sulla SAU (il ground influenza solo l'albedo riflessa,
        # non l'ombreggiamento diretto). Per slope > ~15% considerare
        # implementazione L3 completa con ground plane inclinato (v4.2).
        _z0 = 0.05  # quota base sensori (5 cm sopra il terreno locale)

        def _sensor_z(v_local: float) -> float:
            """Quota Z del sensore per la coordinata locale v (perpendicolare al
            tracker), dato lo slope L3 cross-tracker."""
            return _z0 + float(v_local) * _tan_slope_cross

        # ── Frame coordinate locale (v4.2 item 7) ─────────────────────
        # Sensori posizionati in coordinate locali (u, v, w) ancorate al
        # tracker: u = lungo asse tracker, v = perpendicolare (pitch),
        # w = verticale. Trasformazione a coordinate mondo via rotazione
        # phi = axis_azimuth - 180°. Per axis_azimuth=180° (N-S, default
        # storico), phi=0 → coordinate identiche al precedente layout
        # (sensori lungo world X). Per axis_azimuth diverso, il frame
        # ruota con il tracker.
        import math as _math
        _axis_azimuth = float(p.get('axis_azimuth', 180.0))
        _phi = _math.radians(_axis_azimuth - 180.0)
        _cos_phi = _math.cos(_phi)
        _sin_phi = _math.sin(_phi)

        def _local_to_world(v_local: float):
            """Trasforma coordinata locale v (perpendicolare al tracker) in
            coordinate mondo (x, y). Per axis_azimuth=180° è identità
            (x=v, y=0)."""
            return (v_local * _cos_phi, -v_local * _sin_phi)

        # v4.2: replica multi-fila slope L2 ora axis_azimuth-aware
        # (vedi _local_to_world applicato a _dx nel wrapper sotto).
        # Per axis=180 il comportamento e' bit-per-bit identico a v4.1.

        linepts_lines = []
        profile_slices = {}

        # Profilo centrale: v = 0 .. pitch (locale, perpendicolare al tracker)
        s0 = 0
        for j in range(n_points):
            v = j * xinc
            x_w, y_w = _local_to_world(v)
            linepts_lines.append(f'{x_w:.6f} {y_w:.6f} {_sensor_z(v):.6f} 0 0 1')
        profile_slices['central'] = (s0, len(linepts_lines))

        # Profili bordo (se N_file > 0)
        strip_width_br = 0.0
        if compute_edge:
            # Pitch edge: k*P .. (k+1)*P per k=1..n_ext-1 (in coord. locale v)
            for k in range(1, n_ext):
                s = len(linepts_lines)
                for j in range(n_points):
                    v = k * p['pitch'] + j * xinc
                    x_w, y_w = _local_to_world(v)
                    linepts_lines.append(f'{x_w:.6f} {y_w:.6f} {_sensor_z(v):.6f} 0 0 1')
                profile_slices[f'edge_{k}'] = (s, len(linepts_lines))

            # Fascia esterna: v = n_ext*P .. n_ext*P + strip_width
            strip_width_br = _compute_strip_width_br(solpos, p)
            strip_xinc = strip_width_br / max(n_points - 1, 1)
            s = len(linepts_lines)
            for j in range(n_points):
                v = n_ext * p['pitch'] + j * strip_xinc
                x_w, y_w = _local_to_world(v)
                linepts_lines.append(f'{x_w:.6f} {y_w:.6f} {_sensor_z(v):.6f} 0 0 1')
            profile_slices['outer'] = (s, len(linepts_lines))

            print(f'  Profili bordo: {max(n_ext-1, 0)} edge + 1 outer '
                  f'(strip={strip_width_br:.1f}m)')

        # -- Slope L3 v4.2: groundplane realmente inclinato (Rodrigues) --
        # Per slope_cross != 0 il groundplane e' un ring inclinato con
        # normale ruotata di slope_cross_rad attorno all'asse del tracker
        # (formula di Rodrigues). Centro a (0,0,0): il piano passa per
        # l'origine. I sensori a z = z0 + v*tan(slope_cross) sono per
        # costruzione 5 cm sopra il piano inclinato in ogni posizione.
        # Per slope_cross == 0 manteniamo il ring orizzontale a z=-0.01
        # (bit-per-bit identico a v4.1).
        if abs(_tan_slope_cross) > 1e-8:
            # Normale piano inclinato (Rodrigues, asse rotazione = asse tracker).
            # I sensori giacciono su z = tan(sl)·(x·cosφ − y·sinφ): la normale
            # del piano è ∝ (−sin_sl·cosφ, +sin_sl·sinφ, cos_sl). Il segno Y
            # era invertito (−sinφ): nullo per asse N-S (sinφ=0), ring
            # speculare a sensori/file per axis_azimuth ruotati (es. E-W).
            _sin_sl = np.sin(_slope_cross_rad)
            _cos_sl = np.cos(_slope_cross_rad)
            _gn_x = -_cos_phi * _sin_sl
            _gn_y = _sin_phi * _sin_sl
            _gn_z = _cos_sl
            _gc_x, _gc_y, _gc_z = 0.0, 0.0, 0.0  # ring passante per origine
            # Range quota sensori (info diagnostica)
            _x_max_used = (n_ext * p['pitch'] + strip_width_br) if compute_edge \
                          else p['pitch']
            _z_at_xmin = _sensor_z(0.0)
            _z_at_xmax = _sensor_z(_x_max_used)
            _z_min_sensors = min(_z_at_xmin, _z_at_xmax)
            _z_max_sensors = max(_z_at_xmin, _z_at_xmax)
            print(f'  Slope L3: groundplane inclinato '
                  f'(dz/m={_tan_slope_cross:+.4f}, '
                  f'normale=({_gn_x:+.3f},{_gn_y:+.3f},{_gn_z:+.3f}), '
                  f'z_sensori in [{_z_min_sensors:.2f}, {_z_max_sensors:.2f}]m)')
            _ground_z = 0.0  # solo per legacy reference (non usato dal ring inclinato)
        else:
            _gn_x, _gn_y, _gn_z = 0.0, 0.0, 1.0
            _gc_x, _gc_y, _gc_z = 0.0, 0.0, -0.01
            _ground_z = -0.01  # bit-per-bit v4.1 per slope=0

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
            # R1 (v4.3.0): convenzione pvlib in forma CANONICA bifacial_radiance
            # (la normalizzazione di makeScene1axis): azimuth COSTANTE =
            # axis-90 e tilt FIRMATO = -theta. Fisica identica a
            # (axis+90, +tilt) per theta>=0, ma la scena NON si ribalta fra
            # mattina e pomeriggio: file e sensori restano nello stesso frame
            # del riferimento canonico set1axis in ogni ora (con nRows pari
            # il ribaltamento spostava il contesto di bordo del gap
            # campionato alle ore radenti). theta>0 = faccia a OVEST (pvlib);
            # la formula storica v4.1.0-v4.2.2 era CONTRO-RUOTATA rispetto
            # al sole: provato sperimentalmente (larghezza ombra misurata vs
            # analitica pvlib + riferimento canonico set1axis, dossier R1).
            _tilt = -_ut
            _azimuth = (_axis_azimuth - 90.0) % 360.0
            _ch = hub_height - 0.5 * p['W'] * np.sin(np.radians(abs(_ut)))
            if _ch < 0.01:
                # v4.3.0: il clamp era silenzioso — geometria alterata senza
                # avviso quando H < W/2·sin|theta| (config fisicamente
                # impossibile col beta_max dichiarato).
                print(f'  ⚠ AVVISO: clearance {_ch:.3f}m < 1cm per theta='
                      f'{_ut:+.1f}° (H troppo bassa per W/beta_max): '
                      f'clampata a 0.01m — geometria alterata.')
                _ch = 0.01
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
                if not _scene_rad:
                    # v4.3.0: senza match il fallback silenzioso era la scena
                    # MONO-fila (zero ombreggiamento inter-row -> K_agv
                    # enormemente sovrastimato). Meglio fallire rumorosamente.
                    raise RuntimeError(
                        f'Slope L2: radfile della scena base "{_radname}" non '
                        f'trovato fra {len(_radfiles)} radfiles (cambio naming '
                        f'di bifacial_radiance?).')
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
                    _out = list(_other_lines)
                    for _ri in range(n_rows):
                        _ro = _ri - _center_row
                        if _ro == 0:
                            _out.extend(_xform_cmds)
                        else:
                            # v4.2 L2 fix: replica multi-fila in coord. mondo
                            # tramite _local_to_world(_dx). Per axis=180 e'
                            # identita' (dx_world=_dx, dy_world=0); per altri
                            # axis_azimuth la replica e' nel frame ruotato.
                            # v4.3.0: nessun clamp su dz — il vecchio clamp
                            # (|dz| <= clearance-0.02) era un retaggio del
                            # terreno orizzontale pre-L3: col ring realmente
                            # inclinato dz = dx*tan(slope) mantiene per
                            # costruzione la clearance sul terreno locale, e
                            # il clamp la rompeva (file sepolte in salita /
                            # sospese in discesa per pendenze ripide).
                            _dx = _ro * p['pitch']
                            _dz = _dx * _tan_slope_cross
                            _dx_w, _dy_w = _local_to_world(_dx)
                            for _xc in _xform_cmds:
                                # Inserisci -t prima del filename (ultimo token)
                                _parts = _xc.split()
                                _fname = _parts[-1]
                                _opts = _parts[1:-1]
                                _out.append(
                                    '!xform ' + ' '.join(_opts)
                                    + f' -t {_dx_w:.6f} {_dy_w:.6f} {_dz:.6f} '
                                    + _fname)
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

        # ── FIX cache scene .oct: pre-espandi i radfiles modulo ──────
        # Diagnosi 2026-05-04: oconv su Windows non gestisce la cascata
        # `oconv → !xform "sr_module.rad" → !genbox|xform` quando lanciato
        # via `subprocess.run(stdin=DEVNULL)`. Il popen interno annidato
        # fallisce silenziosamente (rc=0, no stderr, ma scene.oct degenere).
        # Il legacy worker funziona perché bifacial_radiance usa
        # `_popen(stdin=PIPE)`, ma per la pre-compile useremmo subprocess
        # standard. Soluzione: pre-espandi i file modulo (es. sr_module.rad)
        # da `! genbox … | xform …` a polygon flat con `xform` standalone
        # (verificato funzionare in subprocess.run). Così la cascata di
        # popen si riduce a 1 livello compatibile con oconv. Sovrascrivere
        # il file originale è sicuro: il worker legacy funziona ugualmente
        # con il flat (anzi, più veloce).
        if _cache_dir is not None and len(unique_thetas) <= 200:
            import re as _re_flat
            _modfiles_to_flatten = set()
            for _ut_pf in unique_thetas:
                _radfiles_pf, _ = scene_cache[_ut_pf]
                for _rf_pf in _radfiles_pf:
                    _rf_pf_abs = (_rf_pf if os.path.isabs(_rf_pf)
                                  else os.path.join(temp_work, _rf_pf))
                    if not os.path.exists(_rf_pf_abs):
                        continue
                    try:
                        with open(_rf_pf_abs) as _frf_pf:
                            _content_pf = _frf_pf.read()
                        for _m_pf in _re_flat.finditer(
                                r'!xform[^"]*"([^"]+\.rad)"', _content_pf):
                            _modfiles_to_flatten.add(_m_pf.group(1))
                    except Exception:
                        pass
            _n_flat = 0
            for _modrel in _modfiles_to_flatten:
                _modrel_norm = _modrel.replace('\\', '/')
                _modabs = os.path.join(temp_work, _modrel_norm)
                if not os.path.exists(_modabs):
                    continue
                try:
                    with open(_modabs) as _fmm_pf:
                        _modc_pf = _fmm_pf.read()
                    if '!' not in _modc_pf:
                        continue  # già flat, skip
                except Exception:
                    continue
                try:
                    _flat_tmp = _modabs + '.flat_tmp'
                    with open(_flat_tmp, 'wb') as _fft_pf:
                        _xres_pf = _subprocess.run(
                            ['xform', _modrel_norm],
                            stdin=_subprocess.DEVNULL,
                            stdout=_fft_pf,
                            stderr=_subprocess.PIPE,
                            cwd=temp_work,
                            timeout=60,
                        )
                    _flat_sz = os.path.getsize(_flat_tmp)
                    if _xres_pf.returncode == 0 and _flat_sz > 100:
                        shutil.move(_flat_tmp, _modabs)
                        _n_flat += 1
                    else:
                        if os.path.exists(_flat_tmp):
                            os.remove(_flat_tmp)
                except Exception:
                    try:
                        if os.path.exists(_flat_tmp):
                            os.remove(_flat_tmp)
                    except Exception:
                        pass
            if _n_flat > 0:
                print(f'  Cache scene: pre-espansi {_n_flat} radfile modulo '
                      f'(workaround Windows nested-popen bug)')

        # ── Pre-compile scene .oct con cache (item 4 v4.2) ───────────
        # Per ogni theta unico calcolo l'.oct di scena (matfiles+radfiles,
        # senza cielo). Se la cache è abilitata e c'è già un .oct con la
        # stessa chiave, riutilizzo quello — altrimenti compilo e salvo.
        # Fail-safe: in caso di errore lascio scene_oct_cache[theta] = None
        # e il worker tornerà al full oconv legacy.
        #
        # ── Cache scene .oct (item 4 v4.2) ──────────────────────────
        # Diagnosi 2026-05-04 e fix:
        # - Bug originale: pre-compile produceva octree degeneri (~1.2 KB)
        #   perché `_popen` non passava `cwd=temp_work` al subprocess
        #   oconv. Risultato: i `!xform objects/sr_module.rad` con path
        #   relativo dentro i radfiles non venivano risolti, oconv
        #   compilava solo i materiali. Octree senza geometria → rtrace
        #   100% errori al worker.
        # - Fix: il pre-compile usa `_subprocess.run` esplicito con
        #   `cwd=temp_work` per garantire che path relativi dei
        #   radfiles vengano risolti correttamente. Stessa correttezza
        #   per il worker `oconv -i scene.oct sky.rad`.
        # - Soglia automatica: cache attiva solo per N_thetas <= 200
        #   (validazione_br, single-day, tilt fisso). Per N grandi
        #   (flusso annuale) il pre-compile è skippato per evitare
        #   throttling OneDrive.
        _CACHE_MAX_THETAS = 200
        scene_oct_cache = {}
        if _cache_dir is not None and len(unique_thetas) > _CACHE_MAX_THETAS:
            print(f'  Cache scene: DISATTIVATA — {len(unique_thetas)} theta '
                  f'unici > soglia {_CACHE_MAX_THETAS}. Pre-compile '
                  f'sarebbe più lento del beneficio. Uso flusso legacy.')
            _cache_dir = None
        # TILT FISSO (1 sola scena unica): l'.oct di scena incrementale in
        # cache può risultare degenere (specie con molte file) → rtrace va in
        # timeout 60s su ogni ora, rendendo il run lentissimo e tutto-errori.
        # Il flusso LEGACY (full oconv per ora) è invece corretto (lo stesso
        # percorso usato dai progetti con >200 theta). Con una sola scena la
        # cache dà comunque un beneficio marginale: la disattiviamo per i casi
        # a scena unica.
        if _cache_dir is not None and len(unique_thetas) <= 1:
            print('  Cache scene: DISATTIVATA — tilt fisso (1 scena unica): '
                  'l\'.oct incrementale può risultare degenere, uso flusso legacy.')
            _cache_dir = None
        if _cache_dir is not None:
            _n_hits = 0
            _n_built = 0
            _n_skip_oconv = 0
            _n_skip_rtrace = 0
            _n_skip_geom = 0
            _t_pre = _time.time()
            # Setup sky di test per validazione semantica scene cached.
            # Sole zenit + DNI 500 produce IRR vicino a 500 W/m² su raggio
            # verticale open-sky; con un pannello sopra (materiale black =
            # assorbe), IRR scende a ~0. Soglia 100 W/m² discrimina robusto
            # (fattore 5x).
            _sky_test_rad = os.path.join(temp_work, '_cache_sky_test.rad')
            with open(_sky_test_rad, 'w') as _fst:
                _fst.write('!gendaylit -ang 89 0 -W 500 100 -g 0.2 -O 1\n'
                           'skyfunc glow sky_mat\n0\n0\n4 1 1 1 0\n\n'
                           'sky_mat source sky\n0\n0\n4 0 0 1 180\n')
            # Raggio test: parte dal centro pannello, sotto la quota minima
            # del modulo, e va verso lo zenit. Per qualsiasi tilt il modulo
            # centrale (a y=0 surface) passa per (0, 0, hub_height).
            _test_linepts = b'0 0 0.5 0 0 1\n'
            # B1 (v4.2.2): con pannelli semitrasparenti il raggio
            # verticale trasmette ~tau_tot*500 W/m2: soglia adattiva,
            # altrimenti la cache veniva bocciata come 'senza geometria'.
            _IRR_TEST_THRESHOLD = 100.0 + 500.0 * min(
                0.8, _tau + p.get('tau_diff', 0.0))
            for _ut in unique_thetas:
                try:
                    _radfiles_t, _matfiles_t = scene_cache[_ut]
                    _ch_t = clearance_cache[_ut]
                    _scene_params = {
                        # Token di invalidazione cache = versione di release
                        # che ha fissato l'attuale schema di scena+materiale.
                        # Da incrementare a OGNI cambio di geometria o di
                        # mappatura materiale. Storia interna del 4.3.0: scena
                        # canonica R1 e inversione canonica del materiale trans
                        # sono confluite in questo schema (i .oct col vecchio
                        # materiale ~opaco o con la scena specchiata sono così
                        # invalidati).
                        'sr_compat': '4.3.0',
                        'tilt': float(-_ut) + 0.0,  # firmato (+0.0: no -0.0)
                        'azimuth': (p.get('axis_azimuth', 180.0) - 90.0) % 360.0,
                        'clearance_height': _ch_t,
                        'pitch': p['pitch'],
                        'n_rows': n_rows,
                        'module_x': module_length,
                        'module_y': p['W'],
                        'tau': _tau,
                        'tau_diff': p.get('tau_diff', 0.0),  # M2: nel materiale
                        'albedo': p.get('albedo', 0.23),
                        'slope_cross_deg': p.get('slope_cross_deg', 0.0),
                        'slope_along_deg': p.get('slope_along_deg', 0.0),
                        'axis_azimuth': p.get('axis_azimuth', 180.0),
                        'has_slope_scene': _has_slope_scene,
                    }
                    _key = _SR_CACHE.make_cache_key(_scene_params)
                    _cached = _SR_CACHE.lookup(_cache_dir, _key)
                    if _cached is not None:
                        scene_oct_cache[_ut] = str(_cached)
                        _n_hits += 1
                        continue
                    # Cache miss: compila e salva.
                    _scene_oct_path = os.path.join(
                        temp_work, f'scene_theta_{unique_thetas.index(_ut):04d}.oct')

                    # FIX cache scene: pre-flatten i radfiles principali
                    # interpretando manualmente le righe `!xform`. oconv→popen
                    # e xform→popen via subprocess.run falliscono entrambi su
                    # Windows. Workaround: leggiamo il radfile, troviamo
                    # `!xform <args> "<file>"`, eseguiamo `xform <args> "<file>"`
                    # come comando shell standalone (nessun nesting), catturiamo
                    # stdout (polygon flat) e li scriviamo nel file flat. oconv
                    # riceverà solo polygon puri senza shell command `!`.
                    import re as _re_xf
                    _xform_pat = _re_xf.compile(r'^\s*!xform\s+(.+?)\s*$')
                    _radfiles_flat_t = []
                    for _rf_main in _radfiles_t:
                        _rf_main_abs = (_rf_main if os.path.isabs(_rf_main)
                                        else os.path.join(temp_work, _rf_main))
                        _flat_rel = (_rf_main.rsplit('.rad', 1)[0]
                                     + f'_flat_{unique_thetas.index(_ut):04d}.rad')
                        _flat_abs = (_flat_rel if os.path.isabs(_flat_rel)
                                     else os.path.join(temp_work, _flat_rel))
                        try:
                            with open(_rf_main_abs) as _fmain_in:
                                _rf_lines = _fmain_in.readlines()
                            _flat_total_sz = 0
                            # Funzione: rimuove commenti `#` e righe vuote che
                            # potrebbero confondere oconv tra una primitive e
                            # l'altra. xform stampa header `# xform ...` che
                            # oconv su Windows sembra non gestire correttamente
                            # quando intervallano polygon definition.
                            def _clean_rad(_text_b):
                                _out = []
                                for _ln in _text_b.decode('utf-8',
                                                          errors='replace').splitlines():
                                    _s = _ln.strip()
                                    if not _s:
                                        continue
                                    if _s.startswith('#'):
                                        continue
                                    _out.append(_ln)
                                return ('\n'.join(_out) + '\n').encode('utf-8')
                            with open(_flat_abs, 'wb') as _ff_main:
                                # Header materiali base. bifacial_radiance usa
                                # `black` come materiale di default per genbox
                                # ma NON lo definisce in materials/ground.rad.
                                # Senza, oconv scarta i polygon in silenzio.
                                _mat_header = (
                                    b'void plastic black\n0\n0\n5 0 0 0 0 0\n\n'
                                    b'void glass stock_glass\n0\n0\n3 0.96 0.96 0.96\n\n'
                                )
                                _ff_main.write(_mat_header)
                                _flat_total_sz += len(_mat_header)
                                for _line_rf in _rf_lines:
                                    _m_xf = _xform_pat.match(_line_rf)
                                    if _m_xf:
                                        _xf_cmdline = 'xform ' + _m_xf.group(1)
                                        _xf_res = _subprocess.run(
                                            _xf_cmdline,
                                            shell=True,
                                            stdin=_subprocess.DEVNULL,
                                            stdout=_subprocess.PIPE,
                                            stderr=_subprocess.PIPE,
                                            cwd=temp_work,
                                            timeout=60,
                                        )
                                        if (_xf_res.returncode == 0
                                                and _xf_res.stdout
                                                and len(_xf_res.stdout) > 50):
                                            _cleaned = _clean_rad(_xf_res.stdout)
                                            _ff_main.write(_cleaned)
                                            _flat_total_sz += len(_cleaned)
                                        else:
                                            # xform fallito → scrivi linea originale
                                            _ff_main.write(_line_rf.encode('utf-8'))
                                            _flat_total_sz += len(_line_rf)
                                    else:
                                        # Skip commenti e righe vuote anche qui
                                        _s_rf = _line_rf.strip()
                                        if _s_rf and not _s_rf.startswith('#'):
                                            _b_rf = (_line_rf if _line_rf.endswith('\n')
                                                     else _line_rf + '\n').encode('utf-8')
                                            _ff_main.write(_b_rf)
                                            _flat_total_sz += len(_b_rf)
                            if _flat_total_sz > 200:
                                _radfiles_flat_t.append(_flat_rel)
                            else:
                                _radfiles_flat_t.append(_rf_main)
                        except Exception:
                            _radfiles_flat_t.append(_rf_main)
                    _oconv_inputs = list(_matfiles_t) + _radfiles_flat_t
                    _proc_result = None

                    # `-b xmin ymin zmin size`: bbox esplicita 200m^3 centrata
                    # sull'origine. Necessaria perché il sky.rad del worker
                    # iniettato via `oconv -i` contiene `groundplane ring 100m`,
                    # che senza bbox forzata va fuori dall'octree dei pannelli
                    # (~30m) → "boundary does not encompass scene" fatal.
                    # `-f` (freeze): octree self-contained. Senza, il
                    # successivo `oconv -i scene.oct` rilegge i radfile
                    # originali della temp dir del run creatore (cancellata
                    # a fine run) -> al riuso cross-run della cache TUTTE le
                    # ore fallivano in rtrace.
                    # M1 (v4.2.2): con slope_cross != 0 il ring del terreno
                    # (raggio 100 m) raggiunge z = +/-100*tan(slope): la bbox
                    # deve includerlo o `oconv -i` fallisce ("boundary does
                    # not encompass scene") su OGNI ora cache-hit. Per
                    # terreno piano la bbox resta identica (cache invariata).
                    _zm = 100.0 * abs(np.tan(np.radians(
                        p.get('slope_cross_deg', 0.0)))) + 1.0 \
                        if _has_slope_scene else 0.0
                    with open(_scene_oct_path, 'w') as _f_oct:
                        _proc_result = _subprocess.run(
                            ['oconv', '-f', '-b', '-100', '-100',
                             f'{-1.0 - _zm:g}', f'{200.0 + 2.0 * _zm:g}']
                            + _oconv_inputs,
                            stdin=_subprocess.DEVNULL,
                            stdout=_f_oct,
                            stderr=_subprocess.PIPE,
                            cwd=temp_work,
                            timeout=120,
                        )
                    _oct_size = os.path.getsize(_scene_oct_path) \
                                if os.path.exists(_scene_oct_path) else 0

                    # Validazione semantica via rtrace di test:
                    # 1) linka sky_test (sole zenit) all'oct cached
                    # 2) lancia rtrace con raggio verticale al centro pannello
                    # 3) se IRR < soglia: pannello blocca → cache valida
                    #    se IRR ≈ open-sky: nessuna geometria → fallback
                    # Categorizziamo i fallimenti per warning informativi.
                    _oct_valido = False
                    _skip_reason = None
                    _skip_detail = ''
                    _test_oct_path = _scene_oct_path + '.test'
                    if _proc_result.returncode != 0:
                        _skip_reason = 'oconv'
                        _skip_detail = (_proc_result.stderr.decode(errors='replace')[:200]
                                        if _proc_result.stderr else
                                        f'rc={_proc_result.returncode}')
                    else:
                        try:
                            with open(_test_oct_path, 'w') as _ftst:
                                _r_link = _subprocess.run(
                                    ['oconv', '-i', _scene_oct_path,
                                     _sky_test_rad],
                                    stdin=_subprocess.DEVNULL,
                                    stdout=_ftst,
                                    stderr=_subprocess.PIPE,
                                    cwd=temp_work,
                                    timeout=30,
                                )
                            if _r_link.returncode != 0:
                                _skip_reason = 'oconv'
                                _skip_detail = (
                                    _r_link.stderr.decode(errors='replace')[:200]
                                    if _r_link.stderr else 'oconv -i fail')
                            elif (not os.path.exists(_test_oct_path)
                                    or os.path.getsize(_test_oct_path) < 100):
                                _skip_reason = 'oconv'
                                _skip_detail = 'test oct vuoto/troncato'
                            else:
                                _r_rt = _subprocess.run(
                                    f'rtrace {rtrace_opts} "{_test_oct_path}"',
                                    shell=True,
                                    input=_test_linepts,
                                    capture_output=True,
                                    timeout=15,
                                )
                                if _r_rt.returncode != 0:
                                    _skip_reason = 'rtrace'
                                    _skip_detail = (
                                        _r_rt.stderr.decode(errors='replace')[:200]
                                        if _r_rt.stderr else
                                        f'rc={_r_rt.returncode}')
                                else:
                                    _out_lines = _r_rt.stdout.decode().strip().split('\n')
                                    if not _out_lines or not _out_lines[0]:
                                        _skip_reason = 'rtrace'
                                        _skip_detail = 'empty stdout'
                                    else:
                                        _parts_rt = _out_lines[0].split('\t')
                                        if len(_parts_rt) >= 6:
                                            try:
                                                _r_v = float(_parts_rt[3])
                                                _g_v = float(_parts_rt[4])
                                                _b_v = float(_parts_rt[5])
                                                _irr_test = (_r_v + _g_v + _b_v) / 3.0
                                                if _irr_test < _IRR_TEST_THRESHOLD:
                                                    _oct_valido = True
                                                else:
                                                    _skip_reason = 'geom'
                                                    _skip_detail = (
                                                        f'IRR test={_irr_test:.0f} '
                                                        f'W/m² ≥ soglia '
                                                        f'{_IRR_TEST_THRESHOLD:.0f}')
                                            except ValueError as _ve:
                                                _skip_reason = 'rtrace'
                                                _skip_detail = f'parse err: {_ve}'
                                        else:
                                            _skip_reason = 'rtrace'
                                            _skip_detail = (
                                                f'stdout ill-formed: '
                                                f'{_out_lines[0][:100]}')
                        except Exception as _eval:
                            _skip_reason = 'rtrace'
                            _skip_detail = f'exception: {_eval}'
                        finally:
                            try:
                                if os.path.exists(_test_oct_path):
                                    os.remove(_test_oct_path)
                            except Exception:
                                pass
                    if _oct_valido:
                        _stored = _SR_CACHE.store(
                            _cache_dir, _key, _scene_oct_path, _scene_params)
                        scene_oct_cache[_ut] = str(_stored)
                        _n_built += 1
                    else:
                        scene_oct_cache[_ut] = None
                        if _skip_reason == 'oconv':
                            _n_skip_oconv += 1
                        elif _skip_reason == 'rtrace':
                            _n_skip_rtrace += 1
                        elif _skip_reason == 'geom':
                            _n_skip_geom += 1
                        # Stampa primo dettaglio per categoria (debug)
                        if (_skip_reason == 'oconv' and _n_skip_oconv == 1) \
                                or (_skip_reason == 'rtrace' and _n_skip_rtrace == 1) \
                                or (_skip_reason == 'geom' and _n_skip_geom == 1):
                            print(f'  Cache scene: primo skip "{_skip_reason}" '
                                  f'(theta={_ut:.2f}): {_skip_detail}')
                except Exception as _exc:
                    if _ut not in scene_oct_cache:
                        scene_oct_cache[_ut] = None
                    if (_n_skip_oconv + _n_skip_rtrace + _n_skip_geom) == 0:
                        import traceback as _tb
                        print(f'  Cache scene: pre-compile exception: {_exc}')
                        print(_tb.format_exc())
                    _n_skip_rtrace += 1
            _t_pre = _time.time() - _t_pre
            _n_skip_tot = _n_skip_oconv + _n_skip_rtrace + _n_skip_geom
            print(f'  Cache scene: {_n_hits} hit + {_n_built} built + '
                  f'{_n_skip_tot} skip ({_t_pre:.1f}s)')
            # Warning per categoria di skip
            if _n_skip_oconv > 0:
                print(f'  ⚠ Cache scene: {_n_skip_oconv}/{len(unique_thetas)} '
                      f'scene oconv link fail (boundary, sintassi rad, IO?) '
                      f'→ fallback legacy per quelle ore')
            if _n_skip_rtrace > 0:
                print(f'  ⚠ Cache scene: {_n_skip_rtrace}/{len(unique_thetas)} '
                      f'scene rtrace test fail (timeout, parse err?) '
                      f'→ fallback legacy per quelle ore')
            if _n_skip_geom > 0:
                print(f'  ⚠ Cache scene: {_n_skip_geom}/{len(unique_thetas)} '
                      f'scene SENZA geometria pannelli (bug oconv/xform su '
                      f'questa configurazione?) → fallback legacy. Verifica '
                      f'che il modello pannello sia generato correttamente.')
            # Housekeeping: mantieni 20 scene più recenti
            try:
                _n_rem = _SR_CACHE.housekeeping(_cache_dir, keep_n=20)
                if _n_rem > 0:
                    print(f'  Cache scene: rimosse {_n_rem} scene vecchie')
            except Exception:
                pass
        else:
            for _ut in unique_thetas:
                scene_oct_cache[_ut] = None

        # ── Ground string (albedo) ───────────────────────────────────
        _ground_Rrefl = rad.ground.Rrefl[0]
        _ground_Grefl = rad.ground.Grefl[0]
        _ground_Brefl = rad.ground.Brefl[0]
        _ground_refl = rad.ground.ReflAvg[0]
        _ground_type = rad.ground.ground_type

        _nv = max(_ground_Rrefl, _ground_Grefl, _ground_Brefl)
        if _nv == 0:
            _nv = 1
        # Slope L3 v4.2: groundplane reale (orizzontale per slope=0,
        # inclinato per slope_cross != 0). Centro e normale calcolati a
        # monte; per slope=0 riproduce esattamente il ring v4.1.
        _ground_str = (
            f'\nskyfunc glow ground_glow\n0\n0\n4 '
            f'{_ground_Rrefl/_nv} {_ground_Grefl/_nv} {_ground_Brefl/_nv} 0\n'
            '\nground_glow source ground\n0\n0\n4 0 0 -1 180\n'
            f'\nvoid plastic {_ground_type}\n0\n0\n5 '
            f'{_ground_Rrefl:0.3f} {_ground_Grefl:0.3f} {_ground_Brefl:0.3f} 0 0\n'
            f'\n{_ground_type} ring groundplane\n'
            f'0\n0\n8\n{_gc_x:.4f} {_gc_y:.4f} {_gc_z:.4f}\n'
            f'{_gn_x:.6f} {_gn_y:.6f} {_gn_z:.6f}\n0 100'
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
            scene_oct = scene_oct_cache.get(theta)

            task_list.append({
                'task_idx': i,
                'hour_idx': idx_int,
                'oct_inputs': oct_inputs,
                'sky_path': sky_path,
                'scene_oct': scene_oct,  # path .oct cached o None (v4.2 item 4)
            })

        n_tasks = len(task_list)
        n_with_cache = sum(1 for t in task_list if t['scene_oct'])
        if n_with_cache > 0:
            print(f'  {n_tasks} ore da simulare ({n_with_cache} con cache .oct, '
                  f'{n_tasks - n_with_cache} legacy full-oconv)')
        else:
            print(f'  {n_tasks} ore da simulare')

        # ── Worker function ──────────────────────────────────────────
        def _worker(task):
            """Esegue oconv + rtrace per una singola ora.

            v4.2 item 4: se task['scene_oct'] è valorizzato (cache hit),
            usa `oconv -i scene.oct sky.rad` (linkaggio incrementale)
            invece del full `oconv matfiles + sky + radfiles`. La forma
            incrementale evita la ri-compilazione della scena geometrica
            che è invariante tra le ore.

            FIX 2026-05-04: usa subprocess.run con cwd=temp_work esplicito
            (no _popen) per garantire risoluzione corretta dei path
            relativi nei radfiles dello scene.oct cached.
            """
            oct_path = task['sky_path'].replace('.rad', '.oct')

            if task.get('scene_oct'):
                # Modalità cache: incrementale via -i
                oconv_cmd = ['oconv', '-i', task['scene_oct'], task['sky_path']]
            else:
                # Legacy: full oconv
                oconv_cmd = ['oconv'] + task['oct_inputs']
            try:
                with open(oct_path, 'w') as f_oct:
                    rc = _subprocess.run(
                        oconv_cmd,
                        stdout=f_oct,
                        stderr=_subprocess.DEVNULL,
                        cwd=temp_work,
                        timeout=60,
                    )
                if rc.returncode != 0:
                    return task['task_idx'], task['hour_idx'], None
            except Exception:
                return task['task_idx'], task['hour_idx'], None
            if not os.path.exists(oct_path) or os.path.getsize(oct_path) < 100:
                return task['task_idx'], task['hour_idx'], None

            # rtrace — M3 (v4.2.2): try/except su run e parsing: un
            # timeout o un output malformato su UNA ora deve contare come
            # errore di quell'ora, non abortire l'intera simulazione.
            try:
                rtrace_cmd = f'rtrace {rtrace_opts} "{oct_path}"'
                result = _subprocess.run(rtrace_cmd, shell=True,
                                         input=linepts_bytes,
                                         capture_output=True, timeout=60)
            except Exception:
                return task['task_idx'], task['hour_idx'], None
            if result.returncode != 0:
                return task['task_idx'], task['hour_idx'], None

            # Parse output (-oovs: tab-separated, cols 3-5 = value RGB)
            # M3-bis (v4.3.0): errors='replace' — un byte non-UTF8 nello
            # stdout (nomi superficie con -oovs) deve contare come errore
            # dell'ora (token malformato), non abortire il run intero.
            lines = result.stdout.decode(errors='replace').strip().split('\n')
            vals = []
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 6:
                    try:
                        r, g, b = (float(parts[3]), float(parts[4]),
                                   float(parts[5]))
                    except ValueError:  # M3: token malformato
                        return task['task_idx'], task['hour_idx'], None
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

        if not results_list:
            raise RuntimeError(
                'Nessuna ora simulata con successo (100% errori rtrace): '
                'vedi i WARNING sopra. Se il run usa la cache scene, la '
                'cache potrebbe essere corrotta: cancellare '
                '<progetto>/.cache/scenes e rilanciare.')
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
        # v4.2 item 7: posizionato in coordinata locale v=5 e ruotato.
        _os_v = 5.0
        _os_x, _os_y = _local_to_world(_os_v)
        _os_z = _sensor_z(_os_v)
        opensky_linepts = f'{_os_x:.6f} {_os_y:.6f} {_os_z:.6f} 0 0 1'.encode()

        def _worker_opensky(task):
            """rtrace con solo sky+ground (no scene geometry)."""
            sky_path = task['sky_path']
            oct_path = sky_path.replace('.rad', '_os.oct')
            # v4.3.0: oconv con timeout (il _popen storico non lo aveva: un
            # oconv bloccato appendeva il thread e il run non terminava mai)
            try:
                with open(oct_path, 'w') as f_oct:
                    _subprocess.run(['oconv', sky_path], stdout=f_oct,
                                    stderr=_subprocess.DEVNULL, timeout=60)
            except Exception:
                return task['hour_idx'], None
            if not os.path.exists(oct_path):
                return task['hour_idx'], None
            try:  # v4.3.0: anche TimeoutExpired = errore dell'ora, non abort
                rtrace_cmd = f'rtrace {rtrace_opts} "{oct_path}"'
                res = _subprocess.run(rtrace_cmd, shell=True,
                                      input=opensky_linepts,
                                      capture_output=True, timeout=30)
            except Exception:
                return task['hour_idx'], None
            finally:
                try:
                    os.remove(oct_path)
                except Exception:
                    pass
            if res.returncode != 0:
                return task['hour_idx'], None
            try:  # M3 (v4.2.2): parsing difensivo anche nell'open-sky
                parts = res.stdout.decode(errors='replace').strip().split('\t')
                if len(parts) >= 6:
                    r, g, b = (float(parts[3]), float(parts[4]),
                               float(parts[5]))
                    irr = (r + g + b) / 3.0  # W/m² (matches BR convention)
                    return task['hour_idx'], irr
            except Exception:
                pass
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
        if n_os_ok < len(task_list):
            # v4.3.0: le ore fallite restano 0 in IRR_opensky e abbassano il
            # riferimento (PAR_rel sovrastimata in quelle ore): va dichiarato.
            print(f'  ⚠ AVVISO: {len(task_list) - n_os_ok} ore open-sky '
                  f'FALLITE (restano a 0 nel riferimento: PAR relativa '
                  f'sovrastimata in quelle ore).')
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
        # bifacial_radiance (RadianceObj) fa chdir in temp_work: ripristina la
        # CWD PRIMA di cancellarla. Su Linux rmtree della CWD riesce e lascia
        # il processo senza directory corrente -> i successivi import che
        # chiamano os.getcwd() (es. reportlab) fallirebbero: PDF mai scritto.
        try:
            os.chdir(_cwd_orig)
        except OSError:
            os.chdir(tempfile.gettempdir())
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
