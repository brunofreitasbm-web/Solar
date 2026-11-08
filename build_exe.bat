@echo off
rem Gera o aplicativo clicavel em dist\SolarROI e atualiza o atalho da Area de Trabalho.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Crie o ambiente Python primeiro: rode iniciar_solar.bat uma vez.
    pause
    exit /b 1
)

echo Gerando o aplicativo... isso leva alguns minutos.
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean SolarROI.spec
if errorlevel 1 (
    echo Falha ao gerar o aplicativo.
    pause
    exit /b 1
)

if exist ".env" copy /y ".env" "dist\SolarROI\.env" >nul

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0criar_atalho.ps1" -Silencioso
echo.
echo Pronto. Abra pelo atalho "Solar ROI" na Area de Trabalho.
pause
