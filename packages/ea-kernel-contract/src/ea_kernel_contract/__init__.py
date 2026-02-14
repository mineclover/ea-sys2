"""ea-kernel-contract: consumer package for ea-kernel snapshot contracts."""

from ea_kernel_contract.loader import (
    ENV_CONTRACT_DIR,
    default_contract_dir,
    load_contract_bundle,
    load_rules_snapshot,
    load_schema_snapshot,
    load_vectors_snapshot,
    resolve_contract_paths,
    validate_bundle_shape,
)
from ea_kernel_contract.types import (
    ContractBundle,
    ContractPaths,
    JsonObject,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "ENV_CONTRACT_DIR",
    "ContractBundle",
    "ContractPaths",
    "JsonObject",
    "default_contract_dir",
    "resolve_contract_paths",
    "load_schema_snapshot",
    "load_rules_snapshot",
    "load_vectors_snapshot",
    "load_contract_bundle",
    "validate_bundle_shape",
]
