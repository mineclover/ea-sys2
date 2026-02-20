from datetime import UTC, datetime
from pathlib import Path

from ea_decision.topic import DesignReport, ModelingAction, Topic
from ea_flow.kernel_actions import AddRuleStepSpec, DeprecateRuleStepSpec
from ea_flow.kernel_implementers import AddRuleImplementer, DeprecateRuleImplementer
from ea_flow.runtime import FlowRuntime
from ea_flow.schema import SchemaSpec
from ea_flow.spec import StepSpec, WorkflowSpec
from ea_kernel.governance import GovernanceSystem

from ea_governance.transaction import TransactionManager


class DesignWorkflowSpec(WorkflowSpec):
    def __init__(self, name: str, steps: list[StepSpec], anchor: str | None = None):
        self._name = name
        self._steps = steps
        self._anchor = anchor

    @property
    def name(self) -> str:
        return self._name

    @property
    def kernel_anchor(self) -> str:
        return self._anchor or "ea:governance:report_execution"

    @property
    def input_schema(self) -> SchemaSpec | None:
        return None

    @property
    def output_schema(self) -> SchemaSpec | None:
        return None

    def get_steps(self) -> list[StepSpec]:
        return self._steps

class ExecutionService:
    """Bridges DesignReport with flow interpretation/planning."""

    def __init__(
        self,
        kernel: GovernanceSystem,
        runtime: FlowRuntime | None = None,
        tx_db_path: str | Path | None = None,
    ) -> None:
        self.kernel = kernel

        # Default kernel implementers
        default_implementers = {
            "add_rule": AddRuleImplementer(),
            "deprecate_rule": DeprecateRuleImplementer(),
        }

        self.runtime = runtime or FlowRuntime(implementers=default_implementers)
        resolved_tx_db_path = self._resolve_tx_db_path(tx_db_path)
        self.tx_manager = TransactionManager(resolved_tx_db_path)

    def _resolve_tx_db_path(self, tx_db_path: str | Path | None) -> Path:
        if tx_db_path is not None:
            return Path(tx_db_path)

        kernel_data_dir = getattr(self.kernel, "data_dir", None)
        if isinstance(kernel_data_dir, Path):
            return kernel_data_dir.parent / "transactions.db"
        return Path("transactions.db")

    def interpret_report(
        self,
        report: DesignReport,
        topic: Topic | None = None,
    ) -> bool:
        """Translates report actions into a workflow and interprets intent outputs.

        When *topic* is provided, the decision status is updated on completion:
        success → ACCEPTED, failure → REJECTED (topic re-opened for revision).
        """
        steps = []
        for i, action in enumerate(report.modeling_actions):
            step = self._map_action_to_step(action, f"idx_{i}")
            if step:
                steps.append(step)

        if not steps:
            report.execution_log.append("No interpretable actions found in report.")
            return False

        workflow = DesignWorkflowSpec(f"report_{report.id}", steps, anchor=f"ea:governance:report:{report.id}")
        variables = {"governance_system": self.kernel}

        # Begin Transaction (propagate trace_id from topic if available)
        trace_id = getattr(topic, "trace_id", "") if topic is not None else ""
        tx = self.tx_manager.begin_transaction(
            f"exec_{report.id}", tx_type="design_realization", trace_id=trace_id,
        )
        report.transaction_id = tx.id

        # Interpret using runtime (side-effect free)
        result = self.runtime.interpret(workflow, variables)

        # Update Report & Transaction
        report.executed_at = datetime.now(UTC).isoformat() + "Z"
        report.execution_log.extend(result.logs)
        for intent in result.interpreted_intents:
            report.execution_log.append(f"intent: {intent}")
        tx.logs.extend(result.logs)

        if result.success:
            self.tx_manager.commit(tx.id)
            for action in report.modeling_actions:
                action.status = "interpreted"

            # Back-reference: update decision status via Topic
            if topic is not None:
                topic.execution_completed(
                    success=True,
                    execution_log=result.logs,
                    transaction_id=tx.id,
                )

            return True
        else:
            report.execution_log.append("Interpretation failed.")
            if getattr(result, "rollback_occurred", False):
                self.tx_manager.rollback(tx.id, reason="Workflow Interpretation Failed")
                report.execution_log.append("Compensation planning completed.")
                for action in report.modeling_actions:
                    action.status = "rolled_back"
            else:
                self.tx_manager.fail(tx.id, error_msg="Unknown Failure")

            # Back-reference: mark decision as rejected, re-open topic
            if topic is not None:
                topic.execution_completed(
                    success=False,
                    execution_log=result.logs,
                    transaction_id=tx.id,
                )

            return False

    def execute_report(self, report: DesignReport, topic: Topic | None = None) -> bool:
        """Backward-compatible alias for `interpret_report`."""
        return self.interpret_report(report, topic=topic)

    def _map_action_to_step(self, action: ModelingAction, index_key: str) -> StepSpec | None:
        """Mapping logic between business actions and declarative specs."""
        anchor = action.target
        if action.action_type == "create_rule":
            spec = AddRuleStepSpec(f"{action.target}_{index_key}", action.payload, anchor=anchor)
            # Ensure runtime can resolve it (we use the generic name in runtime mapping)
            # In a more advanced system, we'd have a more robust resolution strategy
            return spec
        elif action.action_type == "deprecate_rule":
            return DeprecateRuleStepSpec(action.target, anchor=anchor)
        return None
