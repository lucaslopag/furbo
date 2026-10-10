#!/bin/bash
# Script para subir cambios al repositorio de GitHub
# Uso: ./subir.sh

REPO="lucaslopag/furbo"

# Pedir el token si no está configurado
CURRENT_URL=$(git remote get-url origin 2>/dev/null)
if echo "$CURRENT_URL" | grep -q "@"; then
    echo "Remote ya configurado con credenciales."
else
    echo "Introduce tu GitHub Personal Access Token:"
    read -s TOKEN
    git remote set-url origin "https://lucaslopag:${TOKEN}@github.com/${REPO}.git"
    echo "Token configurado."
fi

# Añadir todos los cambios, hacer commit y push
git add -A
echo "Introduce un mensaje para el commit (o pulsa ENTER para usar uno por defecto):"
read MSG
if [ -z "$MSG" ]; then
    MSG="Actualización $(date '+%Y-%m-%d %H:%M')"
fi

git commit -m "$MSG"
git push -u origin main

echo ""
echo "¡Cambios subidos a https://github.com/${REPO} correctamente!"
