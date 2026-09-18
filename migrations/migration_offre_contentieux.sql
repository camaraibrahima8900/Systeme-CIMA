-- Ajoute le statut CONTENTIEUX au dossier (remplace la liste par les valeurs EXACTES
-- retournées par `SHOW COLUMNS FROM dossier LIKE 'statut';` si elles diffèrent)
ALTER TABLE dossier MODIFY COLUMN statut
  ENUM('EN_CONSTITUTION','DOSSIER_COMPLET','SOUMIS','EN_EVALUATION','VALIDE',
       'REJETE','PAYE','CLOTURE','CONTENTIEUX')
  NOT NULL DEFAULT 'EN_CONSTITUTION';

-- Ajoute le suivi de la négociation (contre-expertise / offre) sur la demande
ALTER TABLE demande_indemnisation
  ADD COLUMN phase VARCHAR(30) NOT NULL DEFAULT 'EN_EVALUATION',
  ADD COLUMN montant_offre DECIMAL(12,2) NULL;
