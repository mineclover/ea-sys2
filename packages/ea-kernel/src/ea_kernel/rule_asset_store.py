"""Rule Asset Store — Phase 3 Governance (S1 Authoring).

Persistent storage for RuleAssets with lifecycle state management.
Provides:
- RuleAssetStore ABC: 규칙 자산 저장소 인터페이스
- InMemoryRuleAssetStore: 테스트용 인메모리 구현
- SQLiteRuleAssetStore: SQLite 기반 영속 저장소

References:
- governance_lifecycle.toml: Authoring 레이어 (RuleAuthor, AuthorRule)
- governance_lifecycle.md: S1 Expert Authoring
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime, UTC
from pathlib import Path
from typing import Iterator

from ea_kernel.governance_types import (
    RuleAsset,
    RuleLifecycle,
    RuleLifecycleState,
    RuleProvenance,
    is_valid_transition,
)
from ea_kernel.types import (
    KernelValidityRule,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleGroup,
    RuleMetadata,
)


from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════════════════════
# Query Options
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RuleAssetQueryOptions:
    """RuleAssetStore 조회 옵션."""
    state: RuleLifecycleState | None = None
    domain: str | None = None
    author: str | None = None
    source_type: str | None = None  # kernel | profile | empirical | manual
    limit: int = 100
    offset: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# RuleAssetStore ABC
# ═══════════════════════════════════════════════════════════════════════════════

class RuleAssetStore(ABC):
    """Rule Asset Store ABC — 규칙 자산 저장소 인터페이스.
    
    규칙의 전체 생명주기를 관리:
    - 생성 (Draft)
    - 상태 전이 (Draft → Review → Approved → Deprecated)
    - 버전 관리
    - 조회/검색
    """
    
    @abstractmethod
    def create(self, asset: RuleAsset) -> RuleAsset:
        """새 규칙 자산 생성.
        
        Args:
            asset: 생성할 RuleAsset (Draft 상태여야 함)
            
        Returns:
            저장된 RuleAsset
            
        Raises:
            ValueError: 이미 존재하는 ID이거나 Draft 상태가 아닌 경우
        """
        ...
    
    @abstractmethod
    def get(self, rule_id: str) -> RuleAsset | None:
        """rule_id로 규칙 자산 조회."""
        ...
    
    @abstractmethod
    def get_version(self, rule_id: str, version: int) -> RuleAsset | None:
        """특정 버전의 규칙 자산 조회."""
        ...
    
    @abstractmethod
    def query(
        self, options: RuleAssetQueryOptions | None = None,
    ) -> tuple[RuleAsset, ...]:
        """조건부 조회.
        
        Args:
            options: 조회 옵션 (None이면 전체 조회)
            
        Returns:
            조건에 맞는 RuleAsset 튜플
        """
        ...
    
    @abstractmethod
    def transition(
        self,
        rule_id: str,
        to_state: RuleLifecycleState,
        actor: str,
        reason: str = "",
    ) -> RuleAsset:
        """규칙 상태 전이.
        
        Args:
            rule_id: 전이할 규칙 ID
            to_state: 목표 상태
            actor: 전이를 수행하는 주체
            reason: 전이 사유
            
        Returns:
            전이된 RuleAsset
            
        Raises:
            ValueError: 규칙이 없거나 무효한 상태 전이
        """
        ...
    
    @abstractmethod
    def update_entry(
        self,
        rule_id: str,
        entry: RuleCorpusEntry,
        actor: str,
    ) -> RuleAsset:
        """규칙 내용 업데이트 (버전 증가).
        
        Draft 또는 Review 상태에서만 가능.
        
        Args:
            rule_id: 업데이트할 규칙 ID
            entry: 새로운 RuleCorpusEntry
            actor: 업데이트 수행자
            
        Returns:
            업데이트된 RuleAsset
            
        Raises:
            ValueError: 규칙이 없거나 수정 불가 상태
        """
        ...
    
    @abstractmethod
    def history(self, rule_id: str) -> tuple[RuleAsset, ...]:
        """규칙의 전체 버전 이력 조회.
        
        Returns:
            버전 오름차순 정렬된 RuleAsset 튜플
        """
        ...
    
    @abstractmethod
    def count(self, options: RuleAssetQueryOptions | None = None) -> int:
        """조건에 맞는 규칙 수."""
        ...
    
    @abstractmethod
    def list_by_state(
        self, state: RuleLifecycleState,
    ) -> tuple[RuleAsset, ...]:
        """특정 상태의 모든 규칙 조회."""
        ...
    
    @abstractmethod
    def active_rules(self) -> tuple[RuleAsset, ...]:
        """활성 규칙 (Approved 상태) 목록."""
        ...

    @abstractmethod
    def restore(self, asset: RuleAsset) -> RuleAsset:
        """규칙 자산 복원 (Lifecycle 상태 무시).
        
        백업/이관 시 사용. 이미 존재하는 ID이면 에러(또는 overwrite 정책은 호출자 책임).
        """
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# InMemoryRuleAssetStore
# ═══════════════════════════════════════════════════════════════════════════════

class InMemoryRuleAssetStore(RuleAssetStore):
    """In-memory Rule Asset Store for testing."""
    
    __slots__ = ("_assets", "_history")
    
    def __init__(self) -> None:
        self._assets: dict[str, RuleAsset] = {}
        self._history: dict[str, list[RuleAsset]] = {}
    
    def create(self, asset: RuleAsset) -> RuleAsset:
        if asset.id in self._assets:
            raise ValueError(f"Rule {asset.id} already exists")
        
        if asset.lifecycle.current_state != RuleLifecycleState.DRAFT:
            raise ValueError("New assets must be in DRAFT state")
        
        self._assets[asset.id] = asset
        self._history[asset.id] = [asset]
        return asset

    def restore(self, asset: RuleAsset) -> RuleAsset:
        # Same as create but no lifecycle check
        if asset.id in self._assets:
            raise ValueError(f"Rule {asset.id} already exists")
            
        self._assets[asset.id] = asset
        self._history[asset.id] = [asset]
        return asset
    
    def get(self, rule_id: str) -> RuleAsset | None:
        return self._assets.get(rule_id)
    
    def get_version(self, rule_id: str, version: int) -> RuleAsset | None:
        history = self._history.get(rule_id, [])
        for asset in history:
            if asset.provenance.version == version:
                return asset
        return None
    
    def query(
        self, options: RuleAssetQueryOptions | None = None,
    ) -> tuple[RuleAsset, ...]:
        if options is None:
            results = list(self._assets.values())
        else:
            results = self._filter(options)
        
        return tuple(results)
    
    def transition(
        self,
        rule_id: str,
        to_state: RuleLifecycleState,
        actor: str,
        reason: str = "",
    ) -> RuleAsset:
        asset = self._assets.get(rule_id)
        if asset is None:
            raise ValueError(f"Rule {rule_id} not found")
        
        new_lifecycle = asset.lifecycle.transition(to_state, actor, reason)
        new_asset = asset.with_lifecycle(new_lifecycle)
        
        self._assets[rule_id] = new_asset
        self._history[rule_id].append(new_asset)
        
        return new_asset
    
    def update_entry(
        self,
        rule_id: str,
        entry: RuleCorpusEntry,
        actor: str,
    ) -> RuleAsset:
        asset = self._assets.get(rule_id)
        if asset is None:
            raise ValueError(f"Rule {rule_id} not found")
        
        state = asset.lifecycle.current_state
        if state not in (RuleLifecycleState.DRAFT, RuleLifecycleState.REVIEW):
            raise ValueError(f"Cannot update rule in {state.value} state")
        
        now = datetime.now(UTC).isoformat() + "Z"
        new_provenance = RuleProvenance(
            author=actor,
            source_type=asset.provenance.source_type,
            source_reference=asset.provenance.source_reference,
            created_at=asset.provenance.created_at,
            updated_at=now,
            version=asset.provenance.version + 1,
        )
        
        new_asset = RuleAsset(
            entry=entry,
            provenance=new_provenance,
            lifecycle=asset.lifecycle,
        )
        
        self._assets[rule_id] = new_asset
        self._history[rule_id].append(new_asset)
        
        return new_asset
    
    def history(self, rule_id: str) -> tuple[RuleAsset, ...]:
        return tuple(self._history.get(rule_id, []))
    
    def count(self, options: RuleAssetQueryOptions | None = None) -> int:
        if options is None:
            return len(self._assets)
        return len(self._filter(options))
    
    def list_by_state(
        self, state: RuleLifecycleState,
    ) -> tuple[RuleAsset, ...]:
        return tuple(
            a for a in self._assets.values()
            if a.lifecycle.current_state == state
        )
    
    def active_rules(self) -> tuple[RuleAsset, ...]:
        return self.list_by_state(RuleLifecycleState.APPROVED)
    
    def _filter(
        self, options: RuleAssetQueryOptions,
    ) -> list[RuleAsset]:
        results: list[RuleAsset] = []
        
        for asset in self._assets.values():
            if options.state and asset.lifecycle.current_state != options.state:
                continue
            if options.domain and asset.metadata.domain != options.domain:
                continue
            if options.author and asset.provenance.author != options.author:
                continue
            if options.source_type and asset.provenance.source_type != options.source_type:
                continue
            
            results.append(asset)
        
        # Pagination
        start = options.offset
        end = options.offset + options.limit
        return results[start:end]


# ═══════════════════════════════════════════════════════════════════════════════
# SQLiteRuleAssetStore
# ═══════════════════════════════════════════════════════════════════════════════

class SQLiteRuleAssetStore(RuleAssetStore):
    """SQLite-backed Rule Asset Store for persistent storage."""
    
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
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                );
                
                -- Rule assets (current version)
                CREATE TABLE IF NOT EXISTS rule_assets (
                    rule_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    
                    -- RuleCorpusEntry serialized
                    entry_json TEXT NOT NULL,
                    
                    -- RuleProvenance
                    author TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_reference TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    
                    -- RuleLifecycle
                    current_state TEXT NOT NULL,
                    state_history_json TEXT DEFAULT '[]',
                    
                    -- Denormalized for queries
                    domain TEXT NOT NULL
                );
                
                -- Version history
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
                
                -- Indexes
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
            """)
            
            cursor = conn.execute("SELECT version FROM schema_version")
            if cursor.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (self._SCHEMA_VERSION,),
                )
            
            conn.commit()
    
    def create(self, asset: RuleAsset) -> RuleAsset:
        if asset.lifecycle.current_state != RuleLifecycleState.DRAFT:
            raise ValueError("New assets must be in DRAFT state")
        
        with self._connection() as conn:
            # Check if exists
            cursor = conn.execute(
                "SELECT rule_id FROM rule_assets WHERE rule_id = ?",
                (asset.id,),
            )
            if cursor.fetchone():
                raise ValueError(f"Rule {asset.id} already exists")
            
            self._insert_asset(conn, asset)
            self._record_history(conn, asset)
            conn.commit()
        
        return asset

    def restore(self, asset: RuleAsset) -> RuleAsset:
        # Same as create but NO lifecycle check
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT rule_id FROM rule_assets WHERE rule_id = ?",
                (asset.id,),
            )
            if cursor.fetchone():
                raise ValueError(f"Rule {asset.id} already exists")
            
            self._insert_asset(conn, asset)
            self._record_history(conn, asset)
            conn.commit()
        return asset
    
    def get(self, rule_id: str) -> RuleAsset | None:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM rule_assets WHERE rule_id = ?",
                (rule_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_asset(row)
    
    def get_version(self, rule_id: str, version: int) -> RuleAsset | None:
        with self._connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM rule_asset_history 
                   WHERE rule_id = ? AND version = ?""",
                (rule_id, version),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._history_row_to_asset(row)
    
    def query(
        self, options: RuleAssetQueryOptions | None = None,
    ) -> tuple[RuleAsset, ...]:
        query = "SELECT * FROM rule_assets"
        params: list[str | int] = []
        conditions: list[str] = []
        
        if options:
            if options.state:
                conditions.append("current_state = ?")
                params.append(options.state.value)
            if options.domain:
                conditions.append("domain = ?")
                params.append(options.domain)
            if options.author:
                conditions.append("author = ?")
                params.append(options.author)
            if options.source_type:
                conditions.append("source_type = ?")
                params.append(options.source_type)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY updated_at DESC"
        
        if options:
            query += f" LIMIT {options.limit} OFFSET {options.offset}"
        
        with self._connection() as conn:
            cursor = conn.execute(query, params)
            return tuple(self._row_to_asset(row) for row in cursor.fetchall())
    
    def transition(
        self,
        rule_id: str,
        to_state: RuleLifecycleState,
        actor: str,
        reason: str = "",
    ) -> RuleAsset:
        asset = self.get(rule_id)
        if asset is None:
            raise ValueError(f"Rule {rule_id} not found")
        
        new_lifecycle = asset.lifecycle.transition(to_state, actor, reason)
        new_asset = asset.with_lifecycle(new_lifecycle)
        
        with self._connection() as conn:
            self._update_asset(conn, new_asset)
            self._record_history(conn, new_asset)
            conn.commit()
        
        return new_asset
    
    def update_entry(
        self,
        rule_id: str,
        entry: RuleCorpusEntry,
        actor: str,
    ) -> RuleAsset:
        asset = self.get(rule_id)
        if asset is None:
            raise ValueError(f"Rule {rule_id} not found")
        
        state = asset.lifecycle.current_state
        if state not in (RuleLifecycleState.DRAFT, RuleLifecycleState.REVIEW):
            raise ValueError(f"Cannot update rule in {state.value} state")
        
        now = datetime.now(UTC).isoformat() + "Z"
        new_provenance = RuleProvenance(
            author=actor,
            source_type=asset.provenance.source_type,
            source_reference=asset.provenance.source_reference,
            created_at=asset.provenance.created_at,
            updated_at=now,
            version=asset.provenance.version + 1,
        )
        
        new_asset = RuleAsset(
            entry=entry,
            provenance=new_provenance,
            lifecycle=asset.lifecycle,
        )
        
        with self._connection() as conn:
            self._update_asset(conn, new_asset)
            self._record_history(conn, new_asset)
            conn.commit()
        
        return new_asset
    
    def history(self, rule_id: str) -> tuple[RuleAsset, ...]:
        with self._connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM rule_asset_history 
                   WHERE rule_id = ? ORDER BY version ASC""",
                (rule_id,),
            )
            return tuple(self._history_row_to_asset(row) for row in cursor.fetchall())
    
    def count(self, options: RuleAssetQueryOptions | None = None) -> int:
        query = "SELECT COUNT(*) FROM rule_assets"
        params: list[str | int] = []
        conditions: list[str] = []
        
        if options:
            if options.state:
                conditions.append("current_state = ?")
                params.append(options.state.value)
            if options.domain:
                conditions.append("domain = ?")
                params.append(options.domain)
            if options.author:
                conditions.append("author = ?")
                params.append(options.author)
            if options.source_type:
                conditions.append("source_type = ?")
                params.append(options.source_type)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        with self._connection() as conn:
            cursor = conn.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else 0
    
    def list_by_state(
        self, state: RuleLifecycleState,
    ) -> tuple[RuleAsset, ...]:
        return self.query(RuleAssetQueryOptions(state=state))
    
    def active_rules(self) -> tuple[RuleAsset, ...]:
        return self.list_by_state(RuleLifecycleState.APPROVED)
    
    # ── Private helpers ─────────────────────────────────────────────
    
    def _serialize_entry(self, entry: RuleCorpusEntry) -> str:
        return json.dumps({
            "rule": {
                "id": entry.rule.id,
                "source_pattern": entry.rule.source_pattern,
                "target_pattern": entry.rule.target_pattern,
                "relationship_name": entry.rule.relationship_name,
                "valid": entry.rule.valid,
                "priority": entry.rule.priority,
                "conditions": list(entry.rule.conditions) if entry.rule.conditions else [],
            },
            "metadata": {
                "domain": entry.metadata.domain,
                "tags": list(entry.metadata.tags),
                "category": entry.metadata.category.value,
                "confidence": entry.metadata.confidence.value,
                "source": entry.metadata.source,
                "established_version": entry.metadata.established_version,
                "rationale": entry.metadata.rationale,
                "group": entry.metadata.group.value,
            },
        })
    
    def _deserialize_entry(self, json_str: str) -> RuleCorpusEntry:
        data = json.loads(json_str)
        
        rule = KernelValidityRule(
            id=data["rule"]["id"],
            source_pattern=data["rule"]["source_pattern"],
            target_pattern=data["rule"]["target_pattern"],
            relationship_name=data["rule"]["relationship_name"],
            valid=data["rule"]["valid"],
            priority=data["rule"]["priority"],
            conditions=tuple(data["rule"].get("conditions", [])),
        )
        
        meta = RuleMetadata(
            domain=data["metadata"]["domain"],
            tags=tuple(data["metadata"]["tags"]),
            category=RuleCategory(data["metadata"]["category"]),
            confidence=RuleConfidence(data["metadata"]["confidence"]),
            source=data["metadata"]["source"],
            established_version=data["metadata"]["established_version"],
            rationale=data["metadata"]["rationale"],
            group=RuleGroup(data["metadata"]["group"]),
        )
        
        return RuleCorpusEntry(rule=rule, metadata=meta)
    
    def _insert_asset(self, conn: sqlite3.Connection, asset: RuleAsset) -> None:
        conn.execute("""
            INSERT INTO rule_assets (
                rule_id, version, entry_json,
                author, source_type, source_reference, created_at, updated_at,
                current_state, state_history_json, domain
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            asset.id,
            asset.provenance.version,
            self._serialize_entry(asset.entry),
            asset.provenance.author,
            asset.provenance.source_type,
            asset.provenance.source_reference,
            asset.provenance.created_at,
            asset.provenance.updated_at,
            asset.lifecycle.current_state.value,
            json.dumps(list(asset.lifecycle.state_history)),
            asset.metadata.domain,
        ))
    
    def _update_asset(self, conn: sqlite3.Connection, asset: RuleAsset) -> None:
        conn.execute("""
            UPDATE rule_assets SET
                version = ?,
                entry_json = ?,
                author = ?,
                source_type = ?,
                source_reference = ?,
                updated_at = ?,
                current_state = ?,
                state_history_json = ?,
                domain = ?
            WHERE rule_id = ?
        """, (
            asset.provenance.version,
            self._serialize_entry(asset.entry),
            asset.provenance.author,
            asset.provenance.source_type,
            asset.provenance.source_reference,
            asset.provenance.updated_at,
            asset.lifecycle.current_state.value,
            json.dumps(list(asset.lifecycle.state_history)),
            asset.metadata.domain,
            asset.id,
        ))
    
    def _record_history(self, conn: sqlite3.Connection, asset: RuleAsset) -> None:
        now = datetime.now(UTC).isoformat() + "Z"
        conn.execute("""
            INSERT OR REPLACE INTO rule_asset_history (
                rule_id, version, entry_json,
                author, source_type, source_reference, created_at, updated_at,
                current_state, state_history_json, domain, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            asset.id,
            asset.provenance.version,
            self._serialize_entry(asset.entry),
            asset.provenance.author,
            asset.provenance.source_type,
            asset.provenance.source_reference,
            asset.provenance.created_at,
            asset.provenance.updated_at,
            asset.lifecycle.current_state.value,
            json.dumps(list(asset.lifecycle.state_history)),
            asset.metadata.domain,
            now,
        ))
    
    def _row_to_asset(self, row: sqlite3.Row) -> RuleAsset:
        entry = self._deserialize_entry(row["entry_json"])
        
        provenance = RuleProvenance(
            author=row["author"],
            source_type=row["source_type"],
            source_reference=row["source_reference"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            version=row["version"],
        )
        
        state_history = tuple(
            tuple(item) for item in json.loads(row["state_history_json"])
        )
        lifecycle = RuleLifecycle(
            current_state=RuleLifecycleState(row["current_state"]),
            state_history=state_history,
        )
        
        return RuleAsset(
            entry=entry,
            provenance=provenance,
            lifecycle=lifecycle,
        )
    
    def _history_row_to_asset(self, row: sqlite3.Row) -> RuleAsset:
        # Same as _row_to_asset since history has same columns
        return self._row_to_asset(row)
