# Model Generation Tools Reference

Quick reference for all model generation MCP tools.

## Overview

The generation tools allow Claude to create 3D models from:
1. **Natural language descriptions** → Parametric generation (CadQuery/OpenSCAD)
2. **Reference images** → Dimension extraction + parametric generation
3. **Text prompts** → AI generation (Meshy, Tripo3D)
4. **Templates** → Pre-built customizable designs

## Tools

### `bambustudio_parse_requirements`
Parse natural language into structured model parameters.

```json
{
  "description": "I need a tube squeezer for a 65mm lotion bottle, heavy duty",
  "target_dimension_mm": 65
}
```

**Returns:**
- Category (tube_squeezer, holder, bracket, clip, etc.)
- Extracted dimensions
- Fit type (tight, snug, sliding, loose)
- Strength requirements
- Wall thickness recommendations

---

### `bambustudio_analyze_reference_image`
Extract dimensions from a photo.

```json
{
  "image_path": "/path/to/photo_with_ruler.jpg",
  "known_dimension_mm": 65  // Optional calibration
}
```

**Features:**
- Automatic ruler/scale detection
- Object edge measurement
- Shape feature detection (slots, holes)
- Category suggestion

---

### `bambustudio_list_templates`
List available model templates.

**Built-in templates:**

| Template | Description | Key Parameters |
|----------|-------------|----------------|
| `tube_squeezer` | Tube/bottle squeezer | tube_diameter, wall_thickness, clearance |
| `phone_holder` | Phone/tablet stand | width, depth, angle |
| `cable_catch` | Cable management clip | cable_diameter, num_slots |

---

### `bambustudio_generate_from_template`
Generate a model from a customizable template.

```json
{
  "template_name": "tube_squeezer",
  "tube_diameter": 65,
  "wall_thickness": 3.0,
  "clearance": 1.5
}
```

**Best for:** Functional parts with known dimensions.

---

### `bambustudio_generate_parametric`
Generate from natural language using parametric CAD.

```json
{
  "description": "A heavy duty tube squeezer for 65mm lotion bottle with grip texture",
  "target_dimension_mm": 65
}
```

**Process:**
1. Parse requirements from description
2. Classify object type
3. Generate CadQuery code (or OpenSCAD fallback)
4. Export to STL

**Best for:** Functional parts described in natural language.

---

### `bambustudio_ai_generate`
Generate using AI text-to-3D services.

```json
{
  "prompt": "A cute cartoon cat figurine sitting",
  "style": "cartoon"
}
```

**Styles:** realistic, cartoon, sculpture

**Requirements:** API key (MESHY_API_KEY or TRIPO3D_API_KEY)

**Best for:** Artistic/organic shapes, decorative items.

---

### `bambustudio_ai_status`
Check AI generation job status.

```json
{
  "job_id": "abc123"
}
```

**Returns:** status (processing/completed/failed), progress %, download URL

---

## Choosing the Right Generation Method

| Use Case | Recommended Tool |
|----------|------------------|
| Tube squeezer with specific dimensions | `generate_from_template` |
| Functional part from description | `generate_parametric` |
| "Make me a phone stand" | `parse_requirements` → `generate_from_template` |
| Artistic figurine | `ai_generate` |
| Dimension from photo | `analyze_reference_image` → `generate_from_template` |

---

## Example Workflow: Lotion Bottle Squeezer

```python
# 1. Parse the request
requirements = await bambustudio_parse_requirements({
    "description": "Heavy duty squeezer for Gold Bond lotion, 65mm bottle",
    "target_dimension_mm": 65
})

# 2. Generate from template (recommended for precise functional parts)
model = await bambustudio_generate_from_template({
    "template_name": "tube_squeezer",
    "tube_diameter": 65,
    "wall_thickness": 3.0,  # Heavy duty
    "clearance": 1.5,
})

# 3. Slice
sliced = await bambustudio_slice_model({
    "file_path": model["output_path"],
    "preset": "tube_squeezer_strong"
})

# 4. Print and iterate...
```

---

## Installing CAD Dependencies

For parametric generation, install CadQuery:

```bash
pip install cadquery-ocp --break-system-packages
```

Or use OpenSCAD as fallback:
```bash
brew install openscad  # macOS
```

For AI generation, set environment variable:
```bash
export MESHY_API_KEY="your_key"
# or
export TRIPO3D_API_KEY="your_key"
```
