"""
Novice Term Parser - Translates layperson language to CAD parameters.

Handles common phrases and descriptions from users who aren't familiar
with 3D printing terminology, converting them to precise parameters.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple, Set


class StrengthLevel(str, Enum):
    """Strength requirements parsed from description."""
    LIGHT = "light"        # Decorative, minimal stress
    MEDIUM = "medium"      # Normal use
    HEAVY = "heavy"        # Heavy duty, high stress
    EXTREME = "extreme"    # Industrial, maximum strength


class FitType(str, Enum):
    """How parts should fit together."""
    PRESS = "press"        # Force together, won't come apart
    TIGHT = "tight"        # Snug, stays put
    SNUG = "snug"          # Comfortable fit, can adjust
    SLIDING = "sliding"    # Moves freely
    LOOSE = "loose"        # Easy on/off


class SizeCategory(str, Enum):
    """Relative size of the object."""
    TINY = "tiny"          # Under 20mm
    SMALL = "small"        # 20-50mm
    MEDIUM = "medium"      # 50-150mm
    LARGE = "large"        # 150-250mm
    HUGE = "huge"          # Over 250mm


@dataclass
class ParsedIntent:
    """Structured interpretation of user's description."""
    # Core parameters
    strength: StrengthLevel = StrengthLevel.MEDIUM
    fit_type: FitType = FitType.SNUG
    size_category: SizeCategory = SizeCategory.MEDIUM

    # Extracted dimensions (if mentioned)
    dimensions: Dict[str, float] = field(default_factory=dict)

    # Inferred parameters
    wall_thickness_mm: float = 2.0
    clearance_mm: float = 0.3
    infill_percent: int = 20
    layer_height_mm: float = 0.2

    # Material suggestions
    suggested_materials: List[str] = field(default_factory=list)

    # Features detected
    needs_grip: bool = False
    needs_flex: bool = False
    waterproof: bool = False
    heat_resistant: bool = False

    # Confidence in parsing
    confidence: float = 0.8
    clarifying_questions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strength": self.strength.value,
            "fit_type": self.fit_type.value,
            "size_category": self.size_category.value,
            "dimensions": self.dimensions,
            "wall_thickness_mm": self.wall_thickness_mm,
            "clearance_mm": self.clearance_mm,
            "infill_percent": self.infill_percent,
            "layer_height_mm": self.layer_height_mm,
            "suggested_materials": self.suggested_materials,
            "needs_grip": self.needs_grip,
            "needs_flex": self.needs_flex,
            "waterproof": self.waterproof,
            "heat_resistant": self.heat_resistant,
            "confidence": self.confidence,
            "clarifying_questions": self.clarifying_questions,
        }


class NoviceTermParser:
    """
    Parses layperson descriptions into technical parameters.

    Handles common phrases like:
    - "thick walls" → wall_thickness = 2.5-3mm
    - "heavy duty" → increased infill, more walls
    - "snug fit" → clearance = 0.2-0.3mm
    - "loose fit" → clearance = 0.8-1.0mm
    """

    # Strength indicators
    STRENGTH_TERMS = {
        StrengthLevel.LIGHT: {
            "light", "decorative", "display", "gentle", "delicate",
            "thin", "minimal", "basic", "simple",
        },
        StrengthLevel.MEDIUM: {
            "normal", "standard", "everyday", "regular", "typical",
            "moderate", "balanced",
        },
        StrengthLevel.HEAVY: {
            "heavy", "strong", "sturdy", "robust", "durable",
            "tough", "solid", "heavy-duty", "heavy duty", "rugged",
            "industrial", "reinforced", "thick",
        },
        StrengthLevel.EXTREME: {
            "extreme", "maximum", "industrial-grade", "unbreakable",
            "bulletproof", "indestructible", "super strong",
        },
    }

    # Fit type indicators
    FIT_TERMS = {
        FitType.PRESS: {
            "press fit", "press-fit", "permanent", "force", "forced",
            "interference", "won't come off", "stays put forever",
        },
        FitType.TIGHT: {
            "tight", "snug fit", "secure", "grip", "grips",
            "firm", "holds", "doesn't move", "friction fit",
        },
        FitType.SNUG: {
            "snug", "comfortable", "nice fit", "good fit",
            "stays in place", "adjustable", "removable",
        },
        FitType.SLIDING: {
            "sliding", "slides", "moves", "glides", "smooth",
            "easy to move", "adjusts", "repositioning",
        },
        FitType.LOOSE: {
            "loose", "easy", "falls off", "drops in", "quick",
            "quick release", "easy on off", "easy to remove",
        },
    }

    # Size terms (when no explicit dimension given)
    SIZE_TERMS = {
        SizeCategory.TINY: {
            "tiny", "miniature", "micro", "mini", "very small",
            "keychain", "earring", "button",
        },
        SizeCategory.SMALL: {
            "small", "compact", "little", "pocket", "palm-sized",
            "handheld", "portable",
        },
        SizeCategory.MEDIUM: {
            "medium", "normal", "standard", "average", "regular",
            "typical", "moderate",
        },
        SizeCategory.LARGE: {
            "large", "big", "sizeable", "substantial", "hefty",
        },
        SizeCategory.HUGE: {
            "huge", "massive", "giant", "oversized", "extra large",
            "xl", "xxl",
        },
    }

    # Feature indicators
    FEATURE_TERMS = {
        "needs_grip": {
            "grip", "texture", "textured", "ridges", "ridged",
            "non-slip", "non slip", "grippy", "handle", "ergonomic",
        },
        "needs_flex": {
            "flexible", "bendy", "flex", "soft", "rubbery",
            "elastic", "spring", "bouncy",
        },
        "waterproof": {
            "waterproof", "water-proof", "watertight", "water tight",
            "sealed", "bathroom", "outdoor", "wet",
        },
        "heat_resistant": {
            "heat", "hot", "temperature", "oven", "microwave",
            "dishwasher", "boiling", "steam",
        },
    }

    # Dimension patterns
    DIMENSION_PATTERNS = [
        # "65mm diameter" or "65 mm diameter"
        (r'(\d+(?:\.\d+)?)\s*mm\s*(diameter|wide|width|long|length|tall|height|thick|deep|depth)',
         lambda m: (m.group(2).lower().replace('wide', 'width').replace('long', 'length')
                   .replace('tall', 'height').replace('thick', 'thickness').replace('deep', 'depth'),
                   float(m.group(1)))),

        # "diameter of 65mm" or "width of 65 mm"
        (r'(diameter|width|length|height|thickness|depth)\s*(?:of|is|:)?\s*(\d+(?:\.\d+)?)\s*mm',
         lambda m: (m.group(1).lower(), float(m.group(2)))),

        # "about 65mm" (assumes primary dimension)
        (r'about\s+(\d+(?:\.\d+)?)\s*mm',
         lambda m: ('primary', float(m.group(1)))),

        # "2.5 inches" or "2.5 inch"
        (r'(\d+(?:\.\d+)?)\s*inch(?:es)?\s*(diameter|wide|width|long|length|tall|height)?',
         lambda m: ((m.group(2) or 'primary').lower().replace('wide', 'width')
                   .replace('long', 'length').replace('tall', 'height'),
                   float(m.group(1)) * 25.4)),

        # Just "65mm" in context
        (r'(\d+(?:\.\d+)?)\s*mm\b(?!\s*(?:nozzle|layer|thick))',
         lambda m: ('primary', float(m.group(1)))),

        # "~65mm" approximate
        (r'[~≈]\s*(\d+(?:\.\d+)?)\s*mm',
         lambda m: ('primary', float(m.group(1)))),
    ]

    # Material suggestions based on features
    MATERIAL_SUGGESTIONS = {
        "waterproof": ["PETG", "ASA"],
        "heat_resistant": ["PC", "PETG", "ABS"],
        "needs_flex": ["TPU 95A", "TPU"],
        "general": ["PLA", "Bambu Basic PLA"],
    }

    def __init__(self):
        self.parsed: Optional[ParsedIntent] = None

    def parse(self, description: str) -> ParsedIntent:
        """
        Parse a natural language description into structured parameters.

        Args:
            description: User's description in plain language

        Returns:
            ParsedIntent with extracted parameters
        """
        text = description.lower()
        self.parsed = ParsedIntent()

        # Extract dimensions first
        self._extract_dimensions(text)

        # Determine strength level
        self._extract_strength(text)

        # Determine fit type
        self._extract_fit_type(text)

        # Determine size category (if not explicit)
        self._extract_size(text)

        # Extract features
        self._extract_features(text)

        # Suggest materials
        self._suggest_materials()

        # Calculate derived parameters
        self._calculate_parameters()

        # Generate clarifying questions if needed
        self._generate_questions(text)

        return self.parsed

    def _extract_dimensions(self, text: str) -> None:
        """Extract explicit dimensions from text."""
        for pattern, extractor in self.DIMENSION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    dim_type, value = extractor(match)
                    self.parsed.dimensions[dim_type] = value
                except (ValueError, IndexError):
                    continue

        # Infer size category from dimensions
        if 'primary' in self.parsed.dimensions:
            size = self.parsed.dimensions['primary']
            if size < 20:
                self.parsed.size_category = SizeCategory.TINY
            elif size < 50:
                self.parsed.size_category = SizeCategory.SMALL
            elif size < 150:
                self.parsed.size_category = SizeCategory.MEDIUM
            elif size < 250:
                self.parsed.size_category = SizeCategory.LARGE
            else:
                self.parsed.size_category = SizeCategory.HUGE

    def _extract_strength(self, text: str) -> None:
        """Extract strength requirements from text."""
        words = set(text.split())

        # Check each strength level
        for level, terms in self.STRENGTH_TERMS.items():
            if words & terms or any(term in text for term in terms if ' ' in term):
                self.parsed.strength = level
                break

    def _extract_fit_type(self, text: str) -> None:
        """Extract fit type from text."""
        # Check multi-word phrases first
        for fit, terms in self.FIT_TERMS.items():
            for term in terms:
                if ' ' in term and term in text:
                    self.parsed.fit_type = fit
                    return

        # Then single words
        words = set(text.split())
        for fit, terms in self.FIT_TERMS.items():
            single_terms = {t for t in terms if ' ' not in t}
            if words & single_terms:
                self.parsed.fit_type = fit
                return

    def _extract_size(self, text: str) -> None:
        """Extract size category from text if not from dimensions."""
        if self.parsed.dimensions:
            return  # Already set from dimensions

        words = set(text.split())
        for size, terms in self.SIZE_TERMS.items():
            if words & terms:
                self.parsed.size_category = size
                break

    def _extract_features(self, text: str) -> None:
        """Extract feature requirements from text."""
        for feature, terms in self.FEATURE_TERMS.items():
            if any(term in text for term in terms):
                setattr(self.parsed, feature, True)

    def _suggest_materials(self) -> None:
        """Suggest materials based on extracted features."""
        suggestions = set()

        if self.parsed.needs_flex:
            suggestions.update(self.MATERIAL_SUGGESTIONS["needs_flex"])
        elif self.parsed.waterproof:
            suggestions.update(self.MATERIAL_SUGGESTIONS["waterproof"])
        elif self.parsed.heat_resistant:
            suggestions.update(self.MATERIAL_SUGGESTIONS["heat_resistant"])
        else:
            suggestions.update(self.MATERIAL_SUGGESTIONS["general"])

        self.parsed.suggested_materials = list(suggestions)

    def _calculate_parameters(self) -> None:
        """Calculate derived parameters from parsed intent."""
        # Wall thickness based on strength
        wall_map = {
            StrengthLevel.LIGHT: 1.2,
            StrengthLevel.MEDIUM: 2.0,
            StrengthLevel.HEAVY: 3.0,
            StrengthLevel.EXTREME: 4.0,
        }
        self.parsed.wall_thickness_mm = wall_map[self.parsed.strength]

        # Clearance based on fit type
        clearance_map = {
            FitType.PRESS: 0.0,
            FitType.TIGHT: 0.15,
            FitType.SNUG: 0.3,
            FitType.SLIDING: 0.5,
            FitType.LOOSE: 1.0,
        }
        self.parsed.clearance_mm = clearance_map[self.parsed.fit_type]

        # Infill based on strength
        infill_map = {
            StrengthLevel.LIGHT: 15,
            StrengthLevel.MEDIUM: 20,
            StrengthLevel.HEAVY: 30,
            StrengthLevel.EXTREME: 50,
        }
        self.parsed.infill_percent = infill_map[self.parsed.strength]

        # Layer height based on size (smaller = finer detail often wanted)
        layer_map = {
            SizeCategory.TINY: 0.12,
            SizeCategory.SMALL: 0.16,
            SizeCategory.MEDIUM: 0.20,
            SizeCategory.LARGE: 0.24,
            SizeCategory.HUGE: 0.28,
        }
        self.parsed.layer_height_mm = layer_map[self.parsed.size_category]

    def _generate_questions(self, text: str) -> None:
        """Generate clarifying questions for ambiguous cases."""
        questions = []

        # If no dimensions found
        if not self.parsed.dimensions:
            questions.append(
                "What are the dimensions? (e.g., '65mm diameter' or 'about 2 inches wide')"
            )

        # If strength seems contradictory
        if self.parsed.strength == StrengthLevel.HEAVY and self.parsed.needs_flex:
            questions.append(
                "You mentioned both 'heavy duty' and 'flexible' - which is more important?"
            )

        # If fit type unclear
        if 'fit' not in text and self.parsed.fit_type == FitType.SNUG:
            questions.append(
                "How should it fit? (snug/tight for staying in place, loose for easy removal)"
            )

        self.parsed.clarifying_questions = questions
        self.parsed.confidence = max(0.5, 1.0 - len(questions) * 0.15)


def parse_novice_description(description: str) -> Dict[str, Any]:
    """
    Convenience function to parse a novice description.

    Args:
        description: Plain language description from user

    Returns:
        Dictionary with parsed parameters and suggestions
    """
    parser = NoviceTermParser()
    result = parser.parse(description)
    return result.to_dict()


# Common phrase translations for documentation/help
PHRASE_TRANSLATIONS = {
    # Strength phrases
    "heavy duty": "Wall thickness: 3mm, Infill: 30%, 4+ perimeters",
    "super strong": "Wall thickness: 4mm, Infill: 50%, 5+ perimeters",
    "thick walls": "Wall thickness: 2.5-3mm",
    "thin walls": "Wall thickness: 1.2mm (minimum safe)",

    # Fit phrases
    "snug fit": "Clearance: 0.2-0.3mm (holds but removable)",
    "tight fit": "Clearance: 0.1-0.15mm (friction fit)",
    "press fit": "Clearance: 0mm or slight interference",
    "loose fit": "Clearance: 0.8-1.0mm (easy on/off)",

    # Quality phrases
    "smooth surface": "Layer height: 0.12-0.16mm, slower outer walls",
    "quick print": "Layer height: 0.24-0.28mm, draft settings",
    "high detail": "Layer height: 0.08-0.12mm, 0.2mm nozzle recommended",

    # Feature phrases
    "waterproof": "Use PETG or ASA, increase perimeters, vase mode if possible",
    "heat resistant": "Use PC or PETG, not PLA",
    "flexible": "Use TPU, reduce infill for more flex",
    "grippy": "Add grip texture, use TPU for extra grip",
}
