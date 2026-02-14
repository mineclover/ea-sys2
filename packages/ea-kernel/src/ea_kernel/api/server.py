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

import os
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import logging

from ea_kernel.governance import GovernanceSystem
from ea_kernel.governance_types import RuleLifecycleState
from ea_kernel.model_registration import (
    KernelModelRegistrationService,
    ModelRegistrationError,
)
from ea_kernel.model_io import ModelIOManager
from ea_kernel.multi_tenancy import MultiTenantManager
from ea_kernel.types import KernelSchema

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ea_kernel.server")

# --- Configuration ---
def get_data_dir() -> Path:
    env_path = os.getenv("EA_KERNEL_DATA_DIR", "./governance_data")
    path = Path(env_path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path

# --- Application Factory ---

def create_app(data_dir: Path, schema: KernelSchema) -> FastAPI:
    app = FastAPI(title="Governance Kernel API", version="1.0.0")
    
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
        actor: Optional[str] = "api-user"
        
    class RuleSubmission(BaseModel):
        # Simplified for demo
        rule_id: str
        source: str
        target: str
        relation: str
        valid: bool
        domain: str
        
    class ExportRequest(BaseModel):
        state: Optional[str] = None # "approved", "draft"...
        domain: Optional[str] = None

    class ModelRegisterRequest(BaseModel):
        profile_toml: str
        owner: Optional[str] = "api-user"
        created_by: Optional[str] = "api-user"
        model_name: Optional[str] = None
        activate: Optional[bool] = False
        context: Optional[Dict[str, Any]] = None
        on_exists: Optional[str] = "validate"  # validate | error

    class ModelValidateRequest(BaseModel):
        model_name: str
        version: str
        context: Optional[Dict[str, Any]] = None

    class ModelActivateRequest(BaseModel):
        model_name: str
        version: str
        actor: Optional[str] = "api-user"

    # --- Endpoints ---

    @app.get("/")
    def health_check():
        return {
            "status": "ok", 
            "service": "ea-kernel-governance",
            "data_dir": str(data_dir),
            "rule_count": system.rule_store.count(),
            "decision_count": system.decision_store.count()
        }

    # 0. Model Registration
    @app.post("/models/register")
    def register_model(req: ModelRegisterRequest):
        from ea_kernel.profile_loader import ProfileLoadError, load_profile_from_content
        from ea_kernel.profile_types import KernelProfile

        if req.on_exists not in ("validate", "error"):
            raise HTTPException(status_code=400, detail="on_exists must be 'validate' or 'error'")

        try:
            profile = load_profile_from_content(req.profile_toml, kernel=schema)
        except ProfileLoadError as e:
            raise HTTPException(status_code=400, detail=f"Invalid profile TOML: {e}")

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
        except ModelRegistrationError as e:
            text = str(e)
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
                    )
            elif "already exists" in text:
                raise HTTPException(status_code=409, detail=text)
            else:
                raise HTTPException(status_code=400, detail=text)

        activation = None
        if req.activate:
            try:
                activation = registration.activate(
                    profile.name,
                    profile.version,
                    actor=req.created_by or "api-user",
                )
            except ModelRegistrationError as e:
                raise HTTPException(status_code=409, detail=str(e))

        return {
            "model_name": profile.name,
            "version": profile.version,
            "created": created,
            "validation_run_id": run_id,
            "activated": activation is not None,
            "status": activation.status if activation else "registered",
            "active_version_id": activation.active_version_id if activation else None,
        }

    @app.post("/models/validate")
    def validate_model(req: ModelValidateRequest):
        try:
            run = registration.validate_registered(
                req.model_name,
                req.version,
                context={"source": "api:models/validate", **(req.context or {})},
            )
        except ModelRegistrationError as e:
            text = str(e)
            if "not found" in text:
                raise HTTPException(status_code=404, detail=text)
            raise HTTPException(status_code=400, detail=text)

        return {
            "model_name": req.model_name,
            "version": req.version,
            "passed": run.passed,
            "run_id": run.run_id,
            "errors": list(run.errors),
        }

    @app.post("/models/activate")
    def activate_model(req: ModelActivateRequest):
        try:
            model = registration.activate(req.model_name, req.version, actor=req.actor or "api-user")
        except ModelRegistrationError as e:
            text = str(e)
            if "not found" in text:
                raise HTTPException(status_code=404, detail=text)
            raise HTTPException(status_code=409, detail=text)

        return {
            "model_name": model.model_name,
            "status": model.status,
            "active_version_id": model.active_version_id,
            "owner": model.owner,
        }

    @app.get("/models/{model_name}")
    def get_model(model_name: str, limit_runs: int = 5):
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
    @app.post("/judgment/execute")
    def execute_judgment(req: ExecuteJudgmentRequest):
        """Execute logic judgment for a triple."""
        result = system.evaluate(req.source, req.target, req.relation)
        return {
            "verdict": result.judgment.verdict,
            "confidence": result.judgment.confidence.value,
            "evidence": [e.entry.rule.id for e in result.judgment.evidence],
            "messages": result.judgment.messages
        }

    # 2. Rule Lifecycle
    @app.get("/rules")
    def list_rules(state: Optional[str] = None):
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
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid state: {state}")
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
        
    @app.post("/rules/{rule_id}/approve")
    def approve_rule(rule_id: str, actor: str = "api-user"):
        """Approve a rule."""
        try:
            asset = system.approve_rule(rule_id, actor)
            return {"status": "approved", "rule_id": asset.id}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # 3. Model I/O (Export/Import)
    @app.post("/model/export")
    def export_model(req: ExportRequest):
        """Export model as JSON."""
        target_state = None
        if req.state:
            try:
                target_state = RuleLifecycleState(req.state.upper())
            except ValueError:
                pass
        
        data = io_manager.export_model(target_state=target_state, domain=req.domain)
        
        # Return as file download
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=governance_export.json"}
        )

    # 4. Diagram
    @app.get("/diagram")
    def get_diagram(show_judgment: bool = True, profile: Optional[str] = None):
        """Get system topology diagram (Mermaid source).
        
        Args:
            show_judgment: Whether to visualize validity/confidence.
            profile: Optional domain/profile name to filter edges.
                     If specified, only edges defined by this profile are shown.
        """
        from ea_kernel.graph_view import TopologyGraph
        from ea_kernel.diagram_exporter import DiagramExporter
        from ea_kernel.profile_loader import load_profile
        from pathlib import Path
        
        # Determine schema to use: Base Kernel + Governance Profile (if requested)
        # By default (or if profile="GovernanceLifecycle"), we show the self-model
        target_schema = schema
        
        # Load Governance Lifecycle profile 
        # (This path could be adjusted or loaded from package resource)
        # Try to find it relative to current file or package
        try:
             # Assuming running as module
            import importlib.resources
            # Python 3.9+ resource access
            try:
                # 3.9+ behavior but might vary by version
                with importlib.resources.path("ea_kernel.profiles", "governance_lifecycle.toml") as p:
                    profile_path = p
            except (ImportError, AttributeError):
                # Fallback for older python or if resource api not available/different
                # Try relative path from source
                profile_path = Path(__file__).parent.parent / "profiles" / "governance_lifecycle.toml"
            
            if profile_path.exists():
                gov_profile = load_profile(profile_path, kernel=schema)
                
                # Merge profile elements into a new schema for visualization
                # We need to extend base schema with profile elements
                # Note: This is a visualization-specific schema view
                from ea_kernel.types import KernelSchema
                
                # Convert profile elements to KernelEntity (if they aren't already compatible)
                # ProfileElement has name, layer, category -> KernelEntity needs mapping
                # But TopologyGraph just needs .entities with .name and .layer
                # Let's trust they are compatible or adaptable
                
                # Create extended schema
                extended_entities = list(schema.entities)
                extended_relations = list(schema.relations)
                
                # Add profile elements
                for elem in gov_profile.elements:
                    # Check for duplicates? for now just append
                    # We need to convert ProfileElement to KernelEntity-like
                    # ProfileElement: name, layer, category, ...
                    # KernelEntity: name, layer, ...
                    from ea_kernel.types import KernelEntity, Layer
                    
                    # Map string layer to Enum
                    try:
                        layer_enum = Layer(elem.layer)
                    except ValueError:
                         # Fallback/Map if profile uses different names?
                         # Profile uses "Authoring", "Judgment" etc -> Map to Kernel Layers?
                         # The TOML uses domain layers. We need to map them to Kernel Layers
                         # governance_lifecycle.toml maps categories to kernel layers implicitly via category definition?
                         # Actually profile.element.layer is a string (Domain Layer).
                         # KernelEntity.layer is generic L1-L4.
                         # Visualization might trip if layer is not L1-L4 enum?
                         # TopologyGraph uses schema.entities...
                         # If we want to visualize domain layers, we might need DiagramExporter to handle strings.
                         # But let's map to L4 (Concrete) for now for all governance elements?
                         # Or L3?
                         layer_enum = Layer.L4 
                    
                    ent = KernelEntity(
                        name=elem.name,
                        layer=layer_enum,
                        is_abstract=False,
                        description=elem.description
                    )
                    extended_entities.append(ent)
                
                # Add profile relations?
                # Profile defines relations mapping to kernel relations.
                # TopologyGraph expects schema.relations to be KernelRelation.
                # Profile relations use kernel_relation.
                # We can add them as specific named relations.
                for rel in gov_profile.relations:
                     # Add as new relation type?
                     from ea_kernel.types import KernelRelation
                     rel_ent = KernelRelation(
                         name=rel.name,
                         layer=Layer.L2, # Default
                         description=rel.description
                     )
                     extended_relations.append(rel_ent)
                
                target_schema = KernelSchema(
                    attributes=schema.attributes,
                    entities=tuple(extended_entities), 
                    relations=tuple(extended_relations),
                    validity_rules=schema.validity_rules + gov_profile.validity_rules
                )
                
        except Exception as e:
            logger.warning(f"Failed to load governance profile for diagram: {e}")
            target_schema = schema

        # Build graph from current system state
        # profile maps to domain in TopologyGraph
        graph = TopologyGraph(target_schema, system.corpus, domain=profile)
        exporter = DiagramExporter(graph)
        
        return Response(
            content=exporter.generate_mermaid(show_judgment), 
            media_type="text/plain"
        )
        
    @app.post("/model/import")
    async def import_model(file: UploadFile = File(...)):
        """Import model from JSON file."""
        try:
            content = await file.read()
            data = json.loads(content)
            
            report = io_manager.import_model(data)
            return report
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON file")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 6. Automation & Evolution
    @app.get("/automation/promotions")
    def get_promotion_proposals():
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

    @app.post("/simulation/what-if")
    def simulate_promotion(req: SimulatePromotionRequest):
        """Simulate a rule promotion."""
        from ea_kernel.promotion_engine import RuleChangeProposal, ProposalType, ProposalStatus
        from ea_kernel.types import RuleConfidence
        import uuid
        from datetime import datetime, UTC
        
        try:
            confidence = RuleConfidence(req.new_confidence.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid confidence level")
            
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
    @app.get("/governance/flow/{anchor_id}")
    def get_flow_logic(anchor_id: str):
        """
        Retrieves the logic specification (Flow/Schemas) anchored to a kernel element.
        Demonstrates how Flow refines Kernel.
        """
        # In a real environment, we'd have a global Container or Session
        # For demo, we instantiate a lightweight container pointing to the same data
        from ea_governance.facade import GovernanceContainer, KernelSchema
        container = GovernanceContainer(data_dir, schema)
        
        spec = container.get_flow_spec(anchor_id)
        if not spec:
            raise HTTPException(status_code=404, detail=f"No flow logic found for anchor: {anchor_id}")
            
        return spec

    # --- System Self-Exploration (Phase 9 Extension) ---
    @app.get("/system/self-model")
    def get_system_self_model():
        """
        Returns a Mermaid diagram of the EA System's own internal architecture.
        Enables autonomic exploration of the Brain/Body/Physics layers.
        """
        from ea_governance.facade import GovernanceContainer
        container = GovernanceContainer(data_dir, schema)
        
        try:
            mermaid_src = container.get_self_model_diagram()
            return Response(content=mermaid_src, media_type="text/plain")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to project self-model: {str(e)}")

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
