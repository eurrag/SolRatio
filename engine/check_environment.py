"""
check_environment.py  |  SolRatio v4.2.0 (2026-05-01)
=======================================================
Verifica che l'ambiente Python contenga tutte le dipendenze necessarie
per eseguire SolRatio. Stampa a video le versioni di ciascuna libreria
e segnala eventuali pacchetti mancanti.

Uso:
    python check_environment.py

Output:
    Stampa a video l'esito (OK / FAIL) e un riepilogo delle versioni.
    Codice di uscita: 0 = OK, 1 = pacchetti mancanti, 2 = Radiance non trovato.

Dipendenza esterna NON pip (verificata separatamente):
    Radiance >= 5.4 nel PATH di sistema (gendaylit, oconv, rtrace).
"""

from __future__ import annotations

import shutil
import subprocess
import sys

# Pacchetti Python richiesti (chiave = nome modulo, valore = nome pip se diverso)
REQUIRED_PACKAGES = [
    'numpy',
    'pandas',
    'pvlib',
    'bifacial_radiance',
    'openpyxl',
    'lxml',
]

# Pacchetti opzionali (avviso se mancanti, non errore)
OPTIONAL_PACKAGES = [
    'reportlab',
    'matplotlib',
]

# Comandi Radiance da verificare nel PATH
RADIANCE_TOOLS = ['gendaylit', 'oconv', 'rtrace']


def check_python() -> str:
    """Restituisce la versione di Python in formato 'X.Y.Z'."""
    return f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'


def check_package(name: str) -> tuple[bool, str]:
    """Tenta l'import di un pacchetto e ne restituisce la versione."""
    try:
        mod = __import__(name)
        version = getattr(mod, '__version__', None)
        if version is None:
            # reportlab usa l'attributo Version (con maiuscola)
            version = getattr(mod, 'Version', 'n/a')
        return True, version
    except ImportError as e:
        return False, str(e)


def check_radiance() -> tuple[bool, list[str]]:
    """Verifica che i comandi Radiance siano presenti nel PATH."""
    missing: list[str] = []
    for tool in RADIANCE_TOOLS:
        if shutil.which(tool) is None:
            missing.append(tool)
    return len(missing) == 0, missing


def main() -> int:
    print('=' * 60)
    print('  SolRatio v4.2.0 - Verifica ambiente Python')
    print('=' * 60)
    print(f'Python: {check_python()}  ({sys.executable})')
    print()

    n_errori = 0

    # Pacchetti obbligatori
    print('[Pacchetti obbligatori]')
    for pkg in REQUIRED_PACKAGES:
        ok, info = check_package(pkg)
        if ok:
            print(f'  [OK]   {pkg:22s} {info}')
        else:
            print(f'  [FAIL] {pkg:22s} non installato')
            n_errori += 1
    print()

    # Pacchetti opzionali
    print('[Pacchetti opzionali]')
    for pkg in OPTIONAL_PACKAGES:
        ok, info = check_package(pkg)
        if ok:
            print(f'  [OK]   {pkg:22s} {info}')
        else:
            print(f'  [--]   {pkg:22s} non installato (opzionale)')
    print()

    # Radiance esterno
    print('[Radiance esterno]')
    rad_ok, rad_missing = check_radiance()
    if rad_ok:
        for tool in RADIANCE_TOOLS:
            print(f'  [OK]   {tool:22s} {shutil.which(tool)}')
    else:
        for tool in RADIANCE_TOOLS:
            path = shutil.which(tool)
            stato = 'OK   ' if path else 'FAIL '
            print(f'  [{stato}] {tool:22s} {path or "non trovato nel PATH"}')
        print()
        print('  Installa Radiance da https://www.radiance-online.org/')
        print('  e aggiungi la cartella bin al PATH di sistema.')
    print()

    # Esito
    print('=' * 60)
    if n_errori == 0 and rad_ok:
        print('  RISULTATO: OK — ambiente pronto per SolRatio')
        return 0
    elif not rad_ok and n_errori == 0:
        print('  RISULTATO: WARNING — Radiance mancante')
        return 2
    else:
        print(f'  RISULTATO: FAIL — {n_errori} pacchetto/i mancante/i')
        print()
        print('  Esegui:  pip install -r requirements.txt')
        return 1


if __name__ == '__main__':
    sys.exit(main())
