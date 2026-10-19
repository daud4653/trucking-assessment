import os

from django.core.exceptions import ImproperlyConfigured


def env_str(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None or value == "":
        raise ImproperlyConfigured(f"Environment variable {name} is required.")
    return value


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"Environment variable {name} must be a boolean.")


def env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(f"Environment variable {name} must be an integer.") from exc
    if value < minimum:
        raise ImproperlyConfigured(f"Environment variable {name} must be >= {minimum}.")
    return value


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(f"Environment variable {name} must be a number.") from exc
    if value <= 0:
        raise ImproperlyConfigured(f"Environment variable {name} must be positive.")
    return value


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]
