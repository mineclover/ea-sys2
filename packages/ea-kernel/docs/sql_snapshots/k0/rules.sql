-- K0 snapshot source: ea_kernel.rule_asset_store.SQLiteRuleAssetStore._init_schema

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS rule_assets (
    rule_id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    entry_json TEXT NOT NULL,
    author TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_reference TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    current_state TEXT NOT NULL,
    state_history_json TEXT DEFAULT '[]',
    domain TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_asset_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    entry_json TEXT NOT NULL,
    author TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_reference TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    current_state TEXT NOT NULL,
    state_history_json TEXT DEFAULT '[]',
    domain TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE(rule_id, version)
);

CREATE INDEX IF NOT EXISTS idx_state
    ON rule_assets(current_state);
CREATE INDEX IF NOT EXISTS idx_domain
    ON rule_assets(domain);
CREATE INDEX IF NOT EXISTS idx_author
    ON rule_assets(author);
CREATE INDEX IF NOT EXISTS idx_source_type
    ON rule_assets(source_type);
CREATE INDEX IF NOT EXISTS idx_history_rule
    ON rule_asset_history(rule_id);
