"""
Requirements Parser - Extract structured parameters from natural language.

Parses user descriptions to identify:
- Target dimensions and measurements
- Object type and purpose
- Material constraints
- Functional requirements
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple


class ObjectCategory(str, Enum):
    """Categories of printable objects."""
    TUBE_SQUEEZER = "tube_squeezer"
    HOLDER = "holder"
    BRACKET = "bracket"
    CLIP = "clip"
    CONTAINER = "container"
    ORGANIZER = "organizer"
    TOOL = "tool"
    ADAPTER = "adapter"
    COVER = "cover"
    CUSTOM = "custom"


class FitType(str, Enum):
    """How the object should fit its target."""
    TIGHT = "tight"      # Press fit, minimal clearance
    SNUG = "snug"        # Slight friction fit
    SLIDING = "sliding"  # Easy sliding fit
    LOOSE = "loose"      # Extra clearance


@dataclass
class Dimension:
    """A dimension with value, unit, and context."""
    value: float
    unit: str = "mm"
    context: str = ""  # e.g., "tube diameter", "bottle width"
    is_target: bool = True  # True if this is the target dimension to match

    def to_mm(self) -> float:
        """Convert to millimeters."""
        conversions = {
            "mm": 1.0,
            "cm": 10.0,
            "m": 1000.0,
            "in": 25.4,
            "inch": 25.4,
            "inches": 25.4,
            "ft": 304.8,
        }
        return self.value * conversions.get(self.unit.lower(), 1.0)


@dataclass
class ModelRequirements:
    """Structured requirements for model generation."""
    # Basic info
    name: str = ""
    description: str = ""
    category: ObjectCategory = ObjectCategory.CUSTOM

    # Dimensions
    target_dimensions: List[Dimension] = field(default_factory=list)
    max_dimensions: Optional[Tuple[float, float, float]] = None  # Max X, Y, Z in mm

    # Functional requirements
    fit_type: FitType = FitType.SLIDING
    needs_strength: bool = False
    needs_flexibility: bool = False
    needs_water_resistance: bool = False

    # Design preferences
    wall_thickness_mm: float = 2.0
    corner_radius_mm: float = 1.0
    add_grip_texture: bool = False

    # Reference info
    reference_object: str = ""  # e.g., "Gold Bond lotion bottle"
    similar_to: str = ""  # e.g., "toothpaste squeezer"

    # Raw input
    original_text: str = ""
    extracted_numbers: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "target_dimensions": [
                {"value": d.value, "unit": d.unit, "context": d.context, "mm": d.to_mm()}
                for d in self.target_dimensions
            ],
            "max_dimensions_mm": self.max_dimensions,
            "fit_type": self.fit_type.value,
            "needs_strength": self.needs_strength,
            "wall_thickness_mm": self.wall_thickness_mm,
            "reference_object": self.reference_object,
            "similar_to": self.similar_to,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    def get_primary_dimension_mm(self) -> Optional[float]:
        """Get the primary target dimension in mm."""
        if self.target_dimensions:
            return self.target_dimensions[0].to_mm()
        return None


class RequirementsParser:
    """
    Parses natural language requirements into structured ModelRequirements.

    Uses pattern matching and heuristics to extract:
    - Dimensions and measurements
    - Object type classification
    - Functional requirements
    """

    # Patterns for dimension extraction
    DIMENSION_PATTERNS = [
        # "65mm diameter"
        r'(\d+\.?\d*)\s*(mm|cm|in|inch|inches?)\s*(diameter|wide|tall|long|thick|deep)?',
        # "2.5 inches wide"
        r'(\d+\.?\d*)\s*(inches?|in|cm|mm)\s*(wide|tall|long|thick|deep|diameter)?',
        # "diameter of 65mm"
        r'(diameter|width|height|length|thickness)\s*(?:of|:|\s)\s*(\d+\.?\d*)\s*(mm|cm|in)?',
        # "5.5 oz bottle" (volume-based hints)
        r'(\d+\.?\d*)\s*(oz|fl\s*oz|ml|liter|L)\s*(bottle|container|tube)?',
    ]

    # Keywords for object classification
    CATEGORY_KEYWORDS = {
        ObjectCategory.TUBE_SQUEEZER: [
            "squeezer", "squeeze", "tube squeezer", "toothpaste", "lotion",
            "cream", "paste", "dispenser", "roller", "wringer"
        ],
        ObjectCategory.HOLDER: [
            "holder", "stand", "dock", "cradle", "rest", "mount"
        ],
        ObjectCategory.BRACKET: [
            "bracket", "mount", "mounting", "wall mount", "shelf bracket"
        ],
        ObjectCategory.CLIP: [
            "clip", "clamp", "grip", "grabber", "pinch"
        ],
        ObjectCategory.CONTAINER: [
            "container", "box", "case", "enclosure", "housing"
        ],
        ObjectCategory.ORGANIZER: [
            "organizer", "tray", "caddy", "sorter", "divider"
        ],
        ObjectCategory.ADAPTER: [
            "adapter", "converter", "fitting", "coupler", "connector"
        ],
        ObjectCategory.COVER: [
            "cover", "cap", "lid", "top", "protector"
        ],
    }

    # Strength indicators
    STRENGTH_KEYWORDS = [
        "strong", "heavy duty", "heavy-duty", "robust", "durable",
        "sturdy", "thick", "reinforced", "solid"
    ]

    # Flexibility indicators
    FLEX_KEYWORDS = [
        "flexible", "bendy", "soft", "elastic", "springy", "snap fit"
    ]

    def __init__(self):
        """Initialize parser."""
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.DIMENSION_PATTERNS
        ]

    def parse(self, text: str) -> ModelRequirements:
        """
        Parse natural language requirements.

        Args:
            text: User's description of what they want

        Returns:
            ModelRequirements with extracted parameters
        """
        requirements = ModelRequirements(original_text=text)

        # Extract dimensions
        requirements.target_dimensions = self._extract_dimensions(text)
        requirements.extracted_numbers = self._extract_all_numbers(text)

        # Classify object type
        requirements.category = self._classify_category(text)

        # Extract functional requirements
        requirements.needs_strength = self._check_keywords(text, self.STRENGTH_KEYWORDS)
        requirements.needs_flexibility = self._check_keywords(text, self.FLEX_KEYWORDS)

        # Extract fit type
        requirements.fit_type = self._determine_fit_type(text)

        # Extract reference objects
        requirements.reference_object = self._extract_reference(text)

        # Generate name and description
        requirements.name = self._generate_name(requirements)
        requirements.description = self._generate_description(requirements)

        # Adjust wall thickness based on size and strength
        if requirements.needs_strength:
            requirements.wall_thickness_mm = 3.0
        if requirements.get_primary_dimension_mm() and requirements.get_primary_dimension_mm() > 50:
            requirements.wall_thickness_mm = max(requirements.wall_thickness_mm, 2.5)

        return requirements

    def _extract_dimensions(self, text: str) -> List[Dimension]:
        """Extract dimension values from text."""
        dimensions = []
        seen_values = set()

        for pattern in self._compiled_patterns:
            for match in pattern.finditer(text):
                groups = match.groups()

                # Handle different pattern formats
                if len(groups) >= 2:
                    try:
                        # Check which group has the number
                        if groups[0].replace('.', '').isdigit():
                            value = float(groups[0])
                            unit = groups[1] if len(groups) > 1 else "mm"
                            context = groups[2] if len(groups) > 2 and groups[2] else ""
                        else:
                            # Pattern like "diameter of 65mm"
                            context = groups[0]
                            value = float(groups[1])
                            unit = groups[2] if len(groups) > 2 and groups[2] else "mm"

                        # Avoid duplicates
                        if value not in seen_values:
                            seen_values.add(value)
                            dimensions.append(Dimension(
                                value=value,
                                unit=unit,
                                context=context or "",
                            ))
                    except (ValueError, IndexError):
                        continue

        return dimensions

    def _extract_all_numbers(self, text: str) -> List[float]:
        """Extract all numeric values from text."""
        numbers = []
        for match in re.finditer(r'\d+\.?\d*', text):
            try:
                numbers.append(float(match.group()))
            except ValueError:
                continue
        return numbers

    def _classify_category(self, text: str) -> ObjectCategory:
        """Classify the object type based on keywords."""
        text_lower = text.lower()

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return category

        return ObjectCategory.CUSTOM

    def _check_keywords(self, text: str, keywords: List[str]) -> bool:
        """Check if any keywords are present."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)

    def _determine_fit_type(self, text: str) -> FitType:
        """Determine the desired fit type."""
        text_lower = text.lower()

        if any(kw in text_lower for kw in ["tight", "press fit", "friction"]):
            return FitType.TIGHT
        if any(kw in text_lower for kw in ["snug", "secure"]):
            return FitType.SNUG
        if any(kw in text_lower for kw in ["loose", "easy", "clearance"]):
            return FitType.LOOSE

        return FitType.SLIDING  # Default for squeezers

    def _extract_reference(self, text: str) -> str:
        """Extract reference object mentions."""
        # Common product patterns
        patterns = [
            r'([\w\s]+(?:bottle|tube|container|can|jar))',
            r'for\s+(?:a\s+|my\s+)?([\w\s]+)',
            r'like\s+(?:a\s+)?([\w\s]+(?:squeezer|holder|clip))',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return ""

    def _generate_name(self, req: ModelRequirements) -> str:
        """Generate a descriptive name."""
        parts = []

        if req.reference_object:
            # Clean up reference
            ref = req.reference_object.lower()
            ref = re.sub(r'\s+', '_', ref)
            parts.append(ref)

        parts.append(req.category.value)

        # Add primary dimension
        dim = req.get_primary_dimension_mm()
        if dim:
            parts.append(f"{dim:.0f}mm")

        return "_".join(parts) if parts else "custom_model"

    def _generate_description(self, req: ModelRequirements) -> str:
        """Generate a description."""
        parts = [f"A {req.category.value.replace('_', ' ')}"]

        if req.reference_object:
            parts.append(f"for {req.reference_object}")

        dim = req.get_primary_dimension_mm()
        if dim:
            parts.append(f"({dim:.0f}mm)")

        if req.needs_strength:
            parts.append("- heavy duty design")

        return " ".join(parts)


def parse_requirements(text: str) -> ModelRequirements:
    """Convenience function to parse requirements."""
    parser = RequirementsParser()
    return parser.parse(text)
