"""ea-kernel: Lightweight Kernel Metamodel.

4-layer progressive abstraction:
  L1 Structure → L2 Relationship → L3 Behavioral → L4 Concrete

Backed by TypeDB for type hierarchy exploration.
"""

__version__ = "2.5.0"

from ea_kernel.ai_interface import AIDecisionInterface
from ea_kernel.corpus_version_store import (
    CorpusVersionStore,
    InMemoryCorpusVersionStore,
    SQLiteCorpusVersionStore,
)
from ea_kernel.decision_ledger import DecisionLedger
from ea_kernel.decision_store import (
    DecisionStore,
    InMemoryDecisionStore,
    SQLiteDecisionStore,
)
from ea_kernel.definition import KERNEL_SCHEMA, KERNEL_VERSION

# Phase 2: Governance Lifecycle Insight
from ea_kernel.evidence_analyzer import (
    AnalysisReport,
    ConflictHotspot,
    ConflictSeverity,
    EffectivenessGrade,
    EvidenceAnalyzer,
    ReferenceGrade,
    RuleEffectiveness,
    UsageProfile,
)

# Phase 1: Governance Lifecycle Foundation
from ea_kernel.governance_types import (
    CorpusVersionInfo,
    DecisionQueryOptions,
    EvidenceSummaryItem,
    JudgmentStatistics,
    RuleAsset,
    RuleLifecycle,
    RuleLifecycleState,
    RuleProvenance,
    StoredDecisionRecord,
    TriggerEventType,
    VersionQueryOptions,
    is_valid_transition,
)
from ea_kernel.graph_view import TopologyGraph
from ea_kernel.instance_validator import InstanceValidator
from ea_kernel.kernel_service import (
    describe_profile,
    describe_rule,
    get_entity_names,
    list_entities,
    list_relations,
    list_rules,
)
from ea_kernel.kernel_service import (
    judge as judge_triple,
)
from ea_kernel.model_registration import (
    KernelModelRegistrationService,
    ModelRegistrationError,
    ModelRegistryEntry,
    ModelVersionEntry,
    RegistrationResult,
    ValidationRunEntry,
)
from ea_kernel.profile_auditor import ProfileAuditor
from ea_kernel.profile_backup import BackupStore
from ea_kernel.profile_builder import ProfileBuilder
from ea_kernel.profile_composer import extend, subset
from ea_kernel.profile_diff import diff_profiles, diff_summary
from ea_kernel.profile_loader import ProfileLoadError, load_profile, load_profile_from_content
from ea_kernel.profile_quality_gate import check_profile_quality
from ea_kernel.profile_query import ElementQuery, ProfileQuery, RuleQuery
from ea_kernel.profile_registry import ProfileRegistry
from ea_kernel.profile_schema import ProfileSchema
from ea_kernel.profile_serializer import (
    compute_content_hash,
    dict_to_profile,
    json_to_profile,
    profile_to_dict,
    profile_to_json,
)
from ea_kernel.profile_store import SQLiteProfileStore, StoragePort
from ea_kernel.profile_types import (
    # Framework interface types
    AuditFinding,
    AuditResult,
    AuditSeverity,
    BackupError,
    BackupFileEntry,
    BackupSnapshot,
    ConditionRegistry,
    DiffChangeType,
    DriftEntry,
    ElementChange,
    # Core profile types
    KernelProfile,
    PatternType,
    ProfileBuildError,
    ProfileDiff,
    ProfileElement,
    ProfileMetadata,
    ProfileOrigin,
    ProfileRegistryError,
    ProfileRelation,
    # Kernel-agnostic rule types
    ProfileRule,
    ProfileStoreError,
    ProfileTag,
    ProfileVersion,
    QualityReport,
    RegistryAuditReport,
    RelationChange,
    RuleChange,
    RuleCondition,
    SchemaPort,
    ValidationCategory,
    classify_pattern,
    match_pattern,
)
from ea_kernel.promotion_engine import (
    DeprecationCandidate,
    PromotionCandidate,
    PromotionCriteria,
    PromotionEngine,
    ProposalStatus,
    ProposalType,
    ProposalVote,
    RuleChangeProposal,
)

# Phase 3: Governance Lifecycle Evolution
from ea_kernel.rule_asset_store import (
    InMemoryRuleAssetStore,
    RuleAssetQueryOptions,
    RuleAssetStore,
    SQLiteRuleAssetStore,
)
from ea_kernel.rule_verifier import RuleVerifier
from ea_kernel.spec import KERNEL_SPEC
from ea_kernel.test_harness import create_standard_tests
from ea_kernel.types import (
    ConformanceResult,
    DecisionContext,
    DecisionRecord,
    GraphEdge,
    GraphPath,
    GroupVerificationResult,
    InstanceElement,
    InstanceRelation,
    KernelEntity,
    KernelRelation,
    KernelSchema,
    KernelValidationResult,
    KernelValidityRule,
    Layer,
    LayerConstraint,
    Recommendation,
    RuleGroup,
    RuleVerificationEntry,
    VerificationReport,
)
from ea_kernel.what_if_simulator import (
    ChangeType,
    ImpactLevel,
    SimulatedChange,
    SimulationResult,
    VerdictChange,
    WhatIfSimulator,
)

__all__ = [
    "__version__",
    # Schema & Spec
    "KERNEL_SCHEMA",
    "KERNEL_SPEC",
    "KERNEL_VERSION",
    # Core types
    "ConformanceResult",
    "DecisionContext",
    "DecisionRecord",
    "GraphEdge",
    "GraphPath",
    "GroupVerificationResult",
    "InstanceElement",
    "InstanceRelation",
    "KernelEntity",
    "KernelRelation",
    "KernelSchema",
    "KernelValidationResult",
    "KernelValidityRule",
    "Layer",
    "LayerConstraint",
    "Recommendation",
    "RuleGroup",
    "RuleVerificationEntry",
    "VerificationReport",
    # Phase 1-4 modules
    "AIDecisionInterface",
    "DecisionLedger",
    "InstanceValidator",
    "ProfileAuditor",
    "RuleVerifier",
    "TopologyGraph",
    # Audit
    "AuditFinding",
    "AuditResult",
    "AuditSeverity",
    "DriftEntry",
    "RegistryAuditReport",
    # Backup
    "BackupError",
    "BackupFileEntry",
    "BackupSnapshot",
    "BackupStore",
    # Profile types
    "KernelProfile",
    "ProfileElement",
    "ProfileMetadata",
    "ProfileRelation",
    # Kernel-agnostic rule types
    "ProfileRule",
    "RuleCondition",
    # Profile Framework
    "ConditionRegistry",
    "PatternType",
    "ProfileBuildError",
    "ProfileBuilder",
    "ProfileLoadError",
    "QualityReport",
    "SchemaPort",
    "ValidationCategory",
    "check_profile_quality",
    "classify_pattern",
    "create_standard_tests",
    "load_profile",
    "load_profile_from_content",
    "match_pattern",
    # Profile Lifecycle
    "DiffChangeType",
    "ElementChange",
    "ProfileDiff",
    "ProfileOrigin",
    "ProfileQuery",
    "ProfileRegistry",
    "ProfileRegistryError",
    "ProfileSchema",
    "ProfileStoreError",
    "ProfileTag",
    "ProfileVersion",
    "KernelModelRegistrationService",
    "ModelRegistrationError",
    "ModelRegistryEntry",
    "ModelVersionEntry",
    "RegistrationResult",
    "ValidationRunEntry",
    "RelationChange",
    "RuleChange",
    "SQLiteProfileStore",
    "StoragePort",
    "compute_content_hash",
    "diff_profiles",
    "diff_summary",
    "dict_to_profile",
    "extend",
    "json_to_profile",
    "profile_to_dict",
    "profile_to_json",
    "subset",
    # Query
    "ElementQuery",
    "RuleQuery",
    # Service layer
    "list_entities",
    "list_relations",
    "list_rules",
    "describe_profile",
    "describe_rule",
    "judge_triple",
    "get_entity_names",
    # Phase 1: Governance Lifecycle Foundation
    "CorpusVersionInfo",
    "CorpusVersionStore",
    "DecisionQueryOptions",
    "DecisionStore",
    "EvidenceSummaryItem",
    "InMemoryCorpusVersionStore",
    "InMemoryDecisionStore",
    "JudgmentStatistics",
    "RuleAsset",
    "RuleLifecycle",
    "RuleLifecycleState",
    "RuleProvenance",
    "SQLiteCorpusVersionStore",
    "SQLiteDecisionStore",
    "StoredDecisionRecord",
    "TriggerEventType",
    "VersionQueryOptions",
    "is_valid_transition",
    # Phase 2: Governance Lifecycle Insight
    "AnalysisReport",
    "ConflictHotspot",
    "ConflictSeverity",
    "EffectivenessGrade",
    "EvidenceAnalyzer",
    "ReferenceGrade",
    "RuleEffectiveness",
    "UsageProfile",
    # Phase 3: Governance Lifecycle Evolution
    "ChangeType",
    "DeprecationCandidate",
    "ImpactLevel",
    "InMemoryRuleAssetStore",
    "ProposalStatus",
    "ProposalType",
    "ProposalVote",
    "PromotionCandidate",
    "PromotionCriteria",
    "PromotionEngine",
    "RuleAssetQueryOptions",
    "RuleAssetStore",
    "RuleChangeProposal",
    "SQLiteRuleAssetStore",
    "SimulatedChange",
    "SimulationResult",
    "VerdictChange",
    "WhatIfSimulator",
    # Phase 4: Governance Lifecycle Automation
    "ImpactEvaluator",
    "RuleChangeSet",
    "ImpactReport",
    "JudgmentService",
    "ReferenceStats",
    "EnhancedJudgment",
    "LifecycleEvent",
    "LifecycleEventPort",
    "InMemoryEventBus",
]
