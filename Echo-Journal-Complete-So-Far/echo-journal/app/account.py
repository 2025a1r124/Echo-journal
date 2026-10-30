"""The account page: download your data or delete your account."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from . import repository, security
from .security import login_required

bp = Blueprint("account", __name__)


def _render(errors=None):
    return render_template(
        "account/index.html", entry_count=repository.count_entries(g.user["id"]), errors=errors or {}
    )


@bp.get("/account")
@login_required
def index():
    return _render()


@bp.post("/account/delete")
@login_required
def delete():
    password = request.form.get("password") or ""
    confirm = (request.form.get("confirm") or "").strip().upper()
    errors = {}
    if confirm != "DELETE":
        errors["confirm"] = "Type the word DELETE to confirm."
    if not security.verify_password(password, g.user["password_hash"]):
        errors["password"] = "That password isn't right."
    if errors:
        return _render(errors)
    repository.delete_user(g.user["id"])  # entries go with it
    security.log_out()
    flash("Your account and every entry in it have been deleted.", "success")
    return redirect(url_for("pages.home"))
