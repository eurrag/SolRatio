"""
_scene_cache.py  |  SolRatio v4.3.0
========================================================================
Cache persistente per scene Radiance pre-compilate.

Motivazione
-----------
La pipeline `br_engine.run_annual()` esegue per ogni ora diurna (8760
ore tipiche, ~5000 effettive) un `oconv` completo che linka:

    matfiles + sky_<h>.rad + radfiles_scena → composite_<h>.oct

Tra run consecutive sullo stesso progetto i `radfiles_scena` e
`matfiles` sono identici (dipendono da geometria + albedo + tau,
parametri "lenti"); cambia solo il `sky_<h>.rad` (sole + GHI/DHI/DNI
ora-per-ora).

Strategia di cache
------------------
1. **Pre-compilare**, una sola volta per progetto, il `.oct` "scenico"
   per ogni angolo theta unico:

       scene_<key>.oct = oconv(matfiles + radfiles_scena)

   Questo file rimane invariato tra run e viene salvato in
   `<progetto>/.cache/scenes/<key>.oct`.

2. **Per-ora** la composizione diventa incrementale via `oconv -i`:

       composite_<h>.oct = oconv(-i scene_<key>.oct, sky_<h>.rad)

   `oconv -i` linka un .oct esistente con nuovi input senza ricompilare
   la geometria → speedup atteso 30-60% sul tempo per ora (la frazione
   esatta dipende dalla complessità della scena vs. complessità del cielo).

Invalidazione cache
-------------------
La chiave di cache è un hash SHA-256 dei parametri di scena rilevanti
(geometria + ottica + albedo + versione cache + versione SolRatio
maggiore). Cambiare uno qualsiasi di questi parametri produce un nuovo
file .oct senza intaccare i precedenti — più cache coexistono.

Per evitare crescita illimitata della cache, una funzione di housekeeping
mantiene gli N file più recenti (default 20) e cancella i più vecchi.

API
---
- `make_cache_key(scene_params: dict) -> str`
- `get_cache_dir(project_dir: Path) -> Path` (crea se non esiste)
- `lookup(cache_dir: Path, key: str) -> Path | None`
- `store(cache_dir: Path, key: str, oct_path: Path) -> Path`
- `housekeeping(cache_dir: Path, keep_n: int = 20) -> int`

Tutte le operazioni sono fail-safe: in caso di errore la cache viene
ignorata e il chiamante riusa il path tradizionale (full oconv).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Mapping

# Versione formato cache. Bump se il formato cambia (es. nuovi parametri
# da includere nella chiave). I file .oct con versione vecchia non
# matcheranno più e verranno ignorati (cache miss → ricompilazione).
# "2": scene compilate con oconv -f (frozen, self-contained): le cache
#      formato "1" referenziavano radfile di temp dir cancellate.
CACHE_FORMAT_VERSION = "2"

# Versione "compatibilità" cache lato SolRatio. Cambiare quando si
# modifica il modo in cui le scene vengono generate (anche se i
# parametri di input sono gli stessi). v4.2.0 = primo formato.
SOLRATIO_CACHE_COMPAT = "4.2"


def _canonicalize(value: Any) -> Any:
    """Rendi il valore JSON-serializzabile e deterministico."""
    if isinstance(value, dict):
        return {k: _canonicalize(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(v) for v in value]
    if isinstance(value, float):
        # Arrotonda i float a 6 decimali per evitare cache miss da
        # rumore numerico (es. 0.1 + 0.2 = 0.30000000000000004).
        return round(value, 6)
    if isinstance(value, (int, str, bool)) or value is None:
        return value
    # Fallback: stringa
    return str(value)


def make_cache_key(scene_params: Mapping[str, Any]) -> str:
    """
    Calcola la chiave di cache deterministica per una scena.

    Parameters
    ----------
    scene_params : dict
        Parametri della scena. Tutti i parametri che influenzano i
        radfiles di output devono essere inclusi. Esempi:
            - tilt (deg)
            - azimuth (deg)
            - clearance_height (m)
            - pitch (m)
            - nMods, nRows
            - module_x, module_y, module_glass
            - tau (trasmittanza pannello)
            - albedo
            - axis_azimuth (per item 7 v4.2)
            - slope_cross_deg, slope_along_deg (per slope L2)
            - axis_tilt (slope L1)

    Returns
    -------
    str
        Hash SHA-256 esadecimale, troncato a 16 caratteri (ampia
        collisione-resistance per cache locale, nome file leggibile).
    """
    canonical = _canonicalize(dict(scene_params))
    blob = json.dumps(
        {
            "fmt": CACHE_FORMAT_VERSION,
            "compat": SOLRATIO_CACHE_COMPAT,
            "params": canonical,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return digest[:16]


def get_cache_dir(project_dir: Path) -> Path:
    """
    Restituisce la cartella di cache per il progetto, creandola se assente.

    Layout creato:

        <project_dir>/.cache/scenes/

    `.cache` è un nome convenzionale ignorato di default da git/zip,
    contiene solo dati derivati e può essere cancellata in sicurezza.
    """
    project_dir = Path(project_dir)
    cache_dir = project_dir / ".cache" / "scenes"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def lookup(cache_dir: Path, key: str) -> Path | None:
    """Ritorna il path al .oct cached se esiste e valido, altrimenti None."""
    cache_dir = Path(cache_dir)
    oct_path = cache_dir / f"scene_{key}.oct"
    meta_path = cache_dir / f"scene_{key}.json"
    try:
        if not (oct_path.is_file() and meta_path.is_file()):
            return None
        # Validazione sanity: file non zero, json parsabile
        if oct_path.stat().st_size < 1:
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("compat") != SOLRATIO_CACHE_COMPAT:
            return None
        # Aggiorna mtime per LRU housekeeping
        oct_path.touch()
        meta_path.touch()
        return oct_path
    except Exception:
        return None


def store(
    cache_dir: Path,
    key: str,
    src_oct: Path,
    scene_params: Mapping[str, Any] | None = None,
) -> Path:
    """
    Copia `src_oct` in cache con la chiave `key`. Ritorna il path cached.

    Salva anche un meta JSON con i parametri scene (per debug/ispezione).
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    src_oct = Path(src_oct)
    dst_oct = cache_dir / f"scene_{key}.oct"
    dst_meta = cache_dir / f"scene_{key}.json"

    # Copia atomica: prima a tmp, poi rename (rename è atomico su stesso fs)
    tmp_oct = cache_dir / f".scene_{key}.oct.tmp"
    shutil.copy2(src_oct, tmp_oct)
    tmp_oct.replace(dst_oct)

    meta = {
        "fmt": CACHE_FORMAT_VERSION,
        "compat": SOLRATIO_CACHE_COMPAT,
        "key": key,
        "stored_at": time.time(),
        "stored_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "src_size_bytes": src_oct.stat().st_size,
        "scene_params": _canonicalize(dict(scene_params)) if scene_params else None,
    }
    dst_meta.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return dst_oct


def housekeeping(cache_dir: Path, keep_n: int = 20) -> int:
    """
    Mantiene gli `keep_n` file più recenti (per mtime), cancella gli altri.
    Ritorna il numero di file cancellati. Fail-safe: errori vengono ignorati.
    """
    cache_dir = Path(cache_dir)
    if not cache_dir.is_dir():
        return 0
    octs = sorted(
        cache_dir.glob("scene_*.oct"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,  # newest first
    )
    if len(octs) <= keep_n:
        return 0
    removed = 0
    for old in octs[keep_n:]:
        try:
            old.unlink(missing_ok=True)
            meta = old.with_suffix(".json")
            meta.unlink(missing_ok=True)
            removed += 1
        except Exception:
            continue
    return removed


def stats(cache_dir: Path) -> dict:
    """Statistiche utili per debug / log."""
    cache_dir = Path(cache_dir)
    if not cache_dir.is_dir():
        return {"exists": False}
    octs = list(cache_dir.glob("scene_*.oct"))
    total_size = sum(p.stat().st_size for p in octs)
    return {
        "exists": True,
        "path": str(cache_dir),
        "n_scenes": len(octs),
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "oldest_age_h": (
            round((time.time() - min(p.stat().st_mtime for p in octs)) / 3600, 1)
            if octs else None
        ),
        "newest_age_h": (
            round((time.time() - max(p.stat().st_mtime for p in octs)) / 3600, 1)
            if octs else None
        ),
    }
