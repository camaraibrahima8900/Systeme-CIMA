-- ============================================================
-- Migration : suivi de confirmation/contestation des paiements
-- À exécuter une seule fois dans MySQL
-- ============================================================

ALTER TABLE paiement
    ADD COLUMN statut_confirmation ENUM('EN_ATTENTE','CONFIRME','CONTESTE','TRANSMIS_ASSUREUR')
        NOT NULL DEFAULT 'EN_ATTENTE' AFTER confirmation_victime,
    ADD COLUMN commentaire_victime TEXT NULL AFTER statut_confirmation;
