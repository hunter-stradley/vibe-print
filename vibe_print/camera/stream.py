"""
Camera Stream Module - RTSPS camera capture for Bambu printers.

Captures frames from the printer's camera for monitoring and analysis.
"""

import asyncio
import base64
import io
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Generator, Tuple
import subprocess

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

from vibe_print.config import config


@dataclass
class CapturedFrame:
    """A captured camera frame with metadata."""
    frame_data: bytes  # JPEG encoded
    timestamp: datetime
    width: int
    height: int
    frame_number: int

    def save(self, path: Path | str) -> Path:
        """Save frame to file."""
        path = Path(path)
        with open(path, "wb") as f:
            f.write(self.frame_data)
        return path

    def to_base64(self) -> str:
        """Convert to base64 string for embedding."""
        return base64.b64encode(self.frame_data).decode("utf-8")

    def to_numpy(self) -> Optional["np.ndarray"]:
        """Convert to numpy array for OpenCV processing."""
        if not CV2_AVAILABLE:
            return None
        nparr = np.frombuffer(self.frame_data, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)


class CameraStream:
    """
    RTSPS camera stream capture for Bambu Lab printers.

    The A1/A1 Mini provides camera feed at 1 FPS via RTSPS on port 322.
    URL format: rtsps://bblp:{access_code}@{ip}:322/streaming/live/1
    """

    def __init__(
        self,
        host: Optional[str] = None,
        access_code: Optional[str] = None,
        port: int = 322,
    ):
        """
        Initialize camera stream.

        Args:
            host: Printer IP address
            access_code: Printer access code
            port: RTSPS port (default 322)
        """
        self.host = host or config.printer.ip_address
        self.access_code = access_code or config.printer.access_code
        self.port = port

        self._capture = None
        self._frame_count = 0
        self._last_frame: Optional[CapturedFrame] = None

    @property
    def rtsp_url(self) -> str:
        """Get the RTSPS URL for the camera."""
        return f"rtsps://bblp:{self.access_code}@{self.host}:{self.port}/streaming/live/1"

    def is_available(self) -> Tuple[bool, str]:
        """
        Check if camera stream is available.

        Returns:
            Tuple of (available, message)
        """
        if not CV2_AVAILABLE:
            return False, "OpenCV (cv2) not installed. Install with: pip install opencv-python --break-system-packages"

        if not self.host or not self.access_code:
            return False, "Printer IP and access code required for camera access"

        return True, "Camera stream should be available"

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Connect to the camera stream.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            True if connected successfully
        """
        if not CV2_AVAILABLE:
            raise ImportError("OpenCV required for camera streaming")

        # OpenCV VideoCapture for RTSP
        # Note: RTSPS with self-signed certs may need ffmpeg backend
        self._capture = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

        # Set buffer size to minimize latency
        self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Wait for connection
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            if self._capture.isOpened():
                # Try to read a frame
                ret, _ = self._capture.read()
                if ret:
                    return True
            await asyncio.sleep(0.5)

        return False

    async def disconnect(self) -> None:
        """Disconnect from camera stream."""
        if self._capture:
            self._capture.release()
            self._capture = None

    async def capture_frame(self) -> Optional[CapturedFrame]:
        """
        Capture a single frame from the camera.

        Returns:
            CapturedFrame or None if capture failed
        """
        if not self._capture or not self._capture.isOpened():
            return None

        # Read frame
        ret, frame = self._capture.read()
        if not ret or frame is None:
            return None

        self._frame_count += 1

        # Encode to JPEG
        success, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not success:
            return None

        captured = CapturedFrame(
            frame_data=buffer.tobytes(),
            timestamp=datetime.now(),
            width=frame.shape[1],
            height=frame.shape[0],
            frame_number=self._frame_count,
        )

        self._last_frame = captured
        return captured

    async def capture_frames(
        self,
        count: int = 5,
        interval: float = 1.0,
    ) -> list[CapturedFrame]:
        """
        Capture multiple frames.

        Args:
            count: Number of frames to capture
            interval: Seconds between frames

        Returns:
            List of captured frames
        """
        frames = []

        for _ in range(count):
            frame = await self.capture_frame()
            if frame:
                frames.append(frame)
            await asyncio.sleep(interval)

        return frames

    def get_last_frame(self) -> Optional[CapturedFrame]:
        """Get the most recently captured frame."""
        return self._last_frame

    async def capture_to_file(
        self,
        output_path: Path | str,
        count: int = 1,
    ) -> list[Path]:
        """
        Capture frames and save to files.

        Args:
            output_path: Output directory or file path
            count: Number of frames to capture

        Returns:
            List of saved file paths
        """
        output_path = Path(output_path)

        if count == 1:
            # Single frame
            frame = await self.capture_frame()
            if frame:
                if output_path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                    return [frame.save(output_path)]
                else:
                    output_path.mkdir(parents=True, exist_ok=True)
                    return [frame.save(output_path / f"frame_{frame.frame_number}.jpg")]
            return []

        # Multiple frames
        output_path.mkdir(parents=True, exist_ok=True)
        saved_paths = []

        for i in range(count):
            frame = await self.capture_frame()
            if frame:
                path = output_path / f"frame_{frame.frame_number:04d}.jpg"
                frame.save(path)
                saved_paths.append(path)
            await asyncio.sleep(1.0)  # A1 is 1 FPS

        return saved_paths


class FrameBuffer:
    """
    Rolling buffer of recent frames for comparison and analysis.
    """

    def __init__(self, max_frames: int = 30):
        """
        Initialize frame buffer.

        Args:
            max_frames: Maximum frames to keep
        """
        self.max_frames = max_frames
        self._frames: list[CapturedFrame] = []

    def add(self, frame: CapturedFrame) -> None:
        """Add a frame to the buffer."""
        self._frames.append(frame)
        if len(self._frames) > self.max_frames:
            self._frames.pop(0)

    def get_recent(self, count: int = 5) -> list[CapturedFrame]:
        """Get the most recent frames."""
        return self._frames[-count:]

    def get_all(self) -> list[CapturedFrame]:
        """Get all buffered frames."""
        return list(self._frames)

    def clear(self) -> None:
        """Clear the buffer."""
        self._frames.clear()

    @property
    def count(self) -> int:
        """Number of frames in buffer."""
        return len(self._frames)


# Fallback capture using ffmpeg directly (if OpenCV fails with RTSPS)
async def capture_with_ffmpeg(
    host: str,
    access_code: str,
    output_path: Path,
    duration: int = 5,
) -> bool:
    """
    Capture using ffmpeg directly (fallback for RTSPS issues).

    Args:
        host: Printer IP
        access_code: Access code
        output_path: Output file path (video or image)
        duration: Capture duration in seconds

    Returns:
        True if successful
    """
    url = f"rtsps://bblp:{access_code}@{host}:322/streaming/live/1"

    cmd = [
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-i", url,
        "-t", str(duration),
        "-y",  # Overwrite
    ]

    if output_path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
        # Single frame
        cmd.extend(["-vframes", "1", str(output_path)])
    else:
        # Video
        cmd.extend(["-c", "copy", str(output_path)])

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            timeout=duration + 10,
        )
        return result.returncode == 0 and output_path.exists()
    except Exception:
        return False
