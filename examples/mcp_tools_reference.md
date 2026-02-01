# Vibe Print MCP Tools Reference

Quick reference for all available MCP tools and their usage.

## Model Preparation Tools

### `vibe_analyze_model`
Analyze a 3D model to extract dimensions and quality metrics.

```json
{
  "file_path": "/path/to/model.stl"
}
```

Returns: Bounding box, triangle count, detected features, recommendations.

### `vibe_scale_model`
Scale a model for a different size application.

**For tube squeezers:**
```json
{
  "file_path": "/path/to/squeezer.stl",
  "original_tube_diameter_mm": 25.0,
  "target_tube_diameter_mm": 65.0
}
```

**For general scaling:**
```json
{
  "file_path": "/path/to/model.stl",
  "scale_factor": 1.5
}
```

Returns: Scaled file path, original and new dimensions.

---

## Slicing Tools

### `vibe_slice_model`
Slice a model using slicer CLI.

```json
{
  "file_path": "/path/to/model.stl",
  "preset": "tube_squeezer_strong",
  "layer_height": 0.20,
  "infill_percent": 25,
  "wall_loops": 4
}
```

**Available presets:**
- `tube_squeezer_standard` - Balanced strength/speed
- `tube_squeezer_strong` - Heavy-duty for larger prints
- `draft` - Fast testing
- `quality` - Fine detail

Returns: 3MF file path, estimated time, filament usage.

### `vibe_list_presets`
List all available slicing presets.

Returns: Preset names, descriptions, and tags.

---

## Printer Control Tools

### `vibe_test_printer_connection`
Test connection to a compatible FDM printer in LAN mode.

```json
{
  "ip_address": "192.168.1.100",
  "access_code": "12345678",
  "serial_number": "00M00A123456789"
}
```

Returns: Connection status and message.

### `vibe_get_printer_status`
Get current printer status (requires env vars configured).

Returns: Temperatures, print progress, operational state.

### `vibe_control_print`
Control an active print job.

```json
{
  "action": "pause"  // or "resume", "stop"
}
```

Returns: Action success status.

---

## Camera & Quality Tools

### `vibe_capture_camera`
Capture frames from the printer's camera.

```json
{
  "output_path": "/path/to/output/",
  "frame_count": 5
}
```

Returns: Captured frame info and file paths.

### `vibe_analyze_print_quality`
Capture and analyze a frame for print defects.

Returns: Quality score (0-100), detected defects, recommendations.

**Detectable defects:**
- `layer_shift` - Horizontal displacement between layers
- `stringing` - Thin strings between features
- `warping` - Corners lifting from bed
- `blob` - Excess material deposits
- `spaghetti` - Failed print with tangled filament
- `under_extrusion` - Gaps in extrusion
- `over_extrusion` - Too much material

---

## Iteration Tracking Tools

### `vibe_create_iteration`
Create a print iteration record for tracking.

```json
{
  "model_name": "lotion_squeezer",
  "model_path": "/path/to/model.stl",
  "scale_factor": 2.6,
  "preset_name": "tube_squeezer_strong"
}
```

Returns: Iteration ID and details.

### `vibe_record_outcome`
Record the result of a print attempt.

```json
{
  "iteration_id": "abc12345",
  "status": "completed",
  "quality_score": 85.0,
  "defects": ["stringing"],
  "notes": "Minor stringing on travel moves"
}
```

Returns: Updated iteration with improvement suggestions.

### `vibe_get_recommendations`
Get parameter recommendations based on defects and history.

```json
{
  "model_name": "lotion_squeezer",
  "defects": ["stringing", "blob"]
}
```

Returns: Prioritized parameter adjustments.

### `vibe_get_model_history`
Get print history and statistics for a model.

```json
{
  "model_name": "lotion_squeezer"
}
```

Returns: Past attempts, success rate, common defects.

---

## Example Workflow

1. **Analyze** the original model
2. **Scale** for target dimensions
3. **Slice** with appropriate preset
4. **Create iteration** record
5. **Submit print** and **monitor** with camera
6. **Analyze quality** periodically
7. **Record outcome** when complete
8. **Get recommendations** for next iteration

Repeat steps 2-8 until desired quality is achieved!
