@echo off
REM Lancia batteria di test L2+L3 v4.2.0 (14 test).
REM Tempo stimato: ~60-75 min totali (slope da 0 a 100%, axis 0/45/90/180).

cd /d "%~dp0"

echo === Syntax check ===
python -c "import ast; ast.parse(open(r'_test_slope_battery.py', encoding='utf-8').read()); print('SYNTAX OK')"
if errorlevel 1 exit /b 1

echo === Lancio batteria test slope (14 test, stima 60-75 min) ===
python _test_slope_battery.py
exit /b %errorlevel%
