"""The one place that talks to the database.

Today this uses SQLite, which comes with Python, so there is nothing extra to
install and the whole database is a single file (instance/echo_journal.db).
When we put the site online, THIS file is the one that gets a PostgreSQL
version; the rest of the app does not change, because everything else asks for
data through the four helpers below: query_one, query_all, execute and insert.

Always pass values as `?` parameters. Never build SQL by joining strings
together; that is what protects the site from SQL injection.
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, g

SCHEMA_FOLDER = Path(__file__).parent / "schema" / "sqlite"

IntegrityError = sqlite3.IntegrityError


class DatabaseConfigError(RuntimeError):
    """DATABASE_URL is wrong. The message explains how to fix it."""


def now_utc():
    """The current time as text like 2026-10-11T09:30:00Z (always UTC, sorts correctly)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def database_path(url, instance_path):
    """Turn DATABASE_URL into a file path."""
    if url.startswith(("postgres://", "postgresql://")):
        raise DatabaseConfigError(
            "PostgreSQL is not switched on yet; it is added in the deployment milestone. "
            "For now use DATABASE_URL=sqlite:///echo_journal.db"
        )
    if not url.startswith("sqlite:///"):
        raise DatabaseConfigError("DATABASE_URL must look like sqlite:///echo_journal.db")
    raw = url[len("sqlite:///"):]
    if raw in ("", ":memory:"):
        raise DatabaseConfigError("In-memory databases are not supported. Use a file name such as echo_journal.db")
    path = Path(raw)
    if not path.is_absolute():
        path = Path(instance_path) / path
    return path


def migrate(path):
    """Apply every schema file that has not been applied yet, in filename order."""
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        done = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
        for file in sorted(SCHEMA_FOLDER.glob("*.sql")):
            if file.name in done:
                continue
            connection.executescript(file.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (file.name, now_utc())
            )
            connection.commit()
    finally:
        connection.close()


def init_app(app):
    path = database_path(app.config["DATABASE_URL"], app.instance_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    app.config["DATABASE_PATH"] = str(path)
    app.teardown_appcontext(_close_connection)

    @app.cli.command("init-db")
    def init_db_command():
        """Create or update the database tables."""
        migrate(app.config["DATABASE_PATH"])
        print("The database is up to date.")

    if app.config["AUTO_MIGRATE"]:
        migrate(app.config["DATABASE_PATH"])


def _connection():
    connection = g.get("_database")
    if connection is None:
        connection = sqlite3.connect(current_app.config["DATABASE_PATH"], timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")  # makes "delete a user" also delete their entries
        g._database = connection
    return connection


def _close_connection(error=None):
    connection = g.pop("_database", None)
    if connection is not None:
        connection.close()


def query_one(sql, params=()):
    row = _connection().execute(sql, params).fetchone()
    return dict(row) if row else None


def query_all(sql, params=()):
    return [dict(row) for row in _connection().execute(sql, params).fetchall()]


def _write(sql, params):
    connection = _connection()
    try:
        cursor = connection.execute(sql, params)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return cursor


def execute(sql, params=()):
    """Run an UPDATE or DELETE. Returns how many rows changed."""
    return _write(sql, params).rowcount


def insert(sql, params=()):
    """Run an INSERT. Returns the id of the new row."""
    return _write(sql, params).lastrowid
