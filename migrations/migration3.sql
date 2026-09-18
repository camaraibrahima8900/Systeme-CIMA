-- ============================================================
-- Migration 3 : Option A — traçabilité des provisions déduites
-- À exécuter une seule fois dans MySQL
-- ============================================================

ALTER TABLE paiement
    ADD COLUMN montant_provisions_deduites DECIMAL(12,2) NOT NULL DEFAULT 0
        AFTER montant_paye;
