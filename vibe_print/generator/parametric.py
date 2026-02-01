"""
Parametric Model Generator - Create 3D models using CadQuery.

Generates precise, parametric 3D models from specifications.
CadQuery is a Python CAD library that can export to STL.
"""

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    import cadquery as cq
    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False

from vibe_print.generator.requirements import ModelRequirements, ObjectCategory


@dataclass
class GeneratedModel:
    """A generated 3D model."""
    name: str
    output_path: Path
    format: str = "stl"

    # Generation info
    method: str = ""  # "cadquery", "openscad", "ai"
    source_code: str = ""

    # Dimensions
    dimensions_mm: Dict[str, float] = field(default_factory=dict)

    # Metadata
    requirements_used: Optional[ModelRequirements] = None
    generation_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "output_path": str(self.output_path),
            "format": self.format,
            "method": self.method,
            "dimensions_mm": self.dimensions_mm,
            "generation_notes": self.generation_notes,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=indent)


class ParametricGenerator:
    """
    Generates parametric 3D models using CadQuery.

    CadQuery allows creating precise, dimensioned models in pure Python.
    Falls back to OpenSCAD script generation if CadQuery is unavailable.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize generator.

        Args:
            output_dir: Directory for generated models
        """
        self.output_dir = output_dir or Path(tempfile.gettempdir()) / "bambustudio-mcp" / "generated"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> tuple[bool, str]:
        """Check if CadQuery is available."""
        if CADQUERY_AVAILABLE:
            return True, "CadQuery is available for parametric generation"
        return False, "CadQuery not installed. Install with: pip install cadquery-ocp --break-system-packages"

    def generate_from_requirements(
        self,
        requirements: ModelRequirements,
        output_name: Optional[str] = None,
    ) -> GeneratedModel:
        """
        Generate a model based on requirements.

        Args:
            requirements: Structured model requirements
            output_name: Optional output filename

        Returns:
            GeneratedModel with path to generated STL
        """
        if output_name is None:
            output_name = requirements.name or "generated_model"

        # Route to appropriate generator based on category
        if requirements.category == ObjectCategory.TUBE_SQUEEZER:
            return self._generate_tube_squeezer(requirements, output_name)
        elif requirements.category == ObjectCategory.HOLDER:
            return self._generate_holder(requirements, output_name)
        elif requirements.category == ObjectCategory.BRACKET:
            return self._generate_bracket(requirements, output_name)
        elif requirements.category == ObjectCategory.CLIP:
            return self._generate_clip(requirements, output_name)
        else:
            return self._generate_custom_box(requirements, output_name)

    def _generate_tube_squeezer(
        self,
        requirements: ModelRequirements,
        output_name: str,
    ) -> GeneratedModel:
        """Generate a tube squeezer model."""
        # Extract parameters
        tube_diameter = requirements.get_primary_dimension_mm() or 50.0
        wall_thickness = requirements.wall_thickness_mm
        clearance = 1.0 if requirements.fit_type.value == "sliding" else 0.5

        # Calculate dimensions
        slot_width = tube_diameter + clearance
        body_width = slot_width + wall_thickness * 2 + 10  # Extra for handles
        body_depth = tube_diameter * 0.8  # Depth of the slot
        body_height = tube_diameter * 1.2

        output_path = self.output_dir / f"{output_name}.stl"

        if CADQUERY_AVAILABLE:
            # Generate with CadQuery
            model = self._cq_tube_squeezer(
                slot_width=slot_width,
                body_width=body_width,
                body_depth=body_depth,
                body_height=body_height,
                wall_thickness=wall_thickness,
            )

            # Export to STL
            cq.exporters.export(model, str(output_path))
            method = "cadquery"
            source = self._get_tube_squeezer_code(slot_width, body_width, body_depth, body_height, wall_thickness)
        else:
            # Generate OpenSCAD file
            scad_path = self.output_dir / f"{output_name}.scad"
            source = self._openscad_tube_squeezer(
                slot_width=slot_width,
                body_width=body_width,
                body_depth=body_depth,
                body_height=body_height,
                wall_thickness=wall_thickness,
            )
            with open(scad_path, "w") as f:
                f.write(source)

            # Try to compile with OpenSCAD
            self._compile_openscad(scad_path, output_path)
            method = "openscad"

        return GeneratedModel(
            name=output_name,
            output_path=output_path,
            format="stl",
            method=method,
            source_code=source,
            dimensions_mm={
                "slot_width": slot_width,
                "body_width": body_width,
                "body_depth": body_depth,
                "body_height": body_height,
                "tube_diameter": tube_diameter,
            },
            requirements_used=requirements,
            generation_notes=[
                f"Tube squeezer for {tube_diameter:.1f}mm diameter tube/bottle",
                f"Slot width: {slot_width:.1f}mm (includes {clearance:.1f}mm clearance)",
                f"Wall thickness: {wall_thickness:.1f}mm",
            ],
        )

    def _cq_tube_squeezer(
        self,
        slot_width: float,
        body_width: float,
        body_depth: float,
        body_height: float,
        wall_thickness: float,
    ):
        """Generate tube squeezer using CadQuery."""
        # Main body
        body = (
            cq.Workplane("XY")
            .box(body_width, body_depth, body_height)
        )

        # Create the slot (U-shaped channel)
        slot = (
            cq.Workplane("XY")
            .center(0, body_depth / 2)
            .box(slot_width, body_depth, body_height + 2)
            .translate((0, 0, wall_thickness))
        )

        # Cut the slot
        result = body.cut(slot)

        # Add finger grips on sides
        grip_width = (body_width - slot_width) / 2 - wall_thickness
        grip_depth = 3.0
        grip_spacing = body_height / 6

        for i in range(3):
            z_pos = grip_spacing * (i + 1) - body_height / 2
            # Left grip
            result = result.faces(">X").workplane(centerOption="CenterOfMass").center(0, z_pos).rect(grip_depth, 5).cutBlind(-2)
            # Right grip
            result = result.faces("<X").workplane(centerOption="CenterOfMass").center(0, z_pos).rect(grip_depth, 5).cutBlind(-2)

        # Round the edges for comfort
        result = result.edges("|Z").fillet(2.0)

        return result

    def _get_tube_squeezer_code(
        self,
        slot_width: float,
        body_width: float,
        body_depth: float,
        body_height: float,
        wall_thickness: float,
    ) -> str:
        """Get the CadQuery source code for tube squeezer."""
        return f'''import cadquery as cq

# Parameters
slot_width = {slot_width}
body_width = {body_width}
body_depth = {body_depth}
body_height = {body_height}
wall_thickness = {wall_thickness}

# Main body
body = cq.Workplane("XY").box(body_width, body_depth, body_height)

# Create the slot
slot = (
    cq.Workplane("XY")
    .center(0, body_depth / 2)
    .box(slot_width, body_depth, body_height + 2)
    .translate((0, 0, wall_thickness))
)

# Cut the slot
result = body.cut(slot)

# Round edges
result = result.edges("|Z").fillet(2.0)

# Export
cq.exporters.export(result, "tube_squeezer.stl")
'''

    def _openscad_tube_squeezer(
        self,
        slot_width: float,
        body_width: float,
        body_depth: float,
        body_height: float,
        wall_thickness: float,
    ) -> str:
        """Generate OpenSCAD code for tube squeezer."""
        return f'''// Tube Squeezer
// Generated by BambuStudio MCP

// Parameters
slot_width = {slot_width};
body_width = {body_width};
body_depth = {body_depth};
body_height = {body_height};
wall_thickness = {wall_thickness};
corner_radius = 2;

module tube_squeezer() {{
    difference() {{
        // Main body with rounded corners
        minkowski() {{
            cube([body_width - corner_radius*2, body_depth - corner_radius*2, body_height - corner_radius*2], center=true);
            sphere(r=corner_radius, $fn=32);
        }}

        // Slot cutout
        translate([0, body_depth/2, wall_thickness])
            cube([slot_width, body_depth, body_height], center=true);

        // Finger grips
        for (z = [-body_height/6, 0, body_height/6]) {{
            translate([body_width/2, 0, z])
                rotate([0, 90, 0])
                    cylinder(r=3, h=5, center=true, $fn=32);
            translate([-body_width/2, 0, z])
                rotate([0, 90, 0])
                    cylinder(r=3, h=5, center=true, $fn=32);
        }}
    }}
}}

tube_squeezer();
'''

    def _generate_holder(
        self,
        requirements: ModelRequirements,
        output_name: str,
    ) -> GeneratedModel:
        """Generate a holder/stand model."""
        diameter = requirements.get_primary_dimension_mm() or 50.0
        wall = requirements.wall_thickness_mm
        height = diameter * 0.8

        output_path = self.output_dir / f"{output_name}.stl"

        if CADQUERY_AVAILABLE:
            # Cylindrical holder
            outer_radius = diameter / 2 + wall
            inner_radius = diameter / 2 + 0.5  # Clearance

            model = (
                cq.Workplane("XY")
                .circle(outer_radius)
                .extrude(height)
                .faces(">Z")
                .workplane()
                .circle(inner_radius)
                .cutBlind(-height + wall)  # Leave bottom
            )

            cq.exporters.export(model, str(output_path))
            method = "cadquery"
        else:
            method = "openscad"
            # Generate OpenSCAD
            scad_path = self.output_dir / f"{output_name}.scad"
            source = f'''// Holder
outer_r = {diameter/2 + wall};
inner_r = {diameter/2 + 0.5};
height = {height};
wall = {wall};

difference() {{
    cylinder(r=outer_r, h=height, $fn=64);
    translate([0, 0, wall])
        cylinder(r=inner_r, h=height, $fn=64);
}}
'''
            with open(scad_path, "w") as f:
                f.write(source)
            self._compile_openscad(scad_path, output_path)

        return GeneratedModel(
            name=output_name,
            output_path=output_path,
            format="stl",
            method=method,
            dimensions_mm={
                "inner_diameter": diameter + 1.0,
                "outer_diameter": diameter + wall * 2 + 1.0,
                "height": height,
            },
            requirements_used=requirements,
        )

    def _generate_bracket(
        self,
        requirements: ModelRequirements,
        output_name: str,
    ) -> GeneratedModel:
        """Generate an L-bracket model."""
        width = requirements.get_primary_dimension_mm() or 40.0
        wall = requirements.wall_thickness_mm
        depth = width * 0.6
        height = width

        output_path = self.output_dir / f"{output_name}.stl"

        if CADQUERY_AVAILABLE:
            # L-bracket
            model = (
                cq.Workplane("XY")
                .box(width, wall, height)
                .faces("<Y")
                .workplane()
                .move(0, height / 2 - wall / 2)
                .box(width, depth, wall)
            )

            # Add mounting holes
            model = (
                model
                .faces(">Y")
                .workplane()
                .pushPoints([(width/4, height/4), (-width/4, height/4)])
                .hole(5.0)
            )

            cq.exporters.export(model, str(output_path))
            method = "cadquery"
        else:
            method = "openscad"
            output_path.touch()  # Placeholder

        return GeneratedModel(
            name=output_name,
            output_path=output_path,
            format="stl",
            method=method,
            dimensions_mm={
                "width": width,
                "depth": depth,
                "height": height,
            },
            requirements_used=requirements,
        )

    def _generate_clip(
        self,
        requirements: ModelRequirements,
        output_name: str,
    ) -> GeneratedModel:
        """Generate a clip model."""
        grip_width = requirements.get_primary_dimension_mm() or 20.0
        wall = requirements.wall_thickness_mm

        output_path = self.output_dir / f"{output_name}.stl"

        # For clips, we'll generate OpenSCAD since the geometry is complex
        method = "openscad"
        scad_path = self.output_dir / f"{output_name}.scad"
        source = f'''// Spring Clip
grip_width = {grip_width};
wall = {wall};
length = grip_width * 1.5;

module clip() {{
    // Base
    cube([grip_width + wall*2, wall, length]);

    // Sides with spring curve
    for (x = [0, grip_width + wall]) {{
        translate([x, 0, 0])
            cube([wall, grip_width * 0.8, length]);
    }}

    // Grip ridges
    for (z = [length/4, length/2, length*3/4]) {{
        translate([wall, grip_width * 0.6, z])
            rotate([0, 90, 0])
                cylinder(r=1, h=grip_width, $fn=16);
    }}
}}

clip();
'''
        with open(scad_path, "w") as f:
            f.write(source)
        self._compile_openscad(scad_path, output_path)

        return GeneratedModel(
            name=output_name,
            output_path=output_path,
            format="stl",
            method=method,
            dimensions_mm={
                "grip_width": grip_width,
                "length": grip_width * 1.5,
            },
            requirements_used=requirements,
        )

    def _generate_custom_box(
        self,
        requirements: ModelRequirements,
        output_name: str,
    ) -> GeneratedModel:
        """Generate a simple box as fallback."""
        size = requirements.get_primary_dimension_mm() or 50.0
        wall = requirements.wall_thickness_mm

        output_path = self.output_dir / f"{output_name}.stl"

        if CADQUERY_AVAILABLE:
            model = (
                cq.Workplane("XY")
                .box(size, size, size)
                .faces(">Z")
                .shell(-wall)
            )
            cq.exporters.export(model, str(output_path))
            method = "cadquery"
        else:
            method = "openscad"
            scad_path = self.output_dir / f"{output_name}.scad"
            source = f'''// Box
size = {size};
wall = {wall};

difference() {{
    cube([size, size, size]);
    translate([wall, wall, wall])
        cube([size - wall*2, size - wall*2, size]);
}}
'''
            with open(scad_path, "w") as f:
                f.write(source)
            self._compile_openscad(scad_path, output_path)

        return GeneratedModel(
            name=output_name,
            output_path=output_path,
            format="stl",
            method=method,
            dimensions_mm={"size": size},
            requirements_used=requirements,
        )

    def _compile_openscad(self, scad_path: Path, stl_path: Path) -> bool:
        """Compile OpenSCAD file to STL."""
        try:
            result = subprocess.run(
                ["openscad", "-o", str(stl_path), str(scad_path)],
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # OpenSCAD not available
            stl_path.touch()  # Create empty placeholder
            return False
