"""
Printer Status Models - Data structures for printer state.

Parses and represents printer status from MQTT reports.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


class PrinterState(str, Enum):
    """Printer operational states."""
    IDLE = "idle"
    PRINTING = "printing"
    PAUSED = "paused"
    FINISHED = "finished"
    FAILED = "failed"
    PREPARING = "preparing"
    SLICING = "slicing"
    UNKNOWN = "unknown"


class GcodeState(str, Enum):
    """G-code execution states."""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSE = "PAUSE"
    FINISH = "FINISH"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class TemperatureReading:
    """Temperature sensor reading."""
    current: float
    target: float

    @property
    def at_target(self) -> bool:
        """Check if within 2 degrees of target."""
        return abs(self.current - self.target) <= 2.0


@dataclass
class PrintProgress:
    """Current print progress information."""
    percentage: float = 0.0
    layer_current: int = 0
    layer_total: int = 0
    time_elapsed_minutes: int = 0
    time_remaining_minutes: int = 0
    gcode_state: GcodeState = GcodeState.IDLE

    @property
    def is_printing(self) -> bool:
        """Check if actively printing."""
        return self.gcode_state == GcodeState.RUNNING

    @property
    def is_finished(self) -> bool:
        """Check if print is finished."""
        return self.gcode_state == GcodeState.FINISH

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "percentage": round(self.percentage, 1),
            "layer": f"{self.layer_current}/{self.layer_total}",
            "time_elapsed_minutes": self.time_elapsed_minutes,
            "time_remaining_minutes": self.time_remaining_minutes,
            "state": self.gcode_state.value,
        }


@dataclass
class PrinterStatus:
    """
    Complete printer status from MQTT report.

    Parses the JSON report from the printer into structured data.
    """
    # Connection
    connected: bool = False
    last_update: Optional[datetime] = None

    # State
    state: PrinterState = PrinterState.UNKNOWN
    gcode_state: GcodeState = GcodeState.UNKNOWN

    # Temperatures
    nozzle_temp: Optional[TemperatureReading] = None
    bed_temp: Optional[TemperatureReading] = None
    chamber_temp: Optional[float] = None

    # Print progress
    progress: PrintProgress = field(default_factory=PrintProgress)

    # Current job
    gcode_file: Optional[str] = None
    subtask_name: Optional[str] = None
    print_type: Optional[str] = None

    # Hardware
    fan_speed_percent: int = 0
    speed_level: int = 1  # 1=silent, 2=standard, 3=sport, 4=ludicrous
    wifi_signal: int = 0

    # Errors/Warnings
    print_error: int = 0
    hw_switch_state: int = 0

    # Raw data
    raw_report: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mqtt_report(cls, report: Dict[str, Any]) -> "PrinterStatus":
        """
        Parse MQTT report into PrinterStatus.

        Args:
            report: Raw MQTT JSON report

        Returns:
            PrinterStatus instance
        """
        status = cls(
            connected=True,
            last_update=datetime.now(),
            raw_report=report,
        )

        # Extract print data
        print_data = report.get("print", {})

        # State
        gcode_state_str = print_data.get("gcode_state", "UNKNOWN")
        try:
            status.gcode_state = GcodeState(gcode_state_str)
        except ValueError:
            status.gcode_state = GcodeState.UNKNOWN

        # Map gcode_state to printer state
        state_map = {
            GcodeState.IDLE: PrinterState.IDLE,
            GcodeState.RUNNING: PrinterState.PRINTING,
            GcodeState.PAUSE: PrinterState.PAUSED,
            GcodeState.FINISH: PrinterState.FINISHED,
            GcodeState.FAILED: PrinterState.FAILED,
        }
        status.state = state_map.get(status.gcode_state, PrinterState.UNKNOWN)

        # Temperatures
        nozzle_temp = print_data.get("nozzle_temper")
        nozzle_target = print_data.get("nozzle_target_temper")
        if nozzle_temp is not None and nozzle_target is not None:
            status.nozzle_temp = TemperatureReading(
                current=float(nozzle_temp),
                target=float(nozzle_target),
            )

        bed_temp = print_data.get("bed_temper")
        bed_target = print_data.get("bed_target_temper")
        if bed_temp is not None and bed_target is not None:
            status.bed_temp = TemperatureReading(
                current=float(bed_temp),
                target=float(bed_target),
            )

        chamber_temp = print_data.get("chamber_temper")
        if chamber_temp is not None:
            status.chamber_temp = float(chamber_temp)

        # Progress
        status.progress = PrintProgress(
            percentage=float(print_data.get("mc_percent", 0)),
            layer_current=int(print_data.get("layer_num", 0)),
            layer_total=int(print_data.get("total_layer_num", 0)),
            time_elapsed_minutes=int(print_data.get("mc_print_time", 0)) // 60,
            time_remaining_minutes=int(print_data.get("mc_remaining_time", 0)),
            gcode_state=status.gcode_state,
        )

        # Job info
        status.gcode_file = print_data.get("gcode_file")
        status.subtask_name = print_data.get("subtask_name")
        status.print_type = print_data.get("print_type")

        # Hardware
        status.fan_speed_percent = int(print_data.get("cooling_fan_speed", 0))
        status.speed_level = int(print_data.get("spd_lvl", 1))
        status.wifi_signal = int(print_data.get("wifi_signal", 0))

        # Errors
        status.print_error = int(print_data.get("print_error", 0))
        status.hw_switch_state = int(print_data.get("hw_switch_state", 0))

        return status

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "connected": self.connected,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "state": self.state.value,
            "temperatures": {
                "nozzle": {
                    "current": self.nozzle_temp.current if self.nozzle_temp else None,
                    "target": self.nozzle_temp.target if self.nozzle_temp else None,
                } if self.nozzle_temp else None,
                "bed": {
                    "current": self.bed_temp.current if self.bed_temp else None,
                    "target": self.bed_temp.target if self.bed_temp else None,
                } if self.bed_temp else None,
                "chamber": self.chamber_temp,
            },
            "progress": self.progress.to_dict(),
            "job": {
                "file": self.gcode_file,
                "name": self.subtask_name,
                "type": self.print_type,
            },
            "hardware": {
                "fan_speed_percent": self.fan_speed_percent,
                "speed_level": self.speed_level,
                "wifi_signal": self.wifi_signal,
            },
            "has_error": self.print_error != 0,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def get_summary(self) -> str:
        """Get human-readable status summary."""
        lines = [f"Printer State: {self.state.value.upper()}"]

        if self.nozzle_temp:
            lines.append(f"Nozzle: {self.nozzle_temp.current:.0f}°C / {self.nozzle_temp.target:.0f}°C")
        if self.bed_temp:
            lines.append(f"Bed: {self.bed_temp.current:.0f}°C / {self.bed_temp.target:.0f}°C")

        if self.state == PrinterState.PRINTING:
            lines.append(f"Progress: {self.progress.percentage:.1f}%")
            lines.append(f"Layer: {self.progress.layer_current}/{self.progress.layer_total}")
            lines.append(f"Time remaining: ~{self.progress.time_remaining_minutes} min")

        if self.subtask_name:
            lines.append(f"Job: {self.subtask_name}")

        if self.print_error != 0:
            lines.append(f"⚠️ Error code: {self.print_error}")

        return "\n".join(lines)
