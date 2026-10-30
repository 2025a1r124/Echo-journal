"""Security helpers: passwords, sign-in, CSRF protection, safe redirects and browser security headers."""
import functools
import hmac
import secrets
from urllib.parse import urlsplit

from flask import current_app, g, redirect, request, session, url_for
from werkzeug.exceptions import BadRequest
from werkzeug.security import check_password_hash, generate_password_hash

from . import repository, validation

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# The browser may only load scripts, styles and images that come from this very site.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


class CSRFError(BadRequest):
    description = "This form expired or didn't come from this site. Reload the page and try again."


# --- passwords --------------------------------------------------------------


def hash_password(password):
    return generate_password_hash(
        validation.normalize_password(password), method=current_app.config["PASSWORD_HASH_METHOD"]
    )


def verify_password(password, stored_hash):
    return check_password_hash(stored_hash, validation.normalize_password(password))


_decoy_hash = None


def waste_time_like_a_login(password):
    """When a username doesn't exist we still do the slow hashing work, so nobody can
    tell 'no such user' from 'wrong password' by timing the response."""
    global _decoy_hash
    if _decoy_hash is None:
        _decoy_hash = generate_password_hash(
            secrets.token_hex(16), method=current_app.config["PASSWORD_HASH_METHOD"]
        )
    check_password_hash(_decoy_hash, validation.normalize_password(password))


# --- signing in -------------------------------------------------------------


def log_in(user_id):
    session.clear()  # never reuse a session from before sign-in
    session["uid"] = int(user_id)
    session.permanent = True


def log_out():
    session.clear()


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if request.method == "GET":
                return redirect(url_for("auth.login", next=request.path))
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def safe_next_url(target, fallback):
    """Only follow a 'next' address that stays on this site (prevents open redirects)."""
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return fallback
    if any(ord(character) < 32 for character in target):
        return fallback
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return fallback
    return target


# --- CSRF protection --------------------------------------------------------
# A forged form on another website can't know this secret value, so it can't
# make your browser change your journal.


def csrf_token():
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def _check_csrf():
    expected = session.get("_csrf", "")
    sent = request.form.get("csrf_token", "") or request.headers.get("X-CSRF-Token", "")
    if not expected or not sent or not hmac.compare_digest(expected.encode(), sent.encode()):
        raise CSRFError()


# --- hooks that run on every request ----------------------------------------


def _before_request():
    g.user = None
    if request.endpoint in (None, "static"):
        return
    user_id = session.get("uid")
    if user_id is not None:
        user = repository.get_user(user_id) if isinstance(user_id, int) else None
        if user is None:
            session.pop("uid", None)  # the account no longer exists
        else:
            g.user = user
    if current_app.config["CSRF_ENABLED"] and request.method in UNSAFE_METHODS:
        _check_csrf()


def _add_security_headers(response):
    headers = response.headers
    headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Referrer-Policy", "no-referrer")
    headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
    headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    if current_app.config["HSTS_ENABLED"]:
        headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.endpoint != "static":
        headers["Cache-Control"] = "no-store"  # private pages should not be kept in browser or proxy caches
    return response


def init_app(app):
    app.before_request(_before_request)
    app.after_request(_add_security_headers)
    app.context_processor(lambda: {"csrf_token": csrf_token})
