@echo off
rem TabDeck: avvia il server (e, se c'e' adb, apre la pagina sul tablet collegato via USB).
rem Chiudi questa finestra (o Ctrl+C) per fermarlo.
title TabDeck
cd /d "%~dp0"
rem Python scelto dall'installer (data\python.txt), altrimenti quello nel PATH
set "PY=python"
if exist "%~dp0data\python.txt" set /p PY=<"%~dp0data\python.txt"
"%PY%" "%~dp0tabdeck.py" --open
pause
