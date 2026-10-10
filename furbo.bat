@echo off
chcp 65001 >nul
title Furbo - AceStream TV

:: Volver a la carpeta del script (necesario al elevar a Administrador)
cd /d "%~dp0"

:: Auto-actualizar desde GitHub (si hay conexion)
git pull --quiet 2>nul

:: Pedir permisos de Administrador para parche antibloqueos (DNS)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Solicitando permisos para aplicar el parche antibloqueos...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Aplicar parche DNS (Cloudflare) de forma invisible en todos los adaptadores activos
echo [*] Aplicando parche antibloqueos de red...
powershell -Command "Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and $_.InterfaceAlias -notmatch 'vEthernet|Pseudo'} | Set-DnsClientServerAddress -ServerAddresses ('1.1.1.1','1.0.0.1')" >nul 2>&1

:: Lanzar el programa
python acestream_launcher.py
if errorlevel 1 (
    echo.
    echo [!] Error al ejecutar. Asegurate de haber ejecutado instalar.bat primero.
    pause
)

