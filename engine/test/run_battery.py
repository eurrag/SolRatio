"""
run_battery.py | Orchestratore batteria test SolRatio v4
=========================================================
Lancia in sequenza tutti i test della batteria (cartelle con SolRatio_progetto.xlsm).

Posizione: engine/test/run_battery.py
Cartella dati di default: ../../progetti/test_battery
Engine di calcolo: ../calcola_br.py

Caratteristiche:
- Itera ricorsivamente sulla cartella dati alla ricerca di SolRatio_progetto.xlsm
- Per ogni cartella lancia engine/calcola_br.py
- Resume automatico via sentinella .br_done (skip cartelle gia' completate)
- Logging robusto: timing, exit code, ETA, riassunto finale
- stdout e stderr separati (br_log.txt e br_err.txt) per debug piu' chiaro
- Ctrl+C gestito: chiude pulito senza lasciare sentinelle parziali
- Stima tempo residuo basata sui run completati nella sessione corrente
- Percorsi auto-rilevati relativi alla posizione dello script (portabile)

Uso:
    python run_battery.py [--data DIR] [--no-resume] [--only PATTERN] [--dry-run]

Opzioni:
    --data DIR    cartella radice dei test (default: ../../progetti/test_battery)
    --no-resume   ignora .br_done, rifa' tutto
    --only X      esegui solo i test il cui rel-path contiene X
    --dry-run     non lancia nulla, mostra solo cosa farebbe
"""
import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta


# ---- Percorsi auto-rilevati (portabili) -----------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
PROJECT_ROOT = os.path.normpath(os.path.join(ENGINE_DIR, ".."))

ENGINE = os.path.join(ENGINE_DIR, "calcola_br.py")
DEFAULT_DATA = os.path.join(PROJECT_ROOT, "progetti", "test_battery")
PYEXE = sys.executable  # usa lo stesso Python con cui questo script gira

# Flag globale per gestione SIGINT pulita
_INTERRUPTED = False
_LOG_FILE = None  # impostato in main()


def _on_sigint(signum, frame):
    global _INTERRUPTED
    _INTERRUPTED = True
    log("!! Ctrl+C ricevuto: termino dopo il test corrente.")


signal.signal(signal.SIGINT, _on_sigint)


def find_tests(data_root, only=None):
    tests = []
    for dirpath, _, files in os.walk(data_root):
        if "SolRatio_progetto.xlsm" in files:
            rel = os.path.relpath(dirpath, data_root).replace("\\", "/")
            if only and only not in rel:
                continue
            tests.append((rel, dirpath))
    tests.sort()
    return tests


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    if _LOG_FILE:
        try:
            with open(_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


def fmt_dur(seconds):
    if seconds is None:
        return "?"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h{m:02d}m{s:02d}s"
    return f"{m}m{s:02d}s"


def run_one(rel, full):
    xlsm = os.path.join(full, "SolRatio_progetto.xlsm")
    log_out = os.path.join(full, "br_log.txt")
    log_err = os.path.join(full, "br_err.txt")
    sentinel = os.path.join(full, ".br_done")

    t0 = time.time()
    try:
        with open(log_out, "w", encoding="utf-8") as fout, \
             open(log_err, "w", encoding="utf-8") as ferr:
            rc = subprocess.call(
                [PYEXE, ENGINE, xlsm],
                stdout=fout, stderr=ferr,
                cwd=full,
            )
    except Exception as e:
        log(f"        EXC: {e}")
        return (-1, time.time() - t0)

    dt = time.time() - t0
    if rc == 0:
        try:
            with open(sentinel, "w", encoding="utf-8") as f:
                f.write(
                    f"completed_at={datetime.now().isoformat()}\n"
                    f"duration_sec={dt:.1f}\n"
                    f"exit_code=0\n"
                    f"engine={ENGINE}\n"
                )
        except Exception:
            pass
    return (rc, dt)


def main():
    global _LOG_FILE
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA,
                    help=f"cartella radice dei test (default: {DEFAULT_DATA})")
    ap.add_argument("--no-resume", action="store_true",
                    help="ignora .br_done, rifa' tutto")
    ap.add_argument("--only", default=None,
                    help="esegui solo test il cui rel-path contiene questa stringa")
    ap.add_argument("--dry-run", action="store_true",
                    help="non lancia nulla, mostra solo elenco")
    args = ap.parse_args()

    data_root = os.path.abspath(args.data)
    _LOG_FILE = os.path.join(data_root, "batteria_log.txt")

    if not os.path.exists(ENGINE):
        log(f"ERRORE: engine non trovato: {ENGINE}")
        sys.exit(2)
    if not os.path.isdir(data_root):
        log(f"ERRORE: cartella dati non trovata: {data_root}")
        sys.exit(2)

    tests = find_tests(data_root, only=args.only)
    n_total = len(tests)
    log("=" * 70)
    log("Avvio batteria SolRatio v4")
    log(f"  DATA   : {data_root}")
    log(f"  ENGINE : {ENGINE}")
    log(f"  PYEXE  : {PYEXE}")
    log(f"  Test   : {n_total}  Resume={'no' if args.no_resume else 'si'}"
        + (f"  Filter='{args.only}'" if args.only else ""))

    if args.dry_run:
        for i, (rel, full) in enumerate(tests, 1):
            sentinel = os.path.join(full, ".br_done")
            status = "DONE" if (not args.no_resume and os.path.exists(sentinel)) else "TODO"
            log(f"  [{i:2d}/{n_total}] {status}  {rel}")
        return

    n_skipped = n_done = n_failed = 0
    durations = []
    t_start = time.time()

    for i, (rel, full) in enumerate(tests, 1):
        if _INTERRUPTED:
            log("!! Interrotto dall'utente, esco.")
            break

        sentinel = os.path.join(full, ".br_done")
        if not args.no_resume and os.path.exists(sentinel):
            log(f"[{i:2d}/{n_total}] SKIP {rel}")
            n_skipped += 1
            continue

        eta = ""
        if durations:
            avg = sum(durations) / len(durations)
            remaining = n_total - i + 1 - n_skipped
            eta_s = avg * remaining
            eta_t = datetime.now() + timedelta(seconds=eta_s)
            eta = f"  ETA fine ~{eta_t.strftime('%H:%M')}"

        log(f"[{i:2d}/{n_total}] RUN  {rel}{eta}")
        rc, dt = run_one(rel, full)

        if rc == 0:
            log(f"        OK  in {fmt_dur(dt)}")
            n_done += 1
            durations.append(dt)
        else:
            log(f"        ERR exit={rc} in {fmt_dur(dt)} - vedi br_err.txt")
            n_failed += 1
            durations.append(dt)

    t_total = time.time() - t_start
    log("=" * 70)
    log(f"Batteria conclusa: {n_done} OK | {n_failed} FAIL | {n_skipped} SKIP "
        f"(su {n_total})  Tempo: {fmt_dur(t_total)}")
    if n_failed > 0:
        log("ATTENZIONE: alcuni test hanno fallito. Controlla br_err.txt nelle cartelle.")


if __name__ == "__main__":
    main()
