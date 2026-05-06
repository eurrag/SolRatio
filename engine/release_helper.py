"""
release_helper.py  |  SolRatio v4.2.0
========================================================================
Strumento di rilascio automatizzato per SolRatio.

Sostituisce la pipeline manuale di bump versione + aggiornamento metadati
DOI Zenodo che in v4.1.x richiedeva ~30 min di edit manuali su molti file.

Subcommand
----------

  bump --new-version X.Y.Z [--date YYYY-MM-DD] [--dry-run]
      Bump della versione corrente alla nuova specificata. Aggiorna:
        - engine/VERSION
        - CITATION.cff (version, date-released)
        - README.md (titolo "# SolRatio vX.Y.Z")
        - engine/*.py:
            * header docstring "<file>.py  |  SolRatio vX.Y.Z[ (YYYY-MM-DD)]"
            * dichiarazione __version__ = '...'
            * stringhe runtime (`f' SolRatio vX.Y.Z'`, ecc.)
            * argparse description con suffisso "— SolRatio vX.Y.Z"

      Pre-check: git working tree pulito, X.Y.Z semver valido e > corrente.
      Le occorrenze "storiche" del numero di versione nei commenti (es. "v4.1.0
      ha introdotto X") restano invariate: il pattern di replace è ancorato
      a prefissi specifici per evitare falsi positivi.

  bump-from-changelog [--dry-run]
      Come `bump` ma legge la nuova versione e la data dalla prima sezione
      `## vX.Y.Z (YYYY-MM-DD)` di documentazione/CHANGELOG.md. Utile come
      single-source-of-truth: se il CHANGELOG documenta vX.Y.Z, allora si
      rilascia X.Y.Z.

  update-doi --doi 10.5281/zenodo.NNNNNNN [--dry-run]
      Aggiorna il DOI Zenodo nei metadati post-rilascio:
        - CITATION.cff (campo doi)
        - README.md (badge DOI + sezione "Come citare" se presente)

  status
      Stampa lo stato corrente: versione corrente, data ultimo rilascio,
      DOI corrente, ramo git, working tree status.

Note di design
--------------
1. Tutti i comandi supportano --dry-run: stampano le sostituzioni che
   farebbero, senza scrivere su disco. Usalo come prima azione.
2. Le operazioni git (commit, tag, push, gh release create) NON sono
   gestite da release_helper.py per scelta: vanno orchestrate da
   _NUOVA_VERSIONE.bat (o equivalente shell). Mantenere release_helper
   focalizzato su edit testuali rende lo strumento facilmente testabile.
3. Lo script accetta come root (CWD) qualsiasi cartella che contenga
   `engine/VERSION`. Risale fino a 3 livelli per trovarlo.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

# ──────────────────────────────────────────────────────────────────────
# Localizzazione root del progetto
# ──────────────────────────────────────────────────────────────────────

def find_project_root(start: Path | None = None) -> Path:
    """Risale dalle CWD finché non trova `engine/VERSION`. Max 4 livelli."""
    p = (start or Path.cwd()).resolve()
    for _ in range(5):
        if (p / "engine" / "VERSION").is_file():
            return p
        if p.parent == p:
            break
        p = p.parent
    raise RuntimeError(
        "Impossibile trovare engine/VERSION risalendo da CWD "
        f"({Path.cwd()}). Eseguire dal root del progetto SolRatio."
    )

# ──────────────────────────────────────────────────────────────────────
# Validazione semver
# ──────────────────────────────────────────────────────────────────────

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([\w\.\-]+))?$")

def parse_semver(version: str) -> Tuple[int, int, int, str | None]:
    m = _SEMVER_RE.match(version.strip())
    if not m:
        raise ValueError(
            f"Versione '{version}' non semver (atteso X.Y.Z[-suffix])."
        )
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4))


def semver_gt(a: str, b: str) -> bool:
    """True se a > b in ordinamento semver (suffix pre-release ignorato)."""
    pa = parse_semver(a)[:3]
    pb = parse_semver(b)[:3]
    return pa > pb

# ──────────────────────────────────────────────────────────────────────
# Patterns di sostituzione versione
# ──────────────────────────────────────────────────────────────────────
# Ogni patch e' una tupla (descrizione, regex_pattern, replacement).
# I pattern sono volutamente ANCORATI a contesti specifici per evitare
# di toccare le occorrenze "storiche" come "(v4.1.0)" nei commenti.

def _build_py_patterns(old: str, new: str) -> List[Tuple[str, re.Pattern, str]]:
    """Pattern applicati a tutti gli engine/*.py."""
    old_re = re.escape(old)
    return [
        (
            "header docstring '<file>.py  |  SolRatio vX.Y.Z'",
            re.compile(rf"(\.py\s+\|\s+SolRatio v){old_re}\b"),
            rf"\g<1>{new}",
        ),
        (
            "__version__ = '...'",
            re.compile(rf"(__version__\s*=\s*['\"]){old_re}(['\"])"),
            rf"\g<1>{new}\g<2>",
        ),
        (
            "stringa runtime ' SolRatio vX.Y.Z' (con leading whitespace)",
            re.compile(rf"((?:^|[^a-zA-Z0-9_]) SolRatio v){old_re}\b"),
            rf"\g<1>{new}",
        ),
        (
            "stringa runtime '# SolRatio vX.Y.Z'",
            re.compile(rf"(# SolRatio v){old_re}\b"),
            rf"\g<1>{new}",
        ),
        (
            "argparse description '— SolRatio vX.Y.Z'",
            re.compile(rf"(— SolRatio v){old_re}\b"),
            rf"\g<1>{new}",
        ),
        (
            "stringa output 'SolRatio vX.Y.Z -- ERRORE'",
            re.compile(rf"(SolRatio v){old_re}( -- ERRORE)"),
            rf"\g<1>{new}\g<2>",
        ),
    ]


def _build_citation_patterns(new: str, date: str) -> List[Tuple[str, re.Pattern, str]]:
    return [
        (
            "CITATION.cff version",
            re.compile(r'^(version:\s*")[^"]+(")', re.MULTILINE),
            rf'\g<1>{new}\g<2>',
        ),
        (
            "CITATION.cff date-released",
            re.compile(r'^(date-released:\s*")[^"]+(")', re.MULTILINE),
            rf'\g<1>{date}\g<2>',
        ),
    ]


def _build_readme_patterns(new: str) -> List[Tuple[str, re.Pattern, str]]:
    return [
        (
            "README.md titolo '# SolRatio vX.Y.Z'",
            re.compile(r"^(# SolRatio v)[\d\.]+", re.MULTILINE),
            rf"\g<1>{new}",
        ),
    ]


def _build_doi_patterns(doi: str) -> List[Tuple[str, re.Pattern, str]]:
    """Pattern per il subcommand update-doi."""
    return [
        (
            "CITATION.cff campo doi",
            re.compile(r'^(doi:\s*")[^"]+(")', re.MULTILINE),
            rf'\g<1>{doi}\g<2>',
        ),
        (
            "README.md badge DOI Zenodo",
            re.compile(r'(zenodo\.\d+\.svg\)\]\(https://doi\.org/)([\d\./a-z]+)'),
            rf'\g<1>{doi}',
        ),
    ]

# ──────────────────────────────────────────────────────────────────────
# Applicazione patterns
# ──────────────────────────────────────────────────────────────────────

def apply_patterns(
    content: str,
    patterns: Iterable[Tuple[str, re.Pattern, str]],
) -> Tuple[str, List[Tuple[str, int]]]:
    """Applica patterns. Ritorna (nuovo_contenuto, [(desc, n_match), ...])."""
    new_content = content
    summary: List[Tuple[str, int]] = []
    for desc, pat, repl in patterns:
        new_content, n = pat.subn(repl, new_content)
        summary.append((desc, n))
    return new_content, summary


def patch_file(
    path: Path,
    patterns: Iterable[Tuple[str, re.Pattern, str]],
    dry_run: bool = False,
) -> Tuple[bool, List[Tuple[str, int]]]:
    """Patcha un file. Ritorna (modified, summary)."""
    if not path.is_file():
        return False, []
    original = path.read_text(encoding="utf-8")
    new_content, summary = apply_patterns(original, patterns)
    n_total = sum(n for _, n in summary)
    if n_total == 0:
        return False, summary
    if not dry_run:
        path.write_text(new_content, encoding="utf-8")
    return True, summary

# ──────────────────────────────────────────────────────────────────────
# Pre-check git
# ──────────────────────────────────────────────────────────────────────

def git_working_tree_clean(root: Path) -> Tuple[bool, str]:
    """True se non ci sono modifiche tracked. Untracked sono OK."""
    import subprocess
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return False, f"git status fallito: {exc}"
    return out.strip() == "", out

# ──────────────────────────────────────────────────────────────────────
# Subcommand: bump
# ──────────────────────────────────────────────────────────────────────

def cmd_bump(args: argparse.Namespace) -> int:
    root = find_project_root()
    version_file = root / "engine" / "VERSION"
    current = version_file.read_text(encoding="utf-8").strip().splitlines()[0]

    new = args.new_version.strip()
    if not _SEMVER_RE.match(new):
        print(f"[ERR] Nuova versione '{new}' non semver.", file=sys.stderr)
        return 2
    if new == current:
        print(f"[ERR] Nuova versione '{new}' uguale alla corrente.", file=sys.stderr)
        return 2
    if not args.allow_downgrade and not semver_gt(new, current):
        print(
            f"[ERR] Nuova versione '{new}' non > corrente '{current}'. "
            "Usa --allow-downgrade se intenzionale.",
            file=sys.stderr,
        )
        return 2

    date = args.date or _dt.date.today().isoformat()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        print(f"[ERR] Data '{date}' non in formato YYYY-MM-DD.", file=sys.stderr)
        return 2

    print(f"=== release_helper bump ===")
    print(f"  root           : {root}")
    print(f"  versione corr. : {current}")
    print(f"  versione nuova : {new}")
    print(f"  data rilascio  : {date}")
    print(f"  dry-run        : {args.dry_run}")
    print()

    if not args.skip_git_check:
        clean, status = git_working_tree_clean(root)
        if not clean:
            print(
                f"[ERR] Working tree non pulito (modifiche tracked):\n{status}",
                file=sys.stderr,
            )
            print("Usa --skip-git-check per forzare.", file=sys.stderr)
            return 3

    # 1) engine/VERSION
    if not args.dry_run:
        version_file.write_text(new + "\n", encoding="utf-8")
    print(f"[ {'DRY' if args.dry_run else 'WRITE'} ] engine/VERSION : {current} -> {new}")

    # 2) CITATION.cff
    cit = root / "CITATION.cff"
    modified, summary = patch_file(
        cit, _build_citation_patterns(new, date), dry_run=args.dry_run,
    )
    if modified:
        for desc, n in summary:
            if n:
                print(f"[ {'DRY' if args.dry_run else 'WRITE'} ] CITATION.cff   : {desc} ({n} match)")

    # 3) README.md
    readme = root / "README.md"
    modified, summary = patch_file(
        readme, _build_readme_patterns(new), dry_run=args.dry_run,
    )
    if modified:
        for desc, n in summary:
            if n:
                print(f"[ {'DRY' if args.dry_run else 'WRITE'} ] README.md      : {desc} ({n} match)")

    # 4) engine/*.py
    py_patterns = _build_py_patterns(current, new)
    py_files = sorted((root / "engine").glob("*.py"))
    py_files += sorted((root / "engine" / "test").glob("*.py"))
    n_files_modified = 0
    n_total_subs = 0
    for py in py_files:
        modified, summary = patch_file(py, py_patterns, dry_run=args.dry_run)
        if modified:
            n_files_modified += 1
            file_subs = sum(n for _, n in summary)
            n_total_subs += file_subs
            print(
                f"[ {'DRY' if args.dry_run else 'WRITE'} ] {py.relative_to(root)} ({file_subs} sub)"
            )

    print()
    print(f"=== Riepilogo ===")
    print(f"  Python files modificati  : {n_files_modified} / {len(py_files)}")
    print(f"  Sostituzioni totali .py  : {n_total_subs}")
    if args.dry_run:
        print()
        print("DRY RUN: nessun file scritto. Rilancia senza --dry-run per applicare.")
    else:
        print()
        print("Prossimi passi (non automatici):")
        print(f"  1. Verifica diff: git -C {root} diff")
        print(f"  2. Aggiorna documentazione/CHANGELOG.md con la sezione v{new}")
        print(f"  3. git -C {root} add -A && git commit -m 'release v{new}: ...'")
        print(f"  4. git -C {root} tag -a v{new} -m '...' && git push origin main v{new}")
        print(f"  5. gh release create v{new} --title 'SolRatio v{new}' --notes '...'")
        print(f"  6. Attendi DOI Zenodo, poi: release_helper update-doi --doi 10.5281/zenodo.NNNNNNN")
    return 0

# ──────────────────────────────────────────────────────────────────────
# Subcommand: bump-from-changelog
# ──────────────────────────────────────────────────────────────────────

_CHANGELOG_HEADER = re.compile(r"^##\s+v(\d+\.\d+\.\d+(?:-[\w\.\-]+)?)\s*\((\d{4}-\d{2}-\d{2})\)")

def cmd_bump_from_changelog(args: argparse.Namespace) -> int:
    root = find_project_root()
    cl = root / "documentazione" / "CHANGELOG.md"
    if not cl.is_file():
        print(f"[ERR] CHANGELOG.md non trovato: {cl}", file=sys.stderr)
        return 2
    new = None
    date = None
    for line in cl.read_text(encoding="utf-8").splitlines():
        m = _CHANGELOG_HEADER.match(line)
        if m:
            new, date = m.group(1), m.group(2)
            break
    if new is None:
        print(
            "[ERR] CHANGELOG.md non contiene una sezione '## vX.Y.Z (YYYY-MM-DD)' "
            "leggibile come prima entry.",
            file=sys.stderr,
        )
        return 2
    print(f"[ChangelogParse] Trovato: v{new} (data {date})")
    args.new_version = new
    args.date = date
    return cmd_bump(args)

# ──────────────────────────────────────────────────────────────────────
# Subcommand: update-doi
# ──────────────────────────────────────────────────────────────────────

_DOI_RE = re.compile(r"^10\.\d{4,9}/[\w\.\-]+$")

def cmd_update_doi(args: argparse.Namespace) -> int:
    root = find_project_root()
    doi = args.doi.strip()
    if not _DOI_RE.match(doi):
        print(
            f"[ERR] DOI '{doi}' non valido. Atteso formato 10.NNNN/zenodo.NNNNNNN",
            file=sys.stderr,
        )
        return 2

    print(f"=== release_helper update-doi ===")
    print(f"  root  : {root}")
    print(f"  DOI   : {doi}")
    print(f"  dry   : {args.dry_run}")
    print()

    cit = root / "CITATION.cff"
    readme = root / "README.md"
    patterns = _build_doi_patterns(doi)

    for path in (cit, readme):
        modified, summary = patch_file(path, patterns, dry_run=args.dry_run)
        if modified:
            for desc, n in summary:
                if n:
                    print(f"[ {'DRY' if args.dry_run else 'WRITE'} ] {path.name}: {desc} ({n})")
        else:
            print(f"[ -- ] {path.name}: nessuna sostituzione")
    return 0

# ──────────────────────────────────────────────────────────────────────
# Subcommand: status
# ──────────────────────────────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> int:
    root = find_project_root()
    version = (root / "engine" / "VERSION").read_text(encoding="utf-8").strip()

    cit_text = (root / "CITATION.cff").read_text(encoding="utf-8")
    cit_version_m = re.search(r'^version:\s*"([^"]+)"', cit_text, re.MULTILINE)
    cit_date_m = re.search(r'^date-released:\s*"([^"]+)"', cit_text, re.MULTILINE)
    cit_doi_m = re.search(r'^doi:\s*"([^"]+)"', cit_text, re.MULTILINE)

    print("=== SolRatio release status ===")
    print(f"  root             : {root}")
    print(f"  engine/VERSION   : {version}")
    print(f"  CITATION version : {cit_version_m.group(1) if cit_version_m else '?'}")
    print(f"  CITATION date    : {cit_date_m.group(1) if cit_date_m else '?'}")
    print(f"  CITATION doi     : {cit_doi_m.group(1) if cit_doi_m else '?'}")
    clean, status = git_working_tree_clean(root)
    print(f"  git working tree : {'clean' if clean else 'DIRTY'}")
    if not clean:
        print(f"    {status.strip()}")
    return 0

# ──────────────────────────────────────────────────────────────────────
# CLI entrypoint
# ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="release_helper.py — bump versione + DOI per SolRatio v4.2.0",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_bump = sub.add_parser("bump", help="Bump versione esplicita")
    p_bump.add_argument("--new-version", required=True, help="X.Y.Z")
    p_bump.add_argument("--date", default=None, help="YYYY-MM-DD (default: oggi)")
    p_bump.add_argument("--dry-run", action="store_true")
    p_bump.add_argument("--skip-git-check", action="store_true",
                        help="Salta controllo working tree pulito")
    p_bump.add_argument("--allow-downgrade", action="store_true",
                        help="Permette nuova versione < corrente (sconsigliato)")
    p_bump.set_defaults(func=cmd_bump)

    p_cl = sub.add_parser("bump-from-changelog",
                          help="Bump leggendo nuova versione da CHANGELOG.md")
    p_cl.add_argument("--dry-run", action="store_true")
    p_cl.add_argument("--skip-git-check", action="store_true")
    p_cl.add_argument("--allow-downgrade", action="store_true")
    p_cl.set_defaults(func=cmd_bump_from_changelog)

    p_doi = sub.add_parser("update-doi", help="Aggiorna DOI Zenodo nei metadati")
    p_doi.add_argument("--doi", required=True, help="10.5281/zenodo.NNNNNNN")
    p_doi.add_argument("--dry-run", action="store_true")
    p_doi.set_defaults(func=cmd_update_doi)

    p_st = sub.add_parser("status", help="Stato corrente versione+DOI+git")
    p_st.set_defaults(func=cmd_status)

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
