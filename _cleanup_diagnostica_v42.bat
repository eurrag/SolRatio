@echo off
REM Cleanup file diagnostici creati durante il debug v4.2 cache scene .oct.
REM Da eseguire dopo che il fix e validato, prima del bump v4.2.0.

cd /d "%~dp0"

echo === Cleanup file diagnostici v4.2 ===
echo.

REM Bat di diagnostica/test temporanei
for %%F in (_diagnosi_cache.bat _test_oconv_isolato.bat _test_oconv_v2.bat _test_oconv_v2.log) do (
    if exist "%%F" (
        echo Cancello: %%F
        del /f /q "%%F"
    )
)

REM Log di diagnostica e smoke regression
for %%F in (diagnosi_cache_oct.log diagnosi_cache_oct_v2.log diagnosi_cache_oct_v3.log diagnosi_cache_oct_final.log smoke_regression.log) do (
    if exist "%%F" (
        echo Cancello: %%F
        del /f /q "%%F"
    )
)

REM Cartella dump scene oct
if exist "_debug_oconv" (
    echo Cancello cartella: _debug_oconv\
    rmdir /s /q "_debug_oconv"
)

REM Backup xlsm creati durante patch button (chiedi conferma)
if exist "progetti\Sample_EW\SolRatio_progetto.xlsm.bak" (
    echo.
    echo Trovato backup xlsm: progetti\Sample_EW\SolRatio_progetto.xlsm.bak
    echo Cancellarlo? Premi CTRL+C per annullare, o INVIO per confermare.
    pause >nul
    del /f /q "progetti\Sample_EW\SolRatio_progetto.xlsm.bak"
    echo Backup xlsm cancellato.
)

REM Eventuali altri .bak
for %%P in (progetti\*\SolRatio_progetto.xlsm.bak) do (
    if exist "%%P" (
        echo Trovato altro backup: %%P
        del /f /q "%%P"
    )
)

echo.
echo === Cleanup completato ===
echo.
echo File preservati ^(utili in produzione^):
echo   _patch_button_label.py
echo   _lancia_sweep.bat
echo   _orchestratore_runs\
echo   engine\orchestratore_sweep.py
echo   engine\plot_profilo_pitch.py
echo   engine\_scene_cache.py
