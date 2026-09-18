CREATE DATABASE IF NOT EXISTS keycloak_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON keycloak_db.* TO 'ibrahima'@'%';
FLUSH PRIVILEGES;
