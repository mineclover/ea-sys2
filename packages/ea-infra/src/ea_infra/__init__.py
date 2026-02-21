"""
ea-infra: Infrastructure and Resource Indexing Layer.
"""

from ea_infra.ops_ingestion import (
    InMemoryOpsEventStore,
    OpsEventRecord,
    SQLiteOpsEventStore,
    build_ops_event_record,
)

__all__ = [
    "InMemoryOpsEventStore",
    "OpsEventRecord",
    "SQLiteOpsEventStore",
    "build_ops_event_record",
]

__version__ = "0.1.0"
