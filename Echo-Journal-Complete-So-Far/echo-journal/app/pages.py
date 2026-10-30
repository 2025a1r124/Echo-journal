"""Pages anyone can open: the start page, the about page and a health check."""
from flask import Blueprint, g, jsonify, redirect, render_template, url_for

bp = Blueprint("pages", __name__)


@bp.get("/")
def home():
    if g.user:
        return redirect(url_for("journal.index"))
    return render_template("home.html")


@bp.get("/about")
def about():
    return render_template("about.html")


@bp.get("/healthz")
def healthz():
    """Hosting services call this to check the site is running. It touches no personal data."""
    return jsonify(status="ok")
