"""Create an account, sign in and sign out."""
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for

from . import repository, security, validation

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=("GET", "POST"))
def register():
    if g.user:
        return redirect(url_for("journal.index"))
    if not current_app.config["ALLOW_REGISTRATION"]:
        return render_template("auth/closed.html"), 403

    username, errors = "", {}
    if request.method == "POST":
        username = validation.normalize_username(request.form.get("username"))
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        errors = validation.check_registration(username, password, confirm)
        if not errors:
            try:
                user_id = repository.create_user(username, security.hash_password(password))
            except repository.UsernameTaken:
                errors["username"] = "That username is already taken. Try another."
            else:
                security.log_in(user_id)
                flash("Welcome. Your journal is ready.", "success")
                return redirect(url_for("journal.index"))
    return render_template("auth/register.html", username=username, errors=errors)


@bp.route("/login", methods=("GET", "POST"))
def login():
    next_url = security.safe_next_url(request.values.get("next"), "")
    if g.user:
        return redirect(next_url or url_for("journal.index"))

    username, error = "", ""
    if request.method == "POST":
        username = validation.normalize_username(request.form.get("username"))
        password = request.form.get("password") or ""
        user = repository.get_user_by_username(username) if username else None
        if user is None:
            security.waste_time_like_a_login(password)
        elif len(password) <= validation.PASSWORD_MAX_LENGTH and security.verify_password(
            password, user["password_hash"]
        ):
            security.log_in(user["id"])
            repository.record_login(user["id"])
            return redirect(next_url or url_for("journal.index"))
        # The same message for "no such user" and "wrong password" on purpose.
        error = "That username and password don't match."
    return render_template("auth/login.html", username=username, error=error, next_url=next_url)


@bp.post("/logout")
def logout():
    security.log_out()
    flash("You're signed out.", "success")
    return redirect(url_for("pages.home"))
