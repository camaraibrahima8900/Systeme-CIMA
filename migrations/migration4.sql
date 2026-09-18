-- ============================================================
-- Migration 4 : colonne username pour résolution fiable
-- des comptes Keycloak (corrige les usernames sans point,
-- ex: camaraibrahima8900)
-- ============================================================

ALTER TABLE acteur
    ADD COLUMN username VARCHAR(100) NULL UNIQUE AFTER email;
