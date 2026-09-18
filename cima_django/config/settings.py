"""
Configuration Django — Système CIMA
Connecte le projet à la base MySQL EXISTANTE (celle déjà utilisée par le
prototype Tkinter) et délègue l'authentification à Keycloak via OpenID Connect.
"""

from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="change-moi-en-production")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "mozilla_django_oidc",   # authentification Keycloak (OpenID Connect)
    "core",                  # application métier CIMA
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "core.middleware.ProfilCimaMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.notifications_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ============================================================
# BASE DE DONNÉES — la même base MySQL que le prototype Tkinter
# ============================================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("DB_NAME", default="gestion_dossiers_victimes"),
        "USER": config("DB_USER", default="ibrahima"),
        "PASSWORD": config("DB_PASSWORD", default="8900"),
        "HOST": config("DB_HOST", default="mysql"),
        "PORT": config("DB_PORT", default="3306"),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

AUTH_PASSWORD_VALIDATORS = []  # les mots de passe sont gérés par Keycloak, pas par Django

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Dakar"

# ============================================================
# Envoi d'emails réels — notifications aux acteurs (Gmail SMTP)
# ============================================================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default=f"Système CIMA <{EMAIL_HOST_USER}>")
SITE_URL_PUBLIC = config("SITE_URL_PUBLIC", default="https://localhost")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/documents/"
MEDIA_ROOT = BASE_DIR / "documents_stockes"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================================================
# AUTHENTIFICATION — Keycloak via OpenID Connect
# ============================================================
AUTHENTICATION_BACKENDS = (
    "core.auth.CimaKeycloakBackend",
    "django.contrib.auth.backends.ModelBackend",
)

KEYCLOAK_URL_INTERNAL = config("KEYCLOAK_URL_INTERNAL", default="http://cima-auth:8080")
KEYCLOAK_URL_PUBLIC   = config("KEYCLOAK_URL_PUBLIC", default="http://cima-auth:8080")
KEYCLOAK_REALM = config("KEYCLOAK_REALM", default="cima")

KC_ADMIN_CLIENT_ID     = config("KC_ADMIN_CLIENT_ID", default="cima-service")
KC_ADMIN_CLIENT_SECRET = config("KC_ADMIN_CLIENT_SECRET", default="")

OIDC_RP_CLIENT_ID = config("OIDC_RP_CLIENT_ID", default="cima-django")
OIDC_RP_CLIENT_SECRET = config("OIDC_RP_CLIENT_SECRET", default="")
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_AUTH_REQUEST_EXTRA_PARAMS = {"prompt": "login"}
OIDC_STORE_ID_TOKEN = True  # nécessaire pour la déconnexion complète côté Keycloak

# Redirige le NAVIGATEUR — doit être une adresse accessible depuis Windows
OIDC_OP_AUTHORIZATION_ENDPOINT = f"{KEYCLOAK_URL_PUBLIC}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"

# Appels faits par Django LUI-MÊME (dans le conteneur) — adresse interne Docker
OIDC_OP_TOKEN_ENDPOINT = f"{KEYCLOAK_URL_INTERNAL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
OIDC_OP_USER_ENDPOINT = f"{KEYCLOAK_URL_INTERNAL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
OIDC_OP_JWKS_ENDPOINT = f"{KEYCLOAK_URL_INTERNAL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"

LOGIN_URL = "oidc_authentication_init"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
CSRF_TRUSTED_ORIGINS = ['https://localhost', 'https://cima-auth:8443']