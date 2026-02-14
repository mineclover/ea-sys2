-- K0 snapshot source: ea_kernel.corpus_version_store.SQLiteCorpusVersionStore._init_schema
-- Note: K0 baseline has no schema_version table in versions.db.

CREATE TABLE IF NOT EXISTS corpus_versions (
    version_id TEXT PRIMARY KEY,
    corpus_name TEXT NOT NULL,
    rule_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    parent_version_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    rule_ids_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_corpus_name
    ON corpus_versions(corpus_name);
CREATE INDEX IF NOT EXISTS idx_created_at
    ON corpus_versions(created_at);

CREATE TABLE IF NOT EXISTS version_entries (
    version_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    rule_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (version_id, rule_id),
    FOREIGN KEY (version_id) REFERENCES corpus_versions(version_id)
);
