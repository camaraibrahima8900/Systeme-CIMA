-- Traçabilité : qui a ajouté le document, et à quelle demande il est éventuellement lié
ALTER TABLE document
  ADD COLUMN ajoute_par INT NULL,
  ADD COLUMN demande_liee INT NULL,
  ADD CONSTRAINT fk_document_ajoute_par
      FOREIGN KEY (ajoute_par) REFERENCES acteur(id_acteur) ON DELETE SET NULL,
  ADD CONSTRAINT fk_document_demande_liee
      FOREIGN KEY (demande_liee) REFERENCES demande_indemnisation(id_demande) ON DELETE SET NULL;

-- Nouveaux types de documents pour l'échange d'expertise (remplace liste complète existante)
ALTER TABLE document MODIFY COLUMN type_document
  ENUM('CNI','PASSEPORT','PV_POLICE','CERTIFICAT_MEDICAL','FACTURE_MEDICALE',
       'PHOTO_ACCIDENT','ATTESTATION_ASSURANCE','RIB','AUTRE','LETTRE_DECISION',
       'QUITTANCE','DEMANDE_PROVISION',
       'RAPPORT_EXPERTISE_INITIALE','RAPPORT_CONTRE_EXPERTISE','REPONSE_ASSUREUR_CONTRE_EXPERTISE')
  NOT NULL;
