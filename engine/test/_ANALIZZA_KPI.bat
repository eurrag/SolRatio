@echo off
setlocal
REM ====================================================================
REM  Aggregatore KPI batteria SolRatio v4 - launcher portabile
REM  Posizione: engine\test\_ANALIZZA_KPI.bat
REM  Cartella dati di default: ..\..\progetti\test_battery
REM ====================================================================

if not defined PYEXE (
    if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
        set "PYEXE=%LOCALAPPDATA%\Python\bin\python.exe"
    ) else (
        where py >nul 2>nul
        if not errorlevel 1 ( set "PYEXE=py" ) else ( set "PYEXE=python" )
    )
)

set "SCRIPT=%~dp0confronta_KPI.py"

echo ============================================================
echo  Analisi KPI batteria SolRatio v4
echo ============================================================
echo.

"%PYEXE%" "%SCRIPT%" %*

echo.
pause
endlocal
