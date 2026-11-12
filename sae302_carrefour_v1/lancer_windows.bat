@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    py -3.12 main.py
)
if errorlevel 1 (
    echo.
    echo Une erreur s'est produite. Verifiez le README et les dependances.
    pause
)
