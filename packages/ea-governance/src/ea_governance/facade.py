from pathlib import Path
from typing import Any

from ea_decision.topic import Topic
from ea_flow.runtime import FlowRuntime
from ea_flow.spec import UseCaseSpec
from ea_kernel.governance import GovernanceSystem as KernelSystem
from ea_kernel.types import KernelSchema

from ea_governance.execution_service import ExecutionService


class GovernanceContainer:
    """
    The Main Entry Point for the Horizontal Governance System.

    Integrates:
    - Kernel (Physics/Structure)
    - Decision (Brain/Intent)
    - Flow (Body/Action)
    """

    def __init__(
        self,
        data_dir: Path,
        schema: KernelSchema,
        flow_runtime: FlowRuntime | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 1. Initialize Core Layer (Kernel)
        self.kernel = KernelSystem(data_dir / "kernel", schema)

        # 2. Initialize Execution Bridge (Coordination)
        self.execution_service = ExecutionService(
            self.kernel,
            runtime=flow_runtime,
            tx_db_path=data_dir / "transactions.db",
        )

        # 3. Reference for direct access if needed
        self.runtime = self.execution_service.runtime

    def create_topic(self, title: str, description: str) -> Topic:
        """Starts a new Design Thinking topic."""
        # This is a lightweight action, maybe no transaction needed yet?
        # Or we can wrap it:
        return Topic(title=title, description=description)

    def propose_initiative(self, title: str, description: str, pattern_name: str | None = None) -> dict[str, Any]:
        """
        Starts a high-level initiative (Method 1: Transactional).
        Returns {Intent/Topic, TransactionID}
        """
        # Start Transaction
        tx = self.execution_service.tx_manager.begin_transaction(f"init_{title}", tx_type="initiative_proposal")

        try:
            topic = Topic(title=title, description=description)

            # Apply Decision Pattern if provided
            if pattern_name:
                from ea_decision.registry import registry
                pattern = registry.get_pattern(pattern_name)
                if pattern:
                    topic.apply_pattern(pattern)

            # Simulate persistence or other logic here

            self.execution_service.tx_manager.commit(tx.id)
            return {"topic": topic, "transaction_id": tx.id}
        except Exception as e:
            self.execution_service.tx_manager.fail(tx.id, str(e))
            raise e

    def execute_decision(self, report_id: str, topic: Topic) -> dict[str, Any]:
        """
        Executes the modeling actions of a finalized report.
        Returns {"success": bool, "transaction_id": str}
        """
        if not topic.report or topic.report.id != report_id:
            return {"success": False, "error": "Invalid Report ID"}

        success = self.execution_service.execute_report(topic.report)
        return {
            "success": success,
            "transaction_id": topic.report.transaction_id,
        }

    def execute_use_case(self, use_case: UseCaseSpec, variables: dict[str, Any]) -> dict[str, Any]:
        """
        Executes a Use Case Specification using the system runtime.
        """
        tx_name = f"use_case_{use_case.name}"
        tx = self.execution_service.tx_manager.begin_transaction(tx_name, tx_type="use_case_execution")

        try:
            # COORDINATION: Prepare context and resolve execution
            context_vars = {**variables, "governance_system": self.kernel}

            # Execute process (Procedural Truth)
            result = self.runtime.execute(use_case, context_vars)

            # Update Transaction with logs
            tx.logs.extend(result.logs)
            if result.success:
                self.execution_service.tx_manager.commit(tx.id)
                return {
                    "success": True,
                    "transaction_id": tx.id,
                    "logs": result.logs,
                    "metrics": {"specs_processed": len(result.step_results)},
                }
            else:
                self.execution_service.tx_manager.fail(tx.id, "Use Case execution failed")
                return {"success": False, "transaction_id": tx.id, "logs": result.logs}

        except Exception as e:
            self.execution_service.tx_manager.fail(tx.id, str(e))
            raise e

    def get_transaction_status(self, tx_id: str) -> dict[str, Any] | None:
        """Retrieves the status of a governance transaction."""
        tx = self.execution_service.tx_manager.get_transaction(tx_id)
        if tx:
            return {"id": tx.id, "status": tx.status, "updated_at": tx.updated_at}
        return None

    def get_transaction_logs(self, tx_id: str) -> list[str]:
        """Retrieves execution logs for a specific transaction."""
        tx = self.execution_service.tx_manager.get_transaction(tx_id)
        return tx.logs if tx else []

    def get_transaction_events(self, tx_id: str) -> list[dict[str, Any]]:
        """Retrieves transaction events from persistent store."""
        events = self.execution_service.tx_manager.get_events(tx_id)
        return [
            {
                "id": event.id,
                "tx_id": event.tx_id,
                "event_type": event.event_type,
                "message": event.message,
                "payload": event.payload,
                "created_at": event.created_at,
            }
            for event in events
        ]

    def get_flow_spec(self, anchor_id: str) -> dict[str, Any] | None:
        """
        Retrieves the logic specification (Flow) anchored to a kernel element.
        This is a draft implementation showing how Flow refines Kernel.
        """
        # In a full project, this would query a registry or database.
        # For Phase 8 Demo, we provide a hardcoded example if the anchor matches.
        if anchor_id == "ea:kernel:rule_creation":

            # Example JSON Schema 2020-12
            input_schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["id"],
            }

            return {
                "anchor": anchor_id,
                "type": "Step",
                "name": "AddRuleStep",
                "input_schema": input_schema,
                "format": "jsonschema-2020-12",
            }
        return None

    def get_self_model_diagram(self, lang: str = "en") -> str:
        """
        Generates a Mermaid diagram of the EA System's own architecture
        by projecting it onto a Kernel schema using the SystemSelfModel profile.
        Supports localized descriptions via lang parameter.
        """
        from importlib.resources import files

        from ea_kernel.diagram_exporter import DiagramExporter
        from ea_kernel.graph_view import TopologyGraph
        from ea_kernel.localizer import ProfileLocalizer
        from ea_kernel.profile_loader import load_profile
        from ea_kernel.profile_rule_compiler import build_profile_runtime_schema
        from ea_kernel.rule_corpus import RuleCorpus

        # 1. Load the Self-Model Profile
        # Try relative path from governance package to sibling ea-kernel package
        profile_path = (
            Path(__file__).parent.parent.parent.parent
            / "ea-kernel"
            / "src"
            / "ea_kernel"
            / "profiles"
            / "system_self_model.toml"
        )
        if not profile_path.exists():
            try:
                resource = files("ea_kernel.profiles").joinpath("system_self_model.toml")
                profile_path = Path(str(resource))
            except Exception as exc:
                raise FileNotFoundError("Cannot locate system_self_model.toml profile") from exc

        base_profile = load_profile(profile_path, kernel=self.kernel._base_schema)

        # 2. Apply Localizer
        localizer = ProfileLocalizer()
        self_profile = localizer.localize(base_profile, lang=lang, search_path=profile_path.parent)

        runtime = build_profile_runtime_schema(
            self.kernel._base_schema,
            self_profile,
            include_base_schema=False,
            include_base_rules=False,
        )
        corpus = RuleCorpus.from_kernel_spec(runtime.schema)

        graph = TopologyGraph(runtime.schema, corpus)
        exporter = DiagramExporter(graph)
        return str(exporter.generate_mermaid(show_judgment=False))
