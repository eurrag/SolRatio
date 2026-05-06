"""
Patch del pulsante Excel BtnCalcola in tutti i progetti SolRatio:
"Ricalcola con BR v4.0.0" -> "Ricalcola"

Modifica direttamente xl/drawings/drawing1.xml dentro l'xlsm (zip).
Crea backup .bak prima di modificare.

Uso: python _patch_button_label.py [path_specifico_xlsm]
     (senza argomenti: patcha tutti i SolRatio_progetto.xlsm in progetti/*/)
"""

import os
import shutil
import sys
import zipfile
from pathlib import Path

OLD_VARIANTS = [
    '<a:t>Ricalcola con BR v4.0.0\r\n</a:t>',
    '<a:t>Ricalcola con BR v4.0.0</a:t>',
    '<a:t>Ricalcola con BR v4.1.0\r\n</a:t>',
    '<a:t>Ricalcola con BR v4.1.0</a:t>',
    '<a:t>Ricalcola con BR v4.1.1\r\n</a:t>',
    '<a:t>Ricalcola con BR v4.1.1</a:t>',
    '<a:t>Ricalcola con BR v4.1.2\r\n</a:t>',
    '<a:t>Ricalcola con BR v4.1.2</a:t>',
    '<a:t>Ricalcola con BR v4.2.0\r\n</a:t>',
    '<a:t>Ricalcola con BR v4.2.0</a:t>',
]
NEW_TEXT = '<a:t>Ricalcola</a:t>'
TARGET = 'xl/drawings/drawing1.xml'


def patch_xlsm(xlsm_path: Path) -> bool:
    """Patcha un singolo xlsm. Ritorna True se modificato, False se nulla da fare."""
    if not xlsm_path.exists():
        print(f'  SKIP {xlsm_path} (non esiste)')
        return False

    # Leggi contenuto
    with zipfile.ZipFile(xlsm_path, 'r') as zin:
        if TARGET not in zin.namelist():
            print(f'  SKIP {xlsm_path.name} (no {TARGET})')
            return False
        info_list = zin.infolist()
        items = {info.filename: zin.read(info.filename) for info in info_list}

    drawing = items[TARGET].decode('utf-8')
    if NEW_TEXT in drawing and not any(v in drawing for v in OLD_VARIANTS):
        # Anche se NEW_TEXT presente, verifica che non sia altro shape;
        # qui assumiamo che basta che le vecchie varianti siano assenti.
        # Per sicurezza richiede che ci sia BtnCalcola nel drawing.
        if 'BtnCalcola' in drawing:
            print(f'  GIA OK {xlsm_path.name} (testo gia "Ricalcola")')
            return False

    matched = None
    for old in OLD_VARIANTS:
        if old in drawing:
            matched = old
            break
    if matched is None:
        print(f'  SKIP {xlsm_path.name} (nessuna variante "Ricalcola con BR..." trovata)')
        return False

    new_drawing = drawing.replace(matched, NEW_TEXT, 1)
    items[TARGET] = new_drawing.encode('utf-8')

    # Backup
    backup = xlsm_path.with_suffix(xlsm_path.suffix + '.bak')
    if not backup.exists():
        shutil.copy2(xlsm_path, backup)

    # Scrivi tmp + atomic rename
    tmp = xlsm_path.with_suffix(xlsm_path.suffix + '.tmp')
    if tmp.exists():
        os.remove(tmp)
    with zipfile.ZipFile(tmp, 'w') as zout:
        for info in info_list:
            new_info = zipfile.ZipInfo(filename=info.filename,
                                        date_time=info.date_time)
            new_info.compress_type = info.compress_type
            new_info.external_attr = info.external_attr
            new_info.create_system = info.create_system
            zout.writestr(new_info, items[info.filename])

    # Sostituisci atomicamente
    os.replace(tmp, xlsm_path)
    print(f'  OK   {xlsm_path.name} (matched "{matched}", backup: {backup.name})')
    return True


def main():
    if len(sys.argv) > 1:
        targets = [Path(sys.argv[1])]
    else:
        # Tutti i SolRatio_progetto.xlsm in progetti/*/
        root = Path(__file__).parent / 'progetti'
        targets = sorted(root.glob('*/SolRatio_progetto.xlsm'))

    if not targets:
        print('Nessun xlsm da patchare.')
        sys.exit(1)

    print(f'Trovati {len(targets)} file da analizzare:')
    n_modified = 0
    for x in targets:
        try:
            if patch_xlsm(x):
                n_modified += 1
        except PermissionError:
            print(f'  ERR  {x.name}: PERMISSION DENIED -- chiudi Excel se aperto')
        except Exception as e:
            print(f'  ERR  {x.name}: {type(e).__name__}: {e}')

    print(f'\nFatto: {n_modified}/{len(targets)} file modificati.')
    if n_modified > 0:
        print('Riapri il file in Excel -- il pulsante mostrera "Ricalcola".')


if __name__ == '__main__':
    main()
