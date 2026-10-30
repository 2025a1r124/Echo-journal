-- Echo Journal, first version of the database.
-- Timestamps are text like 2026-10-11T09:30:00Z (UTC).

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE CHECK (username = lower(username)),
    password_hash TEXT    NOT NULL,           -- never the password itself
    is_admin      INTEGER NOT NULL DEFAULT 0, -- used by the admin dashboard (a later milestone)
    created_at    TEXT    NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS journal_entries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title      TEXT    NOT NULL DEFAULT '',
    body       TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entries_user_created
    ON journal_entries (user_id, created_at DESC, id DESC);
