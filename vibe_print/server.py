"""
Vibe Print MCP Server - Main server with all tools registered.

Provides tools for:
- Model analysis and scaling
- Slicer integration
- Printer control and monitoring
- Camera-based defect detection
- Iterative improvement recommendations
"""

import json
from pathlib import Path
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("vibe_print")


# ============================================================================
# Input Models
# ============================================================================

class AnalyzeModelInput(BaseModel):
    """Input for model analysis."""
    model_config = ConfigDict(str_strip_whitespace=True)

    file_path: str = Field(
        ...,
        description="Path to 3D model file (STL, OBJ, or 3MF)"
    )


class ScaleModelInput(BaseModel):
    """Input for model scaling."""
    model_config = ConfigDict(str_strip_whitespace=True)

    file_path: str = Field(..., description="Path to input model file")
    scale_factor: Optional[float] = Field(
        default=None,
        description="Uniform scale factor (e.g., 1.5 = 150%)"
    )
    target_width_mm: Optional[float] = Field(
        default=None,
        description="Target width in mm (scales uniformly to match)"
    )
    original_tube_diameter_mm: Optional[float] = Field(
        default=None,
        description="For tube squeezers: original tube diameter the model was designed for"
    )
    target_tube_diameter_mm: Optional[float] = Field(
        default=None,
        description="For tube squeezers: target tube/bottle diameter to scale to"
    )


class SliceModelInput(BaseModel):
    """Input for slicing a model."""
    model_config = ConfigDict(str_strip_whitespace=True)

    file_path: str = Field(..., description="Path to model file (STL or scaled STL)")
    preset: Optional[str] = Field(
        default="tube_squeezer_standard",
        description="Slicing preset: tube_squeezer_standard, tube_squeezer_strong, draft, quality"
    )
    layer_height: Optional[float] = Field(default=None, description="Layer height in mm")
    infill_percent: Optional[float] = Field(default=None, description="Infill density 0-100")
    wall_loops: Optional[int] = Field(default=None, description="Number of wall loops")


class PrinterConnectionInput(BaseModel):
    """Input for printer connection."""
    model_config = ConfigDict(str_strip_whitespace=True)

    ip_address: str = Field(..., description="Printer IP address")
    access_code: str = Field(..., description="Printer access code")
    serial_number: str = Field(..., description="Printer serial number")


class PrintJobInput(BaseModel):
    """Input for submitting a print job."""
    model_config = ConfigDict(str_strip_whitespace=True)

    file_path: str = Field(..., description="Path to sliced 3MF file")
    bed_leveling: bool = Field(default=True, description="Enable auto bed leveling")
    timelapse: bool = Field(default=False, description="Enable timelapse recording")


class CameraInput(BaseModel):
    """Input for camera operations."""
    model_config = ConfigDict(str_strip_whitespace=True)

    output_path: Optional[str] = Field(
        default=None,
        description="Path to save captured frames"
    )
    frame_count: int = Field(default=1, description="Number of frames to capture")


class IterationInput(BaseModel):
    """Input for iteration tracking."""
    model_config = ConfigDict(str_strip_whitespace=True)

    model_name: str = Field(..., description="Name of the model being printed")


class RecordOutcomeInput(BaseModel):
    """Input for recording print outcome."""
    model_config = ConfigDict(str_strip_whitespace=True)

    iteration_id: str = Field(..., description="Iteration ID to update")
    status: str = Field(..., description="Status: completed, failed, cancelled")
    quality_score: Optional[float] = Field(default=None, description="Quality score 0-100")
    defects: Optional[List[str]] = Field(default=None, description="List of defect types")
    notes: str = Field(default="", description="Additional notes")


# ============================================================================
# Model Analysis Tools
# ============================================================================

@mcp.tool(
    name="vibe_analyze_model",
    annotations={
        "title": "Analyze 3D Model",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_analyze_model(params: AnalyzeModelInput) -> str:
    """
    Analyze a 3D model file to extract dimensions, mesh quality, and recommendations.

    Use this tool to understand a model before scaling or printing.
    Returns bounding box dimensions, triangle count, and detected features.

    Args:
        params: AnalyzeModelInput containing file_path

    Returns:
        JSON with model analysis including dimensions, quality metrics, and recommendations
    """
    from vibe_print.models.analyzer import ModelAnalyzer

    try:
        analyzer = ModelAnalyzer()
        info = analyzer.analyze(Path(params.file_path))
        return info.to_json()
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_scale_model",
    annotations={
        "title": "Scale 3D Model",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_scale_model(params: ScaleModelInput) -> str:
    """
    Scale a 3D model for a different size application.

    For tube squeezers: provide original_tube_diameter_mm and target_tube_diameter_mm
    to scale the model to fit a different tube/bottle size.

    For general scaling: provide scale_factor or target_width_mm.

    Args:
        params: ScaleModelInput with scaling parameters

    Returns:
        JSON with scaled file path and dimension changes

    Example for tube squeezer:
        Scale toothpaste squeezer (designed for 25mm tube) to fit 65mm lotion bottle:
        - original_tube_diameter_mm: 25
        - target_tube_diameter_mm: 65
    """
    from vibe_print.models.scaler import ModelScaler

    try:
        scaler = ModelScaler()

        if params.original_tube_diameter_mm and params.target_tube_diameter_mm:
            # Tube squeezer scaling
            result = scaler.scale_for_tube_squeezer(
                input_path=Path(params.file_path),
                original_tube_diameter_mm=params.original_tube_diameter_mm,
                target_tube_diameter_mm=params.target_tube_diameter_mm,
            )
        elif params.scale_factor:
            # Uniform scaling
            result = scaler.scale_uniform(
                input_path=Path(params.file_path),
                scale_factor=params.scale_factor,
            )
        elif params.target_width_mm:
            # Target dimension scaling
            result = scaler.scale_to_dimension(
                input_path=Path(params.file_path),
                target_width=params.target_width_mm,
            )
        else:
            return json.dumps({"error": "Must provide scale_factor, target_width_mm, or tube diameter parameters"})

        return result.to_json()

    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Slicing Tools
# ============================================================================

@mcp.tool(
    name="vibe_slice_model",
    annotations={
        "title": "Slice Model for Printing",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def vibe_slice_model(params: SliceModelInput) -> str:
    """
    Slice a 3D model using slicer CLI to generate printable G-code.

    Uses preset profiles optimized for different use cases.
    Available presets: tube_squeezer_standard, tube_squeezer_strong, draft, quality

    Args:
        params: SliceModelInput with file path and optional parameters

    Returns:
        JSON with output 3MF path, estimated time, and filament usage
    """
    from vibe_print.slicer.cli import SlicerCLI
    from vibe_print.slicer.parameters import BUILTIN_PRESETS, SlicingParameters

    try:
        cli = SlicerCLI()

        # Get base parameters from preset
        preset_name = params.preset or "tube_squeezer_standard"
        if preset_name in BUILTIN_PRESETS:
            parameters = BUILTIN_PRESETS[preset_name].parameters
        else:
            parameters = SlicingParameters()

        # Apply overrides
        if params.layer_height:
            parameters.layer_height = params.layer_height
        if params.infill_percent:
            parameters.sparse_infill_density = params.infill_percent
        if params.wall_loops:
            parameters.wall_loops = params.wall_loops

        result = await cli.slice_model(
            model_path=Path(params.file_path),
            parameters=parameters,
        )

        return result.to_json()

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_list_presets",
    annotations={
        "title": "List Slicing Presets",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_list_presets() -> str:
    """
    List available slicing presets with their descriptions.

    Returns:
        JSON list of available presets
    """
    from vibe_print.slicer.parameters import BUILTIN_PRESETS

    presets = []
    for name, preset in BUILTIN_PRESETS.items():
        presets.append({
            "name": name,
            "description": preset.description,
            "tags": preset.tags,
        })

    return json.dumps({"presets": presets}, indent=2)


# ============================================================================
# Printer Control Tools
# ============================================================================

@mcp.tool(
    name="vibe_test_printer_connection",
    annotations={
        "title": "Test Printer Connection",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def vibe_test_printer_connection(params: PrinterConnectionInput) -> str:
    """
    Test connection to a compatible FDM printer in LAN mode.

    Requires printer IP address, access code (from printer settings), and serial number.

    Args:
        params: PrinterConnectionInput with connection details

    Returns:
        JSON with connection status and printer info
    """
    from vibe_print.printer.mqtt_client import test_printer_connection

    try:
        success, message = await test_printer_connection(
            host=params.ip_address,
            access_code=params.access_code,
            serial_number=params.serial_number,
        )

        return json.dumps({
            "connected": success,
            "message": message,
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_get_printer_status",
    annotations={
        "title": "Get Printer Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def vibe_get_printer_status() -> str:
    """
    Get current status of the connected FDM printer.

    Returns temperatures, print progress, and operational state.
    Requires environment variables: VIBE_PRINTER_IP, VIBE_ACCESS_CODE, VIBE_SERIAL

    Returns:
        JSON with printer status including temperatures, progress, and state
    """
    from vibe_print.printer.controller import PrinterController

    try:
        controller = PrinterController()
        connected = await controller.connect(timeout=5.0)

        if not connected:
            return json.dumps({"error": "Could not connect to printer. Check IP and access code."})

        status = await controller.refresh_status()
        await controller.disconnect()

        if status:
            return status.to_json()
        return json.dumps({"error": "No status received from printer"})

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_control_print",
    annotations={
        "title": "Control Print Job",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def vibe_control_print(action: str) -> str:
    """
    Control an active print job.

    Actions: pause, resume, stop

    Args:
        action: Control action (pause, resume, stop)

    Returns:
        JSON with action result
    """
    from vibe_print.printer.controller import PrinterController

    valid_actions = ["pause", "resume", "stop"]
    if action not in valid_actions:
        return json.dumps({"error": f"Invalid action. Must be one of: {valid_actions}"})

    try:
        controller = PrinterController()
        connected = await controller.connect(timeout=5.0)

        if not connected:
            return json.dumps({"error": "Could not connect to printer"})

        if action == "pause":
            result = await controller.pause_print()
        elif action == "resume":
            result = await controller.resume_print()
        else:  # stop
            result = await controller.stop_print()

        await controller.disconnect()

        return json.dumps({
            "action": action,
            "success": result,
        })

    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Camera & Defect Detection Tools
# ============================================================================

@mcp.tool(
    name="vibe_capture_camera",
    annotations={
        "title": "Capture Camera Frame",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def vibe_capture_camera(params: CameraInput) -> str:
    """
    Capture frames from the printer's camera.

    Connects to the printer's RTSPS camera stream and captures frames.
    Compatible printers typically provide 1 FPS camera feed.

    Args:
        params: CameraInput with output path and frame count

    Returns:
        JSON with captured frame info and file paths
    """
    from vibe_print.camera.stream import CameraStream

    try:
        camera = CameraStream()

        available, message = camera.is_available()
        if not available:
            return json.dumps({"error": message})

        connected = await camera.connect(timeout=10.0)
        if not connected:
            return json.dumps({"error": "Could not connect to camera stream"})

        if params.output_path:
            paths = await camera.capture_to_file(
                output_path=Path(params.output_path),
                count=params.frame_count,
            )
            await camera.disconnect()
            return json.dumps({
                "captured": len(paths),
                "files": [str(p) for p in paths],
            })
        else:
            frames = await camera.capture_frames(count=params.frame_count)
            await camera.disconnect()
            return json.dumps({
                "captured": len(frames),
                "frames": [
                    {
                        "frame_number": f.frame_number,
                        "timestamp": f.timestamp.isoformat(),
                        "width": f.width,
                        "height": f.height,
                    }
                    for f in frames
                ],
            })

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_analyze_print_quality",
    annotations={
        "title": "Analyze Print Quality",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def vibe_analyze_print_quality() -> str:
    """
    Capture a camera frame and analyze it for print defects.

    Detects common issues like layer shifts, stringing, warping, blobs,
    and spaghetti failures. Returns quality score and recommendations.

    Returns:
        JSON with quality score, detected defects, and recommendations
    """
    from vibe_print.camera.stream import CameraStream
    from vibe_print.camera.detector import DefectDetector

    try:
        camera = CameraStream()

        available, message = camera.is_available()
        if not available:
            return json.dumps({"error": message})

        connected = await camera.connect(timeout=10.0)
        if not connected:
            return json.dumps({"error": "Could not connect to camera stream"})

        frame = await camera.capture_frame()
        await camera.disconnect()

        if not frame:
            return json.dumps({"error": "Failed to capture frame"})

        detector = DefectDetector()
        result = detector.analyze_frame(frame)

        return result.to_json()

    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Iteration Tracking Tools
# ============================================================================

@mcp.tool(
    name="vibe_create_iteration",
    annotations={
        "title": "Create Print Iteration",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def vibe_create_iteration(
    model_name: str,
    model_path: str,
    scale_factor: Optional[float] = None,
    preset_name: Optional[str] = None,
) -> str:
    """
    Create a new print iteration record for tracking.

    Call this before starting a print to track the attempt and its outcome.

    Args:
        model_name: Name of the model (e.g., "toothpaste_squeezer")
        model_path: Path to the model file
        scale_factor: Applied scale factor if scaled
        preset_name: Slicing preset used

    Returns:
        JSON with iteration ID and details
    """
    from vibe_print.iteration.tracker import IterationTracker

    try:
        tracker = IterationTracker()
        iteration = await tracker.create_iteration(
            model_name=model_name,
            model_path=model_path,
            scale_factor=scale_factor,
            preset_name=preset_name,
        )

        return json.dumps(iteration.to_dict(), indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_record_outcome",
    annotations={
        "title": "Record Print Outcome",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def vibe_record_outcome(params: RecordOutcomeInput) -> str:
    """
    Record the outcome of a print attempt.

    Call this after a print completes (or fails) to track the result.
    Generates improvement suggestions based on any defects detected.

    Args:
        params: RecordOutcomeInput with iteration_id, status, quality_score, defects

    Returns:
        JSON with updated iteration and improvement suggestions
    """
    from vibe_print.iteration.tracker import IterationTracker

    try:
        tracker = IterationTracker()
        iteration = await tracker.record_outcome(
            iteration_id=params.iteration_id,
            status=params.status,
            quality_score=params.quality_score,
            defects=params.defects,
            notes=params.notes,
        )

        if iteration:
            return json.dumps(iteration.to_dict(), indent=2)
        return json.dumps({"error": "Iteration not found"})

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_get_recommendations",
    annotations={
        "title": "Get Parameter Recommendations",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_get_recommendations(
    model_name: str,
    defects: Optional[List[str]] = None,
) -> str:
    """
    Get parameter adjustment recommendations based on detected defects and history.

    Analyzes past prints and current defects to suggest improvements.

    Args:
        model_name: Name of the model
        defects: List of defect types from quality analysis

    Returns:
        JSON with parameter recommendations sorted by priority
    """
    from vibe_print.iteration.tracker import IterationTracker
    from vibe_print.iteration.recommender import ParameterRecommender
    from vibe_print.slicer.parameters import SlicingParameters

    try:
        tracker = IterationTracker()
        recommender = ParameterRecommender()

        # Get history
        iterations = await tracker.get_iterations_for_model(model_name)

        # Get recommendations
        current_params = SlicingParameters()  # Default params
        recommendations = recommender.get_recommendations(
            current_params=current_params,
            defects=defects or [],
            iterations=iterations,
        )

        return json.dumps({
            "model_name": model_name,
            "recommendations": [r.to_dict() for r in recommendations],
            "summary": recommender.get_summary(recommendations),
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_get_model_history",
    annotations={
        "title": "Get Model Print History",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_get_model_history(params: IterationInput) -> str:
    """
    Get print history and statistics for a model.

    Shows past attempts, success rate, common defects, and best quality achieved.

    Args:
        params: IterationInput with model_name

    Returns:
        JSON with print history and statistics
    """
    from vibe_print.iteration.tracker import IterationTracker

    try:
        tracker = IterationTracker()
        stats = await tracker.get_model_statistics(params.model_name)
        return json.dumps(stats, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Model Generation Tools
# ============================================================================

class GenerateModelInput(BaseModel):
    """Input for model generation from text requirements."""
    model_config = ConfigDict(str_strip_whitespace=True)

    description: str = Field(
        ...,
        description="Natural language description of the model to create"
    )
    target_dimension_mm: Optional[float] = Field(
        default=None,
        description="Primary target dimension in mm (e.g., tube diameter)"
    )


class GenerateFromTemplateInput(BaseModel):
    """Input for generating from a template."""
    model_config = ConfigDict(str_strip_whitespace=True)

    template_name: str = Field(..., description="Name of the template to use")
    tube_diameter: Optional[float] = Field(default=None, description="Tube/bottle diameter in mm")
    wall_thickness: Optional[float] = Field(default=2.5, description="Wall thickness in mm")
    clearance: Optional[float] = Field(default=1.0, description="Slot clearance in mm")


class AnalyzeImageInput(BaseModel):
    """Input for image analysis."""
    model_config = ConfigDict(str_strip_whitespace=True)

    image_path: str = Field(..., description="Path to reference image")
    known_dimension_mm: Optional[float] = Field(
        default=None,
        description="If you know one dimension in the image, provide it for calibration"
    )


class AIGenerateInput(BaseModel):
    """Input for AI-powered 3D generation."""
    model_config = ConfigDict(str_strip_whitespace=True)

    prompt: str = Field(..., description="Text description of the 3D model to generate")
    style: str = Field(default="realistic", description="Art style: realistic, cartoon, sculpture")


@mcp.tool(
    name="vibe_parse_requirements",
    annotations={
        "title": "Parse Model Requirements",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_parse_requirements(params: GenerateModelInput) -> str:
    """
    Parse natural language requirements into structured model parameters.

    Extracts dimensions, object type, and design preferences from a text description.
    Use this to understand what model parameters to use before generation.

    Args:
        params: GenerateModelInput with description and optional target dimension

    Returns:
        JSON with parsed requirements including dimensions, category, and recommendations

    Example:
        "I need a squeezer for my lotion bottle that's about 65mm diameter"
        -> Extracts: category=tube_squeezer, tube_diameter=65mm, fit_type=sliding
    """
    from vibe_print.generator.requirements import RequirementsParser

    try:
        parser = RequirementsParser()
        requirements = parser.parse(params.description)

        # Override with explicit dimension if provided
        if params.target_dimension_mm:
            from vibe_print.generator.requirements import Dimension
            requirements.target_dimensions.insert(0, Dimension(
                value=params.target_dimension_mm,
                unit="mm",
                context="user specified",
            ))

        return requirements.to_json()

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_analyze_reference_image",
    annotations={
        "title": "Analyze Reference Image",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_analyze_reference_image(params: AnalyzeImageInput) -> str:
    """
    Analyze a reference image to extract dimensions for model generation.

    Can detect rulers/scales in the image for accurate measurements.
    If no scale is visible, provide a known_dimension_mm for calibration.

    Args:
        params: AnalyzeImageInput with image path and optional known dimension

    Returns:
        JSON with detected dimensions, features, and suggested object category

    Example:
        Analyze a photo showing a lotion bottle next to a ruler
        -> Returns: bottle_width=65mm, suggested_category=tube_squeezer
    """
    from vibe_print.generator.image_analyzer import ImageAnalyzer

    try:
        analyzer = ImageAnalyzer()
        result = analyzer.analyze_image(
            image_path=Path(params.image_path),
            known_dimension_mm=params.known_dimension_mm,
        )

        return result.to_json()

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_list_templates",
    annotations={
        "title": "List Model Templates",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_list_templates() -> str:
    """
    List all available model templates with their parameters.

    Templates are pre-built parametric designs that can be customized
    with specific dimensions.

    Returns:
        JSON list of templates with names, descriptions, and customizable parameters
    """
    from vibe_print.generator.templates import template_library

    try:
        templates = template_library.list_templates()
        return json.dumps({"templates": templates}, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_generate_from_template",
    annotations={
        "title": "Generate Model from Template",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_generate_from_template(params: GenerateFromTemplateInput) -> str:
    """
    Generate a 3D model from a customizable template.

    For tube squeezers, provide the tube_diameter to create a perfectly sized squeezer.
    This is the recommended way to create functional parts like squeezers, holders, and clips.

    Args:
        params: GenerateFromTemplateInput with template name and parameters

    Returns:
        JSON with path to generated STL file and model dimensions

    Example:
        Generate a tube squeezer for a 65mm lotion bottle:
        template_name="tube_squeezer", tube_diameter=65
    """
    from vibe_print.generator.templates import template_library

    try:
        # Build parameter dict
        template_params = {}
        if params.tube_diameter:
            template_params["tube_diameter"] = params.tube_diameter
        if params.wall_thickness:
            template_params["wall_thickness"] = params.wall_thickness
        if params.clearance:
            template_params["clearance"] = params.clearance

        output_path = template_library.generate_from_template(
            template_name=params.template_name,
            params=template_params,
        )

        if output_path and output_path.exists():
            return json.dumps({
                "success": True,
                "template": params.template_name,
                "output_path": str(output_path),
                "parameters_used": template_params,
            }, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": f"Template '{params.template_name}' not found or generation failed",
            })

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_generate_parametric",
    annotations={
        "title": "Generate Parametric Model",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_generate_parametric(params: GenerateModelInput) -> str:
    """
    Generate a 3D model from natural language requirements.

    Parses the description to understand what type of object is needed,
    then generates it using parametric CAD (CadQuery or OpenSCAD).

    Best for functional parts: squeezers, holders, brackets, clips, covers.

    Args:
        params: GenerateModelInput with description and optional target dimension

    Returns:
        JSON with path to generated STL, dimensions, and source code

    Example:
        "A tube squeezer for a 65mm diameter lotion bottle, heavy duty"
        -> Generates STL with appropriate slot width, thick walls, grip textures
    """
    from vibe_print.generator.requirements import RequirementsParser
    from vibe_print.generator.parametric import ParametricGenerator

    try:
        # Parse requirements
        parser = RequirementsParser()
        requirements = parser.parse(params.description)

        # Override dimension if specified
        if params.target_dimension_mm:
            from vibe_print.generator.requirements import Dimension
            requirements.target_dimensions.insert(0, Dimension(
                value=params.target_dimension_mm,
                unit="mm",
                context="user specified",
            ))

        # Generate model
        generator = ParametricGenerator()
        result = generator.generate_from_requirements(requirements)

        return result.to_json()

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_ai_generate",
    annotations={
        "title": "AI Generate 3D Model",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def vibe_ai_generate(params: AIGenerateInput) -> str:
    """
    Generate a 3D model using AI (text-to-3D).

    Uses cloud AI services (Meshy, Tripo3D) to create organic/artistic 3D models.
    Requires API key in environment (MESHY_API_KEY or TRIPO3D_API_KEY).

    Best for: artistic models, organic shapes, characters, decorative items.
    For functional parts, use vibe_generate_parametric instead.

    Args:
        params: AIGenerateInput with prompt and style

    Returns:
        JSON with job_id for tracking (generation takes 1-5 minutes)
    """
    from vibe_print.generator.ai_generator import AIModelGenerator

    try:
        generator = AIModelGenerator()

        # Check if any provider is available
        providers = generator.get_available_providers()
        if not any(p.get("available") for p in providers):
            return json.dumps({
                "error": "No AI provider configured",
                "setup": "Set MESHY_API_KEY or TRIPO3D_API_KEY environment variable",
                "providers": providers,
            }, indent=2)

        # Start generation
        status = await generator.generate_text_to_3d(
            prompt=params.prompt,
            style=params.style,
        )

        return json.dumps(status.to_dict(), indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_ai_status",
    annotations={
        "title": "Check AI Generation Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def vibe_ai_status(job_id: str) -> str:
    """
    Check the status of an AI model generation job.

    Args:
        job_id: The job ID returned from vibe_ai_generate

    Returns:
        JSON with status (processing/completed/failed), progress, and download URL
    """
    from vibe_print.generator.ai_generator import AIModelGenerator

    try:
        generator = AIModelGenerator()
        status = await generator.get_job_status(job_id)

        if status:
            return json.dumps(status.to_dict(), indent=2)
        return json.dumps({"error": f"Job not found: {job_id}"})

    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Wizard & Material Tools
# ============================================================================

class StartWorkflowInput(BaseModel):
    """Input for starting a guided workflow."""
    model_config = ConfigDict(str_strip_whitespace=True)

    description: str = Field(
        ...,
        description="Natural language description of what you want to print"
    )


class DesignReviewInput(BaseModel):
    """Input for design review."""
    model_config = ConfigDict(str_strip_whitespace=True)

    wall_thickness_mm: float = Field(default=2.0, description="Wall thickness in mm")
    clearance_mm: float = Field(default=0.3, description="Clearance for fitting parts in mm")
    tube_diameter: Optional[float] = Field(default=None, description="Tube diameter if applicable")
    intended_use: str = Field(default="", description="What the part will be used for")
    material: str = Field(default="PLA", description="Material to use")
    nozzle_diameter: float = Field(default=0.4, description="Nozzle diameter in mm")


class SlicingReviewInput(BaseModel):
    """Input for slicing review."""
    model_config = ConfigDict(str_strip_whitespace=True)

    material: str = Field(..., description="Filament material name")
    nozzle_diameter: float = Field(default=0.4, description="Nozzle diameter in mm")
    quality: str = Field(default="standard", description="Quality preset: draft, standard, quality, ultra")
    use_case: str = Field(default="functional", description="Use case: functional, decorative, prototype, gift")


class MaterialOptimizeInput(BaseModel):
    """Input for material-based optimization."""
    model_config = ConfigDict(str_strip_whitespace=True)

    material: str = Field(..., description="Filament material name")
    nozzle_diameter: float = Field(default=0.4, description="Nozzle diameter in mm")
    layer_height: Optional[float] = Field(default=None, description="Layer height in mm")
    outer_wall_speed: Optional[int] = Field(default=None, description="Outer wall speed mm/s")
    infill_speed: Optional[int] = Field(default=None, description="Infill speed mm/s")
    nozzle_temp: Optional[int] = Field(default=None, description="Nozzle temperature C")
    bed_temp: Optional[int] = Field(default=None, description="Bed temperature C")


@mcp.tool(
    name="vibe_list_materials",
    annotations={
        "title": "List Available Materials",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_list_materials() -> str:
    """
    List all available filament profiles with their properties.

    Returns profiles for common materials including PLA, PETG, PC, and TPU.
    Shows temperature ranges, speed limits, and special notes for each material.

    Returns:
        JSON list of materials with their printing parameters
    """
    from vibe_print.materials.filaments import list_filament_profiles, get_filament_profile

    try:
        material_names = list_filament_profiles()
        materials = []

        for name in material_names:
            profile = get_filament_profile(name)
            if profile:
                materials.append({
                    "name": profile.name,
                    "type": profile.filament_type.value,
                    "nozzle_temp": {
                        "min": profile.nozzle_temp.min_temp,
                        "optimal": profile.nozzle_temp.optimal,
                        "max": profile.nozzle_temp.max_temp,
                    },
                    "bed_temp": {
                        "min": profile.bed_temp.min_temp,
                        "optimal": profile.bed_temp.optimal,
                        "max": profile.bed_temp.max_temp,
                    },
                    "max_print_speed": profile.max_print_speed,
                    "is_flexible": profile.is_flexible,
                    "is_abrasive": profile.is_abrasive,
                    "ams_compatible": profile.ams_compatible,
                    "special_notes": profile.special_notes,
                })

        return json.dumps({"materials": materials}, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_list_nozzles",
    annotations={
        "title": "List Available Nozzles",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_list_nozzles() -> str:
    """
    List all nozzle sizes available for compatible FDM printers with recommendations.

    Returns nozzle profiles with layer height ranges, speed factors,
    and best-use cases for each nozzle size.

    Returns:
        JSON list of nozzle profiles
    """
    from vibe_print.materials.nozzles import SUPPORTED_NOZZLES

    try:
        nozzles = []
        seen = set()

        for key, profile in SUPPORTED_NOZZLES.items():
            # Skip duplicate entries
            unique_key = f"{profile.diameter}_{profile.nozzle_type.value}"
            if unique_key in seen:
                continue
            seen.add(unique_key)

            nozzles.append({
                "diameter_mm": profile.diameter,
                "type": profile.nozzle_type.value,
                "layer_heights": profile.get_layer_heights(),
                "speed_multiplier": profile.speed_multiplier,
                "abrasive_safe": profile.abrasive_safe,
                "best_for": profile.best_for,
                "avoid_for": profile.avoid_for,
            })

        # Sort by diameter
        nozzles.sort(key=lambda x: x["diameter_mm"])

        return json.dumps({"nozzles": nozzles}, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_start_guided_workflow",
    annotations={
        "title": "Start Guided Workflow",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def vibe_start_guided_workflow(params: StartWorkflowInput) -> str:
    """
    Start an interactive guided workflow for print creation.

    This is the RECOMMENDED starting point for novice users!
    Parses your description and guides you through design decisions
    with interactive checkpoints.

    The workflow covers:
    1. Requirements understanding
    2. Design review with suggestions
    3. Material selection
    4. Nozzle selection
    5. Quality settings
    6. Final review

    Args:
        params: StartWorkflowInput with your description

    Returns:
        JSON with workflow state and first checkpoint questions

    Example:
        "I need a tube squeezer for my 65mm lotion bottle, heavy duty"
    """
    from vibe_print.wizard.guided_workflow import GuidedWorkflow

    try:
        workflow = GuidedWorkflow()
        state = workflow.start_workflow(params.description)

        return json.dumps({
            "workflow_id": state.workflow_id,
            "stage": state.current_stage.value,
            "parsed_requirements": state.parsed_requirements,
            "current_checkpoint": state.checkpoints[-1].to_dict() if state.checkpoints else None,
            "next_action": "Review and answer the questions in the checkpoint",
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_review_design",
    annotations={
        "title": "Review Design Parameters",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_review_design(params: DesignReviewInput) -> str:
    """
    Review design parameters and get suggestions for improvement.

    Analyzes your design choices and provides:
    - Critical issues that need fixing
    - Recommended improvements
    - Material-specific advice
    - Printability checks

    Use this before generating a model to catch potential problems early.

    Args:
        params: DesignReviewInput with design parameters

    Returns:
        JSON with review results, suggestions, and warnings
    """
    from vibe_print.wizard.design_review import DesignReviewer

    try:
        reviewer = DesignReviewer()

        design_params = {
            "wall_thickness_mm": params.wall_thickness_mm,
            "clearance_mm": params.clearance_mm,
        }
        if params.tube_diameter:
            design_params["tube_diameter"] = params.tube_diameter

        review = reviewer.review_design(
            design_params=design_params,
            intended_use=params.intended_use,
            material=params.material,
            nozzle_diameter=params.nozzle_diameter,
        )

        return json.dumps(review, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_review_slicing",
    annotations={
        "title": "Review Slicing Parameters",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_review_slicing(params: SlicingReviewInput) -> str:
    """
    Get recommended slicing settings for your material and use case.

    Provides optimized settings based on:
    - Material properties (temperature, speed limits)
    - Quality level desired
    - Intended use (strength, appearance)
    - Nozzle size

    Args:
        params: SlicingReviewInput with material, quality, and use case

    Returns:
        JSON with recommended settings and explanations
    """
    from vibe_print.wizard.slicing_review import (
        get_recommended_settings,
        get_slicing_questions,
        QualityPreset,
        PrintUseCase,
    )
    from vibe_print.materials.filaments import get_filament_profile

    try:
        # Get quality and use case enums
        quality = QualityPreset(params.quality)
        use_case = PrintUseCase(params.use_case)

        # Get recommended settings
        settings = get_recommended_settings(
            params.material,
            params.nozzle_diameter,
            quality,
            use_case,
        )

        # Get material notes
        profile = get_filament_profile(params.material)
        notes = []
        if profile:
            if not profile.ams_compatible:
                notes.append(f"{profile.name} must be fed directly, not via multi-material system")
            if profile.special_notes:
                notes.append(profile.special_notes)

        return json.dumps({
            "recommended_settings": settings,
            "quality_level": quality.value,
            "use_case": use_case.value,
            "material_notes": notes,
            "time_estimate": "Varies based on model size",
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_optimize_for_material",
    annotations={
        "title": "Optimize Parameters for Material",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_optimize_for_material(params: MaterialOptimizeInput) -> str:
    """
    Optimize slicing parameters for a specific material.

    Takes your current parameters and adjusts them based on
    the material's properties and limitations. Shows what was
    changed and why.

    Args:
        params: MaterialOptimizeInput with current parameters

    Returns:
        JSON with optimized parameters and list of changes made
    """
    from vibe_print.wizard.material_optimizer import MaterialOptimizer

    try:
        optimizer = MaterialOptimizer()

        # Build current params dict
        current_params = {}
        if params.layer_height:
            current_params["layer_height"] = params.layer_height
        if params.outer_wall_speed:
            current_params["outer_wall_speed"] = params.outer_wall_speed
        if params.infill_speed:
            current_params["infill_speed"] = params.infill_speed
        if params.nozzle_temp:
            current_params["nozzle_temp"] = params.nozzle_temp
        if params.bed_temp:
            current_params["bed_temp"] = params.bed_temp

        result = optimizer.optimize_for_material(
            params=current_params,
            material=params.material,
            nozzle_diameter=params.nozzle_diameter,
        )

        return json.dumps(result.to_dict(), indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_get_nozzle_recommendation",
    annotations={
        "title": "Get Nozzle Recommendation",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_get_nozzle_recommendation(
    part_size: str = "medium",
    detail_needed: str = "standard",
    material_abrasive: bool = False,
    speed_priority: bool = False,
) -> str:
    """
    Get nozzle recommendation based on your requirements.

    Args:
        part_size: "small", "medium", or "large"
        detail_needed: "fine", "standard", or "low"
        material_abrasive: True if using CF/GF filaments
        speed_priority: True if speed is more important than detail

    Returns:
        JSON with recommended nozzle and explanation
    """
    from vibe_print.materials.nozzles import get_recommended_nozzle

    try:
        nozzle, explanation = get_recommended_nozzle(
            part_size=part_size,
            detail_needed=detail_needed,
            material_abrasive=material_abrasive,
            speed_priority=speed_priority,
        )

        return json.dumps({
            "recommended": {
                "diameter_mm": nozzle.diameter,
                "type": nozzle.nozzle_type.value,
                "layer_heights": nozzle.get_layer_heights(),
                "speed_multiplier": nozzle.speed_multiplier,
            },
            "explanation": explanation,
            "best_for": nozzle.best_for,
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="vibe_parse_novice_description",
    annotations={
        "title": "Parse Novice Description",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def vibe_parse_novice_description(description: str) -> str:
    """
    Parse a natural language description into CAD parameters.

    Understands everyday language like:
    - "heavy duty" -> thick walls, high infill
    - "snug fit" -> appropriate clearance
    - "flexible" -> suggests TPU material

    Use this to translate novice descriptions into technical parameters.

    Args:
        description: Your description in plain language

    Returns:
        JSON with extracted parameters, material suggestions, and clarifying questions
    """
    from vibe_print.wizard.novice_parser import parse_novice_description

    try:
        result = parse_novice_description(description)
        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
