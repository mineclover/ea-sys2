-- K0 snapshot source: ea_kernel.profile_store._DDL

CREATE TABLE IF NOT EXISTS schema_info (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_versions (
    id               TEXT PRIMARY KEY,
    profile_name     TEXT NOT NULL,
    version          TEXT NOT NULL,
    content_hash     TEXT NOT NULL,
    profile_data     TEXT NOT NULL,
    element_count    INTEGER NOT NULL,
    relation_count   INTEGER NOT NULL,
    rule_count       INTEGER NOT NULL,
    author           TEXT NOT NULL DEFAULT '',
    description      TEXT NOT NULL DEFAULT '',
    origin           TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL,
    parent_id        TEXT REFERENCES profile_versions(id),
    UNIQUE(profile_name, version)
);

CREATE TABLE IF NOT EXISTS profile_tags (
    name          TEXT NOT NULL,
    profile_name  TEXT NOT NULL,
    version_id    TEXT NOT NULL REFERENCES profile_versions(id) ON DELETE CASCADE,
    created_at    TEXT NOT NULL,
    PRIMARY KEY (profile_name, name)
);

CREATE INDEX IF NOT EXISTS idx_pv_name ON profile_versions(profile_name);
CREATE INDEX IF NOT EXISTS idx_pv_hash ON profile_versions(content_hash);
CREATE INDEX IF NOT EXISTS idx_pt_version ON profile_tags(version_id);
