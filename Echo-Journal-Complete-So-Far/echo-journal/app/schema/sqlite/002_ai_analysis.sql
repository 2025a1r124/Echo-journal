-- Milestone 2: store analysis metadata, never duplicate the journal text.
ALTER TABLE journal_entries ADD COLUMN analysis_json TEXT;
ALTER TABLE journal_entries ADD COLUMN analyzed_at TEXT;
