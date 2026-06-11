"""
solratio_pdf.py  |  SolRatio v4.3.0
===================================================
Generazione report PDF di sintesi (5 pagine).

Pagina 1: Introduzione + Parametri + DLI + PAR + Riduzione PAR per zona
Pagina 2: Grafici Profilo_PAR_Spaziale (PAR relativa mensile + DLI mensile)
Pagina 3: K_agv SAU + ottimizzazione pitch + K_agv impianto (effetto bordo)
Pagina 4-5: Descrizione modello + validazione + glossario + assunzioni +
            software + riferimenti (impaginazione libera; nessuna interruzione
            forzata prima di "Assunzioni e limitazioni").

Numerazione pagine "pagina X di Y" in basso a sinistra (NumberedCanvas).

Dipendenze: reportlab (pip install reportlab), matplotlib (per i grafici pag. 2).
Se reportlab non è disponibile, la generazione viene saltata con un avviso.
Se matplotlib non è disponibile, i grafici di pag. 2 vengono saltati con nota.
"""

import os
from io import BytesIO
import numpy as np
from datetime import datetime

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm, cm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, KeepTogether, Image,
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.pdfgen import canvas as _rl_canvas
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from solratio_core import MONTHS, LAUB_COEFFICIENTS, __version__


# ══════════════════════════════════════════════════════════════════════════════
# STILI (solo se reportlab disponibile)
# ══════════════════════════════════════════════════════════════════════════════

if HAS_REPORTLAB:
    BLUE_DARK  = HexColor('#1F4E79')
    BLUE_MED   = HexColor('#2E75B6')
    BLUE_LIGHT = HexColor('#BDD7EE')
    GREEN      = HexColor('#70AD47')
    GREEN_LIGHT= HexColor('#E2EFDA')
    ORANGE     = HexColor('#ED7D31')
    GRAY       = HexColor('#595959')

def _styles():
    return {
        'title': ParagraphStyle('title', fontName='Helvetica-Bold',
                                fontSize=14, textColor=BLUE_DARK,
                                spaceAfter=2*mm),
        'subtitle': ParagraphStyle('subtitle', fontName='Helvetica',
                                   fontSize=9, textColor=GRAY,
                                   spaceAfter=3*mm),
        'section': ParagraphStyle('section', fontName='Helvetica-Bold',
                                  fontSize=10, textColor=BLUE_DARK,
                                  spaceBefore=3*mm, spaceAfter=2*mm),
        'body': ParagraphStyle('body', fontName='Helvetica', fontSize=9,
                               leading=12, spaceAfter=2*mm),
        'small': ParagraphStyle('small', fontName='Helvetica', fontSize=8,
                                textColor=GRAY),
        'param_label': ParagraphStyle('plabel', fontName='Helvetica',
                                      fontSize=9),
        'param_value': ParagraphStyle('pvalue', fontName='Helvetica-Bold',
                                      fontSize=9, textColor=BLUE_DARK),
    }


def _table_style_header():
    """Stile per tabelle con header blu."""
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE_MED),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F2F2F2')]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# CANVAS NUMERATO (pagina X di Y in basso a sinistra)
# ══════════════════════════════════════════════════════════════════════════════

if HAS_REPORTLAB:
    class NumberedCanvas(_rl_canvas.Canvas):
        """
        Canvas che inserisce 'pagina X di Y' in basso a sinistra su ogni pagina.
        Usa il pattern a doppio passaggio: raccoglie gli stati di tutte le pagine
        in showPage() e li rilascia in save() dopo aver calcolato il totale.
        """
        def __init__(self, *args, **kwargs):
            _rl_canvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self._draw_page_number(num_pages)
                _rl_canvas.Canvas.showPage(self)
            _rl_canvas.Canvas.save(self)

        def _draw_page_number(self, page_count):
            self.setFont('Helvetica', 8)
            self.setFillColor(GRAY)
            self.drawString(
                15 * mm, 10 * mm,
                f"pagina {self._pageNumber} di {page_count}"
            )


# ══════════════════════════════════════════════════════════════════════════════
# GRAFICI PAGINA 2 (Profilo_PAR_Spaziale)
# ══════════════════════════════════════════════════════════════════════════════

def _generate_par_charts(zs):
    """
    Genera i due grafici del foglio Profilo_PAR_Spaziale come PNG in memoria.

    Chart 1: PAR relativa mensile per zona (5 zone)
    Chart 2: DLI mensile per zona (DLI rif. + 5 zone)

    Returns:
        tuple (BytesIO, BytesIO) con i PNG dei due grafici, oppure (None, None)
        se matplotlib non e' disponibile.
    """
    if not HAS_MATPLOTLIB:
        return None, None

    ZONES = ['Sotto-tracker', 'Bordo', 'Centrale', 'SAU', 'Media pitch']
    # Colori coerenti con il tema PDF e distintivi per zona
    COLORS = {
        'Sotto-tracker': '#C00000',   # rosso scuro (max ombra)
        'Bordo':         '#ED7D31',   # arancione
        'Centrale':      '#FFC000',   # giallo/ambra (meno ombra)
        'SAU':           '#70AD47',   # verde (zona coltivabile)
        'Media pitch':   '#1F4E79',   # blu scuro (media)
    }
    MONTH_LABELS = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu',
                    'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic']
    months = list(range(1, 13))

    # ── Chart 1: PAR relativa mensile per zona ──────────────────────────
    fig1, ax1 = plt.subplots(figsize=(7.2, 3.6), dpi=150)
    for zona in ZONES:
        y = []
        for m in months:
            ref = zs[m]['dli_ref_p50']
            val = zs[m][zona]['p50'] / ref if ref and ref > 0 else 0
            y.append(val)
        ax1.plot(months, y, marker='o', markersize=4, linewidth=1.5,
                 label=zona, color=COLORS[zona])
    ax1.set_xticks(months)
    ax1.set_xticklabels(MONTH_LABELS, fontsize=8)
    ax1.set_ylabel('PAR relativa (1.00 = cielo aperto)', fontsize=9)
    ax1.set_title('PAR relativa mensile per zona',
                  fontsize=10, fontweight='bold', color='#1F4E79')
    ax1.set_ylim(0, 1.05)
    ax1.grid(True, linestyle=':', alpha=0.5)
    ax1.legend(loc='lower center', ncol=5, fontsize=8,
               framealpha=0.9, bbox_to_anchor=(0.5, -0.28))
    fig1.tight_layout()
    buf1 = BytesIO()
    fig1.savefig(buf1, format='png', dpi=150, bbox_inches='tight')
    buf1.seek(0)
    plt.close(fig1)

    # ── Chart 2: DLI mensile per zona ───────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(7.2, 3.6), dpi=150)
    y_ref = [zs[m]['dli_ref_p50'] for m in months]
    ax2.plot(months, y_ref, marker='s', markersize=5, linewidth=2,
             label='DLI rif. (cielo aperto)', color='black', linestyle='--')
    for zona in ZONES:
        y = [zs[m][zona]['p50'] for m in months]
        ax2.plot(months, y, marker='o', markersize=4, linewidth=1.5,
                 label=zona, color=COLORS[zona])
    ax2.set_xticks(months)
    ax2.set_xticklabels(MONTH_LABELS, fontsize=8)
    ax2.set_ylabel('DLI (mol PAR/m$^2$/giorno)', fontsize=9)
    ax2.set_title('DLI mensile per zona',
                  fontsize=10, fontweight='bold', color='#1F4E79')
    ax2.set_ylim(bottom=0)
    ax2.grid(True, linestyle=':', alpha=0.5)
    ax2.legend(loc='lower center', ncol=3, fontsize=8,
               framealpha=0.9, bbox_to_anchor=(0.5, -0.36))
    fig2.tight_layout()
    buf2 = BytesIO()
    fig2.savefig(buf2, format='png', dpi=150, bbox_inches='tight')
    buf2.seek(0)
    plt.close(fig2)

    return buf1, buf2


# ══════════════════════════════════════════════════════════════════════════════
# GENERAZIONE PDF
# ══════════════════════════════════════════════════════════════════════════════

def generate_report_pdf(pdf_path, p, zs, yield_data, opt_results=None,
                        kagv_imp=None, stats=None, x_pts=None):
    """
    Genera un report PDF di sintesi (3 pagine).

    Contenuto:
      Pagina 1: Introduzione + Parametri impianto + DLI + PAR + Riduzione PAR
      Pagina 2: K_agv + effetto bordo + pitch ottimale + inizio descrizione modello
      Pagina 3: Descrizione modello (cont.) + validazione + glossario + assunzioni + riferimenti

    Parametri:
      pdf_path    : percorso di output del file PDF
      p           : dict parametri impianto
      zs          : dict zone_stats (da compute_monthly_stats + zone_stats)
      yield_data  : dict resa colturale (da compute_yield_curves)
      opt_results : dict ottimizzazione pitch (opzionale)
      stats       : dict monthly_stats per profilo spaziale (opzionale)
      x_pts       : array punti x lungo il pitch (opzionale)
    """
    if not HAS_REPORTLAB:
        print('  PDF: reportlab non installato, report PDF saltato.')
        print('       Installa con: pip install reportlab')
        return False

    S = _styles()

    doc = SimpleDocTemplate(
        pdf_path, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
    )
    story = []
    page_w = A4[0] - 30*mm  # larghezza utile

    # ── PAGINA 1 ──────────────────────────────────────────────────────────

    # Titolo
    proj_name = os.path.basename(os.path.dirname(pdf_path))
    story.append(Paragraph(f'SolRatio v{__version__} -- Report', S['title']))
    story.append(Paragraph(
        f'Progetto: {proj_name} | {datetime.now().strftime("%d/%m/%Y %H:%M")}',
        S['subtitle']))

    # ── Introduzione ─────────────────────────────────────────────────────
    story.append(Paragraph(
        'Il presente report riporta i risultati della simulazione dell\'irradianza solare '
        'al suolo nell\'area sottostante l\'impianto agrivoltaico, condotta con il modello '
        'SolRatio v4 basato su ray-tracing tridimensionale (Radiance/bifacial_radiance NREL). '
        'I risultati consentono di verificare la compatibilita tra produzione energetica '
        'e produzione agricola ai sensi delle Linee Guida MiTE (D.M. 436/2023).',
        S['body']))

    # ── Parametri impianto ────────────────────────────────────────────────
    story.append(Paragraph('Parametri impianto', S['section']))

    params = [
        ['Coordinate', f'{p["lat"]:.4f} N  {p["lon"]:.4f} E'],
        ['Pitch', f'{p["pitch"]:.2f} m'],
        ['W (larghezza modulo)', f'{p["W"]:.2f} m'],
        ['H_min_terra', f'{p["H_min_terra"]:.2f} m'],
        ['H_mozzo', f'{p["H"]:.3f} m'],
        ['GCR', f'{p["GCR"]:.3f}'],
        ['beta_max', f'{p["beta_max"]:.0f} deg'],
        ['SAU', f'{p["SAU"]:.2f} m ({p["SAU"]/p["pitch"]*100:.0f}% pitch)'],
        ['Modalità tracker',
         {0: 'Astronomico (no backtracking)',
          1: 'Backtracking',
          2: f'Tilt fisso θ={p.get("theta_fix", 0.0):+.1f}°'
          }.get(int(p['backtracking']), 'Backtracking')],
        ['Albedo', f'{p.get("albedo", 0.23):.2f}'],
        *([['Trasmittanza diffusa τ_diff', f'{p.get("tau_diff", 0):.2f}']]
          if p.get('tau_diff', 0) > 0 else []),
        *([['Fattore bifaccialità', f'{p.get("bifaciality_factor", 0):.2f}']]
          if p.get('bifaciality_factor', 0) > 0 else []),
        ['Serie PVGIS', f'{p["yr_start"]}-{p["yr_end"]}'],
    ]
    if p.get('tau', 0) > 0:
        params.append(['Trasmittanza', f'{p["tau"]:.2f}'])
    if p.get('slope_pct', 0) > 0:
        params.append(['Pendenza', f'{p["slope_pct"]:.1f}% (az. discesa {p.get("slope_azimuth", 0):.0f} deg)'])
    # Pali: disabilitati in v4.1.0 — vedi CHANGELOG

    # Due colonne
    n_half = (len(params) + 1) // 2
    rows_p = []
    for i in range(n_half):
        row = [params[i][0], params[i][1]]
        if i + n_half < len(params):
            row += [params[i + n_half][0], params[i + n_half][1]]
        else:
            row += ['', '']
        rows_p.append(row)

    t_params = Table(rows_p, colWidths=[page_w*0.22, page_w*0.28,
                                         page_w*0.22, page_w*0.28])
    t_params.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('FONTNAME', (3, 0), (3, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TEXTCOLOR', (1, 0), (1, -1), BLUE_DARK),
        ('TEXTCOLOR', (3, 0), (3, -1), BLUE_DARK),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    story.append(t_params)
    story.append(Spacer(1, 2*mm))

    # ── DLI per zona ─────────────────────────────────────────────────────
    story.append(Paragraph('DLI medio giornaliero P50 (mol PAR/m<super>2</super>/d)', S['section']))

    SEASONS = {'Primavera': [3,4,5], 'Estate': [6,7,8], 'Autunno': [9,10,11]}
    zones_display = ['DLI rif.', 'Sotto-tracker', 'Bordo', 'Centrale', 'SAU', 'Media pitch']

    hdr = ['Zona', 'Annuo'] + list(SEASONS.keys())
    rows_dli = [hdr]
    for zona_label in zones_display:
        row = [zona_label]
        if zona_label == 'DLI rif.':
            annual = np.mean([zs[m]['dli_ref_p50'] for m in range(1, 13)])
            row.append(f'{annual:.1f}')
            for _, months in SEASONS.items():
                row.append(f'{np.mean([zs[m]["dli_ref_p50"] for m in months]):.1f}')
        else:
            annual = np.mean([zs[m][zona_label]['p50'] for m in range(1, 13)])
            row.append(f'{annual:.1f}')
            for _, months in SEASONS.items():
                row.append(f'{np.mean([zs[m][zona_label]["p50"] for m in months]):.1f}')
        rows_dli.append(row)

    t_dli = Table(rows_dli, colWidths=[page_w*0.28] + [page_w*0.18]*4)
    t_dli.setStyle(_table_style_header())
    # Bold SAU row
    sau_row = zones_display.index('SAU') + 1
    t_dli.setStyle(TableStyle([
        ('FONTNAME', (0, sau_row), (-1, sau_row), 'Helvetica-Bold'),
    ]))
    story.append(t_dli)
    story.append(Spacer(1, 1*mm))

    # Commento DLI
    dli_ref_ann = np.mean([zs[m]['dli_ref_p50'] for m in range(1, 13)])
    dli_sau_ann = np.mean([zs[m]['SAU']['p50'] for m in range(1, 13)])
    dli_ratio = dli_sau_ann / dli_ref_ann if dli_ref_ann > 0 else 0
    story.append(Paragraph(
        f'Il DLI medio annuo nella zona SAU risulta pari a <b>{dli_sau_ann:.1f} mol/m2/d</b>, '
        f'corrispondente al <b>{dli_ratio*100:.0f}%</b> del valore di riferimento in cielo aperto '
        f'({dli_ref_ann:.1f} mol/m2/d). La riduzione di luce e dovuta all\'ombreggiamento '
        f'dei pannelli e varia spazialmente lungo la sezione trasversale dell\'interasse.',
        S['small']))
    story.append(Spacer(1, 2*mm))

    # ── PAR relativa ─────────────────────────────────────────────────────
    story.append(Paragraph('PAR relativa P50 (1.00 = cielo aperto)', S['section']))

    hdr_par = ['Zona', 'Annuo'] + list(SEASONS.keys())
    rows_par = [hdr_par]
    for zona in ['Sotto-tracker', 'Bordo', 'Centrale', 'SAU', 'Media pitch']:
        row = [zona]
        dli_z_ann = np.mean([zs[m][zona]['p50'] for m in range(1, 13)])
        dli_ref_ann = np.mean([zs[m]['dli_ref_p50'] for m in range(1, 13)])
        row.append(f'{dli_z_ann/dli_ref_ann:.3f}' if dli_ref_ann > 0 else '-')
        for _, months in SEASONS.items():
            dz = np.mean([zs[m][zona]['p50'] for m in months])
            dr = np.mean([zs[m]['dli_ref_p50'] for m in months])
            row.append(f'{dz/dr:.3f}' if dr > 0 else '-')
        rows_par.append(row)

    t_par = Table(rows_par, colWidths=[page_w*0.28] + [page_w*0.18]*4)
    t_par.setStyle(_table_style_header())
    story.append(t_par)
    story.append(Spacer(1, 1*mm))

    # Commento PAR relativa
    try:
        _par_sau = [r for r in rows_par if r[0] == 'SAU'][0]
        _par_val = float(_par_sau[1])
        story.append(Paragraph(
            f'La PAR relativa nella zona SAU e pari a <b>{_par_val:.3f}</b>: le colture '
            f'ricevono il {_par_val*100:.0f}% della radiazione fotosintetica rispetto al '
            f'pieno campo. La zona centrale, meno ombreggiata, raggiunge valori superiori, '
            f'mentre la zona sotto-tracker presenta la riduzione massima.',
            S['small']))
    except (IndexError, ValueError):
        pass
    story.append(Spacer(1, 2*mm))

    # ── Tabella riduzione PAR mensile (stagione vegetativa) ──────────────
    story.append(Paragraph('Riduzione PAR per zona -- stagione vegetativa (%)',
                           S['section']))

    CROP_MONTHS = list(range(3, 10))  # Mar-Set
    CROP_LABELS = [MONTHS[m-1] for m in CROP_MONTHS]
    zones_red = ['Sotto-tracker', 'Bordo', 'Centrale', 'SAU', 'Media pitch']

    hdr_red = ['Zona'] + CROP_LABELS + ['Media']
    rows_red = [hdr_red]
    for zona in zones_red:
        row = [zona]
        reds = []
        for m in CROP_MONTHS:
            dli_z = zs[m][zona]['p50']
            dli_ref = zs[m]['dli_ref_p50']
            red = (1 - dli_z / dli_ref) * 100 if dli_ref > 0 else 0
            reds.append(red)
            row.append(f'{red:.0f}%')
        row.append(f'{np.mean(reds):.0f}%')
        rows_red.append(row)

    cw = [page_w*0.18] + [page_w*(0.82/8)]*8
    t_red = Table(rows_red, colWidths=cw)
    t_red.setStyle(_table_style_header())
    # Evidenzia colonna Media
    t_red.setStyle(TableStyle([
        ('FONTNAME', (-1, 1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (-1, 1), (-1, -1), HexColor('#E2EFDA')),
    ]))
    story.append(t_red)

    # ── FINE PAGINA 1 ─────────────────────────────────────────────────────
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # PAGINA 2: Grafici Profilo_PAR_Spaziale
    # ══════════════════════════════════════════════════════════════════════
    story.append(Paragraph('Profilo PAR spaziale -- andamento mensile per zona',
                           S['title']))
    story.append(Paragraph(
        'Andamento mensile della PAR relativa e del DLI assoluto per le zone '
        'spaziali lungo la sezione trasversale dell\'interasse.',
        S['subtitle']))

    buf_par, buf_dli = _generate_par_charts(zs)
    if buf_par is not None and buf_dli is not None:
        # Larghezza grafico pari alla larghezza utile; altezza proporzionale
        img_w = page_w
        img_h = img_w * (3.6 / 7.2)  # mantiene aspect ratio figsize
        img1 = Image(buf_par, width=img_w, height=img_h)
        img2 = Image(buf_dli, width=img_w, height=img_h)
        story.append(img1)
        story.append(Spacer(1, 3*mm))
        story.append(img2)
    else:
        story.append(Paragraph(
            'Grafici non disponibili: matplotlib non installato. '
            'Installa con: pip install matplotlib',
            S['small']))

    # ── FINE PAGINA 2 ─────────────────────────────────────────────────────
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # PAGINA 3: K_agv per coltura (SAU) + ottimizzazione pitch + effetto bordo
    # ══════════════════════════════════════════════════════════════════════
    if yield_data:
        story.append(Paragraph('K_agv SAU -- media stagione vegetativa (Mar-Set)', S['section']))

        # K_agv tabella in PERCENTUALE (v4.1.0)
        hdr_k = ['Coltura', 'K_agv SAU (%)', 'K_agv Centr. (%)', 'Coltiv. >80%']
        rows_k = [hdr_k]
        for crop_key, data in yield_data.items():
            kagv_sau = np.nanmean([data['kagv'].get(m, {}).get('SAU', np.nan)
                                   for m in range(3, 10)]) * 100.0
            kagv_cen = np.nanmean([data['kagv'].get(m, {}).get('Centrale', np.nan)
                                   for m in range(3, 10)]) * 100.0
            cult_80  = np.nanmean([data['cultivability'].get(m, {}).get('>80%', np.nan)
                                   for m in range(3, 10)])
            rows_k.append([
                data['label_it'],
                f'{kagv_sau:.1f}' if not np.isnan(kagv_sau) else '-',
                f'{kagv_cen:.1f}' if not np.isnan(kagv_cen) else '-',
                f'{cult_80:.0f}%' if not np.isnan(cult_80) else '-',
            ])

        t_k = Table(rows_k, colWidths=[page_w*0.34, page_w*0.22, page_w*0.22, page_w*0.22])
        t_k.setStyle(_table_style_header())
        # Color code K_agv (soglie in % adesso)
        for ri in range(1, len(rows_k)):
            try:
                v = float(rows_k[ri][1])
                if v >= 100.0:
                    c = GREEN_LIGHT
                elif v >= 80.0:
                    c = HexColor('#FFF2CC')
                else:
                    c = HexColor('#FCE4D6')
                t_k.setStyle(TableStyle([('BACKGROUND', (1, ri), (1, ri), c)]))
            except (ValueError, IndexError):
                pass
        story.append(t_k)
        story.append(Spacer(1, 1*mm))

        # Commento K_agv (soglia 80% in % anziché 0.80)
        try:
            _kagv_rows = [r for r in rows_k[1:] if r[1] != '-']
            _k_above = [r[0] for r in _kagv_rows if float(r[1]) >= 80.0]
            if _k_above:
                story.append(Paragraph(
                    f'Le colture con K_agv SAU >= 80% ({", ".join(_k_above)}) presentano '
                    f'una resa attesa superiore all\'80% rispetto al pieno campo, '
                    f'confermando la compatibilita agronomica della configurazione simulata.',
                    S['small']))
            else:
                story.append(Paragraph(
                    'Nessuna coltura raggiunge K_agv >= 80% nella zona SAU con la '
                    'configurazione attuale. Si consiglia di valutare un aumento '
                    'dell\'interasse (pitch) o la selezione di colture piu tolleranti all\'ombra.',
                    S['small']))
        except (ValueError, IndexError):
            pass
        story.append(Spacer(1, 2*mm))

    # ── Effetto bordo ──────────────────────────────────────────────────────
    if kagv_imp is not None and len(kagv_imp) > 0:
        story.append(Paragraph(
            'K_agv impianto -- effetto bordo (media Mar-Set)', S['section']))
        story.append(Paragraph(
            f'Correzione per file perimetrali, estremita stringhe e SAU esterna '
            f'(N_file={p.get("n_file",0)}, L_tracker={p.get("L_tracker",0):.0f} m, '
            f'SAU_ext={p.get("sau_esterna",0):.0f} m2).',
            S['body']))

        # Tabella K_agv impianto in PERCENTUALE (v4.1.0). FC adimensionale.
        hdr_edge = ['Coltura', 'K_agv inf (%)', 'K_agv imp. (%)', 'FC', 'dK (%)']
        rows_edge = [hdr_edge]
        for crop_key, data in kagv_imp.items():
            k_inf = np.nanmean([data['kagv_inf'].get(m, np.nan)
                                 for m in range(3, 10)]) * 100.0
            k_imp = np.nanmean([data['kagv_impianto'].get(m, np.nan)
                                 for m in range(3, 10)]) * 100.0
            fc = np.nanmean([data['fc_impianto'].get(m, np.nan)
                              for m in range(3, 10)])
            dk = k_imp - k_inf if not (np.isnan(k_imp) or np.isnan(k_inf)) else np.nan
            rows_edge.append([
                data.get('label_it', crop_key),
                f'{k_inf:.1f}' if not np.isnan(k_inf) else '-',
                f'{k_imp:.1f}' if not np.isnan(k_imp) else '-',
                f'{fc:.3f}' if not np.isnan(fc) else '-',
                f'{dk:+.1f}' if not np.isnan(dk) else '-',
            ])

        t_edge = Table(rows_edge, colWidths=[page_w*0.30, page_w*0.175,
                                              page_w*0.175, page_w*0.175, page_w*0.175])
        ts_edge = _table_style_header()
        # Green highlight on K_agv imp column
        for ri in range(1, len(rows_edge)):
            ts_edge.add('BACKGROUND', (2, ri), (2, ri), GREEN_LIGHT)
        t_edge.setStyle(ts_edge)
        story.append(t_edge)

    # ── FINE PAGINA 3 ─────────────────────────────────────────────────────
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # PAGINE 4-5: Descrizione modello + validazione + glossario +
    # assunzioni e limitazioni + software + riferimenti
    # (impaginazione libera: nessun PageBreak forzato prima di
    # "Assunzioni e limitazioni")
    # ══════════════════════════════════════════════════════════════════════
    story.append(Paragraph('Descrizione del modello di calcolo', S['section']))

    # Introduzione generale
    story.append(Paragraph(
        'SolRatio v4 quantifica l\'irradianza solare al suolo in impianti agrivoltaici '
        'con tracker monoassiale mediante simulazione 3D ray-tracing. Il modello utilizza '
        'il software Radiance (LBNL), standard internazionale per la simulazione della luce '
        'naturale, integrato tramite il framework bifacial_radiance (NREL v0.5.1). '
        'Per ogni ora dell\'anno tipo, viene costruita la scena tridimensionale dell\'impianto '
        '(pannelli, suolo, cielo) e calcolata l\'irradianza in una griglia di punti sensore '
        'al livello del suolo. Il rapporto tra irradianza sotto i pannelli e in cielo aperto '
        'fornisce la frazione di luce disponibile per le colture.',
        S['body']))

    model_desc = [
        ('Dati meteorologici',
         'Serie storiche orarie GHI, DNI, DHI dal database satellitare PVGIS-SARAH3 '
         '(JRC, Commissione Europea). Dai dati pluriennali viene costruito un anno '
         'meteorologico tipo (TMY) selezionando, per ciascun mese, l\'anno con GHI '
         'piu prossimo alla mediana del periodo.'),

        ('Posizione solare e tracker',
         'Posizione solare calcolata con l\'algoritmo di Reda &amp; Andreas (2004), '
         'accuratezza +/-0.0003 deg, implementato in pvlib-python. L\'angolo di '
         'rotazione del tracker (theta) segue l\'algoritmo di backtracking di '
         'Lorenzo (2011). Da theta si determinano inclinazione e azimut della scena 3D.'),

        ('Scena 3D Radiance',
         'La geometria comprende: moduli fotovoltaici (rettangoli opachi o semitrasparenti), '
         'array multi-fila (fino a 2xN_ext+1 file), suolo con albedo specificato (disco '
         'fisico + emisfero terreno) e cielo luminoso generato da gendaylit (modello Perez). '
         'Per ogni angolo theta unico vengono pre-generate scene con identificativo univoco, '
         'riutilizzate per tutte le ore con la stessa configurazione geometrica.'),

        ('Simulazione ray-tracing',
         'Per ciascuna delle ~4000 ore diurne, il programma rtrace (Radiance) traccia i '
         'raggi luminosi dalla sorgente cielo attraverso la scena 3D fino ai punti sensore '
         'al suolo. Il calcolo considera rimbalzi multipli della luce e il campionamento '
         'emisferico di Radiance con parametri configurabili (default 2 ambient bounces, '
         '2048 divisioni, 256 super-campioni; i valori del run sono nel foglio Parametri). L\'irradianza e calcolata come (R+G+B)/3 [W/m2].'),

        ('Parallelizzazione',
         'Le simulazioni orarie sono distribuite su worker paralleli (80% dei core CPU, '
         'max 28). Il tempo di calcolo tipico e di 30-60 minuti per un anno completo '
         'su un PC con 8 core.'),

        ('Cielo aperto di riferimento',
         'Un secondo passaggio simula ogni ora senza pannelli (solo cielo + suolo) per '
         'ottenere l\'irradianza indisturbata. Il rapporto IRR_pannelli/IRR_cielo_aperto '
         'fornisce la PAR relativa, indipendente dalla variabilita meteorologica.'),

        ('PAR e DLI',
         'L\'irradianza al suolo e convertita in PAR (Radiazione Fotosinteticamente Attiva, '
         '400-700 nm) con i fattori PAR_frac = 0.45 e 4.57 umol/J (McCree 1972). '
         'Il DLI (Daily Light Integral, mol PAR/m2/giorno) e l\'integrale giornaliero, '
         'parametro chiave per la valutazione agronomica.'),

        ('Zone spaziali',
         'Il pitch e suddiviso in: Sotto-tracker (coperto dalla proiezione verticale), '
         'Bordo (coperto intermittentemente), Centrale (mai coperto), SAU (pitch meno SANU), '
         'Media pitch (tutti i punti). I valori per zona sono medie integrali trapezoidali.'),

        ('Resa colturale',
         'Il modello di Laub et al. (2022) stima la resa relativa Y_rel in funzione della '
         'Relative Shade Ratio RSR = 1 - PAR_rel, con la formula '
         'Y_rel = 10^(2 + alpha x RSR + beta x RSR2). '
         'I coefficienti alpha e beta sono calibrati per 9 tipologie colturali. '
         'K_agv = Y_rel / 100 e il coefficiente di resa agrivoltaica.'),
    ]

    if p.get('n_file', 0) > 0:
        model_desc.append(
            ('Effetto bordo',
             'Le file perimetrali del blocco hanno meno pannelli adiacenti e ricevono piu luce. '
             'Il modello ricalcola il profilo di irradianza per le file di bordo, applica una '
             'correzione longitudinale (FC_NS) per le estremita delle stringhe, e media il K_agv '
             'pesato per area includendo la SAU esterna (4 lati) a pieno campo.'))

    for title, text in model_desc:
        story.append(Paragraph(
            f'<b>{title}</b>: {text}', S['body']))

    story.append(Spacer(1, 4*mm))

    # Validazione
    story.append(Paragraph('Validazione', S['section']))
    story.append(Paragraph(
        'Il modello e stato validato confrontando i risultati con il workflow ufficiale '
        'di bifacial_radiance (NREL) applicato alla stessa scena e agli stessi parametri. '
        'La validazione, condotta su giornate rappresentative (equinozio e solstizio), '
        'ha prodotto: bias medio (MBE) inferiore all\'1%, RMSE inferiore allo 0.5%, '
        'coefficiente di determinazione R2 di almeno 0.997 (misure v4.3.0). Un riferimento '
        'indipendente col workflow nativo set1axis concorda entro 0.5 punti percentuali '
        'sul rapporto giornaliero suolo/GHI.',
        S['body']))

    story.append(Spacer(1, 3*mm))

    # Glossario variabili
    story.append(Paragraph('Glossario delle variabili principali', S['section']))

    glossary = [
        ['Variabile', 'Unita', 'Descrizione'],
        ['GHI', 'W/m2', 'Irradianza globale orizzontale'],
        ['DNI', 'W/m2', 'Irradianza diretta normale'],
        ['DHI', 'W/m2', 'Irradianza diffusa orizzontale'],
        ['IRR', 'W/m2', 'Irradianza al suolo sotto pannelli (output Radiance)'],
        ['PAR', 'umol/m2/s', 'Radiazione fotosinteticamente attiva (400-700 nm)'],
        ['DLI', 'mol/m2/d', 'Daily Light Integral (integrale giornaliero PAR)'],
        ['GCR', '---', 'Ground Coverage Ratio = W / pitch'],
        ['theta', 'deg', 'Angolo di rotazione del tracker (da pvlib)'],
        ['RSR', '0-1', 'Relative Shade Ratio = 1 - PAR_rel'],
        ['K_agv', '%', 'Coefficiente resa agrivoltaica = Y_rel (espresso in %)'],
        ['PAR_rel', '0-1', 'PAR relativa = DLI_zona / DLI_riferimento'],
        ['SAU', 'm', 'Superficie Agricola Utile = pitch - 2 x SANU'],
        ['SANU', 'm', 'Bordo non coltivato per lato del pitch'],
        ['TMY', '---', 'Typical Meteorological Year (anno tipo composito)'],
    ]
    if p.get('n_file', 0) > 0:
        glossary.extend([
            ['FC_NS', '>=1', 'Fattore correttivo bordo N-S (estremita stringhe)'],
            ['FC', '>=1', 'Fattore correttivo impianto = K_agv_imp / K_agv_inf'],
        ])

    t_gloss = Table(glossary, colWidths=[page_w*0.18, page_w*0.14, page_w*0.68])
    t_gloss.setStyle(_table_style_header())
    t_gloss.setStyle(TableStyle([
        ('ALIGN', (0, 0), (1, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'LEFT'),
    ]))
    story.append(t_gloss)

    # ── Assunzioni, riferimenti, note ──────────────────────────────────────
    story.append(Spacer(1, 3*mm))

    # Assunzioni e limitazioni
    story.append(Paragraph('Assunzioni e limitazioni', S['section']))
    limitations = [
        'PAR_FRAC = 0.45: frazione PAR costante (range reale 0.42-0.48). '
        'Errore medio annuo &lt; 3% (McCree 1972, Papaioannou et al. 1993).',

        'W_TO_UMOL = 4.57 umol/J: fattore di conversione per spettro solare medio '
        '(McCree 1972, Thimijan &amp; Heins 1983). Non considera variazioni spettrali sotto pannelli.',

        'Modulo opaco: la geometria Radiance tratta i pannelli come rettangoli opachi. '
        'La trasmittanza tau, se specificata, viene applicata come correzione post-simulazione '
        'sulla componente diretta intercettata dal modulo.',

        'TMY composito: la simulazione opera su un singolo anno tipo assemblato dai mesi '
        'mediani del dataset PVGIS. La variabilita interannuale non e inclusa nei risultati '
        'ma puo essere stimata dal rapporto GHI annuale dei singoli anni.',

        'Orizzonte locale: PVGIS usa il DEM (terreno nudo), non il DSM (edifici, alberi). '
        'I DLI assoluti possono essere sovrastimati in siti con ostruzioni artificiali. '
        'I valori relativi (K_agv) sono meno sensibili.',

        'Parametri Radiance: i default (ab=2, ad=2048, as=256) corrispondono alla modalita '
        '\'low\' di bifacial_radiance. L\'aumento dei parametri migliora la convergenza '
        'ma allunga il tempo di calcolo. La validazione e stata eseguita con i default.',
    ]
    for lim in limitations:
        story.append(Paragraph(lim, S['small']))
        story.append(Spacer(1, 1*mm))

    story.append(Spacer(1, 4*mm))

    # Software e librerie
    story.append(Paragraph('Software e librerie', S['section']))
    software = [
        '<b>Radiance</b> (Lawrence Berkeley National Laboratory): sistema di riferimento '
        'per la simulazione della luce naturale, validato e utilizzato da oltre 30 anni '
        'in ambito architettonico, energetico e illuminotecnico.',

        '<b>bifacial_radiance v0.5.1</b> (National Renewable Energy Laboratory): framework '
        'Python per la simulazione di impianti fotovoltaici bifacciali mediante Radiance, '
        'sviluppato e mantenuto da NREL.',

        '<b>pvlib</b> (Sandia National Laboratories): libreria per il calcolo della posizione '
        'solare, degli angoli di incidenza e dell\'algoritmo di backtracking.',

        '<b>PVGIS-SARAH3</b> (JRC, Commissione Europea): database satellitare di irradianza '
        'solare con copertura europea e risoluzione oraria.',
    ]
    for sw in software:
        story.append(Paragraph(sw, S['body']))

    story.append(Spacer(1, 4*mm))

    # Riferimenti bibliografici
    story.append(Paragraph('Riferimenti bibliografici', S['section']))
    refs = [
        'Ward G.J. (1994). The RADIANCE lighting simulation and rendering system. '
        'Proc. SIGGRAPH 94, Computer Graphics, 459-472.',
        'Deline C. et al. (2017). A simplified model of uniform bifacial photovoltaics. '
        'Proc. 44th IEEE PVSC, Washington DC.',
        'Reda I., Andreas A. (2004). Solar position algorithm for solar radiation applications. '
        'Solar Energy 76(5), 577-589.',
        'Lorenzo E. (2011). On the calculation of the density of one-axis tracking solar arrays. '
        'Progress in Photovoltaics 19(6), 747-753.',
        'Perez R. et al. (1993). All-weather model for sky luminance distribution. '
        'Solar Energy 50(3), 235-245.',
        'McCree K.J. (1972). Test of current definitions of photosynthetically active radiation '
        'against leaf photosynthesis data. Agricultural Meteorology 10, 443-453.',
        'Thimijan R.W., Heins R.D. (1983). Photometric, radiometric, and quantum light units of '
        'measure. HortScience 18(6), 818-822.',
        'Laub M. et al. (2022). Contrasting yield responses at varying levels of shade suggest '
        'different suitability of crops for dual land-use. Agron. Sustain. Dev. 42:51.',
        'PVGIS-SARAH3. JRC, European Commission. https://re.jrc.ec.europa.eu/pvg_tools/',
    ]
    for ref in refs:
        story.append(Paragraph(ref, S['small']))

    # ── Footer ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph(
        f'SolRatio v{__version__} -- Stefano Pesavento, PhD (ORCID 0009-0008-0720-4539) | '
        'Motore: Radiance + bifacial_radiance (NREL) + Laub et al. 2022 | '
        f'Generato: {datetime.now().strftime("%d/%m/%Y %H:%M")}',
        S['small']))

    # Build (con canvas numerato "pagina X di Y")
    doc.build(story, canvasmaker=NumberedCanvas)
    return True
