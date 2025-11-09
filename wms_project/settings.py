import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE_DIR = Path(__file__).resolve().parent.parent


# ----- Environment helpers -----
def get_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-secret-key")
DEBUG = get_bool("DJANGO_DEBUG", True)

_hosts_env = os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
ALLOWED_HOSTS = [h.strip() for h in _hosts_env.split(",") if h.strip()]



# ----- Applications -----
INSTALLED_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "import_export",
    "django_q",
    # Local apps
    "inventory",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "wms_project.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "wms_project.wsgi.application"
ASGI_APPLICATION = "wms_project.asgi.application"


# ----- Database -----
def database_config_from_url(url: str):
    p = urlparse(url)
    scheme = p.scheme.lower()
    query = parse_qs(p.query)

    if scheme in {"postgres", "postgresql", "postgresql+psycopg2"}:
        engine = "django.db.backends.postgresql"
    elif scheme in {"mysql"}:
        engine = "django.db.backends.mysql"
    elif scheme in {"sqlite", "sqlite3"}:
        engine = "django.db.backends.sqlite3"
    else:
        # Fallback assume postgres
        engine = "django.db.backends.postgresql"

    if engine.endswith("sqlite3"):
        # sqlite:///absolute/path or sqlite:///<relative>
        db_path = p.path or ""
        if not db_path or db_path in {"/", ""}:
            name = BASE_DIR / "db.sqlite3"
        else:
            name = db_path.lstrip("/") if os.name == "nt" else db_path
        return {
            "ENGINE": engine,
            "NAME": str(name),
        }

    name = p.path.lstrip("/") or os.getenv("POSTGRES_DB", "postgres")
    cfg = {
        "ENGINE": engine,
        "NAME": name,
        "USER": p.username or "",
        "PASSWORD": p.password or "",
        "HOST": p.hostname or "localhost",
        "PORT": str(p.port or ""),
    }
    # Optional SSL and options
    options = {}
    sslmode = (query.get("sslmode") or [None])[0]
    if sslmode:
        options["sslmode"] = sslmode
    if options:
        cfg["OPTIONS"] = options
    return cfg


DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {"default": database_config_from_url(DATABASE_URL)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ----- Password validation -----
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ----- Internationalization -----
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# ----- Static and media -----
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []


# ----- Email -----
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")


# ----- DRF -----
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}


# ----- Celery (skeleton) -----
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")


# ----- Django-Q (ORM broker for dev/local) -----
Q_CLUSTER = {
    "name": "wms_project",
    "workers": int(os.getenv("DJANGO_Q_WORKERS", "2")),
    "timeout": int(os.getenv("DJANGO_Q_TIMEOUT", "60")),
    "retry": int(os.getenv("DJANGO_Q_RETRY", "120")),
    "queue_limit": int(os.getenv("DJANGO_Q_QUEUE_LIMIT", "50")),
    "bulk": int(os.getenv("DJANGO_Q_BULK", "10")),
    "label": "Django Q",
    "orm": "default",  # Use Django ORM as the broker
}


# ----- Logging -----
LOG_LEVEL = "DEBUG" if DEBUG else os.getenv("DJANGO_LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[%(levelname)s] %(name)s: %(message)s"},
        "verbose": {
            "format": "%(asctime)s [%(levelname)s] %(name)s (%(module)s:%(lineno)d): %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple" if DEBUG else "verbose",
        }
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
}


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
