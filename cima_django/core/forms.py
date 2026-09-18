from django import forms
from core.models import (
    Accident, Dossier, Document, DemandeIndemnisation,
    Evaluation, Decision, Paiement, Acteur, Assistant, Assureur, Victime,
)

CLASSE_CHAMP = {"class": "champ"}


class AccidentForm(forms.ModelForm):
    class Meta:
        model = Accident
        fields = ["date_accident", "lieu", "numero_pv", "description"]
        widgets = {
            "date_accident": forms.DateInput(attrs={"type": "date", **CLASSE_CHAMP}),
            "lieu": forms.TextInput(attrs=CLASSE_CHAMP),
            "numero_pv": forms.TextInput(attrs=CLASSE_CHAMP),
            "description": forms.Textarea(attrs={**CLASSE_CHAMP, "rows": 3}),
        }
        labels = {"numero_pv": "N° Procès verbal (PV) — code accident"}


class DossierForm(forms.ModelForm):
    class Meta:
        model = Dossier
        fields = ["numero_dossier", "victime", "accident"]
        widgets = {
            "numero_dossier": forms.TextInput(attrs=CLASSE_CHAMP),
            "victime": forms.Select(attrs=CLASSE_CHAMP),
            "accident": forms.Select(attrs=CLASSE_CHAMP),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["victime"].queryset = Acteur.objects.filter(role="victime")


class StatutDossierForm(forms.Form):
    statut = forms.ChoiceField(choices=Dossier.STATUT_CHOICES, widget=forms.Select(attrs=CLASSE_CHAMP))


TYPES_DOC_ASSISTANT = [
    "CNI", "PASSEPORT", "PV_POLICE", "CERTIFICAT_MEDICAL", "FACTURE_MEDICALE",
    "PHOTO_ACCIDENT", "ATTESTATION_ASSURANCE", "RIB", "AUTRE", "DEMANDE_PROVISION",
    "RAPPORT_CONTRE_EXPERTISE", "EXPERTISE_JUDICIAIRE",
]
TYPES_DOC_ASSUREUR = [
    "RAPPORT_EXPERTISE_INITIALE", "REPONSE_ASSUREUR_CONTRE_EXPERTISE", "AUTRE",
    "PROPOSITION_OFFRE", "LETTRE_CONVOCATION",
]


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["type_document", "chemin_fichier"]
        widgets = {
            "type_document": forms.Select(attrs=CLASSE_CHAMP),
            "chemin_fichier": forms.ClearableFileInput(attrs=CLASSE_CHAMP),
        }
        labels = {"chemin_fichier": "Fichier"}

    def __init__(self, *args, role=None, **kwargs):
        super().__init__(*args, **kwargs)
        types_autorises = {"assistant": TYPES_DOC_ASSISTANT, "assureur": TYPES_DOC_ASSUREUR}.get(role)
        if types_autorises:
            choix = [c for c in Document.TYPE_CHOICES if c[0] in types_autorises]
        else:
            choix = list(Document.TYPE_CHOICES)
        self.fields["type_document"].choices = [("", "---------")] + choix


class DemandeChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.numero_suivi} — {obj.get_type_demande_display()} ({obj.montant_reclame} FCFA)"


class DocumentAssureurForm(DocumentForm):
    demande_liee = DemandeChoiceField(
        label="Lier à la demande de la victime",
        queryset=None, required=False, widget=forms.Select(attrs=CLASSE_CHAMP),
    )
    montant_offre = forms.DecimalField(
        label="Montant de l'offre (FCFA)",
        max_digits=12, decimal_places=2, required=False, widget=forms.NumberInput(attrs=CLASSE_CHAMP),
    )

    def __init__(self, *args, demandes_queryset=None, **kwargs):
        kwargs["role"] = "assureur"
        super().__init__(*args, **kwargs)
        self.fields["demande_liee"].queryset = demandes_queryset
        self.order_fields(["type_document", "demande_liee", "montant_offre", "chemin_fichier"])

    def clean(self):
        d = super().clean()
        if d.get("type_document") == "PROPOSITION_OFFRE":
            if not d.get("demande_liee"):
                self.add_error("demande_liee", "Obligatoire pour une proposition d'offre.")
            if not d.get("montant_offre"):
                self.add_error("montant_offre", "Obligatoire pour une proposition d'offre.")
        return d


class DemandeIndemnisationForm(forms.ModelForm):
    class Meta:
        model = DemandeIndemnisation
        fields = ["assureur", "montant_reclame"]
        widgets = {
            "assureur": forms.Select(attrs=CLASSE_CHAMP),
            "montant_reclame": forms.NumberInput(attrs={**CLASSE_CHAMP, "placeholder": "Optionnel"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assureur"].queryset = Acteur.objects.filter(role="assureur")
        self.fields["montant_reclame"].required = False


class EvaluationForm(forms.ModelForm):
    class Meta:
        model = Evaluation
        fields = ["type_prejudice", "montant", "observations"]
        widgets = {
            "type_prejudice": forms.Select(attrs=CLASSE_CHAMP),
            "montant": forms.NumberInput(attrs=CLASSE_CHAMP),
            "observations": forms.Textarea(attrs={**CLASSE_CHAMP, "rows": 3}),
        }


class DecisionForm(forms.ModelForm):
    class Meta:
        model = Decision
        fields = ["resultat", "motif"]
        widgets = {
            "resultat": forms.Select(attrs=CLASSE_CHAMP),
            "motif": forms.Textarea(attrs={**CLASSE_CHAMP, "rows": 3}),
        }


class PaiementDefinitifForm(forms.Form):
    montant = forms.DecimalField(label="Montant indemnisation validée (FCFA)",
                                   widget=forms.NumberInput(attrs=CLASSE_CHAMP))
    mode_paiement = forms.ChoiceField(choices=Paiement.MODE_CHOICES, widget=forms.Select(attrs=CLASSE_CHAMP))


class ProvisionForm(forms.Form):
    montant = forms.DecimalField(label="Montant de l'acompte (FCFA)",
                                   widget=forms.NumberInput(attrs=CLASSE_CHAMP))
    mode_paiement = forms.ChoiceField(choices=Paiement.MODE_CHOICES, widget=forms.Select(attrs=CLASSE_CHAMP))


class ContestationForm(forms.Form):
    motif = forms.CharField(label="Motif de la contestation",
                              widget=forms.Textarea(attrs={**CLASSE_CHAMP, "rows": 3}))


class RecoursForm(forms.Form):
    motif = forms.CharField(label="Motif du recours",
                              widget=forms.Textarea(attrs={**CLASSE_CHAMP, "rows": 3}))
    nouveau_montant = forms.DecimalField(label="Nouveau montant réclamé (optionnel)",
                                           required=False, widget=forms.NumberInput(attrs=CLASSE_CHAMP))


class AjouterActeurForm(forms.Form):
    ROLE_CHOICES = [("victime", "Victime"), ("assistant", "Assistant"),
                     ("assureur", "Assureur"), ("administrateur", "Administrateur")]

    nom = forms.CharField(widget=forms.TextInput(attrs=CLASSE_CHAMP))
    prenom = forms.CharField(widget=forms.TextInput(attrs=CLASSE_CHAMP))
    email = forms.EmailField(widget=forms.EmailInput(attrs=CLASSE_CHAMP))
    telephone = forms.CharField(widget=forms.TextInput(attrs=CLASSE_CHAMP))
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.Select(attrs=CLASSE_CHAMP))
    zone_intervention = forms.CharField(required=False, widget=forms.TextInput(attrs=CLASSE_CHAMP))
    nom_compagnie = forms.CharField(required=False, widget=forms.TextInput(attrs=CLASSE_CHAMP))


class InscriptionForm(forms.Form):
    ROLE_CHOICES = [
        ("victime", "🏥 Victime — j'ai été impliqué(e) dans un accident"),
        ("assistant", "📋 Assistant — je gère des dossiers de sinistres"),
        ("assureur", "🏦 Assureur — je représente une compagnie d'assurance"),
    ]
    nom = forms.CharField(widget=forms.TextInput(attrs=CLASSE_CHAMP))
    prenom = forms.CharField(widget=forms.TextInput(attrs=CLASSE_CHAMP))
    email = forms.EmailField(widget=forms.EmailInput(attrs=CLASSE_CHAMP))
    telephone = forms.CharField(widget=forms.TextInput(attrs=CLASSE_CHAMP))
    username = forms.CharField(label="Nom d'utilisateur", widget=forms.TextInput(attrs=CLASSE_CHAMP))
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput(attrs=CLASSE_CHAMP))
    password2 = forms.CharField(label="Confirmer le mot de passe", widget=forms.PasswordInput(attrs=CLASSE_CHAMP))
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect)
    zone_intervention = forms.CharField(required=False, label="Zone d'intervention (si Assistant)",
                                          widget=forms.TextInput(attrs=CLASSE_CHAMP))
    nom_compagnie = forms.CharField(required=False, label="Nom de la compagnie (si Assureur)",
                                      widget=forms.TextInput(attrs=CLASSE_CHAMP))

    def clean(self):
        d = super().clean()
        if d.get("password") and d.get("password2") and d["password"] != d["password2"]:
            self.add_error("password2", "Les mots de passe ne correspondent pas.")
        if len(d.get("password", "")) < 6:
            self.add_error("password", "Le mot de passe doit contenir au moins 6 caractères.")
        if d.get("role") == "assistant" and not d.get("zone_intervention"):
            self.add_error("zone_intervention", "Champ obligatoire pour un Assistant.")
        if d.get("role") == "assureur" and not d.get("nom_compagnie"):
            self.add_error("nom_compagnie", "Champ obligatoire pour un Assureur.")
        return d


class RefusOffreForm(forms.Form):
    motif = forms.CharField(
        label="Motif du refus", widget=forms.Textarea(attrs=CLASSE_CHAMP),
    )
