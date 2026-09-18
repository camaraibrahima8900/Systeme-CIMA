def notifications_context(request):
    """Injecte le compteur de notifications non lues + les 5 plus récentes
    sur CHAQUE page (utilisé par la cloche dans l'en-tête)."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    id_acteur = getattr(request.user, "cima_id_acteur", None)
    if not id_acteur:
        return {}
    from core.models import Notification
    qs = Notification.objects.filter(acteur_id=id_acteur).order_by("-id_notification")
    return {
        "notif_non_lues_count": qs.exclude(statut_envoi="LUE").count(),
        "notif_recentes": qs.select_related("dossier")[:5],
    }
