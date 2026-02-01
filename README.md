# Vibe Print MCP Server

A comprehensive MCP (Model Context Protocol) server for Claude that provides **end-to-end 3D printing automation** with compatible FDM printers - from natural language requirements to perfect printed objects.

> **Disclaimer**
> This is an independent community project. It is not affiliated with, endorsed by, or connected to any printer manufacturer. All product names and trademarks are the property of their respective owners.

## What This Does

Tell Claude what you need, and it will:
1. **Generate** a 3D model from your description
2. **Scale** it to your exact dimensions
3. **Slice** it with optimized parameters
4. **Print** it on your FDM printer
5. **Monitor** the print via camera
6. **Detect** any issues and suggest fixes
7. **Learn** from each print to improve the next one

## Example Workflow

```
You: "I need a tube squeezer for my Gold Bond lotion bottle, it's about 65mm diameter"

Claude:
1. Parses requirements -> tube_squeezer, 65mm, heavy_duty
2. Generates parametric model with CadQuery
3. Adjusts for larger size (thicker walls, more infill)
4. Slices with slicer CLI
5. Monitors print via RTSPS camera
6. Records outcome: 88% quality, minor stringing
7. Recommends: +0.5mm retraction, -5C nozzle temp
```

## Features

### Phase 0: Model Generation
- **Natural Language Parsing**: "I need a squeezer for 65mm bottle" -> structured parameters
- **Image Analysis**: Extract dimensions from photos with rulers
- **Parametric Generation**: CadQuery/OpenSCAD for precise functional parts
- **Template Library**: Pre-built customizable designs (squeezers, holders, clips)
- **AI Generation**: Text-to-3D via Meshy/Tripo3D for organic shapes

### Phase 1: Model Preparation
- **Model Analysis**: Load and analyze STL/3MF files, extract dimensions
- **Smart Scaling**: Scale based on target dimensions (toothpaste -> lotion bottle)
- **Parameter Optimization**: Adjust slicing for scaled prints

### Phase 2: Print Execution & Monitoring
- **Printer Control**: MQTT connection to compatible printers in LAN mode
- **Camera Streaming**: RTSPS feed capture
- **Defect Detection**: Layer shifts, stringing, warping, spaghetti detection

### Phase 3: Iterative Improvement
- **Print History**: SQLite database of all attempts
- **Recommendation Engine**: Learn from defects to suggest fixes
- **Quality Scoring**: 0-100 score based on detected issues

### Novice-Friendly Features
- **Interactive Wizard**: Guided workflow with checkpoints for beginners
- **Plain Language Support**: "heavy duty" -> thick walls, high infill
- **Design Review**: Catches issues before you print (thin walls, tight clearances)
- **Slicing Review**: Recommends settings based on use case (functional vs decorative)
- **Material Optimization**: Auto-adjusts for your specific filament

## Supported Materials

Pre-configured profiles for:
- **Basic PLA** - General purpose, 220C nozzle, up to 300mm/s
- **PETG Translucent** - Functional parts, 250C nozzle
- **PC Blend** - High strength, 270C nozzle (keep parts small on open printers)
- **Generic PETG** - Outdoor/water-resistant, 245C nozzle
- **Generic TPU 95A** - Flexible, 230C nozzle, 40mm/s max, **direct feed only**

## Supported Nozzles

Common FDM nozzle configurations:
- **0.2mm Stainless Steel** - Fine detail, miniatures
- **0.4mm Stainless Steel** - Default, best all-around
- **0.4mm Hardened Steel** - For carbon fiber/glow filaments
- **0.6mm Hardened Steel** - Faster prints, functional parts
- **0.8mm Hardened Steel** - Draft prints, large parts

## Requirements

- macOS with compatible slicer installed
- FDM printer with LAN mode and MQTT support
- Python 3.10+
- Printer access code (from printer settings)

## Installation

```bash
cd vibe-print

# Basic installation
pip install -e . --break-system-packages

# With CAD generation (recommended)
pip install -e ".[cad]" --break-system-packages

# With everything
pip install -e ".[all]" --break-system-packages
```

## Configuration

This project uses [1Password CLI](https://developer.1password.com/docs/cli/) for secure secret management. Never store API keys or credentials in plain text files.

### Setting Up 1Password CLI

1. Install 1Password CLI:
   ```bash
   brew install --cask 1password-cli
   ```

2. Sign in and enable shell integration:
   ```bash
   op signin
   ```

3. Store your secrets in 1Password. Create items with these fields:
   - **Printer Config**: `ip_address`, `access_code`, `serial_number`
   - **Meshy** (optional): `api_key`
   - **Tripo3D** (optional): `api_key`

### Running with 1Password CLI

Use `op run` to inject secrets as environment variables:

```bash
op run --env-file=.env.template -- python -m vibe_print
```

Create a `.env.template` file (safe to commit - contains only references, not secrets):

```bash
# Printer connection (required)
VIBE_PRINTER_IP=op://Personal/Printer Config/ip_address
VIBE_ACCESS_CODE=op://Personal/Printer Config/access_code
VIBE_SERIAL=op://Personal/Printer Config/serial_number

# Slicer path (usually auto-detected)
VIBE_SLICER_PATH=/Applications/YourSlicer.app/Contents/MacOS/slicer

# Optional: AI 3D generation
MESHY_API_KEY=op://Personal/Meshy/api_key
TRIPO3D_API_KEY=op://Personal/Tripo3D/api_key
```

## Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "vibe-print": {
      "command": "op",
      "args": [
        "run",
        "--env-file=/path/to/vibe-print/.env.template",
        "--",
        "python",
        "-m",
        "vibe_print"
      ]
    }
  }
}
```

This ensures secrets are never stored in plain text and are securely injected at runtime.

## Available Tools (33 total)

### Novice-Friendly Wizard Tools
| Tool | Description |
|------|-------------|
| `vibe_start_guided_workflow` | **Start here!** Interactive workflow with checkpoints |
| `vibe_parse_novice_description` | Translate "heavy duty" -> technical parameters |
| `vibe_review_design` | Get design suggestions before generating |
| `vibe_review_slicing` | Get quality settings for your material/use case |
| `vibe_optimize_for_material` | Auto-optimize parameters for your filament |
| `vibe_list_materials` | List supported filaments with properties |
| `vibe_list_nozzles` | List nozzles with recommendations |
| `vibe_get_nozzle_recommendation` | Get best nozzle for your needs |

### Model Generation
| Tool | Description |
|------|-------------|
| `vibe_parse_requirements` | Parse natural language -> structured parameters |
| `vibe_analyze_reference_image` | Extract dimensions from photos |
| `vibe_list_templates` | List available model templates |
| `vibe_generate_from_template` | Generate from customizable template |
| `vibe_generate_parametric` | Generate from description (CadQuery) |
| `vibe_ai_generate` | AI text-to-3D (Meshy/Tripo3D) |
| `vibe_ai_status` | Check AI generation progress |

### Model Preparation
| Tool | Description |
|------|-------------|
| `vibe_analyze_model` | Analyze STL/3MF dimensions and quality |
| `vibe_scale_model` | Scale model to target dimensions |
| `vibe_slice_model` | Slice with slicer CLI |
| `vibe_list_presets` | List slicing presets |

### Printer Control
| Tool | Description |
|------|-------------|
| `vibe_test_printer_connection` | Test MQTT connection |
| `vibe_get_printer_status` | Get temperatures, progress |
| `vibe_control_print` | Pause/resume/stop print |

### Camera & Quality
| Tool | Description |
|------|-------------|
| `vibe_capture_camera` | Capture camera frames |
| `vibe_analyze_print_quality` | Detect defects in frame |

### Iteration Tracking
| Tool | Description |
|------|-------------|
| `vibe_create_iteration` | Start tracking a print |
| `vibe_record_outcome` | Record result + defects |
| `vibe_get_recommendations` | Get parameter fixes |
| `vibe_get_model_history` | View print history |

## Architecture

```
vibe_print/
├── server.py              # MCP server with all 33 tools
├── config.py              # Environment configuration
├── materials/             # Filament & nozzle profiles
│   ├── filaments.py       # Pre-configured filament profiles
│   └── nozzles.py         # Nozzle configurations
├── wizard/                # Novice-friendly workflow
│   ├── guided_workflow.py # Interactive checkpoints
│   ├── design_review.py   # Design suggestions
│   ├── slicing_review.py  # Quality recommendations
│   ├── novice_parser.py   # Plain language -> parameters
│   └── material_optimizer.py # Material-based adjustments
├── generator/             # Model generation
│   ├── requirements.py    # Natural language parsing
│   ├── image_analyzer.py  # Photo dimension extraction
│   ├── parametric.py      # CadQuery/OpenSCAD generation
│   ├── templates.py       # Template library
│   └── ai_generator.py    # Meshy/Tripo3D integration
├── models/
│   ├── analyzer.py        # STL/3MF analysis
│   └── scaler.py          # Dimension scaling
├── slicer/
│   ├── cli.py             # Slicer CLI
│   ├── parameters.py      # Slicing parameters
│   └── profiles.py        # Preset management
├── printer/
│   ├── mqtt_client.py     # MQTT communication
│   ├── controller.py      # Job control
│   └── status.py          # Status parsing
├── camera/
│   ├── stream.py          # RTSPS capture
│   └── detector.py        # Defect detection
└── iteration/
    ├── tracker.py         # SQLite history
    └── recommender.py     # Parameter recommendations
```

## Novice-Friendly Usage

For CAD beginners, use the guided workflow:

```python
# Start with your plain language description
workflow = await vibe_start_guided_workflow({
    "description": "I need a heavy duty squeezer for my 65mm lotion bottle"
})

# The system parses your description:
# - "heavy duty" -> wall_thickness: 3mm, infill: 30%
# - "65mm" -> tube_diameter: 65mm
# - "squeezer" -> category: tube_squeezer

# Then guides you through checkpoints:
# 1. Requirements confirmation
# 2. Design review (catches thin walls, tight tolerances)
# 3. Material selection (suggests TPU if flexible needed)
# 4. Nozzle selection (recommends 0.4mm for standard parts)
# 5. Quality settings (functional vs decorative)
# 6. Final review before generation
```

### Plain Language Examples

The system understands:
- "heavy duty" -> thick walls (3mm), high infill (30%)
- "snug fit" -> clearance: 0.2-0.3mm
- "loose fit" -> clearance: 0.8-1.0mm
- "flexible" -> suggests TPU material
- "waterproof" -> suggests PETG
- "heat resistant" -> suggests PC or PETG

## Examples

See `examples/` directory:
- `complete_workflow.py` - Full end-to-end example
- `tube_squeezer_workflow.py` - Scaling example
- `generation_tools_reference.md` - Generation tool docs
- `mcp_tools_reference.md` - All tools reference

## License

MIT
