#!/bin/bash

# Script de arranque para AceStream Launcher
# Ejecuta el script de Python asegurándose de estar en el directorio correcto

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

python3 acestream_launcher.py
