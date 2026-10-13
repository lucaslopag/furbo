@echo off
chcp 65001 >nul
title Instalador de Furbo (AceStream TV)

cd /d "%~dp0"
echo.
echo ============================================
echo   INSTALADOR DE FURBO - AceStream TV
echo ============================================
echo.

:: 1. Comprobar si Python esta instalado
python --version >nul 2>&1
if not errorlevel 1 goto python_ok

echo [!] Python no esta instalado. Instalando automaticamente...
echo.
winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
:: Refrescar variables de entorno temporalmente
set PATH=%PATH%;C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] No se pudo instalar Python automaticamente.
    echo     Descargalo manualmente desde: https://www.python.org/downloads/
    echo     IMPORTANTE: Marca la casilla "Add Python to PATH"
    pause
    exit /b 1
)
echo [OK] Python instalado correctamente.
echo [!] CIERRA esta ventana y vuelve a ejecutar instalar.bat
pause
exit /b 0

:python_ok
echo [OK] Python ya esta instalado.

:: 2. Comprobar si Git esta instalado
git --version >nul 2>&1
if not errorlevel 1 goto git_ok

echo [!] Git no esta instalado. Instalando automaticamente...
winget install Git.Git --accept-package-agreements --accept-source-agreements
set PATH=%PATH%;C:\Program Files\Git\cmd\
git --version >nul 2>&1
if errorlevel 1 (
    echo [!] No se pudo instalar Git automaticamente.
    echo     Descargalo manualmente desde: https://git-scm.com/download/win
    pause
    exit /b 1
)
echo [OK] Git instalado correctamente.
echo [!] CIERRA esta ventana y vuelve a ejecutar instalar.bat
pause
exit /b 0

:git_ok
echo [OK] Git ya esta instalado.

:: 3. Instalar y configurar la red antibloqueo (Cloudflare WARP)
call :find_warp
if defined WARP_CLI goto warp_installed

echo.
echo [!] VPN Antibloqueo (WARP) no encontrado. Instalando automaticamente...
winget install Cloudflare.Warp --accept-package-agreements --accept-source-agreements
call :find_warp
if defined WARP_CLI goto warp_installed

echo [!] No se pudo instalar WARP automaticamente.
echo     Puedes bajarlo manualmente de https://1.1.1.1 y volver a ejecutar instalar.bat
echo     (Furbo funciona igualmente, pero algunas operadoras pueden bloquear canales).
goto warp_done

:warp_installed
echo [*] Configurando WARP (aceptando terminos y registrando el dispositivo)...
sc start CloudflareWARP >nul 2>&1
timeout /t 3 >nul
"%WARP_CLI%" --accept-tos registration new >nul 2>&1
if errorlevel 1 "%WARP_CLI%" registration new >nul 2>&1
if errorlevel 1 "%WARP_CLI%" register >nul 2>&1
"%WARP_CLI%" --accept-tos disconnect >nul 2>&1
echo [OK] WARP listo: Furbo lo conecta y desconecta solo, sin pedirte nada.

:warp_done

:: 4. Instalar dependencias de Python
echo.
echo Instalando dependencias de Python...

:: Comprobar si pip existe, si no, bajarlo e instalarlo a la fuerza
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [!] Reparando gestor de paquetes de Python...
    curl -sSL https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python get-pip.py >nul 2>&1
    del get-pip.py >nul 2>&1
)

python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r backend\requirements.txt "windows-curses>=2.4.2"
if errorlevel 1 (
    echo [!] Error instalando dependencias.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.

:: 5. Comprobar VLC
if exist "C:\Program Files\VideoLAN\VLC\vlc.exe" goto vlc_ok
if exist "C:\Program Files (x86)\VideoLAN\VLC\vlc.exe" goto vlc_ok

echo [!] VLC no esta instalado. Instalando automaticamente...
winget install VideoLAN.VLC --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo [!] Instala VLC manualmente desde: https://www.videolan.org/vlc/
) else (
    echo [OK] VLC instalado correctamente.
)
goto vlc_done

:vlc_ok
echo [OK] VLC detectado.

:vlc_done

echo.
echo ============================================
echo   INSTALACION COMPLETADA
echo ============================================
echo.
echo   Para usar Furbo:
echo     1. Abre AceStream Engine (icono azul en la bandeja)
echo     2. Haz doble clic en "furbo.bat"
echo.
pause
exit /b 0

:find_warp
set "WARP_CLI="
where warp-cli >nul 2>&1 && set "WARP_CLI=warp-cli"
if not defined WARP_CLI if exist "%ProgramFiles%\Cloudflare\Cloudflare WARP\warp-cli.exe" set "WARP_CLI=%ProgramFiles%\Cloudflare\Cloudflare WARP\warp-cli.exe"
if not defined WARP_CLI if exist "%ProgramFiles(x86)%\Cloudflare\Cloudflare WARP\warp-cli.exe" set "WARP_CLI=%ProgramFiles(x86)%\Cloudflare\Cloudflare WARP\warp-cli.exe"
exit /b 0
