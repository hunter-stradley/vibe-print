"""
BambuStudio CLI Integration - Command-line slicing and export.

Wraps the BambuStudio CLI for automated slicing operations.
"""

import asyncio
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from bambustudio_mcp.config import config
from bambustudio_mcp.slicer.parameters import SlicingParameters, BedType


@dataclass
class SliceResult:
    """Result of a slicing operation."""
    success: bool
    input_model: Path
    output_3mf: Optional[Path] = None
    output_gcode: Optional[Path] = None
    error_message: Optional[str] = None

    # Estimated values from slicer
    estimated_time_seconds: Optional[float] = None
    estimated_filament_mm: Optional[float] = None
    estimated_filament_grams: Optional[float] = None

    # Metadata
    layer_count: Optional[int] = None
    parameters_used: Optional[SlicingParameters] = None
    cli_output: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "input_model": str(self.input_model),
            "output_3mf": str(self.output_3mf) if self.output_3mf else None,
            "output_gcode": str(self.output_gcode) if self.output_gcode else None,
            "error_message": self.error_message,
            "estimated_time_minutes": round(self.estimated_time_seconds / 60, 1) if self.estimated_time_seconds else None,
            "estimated_filament_grams": round(self.estimated_filament_grams, 1) if self.estimated_filament_grams else None,
            "layer_count": self.layer_count,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class BambuStudioCLI:
    """
    BambuStudio command-line interface wrapper.

    Provides methods to slice models and export to 3MF/G-code.
    """

    def __init__(
        self,
        executable_path: Optional[Path] = None,
        profiles_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        """
        Initialize BambuStudio CLI wrapper.

        Args:
            executable_path: Path to BambuStudio executable
            profiles_dir: Directory containing profile JSON files
            output_dir: Directory for sliced output files
        """
        self.executable = executable_path or config.bambustudio.executable_path
        self.profiles_dir = profiles_dir or config.bambustudio.profiles_dir
        self.output_dir = output_dir or config.bambustudio.temp_dir / "sliced"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> Tuple[bool, str]:
        """
        Check if BambuStudio CLI is available.

        Returns:
            Tuple of (available, message)
        """
        if not self.executable.exists():
            return False, f"BambuStudio not found at {self.executable}"

        try:
            result = subprocess.run(
                [str(self.executable), "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 or "Usage:" in result.stdout:
                return True, "BambuStudio CLI is available"
            return False, f"BambuStudio returned error: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "BambuStudio CLI timed out"
        except Exception as e:
            return False, f"Error checking BambuStudio: {e}"

    async def slice_model(
        self,
        model_path: Path | str,
        parameters: Optional[SlicingParameters] = None,
        output_name: Optional[str] = None,
        export_gcode: bool = True,
        export_3mf: bool = True,
        auto_orient: bool = True,
        auto_arrange: bool = True,
    ) -> SliceResult:
        """
        Slice a 3D model using BambuStudio CLI.

        Args:
            model_path: Path to STL, OBJ, or 3MF model
            parameters: Slicing parameters (uses defaults if None)
            output_name: Base name for output files
            export_gcode: Export standalone G-code file
            export_3mf: Export 3MF with embedded G-code
            auto_orient: Automatically orient model
            auto_arrange: Automatically arrange on build plate

        Returns:
            SliceResult with output paths and estimates
        """
        model_path = Path(model_path)
        if not model_path.exists():
            return SliceResult(
                success=False,
                input_model=model_path,
                error_message=f"Model file not found: {model_path}",
            )

        # Check CLI availability
        available, message = self.is_available()
        if not available:
            return SliceResult(
                success=False,
                input_model=model_path,
                error_message=message,
            )

        # Use default parameters if not provided
        if parameters is None:
            parameters = SlicingParameters()

        # Generate output paths
        if output_name is None:
            output_name = model_path.stem

        output_3mf = self.output_dir / f"{output_name}.3mf" if export_3mf else None
        output_gcode = self.output_dir / f"{output_name}.gcode" if export_gcode else None

        # Build CLI command
        cmd = [str(self.executable)]

        if auto_orient:
            cmd.append("--orient")

        if auto_arrange:
            cmd.append("--arrange")
            cmd.append("1")

        # Add bed type
        cmd.extend([f"--curr-bed-type={parameters.bed_type.value}"])

        # Add slicing flag (required to generate G-code)
        cmd.extend(["--slice", "0"])

        # Output
        if output_3mf:
            cmd.extend(["--export-3mf", str(output_3mf)])

        # Input model (must be last)
        cmd.append(str(model_path))

        # Run slicer
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=str(self.output_dir),
            )

            cli_output = result.stdout + result.stderr

            if result.returncode != 0:
                return SliceResult(
                    success=False,
                    input_model=model_path,
                    error_message=f"Slicing failed: {cli_output}",
                    cli_output=cli_output,
                )

            # Parse output for estimates
            estimates = self._parse_slicer_output(cli_output)

            # Verify output files exist
            if output_3mf and not output_3mf.exists():
                return SliceResult(
                    success=False,
                    input_model=model_path,
                    error_message="Slicing completed but 3MF file not found",
                    cli_output=cli_output,
                )

            return SliceResult(
                success=True,
                input_model=model_path,
                output_3mf=output_3mf,
                output_gcode=output_gcode if output_gcode and output_gcode.exists() else None,
                estimated_time_seconds=estimates.get("time_seconds"),
                estimated_filament_mm=estimates.get("filament_mm"),
                estimated_filament_grams=estimates.get("filament_grams"),
                layer_count=estimates.get("layer_count"),
                parameters_used=parameters,
                cli_output=cli_output,
            )

        except subprocess.TimeoutExpired:
            return SliceResult(
                success=False,
                input_model=model_path,
                error_message="Slicing timed out after 5 minutes",
            )
        except Exception as e:
            return SliceResult(
                success=False,
                input_model=model_path,
                error_message=f"Slicing error: {e}",
            )

    def _parse_slicer_output(self, output: str) -> Dict[str, Any]:
        """Parse slicer output for estimates and metadata."""
        estimates = {}

        # Common patterns in slicer output
        import re

        # Time patterns
        time_match = re.search(r"(?:estimated|total)\s*(?:print\s*)?time[:\s]+(\d+)[:\s](\d+)", output, re.I)
        if time_match:
            hours, minutes = int(time_match.group(1)), int(time_match.group(2))
            estimates["time_seconds"] = hours * 3600 + minutes * 60

        # Filament patterns
        filament_match = re.search(r"filament[:\s]+(\d+\.?\d*)\s*(?:mm|m)", output, re.I)
        if filament_match:
            estimates["filament_mm"] = float(filament_match.group(1))

        grams_match = re.search(r"(\d+\.?\d*)\s*g(?:rams)?", output, re.I)
        if grams_match:
            estimates["filament_grams"] = float(grams_match.group(1))

        # Layer count
        layer_match = re.search(r"(\d+)\s*layers?", output, re.I)
        if layer_match:
            estimates["layer_count"] = int(layer_match.group(1))

        return estimates

    async def validate_model(self, model_path: Path | str) -> Tuple[bool, List[str]]:
        """
        Validate a model file can be loaded and sliced.

        Args:
            model_path: Path to model file

        Returns:
            Tuple of (valid, list of issues)
        """
        model_path = Path(model_path)
        issues = []

        if not model_path.exists():
            return False, [f"File not found: {model_path}"]

        suffix = model_path.suffix.lower()
        if suffix not in {".stl", ".obj", ".3mf", ".step", ".stp"}:
            issues.append(f"Unsupported file format: {suffix}")

        # Check file size
        size_mb = model_path.stat().st_size / (1024 * 1024)
        if size_mb > 100:
            issues.append(f"Large file ({size_mb:.1f}MB) may be slow to process")

        # Try a quick load test with BambuStudio
        available, message = self.is_available()
        if not available:
            issues.append(f"Cannot validate with BambuStudio: {message}")

        return len(issues) == 0, issues

    def get_available_profiles(self) -> List[Dict[str, str]]:
        """List available slicing profiles from profiles directory."""
        profiles = []

        if self.profiles_dir and self.profiles_dir.exists():
            for json_file in self.profiles_dir.glob("*.json"):
                try:
                    with open(json_file) as f:
                        data = json.load(f)
                        profiles.append({
                            "name": json_file.stem,
                            "path": str(json_file),
                            "type": data.get("type", "unknown"),
                        })
                except Exception:
                    continue

        return profiles


# Convenience function for quick slicing
async def quick_slice(
    model_path: Path | str,
    output_dir: Optional[Path] = None,
    quality: str = "standard",
) -> SliceResult:
    """
    Quick slice a model with standard settings.

    Args:
        model_path: Path to model file
        output_dir: Output directory (uses temp if None)
        quality: Quality preset (draft, standard, quality)

    Returns:
        SliceResult
    """
    from bambustudio_mcp.slicer.parameters import BUILTIN_PRESETS

    cli = BambuStudioCLI(output_dir=output_dir)

    # Get preset parameters
    preset_name = quality if quality in BUILTIN_PRESETS else "tube_squeezer_standard"
    params = BUILTIN_PRESETS[preset_name].parameters

    return await cli.slice_model(model_path, parameters=params)
