"""
Wizard Module - Interactive design and slicing review for novice users.

Provides guided workflows with checkpoints and suggestions to ensure
high-quality prints even for CAD beginners.
"""

from vibe_print.wizard.design_review import (
    DesignReviewer,
    DesignSuggestion,
    DesignCheckpoint,
    get_design_questions,
)
from vibe_print.wizard.slicing_review import (
    SlicingReviewer,
    SlicingSuggestion,
    QualityPreset,
    PrintUseCase,
    get_slicing_questions,
    get_recommended_settings,
)
from vibe_print.wizard.novice_parser import (
    NoviceTermParser,
    parse_novice_description,
    PHRASE_TRANSLATIONS,
)
from vibe_print.wizard.material_optimizer import (
    MaterialOptimizer,
    OptimizationResult,
    get_material_compatibility,
)
from vibe_print.wizard.guided_workflow import (
    GuidedWorkflow,
    WorkflowState,
    WorkflowStage,
    WorkflowCheckpoint,
    create_workflow,
)

__all__ = [
    # Design Review
    "DesignReviewer",
    "DesignSuggestion",
    "DesignCheckpoint",
    "get_design_questions",
    # Slicing Review
    "SlicingReviewer",
    "SlicingSuggestion",
    "QualityPreset",
    "PrintUseCase",
    "get_slicing_questions",
    "get_recommended_settings",
    # Novice Parser
    "NoviceTermParser",
    "parse_novice_description",
    "PHRASE_TRANSLATIONS",
    # Material Optimizer
    "MaterialOptimizer",
    "OptimizationResult",
    "get_material_compatibility",
    # Guided Workflow
    "GuidedWorkflow",
    "WorkflowState",
    "WorkflowStage",
    "WorkflowCheckpoint",
    "create_workflow",
]
