-- ============================================================
-- Migration 5 : cloisonnement par périmètre (zone / assureur)
-- ============================================================

-- 1) Ajout de la zone sur le dossier (héritée de l'assistant à la création)
ALTER TABLE dossier
    ADD COLUMN zone VARCHAR(150) NULL AFTER id_accident;

-- 2) Rétro-remplissage des dossiers existants depuis la zone de leur assistant
UPDATE dossier d
JOIN assistant a ON d.id_assistant = a.id_acteur
SET d.zone = a.zone_intervention
WHERE d.zone IS NULL;

-- 3) Index pour accélérer le filtrage par zone (utilisé à chaque requête assistant)
CREATE INDEX idx_dossier_zone ON dossier(zone);

-- 4) Index pour accélérer le filtrage assureur (déjà lié via demande_indemnisation)
CREATE INDEX idx_demande_assureur_dossier ON demande_indemnisation(id_assureur, id_dossier);
