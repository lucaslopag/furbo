@echo off
chcp 65001 >nul
title Instalador de Furbo (AceStream TV)
echo.
echo ============================================
echo   INSTALADOR DE FURBO - AceStream TV
echo ============================================
echo.

:: 1. Comprobar si Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python no esta instalado. Instalando automaticamente...
    echo.
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
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
) else (
    echo [OK] Python ya esta instalado.
)

:: 2. Comprobar si Git esta instalado
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Git no esta instalado. Instalando automaticamente...
    winget install Git.Git --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo [!] No se pudo instalar Git automaticamente.
        echo     Descargalo manualmente desde: https://git-scm.com/download/win
        pause
        exit /b 1
    )
    echo [OK] Git instalado correctamente.
    echo [!] CIERRA esta ventana y vuelve a ejecutar instalar.bat
    pause
    exit /b 0
) else (
    echo [OK] Git ya esta instalado.
)

:: 3. Instalar dependencias de Python
echo.
echo Instalando dependencias de Python...
pip install -r requirements.txt windows-curses
if %errorlevel% neq 0 (
    echo [!] Error instalando dependencias.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.

:: 4. Comprobar VLC
if exist "C:\Program Files\VideoLAN\VLC\vlc.exe" (
    echo [OK] VLC detectado.
) else if exist "C:\Program Files (x86)\VideoLAN\VLC\vlc.exe" (
    echo [OK] VLC detectado.
) else (
    echo [!] VLC no esta instalado. Instalando automaticamente...
    winget install VideoLAN.VLC --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo [!] Instala VLC manualmente desde: https://www.videolan.org/vlc/
    ) else (
        echo [OK] VLC instalado correctamente.
    )
)

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
