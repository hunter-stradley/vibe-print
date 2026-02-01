"""
Image Analyzer - Extract dimensions and features from reference images.

Analyzes photos to:
- Detect rulers/scale references and calculate real dimensions
- Measure object widths, heights, and depths
- Extract shape characteristics for model generation
- Identify similar existing designs
"""

import base64
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


@dataclass
class DimensionMeasurement:
    """A measured dimension from an image."""
    dimension_type: str  # "width", "height", "diameter", "depth"
    value_mm: float
    confidence: float  # 0.0 to 1.0
    pixel_value: int
    pixels_per_mm: float
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.dimension_type,
            "value_mm": round(self.value_mm, 1),
            "confidence": round(self.confidence, 2),
            "description": self.description,
        }


@dataclass
class ShapeFeature:
    """Detected shape feature in an image."""
    feature_type: str  # "slot", "hole", "edge", "curve"
    position: Tuple[int, int]  # x, y in pixels
    size_pixels: Tuple[int, int]  # width, height
    size_mm: Optional[Tuple[float, float]] = None
    description: str = ""


@dataclass
class ImageAnalysisResult:
    """Complete analysis result for an image."""
    image_path: Optional[Path]
    analyzed: bool = False
    has_scale_reference: bool = False
    pixels_per_mm: Optional[float] = None

    measurements: List[DimensionMeasurement] = field(default_factory=list)
    features: List[ShapeFeature] = field(default_factory=list)

    # Object detection
    detected_objects: List[str] = field(default_factory=list)
    suggested_category: str = ""

    # For AI analysis
    description: str = ""
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "image_path": str(self.image_path) if self.image_path else None,
            "analyzed": self.analyzed,
            "has_scale_reference": self.has_scale_reference,
            "pixels_per_mm": round(self.pixels_per_mm, 2) if self.pixels_per_mm else None,
            "measurements": [m.to_dict() for m in self.measurements],
            "detected_objects": self.detected_objects,
            "suggested_category": self.suggested_category,
            "description": self.description,
            "notes": self.notes,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    def get_primary_dimension(self) -> Optional[float]:
        """Get the primary measured dimension in mm."""
        if self.measurements:
            # Return highest confidence measurement
            best = max(self.measurements, key=lambda m: m.confidence)
            return best.value_mm
        return None


class ImageAnalyzer:
    """
    Analyzes reference images to extract dimensions for model generation.

    Capabilities:
    - Ruler/scale detection for accurate measurements
    - Object edge detection and measurement
    - Shape feature extraction
    - Size estimation from known objects
    """

    # Known object sizes for reference (mm)
    KNOWN_OBJECT_SIZES = {
        "credit_card": {"width": 85.6, "height": 53.98},
        "us_quarter": {"diameter": 24.26},
        "aa_battery": {"diameter": 14.5, "length": 50.5},
        "usb_a": {"width": 12.0, "height": 4.5},
        "golf_ball": {"diameter": 42.67},
        "tennis_ball": {"diameter": 67.0},
    }

    # Common bottle/tube sizes (diameter in mm)
    COMMON_TUBE_SIZES = {
        "toothpaste_small": 25,
        "toothpaste_large": 35,
        "lotion_small": 45,
        "lotion_medium": 55,
        "lotion_large": 65,
        "shampoo": 55,
        "sunscreen": 40,
    }

    def __init__(self):
        """Initialize analyzer."""
        if not CV2_AVAILABLE:
            print("Warning: OpenCV not available. Install with: pip install opencv-python --break-system-packages")

    def analyze_image(
        self,
        image_path: Path | str,
        known_dimension_mm: Optional[float] = None,
        dimension_type: str = "width",
    ) -> ImageAnalysisResult:
        """
        Analyze an image for dimensions and features.

        Args:
            image_path: Path to image file
            known_dimension_mm: If you know one dimension, provide it for calibration
            dimension_type: What the known dimension represents

        Returns:
            ImageAnalysisResult with measurements and features
        """
        image_path = Path(image_path)
        result = ImageAnalysisResult(image_path=image_path)

        if not image_path.exists():
            result.notes.append(f"Image not found: {image_path}")
            return result

        if not CV2_AVAILABLE:
            result.notes.append("OpenCV not available for image analysis")
            return result

        # Load image
        img = cv2.imread(str(image_path))
        if img is None:
            result.notes.append("Failed to load image")
            return result

        result.analyzed = True

        # Try to detect ruler/scale
        pixels_per_mm = self._detect_ruler(img)
        if pixels_per_mm:
            result.has_scale_reference = True
            result.pixels_per_mm = pixels_per_mm
        elif known_dimension_mm:
            # Use provided dimension for calibration
            pixels_per_mm = self._calibrate_from_known(img, known_dimension_mm)
            result.pixels_per_mm = pixels_per_mm

        # Detect and measure objects
        contours = self._find_main_contours(img)

        for i, contour in enumerate(contours[:5]):  # Analyze top 5 contours
            x, y, w, h = cv2.boundingRect(contour)

            # Calculate real dimensions if we have scale
            if result.pixels_per_mm:
                width_mm = w / result.pixels_per_mm
                height_mm = h / result.pixels_per_mm

                result.measurements.append(DimensionMeasurement(
                    dimension_type="width",
                    value_mm=width_mm,
                    confidence=0.7 if result.has_scale_reference else 0.5,
                    pixel_value=w,
                    pixels_per_mm=result.pixels_per_mm,
                    description=f"Object {i+1} width",
                ))

                result.measurements.append(DimensionMeasurement(
                    dimension_type="height",
                    value_mm=height_mm,
                    confidence=0.7 if result.has_scale_reference else 0.5,
                    pixel_value=h,
                    pixels_per_mm=result.pixels_per_mm,
                    description=f"Object {i+1} height",
                ))

            # Detect shape features
            features = self._detect_features(contour, img)
            result.features.extend(features)

        # Suggest category based on shape
        result.suggested_category = self._suggest_category(result)

        return result

    def _detect_ruler(self, img: np.ndarray) -> Optional[float]:
        """
        Detect ruler markings in image and calculate pixels per mm.

        Looks for regularly spaced lines that indicate ruler graduations.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Find lines
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=20, maxLineGap=5)

        if lines is None:
            return None

        # Look for regularly spaced vertical lines (ruler markings)
        vertical_lines = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.abs(np.arctan2(y2 - y1, x2 - x1))
            if angle > np.pi/4:  # Mostly vertical
                vertical_lines.append((x1 + x2) // 2)  # X center

        if len(vertical_lines) < 3:
            return None

        # Sort and find spacing
        vertical_lines.sort()
        spacings = np.diff(vertical_lines)

        # Find most common spacing (ruler graduation)
        if len(spacings) < 2:
            return None

        # Use median spacing as the graduation interval
        median_spacing = np.median(spacings)

        # Assume 1mm graduations if spacing is small, 5mm or 10mm for larger
        if median_spacing < 20:
            # Likely 1mm marks
            return 1.0 / median_spacing if median_spacing > 0 else None
        elif median_spacing < 50:
            # Likely 5mm marks
            return 5.0 / median_spacing if median_spacing > 0 else None
        else:
            # Likely 10mm (1cm) marks
            return 10.0 / median_spacing if median_spacing > 0 else None

    def _calibrate_from_known(
        self,
        img: np.ndarray,
        known_mm: float,
    ) -> float:
        """Calibrate using a known dimension."""
        # Find the largest contour (assumed to be the known object)
        contours = self._find_main_contours(img)
        if not contours:
            return 1.0  # Fallback

        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)

        # Assume width is the known dimension
        return w / known_mm

    def _find_main_contours(self, img: np.ndarray) -> list:
        """Find main object contours in image."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Threshold
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter by area and sort by size
        min_area = img.shape[0] * img.shape[1] * 0.01  # At least 1% of image
        valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]
        valid_contours.sort(key=cv2.contourArea, reverse=True)

        return valid_contours

    def _detect_features(self, contour, img: np.ndarray) -> List[ShapeFeature]:
        """Detect shape features in a contour."""
        features = []

        # Approximate the contour to find corners/edges
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)

        # Detect if it's a slot (elongated rectangle)
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = max(w, h) / min(w, h) if min(w, h) > 0 else 1

        if aspect_ratio > 2:
            features.append(ShapeFeature(
                feature_type="slot",
                position=(x, y),
                size_pixels=(w, h),
                description="Elongated slot detected",
            ))

        # Detect circular features (holes)
        mask = np.zeros(img.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask, [contour], 0, 255, -1)
        circles = cv2.HoughCircles(
            mask,
            cv2.HOUGH_GRADIENT,
            1,
            20,
            param1=50,
            param2=30,
            minRadius=5,
            maxRadius=100,
        )

        if circles is not None:
            for circle in circles[0]:
                cx, cy, r = circle
                features.append(ShapeFeature(
                    feature_type="hole",
                    position=(int(cx), int(cy)),
                    size_pixels=(int(r*2), int(r*2)),
                    description=f"Circular feature, radius {r:.0f}px",
                ))

        return features

    def _suggest_category(self, result: ImageAnalysisResult) -> str:
        """Suggest object category based on detected features."""
        has_slot = any(f.feature_type == "slot" for f in result.features)
        has_hole = any(f.feature_type == "hole" for f in result.features)

        if has_slot:
            return "tube_squeezer"
        if has_hole:
            return "holder"

        return "custom"

    def measure_from_ruler_image(
        self,
        image_path: Path | str,
        ruler_unit: str = "mm",
        ruler_divisions: int = 10,
    ) -> ImageAnalysisResult:
        """
        Measure objects in an image that includes a ruler.

        Args:
            image_path: Path to image with ruler visible
            ruler_unit: Unit of ruler divisions (mm, cm, inch)
            ruler_divisions: Number of divisions visible on ruler

        Returns:
            ImageAnalysisResult with calibrated measurements
        """
        result = self.analyze_image(image_path)

        # If ruler was detected, measurements are already calibrated
        if result.has_scale_reference:
            result.notes.append(f"Ruler detected. Calibrated at {result.pixels_per_mm:.2f} px/mm")
        else:
            result.notes.append("No ruler detected. Measurements are estimates.")

        return result

    def estimate_bottle_size(
        self,
        image_path: Path | str,
        bottle_type: str = "lotion",
    ) -> Optional[float]:
        """
        Estimate bottle diameter from image using common bottle size heuristics.

        Args:
            image_path: Path to image of bottle
            bottle_type: Type hint (lotion, toothpaste, shampoo)

        Returns:
            Estimated diameter in mm or None
        """
        # Analyze the image
        result = self.analyze_image(image_path)

        if not result.measurements:
            return None

        # Get largest width measurement
        widths = [m for m in result.measurements if m.dimension_type == "width"]
        if not widths:
            return None

        # Use the largest width
        max_width = max(widths, key=lambda m: m.value_mm)

        # If we have scale reference, trust the measurement
        if result.has_scale_reference:
            return max_width.value_mm

        # Otherwise, use heuristics based on bottle type
        type_hints = {
            "lotion": 55.0,
            "toothpaste": 30.0,
            "shampoo": 55.0,
            "sunscreen": 40.0,
        }

        return type_hints.get(bottle_type.lower(), 50.0)


def analyze_reference_image(image_path: Path | str) -> ImageAnalysisResult:
    """Convenience function to analyze an image."""
    analyzer = ImageAnalyzer()
    return analyzer.analyze_image(image_path)
