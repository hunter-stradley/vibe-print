"""
Materials Module - Filament profiles and material-aware settings.

Provides comprehensive filament profiles for common materials
with automatic parameter adjustment based on material properties.
"""

from bambustudio_mcp.materials.filaments import (
    FilamentProfile,
    FilamentType,
    get_filament_profile,
    list_filament_profiles,
    BAMBU_PLA,
    BAMBU_PETG_TRANSLUCENT,
    PRUSA_PC_BLEND,
    GENERIC_PETG,
    GENERIC_TPU_95A,
)
from bambustudio_mcp.materials.nozzles import (
    NozzleProfile,
    NozzleType,
    get_nozzle_profile,
    get_recommended_nozzle,
    A1_NOZZLES,
)

__all__ = [
    "FilamentProfile",
    "FilamentType",
    "get_filament_profile",
    "list_filament_profiles",
    "BAMBU_PLA",
    "BAMBU_PETG_TRANSLUCENT",
    "PRUSA_PC_BLEND",
    "GENERIC_PETG",
    "GENERIC_TPU_95A",
    "NozzleProfile",
    "NozzleType",
    "get_nozzle_profile",
    "get_recommended_nozzle",
    "A1_NOZZLES",
]
