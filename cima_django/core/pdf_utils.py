"""
Génération automatique des lettres officielles (validation / rejet)
suite à la décision de l'assureur — Système CIMA.
"""
import os
from datetime import datetime
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

from core.models import Document


def generer_lettre_decision(decision):
    """
    Génère le PDF de la lettre (validation ou rejet), l'enregistre dans
    MEDIA_ROOT/lettres/ et crée le Document correspondant, visible
    automatiquement dans les onglets Documents de la victime/assistant.
    """
    demande = decision.demande
    dossier = demande.dossier
    victime = dossier.victime
    assistant = dossier.assistant
    assureur_acteur = demande.assureur
    compagnie = getattr(getattr(assureur_acteur, "profil_assureur", None), "nom_compagnie", "Compagnie d'Assurance")
    agrement = getattr(getattr(assureur_acteur, "profil_assureur", None), "numero_agrement_cima", "—")

    dossier_lettres = os.path.join(settings.MEDIA_ROOT, "lettres")
    os.makedirs(dossier_lettres, exist_ok=True)
    type_lettre = "VALIDATION" if decision.resultat == "VALIDEE" else "REJET"
    nom_fichier = f"LETTRE_{type_lettre}_{dossier.numero_dossier}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    chemin_absolu = os.path.join(dossier_lettres, nom_fichier)
    chemin_relatif = os.path.join("lettres", nom_fichier)

    c = canvas.Canvas(chemin_absolu, pagesize=A4)
    largeur, hauteur = A4
    BLEU = HexColor("#1B4F72")
    GRIS = HexColor("#555555")

    c.setFillColor(BLEU)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, hauteur - 25 * mm, compagnie)
    c.setFont("Helvetica", 9)
    c.setFillColor(GRIS)
    c.drawString(20 * mm, hauteur - 31 * mm, f"N° Agrément CIMA : {agrement}")
    c.line(20 * mm, hauteur - 35 * mm, largeur - 20 * mm, hauteur - 35 * mm)

    c.setFillColor(HexColor("#000000"))
    c.setFont("Helvetica", 10)
    c.drawRightString(largeur - 20 * mm, hauteur - 45 * mm, f"Fait le {decision.date_decision.strftime('%d/%m/%Y')}")
    c.drawString(20 * mm, hauteur - 45 * mm, f"Réf. Dossier : {dossier.numero_dossier}")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, hauteur - 60 * mm, f"À l'attention de : {victime.prenom} {victime.nom}")

    y = hauteur - 75 * mm
    c.setFont("Helvetica-Bold", 12)
    if decision.resultat == "VALIDEE":
        c.setFillColor(HexColor("#1E8449"))
        c.drawString(20 * mm, y, "OBJET : NOTIFICATION DE VALIDATION D'INDEMNISATION")
    else:
        c.setFillColor(HexColor("#C0392B"))
        c.drawString(20 * mm, y, "OBJET : NOTIFICATION DE REJET DE DEMANDE D'INDEMNISATION")
    c.setFillColor(HexColor("#000000"))

    y -= 15 * mm
    c.setFont("Helvetica", 10)
    texte = c.beginText(20 * mm, y)
    texte.setLeading(15)

    if decision.resultat == "VALIDEE":
        montant_final = demande.montant_evalue or demande.montant_reclame
        lignes = [
            f"Madame, Monsieur {victime.prenom} {victime.nom},", "",
            f"Nous faisons suite à l'examen de votre dossier n° {dossier.numero_dossier}",
            "concernant votre demande d'indemnisation suite à l'accident de la",
            "circulation dont vous avez été victime.", "",
            "Après évaluation de votre préjudice conformément au Code CIMA, nous",
            "avons le plaisir de vous informer que votre demande a été VALIDÉE.", "",
            f"Montant de l'indemnisation accordée : {montant_final:,.0f} FCFA".replace(",", " "), "",
            "Conformément au Code CIMA, le règlement interviendra dans un délai",
            "de 15 jours à compter de la présente notification.", "",
            f"Votre dossier est suivi par : {assistant.prenom} {assistant.nom}",
            f"Contact : {assistant.email} | {assistant.telephone}", "",
            "Nous vous prions d'agréer nos salutations distinguées.",
        ]
    else:
        motif = decision.motif or "Motif non précisé"
        motif_lignes = [motif[i:i + 85] for i in range(0, len(motif), 85)] or [motif]
        lignes = [
            f"Madame, Monsieur {victime.prenom} {victime.nom},", "",
            f"Nous faisons suite à l'examen de votre dossier n° {dossier.numero_dossier}.", "",
            "Après étude approfondie, nous sommes au regret de vous informer que",
            "votre demande a été REJETÉE, pour le motif suivant :", "",
        ] + [f"    « {l} »" if i == 0 else f"      {l}" for i, l in enumerate(motif_lignes)] + [
            "",
            "DROIT DE RECOURS : vous disposez d'un délai pour contester cette",
            "décision. Rapprochez-vous de votre assistant dans les meilleurs délais.", "",
            f"Votre dossier est suivi par : {assistant.prenom} {assistant.nom}",
            f"Contact : {assistant.email} | {assistant.telephone}", "",
            "Nous vous prions d'agréer nos salutations distinguées.",
        ]

    for ligne in lignes:
        texte.textLine(ligne)
    c.drawText(texte)

    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(GRIS)
    c.drawCentredString(largeur / 2, 15 * mm, "Document généré automatiquement — Système CIMA")
    c.save()

    Document.objects.create(
        dossier=dossier, type_document="LETTRE_DECISION",
        chemin_fichier=chemin_relatif, statut_validation="VALIDE",
    )
    return chemin_absolu


def generer_quittance(paiement):
    """
    Génère la quittance / certificat de règlement définitif : document
    juridique attestant que la victime a reçu le paiement et renonce à
    toute réclamation future sur ce dossier — clôture le litige.
    """
    decision = paiement.decision
    demande = decision.demande if decision else None
    dossier = demande.dossier if demande else paiement.dossier
    victime = dossier.victime
    assistant = dossier.assistant
    assureur_acteur = demande.assureur if demande else None
    compagnie = getattr(getattr(assureur_acteur, "profil_assureur", None), "nom_compagnie", "l'assureur")

    dossier_lettres = os.path.join(settings.MEDIA_ROOT, "lettres")
    os.makedirs(dossier_lettres, exist_ok=True)
    reference = f"QT-{dossier.numero_dossier}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    nom_fichier = f"QUITTANCE_{dossier.numero_dossier}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    chemin_absolu = os.path.join(dossier_lettres, nom_fichier)
    chemin_relatif = os.path.join("lettres", nom_fichier)
    date_reglement = paiement.date_confirmation.date() if paiement.date_confirmation else datetime.now().date()

    c = canvas.Canvas(chemin_absolu, pagesize=A4)
    largeur, hauteur = A4
    BLEU = HexColor("#1B4F72")
    GRIS = HexColor("#555555")
    GRIS_CLAIR = HexColor("#F2F4F6")
    NOIR = HexColor("#000000")

    # --- Bordure décorative ---
    c.setStrokeColor(BLEU)
    c.setLineWidth(1.2)
    c.rect(12 * mm, 12 * mm, largeur - 24 * mm, hauteur - 24 * mm)

    # --- En-tête ---
    c.setFillColor(BLEU)
    c.setFont("Helvetica-Bold", 17)
    c.drawCentredString(largeur / 2, hauteur - 28 * mm, "QUITTANCE DE RÈGLEMENT DÉFINITIF")
    c.setFont("Helvetica", 9)
    c.setFillColor(GRIS)
    c.drawCentredString(largeur / 2, hauteur - 34 * mm, "Certificat de renonciation à recours — Code CIMA")
    c.setStrokeColor(BLEU)
    c.setLineWidth(0.6)
    c.line(25 * mm, hauteur - 38 * mm, largeur - 25 * mm, hauteur - 38 * mm)

    # --- Encadré identification ---
    boite_haut = hauteur - 44 * mm
    boite_bas = boite_haut - 32 * mm
    c.setFillColor(GRIS_CLAIR)
    c.rect(20 * mm, boite_bas, largeur - 40 * mm, boite_haut - boite_bas, fill=1, stroke=0)
    c.setFillColor(NOIR)
    c.setFont("Helvetica-Bold", 9)
    lignes_id = [
        ("Référence quittance", reference),
        ("Dossier CIMA", dossier.numero_dossier),
        ("Victime", f"{victime.prenom} {victime.nom}"),
        ("Assureur", compagnie),
        ("Assistant en charge", f"{assistant.prenom} {assistant.nom}" if assistant else "—"),
        ("Date de règlement", date_reglement.strftime("%d/%m/%Y")),
    ]
    y_id = boite_haut - 7 * mm
    for label, valeur in lignes_id:
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(GRIS)
        c.drawString(25 * mm, y_id, f"{label} :")
        c.setFont("Helvetica", 9)
        c.setFillColor(NOIR)
        c.drawString(70 * mm, y_id, str(valeur))
        y_id -= 5 * mm

    # --- Corps juridique ---
    y = boite_bas - 12 * mm
    c.setFont("Helvetica", 10)
    texte = c.beginText(25 * mm, y)
    texte.setLeading(14.5)
    montant_str = f"{paiement.montant_paye:,.0f} FCFA".replace(",", " ")
    lignes = [
        f"Je soussigné(e) {victime.prenom} {victime.nom}, victime de l'accident de la circulation",
        f"objet du dossier n° {dossier.numero_dossier}, déclare et certifie ce qui suit :", "",
        "1. RECONNAISSANCE DE RÈGLEMENT", "",
        f"   Je reconnais avoir reçu de {compagnie} le règlement définitif d'un montant",
        f"   de {montant_str}, en réparation intégrale du préjudice corporel et/ou",
        "   matériel subi lors de l'accident susvisé.", "",
        "2. RENONCIATION À RECOURS", "",
        "   En contrepartie de ce règlement, je déclare renoncer expressément et sans",
        "   réserve à toute réclamation, action ou recours, amiable ou judiciaire,",
        "   présent ou futur, relatif à cet accident et à ses conséquences directes ou",
        "   indirectes, envers l'assureur susmentionné et toute personne tenue à",
        "   réparation à ce titre.", "",
        "3. VALEUR JURIDIQUE", "",
        "   La présente quittance vaut règlement pour solde de tout compte et clôture",
        "   définitivement et irrévocablement le dossier CIMA susvisé.", "",
        "4. MODALITÉ DE CONFIRMATION", "",
        "   La présente confirmation a été enregistrée électroniquement par la victime",
        "   depuis son espace personnel authentifié sur le Système CIMA, valant",
        "   accord et signature au sens des dispositions applicables.",
    ]
    for ligne in lignes:
        texte.textLine(ligne)
    c.drawText(texte)

    # --- Bloc signatures ---
    y_sign = 45 * mm
    c.setStrokeColor(GRIS)
    c.setLineWidth(0.5)
    c.line(25 * mm, y_sign, 95 * mm, y_sign)
    c.line(largeur - 95 * mm, y_sign, largeur - 25 * mm, y_sign)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(NOIR)
    c.drawString(25 * mm, y_sign - 5 * mm, "La Victime")
    c.drawString(largeur - 95 * mm, y_sign - 5 * mm, "Pour le Système CIMA")
    c.setFont("Helvetica", 8)
    c.setFillColor(GRIS)
    c.drawString(25 * mm, y_sign - 10 * mm, f"{victime.prenom} {victime.nom}")
    c.drawString(largeur - 95 * mm, y_sign - 10 * mm,
                 f"{assistant.prenom} {assistant.nom}" if assistant else "—")
    c.drawString(25 * mm, y_sign - 14 * mm, f"Confirmé le {date_reglement.strftime('%d/%m/%Y')}")

    # --- Pied de page ---
    c.setFont("Helvetica-Oblique", 7.5)
    c.setFillColor(GRIS)
    c.drawCentredString(largeur / 2, 16 * mm,
                         f"Document généré automatiquement — Système CIMA — Réf. {reference}")
    c.save()

    Document.objects.create(
        dossier=dossier, type_document="QUITTANCE",
        chemin_fichier=chemin_relatif, statut_validation="VALIDE",
    )
    return chemin_absolu
