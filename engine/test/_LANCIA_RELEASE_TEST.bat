@echo off
REM SolRatio v4.1.0 — Launcher orchestratore release test
REM Esegue release_orchestrator.py con i flag passati dalla riga di comando.
REM
REM Esempi:
REM   _LANCIA_RELEASE_TEST.bat                     -- modalita' rapida (~25 min)
REM   _LANCIA_RELEASE_TEST.bat --full              -- tutti gli step (~3 ore)
REM   _LANCIA_RELEASE_TEST.bat --full --skip-battery
REM   _LANCIA_RELEASE_TEST.bat --baseline-kagv 0.8732 --tolerance-pct 0.5

setlocal
set PYEXE=C:\Users\Utente\AppData\Local\Python\bin\python.exe
set SCRIPT_DIR=%~dp0
set ORCHESTRATOR=%SCRIPT_DIR%release_orchestrator.py

if not exist "%PYEXE%" (
    echo [ERRORE] Python non trovato in %PYEXE%
    echo Modificare la variabile PYEXE in questo file BAT.
    pause
    exit /b 1
)

if not exist "%ORCHESTRATOR%" (
    echo [ERRORE] release_orchestrator.py non trovato in %SCRIPT_DIR%
    pause
    exit /b 1
)

echo ====================================================================
echo  SolRatio v4.1.0 -- Release Orchestrator
echo ====================================================================
echo  Python: %PYEXE%
echo  Script: %ORCHESTRATOR%
echo  Args:   %*
echo ====================================================================
echo.

REM Avviso sui tempi previsti (dipende dai flag passati)
echo  STIMA TEMPI:
echo    --quick (default)     : ~20 minuti  (pre-flight + smoke + features)
echo    --full                : ~3 ore      (sopra + batteria 47 + validazione vs BR)
echo    --full --skip-battery : ~50 minuti  (full senza batteria)
echo.
echo  Durante l'esecuzione, l'orchestratore stampa heartbeat ogni 60 sec
echo  per confermare che il PC sta lavorando (non e' bloccato).
echo.
echo  Premi un tasto per avviare i test (Ctrl+C per annullare)...
pause >nul
echo.

"%PYEXE%" "%ORCHESTRATOR%" %*

set EXITCODE=%ERRORLEVEL%
echo.
echo ====================================================================
echo  Orchestratore terminato (exit code: %EXITCODE%)
echo ====================================================================
pause
exit /b %EXITCODE%
