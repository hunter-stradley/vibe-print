"""
Model Scaling Engine - Dimension-based scaling with structural adjustments.

Scales 3D models based on target dimensions while optionally adjusting
wall thickness and other structural parameters for larger prints.
"""

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
import numpy as np

try:
    from stl import mesh as stl_mesh
except ImportError:
    stl_mesh = None

try:
    import trimesh
except ImportError:
    trimesh = None


@dataclass
class ScaleResult:
    """Result of a scaling operation."""
    original_path: Path
    scaled_path: Path
    scale_factor: float
    uniform_scale: bool
    original_dimensions: Tuple[float, float, float]
    scaled_dimensions: Tuple[float, float, float]
    wall_thickness_adjusted: bool = False
    adjustments_made: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "original_path": str(self.original_path),
            "scaled_path": str(self.scaled_path),
            "scale_factor": round(self.scale_factor, 4),
            "scale_percentage": round(self.scale_factor * 100, 1),
            "uniform_scale": self.uniform_scale,
            "original_dimensions_mm": {
                "width": round(self.original_dimensions[0], 2),
                "depth": round(self.original_dimensions[1], 2),
                "height": round(self.original_dimensions[2], 2),
            },
            "scaled_dimensions_mm": {
                "width": round(self.scaled_dimensions[0], 2),
                "depth": round(self.scaled_dimensions[1], 2),
                "height": round(self.scaled_dimensions[2], 2),
            },
            "wall_thickness_adjusted": self.wall_thickness_adjusted,
            "adjustments_made": self.adjustments_made,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class ModelScaler:
    """
    Scales 3D models with intelligent adjustments for structural integrity.

    Supports:
    - Uniform scaling (same factor for all axes)
    - Non-uniform scaling (different factors per axis)
    - Target dimension scaling (scale to fit specific size)
    - Slot-width scaling (for tube squeezers - scale based on slot opening)
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize the scaler.

        Args:
            output_dir: Directory for scaled output files. Uses temp dir if None.
        """
        self.output_dir = output_dir or Path(tempfile.gettempdir()) / "vibe-print" / "scaled"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._check_dependencies()

    def _check_dependencies(self) -> None:
        """Verify required libraries are available."""
        if trimesh is None and stl_mesh is None:
            raise ImportError(
                "Either 'trimesh' or 'numpy-stl' required for scaling. "
                "Install with: pip install trimesh numpy-stl --break-system-packages"
            )

    def scale_uniform(
        self,
        input_path: Path | str,
        scale_factor: float,
        output_name: Optional[str] = None,
    ) -> ScaleResult:
        """
        Apply uniform scaling to a model.

        Args:
            input_path: Path to input model (STL, OBJ, 3MF)
            scale_factor: Scale multiplier (e.g., 1.5 = 150%)
            output_name: Optional output filename

        Returns:
            ScaleResult with paths and dimensions
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Generate output path
        if output_name is None:
            output_name = f"{input_path.stem}_scaled_{scale_factor:.2f}{input_path.suffix}"
        output_path = self.output_dir / output_name

        # Load, scale, and save
        if trimesh is not None:
            return self._scale_with_trimesh(
                input_path, output_path, scale_factor, scale_factor, scale_factor
            )
        else:
            return self._scale_with_numpy_stl(
                input_path, output_path, scale_factor, scale_factor, scale_factor
            )

    def scale_to_dimension(
        self,
        input_path: Path | str,
        target_width: Optional[float] = None,
        target_depth: Optional[float] = None,
        target_height: Optional[float] = None,
        maintain_aspect_ratio: bool = True,
        output_name: Optional[str] = None,
    ) -> ScaleResult:
        """
        Scale model to fit target dimensions.

        Args:
            input_path: Path to input model
            target_width: Target X dimension in mm
            target_depth: Target Y dimension in mm
            target_height: Target Z dimension in mm
            maintain_aspect_ratio: If True, scale uniformly based on primary target
            output_name: Optional output filename

        Returns:
            ScaleResult with paths and dimensions
        """
        input_path = Path(input_path)

        # Get current dimensions
        current_dims = self._get_dimensions(input_path)

        # Calculate scale factors
        scale_x = target_width / current_dims[0] if target_width else 1.0
        scale_y = target_depth / current_dims[1] if target_depth else 1.0
        scale_z = target_height / current_dims[2] if target_height else 1.0

        if maintain_aspect_ratio:
            # Use the smallest specified scale to maintain proportions
            specified_scales = []
            if target_width:
                specified_scales.append(scale_x)
            if target_depth:
                specified_scales.append(scale_y)
            if target_height:
                specified_scales.append(scale_z)

            if specified_scales:
                uniform_scale = min(specified_scales)
                scale_x = scale_y = scale_z = uniform_scale

        # Generate output path
        if output_name is None:
            output_name = f"{input_path.stem}_scaled{input_path.suffix}"
        output_path = self.output_dir / output_name

        if trimesh is not None:
            return self._scale_with_trimesh(input_path, output_path, scale_x, scale_y, scale_z)
        else:
            return self._scale_with_numpy_stl(input_path, output_path, scale_x, scale_y, scale_z)

    def scale_for_tube_squeezer(
        self,
        input_path: Path | str,
        original_tube_diameter_mm: float,
        target_tube_diameter_mm: float,
        adjust_wall_thickness: bool = True,
        wall_thickness_factor: float = 1.2,
        output_name: Optional[str] = None,
    ) -> ScaleResult:
        """
        Scale a tube squeezer model for a different tube/bottle size.

        This is the key function for the toothpaste-to-lotion-bottle use case.

        Args:
            input_path: Path to original tube squeezer STL
            original_tube_diameter_mm: Diameter the original was designed for
            target_tube_diameter_mm: Target tube/bottle diameter
            adjust_wall_thickness: If True, slightly increase walls for larger sizes
            wall_thickness_factor: Additional scaling for structural integrity
            output_name: Optional output filename

        Returns:
            ScaleResult with scaling details

        Example:
            # Scale toothpaste squeezer (25mm tube) for lotion bottle (65mm)
            result = scaler.scale_for_tube_squeezer(
                input_path="toothpaste_squeezer.stl",
                original_tube_diameter_mm=25.0,
                target_tube_diameter_mm=65.0,
            )
        """
        input_path = Path(input_path)

        # Calculate base scale factor
        base_scale = target_tube_diameter_mm / original_tube_diameter_mm

        # For larger scales, optionally increase wall thickness
        adjustments = []
        effective_scale = base_scale

        if adjust_wall_thickness and base_scale > 1.5:
            # Larger prints may need thicker walls for structural integrity
            # This is a heuristic - actual wall thickness adjustment would
            # require mesh modification, not just scaling
            thickness_note = (
                f"Recommend increasing wall thickness in slicer by "
                f"{(wall_thickness_factor - 1) * 100:.0f}% for structural integrity"
            )
            adjustments.append(thickness_note)

        # Generate output path
        if output_name is None:
            output_name = (
                f"{input_path.stem}_"
                f"{target_tube_diameter_mm:.0f}mm"
                f"{input_path.suffix}"
            )
        output_path = self.output_dir / output_name

        # Perform uniform scaling
        if trimesh is not None:
            result = self._scale_with_trimesh(
                input_path, output_path, effective_scale, effective_scale, effective_scale
            )
        else:
            result = self._scale_with_numpy_stl(
                input_path, output_path, effective_scale, effective_scale, effective_scale
            )

        # Add tube squeezer specific info
        result.adjustments_made.extend(adjustments)
        result.adjustments_made.append(
            f"Scaled from {original_tube_diameter_mm}mm to {target_tube_diameter_mm}mm tube diameter"
        )

        return result

    def _get_dimensions(self, file_path: Path) -> Tuple[float, float, float]:
        """Get model dimensions (width, depth, height)."""
        if trimesh is not None:
            mesh = trimesh.load(file_path)
            if isinstance(mesh, trimesh.Scene):
                mesh = mesh.dump(concatenate=True)
            bounds = mesh.bounds
            return (
                float(bounds[1][0] - bounds[0][0]),
                float(bounds[1][1] - bounds[0][1]),
                float(bounds[1][2] - bounds[0][2]),
            )
        else:
            mesh = stl_mesh.Mesh.from_file(str(file_path))
            min_coords = mesh.vectors.min(axis=(0, 1))
            max_coords = mesh.vectors.max(axis=(0, 1))
            return (
                float(max_coords[0] - min_coords[0]),
                float(max_coords[1] - min_coords[1]),
                float(max_coords[2] - min_coords[2]),
            )

    def _scale_with_trimesh(
        self,
        input_path: Path,
        output_path: Path,
        scale_x: float,
        scale_y: float,
        scale_z: float,
    ) -> ScaleResult:
        """Scale using trimesh library."""
        mesh = trimesh.load(input_path)
        if isinstance(mesh, trimesh.Scene):
            mesh = mesh.dump(concatenate=True)

        # Get original dimensions
        orig_bounds = mesh.bounds
        orig_dims = (
            float(orig_bounds[1][0] - orig_bounds[0][0]),
            float(orig_bounds[1][1] - orig_bounds[0][1]),
            float(orig_bounds[1][2] - orig_bounds[0][2]),
        )

        # Apply scaling
        scale_matrix = np.diag([scale_x, scale_y, scale_z, 1.0])
        mesh.apply_transform(scale_matrix)

        # Get new dimensions
        new_bounds = mesh.bounds
        new_dims = (
            float(new_bounds[1][0] - new_bounds[0][0]),
            float(new_bounds[1][1] - new_bounds[0][1]),
            float(new_bounds[1][2] - new_bounds[0][2]),
        )

        # Save
        mesh.export(output_path)

        uniform = scale_x == scale_y == scale_z

        return ScaleResult(
            original_path=input_path,
            scaled_path=output_path,
            scale_factor=scale_x if uniform else (scale_x + scale_y + scale_z) / 3,
            uniform_scale=uniform,
            original_dimensions=orig_dims,
            scaled_dimensions=new_dims,
            adjustments_made=[],
        )

    def _scale_with_numpy_stl(
        self,
        input_path: Path,
        output_path: Path,
        scale_x: float,
        scale_y: float,
        scale_z: float,
    ) -> ScaleResult:
        """Scale using numpy-stl library."""
        mesh = stl_mesh.Mesh.from_file(str(input_path))

        # Get original dimensions
        min_coords = mesh.vectors.min(axis=(0, 1))
        max_coords = mesh.vectors.max(axis=(0, 1))
        orig_dims = (
            float(max_coords[0] - min_coords[0]),
            float(max_coords[1] - min_coords[1]),
            float(max_coords[2] - min_coords[2]),
        )

        # Apply scaling to all vertices
        mesh.vectors[:, :, 0] *= scale_x
        mesh.vectors[:, :, 1] *= scale_y
        mesh.vectors[:, :, 2] *= scale_z

        # Update normals
        mesh.update_normals()

        # Get new dimensions
        min_coords = mesh.vectors.min(axis=(0, 1))
        max_coords = mesh.vectors.max(axis=(0, 1))
        new_dims = (
            float(max_coords[0] - min_coords[0]),
            float(max_coords[1] - min_coords[1]),
            float(max_coords[2] - min_coords[2]),
        )

        # Save
        mesh.save(str(output_path))

        uniform = scale_x == scale_y == scale_z

        return ScaleResult(
            original_path=input_path,
            scaled_path=output_path,
            scale_factor=scale_x if uniform else (scale_x + scale_y + scale_z) / 3,
            uniform_scale=uniform,
            original_dimensions=orig_dims,
            scaled_dimensions=new_dims,
            adjustments_made=[],
        )


def calculate_tube_squeezer_scale(
    original_slot_width_mm: float,
    target_tube_diameter_mm: float,
    clearance_mm: float = 1.0,
) -> float:
    """
    Calculate the optimal scale factor for a tube squeezer.

    The slot should be slightly larger than the tube for easy sliding.

    Args:
        original_slot_width_mm: Current slot width in the model
        target_tube_diameter_mm: Diameter of target tube/bottle
        clearance_mm: Additional clearance for easy operation

    Returns:
        Scale factor to apply
    """
    target_slot_width = target_tube_diameter_mm + clearance_mm
    return target_slot_width / original_slot_width_mm
