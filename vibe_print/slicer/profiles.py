"""
Profile Management - Load and save slicing profiles.

Manages JSON profile files for machine, process, and filament settings.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List

from vibe_print.slicer.parameters import SlicingParameters, ParameterPreset, BUILTIN_PRESETS


@dataclass
class ProfileInfo:
    """Information about a slicing profile."""
    name: str
    path: Path
    profile_type: str  # "machine", "process", "filament"
    description: Optional[str] = None
    compatible_printers: List[str] = None

    def __post_init__(self):
        if self.compatible_printers is None:
            self.compatible_printers = []


class ProfileManager:
    """
    Manages slicing profiles for BambuStudio.

    Handles loading, saving, and organizing profile files.
    """

    DEFAULT_PROFILES_DIR = Path.home() / ".bambustudio-mcp" / "profiles"

    def __init__(self, profiles_dir: Optional[Path] = None):
        """
        Initialize profile manager.

        Args:
            profiles_dir: Directory for profile storage
        """
        self.profiles_dir = profiles_dir or self.DEFAULT_PROFILES_DIR
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (self.profiles_dir / "machine").mkdir(exist_ok=True)
        (self.profiles_dir / "process").mkdir(exist_ok=True)
        (self.profiles_dir / "filament").mkdir(exist_ok=True)
        (self.profiles_dir / "presets").mkdir(exist_ok=True)

    def list_profiles(self, profile_type: Optional[str] = None) -> List[ProfileInfo]:
        """
        List available profiles.

        Args:
            profile_type: Filter by type (machine, process, filament)

        Returns:
            List of ProfileInfo objects
        """
        profiles = []

        search_dirs = []
        if profile_type:
            search_dirs.append(self.profiles_dir / profile_type)
        else:
            search_dirs = [
                self.profiles_dir / "machine",
                self.profiles_dir / "process",
                self.profiles_dir / "filament",
            ]

        for dir_path in search_dirs:
            if not dir_path.exists():
                continue

            for json_file in dir_path.glob("*.json"):
                try:
                    with open(json_file) as f:
                        data = json.load(f)

                    profiles.append(ProfileInfo(
                        name=data.get("name", json_file.stem),
                        path=json_file,
                        profile_type=dir_path.name,
                        description=data.get("description"),
                        compatible_printers=data.get("compatible_printers", []),
                    ))
                except Exception:
                    continue

        return profiles

    def load_profile(self, profile_path: Path | str) -> Dict[str, Any]:
        """Load a profile from JSON file."""
        profile_path = Path(profile_path)
        with open(profile_path) as f:
            return json.load(f)

    def save_profile(
        self,
        profile_data: Dict[str, Any],
        name: str,
        profile_type: str,
    ) -> Path:
        """
        Save a profile to JSON file.

        Args:
            profile_data: Profile configuration dictionary
            name: Profile name
            profile_type: Type (machine, process, filament)

        Returns:
            Path to saved file
        """
        output_dir = self.profiles_dir / profile_type
        output_dir.mkdir(exist_ok=True)

        output_path = output_dir / f"{name}.json"

        with open(output_path, "w") as f:
            json.dump(profile_data, f, indent=2)

        return output_path

    def get_preset(self, name: str) -> ParameterPreset:
        """
        Get a parameter preset by name.

        First checks built-in presets, then user-saved presets.
        """
        # Check built-in
        if name in BUILTIN_PRESETS:
            return BUILTIN_PRESETS[name]

        # Check user presets
        preset_path = self.profiles_dir / "presets" / f"{name}.json"
        if preset_path.exists():
            with open(preset_path) as f:
                data = json.load(f)
            return ParameterPreset.from_dict(data)

        raise ValueError(f"Preset not found: {name}")

    def save_preset(self, preset: ParameterPreset) -> Path:
        """Save a parameter preset."""
        output_path = self.profiles_dir / "presets" / f"{preset.name}.json"

        with open(output_path, "w") as f:
            json.dump(preset.to_dict(), f, indent=2)

        return output_path

    def list_presets(self) -> List[str]:
        """List all available presets (built-in and user)."""
        presets = list(BUILTIN_PRESETS.keys())

        preset_dir = self.profiles_dir / "presets"
        if preset_dir.exists():
            for json_file in preset_dir.glob("*.json"):
                name = json_file.stem
                if name not in presets:
                    presets.append(name)

        return sorted(presets)

    def create_machine_profile_a1(self) -> Dict[str, Any]:
        """Create default machine profile for Bambu A1."""
        return {
            "name": "Bambu Lab A1",
            "type": "machine",
            "description": "Default settings for Bambu Lab A1 printer",
            "compatible_printers": ["A1", "A1 mini"],
            "settings": {
                "printer_model": "Bambu Lab A1",
                "nozzle_diameter": 0.4,
                "printable_area": [256, 256],  # A1 build volume
                "printable_height": 256,
                "max_print_speed": 500,
                "max_acceleration": 20000,
                "gcode_flavor": "bambu",
                "has_heated_bed": True,
                "has_chamber_heating": False,
            },
        }

    def create_filament_profile_pla(self) -> Dict[str, Any]:
        """Create default PLA filament profile."""
        return {
            "name": "Generic PLA",
            "type": "filament",
            "description": "Standard PLA settings",
            "settings": {
                "filament_type": "PLA",
                "filament_density": 1.24,
                "filament_cost": 25.0,
                "nozzle_temperature": 220,
                "nozzle_temperature_initial": 220,
                "bed_temperature": 60,
                "bed_temperature_initial": 60,
                "fan_min_speed": 80,
                "fan_max_speed": 100,
                "fan_always_on": True,
            },
        }

    def create_process_profile_standard(self) -> Dict[str, Any]:
        """Create standard process profile."""
        return {
            "name": "Standard Quality",
            "type": "process",
            "description": "Balanced quality and speed",
            "settings": {
                "layer_height": 0.20,
                "initial_layer_height": 0.20,
                "wall_loops": 2,
                "top_shell_layers": 4,
                "bottom_shell_layers": 4,
                "sparse_infill_density": 15,
                "sparse_infill_pattern": "gyroid",
                "outer_wall_speed": 60,
                "inner_wall_speed": 80,
                "infill_speed": 150,
                "support_type": "none",
                "brim_width": 0,
            },
        }

    def initialize_default_profiles(self) -> None:
        """Create default profiles if they don't exist."""
        # Machine profile
        machine_path = self.profiles_dir / "machine" / "bambu_a1.json"
        if not machine_path.exists():
            self.save_profile(
                self.create_machine_profile_a1(),
                "bambu_a1",
                "machine",
            )

        # Filament profile
        filament_path = self.profiles_dir / "filament" / "generic_pla.json"
        if not filament_path.exists():
            self.save_profile(
                self.create_filament_profile_pla(),
                "generic_pla",
                "filament",
            )

        # Process profile
        process_path = self.profiles_dir / "process" / "standard.json"
        if not process_path.exists():
            self.save_profile(
                self.create_process_profile_standard(),
                "standard",
                "process",
            )
