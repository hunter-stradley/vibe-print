"""
Model Generation Module - Create 3D models from requirements and references.

Provides multiple approaches for generating 3D printable models:
1. Parametric generation using CadQuery (precise functional parts)
2. Template-based generation (tube squeezers, brackets, holders)
3. Image analysis for dimension extraction
4. AI-powered generation for organic shapes
"""

from vibe_print.generator.requirements import RequirementsParser, ModelRequirements
from vibe_print.generator.image_analyzer import ImageAnalyzer, DimensionMeasurement
from vibe_print.generator.parametric import ParametricGenerator, GeneratedModel
from vibe_print.generator.templates import TemplateLibrary, TubeSqueezerTemplate
from vibe_print.generator.ai_generator import AIModelGenerator

__all__ = [
    "RequirementsParser",
    "ModelRequirements",
    "ImageAnalyzer",
    "DimensionMeasurement",
    "ParametricGenerator",
    "GeneratedModel",
    "TemplateLibrary",
    "TubeSqueezerTemplate",
    "AIModelGenerator",
]
