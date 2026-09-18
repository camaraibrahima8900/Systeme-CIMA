-- ============================================================
-- Migration 2 : Recours, lettres de décision, offre provisionnelle
-- À exécuter une seule fois dans MySQL
-- ============================================================

-- 1) Traçabilité des recours (demande liée à une demande d'origine rejetée)
ALTER TABLE demande_indemnisation
    ADD COLUMN type_demande ENUM('INITIALE','RECOURS') NOT NULL DEFAULT 'INITIALE' AFTER statut,
    ADD COLUMN id_demande_origine INT NULL AFTER type_demande,
    ADD COLUMN motif_recours TEXT NULL AFTER id_demande_origine,
    ADD CONSTRAINT fk_demande_origine FOREIGN KEY (id_demande_origine)
        REFERENCES demande_indemnisation(id_demande);

-- 2) Nouveau type de document : lettre de décision (validation ou rejet)
ALTER TABLE document
    MODIFY COLUMN type_document ENUM(
        'CNI','PASSEPORT','PV_POLICE','CERTIFICAT_MEDICAL',
        'FACTURE_MEDICALE','PHOTO_ACCIDENT','ATTESTATION_ASSURANCE',
        'RIB','AUTRE','LETTRE_DECISION'
    ) NOT NULL;

-- 3) Paiement : autoriser une offre provisionnelle (avant décision définitive)
ALTER TABLE paiement
    MODIFY COLUMN id_decision INT NULL,
    ADD COLUMN id_dossier INT NULL AFTER id_decision,
    ADD COLUMN type_paiement ENUM('PROVISION','DEFINITIF') NOT NULL DEFAULT 'DEFINITIF' AFTER mode_paiement,
    ADD CONSTRAINT fk_paiement_dossier FOREIGN KEY (id_dossier)
        REFERENCES dossier(id_dossier);
