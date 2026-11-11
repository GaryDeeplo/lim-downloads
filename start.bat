@echo off
rem Lance Downloads Manager sans console : interface + tri automatique + icone dans la barre des taches.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" -m dm
