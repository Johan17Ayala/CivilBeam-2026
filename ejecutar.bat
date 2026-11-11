@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title CivilBeam 2026 - Universidad Distrital

echo ===============================================================================
echo   CIVILBEAM 2026 - ANALISIS DE VIGAS ISOSTATICAS
echo   Universidad Distrital Francisco Jose de Caldas - Facultad Tecnologica
echo   Ingenieria Civil - Programacion II
echo ===============================================================================
echo.

set "PYCMD="
where python >nul 2>&1
if !errorlevel! equ 0 (
    set "PYCMD=python"
) else (
    where py >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYCMD=py -3"
    )
)

if "%PYCMD%"=="" (
    echo [ERROR] No se encontro Python en este equipo o no esta en el PATH.
    echo Por favor descargue e instale Python desde https://www.python.org/downloads/
    echo IMPORTANTE: Marque la casilla "Add python.exe to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

set "RUN_PY="

if not exist ".venv\Scripts\python.exe" (
    echo [1/2] Configurando entorno virtual .venv...
    if exist ".venv" rmdir /s /q ".venv" >nul 2>&1
    %PYCMD% -m venv .venv
)

if exist ".venv\Scripts\python.exe" (
    set "RUN_PY=.venv\Scripts\python.exe"
) else (
    echo [AVISO] No se pudo crear .venv local. Se usara Python del sistema directamente.
    set "RUN_PY=%PYCMD%"
)

REM Verificar si flet y las demas librerias ya estan instaladas
%RUN_PY% -c "import flet, numpy, scipy, matplotlib, docxtpl" >nul 2>&1
if !errorlevel! neq 0 (
    echo [1/2] Instalando paquetes y librerias necesarias: flet, numpy, matplotlib, etc.
    echo Esto se realiza una sola vez. Por favor espere mientras se descargan e instalan.
    echo.
    %RUN_PY% -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo.
        echo [ERROR] Fallo la instalacion de dependencias.
        echo Verifique que este equipo tenga conexion a Internet para descargar las librerias.
        pause
        exit /b 1
    )
    echo [1/2] Librerias instaladas con exito.
) else (
    echo [1/2] Entorno y dependencias verificadas correctamente.
)

echo.
echo [2/2] Iniciando CivilBeam 2026...
echo.
%RUN_PY% main.py

if !errorlevel! neq 0 (
    echo.
    echo [AVISO] La aplicacion se cerro con codigo: !errorlevel!
    pause
)