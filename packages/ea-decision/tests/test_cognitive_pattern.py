from ea_decision.pattern import DecisionComplexity, DecisionPattern
from ea_decision.registry import registry
from ea_decision.topic import Topic


def test_cognitive_pattern_application():
    # 1. Define a rich Cognitive Pattern
    pattern = DecisionPattern(
        name="RefinementSelection",
        description="Choose between multiple refinement paths for a kernel element",
        complexity=DecisionComplexity.STRUCTURAL,
        inquiry_template=(
            "What are the long-term maintenance costs of this refinement?",
            "Does this refinement introduce any circular dependencies in the Kernel?",
            "How does this impact the user experience of the final deployment?"
        ),
        verification_heuristics=(
            "Generate test cases for all boundary values defined in the schema.",
            "Verify that rollback successfully restores the previous kernel state."
        ),
        outcome_anchors={
            "success": "A clean, acyclic kernel structure with 100% schema compliance.",
            "failure": "Increased structural entropy and potential runtime schema errors."
        }
    )

    # 2. Register it
    registry.register(pattern)

    # 3. Create a topic and apply pattern
    topic = Topic(title="Kernel Refinement #42", description="Deciding on the storage strategy")
    topic.apply_pattern(pattern)

    # 4. Verify auto-populated questions
    assert topic.pattern_name == "RefinementSelection"
    assert len(topic.questions) == 3
    assert topic.questions[0].text == "What are the long-term maintenance costs of this refinement?"
    assert topic.questions[0].asked_by == "system:pattern"

    # 5. Verify verification heuristics in research notes
    assert len(topic.research_notes) == 1
    assert "### Verification Heuristics" in topic.research_notes[0].content
    assert "Generate test cases" in topic.research_notes[0].content
    assert topic.research_notes[0].author == "system:pattern"

def test_facade_integration(tmp_path):
    from ea_governance.facade import GovernanceContainer
    from ea_kernel.types import KernelSchema

    # Setup dummy schema
    schema = KernelSchema(attributes=(), entities=(), relations=(), validity_rules=())
    container = GovernanceContainer(tmp_path, schema)

    # Register pattern in registry (it's a singleton)
    pattern = DecisionPattern(
        name="StrategicPivot",
        description="A major architectural change",
        complexity=DecisionComplexity.STRATEGIC,
        inquiry_template=("Why are we doing this?",)
    )
    registry.register(pattern)

    # Propose initiative with pattern
    result = container.propose_initiative(
        title="Move to Event-Sourcing",
        description="Architectural pivot",
        pattern_name="StrategicPivot"
    )

    topic = result["topic"]
    assert topic.pattern_name == "StrategicPivot"
    assert len(topic.questions) == 1
    assert topic.questions[0].text == "Why are we doing this?"
