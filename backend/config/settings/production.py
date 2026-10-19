from django.core.exceptions import ImproperlyConfigured

from config.env import env_bool, env_int, env_str

from .base import *  # noqa: F403

SECRET_KEY = env_str("DJANGO_SECRET_KEY")
if SECRET_KEY == DEVELOPMENT_SECRET_KEY or len(SECRET_KEY) < 40:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a unique value of 40+ characters.")
if not ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")

DEBUG = False
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]
if env_bool("TRUST_X_FORWARDED_PROTO", True):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31_536_000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"
