"""
Slicing Review Wizard - Quality recommendations for slicing parameters.

Provides interactive review of slicing settings with material-aware
suggestions to ensure optimal print quality.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple

from bambustudio_mcp.materials.filaments import (
    FilamentProfile,
    FilamentType,
    get_filament_profile,
    FILAMENT_PROFILES,
)
from bambustudio_mcp.materials.nozzles import (
    NozzleProfile,
    get_nozzle_profile,
    get_recommended_nozzle,
    get_layer_height_for_quality,
)
from bambustudio_mcp.slicer.parameters import SlicingParameters, InfillPattern


class QualityPreset(str, Enum):
    """Print quality presets for novice users."""
    DRAFT = "draft"           # Fast, lower quality
    STANDARD = "standard"      # Balanced
    QUALITY = "quality"        # Slower, better surface
    ULTRA = "ultra"            # Slowest, best quality


class PrintUseCase(str, Enum):
    """Common use cases that affect print settings."""
    DECORATIVE = "decorative"      # Looks matter most
    FUNCTIONAL = "functional"      # Strength matters most
    PROTOTYPE = "prototype"        # Fast iteration
    GIFT = "gift"                  # Balance of both


@dataclass
class SlicingSuggestion:
    """A suggestion for slicing parameter adjustment."""
    parameter: str
    current_value: Any
    suggested_value: Any
    reason: str
    impact: str  # What changes with this setting
    priority: str = "recommended"  # critical, recommended, optional

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter": self.parameter,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
            "reason": self.reason,
            "impact": self.impact,
            "priority": self.priority,
        }


@dataclass
class SlicingReview:
    """Complete slicing review with suggestions."""
    quality_preset: QualityPreset
    estimated_time_change: str
    suggestions: List[SlicingSuggestion] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    material_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quality_preset": self.quality_preset.value,
            "estimated_time_change": self.estimated_time_change,
            "suggestions": [s.to_dict() for s in self.suggestions],
            "warnings": self.warnings,
            "material_notes": self.material_notes,
        }


class SlicingReviewer:
    """
    Reviews slicing parameters and provides quality recommendations.

    Takes into account material properties, nozzle size, and intended
    use to suggest optimal settings.
    """

    # Quality preset definitions
    QUALITY_SETTINGS = {
        QualityPreset.DRAFT: {
            "layer_height_ratio": 0.7,   # % of nozzle diameter
            "wall_loops": 2,
            "infill_density": 15,
            "speed_factor": 1.2,
            "description": "Fast printing, visible layer lines",
        },
        QualityPreset.STANDARD: {
            "layer_height_ratio": 0.5,
            "wall_loops": 3,
            "infill_density": 20,
            "speed_factor": 1.0,
            "description": "Balanced speed and quality",
        },
        QualityPreset.QUALITY: {
            "layer_height_ratio": 0.35,
            "wall_loops": 4,
            "infill_density": 25,
            "speed_factor": 0.8,
            "description": "Better surface finish, slower",
        },
        QualityPreset.ULTRA: {
            "layer_height_ratio": 0.25,
            "wall_loops": 5,
            "infill_density": 30,
            "speed_factor": 0.6,
            "description": "Best quality, much slower",
        },
    }

    def __init__(self):
        self.suggestions: List[SlicingSuggestion] = []
        self.warnings: List[str] = []

    def review_parameters(
        self,
        params: SlicingParameters,
        material: str,
        nozzle_diameter: float = 0.4,
        use_case: PrintUseCase = PrintUseCase.FUNCTIONAL,
        quality: QualityPreset = QualityPreset.STANDARD,
    ) -> SlicingReview:
        """
        Review slicing parameters and provide suggestions.

        Args:
            params: Current slicing parameters
            material: Filament type/name
            nozzle_diameter: Nozzle size in mm
            use_case: What the print is for
            quality: Desired quality level

        Returns:
            SlicingReview with suggestions
        """
        self.suggestions = []
        self.warnings = []

        # Get profiles
        material_profile = get_filament_profile(material)
        nozzle_profile = get_nozzle_profile(nozzle_diameter)
        quality_settings = self.QUALITY_SETTINGS[quality]

        # Run all checks
        self._check_layer_height(params, nozzle_diameter, quality_settings)
        self._check_temperatures(params, material_profile)
        self._check_speeds(params, material_profile, quality_settings)
        self._check_infill(params, use_case, quality_settings)
        self._check_walls(params, use_case, quality_settings)
        self._check_supports(params, use_case)
        self._check_adhesion(params, material_profile)

        # Material-specific notes
        material_notes = self._get_material_notes(material_profile)

        # Estimate time impact
        time_change = self._estimate_time_change(params, quality_settings)

        return SlicingReview(
            quality_preset=quality,
            estimated_time_change=time_change,
            suggestions=self.suggestions,
            warnings=self.warnings,
            material_notes=material_notes,
        )

    def _check_layer_height(
        self,
        params: SlicingParameters,
        nozzle_diameter: float,
        quality: Dict[str, Any]
    ) -> None:
        """Check layer height settings."""
        optimal = nozzle_diameter * quality["layer_height_ratio"]
        optimal = round(optimal / 0.04) * 0.04  # Round to 0.04mm

        if abs(params.layer_height - optimal) > 0.04:
            direction = "thinner" if params.layer_height > optimal else "thicker"
            self.suggestions.append(SlicingSuggestion(
                parameter="layer_height",
                current_value=f"{params.layer_height}mm",
                suggested_value=f"{optimal}mm",
                reason=f"For {quality['description'].lower()}, {direction} layers work better",
                impact=f"{'Better surface finish' if direction == 'thinner' else 'Faster printing'}",
            ))

        # Check max layer height relative to nozzle
        max_safe = nozzle_diameter * 0.75
        if params.layer_height > max_safe:
            self.warnings.append(
                f"Layer height ({params.layer_height}mm) exceeds 75% of nozzle diameter. "
                f"May cause adhesion issues."
            )

    def _check_temperatures(
        self,
        params: SlicingParameters,
        material: Optional[FilamentProfile]
    ) -> None:
        """Check temperature settings against material requirements."""
        if not material:
            return

        # Nozzle temperature
        if hasattr(params, 'nozzle_temp') and params.nozzle_temp:
            if params.nozzle_temp < material.nozzle_temp.min_temp:
                self.suggestions.append(SlicingSuggestion(
                    parameter="nozzle_temp",
                    current_value=f"{params.nozzle_temp}°C",
                    suggested_value=f"{material.nozzle_temp.optimal}°C",
                    reason=f"{material.name} needs at least {material.nozzle_temp.min_temp}°C",
                    impact="Better layer adhesion, fewer clogs",
                    priority="critical",
                ))
            elif params.nozzle_temp > material.nozzle_temp.max_temp:
                self.suggestions.append(SlicingSuggestion(
                    parameter="nozzle_temp",
                    current_value=f"{params.nozzle_temp}°C",
                    suggested_value=f"{material.nozzle_temp.optimal}°C",
                    reason=f"{material.name} may degrade above {material.nozzle_temp.max_temp}°C",
                    impact="Prevents stringing and degradation",
                    priority="critical",
                ))

        # Bed temperature
        if hasattr(params, 'bed_temp') and params.bed_temp:
            if params.bed_temp < material.bed_temp.min_temp:
                self.suggestions.append(SlicingSuggestion(
                    parameter="bed_temp",
                    current_value=f"{params.bed_temp}°C",
                    suggested_value=f"{material.bed_temp.optimal}°C",
                    reason=f"{material.name} may not stick below {material.bed_temp.min_temp}°C",
                    impact="Better first layer adhesion",
                    priority="critical",
                ))

    def _check_speeds(
        self,
        params: SlicingParameters,
        material: Optional[FilamentProfile],
        quality: Dict[str, Any]
    ) -> None:
        """Check print speed settings."""
        if not material:
            return

        max_speed = material.max_print_speed * quality["speed_factor"]

        # Check outer wall speed
        if params.outer_wall_speed > max_speed:
            self.suggestions.append(SlicingSuggestion(
                parameter="outer_wall_speed",
                current_value=f"{params.outer_wall_speed}mm/s",
                suggested_value=f"{int(max_speed)}mm/s",
                reason=f"{material.name} prints best at lower speeds for quality",
                impact="Better surface finish, fewer artifacts",
            ))

        # TPU specific speed limits
        if material.is_flexible and params.outer_wall_speed > 30:
            self.suggestions.append(SlicingSuggestion(
                parameter="outer_wall_speed",
                current_value=f"{params.outer_wall_speed}mm/s",
                suggested_value="25-30mm/s",
                reason="Flexible filaments need slow speeds to prevent jamming",
                impact="Prevents extruder jams and poor quality",
                priority="critical",
            ))

        # Volumetric flow check
        if hasattr(params, 'layer_height') and hasattr(params, 'line_width'):
            volumetric = (params.layer_height * params.line_width *
                         params.outer_wall_speed)
            if volumetric > material.max_volumetric_flow:
                safe_speed = material.max_volumetric_flow / (
                    params.layer_height * params.line_width
                )
                self.suggestions.append(SlicingSuggestion(
                    parameter="outer_wall_speed",
                    current_value=f"{params.outer_wall_speed}mm/s",
                    suggested_value=f"{int(safe_speed)}mm/s",
                    reason=f"Exceeds max flow rate ({material.max_volumetric_flow}mm³/s)",
                    impact="Prevents under-extrusion",
                    priority="critical",
                ))

    def _check_infill(
        self,
        params: SlicingParameters,
        use_case: PrintUseCase,
        quality: Dict[str, Any]
    ) -> None:
        """Check infill settings for use case."""
        target_infill = quality["infill_density"]

        # Adjust for use case
        if use_case == PrintUseCase.FUNCTIONAL:
            target_infill = max(target_infill, 25)  # Need strength
        elif use_case == PrintUseCase.DECORATIVE:
            target_infill = min(target_infill, 15)  # Looks don't need infill
        elif use_case == PrintUseCase.PROTOTYPE:
            target_infill = min(target_infill, 10)  # Fast iteration

        if abs(params.sparse_infill_density - target_infill) > 5:
            direction = "more" if params.sparse_infill_density < target_infill else "less"
            self.suggestions.append(SlicingSuggestion(
                parameter="sparse_infill_density",
                current_value=f"{params.sparse_infill_density}%",
                suggested_value=f"{target_infill}%",
                reason=f"For {use_case.value} use, {direction} infill is recommended",
                impact=f"{'Stronger part' if direction == 'more' else 'Faster print'}",
            ))

        # Infill pattern suggestions
        if use_case == PrintUseCase.FUNCTIONAL:
            if params.sparse_infill_pattern not in [
                InfillPattern.GYROID,
                InfillPattern.CUBIC,
                InfillPattern.HONEYCOMB,
            ]:
                self.suggestions.append(SlicingSuggestion(
                    parameter="sparse_infill_pattern",
                    current_value=params.sparse_infill_pattern.value,
                    suggested_value="gyroid",
                    reason="Gyroid or cubic infill is stronger for functional parts",
                    impact="Better strength in all directions",
                    priority="optional",
                ))

    def _check_walls(
        self,
        params: SlicingParameters,
        use_case: PrintUseCase,
        quality: Dict[str, Any]
    ) -> None:
        """Check wall/perimeter settings."""
        target_walls = quality["wall_loops"]

        if use_case == PrintUseCase.FUNCTIONAL:
            target_walls = max(target_walls, 4)

        if params.wall_loops < target_walls:
            self.suggestions.append(SlicingSuggestion(
                parameter="wall_loops",
                current_value=params.wall_loops,
                suggested_value=target_walls,
                reason=f"More walls = stronger part for {use_case.value} use",
                impact="Increased strength and durability",
            ))

    def _check_supports(
        self,
        params: SlicingParameters,
        use_case: PrintUseCase
    ) -> None:
        """Check support settings."""
        if hasattr(params, 'enable_support'):
            if params.enable_support and use_case == PrintUseCase.DECORATIVE:
                self.suggestions.append(SlicingSuggestion(
                    parameter="support_pattern",
                    current_value="default",
                    suggested_value="tree",
                    reason="Tree supports leave smaller marks on decorative parts",
                    impact="Cleaner surface after support removal",
                    priority="optional",
                ))

    def _check_adhesion(
        self,
        params: SlicingParameters,
        material: Optional[FilamentProfile]
    ) -> None:
        """Check bed adhesion settings."""
        if not material:
            return

        # Materials prone to warping need brim
        warp_prone = ["PC", "ABS", "Nylon", "PA"]
        needs_adhesion = any(m in material.name for m in warp_prone)

        if needs_adhesion and params.brim_width < 5:
            self.suggestions.append(SlicingSuggestion(
                parameter="brim_width",
                current_value=f"{params.brim_width}mm",
                suggested_value="8mm",
                reason=f"{material.name} is prone to warping",
                impact="Prevents corners from lifting",
                priority="recommended",
            ))

        # First layer speed for adhesion
        if params.initial_layer_speed > 30:
            self.suggestions.append(SlicingSuggestion(
                parameter="initial_layer_speed",
                current_value=f"{params.initial_layer_speed}mm/s",
                suggested_value="20-25mm/s",
                reason="Slower first layer improves adhesion",
                impact="Better stick to bed, fewer failed starts",
            ))

    def _get_material_notes(
        self,
        material: Optional[FilamentProfile]
    ) -> List[str]:
        """Get material-specific printing notes."""
        notes = []

        if not material:
            return notes

        # TPU notes
        if material.is_flexible:
            notes.extend([
                "TPU is flexible - print slowly (25-35mm/s max)",
                "Direct drive recommended - may struggle with bowden",
                "Disable retraction or use very short retracts (0.5mm)",
                "TPU 95A is NOT compatible with AMS - feed directly",
            ])

        # PC notes
        if "PC" in material.name:
            notes.extend([
                "PC warps easily - use enclosed printer if possible",
                "Keep parts small when printing on A1 (open frame)",
                "Use wide brim (8-10mm) for better adhesion",
                "High bed temp required - ensure bed is level",
            ])

        # PETG notes
        if material.filament_type == FilamentType.PETG:
            notes.extend([
                "PETG likes to string - tune retraction carefully",
                "Prints glossy - good for visual parts",
                "Z-hop helps prevent nozzle hitting printed parts",
            ])

        # General notes based on properties
        if not material.ams_compatible:
            notes.append(
                f"{material.name} is NOT compatible with AMS - feed directly to extruder"
            )

        return notes

    def _estimate_time_change(
        self,
        params: SlicingParameters,
        quality: Dict[str, Any]
    ) -> str:
        """Estimate how suggestions affect print time."""
        factor = quality["speed_factor"]

        if factor < 0.8:
            return "Significantly longer (+30-50%)"
        elif factor < 1.0:
            return "Slightly longer (+10-20%)"
        elif factor > 1.1:
            return "Faster (-15-25%)"
        else:
            return "Similar time"


def get_slicing_questions(
    material: str,
    model_info: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Get interactive questions for slicing configuration.

    Returns questions to ask the user before slicing.
    """
    questions = []

    # Quality level question
    questions.append({
        "id": "quality",
        "question": "What quality level do you want?",
        "options": [
            {
                "value": "draft",
                "label": "Draft (Fastest)",
                "description": "Quick test print, visible layer lines. Good for checking fit.",
                "time_factor": "~60% of standard time",
            },
            {
                "value": "standard",
                "label": "Standard (Recommended)",
                "description": "Balanced quality and speed. Good for most prints.",
                "time_factor": "Normal print time",
            },
            {
                "value": "quality",
                "label": "Quality",
                "description": "Better surface finish, slower. Good for visible parts.",
                "time_factor": "~130% of standard time",
            },
            {
                "value": "ultra",
                "label": "Ultra Quality (Slowest)",
                "description": "Best possible finish. For display pieces or detailed models.",
                "time_factor": "~200% of standard time",
            },
        ],
        "default": "standard",
    })

    # Use case question
    questions.append({
        "id": "use_case",
        "question": "What will this print be used for?",
        "options": [
            {
                "value": "functional",
                "label": "Functional part (Recommended for tools)",
                "description": "Needs to be strong and durable. May be handled or stressed.",
                "infill": 25,
                "walls": 4,
            },
            {
                "value": "decorative",
                "label": "Decorative / Display",
                "description": "Appearance matters most. Won't be stressed.",
                "infill": 15,
                "walls": 3,
            },
            {
                "value": "prototype",
                "label": "Prototype / Test fit",
                "description": "Just checking if it works. Speed over quality.",
                "infill": 10,
                "walls": 2,
            },
            {
                "value": "gift",
                "label": "Gift / Final product",
                "description": "Balance of strength and appearance.",
                "infill": 20,
                "walls": 4,
            },
        ],
        "default": "functional",
    })

    # Material-specific questions
    material_profile = get_filament_profile(material)
    if material_profile:
        if material_profile.is_flexible:
            questions.append({
                "id": "flexibility",
                "question": "How flexible should the final part be?",
                "options": [
                    {
                        "value": "flexible",
                        "label": "Very flexible",
                        "description": "Thin walls, low infill. Maximum bend.",
                        "wall_loops": 2,
                        "infill": 10,
                    },
                    {
                        "value": "semi_rigid",
                        "label": "Semi-rigid (Recommended)",
                        "description": "Some flex but holds shape. Good for grips.",
                        "wall_loops": 3,
                        "infill": 20,
                    },
                    {
                        "value": "rigid",
                        "label": "Rigid",
                        "description": "Thick walls, high infill. Minimal flex.",
                        "wall_loops": 5,
                        "infill": 40,
                    },
                ],
                "default": "semi_rigid",
            })

    return questions


def get_recommended_settings(
    material: str,
    nozzle_diameter: float,
    quality: QualityPreset,
    use_case: PrintUseCase,
) -> Dict[str, Any]:
    """
    Get recommended slicing settings based on user choices.

    Returns a dictionary of suggested parameter values.
    """
    material_profile = get_filament_profile(material)
    nozzle_profile = get_nozzle_profile(nozzle_diameter)
    quality_settings = SlicingReviewer.QUALITY_SETTINGS[quality]

    settings = {}

    # Layer height
    layer_height = nozzle_diameter * quality_settings["layer_height_ratio"]
    settings["layer_height"] = round(layer_height / 0.04) * 0.04

    # Walls
    base_walls = quality_settings["wall_loops"]
    if use_case == PrintUseCase.FUNCTIONAL:
        base_walls = max(base_walls, 4)
    settings["wall_loops"] = base_walls

    # Infill
    base_infill = quality_settings["infill_density"]
    if use_case == PrintUseCase.FUNCTIONAL:
        base_infill = max(base_infill, 25)
    elif use_case == PrintUseCase.PROTOTYPE:
        base_infill = min(base_infill, 15)
    settings["sparse_infill_density"] = base_infill

    # Pattern
    if use_case == PrintUseCase.FUNCTIONAL:
        settings["sparse_infill_pattern"] = "gyroid"
    else:
        settings["sparse_infill_pattern"] = "grid"

    # Temperatures from material
    if material_profile:
        settings["nozzle_temp"] = material_profile.nozzle_temp.optimal
        settings["bed_temp"] = material_profile.bed_temp.optimal

        # Speed adjustments
        max_speed = material_profile.max_print_speed * quality_settings["speed_factor"]
        settings["outer_wall_speed"] = min(int(max_speed * 0.6), 80)
        settings["inner_wall_speed"] = min(int(max_speed * 0.8), 120)
        settings["infill_speed"] = min(int(max_speed), 150)

        # Retraction
        settings["retraction_length"] = material_profile.retraction_length
        settings["retraction_speed"] = material_profile.retraction_speed

    # First layer
    settings["initial_layer_speed"] = 25
    settings["initial_layer_height"] = settings["layer_height"] * 1.2

    # Adhesion
    settings["brim_width"] = 5
    if material_profile and any(m in material_profile.name for m in ["PC", "ABS", "Nylon"]):
        settings["brim_width"] = 8

    return settings
