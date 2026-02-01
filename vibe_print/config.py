"""Configuration management for Vibe Print MCP."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class PrinterConfig(BaseModel):
    """FDM printer connection configuration."""
    ip_address: str = Field(default="", description="Printer IP address on local network")
    access_code: str = Field(default="", description="Printer access code from settings")
    serial_number: str = Field(default="", description="Printer serial number")
    model: str = Field(default="generic", description="Printer model identifier")


class SlicerConfig(BaseModel):
    """Slicer application configuration."""
    executable_path: Path = Field(
        default=Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"),
        description="Path to slicer executable"
    )
    profiles_dir: Optional[Path] = Field(
        default=None,
        description="Directory containing slicing profiles"
    )
    temp_dir: Path = Field(
        default=Path("/tmp/vibe-print"),
        description="Temporary directory for working files"
    )


class CameraConfig(BaseModel):
    """Camera streaming configuration."""
    rtsp_port: int = Field(default=322, description="RTSPS streaming port")
    frame_rate: int = Field(default=1, description="Expected frame rate")
    capture_interval: float = Field(default=5.0, description="Seconds between captures for analysis")


class Config(BaseModel):
    """Main configuration container."""
    printer: PrinterConfig = Field(default_factory=PrinterConfig)
    slicer: SlicerConfig = Field(default_factory=SlicerConfig)
    camera: CameraConfig = Field(default_factory=CameraConfig)
    database_path: Path = Field(
        default=Path("~/.vibe-print/prints.db").expanduser(),
        description="SQLite database for print history"
    )

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            printer=PrinterConfig(
                ip_address=os.getenv("VIBE_PRINTER_IP", ""),
                access_code=os.getenv("VIBE_ACCESS_CODE", ""),
                serial_number=os.getenv("VIBE_SERIAL", ""),
                model=os.getenv("VIBE_PRINTER_MODEL", "generic"),
            ),
            slicer=SlicerConfig(
                executable_path=Path(os.getenv(
                    "VIBE_SLICER_PATH",
                    "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"
                )),
                profiles_dir=Path(os.getenv("VIBE_SLICER_PROFILES", "")) if os.getenv("VIBE_SLICER_PROFILES") else None,
                temp_dir=Path(os.getenv("VIBE_TEMP", "/tmp/vibe-print")),
            ),
            camera=CameraConfig(
                capture_interval=float(os.getenv("CAMERA_CAPTURE_INTERVAL", "5.0")),
            ),
            database_path=Path(os.getenv(
                "VIBE_DB",
                "~/.vibe-print/prints.db"
            )).expanduser(),
        )


# Global config instance
config = Config.from_env()
