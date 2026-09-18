"""
Middleware — Système CIMA

Les attributs cima_role / cima_id_acteur / cima_zone / cima_id_assureur
posés dans core/auth.py au moment du LOGIN ne survivent pas aux requêtes
suivantes (Django recharge un objet User "neuf" depuis la session à chaque
requête). Ce middleware les recalcule donc systématiquement, sur CHAQUE
requête authentifiée, avant que la vue ne s'exécute.
"""

from core.models import Acteur
from django.contrib.auth import logout as django_logout
from django.contrib import messages
from django.shortcuts import redirect


class ProfilCimaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        if user.is_authenticated:
            acteur = (
                Acteur.objects.filter(username=user.username).first()
                or Acteur.objects.filter(email__iexact=user.email).first()
            )
            if acteur:
                if not acteur.actif:
                    django_logout(request)
                    admin = Acteur.objects.filter(role="administrateur", actif=True).first()
                    if admin:
                        contact = f"{admin.prenom} {admin.nom} — {admin.email} / {admin.telephone}"
                    else:
                        contact = "l'administration du système"
                    messages.error(
                        request,
                        f"🔒 Votre compte a été désactivé. Contactez {contact} pour le réactiver."
                    )
                    return redirect("accueil")

                if not acteur.username:
                    acteur.username = user.username
                    acteur.save(update_fields=["username"])

                user.cima_role = acteur.role
                user.cima_id_acteur = acteur.id_acteur
                user.cima_zone = (
                    acteur.profil_assistant.zone_intervention
                    if acteur.role == "assistant" and hasattr(acteur, "profil_assistant")
                    else None
                )
                user.cima_id_assureur = acteur.id_acteur if acteur.role == "assureur" else None
            else:
                user.cima_role = None
                user.cima_id_acteur = None
                user.cima_zone = None
                user.cima_id_assureur = None

        return self.get_response(request)
