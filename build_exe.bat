@echo off
rem Gera o aplicativo clicavel em dist\SolarROI e atualiza o atalho da Area de Trabalho.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Crie o ambiente Python primeiro: rode iniciar_solar.bat uma vez.
    pause
    exit /b 1
)

rem O PyInstaller apaga dist\SolarROI: guarda antes o banco, os PDFs e os backups do app.
set "DADOS_TEMP=%TEMP%\solar_dados_build"
if exist "%DADOS_TEMP%" rmdir /s /q "%DADOS_TEMP%"
if exist "dist\SolarROI\data" robocopy "dist\SolarROI\data" "%DADOS_TEMP%\data" /E /NFL /NDL /NJH /NJS >nul
if exist "dist\SolarROI\backups" robocopy "dist\SolarROI\backups" "%DADOS_TEMP%\backups" /E /NFL /NDL /NJH /NJS >nul

echo Gerando o aplicativo... isso leva alguns minutos.
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean SolarROI.spec
if errorlevel 1 (
    echo Falha ao gerar o aplicativo. Seus dados continuam em "%DADOS_TEMP%".
    pause
    exit /b 1
)

if exist "%DADOS_TEMP%\data" robocopy "%DADOS_TEMP%\data" "dist\SolarROI\data" /E /NFL /NDL /NJH /NJS >nul
if exist "%DADOS_TEMP%\backups" robocopy "%DADOS_TEMP%\backups" "dist\SolarROI\backups" /E /NFL /NDL /NJH /NJS >nul
if exist "%DADOS_TEMP%" rmdir /s /q "%DADOS_TEMP%"

if exist ".env" copy /y ".env" "dist\SolarROI\.env" >nul

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0criar_atalho.ps1" -Silencioso
echo.
echo Pronto. Abra pelo atalho "Solar ROI" na Area de Trabalho.
pause
