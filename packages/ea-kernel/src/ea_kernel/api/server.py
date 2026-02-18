"""
Governance API Server using FastAPI.

This module exposes the Governance System capabilities via REST API:
- Rule Lifecycle Management (Submit, Approve, etc.)
- Model I/O (Export/Import)
- Multi-tenancy Management
- Diagram Visualization (Experience)

Run with:
    export EA_KERNEL_DATA_DIR=./data
    python -m ea_kernel.api.server
"""

import json
import logging
import os
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Annotated, Any, TypeVar

import uvicorn
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ea_kernel.business_service import BusinessService
from ea_kernel.governance import GovernanceSystem
from ea_kernel.governance_types import RuleLifecycleState
from ea_kernel.model_io import ModelIOManager
from ea_kernel.model_registration import ModelRegistrationError
from ea_kernel.types import KernelSchema

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ea_kernel.server")

endpoint_fn = TypeVar("endpoint_fn", bound=Callable[..., Any])

# --- Configuration ---
def get_data_dir() -> Path:
    env_path = os.getenv("EA_KERNEL_DATA_DIR", "./governance_data")
    path = Path(env_path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path

# --- Application Factory ---

def create_app(data_dir: Path, schema: KernelSchema) -> FastAPI:
    app = FastAPI(title="Governance Kernel API", version="1.0.0")
    diagram_schema_cache: KernelSchema | None = None

    def _typed_get(*args: Any, **kwargs: Any) -> Callable[[endpoint_fn], endpoint_fn]:
        return app.get(*args, **kwargs)

    def _typed_post(*args: Any, **kwargs: Any) -> Callable[[endpoint_fn], endpoint_fn]:
        return app.post(*args, **kwargs)

    def _typed_put(*args: Any, **kwargs: Any) -> Callable[[endpoint_fn], endpoint_fn]:
        return app.put(*args, **kwargs)

    def _model_api_error(
        *,
        status_code: int,
        detail: str,
        category: str,
    ) -> HTTPException:
        # Keep the error envelope deterministic for ModelApiErrorRecord mapping.
        return HTTPException(
            status_code=status_code,
            detail={
                "status_code": status_code,
                "detail": detail,
                "category": category,
            },
        )

    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        token = value.strip()
        if len(token) == 0:
            return None
        return token

    def _require_decision_id(decision_id: str | None, *, operation: str) -> str:
        normalized = _normalize_optional_text(decision_id)
        if normalized is None:
            raise _model_api_error(
                status_code=400,
                detail=(
                    f"decision_id is required for /models/{operation}; "
                    "causal flow must be needs -> decision -> kernel"
                ),
                category="bad_request",
            )
        return normalized

    def _enforce_direct_decision_cause(
        *,
        decision_id: str,
        cause_type: str | None,
        cause_id: str | None,
        operation: str,
    ) -> tuple[str, str]:
        normalized_cause_type = _normalize_optional_text(cause_type)
        normalized_cause_id = _normalize_optional_text(cause_id)
        if normalized_cause_type is not None and normalized_cause_type.lower() != "decision":
            raise _model_api_error(
                status_code=400,
                detail=(
                    f"cause_type must be 'decision' for /models/{operation}; "
                    "direct kernel change cause is always decision"
                ),
                category="bad_request",
            )
        if normalized_cause_id is not None and normalized_cause_id != decision_id:
            raise _model_api_error(
                status_code=400,
                detail=(
                    f"cause_id must match decision_id for /models/{operation}; "
                    "upstream need must be linked through the decision artifact"
                ),
                category="bad_request",
            )
        return "decision", decision_id

    def _get_governance_container() -> Any:
        cached = getattr(app.state, "governance_container", None)
        if cached is not None:
            if getattr(app.state, "registration", None) is None:
                app.state.registration = getattr(cached, "model_registration", None)
            return cached
        from ea_governance.facade import GovernanceContainer

        try:
            container = GovernanceContainer(data_dir, schema, kernel_system=system)
        except TypeError as err:
            if "kernel_system" not in str(err):
                raise
            container = GovernanceContainer(data_dir, schema)
        app.state.governance_container = container
        app.state.registration = getattr(container, "model_registration", None)
        return container

    def _get_governance_diagram_schema() -> KernelSchema:
        nonlocal diagram_schema_cache
        if diagram_schema_cache is not None:
            return diagram_schema_cache

        target_schema = schema
        try:
            from importlib.resources import as_file, files

            from ea_kernel.profile_loader import load_profile
            from ea_kernel.profile_rule_compiler import build_profile_runtime_schema

            resource = files("ea_kernel.profiles").joinpath("governance_lifecycle.toml")
            with as_file(resource) as profile_path:
                if profile_path.exists():
                    gov_profile = load_profile(profile_path, kernel=schema)
                    target_schema = build_profile_runtime_schema(schema, gov_profile).schema
        except Exception as err:
            logger.warning(f"Failed to load governance profile for diagram: {err}")
            target_schema = schema

        diagram_schema_cache = target_schema
        return target_schema

    def _layer_model_match(model_name: str, layer_key: str, profile_name: str) -> tuple[int, list[str]]:
        model_lc = model_name.lower()
        layer_lc = layer_key.lower()
        profile_lc = profile_name.lower()
        score = 0
        rules: list[str] = []

        if model_lc == profile_lc:
            score += 120
            rules.append("exact_profile_name")

        suffix_rules = (
            (f".{layer_lc}", "dot_suffix"),
            (f"-{layer_lc}", "dash_suffix"),
            (f"_{layer_lc}", "underscore_suffix"),
        )
        for suffix, label in suffix_rules:
            if model_lc.endswith(suffix):
                score += 90
                rules.append(label)
                break

        infix_rules = (
            (f".{layer_lc}.", "dot_infix"),
            (f"-{layer_lc}-", "dash_infix"),
            (f"_{layer_lc}_", "underscore_infix"),
        )
        for infix, label in infix_rules:
            if infix in model_lc:
                score += 35
                rules.append(label)
                break

        if layer_lc in model_lc:
            score += 10
            rules.append("contains_layer_key")

        return score, rules

    # 1. Middleware (CORS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all for dev; restrict in prod
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize Managers
    logger.info(f"Initializing Governance System at {data_dir.resolve()}")
    system = GovernanceSystem(data_dir / "default", schema)
    app.state.system = system  # Expose for testing
    app.state.registration = None
    io_manager = ModelIOManager(system)
    business_svc = BusinessService(data_dir, kernel_schema=schema)

    # --- Models ---

    class ExecuteJudgmentRequest(BaseModel):
        source: str
        target: str
        relation: str
        actor: str | None = "api-user"

    class RuleSubmission(BaseModel):
        # Simplified for demo
        rule_id: str
        source: str
        target: str
        relation: str
        valid: bool
        domain: str

    class ExportRequest(BaseModel):
        state: str | None = None # "approved", "draft"...
        domain: str | None = None

    class ModelRegisterRequest(BaseModel):
        profile_toml: str
        owner: str | None = "api-user"
        created_by: str | None = "api-user"
        model_name: str | None = None
        activate: bool | None = False
        context: dict[str, Any] | None = None
        on_exists: str | None = "validate"  # validate | error
        decision_id: str | None = None
        evidence_refs: list[str] | None = None
        cause_type: str | None = None
        cause_id: str | None = None
        change_phase: str | None = None

    class UpdateTranslationRequest(BaseModel):
        value: str

    class CreateNeedsCatalogRequest(BaseModel):
        name: str
        description: str = ""

    class AddStakeholderRequest(BaseModel):
        name: str
        role: str
        context: str = ""

    class AddNeedsUseCaseRequest(BaseModel):
        title: str
        actor: str
        situation: str
        purpose: str
        outcome: str = ""
        tags: list[str] | None = None

    class ExpressNeedRequest(BaseModel):
        stakeholder_id: str
        action: str
        subject: str
        target: str | None = None
        justifications: list[dict[str, str]] | None = None
        priority: str | None = None
        kernel_refs: list[str] | None = None
        tags: list[str] | None = None
        use_case_id: str | None = None
        cause_types: list[str] | None = None
        purpose: str = "unspecified"
        complexity: str = "procedural"
        kernel_change_phase: str | None = None

    class ReviseNeedRequest(BaseModel):
        action: str | None = None
        subject: str | None = None
        target: str | None = None
        justifications: list[dict[str, str]] | None = None
        priority: str | None = None
        kernel_refs: list[str] | None = None
        tags: list[str] | None = None
        use_case_id: str | None = None
        cause_types: list[str] | None = None
        purpose: str | None = None
        complexity: str | None = None
        kernel_change_phase: str | None = None
        clone_process_units: bool | None = None

    class AddNeedProcessUnitRequest(BaseModel):
        stage: str
        label: str
        description: str = ""
        sequence: int | None = None
        metadata: dict[str, str] | None = None

    class InheritNeedDecisionEvidenceRequest(BaseModel):
        decision_id: str
        evidence_refs: list[str]
        kernel_change_phase: str | None = None

    class ModelValidateRequest(BaseModel):
        model_name: str
        version: str
        context: dict[str, Any] | None = None
        decision_id: str | None = None
        evidence_refs: list[str] | None = None
        cause_type: str | None = None
        cause_id: str | None = None
        change_phase: str | None = None

    class ModelActivateRequest(BaseModel):
        model_name: str
        version: str
        actor: str | None = "api-user"
        decision_id: str | None = None
        evidence_refs: list[str] | None = None
        cause_type: str | None = None
        cause_id: str | None = None
        change_phase: str | None = None

    class CreateBusinessRequest(BaseModel):
        name: str
        description: str = ""

    class CreateTagSchemaRequest(BaseModel):
        tag: str
        fields: list[dict[str, Any]] = []
        indexes: list[dict[str, Any]] = []
        keyPath: str = "id"
        autoIncrement: bool = True
        kernel_ref: str | None = None
        description: str = ""

    class UpdateTagSchemaRequest(BaseModel):
        fields: list[dict[str, Any]] | None = None
        indexes: list[dict[str, Any]] | None = None
        keyPath: str | None = None
        autoIncrement: bool | None = None
        kernel_ref: str | None = None
        description: str | None = None

    # --- Endpoints ---

    @_typed_get("/")
    def health_check() -> dict[str, Any]:
        container = _get_governance_container()
        kernel = getattr(container, "kernel", system)
        return {
            "status": "ok",
            "service": "ea-kernel-governance",
            "data_dir": str(data_dir),
            "rule_count": kernel.rule_store.count(),
            "decision_count": kernel.decision_store.count()
        }

    # 0. Model Registration
    @_typed_post("/models/register")
    def register_model(req: ModelRegisterRequest) -> dict[str, Any]:
        from ea_kernel.profile_loader import ProfileLoadError

        container = _get_governance_container()
        try:
            normalized_decision_id = _require_decision_id(req.decision_id, operation="register")
            normalized_cause_type, normalized_cause_id = _enforce_direct_decision_cause(
                decision_id=normalized_decision_id,
                cause_type=req.cause_type,
                cause_id=req.cause_id,
                operation="register",
            )
            result = container.register_kernel_model(
                req.profile_toml,
                owner=req.owner or "api-user",
                created_by=req.created_by or "api-user",
                model_name=req.model_name,
                activate=bool(req.activate),
                context={"source": "api:models/register", **(req.context or {})},
                on_exists=req.on_exists or "validate",
                actor=req.created_by or "api-user",
                decision_id=normalized_decision_id,
                evidence_refs=req.evidence_refs,
                cause_type=normalized_cause_type,
                cause_id=normalized_cause_id,
                change_phase=req.change_phase,
                return_transaction=True,
            )
            if isinstance(result, dict):
                return {
                    "model_name": result.get("model_name"),
                    "version": result.get("version"),
                    "created": bool(result.get("created", False)),
                    "validation_run_id": result.get("validation_run_id"),
                    "activated": bool(result.get("activated", False)),
                    "status": result.get("status"),
                    "active_version_id": result.get("active_version_id"),
                    "transaction_id": result.get("transaction_id"),
                    "decision_trace": result.get("decision_trace"),
                }
            return result
        except ValueError as err:
            raise _model_api_error(
                status_code=400,
                detail=str(err),
                category="bad_request",
            ) from err
        except ProfileLoadError as err:
            raise _model_api_error(
                status_code=400,
                detail=f"Invalid profile TOML: {err}",
                category="invalid_profile",
            ) from err
        except ModelRegistrationError as err:
            text = str(err)
            if (
                "already exists" in text
                or "revalidation failed" in text
                or "Cannot activate" in text
            ):
                raise _model_api_error(
                    status_code=409,
                    detail=text,
                    category="conflict",
                ) from err
            raise _model_api_error(
                status_code=400,
                detail=text,
                category="registration_error",
            ) from err
        except HTTPException:
            raise
        except Exception as err:
            logger.exception("Unhandled /models/register error")
            raise _model_api_error(
                status_code=500,
                detail="Internal governance model API error",
                category="internal_error",
            ) from err

    @_typed_post("/models/validate")
    def validate_model(req: ModelValidateRequest) -> dict[str, Any]:
        container = _get_governance_container()
        try:
            normalized_decision_id = _require_decision_id(req.decision_id, operation="validate")
            normalized_cause_type, normalized_cause_id = _enforce_direct_decision_cause(
                decision_id=normalized_decision_id,
                cause_type=req.cause_type,
                cause_id=req.cause_id,
                operation="validate",
            )
            validate_result = container.validate_kernel_model(
                req.model_name,
                req.version,
                context={"source": "api:models/validate", **(req.context or {})},
                actor="api-user",
                decision_id=normalized_decision_id,
                evidence_refs=req.evidence_refs,
                cause_type=normalized_cause_type,
                cause_id=normalized_cause_id,
                change_phase=req.change_phase,
                return_transaction=True,
            )
            run = validate_result
            transaction_id: str | None = None
            decision_trace: dict[str, Any] | None = None
            if isinstance(validate_result, dict):
                run = validate_result.get("run")
                tx = validate_result.get("transaction_id")
                if isinstance(tx, str) and len(tx.strip()) > 0:
                    transaction_id = tx
                trace = validate_result.get("decision_trace")
                if isinstance(trace, dict):
                    decision_trace = trace

            if run is None:
                raise _model_api_error(
                    status_code=500,
                    detail="Validation run is missing from governance response",
                    category="internal_error",
                )
        except ModelRegistrationError as err:
            text = str(err)
            if "not found" in text:
                raise _model_api_error(
                    status_code=404,
                    detail=text,
                    category="not_found",
                ) from err
            raise _model_api_error(
                status_code=400,
                detail=text,
                category="validation_error",
            ) from err
        except HTTPException:
            raise
        except Exception as err:
            logger.exception("Unhandled /models/validate error")
            raise _model_api_error(
                status_code=500,
                detail="Internal governance model API error",
                category="internal_error",
            ) from err

        return {
            "model_name": req.model_name,
            "version": req.version,
            "passed": run.passed,
            "run_id": run.run_id,
            "errors": list(run.errors),
            "transaction_id": transaction_id,
            "decision_trace": decision_trace,
        }

    @_typed_post("/models/activate")
    def activate_model(req: ModelActivateRequest) -> dict[str, Any]:
        container = _get_governance_container()
        try:
            normalized_decision_id = _require_decision_id(req.decision_id, operation="activate")
            normalized_cause_type, normalized_cause_id = _enforce_direct_decision_cause(
                decision_id=normalized_decision_id,
                cause_type=req.cause_type,
                cause_id=req.cause_id,
                operation="activate",
            )
            activate_result = container.activate_kernel_model(
                req.model_name,
                req.version,
                actor=req.actor or "api-user",
                decision_id=normalized_decision_id,
                evidence_refs=req.evidence_refs,
                cause_type=normalized_cause_type,
                cause_id=normalized_cause_id,
                change_phase=req.change_phase,
                return_transaction=True,
            )
            model = activate_result
            transaction_id: str | None = None
            decision_trace: dict[str, Any] | None = None
            if isinstance(activate_result, dict):
                model = activate_result.get("model")
                tx = activate_result.get("transaction_id")
                if isinstance(tx, str) and len(tx.strip()) > 0:
                    transaction_id = tx
                trace = activate_result.get("decision_trace")
                if isinstance(trace, dict):
                    decision_trace = trace

            if model is None:
                raise _model_api_error(
                    status_code=500,
                    detail="Activation model state is missing from governance response",
                    category="internal_error",
                )
        except ModelRegistrationError as err:
            text = str(err)
            if "not found" in text:
                raise _model_api_error(
                    status_code=404,
                    detail=text,
                    category="not_found",
                ) from err
            raise _model_api_error(
                status_code=409,
                detail=text,
                category="activation_conflict",
            ) from err
        except HTTPException:
            raise
        except Exception as err:
            logger.exception("Unhandled /models/activate error")
            raise _model_api_error(
                status_code=500,
                detail="Internal governance model API error",
                category="internal_error",
            ) from err

        return {
            "model_name": model.model_name,
            "status": model.status,
            "active_version_id": model.active_version_id,
            "owner": model.owner,
            "transaction_id": transaction_id,
            "decision_trace": decision_trace,
        }

    @_typed_get("/models")
    def list_models(status: str | None = None) -> dict[str, Any]:
        container = _get_governance_container()
        if status is not None and status not in {"registered", "active", "disabled"}:
            raise _model_api_error(
                status_code=400,
                detail=f"Invalid status filter: {status}",
                category="bad_request",
            )
        try:
            models = container.list_kernel_models(status=status)
        except Exception as err:
            logger.exception("Unhandled /models error")
            raise _model_api_error(
                status_code=500,
                detail="Internal governance model API error",
                category="internal_error",
            ) from err
        return {
            "status": status,
            "total": len(models),
            "models": models,
        }

    @_typed_get("/models/{model_name}")
    def get_model(model_name: str, limit_runs: int = 5) -> dict[str, Any]:
        container = _get_governance_container()
        if limit_runs <= 0:
            raise _model_api_error(
                status_code=400,
                detail="limit_runs must be greater than zero",
                category="bad_request",
            )
        try:
            model_state = container.get_kernel_model_state(model_name, limit_runs=limit_runs)
        except Exception as err:
            logger.exception("Unhandled /models/{model_name} error")
            raise _model_api_error(
                status_code=500,
                detail="Internal governance model API error",
                category="internal_error",
            ) from err
        if model_state is None:
            raise _model_api_error(
                status_code=404,
                detail=f"Model not found: {model_name}",
                category="not_found",
            )
        return model_state

    @_typed_get("/models/decisions/{decision_id}")
    def get_model_decision_trace(decision_id: str) -> dict[str, Any]:
        container = _get_governance_container()
        try:
            trace = container.get_model_decision_trace(decision_id)
        except ValueError as err:
            raise _model_api_error(
                status_code=400,
                detail=str(err),
                category="bad_request",
            ) from err
        except Exception as err:
            logger.exception("Unhandled /models/decisions/{decision_id} error")
            raise _model_api_error(
                status_code=500,
                detail="Internal governance model API error",
                category="internal_error",
            ) from err

        if trace is None:
            raise _model_api_error(
                status_code=404,
                detail=f"Decision trace not found: {decision_id}",
                category="not_found",
            )
        return trace

    @_typed_get("/models/decisions/{decision_id}/explore")
    def explore_model_decision_trace(decision_id: str) -> dict[str, Any]:
        container = _get_governance_container()
        try:
            exploration = container.explore_model_decision_trace(decision_id)
        except ValueError as err:
            raise _model_api_error(
                status_code=400,
                detail=str(err),
                category="bad_request",
            ) from err
        except Exception as err:
            logger.exception("Unhandled /models/decisions/{decision_id}/explore error")
            raise _model_api_error(
                status_code=500,
                detail="Internal governance model API error",
                category="internal_error",
            ) from err

        if exploration is None:
            raise _model_api_error(
                status_code=404,
                detail=f"Decision trace not found: {decision_id}",
                category="not_found",
            )
        return exploration

    # 1. Judgment
    @_typed_post("/judgment/execute")
    def execute_judgment(req: ExecuteJudgmentRequest) -> dict[str, Any]:
        """Execute logic judgment for a triple."""
        container = _get_governance_container()
        result = container.evaluate_kernel(
            req.source,
            req.target,
            req.relation,
            actor=req.actor or "api-user",
        )
        return {
            "verdict": result.judgment.verdict,
            "confidence": result.judgment.confidence.value,
            "evidence": [e.entry.rule.id for e in result.judgment.evidence],
            "messages": list(result.judgment.conflicts)
        }

    # 2. Rule Lifecycle
    @_typed_get("/rules")
    def list_rules(state: str | None = None) -> list[dict[str, Any]]:
        """List active or all rules."""
        container = _get_governance_container()
        try:
            rules = container.list_kernel_rules(state=state)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid state: {state}") from err

        return [
            {
                "id": r.id,
                "state": r.lifecycle.current_state.value,
                "domain": r.metadata.domain,
                "version": r.provenance.version
            }
            for r in rules
        ]

    @_typed_post("/rules/{rule_id}/approve")
    def approve_rule(rule_id: str, actor: str = "api-user") -> dict[str, Any]:
        """Approve a rule."""
        try:
            container = _get_governance_container()
            asset = container.approve_kernel_rule(rule_id, actor=actor)
            return {"status": "approved", "rule_id": asset.id}
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    # 3. Model I/O (Export/Import)
    @_typed_post("/model/export")
    def export_model(req: ExportRequest) -> Response:
        """Export model as JSON."""
        target_state = None
        if req.state:
            with suppress(ValueError):
                target_state = RuleLifecycleState(req.state.upper())

        data = io_manager.export_model(target_state=target_state, domain=req.domain)

        # Return as file download
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=governance_export.json"}
        )

    # 4. Diagram
    @_typed_get("/diagram")
    def get_diagram(show_judgment: bool = True, profile: str | None = None) -> Response:
        """Get system topology diagram (Mermaid source).

        Args:
            show_judgment: Whether to visualize validity/confidence.
            profile: Optional domain/profile name to filter edges.
                     If specified, only edges defined by this profile are shown.
        """
        from ea_kernel.diagram_exporter import DiagramExporter
        from ea_kernel.graph_view import TopologyGraph

        # Determine schema to use: Base Kernel + Governance Profile (if requested)
        # By default (or if profile="GovernanceLifecycle"), we show the self-model
        target_schema = _get_governance_diagram_schema()
        container = _get_governance_container()
        kernel = getattr(container, "kernel", system)

        # Build graph from current system state
        # profile maps to domain in TopologyGraph
        graph = TopologyGraph(target_schema, kernel.corpus, domain=profile)
        exporter = DiagramExporter(graph)

        return Response(
            content=exporter.generate_mermaid(show_judgment),
            media_type="text/plain"
        )

    @_typed_post("/model/import")
    async def import_model(file: Annotated[UploadFile, File(...)]) -> dict[str, Any]:
        """Import model from JSON file."""
        try:
            content = await file.read()
            data = json.loads(content)

            report = io_manager.import_model(data)
            return report
        except json.JSONDecodeError as err:
            raise HTTPException(status_code=400, detail="Invalid JSON file") from err
        except Exception as err:
            raise HTTPException(status_code=500, detail=str(err)) from err

    # 6. Automation & Evolution
    @_typed_get("/automation/promotions")
    def get_promotion_proposals() -> list[dict[str, Any]]:
        """Get rule promotion proposals based on analysis."""
        container = _get_governance_container()
        proposals = container.get_kernel_promotion_proposals()
        return [
            {
                "id": p.proposal_id,
                "rule_id": p.rule_id,
                "change_type": p.proposal_type.value,
                "rationale": p.rationale,
                "status": p.status.value
            }
            for p in proposals
        ]

    class SimulatePromotionRequest(BaseModel):
        rule_id: str
        new_confidence: str

    @_typed_post("/simulation/what-if")
    def simulate_promotion(req: SimulatePromotionRequest) -> dict[str, Any]:
        """Simulate a rule promotion."""
        import uuid
        from datetime import UTC, datetime

        from ea_kernel.promotion_engine import ProposalStatus, ProposalType, RuleChangeProposal
        from ea_kernel.types import RuleConfidence

        try:
            RuleConfidence(req.new_confidence.lower())
        except ValueError as err:
            raise HTTPException(status_code=400, detail="Invalid confidence level") from err

        # Create a transient proposal object
        proposal = RuleChangeProposal(
            proposal_id=str(uuid.uuid4()),
            proposal_type=ProposalType.PROMOTE,
            rule_id=req.rule_id,
            proposed_by="api-user",
            proposed_at=datetime.now(UTC).isoformat() + "Z",
            rationale="Simulation request",
            evidence_report_id="",
            status=ProposalStatus.PENDING
        )

        # Simulate
        container = _get_governance_container()
        result = container.simulate_kernel_proposal(proposal)

        return {
            "simulation_id": result.simulation_id,
            "impact_level": result.impact_level.value,
            "total_decisions_analyzed": result.total_decisions_analyzed,
            "affected_decisions": result.affected_decisions,
            "safe_to_apply": result.safe_to_apply,
            "risk_factors": list(result.risk_factors),
            "verdict_changes": [
                {
                    "triple": list(c.triple),
                    "original": c.original_verdict,
                    "simulated": c.simulated_verdict,
                    "winning_rule_change": {
                        "from": c.original_winning_rule,
                        "to": c.simulated_winning_rule
                    }
                }
                for c in result.verdict_changes
            ]
        }

    # --- Kernel Schema Exploration API ---

    @_typed_get("/kernel/entities")
    def get_kernel_entities(lang: str | None = None) -> dict[str, Any]:
        """List all kernel entities grouped by layer."""
        from ea_kernel.kernel_service import list_entities
        return list_entities(lang=lang)

    @_typed_get("/kernel/relations")
    def get_kernel_relations(lang: str | None = None) -> dict[str, Any]:
        """List all kernel relations grouped by layer."""
        from ea_kernel.kernel_service import list_relations
        return list_relations(lang=lang)

    @_typed_get("/kernel/rules")
    def get_kernel_rules(group: str | None = None, relation: str | None = None) -> dict[str, Any]:
        """List kernel rules with optional group/relation filter."""
        from ea_kernel.kernel_service import list_rules as service_list_rules
        return service_list_rules(group=group, relation=relation)

    @_typed_get("/kernel/rules/{rule_id}")
    def get_kernel_rule(rule_id: str) -> dict[str, Any]:
        """Get full detail of a single kernel rule."""
        from ea_kernel.kernel_service import describe_rule
        result = describe_rule(rule_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Rule not found: {rule_id}")
        return result

    @_typed_post("/kernel/judge")
    def kernel_judge(req: ExecuteJudgmentRequest) -> dict[str, Any]:
        """Evidence-based judgment for a relationship triple."""
        from ea_kernel.kernel_service import judge
        result = judge(req.source, req.target, req.relation)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    # --- I18n API ---

    @_typed_get("/i18n/audit")
    def i18n_audit(lang: str = "ko") -> dict[str, Any]:
        """I18n translation audit report."""
        from ea_kernel.kernel_service import audit_i18n
        return audit_i18n(lang)

    @_typed_get("/i18n/audit/profiles/{name}")
    def i18n_profile_audit(name: str, lang: str = "ko") -> dict[str, Any]:
        """Profile(M1) i18n patch audit report."""
        from ea_kernel.kernel_service import audit_profile_i18n

        result = audit_profile_i18n(name=name, lang=lang)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    @_typed_get("/i18n/translations")
    def i18n_list_translations(lang: str = "ko", kind: str | None = None) -> dict[str, Any]:
        """List translations for a language."""
        from ea_kernel.kernel_service import list_translations
        return list_translations(lang, kind)

    @_typed_get("/i18n/translations/{kind}/{name}/{lang}/{field}")
    def i18n_get_translation(kind: str, name: str, lang: str, field: str) -> dict[str, Any]:
        """Get a single translation entry."""
        from ea_kernel.kernel_service import get_translation
        result = get_translation(kind, name, lang, field)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    @_typed_put("/i18n/translations/{kind}/{name}/{lang}/{field}")
    def i18n_update_translation(
        kind: str, name: str, lang: str, field: str, req: UpdateTranslationRequest,
    ) -> dict[str, Any]:
        """Update a translation entry."""
        from ea_kernel.kernel_service import update_translation
        result = update_translation(kind, name, lang, field, req.value)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    @_typed_get("/i18n/translations/{kind}/{name}/{lang}/{field}/history")
    def i18n_translation_history(kind: str, name: str, lang: str, field: str) -> dict[str, Any]:
        """Get translation change history."""
        from ea_kernel.kernel_service import translation_history
        return translation_history(kind, name, lang, field)

    @_typed_get("/layers/{layer_key}/stack")
    def get_layer_stack(
        layer_key: str,
        lang: str | None = None,
        m0_limit: int = 20,
    ) -> dict[str, Any]:
        """Unified layer stack view — M2(schema) / M1(topology) / M0(runtime snapshots+models)."""
        if m0_limit <= 0:
            raise HTTPException(status_code=400, detail="m0_limit must be greater than zero")

        from ea_governance.governance_service import layer_schema as service_layer_schema
        from ea_kernel.kernel_service import profile_topology as service_profile_topology

        m2 = service_layer_schema(layer_key, lang=lang)
        if "error" in m2:
            raise HTTPException(status_code=404, detail=m2["error"])

        profile_name = str(m2["profile_name"])
        m1 = service_profile_topology(
            profile_name=profile_name,
            cross_layer=False,
            lang=lang,
            view_mode="summary",
            surface_only=True,
            max_edges=900,
        )
        if "error" in m1:
            raise HTTPException(status_code=404, detail=m1["error"])

        container = _get_governance_container()
        try:
            snapshots = container.list_layer_snapshots(layer_key)
        except ValueError as err:
            raise HTTPException(status_code=404, detail=str(err)) from err

        snapshots_sorted = sorted(
            snapshots,
            key=lambda item: str(item.get("updated_at", "")),
            reverse=True,
        )
        snapshot_items = [
            {
                "layer": str(item.get("layer", layer_key)),
                "model_id": str(item.get("model_id", "")),
                "updated_at": str(item.get("updated_at", "")),
                "kind": str((item.get("payload") or {}).get("kind", "unknown")),
                "payload_keys": sorted(((item.get("payload") or {}).keys())),
            }
            for item in snapshots_sorted[:m0_limit]
        ]

        all_models = container.list_kernel_models()
        model_candidates: list[dict[str, Any]] = []
        for model in all_models:
            model_name = str(model.get("model_name", ""))
            score, rules = _layer_model_match(model_name, layer_key, profile_name)
            if score <= 0:
                continue
            model_candidates.append(
                {
                    "model_id": model.get("model_id"),
                    "model_name": model_name,
                    "owner": model.get("owner"),
                    "status": model.get("status"),
                    "active_version_id": model.get("active_version_id"),
                    "updated_at": model.get("updated_at"),
                    "score": score,
                    "match_rules": rules,
                }
            )
        model_candidates.sort(
            key=lambda item: (-int(item["score"]), str(item["model_name"]).lower()),
        )

        return {
            "layer_key": layer_key,
            "profile_name": profile_name,
            "version": m2.get("version", ""),
            "lang": lang or "en",
            "m2": m2,
            "m1": m1,
            "m0": {
                "snapshot_total": len(snapshots_sorted),
                "snapshots": snapshot_items,
                "model_candidate_total": len(model_candidates),
                "model_candidates": model_candidates[:m0_limit],
            },
        }

    # --- Profile Graph Traversal (Profile Topology API) ---

    @_typed_get("/profiles")
    def list_profiles() -> list[dict[str, Any]]:
        """List all registered profiles."""
        from ea_kernel.profile_registry import ProfileRegistry
        registry = ProfileRegistry()
        registry.bootstrap()
        return [
            {"name": p.name, "version": p.version}
            for p in registry.list_all()
        ]

    @_typed_get("/profiles/{name}")
    def get_profile(name: str, lang: str | None = None) -> dict[str, Any]:
        """Get profile metadata."""
        from ea_kernel.kernel_service import describe_profile
        result = describe_profile(name=name, lang=lang)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Profile not found: {name}")
        return result

    @_typed_get("/profiles/{name}/topology")
    def get_profile_topology(
        name: str,
        cross_layer: bool = False,
        lang: str | None = None,
        max_edges: int | None = None,
        view_mode: str = "raw",
        surface_only: bool = False,
        domain_scope: str = "all",
        focus: str | None = None,
        focus_relation: str | None = None,
        focus_layer: str | None = None,
        focus_actor: str | None = None,
        focus_topic: str | None = None,
        focus_depth: int | None = None,
    ) -> dict[str, Any]:
        """Get full profile topology graph (nodes + edges).

        When *cross_layer* is true, only edges connecting elements from
        different domain layers are returned.
        """
        if max_edges is not None and max_edges <= 0:
            raise HTTPException(status_code=400, detail="max_edges must be greater than zero")
        if view_mode not in {"raw", "summary", "focus"}:
            raise HTTPException(status_code=400, detail="view_mode must be one of: raw, summary, focus")
        if domain_scope not in {"all", "owned", "bridge"}:
            raise HTTPException(status_code=400, detail="domain_scope must be one of: all, owned, bridge")
        if focus is not None and focus not in {"core", "relation", "layer", "actor", "topic"}:
            raise HTTPException(status_code=400, detail="focus must be one of: core, relation, layer, actor, topic")
        if focus_depth is not None and focus_depth <= 0:
            raise HTTPException(status_code=400, detail="focus_depth must be greater than zero")
        if view_mode != "focus" and (
            focus is not None
            or focus_relation is not None
            or focus_layer is not None
            or focus_actor is not None
            or focus_topic is not None
            or focus_depth is not None
        ):
            raise HTTPException(
                status_code=400,
                detail="focus params are only valid when view_mode=focus",
            )
        if view_mode == "focus" and focus == "relation" and not focus_relation:
            raise HTTPException(status_code=400, detail="focus_relation is required when focus=relation")
        if view_mode == "focus" and focus == "layer" and not focus_layer:
            raise HTTPException(status_code=400, detail="focus_layer is required when focus=layer")
        if view_mode == "focus" and focus == "topic" and not focus_topic:
            raise HTTPException(status_code=400, detail="focus_topic is required when focus=topic")
        from ea_kernel.kernel_service import profile_topology
        result = profile_topology(
            profile_name=name,
            cross_layer=cross_layer,
            lang=lang,
            max_edges=max_edges,
            view_mode=view_mode,
            surface_only=surface_only,
            domain_scope=domain_scope,
            focus=focus,
            focus_relation=focus_relation,
            focus_layer=focus_layer,
            focus_actor=focus_actor,
            focus_topic=focus_topic,
            focus_depth=focus_depth,
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    @_typed_get("/profiles/{name}/projection")
    def get_profile_projection(
        name: str,
        level: str = "l0",
        lens: str | None = None,
        cross_layer: bool = False,
        domain_scope: str = "all",
        lang: str | None = None,
        actor: str | None = None,
        depth: int | None = None,
        max_edges: int | None = None,
    ) -> dict[str, Any]:
        """Get projection-layer topology view (L0~L4 abstraction levels)."""
        from ea_kernel.kernel_service import profile_projection

        result = profile_projection(
            profile_name=name,
            level=level,
            lens=lens,
            cross_layer=cross_layer,
            domain_scope=domain_scope,
            lang=lang,
            actor=actor,
            depth=depth,
            max_edges=max_edges,
        )
        if "error" in result:
            message = str(result["error"]).lower()
            status_code = 404 if "profile not found" in message else 400
            detail: Any
            if "policy_error" in result:
                detail = {
                    "error": result["error"],
                    "policy_error": result["policy_error"],
                }
            else:
                detail = result["error"]
            raise HTTPException(status_code=status_code, detail=detail)
        return result

    @_typed_get("/profiles/{name}/composed")
    def get_profile_composed_topology(
        name: str,
        lang: str | None = None,
        domain_scope: str = "all",
        max_edges: int | None = None,
        surface_only: bool = False,
        include_profiles: str | None = None,
        focus: str | None = None,
        focus_relation: str | None = None,
        focus_layer: str | None = None,
        focus_actor: str | None = None,
        focus_topic: str | None = None,
        focus_depth: int | None = None,
    ) -> dict[str, Any]:
        """Get cross-profile composed M1 topology anchored by a profile."""
        if max_edges is not None and max_edges <= 0:
            raise HTTPException(status_code=400, detail="max_edges must be greater than zero")
        if domain_scope not in {"all", "owned", "bridge"}:
            raise HTTPException(status_code=400, detail="domain_scope must be one of: all, owned, bridge")
        if focus is not None and focus not in {"core", "relation", "layer", "actor", "topic"}:
            raise HTTPException(status_code=400, detail="focus must be one of: core, relation, layer, actor, topic")
        if focus is None and (
            focus_relation is not None
            or focus_layer is not None
            or focus_actor is not None
            or focus_topic is not None
            or focus_depth is not None
        ):
            raise HTTPException(status_code=400, detail="focus params require focus mode")
        if focus == "relation" and not focus_relation:
            raise HTTPException(status_code=400, detail="focus_relation is required when focus=relation")
        if focus == "layer" and not focus_layer:
            raise HTTPException(status_code=400, detail="focus_layer is required when focus=layer")
        if focus == "topic" and not focus_topic:
            raise HTTPException(status_code=400, detail="focus_topic is required when focus=topic")
        if focus_depth is not None and focus_depth <= 0:
            raise HTTPException(status_code=400, detail="focus_depth must be greater than zero")

        profile_filter: list[str] | None = None
        if include_profiles is not None:
            parsed = [item.strip() for item in include_profiles.split(",") if item.strip()]
            profile_filter = parsed or None

        from ea_kernel.kernel_service import profile_composed_topology

        result = profile_composed_topology(
            profile_name=name,
            lang=lang,
            domain_scope=domain_scope,
            max_edges=max_edges,
            surface_only=surface_only,
            include_profiles=profile_filter,
            focus=focus,
            focus_relation=focus_relation,
            focus_layer=focus_layer,
            focus_actor=focus_actor,
            focus_topic=focus_topic,
            focus_depth=focus_depth,
        )
        if "error" in result:
            message = str(result["error"]).lower()
            status_code = 404 if "profile not found" in message else 400
            raise HTTPException(status_code=status_code, detail=result["error"])
        return result

    @_typed_get("/profiles/{name}/reachable")
    def get_profile_reachable(
        name: str,
        element: str = "",
        max_depth: int = 3,
        relation: str | None = None,
    ) -> dict[str, Any]:
        """Get reachable elements from a profile element."""
        if not element:
            raise HTTPException(status_code=400, detail="Missing required query param: element")
        from ea_kernel.kernel_service import profile_reachable
        result = profile_reachable(
            profile_name=name,
            element=element,
            max_depth=max_depth,
            relation=relation,
        )
        if "error" in result:
            status = 404 if "not found" in result["error"].lower() else 400
            raise HTTPException(status_code=status, detail=result["error"])
        return result

    class ElementScopeRequest(BaseModel):
        elements: list[str]
        max_depth: int = 4

    @_typed_post("/profiles/{name}/element-scope")
    def post_profile_element_scope(name: str, req: ElementScopeRequest) -> dict[str, Any]:
        """Compute union of reachable sets from multiple seed elements."""
        from ea_kernel.kernel_service import profile_element_scope
        result = profile_element_scope(
            profile_name=name,
            elements=req.elements,
            max_depth=req.max_depth,
        )
        if "error" in result:
            status = 404 if "not found" in result["error"].lower() else 400
            raise HTTPException(status_code=status, detail=result["error"])
        return result

    @_typed_get("/profiles/{name}/paths")
    def get_profile_paths(
        name: str,
        source: str = "",
        target: str = "",
        max_depth: int = 5,
        relation: str | None = None,
    ) -> dict[str, Any]:
        """Find paths between two profile elements."""
        if not source or not target:
            raise HTTPException(status_code=400, detail="Missing required query params: source, target")
        from ea_kernel.kernel_service import profile_paths
        result = profile_paths(
            profile_name=name,
            source=source,
            target=target,
            max_depth=max_depth,
            relation=relation,
        )
        if "error" in result:
            status = 404 if "not found" in result["error"].lower() else 400
            raise HTTPException(status_code=status, detail=result["error"])
        return result

    @_typed_get("/profiles/{name}/impact")
    def get_profile_impact(
        name: str,
        element: str = "",
        direction: str = "both",
        max_depth: int = 3,
    ) -> dict[str, Any]:
        """Impact analysis for a profile element."""
        if not element:
            raise HTTPException(status_code=400, detail="Missing required query param: element")
        from ea_kernel.kernel_service import profile_impact
        result = profile_impact(
            profile_name=name,
            element=element,
            direction=direction,
            max_depth=max_depth,
        )
        if "error" in result:
            status = 404 if "not found" in result["error"].lower() else 400
            raise HTTPException(status_code=status, detail=result["error"])
        return result

    # --- Profile Version Management ---

    @_typed_get("/profiles/{name}/versions")
    def get_profile_versions(name: str, limit: int = 50) -> dict[str, Any]:
        """List profile version history (newest first)."""
        from ea_kernel.kernel_service import profile_version_history
        return profile_version_history(profile_name=name, limit=limit)

    @_typed_get("/profiles/{name}/versions/diff")
    def get_profile_version_diff(name: str, a: str = "", b: str = "") -> dict[str, Any]:
        """Diff two profile versions."""
        if not a or not b:
            raise HTTPException(status_code=400, detail="Missing required query params: a, b")
        from ea_kernel.kernel_service import profile_version_diff
        result = profile_version_diff(profile_name=name, version_a=a, version_b=b)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    @_typed_get("/profiles/{name}/versions/{version}")
    def get_profile_version_detail(name: str, version: str) -> dict[str, Any]:
        """Get detailed info about a specific profile version."""
        from ea_kernel.kernel_service import profile_version_detail
        result = profile_version_detail(profile_name=name, version=version)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    @_typed_get("/profiles/{name}/tags")
    def get_profile_tags(name: str) -> dict[str, Any]:
        """List all tags for a profile."""
        from ea_kernel.kernel_service import profile_version_tags
        return profile_version_tags(profile_name=name)

    # --- Governance Service API (plugin from ea-governance) ---
    try:
        from ea_governance.api_router import governance_router, layer_schema_router
        app.include_router(governance_router)
        app.include_router(layer_schema_router)
    except ImportError:
        pass  # ea-governance not installed; governance query endpoints disabled

    # --- Governance Flow Logic (Phase 8 Extension) ---
    @_typed_get("/governance/flow/{anchor_id}")
    def get_flow_logic(anchor_id: str) -> dict[str, Any]:
        """
        Retrieves the logic specification (Flow/Schemas) anchored to a kernel element.
        Demonstrates how Flow refines Kernel.
        """
        # In a real environment, we'd have a global Container or Session
        # For demo, we instantiate a lightweight container pointing to the same data
        container = _get_governance_container()

        spec = container.get_flow_spec(anchor_id)
        if not spec:
            raise HTTPException(status_code=404, detail=f"No flow logic found for anchor: {anchor_id}")

        if not isinstance(spec, dict):
            raise HTTPException(status_code=500, detail="Invalid flow spec type")

        return spec

    # --- Needs API ---

    @_typed_get("/needs/catalogs")
    def list_needs_catalogs() -> list[dict[str, Any]]:
        """List all needs catalogs with summary info."""
        container = _get_governance_container()
        try:
            catalogs = container.list_needs_catalogs()
        except Exception as err:
            logger.exception("Unhandled /needs/catalogs error")
            raise _model_api_error(
                status_code=500, detail="Internal needs API error", category="internal_error",
            ) from err
        result = []
        for cat in catalogs:
            result.append({
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "needs_count": len(cat.needs),
                "stakeholder_count": len(cat.stakeholders),
                "use_case_count": len(cat.use_cases),
                "updated_at": cat.updated_at,
            })
        return result

    @_typed_post("/needs/catalogs")
    def create_needs_catalog(req: CreateNeedsCatalogRequest) -> dict[str, Any]:
        """Create a new needs catalog."""
        container = _get_governance_container()
        try:
            result = container.create_needs_catalog(
                req.name, req.description, actor="api-user",
            )
            return result
        except ValueError as err:
            raise _model_api_error(
                status_code=400, detail=str(err), category="bad_request",
            ) from err
        except Exception as err:
            logger.exception("Unhandled POST /needs/catalogs error")
            raise _model_api_error(
                status_code=500, detail="Internal needs API error", category="internal_error",
            ) from err

    @_typed_get("/needs/catalogs/{catalog_id}")
    def get_needs_catalog(catalog_id: str) -> dict[str, Any]:
        """Get full catalog detail."""
        container = _get_governance_container()
        try:
            cat = container.get_needs_catalog(catalog_id)
        except Exception as err:
            logger.exception("Unhandled /needs/catalogs/{catalog_id} error")
            raise _model_api_error(
                status_code=500, detail="Internal needs API error", category="internal_error",
            ) from err
        if cat is None:
            raise _model_api_error(
                status_code=404, detail=f"Catalog not found: {catalog_id}", category="not_found",
            )
        return json.loads(cat.to_json())

    @_typed_get("/needs/catalogs/{catalog_id}/needs")
    def list_catalog_needs(
        catalog_id: str,
        status: str | None = None,
        priority: str | None = None,
        stakeholder_id: str | None = None,
        purpose: str | None = None,
        complexity: str | None = None,
        use_case_id: str | None = None,
        cause_type: str | None = None,
        kernel_change_phase: str | None = None,
        decision_id: str | None = None,
        decision_linked: bool | None = None,
    ) -> list[dict[str, Any]]:
        """List needs in a catalog with optional filters."""
        container = _get_governance_container()
        try:
            cat = container.get_needs_catalog(catalog_id)
        except Exception as err:
            logger.exception("Unhandled /needs/catalogs/{catalog_id}/needs error")
            raise _model_api_error(
                status_code=500, detail="Internal needs API error", category="internal_error",
            ) from err
        if cat is None:
            raise _model_api_error(
                status_code=404, detail=f"Catalog not found: {catalog_id}", category="not_found",
            )
        needs = cat.needs
        if status:
            needs = [n for n in needs if n.status.value.lower() == status.lower()]
        if priority:
            needs = [n for n in needs if n.priority.value.lower() == priority.lower()]
        if stakeholder_id:
            needs = [n for n in needs if n.statement.stakeholder_id == stakeholder_id]
        if purpose:
            needs = [
                n for n in needs
                if str(getattr(n.statement.purpose, "value", n.statement.purpose)).lower() == purpose.lower()
            ]
        if complexity:
            needs = [
                n for n in needs
                if str(getattr(n.statement.complexity, "value", n.statement.complexity)).lower() == complexity.lower()
            ]
        if use_case_id:
            needs = [n for n in needs if n.statement.use_case_id == use_case_id or n.use_case_id == use_case_id]
        if cause_type:
            needs = [
                n for n in needs
                if any(
                    str(getattr(ct, "value", ct)).lower() == cause_type.lower()
                    for ct in n.statement.cause_types
                )
            ]
        if kernel_change_phase:
            needs = [
                n for n in needs
                if str(getattr(n.kernel_change_phase, "value", n.kernel_change_phase)).lower()
                == kernel_change_phase.lower()
            ]
        if decision_id:
            needs = [
                n for n in needs
                if decision_id in getattr(n, "inherited_from_decisions", [])
            ]
        if decision_linked is not None:
            needs = [
                n for n in needs
                if (
                    len(getattr(n, "inherited_from_decisions", [])) > 0
                    or len(getattr(n, "decision_evidence_refs", [])) > 0
                ) == decision_linked
            ]
        result = []
        for n in needs:
            inherited_from_decisions = list(getattr(n, "inherited_from_decisions", []))
            decision_evidence_refs = list(getattr(n, "decision_evidence_refs", []))
            result.append({
                "id": n.id,
                "lineage_id": n.lineage_id,
                "version": n.version,
                "status": n.status.value,
                "priority": n.priority.value,
                "kernel_change_phase": str(getattr(n.kernel_change_phase, "value", n.kernel_change_phase)),
                "stakeholder_id": n.statement.stakeholder_id,
                "action": n.statement.desire.action,
                "subject": n.statement.desire.subject,
                "target": n.statement.desire.target,
                "kernel_refs": list(n.statement.kernel_refs),
                "tags": list(n.statement.tags),
                "purpose": str(getattr(n.statement.purpose, "value", n.statement.purpose)),
                "cause_types": [str(getattr(ct, "value", ct)) for ct in n.statement.cause_types],
                "complexity": str(getattr(n.statement.complexity, "value", n.statement.complexity)),
                "use_case_id": n.statement.use_case_id,
                "decision_evidence_refs": decision_evidence_refs,
                "inherited_from_decisions": inherited_from_decisions,
                "decision_linked": bool(inherited_from_decisions or decision_evidence_refs),
                "updated_at": n.updated_at,
            })
        return result

    @_typed_get("/needs/catalogs/{catalog_id}/needs/{need_id}")
    def get_catalog_need(catalog_id: str, need_id: str) -> dict[str, Any]:
        """Get a single need with full detail."""
        container = _get_governance_container()
        try:
            cat = container.get_needs_catalog(catalog_id)
        except Exception as err:
            logger.exception("Unhandled /needs/catalogs/{catalog_id}/needs/{need_id} error")
            raise _model_api_error(
                status_code=500, detail="Internal needs API error", category="internal_error",
            ) from err
        if cat is None:
            raise _model_api_error(
                status_code=404, detail=f"Catalog not found: {catalog_id}", category="not_found",
            )
        need = cat.get_need(need_id)
        if need is None:
            raise _model_api_error(
                status_code=404, detail=f"Need not found: {need_id}", category="not_found",
            )
        process_units = cat.process_units_for_need(need_id)
        return {
            "id": need.id,
            "lineage_id": need.lineage_id,
            "version": need.version,
            "status": need.status.value,
            "priority": need.priority.value,
            "kernel_change_phase": str(getattr(need.kernel_change_phase, "value", need.kernel_change_phase)),
            "stakeholder_id": need.statement.stakeholder_id,
            "action": need.statement.desire.action,
            "subject": need.statement.desire.subject,
            "target": need.statement.desire.target,
            "justifications": [
                {"type": j.type.value if hasattr(j.type, "value") else str(j.type), "description": j.description}
                for j in need.statement.justifications
            ],
            "kernel_refs": list(need.statement.kernel_refs),
            "tags": list(need.statement.tags),
            "purpose": need.statement.purpose.value if hasattr(need.statement.purpose, "value") else str(need.statement.purpose),
            "cause_types": [ct.value if hasattr(ct, "value") else str(ct) for ct in need.statement.cause_types],
            "complexity": need.statement.complexity.value if hasattr(need.statement.complexity, "value") else str(need.statement.complexity),
            "use_case_id": need.statement.use_case_id,
            "decision_evidence_refs": list(getattr(need, "decision_evidence_refs", [])),
            "inherited_from_decisions": list(getattr(need, "inherited_from_decisions", [])),
            "decision_linked": bool(
                list(getattr(need, "decision_evidence_refs", []))
                or list(getattr(need, "inherited_from_decisions", [])),
            ),
            "created_at": need.created_at,
            "updated_at": need.updated_at,
            "process_units": [
                {
                    "id": pu.id,
                    "stage": pu.stage.value if hasattr(pu.stage, "value") else str(pu.stage),
                    "label": pu.label,
                    "description": pu.description,
                    "sequence": pu.sequence,
                }
                for pu in process_units
            ],
        }

    @_typed_post("/needs/catalogs/{catalog_id}/stakeholders")
    def add_needs_stakeholder(catalog_id: str, req: AddStakeholderRequest) -> dict[str, Any]:
        """Add a stakeholder to a catalog."""
        container = _get_governance_container()
        try:
            result = container.add_needs_stakeholder(
                catalog_id, name=req.name, role=req.role, context=req.context, actor="api-user",
            )
            return result
        except ValueError as err:
            raise _model_api_error(
                status_code=400, detail=str(err), category="bad_request",
            ) from err
        except Exception as err:
            logger.exception("Unhandled POST /needs/catalogs/{catalog_id}/stakeholders error")
            raise _model_api_error(
                status_code=500, detail="Internal needs API error", category="internal_error",
            ) from err

    @_typed_post("/needs/catalogs/{catalog_id}/use-cases")
    def add_needs_use_case(catalog_id: str, req: AddNeedsUseCaseRequest) -> dict[str, Any]:
        """Add a needs use-case in a catalog."""
        container = _get_governance_container()
        try:
            result = container.add_needs_use_case(
                catalog_id,
                title=req.title,
                actor_name=req.actor,
                situation=req.situation,
                purpose=req.purpose,
                outcome=req.outcome,
                tags=req.tags,
                actor="api-user",
            )
            return result
        except ValueError as err:
            raise _model_api_error(
                status_code=400, detail=str(err), category="bad_request",
            ) from err
        except Exception as err:
            logger.exception("Unhandled POST /needs/catalogs/{catalog_id}/use-cases error")
            raise _model_api_error(
                status_code=500, detail="Internal needs API error", category="internal_error",
            ) from err

    @_typed_post("/needs/catalogs/{catalog_id}/needs")
    def express_need(catalog_id: str, req: ExpressNeedRequest) -> dict[str, Any]:
        """Express a new need in a catalog."""
        container = _get_governance_container()
        try:
            result = container.express_need_in_catalog(
                catalog_id,
                stakeholder_id=req.stakeholder_id,
                action=req.action,
                subject=req.subject,
                target=req.target,
                justifications=req.justifications,
                priority=req.priority,
                kernel_refs=req.kernel_refs,
                tags=req.tags,
                use_case_id=req.use_case_id,
                cause_types=req.cause_types,
                purpose=req.purpose,
                complexity=req.complexity,
                kernel_change_phase=req.kernel_change_phase,
                actor="api-user",
            )
            return result
        except ValueError as err:
            raise _model_api_error(
                status_code=400, detail=str(err), category="bad_request",
            ) from err
        except Exception as err:
            logger.exception("Unhandled POST /needs/catalogs/{catalog_id}/needs error")
            raise _model_api_error(
                status_code=500, detail="Internal needs API error", category="internal_error",
            ) from err

    @_typed_post("/needs/catalogs/{catalog_id}/needs/{need_id}/revise")
    def revise_need(catalog_id: str, need_id: str, req: ReviseNeedRequest) -> dict[str, Any]:
        """Create a revised version of an existing need."""
        container = _get_governance_container()
        try:
            changes = req.model_dump(exclude_unset=True)
            if not changes:
                raise ValueError("At least one change field must be provided")
            result = container.revise_need_in_catalog(
                catalog_id,
                need_id,
                changes=changes,
                actor="api-user",
            )
            return result
        except ValueError as err:
            raise _model_api_error(
                status_code=400, detail=str(err), category="bad_request",
            ) from err
        except Exception as err:
            logger.exception("Unhandled POST /needs/catalogs/{catalog_id}/needs/{need_id}/revise error")
            raise _model_api_error(
                status_code=500, detail="Internal needs API error", category="internal_error",
            ) from err

    @_typed_post("/needs/catalogs/{catalog_id}/needs/{need_id}/process-units")
    def add_need_process_unit(
        catalog_id: str,
        need_id: str,
        req: AddNeedProcessUnitRequest,
    ) -> dict[str, Any]:
        """Add process-model unit to a need."""
        container = _get_governance_container()
        try:
            result = container.add_need_process_unit(
                catalog_id,
                need_id,
                stage=req.stage,
                label=req.label,
                description=req.description,
                sequence=req.sequence,
                metadata=req.metadata,
                actor="api-user",
            )
            return result
        except ValueError as err:
            raise _model_api_error(
                status_code=400, detail=str(err), category="bad_request",
            ) from err
        except Exception as err:
            logger.exception(
                "Unhandled POST /needs/catalogs/{catalog_id}/needs/{need_id}/process-units error",
            )
            raise _model_api_error(
                status_code=500, detail="Internal needs API error", category="internal_error",
            ) from err

    @_typed_post("/needs/catalogs/{catalog_id}/needs/{need_id}/inherit-decision-evidence")
    def inherit_need_decision_evidence(
        catalog_id: str,
        need_id: str,
        req: InheritNeedDecisionEvidenceRequest,
    ) -> dict[str, Any]:
        """Inherit evidence references from a decision into a need."""
        container = _get_governance_container()
        try:
            result = container.inherit_need_decision_evidence(
                catalog_id,
                need_id,
                decision_id=req.decision_id,
                evidence_refs=req.evidence_refs,
                kernel_change_phase=req.kernel_change_phase,
                actor="api-user",
            )
            return result
        except ValueError as err:
            raise _model_api_error(
                status_code=400, detail=str(err), category="bad_request",
            ) from err
        except Exception as err:
            logger.exception(
                "Unhandled POST /needs/catalogs/{catalog_id}/needs/{need_id}/inherit-decision-evidence error",
            )
            raise _model_api_error(
                status_code=500, detail="Internal needs API error", category="internal_error",
            ) from err

    @_typed_get("/needs/catalogs/{catalog_id}/history")
    def get_needs_catalog_history(catalog_id: str) -> list[dict[str, Any]]:
        """Get transaction history for a catalog."""
        container = _get_governance_container()
        try:
            history = container.get_needs_catalog_history(catalog_id)
            return history
        except Exception as err:
            logger.exception("Unhandled /needs/catalogs/{catalog_id}/history error")
            raise _model_api_error(
                status_code=500, detail="Internal needs API error", category="internal_error",
            ) from err

    @_typed_get("/needs/by-kernel-ref/{ref}")
    def needs_by_kernel_ref(ref: str) -> dict[str, Any]:
        """Find needs across all catalogs that reference a kernel element."""
        container = _get_governance_container()
        try:
            catalogs = container.list_needs_catalogs()
        except Exception as err:
            logger.exception("Unhandled /needs/by-kernel-ref/{ref} error")
            raise _model_api_error(
                status_code=500, detail="Internal needs API error", category="internal_error",
            ) from err
        matches = []
        for cat in catalogs:
            for need in cat.needs_by_kernel_ref(ref):
                matches.append({
                    "catalog_id": cat.id,
                    "catalog_name": cat.name,
                    "need_id": need.id,
                    "action": need.statement.desire.action,
                    "subject": need.statement.desire.subject,
                    "status": need.status.value,
                    "kernel_change_phase": str(
                        getattr(need.kernel_change_phase, "value", need.kernel_change_phase),
                    ),
                })
        return {"kernel_ref": ref, "matches": matches}

    # --- System Self-Exploration (Phase 9 Extension) ---
    @_typed_get("/system/self-model")
    def get_system_self_model() -> Response:
        """
        Returns a Mermaid diagram of the EA System's own internal architecture.
        Enables autonomic exploration of the Brain/Body/Physics layers.
        """
        container = _get_governance_container()

        try:
            mermaid_src = container.get_self_model_diagram()
            return Response(content=mermaid_src, media_type="text/plain")
        except Exception as err:
            raise HTTPException(status_code=500, detail=f"Failed to project self-model: {err}") from err

    # ========== Business Model & Tag-Schema Registry ==========

    @_typed_post("/business")
    def create_business(req: CreateBusinessRequest) -> dict[str, Any]:
        try:
            return business_svc.create_business(req.name, req.description)
        except ValueError as err:
            raise _model_api_error(
                status_code=400, detail=str(err), category="bad_request",
            ) from err

    @_typed_get("/business")
    def list_businesses() -> list[dict[str, Any]]:
        return business_svc.list_businesses()

    @_typed_get("/business/{bid}")
    def get_business(bid: str) -> dict[str, Any]:
        try:
            return business_svc.get_business(bid)
        except (ValueError, KeyError) as err:
            code = 400 if isinstance(err, ValueError) else 404
            raise _model_api_error(
                status_code=code,
                detail=str(err),
                category="bad_request" if code == 400 else "not_found",
            ) from err

    @app.delete("/business/{bid}")
    def delete_business(bid: str) -> dict[str, str]:
        try:
            business_svc.delete_business(bid)
            return {"status": "deleted", "bid": bid}
        except (ValueError, KeyError) as err:
            code = 400 if isinstance(err, ValueError) else 404
            raise _model_api_error(
                status_code=code,
                detail=str(err),
                category="bad_request" if code == 400 else "not_found",
            ) from err

    @_typed_post("/business/{bid}/tags")
    def create_tag(bid: str, req: CreateTagSchemaRequest) -> dict[str, Any]:
        try:
            return business_svc.create_tag(bid, req.model_dump())
        except (ValueError, KeyError) as err:
            code = 400 if isinstance(err, ValueError) else 404
            raise _model_api_error(
                status_code=code,
                detail=str(err),
                category="bad_request" if code == 400 else "not_found",
            ) from err

    @_typed_get("/business/{bid}/tags")
    def list_tags(bid: str) -> list[dict[str, Any]]:
        try:
            return business_svc.list_tags(bid)
        except (ValueError, KeyError) as err:
            code = 400 if isinstance(err, ValueError) else 404
            raise _model_api_error(
                status_code=code,
                detail=str(err),
                category="bad_request" if code == 400 else "not_found",
            ) from err

    @_typed_get("/business/{bid}/tags/{tag}")
    def get_tag(bid: str, tag: str) -> dict[str, Any]:
        try:
            return business_svc.get_tag(bid, tag)
        except (ValueError, KeyError) as err:
            code = 400 if isinstance(err, ValueError) else 404
            raise _model_api_error(
                status_code=code,
                detail=str(err),
                category="bad_request" if code == 400 else "not_found",
            ) from err

    @_typed_put("/business/{bid}/tags/{tag}")
    def update_tag(bid: str, tag: str, req: UpdateTagSchemaRequest) -> dict[str, Any]:
        try:
            data = {k: v for k, v in req.model_dump().items() if v is not None}
            return business_svc.update_tag(bid, tag, data)
        except (ValueError, KeyError) as err:
            code = 400 if isinstance(err, ValueError) else 404
            raise _model_api_error(
                status_code=code,
                detail=str(err),
                category="bad_request" if code == 400 else "not_found",
            ) from err

    @app.delete("/business/{bid}/tags/{tag}")
    def delete_tag(bid: str, tag: str) -> dict[str, str]:
        try:
            business_svc.delete_tag(bid, tag)
            return {"status": "deleted", "bid": bid, "tag": tag}
        except (ValueError, KeyError) as err:
            code = 400 if isinstance(err, ValueError) else 404
            raise _model_api_error(
                status_code=code,
                detail=str(err),
                category="bad_request" if code == 400 else "not_found",
            ) from err

    @_typed_get("/business/{bid}/indexing-spec")
    def get_indexing_spec(bid: str) -> dict[str, Any]:
        try:
            return business_svc.derive_indexing_spec(bid)
        except (ValueError, KeyError) as err:
            code = 400 if isinstance(err, ValueError) else 404
            raise _model_api_error(
                status_code=code,
                detail=str(err),
                category="bad_request" if code == 400 else "not_found",
            ) from err

    @_typed_get("/business/{bid}/export")
    def export_business(bid: str) -> dict[str, Any]:
        try:
            return business_svc.export_business(bid)
        except (ValueError, KeyError) as err:
            code = 400 if isinstance(err, ValueError) else 404
            raise _model_api_error(
                status_code=code,
                detail=str(err),
                category="bad_request" if code == 400 else "not_found",
            ) from err

    class ImportBusinessRequest(BaseModel):
        meta: dict[str, Any]
        tags: list[dict[str, Any]] = []

    @_typed_post("/business/import")
    def import_business(req: ImportBusinessRequest) -> dict[str, Any]:
        try:
            return business_svc.import_business(req.model_dump())
        except ValueError as err:
            raise _model_api_error(
                status_code=400, detail=str(err), category="bad_request",
            ) from err

    return app

# --- Entry Point for Dev ---
if __name__ == "__main__":
    from ea_kernel.schema_loader import load_kernel_schema_from_package

    schema = load_kernel_schema_from_package()
    data_dir = get_data_dir()

    app = create_app(data_dir, schema)

    host = os.getenv("EA_KERNEL_HOST", "0.0.0.0")
    port = int(os.getenv("EA_KERNEL_PORT", "8000"))

    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
