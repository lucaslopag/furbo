@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Furbo - AceStream TV

cd /d "%~dp0"

:: 1. Comprobar actualizaciones en GitHub
echo [*] Buscando actualizaciones en GitHub...
git fetch origin main >nul 2>&1
for /f "tokens=*" %%a in ('git rev-list --count HEAD..origin/main 2^>nul') do set "updates=%%a"
if "%updates%" neq "0" if "%updates%" neq "" (
    echo.
    echo [+] %updates% cambios encontrados! Descargando actualizaciones...
    git pull
    timeout /t 2 >nul
) else (
    echo [OK] Lista de canales y programa actualizados.
)

:: 2. Deteccion activa y arranque de AceStream si no esta abierto
tasklist /fi "imagename eq ace_engine.exe" 2>nul | find /i "ace_engine.exe" >nul
if errorlevel 1 (
    echo [*] AceStream Engine no esta abierto. Buscando instalacion...
    set "ACE_EXE="
    if exist "%APPDATA%\AceStream\engine\ace_engine.exe" set "ACE_EXE=%APPDATA%\AceStream\engine\ace_engine.exe"
    if not defined ACE_EXE if exist "%LOCALAPPDATA%\AceStream\engine\ace_engine.exe" set "ACE_EXE=%LOCALAPPDATA%\AceStream\engine\ace_engine.exe"
    if not defined ACE_EXE if exist "%PROGRAMFILES%\AceStream\engine\ace_engine.exe" set "ACE_EXE=%PROGRAMFILES%\AceStream\engine\ace_engine.exe"
    if not defined ACE_EXE if exist "%PROGRAMFILES(X86)%\AceStream\engine\ace_engine.exe" set "ACE_EXE=%PROGRAMFILES(X86)%\AceStream\engine\ace_engine.exe"
    if not defined ACE_EXE if exist "%PROGRAMFILES%\AceStream\ace_engine.exe" set "ACE_EXE=%PROGRAMFILES%\AceStream\ace_engine.exe"

    if defined ACE_EXE (
        echo [+] Iniciando AceStream desde: !ACE_EXE!
        start "" "!ACE_EXE!"
        timeout /t 3 >nul
    ) else (
        echo [*] Busqueda en profundidad activa dentro del launcher...
    )
) else (
    echo [OK] AceStream Engine detectado y en ejecucion.
)

:: 3. Lanzar la aplicacion
python backend\acestream_launcher.py
if errorlevel 1 (
    echo.
    echo [!] Error al ejecutar. Asegurate de haber ejecutado instalar.bat primero.
    pause
)
