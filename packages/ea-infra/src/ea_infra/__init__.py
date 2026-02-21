"""
ea-infra: Infrastructure and Resource Indexing Layer.
"""

from ea_infra.ops_ingestion import (
    InMemoryOpsEventStore,
    OpsEventCleanupResult,
    OpsEventRecord,
    OpsEventRetentionPolicy,
    SQLiteOpsEventStore,
    build_ops_event_record,
)

__all__ = [
    "InMemoryOpsEventStore",
    "OpsEventCleanupResult",
    "OpsEventRecord",
    "OpsEventRetentionPolicy",
    "SQLiteOpsEventStore",
    "build_ops_event_record",
]

__version__ = "0.1.0"
