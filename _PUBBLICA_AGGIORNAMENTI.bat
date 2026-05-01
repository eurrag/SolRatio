@echo off
REM SolRatio - Pubblica aggiornamenti su GitHub
REM ============================================
REM Routine di push per modifiche a codice/documentazione.
REM NON crea tag ne triggera release Zenodo - per quello vedi
REM la sezione in fondo a questo file.

setlocal
set REPO_DIR=%~dp0
cd /d "%REPO_DIR%"

echo ================================================================
echo  SolRatio -- Pubblica aggiornamenti su GitHub
echo ================================================================
echo  Cartella: %REPO_DIR%
echo.

REM Verifica che sia un repo git
if not exist ".git" (
    echo [ERRORE] Questa cartella non e' un repository git.
    echo Esegui prima 'git init' o spostati nella cartella corretta.
    pause
    exit /b 1
)

REM Verifica connessione al remote
git remote -v >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Nessun remote git configurato.
    pause
    exit /b 1
)

echo --- Stato corrente del repository ---
git status --short
echo.

REM Conta i file modificati
for /f %%i in ('git status --short ^| find /c /v ""') do set N_CHANGES=%%i

if "%N_CHANGES%"=="0" (
    echo Nessuna modifica da pubblicare. Tutto gia' allineato con GitHub.
    echo.
    pause
    exit /b 0
)

echo Trovate %N_CHANGES% righe di modifiche sopra.
echo.
echo --- Anteprima diff (prime 50 righe) ---
git diff --stat HEAD
echo.

set /p CONFIRM="Procedere con add + commit + push? [s/N]: "
if /i not "%CONFIRM%"=="s" (
    echo Annullato.
    pause
    exit /b 0
)

echo.
set /p MSG="Messaggio di commit (breve, in italiano): "
if "%MSG%"=="" (
    echo [ERRORE] Messaggio commit vuoto. Annullato.
    pause
    exit /b 1
)

echo.
echo --- Add ---
git add -A
if errorlevel 1 (
    echo [ERRORE] git add fallito.
    pause
    exit /b 1
)

echo.
echo --- Commit ---
git commit -m "%MSG%"
if errorlevel 1 (
    echo [ERRORE] git commit fallito.
    pause
    exit /b 1
)

echo.
echo --- Push ---
git push
if errorlevel 1 (
    echo [ERRORE] git push fallito.
    echo Controllare credenziali GitHub e connessione rete.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo  Aggiornamenti pubblicati con successo su GitHub.
echo ================================================================
echo.
echo  Verifica online: https://github.com/eurrag/SolRatio/commits/main
echo.
pause
exit /b 0


REM =================================================================
REM  NOTA - Per pubblicare una NUOVA RELEASE con DOI Zenodo nuovo:
REM =================================================================
REM
REM  Questo bat NON crea tag ne triggera Zenodo. Per una release nuova:
REM
REM  1. Aggiorna engine\VERSION (es. "4.1.1" o "4.2.0")
REM  2. Aggiorna documentazione\CHANGELOG.md con la nuova sezione
REM  3. Esegui questo bat per pubblicare il commit dei file aggiornati
REM  4. Crea il tag e pubblica su GitHub:
REM
REM     git tag -a v4.1.1 -m "SolRatio v4.1.1"
REM     git push origin v4.1.1
REM
REM  5. Vai su https://github.com/eurrag/SolRatio/releases/new
REM     - Seleziona il tag v4.1.1
REM     - Titolo: "SolRatio v4.1.1"
REM     - Descrizione: incolla la sezione corrispondente dal CHANGELOG
REM     - Publish release
REM
REM  6. Zenodo riceve il webhook e crea automaticamente un DOI nuovo
REM     per la nuova versione. Verifica su:
REM     https://zenodo.org/account/settings/github/repository/eurrag/SolRatio
REM
REM  7. Aggiorna CITATION.cff con il nuovo DOI versione
REM     (il Concept DOI nel README resta uguale - punta sempre all'ultima)
REM
REM  8. Esegui di nuovo questo bat per committare l'aggiornamento di
REM     CITATION.cff (NON serve un altro tag - e' solo doc).
REM
REM =================================================================
