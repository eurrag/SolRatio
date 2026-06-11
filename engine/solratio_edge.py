"""
solratio_edge.py  |  SolRatio v4.2.1 (2026-05-01)
=====================================================
Effetto bordo semplificato: profili file perimetrali, fascia esterna,
correzione N-S, SAU esterna, K_agv medio impianto.

Geometria del bordo E-O:
  Il blocco tracker ha N_file. Per ogni fila dal bordo, il modello calcola:
  1. Pitch interno (0→P): il pitch tra la fila e la fila adiacente verso
     il centro, con un numero ridotto di pannelli sul lato esterno.
  2. Fascia esterna: il terreno tra l'asse della fila di bordo e il punto
     dove l'ombra del tracker diventa trascurabile. La larghezza è calcolata
     automaticamente dal P95 della proiezione dell'ombra sulle ore diurne
     annuali (dipende da H_max, latitudine, β_max — non dal pitch).

Nessuna dipendenza da openpyxl — solo numpy, pandas, solratio_core.
"""

import numpy as np
import pandas as pd
from datetime import datetime

from solratio_core import (
    PAR_FRAC, W_TO_UMOL, LAUB_COEFFICIENTS, laub_yield,
    compute_vf_matrix, compute_shadow_matrix,
    compute_perez_components, compute_monthly_stats, zone_stats,
    zone_masks, trapz_zone_mean, _trapz, compute_irradiance_matrix,
    compute_par_frac,
)


# ══════════════════════════════════════════════════════════════════════════════
# ASSI PANNELLO PER FILE DI BORDO
# ══════════════════════════════════════════════════════════════════════════════

def panel_axes_edge(p, n_left, n_right):
    """
    Assi pannello per una fila con n_left pannelli a sinistra e n_right a destra.
    Il pitch simulato va da x=0 (tracker sinistro) a x=P (tracker destro).
    """
    pitch = p['pitch']
    left  = [-i * pitch for i in range(1, n_left + 1)]
    right = [(1 + i) * pitch for i in range(1, n_right + 1)]
    return np.array(sorted(left + [0, pitch] + right))


def panel_axes_outer(p, n_internal, strip_width):
    """
    Assi pannello per la fascia esterna alla fila di bordo.

    Dominio simulato: x ∈ [0, strip_width].
    x = strip_width è il punto più lontano dal tracker.
    x = 0 è l'asse della fila di bordo.

    n_internal: numero di file tracker verso l'interno del blocco da
                includere nel calcolo (tipicamente n_ext=2).
                Queste file sono a coordinate negative:
                x = -P, -2P, ..., -(n_internal)·P

    I punti del profilo vanno da 0 (sotto il tracker) a strip_width
    (punto più lontano, quasi pieno campo).
    """
    pitch = p['pitch']
    axes = [0]  # asse della fila di bordo
    for i in range(1, n_internal + 1):
        axes.append(-i * pitch)  # file interne (verso centro blocco)
    return np.array(sorted(axes))


# ══════════════════════════════════════════════════════════════════════════════
# LARGHEZZA FASCIA ESTERNA (calcolata dai dati solari)
# ══════════════════════════════════════════════════════════════════════════════

def compute_strip_width(df, p, percentile=95):
    """
    Calcola la larghezza della fascia esterna dal P95 della proiezione
    dell'ombra del pannello sulle ore diurne annuali.

        d_ombra(t) = H_max / tan(|φ_p(t)|)

    dove H_max = H_mozzo + (W/2)·sin(β_max) è l'altezza del bordo
    superiore del pannello alla massima inclinazione.

    v3.3: usa il P95 mensile e prende il massimo tra i 12 mesi.
    Questo garantisce un dominio largo abbastanza per il mese peggiore
    (dicembre, ombre lunghe), mentre i mesi estivi calcolano
    correttamente PAR ≈ 1.0 sui punti lontani dal tracker.

    Restituisce:
      strip_width : float [m], larghezza della fascia esterna
    """
    W = p['W']
    beta_max = p['beta_max']
    H_bordo_sup = p['H'] + (W / 2) * np.sin(np.radians(beta_max))

    sun_mask = df['apparent_elevation'].values > 2.0
    phi_p = np.abs(df['phi_p'].values)

    # Filtra ore diurne con φ_p significativo (> 3° per evitare div/0)
    valid = sun_mask & (phi_p > 3.0)
    if not valid.any():
        return p['pitch']  # fallback

    tan_phi = np.tan(np.radians(phi_p[valid]))
    d_ombra = H_bordo_sup / tan_phi
    months = df.index.month.values[valid]

    # P95 per ogni mese, poi prende il massimo
    strip_monthly = {}
    for m in range(1, 13):
        m_mask = months == m
        if m_mask.any():
            strip_monthly[m] = float(np.percentile(d_ombra[m_mask], percentile))
        else:
            strip_monthly[m] = 0.0

    strip = max(strip_monthly.values())

    # Limita a un massimo ragionevole (5×pitch) e minimo (W)
    strip = np.clip(strip, W, 5.0 * p['pitch'])

    return strip


# ══════════════════════════════════════════════════════════════════════════════
# CALCOLO SINGOLO PROFILO (helper riutilizzabile)
# ══════════════════════════════════════════════════════════════════════════════

def _compute_single_profile(df, p, axes, x_pts, sun_mask, df_sun,
                            dni_ground, dhi_circ, dhi_horiz, dhi_iso, ghi,
                            dli_daily_ref, par_frac=None, domain_pitch=None):
    """
    Calcola stats e zone_stats per un set di assi pannello e punti x.
    Helper riutilizzato sia per i profili di bordo interni che per la fascia esterna.

    par_frac: array (n_times,) di PAR_FRAC orario. Se None, usa costante 0.45.
    domain_pitch: se fornito, sovrascrive p['pitch'] per zone_masks e zone_stats.
                  Usare strip_width per la fascia esterna, dove il dominio x
                  non è un pitch standard ma va da 0 a strip_width.
    """
    tau = p.get('tau', 0.0)
    albedo = p.get('albedo', 0.23)
    n_all = len(df)
    n_pts = len(x_pts)
    if par_frac is None:
        par_frac = PAR_FRAC  # costante scalare come fallback

    theta_sun = np.radians(df_sun['tracker_theta'].values)
    VF_sun = compute_vf_matrix(np.array(x_pts), theta_sun, p, axes_override=axes)
    f_dir_sun = compute_shadow_matrix(x_pts, df_sun, p, axes_override=axes)

    if tau > 0:
        f_dir_sun = np.where(f_dir_sun < 1.0,
                             np.maximum(f_dir_sun, tau), f_dir_sun)


    f_dir = np.zeros((n_all, n_pts))
    VF_full = np.zeros((n_all, n_pts))
    f_dir[sun_mask] = f_dir_sun
    VF_full[sun_mask] = VF_sun

    PAR_W = compute_irradiance_matrix(f_dir, VF_full, dni_ground, dhi_circ,
                                      dhi_horiz, dhi_iso, ghi, albedo)
    # par_frac puo essere scalare (0.45) o array (n_times,)
    if np.ndim(par_frac) == 0:
        PAR_mol = PAR_W * par_frac * W_TO_UMOL
    else:
        PAR_mol = PAR_W * par_frac[:, None] * W_TO_UMOL
    DLI_h = PAR_mol * 3600 / 1e6

    dli_df = pd.DataFrame(DLI_h, index=df.index, columns=x_pts)
    dli_daily = dli_df.groupby(df.index.normalize()).sum()

    stats = compute_monthly_stats(dli_daily, x_pts, p, dli_daily_ref=dli_daily_ref)

    # Per domini non-pitch (fascia esterna), sovrascriviamo pitch e sanu
    # nel dizionario parametri passato a zone_stats in modo che le maschere
    # coprano correttamente il dominio [0, domain_pitch].
    if domain_pitch is not None:
        p_zs = p.copy()
        p_zs['pitch'] = domain_pitch
        p_zs['sanu'] = 0.0          # nessun bordo SANU nella fascia esterna
        p_zs['SAU'] = domain_pitch   # tutta la fascia è SAU
    else:
        p_zs = p
    zs = zone_stats(stats, x_pts, p_zs)

    return stats, zs


# ══════════════════════════════════════════════════════════════════════════════
# CALCOLO PROFILI BORDO E-O (interni + fascia esterna)
# ══════════════════════════════════════════════════════════════════════════════

def compute_edge_profiles(df, p, dli_daily_ref=None):
    """
    Calcola i profili DLI per le file di bordo e per la fascia esterna.

    Per ogni fila k-esima dal bordo (k=1..n_ext):
      - Pitch interno: profilo [0,P] con n_left=k-1, n_right=n_ext

    Fascia esterna:
      - Larghezza calcolata dal P95 dell'ombra (compute_strip_width)
      - Dominio [0, strip_width] con tracker a x=0 e punti fino a strip_width
      - Pannelli solo a x ≤ 0 (la fila di bordo e le file interne)

    Restituisce dict:
      {
        'inner': [profili pitch interni...],
        'outer': {'stats': ..., 'zs': ..., 'strip_width': float},
        'strip_width': float   [m]
      }
    """
    n_ext = p['n_ext']
    n_points = p['n_points']
    x_pts_pitch = list(np.linspace(0, p['pitch'], n_points))

    # Pre-computazioni comuni
    sun_mask = df['apparent_elevation'].values > 2.0
    df_sun = df[sun_mask].copy()
    dhi_circ, dhi_horiz, dhi_iso = compute_perez_components(df, p)

    slope_tilt_rad = np.radians(p.get('slope_angle', 0.0))
    # R3 (v4.2.2): aspetto = direzione di discesa (niente +180, vedi core)
    slope_aspect_rad = np.radians(p.get('slope_azimuth', 0.0) % 360.0)
    elev_rad = np.radians(np.clip(df['apparent_elevation'].values, 0, 90))
    az_rad = np.radians(df['azimuth'].values)
    cos_incidence = (np.sin(elev_rad) * np.cos(slope_tilt_rad) +
                     np.cos(elev_rad) * np.sin(slope_tilt_rad) *
                     np.cos(az_rad - slope_aspect_rad))
    cos_incidence = np.maximum(cos_incidence, 0.0)
    dni_ground = df['dni'].values * cos_incidence
    ghi = df['ghi'].values if 'ghi' in df.columns else (dni_ground + df['dhi'].values)

    # PAR_FRAC variabile (Jacovides et al. 2004)
    import pvlib as _pvlib
    _dni_extra = _pvlib.irradiance.get_extra_radiation(df.index.dayofyear)
    if isinstance(_dni_extra, pd.Series):
        _dni_extra = _dni_extra.values
    par_frac = compute_par_frac(ghi, _dni_extra, df['cos_zenith'].values)

    # ── Profili pitch interni (uno per ogni configurazione di bordo) ──────
    inner_profiles = []
    for n_left in range(n_ext):
        n_right = n_ext
        print(f'   Profilo bordo interno: n_left={n_left}, n_right={n_right}...')
        axes = panel_axes_edge(p, n_left, n_right)
        stats, zs = _compute_single_profile(
            df, p, axes, x_pts_pitch, sun_mask, df_sun,
            dni_ground, dhi_circ, dhi_horiz, dhi_iso, ghi, dli_daily_ref,
            par_frac=par_frac)
        inner_profiles.append({
            'n_left': n_left,
            'n_right': n_right,
            'stats': stats,
            'zs': zs,
        })

    # ── Larghezza fascia esterna (dal P95 dell'ombra) ─────────────────────
    strip_width = compute_strip_width(df, p)
    sau_esterna = p.get('sau_esterna', 0.0)  # area totale SAU esterna [m²] (4 lati: E+O+N+S)
    L_tracker = p.get('L_tracker', 0.0)

    # Area della fascia esterna ombreggiata (solo E-O): 2 fasce × strip_width × L_tracker
    # La SAU N-S e il residuo E-O oltre la fascia ombra sono pieno campo.
    if L_tracker > 0:
        area_fascia = 2 * strip_width * L_tracker
    else:
        area_fascia = 2 * strip_width  # senza L_tracker, usiamo aree relative per m

    # Decomposizione: SAU_esterna (4 lati) = fascia E-O (ombreggiata) + pieno campo (resto)
    # Il pieno campo include i lati N-S e l'eventuale residuo E-O oltre la portata dell'ombra.
    # Se la SAU esterna è inferiore all'area della fascia, la fascia si tronca.
    if sau_esterna > 0 and area_fascia > 0:
        if sau_esterna >= area_fascia:
            # La fascia sta tutta dentro la SAU esterna
            area_pieno_campo = sau_esterna - area_fascia
            strip_effective = strip_width
        else:
            # La SAU esterna è più piccola della fascia → tronca
            strip_effective = strip_width * (sau_esterna / area_fascia)
            area_fascia = sau_esterna
            area_pieno_campo = 0.0
            print(f'   NOTA: SAU esterna ({sau_esterna:.0f} m²) < area fascia '
                  f'({2 * strip_width * max(L_tracker, 1):.0f} m²) → fascia troncata')
    else:
        strip_effective = strip_width
        area_pieno_campo = 0.0
        area_fascia = 0.0

    print(f'   Larghezza fascia esterna: {strip_width:.1f} m '
          f'(P95 ombra, {strip_width/p["pitch"]:.1f}× pitch)')
    if sau_esterna > 0:
        print(f'   SAU esterna (4 lati): {sau_esterna:.0f} m² = '
              f'fascia E-O {area_fascia:.0f} m² + pieno campo {area_pieno_campo:.0f} m²')

    # ── Profilo fascia esterna ────────────────────────────────────────────
    outer_profile = None
    if strip_effective > 0 and sau_esterna > 0:
        print(f'   Profilo fascia esterna ({strip_effective:.1f}m, n_right={n_ext})...')
        x_pts_outer = list(np.linspace(0, strip_effective, n_points))
        axes_outer = panel_axes_outer(p, n_ext, strip_effective)

        stats_o, zs_o = _compute_single_profile(
            df, p, axes_outer, x_pts_outer, sun_mask, df_sun,
            dni_ground, dhi_circ, dhi_horiz, dhi_iso, ghi, dli_daily_ref,
            par_frac=par_frac, domain_pitch=strip_effective)

        outer_par_rel = {}
        x_arr_outer = np.array(x_pts_outer)
        all_mask = np.ones(len(x_arr_outer), dtype=bool)
        for m in range(1, 13):
            dli_ref = stats_o[m]['dli_ref_p50']
            if dli_ref and dli_ref > 0:
                par_pts = stats_o[m]['p50'] / dli_ref
                outer_par_rel[m] = float(trapz_zone_mean(par_pts, x_arr_outer, all_mask))
            else:
                outer_par_rel[m] = 1.0

        outer_profile = {
            'stats': stats_o,
            'zs': zs_o,
            'strip_width': strip_effective,
            'par_rel': outer_par_rel,
        }

    return {
        'inner': inner_profiles,
        'outer': outer_profile,
        'strip_width': strip_effective if sau_esterna > 0 else 0.0,
        'strip_width_p95': strip_width,     # P95 ombra (non troncato)
        'area_fascia': area_fascia,          # [m²]
        'area_pieno_campo': area_pieno_campo,  # [m²]
    }


# ══════════════════════════════════════════════════════════════════════════════
# CORREZIONE BORDO N-S (LONGITUDINALE)
# ══════════════════════════════════════════════════════════════════════════════

def compute_dns_monthly(df, p):
    """
    Calcola d_NS medio mensile: distanza oltre l'estremità della stringa
    entro cui l'ombra del pannello è ancora presente.

        d_NS(t) = H / tan(α) × |cos(γ − axis_azimuth)|

    Restituisce dict {mese: d_NS_medio} per mesi 1-12.
    """
    H = p['H']
    ax_az = p.get('axis_azimuth', 180.0)
    sun_mask = df['apparent_elevation'].values > 2.0

    elev = df['apparent_elevation'].values
    azim = df['azimuth'].values

    elev_rad = np.radians(np.clip(elev, 0.1, 90.0))
    tan_elev = np.tan(elev_rad)
    cos_along = np.abs(np.cos(np.radians(azim - ax_az)))

    dns_all = np.where(sun_mask & (tan_elev > 0.01),
                       H / tan_elev * cos_along, 0.0)

    # M8 (v4.2.2): media PESATA sul DNI — l'ombra del beam esiste solo
    # quando c'e' beam; la media aritmetica era dominata dalle code
    # 1/tan(alfa) di alba/tramonto (fino a ~28*H con DNI~0) e gonfiava
    # il bonus FC_NS, soprattutto nei mesi invernali.
    dni_w = np.maximum(np.asarray(df['dni'].values, dtype=float), 0.0) \
        if 'dni' in df.columns else np.ones(len(dns_all))

    result = {}
    for m in range(1, 13):
        m_mask = (df.index.month == m) & sun_mask
        w = dni_w[m_mask]
        if m_mask.any() and w.sum() > 0:
            result[m] = float(np.average(dns_all[m_mask], weights=w))
        elif m_mask.any():
            result[m] = float(np.mean(dns_all[m_mask]))
        else:
            result[m] = 0.0

    return result


def compute_fc_ns(dns_monthly, L_tracker, zs):
    """
    Fattore correttivo longitudinale per mese.
    Con L=0 o d_NS=0, restituisce 1.0 per tutti i mesi.
    """
    result = {}
    for m in range(1, 13):
        if L_tracker <= 0 or dns_monthly.get(m, 0) <= 0:
            result[m] = 1.0
            continue

        d_ns = dns_monthly[m]
        frac_trans = min(2.0 * d_ns, L_tracker) / L_tracker

        dli_ref = zs[m].get('dli_ref_p50', 0)
        dli_sau = zs[m].get('SAU', {}).get('p50', 0)
        par_rel = dli_sau / dli_ref if (dli_ref > 0 and dli_sau > 0) else 1.0

        bonus = (1.0 - par_rel) * 0.5 * frac_trans
        result[m] = 1.0 + bonus

    return result


# ══════════════════════════════════════════════════════════════════════════════
# K_AGV MEDIO IMPIANTO
# ══════════════════════════════════════════════════════════════════════════════

def compute_kagv_impianto(yield_data_inf, edge_data, fc_ns, p, crop_keys=None):
    """
    Calcola K_agv medio impianto pesato per area, combinando:
    - File interne (profilo campo infinito): area = n_interne × SAU_pitch × L
    - File di bordo E-O, pitch interno: area = 1 × SAU_pitch × L ciascuna
    - Fascia esterna: area_fascia [m²] (da edge_data, calcolata dal P95 ombra)
    - SAU pieno campo: area_pieno_campo [m²] (= SAU_esterna − area_fascia, include N-S)
    - Correzione N-S (FC_NS) applicata a tutte le file del blocco
    """
    if crop_keys is None:
        crop_keys = list(yield_data_inf.keys())

    n_ext = p['n_ext']
    n_file = p.get('n_file', 0)
    pitch = p['pitch']
    SAU_pitch = p['SAU']
    L_tracker = p.get('L_tracker', 0.0)
    L_eff = L_tracker if L_tracker > 0 else 1.0

    area_fascia = edge_data.get('area_fascia', 0.0)
    area_pieno_campo = edge_data.get('area_pieno_campo', 0.0)

    inner_profiles = edge_data['inner']
    outer_profile = edge_data.get('outer')

    # M7 (v4.2.2): Laub applicata PUNTO PER PUNTO e poi mediata (come
    # compute_yield_curves per il campo infinito). La curva e' concava:
    # Laub(RSR_media) sovrastimava sistematicamente bordo e soprattutto
    # fascia esterna (gradiente PAR massimo) di 0.5-2 pp.
    def _kagv_pointwise(profile_stats, crop_key, m, x_mask=None):
        dli_ref = profile_stats[m]['dli_ref_p50']
        p50 = np.asarray(profile_stats[m]['p50'], dtype=float)
        if not (dli_ref and dli_ref > 0) or p50.size == 0:
            return np.nan
        par_pts = np.clip(p50 / dli_ref, 0.0, None)
        rsr_pts = np.clip(1.0 - par_pts, 0.0, 1.0)
        y_pts = laub_yield(rsr_pts, crop_key) / 100.0
        x_arr = np.linspace(0.0, 1.0, len(y_pts))
        mask = x_mask if x_mask is not None else np.ones(len(y_pts), bool)
        if not mask.any():
            return np.nan
        return float(trapz_zone_mean(y_pts, x_arr, mask))

    def _kagv_outer(crop_key, m):
        """K_agv puntuale della fascia esterna (tutti i punti)."""
        if outer_profile is None:
            return float(laub_yield(0.0, crop_key)) / 100.0
        v = _kagv_pointwise(outer_profile['stats'], crop_key, m)
        if np.isnan(v):
            par_rel = outer_profile.get('par_rel', {}).get(m, 1.0)
            rsr = np.clip(1.0 - par_rel, 0.0, 1.0)
            return float(laub_yield(rsr, crop_key)) / 100.0
        return v

    def _kagv_from_profile(profile_stats, profile_zs, crop_key, m):
        """K_agv puntuale del pitch di bordo, sulla zona SAU."""
        n_pts = len(np.asarray(profile_stats[m]['p50']))
        x_abs = np.linspace(0.0, pitch, n_pts)
        sau_mask = (x_abs >= p.get('sanu', 0.5)) & \
                   (x_abs <= pitch - p.get('sanu', 0.5))
        v = _kagv_pointwise(profile_stats, crop_key, m, x_mask=sau_mask)
        return v

    result = {}

    for crop_key in crop_keys:
        kagv_pieno = float(laub_yield(0.0, crop_key)) / 100.0

        kagv_inf = {}
        kagv_imp = {}
        fc_imp = {}

        for m in range(1, 13):
            k_inf = yield_data_inf[crop_key]['kagv'].get(m, {}).get('SAU', np.nan)
            kagv_inf[m] = k_inf

            if np.isnan(k_inf) or n_file <= 0:
                kagv_imp[m] = k_inf
                fc_imp[m] = 1.0
                continue

            # ── Costruzione media pesata per area [m²] ─────────────────────
            #
            # Impianto = blocco tracker + SAU esterna
            # Blocco = file bordo sinistro + file interne + file bordo destro
            # SAU esterna = fascia (ombreggiata) + pieno campo (residuo)

            weights = []    # lista di (k_agv, area_m2, is_tracker)
                            # is_tracker=True → riceve FC_NS
                            # is_tracker=False → non riceve FC_NS

            # Area per pitch (tutte le file hanno la stessa area trasversale)
            area_pitch = SAU_pitch * L_eff

            # 1. Fascia esterna (area totale, già calcolata)
            if area_fascia > 0:
                k_outer = _kagv_outer(crop_key, m)
                weights.append((k_outer, area_fascia, False))

            # 2. Allocazione simmetrica delle file bordo/interne
            # Con n_file file totali e n_ext profili di bordo per lato:
            #   bordo_sx = min(n_ext, n_file // 2 + n_file % 2)
            #   bordo_dx = min(n_ext, n_file // 2)
            #   interne  = n_file - bordo_sx - bordo_dx
            # M6 (v4.2.2): fra n_file file esistono n_file-1 strisce di
            # pitch (la fascia oltre l'asse delle file di bordo e' gia'
            # contata in area_fascia): contarne n_file duplicava una
            # striscia, con peso errato ~1/n_file.
            _n_str = max(0, n_file - 1)
            n_bordo_sx = min(n_ext, (_n_str + 1) // 2)
            n_bordo_dx = min(n_ext, _n_str // 2)
            n_interne = max(0, _n_str - n_bordo_sx - n_bordo_dx)

            # File dal bordo sinistro
            for k in range(n_bordo_sx):
                ep = inner_profiles[k] if k < len(inner_profiles) else None
                if ep is not None:
                    k_edge = _kagv_from_profile(ep['stats'], ep['zs'], crop_key, m)
                else:
                    k_edge = np.nan
                if np.isnan(k_edge):
                    k_edge = k_inf
                weights.append((k_edge, area_pitch, True))

            # File interne (campo infinito)
            if n_interne > 0:
                weights.append((k_inf, area_pitch * n_interne, True))

            # File dal bordo destro (specchio dei profili sinistri)
            for k in range(n_bordo_dx):
                ep = inner_profiles[k] if k < len(inner_profiles) else None
                if ep is not None:
                    k_edge = _kagv_from_profile(ep['stats'], ep['zs'], crop_key, m)
                else:
                    k_edge = np.nan
                if np.isnan(k_edge):
                    k_edge = k_inf
                weights.append((k_edge, area_pitch, True))

            # 5. SAU pieno campo residua
            if area_pieno_campo > 0:
                weights.append((kagv_pieno, area_pieno_campo, False))

            # Media pesata con FC_NS selettivo:
            # FC_NS corregge il bordo N-S delle stringhe tracker.
            # La SAU pieno campo e la fascia esterna non sono sotto tracker
            # → non ricevono il bonus FC_NS.
            fc_n = fc_ns.get(m, 1.0)

            # Separa contributi tracker da contributi esterni usando il tag esplicito
            kw_tracker = 0.0
            w_tracker = 0.0
            kw_external = 0.0
            w_external = 0.0
            for k_val, area_val, is_tracker in weights:
                if is_tracker:
                    kw_tracker += k_val * area_val
                    w_tracker += area_val
                else:
                    kw_external += k_val * area_val
                    w_external += area_val

            total_w = w_tracker + w_external
            if total_w > 0:
                kagv_imp[m] = (kw_tracker * fc_n + kw_external) / total_w
            else:
                kagv_imp[m] = k_inf
            fc_imp[m] = kagv_imp[m] / k_inf if k_inf > 0 else 1.0

        result[crop_key] = {
            'kagv_inf': kagv_inf,
            'kagv_impianto': kagv_imp,
            'fc_impianto': fc_imp,
            'kagv_pieno_campo': kagv_pieno,
            'label_it': LAUB_COEFFICIENTS[crop_key]['label_it'],
        }

    return result
