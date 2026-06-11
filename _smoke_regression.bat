@echo off
REM Smoke regression SolRatio: lancia calcola_br sui progetti Sample (N-S) e
REM Sample_EW (E-W) e verifica il K_agv SAU Cereali C3 contro i riferimenti
REM (vedi _smoke_check_kagv.py: tolleranza +/- 0.2 punti percentuali).

cd /d "%~dp0"

echo === Smoke regression SolRatio ===
echo Progetti: Sample (N-S) + Sample_EW (E-W)
echo.

for %%P in (Sample Sample_EW) do (
    echo === RUN %%P ^(~3-5 min^) ===
    REM cache, sentinella ed EPW cancellati: run pulito e EPW rigenerato dal CSV
    if exist "progetti\%%P\.cache"   rmdir /s /q "progetti\%%P\.cache"
    if exist "progetti\%%P\.br_done" del /q "progetti\%%P\.br_done"
    if exist "progetti\%%P\PVGIS_45.3000_9.3400_TMY.epw" del /q "progetti\%%P\PVGIS_45.3000_9.3400_TMY.epw"
    python engine\calcola_br.py "progetti\%%P\SolRatio_progetto.xlsm" > smoke_%%P.log 2>&1
    if errorlevel 1 (
        echo ERR: calcola_br.py su %%P exit con errore. Vedi smoke_%%P.log
        exit /b 1
    )
)

echo.
echo === Estrazione e verifica K_agv ===
python _smoke_check_kagv.py
set CHECK_RC=%errorlevel%

echo.
if %CHECK_RC%==0 (
    echo === Smoke regression OK ===
) else (
    echo === Smoke regression FAIL ===
)
exit /b %CHECK_RC%
