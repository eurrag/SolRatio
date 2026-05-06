@echo off
REM Smoke regression test pre-bump v4.2.0:
REM Lancia calcola_br su Sample_EW e verifica K_agv SAU vs riferimento v4.1.2.

cd /d "%~dp0"

echo === Smoke regression v4.2.0 ===
echo Progetto: progetti\Sample_EW\SolRatio_progetto.xlsm
echo Riferimento: K_agv SAU Cereali C3 = 84.00%% ^(v4.1.2^), tolleranza +/- 0.5%%
echo.

REM Cancella cache eventualmente esistente per partire pulito
if exist "progetti\Sample_EW\.cache" (
    echo Cancello cache scene esistente...
    rmdir /s /q "progetti\Sample_EW\.cache"
)

echo === Run calcola_br.py ^(~3-5 min^) ===
python engine\calcola_br.py "progetti\Sample_EW\SolRatio_progetto.xlsm" > smoke_regression.log 2>&1
if errorlevel 1 (
    echo ERR: calcola_br.py exit con errore. Vedi smoke_regression.log
    type smoke_regression.log
    exit /b 1
)
echo Run completato. Log salvato in smoke_regression.log
echo.

echo === Estrazione e verifica K_agv SAU ===
python _smoke_check_kagv.py
set CHECK_RC=%errorlevel%

echo.
if %CHECK_RC%==0 (
    echo === Smoke regression OK -- pronto per bump v4.2.0 ===
) else (
    echo === Smoke regression FAIL -- non procedere col bump ===
)
exit /b %CHECK_RC%
