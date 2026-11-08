<#
Cria (ou atualiza) o atalho "Solar ROI" na Area de Trabalho apontando para o executavel.
Sem ele, o app teria que ser aberto procurando a pasta dist\SolarROI.
#>
param([switch]$Silencioso)

$exe = Join-Path $PSScriptRoot 'dist\SolarROI\SolarROI.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    Write-Host 'O aplicativo ainda nao foi gerado. Rode build_exe.bat primeiro.' -ForegroundColor Yellow
    if (-not $Silencioso) { Read-Host 'Enter para fechar' }
    exit 1
}

$atalho = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Solar ROI.lnk'
$concha = New-Object -ComObject WScript.Shell
$destino = $concha.CreateShortcut($atalho)
$destino.TargetPath = $exe
$destino.WorkingDirectory = Split-Path -Parent $exe
$destino.IconLocation = "$exe,0"
$destino.Description = 'Solar ROI'
$destino.Save()

Write-Host "Atalho criado: $atalho"
if (-not $Silencioso) { Read-Host 'Enter para fechar' }
