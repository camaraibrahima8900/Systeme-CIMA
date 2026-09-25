from django.conf import settings
from django.contrib.auth import logout as django_logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
import urllib.parse

from core.models import (
    Acteur, Accident, Dossier, Document, DemandeIndemnisation,
    Evaluation, Decision, Paiement, Assistant, Assureur, Victime, Notification,
)
from django.db import models
from core.permissions import dossiers_visibles_par, peut_voir_dossier, role_requis
from core.forms import (
    AccidentForm, DossierForm, StatutDossierForm, DocumentForm, DocumentAssureurForm,
    DemandeIndemnisationForm, EvaluationForm, DecisionForm,
    PaiementDefinitifForm, ProvisionForm, ContestationForm, RecoursForm,
    AjouterActeurForm, RefusOffreForm,
)


PIECES_CLASSIQUES = [
    "CNI", "PASSEPORT", "PV_POLICE", "CERTIFICAT_MEDICAL", "FACTURE_MEDICALE",
    "PHOTO_ACCIDENT", "ATTESTATION_ASSURANCE", "RIB", "AUTRE",
]


def notifier(acteur, dossier, message):
    """Crée une notification en base ET envoie un vrai email HTML professionnel à l'acteur concerné."""
    if acteur is None or not acteur.email:
        return
    Notification.objects.create(acteur=acteur, dossier=dossier, message=message)
    try:
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        from django.conf import settings

        contexte = {
            "prenom": acteur.prenom, "message": message,
            "numero_dossier": dossier.numero_dossier,
            "lien": f"{settings.SITE_URL_PUBLIC}/notifications/dossier/{dossier.pk}/",
        }
        html = render_to_string("core/email_notification.html", contexte)
        texte = (
            f"Bonjour {acteur.prenom},\n\n{message}\n\n"
            f"Dossier concerné : {dossier.numero_dossier}\n"
            f"Connectez-vous sur le Système CIMA pour plus de détails : {contexte['lien']}\n\n"
            f"— Système CIMA (notification automatique)"
        )
        email = EmailMultiAlternatives(
            subject=f"[Système CIMA] Dossier {dossier.numero_dossier}",
            body=texte,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[acteur.email],
        )
        email.attach_alternative(html, "text/html")
        email.send(fail_silently=True)
    except Exception as e:
        print(f"[EMAIL] Échec d'envoi à {acteur.email} : {e}")


# ============================================================
# CONNEXION / DÉCONNEXION
# ============================================================
def deconnexion(request):
    """Déconnecte de Django ET termine la session SSO Keycloak."""
    id_token = request.session.get("oidc_id_token")
    django_logout(request)

    params = {"post_logout_redirect_uri": request.build_absolute_uri("/")}
    if id_token:
        params["id_token_hint"] = id_token
    else:
        params["client_id"] = settings.OIDC_RP_CLIENT_ID

    url_logout_keycloak = (
        f"{settings.KEYCLOAK_URL_PUBLIC}/realms/{settings.KEYCLOAK_REALM}"
        f"/protocol/openid-connect/logout?{urllib.parse.urlencode(params)}"
    )
    return redirect(url_logout_keycloak)


def _est_provisionne(request):
    return getattr(request.user, "cima_role", None) is not None


def accueil(request):
    """Page publique si non connecté, sinon redirige vers le bon tableau de bord."""
    if not request.user.is_authenticated:
        admin = Acteur.objects.filter(role="administrateur", actif=True).first()
        return render(request, "core/accueil_public.html", {"admin_contact": admin})
    if not _est_provisionne(request):
        return redirect("completer_profil")
    role = request.user.cima_role
    return redirect({
        "victime": "tableau_victime",
        "assistant": "tableau_assistant",
        "assureur": "tableau_assureur",
        "administrateur": "tableau_admin",
    }.get(role, "tableau_victime"))


@login_required
def mes_notifications(request):
    """Page dédiée : toutes les notifications de l'acteur, groupées par dossier.
    Marque automatiquement comme lues à la consultation."""
    id_acteur = getattr(request.user, "cima_id_acteur", None)
    qs = Notification.objects.filter(acteur_id=id_acteur).select_related("dossier").order_by(
        "dossier__numero_dossier", "-id_notification"
    )
    dossiers_notifs = {}
    for n in qs:
        dossiers_notifs.setdefault(n.dossier, []).append(n)
    # trie les groupes par notification la plus récente en premier
    groupes = sorted(dossiers_notifs.items(), key=lambda item: item[1][0].id_notification, reverse=True)

    Notification.objects.filter(acteur_id=id_acteur).exclude(statut_envoi="LUE").update(statut_envoi="LUE")
    return render(request, "core/mes_notifications.html", {"groupes": groupes})


@login_required
def voir_dossier_notification(request, pk):
    """Redirige vers la bonne page de détail selon le rôle de l'acteur connecté."""
    dossier = get_object_or_404(Dossier, pk=pk)
    role = getattr(request.user, "cima_role", None)
    if role in ("assistant", "victime"):
        return redirect("detail_dossier", pk=dossier.pk)
    if role == "assureur":
        demande = dossier.demandes.filter(assureur_id=request.user.cima_id_assureur).order_by("-id_demande").first()
        if demande:
            return redirect("detail_demande", pk=demande.pk)
        messages.info(request, "Aucune demande de votre compagnie sur ce dossier.")
        return redirect("tableau_assureur")
    return redirect("accueil")


@login_required
def completer_profil(request):
    """1ère connexion : le compte Keycloak n'a pas encore de profil `acteur`."""
    if _est_provisionne(request):
        return redirect("accueil")

    if request.method == "POST":
        form = AjouterActeurForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            acteur = Acteur.objects.create(
                nom=d["nom"], prenom=d["prenom"], email=d["email"],
                username=request.user.username, telephone=d["telephone"],
                mot_de_passe="keycloak_managed", role=d["role"],
            )
            if d["role"] == "victime":
                Victime.objects.create(acteur=acteur)
            elif d["role"] == "assistant":
                Assistant.objects.create(acteur=acteur, zone_intervention=d["zone_intervention"])
            elif d["role"] == "assureur":
                Assureur.objects.create(acteur=acteur, nom_compagnie=d["nom_compagnie"])
            messages.success(request, f"Bienvenue {d['prenom']} {d['nom']} ! Votre profil a été créé.")
            return redirect("accueil")
    else:
        form = AjouterActeurForm(initial={
            "email": request.user.email,
            "prenom": request.user.first_name,
            "nom": request.user.last_name,
        })
    return render(request, "core/completer_profil.html", {"form": form})


# ============================================================
# ESPACE VICTIME
# ============================================================
@login_required
@role_requis("victime", "administrateur")
def tableau_victime(request):
    dossiers = dossiers_visibles_par(request.user).select_related("assistant", "accident")

    paiements = (
        Paiement.objects.filter(decision__demande__dossier__victime_id=request.user.cima_id_acteur)
        | Paiement.objects.filter(dossier__victime_id=request.user.cima_id_acteur, type_paiement="PROVISION")
    ).distinct().select_related("dossier", "decision__demande__dossier").order_by("-id_paiement")

    paiements_par_dossier = {}
    for p in paiements:
        d = p.dossier or p.decision.demande.dossier
        paiements_par_dossier.setdefault(d, []).append(p)
    groupes_paiements = sorted(paiements_par_dossier.items(), key=lambda kv: kv[0].pk, reverse=True)

    acteur = Acteur.objects.filter(pk=request.user.cima_id_acteur).first()
    notifications = acteur.notifications.order_by("-id_notification")[:20] if acteur else []

    paginator = Paginator(dossiers, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "core/tableau_victime.html", {
        "dossiers": dossiers, "groupes_paiements": groupes_paiements, "notifications": notifications,
        "page_obj": page_obj, "param_name": "page", "extra_qs": "",
    })


@login_required
@role_requis("victime", "administrateur")
def confirmer_paiement(request, pk):
    paiement = get_object_or_404(Paiement, pk=pk)
    if paiement.statut_confirmation == "CONFIRME":
        messages.info(request, "Ce paiement a déjà été confirmé.")
    else:
        from django.utils import timezone
        paiement.confirmation_victime = True
        paiement.statut_confirmation = "CONFIRME"
        paiement.date_confirmation = timezone.now()
        paiement.save()
        dossier = paiement.dossier or (paiement.decision.demande.dossier if paiement.decision else None)
        if dossier:
            if dossier.assistant:
                notifier(dossier.assistant, dossier,
                         f"La victime a confirmé le paiement du dossier {dossier.numero_dossier}.")
            if paiement.decision:
                from core.pdf_utils import generer_quittance
                generer_quittance(paiement)
        messages.success(request, "✅ Confirmation enregistrée. L'assistant a été notifié et la quittance générée.")
    return redirect("tableau_victime")


@login_required
@role_requis("victime", "administrateur")
def contester_paiement(request, pk):
    paiement = get_object_or_404(Paiement, pk=pk)
    if request.method == "POST":
        form = ContestationForm(request.POST)
        if form.is_valid():
            paiement.statut_confirmation = "CONTESTE"
            paiement.commentaire_victime = form.cleaned_data["motif"]
            paiement.save()
            dossier = paiement.dossier or (paiement.decision.demande.dossier if paiement.decision else None)
            if dossier and dossier.assistant:
                notifier(dossier.assistant, dossier,
                         f"Le paiement du dossier {dossier.numero_dossier} a été contesté par la victime : "
                         f"« {form.cleaned_data['motif']} »")
            messages.warning(request, "Votre contestation a été enregistrée et transmise à l'assistant.")
            return redirect("tableau_victime")
    else:
        form = ContestationForm()
    return render(request, "core/formulaire_simple.html", {
        "form": form, "titre": f"❌ Contester le paiement #{paiement.pk}",
    })


@login_required
@role_requis("victime", "administrateur")
def contester_rejet(request, pk):
    dossier = get_object_or_404(Dossier, pk=pk)
    if not peut_voir_dossier(request.user, dossier):
        return HttpResponseForbidden("⛔ Accès refusé.")
    if dossier.statut != "REJETE":
        messages.info(request, "Ce dossier n'est pas au statut REJETÉ.")
        return redirect("tableau_victime")
    if request.method == "POST":
        form = ContestationForm(request.POST)
        if form.is_valid():
            if dossier.assistant:
                notifier(dossier.assistant, dossier,
                         f"La victime conteste le rejet du dossier {dossier.numero_dossier} : "
                         f"« {form.cleaned_data['motif']} ». Un recours peut être déposé.")
            messages.warning(request, "Votre contestation a été transmise à votre assistant pour recours.")
            return redirect("tableau_victime")
    else:
        form = ContestationForm()
    return render(request, "core/formulaire_simple.html", {
        "form": form, "titre": f"❌ Contester le rejet — {dossier.numero_dossier}",
    })


# ============================================================
# ESPACE ASSISTANT
# ============================================================
@login_required
@role_requis("assistant", "administrateur")
def tableau_assistant(request):
    q = request.GET.get("q", "").strip()
    base_qs = dossiers_visibles_par(request.user).select_related("victime", "accident")
    if q:
        base_qs = base_qs.filter(
            models.Q(numero_dossier__icontains=q)
            | models.Q(victime__nom__icontains=q)
            | models.Q(victime__prenom__icontains=q)
        )
    dossiers = base_qs.exclude(statut="CLOTURE")
    dossiers_archives = base_qs.filter(statut="CLOTURE").order_by("-date_cloture")

    paginator = Paginator(dossiers, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    extra_qs = f"&q={q}" if q else ""

    accidents = Accident.objects.filter(
        dossiers__in=dossiers_visibles_par(request.user)
    ).exclude(dossiers__statut="CLOTURE").distinct().order_by("-id_accident")[:20]
    demandes = DemandeIndemnisation.objects.filter(
        dossier__in=dossiers_visibles_par(request.user)
    ).exclude(dossier__statut="CLOTURE").select_related("dossier", "assureur").order_by("-id_demande")
    contestations_brutes = Paiement.objects.filter(
        statut_confirmation__in=["CONTESTE", "TRANSMIS_ASSUREUR"]
    ).select_related("dossier", "decision__demande__dossier")
    contestations = [
        p for p in contestations_brutes
        if not (
            (p.dossier and p.dossier.statut == "CLOTURE")
            or (p.decision and p.decision.demande.dossier.statut == "CLOTURE")
        )
    ]
    dossiers_rejetes = dossiers_visibles_par(request.user).filter(statut="REJETE")
    acteur = Acteur.objects.filter(pk=request.user.cima_id_acteur).first()
    notifications = acteur.notifications.order_by("-id_notification")[:20] if acteur else []

    return render(request, "core/tableau_assistant.html", {
        "dossiers": dossiers, "dossiers_archives": dossiers_archives, "q": q,
        "page_obj": page_obj, "param_name": "page", "extra_qs": extra_qs,
        "accidents": accidents, "demandes": demandes,
        "contestations": contestations, "dossiers_rejetes": dossiers_rejetes,
        "notifications": notifications,
        "victimes": Acteur.objects.filter(role="victime"),
        "assureurs": Acteur.objects.filter(role="assureur"),
    })


@login_required
@role_requis("assistant", "administrateur")
def creer_accident(request):
    if request.method == "POST":
        form = AccidentForm(request.POST)
        if form.is_valid():
            accident = form.save()
            messages.success(request, f"Accident enregistré (ID {accident.pk}).")
            return redirect("tableau_assistant")
    else:
        form = AccidentForm()
    return render(request, "core/formulaire_simple.html", {"form": form, "titre": "🚗 Enregistrer un accident"})


@login_required
@role_requis("assistant", "administrateur")
def creer_dossier(request):
    if request.method == "POST":
        form = DossierForm(request.POST)
        if form.is_valid():
            dossier = form.save(commit=False)
            assistant_acteur = Acteur.objects.get(pk=request.user.cima_id_acteur)
            dossier.assistant = assistant_acteur
            dossier.zone = getattr(request.user, "cima_zone", None)
            dossier.statut = "EN_CONSTITUTION"
            dossier.save()
            notifier(dossier.victime, dossier,
                     f"Un dossier {dossier.numero_dossier} a été créé pour vous suite à votre accident.")
            messages.success(request, f"Dossier '{dossier.numero_dossier}' créé et notifié à la victime.")
            return redirect("detail_dossier", pk=dossier.pk)
    else:
        form = DossierForm()
    return render(request, "core/formulaire_simple.html", {"form": form, "titre": "➕ Créer un dossier"})


@login_required
@role_requis("assistant", "administrateur")
def modifier_statut(request, pk):
    dossier = get_object_or_404(Dossier, pk=pk)
    if not peut_voir_dossier(request.user, dossier):
        return HttpResponseForbidden("⛔ Ce dossier n'est pas dans votre zone.")
    if dossier.statut == "CLOTURE":
        messages.error(request, "Ce dossier est clôturé et archivé : statut verrouillé.")
        return redirect("detail_dossier", pk=dossier.pk)
    if request.method == "POST":
        form = StatutDossierForm(request.POST)
        if form.is_valid():
            dossier.statut = form.cleaned_data["statut"]
            dossier.save()
            messages.success(request, f"Statut du dossier '{dossier.numero_dossier}' mis à jour.")
            return redirect("tableau_assistant")
    else:
        form = StatutDossierForm(initial={"statut": dossier.statut})
    return render(request, "core/formulaire_simple.html", {
        "form": form, "titre": f"🔄 Statut — {dossier.numero_dossier}",
    })


@login_required
@role_requis("assistant", "administrateur")
def cloturer_dossier(request, pk):
    dossier = get_object_or_404(Dossier, pk=pk)
    if not peut_voir_dossier(request.user, dossier):
        return HttpResponseForbidden("⛔ Accès refusé.")
    if dossier.statut != "PAYE":
        messages.error(request, "Seul un dossier payé peut être clôturé.")
        return redirect("detail_dossier", pk=dossier.pk)
    dossier.statut = "CLOTURE"
    from django.utils import timezone
    dossier.date_cloture = timezone.now()
    dossier.save()
    messages.success(request, f"Dossier '{dossier.numero_dossier}' clôturé (archivage 10 ans — Code CIMA).")
    return redirect("tableau_assistant")


@login_required
@role_requis("assistant", "administrateur")
def ajouter_document(request, pk):
    dossier = get_object_or_404(Dossier, pk=pk)
    if not peut_voir_dossier(request.user, dossier):
        return HttpResponseForbidden("⛔ Accès refusé.")
    if dossier.statut == "CLOTURE":
        messages.error(request, "Ce dossier est clôturé et archivé : plus aucune modification possible.")
        return redirect("detail_dossier", pk=dossier.pk)

    if request.method == "POST":
        form = DocumentForm(request.POST, request.FILES, role="assistant")
        if form.is_valid():
            type_doc = form.cleaned_data["type_document"]

            if type_doc in PIECES_CLASSIQUES and dossier.statut not in ("EN_CONSTITUTION", "DOSSIER_COMPLET"):
                messages.error(
                    request,
                    "Ce dossier a déjà été soumis à l'assureur : les pièces justificatives classiques "
                    "ne peuvent plus être ajoutées (sauf en cas de recours après rejet)."
                    if dossier.statut != "REJETE" else
                    "Impossible d'ajouter cette pièce ici : sur un dossier rejeté, utilisez le circuit de recours."
                )
                return redirect("detail_dossier", pk=dossier.pk)

            if type_doc == "DEMANDE_PROVISION" and dossier.statut == "PAYE":
                messages.error(
                    request, "Le dossier a déjà été payé : plus aucune demande de provision n'est possible."
                )
                return redirect("detail_dossier", pk=dossier.pk)

            if type_doc == "RAPPORT_CONTRE_EXPERTISE":
                if not dossier.documents.filter(type_document="RAPPORT_EXPERTISE_INITIALE").exists():
                    messages.error(
                        request,
                        "Vous ne pouvez transmettre un rapport de contre-expertise qu'après réception "
                        "du rapport d'expertise initiale de l'assureur."
                    )
                    return redirect("detail_dossier", pk=dossier.pk)

            doc = form.save(commit=False)
            doc.dossier = dossier
            doc.ajoute_par = Acteur.objects.filter(pk=request.user.cima_id_acteur).first()
            doc.save()

            for demande in dossier.demandes.all():
                notifier(demande.assureur, dossier,
                         f"Un nouveau document ({doc.get_type_document_display()}) a été ajouté "
                         f"au dossier {dossier.numero_dossier} par l'assistant.")

            messages.success(request, "Document ajouté avec succès.")
            return redirect("detail_dossier", pk=dossier.pk)
    else:
        form = DocumentForm(role="assistant")
    return render(request, "core/formulaire_simple.html", {
        "form": form, "titre": f"📄 Ajouter document — {dossier.numero_dossier}",
    })


@login_required
@role_requis("assistant", "victime", "administrateur")
def detail_dossier(request, pk):
    dossier = get_object_or_404(Dossier, pk=pk)
    if not peut_voir_dossier(request.user, dossier):
        return HttpResponseForbidden("⛔ Accès refusé.")

    date_archivage = None
    if dossier.date_cloture:
        import datetime as _dt
        date_archivage = dossier.date_cloture + _dt.timedelta(days=365 * 10)

    id_acteur = getattr(request.user, "cima_id_acteur", None)
    notifications_dossier = dossier.notifications.filter(acteur_id=id_acteur).order_by("-id_notification")

    return render(request, "core/detail_dossier.html", {
        "dossier": dossier,
        "documents": dossier.documents.order_by("-date_upload"),
        "demandes": dossier.demandes.order_by("-id_demande"),
        "date_archivage": date_archivage,
        "notifications_dossier": notifications_dossier,
    })


@login_required
@role_requis("assistant", "administrateur")
def supprimer_document(request, pk):
    document = get_object_or_404(Document, pk=pk)
    dossier = document.dossier
    if not peut_voir_dossier(request.user, dossier):
        return HttpResponseForbidden("⛔ Accès refusé.")
    if dossier.statut not in ("EN_CONSTITUTION", "DOSSIER_COMPLET"):
        messages.error(request, "Impossible de retirer un document : le dossier a déjà été soumis ou traité.")
        return redirect("detail_dossier", pk=dossier.pk)
    document.delete()
    messages.success(request, "Document retiré du dossier.")
    return redirect("detail_dossier", pk=dossier.pk)


@login_required
@role_requis("assistant", "administrateur")
def soumettre_demande(request, pk):
    dossier = get_object_or_404(Dossier, pk=pk)
    if not peut_voir_dossier(request.user, dossier):
        return HttpResponseForbidden("⛔ Accès refusé.")
    if request.method == "POST":
        form = DemandeIndemnisationForm(request.POST)
        if form.is_valid():
            demande = form.save(commit=False)
            demande.dossier = dossier
            demande.type_demande = "INITIALE"
            demande.montant_reclame = demande.montant_reclame or 0
            import datetime
            base = f"DEM-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{dossier.pk:03d}"
            numero = base
            compteur = 1
            while DemandeIndemnisation.objects.filter(numero_suivi=numero).exists():
                compteur += 1
                numero = f"{base}-{compteur}"
            demande.numero_suivi = numero
            demande.save()
            dossier.statut = "SOUMIS"
            dossier.save()
            messages.success(request, f"Demande '{demande.numero_suivi}' soumise à l'assureur.")
            return redirect("tableau_assistant")
    else:
        form = DemandeIndemnisationForm()
    return render(request, "core/formulaire_simple.html", {
        "form": form, "titre": f"💼 Soumettre demande — {dossier.numero_dossier}",
    })


@login_required
@role_requis("assistant", "administrateur")
def transmettre_contestation(request, pk):
    paiement = get_object_or_404(Paiement, pk=pk)
    if paiement.statut_confirmation != "CONTESTE":
        messages.info(request, "Cette contestation a déjà été transmise ou n'existe pas.")
        return redirect("tableau_assistant")
    paiement.statut_confirmation = "TRANSMIS_ASSUREUR"
    paiement.save()
    dossier = paiement.dossier or (paiement.decision.demande.dossier if paiement.decision else None)
    if paiement.decision:
        notifier(paiement.decision.demande.assureur, dossier,
                 f"Contestation de paiement transmise sur le dossier {dossier.numero_dossier} : "
                 f"« {paiement.commentaire_victime} »")
    messages.success(request, "Contestation transmise à l'assureur pour réexamen.")
    return redirect("tableau_assistant")


@login_required
@role_requis("assistant", "administrateur")
def creer_recours(request, pk):
    dossier = get_object_or_404(Dossier, pk=pk)
    if not peut_voir_dossier(request.user, dossier):
        return HttpResponseForbidden("⛔ Accès refusé.")
    if dossier.statut != "REJETE":
        messages.info(request, "Le recours n'est possible que sur un dossier REJETÉ.")
        return redirect("tableau_assistant")

    if request.method == "POST":
        form = RecoursForm(request.POST)
        if form.is_valid():
            demande_origine = dossier.demandes.filter(type_demande="INITIALE").order_by("-id_demande").first()
            if not demande_origine:
                messages.error(request, "Aucune demande d'origine trouvée.")
                return redirect("tableau_assistant")
            import datetime
            base = f"REC-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{dossier.pk:03d}"
            numero_suivi = base
            compteur = 1
            while DemandeIndemnisation.objects.filter(numero_suivi=numero_suivi).exists():
                compteur += 1
                numero_suivi = f"{base}-{compteur}"
            montant = form.cleaned_data["nouveau_montant"] or demande_origine.montant_reclame
            DemandeIndemnisation.objects.create(
                dossier=dossier, assureur=demande_origine.assureur, numero_suivi=numero_suivi,
                montant_reclame=montant, statut="SOUMISE", type_demande="RECOURS",
                demande_origine=demande_origine, motif_recours=form.cleaned_data["motif"],
            )
            dossier.statut = "EN_EVALUATION"
            dossier.save()
            notifier(demande_origine.assureur, dossier,
                     f"Un recours ({numero_suivi}) a été déposé sur le dossier {dossier.numero_dossier} "
                     f"— motif : « {form.cleaned_data['motif']} »")
            messages.success(request, f"Recours '{numero_suivi}' créé et transmis à l'assureur.")
            return redirect("tableau_assistant")
    else:
        form = RecoursForm()
    return render(request, "core/formulaire_simple.html", {
        "form": form, "titre": f"🔄 Créer un recours — {dossier.numero_dossier}",
    })


# ============================================================
# ESPACE ASSUREUR
# ============================================================
@login_required
@role_requis("assureur", "administrateur")
def tableau_assureur(request):
    q = request.GET.get("q", "").strip()
    demandes = DemandeIndemnisation.objects.filter(
        assureur_id=request.user.cima_id_assureur
    ).select_related("dossier", "dossier__victime").order_by("-id_demande")
    if q:
        demandes = demandes.filter(
            models.Q(dossier__numero_dossier__icontains=q)
            | models.Q(dossier__victime__nom__icontains=q)
            | models.Q(dossier__victime__prenom__icontains=q)
            | models.Q(numero_suivi__icontains=q)
        )

    demandes_par_dossier = {}
    for d in demandes:
        demandes_par_dossier.setdefault(d.dossier, []).append(d)
    groupes_demandes = sorted(demandes_par_dossier.items(), key=lambda kv: kv[0].pk, reverse=True)

    decisions_brutes = Decision.objects.filter(
        demande__assureur_id=request.user.cima_id_assureur
    ).select_related("demande__dossier").order_by("-id_decision")
    decisions = [dec for dec in decisions_brutes if dec.demande.dossier.statut != "CLOTURE"]

    contestations_brutes = Paiement.objects.filter(
        statut_confirmation="TRANSMIS_ASSUREUR",
        decision__demande__assureur_id=request.user.cima_id_assureur,
    ).select_related("decision__demande__dossier")
    contestations = [c for c in contestations_brutes if c.decision.demande.dossier.statut != "CLOTURE"]

    acteur = Acteur.objects.filter(pk=request.user.cima_id_acteur).first()
    notifications = acteur.notifications.order_by("-id_notification")[:20] if acteur else []

    paginator = Paginator(groupes_demandes, 8)
    page_obj = paginator.get_page(request.GET.get("page"))
    extra_qs = f"&q={q}" if q else ""

    return render(request, "core/tableau_assureur.html", {
        "demandes": demandes, "decisions": decisions, "q": q,
        "page_obj": page_obj, "param_name": "page", "extra_qs": extra_qs,
        "contestations": contestations, "notifications": notifications,
        "assistants": Acteur.objects.filter(role="assistant"),
    })


@login_required
@role_requis("assureur", "administrateur")
def detail_demande(request, pk):
    demande = get_object_or_404(DemandeIndemnisation, pk=pk)
    if demande.assureur_id != request.user.cima_id_assureur and request.user.cima_role != "administrateur":
        return HttpResponseForbidden("⛔ Cette demande ne relève pas de votre compagnie.")
    dossier = demande.dossier
    id_acteur = getattr(request.user, "cima_id_acteur", None)
    notifications_dossier = dossier.notifications.filter(acteur_id=id_acteur).order_by("-id_notification")
    return render(request, "core/detail_demande.html", {
        "demande": demande,
        "dossier": dossier,
        "documents": dossier.documents.order_by("-date_upload"),
        "notifications_dossier": notifications_dossier,
    })


@login_required
@role_requis("assureur", "administrateur")
def ajouter_document_assureur(request, pk):
    """L'assureur ajoute un document (rapport initial, réponse à la contre-expertise...) sur le dossier."""
    dossier = get_object_or_404(Dossier, pk=pk)
    demandes_assureur = dossier.demandes.filter(assureur_id=request.user.cima_id_assureur)
    if not demandes_assureur.exists() and request.user.cima_role != "administrateur":
        return HttpResponseForbidden("⛔ Ce dossier ne comporte aucune demande de votre compagnie.")
    if dossier.statut == "CLOTURE":
        messages.error(request, "Ce dossier est clôturé et archivé : plus aucune modification possible.")
        return redirect("tableau_assureur")

    if request.method == "POST":
        form = DocumentAssureurForm(request.POST, request.FILES, demandes_queryset=demandes_assureur)
        if form.is_valid():
            type_doc = form.cleaned_data["type_document"]
            if type_doc == "REPONSE_ASSUREUR_CONTRE_EXPERTISE":
                if not dossier.documents.filter(type_document="RAPPORT_CONTRE_EXPERTISE").exists():
                    messages.error(
                        request,
                        "Aucun rapport de contre-expertise n'a encore été transmis sur ce dossier."
                    )
                    return redirect("ajouter_document_assureur", pk=dossier.pk)

            doc = form.save(commit=False)
            doc.dossier = dossier
            doc.ajoute_par = Acteur.objects.filter(pk=request.user.cima_id_acteur).first()
            demande_liee = form.cleaned_data.get("demande_liee")
            doc.demande_liee = demande_liee
            doc.save()

            if type_doc == "PROPOSITION_OFFRE" and demande_liee:
                demande_liee.montant_offre = form.cleaned_data["montant_offre"]
                demande_liee.phase = "OFFRE_TRANSMISE"
                demande_liee.save(update_fields=["montant_offre", "phase"])
                dossier.statut = "EN_EVALUATION"
                dossier.save(update_fields=["statut"])
                notifier(dossier.victime, dossier,
                         f"Une offre de {demande_liee.montant_offre} FCFA vous a été transmise pour le "
                         f"dossier {dossier.numero_dossier}. Consultez votre dossier pour l'accepter ou la refuser.")
                if dossier.assistant:
                    notifier(dossier.assistant, dossier,
                             f"L'assureur a transmis une offre de {demande_liee.montant_offre} FCFA "
                             f"sur le dossier {dossier.numero_dossier}.")
            else:
                notifier(dossier.victime, dossier,
                         f"L'assureur a ajouté un document ({doc.get_type_document_display()}) "
                         f"sur votre dossier {dossier.numero_dossier}.")
                if dossier.assistant:
                    notifier(dossier.assistant, dossier,
                             f"L'assureur a ajouté un document ({doc.get_type_document_display()}) "
                             f"sur le dossier {dossier.numero_dossier}.")

            messages.success(request, "Document ajouté et notifié à la victime et à l'assistant.")
            demande_ref = demande_liee or demandes_assureur.first()
            if demande_ref:
                return redirect("detail_demande", pk=demande_ref.pk)
            return redirect("tableau_assureur")
    else:
        form = DocumentAssureurForm(demandes_queryset=demandes_assureur)
    return render(request, "core/formulaire_simple.html", {
        "form": form, "titre": f"📄 Ajouter document — Dossier {dossier.numero_dossier}",
    })


@login_required
@role_requis("assureur", "administrateur")
def valider_document(request, pk, decision):
    """L'assureur valide ou rejette un document soumis par la victime/l'assistant."""
    document = get_object_or_404(Document, pk=pk)
    dossier = document.dossier
    a_une_demande = dossier.demandes.filter(assureur_id=request.user.cima_id_assureur).exists()
    if not a_une_demande and request.user.cima_role != "administrateur":
        return HttpResponseForbidden("⛔ Ce dossier ne comporte aucune demande de votre compagnie.")
    if decision not in ("VALIDE", "REJETE"):
        return HttpResponseForbidden("Action inconnue.")
    document.statut_validation = decision
    document.save(update_fields=["statut_validation"])
    libelle = "validé" if decision == "VALIDE" else "rejeté"
    if dossier.assistant:
        notifier(dossier.assistant, dossier,
                 f"Le document « {document.get_type_document_display()} » du dossier "
                 f"{dossier.numero_dossier} a été {libelle} par l'assureur.")
    notifier(dossier.victime, dossier,
             f"Votre document « {document.get_type_document_display()} » a été {libelle} par l'assureur.")
    messages.success(request, f"Document {libelle}.")
    demande_ref = dossier.demandes.filter(assureur_id=request.user.cima_id_assureur).first()
    if demande_ref:
        return redirect("detail_demande", pk=demande_ref.pk)
    return redirect("tableau_assureur")


@login_required
@role_requis("victime", "administrateur")
def accepter_offre(request, pk):
    """La victime accepte l'offre — équivaut à une décision VALIDÉE, déclenche la lettre."""
    demande = get_object_or_404(DemandeIndemnisation, pk=pk)
    dossier = demande.dossier
    if not peut_voir_dossier(request.user, dossier):
        return HttpResponseForbidden("⛔ Accès refusé.")
    if demande.phase != "OFFRE_TRANSMISE":
        messages.error(request, "Aucune offre en attente sur cette demande.")
        return redirect("detail_dossier", pk=dossier.pk)

    demande.phase = "OFFRE_ACCEPTEE"
    demande.montant_evalue = demande.montant_offre
    demande.statut = "TRAITEE"
    demande.save(update_fields=["phase", "montant_evalue", "statut"])

    decision_existante = getattr(demande, "decision", None)
    decision = decision_existante or Decision(demande=demande)
    decision.resultat = "VALIDEE"
    decision.motif = "Offre transactionnelle acceptée par la victime."
    decision.save()

    dossier.statut = "VALIDE"
    dossier.save(update_fields=["statut"])

    notifier(dossier.assistant, dossier,
             f"La victime a accepté l'offre de {demande.montant_offre} FCFA sur le dossier {dossier.numero_dossier}.")
    notifier(demande.assureur, dossier,
             f"L'offre a été acceptée par la victime sur le dossier {dossier.numero_dossier}. "
             f"Vous pouvez procéder au paiement définitif.")

    from core.pdf_utils import generer_lettre_decision
    try:
        generer_lettre_decision(decision)
    except Exception:
        pass

    messages.success(request, "Offre acceptée. Le dossier est validé, l'assureur peut procéder au paiement.")
    return redirect("detail_dossier", pk=dossier.pk)


@login_required
@role_requis("victime", "administrateur")
def refuser_offre(request, pk):
    """La victime refuse l'offre — l'assureur pourra renégocier ou l'assistant déclarera un contentieux."""
    demande = get_object_or_404(DemandeIndemnisation, pk=pk)
    dossier = demande.dossier
    if not peut_voir_dossier(request.user, dossier):
        return HttpResponseForbidden("⛔ Accès refusé.")
    if demande.phase != "OFFRE_TRANSMISE":
        messages.error(request, "Aucune offre en attente sur cette demande.")
        return redirect("detail_dossier", pk=dossier.pk)
    if request.method == "POST":
        form = RefusOffreForm(request.POST)
        if form.is_valid():
            demande.phase = "OFFRE_REFUSEE"
            demande.save(update_fields=["phase"])
            motif = form.cleaned_data["motif"]
            notifier(demande.assureur, dossier,
                     f"La victime a refusé l'offre de {demande.montant_offre} FCFA sur le dossier "
                     f"{dossier.numero_dossier}. Motif : « {motif} ». Vous pouvez transmettre une nouvelle offre.")
            notifier(dossier.assistant, dossier,
                     f"L'offre a été refusée sur le dossier {dossier.numero_dossier}. Motif : « {motif} ». "
                     f"Si aucun accord n'est trouvé, vous pouvez déclarer le contentieux depuis le dossier.")
            messages.warning(request, "Refus enregistré et transmis à l'assureur et à l'assistant.")
            return redirect("detail_dossier", pk=dossier.pk)
    else:
        form = RefusOffreForm()
    return render(request, "core/formulaire_simple.html", {
        "form": form, "titre": f"❌ Refuser l'offre — {demande.numero_suivi}",
    })


@login_required
@role_requis("assureur", "administrateur")
def reexaminer_demande(request, pk):
    demande = get_object_or_404(DemandeIndemnisation, pk=pk)
    if demande.assureur_id != request.user.cima_id_assureur and request.user.cima_role != "administrateur":
        return HttpResponseForbidden("⛔ Cette demande ne relève pas de votre compagnie.")
    dossier = demande.dossier
    if dossier.statut == "CLOTURE":
        messages.error(request, "Ce dossier est clôturé et archivé : plus aucun réexamen possible.")
        return redirect("detail_demande", pk=demande.pk)
    demande.statut = "EN_COURS"
    demande.save()
    notifier(dossier.victime, dossier,
             f"Votre dossier {dossier.numero_dossier} fait l'objet d'un réexamen par l'assureur.")
    notifier(dossier.assistant, dossier,
             f"L'assureur réexamine la demande {demande.numero_suivi} du dossier {dossier.numero_dossier}.")
    messages.success(request, "Demande déverrouillée : vous pouvez à nouveau l'évaluer ou la décider.")
    return redirect("detail_demande", pk=demande.pk)


@login_required
@role_requis("assureur", "administrateur")
def enregistrer_evaluation(request, pk):
    demande = get_object_or_404(DemandeIndemnisation, pk=pk)
    if demande.assureur_id != request.user.cima_id_assureur and request.user.cima_role != "administrateur":
        return HttpResponseForbidden("⛔ Cette demande ne relève pas de votre compagnie.")
    if demande.statut == "TRAITEE":
        messages.error(request, "Cette demande a déjà été traitée et ne peut plus être évaluée.")
        return redirect("detail_demande", pk=demande.pk)
    if request.method == "POST":
        form = EvaluationForm(request.POST)
        if form.is_valid():
            evaluation = form.save(commit=False)
            evaluation.demande = demande
            evaluation.save()
            demande.montant_evalue = evaluation.montant
            demande.statut = "EN_COURS"
            demande.save()
            messages.success(request, "Évaluation enregistrée.")
            return redirect("tableau_assureur")
    else:
        form = EvaluationForm()
    return render(request, "core/formulaire_simple.html", {
        "form": form, "titre": f"⚖️ Évaluation — Demande #{demande.pk}",
    })


@login_required
@role_requis("assureur", "administrateur")
def enregistrer_decision(request, pk):
    demande = get_object_or_404(DemandeIndemnisation, pk=pk)
    if demande.assureur_id != request.user.cima_id_assureur and request.user.cima_role != "administrateur":
        return HttpResponseForbidden("⛔ Cette demande ne relève pas de votre compagnie.")
    decision_existante = getattr(demande, "decision", None)
    if request.method == "POST":
        form = DecisionForm(request.POST, instance=decision_existante)
        if form.is_valid():
            decision = form.save(commit=False)
            decision.demande = demande
            decision.save()

            dossier = demande.dossier
            dossier.statut = "VALIDE" if decision.resultat == "VALIDEE" else "REJETE"
            dossier.save()
            demande.statut = "TRAITEE"
            demande.save()

            resultat_lisible = "validée" if decision.resultat == "VALIDEE" else "rejetée"
            verbe = "réexaminée et" if decision_existante else ""
            notifier(dossier.victime, dossier,
                     f"Votre demande {demande.numero_suivi} a été {verbe} {resultat_lisible} par l'assureur.")
            notifier(dossier.assistant, dossier,
                     f"Décision {'mise à jour' if decision_existante else 'rendue'} sur le dossier "
                     f"{dossier.numero_dossier} : {resultat_lisible}.")

            from core.pdf_utils import generer_lettre_decision
            try:
                generer_lettre_decision(decision)
                messages.success(request, f"Décision '{decision.resultat}' enregistrée. 📄 Lettre officielle générée et notifications envoyées.")
            except Exception as e:
                messages.warning(request, f"Décision enregistrée, mais la lettre PDF n'a pas pu être générée ({e}).")

            return redirect("tableau_assureur")
    else:
        form = DecisionForm()
    return render(request, "core/formulaire_simple.html", {
        "form": form, "titre": f"✅ Décision — Demande #{demande.pk}",
    })


@login_required
@role_requis("assureur", "administrateur")
def verser_provision(request, pk):
    dossier = get_object_or_404(Dossier, pk=pk)
    if dossier.statut == "PAYE":
        messages.error(
            request,
            "Le dossier a déjà été payé (règlement définitif) : aucune nouvelle provision n'est possible."
        )
        return redirect("tableau_assureur")
    if request.method == "POST":
        form = ProvisionForm(request.POST)
        if form.is_valid():
            montant = form.cleaned_data["montant"]
            Paiement.objects.create(
                dossier=dossier, montant_paye=montant,
                mode_paiement=form.cleaned_data["mode_paiement"], type_paiement="PROVISION",
            )
            notifier(dossier.victime, dossier,
                     f"Une provision de {montant} FCFA a été versée sur le dossier {dossier.numero_dossier}.")
            if dossier.assistant:
                notifier(dossier.assistant, dossier,
                         f"L'assureur a versé une provision de {montant} FCFA sur le dossier {dossier.numero_dossier}.")
            messages.success(request, f"Provision de {montant} FCFA versée.")
            return redirect("tableau_assureur")
    else:
        form = ProvisionForm()
    return render(request, "core/formulaire_simple.html", {
        "form": form, "titre": f"💵 Provision — {dossier.numero_dossier}",
    })


@login_required
@role_requis("assureur", "administrateur")
def enregistrer_paiement_definitif(request, pk):
    decision = get_object_or_404(Decision, pk=pk)
    if decision.demande.assureur_id != request.user.cima_id_assureur and request.user.cima_role != "administrateur":
        return HttpResponseForbidden("⛔ Accès refusé.")
    if decision.resultat != "VALIDEE":
        messages.error(request, "Le paiement n'est possible qu'après une décision VALIDÉE.")
        return redirect("tableau_assureur")
    paiement_existant = getattr(decision, "paiement", None)
    if paiement_existant and paiement_existant.statut_confirmation == "CONFIRME":
        messages.warning(request, "Ce paiement a déjà été confirmé par la victime, il ne peut plus être modifié.")
        return redirect("tableau_assureur")
    if paiement_existant and paiement_existant.statut_confirmation not in ("CONTESTE", "TRANSMIS_ASSUREUR"):
        messages.warning(request, "Un paiement est déjà en attente de confirmation pour cette décision.")
        return redirect("tableau_assureur")

    if request.method == "POST":
        form = PaiementDefinitifForm(request.POST)
        if form.is_valid():
            dossier = decision.demande.dossier
            total_provisions = sum(
                p.montant_paye for p in dossier.provisions.filter(type_paiement="PROVISION")
            )
            montant_valide = form.cleaned_data["montant"]
            montant_net = montant_valide - total_provisions
            if montant_net < 0:
                messages.error(request, "Les provisions déjà versées dépassent le montant validé.")
                return redirect("tableau_assureur")

            if paiement_existant:
                paiement_existant.montant_paye = montant_net
                paiement_existant.montant_provisions_deduites = total_provisions
                paiement_existant.mode_paiement = form.cleaned_data["mode_paiement"]
                paiement_existant.statut_confirmation = "EN_ATTENTE"
                paiement_existant.confirmation_victime = False
                paiement_existant.commentaire_victime = None
                paiement_existant.save()
            else:
                Paiement.objects.create(
                    decision=decision, montant_paye=montant_net,
                    montant_provisions_deduites=total_provisions,
                    mode_paiement=form.cleaned_data["mode_paiement"],
                )
            dossier.statut = "PAYE"
            dossier.save()
            notifier(dossier.victime, dossier,
                     f"Un paiement définitif corrigé de {montant_net} FCFA a été effectué pour le dossier "
                     f"{dossier.numero_dossier}. Merci de le confirmer dans votre espace."
                     if paiement_existant else
                     f"Le paiement définitif de {montant_net} FCFA a été effectué pour le dossier "
                     f"{dossier.numero_dossier}. Merci de le confirmer dans votre espace.")
            messages.success(
                request,
                f"Solde net de {montant_net} FCFA enregistré "
                f"(indemnisation {montant_valide} − provisions {total_provisions})."
            )
            return redirect("tableau_assureur")
    else:
        form = PaiementDefinitifForm(
            initial={"montant": decision.demande.montant_evalue} if not paiement_existant else None
        )
    return render(request, "core/formulaire_simple.html", {
        "form": form, "titre": f"💰 Paiement définitif — Décision #{decision.pk}",
    })


# ============================================================
# ESPACE ADMINISTRATEUR
# ============================================================
@login_required
@role_requis("administrateur")
@login_required
@role_requis("administrateur")
def tableau_admin(request):
    q = request.GET.get("q", "").strip()
    statut_filtre = request.GET.get("statut", "")

    dossiers_qs = Dossier.objects.select_related("victime", "assistant").order_by("-id_dossier")
    if q:
        dossiers_qs = dossiers_qs.filter(
            models.Q(numero_dossier__icontains=q)
            | models.Q(victime__nom__icontains=q)
            | models.Q(victime__prenom__icontains=q)
            | models.Q(zone__icontains=q)
        )
    if statut_filtre:
        dossiers_qs = dossiers_qs.filter(statut=statut_filtre)

    acteurs_qs = Acteur.objects.all().order_by("nom", "prenom")
    q_acteur = request.GET.get("q_acteur", "").strip()
    if q_acteur:
        acteurs_qs = acteurs_qs.filter(
            models.Q(nom__icontains=q_acteur)
            | models.Q(prenom__icontains=q_acteur)
            | models.Q(email__icontains=q_acteur)
            | models.Q(role__icontains=q_acteur)
        )

    pag_d = Paginator(dossiers_qs, 15)
    page_d = pag_d.get_page(request.GET.get("page_d"))
    pag_a = Paginator(acteurs_qs, 15)
    page_a = pag_a.get_page(request.GET.get("page_a"))
    extra_qs = ""
    if q:
        extra_qs += f"&q={q}"
    if statut_filtre:
        extra_qs += f"&statut={statut_filtre}"

    paiements_qs = Paiement.objects.select_related("dossier", "decision__demande__dossier").order_by("-id_paiement")
    paiements_par_dossier = {}
    for p in paiements_qs:
        d = p.dossier or (p.decision.demande.dossier if p.decision else None)
        if d:
            paiements_par_dossier.setdefault(d, []).append(p)
    groupes_paiements = sorted(paiements_par_dossier.items(), key=lambda kv: kv[0].pk, reverse=True)

    q_paiement = request.GET.get("q_paiement", "").strip()
    if q_paiement:
        groupes_paiements = [
            (d, liste) for d, liste in groupes_paiements
            if q_paiement.lower() in d.numero_dossier.lower()
        ]

    pag_p = Paginator(groupes_paiements, 10)
    page_p = pag_p.get_page(request.GET.get("page_p"))

    documents_qs = Document.objects.select_related("dossier", "ajoute_par").order_by("-date_upload")
    q_document = request.GET.get("q_document", "").strip()
    if q_document:
        documents_qs = documents_qs.filter(
            models.Q(dossier__numero_dossier__icontains=q_document)
            | models.Q(type_document__icontains=q_document)
        )
    pag_doc = Paginator(documents_qs, 15)
    page_documents = pag_doc.get_page(request.GET.get("page_doc"))

    return render(request, "core/tableau_admin.html", {
        "acteurs": Acteur.objects.all().order_by("id_acteur"),
        "page_acteurs": page_a, "q_acteur": q_acteur,
        "dossiers": Dossier.objects.select_related("victime", "assistant").order_by("id_dossier"),
        "page_dossiers": page_d, "q": q, "statut_filtre": statut_filtre, "extra_qs": extra_qs,
        "statuts_disponibles": Dossier.STATUT_CHOICES,
        "documents": Document.objects.select_related("dossier").order_by("id_document"),
        "demandes": DemandeIndemnisation.objects.select_related("dossier", "assureur").order_by("id_demande"),
        "decisions": Decision.objects.select_related("demande").order_by("id_decision"),
        "page_paiements": page_p, "q_paiement": q_paiement,
        "page_documents": page_documents, "q_document": q_document,
        "paiements": Paiement.objects.order_by("id_paiement"),
    })


@login_required
@role_requis("administrateur")
def ajouter_acteur(request):
    if request.method == "POST":
        form = AjouterActeurForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            acteur = Acteur.objects.create(
                nom=d["nom"], prenom=d["prenom"], email=d["email"],
                telephone=d["telephone"], mot_de_passe="admin_created", role=d["role"],
            )
            if d["role"] == "victime":
                Victime.objects.create(acteur=acteur)
            elif d["role"] == "assistant":
                Assistant.objects.create(acteur=acteur, zone_intervention=d["zone_intervention"])
            elif d["role"] == "assureur":
                Assureur.objects.create(acteur=acteur, nom_compagnie=d["nom_compagnie"])
            messages.success(request, f"Acteur '{d['prenom']} {d['nom']}' ajouté.")
            return redirect("tableau_admin")
    else:
        form = AjouterActeurForm()
    return render(request, "core/formulaire_simple.html", {"form": form, "titre": "➕ Ajouter un acteur"})


@login_required
@role_requis("administrateur")
def modifier_acteur(request, pk):
    acteur = get_object_or_404(Acteur, pk=pk)
    if request.method == "POST":
        acteur.nom = request.POST.get("nom", acteur.nom)
        acteur.prenom = request.POST.get("prenom", acteur.prenom)
        acteur.email = request.POST.get("email", acteur.email)
        acteur.role = request.POST.get("role", acteur.role)
        acteur.actif = request.POST.get("actif") == "on"
        acteur.save()
        messages.success(request, "Acteur modifié.")
        return redirect("tableau_admin")
    return render(request, "core/modifier_acteur.html", {"acteur": acteur})


@login_required
@role_requis("administrateur")
def basculer_actif_acteur(request, pk):
    """Bloque/débloque l'accès d'un acteur. Un administrateur ne peut pas être bloqué via cette action."""
    acteur = get_object_or_404(Acteur, pk=pk)
    if acteur.role == "administrateur":
        messages.error(request, "Un compte administrateur ne peut pas être bloqué.")
        return redirect("tableau_admin")
    acteur.actif = not acteur.actif
    acteur.save(update_fields=["actif"])
    messages.success(
        request,
        f"Compte de {acteur.prenom} {acteur.nom} " + ("réactivé." if acteur.actif else "bloqué — accès coupé immédiatement.")
    )
    return redirect("tableau_admin")


@login_required
@role_requis("administrateur")
def supprimer_objet(request, modele, pk):
    """Suppression générique — utilisée par tous les boutons 🗑️ du tableau admin."""
    from django.db.models import ProtectedError
    modeles = {
        "acteur": Acteur, "dossier": Dossier, "document": Document,
        "demande": DemandeIndemnisation, "decision": Decision, "paiement": Paiement,
    }
    Modele = modeles.get(modele)
    if not Modele:
        messages.error(request, "Type d'objet inconnu.")
        return redirect("tableau_admin")
    obj = get_object_or_404(Modele, pk=pk)
    if modele == "acteur" and obj.role == "administrateur":
        messages.error(request, "Un compte administrateur ne peut pas être supprimé.")
        return redirect("tableau_admin")
    try:
        obj.delete()
        messages.success(request, f"{modele.capitalize()} #{pk} supprimé.")
    except ProtectedError:
        if modele == "dossier":
            messages.error(
                request,
                f"Impossible de supprimer le dossier {obj.numero_dossier} : il contient des demandes "
                "d'indemnisation liées (historique légal/financier protégé). "
                "Utilisez plutôt la clôture du dossier si besoin."
            )
        else:
            messages.error(
                request,
                f"Impossible de supprimer cet élément : d'autres données en dépendent encore."
            )
    return redirect("tableau_admin")


@login_required
@role_requis("administrateur")
def forcer_suppression_dossier(request, pk):
    """Supprime un dossier ET tout son contenu lié (irréversible) — réservé à l'admin."""
    dossier = get_object_or_404(Dossier, pk=pk)
    demandes = dossier.demandes.all()
    nb_demandes = demandes.count()
    nb_decisions = Decision.objects.filter(demande__dossier=dossier).count()
    nb_paiements = (
        Paiement.objects.filter(dossier=dossier).count()
        + Paiement.objects.filter(decision__demande__dossier=dossier).count()
    )
    nb_documents = dossier.documents.count()
    nb_notifications = dossier.notifications.count()

    if request.method == "POST":
        numero = dossier.numero_dossier
        Paiement.objects.filter(decision__demande__dossier=dossier).delete()
        Paiement.objects.filter(dossier=dossier).delete()
        Decision.objects.filter(demande__dossier=dossier).delete()
        Evaluation.objects.filter(demande__dossier=dossier).delete()
        demandes.delete()
        dossier.notifications.all().delete()
        dossier.documents.all().delete()
        dossier.delete()
        messages.success(request, f"Dossier {numero} et toutes ses données liées supprimés définitivement.")
        return redirect("tableau_admin")

    return render(request, "core/confirmer_suppression_dossier.html", {
        "dossier": dossier,
        "nb_demandes": nb_demandes, "nb_decisions": nb_decisions,
        "nb_paiements": nb_paiements, "nb_documents": nb_documents,
        "nb_notifications": nb_notifications,
    })


# ============================================================
# PAGES CONTACTS (annuaires professionnels)
# ============================================================
@login_required
@role_requis("assistant", "administrateur")
def contacts_assureurs(request):
    q = request.GET.get("q", "").strip()
    assureurs = Acteur.objects.filter(role="assureur").select_related("profil_assureur")
    if q:
        assureurs = assureurs.filter(
            models.Q(nom__icontains=q) | models.Q(prenom__icontains=q)
            | models.Q(email__icontains=q) | models.Q(profil_assureur__nom_compagnie__icontains=q)
        )
    return render(request, "core/contacts.html", {
        "titre": "🏦 Assureurs", "acteurs": assureurs, "colonne_extra": "compagnie", "q": q,
    })


@login_required
@role_requis("assistant", "administrateur")
def contacts_victimes(request):
    q = request.GET.get("q", "").strip()
    victimes = dossiers_visibles_par(request.user).values_list("victime", flat=True).distinct()
    acteurs = Acteur.objects.filter(pk__in=victimes)
    if q:
        acteurs = acteurs.filter(
            models.Q(nom__icontains=q) | models.Q(prenom__icontains=q) | models.Q(email__icontains=q)
        )
    return render(request, "core/contacts.html", {
        "titre": "🧑 Victimes de ma zone", "acteurs": acteurs, "colonne_extra": None, "q": q,
    })


@login_required
@role_requis("victime", "assureur", "administrateur")
def contacts_assistants(request):
    if request.user.cima_role == "assistant":
        return HttpResponseForbidden()
    q = request.GET.get("q", "").strip()
    assistants = Acteur.objects.filter(role="assistant").select_related("profil_assistant")
    if q:
        assistants = assistants.filter(
            models.Q(nom__icontains=q) | models.Q(prenom__icontains=q)
            | models.Q(email__icontains=q) | models.Q(profil_assistant__zone_intervention__icontains=q)
        )
    return render(request, "core/contacts.html", {
        "titre": "📞 Assistants", "acteurs": assistants, "colonne_extra": "zone", "q": q,
    })


# ============================================================
# INSCRIPTION NATIVE (sans navigateur Keycloak)
# ============================================================
def inscription(request):
    """Crée le compte Keycloak (API Admin) + le profil métier en une seule étape."""
    from core.forms import InscriptionForm
    from core.keycloak_admin import creer_utilisateur_keycloak

    if request.method == "POST":
        form = InscriptionForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            succes, resultat = creer_utilisateur_keycloak(
                d["username"], d["email"], d["password"], d["prenom"], d["nom"]
            )
            if not succes:
                messages.error(request, resultat)
                return render(request, "core/inscription.html", {"form": form})

            acteur = Acteur.objects.create(
                nom=d["nom"], prenom=d["prenom"], email=d["email"], username=d["username"],
                telephone=d["telephone"], mot_de_passe="keycloak_managed", role=d["role"],
            )
            if d["role"] == "victime":
                Victime.objects.create(acteur=acteur)
            elif d["role"] == "assistant":
                Assistant.objects.create(acteur=acteur, zone_intervention=d["zone_intervention"])
            elif d["role"] == "assureur":
                Assureur.objects.create(acteur=acteur, nom_compagnie=d["nom_compagnie"])

            messages.success(
                request,
                f"✅ Bienvenue {d['prenom']} {d['nom']} ! Un email de vérification a été "
                f"envoyé à {d['email']}. Cliquez sur le lien reçu avant de vous connecter."
            )
            return redirect("accueil")
    else:
        form = InscriptionForm()
    return render(request, "core/inscription.html", {"form": form})
