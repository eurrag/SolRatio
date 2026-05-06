@echo off
REM ===============================================================
REM _NUOVA_VERSIONE.bat  -  SolRatio v4.2.0
REM
REM Orchestratore semi-interattivo per il rilascio di una nuova
REM versione di SolRatio. Esegue i passi 1-9 della pipeline a 14
REM step descritta in documentazione/ROADMAP.md.
REM
REM PRE-REQUISITI:
REM   - GitHub CLI installato (gh) e autenticato (gh auth login)
REM   - git working tree pulito
REM   - python in PATH con tutti i moduli del repo
REM   - documentazione/CHANGELOG.md gia' aggiornato con la nuova
REM     sezione "## vX.Y.Z (YYYY-MM-DD)" come PRIMA voce
REM
REM USO:
REM   _NUOVA_VERSIONE.bat                 (legge versione da CHANGELOG)
REM   _NUOVA_VERSIONE.bat --version 4.2.0 (esplicita)
REM
REM Lo step 11-13 (polling Zenodo + update DOI) restano manuali
REM in v4.2.0; vanno eseguiti dopo la creazione della release GitHub
REM con: python engine\release_helper.py update-doi --doi 10.5281/zenodo.NNNNNNN
REM ===============================================================
setlocal EnableDelayedExpansion

cd /d "%~dp0"

if "%1"=="--version" (
  set NEW_VERSION=%2
  set BUMP_MODE=explicit
) else (
  set NEW_VERSION=
  set BUMP_MODE=changelog
)

echo.
echo ===============================================================
echo  SolRatio - Pipeline rilascio nuova versione
echo ===============================================================
echo.

REM Step 2: Pre-check git
echo [Step 2/9] Pre-check working tree pulito...
git diff-index --quiet HEAD -- || (
  echo [ERR] Working tree non pulito. Commit o stash le modifiche prima.
  git status --short
  exit /b 1
)
echo   OK

REM Step 3: Status corrente
echo.
echo [Step 3/9] Status corrente:
python engine\release_helper.py status
if errorlevel 1 (
  echo [ERR] release_helper status fallito
  exit /b 1
)

REM Step 4-5: CHANGELOG check
echo.
echo [Step 4/9] Verifica CHANGELOG...
if not exist documentazione\CHANGELOG.md (
  echo [ERR] documentazione\CHANGELOG.md non trovato
  exit /b 1
)
echo   Prime righe di CHANGELOG:
powershell -Command "Get-Content documentazione\CHANGELOG.md -Head 5"

echo.
set /p PROCEED=Confermi di voler procedere col bump? (s/N):
if /i not "!PROCEED!"=="s" (
  echo Operazione annullata.
  exit /b 0
)

REM Step 6: Bump
echo.
echo [Step 6/9] Bump versione...
if "%BUMP_MODE%"=="explicit" (
  python engine\release_helper.py bump --new-version !NEW_VERSION!
) else (
  python engine\release_helper.py bump-from-changelog
)
if errorlevel 1 (
  echo [ERR] Bump fallito.
  exit /b 1
)

REM Step 7: Mostra diff
echo.
echo [Step 7/9] Diff atteso:
git diff --stat
echo.
set /p CONFIRM=Diff OK? Procedo con commit + tag + push? (s/N):
if /i not "!CONFIRM!"=="s" (
  echo Annullato. Per ripristinare: git checkout -- .
  exit /b 0
)

REM Step 8: Commit
REM Estrai versione effettiva da engine\VERSION (single source of truth)
set /p ACTUAL_VERSION=<engine\VERSION
echo.
echo [Step 8/9] Commit + tag v!ACTUAL_VERSION!...
git add -A
git commit -m "release v!ACTUAL_VERSION!"
if errorlevel 1 (
  echo [ERR] Commit fallito.
  exit /b 1
)

REM Step 9: Tag + push
git tag -a v!ACTUAL_VERSION! -m "SolRatio v!ACTUAL_VERSION!"
git push origin main
git push origin v!ACTUAL_VERSION!
if errorlevel 1 (
  echo [WARN] Push fallito - verifica connessione e ritenta manualmente
  exit /b 1
)

REM Step 10: Release GitHub
echo.
echo [Step 10/9 (extra)] Creazione release su GitHub...
echo   Nota: ti chiedera' di confermare. Se non vuoi crearla ora, premi Ctrl+C.
gh release create v!ACTUAL_VERSION! --title "SolRatio v!ACTUAL_VERSION!" --generate-notes

echo.
echo ===============================================================
echo  COMPLETATO step 1-10. v!ACTUAL_VERSION! pubblicata su GitHub.
echo  Prossimo passo manuale (step 11-13):
echo    1. Attendi che Zenodo sincronizzi il rilascio (~30 sec - 5 min)
echo    2. Recupera il DOI da https://zenodo.org/account/settings/github
echo    3. Esegui:
echo       python engine\release_helper.py update-doi --doi 10.5281/zenodo.NNNNNNN
echo    4. git add CITATION.cff README.md
echo    5. git commit -m "docs: add DOI for v!ACTUAL_VERSION!"
echo    6. git push origin main
echo ===============================================================
endlocal
