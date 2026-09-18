# Système CIMA — Projet Django

Ce projet **remplace progressivement** le prototype Tkinter, en réutilisant
la **même base MySQL** (aucune donnée perdue) et **Keycloak** pour
l'authentification.

## 1. Créer un client Keycloak dédié à Django

Contrairement à `cima-client` (utilisé par Tkinter, en Direct Access Grant),
Django a besoin d'un client **confidentiel** en flux **Authorization Code**.

Dans Keycloak → Realm `cima` → **Clients** → **Create client** :
- Client ID : `cima-django`
- Client authentication : **ON**
- Authentication flow : **Standard flow** uniquement (décoche Direct access grants)
- Valid redirect URIs : `http://localhost:8000/oidc/callback/`
- Web origins : `http://localhost:8000`

Récupère le **Client secret** (onglet Credentials) → mets-le dans `.env`
(`OIDC_RP_CLIENT_SECRET`).

## 2. Copier la configuration

```bash
cp .env.example .env
# puis édite .env avec le client secret récupéré à l'étape 1
```

## 3. Appliquer la migration d'isolation (si pas déjà fait)

```bash
docker exec -i cima_mysql mysql -u ibrahima -p8900 gestion_dossiers_victimes < migration5_isolation.sql
```

## 4. Ajouter le service Django à ton `docker-compose.yml` existant

```yaml
  django:
    build:
      context: ./cima_django
      dockerfile: Dockerfile.django
    container_name: cima_django
    restart: always
    env_file:
      - ./cima_django/.env
    ports:
      - "8000:8000"
    volumes:
      - ./cima_django:/app
    depends_on:
      mysql:
        condition: service_healthy
      keycloak:
        condition: service_started
    networks:
      - cima_network
```

## 5. Lancer

```bash
docker compose up -d --build django
```

Puis ouvre : **http://localhost:8000**

## Vérifier que le cloisonnement fonctionne

Connecte-toi successivement avec chaque type de compte et observe la liste :

| Compte | Ce que tu dois voir |
|---|---|
| `mamoudou.ndao` (victime) | Uniquement son propre dossier |
| `vieux.cisse` (assistant, zone Kaffrine) | Tous les dossiers de la zone Kaffrine |
| `babacar.diop` (assureur) | Uniquement les dossiers où NSIA est engagé |
| `ibrahima.camara` (administrateur) | Tous les dossiers, toutes zones confondues |

Toute la logique de filtrage est dans **`core/permissions.py`** — un seul
fichier à auditer pour vérifier la conformité Code CIMA (confidentialité).

## Prochaines étapes (à développer sur ce même modèle)

- Formulaires de création dossier / documents / demandes (`core/forms.py`)
- Vues Assureur (évaluation, décision, paiement) avec le même filtrage
- Génération PDF des lettres de décision (reportlab, déjà dans requirements.txt)
- Notifications (réutiliser la table `notification` existante)
