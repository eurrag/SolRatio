"""
Smoke regression v4.2: estrae K_agv SAU dai risultati Sample_EW e
confronta con il riferimento v4.1.2.
"""
import sys
from pathlib import Path
from openpyxl import load_workbook

REFERENCE_KAGV_SAU_CEREALI = 84.0  # v4.1.2 atteso (Mar-Set, axis=180, tau=0)
TOLERANCE_PCT = 0.5  # rumore stocastico rtrace ammesso

def extract_kagv_sau(results_xlsx: str) -> dict:
    wb = load_workbook(results_xlsx, data_only=True, read_only=True)
    ws = wb['Resa_Colturale']
    out = {}
    cur_crop = None
    for r in range(1, ws.max_row + 1):
        a = ws.cell(r, 1).value
        if a and isinstance(a, str):
            a = a.strip()
            # Header coltura (es. "  Cereali C3 (cereals_C3)")
            if any(c in a for c in ('Cereali C3', 'Mais', 'Bacche', 'Frutta',
                                     'Ortaggi', 'Foraggere', 'Tuberi',
                                     'Leguminose')):
                cur_crop = a
            elif a == 'SAU' and cur_crop:
                v = ws.cell(r, 15).value  # colonna O = Media Mar-Set
                if v is not None and isinstance(v, (int, float)):
                    out[cur_crop] = float(v)
                cur_crop = None
    wb.close()
    return out


def main():
    project = Path('progetti/Sample_EW')
    results_xlsx = project / f'risultati_{project.name.replace("_EW", "")}.xlsx'
    # Fallback: cerca qualunque risultati_*.xlsx
    if not results_xlsx.exists():
        candidates = list(project.glob('risultati_*.xlsx'))
        if not candidates:
            print(f'ERR: nessun risultati_*.xlsx in {project}')
            sys.exit(2)
        results_xlsx = candidates[0]

    print(f'Leggo: {results_xlsx}')
    kagv = extract_kagv_sau(str(results_xlsx))
    if not kagv:
        print('ERR: nessun K_agv SAU trovato.')
        sys.exit(2)

    print('\n=== K_agv SAU (Mar-Set) per coltura ===')
    for crop, v in kagv.items():
        print(f'  {crop}: {v:.2f}%')

    # Verifica regression sul Cereali C3 (riferimento storico)
    target = None
    for k, v in kagv.items():
        if 'Cereali C3' in k:
            target = v
            break
    if target is None:
        print('\nWARNING: Cereali C3 non trovato, skip regression check.')
        return

    diff = target - REFERENCE_KAGV_SAU_CEREALI
    print(f'\n=== Regression check (Cereali C3) ===')
    print(f'  Atteso v4.1.2: {REFERENCE_KAGV_SAU_CEREALI:.2f}%')
    print(f'  Misurato v4.2: {target:.2f}%')
    print(f'  Differenza:    {diff:+.2f}%  (tolleranza: +/-{TOLERANCE_PCT})')

    if abs(diff) <= TOLERANCE_PCT:
        print(f'\n[OK] REGRESSION ({abs(diff):.2f}% <= {TOLERANCE_PCT}%)')
        sys.exit(0)
    else:
        print(f'\n[FAIL] REGRESSION ({abs(diff):.2f}% > {TOLERANCE_PCT}%)')
        print('  Indagare prima del bump v4.2.0.')
        sys.exit(1)


if __name__ == '__main__':
    main()
