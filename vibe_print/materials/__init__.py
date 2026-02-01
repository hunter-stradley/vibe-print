"""
Materials Module - Filament profiles and material-aware settings.

Provides comprehensive filament profiles for common materials
with automatic parameter adjustment based on material properties.
"""

from vibe_print.materials.filaments import (
    FilamentProfile,
    FilamentType,
    get_filament_profile,
    list_filament_profiles,
    # Primary profiles
    BASIC_PLA,
    PETG_TRANSLUCENT,
    PC_BLEND,
    GENERIC_PETG,
    GENERIC_TPU_95A,
    # Backwards compatibility aliases
    BAMBU_PLA,
    BAMBU_PETG_TRANSLUCENT,
    PRUSA_PC_BLEND,
)
from vibe_print.materials.nozzles import (
    NozzleProfile,
    NozzleType,
    get_nozzle_profile,
    get_recommended_nozzle,
    SUPPORTED_NOZZLES,
    A1_NOZZLES,  # Backwards compatibility
)

__all__ = [
    "FilamentProfile",
    "FilamentType",
    "get_filament_profile",
    "list_filament_profiles",
    # Primary profiles
    "BASIC_PLA",
    "PETG_TRANSLUCENT",
    "PC_BLEND",
    "GENERIC_PETG",
    "GENERIC_TPU_95A",
    # Backwards compatibility aliases
    "BAMBU_PLA",
    "BAMBU_PETG_TRANSLUCENT",
    "PRUSA_PC_BLEND",
    # Nozzle profiles
    "NozzleProfile",
    "NozzleType",
    "get_nozzle_profile",
    "get_recommended_nozzle",
    "SUPPORTED_NOZZLES",
    "A1_NOZZLES",  # Backwards compatibility
]
