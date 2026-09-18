#!/bin/bash
# ============================================================
# lancer.sh — Script de démarrage du projet CIMA
# MySQL + Tkinter dans Docker (WSL Ubuntu)
# ============================================================

echo "🚀 Démarrage du projet CIMA..."

# 1. Autoriser l'affichage X11 depuis Docker
echo "📺 Autorisation de l'affichage X11..."
xhost +local:docker 2>/dev/null || echo "⚠️  xhost non disponible (normal sous Windows)"

# 2. Exporter la variable DISPLAY
export DISPLAY=${DISPLAY:-:0}
echo "🖥️  DISPLAY = $DISPLAY"

# 3. Lancer les conteneurs
echo "🐋 Lancement des conteneurs MySQL + Tkinter..."
docker-compose up --build

echo "✅ Arrêt terminé."
