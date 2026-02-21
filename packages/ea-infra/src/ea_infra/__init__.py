"""
ea-infra: Infrastructure and Resource Indexing Layer.
"""

from ea_infra.asset_catalog import (
    InfraAssetCatalogStore,
    InfraAssetQuery,
    InMemoryInfraAssetCatalogStore,
    SQLiteInfraAssetCatalogStore,
)
from ea_infra.ops_ingestion import (
    InMemoryOpsEventStore,
    OpsEventCleanupResult,
    OpsEventRecord,
    OpsEventRetentionPolicy,
    SQLiteOpsEventStore,
    build_ops_event_record,
)

__all__ = [
    "InfraAssetCatalogStore",
    "InfraAssetQuery",
    "InMemoryInfraAssetCatalogStore",
    "SQLiteInfraAssetCatalogStore",
    "InMemoryOpsEventStore",
    "OpsEventCleanupResult",
    "OpsEventRecord",
    "OpsEventRetentionPolicy",
    "SQLiteOpsEventStore",
    "build_ops_event_record",
]

__version__ = "0.1.0"
