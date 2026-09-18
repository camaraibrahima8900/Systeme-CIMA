"""
Modèles Django — Système CIMA
Ces modèles pointent vers les tables MySQL DÉJÀ EXISTANTES (créées par le
script SQL du prototype Tkinter). managed=False → Django ne touche jamais
au schéma de ces tables via ses propres migrations ; seules les migrations
SQL manuelles (migration1.sql, migration2.sql, ... migration5_isolation.sql)
font évoluer la structure.
"""

from django.db import models


class Acteur(models.Model):
    ROLE_CHOICES = [
        ("victime", "Victime"),
        ("assistant", "Assistant"),
        ("assureur", "Assureur"),
        ("administrateur", "Administrateur"),
    ]

    id_acteur = models.AutoField(primary_key=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(max_length=150, unique=True)
    username = models.CharField(max_length=100, unique=True, null=True, blank=True)
    telephone = models.CharField(max_length=20)
    mot_de_passe = models.CharField(max_length=255)  # géré par Keycloak, non utilisé en Django
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    date_creation = models.DateTimeField(auto_now_add=True)
    actif = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "acteur"

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.role})"


class Victime(models.Model):
    acteur = models.OneToOneField(Acteur, primary_key=True, db_column="id_acteur",
                                   on_delete=models.CASCADE, related_name="profil_victime")
    adresse = models.CharField(max_length=255, null=True, blank=True)
    cni_numero = models.CharField(max_length=50, null=True, blank=True)
    date_naissance = models.DateField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "victime"


class Assistant(models.Model):
    acteur = models.OneToOneField(Acteur, primary_key=True, db_column="id_acteur",
                                   on_delete=models.CASCADE, related_name="profil_assistant")
    matricule = models.CharField(max_length=50, unique=True, null=True, blank=True)
    zone_intervention = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "assistant"


class Assureur(models.Model):
    acteur = models.OneToOneField(Acteur, primary_key=True, db_column="id_acteur",
                                   on_delete=models.CASCADE, related_name="profil_assureur")
    nom_compagnie = models.CharField(max_length=150)
    numero_agrement_cima = models.CharField(max_length=50, null=True, blank=True)
    adresse_siege = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "assureur"


class Accident(models.Model):
    id_accident = models.AutoField(primary_key=True)
    date_accident = models.DateTimeField()
    lieu = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    numero_pv = models.CharField(max_length=50, unique=True, null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "accident"


class Dossier(models.Model):
    STATUT_CHOICES = [
        ("EN_CONSTITUTION", "En constitution"),
        ("DOSSIER_COMPLET", "Dossier complet"),
        ("SOUMIS", "Soumis"),
        ("EN_EVALUATION", "En évaluation"),
        ("VALIDE", "Validé"),
        ("REJETE", "Rejeté"),
        ("PAYE", "Payé"),
        ("CLOTURE", "Clôturé"),
        ("CONTENTIEUX", "Contentieux (judiciaire)"),
    ]

    id_dossier = models.AutoField(primary_key=True)
    numero_dossier = models.CharField(max_length=30, unique=True)
    victime = models.ForeignKey(Acteur, db_column="id_victime", on_delete=models.PROTECT,
                                 related_name="dossiers_victime", limit_choices_to={"role": "victime"})
    assistant = models.ForeignKey(Acteur, db_column="id_assistant", on_delete=models.PROTECT,
                                   related_name="dossiers_assistant", limit_choices_to={"role": "assistant"})
    accident = models.ForeignKey(Accident, db_column="id_accident", on_delete=models.PROTECT,
                                  related_name="dossiers")
    # 🔒 Colonne d'isolation — cœur du cloisonnement par périmètre (migration5_isolation.sql)
    zone = models.CharField(max_length=150, null=True, blank=True, db_index=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="EN_CONSTITUTION")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_cloture = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "dossier"

    def __str__(self):
        return self.numero_dossier


class Document(models.Model):
    TYPE_CHOICES = [
    ("CNI", "CNI"), ("PASSEPORT", "Passeport"), ("PV_POLICE", "Procès verbal (PV)"),
    ("CERTIFICAT_MEDICAL", "Certificat médical"), ("FACTURE_MEDICALE", "Facture médicale"),
    ("PHOTO_ACCIDENT", "Photo accident"), ("ATTESTATION_ASSURANCE", "Attestation assurance"),
    ("RIB", "RIB"), ("LETTRE_DECISION", "Lettre de décision"),
    ("QUITTANCE", "Quittance de règlement définitif"),
    ("DEMANDE_PROVISION", "Demande de provision (victime)"),
    ("RAPPORT_EXPERTISE_INITIALE", "Rapport d'expertise initiale (assureur)"),
    ("RAPPORT_CONTRE_EXPERTISE", "Rapport de contre-expertise (victime/assistant)"),
    ("REPONSE_ASSUREUR_CONTRE_EXPERTISE", "Réponse de l'assureur à la contre-expertise"),
    ("PROPOSITION_OFFRE", "Proposition d'offre (assureur)"),
    ("LETTRE_CONVOCATION", "Convocation à expertise médicale"),
    ("EXPERTISE_JUDICIAIRE", "Expertise judiciaire (recours au tribunal)"),
    ("AUTRE", "Autre"),
    ]
    STATUT_CHOICES = [("EN_ATTENTE", "En attente"), ("VALIDE", "Validé"), ("REJETE", "Rejeté")]

    id_document = models.AutoField(primary_key=True)
    dossier = models.ForeignKey(Dossier, db_column="id_dossier", on_delete=models.CASCADE,
                                 related_name="documents")
    type_document = models.CharField(max_length=40, choices=TYPE_CHOICES)
    chemin_fichier = models.FileField(upload_to="uploads/", max_length=255)
    statut_validation = models.CharField(max_length=15, choices=STATUT_CHOICES, default="EN_ATTENTE")
    date_upload = models.DateTimeField(auto_now_add=True)
    ajoute_par = models.ForeignKey(Acteur, db_column="ajoute_par", null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="documents_ajoutes")
    demande_liee = models.ForeignKey("DemandeIndemnisation", db_column="demande_liee", null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name="documents_lies")

    @property
    def url_fichier(self):
        """URL publique du fichier — tolère un chemin_fichier hérité stocké en absolu."""
        from django.conf import settings
        chemin = str(self.chemin_fichier or "").replace(str(settings.MEDIA_ROOT), "").lstrip("/\\")
        return f"{settings.MEDIA_URL}{chemin}"

    class Meta:
        managed = False
        db_table = "document"


class DemandeIndemnisation(models.Model):
    STATUT_CHOICES = [("SOUMISE", "Soumise"), ("EN_COURS", "En cours"), ("TRAITEE", "Traitée")]
    TYPE_CHOICES = [("INITIALE", "Initiale"), ("RECOURS", "Recours")]
    PHASE_CHOICES = [
        ("EN_EVALUATION", "En évaluation"),
        ("CONTRE_EXPERTISE_DEMANDEE", "Contre-expertise demandée"),
        ("EXPERTISE_CONTRADICTOIRE", "Expertise contradictoire réalisée"),
        ("OFFRE_TRANSMISE", "Offre transmise"),
        ("OFFRE_ACCEPTEE", "Offre acceptée"),
        ("OFFRE_REFUSEE", "Offre refusée"),
    ]

    id_demande = models.AutoField(primary_key=True)
    dossier = models.ForeignKey(Dossier, db_column="id_dossier", on_delete=models.PROTECT,
                                 related_name="demandes")
    # 🔒 Clé d'isolation pour le rôle Assureur
    assureur = models.ForeignKey(Acteur, db_column="id_assureur", on_delete=models.PROTECT,
                                  related_name="demandes_traitees", limit_choices_to={"role": "assureur"})
    numero_suivi = models.CharField(max_length=30, unique=True)
    montant_reclame = models.DecimalField(max_digits=12, decimal_places=2)
    montant_evalue = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    montant_offre = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    phase = models.CharField(max_length=30, choices=PHASE_CHOICES, default="EN_EVALUATION")
    statut = models.CharField(max_length=15, choices=STATUT_CHOICES, default="SOUMISE")
    type_demande = models.CharField(max_length=10, choices=TYPE_CHOICES, default="INITIALE")
    demande_origine = models.ForeignKey("self", db_column="id_demande_origine", null=True, blank=True,
                                         on_delete=models.SET_NULL, related_name="recours")
    motif_recours = models.TextField(null=True, blank=True)
    date_soumission = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "demande_indemnisation"


class Evaluation(models.Model):
    TYPE_CHOICES = [("CORPOREL", "Corporel"), ("MATERIEL", "Matériel")]

    id_evaluation = models.AutoField(primary_key=True)
    demande = models.ForeignKey(DemandeIndemnisation, db_column="id_demande",
                                 on_delete=models.CASCADE, related_name="evaluations")
    type_prejudice = models.CharField(max_length=10, choices=TYPE_CHOICES)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    observations = models.TextField(null=True, blank=True)
    date_evaluation = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "evaluation"


class Decision(models.Model):
    RESULTAT_CHOICES = [("VALIDEE", "Validée"), ("REJETEE", "Rejetée")]

    id_decision = models.AutoField(primary_key=True)
    demande = models.OneToOneField(DemandeIndemnisation, db_column="id_demande",
                                    on_delete=models.CASCADE, related_name="decision")
    resultat = models.CharField(max_length=10, choices=RESULTAT_CHOICES)
    motif = models.TextField(null=True, blank=True)
    date_decision = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "decision"


class Paiement(models.Model):
    MODE_CHOICES = [("VIREMENT", "Virement"), ("CHEQUE", "Chèque"), ("MOBILE_MONEY", "Mobile Money")]
    TYPE_CHOICES = [("PROVISION", "Provision"), ("DEFINITIF", "Définitif")]
    CONFIRM_CHOICES = [
        ("EN_ATTENTE", "En attente"), ("CONFIRME", "Confirmé"),
        ("CONTESTE", "Contesté"), ("TRANSMIS_ASSUREUR", "Transmis à l'assureur"),
    ]

    id_paiement = models.AutoField(primary_key=True)
    decision = models.OneToOneField(Decision, db_column="id_decision", null=True, blank=True,
                                     on_delete=models.CASCADE, related_name="paiement")
    dossier = models.ForeignKey(Dossier, db_column="id_dossier", null=True, blank=True,
                                 on_delete=models.CASCADE, related_name="provisions")
    montant_paye = models.DecimalField(max_digits=12, decimal_places=2)
    montant_provisions_deduites = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mode_paiement = models.CharField(max_length=15, choices=MODE_CHOICES)
    type_paiement = models.CharField(max_length=10, choices=TYPE_CHOICES, default="DEFINITIF")
    preuve_paiement = models.CharField(max_length=255, null=True, blank=True)
    confirmation_victime = models.BooleanField(default=False)
    statut_confirmation = models.CharField(max_length=20, choices=CONFIRM_CHOICES, default="EN_ATTENTE")
    commentaire_victime = models.TextField(null=True, blank=True)
    date_paiement = models.DateTimeField(auto_now_add=True)
    date_confirmation = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "paiement"


class Notification(models.Model):
    STATUT_CHOICES = [("ENVOYEE", "Envoyée"), ("ECHEC", "Échec"), ("LUE", "Lue")]

    id_notification = models.AutoField(primary_key=True)
    acteur = models.ForeignKey(Acteur, db_column="id_acteur", on_delete=models.CASCADE,
                                related_name="notifications")
    dossier = models.ForeignKey(Dossier, db_column="id_dossier", on_delete=models.CASCADE,
                                 related_name="notifications")
    message = models.TextField()
    statut_envoi = models.CharField(max_length=10, choices=STATUT_CHOICES, default="ENVOYEE")
    date_envoi = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "notification"
