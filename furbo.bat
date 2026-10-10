@echo off
chcp 65001 >nul
title Furbo - AceStream TV

:: Auto-actualizar desde GitHub (si hay conexion)
git pull --quiet 2>nul

:: Lanzar el programa
python acestream_launcher.py
if %errorlevel% neq 0 (
    echo.
    echo [!] Error al ejecutar. Asegurate de haber ejecutado instalar.bat primero.
    pause
)
