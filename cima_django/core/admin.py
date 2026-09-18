from django.contrib import admin
from core.models import (
    Acteur, Victime, Assistant, Assureur, Accident, Dossier,
    Document, DemandeIndemnisation, Evaluation, Decision, Paiement, Notification,
)

admin.site.register(Acteur)
admin.site.register(Victime)
admin.site.register(Assistant)
admin.site.register(Assureur)
admin.site.register(Accident)
admin.site.register(Dossier)
admin.site.register(Document)
admin.site.register(DemandeIndemnisation)
admin.site.register(Evaluation)
admin.site.register(Decision)
admin.site.register(Paiement)
admin.site.register(Notification)
