@echo off
rem TabDeck: pubblica una nuova versione su GitHub (solo per chi sviluppa).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pubblica.ps1" %*
pause
