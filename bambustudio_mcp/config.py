"""Configuration management for BambuStudio MCP."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class PrinterConfig(BaseModel):
    """Bambu printer connection configuration."""
    ip_address: str = Field(default="", description="Printer IP address on local network")
    access_code: str = Field(default="", description="Printer access code from settings")
    serial_number: str = Field(default="", description="Printer serial number")
    model: str = Field(default="A1", description="Printer model (A1, A1 Mini, P1S, X1C)")


class BambuStudioConfig(BaseModel):
    """BambuStudio application configuration."""
    executable_path: Path = Field(
        default=Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"),
        description="Path to BambuStudio executable"
    )
    profiles_dir: Optional[Path] = Field(
        default=None,
        description="Directory containing slicing profiles"
    )
    temp_dir: Path = Field(
        default=Path("/tmp/bambustudio-mcp"),
        description="Temporary directory for working files"
    )


class CameraConfig(BaseModel):
    """Camera streaming configuration."""
    rtsp_port: int = Field(default=322, description="RTSPS streaming port")
    frame_rate: int = Field(default=1, description="Expected frame rate (A1 is 1 FPS)")
    capture_interval: float = Field(default=5.0, description="Seconds between captures for analysis")


class Config(BaseModel):
    """Main configuration container."""
    printer: PrinterConfig = Field(default_factory=PrinterConfig)
    bambustudio: BambuStudioConfig = Field(default_factory=BambuStudioConfig)
    camera: CameraConfig = Field(default_factory=CameraConfig)
    database_path: Path = Field(
        default=Path("~/.bambustudio-mcp/prints.db").expanduser(),
        description="SQLite database for print history"
    )

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            printer=PrinterConfig(
                ip_address=os.getenv("BAMBU_PRINTER_IP", ""),
                access_code=os.getenv("BAMBU_ACCESS_CODE", ""),
                serial_number=os.getenv("BAMBU_SERIAL", ""),
                model=os.getenv("BAMBU_PRINTER_MODEL", "A1"),
            ),
            bambustudio=BambuStudioConfig(
                executable_path=Path(os.getenv(
                    "BAMBUSTUDIO_PATH",
                    "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"
                )),
                profiles_dir=Path(os.getenv("BAMBUSTUDIO_PROFILES", "")) if os.getenv("BAMBUSTUDIO_PROFILES") else None,
                temp_dir=Path(os.getenv("BAMBUSTUDIO_TEMP", "/tmp/bambustudio-mcp")),
            ),
            camera=CameraConfig(
                capture_interval=float(os.getenv("CAMERA_CAPTURE_INTERVAL", "5.0")),
            ),
            database_path=Path(os.getenv(
                "BAMBUSTUDIO_DB",
                "~/.bambustudio-mcp/prints.db"
            )).expanduser(),
        )


# Global config instance
config = Config.from_env()
