"""Checks for everything a person types into a form."""
import re
import unicodedata

USERNAME_PATTERN = re.compile(r"[a-z0-9_]{3,32}")
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128


def normalize_username(raw):
    return (raw or "").strip().lower()


def normalize_password(raw):
    """Look-alike characters from different keyboards end up hashed the same way."""
    return unicodedata.normalize("NFKC", raw or "")


def check_registration(username, password, confirm):
    """Return a dict of problems, keyed by field name. An empty dict means all good."""
    errors = {}
    if not USERNAME_PATTERN.fullmatch(username):
        errors["username"] = "Use 3 to 32 letters, numbers or underscores. No spaces."
    if len(password) < PASSWORD_MIN_LENGTH:
        errors["password"] = f"Use at least {PASSWORD_MIN_LENGTH} characters. A few random words work well."
    elif len(password) > PASSWORD_MAX_LENGTH:
        errors["password"] = f"Use {PASSWORD_MAX_LENGTH} characters or fewer."
    elif password.strip().lower() == username:
        errors["password"] = "Your password can't be the same as your username."
    elif password != confirm:
        errors["confirm"] = "The two passwords don't match."
    return errors


def _tidy(text):
    """Same line endings everywhere, and no NUL characters (databases dislike them)."""
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")


def check_entry(raw_title, raw_body, max_title, max_body):
    """Clean up a journal entry. Returns (title, body, errors)."""
    title = " ".join(_tidy(raw_title).split())  # one line, single spaces
    body = _tidy(raw_body).strip()
    errors = {}
    if len(title) > max_title:
        errors["title"] = f"Titles can be up to {max_title} characters. This one has {len(title)}."
    if not body:
        errors["body"] = "Write something before you save."
    elif len(body) > max_body:
        errors["body"] = f"Entries can be up to {max_body:,} characters. This one has {len(body):,}."
    return title, body, errors
