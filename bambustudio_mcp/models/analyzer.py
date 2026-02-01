"""
Model Analysis Module - STL/3MF parsing and dimensional analysis.

Analyzes 3D models to extract dimensions, mesh quality metrics, and
identify key features like slots, holes, and surfaces for scaling decisions.
"""

import json
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
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
class BoundingBox:
    """3D bounding box dimensions."""
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float
    max_z: float

    @property
    def width(self) -> float:
        """X dimension."""
        return self.max_x - self.min_x

    @property
    def depth(self) -> float:
        """Y dimension."""
        return self.max_y - self.min_y

    @property
    def height(self) -> float:
        """Z dimension."""
        return self.max_z - self.min_z

    @property
    def dimensions(self) -> Tuple[float, float, float]:
        """Return (width, depth, height) tuple."""
        return (self.width, self.depth, self.height)

    @property
    def center(self) -> Tuple[float, float, float]:
        """Return center point."""
        return (
            (self.min_x + self.max_x) / 2,
            (self.min_y + self.max_y) / 2,
            (self.min_z + self.max_z) / 2,
        )

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "width_mm": round(self.width, 2),
            "depth_mm": round(self.depth, 2),
            "height_mm": round(self.height, 2),
            "min": {"x": round(self.min_x, 2), "y": round(self.min_y, 2), "z": round(self.min_z, 2)},
            "max": {"x": round(self.max_x, 2), "y": round(self.max_y, 2), "z": round(self.max_z, 2)},
        }


@dataclass
class MeshQuality:
    """Mesh quality metrics."""
    triangle_count: int
    vertex_count: int
    is_watertight: bool
    has_degenerate_faces: bool
    volume_mm3: Optional[float] = None
    surface_area_mm2: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "triangle_count": self.triangle_count,
            "vertex_count": self.vertex_count,
            "is_watertight": self.is_watertight,
            "has_degenerate_faces": self.has_degenerate_faces,
            "volume_mm3": round(self.volume_mm3, 2) if self.volume_mm3 else None,
            "surface_area_mm2": round(self.surface_area_mm2, 2) if self.surface_area_mm2 else None,
        }


@dataclass
class SlotFeature:
    """Detected slot/opening feature for tube squeezers."""
    width_mm: float
    height_mm: float
    depth_mm: float
    position: Tuple[float, float, float]
    orientation: str  # "horizontal", "vertical"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "width_mm": round(self.width_mm, 2),
            "height_mm": round(self.height_mm, 2),
            "depth_mm": round(self.depth_mm, 2),
            "position": [round(p, 2) for p in self.position],
            "orientation": self.orientation,
        }


@dataclass
class ModelInfo:
    """Complete model analysis result."""
    file_path: Path
    file_format: str
    bounding_box: BoundingBox
    mesh_quality: MeshQuality
    detected_slots: List[SlotFeature] = field(default_factory=list)
    estimated_print_time_mins: Optional[float] = None
    estimated_filament_grams: Optional[float] = None
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": str(self.file_path),
            "file_format": self.file_format,
            "bounding_box": self.bounding_box.to_dict(),
            "mesh_quality": self.mesh_quality.to_dict(),
            "detected_slots": [s.to_dict() for s in self.detected_slots],
            "estimated_print_time_mins": self.estimated_print_time_mins,
            "estimated_filament_grams": self.estimated_filament_grams,
            "recommendations": self.recommendations,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class ModelAnalyzer:
    """
    Analyzes 3D models (STL, 3MF) to extract dimensions, quality metrics,
    and detect features relevant to scaling decisions.
    """

    SUPPORTED_FORMATS = {".stl", ".3mf", ".obj"}

    def __init__(self):
        """Initialize the analyzer."""
        self._check_dependencies()

    def _check_dependencies(self) -> None:
        """Verify required libraries are available."""
        if trimesh is None and stl_mesh is None:
            raise ImportError(
                "Either 'trimesh' or 'numpy-stl' is required. "
                "Install with: pip install trimesh numpy-stl --break-system-packages"
            )

    def analyze(self, file_path: Path | str) -> ModelInfo:
        """
        Analyze a 3D model file.

        Args:
            file_path: Path to STL, 3MF, or OBJ file

        Returns:
            ModelInfo with complete analysis results
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Model file not found: {file_path}")

        suffix = file_path.suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {suffix}. Supported: {self.SUPPORTED_FORMATS}")

        if suffix == ".3mf":
            return self._analyze_3mf(file_path)
        else:
            return self._analyze_mesh(file_path)

    def _analyze_mesh(self, file_path: Path) -> ModelInfo:
        """Analyze STL or OBJ mesh file."""
        if trimesh is not None:
            return self._analyze_with_trimesh(file_path)
        else:
            return self._analyze_with_numpy_stl(file_path)

    def _analyze_with_trimesh(self, file_path: Path) -> ModelInfo:
        """Analyze using trimesh library (preferred)."""
        mesh = trimesh.load(file_path)

        # Handle scene vs single mesh
        if isinstance(mesh, trimesh.Scene):
            mesh = mesh.dump(concatenate=True)

        # Bounding box
        bounds = mesh.bounds
        bbox = BoundingBox(
            min_x=float(bounds[0][0]),
            max_x=float(bounds[1][0]),
            min_y=float(bounds[0][1]),
            max_y=float(bounds[1][1]),
            min_z=float(bounds[0][2]),
            max_z=float(bounds[1][2]),
        )

        # Mesh quality
        quality = MeshQuality(
            triangle_count=len(mesh.faces),
            vertex_count=len(mesh.vertices),
            is_watertight=mesh.is_watertight,
            has_degenerate_faces=bool(mesh.degenerate_faces.any()) if hasattr(mesh, 'degenerate_faces') else False,
            volume_mm3=float(mesh.volume) if mesh.is_watertight else None,
            surface_area_mm2=float(mesh.area),
        )

        # Detect slot features (for tube squeezers)
        slots = self._detect_slots_trimesh(mesh)

        # Generate recommendations
        recommendations = self._generate_recommendations(bbox, quality, slots)

        return ModelInfo(
            file_path=file_path,
            file_format=file_path.suffix.lower(),
            bounding_box=bbox,
            mesh_quality=quality,
            detected_slots=slots,
            recommendations=recommendations,
        )

    def _analyze_with_numpy_stl(self, file_path: Path) -> ModelInfo:
        """Analyze using numpy-stl library (fallback)."""
        mesh = stl_mesh.Mesh.from_file(str(file_path))

        # Bounding box from vertices
        min_coords = mesh.vectors.min(axis=(0, 1))
        max_coords = mesh.vectors.max(axis=(0, 1))

        bbox = BoundingBox(
            min_x=float(min_coords[0]),
            max_x=float(max_coords[0]),
            min_y=float(min_coords[1]),
            max_y=float(max_coords[1]),
            min_z=float(min_coords[2]),
            max_z=float(max_coords[2]),
        )

        # Basic mesh quality (limited without trimesh)
        quality = MeshQuality(
            triangle_count=len(mesh.vectors),
            vertex_count=len(mesh.vectors) * 3,  # Approximate
            is_watertight=False,  # Can't determine with numpy-stl
            has_degenerate_faces=False,
            volume_mm3=float(mesh.get_mass_properties()[0]) if hasattr(mesh, 'get_mass_properties') else None,
        )

        recommendations = self._generate_recommendations(bbox, quality, [])

        return ModelInfo(
            file_path=file_path,
            file_format=file_path.suffix.lower(),
            bounding_box=bbox,
            mesh_quality=quality,
            detected_slots=[],
            recommendations=recommendations,
        )

    def _analyze_3mf(self, file_path: Path) -> ModelInfo:
        """Analyze 3MF file (ZIP archive with model and metadata)."""
        with zipfile.ZipFile(file_path, 'r') as zf:
            # Find the model file
            model_file = None
            for name in zf.namelist():
                if name.endswith('.model') or '3D/3dmodel.model' in name:
                    model_file = name
                    break

            if model_file is None:
                raise ValueError("No model found in 3MF file")

            # Extract to temp and analyze
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                zf.extract(model_file, tmpdir)
                model_path = Path(tmpdir) / model_file

                # Parse 3MF XML for metadata
                tree = ET.parse(model_path)
                root = tree.getroot()

                # Try to extract vertices for bounding box
                ns = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
                vertices = []
                for vertex in root.findall('.//m:vertex', ns):
                    x = float(vertex.get('x', 0))
                    y = float(vertex.get('y', 0))
                    z = float(vertex.get('z', 0))
                    vertices.append([x, y, z])

                if vertices:
                    vertices = np.array(vertices)
                    bbox = BoundingBox(
                        min_x=float(vertices[:, 0].min()),
                        max_x=float(vertices[:, 0].max()),
                        min_y=float(vertices[:, 1].min()),
                        max_y=float(vertices[:, 1].max()),
                        min_z=float(vertices[:, 2].min()),
                        max_z=float(vertices[:, 2].max()),
                    )
                else:
                    # Fallback - try loading with trimesh
                    if trimesh is not None:
                        return self._analyze_with_trimesh(file_path)
                    bbox = BoundingBox(0, 0, 0, 0, 0, 0)

                # Count triangles
                triangles = root.findall('.//m:triangle', ns)
                triangle_count = len(triangles)

                quality = MeshQuality(
                    triangle_count=triangle_count,
                    vertex_count=len(vertices),
                    is_watertight=True,  # 3MF typically watertight
                    has_degenerate_faces=False,
                )

                recommendations = self._generate_recommendations(bbox, quality, [])

                return ModelInfo(
                    file_path=file_path,
                    file_format=".3mf",
                    bounding_box=bbox,
                    mesh_quality=quality,
                    detected_slots=[],
                    recommendations=recommendations,
                )

    def _detect_slots_trimesh(self, mesh) -> List[SlotFeature]:
        """
        Detect slot/opening features in mesh (for tube squeezers).

        Uses cross-section analysis to find rectangular openings.
        """
        slots = []

        try:
            # Take cross-sections at different heights
            z_min, z_max = mesh.bounds[0][2], mesh.bounds[1][2]
            height = z_max - z_min

            for z_ratio in [0.25, 0.5, 0.75]:
                z = z_min + height * z_ratio
                try:
                    section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
                    if section is not None:
                        # Analyze the 2D section for rectangular openings
                        path = section.to_planar()[0]
                        if hasattr(path, 'bounds'):
                            bounds = path.bounds
                            width = bounds[1][0] - bounds[0][0]
                            depth = bounds[1][1] - bounds[0][1]

                            # Heuristic: slot is likely if there's a significant opening
                            if width > 5 and depth > 2:  # mm thresholds
                                slots.append(SlotFeature(
                                    width_mm=float(width),
                                    height_mm=float(height * 0.5),  # Estimate
                                    depth_mm=float(depth),
                                    position=(0, 0, z),
                                    orientation="horizontal" if width > depth else "vertical",
                                ))
                except Exception:
                    continue
        except Exception:
            pass

        return slots

    def _generate_recommendations(
        self,
        bbox: BoundingBox,
        quality: MeshQuality,
        slots: List[SlotFeature],
    ) -> List[str]:
        """Generate printing recommendations based on analysis."""
        recommendations = []

        # Size-based recommendations
        max_dim = max(bbox.dimensions)
        if max_dim > 200:
            recommendations.append(
                f"Model is large ({max_dim:.1f}mm). Consider splitting or scaling down."
            )
        if max_dim < 10:
            recommendations.append(
                f"Model is small ({max_dim:.1f}mm). Consider scaling up for better detail."
            )

        # Quality recommendations
        if not quality.is_watertight:
            recommendations.append(
                "Mesh is not watertight. May need repair before slicing."
            )
        if quality.has_degenerate_faces:
            recommendations.append(
                "Mesh has degenerate faces. Run mesh repair for best results."
            )
        if quality.triangle_count < 1000:
            recommendations.append(
                "Low triangle count may result in faceted surfaces."
            )

        # Slot-based recommendations (for tube squeezers)
        if slots:
            slot = slots[0]
            recommendations.append(
                f"Detected slot opening: {slot.width_mm:.1f}mm wide. "
                f"Scale based on target tube/bottle diameter."
            )

        return recommendations

    def get_scale_factor_for_slot(
        self,
        model_info: ModelInfo,
        target_width_mm: float,
    ) -> float:
        """
        Calculate scale factor to fit a target tube/bottle width.

        For tube squeezers, the slot width should match the tube diameter.

        Args:
            model_info: Analyzed model information
            target_width_mm: Target slot width (tube diameter) in mm

        Returns:
            Scale factor (e.g., 1.5 means 150% scale)
        """
        if model_info.detected_slots:
            current_width = model_info.detected_slots[0].width_mm
        else:
            # Fallback: use model width
            current_width = model_info.bounding_box.width

        if current_width <= 0:
            raise ValueError("Cannot determine current slot width")

        return target_width_mm / current_width
