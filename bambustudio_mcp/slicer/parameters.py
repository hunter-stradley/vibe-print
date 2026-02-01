"""
Slicing Parameter Management - Profiles and settings for BambuStudio.

Manages slicing parameters for different use cases, materials, and quality levels.
"""

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List


class QualityLevel(str, Enum):
    """Print quality presets."""
    DRAFT = "draft"           # Fast, lower quality (0.28mm)
    STANDARD = "standard"     # Balanced (0.20mm)
    QUALITY = "quality"       # Higher quality (0.16mm)
    FINE = "fine"            # Fine detail (0.12mm)
    ULTRA = "ultra"          # Maximum quality (0.08mm)


class InfillPattern(str, Enum):
    """Infill pattern types."""
    GRID = "grid"
    GYROID = "gyroid"
    HONEYCOMB = "honeycomb"
    CUBIC = "cubic"
    LINE = "line"
    RECTILINEAR = "rectilinear"
    TRIANGLES = "triangles"
    ADAPTIVE_CUBIC = "adaptivecubic"


class SupportType(str, Enum):
    """Support structure types."""
    NONE = "none"
    NORMAL = "normal"
    TREE = "tree"
    ORGANIC = "organic"


class BedType(str, Enum):
    """Bambu bed plate types."""
    COOL_PLATE = "Cool Plate"
    ENGINEERING_PLATE = "Engineering Plate"
    HIGH_TEMP_PLATE = "High Temp Plate"
    TEXTURED_PEI = "Textured PEI Plate"


@dataclass
class SlicingParameters:
    """
    Complete slicing parameter set for BambuStudio.

    These map to BambuStudio's configuration options.
    """
    # Layer settings
    layer_height: float = 0.20
    initial_layer_height: float = 0.20

    # Wall settings
    wall_loops: int = 2
    wall_thickness: float = 0.8  # Calculated from loops * nozzle
    top_shell_layers: int = 4
    bottom_shell_layers: int = 4

    # Infill settings
    sparse_infill_density: float = 15.0  # Percentage
    sparse_infill_pattern: InfillPattern = InfillPattern.GYROID

    # Speed settings (mm/s)
    outer_wall_speed: float = 60.0
    inner_wall_speed: float = 80.0
    sparse_infill_speed: float = 150.0
    travel_speed: float = 300.0
    initial_layer_speed: float = 30.0

    # Temperature settings
    nozzle_temperature: int = 220
    nozzle_temperature_initial_layer: int = 220
    bed_temperature: int = 60
    bed_temperature_initial_layer: int = 60

    # Support settings
    support_type: SupportType = SupportType.NONE
    support_threshold_angle: int = 45

    # Bed settings
    bed_type: BedType = BedType.COOL_PLATE

    # Brim/Adhesion
    brim_width: float = 0.0  # 0 = disabled
    brim_type: str = "outer_only"

    # Retraction
    retraction_length: float = 0.8
    retraction_speed: float = 30.0
    z_hop: float = 0.4

    # Quality
    seam_position: str = "aligned"
    ironing: bool = False

    # Filament settings (for reference)
    filament_type: str = "PLA"
    filament_density: float = 1.24  # g/cm³
    filament_cost: float = 25.0  # per kg

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        # Convert enums to strings
        result["sparse_infill_pattern"] = self.sparse_infill_pattern.value
        result["support_type"] = self.support_type.value
        result["bed_type"] = self.bed_type.value
        return result

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SlicingParameters":
        """Create from dictionary."""
        # Convert string enums back
        if "sparse_infill_pattern" in data:
            data["sparse_infill_pattern"] = InfillPattern(data["sparse_infill_pattern"])
        if "support_type" in data:
            data["support_type"] = SupportType(data["support_type"])
        if "bed_type" in data:
            data["bed_type"] = BedType(data["bed_type"])
        return cls(**data)

    def to_cli_args(self) -> List[str]:
        """
        Convert to BambuStudio CLI arguments.

        Returns list of --key=value pairs.
        """
        args = [
            f"--layer-height={self.layer_height}",
            f"--first-layer-height={self.initial_layer_height}",
            f"--wall-loops={self.wall_loops}",
            f"--top-shell-layers={self.top_shell_layers}",
            f"--bottom-shell-layers={self.bottom_shell_layers}",
            f"--sparse-infill-density={self.sparse_infill_density}",
            f"--sparse-infill-pattern={self.sparse_infill_pattern.value}",
            f"--curr-bed-type={self.bed_type.value}",
        ]

        if self.support_type != SupportType.NONE:
            args.append(f"--support-type={self.support_type.value}")

        return args


@dataclass
class ParameterPreset:
    """Named parameter preset for easy reuse."""
    name: str
    description: str
    parameters: SlicingParameters
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters.to_dict(),
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParameterPreset":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data["description"],
            parameters=SlicingParameters.from_dict(data["parameters"]),
            tags=data.get("tags", []),
        )


# Built-in presets for common use cases
PRESET_TUBE_SQUEEZER_STANDARD = ParameterPreset(
    name="tube_squeezer_standard",
    description="Standard settings for tube squeezers - good balance of strength and speed",
    parameters=SlicingParameters(
        layer_height=0.20,
        wall_loops=3,  # Extra walls for strength
        sparse_infill_density=20.0,
        sparse_infill_pattern=InfillPattern.GYROID,
        support_type=SupportType.NONE,
        brim_width=5.0,  # Brim for bed adhesion
    ),
    tags=["tube_squeezer", "functional", "strength"],
)

PRESET_TUBE_SQUEEZER_STRONG = ParameterPreset(
    name="tube_squeezer_strong",
    description="Heavy-duty settings for larger tube squeezers (lotion bottles, etc.)",
    parameters=SlicingParameters(
        layer_height=0.20,
        wall_loops=4,  # Extra thick walls
        sparse_infill_density=30.0,  # More infill
        sparse_infill_pattern=InfillPattern.CUBIC,
        support_type=SupportType.NONE,
        brim_width=8.0,
        outer_wall_speed=50.0,  # Slower for better adhesion
    ),
    tags=["tube_squeezer", "functional", "heavy_duty", "strength"],
)

PRESET_DRAFT = ParameterPreset(
    name="draft",
    description="Fast draft quality for testing fit and dimensions",
    parameters=SlicingParameters(
        layer_height=0.28,
        wall_loops=2,
        sparse_infill_density=10.0,
        sparse_infill_pattern=InfillPattern.GRID,
        outer_wall_speed=80.0,
        inner_wall_speed=100.0,
    ),
    tags=["draft", "fast", "testing"],
)

PRESET_QUALITY = ParameterPreset(
    name="quality",
    description="High quality for final prints with fine detail",
    parameters=SlicingParameters(
        layer_height=0.12,
        wall_loops=3,
        sparse_infill_density=20.0,
        sparse_infill_pattern=InfillPattern.GYROID,
        outer_wall_speed=40.0,
        inner_wall_speed=60.0,
    ),
    tags=["quality", "detail", "final"],
)


# All built-in presets
BUILTIN_PRESETS: Dict[str, ParameterPreset] = {
    "tube_squeezer_standard": PRESET_TUBE_SQUEEZER_STANDARD,
    "tube_squeezer_strong": PRESET_TUBE_SQUEEZER_STRONG,
    "draft": PRESET_DRAFT,
    "quality": PRESET_QUALITY,
}


def get_preset(name: str) -> ParameterPreset:
    """Get a built-in preset by name."""
    if name not in BUILTIN_PRESETS:
        available = ", ".join(BUILTIN_PRESETS.keys())
        raise ValueError(f"Unknown preset '{name}'. Available: {available}")
    return BUILTIN_PRESETS[name]


def adjust_for_scale(params: SlicingParameters, scale_factor: float) -> SlicingParameters:
    """
    Adjust slicing parameters based on model scale.

    Larger models may need different settings for strength and print time.

    Args:
        params: Base parameters
        scale_factor: How much the model was scaled

    Returns:
        Adjusted parameters
    """
    import copy
    adjusted = copy.deepcopy(params)

    if scale_factor > 2.0:
        # Large scale-up: increase strength
        adjusted.wall_loops = max(params.wall_loops, 4)
        adjusted.sparse_infill_density = min(params.sparse_infill_density + 10, 40)
        adjusted.brim_width = max(params.brim_width, 8.0)

    elif scale_factor > 1.5:
        # Moderate scale-up
        adjusted.wall_loops = max(params.wall_loops, 3)
        adjusted.sparse_infill_density = min(params.sparse_infill_density + 5, 30)
        adjusted.brim_width = max(params.brim_width, 5.0)

    elif scale_factor < 0.5:
        # Scale down: may need finer layers
        adjusted.layer_height = min(params.layer_height, 0.16)

    return adjusted
