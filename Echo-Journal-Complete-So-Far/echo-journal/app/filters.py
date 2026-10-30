"""Small helpers for the page templates."""
import re

from markupsafe import Markup, escape

_UTC_TEXT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def as_time(value, kind="datetime"):
    """Show a stored UTC time. A little script (static/js/local-time.js) swaps it for the
    reader's own time zone; without JavaScript the UTC text below stays visible."""
    text = str(value or "")
    if not _UTC_TEXT.fullmatch(text):
        return escape(text)
    fallback = text[:10] if kind == "date" else f"{text[:10]} {text[11:16]} UTC"
    return Markup('<time class="local-time" datetime="{}" data-format="{}">{}</time>').format(text, kind, fallback)


def excerpt(value, length=220):
    """The start of an entry on one line, cut at a word boundary."""
    text = " ".join(str(value or "").split())
    if len(text) <= length:
        return text
    cut = text[:length].rsplit(" ", 1)[0] or text[:length]
    return cut.rstrip(" ,.;:") + "…"


def init_app(app):
    app.jinja_env.filters["as_time"] = as_time
    app.jinja_env.filters["excerpt"] = excerpt
