"""Settings for Echo Journal.

Every setting is read from an environment variable (or from the ".env" file on
your own computer), so no password or secret key is ever written in the code.
"""
import hashlib
import os
import secrets
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

PLACEHOLDER_SECRETS = {"", "change-me", "changeme", "replace-me"}


class ConfigError(RuntimeError):
    """A setting is missing or unsafe. The message says how to fix it."""


def _flag(name, default):
    raw = os.environ.get(name, "").strip().lower()
    if raw == "":
        return default
    return raw in {"1", "true", "yes", "on"}


def _number(name, default):
    raw = os.environ.get(name, "").strip()
    if raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, but it is {raw!r}.") from None


def load_config(overrides=None):
    """Build the settings dictionary. `overrides` is used by the tests."""
    overrides = dict(overrides or {})
    environment = os.environ.get("APP_ENV", "development").strip().lower()
    production = environment == "production"

    secret_key = str(overrides.get("SECRET_KEY") or os.environ.get("SECRET_KEY", "")).strip()
    if secret_key.lower() in PLACEHOLDER_SECRETS:
        if production:
            raise ConfigError(
                "SECRET_KEY is missing. Set it to a long random value, for example the output of: "
                'python -c "import secrets; print(secrets.token_hex(32))"'
            )
        secret_key = secrets.token_hex(32)
        print(
            "NOTE: SECRET_KEY is not set in your .env file, so you will be signed out every time "
            "the server restarts. See the README to set it.",
            file=sys.stderr,
        )
    if production and len(secret_key) < 32:
        raise ConfigError("SECRET_KEY is too short. Use at least 32 random characters.")

    cookie_secure = _flag("COOKIE_SECURE", production)

    config = {
        "APP_ENV": environment,
        "SECRET_KEY": secret_key,
        "DATABASE_URL": os.environ.get("DATABASE_URL", "").strip() or "sqlite:///echo_journal.db",
        "AUTO_MIGRATE": _flag("AUTO_MIGRATE", True),
        "ALLOW_REGISTRATION": _flag("ALLOW_REGISTRATION", True),
        "TRUST_PROXY_HEADERS": _flag("TRUST_PROXY_HEADERS", False),
        # scrypt is a slow, memory-hungry hash designed for storing passwords.
        "PASSWORD_HASH_METHOD": "scrypt" if hasattr(hashlib, "scrypt") else "pbkdf2:sha256:600000",
        # Limits
        "ENTRY_MAX_CHARS": 20_000,
        "TITLE_MAX_CHARS": 120,
        "PAGE_SIZE": 10,
        "MAX_CONTENT_LENGTH": 256 * 1024,
        # Sign-in cookie
        "SESSION_COOKIE_NAME": "__Host-echo_session" if cookie_secure else "echo_session",
        "SESSION_COOKIE_SECURE": cookie_secure,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=_number("SESSION_HOURS", 12)),
        "HSTS_ENABLED": cookie_secure,
        "CSRF_ENABLED": True,
    }
    config.update(overrides)
    return config
