"""
Vibe Print MCP Server - End-to-end 3D printing automation for FDM printers.

This MCP server provides tools for:
- Model analysis and scaling
- Slicer CLI integration for slicing
- Printer control via MQTT
- Camera-based print monitoring
- Iterative improvement recommendations
"""

from vibe_print.server import mcp, main

__version__ = "0.1.0"
__all__ = ["mcp", "main"]
