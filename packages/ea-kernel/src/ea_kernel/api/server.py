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
from ea_kernel.model_registration import (
    KernelModelRegistrationService,
    ModelRegistrationError,
)
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

    def _get_governance_container() -> Any:
        cached = getattr(app.state, "governance_container", None)
        if cached is not None:
            return cached
        from ea_governance.facade import GovernanceContainer

        container = GovernanceContainer(data_dir, schema)
        app.state.governance_container = container
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
    registration = KernelModelRegistrationService(data_dir / "default" / "profiles.db", schema)
    app.state.system = system  # Expose for testing
    app.state.registration = registration
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

    class ModelValidateRequest(BaseModel):
        model_name: str
        version: str
        context: dict[str, Any] | None = None

    class ModelActivateRequest(BaseModel):
        model_name: str
        version: str
        actor: str | None = "api-user"

    # --- Endpoints ---

    @_typed_get("/")
    def health_check() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "ea-kernel-governance",
            "data_dir": str(data_dir),
            "rule_count": system.rule_store.count(),
            "decision_count": system.decision_store.count()
        }

    # 0. Model Registration
    @_typed_post("/models/register")
    def register_model(req: ModelRegisterRequest) -> dict[str, Any]:
        from ea_kernel.profile_loader import ProfileLoadError, load_profile_from_content
        from ea_kernel.profile_types import KernelProfile

        if req.on_exists not in ("validate", "error"):
            raise HTTPException(status_code=400, detail="on_exists must be 'validate' or 'error'")

        try:
            profile = load_profile_from_content(req.profile_toml, kernel=schema)
        except ProfileLoadError as err:
            raise HTTPException(status_code=400, detail=f"Invalid profile TOML: {err}") from err

        if req.model_name and req.model_name != profile.name:
            profile = KernelProfile(
                name=req.model_name,
                version=profile.version,
                kernel_version=profile.kernel_version,
                elements=profile.elements,
                relations=profile.relations,
                validity_rules=profile.validity_rules,
                metadata=profile.metadata,
            )

        context = {
            "source": "api:models/register",
            **(req.context or {}),
        }

        try:
            result = registration.register(
                profile,
                owner=req.owner or "api-user",
                created_by=req.created_by or "api-user",
                context=context,
            )
            created = True
            run_id = result.validation_run_id
        except ModelRegistrationError as err:
            text = str(err)
            if req.on_exists == "validate" and "already exists" in text:
                rerun = registration.validate_registered(
                    profile.name,
                    profile.version,
                    context={**context, "mode": "reregister"},
                )
                created = False
                run_id = rerun.run_id
                if not rerun.passed:
                    raise HTTPException(
                        status_code=409,
                        detail="Existing model version revalidation failed",
                    ) from err
            elif "already exists" in text:
                raise HTTPException(status_code=409, detail=text) from err
            else:
                raise HTTPException(status_code=400, detail=text) from err

        activation = None
        if req.activate:
            try:
                activation = registration.activate(
                    profile.name,
                    profile.version,
                    actor=req.created_by or "api-user",
                )
            except ModelRegistrationError as err:
                raise HTTPException(status_code=409, detail=str(err)) from err

        return {
            "model_name": profile.name,
            "version": profile.version,
            "created": created,
            "validation_run_id": run_id,
            "activated": activation is not None,
            "status": activation.status if activation else "registered",
            "active_version_id": activation.active_version_id if activation else None,
        }

    @_typed_post("/models/validate")
    def validate_model(req: ModelValidateRequest) -> dict[str, Any]:
        try:
            run = registration.validate_registered(
                req.model_name,
                req.version,
                context={"source": "api:models/validate", **(req.context or {})},
            )
        except ModelRegistrationError as err:
            text = str(err)
            if "not found" in text:
                raise HTTPException(status_code=404, detail=text) from err
            raise HTTPException(status_code=400, detail=text) from err

        return {
            "model_name": req.model_name,
            "version": req.version,
            "passed": run.passed,
            "run_id": run.run_id,
            "errors": list(run.errors),
        }

    @_typed_post("/models/activate")
    def activate_model(req: ModelActivateRequest) -> dict[str, Any]:
        try:
            model = registration.activate(req.model_name, req.version, actor=req.actor or "api-user")
        except ModelRegistrationError as err:
            text = str(err)
            if "not found" in text:
                raise HTTPException(status_code=404, detail=text) from err
            raise HTTPException(status_code=409, detail=text) from err

        return {
            "model_name": model.model_name,
            "status": model.status,
            "active_version_id": model.active_version_id,
            "owner": model.owner,
        }

    @_typed_get("/models/{model_name}")
    def get_model(model_name: str, limit_runs: int = 5) -> dict[str, Any]:
        model = registration.get_model(model_name)
        if model is None:
            raise HTTPException(status_code=404, detail=f"Model not found: {model_name}")

        versions = registration.list_versions(model_name)
        runs = registration.list_validation_runs(model_name=model_name, limit=limit_runs)
        return {
            "model": {
                "model_id": model.model_id,
                "model_name": model.model_name,
                "owner": model.owner,
                "status": model.status,
                "active_version_id": model.active_version_id,
                "created_at": model.created_at,
                "updated_at": model.updated_at,
            },
            "versions": [
                {
                    "version_id": v.version_id,
                    "version": v.version,
                    "content_hash": v.content_hash,
                    "parent_version_id": v.parent_version_id,
                    "created_by": v.created_by,
                    "created_at": v.created_at,
                }
                for v in versions
            ],
            "validation_runs": [
                {
                    "run_id": run.run_id,
                    "version_id": run.version_id,
                    "passed": run.passed,
                    "errors": list(run.errors),
                    "context": run.context,
                    "created_at": run.created_at,
                }
                for run in runs
            ],
        }

    # 1. Judgment
    @_typed_post("/judgment/execute")
    def execute_judgment(req: ExecuteJudgmentRequest) -> dict[str, Any]:
        """Execute logic judgment for a triple."""
        result = system.evaluate(req.source, req.target, req.relation)
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
        if state:
            try:
                # Case-insensitive mapping
                state_upper = state.upper()
                try:
                    lifecycle_state = RuleLifecycleState(state_upper)
                except ValueError:
                    lifecycle_state = RuleLifecycleState(state) # try exact match

                rules = system.rule_store.list_by_state(lifecycle_state)
            except ValueError as err:
                raise HTTPException(status_code=400, detail=f"Invalid state: {state}") from err
        else:
            rules = system.rule_store.query() # All

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
            asset = system.approve_rule(rule_id, actor)
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

        # Build graph from current system state
        # profile maps to domain in TopologyGraph
        graph = TopologyGraph(target_schema, system.corpus, domain=profile)
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
        proposals = system.get_promotion_proposals()
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
        result = system.simulate_proposal(proposal)

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
