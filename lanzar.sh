#!/bin/bash
# Lanzador de Furbo para Linux
# Auto-actualiza desde GitHub antes de arrancar

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Auto-actualizar si hay git y conexión
if command -v git &>/dev/null && [ -d .git ]; then
    git pull --quiet 2>/dev/null
fi

python3 acestream_launcher.py
