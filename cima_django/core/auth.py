"""
Backend d'authentification Keycloak — Système CIMA

Rôle de ce module :
1. Vérifie l'identité via Keycloak (délégué à mozilla-django-oidc)
2. Rattache le compte Keycloak à son profil métier dans la table `acteur`
3. Expose sur l'utilisateur Django connecté (`request.user`) les attributs
   nécessaires au cloisonnement des données :
      - request.user.cima_role        → 'victime' | 'assistant' | 'assureur' | 'administrateur'
      - request.user.cima_id_acteur   → id_acteur (clé métier)
      - request.user.cima_zone        → zone d'intervention (si assistant)
"""

from django.contrib.auth.models import User
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from core.models import Acteur


class CimaKeycloakBackend(OIDCAuthenticationBackend):

    def create_user(self, claims):
        user = super().create_user(claims)
        self._attacher_profil_metier(user, claims)
        return user

    def update_user(self, user, claims):
        user = super().update_user(user, claims)
        self._attacher_profil_metier(user, claims)
        return user

    def _attacher_profil_metier(self, user, claims):
        """Fait le lien Keycloak ↔ table `acteur` et attache le périmètre d'accès."""
        username = claims.get("preferred_username", "")
        email = claims.get("email", "")

        acteur = (
            Acteur.objects.filter(username=username).first()
            or Acteur.objects.filter(email__iexact=email).first()
        )

        if acteur is None:
            # Compte Keycloak valide mais sans profil métier créé —
            # redirigé vers la vue de complétion de profil (voir core/views.py)
            user.cima_role = None
            user.cima_id_acteur = None
            user.cima_zone = None
            user.cima_id_assureur = None
            return user

        # Auto-réparation : si le compte existait avant l'ajout de la colonne username
        if not acteur.username:
            acteur.username = username
            acteur.save(update_fields=["username"])

        user.cima_role = acteur.role
        user.cima_id_acteur = acteur.id_acteur
        user.cima_zone = (
            acteur.profil_assistant.zone_intervention
            if acteur.role == "assistant" and hasattr(acteur, "profil_assistant")
            else None
        )
        user.cima_id_assureur = acteur.id_acteur if acteur.role == "assureur" else None
        return user
