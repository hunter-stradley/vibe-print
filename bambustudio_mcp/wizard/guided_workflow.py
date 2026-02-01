"""
Guided Workflow - End-to-end printing workflow with checkpoints.

Orchestrates the entire process from requirements to print,
with interactive checkpoints for novice users.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
import uuid

from bambustudio_mcp.wizard.novice_parser import NoviceTermParser, ParsedIntent
from bambustudio_mcp.wizard.design_review import DesignReviewer, get_design_questions
from bambustudio_mcp.wizard.slicing_review import (
    SlicingReviewer,
    QualityPreset,
    PrintUseCase,
    get_slicing_questions,
    get_recommended_settings,
)
from bambustudio_mcp.wizard.material_optimizer import MaterialOptimizer
from bambustudio_mcp.materials.filaments import get_filament_profile, list_filament_profiles
from bambustudio_mcp.materials.nozzles import get_recommended_nozzle, A1_NOZZLES


class WorkflowStage(str, Enum):
    """Stages of the guided workflow."""
    REQUIREMENTS = "requirements"      # Gathering user requirements
    DESIGN_REVIEW = "design_review"    # Review design parameters
    MATERIAL_SELECT = "material"       # Choose material
    NOZZLE_SELECT = "nozzle"          # Choose nozzle
    SLICING_REVIEW = "slicing"         # Review slicing parameters
    FINAL_REVIEW = "final"             # Final confirmation
    GENERATION = "generation"          # Generating model
    SLICING = "slicing_exec"           # Executing slice
    READY = "ready"                    # Ready to print
    PRINTING = "printing"              # Currently printing
    COMPLETE = "complete"              # Finished


class CheckpointStatus(str, Enum):
    """Status of a workflow checkpoint."""
    PENDING = "pending"
    WAITING_INPUT = "waiting_input"
    APPROVED = "approved"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class WorkflowCheckpoint:
    """A checkpoint in the workflow requiring user input or confirmation."""
    stage: WorkflowStage
    title: str
    description: str
    status: CheckpointStatus = CheckpointStatus.PENDING

    # Questions to ask user
    questions: List[Dict[str, Any]] = field(default_factory=list)

    # User's answers
    answers: Dict[str, Any] = field(default_factory=dict)

    # Suggestions/warnings to show
    suggestions: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Can this checkpoint be auto-approved?
    auto_approvable: bool = False

    # Timestamp
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "questions": self.questions,
            "answers": self.answers,
            "suggestions": self.suggestions,
            "warnings": self.warnings,
            "auto_approvable": self.auto_approvable,
            "timestamp": self.timestamp,
        }


@dataclass
class WorkflowState:
    """Current state of the guided workflow."""
    workflow_id: str
    created_at: str
    current_stage: WorkflowStage
    checkpoints: List[WorkflowCheckpoint] = field(default_factory=list)

    # Accumulated parameters
    user_description: str = ""
    parsed_requirements: Optional[Dict[str, Any]] = None
    design_params: Dict[str, Any] = field(default_factory=dict)
    material: str = "Bambu Basic PLA"
    nozzle_diameter: float = 0.4
    slicing_params: Dict[str, Any] = field(default_factory=dict)

    # Generated artifacts
    model_path: Optional[str] = None
    gcode_path: Optional[str] = None

    # Status
    is_complete: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "created_at": self.created_at,
            "current_stage": self.current_stage.value,
            "checkpoints": [cp.to_dict() for cp in self.checkpoints],
            "user_description": self.user_description,
            "parsed_requirements": self.parsed_requirements,
            "design_params": self.design_params,
            "material": self.material,
            "nozzle_diameter": self.nozzle_diameter,
            "slicing_params": self.slicing_params,
            "model_path": self.model_path,
            "gcode_path": self.gcode_path,
            "is_complete": self.is_complete,
            "error": self.error,
        }


class GuidedWorkflow:
    """
    Orchestrates the complete print workflow with interactive checkpoints.

    Guides novice users through:
    1. Requirements gathering
    2. Design parameter review
    3. Material selection
    4. Nozzle selection
    5. Slicing parameter review
    6. Final confirmation
    7. Model generation
    8. Slicing execution
    """

    def __init__(self):
        self.state: Optional[WorkflowState] = None
        self.novice_parser = NoviceTermParser()
        self.design_reviewer = DesignReviewer()
        self.slicing_reviewer = SlicingReviewer()
        self.material_optimizer = MaterialOptimizer()

    def start_workflow(self, description: str = "") -> WorkflowState:
        """
        Start a new guided workflow.

        Args:
            description: Initial user description (optional)

        Returns:
            Initial workflow state
        """
        self.state = WorkflowState(
            workflow_id=str(uuid.uuid4())[:8],
            created_at=datetime.now().isoformat(),
            current_stage=WorkflowStage.REQUIREMENTS,
            user_description=description,
        )

        # If description provided, parse it
        if description:
            self._process_requirements(description)

        return self.state

    def _process_requirements(self, description: str) -> None:
        """Parse user description into requirements."""
        parsed = self.novice_parser.parse(description)
        self.state.parsed_requirements = parsed.to_dict()
        self.state.user_description = description

        # Create requirements checkpoint
        checkpoint = WorkflowCheckpoint(
            stage=WorkflowStage.REQUIREMENTS,
            title="Understanding Your Requirements",
            description="I've analyzed your description. Please confirm or adjust:",
            status=CheckpointStatus.WAITING_INPUT,
            timestamp=datetime.now().isoformat(),
        )

        # Add clarifying questions
        questions = []

        # Always confirm key parameters
        questions.append({
            "id": "confirm_dimensions",
            "question": "Are these dimensions correct?",
            "type": "confirm",
            "current_value": self.state.parsed_requirements.get("dimensions", {}),
            "editable": True,
        })

        questions.append({
            "id": "strength_level",
            "question": "How strong does it need to be?",
            "type": "select",
            "options": [
                {"value": "light", "label": "Light duty (decorative)"},
                {"value": "medium", "label": "Normal use (Recommended)"},
                {"value": "heavy", "label": "Heavy duty (lots of force)"},
            ],
            "current_value": parsed.strength.value,
        })

        questions.append({
            "id": "fit_type",
            "question": "How should parts fit together?",
            "type": "select",
            "options": [
                {"value": "tight", "label": "Tight (stays put firmly)"},
                {"value": "snug", "label": "Snug (Recommended - adjustable)"},
                {"value": "loose", "label": "Loose (easy to move)"},
            ],
            "current_value": parsed.fit_type.value,
        })

        # Add any clarifying questions from parser
        for q in parsed.clarifying_questions:
            questions.append({
                "id": f"clarify_{len(questions)}",
                "question": q,
                "type": "text",
            })

        checkpoint.questions = questions
        self.state.checkpoints.append(checkpoint)

    def advance_to_design_review(self, answers: Dict[str, Any] = None) -> WorkflowCheckpoint:
        """
        Move to design review stage.

        Args:
            answers: Answers from previous checkpoint

        Returns:
            Design review checkpoint
        """
        # Apply answers to state
        if answers:
            self._apply_answers(answers)

        self.state.current_stage = WorkflowStage.DESIGN_REVIEW

        # Build design params from parsed requirements
        req = self.state.parsed_requirements or {}
        self.state.design_params = {
            "wall_thickness_mm": req.get("wall_thickness_mm", 2.0),
            "clearance_mm": req.get("clearance_mm", 0.3),
            "dimensions": req.get("dimensions", {}),
            "needs_grip": req.get("needs_grip", False),
        }

        # If we have a primary dimension, add it
        dims = req.get("dimensions", {})
        if "primary" in dims:
            self.state.design_params["tube_diameter"] = dims["primary"]

        # Review design
        review = self.design_reviewer.review_design(
            design_params=self.state.design_params,
            intended_use=self.state.user_description,
            material=self.state.material,
            nozzle_diameter=self.state.nozzle_diameter,
        )

        # Create design review checkpoint
        checkpoint = WorkflowCheckpoint(
            stage=WorkflowStage.DESIGN_REVIEW,
            title="Design Review",
            description="Let's review your design parameters:",
            status=CheckpointStatus.WAITING_INPUT,
            suggestions=review.get("suggestions", []),
            warnings=[s["title"] for s in review.get("suggestions", [])
                     if s.get("priority") == "critical"],
            auto_approvable=review.get("critical_issues", 0) == 0,
            timestamp=datetime.now().isoformat(),
        )

        # Add design questions based on category (if detected)
        if self.state.parsed_requirements:
            category = self.state.parsed_requirements.get("category", "general")
            checkpoint.questions = get_design_questions(
                category, self.state.design_params
            )

        self.state.checkpoints.append(checkpoint)
        return checkpoint

    def advance_to_material_select(self, answers: Dict[str, Any] = None) -> WorkflowCheckpoint:
        """Move to material selection stage."""
        if answers:
            self._apply_answers(answers)

        self.state.current_stage = WorkflowStage.MATERIAL_SELECT

        # Get available materials
        materials = list_filament_profiles()

        # Build material options
        material_options = []
        for name in materials:
            profile = get_filament_profile(name)
            if profile:
                material_options.append({
                    "value": name,
                    "label": profile.name,
                    "description": f"{profile.filament_type.value.upper()} - "
                                 f"Nozzle: {profile.nozzle_temp.optimal}°C, "
                                 f"Bed: {profile.bed_temp.optimal}°C",
                    "ams_compatible": profile.ams_compatible,
                    "special_notes": profile.special_notes[:100] if profile.special_notes else "",
                })

        checkpoint = WorkflowCheckpoint(
            stage=WorkflowStage.MATERIAL_SELECT,
            title="Material Selection",
            description="Choose your filament material:",
            status=CheckpointStatus.WAITING_INPUT,
            questions=[{
                "id": "material",
                "question": "Which filament will you use?",
                "type": "select",
                "options": material_options,
                "current_value": self.state.material,
            }],
            timestamp=datetime.now().isoformat(),
        )

        # Add material-specific warnings from requirements
        req = self.state.parsed_requirements or {}
        if req.get("needs_flex"):
            checkpoint.warnings.append(
                "Your design needs flexibility - TPU is recommended"
            )
        if req.get("waterproof"):
            checkpoint.warnings.append(
                "For waterproof parts, PETG works better than PLA"
            )
        if req.get("heat_resistant"):
            checkpoint.warnings.append(
                "For heat resistance, use PC or PETG (not PLA)"
            )

        self.state.checkpoints.append(checkpoint)
        return checkpoint

    def advance_to_nozzle_select(self, answers: Dict[str, Any] = None) -> WorkflowCheckpoint:
        """Move to nozzle selection stage."""
        if answers:
            if "material" in answers:
                self.state.material = answers["material"]
            self._apply_answers(answers)

        self.state.current_stage = WorkflowStage.NOZZLE_SELECT

        # Get recommended nozzle based on requirements
        req = self.state.parsed_requirements or {}
        material_profile = get_filament_profile(self.state.material)

        recommended, reason = get_recommended_nozzle(
            part_size=req.get("size_category", "medium"),
            detail_needed="standard",
            material_abrasive=material_profile.is_abrasive if material_profile else False,
            speed_priority=False,
        )

        # Build nozzle options
        nozzle_options = []
        for key, profile in A1_NOZZLES.items():
            if "_" in key:  # Skip duplicates like "0.4_ss"
                continue
            is_recommended = abs(profile.diameter - recommended.diameter) < 0.01
            nozzle_options.append({
                "value": profile.diameter,
                "label": f"{profile.diameter}mm - {profile.nozzle_type.value.replace('_', ' ').title()}"
                        + (" (Recommended)" if is_recommended else ""),
                "description": ", ".join(profile.best_for[:2]),
                "layer_heights": profile.get_layer_heights(),
            })

        checkpoint = WorkflowCheckpoint(
            stage=WorkflowStage.NOZZLE_SELECT,
            title="Nozzle Selection",
            description=f"Recommendation: {reason}",
            status=CheckpointStatus.WAITING_INPUT,
            questions=[{
                "id": "nozzle",
                "question": "Which nozzle size will you use?",
                "type": "select",
                "options": nozzle_options,
                "current_value": recommended.diameter,
            }],
            auto_approvable=True,  # Can use recommended
            timestamp=datetime.now().isoformat(),
        )

        self.state.checkpoints.append(checkpoint)
        return checkpoint

    def advance_to_slicing_review(self, answers: Dict[str, Any] = None) -> WorkflowCheckpoint:
        """Move to slicing parameter review."""
        if answers:
            if "nozzle" in answers:
                self.state.nozzle_diameter = float(answers["nozzle"])
            self._apply_answers(answers)

        self.state.current_stage = WorkflowStage.SLICING_REVIEW

        # Get slicing questions
        questions = get_slicing_questions(
            self.state.material,
            {"dimensions": self.state.design_params.get("dimensions", {})}
        )

        checkpoint = WorkflowCheckpoint(
            stage=WorkflowStage.SLICING_REVIEW,
            title="Print Quality Settings",
            description="How should we slice your model?",
            status=CheckpointStatus.WAITING_INPUT,
            questions=questions,
            timestamp=datetime.now().isoformat(),
        )

        # Get material notes
        material_profile = get_filament_profile(self.state.material)
        if material_profile:
            notes = []
            if not material_profile.ams_compatible:
                notes.append(f"{material_profile.name} must be fed directly (not via AMS)")
            if material_profile.special_notes:
                notes.append(material_profile.special_notes)
            checkpoint.warnings = notes

        self.state.checkpoints.append(checkpoint)
        return checkpoint

    def advance_to_final_review(self, answers: Dict[str, Any] = None) -> WorkflowCheckpoint:
        """Move to final review before generation."""
        if answers:
            self._apply_answers(answers)

        self.state.current_stage = WorkflowStage.FINAL_REVIEW

        # Calculate recommended slicing settings
        quality = QualityPreset(answers.get("quality", "standard")) if answers else QualityPreset.STANDARD
        use_case = PrintUseCase(answers.get("use_case", "functional")) if answers else PrintUseCase.FUNCTIONAL

        self.state.slicing_params = get_recommended_settings(
            self.state.material,
            self.state.nozzle_diameter,
            quality,
            use_case,
        )

        # Optimize for material
        optimization = self.material_optimizer.optimize_for_material(
            self.state.slicing_params,
            self.state.material,
            self.state.nozzle_diameter,
        )

        self.state.slicing_params = optimization.optimized_params

        # Create final summary
        checkpoint = WorkflowCheckpoint(
            stage=WorkflowStage.FINAL_REVIEW,
            title="Ready to Generate",
            description="Review your settings before we create the model:",
            status=CheckpointStatus.WAITING_INPUT,
            suggestions=[{
                "type": "summary",
                "design": self.state.design_params,
                "material": self.state.material,
                "nozzle": f"{self.state.nozzle_diameter}mm",
                "quality": quality.value,
                "slicing": {
                    "layer_height": f"{self.state.slicing_params.get('layer_height', 0.2)}mm",
                    "infill": f"{self.state.slicing_params.get('sparse_infill_density', 20)}%",
                    "walls": self.state.slicing_params.get('wall_loops', 3),
                },
            }],
            warnings=optimization.warnings,
            questions=[{
                "id": "confirm",
                "question": "Ready to generate your model?",
                "type": "confirm",
                "options": [
                    {"value": "yes", "label": "Yes, generate model"},
                    {"value": "no", "label": "No, go back and adjust"},
                ],
            }],
            timestamp=datetime.now().isoformat(),
        )

        self.state.checkpoints.append(checkpoint)
        return checkpoint

    def get_current_checkpoint(self) -> Optional[WorkflowCheckpoint]:
        """Get the current active checkpoint."""
        for cp in reversed(self.state.checkpoints):
            if cp.status == CheckpointStatus.WAITING_INPUT:
                return cp
        return None

    def approve_checkpoint(self, answers: Dict[str, Any] = None) -> WorkflowCheckpoint:
        """
        Approve current checkpoint and advance to next stage.

        Args:
            answers: User's answers to checkpoint questions

        Returns:
            Next checkpoint
        """
        current = self.get_current_checkpoint()
        if current:
            current.status = CheckpointStatus.APPROVED
            if answers:
                current.answers = answers

        # Advance to next stage
        stage = self.state.current_stage

        if stage == WorkflowStage.REQUIREMENTS:
            return self.advance_to_design_review(answers)
        elif stage == WorkflowStage.DESIGN_REVIEW:
            return self.advance_to_material_select(answers)
        elif stage == WorkflowStage.MATERIAL_SELECT:
            return self.advance_to_nozzle_select(answers)
        elif stage == WorkflowStage.NOZZLE_SELECT:
            return self.advance_to_slicing_review(answers)
        elif stage == WorkflowStage.SLICING_REVIEW:
            return self.advance_to_final_review(answers)
        elif stage == WorkflowStage.FINAL_REVIEW:
            self.state.current_stage = WorkflowStage.READY
            self.state.is_complete = True
            return current

        return current

    def _apply_answers(self, answers: Dict[str, Any]) -> None:
        """Apply user answers to workflow state."""
        # Update design params
        if "wall_thickness_mm" in answers:
            self.state.design_params["wall_thickness_mm"] = float(answers["wall_thickness_mm"])
        if "clearance_mm" in answers:
            self.state.design_params["clearance_mm"] = float(answers["clearance_mm"])
        if "fit_type" in answers:
            # Convert fit type to clearance
            fit_clearance = {
                "tight": 0.15, "snug": 0.3, "loose": 1.0,
                "press": 0.0, "sliding": 0.5
            }
            self.state.design_params["clearance_mm"] = fit_clearance.get(
                answers["fit_type"], 0.3
            )
        if "strength_level" in answers:
            # Convert strength to wall thickness
            strength_walls = {
                "light": 1.5, "medium": 2.0, "heavy": 3.0, "extreme": 4.0
            }
            self.state.design_params["wall_thickness_mm"] = strength_walls.get(
                answers["strength_level"], 2.0
            )

    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of current workflow state."""
        return {
            "workflow_id": self.state.workflow_id,
            "stage": self.state.current_stage.value,
            "stage_number": list(WorkflowStage).index(self.state.current_stage) + 1,
            "total_stages": len(WorkflowStage),
            "is_complete": self.state.is_complete,
            "current_checkpoint": self.get_current_checkpoint().to_dict()
                                 if self.get_current_checkpoint() else None,
            "parameters": {
                "design": self.state.design_params,
                "material": self.state.material,
                "nozzle": self.state.nozzle_diameter,
                "slicing": self.state.slicing_params,
            },
        }


def create_workflow(description: str = "") -> Dict[str, Any]:
    """
    Create a new guided workflow.

    Convenience function for MCP tool.

    Args:
        description: User's initial description

    Returns:
        Workflow state dictionary
    """
    workflow = GuidedWorkflow()
    state = workflow.start_workflow(description)
    return {
        "workflow": workflow,
        "state": state.to_dict(),
        "next_action": "Answer the questions in the current checkpoint",
    }
