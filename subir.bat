@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Subir cambios a GitHub - Furbo

cd /d "%~dp0"

echo [*] Preparando cambios para subir a GitHub...
git add -A

set /p MSG="Introduce mensaje de commit (ENTER para fecha actual): "
if "%MSG%"=="" (
    for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set mydate=%%a-%%b-%%c
    for /f "tokens=1-2 delims=: " %%a in ('time /t') do set mytime=%%a:%%b
    set MSG=Actualizacion !mydate! !mytime!
)

git commit -m "%MSG%"
if errorlevel 1 (
    echo [!] No habia cambios pendientes o commit cancelado.
    pause
    exit /b 0
)

echo [*] Subiendo a GitHub...
git push -u origin main
if errorlevel 1 (
    echo [!] Error al subir a GitHub. Comprueba la conexion o el token.
    pause
    exit /b 1
)

echo.
echo [OK] Cambios subidos a GitHub correctamente.
timeout /t 3 >nul
