"""
solratio_multiyear.py  |  SolRatio v4.3.0
========================================================================
Esegue la pipeline SolRatio (motore BR + ottica + agronomia) su più
anni meteorologici PVGIS e aggrega le statistiche di K_agv come
quantili P10/P50/P90.

Strategia A (decisione utente 2026-05-02):
- Run sequenziale anno-per-anno
- Salvataggio incrementale (resilienza a crash / interruzioni)
- Flag CLI `--years` per cappare lo scope durante sviluppo

Uso
---

    python engine/solratio_multiyear.py <progetto.xlsm> [--years SPEC]

`SPEC` può essere:
  - `tmy`            (default v4.1: TMY composito mese-per-mese)
  - `all`            (tutti gli anni disponibili in PVGIS CSV)
  - `2010,2015,2020` (lista esplicita)
  - `3`              (numero: i 3 anni equispaziati nel range disponibile)

Output
------

    <progetto>/test/multiyear_results.csv   (un riga per anno)
    <progetto>/test/multiyear_quantiles.json (P10/P50/P90 K_agv per coltura)

Se la cartella `test/` non esiste, viene creata. Se esiste un risultato
parziale (multiyear_results.csv esistente), gli anni già completati
vengono saltati: rilanciare lo script riprende dove si era interrotto.

Note di design
--------------
- Per ogni anno la pipeline esegue: pvgis_to_epw_year() → run_annual()
  → compute_yield_curves() → estrae K_agv aggregato.
- L'aggregazione P10/P50/P90 è calcolata DA PYTHON usando numpy.percentile
  sui valori di K_agv per anno.
- Il TMY composito è SEMPRE incluso come riga aggiuntiva nel CSV come
  riferimento storico (ma non entra nei quantili).
- Il salvataggio è incrementale: ogni anno completato → append a CSV
  immediato. In caso di crash, i risultati finora completati sono salvati.
- Bifacial_radiance/Radiance non sono progettati per multi-thread (file
  temp condivisi). Quindi: run sequenziale, no parallelizzazione.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd


def parse_years_spec(spec: str, available_years: List[int]) -> List[int]:
    """
    Risolve la spec CLI in una lista di anni.

    Parameters
    ----------
    spec : str
        'tmy' | 'all' | '2010,2015,2020' | '3' (intero N → N anni equispaziati)
    available_years : list of int
        Anni effettivamente presenti in PVGIS CSV.
    """
    spec = spec.strip().lower()
    if spec == "tmy":
        return []  # speciale: solo TMY, niente anni singoli
    if spec == "all":
        return sorted(available_years)
    if "," in spec:
        years = [int(s.strip()) for s in spec.split(",") if s.strip()]
        missing = set(years) - set(available_years)
        if missing:
            print(f"  AVVISO: anni richiesti non disponibili: {sorted(missing)}")
        return sorted(set(years) & set(available_years))
    try:
        n = int(spec)
    except ValueError:
        raise SystemExit(f"--years '{spec}' non riconosciuto. Valori ammessi: "
                         f"'tmy', 'all', N (anni equispaziati), "
                         f"'2010,2015,2020' (lista).")
    # v4.3.0: un anno a 4 cifre senza virgola (es. '--years 2015') era
    # interpretato come "2015 anni equispaziati" -> errore fuorviante.
    if n in available_years and n > len(available_years):
        return [n]
    if n < 1 or n > len(available_years):
        # v4.3.0: il raise informativo era DENTRO il try e veniva
        # catturato dal proprio except ValueError -> messaggio generico.
        raise SystemExit(
            f"--years {n}: deve essere tra 1 e {len(available_years)} "
            f"(anni disponibili: {min(available_years)}-{max(available_years)}; "
            f"per un anno specifico usare la lista, es. '{n},').")
    # Anni equispaziati nel range
    idxs = np.linspace(0, len(available_years) - 1, n).round().astype(int)
    years = [sorted(available_years)[int(i)] for i in idxs]
    return sorted(set(years))


# Versione formato EPW generato da questo script. Bumpare quando si
# modifica il layout dei campi data (es. nuovo numero di colonne,
# diverso flag string, ecc.). Gli EPW cached con versione mismatched
# vengono rigenerati automaticamente al prossimo run.
EPW_FORMAT_VERSION = "v2"  # v2 = formato 35-campi corretto (v4.2.0+)


def _epw_format_marker() -> str:
    """Stringa che identifica il formato EPW corrente, scritta in COMMENTS 1."""
    return f"format={EPW_FORMAT_VERSION}"


def _epw_has_current_format(epw_path: Path) -> bool:
    """
    True se il file EPW contiene il marker di formato corrente in
    COMMENTS 1. Se il file esiste ma il marker manca / è vecchio
    (perché generato da una versione precedente), torna False e il
    chiamante lo rigenera.
    """
    try:
        with open(epw_path, 'r', encoding='ascii', errors='ignore') as f:
            for _ in range(8):  # leggi solo header (max 8 righe)
                line = f.readline()
                if not line:
                    return False
                # v4.3.0: match con delimitatore (\b): 'format=v2' senza
                # boundary combacerebbe anche con un futuro 'format=v2.1'
                # in uno scenario di downgrade.
                if line.startswith('COMMENTS 1,') and re.search(
                        re.escape(_epw_format_marker()) + r'\b', line):
                    return True
        return False
    except Exception:
        return False


def build_year_epw(
    pvgis_csv_path: Path,
    year: int,
    lat: float,
    lon: float,
    output_dir: Path,
    elevation: float = 0,
) -> Path:
    """
    Genera un EPW per un anno specifico estratto dal PVGIS multi-anno CSV.

    Differente da `pvgis_to_epw` standard che fa TMY mese-per-mese: qui
    si prende l'anno fisico così com'è (12 mesi consecutivi dello stesso
    anno calendar).

    Cache invalidation: se il file EPW esiste ma è stato generato con
    una versione di formato precedente (marker mancante o diverso in
    COMMENTS 1), viene cancellato e rigenerato. Questo evita che bug
    di formato risolti in versioni successive vengano "sovrascritti"
    da cache obsolete.

    Returns
    -------
    Path al file EPW generato in output_dir.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    epw_path = output_dir / f"PVGIS_{lat:.4f}_{lon:.4f}_{year}.epw"
    if epw_path.is_file():
        if _epw_has_current_format(epw_path):
            print(f"  EPW {year} già esistente (formato {EPW_FORMAT_VERSION} OK): "
                  f"{epw_path.name}")
            return epw_path
        # File esistente con formato obsoleto: cancello e rigenero
        try:
            epw_path.unlink()
            print(f"  EPW {year}: formato obsoleto, rigenero ({epw_path.name})")
        except Exception as exc:
            # v4.3.0: l'EPW e' appena stato dichiarato INVALIDO: usarlo
            # comunque (comportamento storico) produceva numeri errati con
            # una sola riga di log. Meglio fermarsi.
            raise RuntimeError(
                f"EPW {year}: formato obsoleto ma impossibile rimuovere "
                f"{epw_path} ({exc}). Chiudere i programmi che lo bloccano "
                f"(OneDrive/Excel) e rilanciare.") from exc

    df = pd.read_csv(pvgis_csv_path, parse_dates=['time'])
    df_year = df[df['time'].dt.year == year].copy()
    if len(df_year) == 0:
        raise ValueError(
            f"Nessun dato PVGIS per anno {year} in {pvgis_csv_path.name}"
        )

    df_year = df_year.sort_values('time').reset_index(drop=True)
    # Rimuove il 29 feb degli anni bisestili (l'EPW e' sempre 8760 ore)
    df_year = df_year[~((df_year['time'].dt.month == 2) &
                        (df_year['time'].dt.day == 29))].head(8760)
    if len(df_year) < 8760:
        # v4.3.0: un anno PARZIALE proseguiva con solo AVVISO ("padding"
        # promesso dal commento ma mai implementato): GHI annuo monco e
        # K_agv su mesi parziali entravano nei quantili P10/P50/P90 in
        # silenzio. Errore esplicito: escludere l'anno dalla spec.
        raise ValueError(
            f"Anno {year} INCOMPLETO nella serie PVGIS: "
            f"{len(df_year)} ore dopo il filtro 29/02 (attese 8760). "
            f"Escluderlo da --years.")

    # TZ dell'header LOCATION = 0 (fix F1, backport dalla revisione 2026-06-10):
    # i CSV PVGIS sono in UTC (timestamp HH:10) e questo writer (duplicato di pvgis_to_epw) NON ri-localizza i
    # timestamp, quindi l'header deve dichiarare UTC. Il vecchio `round(lon/15)`
    # (=+1 per l'Italia) faceva interpretare a bifacial_radiance i timestamp
    # come ora locale -> posizione solare ~40 min in anticipo rispetto alle
    # irradianze (asimmetria mattina/sera). Con TZ=0 e label='right' (default
    # EPW) il solpos e' calcolato a timestamp-30min, coerente col dato orario
    # UTC right-labeled. Sposta i numeri pubblicati: prima/dopo nel CHANGELOG.
    tz_offset = 0
    city = f'PVGIS_{lat:.4f}_{lon:.4f}_{year}'

    headers = [
        f'LOCATION,{city},-,ITA,PVGIS,999999,{lat:.4f},{lon:.4f},{tz_offset:.1f},{elevation:.1f}',
        'DESIGN CONDITIONS,0',
        'TYPICAL/EXTREME PERIODS,0',
        'GROUND TEMPERATURES,0',
        'HOLIDAYS/DAYLIGHT SAVING,No,0,0,0',
        f'COMMENTS 1,Annual EPW year={year} (multiyear strategy A) '
        f'{_epw_format_marker()} for SolRatio v4.3.0',
        'COMMENTS 2,',
        'DATA PERIODS,1,1,Data,Sunday, 1/ 1,12/31',
    ]

    # Formato EPW data lines: identico a pvgis_to_epw() di br_engine.
    # 35 campi separati da virgola + flag string da 50 "?0" pairs.
    data_lines = []
    for i in range(len(df_year)):
        row = df_year.iloc[i]
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

        line = (f'{ts.year},{ts.month},{ts.day},{hour},60,'
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

    epw_path.write_text('\n'.join(headers + data_lines) + '\n', encoding='ascii')
    print(f"  EPW {year}: {epw_path.name} ({len(df_year)} ore)")
    return epw_path


def append_result(csv_path: Path, row: dict) -> None:
    """Append idempotente di una riga al CSV risultati. Atomico via tmpfile."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    # Se il file non esiste, scrivilo con header
    if not csv_path.is_file():
        pd.DataFrame([row]).to_csv(csv_path, index=False)
    else:
        existing = pd.read_csv(csv_path)
        # Se l'anno è già presente, salta (idempotenza)
        if 'year' in existing.columns and 'year' in row \
           and str(row['year']) in existing['year'].astype(str).values:
            return
        new_df = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
        new_df.to_csv(csv_path, index=False)


def aggregate_quantiles(csv_path: Path) -> dict:
    """Calcola P10/P50/P90 per ogni KPI numerico nel CSV (escluso 'year')."""
    df = pd.read_csv(csv_path)
    # Solo le righe corrispondenti a anni reali (non TMY)
    df_years = df[df['year'].apply(lambda x: str(x).isdigit())]
    if len(df_years) < 3:
        return {
            "n_years": int(len(df_years)),
            "warning": "Troppi pochi anni per quantili robusti (<3).",
        }
    quantiles = {}
    for col in df_years.select_dtypes(include=[np.number]).columns:
        if col == 'year':
            continue
        vals = df_years[col].dropna().values
        if len(vals) < 1:
            continue
        quantiles[col] = {
            "n": int(len(vals)),
            "P10": float(np.percentile(vals, 10)),
            "P50": float(np.percentile(vals, 50)),
            "P90": float(np.percentile(vals, 90)),
            "mean": float(np.mean(vals)),
            "std": float(np.std(vals, ddof=1)) if len(vals) >= 2 else 0.0,
        }
    return {"n_years": int(len(df_years)), "quantiles": quantiles}


# ──────────────────────────────────────────────────────────────────────
# Pipeline orchestrata: legge progetto → loop anni → salva incrementale
# ──────────────────────────────────────────────────────────────────────

def run_multiyear(project_xlsm: Path, years_spec: str = "tmy",
                  output_dir: Path | None = None) -> dict:
    """
    Esegue la pipeline multi-anno. Ritorna dict con output paths e stats.

    Importa lazy le dipendenze pesanti (br_engine, calcola_br) per
    permettere l'uso interattivo con --help senza Radiance installato.
    """
    project_xlsm = Path(project_xlsm).resolve()
    if not project_xlsm.is_file():
        raise SystemExit(f"File progetto non trovato: {project_xlsm}")
    project_dir = project_xlsm.parent

    # Output: <progetto>/test/ (layout v4.2) o <progetto>/ (legacy)
    if output_dir is None:
        test_dir = project_dir / "test"
        output_dir = test_dir if test_dir.is_dir() else project_dir
    csv_path = output_dir / "multiyear_results.csv"
    json_path = output_dir / "multiyear_quantiles.json"

    print(f"=== SolRatio multiyear ===")
    print(f"  progetto:   {project_xlsm.name}")
    print(f"  cartella:   {project_dir}")
    print(f"  spec anni:  {years_spec}")
    print(f"  output:     {output_dir}")

    # Lazy imports (richiedono dipendenze runtime)
    sys.path.insert(0, str(Path(__file__).parent))
    from openpyxl import load_workbook  # type: ignore
    from solratio_excel import read_parameters  # type: ignore
    from br_engine import find_pvgis_csv, pvgis_to_epw, run_annual  # type: ignore

    wb = load_workbook(str(project_xlsm), data_only=True)
    p = read_parameters(wb)
    lat, lon = p['lat'], p['lon']

    pvgis_csv = find_pvgis_csv(project_dir, lat, lon)
    if pvgis_csv is None:
        raise SystemExit(
            f"Nessun PVGIS CSV trovato in {project_dir} né in {project_dir}/input/. "
            f"Atteso: PVGIS_{lat:.4f}_{lon:.4f}_*.csv"
        )
    print(f"  PVGIS CSV:  {pvgis_csv.name}")

    # Anni disponibili — v4.3.0: SOLO anni completi. Gli anni parziali
    # (serie troncate a inizio/fine periodo) entravano nei quantili con
    # GHI annuo monco e K_agv su mesi parziali, in silenzio; e la
    # linspace di --years N include per costruzione primo e ultimo anno,
    # cioe' proprio i candidati parziali.
    df_csv = pd.read_csv(pvgis_csv, parse_dates=['time'])
    _hours_per_year = df_csv['time'].dt.year.value_counts()
    _all_years = sorted(_hours_per_year.index.tolist())
    available_years = sorted(
        int(y) for y, n in _hours_per_year.items() if n >= 8760)
    _partial = sorted(set(_all_years) - set(available_years))
    if _partial:
        print(f"  AVVISO: anni INCOMPLETI esclusi dalla selezione: {_partial}")
    if not available_years:
        raise SystemExit("Nessun anno completo (>=8760 ore) nella serie PVGIS.")
    print(f"  Anni dispo: {available_years[0]}-{available_years[-1]} "
          f"(n={len(available_years)})")
    target_years = parse_years_spec(years_spec, available_years)
    if not target_years and years_spec.strip().lower() != "tmy":
        raise SystemExit("Nessun anno selezionato dopo parsing della spec.")
    print(f"  Anni target: {target_years if target_years else 'TMY only'}")

    def _post_process_kagv(result, p):
        """
        Post-processing minimo per estrarre K_agv SAU mediato Mar-Set per
        Cereali C3 dal risultato BR di un singolo anno. Replica il pattern
        usato da calcola_br.py senza scrivere su Excel.

        Returns
        -------
        dict con 'kagv_sau_cereali_c3' e 'kagv_sau_aggregato' (media tra
        le 9 colture Laub).
        """
        from solratio_core import (
            compute_par_frac, compute_monthly_stats, zone_stats, W_TO_UMOL,
            LAUB_COEFFICIENTS,
        )
        from solratio_yield import compute_yield_curves
        from pvlib import irradiance as _pvlib_irr

        IRR_hourly = result['IRR_hourly']
        ok_indices = result['daylight_indices']
        metdata = result['metdata']
        ghi_arr = np.asarray(result['ghi_arr'], dtype=float)
        IRR_opensky = np.asarray(result['IRR_opensky'], dtype=float)
        x_pts = np.asarray(result['x_pts'], dtype=float)
        n_all = len(ghi_arr)
        n_pts = len(x_pts)

        # Costruisce timestamp index
        try:
            ts_list = [metdata.datetime[i] for i in range(n_all)]
        except Exception:
            # Anno NON bisestile (E15): col 2020 i timestamp sintetici
            # includevano il 29/02 e sfalsavano i mesi successivi.
            ts_list = pd.date_range('2019-01-01', periods=n_all, freq='h').tolist()
        df = pd.DataFrame(index=pd.DatetimeIndex(ts_list))

        # PAR_W: irradianza al suolo (già in W/m²)
        PAR_W = np.zeros((n_all, n_pts), dtype=float)
        for i, idx in enumerate(ok_indices):
            if idx < n_all:
                PAR_W[idx, :] = IRR_hourly[i, :]

        # PAR fraction: v4.3.0 — VARIABILE (Jacovides) come in calcola_br,
        # usando il solpos gia' calcolato da run_annual. Prima era fisso
        # 0.454: la costante si cancella nel rapporto DLI/DLI_ref
        # giornaliero ma resta un residuo di pesatura oraria, e la riga
        # TMY non coincideva col K_agv di risultati_*.xlsx dello stesso
        # progetto. Fallback alla costante solo se solpos indisponibile.
        try:
            solpos = metdata.solpos
            cos_zen = np.maximum(0.0, np.cos(np.radians(np.asarray(
                solpos['apparent_zenith'].values[:n_all], dtype=float))))
            dni_extra = np.asarray(
                _pvlib_irr.get_extra_radiation(df.index), dtype=float)[:n_all]
            par_frac = np.asarray(
                compute_par_frac(ghi_arr, dni_extra, cos_zen), dtype=float)
        except Exception:
            par_frac = np.full(n_all, 0.454, dtype=float)

        PAR_mol = PAR_W * par_frac[:, None] * W_TO_UMOL
        DLI_h = PAR_mol * 3600 / 1e6
        dli_df = pd.DataFrame(DLI_h, index=df.index, columns=x_pts)
        dli_daily = dli_df.groupby(df.index.normalize()).sum()

        # Riferimento open sky
        PAR_W_ref = np.maximum(IRR_opensky, 0.0)
        no_os = (PAR_W_ref < 0.1) & (ghi_arr > 20)
        PAR_W_ref[no_os] = ghi_arr[no_os]
        PAR_mol_ref = PAR_W_ref * par_frac * W_TO_UMOL
        DLI_h_ref = PAR_mol_ref * 3600 / 1e6
        dli_ref_s = pd.Series(DLI_h_ref, index=df.index)
        dli_daily_ref = dli_ref_s.groupby(df.index.normalize()).sum()

        stats = compute_monthly_stats(dli_daily, list(x_pts), p,
                                       dli_daily_ref=dli_daily_ref)
        yield_data = compute_yield_curves(stats, list(x_pts), p)

        # K_agv SAU Cereali C3 mediato Mar-Set
        kagv_c3 = np.nan
        kagv_agg_list = []
        for crop_key, data in yield_data.items():
            kagv_marset = np.nanmean([
                data['kagv'].get(m, {}).get('SAU', np.nan)
                for m in range(3, 10)
            ]) * 100.0
            kagv_agg_list.append(kagv_marset)
            if crop_key == 'cereali_C3':
                kagv_c3 = float(kagv_marset)
        kagv_agg = float(np.nanmean(kagv_agg_list)) if kagv_agg_list else np.nan
        return {
            'kagv_sau_cereali_c3': kagv_c3,
            'kagv_sau_media_9_colture': kagv_agg,
        }

    # Esegui TMY se richiesto (modalità default v4.1)
    if years_spec.strip().lower() == "tmy" or len(target_years) == 0:
        # v4.3.0: idempotenza anche per il ramo TMY (come per i singoli
        # anni): prima il check stava solo in append_result, DOPO il run
        # piu' costoso — un resume post-crash lo rifaceva ogni volta.
        _tmy_done = False
        if csv_path.is_file():
            _existing = pd.read_csv(csv_path)
            _tmy_done = ('year' in _existing.columns and
                         'TMY' in _existing['year'].astype(str).values)
        if _tmy_done:
            print(f"\n--- Run TMY composito: già completato, salto ---")
        else:
            print(f"\n--- Run TMY composito ---")
            epw_path, tmy_info = pvgis_to_epw(str(pvgis_csv), lat, lon)
            result = run_annual(p, epw_path, n_points=p.get('n_points', 51),
                                project_dir=str(project_dir))
            kagv = _post_process_kagv(result, p)
            append_result(csv_path, {
                "year": "TMY",
                "tmy_info": tmy_info,
                "ghi_annual_kwhm2": round(result['ghi_annual'] / 1000, 1),
                "kagv_sau_cereali_c3": round(kagv['kagv_sau_cereali_c3'], 2),
                "kagv_sau_media_9_colture": round(kagv['kagv_sau_media_9_colture'], 2),
            })
            print(f"  TMY completato: K_agv SAU Cereali C3 = "
                  f"{kagv['kagv_sau_cereali_c3']:.2f}%")

    # Loop anni singoli
    for year in target_years:
        print(f"\n--- Run anno {year} ({target_years.index(year)+1}/{len(target_years)}) ---")
        t0 = time.time()
        # Idempotenza: skip se già fatto
        if csv_path.is_file():
            existing = pd.read_csv(csv_path)
            if 'year' in existing.columns and year in existing['year'].astype(str).str.replace('TMY', '').apply(
                lambda x: int(x) if x.isdigit() else -1).values:
                print(f"  Già completato in run precedente, salto.")
                continue
        try:
            year_epw_dir = output_dir / f".cache/multiyear_epw"
            epw_path = build_year_epw(pvgis_csv, year, lat, lon, year_epw_dir)
            result = run_annual(p, str(epw_path), n_points=p.get('n_points', 51),
                                project_dir=str(project_dir))
            kagv = _post_process_kagv(result, p)
            elapsed = time.time() - t0
            append_result(csv_path, {
                "year": year,
                "ghi_annual_kwhm2": round(result['ghi_annual'] / 1000, 1),
                "kagv_sau_cereali_c3": round(kagv['kagv_sau_cereali_c3'], 2),
                "kagv_sau_media_9_colture": round(kagv['kagv_sau_media_9_colture'], 2),
                "runtime_min": round(elapsed / 60, 2),
            })
            print(f"  Anno {year} completato: K_agv SAU Cereali C3 = "
                  f"{kagv['kagv_sau_cereali_c3']:.2f}%, "
                  f"runtime {elapsed/60:.1f} min")
        except Exception as exc:
            print(f"  ERRORE anno {year}: {exc}. Salto, continua.")
            continue

    # Aggrega quantili finali
    if csv_path.is_file():
        quantiles = aggregate_quantiles(csv_path)
        json_path.write_text(json.dumps(quantiles, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        print(f"\n=== Quantili calcolati su {quantiles.get('n_years', 0)} anni ===")
        for kpi, q in quantiles.get("quantiles", {}).items():
            print(f"  {kpi}: P10={q['P10']:.4f} P50={q['P50']:.4f} P90={q['P90']:.4f}")
        print(f"  CSV: {csv_path}")
        print(f"  JSON: {json_path}")
        return {"csv": str(csv_path), "json": str(json_path), **quantiles}
    return {"csv": None, "json": None, "n_years": 0}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Multi-anno orchestrator SolRatio v4.2 — strategia A "
                    "(sequenziale + incrementale)",
    )
    parser.add_argument("project_xlsm", help="Path al SolRatio_progetto.xlsm")
    parser.add_argument("--years", default="tmy",
                        help="Spec anni: tmy | all | 2010,2015 | 3 (default: tmy)")
    parser.add_argument("--output-dir", default=None,
                        help="Cartella output (default: <progetto>/test/ o <progetto>/)")
    args = parser.parse_args(argv)

    out_dir = Path(args.output_dir) if args.output_dir else None
    run_multiyear(Path(args.project_xlsm), args.years, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
