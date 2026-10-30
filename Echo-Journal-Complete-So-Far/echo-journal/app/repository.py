"""Every question we ask the database lives here.

Rules that keep journals private:
* Every function that touches journal entries takes the owner's user_id and
  puts `user_id = ?` in its SQL. There is deliberately no function that fetches
  an entry by its id alone.
* No admin screen uses this file for entries. Admin statistics (a later
  milestone) will live in their own file and will only count things; they will
  never select entry text.
"""
from . import db


class UsernameTaken(Exception):
    """That username already exists."""


# --- people ---------------------------------------------------------------


def create_user(username, password_hash):
    try:
        return db.insert(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, db.now_utc()),
        )
    except db.IntegrityError as error:
        raise UsernameTaken(username) from error


def get_user(user_id):
    return db.query_one(
        "SELECT id, username, password_hash, is_admin, created_at, last_login_at FROM users WHERE id = ?",
        (user_id,),
    )


def get_user_by_username(username):
    return db.query_one(
        "SELECT id, username, password_hash, is_admin, created_at, last_login_at FROM users WHERE username = ?",
        (username,),
    )


def record_login(user_id):
    db.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (db.now_utc(), user_id))


def delete_user(user_id):
    """Deletes the account. The database deletes all of that person's entries with it."""
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))


# --- journal entries (always for ONE owner) ---------------------------------


def create_entry(user_id, title, body):
    now = db.now_utc()
    return db.insert(
        "INSERT INTO journal_entries (user_id, title, body, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, title, body, now, now),
    )


def get_entry(user_id, entry_id):
    return db.query_one(
        "SELECT id, title, body, created_at, updated_at, analysis_json, analyzed_at "
        "FROM journal_entries WHERE id = ? AND user_id = ?",
        (entry_id, user_id),
    )


def update_entry(user_id, entry_id, title, body):
    changed = db.execute(
        "UPDATE journal_entries SET title = ?, body = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (title, body, db.now_utc(), entry_id, user_id),
    )
    return changed > 0


def delete_entry(user_id, entry_id):
    changed = db.execute("DELETE FROM journal_entries WHERE id = ? AND user_id = ?", (entry_id, user_id))
    return changed > 0


def _search_filter(query):
    """SQL for 'title or body contains the search words'. Only fixed text goes into the SQL;
    what the person typed travels separately as a parameter, with % and _ made literal."""
    if not query:
        return "", ()
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = "%" + escaped + "%"
    clause = " AND (LOWER(title) LIKE LOWER(?) ESCAPE '\\' OR LOWER(body) LIKE LOWER(?) ESCAPE '\\')"
    return clause, (pattern, pattern)


def count_entries(user_id, query=""):
    clause, params = _search_filter(query)
    row = db.query_one(
        "SELECT COUNT(*) AS total FROM journal_entries WHERE user_id = ?" + clause,
        (user_id, *params),
    )
    return row["total"]


def list_entries(user_id, query, limit, offset):
    """Newest first. Returns a short `preview` of the body, not the whole text."""
    clause, params = _search_filter(query)
    return db.query_all(
        "SELECT id, title, SUBSTR(body, 1, 400) AS preview, created_at, updated_at "
        "FROM journal_entries WHERE user_id = ?" + clause + " "
        "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        (user_id, *params, limit, offset),
    )


def all_entries(user_id):
    """Everything this person wrote, oldest first (used for export)."""
    return db.query_all(
        "SELECT id, title, body, created_at, updated_at FROM journal_entries "
        "WHERE user_id = ? ORDER BY created_at ASC, id ASC",
        (user_id,),
    )


def save_entry_analysis(user_id, entry_id, analysis_json):
    """Save only derived labels for an entry owned by this user."""
    changed = db.execute(
        "UPDATE journal_entries SET analysis_json = ?, analyzed_at = ? WHERE id = ? AND user_id = ?",
        (analysis_json, db.now_utc(), entry_id, user_id),
    )
    return changed > 0
