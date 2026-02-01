"""
Defect Detection Module - Vision-based print quality analysis.

Analyzes camera frames to detect common 3D printing defects.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from vibe_print.camera.stream import CapturedFrame


class DefectType(str, Enum):
    """Types of detectable print defects."""
    LAYER_SHIFT = "layer_shift"
    STRINGING = "stringing"
    WARPING = "warping"
    BLOB = "blob"
    UNDER_EXTRUSION = "under_extrusion"
    OVER_EXTRUSION = "over_extrusion"
    POOR_ADHESION = "poor_adhesion"
    SPAGHETTI = "spaghetti"  # Failed print with messy filament
    NOZZLE_CLOG = "nozzle_clog"
    LAYER_SEPARATION = "layer_separation"


class Severity(str, Enum):
    """Defect severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class DetectedDefect:
    """A detected print defect."""
    defect_type: DefectType
    severity: Severity
    confidence: float  # 0.0 to 1.0
    description: str
    location: Optional[Tuple[int, int, int, int]] = None  # x, y, width, height
    suggested_fix: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.defect_type.value,
            "severity": self.severity.value,
            "confidence": round(self.confidence, 2),
            "description": self.description,
            "location": self.location,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class DetectionResult:
    """Result of defect detection analysis."""
    timestamp: datetime
    frame_analyzed: bool
    defects: List[DetectedDefect] = field(default_factory=list)
    print_quality_score: float = 100.0  # 0-100, 100 = perfect
    analysis_notes: List[str] = field(default_factory=list)

    @property
    def has_critical_defects(self) -> bool:
        """Check if any critical defects were found."""
        return any(d.severity == Severity.CRITICAL for d in self.defects)

    @property
    def should_pause(self) -> bool:
        """Check if print should be paused."""
        return self.has_critical_defects or self.print_quality_score < 30

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "frame_analyzed": self.frame_analyzed,
            "defects": [d.to_dict() for d in self.defects],
            "defect_count": len(self.defects),
            "print_quality_score": round(self.print_quality_score, 1),
            "has_critical_defects": self.has_critical_defects,
            "should_pause": self.should_pause,
            "analysis_notes": self.analysis_notes,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def get_summary(self) -> str:
        """Get human-readable summary."""
        lines = [f"Print Quality Score: {self.print_quality_score:.0f}/100"]

        if not self.defects:
            lines.append("No defects detected ✓")
        else:
            lines.append(f"Defects found: {len(self.defects)}")
            for defect in self.defects:
                icon = "🔴" if defect.severity == Severity.CRITICAL else "🟡" if defect.severity == Severity.WARNING else "🔵"
                lines.append(f"  {icon} {defect.defect_type.value}: {defect.description}")
                if defect.suggested_fix:
                    lines.append(f"     → Fix: {defect.suggested_fix}")

        if self.should_pause:
            lines.append("\n⚠️ RECOMMEND PAUSING PRINT")

        return "\n".join(lines)


class DefectDetector:
    """
    Vision-based defect detection for 3D prints.

    Uses computer vision techniques to analyze camera frames
    and detect common printing issues.
    """

    def __init__(self):
        """Initialize detector."""
        if not CV2_AVAILABLE:
            raise ImportError(
                "OpenCV required for defect detection. "
                "Install with: pip install opencv-python --break-system-packages"
            )

        self._reference_frame: Optional[np.ndarray] = None
        self._last_frame: Optional[np.ndarray] = None
        self._baseline_set = False

    def set_reference_frame(self, frame: CapturedFrame) -> None:
        """
        Set reference frame for comparison (e.g., empty bed or first layer).

        Args:
            frame: Reference frame to compare against
        """
        self._reference_frame = frame.to_numpy()
        self._baseline_set = True

    def analyze_frame(self, frame: CapturedFrame) -> DetectionResult:
        """
        Analyze a frame for defects.

        Args:
            frame: Frame to analyze

        Returns:
            DetectionResult with detected defects
        """
        result = DetectionResult(
            timestamp=datetime.now(),
            frame_analyzed=True,
        )

        img = frame.to_numpy()
        if img is None:
            result.frame_analyzed = False
            result.analysis_notes.append("Failed to decode frame")
            return result

        defects = []
        notes = []

        # Run detection algorithms
        defects.extend(self._detect_spaghetti(img))
        defects.extend(self._detect_layer_shift(img))
        defects.extend(self._detect_stringing(img))
        defects.extend(self._detect_warping(img))
        defects.extend(self._detect_blob(img))

        # Motion detection (if we have previous frame)
        if self._last_frame is not None:
            motion_defects, motion_notes = self._analyze_motion(self._last_frame, img)
            defects.extend(motion_defects)
            notes.extend(motion_notes)

        self._last_frame = img.copy()

        # Calculate quality score
        quality_score = self._calculate_quality_score(defects)

        result.defects = defects
        result.print_quality_score = quality_score
        result.analysis_notes = notes

        return result

    def _detect_spaghetti(self, img: np.ndarray) -> List[DetectedDefect]:
        """
        Detect spaghetti failure (messy filament everywhere).

        Uses edge detection and contour analysis to find chaotic patterns.
        """
        defects = []

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Spaghetti often has many small, irregular contours
        small_contours = [c for c in contours if 10 < cv2.contourArea(c) < 500]

        if len(small_contours) > 100:  # Threshold for "too many" small contours
            # Check distribution - spaghetti is usually spread out
            if self._is_distributed(small_contours, img.shape):
                defects.append(DetectedDefect(
                    defect_type=DefectType.SPAGHETTI,
                    severity=Severity.CRITICAL,
                    confidence=min(0.9, len(small_contours) / 200),
                    description="Possible spaghetti failure detected - chaotic filament pattern",
                    suggested_fix="Stop print immediately. Check bed adhesion and first layer settings.",
                ))

        return defects

    def _detect_layer_shift(self, img: np.ndarray) -> List[DetectedDefect]:
        """
        Detect layer shifting.

        Looks for horizontal discontinuities in vertical edges.
        """
        defects = []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Detect vertical edges (which would show horizontal shifts)
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_x = np.abs(sobel_x)

        # Sum along columns to find horizontal patterns
        col_sums = np.sum(sobel_x, axis=0)

        # Look for sudden changes that might indicate layer shift
        col_diff = np.abs(np.diff(col_sums))
        threshold = np.mean(col_diff) + 2 * np.std(col_diff)

        shifts = np.where(col_diff > threshold)[0]

        if len(shifts) > 5:  # Multiple potential shifts
            defects.append(DetectedDefect(
                defect_type=DefectType.LAYER_SHIFT,
                severity=Severity.WARNING,
                confidence=0.6,
                description="Possible layer shift detected",
                suggested_fix="Check belt tension and ensure printer is on stable surface.",
            ))

        return defects

    def _detect_stringing(self, img: np.ndarray) -> List[DetectedDefect]:
        """
        Detect stringing/oozing.

        Looks for thin vertical lines between print features.
        """
        defects = []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Enhance thin vertical features
        kernel = np.array([[-1, 2, -1],
                          [-1, 2, -1],
                          [-1, 2, -1]], dtype=np.float32)
        filtered = cv2.filter2D(gray, -1, kernel)

        # Threshold to find thin lines
        _, thresh = cv2.threshold(filtered, 30, 255, cv2.THRESH_BINARY)

        # Find vertical line segments
        lines = cv2.HoughLinesP(thresh, 1, np.pi/180, 20, minLineLength=20, maxLineGap=5)

        if lines is not None:
            vertical_lines = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = np.abs(np.arctan2(y2 - y1, x2 - x1))
                if angle > np.pi/4:  # Mostly vertical
                    vertical_lines.append(line)

            if len(vertical_lines) > 10:
                defects.append(DetectedDefect(
                    defect_type=DefectType.STRINGING,
                    severity=Severity.INFO,
                    confidence=min(0.8, len(vertical_lines) / 30),
                    description=f"Stringing detected ({len(vertical_lines)} strings)",
                    suggested_fix="Increase retraction distance/speed or lower nozzle temperature.",
                ))

        return defects

    def _detect_warping(self, img: np.ndarray) -> List[DetectedDefect]:
        """
        Detect bed warping/lifting.

        Looks for curved edges at the bottom of the print.
        """
        defects = []

        # Focus on bottom third of image (where bed/first layers are)
        h = img.shape[0]
        bottom_region = img[int(2*h/3):, :]

        gray = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        # Find contours in bottom region
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            if cv2.contourArea(contour) < 100:
                continue

            # Fit ellipse to detect curved shapes
            if len(contour) >= 5:
                try:
                    ellipse = cv2.fitEllipse(contour)
                    (cx, cy), (MA, ma), angle = ellipse

                    # Warping typically shows as horizontal curves
                    if 60 < angle < 120 and MA / (ma + 0.01) > 3:
                        defects.append(DetectedDefect(
                            defect_type=DefectType.WARPING,
                            severity=Severity.WARNING,
                            confidence=0.5,
                            description="Possible corner warping detected",
                            location=(int(cx), int(cy + 2*h/3), int(MA), int(ma)),
                            suggested_fix="Increase bed temperature, add brim, or use enclosure.",
                        ))
                        break
                except cv2.error:
                    continue

        return defects

    def _detect_blob(self, img: np.ndarray) -> List[DetectedDefect]:
        """
        Detect blobs/zits on print surface.

        Looks for small bright spots that indicate over-extrusion points.
        """
        defects = []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Blob detection parameters
        params = cv2.SimpleBlobDetector_Params()
        params.filterByArea = True
        params.minArea = 20
        params.maxArea = 500
        params.filterByCircularity = True
        params.minCircularity = 0.5
        params.filterByConvexity = True
        params.minConvexity = 0.5

        detector = cv2.SimpleBlobDetector_create(params)
        keypoints = detector.detect(gray)

        if len(keypoints) > 5:
            defects.append(DetectedDefect(
                defect_type=DefectType.BLOB,
                severity=Severity.INFO,
                confidence=min(0.7, len(keypoints) / 15),
                description=f"Blobs/zits detected ({len(keypoints)} spots)",
                suggested_fix="Enable coasting, adjust retraction, or lower nozzle temperature.",
            ))

        return defects

    def _analyze_motion(
        self,
        prev_frame: np.ndarray,
        curr_frame: np.ndarray,
    ) -> Tuple[List[DetectedDefect], List[str]]:
        """
        Analyze motion between frames.

        Can detect if print is progressing normally.
        """
        defects = []
        notes = []

        # Calculate frame difference
        diff = cv2.absdiff(prev_frame, curr_frame)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

        # Threshold
        _, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
        motion_pixels = np.sum(thresh > 0)

        total_pixels = thresh.shape[0] * thresh.shape[1]
        motion_ratio = motion_pixels / total_pixels

        if motion_ratio < 0.001:
            notes.append("Very little motion detected - print may be stalled")
        elif motion_ratio > 0.3:
            notes.append("High motion detected - possible print failure")
            defects.append(DetectedDefect(
                defect_type=DefectType.SPAGHETTI,
                severity=Severity.WARNING,
                confidence=0.5,
                description="Abnormally high motion detected between frames",
                suggested_fix="Check print visually for failures.",
            ))

        return defects, notes

    def _is_distributed(self, contours: list, img_shape: tuple) -> bool:
        """Check if contours are distributed across the image (spaghetti pattern)."""
        if not contours:
            return False

        # Get centroids
        centroids = []
        for c in contours:
            M = cv2.moments(c)
            if M["m00"] > 0:
                centroids.append((M["m10"]/M["m00"], M["m01"]/M["m00"]))

        if len(centroids) < 10:
            return False

        # Check spread
        xs = [c[0] for c in centroids]
        ys = [c[1] for c in centroids]

        x_spread = (max(xs) - min(xs)) / img_shape[1]
        y_spread = (max(ys) - min(ys)) / img_shape[0]

        return x_spread > 0.3 and y_spread > 0.3

    def _calculate_quality_score(self, defects: List[DetectedDefect]) -> float:
        """Calculate overall print quality score based on defects."""
        score = 100.0

        for defect in defects:
            # Deduct based on severity and confidence
            if defect.severity == Severity.CRITICAL:
                score -= 40 * defect.confidence
            elif defect.severity == Severity.WARNING:
                score -= 20 * defect.confidence
            else:  # INFO
                score -= 5 * defect.confidence

        return max(0.0, score)


# Convenience function for single-frame analysis
def quick_analyze(frame: CapturedFrame) -> DetectionResult:
    """Quick analysis of a single frame."""
    detector = DefectDetector()
    return detector.analyze_frame(frame)
