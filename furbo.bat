@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Furbo - AceStream TV

cd /d "%~dp0"

:: 1. Comprobar actualizaciones en GitHub
echo [*] Buscando actualizaciones en GitHub...
set "updates=0"
git fetch origin main >nul 2>&1
for /f "tokens=*" %%a in ('git rev-list --count HEAD..origin/main 2^>nul') do set "updates=%%a"
if "%updates%"=="0" (
    echo [OK] Lista de canales y programa actualizados.
) else (
    echo.
    echo [+] %updates% cambios encontrados. Descargando actualizaciones...
    rem --autostash conserva tus cambios locales (canales anadidos, etc.) durante la actualizacion
    git pull --ff-only --autostash >nul 2>&1
    if errorlevel 1 (
        echo [!] No se pudieron aplicar las actualizaciones ahora mismo. Se usara la version actual.
    ) else (
        echo [OK] Actualizado correctamente.
    )
    timeout /t 2 >nul
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

:: 3. La VPN antibloqueo (Cloudflare WARP) ya NO se gestiona aqui.
::    El launcher de Python la conecta solo (aceptando los terminos), la vigila
::    mientras Furbo esta abierto y la desconecta al salir.

:: 4. Comprobar dependencias minimas de Python
python -c "import curses" >nul 2>&1
if errorlevel 1 (
    echo [*] Configurando dependencias de Python...
    python -m pip install -r backend\requirements.txt "windows-curses>=2.4.2"
)

:: 5. Lanzar la aplicacion (gestiona la VPN y la apaga al cerrar)
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
python backend\acestream_launcher.py
set "EXIT_CODE=%ERRORLEVEL%"

if "%EXIT_CODE%" neq "0" (
    echo.
    echo [!] Error al ejecutar. Asegurate de haber ejecutado instalar.bat primero.
    echo     Si el programa se cerro por un fallo, los detalles estan en backend\acestream_error.log
    pause
)
