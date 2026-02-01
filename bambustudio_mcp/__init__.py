"""
BambuStudio MCP Server - End-to-end 3D printing automation for Bambu Lab printers.

This MCP server provides tools for:
- Model analysis and scaling
- BambuStudio CLI integration for slicing
- Printer control via MQTT
- Camera-based print monitoring
- Iterative improvement recommendations
"""

from bambustudio_mcp.server import mcp, main

__version__ = "0.1.0"
__all__ = ["mcp", "main"]
