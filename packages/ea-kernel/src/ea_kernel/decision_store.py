"""Decision Store — Phase 1 Foundation (S3 Recording).

Persistent storage for decision records with query capabilities.
Provides:
- DecisionStore ABC: 저장소 인터페이스
- InMemoryDecisionStore: 테스트용 인메모리 구현
- SQLiteDecisionStore: SQLite 기반 영속 저장소

References:
- governance_lifecycle.toml: DecisionStore(structure), DecisionRecord(item)
- governance_lifecycle.md: S3 Decision Recording
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
    CorpusVersionInfo,
    DecisionQueryOptions,
    EvidenceSummaryItem,
    JudgmentStatistics,
    StoredDecisionRecord,
)
from ea_kernel.types import (
    DecisionRecord,
    JudgmentReport,
    RuleConfidence,
    RuleEvidence,
)


# ═══════════════════════════════════════════════════════════════════════════════
# DecisionStore ABC — 저장소 인터페이스
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionStore(ABC):
    """Decision Store ABC — 판단 기록 저장소 인터페이스.
    
    포트 기반 확장: DecisionLedger는 이 인터페이스를 선택적으로 사용.
    None이면 기존 in-memory 동작 유지.
    """
    
    @abstractmethod
    def store(
        self,
        record: DecisionRecord,
        corpus_version_id: str = "",
        evidence_summary: tuple[EvidenceSummaryItem, ...] | None = None,
    ) -> StoredDecisionRecord:
        """판단 기록 저장.
        
        Args:
            record: 저장할 DecisionRecord
            corpus_version_id: 판단 시점의 Corpus 버전 ID
            evidence_summary: 명시적 증거 요약 (None이면 judgment에서 자동 생성)
            
        Returns:
            StoredDecisionRecord with storage metadata
        """
        ...
    
    @abstractmethod
    def get(self, storage_id: str) -> StoredDecisionRecord | None:
        """storage_id로 기록 조회."""
        ...
    
    @abstractmethod
    def query(
        self, options: DecisionQueryOptions | None = None,
    ) -> tuple[StoredDecisionRecord, ...]:
        """조건부 조회.
        
        Args:
            options: 조회 옵션 (None이면 전체 조회)
            
        Returns:
            조건에 맞는 StoredDecisionRecord 튜플
        """
        ...
    
    @abstractmethod
    def count(self, options: DecisionQueryOptions | None = None) -> int:
        """조건에 맞는 레코드 수."""
        ...
    
    @abstractmethod
    def statistics_for(
        self, source: str, target: str, relation: str,
    ) -> JudgmentStatistics:
        """특정 triple의 판단 통계."""
        ...
    
    @abstractmethod
    def all_statistics(self) -> tuple[JudgmentStatistics, ...]:
        """모든 triple의 판단 통계."""
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# InMemoryDecisionStore — 테스트용 인메모리 구현
# ═══════════════════════════════════════════════════════════════════════════════

class InMemoryDecisionStore(DecisionStore):
    """In-memory Decision Store for testing.
    
    모든 데이터가 메모리에만 존재, 프로세스 종료 시 소멸.
    """
    
    __slots__ = ("_records", "_by_triple", "_statistics")
    
    def __init__(self) -> None:
        self._records: dict[str, StoredDecisionRecord] = {}
        self._by_triple: dict[tuple[str, str, str], list[StoredDecisionRecord]] = {}
        self._statistics: dict[tuple[str, str, str], JudgmentStatistics] = {}
    
    def store(
        self,
        record: DecisionRecord,
        corpus_version_id: str = "",
        evidence_summary: tuple[EvidenceSummaryItem, ...] | None = None,
    ) -> StoredDecisionRecord:
        storage_id = str(uuid.uuid4())
        
        # Build evidence summary from judgment if not provided
        if evidence_summary is None:
            evidence_summary = self._build_evidence_summary(record)
        
        stored = StoredDecisionRecord(
            record=record,
            storage_id=storage_id,
            corpus_version_id=corpus_version_id,
            evidence_summary=evidence_summary,
        )
        
        self._records[storage_id] = stored
        triple = record.subject_triple
        self._by_triple.setdefault(triple, []).append(stored)
        
        # 통계 업데이트
        self._update_statistics(record)
        
        return stored
    
    def _build_evidence_summary(
        self, record: DecisionRecord,
    ) -> tuple[EvidenceSummaryItem, ...]:
        """Build evidence summary from DecisionRecord judgment."""
        if record.judgment is None:
            return ()
        
        return tuple(
            EvidenceSummaryItem(
                rule_id=e.entry.rule.id,
                domain=e.entry.metadata.domain,
                matched=e.matched,
                is_winner=e.is_winner,
            )
            for e in record.judgment.evidence
        )
    
    def get(self, storage_id: str) -> StoredDecisionRecord | None:
        return self._records.get(storage_id)
    
    def query(
        self, options: DecisionQueryOptions | None = None,
    ) -> tuple[StoredDecisionRecord, ...]:
        if options is None:
            results = list(self._records.values())
        else:
            results = self._filter_records(options)
        
        return tuple(results)
    
    def count(self, options: DecisionQueryOptions | None = None) -> int:
        if options is None:
            return len(self._records)
        return len(self._filter_records(options))
    
    def statistics_for(
        self, source: str, target: str, relation: str,
    ) -> JudgmentStatistics:
        triple = (source, target, relation)
        return self._statistics.get(
            triple,
            JudgmentStatistics(source=source, target=target, relation=relation),
        )
    
    def all_statistics(self) -> tuple[JudgmentStatistics, ...]:
        return tuple(self._statistics.values())
    
    def _filter_records(
        self, options: DecisionQueryOptions,
    ) -> list[StoredDecisionRecord]:
        results: list[StoredDecisionRecord] = []
        
        # Triple 필터 — O(1) if specified
        if options.triple:
            candidates = self._by_triple.get(options.triple, [])
        else:
            candidates = list(self._records.values())
        
        for stored in candidates:
            rec = stored.record
            
            if options.actor_prefix and not rec.actor.startswith(options.actor_prefix):
                continue
            if options.decision_type and rec.decision_type != options.decision_type:
                continue
            if options.start_time and rec.timestamp < options.start_time:
                continue
            if options.end_time and rec.timestamp > options.end_time:
                continue
            if options.corpus_version_id and stored.corpus_version_id != options.corpus_version_id:
                continue
            
            results.append(stored)
        
        # Pagination
        start = options.offset
        end = options.offset + options.limit
        return results[start:end]
    
    def _update_statistics(self, record: DecisionRecord) -> None:
        triple = record.subject_triple
        src, tgt, rel = triple
        
        existing = self._statistics.get(
            triple,
            JudgmentStatistics(source=src, target=tgt, relation=rel),
        )
        
        # Extract info from judgment if available
        verdict = True
        confidence = RuleConfidence.COMMON
        domains: tuple[str, ...] = ()
        is_override = record.decision_type == "override"
        
        if record.judgment:
            verdict = record.judgment.verdict
            confidence = record.judgment.confidence
            domains = record.judgment.domains
        
        self._statistics[triple] = existing.with_judgment(
            verdict=verdict,
            confidence=confidence,
            domains=domains,
            is_override=is_override,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SQLiteDecisionStore — SQLite 기반 영속 저장소
# ═══════════════════════════════════════════════════════════════════════════════

class SQLiteDecisionStore(DecisionStore):
    """SQLite-backed Decision Store for persistent storage.
    
    Thread-safe with connection per-operation pattern.
    """
    
    __slots__ = ("_db_path",)
    
    # Schema version for migrations
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
        """Initialize database schema."""
        with self._connection() as conn:
            conn.executescript("""
                -- Schema version tracking
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                );
                
                -- Decision records
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
                
                -- Indexes for common queries
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
                
                -- Aggregated statistics (materialized for performance)
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
            """)
            
            # Set initial schema version if not exists
            cursor = conn.execute("SELECT version FROM schema_version")
            if cursor.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (self._SCHEMA_VERSION,),
                )
            
            conn.commit()
    
    def store(
        self,
        record: DecisionRecord,
        corpus_version_id: str = "",
        evidence_summary: tuple[EvidenceSummaryItem, ...] | None = None,
    ) -> StoredDecisionRecord:
        storage_id = str(uuid.uuid4())
        stored_at = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        src, tgt, rel = record.subject_triple
        
        # Build evidence summary for analysis if not provided
        if evidence_summary is None:
            evidence_summary = self._build_evidence_summary(record)
        
        # Serialize judgment to JSON
        judgment_json = self._serialize_judgment(record.judgment, evidence_summary)
        context_json = json.dumps(list(record.context))
        
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO decision_records (
                    storage_id, record_id, timestamp, actor, decision_type,
                    source, target, relation, judgment_json, override_reason,
                    context_json, corpus_version_id, stored_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                storage_id, record.id, record.timestamp, record.actor,
                record.decision_type, src, tgt, rel, judgment_json,
                record.override_reason, context_json, corpus_version_id, stored_at,
            ))
            
            # Update statistics
            self._update_statistics_sql(conn, record)
            conn.commit()
        
        return StoredDecisionRecord(
            record=record,
            storage_id=storage_id,
            corpus_version_id=corpus_version_id,
            stored_at=stored_at,
            evidence_summary=evidence_summary,
        )
    
    def _build_evidence_summary(
        self, record: DecisionRecord,
    ) -> tuple[EvidenceSummaryItem, ...]:
        """Build evidence summary from DecisionRecord judgment."""
        if record.judgment is None:
            return ()
        
        return tuple(
            EvidenceSummaryItem(
                rule_id=e.entry.rule.id,
                domain=e.entry.metadata.domain,
                matched=e.matched,
                is_winner=e.is_winner,
            )
            for e in record.judgment.evidence
        )
    
    def get(self, storage_id: str) -> StoredDecisionRecord | None:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM decision_records WHERE storage_id = ?",
                (storage_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_stored(row)
    
    def query(
        self, options: DecisionQueryOptions | None = None,
    ) -> tuple[StoredDecisionRecord, ...]:
        query = "SELECT * FROM decision_records"
        params: list[str | int] = []
        conditions: list[str] = []
        
        if options:
            if options.triple:
                conditions.append("source = ? AND target = ? AND relation = ?")
                params.extend(options.triple)
            if options.actor_prefix:
                conditions.append("actor LIKE ?")
                params.append(f"{options.actor_prefix}%")
            if options.decision_type:
                conditions.append("decision_type = ?")
                params.append(options.decision_type)
            if options.start_time:
                conditions.append("timestamp >= ?")
                params.append(options.start_time)
            if options.end_time:
                conditions.append("timestamp <= ?")
                params.append(options.end_time)
            if options.corpus_version_id:
                conditions.append("corpus_version_id = ?")
                params.append(options.corpus_version_id)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY timestamp DESC"
        
        if options:
            query += f" LIMIT {options.limit} OFFSET {options.offset}"
        
        with self._connection() as conn:
            cursor = conn.execute(query, params)
            return tuple(self._row_to_stored(row) for row in cursor.fetchall())
    
    def count(self, options: DecisionQueryOptions | None = None) -> int:
        query = "SELECT COUNT(*) FROM decision_records"
        params: list[str | int] = []
        conditions: list[str] = []
        
        if options:
            if options.triple:
                conditions.append("source = ? AND target = ? AND relation = ?")
                params.extend(options.triple)
            if options.actor_prefix:
                conditions.append("actor LIKE ?")
                params.append(f"{options.actor_prefix}%")
            if options.decision_type:
                conditions.append("decision_type = ?")
                params.append(options.decision_type)
            if options.start_time:
                conditions.append("timestamp >= ?")
                params.append(options.start_time)
            if options.end_time:
                conditions.append("timestamp <= ?")
                params.append(options.end_time)
            if options.corpus_version_id:
                conditions.append("corpus_version_id = ?")
                params.append(options.corpus_version_id)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        with self._connection() as conn:
            cursor = conn.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else 0
    
    def statistics_for(
        self, source: str, target: str, relation: str,
    ) -> JudgmentStatistics:
        with self._connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM judgment_statistics
                WHERE source = ? AND target = ? AND relation = ?
            """, (source, target, relation))
            row = cursor.fetchone()
            
            if row is None:
                return JudgmentStatistics(
                    source=source, target=target, relation=relation,
                )
            
            return self._row_to_statistics(row)
    
    def all_statistics(self) -> tuple[JudgmentStatistics, ...]:
        with self._connection() as conn:
            cursor = conn.execute("SELECT * FROM judgment_statistics")
            return tuple(self._row_to_statistics(row) for row in cursor.fetchall())
    
    # ── Private helpers ─────────────────────────────────────────────
    
    def _serialize_judgment(
        self,
        judgment: JudgmentReport | None,
        evidence_summary: tuple[EvidenceSummaryItem, ...] | None = None,
    ) -> str:
        if judgment is None:
            return ""
        
        # Serialize evidence with domain for analysis
        if evidence_summary is not None:
             evidence_data = [
                {
                    "rule_id": e.rule_id,
                    "domain": e.domain,
                    "matched": e.matched,
                    "is_winner": e.is_winner,
                }
                for e in evidence_summary
            ]
        else:
            evidence_data = [
                {
                    "rule_id": e.entry.rule.id,
                    "domain": e.entry.metadata.domain,
                    "matched": e.matched,
                    "is_winner": e.is_winner,
                }
                for e in judgment.evidence
            ]
        
        return json.dumps({
            "verdict": judgment.verdict,
            "confidence": judgment.confidence.value,
            "domains": list(judgment.domains),
            "conflicts": list(judgment.conflicts),
            "evidence_summary": evidence_data,
        })
    
    def _deserialize_judgment(self, json_str: str) -> JudgmentReport | None:
        if not json_str:
            return None
        
        data = json.loads(json_str)
        
        # Note: We cannot fully reconstruct evidence without the RuleCorpus,
        # so we create a minimal JudgmentReport for storage purposes.
        return JudgmentReport(
            verdict=data["verdict"],
            evidence=(),  # Evidence is not fully reconstructed
            confidence=RuleConfidence(data["confidence"]),
            domains=tuple(data["domains"]),
            conflicts=tuple(data["conflicts"]),
        )
    
    def _row_to_stored(self, row: sqlite3.Row) -> StoredDecisionRecord:
        judgment_data = self._parse_judgment_json(row["judgment_json"])
        judgment = judgment_data["judgment"]
        evidence_summary = judgment_data["evidence_summary"]
        context = tuple(tuple(item) for item in json.loads(row["context_json"]))
        
        record = DecisionRecord(
            id=row["record_id"],
            timestamp=row["timestamp"],
            actor=row["actor"],
            decision_type=row["decision_type"],
            subject_triple=(row["source"], row["target"], row["relation"]),
            judgment=judgment,
            override_reason=row["override_reason"],
            context=context,
        )
        
        return StoredDecisionRecord(
            record=record,
            storage_id=row["storage_id"],
            corpus_version_id=row["corpus_version_id"],
            stored_at=row["stored_at"],
            evidence_summary=evidence_summary,
        )
    
    def _parse_judgment_json(
        self, json_str: str,
    ) -> dict:
        """Parse judgment JSON and extract both judgment and evidence summary."""
        result: dict = {
            "judgment": None,
            "evidence_summary": (),
        }
        
        if not json_str:
            return result
        
        data = json.loads(json_str)
        
        # Build evidence summary
        evidence_items = []
        for e in data.get("evidence_summary", []):
            evidence_items.append(EvidenceSummaryItem(
                rule_id=e["rule_id"],
                domain=e.get("domain", "unknown"),
                matched=e["matched"],
                is_winner=e["is_winner"],
            ))
        result["evidence_summary"] = tuple(evidence_items)
        
        # Build minimal judgment
        result["judgment"] = JudgmentReport(
            verdict=data["verdict"],
            evidence=(),  # Full evidence not reconstructed
            confidence=RuleConfidence(data["confidence"]),
            domains=tuple(data["domains"]),
            conflicts=tuple(data["conflicts"]),
        )
        
        return result
    
    def _row_to_statistics(self, row: sqlite3.Row) -> JudgmentStatistics:
        domains = tuple(json.loads(row["dominant_domains_json"]))
        return JudgmentStatistics(
            source=row["source"],
            target=row["target"],
            relation=row["relation"],
            total_judgments=row["total_judgments"],
            allow_count=row["allow_count"],
            deny_count=row["deny_count"],
            override_count=row["override_count"],
            avg_confidence=row["avg_confidence"],
            last_judgment_at=row["last_judgment_at"] or "",
            dominant_domains=domains,
        )
    
    def _update_statistics_sql(
        self,
        conn: sqlite3.Connection,
        record: DecisionRecord,
    ) -> None:
        src, tgt, rel = record.subject_triple
        
        # Get current statistics
        cursor = conn.execute("""
            SELECT * FROM judgment_statistics
            WHERE source = ? AND target = ? AND relation = ?
        """, (src, tgt, rel))
        row = cursor.fetchone()
        
        # Calculate new values
        verdict = record.judgment.verdict if record.judgment else True
        confidence_value = 0.5
        domains: list[str] = []
        
        if record.judgment:
            confidence_value = {
                RuleConfidence.UNIVERSAL: 1.0,
                RuleConfidence.COMMON: 0.75,
                RuleConfidence.CONTEXTUAL: 0.5,
                RuleConfidence.EMPIRICAL: 0.25,
            }.get(record.judgment.confidence, 0.5)
            domains = list(record.judgment.domains)
        
        is_override = record.decision_type == "override"
        now = datetime.now(UTC).isoformat() + "Z"
        
        if row is None:
            # Insert new
            conn.execute("""
                INSERT INTO judgment_statistics (
                    source, target, relation,
                    total_judgments, allow_count, deny_count, override_count,
                    avg_confidence, last_judgment_at, dominant_domains_json
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
            """, (
                src, tgt, rel,
                1 if verdict else 0,
                0 if verdict else 1,
                1 if is_override else 0,
                confidence_value,
                now,
                json.dumps(domains),
            ))
        else:
            # Update existing
            old_total = row["total_judgments"]
            new_total = old_total + 1
            new_avg = (row["avg_confidence"] * old_total + confidence_value) / new_total
            
            old_domains = set(json.loads(row["dominant_domains_json"]))
            new_domains = old_domains | set(domains)
            
            conn.execute("""
                UPDATE judgment_statistics SET
                    total_judgments = ?,
                    allow_count = allow_count + ?,
                    deny_count = deny_count + ?,
                    override_count = override_count + ?,
                    avg_confidence = ?,
                    last_judgment_at = ?,
                    dominant_domains_json = ?
                WHERE source = ? AND target = ? AND relation = ?
            """, (
                new_total,
                1 if verdict else 0,
                0 if verdict else 1,
                1 if is_override else 0,
                new_avg,
                now,
                json.dumps(sorted(new_domains)),
                src, tgt, rel,
            ))
