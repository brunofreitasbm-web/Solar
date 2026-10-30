@echo off
title Solar ROI
cd /d "%~dp0"

rem Atualiza o codigo (se estiver sem internet, segue com a versao atual).
git checkout master >nul 2>&1
git pull --ff-only origin master >nul 2>&1

rem Primeira execucao: cria o ambiente Python do projeto.
if not exist ".venv\Scripts\python.exe" (
    echo Preparando o Solar ROI pela primeira vez. Isso leva alguns minutos...
    py -m venv .venv 2>nul || python -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo Nao encontrei o Python. Instale em python.org e marque "Add Python to PATH".
        pause
        exit /b 1
    )
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt

rem Usa os dados do executavel antigo (faturas, PDFs, backups) se ele existir, e traz os loggers para la uma unica vez.
if exist "dist\SolarROI\data\solar.db" (
    set "SOLAR_RAIZ_DADOS=%~dp0dist\SolarROI"
    if exist "data\solar.db" if not exist "dist\SolarROI\data\loggers_importados.txt" (
        ".venv\Scripts\python.exe" -m solar.loggers.coleta importar "data\solar.db"
        echo ok> "dist\SolarROI\data\loggers_importados.txt"
    )
)

start "Solar ROI" /min ".venv\Scripts\python.exe" run_app.py
exit
