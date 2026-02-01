"""
Design Review Wizard - Interactive prompts during the design process.

Provides suggestions and checkpoints to guide novice users through
design decisions, ensuring printable and functional results.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple

from bambustudio_mcp.materials.filaments import FilamentProfile, get_filament_profile
from bambustudio_mcp.materials.nozzles import (
    NozzleProfile,
    get_recommended_nozzle,
    get_nozzle_profile,
)


class SuggestionPriority(str, Enum):
    """Priority level for design suggestions."""
    CRITICAL = "critical"      # Must fix - will cause print failure
    RECOMMENDED = "recommended"  # Should consider - improves quality
    OPTIONAL = "optional"       # Nice to have - minor improvement


class DesignCategory(str, Enum):
    """Categories of design suggestions."""
    DIMENSIONS = "dimensions"
    STRUCTURE = "structure"
    PRINTABILITY = "printability"
    MATERIAL = "material"
    AESTHETICS = "aesthetics"


@dataclass
class DesignSuggestion:
    """A suggestion for improving the design."""
    title: str
    description: str
    category: DesignCategory
    priority: SuggestionPriority

    # Current vs suggested values
    current_value: Optional[Any] = None
    suggested_value: Optional[Any] = None

    # Why this matters (novice-friendly explanation)
    why_it_matters: str = ""

    # What happens if ignored
    if_ignored: str = ""

    # Automatic fix available?
    auto_fixable: bool = False
    fix_parameter: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MCP response."""
        return {
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "priority": self.priority.value,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
            "why_it_matters": self.why_it_matters,
            "if_ignored": self.if_ignored,
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class DesignCheckpoint:
    """A checkpoint in the design review process."""
    name: str
    description: str
    passed: bool
    suggestions: List[DesignSuggestion] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "passed": self.passed,
            "suggestions": [s.to_dict() for s in self.suggestions],
        }


class DesignReviewer:
    """
    Interactive design reviewer for novice users.

    Analyzes design parameters and provides friendly suggestions
    to improve printability and quality.
    """

    # Novice-friendly dimension constraints
    DIMENSION_LIMITS = {
        "min_wall_thickness_mm": 0.8,   # Below this = fragile
        "min_feature_size_mm": 0.4,     # Below this = won't print
        "max_overhang_angle": 45,       # Above this = needs support
        "min_clearance_mm": 0.2,        # Below this = parts fuse
        "max_bridge_mm": 10,            # Above this = sag risk
    }

    # Common novice mistakes and fixes
    COMMON_ISSUES = {
        "too_thin_walls": {
            "min_mm": 0.8,
            "suggested_mm": 1.2,
            "explanation": "Walls thinner than 0.8mm are fragile and may not print properly.",
        },
        "no_clearance": {
            "min_mm": 0.2,
            "suggested_mm": 0.3,
            "explanation": "Moving parts need clearance or they'll fuse together during printing.",
        },
        "sharp_corners": {
            "min_radius_mm": 0.5,
            "explanation": "Sharp internal corners create stress concentrators that can crack.",
        },
    }

    def __init__(self):
        self.checkpoints: List[DesignCheckpoint] = []
        self.suggestions: List[DesignSuggestion] = []

    def review_design(
        self,
        design_params: Dict[str, Any],
        intended_use: str = "",
        material: Optional[str] = None,
        nozzle_diameter: float = 0.4,
    ) -> Dict[str, Any]:
        """
        Comprehensive design review with interactive suggestions.

        Args:
            design_params: Current design parameters
            intended_use: What the part is for (helps contextualize suggestions)
            material: Filament type to use
            nozzle_diameter: Nozzle size in mm

        Returns:
            Review results with checkpoints and suggestions
        """
        self.checkpoints = []
        self.suggestions = []

        # Get material profile if specified
        material_profile = None
        if material:
            material_profile = get_filament_profile(material)

        # Get nozzle profile
        nozzle_profile = get_nozzle_profile(nozzle_diameter)

        # Run all review checkpoints
        self._check_dimensions(design_params, nozzle_diameter)
        self._check_structural_integrity(design_params, intended_use)
        self._check_printability(design_params, nozzle_profile)
        self._check_material_compatibility(design_params, material_profile)
        self._check_aesthetics(design_params)

        # Generate summary
        critical_count = sum(
            1 for s in self.suggestions
            if s.priority == SuggestionPriority.CRITICAL
        )
        recommended_count = sum(
            1 for s in self.suggestions
            if s.priority == SuggestionPriority.RECOMMENDED
        )

        return {
            "overall_status": "needs_attention" if critical_count > 0 else "good",
            "summary": self._generate_summary(critical_count, recommended_count),
            "checkpoints": [cp.to_dict() for cp in self.checkpoints],
            "suggestions": [s.to_dict() for s in self.suggestions],
            "critical_issues": critical_count,
            "recommendations": recommended_count,
            "auto_fixable": sum(1 for s in self.suggestions if s.auto_fixable),
        }

    def _check_dimensions(
        self,
        params: Dict[str, Any],
        nozzle_diameter: float
    ) -> None:
        """Check dimension-related issues."""
        suggestions = []

        # Wall thickness check
        wall_thickness = params.get("wall_thickness", params.get("wall_thickness_mm", 0))
        if wall_thickness > 0:
            min_wall = max(nozzle_diameter * 2, 0.8)  # At least 2 perimeters
            if wall_thickness < min_wall:
                suggestions.append(DesignSuggestion(
                    title="Wall thickness too thin",
                    description=f"Your wall thickness of {wall_thickness}mm may be too thin for reliable printing.",
                    category=DesignCategory.DIMENSIONS,
                    priority=SuggestionPriority.CRITICAL,
                    current_value=wall_thickness,
                    suggested_value=max(min_wall, 1.2),
                    why_it_matters=(
                        "Thin walls are fragile and may not print properly. "
                        f"With a {nozzle_diameter}mm nozzle, you need at least "
                        f"{min_wall}mm for two solid perimeters."
                    ),
                    if_ignored="Part may have gaps, be fragile, or fail to print.",
                    auto_fixable=True,
                    fix_parameter="wall_thickness",
                ))

        # Clearance check for moving/fitting parts
        clearance = params.get("clearance", params.get("clearance_mm", 0))
        if clearance > 0 and clearance < 0.2:
            suggestions.append(DesignSuggestion(
                title="Clearance too tight",
                description=f"Your clearance of {clearance}mm may cause parts to fuse together.",
                category=DesignCategory.DIMENSIONS,
                priority=SuggestionPriority.CRITICAL,
                current_value=clearance,
                suggested_value=0.3,
                why_it_matters=(
                    "3D printers have slight inaccuracies. Parts with less than "
                    "0.2mm clearance often fuse together or don't fit."
                ),
                if_ignored="Parts may not fit together or be impossible to separate.",
                auto_fixable=True,
                fix_parameter="clearance",
            ))

        # Very large clearance warning
        if clearance > 2.0:
            suggestions.append(DesignSuggestion(
                title="Large clearance - verify fit type",
                description=f"Your clearance of {clearance}mm will create a loose fit.",
                category=DesignCategory.DIMENSIONS,
                priority=SuggestionPriority.OPTIONAL,
                current_value=clearance,
                suggested_value=None,  # Just informational
                why_it_matters=(
                    "Large clearance means the parts will be loose. "
                    "This is fine for sliding fits but may be too loose for snug fits."
                ),
                if_ignored="Part may be looser than intended.",
                auto_fixable=False,
            ))

        # Check for very small features
        for key in ["hole_diameter", "slot_width", "feature_size"]:
            if key in params:
                size = params[key]
                if size < nozzle_diameter:
                    suggestions.append(DesignSuggestion(
                        title=f"Feature may be too small: {key}",
                        description=f"The {key} of {size}mm is smaller than your nozzle diameter.",
                        category=DesignCategory.DIMENSIONS,
                        priority=SuggestionPriority.CRITICAL,
                        current_value=size,
                        suggested_value=nozzle_diameter * 1.5,
                        why_it_matters=(
                            f"Your {nozzle_diameter}mm nozzle can't reliably print features "
                            f"smaller than {nozzle_diameter}mm. The feature may not appear "
                            "or will be very rough."
                        ),
                        if_ignored="Feature may not print or look very rough.",
                        auto_fixable=True,
                        fix_parameter=key,
                    ))

        self.suggestions.extend(suggestions)
        self.checkpoints.append(DesignCheckpoint(
            name="Dimension Check",
            description="Verify dimensions are printable",
            passed=not any(s.priority == SuggestionPriority.CRITICAL for s in suggestions),
            suggestions=suggestions,
        ))

    def _check_structural_integrity(
        self,
        params: Dict[str, Any],
        intended_use: str
    ) -> None:
        """Check structural concerns based on intended use."""
        suggestions = []
        use_lower = intended_use.lower()

        # Check if heavy-duty use needs more structure
        heavy_duty_keywords = ["heavy", "strong", "force", "load", "squeeze", "grip", "hold"]
        needs_strength = any(kw in use_lower for kw in heavy_duty_keywords)

        if needs_strength:
            wall_thickness = params.get("wall_thickness", params.get("wall_thickness_mm", 2.0))
            if wall_thickness < 2.5:
                suggestions.append(DesignSuggestion(
                    title="Consider thicker walls for heavy use",
                    description="For heavy-duty applications, thicker walls add strength.",
                    category=DesignCategory.STRUCTURE,
                    priority=SuggestionPriority.RECOMMENDED,
                    current_value=wall_thickness,
                    suggested_value=3.0,
                    why_it_matters=(
                        "Based on your description mentioning heavy-duty use, "
                        "thicker walls (2.5-3mm) will significantly improve strength "
                        "and durability under load."
                    ),
                    if_ignored="Part may crack or break under heavy use.",
                    auto_fixable=True,
                    fix_parameter="wall_thickness",
                ))

        # Check handle/grip areas
        if "handle" in params or "grip" in params:
            handle_width = params.get("handle_width", params.get("handle_width_mm", 0))
            if handle_width > 0 and handle_width < 12:
                suggestions.append(DesignSuggestion(
                    title="Handle may be too narrow",
                    description="Narrow handles are uncomfortable to grip.",
                    category=DesignCategory.STRUCTURE,
                    priority=SuggestionPriority.RECOMMENDED,
                    current_value=handle_width,
                    suggested_value=15.0,
                    why_it_matters=(
                        "Handles narrower than 12mm can be uncomfortable, especially "
                        "when applying force. 15-20mm is more ergonomic."
                    ),
                    if_ignored="Handle may be uncomfortable during use.",
                    auto_fixable=True,
                    fix_parameter="handle_width",
                ))

        # Check for grip texture on handles
        if needs_strength and "add_grip_texture" in params:
            if not params.get("add_grip_texture"):
                suggestions.append(DesignSuggestion(
                    title="Consider adding grip texture",
                    description="Grip texture improves handling for heavy-duty use.",
                    category=DesignCategory.STRUCTURE,
                    priority=SuggestionPriority.OPTIONAL,
                    current_value=False,
                    suggested_value=True,
                    why_it_matters=(
                        "For parts you'll grip firmly, adding texture helps prevent "
                        "slipping, especially with wet or oily hands."
                    ),
                    if_ignored="Part may be slippery when gripping.",
                    auto_fixable=True,
                    fix_parameter="add_grip_texture",
                ))

        self.suggestions.extend(suggestions)
        self.checkpoints.append(DesignCheckpoint(
            name="Structural Review",
            description="Check strength and durability",
            passed=not any(s.priority == SuggestionPriority.CRITICAL for s in suggestions),
            suggestions=suggestions,
        ))

    def _check_printability(
        self,
        params: Dict[str, Any],
        nozzle_profile: Optional[NozzleProfile]
    ) -> None:
        """Check if design will print well."""
        suggestions = []

        # Corner radius check
        corner_radius = params.get("corner_radius", params.get("corner_radius_mm", 0))
        if corner_radius == 0:
            suggestions.append(DesignSuggestion(
                title="Add corner radius for strength",
                description="Sharp internal corners are stress concentrators.",
                category=DesignCategory.PRINTABILITY,
                priority=SuggestionPriority.RECOMMENDED,
                current_value=0,
                suggested_value=1.0,
                why_it_matters=(
                    "Sharp internal corners concentrate stress and can crack. "
                    "A small radius (1-2mm) significantly improves strength and "
                    "prints more cleanly."
                ),
                if_ignored="Part may crack at corners under stress.",
                auto_fixable=True,
                fix_parameter="corner_radius",
            ))

        # Check for known problematic aspect ratios
        if "height" in params and "width" in params:
            height = params["height"]
            width = params["width"]
            aspect = height / width if width > 0 else 0
            if aspect > 5:
                suggestions.append(DesignSuggestion(
                    title="Tall/thin part may need support",
                    description=f"Part is {aspect:.1f}x taller than wide - may tip during printing.",
                    category=DesignCategory.PRINTABILITY,
                    priority=SuggestionPriority.RECOMMENDED,
                    current_value=f"{height}h x {width}w",
                    suggested_value="Consider splitting or adding base",
                    why_it_matters=(
                        "Very tall, thin parts can wobble or tip during printing. "
                        "Consider printing in a different orientation or adding a "
                        "temporary base for stability."
                    ),
                    if_ignored="Print may fail if part tips over.",
                    auto_fixable=False,
                ))

        self.suggestions.extend(suggestions)
        self.checkpoints.append(DesignCheckpoint(
            name="Printability Check",
            description="Verify design will print reliably",
            passed=not any(s.priority == SuggestionPriority.CRITICAL for s in suggestions),
            suggestions=suggestions,
        ))

    def _check_material_compatibility(
        self,
        params: Dict[str, Any],
        material_profile: Optional[FilamentProfile]
    ) -> None:
        """Check material-specific concerns."""
        suggestions = []

        if not material_profile:
            return  # No material specified, skip

        # TPU flexibility check
        if material_profile.is_flexible:
            wall_thickness = params.get("wall_thickness", 2.0)
            if wall_thickness < 1.5:
                suggestions.append(DesignSuggestion(
                    title="TPU needs thicker walls",
                    description="Flexible materials need extra wall thickness.",
                    category=DesignCategory.MATERIAL,
                    priority=SuggestionPriority.RECOMMENDED,
                    current_value=wall_thickness,
                    suggested_value=2.5,
                    why_it_matters=(
                        "TPU is flexible, so thin walls will be very floppy. "
                        "For a functional part, use at least 2mm walls."
                    ),
                    if_ignored="Part will be very flexible/floppy.",
                    auto_fixable=True,
                    fix_parameter="wall_thickness",
                ))

        # PC heat resistance note
        if "PC" in material_profile.name or material_profile.filament_type.value == "pc":
            suggestions.append(DesignSuggestion(
                title="Polycarbonate properties",
                description="PC is strong but requires careful printing.",
                category=DesignCategory.MATERIAL,
                priority=SuggestionPriority.OPTIONAL,
                why_it_matters=(
                    "Polycarbonate is heat-resistant and strong, but prone to warping. "
                    "Keep the design compact, use a brim, and ensure good bed adhesion."
                ),
                if_ignored="Large PC parts may warp.",
                auto_fixable=False,
            ))

        self.suggestions.extend(suggestions)
        self.checkpoints.append(DesignCheckpoint(
            name="Material Compatibility",
            description="Check material-specific requirements",
            passed=True,  # Material issues are usually recommendations, not critical
            suggestions=suggestions,
        ))

    def _check_aesthetics(self, params: Dict[str, Any]) -> None:
        """Check aesthetic considerations."""
        suggestions = []

        # This checkpoint provides optional aesthetic suggestions
        # Not critical for function, just nice-to-haves

        self.checkpoints.append(DesignCheckpoint(
            name="Aesthetics Review",
            description="Optional aesthetic improvements",
            passed=True,
            suggestions=suggestions,
        ))

    def _generate_summary(self, critical: int, recommended: int) -> str:
        """Generate a novice-friendly summary."""
        if critical == 0 and recommended == 0:
            return "Your design looks great! No issues detected."

        parts = []
        if critical > 0:
            parts.append(f"{critical} issue(s) that should be fixed before printing")
        if recommended > 0:
            parts.append(f"{recommended} suggestion(s) to improve quality")

        return "Design review found: " + " and ".join(parts) + "."

    def apply_suggestion(
        self,
        params: Dict[str, Any],
        suggestion: DesignSuggestion
    ) -> Dict[str, Any]:
        """Apply an auto-fixable suggestion to the parameters."""
        if not suggestion.auto_fixable or not suggestion.fix_parameter:
            return params

        updated = params.copy()
        updated[suggestion.fix_parameter] = suggestion.suggested_value
        return updated

    def apply_all_critical(
        self,
        params: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Apply all critical auto-fixable suggestions."""
        updated = params.copy()
        applied = []

        for suggestion in self.suggestions:
            if (suggestion.priority == SuggestionPriority.CRITICAL
                and suggestion.auto_fixable
                and suggestion.fix_parameter):
                updated[suggestion.fix_parameter] = suggestion.suggested_value
                applied.append(suggestion.title)

        return updated, applied


def get_design_questions(
    category: str,
    current_params: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Get interactive questions to ask the user during design.

    Returns a list of questions with options for the MCP to present.
    """
    questions = []

    if category == "tube_squeezer":
        # Fit type question
        questions.append({
            "id": "fit_type",
            "question": "How should the squeezer fit on the tube?",
            "options": [
                {
                    "value": "snug",
                    "label": "Snug fit (Recommended)",
                    "description": "Stays in place but can slide with effort. Best for daily use.",
                    "clearance_mm": 0.3,
                },
                {
                    "value": "tight",
                    "label": "Tight fit",
                    "description": "Grips firmly, harder to move. Good for thick products.",
                    "clearance_mm": 0.15,
                },
                {
                    "value": "loose",
                    "label": "Loose fit",
                    "description": "Slides easily. Good for frequently repositioning.",
                    "clearance_mm": 0.8,
                },
            ],
            "default": "snug",
        })

        # Strength question
        questions.append({
            "id": "strength",
            "question": "How much force will you apply when squeezing?",
            "options": [
                {
                    "value": "light",
                    "label": "Light (toothpaste, thin lotions)",
                    "description": "Standard wall thickness is fine.",
                    "wall_thickness_mm": 2.0,
                },
                {
                    "value": "medium",
                    "label": "Medium (Recommended)",
                    "description": "Slightly thicker walls for everyday use.",
                    "wall_thickness_mm": 2.5,
                },
                {
                    "value": "heavy",
                    "label": "Heavy (thick lotions, paste)",
                    "description": "Extra thick walls for maximum durability.",
                    "wall_thickness_mm": 3.5,
                },
            ],
            "default": "medium",
        })

        # Grip texture question
        if current_params.get("wall_thickness_mm", 0) >= 2.5:
            questions.append({
                "id": "grip",
                "question": "Would you like grip texture on the handles?",
                "options": [
                    {
                        "value": "yes",
                        "label": "Yes, add grip ridges (Recommended)",
                        "description": "Easier to hold, especially with wet hands.",
                        "add_grip_texture": True,
                    },
                    {
                        "value": "no",
                        "label": "No, keep smooth",
                        "description": "Cleaner look, but may be slippery.",
                        "add_grip_texture": False,
                    },
                ],
                "default": "yes",
            })

    return questions
