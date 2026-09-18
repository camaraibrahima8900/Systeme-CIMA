from django.urls import path
from core import views

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("inscription/", views.inscription, name="inscription"),
    path("deconnexion/", views.deconnexion, name="deconnexion"),
    path("completer-profil/", views.completer_profil, name="completer_profil"),
    path("notifications/", views.mes_notifications, name="mes_notifications"),
    path("notifications/dossier/<int:pk>/", views.voir_dossier_notification, name="voir_dossier_notification"),

    # Victime
    path("victime/", views.tableau_victime, name="tableau_victime"),
    path("victime/paiement/<int:pk>/confirmer/", views.confirmer_paiement, name="confirmer_paiement"),
    path("victime/paiement/<int:pk>/contester/", views.contester_paiement, name="contester_paiement"),
    path("victime/dossier/<int:pk>/contester-rejet/", views.contester_rejet, name="contester_rejet"),
    path("victime/contacts/assistants/", views.contacts_assistants, name="contacts_assistants_victime"),

    # Assistant
    path("assistant/", views.tableau_assistant, name="tableau_assistant"),
    path("assistant/accident/nouveau/", views.creer_accident, name="creer_accident"),
    path("assistant/dossier/nouveau/", views.creer_dossier, name="creer_dossier"),
    path("assistant/dossier/<int:pk>/", views.detail_dossier, name="detail_dossier"),
    path("assistant/dossier/<int:pk>/statut/", views.modifier_statut, name="modifier_statut"),
    path("assistant/dossier/<int:pk>/cloturer/", views.cloturer_dossier, name="cloturer_dossier"),
    path("assistant/dossier/<int:pk>/document/", views.ajouter_document, name="ajouter_document"),
    path("assistant/document/<int:pk>/supprimer/", views.supprimer_document, name="supprimer_document"),
    path("assistant/dossier/<int:pk>/demande/", views.soumettre_demande, name="soumettre_demande"),
    path("assistant/paiement/<int:pk>/transmettre/", views.transmettre_contestation, name="transmettre_contestation"),
    path("assistant/dossier/<int:pk>/recours/", views.creer_recours, name="creer_recours"),
    path("assistant/contacts/assureurs/", views.contacts_assureurs, name="contacts_assureurs"),
    path("assistant/contacts/victimes/", views.contacts_victimes, name="contacts_victimes"),

    # Assureur
    path("assureur/", views.tableau_assureur, name="tableau_assureur"),
    path("assureur/contacts/assistants/", views.contacts_assistants, name="contacts_assistants_assureur"),
    path("assureur/demande/<int:pk>/", views.detail_demande, name="detail_demande"),
    path("assureur/dossier/<int:pk>/document/", views.ajouter_document_assureur, name="ajouter_document_assureur"),
    path("assureur/document/<int:pk>/valider/", views.valider_document, {"decision": "VALIDE"}, name="valider_document"),
    path("assureur/document/<int:pk>/rejeter/", views.valider_document, {"decision": "REJETE"}, name="rejeter_document"),
    path("assureur/demande/<int:pk>/evaluation/", views.enregistrer_evaluation, name="enregistrer_evaluation"),
    path("assureur/demande/<int:pk>/decision/", views.enregistrer_decision, name="enregistrer_decision"),
    path("assureur/demande/<int:pk>/reexaminer/", views.reexaminer_demande, name="reexaminer_demande"),
    path("assureur/dossier/<int:pk>/provision/", views.verser_provision, name="verser_provision"),
    path("assureur/decision/<int:pk>/paiement/", views.enregistrer_paiement_definitif, name="enregistrer_paiement_definitif"),
    path("victime/demande/<int:pk>/accepter-offre/", views.accepter_offre, name="accepter_offre"),
    path("victime/demande/<int:pk>/refuser-offre/", views.refuser_offre, name="refuser_offre"),

    # Administrateur
    path("admin-cima/", views.tableau_admin, name="tableau_admin"),
    path("admin-cima/acteur/nouveau/", views.ajouter_acteur, name="ajouter_acteur"),
    path("admin-cima/acteur/<int:pk>/modifier/", views.modifier_acteur, name="modifier_acteur"),
    path("admin-cima/acteur/<int:pk>/basculer-actif/", views.basculer_actif_acteur, name="basculer_actif_acteur"),
    path("admin-cima/<str:modele>/<int:pk>/supprimer/", views.supprimer_objet, name="supprimer_objet"),
    path("admin-cima/dossier/<int:pk>/forcer-suppression/", views.forcer_suppression_dossier, name="forcer_suppression_dossier"),
]
