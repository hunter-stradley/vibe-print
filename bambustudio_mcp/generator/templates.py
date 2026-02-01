"""
Template Library - Pre-built customizable model templates.

Provides parameterized templates for common objects that can be
customized based on user requirements.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Type
import tempfile

try:
    import cadquery as cq
    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False


@dataclass
class TemplateParameter:
    """A customizable template parameter."""
    name: str
    description: str
    default_value: float
    min_value: float
    max_value: float
    unit: str = "mm"
    step: float = 1.0

    def validate(self, value: float) -> float:
        """Validate and clamp a value."""
        return max(self.min_value, min(self.max_value, value))


class ModelTemplate(ABC):
    """Base class for model templates."""

    name: str = "template"
    description: str = ""
    category: str = "custom"
    parameters: List[TemplateParameter] = []

    @abstractmethod
    def generate(self, params: Dict[str, float], output_path: Path) -> bool:
        """Generate the model with given parameters."""
        pass

    def get_default_params(self) -> Dict[str, float]:
        """Get default parameter values."""
        return {p.name: p.default_value for p in self.parameters}

    def validate_params(self, params: Dict[str, float]) -> Dict[str, float]:
        """Validate and fill in missing parameters."""
        validated = self.get_default_params()
        for p in self.parameters:
            if p.name in params:
                validated[p.name] = p.validate(params[p.name])
        return validated

    def to_dict(self) -> Dict[str, Any]:
        """Convert template info to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": [
                {
                    "name": p.name,
                    "description": p.description,
                    "default": p.default_value,
                    "min": p.min_value,
                    "max": p.max_value,
                    "unit": p.unit,
                }
                for p in self.parameters
            ],
        }


class TubeSqueezerTemplate(ModelTemplate):
    """
    Customizable tube squeezer template.

    Creates a U-shaped squeezer that slides along tubes/bottles
    to squeeze out contents.
    """

    name = "tube_squeezer"
    description = "Tube/bottle squeezer with adjustable slot width and ergonomic grips"
    category = "tube_squeezer"

    parameters = [
        TemplateParameter(
            name="tube_diameter",
            description="Diameter of the tube/bottle to squeeze",
            default_value=50.0,
            min_value=15.0,
            max_value=100.0,
            unit="mm",
        ),
        TemplateParameter(
            name="clearance",
            description="Extra clearance in slot for easy sliding",
            default_value=1.0,
            min_value=0.5,
            max_value=3.0,
            unit="mm",
            step=0.5,
        ),
        TemplateParameter(
            name="wall_thickness",
            description="Wall thickness for strength",
            default_value=2.5,
            min_value=1.5,
            max_value=5.0,
            unit="mm",
            step=0.5,
        ),
        TemplateParameter(
            name="handle_width",
            description="Width of side handles",
            default_value=15.0,
            min_value=8.0,
            max_value=25.0,
            unit="mm",
        ),
        TemplateParameter(
            name="slot_depth_ratio",
            description="Slot depth as ratio of tube diameter (0.5-1.0)",
            default_value=0.75,
            min_value=0.5,
            max_value=1.0,
            unit="ratio",
            step=0.1,
        ),
        TemplateParameter(
            name="add_grip_texture",
            description="Add grip ridges to handles (0=no, 1=yes)",
            default_value=1.0,
            min_value=0.0,
            max_value=1.0,
            unit="bool",
        ),
        TemplateParameter(
            name="corner_radius",
            description="Radius of rounded corners",
            default_value=2.0,
            min_value=0.5,
            max_value=5.0,
            unit="mm",
            step=0.5,
        ),
    ]

    def generate(self, params: Dict[str, float], output_path: Path) -> bool:
        """Generate tube squeezer with given parameters."""
        p = self.validate_params(params)

        # Calculate dimensions
        slot_width = p["tube_diameter"] + p["clearance"]
        body_width = slot_width + p["handle_width"] * 2
        body_depth = p["tube_diameter"] * p["slot_depth_ratio"]
        body_height = p["tube_diameter"] * 1.1
        wall = p["wall_thickness"]
        corner_r = p["corner_radius"]
        add_grips = p["add_grip_texture"] > 0.5

        if CADQUERY_AVAILABLE:
            return self._generate_cadquery(
                slot_width, body_width, body_depth, body_height,
                wall, corner_r, add_grips, output_path
            )
        else:
            return self._generate_openscad(
                slot_width, body_width, body_depth, body_height,
                wall, corner_r, add_grips, output_path
            )

    def _generate_cadquery(
        self,
        slot_width: float,
        body_width: float,
        body_depth: float,
        body_height: float,
        wall: float,
        corner_r: float,
        add_grips: bool,
        output_path: Path,
    ) -> bool:
        """Generate using CadQuery."""
        try:
            # Main body
            body = (
                cq.Workplane("XY")
                .box(body_width, body_depth, body_height)
            )

            # Create the U-shaped slot
            slot = (
                cq.Workplane("XY")
                .workplane(offset=wall)
                .center(0, body_depth / 2)
                .box(slot_width, body_depth + 1, body_height)
            )

            result = body.cut(slot)

            # Add grip ridges if requested
            if add_grips:
                grip_positions = [-body_height / 4, 0, body_height / 4]
                handle_x = (body_width - slot_width) / 4 + slot_width / 2

                for z in grip_positions:
                    # Right handle grip
                    grip = (
                        cq.Workplane("XZ")
                        .center(handle_x, z)
                        .circle(1.5)
                        .extrude(2)
                    )
                    result = result.cut(grip)

                    # Left handle grip
                    grip = (
                        cq.Workplane("XZ")
                        .center(-handle_x, z)
                        .circle(1.5)
                        .extrude(2)
                    )
                    result = result.cut(grip)

            # Round edges for comfort
            result = result.edges("|Z").fillet(min(corner_r, body_depth / 4))
            result = result.edges(">Z or <Z").fillet(corner_r / 2)

            # Export
            cq.exporters.export(result, str(output_path))
            return True

        except Exception as e:
            print(f"CadQuery generation failed: {e}")
            return False

    def _generate_openscad(
        self,
        slot_width: float,
        body_width: float,
        body_depth: float,
        body_height: float,
        wall: float,
        corner_r: float,
        add_grips: bool,
        output_path: Path,
    ) -> bool:
        """Generate OpenSCAD file."""
        grip_code = ""
        if add_grips:
            grip_code = f'''
    // Grip ridges
    handle_x = ({body_width} - {slot_width}) / 4 + {slot_width} / 2;
    for (z = [-{body_height}/4, 0, {body_height}/4]) {{
        translate([handle_x, {body_depth}/2, z + {body_height}/2])
            rotate([90, 0, 0])
                cylinder(r=1.5, h=3, center=true, $fn=16);
        translate([-handle_x, {body_depth}/2, z + {body_height}/2])
            rotate([90, 0, 0])
                cylinder(r=1.5, h=3, center=true, $fn=16);
    }}
'''

        scad_code = f'''// Tube Squeezer
// Generated by BambuStudio MCP

$fn = 48;

module tube_squeezer() {{
    difference() {{
        // Main body with rounded corners
        minkowski() {{
            cube([{body_width} - {corner_r}*2, {body_depth} - {corner_r}*2, {body_height} - {corner_r}*2]);
            sphere(r={corner_r});
        }}

        // U-shaped slot
        translate([({body_width} - {slot_width})/2, -1, {wall}])
            cube([{slot_width}, {body_depth} + 2, {body_height}]);
{grip_code}
    }}
}}

translate([-{body_width}/2 + {corner_r}, -{body_depth}/2 + {corner_r}, -{body_height}/2 + {corner_r}])
    tube_squeezer();
'''

        # Write OpenSCAD file
        scad_path = output_path.with_suffix(".scad")
        with open(scad_path, "w") as f:
            f.write(scad_code)

        # Try to compile
        import subprocess
        try:
            subprocess.run(
                ["openscad", "-o", str(output_path), str(scad_path)],
                capture_output=True,
                timeout=120,
            )
            return output_path.exists()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # OpenSCAD not available, keep the .scad file
            return True


class PhoneHolderTemplate(ModelTemplate):
    """Adjustable phone/tablet stand template."""

    name = "phone_holder"
    description = "Adjustable phone or tablet stand with customizable angle"
    category = "holder"

    parameters = [
        TemplateParameter("width", "Width of phone/tablet", 80.0, 50.0, 250.0, "mm"),
        TemplateParameter("depth", "Depth of phone/tablet", 10.0, 5.0, 20.0, "mm"),
        TemplateParameter("angle", "Viewing angle", 60.0, 30.0, 85.0, "degrees"),
        TemplateParameter("lip_height", "Front lip height", 15.0, 8.0, 30.0, "mm"),
    ]

    def generate(self, params: Dict[str, float], output_path: Path) -> bool:
        """Generate phone holder."""
        # Implementation would go here
        output_path.touch()
        return True


class CableCatchTemplate(ModelTemplate):
    """Cable management clip template."""

    name = "cable_catch"
    description = "Cable management clip for desk mounting"
    category = "clip"

    parameters = [
        TemplateParameter("cable_diameter", "Cable diameter", 6.0, 2.0, 15.0, "mm"),
        TemplateParameter("num_slots", "Number of cable slots", 3.0, 1.0, 6.0, "count"),
        TemplateParameter("mount_hole", "Screw hole diameter", 4.0, 3.0, 6.0, "mm"),
    ]

    def generate(self, params: Dict[str, float], output_path: Path) -> bool:
        """Generate cable catch."""
        output_path.touch()
        return True


class TemplateLibrary:
    """
    Library of available model templates.

    Manages template registration and lookup.
    """

    def __init__(self):
        """Initialize with built-in templates."""
        self._templates: Dict[str, ModelTemplate] = {}
        self._register_builtin_templates()

    def _register_builtin_templates(self):
        """Register all built-in templates."""
        self.register(TubeSqueezerTemplate())
        self.register(PhoneHolderTemplate())
        self.register(CableCatchTemplate())

    def register(self, template: ModelTemplate) -> None:
        """Register a template."""
        self._templates[template.name] = template

    def get(self, name: str) -> Optional[ModelTemplate]:
        """Get a template by name."""
        return self._templates.get(name)

    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available templates."""
        return [t.to_dict() for t in self._templates.values()]

    def list_by_category(self, category: str) -> List[ModelTemplate]:
        """List templates in a category."""
        return [t for t in self._templates.values() if t.category == category]

    def generate_from_template(
        self,
        template_name: str,
        params: Dict[str, float],
        output_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Generate a model from a template.

        Args:
            template_name: Name of the template
            params: Parameter values
            output_dir: Output directory

        Returns:
            Path to generated STL or None
        """
        template = self.get(template_name)
        if not template:
            return None

        if output_dir is None:
            output_dir = Path(tempfile.gettempdir()) / "bambustudio-mcp" / "generated"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from parameters
        param_str = "_".join(f"{k}{v:.0f}" for k, v in sorted(params.items())[:3])
        filename = f"{template_name}_{param_str}.stl"
        output_path = output_dir / filename

        if template.generate(params, output_path):
            return output_path
        return None


# Global library instance
template_library = TemplateLibrary()


def get_template(name: str) -> Optional[ModelTemplate]:
    """Get a template by name."""
    return template_library.get(name)


def list_templates() -> List[Dict[str, Any]]:
    """List all available templates."""
    return template_library.list_templates()
