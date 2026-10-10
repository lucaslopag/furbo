@echo off
chcp 65001 >nul
title Furbo - AceStream TV

cd /d "%~dp0"

echo [*] Buscando actualizaciones en GitHub...
git fetch origin main >nul 2>&1
for /f "tokens=*" %%a in ('git rev-list --count HEAD..origin/main 2^>nul') do set "updates=%%a"
if "%updates%" neq "0" if "%updates%" neq "" (
    echo.
    echo [+] %updates% cambios encontrados! Descargando actualizaciones...
    git pull
    timeout /t 3 >nul
) else (
    echo [OK] Todo esta actualizado.
)

:: Lanzar el programa
python acestream_launcher.py
if errorlevel 1 (
    echo.
    echo [!] Error al ejecutar. Asegurate de haber ejecutado instalar.bat primero.
    pause
)

