"""
Client API Admin Keycloak — Système CIMA
Permet de créer un utilisateur Keycloak directement depuis Django,
sans jamais quitter l'application (inscription 100% native).
Réutilise le client de service "cima-service" déjà configuré pour Tkinter.
"""
import json
import urllib.request
import urllib.parse
from django.conf import settings


def _obtenir_token_admin():
    url = f"{settings.KEYCLOAK_URL_INTERNAL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
    data = urllib.parse.urlencode({
        "client_id": settings.KC_ADMIN_CLIENT_ID,
        "client_secret": settings.KC_ADMIN_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["access_token"]


def creer_utilisateur_keycloak(username, email, password, prenom, nom):
    """Retourne (succes: bool, message: str)."""
    try:
        token = _obtenir_token_admin()
    except Exception as e:
        return False, f"Keycloak injoignable : {e}"

    try:
        url = f"{settings.KEYCLOAK_URL_INTERNAL}/admin/realms/{settings.KEYCLOAK_REALM}/users"
        payload = json.dumps({
            "username": username, "email": email,
            "firstName": prenom, "lastName": nom,
            "enabled": True, "emailVerified": False,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            location = resp.headers.get("Location", "")
        id_utilisateur = location.rstrip("/").split("/")[-1] if location else None

        if id_utilisateur:
            try:
                url_verif = f"{settings.KEYCLOAK_URL_INTERNAL}/admin/realms/{settings.KEYCLOAK_REALM}/users/{id_utilisateur}/send-verify-email"
                req2 = urllib.request.Request(url_verif, data=b"", method="PUT")
                req2.add_header("Authorization", f"Bearer {token}")
                urllib.request.urlopen(req2, timeout=10)
            except Exception:
                pass

        return True, id_utilisateur
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("errorMessage", "Erreur inconnue.")
        except Exception:
            msg = "Erreur inconnue."
        if e.code == 409:
            return False, "Ce nom d'utilisateur ou cet email est déjà utilisé."
        return False, msg
    except Exception as e:
        return False, f"Erreur de connexion à Keycloak : {e}"
