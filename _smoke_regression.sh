#!/usr/bin/env bash
# Smoke regression SolRatio (Linux/macOS): run completi su Sample (N-S) e
# Sample_EW (E-W) + verifica K_agv SAU Cereali C3 contro i riferimenti
# (vedi _smoke_check_kagv.py: tolleranza +/- 0.2 punti percentuali).
# Richiede: dipendenze di requirements.txt + binari Radiance nel PATH.
set -u
cd "$(dirname "$0")"

echo "=== Smoke regression SolRatio ==="
for P in Sample Sample_EW; do
  echo "=== RUN $P (~3-5 min) ==="
  # cache, sentinella ed EPW cancellati: run pulito e EPW rigenerato dal CSV
  rm -rf "progetti/$P/.cache" "progetti/$P/.br_done" \
         "progetti/$P/PVGIS_45.3000_9.3400_TMY.epw"
  if ! python3 engine/calcola_br.py "progetti/$P/SolRatio_progetto.xlsm" \
       > "smoke_${P}.log" 2>&1; then
    echo "ERR: calcola_br.py su $P exit con errore. Vedi smoke_${P}.log"
    exit 1
  fi
done

echo
echo "=== Estrazione e verifica K_agv ==="
python3 _smoke_check_kagv.py
