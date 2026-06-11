"""
solratio_core.py  |  SolRatio v4.3.0 (2026-06-11)
====================================================
Modello fisico: posizione solare, ray-tracing, view factor, PAR/DLI,
statistiche mensili, decomposizione diffusa Perez, self-test.

Novita v3.3.4:
  - Analisi sensitivita: UserForm VBA con selezione parametri, range Min/Max
    editabili, n. livelli OAT, delta% tornado, coltura selezionabile (9 Laub)
  - 13 parametri in 4 categorie (Strutturali, Ottici, Terreno/Asse, Geografici)
  - Parametri effetto bordo esclusi (non integrati nel loop sensitivita)
  - Fix tornado con base_val=0 (slope_pct, axis_azimuth): delta assoluto dal range
  - Cache PVGIS in Morris: dict (lat,lon)->df, evita ri-download ripetuti
  - Validazione range custom CLI: min<max, clip a limiti assoluti
  - Riepilogo configurazione nel foglio Excel OAT (parametri, livelli, GCR)
  - Progresso per-livello OAT per parametri PVGIS lenti
  - CLI: --crop, --params, --levels, --delta_tornado

Novita v3.3.3:
  - PAR_FRAC variabile con clearness index (Jacovides et al. 2004):
    compute_par_frac(ghi, dni_extra, cos_z) → array orario 0.42-0.48
  - PVGIS con surface_tilt=0: ottiene GHI/DNI/DHI diretti, elimina fallback Erbs
  - Warning quantitativo per fallback Erbs (CSV vecchio formato)
  - Fix ombra pali: sin(az-180) → sin(az-axis_azimuth) per asse arbitrario
  - Limitazioni modello ampliate con stime quantitative
  - PDF: pagina descrizione modello con glossario e riferimenti
  - Script validazione forma rettangolare (documentazione/)

Novità v3.3.2:
  - Fix: write_effetto_bordo area fascia fantasma quando sau_esterna=0
  - Fix: compute_kagv_impianto weights con tag espliciti (is_tracker)
  - Fix: panel_axes_outer rinomina n_right → n_internal (chiarezza)
  - Fix: conteggio assertion nella documentazione (215 → 150)
  - Test: aggiunto test 19 end-to-end edge + compute_kagv_impianto

Novità v3.3.1:
  - Fix: crash write_effetto_bordo quando outer_profile=None (SAU_esterna=0)
  - Fix: zone_masks errato per fascia esterna (domain_pitch parametrico)
  - Fix: optimize_pitch usa cos_incidence (slope-aware) anziché cos_z
  - compute_irradiance_matrix: formula irradianza al suolo unificata (elimina duplicazione)
  - compute_vf_matrix/compute_shadow_matrix: parametro axes_override
  - solratio_edge: rimossi duplicati _compute_vf/shadow_with_axes (~200 righe)
  - Test: aggiunta suite test_edge (solratio_edge.py)
  - Test 16: aggiunto solratio_edge.py, fix filename guida

Novità v3.3.0:
  - Effetto bordo semplificato (modulo solratio_edge.py):
    N_file, L_tracker, SAU_esterna → profili file perimetrali,
    correzione N-S, K_agv medio impianto
  - Fix: phi_p docstring sign convention allineato al codice
  - optimize_pitch con Perez (pre-calcolato, nessun overhead nel loop)
  - optimize_pitch target_months allineato a Mar-Set (coerente con Riepilogo)

Novità v3.2:
  - axis_azimuth parametrico (B27, default 180° = asse N-S)
  - phi_p generalizzato per asse tracker con orientamento arbitrario
  - Retrocompatibile: axis_azimuth=180 produce risultati identici a v3.1

Nessuna dipendenza da openpyxl — solo numpy, pandas, pvlib.
"""

import os
import numpy as np
import pandas as pd
import pvlib
from pvlib import tracking
from pvlib.bifacial.utils import vf_ground_sky_2d
from pvlib.shading import projected_solar_zenith_angle

# ══════════════════════════════════════════════════════════════════════════════
# VERSIONE (fonte unica: file VERSION nella cartella engine/)
# Tutti i moduli Python importano __version__ da qui.
# Il VBA legge la versione da GetVersion() (unico punto VBA).
# Il test 16 verifica la coerenza tra VERSION, Python, VBA e documentazione.
# ══════════════════════════════════════════════════════════════════════════════

def _read_version():
    """Legge la versione dal file VERSION nella stessa cartella di solratio_core.py."""
    version_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'VERSION')
    try:
        with open(version_path, encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return '0.0.0'  # fallback se VERSION mancante

__version__ = _read_version()

# ══════════════════════════════════════════════════════════════════════════════
# COSTANTI
# ══════════════════════════════════════════════════════════════════════════════

MONTHS     = ['Gen','Feb','Mar','Apr','Mag','Giu',
              'Lug','Ago','Set','Ott','Nov','Dic']

# Frazione PAR (400-700 nm) dello spettro solare globale.
# Valore costante 0.45 mantenuto come default e fallback.
# La funzione compute_par_frac() calcola il valore orario in funzione del
# clearness index kt = GHI / GHI_extraterrestre (Jacovides et al. 2004):
#   kt basso (coperto)  → PAR_FRAC ~ 0.48
#   kt alto (sereno)    → PAR_FRAC ~ 0.42
# Rif: McCree K.J. (1972) Agric. Meteorol. 9:191-216;
#      Papaioannou G. et al. (1993) Agric. For. Meteorol. 66:101-113;
#      Jacovides C.P. et al. (2004) Agric. For. Meteorol. 127:65-80.
PAR_FRAC   = 0.45

# Fattore di conversione energia radiante -> densita di flusso fotonico PAR.
# 4.57 umol fotoni per Joule di radiazione solare a spettro naturale (400-700 nm).
# Derivazione: media ponderata dell'energia per fotone sullo spettro PAR, E = hc/lambda.
# Rif: McCree K.J. (1972) Agric. Meteorol. 9:191-216;
#      Thimijan R.W. & Heins R.D. (1983) HortScience 18:818-822.
W_TO_UMOL  = 4.57


def compute_par_frac(ghi, dni_extra, cos_zenith):
    """
    Frazione PAR variabile con il clearness index kt (Jacovides et al. 2004).

    kt = GHI / (DNI_extra * cos_zenith).
    PAR_FRAC = 0.500 - 0.082 * kt, clippato in [0.42, 0.48].

    Parametri (tutti array n_times):
      ghi        : irradianza globale orizzontale [W/m2]
      dni_extra  : irradianza extraterrestre [W/m2]
      cos_zenith : cos(zenith), gia clippato >= 0

    Restituisce array (n_times,) di PAR_FRAC orario.
    Per ore notturne (cos_z ~ 0) restituisce il default 0.45.
    """
    ghi_extra = dni_extra * np.maximum(cos_zenith, 0.0)
    kt = np.where(ghi_extra > 10.0,
                  np.clip(ghi / ghi_extra, 0.0, 1.0),
                  0.6)   # default kt per ore con sole basso
    return np.clip(0.500 - 0.082 * kt, 0.42, 0.48)

TZ         = 'UTC'     # v2.3: lavora in UTC (PVGIS fornisce dati in UTC,
                        # pvlib calcola posizione solare da coordinate+UTC)
PALETTE    = ['1F4E79','2E75B6','70AD47','A9D18E','FFC000','FF0000',
              'C00000','FF7C00','ED7D31','7030A0','4472C4','9DC3E6']


def _utc_offset_from_lon(lon):
    """
    Stima l'offset UTC (ore intere) dalla longitudine.
    Approssimazione: offset = round(lon / 15).
    Accurata per la maggior parte dei fusi orari standard.
    Non tiene conto dell'ora legale.
    """
    return int(round(lon / 15.0))


def _hour_label(utc_hour, lon):
    """
    Restituisce una stringa con ora UTC e ora locale stimata.
    Es: '09:00 UTC (11:00 loc)' per lon=30°E.
    """
    offset = _utc_offset_from_lon(lon)
    local_h = (utc_hour + offset) % 24
    sign = '+' if offset >= 0 else ''
    return f'{utc_hour:02d}:00 UTC ({local_h:02d}:00 loc, UTC{sign}{offset})'

def _compute_phi_p_scalar(elev, az, axis_azimuth=180.0):
    """
    Angolo di profilo φ_p con segno per un singolo timestep.

    v3.2: generalizzato per axis_azimuth arbitrario.
    Il piano di profilo è perpendicolare all'asse tracker.

    Convenzione:
      φ_p > 0  quando sin(az - axis_azimuth) <= 0
               (per axis_azimuth=180: sole a est, mattina → ombra verso ovest)
      φ_p < 0  quando sin(az - axis_azimuth) > 0
               (per axis_azimuth=180: sole a ovest, pomeriggio → ombra verso est)

    Parametri:
      elev : elevazione solare apparente [°]
      az   : azimut solare [°]
      axis_azimuth : orientamento asse tracker [°da Nord], default 180

    Restituisce:
      float φ_p [°], 0 se elevazione ≤ 2°.
    """
    if elev <= 2.0:
        return 0.0
    alt_r = np.radians(np.clip(elev, 0, 90))
    az_cross_r = np.radians(az - axis_azimuth)
    # R4 (v4.2.2): la componente TRASVERSALE all'asse e' |sin(az-axis)|
    # (con |cos| si otteneva la proiezione longitudinale: d~0 con sole a
    # est su asse N-S — contraddiceva pvlib PSZA, dossier R4).
    sin_az_cross = max(0.01, abs(np.sin(az_cross_r)))
    magnitude = np.degrees(np.arctan(np.tan(alt_r) / sin_az_cross))
    sign = 1.0 if np.sin(az_cross_r) <= 0 else -1.0
    return magnitude * sign


# Compatibilità NumPy 1.x / 2.x
_trapz = getattr(np, 'trapezoid', None) or getattr(np, 'trapz', None)


def compute_slope_components(slope_pct, slope_azimuth, axis_azimuth=180.0):
    """
    Calcola le componenti trasversale (cross, E-O) e longitudinale (along, N-S)
    della pendenza rispetto all'asse tracker.

    Parametri:
      slope_pct      : pendenza terreno [%]
      slope_azimuth  : azimut direzione di discesa [° da Nord]
      axis_azimuth   : orientamento asse tracker [° da Nord], default 180

    Restituisce:
      (slope_angle, slope_cross_deg, slope_along_deg, slope_cross_rad)
    """
    slope_rad = np.arctan(slope_pct / 100.0)
    slope_angle = np.degrees(slope_rad)
    delta_az = np.radians(slope_azimuth - axis_azimuth)
    slope_cross_deg = np.degrees(np.arctan(np.tan(slope_rad) * np.sin(delta_az)))
    slope_along_deg = np.degrees(np.arctan(np.tan(slope_rad) * np.cos(delta_az)))
    slope_cross_rad = np.radians(slope_cross_deg)
    return slope_angle, slope_cross_deg, slope_along_deg, slope_cross_rad

# ══════════════════════════════════════════════════════════════════════════════
# COEFFICIENTI RESA COLTURALE -- Laub et al. (2022)
# ══════════════════════════════════════════════════════════════════════════════
# Modello: Y_rel = 10^(2 + α·RSR + β·RSR²),  RSR in [0,1], Y_rel in %
# Calibrati da Table S2 tramite curve_fit (RMSE < 1.6% per tutte le tipologie)
# Rif: Laub et al., Agron. Sustain. Dev., 42:51 (2022)
# Dataset: doi:10.5281/zenodo.5716091

LAUB_COEFFICIENTS = {
    'bacche':              {'alpha':  0.4318, 'beta': -0.7337, 'label_it': 'Bacche',              'label_en': 'Berries'},
    'frutta':              {'alpha':  0.4330, 'beta': -0.7690, 'label_it': 'Frutta',              'label_en': 'Fruits'},
    'ortaggi_frutto':      {'alpha':  0.3171, 'beta': -0.7565, 'label_it': 'Ortaggi da frutto',   'label_en': 'Fruity vegetables'},
    'foraggere':           {'alpha':  0.1945, 'beta': -0.6835, 'label_it': 'Foraggere',           'label_en': 'Forages'},
    'ortaggi_foglia':      {'alpha':  0.2153, 'beta': -0.9377, 'label_it': 'Ortaggi da foglia',   'label_en': 'Leafy vegetables'},
    'tuberi_radici':       {'alpha':  0.1101, 'beta': -0.8653, 'label_it': 'Tuberi/radici',       'label_en': 'Tubers/root crops'},
    'cereali_C3':          {'alpha':  0.0310, 'beta': -0.9341, 'label_it': 'Cereali C3',          'label_en': 'C3 cereals'},
    'leguminose_granella': {'alpha': -0.1285, 'beta': -1.5675, 'label_it': 'Leguminose granella', 'label_en': 'Grain legumes'},
    'mais':                {'alpha': -0.3169, 'beta': -1.4154, 'label_it': 'Mais (C4)',           'label_en': 'Maize (C4)'},
}


def laub_yield(rsr, crop_key):
    """Resa relativa (%) per data RSR e tipologia colturale (Laub et al. 2022)."""
    c = LAUB_COEFFICIENTS[crop_key]
    rsr = np.clip(np.asarray(rsr, dtype=float), 0.0, 1.0)
    return np.clip(np.power(10.0, 2.0 + c['alpha'] * rsr + c['beta'] * rsr**2), 0, 200)

# ══════════════════════════════════════════════════════════════════════════════
# ACQUISIZIONE DATI PVGIS
# ══════════════════════════════════════════════════════════════════════════════

def _probe_pvgis_year_range(lat, lon):
    """Interroga PVGIS per scoprire l'intervallo anni SARAH3 disponibile.
    Fa una richiesta con anni volutamente errati e parsa il messaggio di errore.
    Ritorna (yr_min, yr_max) o (None, None) se non riesce."""
    import re
    try:
        import requests
        url = 'https://re.jrc.ec.europa.eu/api/v5_3/seriescalc'
        params = {'lat': lat, 'lon': lon, 'startyear': 1900, 'endyear': 2099, 'raddatabase': 'PVGIS-SARAH3', 'outputformat': 'json'}
        r = requests.get(url, params=params, timeout=15)
        m = re.search(r'between\s+(\d{4})\s+and\s+(\d{4})', r.text)
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception:
        pass
    return None, None


def get_pvgis_data(p, xlsx_dir):
    """
    Restituisce DataFrame con serie oraria PVGIS (GHI, DNI, DHI, solar_elevation).
    Cerca prima il CSV locale (layout v4.1.x in root o v4.2 in input/),
    altrimenti scarica da PVGIS e salva il CSV nella root del progetto.
    """
    # Determina percorso CSV
    csv_path = p.get('csv_path', '').strip()
    if not csv_path:
        fname = f"PVGIS_{p['lat']:.4f}_{p['lon']:.4f}_{p['yr_start']}_{p['yr_end']}.csv"
        csv_path = os.path.join(xlsx_dir, fname)
        # v4.2 item 5: se non esiste in root, prova layout standardizzato
        # con CSV in <xlsx_dir>/input/
        if not os.path.exists(csv_path):
            input_csv_path = os.path.join(xlsx_dir, 'input', fname)
            if os.path.exists(input_csv_path):
                csv_path = input_csv_path
            else:
                # Fallback più ampio: usa find_pvgis_csv se disponibile
                # (gestisce match approssimato sui nomi PVGIS_*.csv).
                try:
                    from br_engine import find_pvgis_csv
                    found = find_pvgis_csv(xlsx_dir, p['lat'], p['lon'])
                    if found is not None:
                        csv_path = str(found)
                except Exception:
                    pass

    if os.path.exists(csv_path):
        print(f"  CSV PVGIS trovato: {csv_path}")
        print(f"  Caricamento dati...", end=' ')
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        # Gestione timezone robusta: il CSV potrebbe avere indice
        # tz-aware (UTC) o tz-naive. Normalizziamo a UTC.
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        elif str(df.index.tz) != 'UTC':
            df.index = df.index.tz_convert('UTC')
        print(f"{len(df):,} ore caricate.")
        # v4.3.0: un CSV senza le colonne richieste NON va restituito
        # (prima: solo ATTENZIONE e df inutilizzabile -> KeyError oscuro
        # a valle). Servono ghi+dni+dhi; in mancanza, errore esplicito.
        _missing = [c for c in ('ghi', 'dni', 'dhi') if c not in df.columns]
        if _missing:
            raise ValueError(
                f"Il CSV PVGIS non contiene le colonne {_missing} "
                f"(vecchio formato solo-POA?). Cancellare il file e "
                f"rilanciare il calcolo per riscaricarlo nel formato "
                f"corrente. File: {csv_path}")
        return df

    # Download da PVGIS
    print(f"  CSV PVGIS non trovato. Download da PVGIS API...")
    print(f"  Posizione: lat={p['lat']}, lon={p['lon']}")
    print(f"  Periodo: {p['yr_start']}-{p['yr_end']}")
    print(f"  (questa operazione richiede ~20-40 secondi)")

    try:
        # PVGIS-SARAH3: verifica dinamica intervallo disponibile
        yr_end_sarah3 = p['yr_end']
        if p['yr_start'] > p['yr_end']:
            raise RuntimeError(
                f'Anno inizio ({p["yr_start"]}) > anno fine ({p["yr_end"]})')

        pvgis_min, pvgis_max = _probe_pvgis_year_range(p['lat'], p['lon'])
        if pvgis_min and pvgis_max:
            print(f"  PVGIS-SARAH3 disponibile: {pvgis_min}-{pvgis_max}")
            if p['yr_start'] < pvgis_min:
                raise ValueError(
                    f"Anno inizio {p['yr_start']} fuori range PVGIS ({pvgis_min}-{pvgis_max}). "
                    f"Impostare B41 >= {pvgis_min}.")
            if yr_end_sarah3 > pvgis_max:
                raise ValueError(
                    f"Anno fine {yr_end_sarah3} fuori range PVGIS ({pvgis_min}-{pvgis_max}). "
                    f"Impostare B42 <= {pvgis_max}.")
        
        # PVGIS-SARAH3: tenta di ottenere GHI/DNI/DHI diretti.
        # Strategia 1: surface_tilt=0 + components=True → G(h), Gb(n), Gd(h)
        # Strategia 2: se pvlib non supporta surface_tilt, components=True senza tilt
        #              → POA components → fallback Erbs (gia implementato sotto)
        try:
            data, metadata = pvlib.iotools.get_pvgis_hourly(
                latitude      = p['lat'],
                longitude     = p['lon'],
                start         = p['yr_start'],
                end           = yr_end_sarah3,
                raddatabase   = 'PVGIS-SARAH3',
                components    = True,
                surface_tilt  = 0,
                surface_azimuth = 180,
                outputformat  = 'json',
                usehorizon    = True,
                map_variables = False,
            )
        except TypeError:
            # Versione pvlib che non supporta surface_tilt → fallback senza
            print("  NOTA: pvlib non supporta surface_tilt, download senza.")
            data, metadata = pvlib.iotools.get_pvgis_hourly(
                latitude      = p['lat'],
                longitude     = p['lon'],
                start         = p['yr_start'],
                end           = yr_end_sarah3,
                raddatabase   = 'PVGIS-SARAH3',
                components    = True,
                outputformat  = 'json',
                usehorizon    = True,
                map_variables = False,
            )
    except Exception as e:
        raise RuntimeError(
            f"Download PVGIS fallito: {e}\n"
            f"Verifica connessione internet o inserisci manualmente il percorso CSV "
            f"nella cella B43 del foglio Parametri."
        )

    # Stampa colonne reali per diagnostica
    print(f"  Colonne PVGIS ricevute: {list(data.columns)}")

    # Normalizza nomi colonne
    col_map = {
        'G(h)': 'ghi', 'Gb(n)': 'dni', 'Gd(h)': 'dhi',
        'ghi': 'ghi', 'dni': 'dni', 'dhi': 'dhi',
        'Gb(i)': 'poa_direct', 'Gd(i)': 'poa_sky_diffuse', 'Gr(i)': 'poa_ground_diffuse',
        'G(i)': 'poa_global',
        'H_sun': 'solar_elevation', 'solar_elevation': 'solar_elevation',
        'T2m': 'temp_air', 'temp_air': 'temp_air',
        'WS10m': 'wind_speed', 'wind_speed': 'wind_speed',
    }
    data = data.rename(columns={c: col_map[c] for c in data.columns if c in col_map})
    print(f"  Colonne dopo rinomina: {list(data.columns)}")

    # --- Derivazione GHI/DNI/DHI -------------------------------------------
    # SARAH3 con components=True fornisce solo componenti sul piano inclinato
    # (poa_direct, poa_sky_diffuse, poa_ground_diffuse).
    # GHI si ricava come: GHI = poa_direct * cos(zenith) + poa_sky_diffuse + poa_ground_diffuse
    # DNI e DHI si derivano con il modello Erbs (1982) da GHI e zenith.
    if 'ghi' not in data.columns:
        if all(c in data.columns for c in ['poa_direct', 'poa_sky_diffuse', 'poa_ground_diffuse']):
            print("  GHI/DNI/DHI non disponibili direttamente: derivazione da componenti POA (Erbs)...")
            # Calcola posizione solare per ottenere zenith
            loc = pvlib.location.Location(
                latitude=p['lat'], longitude=p['lon'], tz='UTC'
            )
            solar_pos = loc.get_solarposition(data.index)
            zenith = solar_pos['apparent_zenith']
            cos_z = np.cos(np.radians(zenith)).clip(0)
            # GHI = DNI*cos(z) + DHI; approssimazione da POA orizzontale
            # Con surface_tilt=0: poa_direct = DNI*cos(z), poa_sky_diffuse ~ DHI
            data['dni'] = data['poa_direct'] / cos_z.where(cos_z > 0.01, np.nan)
            data['dni'] = data['dni'].fillna(0).clip(0)
            data['dhi'] = data['poa_sky_diffuse'].clip(0)
            data['ghi'] = (data['dni'] * cos_z + data['dhi']).clip(0)
            print(f"  GHI medio annuo stimato: {data['ghi'].mean()*8760/1000:.0f} kWh/m2/anno")
            print(f"  NOTA: GHI/DNI/DHI derivati da componenti POA con fallback Erbs (1982).")
            print(f"  Errore stimato su DLI annuo: +/-5-8% rispetto a misure dirette GHI/DNI/DHI.")
            print(f"  Per maggiore precisione, fornire un CSV con colonne ghi, dni, dhi.")
        elif 'poa_global' in data.columns:
            # Solo G(i) disponibile - decomposizione Erbs da poa_global
            print("  Solo G(i) disponibile: decomposizione Erbs da poa_global...")
            loc = pvlib.location.Location(latitude=p['lat'], longitude=p['lon'], tz='UTC')
            solar_pos = loc.get_solarposition(data.index)
            zenith = solar_pos['apparent_zenith']
            erbs = pvlib.irradiance.erbs_driesse(data['poa_global'], zenith, data.index.dayofyear)
            data['ghi'] = data['poa_global'].clip(0)
            data['dni'] = erbs['dni'].clip(0)
            data['dhi'] = erbs['dhi'].clip(0)
            print(f"  GHI medio annuo stimato: {data['ghi'].mean()*8760/1000:.0f} kWh/m2/anno")
            print(f"  NOTA: GHI/DNI/DHI derivati da G(i) con decomposizione Erbs (1982).")
            print(f"  Errore stimato su DLI annuo: +/-8-12% (doppia approssimazione POA->GHI->Erbs).")
            print(f"  Per maggiore precisione, fornire un CSV con colonne ghi, dni, dhi.")
        else:
            raise RuntimeError(
                f"Impossibile derivare GHI/DNI/DHI. Colonne disponibili: {list(data.columns)}"
            )

    # Verifica finale
    needed = ['ghi', 'dni', 'dhi']
    missing = [c for c in needed if c not in data.columns]
    if missing:
        raise RuntimeError(f"Colonne mancanti nei dati PVGIS: {missing}")

    # Filtra ore con sole sotto orizzonte (GHI=0)
    # Mantieni tutte le righe per preservare l'indice temporale completo

    # Salva CSV
    data.to_csv(csv_path)
    print(f"  Dati salvati in: {csv_path}")
    print(f"  {len(data):,} ore scaricate ({p['yr_start']}-{p['yr_end']}).")

    return data

# ══════════════════════════════════════════════════════════════════════════════
# CALCOLO POSIZIONE SOLARE E ANGOLO TRACKER
# ══════════════════════════════════════════════════════════════════════════════

def compute_solar_and_tracker(df, p):
    """
    Aggiunge al DataFrame:
      - apparent_zenith, apparent_elevation, azimuth  (pvlib Reda & Andreas)
      - tracker_theta  (backtracking Lorenzo 2011, opzionale)
      - cos_zenith     (cos(θz), già clippato a 0)
      - phi_p          (angolo di profilo CON SEGNO: >0 = sole a est/ombra verso ovest,
                         <0 = sole a ovest/ombra verso est)
    """
    print("  Calcolo posizione solare (pvlib Reda & Andreas 2004)...", end=' ')

    loc    = pvlib.location.Location(p['lat'], p['lon'], tz=TZ, altitude=10)
    times  = df.index

    # Assicura indice UTC
    if times.tz is None:
        times = times.tz_localize(TZ)
        df.index = times
    elif str(times.tz) != TZ:
        times = times.tz_convert(TZ)
        df.index = times

    solpos = loc.get_solarposition(times)

    df['apparent_zenith']    = solpos['apparent_zenith'].values
    df['apparent_elevation'] = (90 - solpos['apparent_zenith']).values
    df['azimuth']            = solpos['azimuth'].values
    df['cos_zenith']         = np.maximum(0, np.cos(np.radians(
                                    solpos['apparent_zenith'].values)))

    # [v3.3.6] Modalità tracker (B19):
    #   0 = astronomico (θ segue il sole, limitato a ±β_max)
    #   1 = backtracking (Lorenzo 2011, auto-protezione ombra reciproca)
    #   2 = TILT FISSO (θ = θ_fix costante tutto l'anno, B46)
    bt_mode = int(p.get('backtracking', 1))
    ax_az = p.get('axis_azimuth', 180.0)

    if bt_mode == 2:
        theta_fix = float(p.get('theta_fix', 0.0))
        if abs(theta_fix) > p['beta_max'] + 0.01:
            raise ValueError(
                f"θ_fix={theta_fix}° eccede β_max={p['beta_max']}° "
                f"(cella B46 vs B18).")
        # θ costante; di notte si mantiene comunque il valore (ininfluente
        # perché f_dir=0 quando apparent_elevation≤2°)
        df['tracker_theta'] = np.full(len(df), theta_fix)
        bt_label = f'TILT FISSO θ={theta_fix:+.1f}°'
    else:
        do_backtrack = (bt_mode == 1)
        tracker_result = tracking.singleaxis(
            apparent_zenith  = solpos['apparent_zenith'],
            solar_azimuth    = solpos['azimuth'],
            # v4.3.0: parametrico come nel resto del file (PSZA e
            # sub-campioni usano p['axis_tilt']): un eventuale axis_tilt
            # impostato non deve far divergere theta principale e theta sub.
            axis_tilt        = p.get('axis_tilt', 0.0),
            axis_azimuth     = ax_az,
            max_angle        = p['beta_max'],
            backtrack        = do_backtrack,
            gcr              = p['GCR'],
        )
        df['tracker_theta'] = tracker_result['tracker_theta'].fillna(0).values
        bt_label = 'ON' if do_backtrack else 'OFF (astronomico)'

    # Angolo di profilo φ_p CON SEGNO
    # v3.2: proiettato sul piano perpendicolare all'asse tracker (axis_azimuth)
    # Per axis_azimuth=180 (N-S), il piano è E-O e φ_p è uguale alla v3.1.
    # Per axis_azimuth≠180, si proietta l'azimut solare sull'asse perpendicolare.
    # Il piano di profilo è perpendicolare all'asse tracker, cioè a (axis_azimuth + 90°).
    # L'angolo relativo del sole rispetto a questo piano è:
    #   az_cross = azimuth_sole - axis_azimuth
    # Convenzione: φ_p > 0 quando il sole è sul lato "positivo" del piano trasversale
    #              φ_p < 0 quando è sul lato "negativo"
    alt_r    = np.radians(np.clip(df['apparent_elevation'].values, 0, 90))
    az_cross_r = np.radians(df['azimuth'].values - ax_az)
    # R4 (v4.2.2): componente trasversale = |sin| (vedi _compute_phi_p_scalar)
    sin_az_cross = np.maximum(0.01, np.abs(np.sin(az_cross_r)))
    phi_magnitude = np.degrees(np.arctan(np.tan(alt_r) / sin_az_cross))
    # Segno: basato sulla posizione del sole rispetto all'asse tracker
    # Per axis_azimuth=180 (N-S): sin(az-180) < 0 quando az < 180 (sole a est) → φ_p positivo
    # Generalizzazione: il sole è sul lato "sinistro" (est per N-S) quando sin(az-axis_az) < 0
    sin_cross = np.sin(az_cross_r)
    sun_sign = np.where(sin_cross <= 0, 1.0, -1.0)
    df['phi_p'] = np.where(
        df['apparent_elevation'].values > 2.0,
        phi_magnitude * sun_sign,
        0.0
    )

    print(f"OK ({len(df):,} timestep, backtracking={bt_label}, axis_az={ax_az:.0f} deg).")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# ASSI PANNELLI SIMMETRICI
# ══════════════════════════════════════════════════════════════════════════════

def panel_axes(p):
    """
    Genera la lista degli assi dei pannelli, simmetrica rispetto al pitch 0→P.

    Il pitch simulato va da x=0 (tracker sinistro) a x=P (tracker destro).
    Si aggiungono n_ext pannelli esterni per lato:
      - a sinistra di 0:   -P, -2P, ..., -n_ext·P
      - a destra di P:     2P, 3P, ..., (n_ext+1)·P

    Totale pannelli = 2 (pitch) + 2·n_ext (esterni) = 2·(n_ext + 1)

    Es: n_ext=2 → assi: -2P, -P, 0, +P, +2P, +3P  (6 pannelli, simmetrici)
        n_ext=1 → assi: -P, 0, +P, +2P              (4 pannelli, simmetrici)
    """
    n_ext = p['n_ext']
    pitch = p['pitch']
    return np.array([i * pitch for i in range(-n_ext, n_ext + 2)])




def compute_vf_matrix(x_pts, theta_arr, p, axes_override=None):
    """
    Calcola la matrice VF(n_times x n_points) — sky view factor al suolo.

    v3.3.5: delega a pvlib.bifacial.utils.vf_ground_sky_2d (normalizzazione
    Lambert coseno-pesata, fisicamente corretta) quando possibile.

    Fallback a calcolo custom (con normalizzazione Lambert corretta) quando:
      - axes_override è specificato (pvlib assume array infinito uniforme)
      - slope_cross_rad ≠ 0 (pvlib assume terreno piano)

    axes_override: se fornito, usa questi assi pannello invece di panel_axes(p).
                   Usato da solratio_edge per profili di bordo con assi ridotti.
    """
    H     = p['H']
    W     = p['W']
    pitch = p['pitch']
    slope = p.get('slope_cross_rad', 0.0)
    use_pvlib = (axes_override is None) and (abs(slope) < 1e-6)

    if use_pvlib:
        # ── Percorso pvlib (caso standard: array uniforme, terreno piano) ──
        gcr = W / pitch
        rotation_deg = np.degrees(theta_arr)   # pvlib vuole gradi

        # Mappatura coordinate SR → pvlib:
        #   SR:    x_pts in metri, 0 = sotto il pannello (asse a x=0)
        #   pvlib: x come frazione di pitch, 0 = sotto il centro del pannello
        # Il primo asse SR è a x=0, quindi x_frac = x/pitch.
        x_frac = np.array(x_pts) / pitch          # (n_points,)

        # pvlib restituisce shape (len(x), len(rotation)) — trasponiamo in (n_times, n_points)
        VF = vf_ground_sky_2d(rotation_deg, gcr, x_frac, pitch, H, max_rows=10).T

        return np.clip(VF, 0.0, 1.0)

    # ── Fallback: algoritmo gap-based (come pvlib) per assi non uniformi ────
    # Usato per axes_override (bordo) e terreno inclinato.
    # Replica l'approccio pvlib: calcola gli angoli di elevazione verso tutti
    # i bordi dei pannelli, poi somma i "gap" di cielo visibile tra pannelli
    # consecutivi, pesati con Lambert (cos dell'angolo di elevazione).
    axes  = axes_override if axes_override is not None else panel_axes(p)
    axes  = np.sort(axes)                        # ordine crescente
    tan_s = np.tan(slope)
    n_axes = len(axes)

    th   = theta_arr[:, None, None]              # (n_times, 1, 1)
    half_cos = W / 2 * np.abs(np.cos(th))       # (n_times, 1, 1)
    # B11 (v4.2.2): sin CON SEGNO — dz_low appartiene al bordo x_left
    # (ovest) e dz_high a x_right (est); con |sin| il pannello era
    # specchiato per theta<0 in questo fallback (slope/axes_override).
    half_sin = W / 2 * np.sin(th)               # (n_times, 1, 1) CON SEGNO

    ax  = axes[None, None, :]                    # (1, 1, n_axes)
    xp  = np.array(x_pts)[None, :, None]        # (1, n_points, 1)

    # Coordinate bordi pannello
    x_left  = ax - half_cos                      # (n_times, 1, n_axes)
    x_right = ax + half_cos

    dz_base = (ax - xp) * tan_s + H             # (n_times, n_points, n_axes)
    dz_low  = dz_base - half_sin                 # bordo inferiore
    dz_high = dz_base + half_sin                 # bordo superiore

    # Angoli di elevazione dal punto a terra verso i bordi
    # arctan2(dz, dx) = angolo dall'orizzontale (come pvlib)
    phi_left  = np.arctan2(dz_low,  x_left  - xp)   # (n_times, n_points, n_axes)
    phi_right = np.arctan2(dz_high, x_right - xp)

    # Per ogni pannello: angolo minore e maggiore
    phi_lo = np.minimum(phi_left, phi_right)     # (n_times, n_points, n_axes)
    phi_hi = np.maximum(phi_left, phi_right)

    # Sky gap tra pannelli consecutivi (come pvlib):
    # Gli assi sono ordinati da sinistra a destra; gli angoli di elevazione
    # decrescono da ~π (sinistra) a ~0 (destra).
    # Il gap di cielo tra pannello k e k+1 va da phi_hi[k+1] a phi_lo[k]:
    # VF_gap = max(cos(phi_hi[k+1]) - cos(phi_lo[k]), 0) / 2
    gap_between = np.clip(
        np.cos(phi_hi[:, :, 1:]) - np.cos(phi_lo[:, :, :-1]),
        0.0, None
    )

    # Gap orizzonte: cielo visibile oltre i pannelli estremi.
    # Orizzonte sinistro (angolo π → cos=-1) al bordo inf del pannello più sinistro
    gap_left = np.clip(np.cos(phi_hi[:, :, 0:1]) - (-1.0), 0.0, None)
    # Orizzonte destro (angolo 0 → cos=+1) dal bordo inf del pannello più destro
    gap_right = np.clip(1.0 - np.cos(phi_lo[:, :, -1:]), 0.0, None)

    VF = np.clip(
        (gap_between.sum(axis=2) + gap_left[:, :, 0] + gap_right[:, :, 0]) / 2.0,
        0.0, 1.0
    )

    return VF


# ══════════════════════════════════════════════════════════════════════════════
# RAY-TRACING 2D -- ombra diretta
# ══════════════════════════════════════════════════════════════════════════════

def _shadow_kinematics(solar_elev, solar_az, theta_deg, p, tan_s):
    """
    [v3.3.6] Helper: calcola le grandezze cinematiche per il ray-tracing
    ombra dato un set (elev, azimut solari, θ tracker) — vettorizzato su n_times.
    Restituisce: hs, hc, atp, den, den_w, east, sun_up.
    """
    W = p['W']
    ax_az = p.get('axis_azimuth', 180.0)
    ax_tilt = p.get('axis_tilt', 0.0)
    solar_zenith = 90.0 - solar_elev
    psza_deg = projected_solar_zenith_angle(
        solar_zenith, solar_az, ax_tilt, ax_az)
    psza_clamped = np.clip(np.abs(psza_deg), 0.5, 89.5)
    abs_tan_phi = np.abs(np.tan(np.radians(90.0 - psza_clamped)))
    east = (psza_deg > 0)   # R1-analitica: True = ombra verso +x
    theta_arr = np.radians(theta_deg)
    hs = W / 2 * np.sin(theta_arr)   # M5: con segno
    hc = W / 2 * np.abs(np.cos(theta_arr))
    # v4.3.0: clamp simmetrico su ENTRAMBI i denominatori — con tan_s
    # negativo ripido (terreno che scende verso +x) e sole radente,
    # raw_den (lato est) puo' azzerarsi/cambiare segno come raw_den_w:
    # il raggio non interseca il terreno in discesa -> ombra disattivata
    # (den=1e6), non proiettata dal lato sbagliato.
    _re = np.full_like(abs_tan_phi, 0.0)
    np.divide(tan_s, abs_tan_phi, out=_re, where=abs_tan_phi > 0.001)
    raw_den = np.where(abs_tan_phi > 0.001, 1.0 + _re, 1e6)
    den = np.where(raw_den > 0.01, raw_den, 1e6)
    _rw = np.full_like(abs_tan_phi, 0.0)
    np.divide(tan_s, abs_tan_phi, out=_rw, where=abs_tan_phi > 0.001)
    raw_den_w = np.where(abs_tan_phi > 0.001, 1.0 - _rw, 1e6)
    den_w = np.where(raw_den_w > 0.01, raw_den_w, 1e6)
    sun_up = solar_elev > 2.0
    return hs, hc, abs_tan_phi, den, den_w, east, sun_up


def _build_subsamples(df, p):
    """
    [v3.3.6] Costruisce N sub-campioni equidistanti dentro ciascun intervallo
    orario, ricalcolando posizione solare e theta tracker con pvlib.
    Usato per anti-aliasing temporale dentro compute_shadow_matrix.

    Il numero di sub-campioni e' controllato da p['n_sub'] (default 4).
    Con n_sub=4 gli offset sono -22.5, -7.5, +7.5, +22.5 min (come prima).
    Con n_sub=2 gli offset sono -15, +15 min.
    Con n_sub=1 nessun sub-sampling (offset=0, solo posizione centrale).

    Ritorna lista di n_sub dict con chiavi 'elev','az','theta' (ciascuna di
    lunghezza n_times). Se pvlib non e' disponibile o df non e' orario,
    ritorna None (fallback a interp lineare).
    """
    try:
        import pvlib  # noqa
    except ImportError:
        return None
    if len(df) < 2:
        return None
    dt = df.index[1] - df.index[0]
    # Accetta solo step ~ orario (tolleranza 1 sec)
    if abs(dt.total_seconds() - 3600) > 1:
        return None
    if not all(k in p for k in ('lat', 'lon')):
        return None

    n_sub = int(p.get('n_sub', 4))
    if n_sub < 1:
        n_sub = 1

    loc = pvlib.location.Location(p['lat'], p['lon'])
    ax_tilt = p.get('axis_tilt', 0.0)
    ax_az = p.get('axis_azimuth', 180.0)
    beta_max = p.get('beta_max', 60)
    bt_mode = int(p.get('backtracking', 1))
    gcr = p.get('GCR', p['W'] / p['pitch'])
    theta_fix = float(p.get('theta_fix', 0.0))

    # Offset equidistanti centrati nell'ora: per n_sub=4 → -22.5,-7.5,+7.5,+22.5
    # Formula: offset_k = (k + 0.5) / n_sub * 60 - 30  [minuti dal centro ora]
    offsets = [pd.Timedelta(minutes=((k + 0.5) / n_sub * 60.0 - 30.0))
               for k in range(n_sub)]
    subs = []
    for off in offsets:
        t_sub = df.index + off
        sp = loc.get_solarposition(t_sub)
        if bt_mode == 2:
            # Tilt fisso: theta costante anche nei sub-istanti
            theta_sub = np.full(len(t_sub), theta_fix)
        else:
            tr = pvlib.tracking.singleaxis(
                sp['apparent_zenith'], sp['azimuth'],
                axis_tilt=ax_tilt, axis_azimuth=ax_az,
                max_angle=beta_max, backtrack=(bt_mode == 1), gcr=gcr)
            theta_sub = np.nan_to_num(tr['tracker_theta'].values, nan=0.0)
        subs.append({
            'elev': (90.0 - sp['apparent_zenith'].values),
            'az':   sp['azimuth'].values,
            'theta': theta_sub,
        })
    return subs


def compute_shadow_matrix(x_pts, df, p, axes_override=None):
    """
    Calcola la matrice f_dir(n_times x n_points) — versione VETTORIZZATA.
      1.0 = punto illuminato direttamente
      0.0 = punto in ombra (pannello sovrastante o adiacente)

    v2.3: ray-tracing direzionale con phi_p signed + terreno inclinato.
    v3.3.6: anti-aliasing spaziale (frazione celletta Dx in ombra) +
            anti-aliasing temporale via n_sub sub-campioni (p['n_sub'],
            default 4) equidistanti nell'ora, ricalcolati con pvlib
            (posizione solare + theta tracker reali). Fallback a interp
            lineare se pvlib indisponibile o df non orario.

    axes_override: se fornito, usa questi assi pannello invece di panel_axes(p).

    Geometria dell'ombra (convenzione pvlib PSZA, v4.3.0 — phi_p non e'
    piu' usato da questa funzione):
      PSZA > 0 (sole a OVEST): l'ombra cade verso +x (est) dell'asse
      PSZA < 0 (sole a EST):  l'ombra cade verso −x (ovest) dell'asse

    Su terreno inclinato:
      La quota del suolo è z_ground(x) = x · tan(slope_cross).
      L'asse del pannello è a quota z_ground(axis) + H.
    """
    n_times  = len(df)
    n_points = len(x_pts)

    H     = p['H']
    W     = p['W']
    axes  = axes_override if axes_override is not None else panel_axes(p)
    tan_s = np.tan(p.get('slope_cross_rad', 0.0))

    # [v3.3.6] Prova a costruire n_sub sub-campioni con pvlib.
    # Se riesce -> anti-aliasing temporale basato sui DATI VERI.
    # Se fallisce (pvlib assente, df non orario, parametri mancanti) ->
    # fallback al calcolo orario con interpolazione lineare
    # sh_min/sh_max tra step adiacenti.
    n_sub = int(p.get('n_sub', 4))
    if n_sub < 1:
        n_sub = 1
    subs_15min = _build_subsamples(df, p)

    sun_up    = df['apparent_elevation'].values > 2.0       # (n_times,)
    theta_arr = np.radians(df['tracker_theta'].values)      # (n_times,)

    # ── Angolo proiettato ombra via pvlib (v3.3.5) ─────────────────────────
    # pvlib.shading.projected_solar_zenith_angle calcola l'angolo zenitale
    # del sole proiettato sul piano perpendicolare all'asse del tracker.
    # tan(PSZA) = sin(az_cross) / tan(elev) = offset_ombra / dz
    #
    # Convenzione segno PSZA (verificata empiricamente con pvlib, v4.3.0:
    # mattina az≈79° → PSZA=−67; pomeriggio az≈262° → PSZA=+48):
    #   PSZA < 0 → sole a EST dell'asse  → ombra verso −x (ovest)
    #   PSZA > 0 → sole a OVEST dell'asse → ombra verso +x (est)
    ax_az = p.get('axis_azimuth', 180.0)
    ax_tilt = p.get('axis_tilt', 0.0)
    solar_zenith  = 90.0 - df['apparent_elevation'].values
    solar_azimuth = df['azimuth'].values

    psza_deg = projected_solar_zenith_angle(
        solar_zenith, solar_azimuth, ax_tilt, ax_az)   # (n_times,) gradi

    # Conversione PSZA → grandezze usate dal ray-tracing downstream:
    #   phi_shadow = 90° - |PSZA| (angolo profilo dal piano orizzontale)
    #   abs_tan_phi = |tan(phi_shadow)| = |1/tan(PSZA)|
    # Il downstream calcola offset = z / abs_tan_phi, equivalente a z·|tan(PSZA)|.
    #
    # Clamp |PSZA| in [0.5°, 89.5°]:
    #   PSZA→0° (sole lungo asse): phi_shadow→90°, abs_tan_phi grande, offset→0  ✓
    #   PSZA→±90° (sole rasente): phi_shadow→0°, abs_tan_phi→0, offset→∞ (clamp) ✓
    psza_clamped = np.clip(np.abs(psza_deg), 0.5, 89.5)
    abs_tan_phi = np.abs(np.tan(np.radians(90.0 - psza_clamped)))  # (n_times,)
    # R1-analitica (v4.2.2): l'ombra cade dal lato OPPOSTO al sole.
    # PSZA<0 = sole a EST (pvlib) -> ombra verso OVEST (-x). La selezione
    # storica proiettava l'ombra VERSO il sole (specchiata, coerente con
    # la scena specchiata pre-R1).
    shadow_east = (psza_deg > 0)                         # True = OMBRA verso +x

    # M5 (v4.2.2): sin CON SEGNO — il bordo ovest (x_left) sta a
    # z = H - half_sin, quello est (x_right) a z = H + half_sin, per
    # qualunque segno di theta (pvlib: theta>0 = faccia a ovest = bordo
    # ovest basso). Con |sin| il pannello veniva specchiato per meta'
    # giornata in modalita' tilt fisso.
    half_sin = W / 2 * np.sin(theta_arr)                    # (n_times,) CON SEGNO
    half_cos = W / 2 * np.abs(np.cos(theta_arr))            # (n_times,)

    # Denominatore terreno inclinato: (n_times,)
    # v4.3.0: clamp come per den_w (vedi _shadow_kinematics) — con tan_s
    # negativo ripido e sole radente il denominatore est puo' azzerarsi o
    # cambiare segno: ombra disattivata (1e6), non dal lato sbagliato.
    _raw_denom = np.where(abs_tan_phi > 0.001,
                          1.0 + tan_s / abs_tan_phi, 1e6)
    denom = np.where(_raw_denom > 0.01, _raw_denom, 1e6)

    # Punti a terra: (n_points,)
    xp = np.array(x_pts)
    z_ground = xp * tan_s                                   # (n_points,)

    # [v3.3.6] Anti-aliasing: larghezza cella griglia per smoothing dei bordi
    # ombra. Ogni punto x rappresenta una "celletta" [x-Δx/2, x+Δx/2]; la
    # frazione in ombra è calcolata come overlap dell'intervallo ombra con
    # la celletta, evitando aliasing spaziale × temporale (che produceva
    # lobi periodici nel profilo annuale di f_dir).
    if len(xp) > 1:
        dx = float(np.mean(np.diff(xp)))
    else:
        dx = 1e-6
    half_dx = dx / 2.0

    # Inizializza: notte = 0, giorno = 1 (poi si mette in ombra)
    f_dir = np.zeros((n_times, n_points))
    f_dir[sun_up] = 1.0

    # Indici delle ore diurne
    t_idx = np.where(sun_up)[0]
    if len(t_idx) == 0:
        return f_dir

    # Pre-calcola per tutte le ore diurne: shape (n_sun,)
    hs   = half_sin[t_idx]
    hc   = half_cos[t_idx]
    atp  = abs_tan_phi[t_idx]
    den  = denom[t_idx]
    east = shadow_east[t_idx]

    # Denominatore per sole a ovest su terreno inclinato (pre-calcolato, M4)
    # Indipendente dall'asse → fuori dal loop.
    # np.divide con out+where evita RuntimeWarning su divisioni scartate
    #
    # Fisica: den_w = 1 - tan_s/atp. Se tan_s > atp (pendenza > angolo solare
    # proiettato), den_w ≤ 0: il raggio solare dal lato ovest non interseca il
    # terreno in salita (l'ombra "sfugge" all'infinito o si ribalta). In tal caso
    # si disabilita l'ombra ovest (den_w → 1e6 ⟹ x_shadow → 0, intervallo nullo).
    _ratio_w = np.full_like(atp, 0.0)
    np.divide(tan_s, atp, out=_ratio_w, where=atp > 0.001)
    raw_den_w = np.where(atp > 0.001, 1.0 - _ratio_w, 1e6)
    # Clamp: se den_w ≤ 0 (pendenza > angolo solare), disabilita ombra ovest
    den_w = np.where(raw_den_w > 0.01, raw_den_w, 1e6)          # (n_sun,)

    # [v3.3.6] Se i sub-campioni sono disponibili, costruisci
    # le grandezze cinematiche (hs, hc, atp, den, den_w, east) per ciascun
    # sub SULL'INTERO df (n_times), poi nel loop per asse accumula la
    # coverage sommando le sotto-coverage e dividendo per n_sub.
    if subs_15min is not None:
        sub_kin = []
        for s in subs_15min:  # n_sub elementi
            hs_s, hc_s, atp_s, den_s, den_w_s, east_s, su_s = _shadow_kinematics(
                s['elev'], s['az'], s['theta'], p, tan_s)
            sub_kin.append({
                'hs': hs_s, 'hc': hc_s, 'atp': atp_s,
                'den': den_s, 'den_w': den_w_s,
                'east': east_s, 'sun_up': su_s,
            })

    # Ciclo solo sugli assi (tipicamente 6) — il calcolo interno è vettorizzato
    f_dir_sun = np.ones((len(t_idx), n_points))

    for axis in axes:
        z_axis = axis * tan_s + H
        z_inf  = z_axis - hs                              # (n_sun,)
        z_sup  = z_axis + hs                              # (n_sun,)
        x_left  = axis - hc                               # (n_sun,)
        x_right = axis + hc                               # (n_sun,)

        # [RIMOSSO v3.3.5] Test 1 "under" (proiezione verticale del pannello).
        # Bug: marcava in ombra punti sotto il pannello anche quando il raggio
        # solare li raggiungeva dal lato senza intersecare il pannello.
        # Il Test 2 (ombra proiettata) copre correttamente TUTTI i casi,
        # incluso sole verticale (phi_p→90° ⟹ ombra proiettata → proiezione verticale).

        # Test 2: ombra proiettata (ray-tracing direzionale)
        # Geometria: il raggio solare con angolo di profilo φ_p colpisce
        # i bordi del pannello e proietta l'ombra al suolo.
        #
        # Per sole a OVEST (PSZA > 0), l'ombra cade a DESTRA (+x) dell'asse.
        # Coordinate ombra al suolo per ciascun bordo del pannello:
        #   x_shadow = x_bordo + (z_bordo - z_ground(x_shadow)) / tan(|φ_p|)
        #
        # Su terreno inclinato, z_ground(x) = x · tan(slope_cross), quindi:
        #   x_sh = x_bordo + (z_bordo - x_sh · tan_s) / tan(|φ_p|)
        #   x_sh · (1 + tan_s / tan(|φ_p|)) = x_bordo + z_bordo / tan(|φ_p|)
        #   x_sh = (x_bordo + z_bordo / tan(|φ_p|)) / (1 + tan_s / tan(|φ_p|))
        #
        # Per sole a EST (PSZA < 0), l'ombra cade a SINISTRA (-x):
        #   x_sh = x_bordo - (z_bordo - z_ground(x_shadow)) / tan(|φ_p|)
        #   x_sh · (1 - tan_s / tan(|φ_p|)) = x_bordo - z_bordo / tan(|φ_p|)
        #   x_sh = (x_bordo - z_bordo / tan(|φ_p|)) / (1 - tan_s / tan(|φ_p|))

        # (den_w è pre-calcolato fuori dal loop — dipende solo dal timestep)

        # Ombra est: i 4 punti di proiezione dei bordi
        x_sh_e1 = (x_left  + z_inf / atp) / den             # (n_sun,)
        x_sh_e2 = (x_right + z_sup / atp) / den             # (n_sun,)
        sh_min_e = np.minimum(x_sh_e1, x_sh_e2)[:, None]    # (n_sun, 1)
        sh_max_e = np.maximum(x_sh_e1, x_sh_e2)[:, None]    # (n_sun, 1)

        # Ombra verso ovest (-x): stessi bordi fisici (x_left con z_inf,
        # x_right con z_sup — accoppiamento CON SEGNO, M5), spostamento -x.
        x_sh_w1 = (x_left  - z_inf / atp) / den_w           # (n_sun,)
        x_sh_w2 = (x_right - z_sup / atp) / den_w           # (n_sun,)
        sh_min_w = np.minimum(x_sh_w1, x_sh_w2)[:, None]    # (n_sun, 1)
        sh_max_w = np.maximum(x_sh_w1, x_sh_w2)[:, None]    # (n_sun, 1)

        # Seleziona in base alla direzione del sole
        sh_min = np.where(east[:, None], sh_min_e, sh_min_w)
        sh_max = np.where(east[:, None], sh_max_e, sh_max_w)

        # [v3.3.6] Anti-aliasing spaziale + temporale sui bordi ombra.
        #
        # SPAZIALE: ogni punto x rappresenta una celletta [x-Δx/2, x+Δx/2];
        # la frazione in ombra è calcolata come overlap dell'intervallo
        # [sh_min, sh_max] con la celletta (anziché test binario in/out).
        #
        # TEMPORALE: due strategie alternative (n_sub sub-campioni).
        #   (A) se subs disponibile -> ricalcola sh_min/sh_max in n_sub
        #       sub-istanti usando pvlib (DATI VERI di elevazione,
        #       azimut e theta tracker ricampionati con backtracking vero).
        #   (B) fallback -> interpola linearmente sh_min/sh_max tra timestep
        #       orari adiacenti con n_sub pesi equidistanti.
        cell_lo = xp[None, :] - half_dx                      # (1, n_points)
        cell_hi = xp[None, :] + half_dx                      # (1, n_points)

        coverage = np.zeros_like(f_dir_sun)

        if subs_15min is not None:
            # Strategia A: n_sub sub-istanti con dati veri
            for k in range(n_sub):
                sk = sub_kin[k]
                hs_k = sk['hs'][t_idx]
                atp_k = sk['atp'][t_idx]
                den_k = sk['den'][t_idx]
                den_w_k = sk['den_w'][t_idx]
                east_k = sk['east'][t_idx]
                su_k = sk['sun_up'][t_idx]   # sub-istante potrebbe essere buio

                z_inf_k = z_axis - hs_k
                z_sup_k = z_axis + hs_k
                hc_k = sk['hc'][t_idx]
                x_left_k  = axis - hc_k
                x_right_k = axis + hc_k

                # Est
                x_sh_e1 = (x_left_k  + z_inf_k / atp_k) / den_k
                x_sh_e2 = (x_right_k + z_sup_k / atp_k) / den_k
                sh_min_ke = np.minimum(x_sh_e1, x_sh_e2)[:, None]
                sh_max_ke = np.maximum(x_sh_e1, x_sh_e2)[:, None]
                # Ovest: stessi bordi fisici del percorso principale
                # (x_left con z_inf, x_right con z_sup — accoppiamento CON
                # SEGNO, M5). Il pairing scambiato pre-M5 era rimasto solo
                # qui: proiettava gli spigoli del pannello contro-ruotato
                # (larghezza ombra ridotta di |cos(2·PSZA)| nelle mattine).
                x_sh_w1 = (x_left_k  - z_inf_k / atp_k) / den_w_k
                x_sh_w2 = (x_right_k - z_sup_k / atp_k) / den_w_k
                sh_min_kw = np.minimum(x_sh_w1, x_sh_w2)[:, None]
                sh_max_kw = np.maximum(x_sh_w1, x_sh_w2)[:, None]
                sh_min_k = np.where(east_k[:, None], sh_min_ke, sh_min_kw)
                sh_max_k = np.where(east_k[:, None], sh_max_ke, sh_max_kw)

                ov_lo = np.maximum(cell_lo, sh_min_k)
                ov_hi = np.minimum(cell_hi, sh_max_k)
                cov_k = np.clip((ov_hi - ov_lo) / dx, 0.0, 1.0)
                # Sub-istanti di notte non contribuiscono all'ombra
                cov_k[~su_k, :] = 0.0
                coverage += cov_k
            coverage /= n_sub
        else:
            # Strategia B: interpolazione lineare sh_min/sh_max (fallback, n_sub pesi)
            def _bracket(arr):
                prev = np.empty_like(arr); prev[0] = arr[0]; prev[1:] = arr[:-1]
                nxt  = np.empty_like(arr); nxt[-1] = arr[-1]; nxt[:-1] = arr[1:]
                return 0.5 * (prev + arr), 0.5 * (arr + nxt)

            smin_p, smin_n = _bracket(sh_min)
            smax_p, smax_n = _bracket(sh_max)
            # n_sub pesi equidistanti: per n_sub=4 -> 0.125, 0.375, 0.625, 0.875
            for ki in range(n_sub):
                w = (ki + 0.5) / n_sub
                sh_min_w = smin_p + w * (smin_n - smin_p)
                sh_max_w = smax_p + w * (smax_n - smax_p)
                ov_lo = np.maximum(cell_lo, sh_min_w)
                ov_hi = np.minimum(cell_hi, sh_max_w)
                coverage += np.clip((ov_hi - ov_lo) / dx, 0.0, 1.0)
            coverage /= n_sub

        # Combinazione tra assi: regola "any panel shadows" → conservativa
        # via minimo (1 - max coverage).
        f_dir_sun = np.minimum(f_dir_sun, 1.0 - coverage)

    f_dir[sun_up] = f_dir_sun
    return f_dir


# ══════════════════════════════════════════════════════════════════════════════
# STATISTICHE MENSILI -- P10 / P50 / P90
# ══════════════════════════════════════════════════════════════════════════════

def compute_monthly_stats(dli_daily, x_pts, p, dli_daily_ref=None):
    """
    Per ogni mese (1-12) e ogni punto x calcola:
      - DLI medio giornaliero per anno (media dei giorni del mese)
      - P10, P50, P90 su tutti gli anni disponibili

    Restituisce dizionario:
      stats[mese] = {
          'p10':  array (n_points,)   — NaN se simulazione su singolo anno (TMY)
          'p50':  array (n_points,)
          'p90':  array (n_points,)   — NaN se simulazione su singolo anno (TMY)
          'mean': array (n_points,)
          'dli_ref_p50': float (DLI riferimento a cielo aperto, mediana)
          'n_years': int (numero di anni unici nei dati di input)
      }

    Se dli_daily_ref è fornito (Serie con DLI giornaliero a cielo aperto),
    viene usato come riferimento. Altrimenti si stima dal max spaziale.

    NOTA SUI PERCENTILI (v4.1.0):
    Quando i dati di input contengono UN SOLO anno (es. TMY composito mese-per-mese
    in v4.x), P10 e P90 sarebbero matematicamente uguali a P50 (un solo campione
    nella distribuzione interannuale). Per evitare di mostrare informazione
    fuorviante nei report, in questo caso `p10` e `p90` vengono impostati a NaN.
    Le funzioni di scrittura Excel/PDF interpretano NaN come "--" (non disponibile)
    e mantengono solo P50 valido. La simulazione multi-anno con P10/P50/P90 reali
    sarà disponibile in v4.2 (vedi ROADMAP).
    """
    stats = {}

    for m in range(1, 13):
        # Seleziona giorni del mese m
        mask  = dli_daily.index.month == m
        daily = dli_daily[mask]

        if len(daily) == 0:
            stats[m] = {k: np.full(len(x_pts), np.nan)
                        for k in ('p10','p50','p90','mean')}
            stats[m]['dli_ref_p50'] = np.nan
            stats[m]['n_years'] = 0
            continue

        # Media per anno
        years     = daily.index.year
        by_year   = daily.groupby(years).mean()   # (n_anni x n_points)
        n_years_m = len(by_year)

        p50  = np.percentile(by_year.values, 50, axis=0)
        mean = by_year.values.mean(axis=0)
        # P10/P90 significativi solo con >=2 anni unici nella distribuzione
        # interannuale. Con un solo anno (TMY): NaN per evitare ridondanza.
        if n_years_m >= 2:
            p10 = np.percentile(by_year.values, 10, axis=0)
            p90 = np.percentile(by_year.values, 90, axis=0)
        else:
            p10 = np.full(len(x_pts), np.nan)
            p90 = np.full(len(x_pts), np.nan)

        # DLI riferimento a cielo aperto
        if dli_daily_ref is not None:
            # Usa il DLI calcolato senza pannelli
            ref_mask = dli_daily_ref.index.month == m
            ref_daily = dli_daily_ref[ref_mask]
            if len(ref_daily) > 0:
                ref_by_year = ref_daily.groupby(ref_daily.index.year).mean()
                dli_ref_p50 = float(np.percentile(ref_by_year.values, 50))
            else:
                dli_ref_p50 = np.nan
        else:
            # Fallback: P50 del massimo spaziale per anno
            dli_ref_p50 = float(np.percentile(by_year.values.max(axis=1), 50))

        stats[m] = {
            'p10':        p10,
            'p50':        p50,
            'p90':        p90,
            'mean':       mean,
            'dli_ref_p50': dli_ref_p50,
            'n_years':    n_years_m,
        }

    return stats


def zone_masks(x_arr, p):
    """
    Calcola le maschere per le 4 zone standard.

    Definizioni basate sulla proiezione verticale del pannello:
      half_w     = W/2                    proiezione a pannello piatto (θ=0)
      half_w_min = (W/2)·cos(β_max)      proiezione a massima inclinazione

    Zone (misurate dalla distanza dall'asse tracker più vicino):
      Sotto-tracker : d < half_w_min      → sempre coperta sulla verticale
      Bordo         : half_w_min ≤ d < half_w → coperta intermittentemente
      Centrale      : d ≥ half_w          → mai coperta dalla verticale
      Media pitch   : tutti i punti
    """
    half_w     = p['W'] / 2
    half_w_min = half_w * np.cos(np.radians(p['beta_max']))
    pitch      = p['pitch']

    return {
        'Sotto-tracker': (x_arr < half_w_min) | (x_arr > pitch - half_w_min),
        'Bordo':         (((x_arr >= half_w_min) & (x_arr < half_w)) |
                          ((x_arr > pitch - half_w) & (x_arr <= pitch - half_w_min))),
        'Centrale':      (x_arr >= half_w) & (x_arr <= pitch - half_w),
        'Media pitch':   np.ones(len(x_arr), dtype=bool),
    }


def trapz_zone_mean(values, x_arr, mask):
    """
    Media integrale (trapezoidale) di values(x) sulla sotto-zona definita da mask.
    Gestisce zone non contigue (sotto-tracker = due fasce simmetriche).
    """
    if not mask.any():
        return np.nan
    idx = np.where(mask)[0]
    if len(idx) < 2:
        return float(values[idx[0]])
    breaks = np.where(np.diff(idx) > 1)[0]
    integral_tot = 0.0
    length_tot   = 0.0
    start = 0
    for brk in np.append(breaks, len(idx) - 1):
        sub_idx = idx[start:brk + 1]
        if len(sub_idx) >= 2:
            x_sub = x_arr[sub_idx]
            v_sub = values[sub_idx]
            integral_tot += _trapz(v_sub, x_sub)
            length_tot   += x_sub[-1] - x_sub[0]
        elif len(sub_idx) == 1:
            dx = x_arr[1] - x_arr[0] if len(x_arr) > 1 else 1.0
            integral_tot += float(values[sub_idx[0]]) * dx
            length_tot   += dx
        start = brk + 1
    return integral_tot / length_tot if length_tot > 0 else float(values[idx].mean())


def zone_stats(stats, x_pts, p):
    """
    Aggrega le statistiche per le 4 zone standard + SAU usando integrazione
    trapezoidale.
    Restituisce dizionario zone_stats[mese][zona] = {p10, p50, p90, mean}.
    """
    x_arr  = np.array(x_pts)
    masks = zone_masks(x_arr, p)

    # Aggiungi maschera SAU
    sanu = p.get('sanu', 0.5)
    pitch = p['pitch']
    masks['SAU'] = (x_arr >= sanu) & (x_arr <= pitch - sanu)

    zs = {}
    for m in range(1, 13):
        zs[m] = {}
        for zona, mask in masks.items():
            if not mask.any():
                zs[m][zona] = {k: np.nan for k in ('p10','p50','p90','mean')}
                continue
            zs[m][zona] = {
                'p10':  trapz_zone_mean(stats[m]['p10'],  x_arr, mask),
                'p50':  trapz_zone_mean(stats[m]['p50'],  x_arr, mask),
                'p90':  trapz_zone_mean(stats[m]['p90'],  x_arr, mask),
                'mean': trapz_zone_mean(stats[m]['mean'], x_arr, mask),
            }
        zs[m]['dli_ref_p50'] = stats[m]['dli_ref_p50']
        zs[m]['n_years']     = stats[m].get('n_years', 0)

    return zs


# ══════════════════════════════════════════════════════════════════════════════
# OMBRA PALI DI SOSTEGNO
# ══════════════════════════════════════════════════════════════════════════════

def compute_perez_components(df, p, verbose=True):
    """
    Decompone la DHI in componente circumsolare, orizzonte e isotropa
    usando il modello di Perez et al. (1990) implementato in pvlib.

    Restituisce tre array (n_times,):
      dhi_circ  — componente circumsolare (segue f_dir, come la diretta)
      dhi_horiz — componente orizzonte (segue VF)
      dhi_iso   — componente isotropa (segue VF)

    v3.1: su terreno inclinato (slope_pct > 0), usa direttamente
    pvlib.irradiance.perez con surface_tilt = slope_angle e
    surface_azimuth = slope_aspect, ottenendo le 3 componenti
    già trasposte sul piano inclinato. Non serve più il fattore
    Liu & Jordan separato nel main().
    Su terreno piano, surface_tilt=0 come prima.
    """
    dhi_vals = df['dhi'].values.copy()
    n = len(dhi_vals)
    zeros = np.zeros(n)

    # Irradianza extraterrestre
    dni_extra = pvlib.irradiance.get_extra_radiation(df.index.dayofyear)
    if isinstance(dni_extra, pd.Series):
        dni_extra = dni_extra.values

    # Airmass relativa (non corretta per pressione)
    airmass = pvlib.atmosphere.get_relative_airmass(
        df['apparent_zenith'].values
    )

    # Terreno inclinato: usa Perez con tilt/azimut del terreno
    slope_tilt = p.get('slope_angle', 0.0)
    if slope_tilt > 0.1:
        surface_tilt = slope_tilt
        # R3 (v4.2.2): l'aspetto di un piano che scende verso D e' D stessa
        # (la normale pende verso valle). Il +180 storico calcolava un
        # pendio esposto a sud come esposto a nord (provato con pvlib:
        # beam 160 vs 271 W/m2 a mezzogiorno invernale, dossier R3).
        surface_azimuth = p.get('slope_azimuth', 0.0) % 360.0
    else:
        surface_tilt = 0
        surface_azimuth = 180

    try:
        components = pvlib.irradiance.perez(
            surface_tilt    = surface_tilt,
            surface_azimuth = surface_azimuth,
            dhi             = dhi_vals,
            dni             = df['dni'].values,
            dni_extra       = dni_extra,
            solar_zenith    = df['apparent_zenith'].values,
            solar_azimuth   = df['azimuth'].values,
            airmass         = airmass,
            model           = 'allsitescomposite1990',
            return_components = True,
        )
    except Exception as e:
        print(f'   AVVISO CRITICO: Decomposizione Perez fallita ({e}).')
        print(f'   Fallback: DHI completamente isotropa (accuratezza -5/-10% su DLI sereno).')
        return zeros.copy(), zeros.copy(), dhi_vals.copy()

    # Estrai componenti — il formato dipende dalla versione di pvlib
    def _extract(d, *keys):
        for k in keys:
            if isinstance(d, dict) and k in d:
                v = d[k]
                return np.asarray(v.values if hasattr(v, 'values') else v)
            elif isinstance(d, pd.DataFrame) and k in d.columns:
                return d[k].values
        return zeros.copy()

    iso   = _extract(components, 'isotropic', 'poa_isotropic')
    circ  = _extract(components, 'circumsolar', 'poa_circumsolar')
    horiz = _extract(components, 'horizon', 'poa_horizon')

    # Clip valori negativi (Perez può restituire F2 < 0 per orizzonte)
    circ  = np.maximum(circ, 0.0)
    iso   = np.maximum(iso, 0.0)
    # horiz può essere leggermente negativo, lo azzeriamo
    horiz = np.maximum(horiz, 0.0)

    # Normalizzazione componenti diffuse
    # Individua ore con NaN dalla decomposizione Perez
    nan_mask = np.isnan(circ) | np.isnan(iso) | np.isnan(horiz)

    if slope_tilt > 0.1:
        # Su terreno inclinato le componenti Perez sono già trasposte sul piano
        # inclinato: NON normalizzare a DHI orizzontale (v3.1 fix)
        # Fallback NaN: tutto il DHI come isotropa
        dhi_circ  = np.where(nan_mask, 0.0, circ)
        dhi_horiz = np.where(nan_mask, 0.0, horiz)
        dhi_iso   = np.where(nan_mask, dhi_vals, iso)
    else:
        # Terreno piano: normalizza a DHI orizzontale per coerenza
        # Pulisci NaN prima della normalizzazione
        circ  = np.where(nan_mask, 0.0, circ)
        iso   = np.where(nan_mask, 0.0, iso)
        horiz = np.where(nan_mask, 0.0, horiz)

        total = circ + iso + horiz
        safe_total = np.maximum(total, 1e-6)
        scale = np.where(total > 0.01, dhi_vals / safe_total, 0.0)
        dhi_circ  = circ * scale
        dhi_horiz = horiz * scale
        dhi_iso   = iso * scale

        # Fallback: ore con NaN Perez → tutto il DHI come isotropa
        dhi_circ  = np.where(nan_mask, 0.0, dhi_circ)
        dhi_horiz = np.where(nan_mask, 0.0, dhi_horiz)
        dhi_iso   = np.where(nan_mask, dhi_vals, dhi_iso)

    # Diagnostica (dopo pulizia NaN)
    if verbose:
        sun_mask = df['cos_zenith'].values > 0.01
        if sun_mask.any():
            dhi_sun = dhi_vals[sun_mask].sum()
            if dhi_sun > 0:
                f1_mean = dhi_circ[sun_mask].sum() / dhi_sun
                n_nan = nan_mask[sun_mask].sum() if nan_mask is not None else 0
                print(f'   Perez F1 medio diurno (circ/DHI): {f1_mean:.3f}'
                      f' ({n_nan} ore NaN → fallback isotropa)')

    # Pulizia finale: eventuali NaN residui → 0
    dhi_circ  = np.nan_to_num(dhi_circ, nan=0.0)
    dhi_horiz = np.nan_to_num(dhi_horiz, nan=0.0)
    dhi_iso   = np.nan_to_num(dhi_iso, nan=0.0)

    return dhi_circ, dhi_horiz, dhi_iso


# ══════════════════════════════════════════════════════════════════════════════
# FORMULA IRRADIANZA AL SUOLO UNIFICATA
# (usata da main, solratio_edge, benchmark)
# ══════════════════════════════════════════════════════════════════════════════

def compute_irradiance_matrix(f_dir, VF, dni_ground, dhi_circ, dhi_horiz, dhi_iso,
                              ghi, albedo=0.23):
    """
    Calcola la matrice di irradianza al suolo (n_times x n_points) [W/m²].

      IRR = (DNI_ground + DHI_circ) × f_dir
          + (DHI_iso + DHI_horiz) × VF
          + GHI × albedo × (1 - VF) / 2

    Parametri (tutti array):
      f_dir, VF      : (n_times x n_points)
      dni_ground, dhi_circ, dhi_horiz, dhi_iso, ghi : (n_times,)
      albedo          : float

    Restituisce IRR (n_times x n_points) in W/m².
    Nota: la conversione in PAR (µmol/m²/s) avviene a valle con par_frac × W_TO_UMOL.
    """
    IRR = ((dni_ground + dhi_circ)[:, None] * f_dir +
           (dhi_iso + dhi_horiz)[:, None] * VF +
           ghi[:, None] * albedo * (1.0 - VF) * 0.5)
    return np.maximum(IRR, 0.0)


# Alias per retrocompatibilità
compute_par_matrix = compute_irradiance_matrix


# ══════════════════════════════════════════════════════════════════════════════
# OTTIMIZZAZIONE PITCH
# ══════════════════════════════════════════════════════════════════════════════

def self_test():
    """
    Verifica il modello con casi analitici a soluzione nota.

    Geometria: pannello piatto (θ=0), pitch=2W, H=W.

    Caso 1 — VF:
      a) VF centro pitch > VF sotto tracker (meno cielo ostruito)
      b) VF simmetrico rispetto al centro del pitch
      c) VF nel range atteso (0.70–0.98 al centro)

    Caso 2 — Shadow con sole alto (azimut=179°, elevazione=70°):
      Sole quasi allineato all'asse N-S → |PSZA| clampato a 0.5°:
      l'ombra è quasi verticale, ≈ [−W/2, W/2] attorno all'asse 0
      (numericamente ≈ [−1.02, 0.98] col clamp).
      → punto x=0 (sotto il pannello): in ombra ✓
      → punto x=1.2W (centro gap): illuminato ✓
      [v3.3.5] Rimosso Test 1 "under" (proiezione verticale): il Test 2
      (ombra proiettata) copre tutti i casi incluso sole verticale.
      [v4.3.0] Razionale aggiornato: il commento storico citava la
      proiezione φ_p (pre-R4) e un'ombra [−0.27, 1.73] mai prodotta
      dal codice attuale (PSZA).

    Caso 3 — Shadow direzionale (sole da ovest vs sole da est):
      Profili diversi fra i due lati (test di non-identità).

    Caso 4 — Notte:
      Elevazione < 2° → tutti i punti in ombra (f_dir = 0).

    Caso 5 (v4.3.0) — Direzione ASSOLUTA con θ≠0 (inchioda la convenzione
      pvlib: sole a EST → PSZA<0 → ombra verso OVEST, tilt firmato):
      sole est (az=90°, elev=35°), θ=−50° (faccia a est). Il pannello
      con asse a x=P proietta l'ombra a ovest fino a ~x=2.88 m:
      x=2.5 in ombra, x=3.1 illuminato. Con la convenzione contro-ruotata
      storica (θ→−θ) l'ombra sarebbe [0.69, 1.59] e il test fallirebbe.

    Caso 6 (v4.3.0) — Handedness pendenza trasversale: con tan_s>0
      (terreno che SALE verso +x/est) e sole a est, l'ombra cade a ovest
      in DISCESA e si allunga (den_w<1): più punti in ombra che su
      terreno piano a parità di sole.

    Caso 7 (v4.3.0) — Equivalenza strategia A (sub-campioni pvlib,
      n_sub=1) vs strategia B (fallback): stessi input → stessi profili.
      Avrebbe intercettato il pairing scambiato del ramo ovest del loop
      sub-campioni (bug della revisione v4.3.0).

    Restituisce True se tutti i test passano, altrimenti stampa errori.
    """
    W = 2.0
    P = 2 * W   # pitch = 2W = 4m
    H = W       # H = W = 2m

    p_test = {
        'W': W, 'pitch': P, 'H': H, 'beta_max': 55, 'n_ext': 2,
        'GCR': W / P, 'sanu': 0.0, 'SAU': P,
        'slope_pct': 0.0, 'slope_angle': 0.0, 'slope_cross_deg': 0.0,
        'slope_cross_rad': 0.0, 'slope_azimuth': 0.0,
        'backtracking': 1,
        'axis_azimuth': 180.0,
    }

    n_pts = 101  # risoluzione fine per test precisi
    x_pts = np.linspace(0, P, n_pts)
    ok = True
    errors = []

    n_checks = 0  # v4.3.0: conteggio reale dei check (era hardcoded errato)

    def _check(condition, name, detail=''):
        nonlocal ok, n_checks
        n_checks += 1
        if not condition:
            ok = False
            msg = f'  {name}'
            if detail:
                msg += f': {detail}'
            errors.append(msg)

    # ── Test 1: VF a pannello piatto ──────────────────────────────────────
    theta_arr = np.array([0.0])
    VF = compute_vf_matrix(x_pts, theta_arr, p_test)

    mid_idx = n_pts // 2
    vf_mid = VF[0, mid_idx]
    vf_under = VF[0, 0]

    # v3.3.5: normalizzazione Lambert (coseno-pesata) via pvlib produce VF
    # più bassi rispetto alla vecchia normalizzazione angolare. Per GCR=0.5,
    # H=W, pannello piatto: VF al centro pitch ≈ 0.57, sotto pannello ≈ 0.43.
    _check(0.40 < vf_mid < 0.70, 'VF range centro',
           f'{vf_mid:.4f} non in (0.40, 0.70)')
    _check(vf_under < vf_mid, 'VF monotonia',
           f'sotto={vf_under:.4f} >= centro={vf_mid:.4f}')

    vf_left  = VF[0, n_pts // 4]
    vf_right = VF[0, 3 * n_pts // 4]
    _check(abs(vf_left - vf_right) < 0.01, 'VF simmetria',
           f'P/4={vf_left:.4f} vs 3P/4={vf_right:.4f}')

    # ── Test 2: Shadow con sole alto (elevazione 70°, azimut 179°) ─────────
    # Sole quasi allineato all'asse → |PSZA| clampato a 0.5°: ombra quasi
    # verticale ≈ [−W/2, W/2] attorno all'asse 0 (≈ [−1.02, 0.98]).
    import pandas as pd
    idx = pd.DatetimeIndex(['2010-06-21 12:00:00'], tz='UTC')
    df_test = pd.DataFrame({
        'apparent_elevation': [70.0],
        'azimuth': [179.0],
        'tracker_theta': [0.0],
        'cos_zenith': [np.cos(np.radians(20.0))],
    }, index=idx)

    f_dir = compute_shadow_matrix(list(x_pts), df_test, p_test)

    # x=0: sotto il pannello centrale (ombra quasi verticale ⊃ x=0)
    _check(f_dir[0, 0] == 0.0, 'Shadow sotto pannello',
           f'f_dir={f_dir[0, 0]}')

    # x=1.2W=2.4m: oltre ombra proiettata (~1.73m), prima del pannello P
    # → deve essere illuminato
    idx_free = np.argmin(np.abs(x_pts - 1.2 * W))
    _check(f_dir[0, idx_free] == 1.0, 'Shadow zona illuminata',
           f'x={x_pts[idx_free]:.2f}m f_dir={f_dir[0, idx_free]} (atteso 1.0)')

    # Verifica che esista almeno una zona in ombra E una illuminata nel pitch
    n_shadow = (f_dir[0, :] == 0.0).sum()
    n_lit = (f_dir[0, :] == 1.0).sum()
    _check(n_shadow > 0 and n_lit > 0, 'Shadow mix ombra/luce',
           f'ombra={n_shadow} illuminati={n_lit}')

    # ── Test 3: Direzionalità ombra (est vs ovest) ───────────────────────
    df_east = pd.DataFrame({
        'apparent_elevation': [30.0], 'azimuth': [120.0],
        'tracker_theta': [0.0],
        'cos_zenith': [np.cos(np.radians(60.0))],
    }, index=idx)
    df_west = pd.DataFrame({
        'apparent_elevation': [30.0], 'azimuth': [240.0],
        'tracker_theta': [0.0],
        'cos_zenith': [np.cos(np.radians(60.0))],
    }, index=idx)

    f_east = compute_shadow_matrix(list(x_pts), df_east, p_test)
    f_west = compute_shadow_matrix(list(x_pts), df_west, p_test)

    # I profili NON devono essere identici (direzionalità)
    diff = np.abs(f_east[0, :] - f_west[0, :]).sum()
    _check(diff > 0, 'Shadow direzionalità',
           f'est e ovest identici (diff={diff})')

    # ── Test 4: Notte ─────────────────────────────────────────────────────
    df_night = pd.DataFrame({
        'apparent_elevation': [1.0], 'azimuth': [180.0],
        'tracker_theta': [0.0], 'cos_zenith': [0.0],
    }, index=idx)
    f_night = compute_shadow_matrix(list(x_pts), df_night, p_test)
    _check(f_night[0, :].sum() == 0.0, 'Shadow notte',
           f'f_dir non zero di notte: sum={f_night[0,:].sum()}')

    # ── Test 5 (v4.3.0): direzione ASSOLUTA con theta ≠ 0 ────────────────
    # Sole a EST (az=90°, elev=35°) → PSZA≈−55° → ombra verso OVEST (−x).
    # Tracker θ=−50° (faccia a est, pvlib). Bordi pannello (asse a x=a):
    # x=a±(W/2)cos50, z=H∓(W/2)sin(−50) → il pannello con asse a x=P
    # proietta a ovest l'intervallo ≈ [−0.59, 2.88] (atp=tan35°≈0.700).
    # Con la convenzione CONTRO-RUOTATA storica (θ→+50) sarebbe
    # ≈ [0.69, 1.59]: x=2.5 illuminato. Questo check la esclude.
    df_t5 = pd.DataFrame({
        'apparent_elevation': [35.0], 'azimuth': [90.0],
        'tracker_theta': [-50.0],
        'cos_zenith': [np.cos(np.radians(55.0))],
    }, index=idx)
    f_t5 = compute_shadow_matrix(list(x_pts), df_t5, p_test)
    idx_25 = np.argmin(np.abs(x_pts - 2.5))
    idx_31 = np.argmin(np.abs(x_pts - 3.1))
    _check(f_t5[0, idx_25] == 0.0, 'Shadow direzione assoluta (in ombra)',
           f'x=2.5m f_dir={f_t5[0, idx_25]} (atteso 0: ombra a ovest di P)')
    _check(f_t5[0, idx_31] == 1.0, 'Shadow direzione assoluta (illuminato)',
           f'x=3.1m f_dir={f_t5[0, idx_31]} (atteso 1)')

    # ── Test 6 (v4.3.0): handedness pendenza trasversale ─────────────────
    # tan_s>0 = terreno che SALE verso +x (est). Sole a est, θ=0: ombra a
    # ovest, in DISCESA → allungata (den_w<1) → più punti in ombra che su
    # terreno piano.
    df_t6 = pd.DataFrame({
        'apparent_elevation': [35.0], 'azimuth': [90.0],
        'tracker_theta': [0.0],
        'cos_zenith': [np.cos(np.radians(55.0))],
    }, index=idx)
    p_slope = dict(p_test)
    p_slope['slope_cross_rad'] = np.arctan(0.10)
    p_slope['slope_cross_deg'] = np.degrees(np.arctan(0.10))
    f_flat = compute_shadow_matrix(list(x_pts), df_t6, p_test)
    f_slope = compute_shadow_matrix(list(x_pts), df_t6, p_slope)
    n_sh_flat = int((f_flat[0, :] == 0.0).sum())
    n_sh_slope = int((f_slope[0, :] == 0.0).sum())
    _check(n_sh_slope > n_sh_flat, 'Shadow handedness slope',
           f'ombra in discesa NON allungata: slope={n_sh_slope} pts vs '
           f'flat={n_sh_flat} pts')

    # ── Test 7 (v4.3.0): strategia A (sub pvlib, n_sub=1) ~ strategia B ──
    # Mattina estiva con theta fortemente negativo (sole a est): le due
    # strategie sono stimatori anti-aliasing diversi (B smussa sui vicini)
    # quindi NON si confrontano punto-per-punto, ma la COPERTURA d'ombra
    # oraria deve coincidere entro pochi %. Col pairing dei bordi
    # scambiato nel ramo ovest del loop sub (bug revisione v4.3.0)
    # l'ombra mattutina di A si riduce di |cos(2·PSZA)| (≈ dimezzata a
    # |PSZA|≈60°) e questo check fallisce.
    idx7 = pd.DatetimeIndex(['2010-06-21 06:00:00', '2010-06-21 07:00:00',
                             '2010-06-21 08:00:00'], tz='UTC')
    p_A = dict(p_test)
    p_A.update({'lat': 45.3, 'lon': 9.34, 'n_sub': 1, 'beta_max': 60.0,
                'backtracking': 1, 'GCR': W / P})
    df_t7 = pd.DataFrame(index=idx7)
    try:
        df_t7 = compute_solar_and_tracker(df_t7, p_A)
        f_A = compute_shadow_matrix(list(x_pts), df_t7, p_A)
        p_B = dict(p_A)
        p_B.pop('lat')   # senza lat/lon -> _build_subsamples=None -> B
        p_B.pop('lon')
        f_B = compute_shadow_matrix(list(x_pts), df_t7, p_B)
        cov_A = (1.0 - f_A).sum(axis=1)   # copertura ombra per ora
        cov_B = (1.0 - f_B).sum(axis=1)
        rel = float(np.max(np.abs(cov_A - cov_B) / np.maximum(cov_B, 1.0)))
        _check(rel < 0.15, 'Strategia A ~ B (copertura ombra)',
               f'scarto copertura max {rel:.1%} (atteso <15%): possibile '
               f'incoerenza fra percorso principale e loop sub-campioni')
    except Exception as _e:
        _check(False, 'Strategia A ~ B (copertura ombra)',
               f'eccezione durante il test: {type(_e).__name__}: {_e}')

    # ── Risultato ─────────────────────────────────────────────────────────
    n_pass = n_checks - len(errors)
    if ok:
        print(f'   Self-test: PASS ({n_pass}/{n_checks} - '
              f'VF range/simmetria/monotonia; shadow sotto/illuminata/mix/'
              f'direzionalita/notte; direzione assoluta theta!=0; '
              f'handedness slope; strategia A=B)')
    else:
        print(f'   Self-test: FAIL ({n_pass}/{n_checks})')
        for e in errors:
            print(e)

    return ok


