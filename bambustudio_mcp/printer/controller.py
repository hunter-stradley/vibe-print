"""
Printer Controller - High-level print job management.

Provides methods for submitting jobs, controlling prints, and monitoring.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Awaitable

from bambustudio_mcp.printer.mqtt_client import BambuMQTTClient
from bambustudio_mcp.printer.status import PrinterStatus, PrinterState


@dataclass
class PrintJob:
    """Represents a print job."""
    job_id: str
    file_path: Path
    file_name: str
    submitted_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, printing, paused, completed, failed, cancelled
    progress_percent: float = 0.0
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "file_name": self.file_name,
            "submitted_at": self.submitted_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "progress_percent": round(self.progress_percent, 1),
            "error_message": self.error_message,
        }


class PrinterController:
    """
    High-level printer control interface.

    Manages print jobs, provides control commands, and status monitoring.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        access_code: Optional[str] = None,
        serial_number: Optional[str] = None,
    ):
        """
        Initialize printer controller.

        Args:
            host: Printer IP address
            access_code: Printer access code
            serial_number: Printer serial number
        """
        self._mqtt = BambuMQTTClient(
            host=host,
            access_code=access_code,
            serial_number=serial_number,
        )
        self._current_status: Optional[PrinterStatus] = None
        self._current_job: Optional[PrintJob] = None
        self._status_callbacks: List[Callable[[PrinterStatus], Awaitable[None]]] = []

    @property
    def is_connected(self) -> bool:
        """Check if connected to printer."""
        return self._mqtt.is_connected

    @property
    def current_status(self) -> Optional[PrinterStatus]:
        """Get current printer status."""
        return self._current_status

    @property
    def current_job(self) -> Optional[PrintJob]:
        """Get current print job."""
        return self._current_job

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Connect to the printer.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            True if connected successfully
        """
        # Register status callback
        self._mqtt.register_callback("status_update", self._handle_status_update)

        connected = await self._mqtt.connect(timeout=timeout)
        if connected:
            # Get initial status
            await self.refresh_status()

        return connected

    async def disconnect(self) -> None:
        """Disconnect from printer."""
        self._mqtt.unregister_callback("status_update")
        await self._mqtt.disconnect()

    async def _handle_status_update(self, report: Dict[str, Any]) -> None:
        """Handle incoming status updates."""
        self._current_status = PrinterStatus.from_mqtt_report(report)

        # Update job progress if printing
        if self._current_job and self._current_status.state == PrinterState.PRINTING:
            self._current_job.progress_percent = self._current_status.progress.percentage
            self._current_job.status = "printing"
            if self._current_job.started_at is None:
                self._current_job.started_at = datetime.now()

        # Check for job completion
        if self._current_job and self._current_status.state == PrinterState.FINISHED:
            self._current_job.status = "completed"
            self._current_job.progress_percent = 100.0
            self._current_job.completed_at = datetime.now()

        # Check for failure
        if self._current_job and self._current_status.state == PrinterState.FAILED:
            self._current_job.status = "failed"
            self._current_job.error_message = f"Print error code: {self._current_status.print_error}"

        # Notify callbacks
        for callback in self._status_callbacks:
            try:
                await callback(self._current_status)
            except Exception:
                pass

    def register_status_callback(
        self,
        callback: Callable[[PrinterStatus], Awaitable[None]],
    ) -> None:
        """Register callback for status updates."""
        self._status_callbacks.append(callback)

    async def refresh_status(self) -> Optional[PrinterStatus]:
        """
        Request fresh status from printer.

        Returns:
            Current PrinterStatus or None
        """
        report = await self._mqtt.get_status()
        if report:
            self._current_status = PrinterStatus.from_mqtt_report(report)
        return self._current_status

    async def submit_print_job(
        self,
        file_path: Path | str,
        use_ams: bool = False,
        ams_mapping: Optional[List[int]] = None,
        bed_leveling: bool = True,
        flow_calibration: bool = True,
        vibration_calibration: bool = True,
        layer_inspect: bool = False,
        timelapse: bool = False,
    ) -> PrintJob:
        """
        Submit a print job to the printer.

        Args:
            file_path: Path to 3MF file with G-code
            use_ams: Whether to use AMS for filament
            ams_mapping: AMS tray mapping if using AMS
            bed_leveling: Enable auto bed leveling
            flow_calibration: Enable flow calibration
            vibration_calibration: Enable vibration calibration
            layer_inspect: Enable AI layer inspection
            timelapse: Enable timelapse recording

        Returns:
            PrintJob object for tracking

        Note:
            The 3MF file must contain embedded G-code (sliced file).
            Use BambuStudio CLI to slice and export to 3MF first.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Print file not found: {file_path}")

        if file_path.suffix.lower() != ".3mf":
            raise ValueError("Only 3MF files with embedded G-code are supported")

        # Create job
        import uuid
        job = PrintJob(
            job_id=str(uuid.uuid4())[:8],
            file_path=file_path,
            file_name=file_path.name,
            submitted_at=datetime.now(),
        )

        # For local files, we need to use FTP or HTTP upload
        # This is a simplified version - actual implementation needs file transfer
        # The Bambu A1 in LAN mode requires the file to be uploaded first

        # Send print command
        # Note: This assumes the file is already on the printer or accessible via URL
        await self._mqtt.send_command(
            "print",
            "project_file",
            param=f"Metadata/plate_1.gcode",
            url=f"ftp://{self._mqtt.config.host}/{file_path.name}",
            subtask_name=file_path.stem,
            bed_leveling=bed_leveling,
            flow_cali=flow_calibration,
            vibration_cali=vibration_calibration,
            layer_inspect=layer_inspect,
            timelapse=timelapse,
            use_ams=use_ams,
            ams_mapping=ams_mapping or [0],
        )

        self._current_job = job
        return job

    async def pause_print(self) -> bool:
        """Pause current print."""
        if not self._current_job:
            return False

        await self._mqtt.send_command("print", "pause")
        self._current_job.status = "paused"
        return True

    async def resume_print(self) -> bool:
        """Resume paused print."""
        if not self._current_job or self._current_job.status != "paused":
            return False

        await self._mqtt.send_command("print", "resume")
        self._current_job.status = "printing"
        return True

    async def stop_print(self) -> bool:
        """Stop/cancel current print."""
        if not self._current_job:
            return False

        await self._mqtt.send_command("print", "stop")
        self._current_job.status = "cancelled"
        self._current_job.completed_at = datetime.now()
        return True

    async def set_speed_level(self, level: int) -> bool:
        """
        Set print speed level.

        Args:
            level: 1=Silent, 2=Standard, 3=Sport, 4=Ludicrous
        """
        if level < 1 or level > 4:
            raise ValueError("Speed level must be 1-4")

        await self._mqtt.send_command("print", "print_speed", param=str(level))
        return True

    async def set_fan_speed(self, speed_percent: int) -> bool:
        """
        Set cooling fan speed.

        Args:
            speed_percent: 0-100
        """
        if speed_percent < 0 or speed_percent > 100:
            raise ValueError("Fan speed must be 0-100")

        await self._mqtt.send_command(
            "print",
            "gcode_line",
            param=f"M106 P1 S{int(speed_percent * 2.55)}",  # Convert to 0-255
        )
        return True

    async def send_gcode(self, gcode: str) -> bool:
        """
        Send raw G-code command.

        Args:
            gcode: G-code command string
        """
        await self._mqtt.send_command("print", "gcode_line", param=gcode)
        return True

    async def home_axes(self) -> bool:
        """Home all axes."""
        return await self.send_gcode("G28")

    async def set_nozzle_temp(self, temp: int) -> bool:
        """Set nozzle target temperature."""
        return await self.send_gcode(f"M104 S{temp}")

    async def set_bed_temp(self, temp: int) -> bool:
        """Set bed target temperature."""
        return await self.send_gcode(f"M140 S{temp}")

    def get_job_summary(self) -> Optional[str]:
        """Get summary of current job."""
        if not self._current_job:
            return None

        job = self._current_job
        lines = [
            f"Job: {job.file_name}",
            f"Status: {job.status.upper()}",
            f"Progress: {job.progress_percent:.1f}%",
        ]

        if self._current_status and self._current_status.progress.time_remaining_minutes > 0:
            lines.append(f"Time remaining: ~{self._current_status.progress.time_remaining_minutes} min")

        return "\n".join(lines)
