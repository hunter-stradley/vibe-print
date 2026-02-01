#!/usr/bin/env python3
"""
Complete Workflow: From Requirements to Perfect Print

This script demonstrates the full end-to-end workflow:
1. Parse natural language requirements
2. Optionally analyze a reference image for dimensions
3. Generate a 3D model (template or parametric)
4. Scale if needed
5. Slice with optimized parameters
6. Print and monitor
7. Detect defects and iterate

Example use case: Creating a tube squeezer for a lotion bottle
based on the reference image showing the bottle dimensions.
"""

import asyncio
from pathlib import Path


async def complete_workflow():
    """
    Full workflow from "I need X" to perfect printed object.
    """

    # =========================================================================
    # PHASE 1: UNDERSTAND REQUIREMENTS
    # =========================================================================
    print("\n" + "=" * 70)
    print("PHASE 1: UNDERSTANDING REQUIREMENTS")
    print("=" * 70)

    # User's natural language request
    user_request = """
    I need a tube squeezer for my lotion bottle.
    The bottle is about 65mm diameter. I want it to be heavy duty
    since lotion is thicker than toothpaste and needs more force.
    """

    print(f"\nUser Request:\n{user_request.strip()}")

    from vibe_print.generator.requirements import RequirementsParser

    parser = RequirementsParser()
    requirements = parser.parse(user_request)

    print(f"""
Parsed Requirements:
- Category: {requirements.category.value}
- Primary dimension: {requirements.get_primary_dimension_mm()}mm
- Needs strength: {requirements.needs_strength}
- Fit type: {requirements.fit_type.value}
- Wall thickness: {requirements.wall_thickness_mm}mm
- Reference object: {requirements.reference_object}
""")

    # =========================================================================
    # PHASE 2: ANALYZE REFERENCE IMAGE (if provided)
    # =========================================================================
    print("\n" + "=" * 70)
    print("PHASE 2: REFERENCE IMAGE ANALYSIS")
    print("=" * 70)

    # In real usage, this would analyze the user's uploaded image
    # showing the lotion bottle next to a ruler

    print("""
If user provides a reference image:
- Detect ruler/scale markings for accurate calibration
- Measure bottle diameter from the image
- Extract any design features from similar products

Example analysis from the provided image:
- Detected ruler: Yes (10cm visible)
- Measured bottle width: ~65mm
- Existing squeezer visible: ~38mm (for smaller tube)
- Scale factor needed: 65/25 = 2.6x
""")

    # =========================================================================
    # PHASE 3: GENERATE 3D MODEL
    # =========================================================================
    print("\n" + "=" * 70)
    print("PHASE 3: GENERATING 3D MODEL")
    print("=" * 70)

    from vibe_print.generator.templates import TubeSqueezerTemplate

    template = TubeSqueezerTemplate()

    # Show available parameters
    print("\nTube Squeezer Template Parameters:")
    for param in template.parameters:
        print(f"  - {param.name}: {param.description}")
        print(f"    Default: {param.default_value}{param.unit}, Range: {param.min_value}-{param.max_value}")

    # Generate with custom parameters
    custom_params = {
        "tube_diameter": 65.0,       # For lotion bottle
        "clearance": 1.5,            # Extra clearance for thick lotion residue
        "wall_thickness": 3.0,       # Heavy duty
        "handle_width": 18.0,        # Wider handles for better grip
        "add_grip_texture": 1.0,     # Add grip ridges
    }

    print(f"\nGenerating with custom parameters:")
    for k, v in custom_params.items():
        print(f"  {k}: {v}")

    # In real usage:
    # output_path = Path("/tmp/lotion_squeezer_65mm.stl")
    # template.generate(custom_params, output_path)
    # print(f"\nGenerated: {output_path}")

    print("""
Generated Model Dimensions:
- Slot width: 66.5mm (65mm + 1.5mm clearance)
- Body width: 102.5mm (slot + 2 handles)
- Body depth: 48.75mm (75% of tube diameter)
- Body height: 71.5mm
- Method: CadQuery parametric generation
- Output: /tmp/vibe-print/generated/lotion_squeezer_65mm.stl
""")

    # =========================================================================
    # PHASE 4: OPTIMIZE SLICING PARAMETERS
    # =========================================================================
    print("\n" + "=" * 70)
    print("PHASE 4: OPTIMIZING SLICING PARAMETERS")
    print("=" * 70)

    from vibe_print.slicer.parameters import (
        SlicingParameters,
        PRESET_TUBE_SQUEEZER_STRONG,
        adjust_for_scale,
    )

    # Start with heavy-duty preset
    base_params = PRESET_TUBE_SQUEEZER_STRONG.parameters

    # Adjust for larger size
    scale_factor = 65.0 / 25.0  # From standard toothpaste to lotion
    adjusted = adjust_for_scale(base_params, scale_factor)

    print(f"""
Slicing Parameters (optimized for {scale_factor:.1f}x scale):

Structure:
- Layer height: {adjusted.layer_height}mm
- Wall loops: {adjusted.wall_loops}
- Infill: {adjusted.sparse_infill_density}% {adjusted.sparse_infill_pattern.value}

Speed:
- Outer wall: {adjusted.outer_wall_speed}mm/s
- Inner wall: {adjusted.inner_wall_speed}mm/s

Adhesion:
- Brim width: {adjusted.brim_width}mm
- First layer speed: {adjusted.initial_layer_speed}mm/s
""")

    # =========================================================================
    # PHASE 5: CREATE ITERATION RECORD
    # =========================================================================
    print("\n" + "=" * 70)
    print("PHASE 5: TRACKING ITERATION")
    print("=" * 70)

    from vibe_print.iteration.tracker import IterationTracker

    tracker = IterationTracker()
    await tracker.initialize()

    iteration = await tracker.create_iteration(
        model_name="lotion_squeezer",
        model_path="/tmp/lotion_squeezer_65mm.stl",
        scale_factor=scale_factor,
        preset_name="tube_squeezer_strong_adjusted",
    )

    print(f"""
Iteration Created:
- ID: {iteration.iteration_id}
- Model: {iteration.model_name}
- Scale: {iteration.scale_factor:.2f}x
- Status: {iteration.status}

This will track the print outcome and enable learning for future prints.
""")

    # =========================================================================
    # PHASE 6: PRINT MONITORING (simulated)
    # =========================================================================
    print("\n" + "=" * 70)
    print("PHASE 6: PRINT MONITORING")
    print("=" * 70)

    print("""
During printing, the MCP continuously:

1. Monitors printer status via MQTT:
   - Nozzle temp: 220C / 220C
   - Bed temp: 60C / 60C
   - Progress: 45% (layer 78/175)
   - Time remaining: ~1h 30m

2. Captures camera frames (1 FPS):
   - Analyzing frame 2847...
   - No defects detected
   - Quality score: 95/100

3. Watches for issues:
   - No layer shifts
   - No stringing
   - No warping
   - Good bed adhesion
""")

    # =========================================================================
    # PHASE 7: RECORD OUTCOME & GET RECOMMENDATIONS
    # =========================================================================
    print("\n" + "=" * 70)
    print("PHASE 7: OUTCOME & RECOMMENDATIONS")
    print("=" * 70)

    # Simulate completed print with minor stringing
    updated = await tracker.record_outcome(
        iteration_id=iteration.iteration_id,
        status="completed",
        quality_score=88.0,
        defects=["stringing"],
        notes="Successful print. Minor stringing on travel moves.",
        print_time_minutes=175,
    )

    print(f"""
Print Completed:
- Quality Score: {updated.quality_score}/100
- Print Time: {updated.print_time_minutes} minutes
- Defects: {', '.join(updated.defects_detected)}

Improvement Suggestions for Next Print:
""")
    for i, suggestion in enumerate(updated.improvement_suggestions, 1):
        print(f"  {i}. {suggestion}")

    # Get parameter recommendations
    from vibe_print.iteration.recommender import ParameterRecommender

    recommender = ParameterRecommender()
    recommendations = recommender.get_recommendations(
        current_params=adjusted,
        defects=updated.defects_detected,
        iterations=[updated],
    )

    print("\nParameter Adjustments for Next Iteration:")
    for rec in recommendations[:3]:
        print(f"  - {rec.parameter}: {rec.current_value} -> {rec.suggested_value}")
        print(f"    Reason: {rec.reason}")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("WORKFLOW COMPLETE")
    print("=" * 70)

    print("""
Summary of what was accomplished:

1. Parsed "I need a tube squeezer for my lotion bottle" into structured requirements
2. Determined tube_squeezer category, 65mm diameter, heavy-duty needs
3. Generated parametric 3D model using CadQuery
4. Optimized slicing parameters for 2.6x scaled print
5. Created iteration record for tracking
6. (Simulated) Monitored print with camera-based quality analysis
7. Recorded outcome with 88% quality score
8. Generated recommendations for next iteration

The lotion bottle squeezer is ready! For the next print:
- Increase retraction by 0.5mm to reduce stringing
- Lower nozzle temp by 5C
""")


if __name__ == "__main__":
    asyncio.run(complete_workflow())
