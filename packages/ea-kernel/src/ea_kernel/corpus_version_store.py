"""Corpus Version Store — Phase 1 Foundation (S3 Recording).

Versioned storage for RuleCorpus snapshots.
Enables:
- 판단 재현: 특정 시점의 Corpus로 동일 판단 재현
- 변경 추적: Corpus 버전 간 규칙 변경 내역 비교
- 히스토리 탐색: 시간순 버전 이력 조회

References:
- governance_lifecycle.toml: CorpusVersion(item), RuleCorpus(package)
- governance_lifecycle.md: S1 Rule Authoring
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from ea_kernel.governance_types import (
    CorpusVersionInfo,
    VersionQueryOptions,
)
from ea_kernel.types import (
    KernelValidityRule,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleGroup,
    RuleMetadata,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CorpusVersionStore ABC — 버전 저장소 인터페이스
# ═══════════════════════════════════════════════════════════════════════════════

class CorpusVersionStore(ABC):
    """Corpus Version Store ABC — Corpus 버전 저장소 인터페이스.
    
    RuleCorpus의 시점별 스냅샷을 저장하고 조회.
    """
    
    @abstractmethod
    def create_version(
        self,
        corpus_name: str,
        entries: tuple[RuleCorpusEntry, ...],
        description: str = "",
        parent_version_id: str = "",
    ) -> CorpusVersionInfo:
        """새 Corpus 버전 생성.
        
        Args:
            corpus_name: Corpus 이름 (e.g., "kernel", "GovernanceLifecycle")
            entries: 포함할 규칙 엔트리들
            description: 버전 설명
            parent_version_id: 이전 버전 ID (변경 추적용)
            
        Returns:
            생성된 CorpusVersionInfo
        """
        ...
    
    @abstractmethod
    def get(self, version_id: str) -> CorpusVersionInfo | None:
        """version_id로 버전 정보 조회."""
        ...
    
    @abstractmethod
    def get_entries(self, version_id: str) -> tuple[RuleCorpusEntry, ...]:
        """특정 버전의 규칙 엔트리 조회.
        
        Returns:
            해당 버전에 포함된 RuleCorpusEntry 튜플
        """
        ...
    
    @abstractmethod
    def get_latest(self, corpus_name: str) -> CorpusVersionInfo | None:
        """특정 Corpus의 최신 버전 조회."""
        ...
    
    @abstractmethod
    def query(
        self, options: VersionQueryOptions | None = None,
    ) -> tuple[CorpusVersionInfo, ...]:
        """조건부 버전 목록 조회."""
        ...
    
    @abstractmethod
    def history(
        self, corpus_name: str, limit: int = 100,
    ) -> tuple[CorpusVersionInfo, ...]:
        """특정 Corpus의 버전 이력 (최신순)."""
        ...
    
    @abstractmethod
    def diff(
        self, 
        from_version_id: str, 
        to_version_id: str,
    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        """두 버전 간 규칙 변경 비교.
        
        Returns:
            (added_rule_ids, removed_rule_ids, modified_rule_ids)
        """
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# InMemoryCorpusVersionStore — 테스트용 인메모리 구현
# ═══════════════════════════════════════════════════════════════════════════════

class InMemoryCorpusVersionStore(CorpusVersionStore):
    """In-memory Corpus Version Store for testing."""
    
    __slots__ = ("_versions", "_entries", "_by_corpus", "_content_hashes")

    def __init__(self) -> None:
        self._versions: dict[str, CorpusVersionInfo] = {}
        self._entries: dict[str, tuple[RuleCorpusEntry, ...]] = {}
        self._by_corpus: dict[str, list[str]] = {}  # corpus_name -> version_ids (oldest first)
        self._content_hashes: dict[str, dict[str, str]] = {}  # version_id -> {rule_id -> hash}
    
    def create_version(
        self,
        corpus_name: str,
        entries: tuple[RuleCorpusEntry, ...],
        description: str = "",
        parent_version_id: str = "",
    ) -> CorpusVersionInfo:
        # Generate deterministic version ID based on content
        rule_ids = tuple(sorted(e.rule.id for e in entries))
        content_hash = hashlib.sha256(
            json.dumps(rule_ids).encode()
        ).hexdigest()[:12]
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        version_id = f"{corpus_name}-{timestamp}-{content_hash}"
        
        version_info = CorpusVersionInfo(
            version_id=version_id,
            corpus_name=corpus_name,
            rule_count=len(entries),
            parent_version_id=parent_version_id,
            description=description,
            rule_ids=rule_ids,
        )
        
        self._versions[version_id] = version_info
        self._entries[version_id] = entries
        self._by_corpus.setdefault(corpus_name, []).append(version_id)

        # Store per-rule content hashes for modification detection in diff()
        self._content_hashes[version_id] = {
            e.rule.id: self._rule_content_hash(e) for e in entries
        }

        return version_info

    @staticmethod
    def _rule_content_hash(entry: RuleCorpusEntry) -> str:
        """Deterministic hash of rule content for modification detection."""
        rule = entry.rule
        content = json.dumps({
            "source": rule.source_pattern,
            "target": rule.target_pattern,
            "relation": rule.relationship_name,
            "valid": rule.valid,
            "priority": rule.priority,
            "notes": rule.notes,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get(self, version_id: str) -> CorpusVersionInfo | None:
        return self._versions.get(version_id)
    
    def get_entries(self, version_id: str) -> tuple[RuleCorpusEntry, ...]:
        return self._entries.get(version_id, ())
    
    def get_latest(self, corpus_name: str) -> CorpusVersionInfo | None:
        version_ids = self._by_corpus.get(corpus_name, [])
        if not version_ids:
            return None
        return self._versions.get(version_ids[-1])
    
    def query(
        self, options: VersionQueryOptions | None = None,
    ) -> tuple[CorpusVersionInfo, ...]:
        results: list[CorpusVersionInfo] = []
        
        for info in self._versions.values():
            if options:
                if options.corpus_name and info.corpus_name != options.corpus_name:
                    continue
                if options.start_time and info.created_at < options.start_time:
                    continue
                if options.end_time and info.created_at > options.end_time:
                    continue
            results.append(info)
        
        # Sort by created_at descending
        results.sort(key=lambda x: x.created_at, reverse=True)
        
        if options:
            start = options.offset
            end = options.offset + options.limit
            return tuple(results[start:end])
        
        return tuple(results)
    
    def history(
        self, corpus_name: str, limit: int = 100,
    ) -> tuple[CorpusVersionInfo, ...]:
        version_ids = self._by_corpus.get(corpus_name, [])
        # Latest first
        results = [
            self._versions[vid]
            for vid in reversed(version_ids[-limit:])
            if vid in self._versions
        ]
        return tuple(results)
    
    def diff(
        self,
        from_version_id: str,
        to_version_id: str,
    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        from_info = self.get(from_version_id)
        to_info = self.get(to_version_id)
        
        if from_info is None or to_info is None:
            return ((), (), ())
        
        from_ids = set(from_info.rule_ids)
        to_ids = set(to_info.rule_ids)
        
        added = tuple(sorted(to_ids - from_ids))
        removed = tuple(sorted(from_ids - to_ids))

        # Detect modifications via content hash comparison
        common_ids = from_ids & to_ids
        from_hashes = self._content_hashes.get(from_version_id, {})
        to_hashes = self._content_hashes.get(to_version_id, {})
        modified = tuple(sorted(
            rid for rid in common_ids
            if from_hashes.get(rid) != to_hashes.get(rid)
        ))

        return (added, removed, modified)


# ═══════════════════════════════════════════════════════════════════════════════
# SQLiteCorpusVersionStore — SQLite 기반 영속 저장소
# ═══════════════════════════════════════════════════════════════════════════════

class SQLiteCorpusVersionStore(CorpusVersionStore):
    """SQLite-backed Corpus Version Store for persistent storage."""
    
    __slots__ = ("_db_path",)
    
    _SCHEMA_VERSION = 1
    
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._init_schema()
    
    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript("""
                -- Corpus versions
                CREATE TABLE IF NOT EXISTS corpus_versions (
                    version_id TEXT PRIMARY KEY,
                    corpus_name TEXT NOT NULL,
                    rule_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    parent_version_id TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    rule_ids_json TEXT NOT NULL
                );
                
                -- Index for efficient queries
                CREATE INDEX IF NOT EXISTS idx_corpus_name
                    ON corpus_versions(corpus_name);
                CREATE INDEX IF NOT EXISTS idx_created_at
                    ON corpus_versions(created_at);
                
                -- Rule entries per version (normalized)
                CREATE TABLE IF NOT EXISTS version_entries (
                    version_id TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    rule_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY (version_id, rule_id),
                    FOREIGN KEY (version_id) REFERENCES corpus_versions(version_id)
                );
            """)
            conn.commit()
    
    def create_version(
        self,
        corpus_name: str,
        entries: tuple[RuleCorpusEntry, ...],
        description: str = "",
        parent_version_id: str = "",
    ) -> CorpusVersionInfo:
        rule_ids = tuple(sorted(e.rule.id for e in entries))
        content_hash = hashlib.sha256(
            json.dumps(rule_ids).encode()
        ).hexdigest()[:12]
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        version_id = f"{corpus_name}-{timestamp}-{content_hash}"
        created_at = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        
        with self._connection() as conn:
            # Insert version info
            conn.execute("""
                INSERT INTO corpus_versions (
                    version_id, corpus_name, rule_count, created_at,
                    parent_version_id, description, rule_ids_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                version_id, corpus_name, len(entries), created_at,
                parent_version_id, description, json.dumps(rule_ids),
            ))
            
            # Insert entries
            for entry in entries:
                rule_json = self._serialize_rule(entry.rule)
                meta_json = self._serialize_metadata(entry.metadata)
                conn.execute("""
                    INSERT INTO version_entries (version_id, rule_id, rule_json, metadata_json)
                    VALUES (?, ?, ?, ?)
                """, (version_id, entry.rule.id, rule_json, meta_json))
            
            conn.commit()
        
        return CorpusVersionInfo(
            version_id=version_id,
            corpus_name=corpus_name,
            rule_count=len(entries),
            created_at=created_at,
            parent_version_id=parent_version_id,
            description=description,
            rule_ids=rule_ids,
        )
    
    def get(self, version_id: str) -> CorpusVersionInfo | None:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM corpus_versions WHERE version_id = ?",
                (version_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_version_info(row)
    
    def get_entries(self, version_id: str) -> tuple[RuleCorpusEntry, ...]:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM version_entries WHERE version_id = ?",
                (version_id,),
            )
            return tuple(
                self._row_to_entry(row) for row in cursor.fetchall()
            )
    
    def get_latest(self, corpus_name: str) -> CorpusVersionInfo | None:
        with self._connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM corpus_versions
                WHERE corpus_name = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (corpus_name,))
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_version_info(row)
    
    def query(
        self, options: VersionQueryOptions | None = None,
    ) -> tuple[CorpusVersionInfo, ...]:
        query = "SELECT * FROM corpus_versions"
        params: list[str | int] = []
        conditions: list[str] = []
        
        if options:
            if options.corpus_name:
                conditions.append("corpus_name = ?")
                params.append(options.corpus_name)
            if options.start_time:
                conditions.append("created_at >= ?")
                params.append(options.start_time)
            if options.end_time:
                conditions.append("created_at <= ?")
                params.append(options.end_time)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY created_at DESC"
        
        if options:
            query += f" LIMIT {options.limit} OFFSET {options.offset}"
        
        with self._connection() as conn:
            cursor = conn.execute(query, params)
            return tuple(self._row_to_version_info(row) for row in cursor.fetchall())
    
    def history(
        self, corpus_name: str, limit: int = 100,
    ) -> tuple[CorpusVersionInfo, ...]:
        with self._connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM corpus_versions
                WHERE corpus_name = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (corpus_name, limit))
            return tuple(self._row_to_version_info(row) for row in cursor.fetchall())
    
    def diff(
        self,
        from_version_id: str,
        to_version_id: str,
    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        from_info = self.get(from_version_id)
        to_info = self.get(to_version_id)
        
        if from_info is None or to_info is None:
            return ((), (), ())
        
        from_ids = set(from_info.rule_ids)
        to_ids = set(to_info.rule_ids)
        
        added = tuple(sorted(to_ids - from_ids))
        removed = tuple(sorted(from_ids - to_ids))
        
        # Check for modifications by comparing rule content
        common_ids = from_ids & to_ids
        modified_ids: list[str] = []
        
        if common_ids:
            with self._connection() as conn:
                for rule_id in common_ids:
                    cursor = conn.execute("""
                        SELECT rule_json FROM version_entries
                        WHERE version_id = ? AND rule_id = ?
                    """, (from_version_id, rule_id))
                    from_row = cursor.fetchone()
                    
                    cursor = conn.execute("""
                        SELECT rule_json FROM version_entries
                        WHERE version_id = ? AND rule_id = ?
                    """, (to_version_id, rule_id))
                    to_row = cursor.fetchone()
                    
                    if from_row and to_row:
                        if from_row["rule_json"] != to_row["rule_json"]:
                            modified_ids.append(rule_id)
        
        return (added, removed, tuple(sorted(modified_ids)))
    
    # ── Serialization helpers ───────────────────────────────────────
    
    def _serialize_rule(self, rule: KernelValidityRule) -> str:
        conditions = [
            {
                "type": c.condition_type.value,
                "params": list(c.parameters),
            }
            for c in rule.conditions
        ]
        return json.dumps({
            "id": rule.id,
            "source_pattern": rule.source_pattern,
            "target_pattern": rule.target_pattern,
            "relationship_name": rule.relationship_name,
            "valid": rule.valid,
            "priority": rule.priority,
            "conditions": conditions,
            "notes": rule.notes,
        })
    
    def _serialize_metadata(self, meta: RuleMetadata) -> str:
        return json.dumps({
            "domain": meta.domain,
            "tags": list(meta.tags),
            "category": meta.category.value,
            "confidence": meta.confidence.value,
            "source": meta.source,
            "established_version": meta.established_version,
            "rationale": meta.rationale,
            "group": meta.group.value,
        })
    
    def _row_to_version_info(self, row: sqlite3.Row) -> CorpusVersionInfo:
        rule_ids = tuple(json.loads(row["rule_ids_json"]))
        return CorpusVersionInfo(
            version_id=row["version_id"],
            corpus_name=row["corpus_name"],
            rule_count=row["rule_count"],
            created_at=row["created_at"],
            parent_version_id=row["parent_version_id"],
            description=row["description"],
            rule_ids=rule_ids,
        )
    
    def _row_to_entry(self, row: sqlite3.Row) -> RuleCorpusEntry:
        rule_data = json.loads(row["rule_json"])
        meta_data = json.loads(row["metadata_json"])
        
        # Reconstruct rule
        from ea_kernel.types import KernelConditionType, KernelRuleCondition
        
        conditions = tuple(
            KernelRuleCondition(
                condition_type=KernelConditionType(c["type"]),
                parameters=tuple(tuple(p) for p in c["params"]),
            )
            for c in rule_data["conditions"]
        )
        
        rule = KernelValidityRule(
            id=rule_data["id"],
            source_pattern=rule_data["source_pattern"],
            target_pattern=rule_data["target_pattern"],
            relationship_name=rule_data["relationship_name"],
            valid=rule_data["valid"],
            priority=rule_data["priority"],
            conditions=conditions,
            notes=rule_data["notes"],
        )
        
        # Reconstruct metadata
        metadata = RuleMetadata(
            domain=meta_data["domain"],
            tags=tuple(meta_data["tags"]),
            category=RuleCategory(meta_data["category"]),
            confidence=RuleConfidence(meta_data["confidence"]),
            source=meta_data["source"],
            established_version=meta_data["established_version"],
            rationale=meta_data["rationale"],
            group=RuleGroup(meta_data["group"]),
        )
        
        return RuleCorpusEntry(rule=rule, metadata=metadata)
