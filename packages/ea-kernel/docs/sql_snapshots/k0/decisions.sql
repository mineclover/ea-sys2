-- K0 snapshot source: ea_kernel.decision_store.SQLiteDecisionStore._init_schema

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS decision_records (
    storage_id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    relation TEXT NOT NULL,
    judgment_json TEXT,
    override_reason TEXT DEFAULT '',
    context_json TEXT DEFAULT '[]',
    corpus_version_id TEXT DEFAULT '',
    stored_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_triple
    ON decision_records(source, target, relation);
CREATE INDEX IF NOT EXISTS idx_actor
    ON decision_records(actor);
CREATE INDEX IF NOT EXISTS idx_decision_type
    ON decision_records(decision_type);
CREATE INDEX IF NOT EXISTS idx_timestamp
    ON decision_records(timestamp);
CREATE INDEX IF NOT EXISTS idx_corpus_version
    ON decision_records(corpus_version_id);

CREATE TABLE IF NOT EXISTS judgment_statistics (
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    relation TEXT NOT NULL,
    total_judgments INTEGER DEFAULT 0,
    allow_count INTEGER DEFAULT 0,
    deny_count INTEGER DEFAULT 0,
    override_count INTEGER DEFAULT 0,
    avg_confidence REAL DEFAULT 0.0,
    last_judgment_at TEXT,
    dominant_domains_json TEXT DEFAULT '[]',
    PRIMARY KEY (source, target, relation)
);
