@echo off
rem TabDeck: disinstallazione guidata. Ogni passo spiega cosa fa e chiede conferma.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installa.ps1" -Uninstall %*
pause
