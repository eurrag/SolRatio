@echo off
REM Sweep parametrico H_min x axis_azimuth -- SolRatio v4.2
REM ============================================================
REM Esegue una griglia di simulazioni variando H_min e axis_azimuth,
REM raccoglie K_agv per coltura target, genera CSV + grafici PNG.
REM
REM Default: 9 H_min x 5 azimuth = 45 run x ~3-5min cad. = ~2.5 ore
REM
REM Uso:
REM   _lancia_sweep.bat                          -> sweep completo Sample_EW
REM   _lancia_sweep.bat dry                      -> solo dry-run (vede griglia)
REM   _lancia_sweep.bat resume YYYYMMDD_HHMMSS   -> riprende da run interrotto
REM   _lancia_sweep.bat <progetto.xlsm>          -> sweep su altro progetto

cd /d "%~dp0"

echo === Syntax check orchestratore_sweep.py ===
python -c "import ast; ast.parse(open(r'engine\orchestratore_sweep.py', encoding='utf-8').read()); print('SYNTAX OK')"
if errorlevel 1 (
    echo SYNTAX ERROR -- abort.
    exit /b 1
)

if "%~1"=="dry" (
    python engine\orchestratore_sweep.py "progetti\Sample_EW\SolRatio_progetto.xlsm" --dry-run
    exit /b 0
)

if "%~1"=="resume" (
    if "%~2"=="" (
        echo ERRORE: specifica timestamp del run da riprendere.
        echo Es: _lancia_sweep.bat resume 20260504_180000
        exit /b 1
    )
    python engine\orchestratore_sweep.py "progetti\Sample_EW\SolRatio_progetto.xlsm" --resume %~2
    exit /b %errorlevel%
)

if not "%~1"=="" (
    REM Progetto custom
    python engine\orchestratore_sweep.py "%~1"
    exit /b %errorlevel%
)

REM Default: Sample_EW con griglia 9 x 5
python engine\orchestratore_sweep.py "progetti\Sample_EW\SolRatio_progetto.xlsm"
