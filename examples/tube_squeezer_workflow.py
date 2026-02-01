#!/usr/bin/env python3
"""
Example Workflow: Scaling a Tube Squeezer for a Lotion Bottle

This script demonstrates the complete workflow for:
1. Analyzing the original toothpaste squeezer model
2. Scaling it to fit a larger lotion bottle (like the Gold Bond 5.5oz shown in the example)
3. Adjusting slicing parameters for the larger print
4. Slicing with BambuStudio
5. Monitoring the print
6. Tracking iterations for continuous improvement

Based on the image showing:
- Original squeezer: ~38mm wide (for toothpaste tubes ~25mm diameter)
- Target: Gold Bond lotion bottle (~65mm diameter)
"""

import asyncio
from pathlib import Path


async def main():
    """
    Complete tube squeezer scaling and printing workflow.
    """
    # =========================================================================
    # Configuration
    # =========================================================================

    # Path to your original tube squeezer STL file
    ORIGINAL_MODEL = Path("~/Downloads/toothpaste_squeezer.stl").expanduser()

    # Original tube diameter the squeezer was designed for (mm)
    ORIGINAL_TUBE_DIAMETER = 25.0  # Standard toothpaste tube

    # Target bottle diameter (mm)
    # Gold Bond 5.5oz lotion bottle is approximately 65mm diameter
    TARGET_BOTTLE_DIAMETER = 65.0

    # =========================================================================
    # Step 1: Analyze Original Model
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 1: Analyzing original model")
    print("=" * 60)

    from bambustudio_mcp.models import ModelAnalyzer

    analyzer = ModelAnalyzer()

    # In real usage, this would analyze your actual STL file
    # For demonstration, we'll show what the output would look like
    print(f"""
Model Analysis Results:
- File: {ORIGINAL_MODEL}
- Dimensions: 38mm (W) x 45mm (D) x 35mm (H)
- Triangles: 12,450
- Watertight: Yes
- Detected slot width: ~27mm (for {ORIGINAL_TUBE_DIAMETER}mm tube + clearance)

Recommendations:
- Model is suitable for scaling
- Slot detected - use tube_squeezer scaling mode
""")

    # =========================================================================
    # Step 2: Calculate and Apply Scaling
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 2: Scaling model for lotion bottle")
    print("=" * 60)

    from bambustudio_mcp.models import ModelScaler

    scaler = ModelScaler()

    # Calculate scale factor
    scale_factor = TARGET_BOTTLE_DIAMETER / ORIGINAL_TUBE_DIAMETER
    print(f"""
Scaling Calculation:
- Original tube diameter: {ORIGINAL_TUBE_DIAMETER}mm
- Target bottle diameter: {TARGET_BOTTLE_DIAMETER}mm
- Scale factor: {scale_factor:.2f}x ({scale_factor * 100:.0f}%)

Scaled Dimensions:
- Width: {38 * scale_factor:.1f}mm (was 38mm)
- Depth: {45 * scale_factor:.1f}mm (was 45mm)
- Height: {35 * scale_factor:.1f}mm (was 35mm)

Structural Recommendations:
- Recommend increasing wall thickness by 20% for larger size
- Use tube_squeezer_strong preset for heavy-duty use
""")

    # In real usage:
    # result = scaler.scale_for_tube_squeezer(
    #     input_path=ORIGINAL_MODEL,
    #     original_tube_diameter_mm=ORIGINAL_TUBE_DIAMETER,
    #     target_tube_diameter_mm=TARGET_BOTTLE_DIAMETER,
    # )
    # print(f"Scaled model saved to: {result.scaled_path}")

    # =========================================================================
    # Step 3: Configure Slicing Parameters
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 3: Configuring slicing parameters")
    print("=" * 60)

    from bambustudio_mcp.slicer.parameters import (
        SlicingParameters,
        PRESET_TUBE_SQUEEZER_STRONG,
        adjust_for_scale,
    )

    # Start with the strong preset (better for larger prints)
    base_params = PRESET_TUBE_SQUEEZER_STRONG.parameters

    # Adjust for scale
    adjusted_params = adjust_for_scale(base_params, scale_factor)

    print(f"""
Slicing Parameters (tube_squeezer_strong preset, adjusted for {scale_factor:.1f}x scale):

Layer Settings:
- Layer height: {adjusted_params.layer_height}mm
- Initial layer: {adjusted_params.initial_layer_height}mm

Strength Settings:
- Wall loops: {adjusted_params.wall_loops} (extra for larger size)
- Infill density: {adjusted_params.sparse_infill_density}%
- Infill pattern: {adjusted_params.sparse_infill_pattern.value}

Adhesion:
- Brim width: {adjusted_params.brim_width}mm (important for larger prints)
- Bed type: {adjusted_params.bed_type.value}

Speed:
- Outer wall: {adjusted_params.outer_wall_speed}mm/s
- Inner wall: {adjusted_params.inner_wall_speed}mm/s
""")

    # =========================================================================
    # Step 4: Slice with BambuStudio
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 4: Slicing with BambuStudio CLI")
    print("=" * 60)

    from bambustudio_mcp.slicer.cli import BambuStudioCLI

    cli = BambuStudioCLI()
    available, message = cli.is_available()

    if available:
        print(f"BambuStudio CLI: {message}")
        print("""
Slicing command would be:
/Applications/BambuStudio.app/Contents/MacOS/BambuStudio \\
    --orient \\
    --arrange 1 \\
    --curr-bed-type="Cool Plate" \\
    --slice 0 \\
    --export-3mf /path/to/output.3mf \\
    /path/to/scaled_model.stl

Expected output:
- Output: lotion_squeezer_65mm.3mf
- Estimated time: ~2h 45m
- Estimated filament: ~85g
- Layers: 175
""")
    else:
        print(f"BambuStudio not available: {message}")
        print("Install BambuStudio from: https://bambulab.com/en/download/studio")

    # =========================================================================
    # Step 5: Create Iteration Record
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 5: Creating iteration record for tracking")
    print("=" * 60)

    from bambustudio_mcp.iteration.tracker import IterationTracker

    tracker = IterationTracker()
    await tracker.initialize()

    iteration = await tracker.create_iteration(
        model_name="lotion_bottle_squeezer",
        model_path=str(ORIGINAL_MODEL),
        scale_factor=scale_factor,
        preset_name="tube_squeezer_strong",
    )

    print(f"""
Iteration Created:
- ID: {iteration.iteration_id}
- Model: {iteration.model_name}
- Scale: {iteration.scale_factor:.2f}x
- Preset: {iteration.preset_name}
- Status: {iteration.status}

Use this ID to record the outcome after printing.
""")

    # =========================================================================
    # Step 6: Print Monitoring (simulated)
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 6: Print monitoring and quality analysis")
    print("=" * 60)

    print("""
During printing, the MCP can:

1. Monitor printer status via MQTT:
   - Temperature tracking (nozzle, bed)
   - Progress percentage and layer count
   - Time remaining estimates

2. Capture camera frames:
   - RTSPS stream at 1 FPS
   - Save snapshots for analysis

3. Analyze print quality:
   - Detect layer shifts
   - Identify stringing
   - Spot warping issues
   - Alert on spaghetti failures

4. Recommend actions:
   - Pause if critical defects detected
   - Suggest parameter adjustments for next iteration
""")

    # =========================================================================
    # Step 7: Record Outcome (simulated successful print)
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 7: Recording print outcome")
    print("=" * 60)

    # Simulate a successful print with minor stringing
    updated = await tracker.record_outcome(
        iteration_id=iteration.iteration_id,
        status="completed",
        quality_score=85.0,
        defects=["stringing"],
        notes="Print completed successfully. Minor stringing on travel moves.",
        print_time_minutes=165,
    )

    print(f"""
Outcome Recorded:
- Status: {updated.status}
- Quality Score: {updated.quality_score}/100
- Print Time: {updated.print_time_minutes} minutes
- Defects: {', '.join(updated.defects_detected) or 'None'}

Improvement Suggestions:
""")
    for suggestion in updated.improvement_suggestions:
        print(f"  - {suggestion}")

    # =========================================================================
    # Step 8: Get Recommendations for Next Print
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 8: Recommendations for next iteration")
    print("=" * 60)

    from bambustudio_mcp.iteration.recommender import ParameterRecommender

    recommender = ParameterRecommender()
    recommendations = recommender.get_recommendations(
        current_params=adjusted_params,
        defects=["stringing"],
        iterations=[updated],
    )

    print(recommender.get_summary(recommendations))

    print("\n" + "=" * 60)
    print("WORKFLOW COMPLETE")
    print("=" * 60)
    print("""
Summary:
1. ✅ Analyzed original toothpaste squeezer model
2. ✅ Scaled from 25mm to 65mm tube diameter (2.6x)
3. ✅ Configured heavy-duty slicing parameters
4. ✅ Ready for BambuStudio slicing
5. ✅ Created iteration tracking record
6. ✅ Print monitoring available via camera/MQTT
7. ✅ Recorded outcome with quality assessment
8. ✅ Generated recommendations for next print

The scaled lotion bottle squeezer is ready for printing!
""")


if __name__ == "__main__":
    asyncio.run(main())
