DROP DATABASE IF EXISTS gestion_dossiers_victimes;
CREATE DATABASE gestion_dossiers_victimes
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE gestion_dossiers_victimes;

SET FOREIGN_KEY_CHECKS = 0;


CREATE TABLE acteur (
    id_acteur       INT AUTO_INCREMENT PRIMARY KEY,
    nom             VARCHAR(100)    NOT NULL,
    prenom          VARCHAR(100)    NOT NULL,
    email           VARCHAR(150)    NOT NULL UNIQUE,
    telephone       VARCHAR(20)     NOT NULL,
    mot_de_passe    VARCHAR(255)    NOT NULL,
    role            ENUM('victime', 'assistant', 'assureur', 'administrateur') NOT NULL,
    date_creation   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actif           BOOLEAN         NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;


CREATE TABLE victime (
    id_acteur       INT PRIMARY KEY,
    adresse         VARCHAR(255),
    cni_numero      VARCHAR(50),
    date_naissance  DATE,
    CONSTRAINT fk_victime_acteur FOREIGN KEY (id_acteur)
        REFERENCES acteur(id_acteur) ON DELETE CASCADE
) ENGINE=InnoDB;


CREATE TABLE assistant (
    id_acteur       INT PRIMARY KEY,
    matricule       VARCHAR(50)     UNIQUE,
    zone_intervention VARCHAR(150),
    CONSTRAINT fk_assistant_acteur FOREIGN KEY (id_acteur)
        REFERENCES acteur(id_acteur) ON DELETE CASCADE
) ENGINE=InnoDB;


CREATE TABLE assureur (
    id_acteur           INT PRIMARY KEY,
    nom_compagnie       VARCHAR(150)    NOT NULL,
    numero_agrement_cima VARCHAR(50),
    adresse_siege       VARCHAR(255),
    CONSTRAINT fk_assureur_acteur FOREIGN KEY (id_acteur)
        REFERENCES acteur(id_acteur) ON DELETE CASCADE
) ENGINE=InnoDB;


CREATE TABLE accident (
    id_accident     INT AUTO_INCREMENT PRIMARY KEY,
    date_accident   DATETIME        NOT NULL,
    lieu            VARCHAR(255)    NOT NULL,
    description     TEXT,
    numero_pv       VARCHAR(50)     UNIQUE,
    date_creation   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;


CREATE TABLE dossier (
    id_dossier      INT AUTO_INCREMENT PRIMARY KEY,
    numero_dossier  VARCHAR(30)     NOT NULL UNIQUE,
    id_victime      INT             NOT NULL,
    id_assistant    INT             NOT NULL,
    id_accident     INT             NOT NULL,
    statut          ENUM(
                        'EN_CONSTITUTION',
                        'DOSSIER_COMPLET',
                        'SOUMIS',
                        'EN_EVALUATION',
                        'VALIDE',
                        'REJETE',
                        'PAYE',
                        'CLOTURE'
                    ) NOT NULL DEFAULT 'EN_CONSTITUTION',
    date_creation   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    date_cloture    DATETIME        NULL,
    CONSTRAINT fk_dossier_victime FOREIGN KEY (id_victime)
        REFERENCES victime(id_acteur),
    CONSTRAINT fk_dossier_assistant FOREIGN KEY (id_assistant)
        REFERENCES assistant(id_acteur),
    CONSTRAINT fk_dossier_accident FOREIGN KEY (id_accident)
        REFERENCES accident(id_accident)
) ENGINE=InnoDB;



CREATE TABLE document (
    id_document         INT AUTO_INCREMENT PRIMARY KEY,
    id_dossier          INT             NOT NULL,
    type_document       ENUM(
                            'CNI', 'PASSEPORT', 'PV_POLICE', 'CERTIFICAT_MEDICAL',
                            'FACTURE_MEDICALE', 'PHOTO_ACCIDENT',
                            'ATTESTATION_ASSURANCE', 'RIB', 'AUTRE'
                        ) NOT NULL,
    chemin_fichier      VARCHAR(255)    NOT NULL,
    statut_validation   ENUM('EN_ATTENTE', 'VALIDE', 'REJETE') NOT NULL DEFAULT 'EN_ATTENTE',
    date_upload         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_document_dossier FOREIGN KEY (id_dossier)
        REFERENCES dossier(id_dossier) ON DELETE CASCADE
) ENGINE=InnoDB;


CREATE TABLE demande_indemnisation (
    id_demande          INT AUTO_INCREMENT PRIMARY KEY,
    id_dossier          INT             NOT NULL,
    id_assureur         INT             NOT NULL,
    numero_suivi        VARCHAR(30)     NOT NULL UNIQUE,
    montant_reclame      DECIMAL(12,2)   NOT NULL,
    montant_evalue       DECIMAL(12,2)   NULL,
    statut               ENUM('SOUMISE', 'EN_COURS', 'TRAITEE') NOT NULL DEFAULT 'SOUMISE',
    date_soumission      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_demande_dossier FOREIGN KEY (id_dossier)
        REFERENCES dossier(id_dossier),
    CONSTRAINT fk_demande_assureur FOREIGN KEY (id_assureur)
        REFERENCES assureur(id_acteur)
) ENGINE=InnoDB;


CREATE TABLE evaluation (
    id_evaluation       INT AUTO_INCREMENT PRIMARY KEY,
    id_demande          INT             NOT NULL,
    type_prejudice       ENUM('CORPOREL', 'MATERIEL') NOT NULL,
    montant              DECIMAL(12,2)   NOT NULL,
    observations          TEXT,
    date_evaluation       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_evaluation_demande FOREIGN KEY (id_demande)
        REFERENCES demande_indemnisation(id_demande) ON DELETE CASCADE
) ENGINE=InnoDB;



CREATE TABLE decision (
    id_decision     INT AUTO_INCREMENT PRIMARY KEY,
    id_demande      INT             NOT NULL UNIQUE,
    resultat        ENUM('VALIDEE', 'REJETEE') NOT NULL,
    motif           TEXT,
    date_decision   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_decision_demande FOREIGN KEY (id_demande)
        REFERENCES demande_indemnisation(id_demande) ON DELETE CASCADE
) ENGINE=InnoDB;


CREATE TABLE paiement (
    id_paiement     INT AUTO_INCREMENT PRIMARY KEY,
    id_decision     INT             NOT NULL UNIQUE,
    montant_paye     DECIMAL(12,2)   NOT NULL,
    mode_paiement    ENUM('VIREMENT', 'CHEQUE', 'MOBILE_MONEY') NOT NULL,
    preuve_paiement  VARCHAR(255),
    confirmation_victime BOOLEAN     NOT NULL DEFAULT FALSE,
    date_paiement    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    date_confirmation DATETIME       NULL,
    CONSTRAINT fk_paiement_decision FOREIGN KEY (id_decision)
        REFERENCES decision(id_decision) ON DELETE CASCADE
) ENGINE=InnoDB;


CREATE TABLE notification (
    id_notification INT AUTO_INCREMENT PRIMARY KEY,
    id_acteur       INT             NOT NULL,
    id_dossier      INT             NOT NULL,
    message         TEXT            NOT NULL,
    statut_envoi    ENUM('ENVOYEE', 'ECHEC', 'LUE') NOT NULL DEFAULT 'ENVOYEE',
    date_envoi      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notification_acteur FOREIGN KEY (id_acteur)
        REFERENCES acteur(id_acteur) ON DELETE CASCADE,
    CONSTRAINT fk_notification_dossier FOREIGN KEY (id_dossier)
        REFERENCES dossier(id_dossier) ON DELETE CASCADE
) ENGINE=InnoDB;

SET FOREIGN_KEY_CHECKS = 1;



CREATE INDEX idx_dossier_statut ON dossier(statut);
CREATE INDEX idx_dossier_numero ON dossier(numero_dossier);
CREATE INDEX idx_demande_statut ON demande_indemnisation(statut);
CREATE INDEX idx_acteur_role ON acteur(role);
CREATE INDEX idx_document_dossier ON document(id_dossier);
CREATE INDEX idx_notification_acteur ON notification(id_acteur);


 INSERT INTO acteur (nom, prenom, email, telephone, mot_de_passe, role) VALUES
 ('NDao', 'Mamoudou', 'mamoudou.ndao@email.com', '770000001', 'victime_1', 'victime'),
 ('Cisse', 'Vieux', 'vieux.cisse@email.com', '770000002', 'assistant_1', 'assistant'),
 ('Diop', 'Babacar', 'contact@nsia.sn', '770000003', 'assureur_1', 'assureur'),
 ('Camara', 'Ibrahima', 'admin@plateforme.sn', '784760384', 'admin_1', 'administrateur');

 INSERT INTO victime (id_acteur, adresse, cni_numero, date_naissance) VALUES
 (1, 'Tambacounda, Koussanar', '1234567890123', '2000-01-01');

 INSERT INTO assistant (id_acteur, matricule, zone_intervention) VALUES
 (2, 'AST-001', 'Kaffrine');

 INSERT INTO assureur (id_acteur, nom_compagnie, numero_agrement_cima, adresse_siege) VALUES
 (3, 'NSIA Assurances', 'CIMA-SN-001', 'Dakar, Plateau');
