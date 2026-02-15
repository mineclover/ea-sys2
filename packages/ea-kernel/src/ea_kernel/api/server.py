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

    class ModelValidateRequest(BaseModel):
        model_name: str
        version: str
        context: dict[str, Any] | None = None
        decision_id: str | None = None
        evidence_refs: list[str] | None = None

    class ModelActivateRequest(BaseModel):
        model_name: str
        version: str
        actor: str | None = "api-user"
        decision_id: str | None = None
        evidence_refs: list[str] | None = None

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
            result = container.register_kernel_model(
                req.profile_toml,
                owner=req.owner or "api-user",
                created_by=req.created_by or "api-user",
                model_name=req.model_name,
                activate=bool(req.activate),
                context={"source": "api:models/register", **(req.context or {})},
                on_exists=req.on_exists or "validate",
                actor=req.created_by or "api-user",
                decision_id=req.decision_id,
                evidence_refs=req.evidence_refs,
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
            validate_result = container.validate_kernel_model(
                req.model_name,
                req.version,
                context={"source": "api:models/validate", **(req.context or {})},
                actor="api-user",
                decision_id=req.decision_id,
                evidence_refs=req.evidence_refs,
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
            activate_result = container.activate_kernel_model(
                req.model_name,
                req.version,
                actor=req.actor or "api-user",
                decision_id=req.decision_id,
                evidence_refs=req.evidence_refs,
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
