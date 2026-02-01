"""
Material Optimizer - Automatic parameter adjustment based on filament properties.

Adjusts slicing parameters, speeds, temperatures, and design parameters
based on the selected material's properties.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

from vibe_print.materials.filaments import (
    FilamentProfile,
    FilamentType,
    get_filament_profile,
    FILAMENT_PROFILES,
)
from vibe_print.materials.nozzles import (
    NozzleProfile,
    get_nozzle_profile,
    get_recommended_nozzle,
)
from vibe_print.slicer.parameters import SlicingParameters


@dataclass
class OptimizationResult:
    """Result of material-based parameter optimization."""
    original_params: Dict[str, Any]
    optimized_params: Dict[str, Any]
    changes_made: List[Dict[str, Any]]
    warnings: List[str]
    notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original_params,
            "optimized": self.optimized_params,
            "changes": self.changes_made,
            "warnings": self.warnings,
            "notes": self.notes,
        }


class MaterialOptimizer:
    """
    Optimizes print parameters based on material properties.

    Handles material-specific adjustments for:
    - Temperature settings
    - Speed limits
    - Retraction tuning
    - Cooling requirements
    - Structural parameters
    """

    def __init__(self):
        self.changes: List[Dict[str, Any]] = []
        self.warnings: List[str] = []
        self.notes: List[str] = []

    def optimize_for_material(
        self,
        params: Dict[str, Any],
        material: str,
        nozzle_diameter: float = 0.4,
        ambient_temp: float = 22.0,
    ) -> OptimizationResult:
        """
        Optimize parameters for a specific material.

        Args:
            params: Current slicing/design parameters
            material: Filament name or type
            nozzle_diameter: Nozzle size in mm
            ambient_temp: Room temperature (affects some materials)

        Returns:
            OptimizationResult with optimized parameters
        """
        self.changes = []
        self.warnings = []
        self.notes = []

        original = params.copy()
        optimized = params.copy()

        # Get material profile
        material_profile = get_filament_profile(material)
        if not material_profile:
            self.warnings.append(f"Unknown material '{material}', using defaults")
            return OptimizationResult(
                original_params=original,
                optimized_params=optimized,
                changes_made=[],
                warnings=self.warnings,
                notes=self.notes,
            )

        # Get nozzle profile
        nozzle_profile = get_nozzle_profile(nozzle_diameter)

        # Apply optimizations based on material type
        self._optimize_temperatures(optimized, material_profile)
        self._optimize_speeds(optimized, material_profile, nozzle_diameter)
        self._optimize_retraction(optimized, material_profile)
        self._optimize_cooling(optimized, material_profile)
        self._optimize_adhesion(optimized, material_profile)
        self._optimize_structure(optimized, material_profile)

        # Material-specific special handling
        self._apply_material_specifics(optimized, material_profile, ambient_temp)

        return OptimizationResult(
            original_params=original,
            optimized_params=optimized,
            changes_made=self.changes,
            warnings=self.warnings,
            notes=self.notes,
        )

    def _record_change(
        self,
        param: str,
        old_value: Any,
        new_value: Any,
        reason: str
    ) -> None:
        """Record a parameter change."""
        if old_value != new_value:
            self.changes.append({
                "parameter": param,
                "old_value": old_value,
                "new_value": new_value,
                "reason": reason,
            })

    def _optimize_temperatures(
        self,
        params: Dict[str, Any],
        material: FilamentProfile
    ) -> None:
        """Optimize temperature settings."""
        # Nozzle temperature
        if "nozzle_temp" in params:
            old_temp = params["nozzle_temp"]
            if old_temp < material.nozzle_temp.min_temp:
                params["nozzle_temp"] = material.nozzle_temp.optimal
                self._record_change(
                    "nozzle_temp", old_temp, material.nozzle_temp.optimal,
                    f"{material.name} requires at least {material.nozzle_temp.min_temp}°C"
                )
            elif old_temp > material.nozzle_temp.max_temp:
                params["nozzle_temp"] = material.nozzle_temp.optimal
                self._record_change(
                    "nozzle_temp", old_temp, material.nozzle_temp.optimal,
                    f"{material.name} degrades above {material.nozzle_temp.max_temp}°C"
                )
        else:
            params["nozzle_temp"] = material.nozzle_temp.optimal
            self._record_change(
                "nozzle_temp", None, material.nozzle_temp.optimal,
                f"Set optimal temperature for {material.name}"
            )

        # Bed temperature
        if "bed_temp" in params:
            old_temp = params["bed_temp"]
            if old_temp < material.bed_temp.min_temp:
                params["bed_temp"] = material.bed_temp.optimal
                self._record_change(
                    "bed_temp", old_temp, material.bed_temp.optimal,
                    f"{material.name} needs bed at least {material.bed_temp.min_temp}°C"
                )
        else:
            params["bed_temp"] = material.bed_temp.optimal
            self._record_change(
                "bed_temp", None, material.bed_temp.optimal,
                f"Set optimal bed temperature for {material.name}"
            )

    def _optimize_speeds(
        self,
        params: Dict[str, Any],
        material: FilamentProfile,
        nozzle_diameter: float
    ) -> None:
        """Optimize print speeds based on material limits."""
        max_speed = material.max_print_speed

        # Check outer wall speed
        if "outer_wall_speed" in params:
            old_speed = params["outer_wall_speed"]
            # Outer walls should be slower for quality
            optimal_outer = min(old_speed, max_speed * 0.5)
            if old_speed > optimal_outer:
                params["outer_wall_speed"] = int(optimal_outer)
                self._record_change(
                    "outer_wall_speed", old_speed, int(optimal_outer),
                    f"{material.name} prints better at slower outer wall speeds"
                )

        # Check inner wall speed
        if "inner_wall_speed" in params:
            old_speed = params["inner_wall_speed"]
            optimal_inner = min(old_speed, max_speed * 0.7)
            if old_speed > optimal_inner:
                params["inner_wall_speed"] = int(optimal_inner)
                self._record_change(
                    "inner_wall_speed", old_speed, int(optimal_inner),
                    f"Reduced for {material.name} quality"
                )

        # Check infill speed
        if "infill_speed" in params:
            old_speed = params["infill_speed"]
            optimal_infill = min(old_speed, max_speed)
            if old_speed > optimal_infill:
                params["infill_speed"] = int(optimal_infill)
                self._record_change(
                    "infill_speed", old_speed, int(optimal_infill),
                    f"{material.name} max speed is {max_speed}mm/s"
                )

        # Volumetric flow check
        layer_height = params.get("layer_height", 0.2)
        line_width = params.get("line_width", nozzle_diameter * 1.1)
        outer_speed = params.get("outer_wall_speed", 50)

        volumetric = layer_height * line_width * outer_speed
        if volumetric > material.max_volumetric_flow:
            # Need to reduce speed
            safe_speed = material.max_volumetric_flow / (layer_height * line_width)
            old_speed = params.get("outer_wall_speed", outer_speed)
            params["outer_wall_speed"] = int(safe_speed * 0.9)  # 10% safety margin
            self._record_change(
                "outer_wall_speed", old_speed, int(safe_speed * 0.9),
                f"Reduced to stay within {material.max_volumetric_flow}mm³/s flow limit"
            )
            self.notes.append(
                f"Volumetric flow limited to {material.max_volumetric_flow}mm³/s for {material.name}"
            )

    def _optimize_retraction(
        self,
        params: Dict[str, Any],
        material: FilamentProfile
    ) -> None:
        """Optimize retraction settings."""
        # Retraction length
        old_length = params.get("retraction_length", 0.8)
        if abs(old_length - material.retraction_length) > 0.2:
            params["retraction_length"] = material.retraction_length
            self._record_change(
                "retraction_length", old_length, material.retraction_length,
                f"Optimal retraction for {material.name}"
            )

        # Retraction speed
        old_speed = params.get("retraction_speed", 30)
        if abs(old_speed - material.retraction_speed) > 5:
            params["retraction_speed"] = material.retraction_speed
            self._record_change(
                "retraction_speed", old_speed, material.retraction_speed,
                f"Optimal retraction speed for {material.name}"
            )

        # Special handling for flexible materials
        if material.is_flexible:
            # Minimal retraction for TPU
            if params.get("retraction_length", 0) > 1.0:
                params["retraction_length"] = 0.5
                self._record_change(
                    "retraction_length", old_length, 0.5,
                    "Flexible filaments need minimal retraction to prevent jams"
                )
            self.notes.append("TPU: Reduce or disable retraction to prevent jams")

    def _optimize_cooling(
        self,
        params: Dict[str, Any],
        material: FilamentProfile
    ) -> None:
        """Optimize cooling fan settings."""
        # Fan speed
        old_fan = params.get("fan_speed", 100)

        if material.filament_type == FilamentType.PLA:
            # PLA likes cooling
            if old_fan < 80:
                params["fan_speed"] = 100
                self._record_change(
                    "fan_speed", old_fan, 100,
                    "PLA benefits from high cooling"
                )
        elif material.filament_type == FilamentType.PETG:
            # PETG moderate cooling
            if old_fan > 60:
                params["fan_speed"] = 50
                self._record_change(
                    "fan_speed", old_fan, 50,
                    "PETG needs moderate cooling to prevent brittleness"
                )
        elif material.filament_type == FilamentType.PC:
            # PC minimal cooling
            if old_fan > 30:
                params["fan_speed"] = 20
                params["fan_min_layer_time"] = 15
                self._record_change(
                    "fan_speed", old_fan, 20,
                    "PC needs minimal cooling to prevent cracking"
                )
                self.notes.append("PC: Keep fan low to prevent layer separation")
        elif material.filament_type in [FilamentType.TPU, FilamentType.TPE]:
            # TPU moderate cooling
            params["fan_speed"] = min(old_fan, 50)
            if old_fan != params["fan_speed"]:
                self._record_change(
                    "fan_speed", old_fan, params["fan_speed"],
                    "TPU works best with moderate cooling"
                )

    def _optimize_adhesion(
        self,
        params: Dict[str, Any],
        material: FilamentProfile
    ) -> None:
        """Optimize bed adhesion settings."""
        # Brim width for warp-prone materials
        warp_prone = material.filament_type in [FilamentType.PC, FilamentType.ABS]
        old_brim = params.get("brim_width", 5)

        if warp_prone and old_brim < 8:
            params["brim_width"] = 10
            self._record_change(
                "brim_width", old_brim, 10,
                f"{material.name} is prone to warping - larger brim helps"
            )
            self.warnings.append(
                f"{material.name} tends to warp. Use brim, ensure bed is level, "
                "and consider enclosure if available."
            )

        # First layer speed
        old_first = params.get("initial_layer_speed", 30)
        if old_first > 25:
            params["initial_layer_speed"] = 20
            self._record_change(
                "initial_layer_speed", old_first, 20,
                "Slower first layer improves adhesion"
            )

        # First layer height (squish for adhesion)
        old_height = params.get("initial_layer_height", 0.2)
        layer_height = params.get("layer_height", 0.2)
        optimal_first = layer_height * 1.2  # 20% thicker
        if abs(old_height - optimal_first) > 0.02:
            params["initial_layer_height"] = round(optimal_first, 2)
            self._record_change(
                "initial_layer_height", old_height, round(optimal_first, 2),
                "Slightly thicker first layer improves bed adhesion"
            )

    def _optimize_structure(
        self,
        params: Dict[str, Any],
        material: FilamentProfile
    ) -> None:
        """Optimize structural parameters based on material strength."""
        # Flexible materials need different approach
        if material.is_flexible:
            # More walls, less infill for flexible
            old_walls = params.get("wall_loops", 3)
            if old_walls < 3:
                params["wall_loops"] = 3
                self._record_change(
                    "wall_loops", old_walls, 3,
                    "Flexible materials benefit from more walls"
                )

            # Suggest lower infill for more flex
            old_infill = params.get("sparse_infill_density", 20)
            if old_infill > 25:
                self.notes.append(
                    f"Current infill is {old_infill}%. Lower infill (10-20%) "
                    "makes TPU more flexible."
                )

    def _apply_material_specifics(
        self,
        params: Dict[str, Any],
        material: FilamentProfile,
        ambient_temp: float
    ) -> None:
        """Apply material-specific special handling."""
        # AMS compatibility warning
        if not material.ams_compatible:
            self.warnings.append(
                f"{material.name} is NOT compatible with AMS. "
                "Feed filament directly to the extruder."
            )

        # PC on open frame printer warning
        if material.filament_type == FilamentType.PC:
            self.warnings.append(
                "Polycarbonate prints best in an enclosed printer. "
                "A1 is open frame - keep parts small and use draft shield."
            )
            # Add draft shield suggestion
            params["enable_draft_shield"] = True
            self._record_change(
                "enable_draft_shield", False, True,
                "Draft shield helps PC on open frame printers"
            )

        # Cold room adjustments
        if ambient_temp < 18:
            self.notes.append(
                f"Room is cold ({ambient_temp}°C). Consider +5°C bed temp "
                "and using enclosure/draft shield for better adhesion."
            )
            # Bump bed temp slightly
            if "bed_temp" in params:
                params["bed_temp"] = min(params["bed_temp"] + 5,
                                        material.bed_temp.max_temp)

        # PETG stringing mitigation
        if material.filament_type == FilamentType.PETG:
            self.notes.append(
                "PETG tends to string. Tune retraction and consider "
                "lowering temp by 5-10°C if stringing occurs."
            )
            # Enable z-hop for PETG
            if not params.get("z_hop_enabled", False):
                params["z_hop_enabled"] = True
                params["z_hop_height"] = 0.4
                self._record_change(
                    "z_hop_enabled", False, True,
                    "Z-hop helps PETG avoid nozzle hitting printed parts"
                )


def get_material_compatibility(
    design_params: Dict[str, Any],
    materials: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Check compatibility of design parameters with multiple materials.

    Args:
        design_params: Design parameters to check
        materials: List of material names to check against

    Returns:
        Dictionary of material names to compatibility results
    """
    results = {}
    optimizer = MaterialOptimizer()

    for material in materials:
        profile = get_filament_profile(material)
        if not profile:
            results[material] = {"compatible": False, "reason": "Unknown material"}
            continue

        issues = []
        recommendations = []

        # Check wall thickness for flexible materials
        wall = design_params.get("wall_thickness_mm", 2.0)
        if profile.is_flexible and wall < 1.5:
            issues.append("Wall thickness too thin for flexible filament")
            recommendations.append("Increase wall thickness to at least 2mm")

        # Check if heat resistance is needed
        if design_params.get("heat_resistant"):
            if profile.filament_type == FilamentType.PLA:
                issues.append("PLA is not heat resistant")
                recommendations.append("Use PETG or PC instead")

        # Check if waterproof is needed
        if design_params.get("waterproof"):
            if profile.filament_type == FilamentType.PLA:
                issues.append("PLA is not waterproof long-term")
                recommendations.append("Use PETG or ASA instead")

        results[material] = {
            "compatible": len(issues) == 0,
            "material_name": profile.name,
            "issues": issues,
            "recommendations": recommendations,
            "print_notes": profile.special_notes,
        }

    return results
