from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key-change-in-production")

DEBUG = os.getenv("DEBUG", "True") == "True"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    # Local
    "trades",
    "ohlcv",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "core.wsgi.application"

# ── Database ──────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME":     os.getenv("DB_NAME",     "solara_quant"),
        "USER":     os.getenv("DB_USER",     "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
        "HOST":     os.getenv("DB_HOST",     "localhost"),
        "PORT":     os.getenv("DB_PORT",     "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── REST Framework ─────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
}

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:5174,http://localhost:3000",
).split(",")

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL         = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND     = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT     = ["json"]
CELERY_TASK_SERIALIZER    = "json"
CELERY_RESULT_SERIALIZER  = "json"
CELERY_TIMEZONE           = "UTC"

# django-celery-beat: stores schedules in the DB (manageable via admin)
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

INSTALLED_APPS += [
    "django_celery_beat",
    "django_celery_results",
]

CELERY_RESULT_BACKEND = "django-db"

# ── Celery Beat schedule ───────────────────────────────────────────────────────
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Insert M15 candles — 1 minute after each M15 close (:00 :15 :30 :45)
    "ohlcv-insert-m15": {
        "task":     "ohlcv.insert_m15",
        "schedule": crontab(minute="1,16,31,46"),
    },
    # Insert H1 candles — 1 minute after each hour closes
    "ohlcv-insert-h1": {
        "task":     "ohlcv.insert_h1",
        "schedule": crontab(minute=1),
    },
    # Insert H4 candles — 1 minute after each H4 session closes
    "ohlcv-insert-h4": {
        "task":     "ohlcv.insert_h4",
        "schedule": crontab(minute=1, hour="0,4,8,12,16,20"),
    },
    # Insert D1 candles — 1 minute after forex daily close (22:00 UTC)
    "ohlcv-insert-d1": {
        "task":     "ohlcv.insert_d1",
        "schedule": crontab(minute=1, hour=22),
    },
    # Insert W1 candles — 1 minute after weekly close (Friday 22:00 UTC)
    "ohlcv-insert-w1": {
        "task":     "ohlcv.insert_w1",
        "schedule": crontab(minute=1, hour=22, day_of_week=4),
    },
    # Gap check + fix — daily safety net at 23:00 UTC
    # After first run, known closures are cached so this becomes very fast
    "ohlcv-gap-check-daily": {
        "task":     "ohlcv.check_and_fix_gaps",
        "schedule": crontab(minute=0, hour=23),
    },
}
