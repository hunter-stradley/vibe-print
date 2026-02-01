"""
Nozzle Profiles - A1 nozzle configurations and recommendations.

Based on Bambu Lab A1 specifications and community best practices.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple


class NozzleType(str, Enum):
    """Nozzle material types."""
    STAINLESS_STEEL = "stainless_steel"
    HARDENED_STEEL = "hardened_steel"


@dataclass
class NozzleProfile:
    """
    Nozzle configuration for A1 printer.

    Based on Bambu Lab specifications:
    - 0.2mm: Stainless steel only (fine detail)
    - 0.4mm: Stainless steel (default) or Hardened steel
    - 0.6mm: Hardened steel only (faster printing)
    - 0.8mm: Hardened steel only (fast/draft)
    """
    diameter: float  # mm
    nozzle_type: NozzleType

    # Layer height recommendations
    min_layer_height: float = 0.08
    optimal_layer_height: float = 0.20
    max_layer_height: float = 0.28

    # Speed adjustments
    speed_multiplier: float = 1.0  # Relative to 0.4mm baseline

    # Compatible materials
    abrasive_safe: bool = False  # Can print CF/GF filaments

    # Use cases
    best_for: List[str] = field(default_factory=list)
    avoid_for: List[str] = field(default_factory=list)

    def get_layer_heights(self) -> Dict[str, float]:
        """Get layer height recommendations."""
        return {
            "fine": self.min_layer_height,
            "standard": self.optimal_layer_height,
            "draft": self.max_layer_height,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "diameter_mm": self.diameter,
            "type": self.nozzle_type.value,
            "layer_heights": self.get_layer_heights(),
            "speed_multiplier": self.speed_multiplier,
            "abrasive_safe": self.abrasive_safe,
            "best_for": self.best_for,
            "avoid_for": self.avoid_for,
        }


# =============================================================================
# A1 Nozzle Configurations
# =============================================================================

NOZZLE_02_SS = NozzleProfile(
    diameter=0.2,
    nozzle_type=NozzleType.STAINLESS_STEEL,
    min_layer_height=0.04,
    optimal_layer_height=0.08,
    max_layer_height=0.12,
    speed_multiplier=0.5,  # Much slower
    abrasive_safe=False,
    best_for=[
        "Fine text and lettering",
        "Miniatures and figurines",
        "High-detail decorative items",
        "Thin-walled parts",
    ],
    avoid_for=[
        "Large prints (very slow)",
        "Functional/structural parts",
        "Abrasive filaments (CF/GF)",
    ],
)

NOZZLE_04_SS = NozzleProfile(
    diameter=0.4,
    nozzle_type=NozzleType.STAINLESS_STEEL,
    min_layer_height=0.08,
    optimal_layer_height=0.20,
    max_layer_height=0.28,
    speed_multiplier=1.0,  # Baseline
    abrasive_safe=False,
    best_for=[
        "General purpose printing",
        "Good balance of speed and detail",
        "Most PLA, PETG, TPU prints",
        "Functional prototypes",
    ],
    avoid_for=[
        "Carbon fiber filaments",
        "Glass fiber filaments",
        "Glow-in-the-dark filaments",
    ],
)

NOZZLE_04_HS = NozzleProfile(
    diameter=0.4,
    nozzle_type=NozzleType.HARDENED_STEEL,
    min_layer_height=0.08,
    optimal_layer_height=0.20,
    max_layer_height=0.28,
    speed_multiplier=1.0,
    abrasive_safe=True,
    best_for=[
        "Abrasive filaments (CF, GF)",
        "Glow-in-the-dark filaments",
        "Long-term heavy use",
        "When you don't want to swap nozzles",
    ],
    avoid_for=[
        "Highest thermal conductivity needed",
        # Hardened steel has slightly lower thermal conductivity
    ],
)

NOZZLE_06_HS = NozzleProfile(
    diameter=0.6,
    nozzle_type=NozzleType.HARDENED_STEEL,
    min_layer_height=0.12,
    optimal_layer_height=0.30,
    max_layer_height=0.42,
    speed_multiplier=1.5,  # Faster
    abrasive_safe=True,
    best_for=[
        "Faster prints with acceptable detail",
        "Larger functional parts",
        "Vases and containers",
        "Carbon fiber filaments (less clog risk)",
        "Structural parts that don't need fine detail",
    ],
    avoid_for=[
        "Fine text or small details",
        "Miniatures",
        "Parts requiring thin walls < 0.6mm",
    ],
)

NOZZLE_08_HS = NozzleProfile(
    diameter=0.8,
    nozzle_type=NozzleType.HARDENED_STEEL,
    min_layer_height=0.20,
    optimal_layer_height=0.40,
    max_layer_height=0.56,
    speed_multiplier=2.0,  # Much faster
    abrasive_safe=True,
    best_for=[
        "Draft/test prints",
        "Very large parts",
        "Speed is priority over detail",
        "Thick-walled sturdy parts",
        "Industrial prototypes",
    ],
    avoid_for=[
        "Any fine detail work",
        "Small parts",
        "Decorative items",
        "Parts with thin features",
    ],
)


# Registry of all A1 nozzles
A1_NOZZLES: Dict[str, NozzleProfile] = {
    "0.2": NOZZLE_02_SS,
    "0.2_ss": NOZZLE_02_SS,
    "0.4": NOZZLE_04_SS,  # Default
    "0.4_ss": NOZZLE_04_SS,
    "0.4_hs": NOZZLE_04_HS,
    "0.6": NOZZLE_06_HS,
    "0.6_hs": NOZZLE_06_HS,
    "0.8": NOZZLE_08_HS,
    "0.8_hs": NOZZLE_08_HS,
}


def get_nozzle_profile(diameter: float, hardened: bool = False) -> Optional[NozzleProfile]:
    """
    Get nozzle profile by diameter and type.

    Args:
        diameter: Nozzle diameter (0.2, 0.4, 0.6, 0.8)
        hardened: Whether to get hardened steel variant

    Returns:
        NozzleProfile or None
    """
    key = f"{diameter:.1f}"
    if hardened and diameter >= 0.4:
        key += "_hs"
    elif diameter == 0.4:
        key += "_ss"

    return A1_NOZZLES.get(key)


def get_recommended_nozzle(
    part_size: str = "medium",
    detail_needed: str = "standard",
    material_abrasive: bool = False,
    speed_priority: bool = False,
) -> Tuple[NozzleProfile, str]:
    """
    Recommend a nozzle based on requirements.

    Args:
        part_size: "small", "medium", "large"
        detail_needed: "fine", "standard", "low"
        material_abrasive: If using CF/GF filaments
        speed_priority: If print speed is more important than detail

    Returns:
        Tuple of (NozzleProfile, explanation)
    """
    # Abrasive materials require hardened steel
    if material_abrasive:
        if detail_needed == "fine":
            return NOZZLE_04_HS, "0.4mm hardened steel for abrasive materials with good detail"
        elif speed_priority or part_size == "large":
            return NOZZLE_06_HS, "0.6mm hardened steel for faster abrasive printing with less clog risk"
        else:
            return NOZZLE_04_HS, "0.4mm hardened steel for balanced abrasive material printing"

    # Fine detail requirements
    if detail_needed == "fine":
        if part_size == "small":
            return NOZZLE_02_SS, "0.2mm for maximum detail on small parts"
        else:
            return NOZZLE_04_SS, "0.4mm with fine layer heights for good detail"

    # Speed priority
    if speed_priority:
        if part_size == "large":
            return NOZZLE_08_HS, "0.8mm for fastest large prints"
        else:
            return NOZZLE_06_HS, "0.6mm for faster printing with acceptable detail"

    # Default: balanced 0.4mm
    return NOZZLE_04_SS, "0.4mm stainless steel - best all-around choice"


def get_layer_height_for_quality(
    nozzle_diameter: float,
    quality: str = "standard"
) -> float:
    """
    Get recommended layer height for a quality level.

    Args:
        nozzle_diameter: Nozzle size in mm
        quality: "fine", "standard", "draft"

    Returns:
        Layer height in mm
    """
    # Rule of thumb: layer height = 25-75% of nozzle diameter
    ratios = {
        "fine": 0.25,
        "standard": 0.50,
        "draft": 0.70,
    }

    ratio = ratios.get(quality, 0.50)
    layer_height = nozzle_diameter * ratio

    # Round to nearest 0.04mm
    return round(layer_height / 0.04) * 0.04
