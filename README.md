# BambuStudio MCP Server

A comprehensive MCP (Model Context Protocol) server for Claude macOS app that provides **end-to-end 3D printing automation** with Bambu Lab printers - from natural language requirements to perfect printed objects.

## What This Does

Tell Claude what you need, and it will:
1. **Generate** a 3D model from your description
2. **Scale** it to your exact dimensions
3. **Slice** it with optimized parameters
4. **Print** it on your Bambu printer
5. **Monitor** the print via camera
6. **Detect** any issues and suggest fixes
7. **Learn** from each print to improve the next one

## Example Workflow

```
You: "I need a tube squeezer for my Gold Bond lotion bottle, it's about 65mm diameter"

Claude:
1. Parses requirements → tube_squeezer, 65mm, heavy_duty
2. Generates parametric model with CadQuery
3. Adjusts for larger size (thicker walls, more infill)
4. Slices with BambuStudio CLI
5. Monitors print via RTSPS camera
6. Records outcome: 88% quality, minor stringing
7. Recommends: +0.5mm retraction, -5°C nozzle temp
```

## Features

### Phase 0: Model Generation (NEW!)
- **Natural Language Parsing**: "I need a squeezer for 65mm bottle" → structured parameters
- **Image Analysis**: Extract dimensions from photos with rulers
- **Parametric Generation**: CadQuery/OpenSCAD for precise functional parts
- **Template Library**: Pre-built customizable designs (squeezers, holders, clips)
- **AI Generation**: Text-to-3D via Meshy/Tripo3D for organic shapes

### Phase 1: Model Preparation
- **Model Analysis**: Load and analyze STL/3MF files, extract dimensions
- **Smart Scaling**: Scale based on target dimensions (toothpaste → lotion bottle)
- **Parameter Optimization**: Adjust slicing for scaled prints

### Phase 2: Print Execution & Monitoring
- **Printer Control**: MQTT connection to Bambu A1/A1 Mini in LAN mode
- **Camera Streaming**: RTSPS feed at 1 FPS
- **Defect Detection**: Layer shifts, stringing, warping, spaghetti detection

### Phase 3: Iterative Improvement
- **Print History**: SQLite database of all attempts
- **Recommendation Engine**: Learn from defects to suggest fixes
- **Quality Scoring**: 0-100 score based on detected issues

### Novice-Friendly Features (NEW!)
- **Interactive Wizard**: Guided workflow with checkpoints for beginners
- **Plain Language Support**: "heavy duty" → thick walls, high infill
- **Design Review**: Catches issues before you print (thin walls, tight clearances)
- **Slicing Review**: Recommends settings based on use case (functional vs decorative)
- **Material Optimization**: Auto-adjusts for your specific filament

## Supported Materials

Pre-configured profiles for:
- **Bambu Basic PLA** - General purpose, 220°C nozzle, up to 300mm/s
- **Bambu PETG Translucent** - Functional parts, 250°C nozzle
- **Prusament PC Blend** - High strength, 270°C nozzle (keep parts small on A1)
- **Generic PETG** - Outdoor/water-resistant, 245°C nozzle
- **Generic TPU 95A** - Flexible, 230°C nozzle, 40mm/s max, **NO AMS**

## Supported Nozzles

All A1/A1 Mini nozzle configurations:
- **0.2mm Stainless Steel** - Fine detail, miniatures
- **0.4mm Stainless Steel** - Default, best all-around
- **0.4mm Hardened Steel** - For carbon fiber/glow filaments
- **0.6mm Hardened Steel** - Faster prints, functional parts
- **0.8mm Hardened Steel** - Draft prints, large parts

## Requirements

- macOS with BambuStudio installed
- Bambu Lab A1/A1 Mini printer in LAN mode
- Python 3.10+
- Printer access code (from printer settings)

## Installation

```bash
cd bambustudio-mcp

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
   - **Bambu Printer**: `ip_address`, `access_code`, `serial_number`
   - **Meshy** (optional): `api_key`
   - **Tripo3D** (optional): `api_key`

### Running with 1Password CLI

Use `op run` to inject secrets as environment variables:

```bash
op run --env-file=.env.template -- python -m bambustudio_mcp
```

Create a `.env.template` file (safe to commit - contains only references, not secrets):

```bash
# Printer connection (required)
BAMBU_PRINTER_IP=op://Personal/Bambu Printer/ip_address
BAMBU_ACCESS_CODE=op://Personal/Bambu Printer/access_code
BAMBU_SERIAL=op://Personal/Bambu Printer/serial_number

# BambuStudio path (usually auto-detected)
BAMBUSTUDIO_PATH=/Applications/BambuStudio.app/Contents/MacOS/BambuStudio

# Optional: AI 3D generation
MESHY_API_KEY=op://Personal/Meshy/api_key
TRIPO3D_API_KEY=op://Personal/Tripo3D/api_key
```

## Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bambustudio": {
      "command": "op",
      "args": [
        "run",
        "--env-file=/path/to/bambustudio-mcp/.env.template",
        "--",
        "python",
        "-m",
        "bambustudio_mcp"
      ]
    }
  }
}
```

This ensures secrets are never stored in plain text and are securely injected at runtime.

## Available Tools (33 total)

### Novice-Friendly Wizard Tools (NEW!)
| Tool | Description |
|------|-------------|
| `bambustudio_start_guided_workflow` | **Start here!** Interactive workflow with checkpoints |
| `bambustudio_parse_novice_description` | Translate "heavy duty" → technical parameters |
| `bambustudio_review_design` | Get design suggestions before generating |
| `bambustudio_review_slicing` | Get quality settings for your material/use case |
| `bambustudio_optimize_for_material` | Auto-optimize parameters for your filament |
| `bambustudio_list_materials` | List supported filaments with properties |
| `bambustudio_list_nozzles` | List A1 nozzles with recommendations |
| `bambustudio_get_nozzle_recommendation` | Get best nozzle for your needs |

### Model Generation
| Tool | Description |
|------|-------------|
| `bambustudio_parse_requirements` | Parse natural language → structured parameters |
| `bambustudio_analyze_reference_image` | Extract dimensions from photos |
| `bambustudio_list_templates` | List available model templates |
| `bambustudio_generate_from_template` | Generate from customizable template |
| `bambustudio_generate_parametric` | Generate from description (CadQuery) |
| `bambustudio_ai_generate` | AI text-to-3D (Meshy/Tripo3D) |
| `bambustudio_ai_status` | Check AI generation progress |

### Model Preparation
| Tool | Description |
|------|-------------|
| `bambustudio_analyze_model` | Analyze STL/3MF dimensions and quality |
| `bambustudio_scale_model` | Scale model to target dimensions |
| `bambustudio_slice_model` | Slice with BambuStudio CLI |
| `bambustudio_list_presets` | List slicing presets |

### Printer Control
| Tool | Description |
|------|-------------|
| `bambustudio_test_printer_connection` | Test MQTT connection |
| `bambustudio_get_printer_status` | Get temperatures, progress |
| `bambustudio_control_print` | Pause/resume/stop print |

### Camera & Quality
| Tool | Description |
|------|-------------|
| `bambustudio_capture_camera` | Capture camera frames |
| `bambustudio_analyze_print_quality` | Detect defects in frame |

### Iteration Tracking
| Tool | Description |
|------|-------------|
| `bambustudio_create_iteration` | Start tracking a print |
| `bambustudio_record_outcome` | Record result + defects |
| `bambustudio_get_recommendations` | Get parameter fixes |
| `bambustudio_get_model_history` | View print history |

## Architecture

```
bambustudio_mcp/
├── server.py              # MCP server with all 33 tools
├── config.py              # Environment configuration
├── materials/             # NEW: Filament & nozzle profiles
│   ├── filaments.py       # 5 pre-configured filament profiles
│   └── nozzles.py         # A1 nozzle configurations
├── wizard/                # NEW: Novice-friendly workflow
│   ├── guided_workflow.py # Interactive checkpoints
│   ├── design_review.py   # Design suggestions
│   ├── slicing_review.py  # Quality recommendations
│   ├── novice_parser.py   # Plain language → parameters
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
│   ├── cli.py             # BambuStudio CLI
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
workflow = await bambustudio_start_guided_workflow({
    "description": "I need a heavy duty squeezer for my 65mm lotion bottle"
})

# The system parses your description:
# - "heavy duty" → wall_thickness: 3mm, infill: 30%
# - "65mm" → tube_diameter: 65mm
# - "squeezer" → category: tube_squeezer

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
- "heavy duty" → thick walls (3mm), high infill (30%)
- "snug fit" → clearance: 0.2-0.3mm
- "loose fit" → clearance: 0.8-1.0mm
- "flexible" → suggests TPU material
- "waterproof" → suggests PETG
- "heat resistant" → suggests PC or PETG

## Examples

See `examples/` directory:
- `complete_workflow.py` - Full end-to-end example
- `tube_squeezer_workflow.py` - Scaling example
- `generation_tools_reference.md` - Generation tool docs
- `mcp_tools_reference.md` - All tools reference

## License

MIT
