# Projet CIMA — Docker Setup
## MySQL + Tkinter (Django en attente)

### Structure
```
cima_docker/
├── docker-compose.yml        ← orchestration des services
├── Dockerfile.tkinter        ← image Python + Tkinter
├── requirements.tkinter.txt  ← dépendances Python
├── dossiers_victimes_accidents.sql  ← script SQL (à copier ici)
├── lancer.sh                 ← script de démarrage WSL
└── app/
    └── interface_tkinter_v2.py  ← interface graphique
```

### Lancer le projet (WSL Ubuntu)
```bash
# Copier ton fichier SQL ici
cp ~/dossiers_victimes_accidents.sql .

# Donner les droits au script
chmod +x lancer.sh

# Lancer
./lancer.sh
```

### Ou manuellement
```bash
xhost +local:docker
export DISPLAY=:0
docker-compose up --build
```

### Activer Django plus tard
Dans docker-compose.yml, décommenter le bloc :
```yaml
# django:
#   build: ...
```

### Connexion MySQL
- host : mysql (dans Docker) / 127.0.0.1 (depuis ta machine)
- user : ibrahima
- password : 8900
- database : gestion_dossiers_victimes
- port : 3307
