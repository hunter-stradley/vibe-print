"""Camera monitoring and defect detection modules."""

from bambustudio_mcp.camera.stream import CameraStream, CapturedFrame
from bambustudio_mcp.camera.detector import DefectDetector, DetectionResult, DefectType

__all__ = [
    "CameraStream",
    "CapturedFrame",
    "DefectDetector",
    "DetectionResult",
    "DefectType",
]
