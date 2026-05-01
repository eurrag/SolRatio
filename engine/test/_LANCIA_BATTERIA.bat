@echo off
setlocal
REM ====================================================================
REM  Batteria SolRatio v4 - launcher portabile
REM  Posizione: engine\test\_LANCIA_BATTERIA.bat
REM  Cartella dati di default: ..\..\progetti\test_battery
REM
REM  Usa %~dp0 (cartella di questo .bat) per rimanere portabile.
REM  Argomenti aggiuntivi vengono passati a run_battery.py
REM    es. _LANCIA_BATTERIA.bat --no-resume
REM        _LANCIA_BATTERIA.bat --only 05_BORDO
REM        _LANCIA_BATTERIA.bat --dry-run
REM ====================================================================

if not defined PYEXE (
    if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
        set "PYEXE=%LOCALAPPDATA%\Python\bin\python.exe"
    ) else (
        where py >nul 2>nul
        if not errorlevel 1 ( set "PYEXE=py" ) else ( set "PYEXE=python" )
    )
)

set "SCRIPT=%~dp0run_battery.py"

echo ============================================================
echo  Batteria SolRatio v4 - 47 test
echo  Python : %PYEXE%
echo  Script : %SCRIPT%
echo  Tempo stimato: ~2h 30m (con resume sui test gia' fatti)
echo ============================================================
echo.

"%PYEXE%" "%SCRIPT%" %*

echo.
echo Batteria conclusa. Vedi batteria_log.txt e 99_ANALISI/ nella cartella dati.
pause
endlocal
