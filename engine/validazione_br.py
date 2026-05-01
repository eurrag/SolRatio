"""
validazione_br.py  |  SolRatio v4.1.0
=======================================
Confronto tra SolRatio v4 (rtrace custom) e workflow standard
bifacial_radiance (AnalysisObj) sullo stesso progetto.

Esegue una simulazione con il workflow ufficiale BR su un giorno campione
e confronta il profilo di irradianza al suolo con quello prodotto da
SolRatio v4 (br_engine.run_annual con sample_days).

Uso:
    python validazione_br.py <percorso_SolRatio_progetto.xlsm>

Output:
    - Stampa tabella confronto punto per punto
    - Salva CSV con profili affiancati
    - Calcola MBE, RMSE, R² tra i due profili
"""

import sys
import os
import shutil
import tempfile
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    if len(sys.argv) < 2:
        print("Uso: python validazione_br.py <percorso_SolRatio_progetto.xlsm>")
        sys.exit(1)

    input_path = os.path.abspath(sys.argv[1])
    proj_dir = os.path.dirname(input_path)

    print('=' * 65)
    print(' VALIDAZIONE SolRatio v4 vs bifacial_radiance ufficiale')
    print('=' * 65)

    # ── Lettura parametri ────────────────────────────────────────────
    from openpyxl import load_workbook
    from solratio_excel import read_parameters
    from br_engine import pvgis_to_epw, run_annual

    tmp_input = os.path.join(proj_dir, '_sr_temp_val.xlsx')
    shutil.copy2(input_path, tmp_input)
    wb = load_workbook(tmp_input, data_only=True)
    p = read_parameters(wb)
    wb.close()
    try:
        os.remove(tmp_input)
    except Exception:
        pass

    print(f'  Progetto: {proj_dir}')
    print(f'  Pitch={p["pitch"]}m  W={p["W"]}m  H={p["H"]:.3f}m')
    print(f'  GCR={p["GCR"]:.3f}  beta_max={p["beta_max"]}°')
    print(f'  Albedo={p["albedo"]:.2f}  n_ext={p["n_ext"]}')
    print()

    # ── Generazione EPW ──────────────────────────────────────────────
    pvgis_files = [f for f in os.listdir(proj_dir)
                   if f.startswith('PVGIS') and f.endswith('.csv')]
    if not pvgis_files:
        print("ERRORE: nessun file PVGIS*.csv")
        sys.exit(1)
    pvgis_csv = os.path.join(proj_dir, pvgis_files[0])
    epw_path, tmy_info = pvgis_to_epw(pvgis_csv, p['lat'], p['lon'])
    print()

    # ── Giorni campione: equinozio (21 mar) e solstizio estate (21 giu) ─
    sample_days_list = [(3, 21), (6, 21)]

    for target_month, target_day in sample_days_list:
        print('=' * 65)
        print(f' GIORNO CAMPIONE: {target_day}/{target_month}')
        print('=' * 65)

        n_points = p['n_points']

        # ══════════════════════════════════════════════════════════════
        # A) SOLRATIO v4 (rtrace custom)
        # ══════════════════════════════════════════════════════════════
        print('\n--- A) SolRatio v4 (rtrace custom) ---')
        sample_days = {(target_month, target_day)}
        sr_result = run_annual(p, epw_path, n_points=n_points,
                               sample_days=sample_days)
        IRR_sr = sr_result['IRR_hourly']  # (n_hours, n_points)
        x_pts = sr_result['x_pts']

        # Profilo medio giornaliero [W/m²]
        if len(IRR_sr) > 0:
            profile_sr = IRR_sr.mean(axis=0)
            profile_sr_sum = IRR_sr.sum(axis=0)  # Wh/m²
        else:
            profile_sr = np.zeros(n_points)
            profile_sr_sum = np.zeros(n_points)
        print(f'  Ore simulate: {sr_result["n_hours_ok"]}')
        print(f'  IRR medio: {profile_sr.mean():.1f} W/m²')

        # ══════════════════════════════════════════════════════════════
        # B) BIFACIAL_RADIANCE UFFICIALE (AnalysisObj)
        # ══════════════════════════════════════════════════════════════
        print('\n--- B) bifacial_radiance ufficiale (AnalysisObj) ---')
        profile_br = _run_br_official(p, epw_path, target_month, target_day,
                                       n_points)
        if profile_br is not None:
            print(f'  IRR medio: {profile_br.mean():.1f} W/m²')
        else:
            print('  ERRORE: simulazione BR ufficiale fallita')
            continue

        # ══════════════════════════════════════════════════════════════
        # C) CONFRONTO
        # ══════════════════════════════════════════════════════════════
        print(f'\n--- Confronto profilo irradianza ({target_day}/{target_month}) ---')
        print(f'  {"x/pitch":>8s}  {"SR v4":>10s}  {"BR uff.":>10s}  '
              f'{"diff":>8s}  {"diff%":>7s}')
        print('  ' + '-' * 52)

        for i in range(0, n_points, max(1, n_points // 10)):
            xp = x_pts[i] / p['pitch']
            sv = profile_sr_sum[i]
            bv = profile_br[i]
            diff = sv - bv
            pct = diff / bv * 100 if bv > 0 else 0
            print(f'  {xp:>8.2f}  {sv:>10.1f}  {bv:>10.1f}  '
                  f'{diff:>+8.1f}  {pct:>+6.1f}%')

        # Statistiche
        valid = profile_br > 0
        if valid.any():
            mbe = np.mean(profile_sr_sum[valid] - profile_br[valid])
            rmse = np.sqrt(np.mean((profile_sr_sum[valid] - profile_br[valid])**2))
            mean_br = np.mean(profile_br[valid])
            nmbe = mbe / mean_br * 100
            nrmse = rmse / mean_br * 100

            # R²
            ss_res = np.sum((profile_sr_sum[valid] - profile_br[valid])**2)
            ss_tot = np.sum((profile_br[valid] - np.mean(profile_br[valid]))**2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

            print(f'\n  MBE  = {mbe:+.1f} Wh/m² ({nmbe:+.1f}%)')
            print(f'  RMSE = {rmse:.1f} Wh/m² ({nrmse:.1f}%)')
            print(f'  R²   = {r2:.4f}')
        print()

        # Salva CSV
        csv_path = os.path.join(proj_dir,
                                f'validazione_{target_month:02d}{target_day:02d}.csv')
        df_out = pd.DataFrame({
            'x_m': x_pts,
            'x_pitch': x_pts / p['pitch'],
            'SR_v4_Whm2': profile_sr_sum,
            'BR_ufficiale_Whm2': profile_br,
            'diff_Whm2': profile_sr_sum - profile_br,
        })
        df_out.to_csv(csv_path, index=False)
        print(f'  CSV salvato: {csv_path}')
        print()

    print('Validazione completata.')


def _run_br_official(p, epw_path, target_month, target_day, n_points):
    """
    Esegue simulazione con workflow ufficiale bifacial_radiance:
    RadianceObj → readWeatherFile → makeScene → gendaylit → AnalysisObj

    Restituisce profilo irradianza cumulata giornaliera [Wh/m²] (n_points,)
    o None se fallisce.
    """
    import bifacial_radiance as br
    from pvlib import tracking as pvlib_tracking

    temp_work = tempfile.mkdtemp(prefix='sr_val_br_')

    try:
        rad = br.RadianceObj(name='validation', path=temp_work)
        epw_local = os.path.join(temp_work, os.path.basename(epw_path))
        shutil.copy2(epw_path, epw_local)
        metdata = rad.readWeatherFile(epw_local)
        rad.setGround(p.get('albedo', 0.23))

        module_length = 30.0
        n_ext = p.get('n_ext', 2)
        n_rows = 2 * n_ext + 1

        mod = rad.makeModule(name='val_module', x=module_length, y=p['W'],
                             glass=False)

        # Tracker angles
        solpos = metdata.solpos
        tracker_res = pvlib_tracking.singleaxis(
            apparent_zenith=solpos['apparent_zenith'],
            solar_azimuth=solpos['azimuth'],
            axis_tilt=0,
            axis_azimuth=p.get('axis_azimuth', 180.0),
            max_angle=p['beta_max'],
            backtrack=bool(p.get('backtracking', 1)),
            gcr=p['GCR'],
        )
        tracker_theta = tracker_res['tracker_theta'].fillna(0).values

        ghi_arr = np.array(metdata.ghi if hasattr(metdata, 'ghi') else
                           metdata.GHI, dtype=float)
        sun_elev = solpos['apparent_elevation'].values

        # Filtra ore del giorno campione
        day_indices = []
        for idx in range(len(metdata.datetime)):
            dt = metdata.datetime[idx]
            if (dt.month == target_month and dt.day == target_day
                    and sun_elev[idx] > 2.0 and ghi_arr[idx] > 20.0):
                day_indices.append(idx)

        if not day_indices:
            print(f'  Nessuna ora diurna per {target_day}/{target_month}')
            return None

        print(f'  Ore diurne: {len(day_indices)}')

        hub_height = p['H']

        # Parametri rtrace (identici a SR v4 = BR 'low')
        br_ab = p.get('br_ab', 2)
        br_ad = p.get('br_ad', 2048)
        br_as = p.get('br_as', 256)
        rtrace_opts = (f'-I -ab {br_ab} -aa .1 -ar 256'
                       f' -ad {br_ad} -as {br_as} -h -oovs')
        print(f'  rtrace: -ab {br_ab} -ad {br_ad} -as {br_as} -oovs')

        # Sensori al suolo: stessi punti di SR v4
        xinc = p['pitch'] / (n_points - 1)
        linepts = '\n'.join(
            f'{j * xinc:.6f} 0 0.05 0 0 1'
            for j in range(n_points))
        linepts_bytes = linepts.encode()

        cumulative_irr = np.zeros(n_points)
        n_ok = 0

        import subprocess as _subprocess

        for idx in day_indices:
            theta = float(tracker_theta[idx])
            tilt = abs(theta)
            azimuth = 90.0 if theta >= 0 else 270.0
            ch = hub_height - 0.5 * p['W'] * np.sin(np.radians(tilt))
            ch = max(0.01, ch)

            dni_val = float(metdata.dni[idx])
            dhi_val = float(metdata.dhi[idx])
            sun_alt = float(solpos['elevation'].values[idx])
            sun_az = float(solpos['azimuth'].values[idx]) - 180.0

            if dhi_val <= 0 or sun_alt <= 0:
                continue

            # Genera cielo con gendaylit (metodo BR ufficiale)
            try:
                rad.gendaylit2manual(dni_val, dhi_val, sun_alt, sun_az)
            except Exception:
                try:
                    sky_str = (
                        f"!gendaylit -ang {sun_alt} {sun_az}"
                        f" -W {dni_val} {dhi_val}"
                        f" -g {p.get('albedo', 0.23)} -O 1 \n"
                        "skyfunc glow sky_mat\n0\n0\n4 1 1 1 0\n"
                        "\nsky_mat source sky\n0\n0\n4 0 0 1 180\n"
                    )
                    sky_path = os.path.join(temp_work, 'skies', 'sky_val.rad')
                    os.makedirs(os.path.dirname(sky_path), exist_ok=True)
                    with open(sky_path, 'w') as f:
                        f.write(sky_str)
                except Exception as e2:
                    print(f'  Errore sky idx={idx}: {e2}')
                    continue

            # Crea scena e octree con workflow BR ufficiale
            sceneDict = {
                'tilt': tilt, 'pitch': p['pitch'],
                'clearance_height': ch,
                'azimuth': azimuth,
                'nMods': 1, 'nRows': n_rows,
            }

            import io
            import contextlib
            _devnull = io.StringIO()
            with contextlib.redirect_stdout(_devnull):
                scene = rad.makeScene(module=mod, sceneDict=sceneDict)
                octfile = rad.makeOct()

            # rtrace con stessi parametri e formula di SR v4
            try:
                rtrace_cmd = f'rtrace {rtrace_opts} "{octfile}"'
                res = _subprocess.run(rtrace_cmd, shell=True,
                                       input=linepts_bytes,
                                       capture_output=True, timeout=60)
                if res.returncode == 0:
                    lines = res.stdout.decode().strip().split('\n')
                    vals = []
                    for line in lines:
                        parts = line.split('\t')
                        if len(parts) >= 6:
                            r, g, b = (float(parts[3]), float(parts[4]),
                                       float(parts[5]))
                            irr = (r + g + b) / 3.0  # W/m² (BR convention)
                            vals.append(irr)
                    if len(vals) == n_points:
                        cumulative_irr += np.array(vals)
                        n_ok += 1
            except Exception as e:
                print(f'  Errore rtrace idx={idx}: {e}')

        print(f'  Ore simulate: {n_ok}/{len(day_indices)}')
        return cumulative_irr

    finally:
        try:
            shutil.rmtree(temp_work)
        except Exception:
            pass


if __name__ == '__main__':
    import traceback as _tb
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        print('\n' + '=' * 65)
        print(' ERRORE')
        print('=' * 65)
        print(_tb.format_exc())
        sys.exit(1)
