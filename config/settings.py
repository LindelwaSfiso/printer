"""ESprints — Engineering Society e-printing service."""
from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-change-me"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG=0")

ALLOWED_HOSTS = [h.strip() for h in os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]

SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8000").rstrip("/")
CSRF_TRUSTED_ORIGINS = [SITE_URL]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "apps.core",
    "apps.accounts",
    "apps.subscriptions",
    "apps.credits",
    "apps.printing",
    "apps.billing",
    "apps.console",
]

# No django.contrib.admin: the society gets a purpose-built dashboard instead.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "apps.core.context.nav_counts",
    ]},
}]

# SQLite in WAL mode: the web process reads while the worker writes.
# PRAGMAs are applied per connection in apps/core/apps.py, which works on every
# Django version we might land on.
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": BASE_DIR / "db.sqlite3",
    "OPTIONS": {"timeout": 20},
}}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:home"
LOGOUT_REDIRECT_URL = "accounts:login"
PASSWORD_RESET_TIMEOUT = 60 * 60 * 72          # invite links live for 3 days

LANGUAGE_CODE = "en"
TIME_ZONE = "Africa/Mbabane"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------- #
# Static and private documents
# --------------------------------------------------------------------------- #
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Uploaded documents are never public: the folder lives outside the web root and
# MEDIA_URL is deliberately not routed in config/urls.py.
MEDIA_ROOT = BASE_DIR / "private_media"
MEDIA_URL = "/media/"

# --------------------------------------------------------------------------- #
# Business rules
# --------------------------------------------------------------------------- #
CREDITS_PER_RAND = int(os.environ.get("CREDITS_PER_RAND", "10"))   # 10 credits = E1.00
TOPUP_MIN_CENTS = int(os.environ.get("TOPUP_MIN_CENTS", "500"))
TOPUP_MAX_CENTS = int(os.environ.get("TOPUP_MAX_CENTS", "50000"))
INVOICE_TTL_HOURS = int(os.environ.get("INVOICE_TTL_HOURS", "72"))
JOB_EXPIRY_HOURS = int(os.environ.get("JOB_EXPIRY_HOURS", "24"))
LOW_CREDITS_THRESHOLD = int(os.environ.get("LOW_CREDITS_THRESHOLD", "20"))

# Who may print?
#   0 (default) -> any approved, active member with credits. A subscription is
#                  one way to get credits, a top-up is another, and expired
#                  members can still spend the credits they already paid for.
#   1           -> only members with an active subscription may print.
# Printing is always paid for: this switch decides who is *allowed* to try, not
# whether credit is required.
REQUIRE_SUBSCRIPTION_TO_PRINT = os.environ.get(
    "REQUIRE_SUBSCRIPTION_TO_PRINT", "0") == "1"

SOCIETY_NAME = os.environ.get("SOCIETY_NAME", "Engineering Society")
SOCIETY_MOMO_NUMBER = os.environ.get("SOCIETY_MOMO_NUMBER", "+268 7612 3456")
SOCIETY_MOMO_NAME = os.environ.get("SOCIETY_MOMO_NAME", "Engineering Society (UNESWA)")

# --------------------------------------------------------------------------- #
# Printing
# --------------------------------------------------------------------------- #
# pdf  -> render the job to a PDF in private_media/printout (current default:
#         proves the whole queue/billing path without a printer)
# windows -> SumatraPDF to the Windows spooler
# cups     -> lp to a CUPS queue
PRINT_BACKEND = os.environ.get("PRINT_BACKEND", "pdf")
PRINTER_NAME = os.environ.get("PRINTER_NAME", "")
SUMATRA_PATH = os.environ.get("SUMATRA_PATH", r"C:\Program Files\SumatraPDF\SumatraPDF.exe")
WORKER_IDLE_SECONDS = float(os.environ.get("WORKER_IDLE_SECONDS", "2"))
PRINT_TIMEOUT_SECONDS = int(os.environ.get("PRINT_TIMEOUT_SECONDS", "180"))
PRINT_TICKET = os.environ.get("PRINT_TICKET", "1") == "1"

# --------------------------------------------------------------------------- #
# Email — the console backend writes invites to the terminal during development
# --------------------------------------------------------------------------- #
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", f"{SOCIETY_NAME} <no-reply@esprints.local>")

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "{asctime} {levelname} {name}: {message}",
                             "style": "{"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
        "file": {"class": "logging.handlers.RotatingFileHandler",
                 "filename": LOGS_DIR / "esprints.log", "maxBytes": 2_000_000,
                 "backupCount": 3, "formatter": "plain"},
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {"apps": {"handlers": ["console", "file"], "level": "INFO",
                         "propagate": False}},
}

# Dev-only conveniences
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
