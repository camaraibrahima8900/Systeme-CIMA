#!/bin/bash
echo "🚀 Démarrage du Système CIMA..."
cd ~/projet_memoire/cima_docker
xhost +local:docker
docker compose up -d
echo ""
echo "✅ Système CIMA démarré !"
echo "🖥️  Tkinter  : ouvert automatiquement"
echo "🔐 Keycloak : http://localhost:8080"
echo "🗄️  MySQL    : localhost:3307"
echo ""
docker ps
