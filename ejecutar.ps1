# CivilBeam 2026 - Lanzador en PowerShell
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "  CIVILBEAM 2026 - ANALISIS DE VIGAS ISOSTATICAS" -ForegroundColor Yellow
Write-Host "  Universidad Distrital Francisco Jose de Caldas - Facultad Tecnologica" -ForegroundColor White
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host ""

$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
}

if (-not $pythonCmd) {
    Write-Host "[ERROR] No se encontro Python en el sistema o no esta en el PATH." -ForegroundColor Red
    Write-Host "Descargue e instale Python desde https://www.python.org/downloads/ marcando 'Add to PATH'." -ForegroundColor Yellow
    Read-Host "Presione Enter para salir..."
    exit 1
}

$venvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[1/2] Configurando entorno virtual .venv..." -ForegroundColor Green
    if (Test-Path ".\.venv") {
        Remove-Item -Recurse -Force ".\.venv" -ErrorAction SilentlyContinue
    }
    & $pythonCmd -m venv .venv
}

$runPy = $null
if (Test-Path $venvPython) {
    $runPy = $venvPython
} else {
    Write-Host "[AVISO] Usando Python del sistema directamente." -ForegroundColor Yellow
    $runPy = $pythonCmd
}

$testImport = & $runPy -c "import flet, numpy, scipy, matplotlib, docxtpl" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[1/2] Instalando paquetes y dependencias (flet, numpy, matplotlib, etc.)..." -ForegroundColor Yellow
    Write-Host "Esto se realiza una sola vez. Por favor espere mientras se descargan e instalan..." -ForegroundColor Yellow
    & $runPy -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Fallo la instalacion de dependencias. Verifique conexion a Internet." -ForegroundColor Red
        Read-Host "Presione Enter para salir..."
        exit 1
    }
    Write-Host "[1/2] Dependencias instaladas con exito." -ForegroundColor Green
} else {
    Write-Host "[1/2] Entorno virtual y dependencias verificadas correctamente." -ForegroundColor Green
}

Write-Host ""
Write-Host "[2/2] Iniciando aplicacion CivilBeam 2026..." -ForegroundColor Cyan
& $runPy main.py