"""
Cloisonnement des données — Système CIMA

Une seule fonction, `dossiers_visibles_par(user)`, centralise TOUTE la règle
métier de confidentialité. Chaque vue qui liste ou consulte des dossiers
doit passer par cette fonction — jamais par `Dossier.objects.all()` directement.

Politique appliquée :
- Victime        → uniquement ses propres dossiers
- Assistant      → tous les dossiers de SA zone (pas seulement les siens)
- Assureur       → uniquement les dossiers où il est/était engagé
- Administrateur → tout, sans filtre (supervision, statistiques, litiges)
"""

from functools import wraps
from django.http import HttpResponseForbidden
from core.models import Dossier


def role_requis(*roles_autorises):
    """Décorateur de vue : bloque l'accès si request.user.cima_role n'est pas dans la liste."""
    def decorateur(vue):
        @wraps(vue)
        def wrapper(request, *args, **kwargs):
            if getattr(request.user, "cima_role", None) not in roles_autorises:
                return HttpResponseForbidden("⛔ Accès réservé à : " + ", ".join(roles_autorises))
            return vue(request, *args, **kwargs)
        return wrapper
    return decorateur


def dossiers_visibles_par(user):
    """Retourne le QuerySet des dossiers que cet utilisateur a le droit de voir."""
    role = getattr(user, "cima_role", None)

    if role == "administrateur":
        return Dossier.objects.all()

    if role == "victime":
        return Dossier.objects.filter(victime_id=user.cima_id_acteur)

    if role == "assistant":
        if not user.cima_zone:
            return Dossier.objects.none()  # pas de zone renseignée → aucun accès par prudence
        return Dossier.objects.filter(zone=user.cima_zone)

    if role == "assureur":
        return Dossier.objects.filter(
            demandes__assureur_id=user.cima_id_assureur
        ).distinct()

    return Dossier.objects.none()  # rôle inconnu ou profil non provisionné


def peut_voir_dossier(user, dossier):
    """Vérifie l'accès à UN dossier précis (utilisé dans les vues détail)."""
    return dossiers_visibles_par(user).filter(pk=dossier.pk).exists()
