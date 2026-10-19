from pathlib import Path

import dj_database_url

from config.env import env_float, env_int, env_list, env_str

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_DIR = BASE_DIR.parent

DEVELOPMENT_SECRET_KEY = "insecure-development-key"  # noqa: S105
SECRET_KEY = env_str("DJANGO_SECRET_KEY", DEVELOPMENT_SECRET_KEY)
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.route_planning",
    "apps.health",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": False,
        "OPTIONS": {},
    }
]

DATABASES = {
    "default": dj_database_url.parse(
        env_str("DATABASE_URL", "postgres:///trucking"),
        conn_max_age=env_int("DATABASE_CONN_MAX_AGE", 60),
        conn_health_checks=True,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# The database cache is shared by every worker, so rate limits, provider
# response caching and planning locks hold across processes without Redis.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
        "TIMEOUT": 1800,
        "OPTIONS": {"MAX_ENTRIES": 20_000, "CULL_FREQUENCY": 4},
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
FRONTEND_DIST_DIR = Path(env_str("FRONTEND_DIST_DIR", str(REPO_DIR / "frontend" / "dist")))
WHITENOISE_ROOT = FRONTEND_DIST_DIR if FRONTEND_DIST_DIR.is_dir() else None

DATA_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "apps.route_planning.api.errors.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "route_plan": env_str("THROTTLE_ROUTE_PLAN", "20/hour"),
        "corridor_forecast": env_str("THROTTLE_CORRIDOR", "60/hour"),
        "geocode": env_str("THROTTLE_GEOCODE", "60/min"),
        "read": env_str("THROTTLE_READ", "240/hour"),
    },
    "NUM_PROXIES": env_int("NUM_PROXIES", 0),
}

PROVIDERS = {
    "VALHALLA_BASE_URL": env_str("VALHALLA_BASE_URL", "https://valhalla1.openstreetmap.de"),
    "OPEN_METEO_BASE_URL": env_str("OPEN_METEO_BASE_URL", "https://api.open-meteo.com"),
    "PHOTON_BASE_URL": env_str("PHOTON_BASE_URL", "https://photon.komoot.io"),
    "USER_AGENT": env_str(
        "PROVIDER_USER_AGENT", "weather-aware-truck-routing/1.0 (+https://github.com/)"
    ),
    "CONNECT_TIMEOUT_SECONDS": env_float("PROVIDER_CONNECT_TIMEOUT", 5.0),
    "READ_TIMEOUT_SECONDS": env_float("PROVIDER_READ_TIMEOUT", 20.0),
    "MAX_RETRIES": env_int("PROVIDER_MAX_RETRIES", 2),
    "WEATHER_CONCURRENCY": env_int("WEATHER_CONCURRENCY", 4, minimum=1),
}

PLANNING = {
    "TRUCK_TARE_WEIGHT_LB": env_int("TRUCK_TARE_WEIGHT_LB", 35_000, minimum=1),
    "PLAN_RETENTION_HOURS": env_int("PLAN_RETENTION_HOURS", 24, minimum=1),
    "WEATHER_CACHE_SECONDS": env_int("WEATHER_CACHE_SECONDS", 1800, minimum=60),
    "GEOCODE_CACHE_SECONDS": env_int("GEOCODE_CACHE_SECONDS", 86_400, minimum=60),
    "ROUTE_CACHE_SECONDS": env_int("ROUTE_CACHE_SECONDS", 3600, minimum=60),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "config.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": env_str("LOG_LEVEL", "INFO")},
    "loggers": {"httpx": {"level": "WARNING"}, "httpcore": {"level": "WARNING"}},
}
