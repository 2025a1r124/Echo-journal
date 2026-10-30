"""Journal pages: list and search, write, read, edit, delete and export."""
import json

from flask import Blueprint, Response, abort, current_app, flash, g, redirect, render_template, request, url_for

from . import ai_analysis, db, repository, validation
from .security import login_required

bp = Blueprint("journal", __name__)


def _own_entry_or_404(entry_id):
    """Fetch one of the signed-in person's entries. Anyone else's entry looks like it doesn't exist."""
    entry = repository.get_entry(g.user["id"], entry_id)
    if entry is None:
        abort(404)
    return entry


def _requested_page():
    try:
        return max(1, int(request.args.get("page", "1")))
    except ValueError:
        return 1


def _check_submitted_entry():
    return validation.check_entry(
        request.form.get("title"),
        request.form.get("body"),
        current_app.config["TITLE_MAX_CHARS"],
        current_app.config["ENTRY_MAX_CHARS"],
    )


@bp.get("/journal")
@login_required
def index():
    query = request.args.get("q", "").strip()[:100]
    size = current_app.config["PAGE_SIZE"]
    total = repository.count_entries(g.user["id"], query)
    page_count = max(1, -(-total // size))
    page = min(_requested_page(), page_count)
    entries = repository.list_entries(g.user["id"], query, size, (page - 1) * size)
    return render_template(
        "journal/index.html", entries=entries, q=query, page=page, page_count=page_count, total=total
    )


@bp.route("/journal/new", methods=("GET", "POST"))
@login_required
def new():
    values, errors = {"title": "", "body": ""}, {}
    if request.method == "POST":
        title, body, errors = _check_submitted_entry()
        values = {"title": title, "body": body}
        if not errors:
            entry_id = repository.create_entry(g.user["id"], title, body)
            flash("Entry saved.", "success")
            return redirect(url_for("journal.view", entry_id=entry_id))
    return render_template(
        "journal/form.html", heading="New entry", values=values, errors=errors, cancel_url=url_for("journal.index")
    )


@bp.get("/journal/<int:entry_id>")
@login_required
def view(entry_id):
    entry = _own_entry_or_404(entry_id)
    entry["analysis"] = ai_analysis.deserialize_analysis(entry.get("analysis_json"))
    return render_template("journal/view.html", entry=entry)


@bp.post("/journal/<int:entry_id>/analyze")
@login_required
def analyze(entry_id):
    """Run local NLP only after an explicit action by the signed-in owner."""
    entry = _own_entry_or_404(entry_id)
    try:
        result = ai_analysis.analyze_text(entry["body"])
    except ValueError as error:
        flash(str(error), "error")
    except ai_analysis.AIUnavailable as error:
        flash(str(error), "error")
    else:
        repository.save_entry_analysis(g.user["id"], entry_id, ai_analysis.serialize_analysis(result))
        flash("AI reflection analysis saved. It is an estimate, not a diagnosis.", "success")
    return redirect(url_for("journal.view", entry_id=entry_id))


@bp.route("/journal/<int:entry_id>/edit", methods=("GET", "POST"))
@login_required
def edit(entry_id):
    entry = _own_entry_or_404(entry_id)
    values, errors = {"title": entry["title"], "body": entry["body"]}, {}
    if request.method == "POST":
        title, body, errors = _check_submitted_entry()
        values = {"title": title, "body": body}
        if not errors:
            repository.update_entry(g.user["id"], entry_id, title, body)
            flash("Changes saved.", "success")
            return redirect(url_for("journal.view", entry_id=entry_id))
    return render_template(
        "journal/form.html",
        heading="Edit entry",
        values=values,
        errors=errors,
        cancel_url=url_for("journal.view", entry_id=entry_id),
    )


@bp.route("/journal/<int:entry_id>/delete", methods=("GET", "POST"))
@login_required
def delete(entry_id):
    entry = _own_entry_or_404(entry_id)
    if request.method == "POST":
        repository.delete_entry(g.user["id"], entry_id)
        flash("Entry deleted.", "success")
        return redirect(url_for("journal.index"))
    return render_template("journal/delete.html", entry=entry)  # GET only asks "are you sure?"


# --- export -----------------------------------------------------------------


def _download(text, mimetype, extension):
    response = Response(text, mimetype=mimetype)
    filename = f"echo-journal-{db.now_utc()[:10]}.{extension}"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@bp.get("/journal/export.json")
@login_required
def export_json():
    entries = repository.all_entries(g.user["id"])
    payload = {
        "app": "Echo Journal",
        "exported_at": db.now_utc(),
        "username": g.user["username"],
        "entry_count": len(entries),
        "entries": entries,
    }
    return _download(json.dumps(payload, ensure_ascii=False, indent=2), "application/json", "json")


@bp.get("/journal/export.md")
@login_required
def export_markdown():
    entries = repository.all_entries(g.user["id"])
    parts = [f"# Echo Journal export\n\nExported {db.now_utc()} for {g.user['username']}. {len(entries)} entries.\n"]
    for entry in entries:
        parts.append(f"\n---\n\n## {entry['title'] or 'Untitled'}\n\n*Written {entry['created_at']}*\n\n{entry['body']}\n")
    return _download("".join(parts), "text/markdown", "md")
