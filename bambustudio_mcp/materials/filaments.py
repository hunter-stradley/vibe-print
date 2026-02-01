"""
Filament Profiles - Comprehensive settings for common filament types.

Based on research from Bambu Lab Wiki, Prusa Knowledge Base, and community testing.
Optimized for Bambu Lab A1 printer.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple


class FilamentType(str, Enum):
    """Filament material types."""
    PLA = "PLA"
    PETG = "PETG"
    PC = "PC"  # Polycarbonate
    TPU = "TPU"
    ABS = "ABS"
    ASA = "ASA"
    NYLON = "NYLON"
    PLA_CF = "PLA-CF"
    PETG_CF = "PETG-CF"


class FlexRating(str, Enum):
    """How flexible a material is."""
    RIGID = "rigid"           # PLA, PETG, PC
    SEMI_RIGID = "semi_rigid" # Some PETG blends
    SEMI_FLEX = "semi_flex"   # TPU 95A
    FLEXIBLE = "flexible"     # TPU 85A and softer


@dataclass
class TemperatureRange:
    """Temperature range with optimal value."""
    min_temp: int
    optimal: int
    max_temp: int

    def __str__(self) -> str:
        return f"{self.optimal}°C ({self.min_temp}-{self.max_temp}°C)"


@dataclass
class FilamentProfile:
    """
    Complete filament profile with printing parameters.

    All temperatures in °C, speeds in mm/s, distances in mm.
    """
    # Identification
    name: str
    brand: str
    material_type: FilamentType

    # Physical properties
    density: float = 1.24  # g/cm³
    diameter: float = 1.75  # mm

    # Temperature settings
    nozzle_temp: TemperatureRange = field(default_factory=lambda: TemperatureRange(200, 215, 230))
    nozzle_temp_first_layer: Optional[int] = None  # If different from optimal
    bed_temp: TemperatureRange = field(default_factory=lambda: TemperatureRange(45, 55, 65))
    bed_temp_first_layer: Optional[int] = None
    max_hotend_temp: int = 300  # A1 max is 300°C

    # Speed settings
    max_print_speed: float = 200.0  # mm/s
    recommended_speed: float = 100.0  # mm/s for quality
    first_layer_speed: float = 30.0  # mm/s
    max_volumetric_flow: float = 15.0  # mm³/s

    # Retraction settings
    retraction_length: float = 0.8  # mm (direct drive)
    retraction_speed: float = 30.0  # mm/s

    # Cooling
    fan_min_speed: int = 80  # % (0-100)
    fan_max_speed: int = 100
    fan_first_layers: int = 0  # Layers before fan kicks in

    # Mechanical properties (for design decisions)
    flex_rating: FlexRating = FlexRating.RIGID
    impact_resistance: str = "medium"  # low, medium, high
    heat_resistance: int = 60  # °C before deformation
    uv_resistance: bool = False
    water_resistance: bool = False
    food_safe: bool = False

    # Printing notes
    requires_enclosure: bool = False
    requires_hardened_nozzle: bool = False
    ams_compatible: bool = True
    bed_adhesion: str = "good"  # poor, fair, good, excellent
    warping_tendency: str = "low"  # none, low, medium, high
    stringing_tendency: str = "low"  # none, low, medium, high

    # Special considerations
    notes: List[str] = field(default_factory=list)

    # Cost estimate
    cost_per_kg: float = 25.0  # USD

    @property
    def is_flexible(self) -> bool:
        """Check if material is flexible (TPU, TPE)."""
        return self.flex_rating in (FlexRating.FLEXIBLE, FlexRating.SEMI_FLEX)

    @property
    def is_abrasive(self) -> bool:
        """Check if material requires hardened nozzle (CF, GF)."""
        return self.requires_hardened_nozzle

    @property
    def filament_type(self) -> FilamentType:
        """Alias for material_type for API consistency."""
        return self.material_type

    @property
    def special_notes(self) -> str:
        """Get combined notes as a single string."""
        return " | ".join(self.notes) if self.notes else ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "brand": self.brand,
            "material_type": self.material_type.value,
            "temperatures": {
                "nozzle": str(self.nozzle_temp),
                "bed": str(self.bed_temp),
            },
            "speeds": {
                "max": self.max_print_speed,
                "recommended": self.recommended_speed,
                "first_layer": self.first_layer_speed,
            },
            "retraction": {
                "length": self.retraction_length,
                "speed": self.retraction_speed,
            },
            "properties": {
                "flex_rating": self.flex_rating.value,
                "impact_resistance": self.impact_resistance,
                "heat_resistance_c": self.heat_resistance,
            },
            "requirements": {
                "enclosure": self.requires_enclosure,
                "hardened_nozzle": self.requires_hardened_nozzle,
                "ams_compatible": self.ams_compatible,
            },
            "notes": self.notes,
        }

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)

    def get_slicer_params(self) -> Dict[str, Any]:
        """Get parameters for slicer integration."""
        return {
            "nozzle_temperature": self.nozzle_temp.optimal,
            "nozzle_temperature_initial_layer": self.nozzle_temp_first_layer or self.nozzle_temp.optimal,
            "bed_temperature": self.bed_temp.optimal,
            "bed_temperature_initial_layer": self.bed_temp_first_layer or self.bed_temp.optimal + 5,
            "fan_min_speed": self.fan_min_speed,
            "fan_max_speed": self.fan_max_speed,
            "retraction_length": self.retraction_length,
            "retraction_speed": self.retraction_speed,
        }

    def get_design_recommendations(self) -> List[str]:
        """Get design recommendations based on material properties."""
        recs = []

        if self.flex_rating == FlexRating.FLEXIBLE or self.flex_rating == FlexRating.SEMI_FLEX:
            recs.append("Reduce infill to 15-25% for flexibility")
            recs.append("Use 2-3 wall loops for TPU")
            recs.append("Avoid thin walls < 1.2mm")

        if self.warping_tendency in ("medium", "high"):
            recs.append("Use brim (8mm+) for bed adhesion")
            recs.append("Avoid large flat surfaces or add mouse ears")

        if self.stringing_tendency in ("medium", "high"):
            recs.append("Minimize travel moves between parts")
            recs.append("Print one object at a time if possible")

        if self.impact_resistance == "low":
            recs.append("Increase wall loops to 4+ for strength")
            recs.append("Use 30%+ infill for load-bearing parts")

        if self.material_type == FilamentType.TPU:
            recs.append("Disable dynamic flow calibration")
            recs.append("Use direct extruder feed (no AMS)")

        if self.requires_enclosure:
            recs.append("⚠️ This material works best with an enclosed printer")
            recs.append("Consider smaller parts to reduce warping")

        return recs


# =============================================================================
# Pre-defined Filament Profiles for User's Materials
# =============================================================================

BAMBU_PLA = FilamentProfile(
    name="Bambu Basic PLA",
    brand="Bambu Lab",
    material_type=FilamentType.PLA,
    density=1.24,

    nozzle_temp=TemperatureRange(190, 220, 230),
    bed_temp=TemperatureRange(45, 55, 65),

    max_print_speed=300.0,  # A1 can go fast with PLA
    recommended_speed=150.0,
    first_layer_speed=30.0,
    max_volumetric_flow=21.0,  # Bambu PLA flows well

    retraction_length=0.8,
    retraction_speed=30.0,

    fan_min_speed=80,
    fan_max_speed=100,
    fan_first_layers=1,

    flex_rating=FlexRating.RIGID,
    impact_resistance="medium",
    heat_resistance=55,
    uv_resistance=False,
    water_resistance=False,
    food_safe=False,  # Check specific colors

    requires_enclosure=False,
    requires_hardened_nozzle=False,
    ams_compatible=True,
    bed_adhesion="excellent",
    warping_tendency="none",
    stringing_tendency="low",

    notes=[
        "Great all-around filament for most prints",
        "Easy to print, minimal tuning needed",
        "Good for functional prototypes and decorative items",
        "Can use Cool Plate or Engineering Plate",
    ],
    cost_per_kg=25.0,
)

BAMBU_PETG_TRANSLUCENT = FilamentProfile(
    name="Bambu PETG Translucent",
    brand="Bambu Lab",
    material_type=FilamentType.PETG,
    density=1.27,

    nozzle_temp=TemperatureRange(230, 245, 260),
    bed_temp=TemperatureRange(70, 80, 90),
    bed_temp_first_layer=85,

    max_print_speed=200.0,
    recommended_speed=80.0,  # Slower for quality with PETG
    first_layer_speed=25.0,
    max_volumetric_flow=12.0,

    retraction_length=0.6,  # Less retraction for PETG
    retraction_speed=25.0,

    fan_min_speed=50,
    fan_max_speed=80,  # Less cooling than PLA
    fan_first_layers=3,

    flex_rating=FlexRating.RIGID,
    impact_resistance="high",
    heat_resistance=75,
    uv_resistance=True,
    water_resistance=True,
    food_safe=False,

    requires_enclosure=False,
    requires_hardened_nozzle=False,
    ams_compatible=True,
    bed_adhesion="good",
    warping_tendency="low",
    stringing_tendency="high",  # PETG strings!

    notes=[
        "Higher impact resistance than PLA",
        "Prone to stringing - tune retraction carefully",
        "Translucent effect works well with internal lighting",
        "Use Engineering Plate with glue stick for best adhesion",
        "Let cool completely before removing from bed",
    ],
    cost_per_kg=30.0,
)

PRUSA_PC_BLEND = FilamentProfile(
    name="Prusament PC Blend",
    brand="Prusa",
    material_type=FilamentType.PC,
    density=1.20,

    nozzle_temp=TemperatureRange(265, 275, 285),
    nozzle_temp_first_layer=280,
    bed_temp=TemperatureRange(100, 110, 115),
    bed_temp_first_layer=115,

    max_print_speed=150.0,
    recommended_speed=60.0,  # Slow for PC
    first_layer_speed=20.0,
    max_volumetric_flow=8.0,

    retraction_length=0.6,
    retraction_speed=25.0,

    fan_min_speed=0,
    fan_max_speed=30,  # Very low cooling
    fan_first_layers=5,

    flex_rating=FlexRating.RIGID,
    impact_resistance="high",
    heat_resistance=110,
    uv_resistance=True,
    water_resistance=True,
    food_safe=False,

    requires_enclosure=False,  # PC Blend works on open frame
    requires_hardened_nozzle=False,
    ams_compatible=True,
    bed_adhesion="fair",  # Needs glue
    warping_tendency="medium",
    stringing_tendency="low",

    notes=[
        "⚠️ A1 can print PC Blend but with limitations",
        "Use textured PEI plate with glue stick",
        "Smaller parts work better on open-frame printers",
        "Keep ambient temp > 18°C to avoid thermal runaway",
        "May have some warping on larger parts (>10cm)",
        "Add 4mm+ brim for parts larger than 5cm",
        "Excellent strength and heat resistance",
    ],
    cost_per_kg=45.0,
)

GENERIC_PETG = FilamentProfile(
    name="Generic PETG",
    brand="Generic",
    material_type=FilamentType.PETG,
    density=1.27,

    nozzle_temp=TemperatureRange(220, 240, 260),
    bed_temp=TemperatureRange(70, 80, 90),

    max_print_speed=150.0,
    recommended_speed=60.0,
    first_layer_speed=20.0,
    max_volumetric_flow=10.0,

    retraction_length=0.8,
    retraction_speed=25.0,

    fan_min_speed=30,
    fan_max_speed=70,
    fan_first_layers=3,

    flex_rating=FlexRating.RIGID,
    impact_resistance="high",
    heat_resistance=70,
    uv_resistance=True,
    water_resistance=True,
    food_safe=False,

    requires_enclosure=False,
    requires_hardened_nozzle=False,
    ams_compatible=True,
    bed_adhesion="good",
    warping_tendency="low",
    stringing_tendency="high",

    notes=[
        "Third-party PETG may need temperature tuning",
        "Start at 235°C and adjust in 5°C increments",
        "Significant stringing is normal - use post-processing",
        "Print temperature tower to find optimal settings",
    ],
    cost_per_kg=25.0,
)

GENERIC_TPU_95A = FilamentProfile(
    name="Generic TPU 95A",
    brand="Generic",
    material_type=FilamentType.TPU,
    density=1.21,

    nozzle_temp=TemperatureRange(210, 230, 240),
    bed_temp=TemperatureRange(30, 45, 60),

    max_print_speed=40.0,  # TPU is SLOW
    recommended_speed=25.0,
    first_layer_speed=15.0,
    max_volumetric_flow=3.2,  # Very low for generic TPU

    retraction_length=0.5,  # Minimal retraction
    retraction_speed=20.0,  # Slow retraction

    fan_min_speed=50,
    fan_max_speed=80,
    fan_first_layers=2,

    flex_rating=FlexRating.SEMI_FLEX,
    impact_resistance="high",  # Absorbs impact
    heat_resistance=80,
    uv_resistance=True,
    water_resistance=True,
    food_safe=False,

    requires_enclosure=False,
    requires_hardened_nozzle=False,
    ams_compatible=False,  # TPU 95A doesn't work with AMS
    bed_adhesion="good",
    warping_tendency="none",
    stringing_tendency="high",

    notes=[
        "⚠️ Do NOT use with AMS - feed directly",
        "Disable dynamic flow calibration in Bambu Studio",
        "Print one object at a time to minimize travel",
        "Use low retraction (0.5mm) and slow speed (20mm/s)",
        "Max volumetric flow is 3.2 mm³/s for generic TPU",
        "Avoid excessive travel moves",
        "95A is semi-flexible, good for phone cases, grips",
    ],
    cost_per_kg=35.0,
)


# =============================================================================
# Profile Registry
# =============================================================================

FILAMENT_PROFILES: Dict[str, FilamentProfile] = {
    "bambu_pla": BAMBU_PLA,
    "bambu_basic_pla": BAMBU_PLA,
    "bambu_petg": BAMBU_PETG_TRANSLUCENT,
    "bambu_petg_translucent": BAMBU_PETG_TRANSLUCENT,
    "prusa_pc": PRUSA_PC_BLEND,
    "prusa_pc_blend": PRUSA_PC_BLEND,
    "prusament_pc": PRUSA_PC_BLEND,
    "generic_petg": GENERIC_PETG,
    "petg": GENERIC_PETG,
    "generic_tpu": GENERIC_TPU_95A,
    "tpu_95a": GENERIC_TPU_95A,
    "tpu": GENERIC_TPU_95A,
}


def get_filament_profile(name: str) -> Optional[FilamentProfile]:
    """Get a filament profile by name."""
    key = name.lower().replace(" ", "_").replace("-", "_")
    return FILAMENT_PROFILES.get(key)


def list_filament_profiles() -> List[Dict[str, Any]]:
    """List all available filament profiles."""
    seen = set()
    profiles = []
    for profile in FILAMENT_PROFILES.values():
        if profile.name not in seen:
            seen.add(profile.name)
            profiles.append({
                "name": profile.name,
                "brand": profile.brand,
                "type": profile.material_type.value,
                "use_cases": _get_use_cases(profile),
            })
    return profiles


def _get_use_cases(profile: FilamentProfile) -> List[str]:
    """Get typical use cases for a filament."""
    uses = []

    if profile.material_type == FilamentType.PLA:
        uses = ["Prototypes", "Decorative items", "Low-stress parts", "General purpose"]
    elif profile.material_type == FilamentType.PETG:
        uses = ["Functional parts", "Outdoor use", "Water-resistant items", "Food containers (check food-safe)"]
    elif profile.material_type == FilamentType.PC:
        uses = ["High-strength parts", "Heat-resistant items", "Mechanical components", "Protective gear"]
    elif profile.material_type == FilamentType.TPU:
        uses = ["Phone cases", "Gaskets/seals", "Flexible hinges", "Shoe insoles", "Grips"]

    return uses


def suggest_filament(
    needs_strength: bool = False,
    needs_flexibility: bool = False,
    needs_heat_resistance: bool = False,
    needs_outdoor: bool = False,
    needs_water_resistance: bool = False,
) -> List[str]:
    """Suggest filaments based on requirements."""
    suggestions = []

    if needs_flexibility:
        suggestions.append("generic_tpu")
        return suggestions  # TPU is the only flexible option

    if needs_heat_resistance and needs_strength:
        suggestions.append("prusa_pc")
    elif needs_outdoor and needs_strength:
        suggestions.append("bambu_petg")
        suggestions.append("prusa_pc")
    elif needs_water_resistance:
        suggestions.append("bambu_petg")
        suggestions.append("generic_petg")
    elif needs_strength:
        suggestions.append("bambu_petg")
        suggestions.append("prusa_pc")
    else:
        suggestions.append("bambu_pla")  # Default choice

    return suggestions
