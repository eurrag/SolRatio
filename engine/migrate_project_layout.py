"""
migrate_project_layout.py  |  SolRatio v4.2.0
========================================================================
Migra un progetto SolRatio dal layout v4.1.x ("piatto") al layout
standardizzato v4.2 con sottocartelle `input/` e `test/`.

Layout v4.1.x (sorgente):

    <progetto>/
    ├── SolRatio_progetto.xlsm
    ├── PVGIS_<lat>_<lon>_*.csv
    ├── PVGIS_<lat>_<lon>_TMY.epw
    ├── README.md
    ├── optimization_*.xlsx
    ├── optimization_*.png
    ├── validazione_*.csv
    └── risultati_*.xlsx

Layout v4.2 (destinazione):

    <progetto>/
    ├── SolRatio_progetto.xlsm        (root: punto di ingresso)
    ├── README.md                      (root)
    ├── input/
    │   ├── PVGIS_<lat>_<lon>_*.csv   (meteo grezzo)
    │   └── PVGIS_<lat>_<lon>_*.epw   (TMY EPW generato)
    └── test/
        ├── optimization_*.xlsx       (curva K_agv vs H_min)
        ├── optimization_*.png        (grafico)
        ├── validazione_*.csv         (confronto SR vs BR ufficiale)
        └── risultati_*.xlsx          (output principale BR)

Compatibilità retroattiva
-------------------------
- `engine/br_engine.find_pvgis_csv()` cerca prima in `<progetto>/`
  poi in `<progetto>/input/`. Quindi i progetti v4.2 funzionano
  senza modifiche al motore di SolRatio.
- I path di output v4.2 (test/) sono opzionali in v4.2.0 stessa:
  se la cartella `test/` esiste, i nuovi output vi vengono scritti;
  se non esiste, restano in root come v4.1.x. Il bump completo
  dei path output è previsto in v4.2.x successivo (non implementato qui).

Uso
---

    python engine/migrate_project_layout.py <path_progetto> [--dry-run]

Opzioni:
  --dry-run     Mostra i movimenti che farebbe, senza eseguirli.
  --rollback    Sposta i file da input/ e test/ tornando in root
                (per tornare al layout v4.1.x).

Sicurezza
---------
- Non elimina mai file: solo `shutil.move`.
- Non sovrascrive: se il file di destinazione esiste già, salta con warning.
- Idempotente: rilanciare la migrazione su un progetto già migrato
  non altera nulla (i file sono già in posizione).
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# File pattern → cartella destinazione v4.2
_LAYOUT_V42 = {
    "input": [
        "PVGIS_*.csv",
        "PVGIS_*.epw",
    ],
    "test": [
        "optimization_*.xlsx",
        "optimization_*.png",
        "validazione_*.csv",
        "risultati_*.xlsx",
        "report_SolRatio_*.pdf",
        "optimize_hmin_fail_*.log",
    ],
}

# File da NON spostare (devono restare in root)
_KEEP_IN_ROOT = {
    "SolRatio_progetto.xlsm",
    "SolRatio_progetto.xlsb",
    "README.md",
    ".gitignore",
}


def _move(src: Path, dst: Path, dry_run: bool) -> str:
    if dst.exists():
        return f"SKIP (esiste già)   {src.name}"
    if dry_run:
        return f"DRY  {src.name} -> {dst.relative_to(dst.parent.parent)}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return f"MOVE {src.name} -> {dst.relative_to(dst.parent.parent)}"


def migrate_to_v42(project_dir: Path, dry_run: bool = False) -> dict:
    """Migra un progetto da layout v4.1.x a v4.2."""
    project_dir = Path(project_dir).resolve()
    if not project_dir.is_dir():
        raise SystemExit(f"Cartella progetto non trovata: {project_dir}")

    print(f"Migrazione {project_dir} → layout v4.2 "
          f"(dry-run={dry_run})")

    moved = 0
    skipped = 0

    for subdir, patterns in _LAYOUT_V42.items():
        target = project_dir / subdir
        for pat in patterns:
            for src in sorted(project_dir.glob(pat)):
                if not src.is_file():
                    continue
                if src.name in _KEEP_IN_ROOT:
                    continue
                dst = target / src.name
                msg = _move(src, dst, dry_run)
                print(f"  {msg}")
                if msg.startswith("MOVE") or msg.startswith("DRY"):
                    moved += 1
                elif msg.startswith("SKIP"):
                    skipped += 1

    return {"moved": moved, "skipped": skipped}


def rollback_to_v41(project_dir: Path, dry_run: bool = False) -> dict:
    """Riporta un progetto dal layout v4.2 a v4.1.x (file in root)."""
    project_dir = Path(project_dir).resolve()
    if not project_dir.is_dir():
        raise SystemExit(f"Cartella progetto non trovata: {project_dir}")

    print(f"Rollback {project_dir} → layout v4.1.x "
          f"(dry-run={dry_run})")

    moved = 0
    skipped = 0

    for subdir in _LAYOUT_V42:
        sub_path = project_dir / subdir
        if not sub_path.is_dir():
            continue
        for src in sorted(sub_path.iterdir()):
            if not src.is_file():
                continue
            dst = project_dir / src.name
            msg = _move(src, dst, dry_run)
            print(f"  {msg}")
            if msg.startswith("MOVE") or msg.startswith("DRY"):
                moved += 1
            elif msg.startswith("SKIP"):
                skipped += 1
        # Rimuovi cartella se vuota
        if not dry_run:
            try:
                sub_path.rmdir()
            except OSError:
                pass

    return {"moved": moved, "skipped": skipped}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrazione layout cartella progetto SolRatio v4.1→v4.2",
    )
    parser.add_argument("project_dir", help="Path della cartella progetto")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra spostamenti senza eseguirli")
    parser.add_argument("--rollback", action="store_true",
                        help="Riporta a layout v4.1.x (file in root)")
    args = parser.parse_args(argv)

    if args.rollback:
        result = rollback_to_v41(Path(args.project_dir), args.dry_run)
    else:
        result = migrate_to_v42(Path(args.project_dir), args.dry_run)

    print(f"\nRiepilogo: {result['moved']} spostati, {result['skipped']} saltati")
    return 0


if __name__ == "__main__":
    sys.exit(main())
