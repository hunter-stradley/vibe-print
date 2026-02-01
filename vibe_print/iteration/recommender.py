"""
Parameter Recommender - Suggest parameter improvements based on print history.

Analyzes past prints to recommend parameter adjustments for better results.
"""

import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from vibe_print.slicer.parameters import SlicingParameters
from vibe_print.camera.detector import DefectType
from vibe_print.iteration.tracker import PrintIteration


@dataclass
class Recommendation:
    """A parameter adjustment recommendation."""
    parameter: str
    current_value: Any
    suggested_value: Any
    reason: str
    confidence: float  # 0.0 to 1.0
    priority: int = 1  # 1 = highest priority

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "parameter": self.parameter,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
            "priority": self.priority,
        }


class ParameterRecommender:
    """
    Recommends parameter adjustments based on print history and defects.

    Uses heuristic rules based on common 3D printing troubleshooting knowledge.
    """

    # Defect to parameter adjustment mappings
    DEFECT_ADJUSTMENTS = {
        DefectType.LAYER_SHIFT.value: [
            ("outer_wall_speed", -10, "Reduce outer wall speed to minimize vibration"),
            ("inner_wall_speed", -15, "Reduce inner wall speed"),
            ("travel_speed", -50, "Reduce travel speed to minimize jerky movements"),
        ],
        DefectType.STRINGING.value: [
            ("retraction_length", +0.5, "Increase retraction to reduce oozing"),
            ("retraction_speed", +5, "Increase retraction speed"),
            ("nozzle_temperature", -5, "Lower temperature reduces oozing"),
            ("travel_speed", +20, "Faster travel gives less time to ooze"),
        ],
        DefectType.WARPING.value: [
            ("bed_temperature", +5, "Higher bed temp improves adhesion"),
            ("bed_temperature_initial_layer", +10, "Higher initial bed temp"),
            ("brim_width", +5, "Larger brim for better adhesion"),
            ("initial_layer_speed", -10, "Slower first layer for better adhesion"),
        ],
        DefectType.BLOB.value: [
            ("retraction_length", +0.3, "More retraction at seams"),
            ("outer_wall_speed", -5, "Slower walls for cleaner seams"),
        ],
        DefectType.UNDER_EXTRUSION.value: [
            ("nozzle_temperature", +10, "Higher temp for better flow"),
            ("sparse_infill_speed", -20, "Slower infill to ensure full extrusion"),
        ],
        DefectType.OVER_EXTRUSION.value: [
            ("nozzle_temperature", -5, "Lower temp to reduce flow"),
        ],
        DefectType.POOR_ADHESION.value: [
            ("bed_temperature_initial_layer", +10, "Higher bed temp for adhesion"),
            ("initial_layer_height", +0.05, "Thicker first layer squishes better"),
            ("initial_layer_speed", -10, "Slower first layer"),
            ("brim_width", +8, "Add substantial brim"),
        ],
        DefectType.SPAGHETTI.value: [
            ("brim_width", +10, "Significant brim needed"),
            ("initial_layer_speed", -15, "Much slower first layer"),
            ("bed_temperature_initial_layer", +15, "Higher bed temp"),
            ("initial_layer_height", +0.1, "Thicker first layer"),
        ],
    }

    def __init__(self):
        """Initialize recommender."""
        pass

    def get_recommendations(
        self,
        current_params: SlicingParameters,
        defects: List[str],
        quality_score: Optional[float] = None,
        iterations: Optional[List[PrintIteration]] = None,
    ) -> List[Recommendation]:
        """
        Get parameter recommendations based on defects and history.

        Args:
            current_params: Current slicing parameters
            defects: List of defect types detected
            quality_score: Current quality score
            iterations: Historical print iterations for context

        Returns:
            List of recommendations, sorted by priority
        """
        recommendations = []
        seen_params = set()

        # Generate recommendations based on defects
        for defect in defects:
            if defect in self.DEFECT_ADJUSTMENTS:
                for param, adjustment, reason in self.DEFECT_ADJUSTMENTS[defect]:
                    if param in seen_params:
                        continue  # Avoid duplicate recommendations
                    seen_params.add(param)

                    current_value = getattr(current_params, param, None)
                    if current_value is None:
                        continue

                    suggested_value = current_value + adjustment

                    # Apply reasonable limits
                    suggested_value = self._apply_limits(param, suggested_value)

                    recommendations.append(Recommendation(
                        parameter=param,
                        current_value=current_value,
                        suggested_value=suggested_value,
                        reason=f"{reason} (addressing {defect})",
                        confidence=0.7,
                        priority=self._get_defect_priority(defect),
                    ))

        # Add recommendations based on quality score
        if quality_score is not None and quality_score < 50:
            # Low quality - suggest more conservative settings
            if "outer_wall_speed" not in seen_params:
                recommendations.append(Recommendation(
                    parameter="outer_wall_speed",
                    current_value=current_params.outer_wall_speed,
                    suggested_value=max(30, current_params.outer_wall_speed * 0.7),
                    reason="Significantly reduce speed for better quality",
                    confidence=0.6,
                    priority=2,
                ))

        # Learn from history if available
        if iterations:
            history_recs = self._learn_from_history(current_params, iterations)
            for rec in history_recs:
                if rec.parameter not in seen_params:
                    recommendations.append(rec)
                    seen_params.add(rec.parameter)

        # Sort by priority (lower = higher priority)
        recommendations.sort(key=lambda r: (r.priority, -r.confidence))

        return recommendations

    def _apply_limits(self, param: str, value: Any) -> Any:
        """Apply reasonable limits to parameter values."""
        limits = {
            "outer_wall_speed": (20, 150),
            "inner_wall_speed": (30, 200),
            "sparse_infill_speed": (50, 300),
            "travel_speed": (100, 500),
            "nozzle_temperature": (180, 280),
            "bed_temperature": (40, 110),
            "bed_temperature_initial_layer": (40, 110),
            "retraction_length": (0.2, 5.0),
            "retraction_speed": (20, 80),
            "brim_width": (0, 20),
            "initial_layer_speed": (10, 50),
            "initial_layer_height": (0.1, 0.4),
            "layer_height": (0.08, 0.32),
        }

        if param in limits:
            min_val, max_val = limits[param]
            return max(min_val, min(max_val, value))

        return value

    def _get_defect_priority(self, defect: str) -> int:
        """Get priority level for a defect type."""
        priorities = {
            DefectType.SPAGHETTI.value: 1,  # Critical
            DefectType.LAYER_SHIFT.value: 1,
            DefectType.POOR_ADHESION.value: 1,
            DefectType.WARPING.value: 2,
            DefectType.UNDER_EXTRUSION.value: 2,
            DefectType.OVER_EXTRUSION.value: 3,
            DefectType.STRINGING.value: 3,
            DefectType.BLOB.value: 4,
        }
        return priorities.get(defect, 5)

    def _learn_from_history(
        self,
        current_params: SlicingParameters,
        iterations: List[PrintIteration],
    ) -> List[Recommendation]:
        """
        Learn parameter suggestions from historical successful prints.

        Looks at successful prints with similar models to suggest parameters.
        """
        recommendations = []

        # Find successful prints with good quality
        successful = [
            i for i in iterations
            if i.status == "completed"
            and i.quality_score is not None
            and i.quality_score > 80
            and i.parameters is not None
        ]

        if not successful:
            return recommendations

        # Find the best print
        best = max(successful, key=lambda i: i.quality_score or 0)

        if best.parameters:
            best_params = best.parameters

            # Compare key parameters and suggest differences
            compare_params = [
                "layer_height",
                "wall_loops",
                "sparse_infill_density",
                "outer_wall_speed",
            ]

            for param in compare_params:
                current = getattr(current_params, param, None)
                best_value = best_params.get(param)

                if current is not None and best_value is not None and current != best_value:
                    recommendations.append(Recommendation(
                        parameter=param,
                        current_value=current,
                        suggested_value=best_value,
                        reason=f"Value used in successful print (quality: {best.quality_score:.0f}%)",
                        confidence=0.5,
                        priority=3,
                    ))

        return recommendations

    def apply_recommendations(
        self,
        params: SlicingParameters,
        recommendations: List[Recommendation],
        max_changes: int = 3,
    ) -> SlicingParameters:
        """
        Apply top recommendations to parameters.

        Args:
            params: Current parameters
            recommendations: List of recommendations
            max_changes: Maximum number of changes to apply

        Returns:
            New SlicingParameters with adjustments
        """
        import copy
        new_params = copy.deepcopy(params)

        # Apply top recommendations
        for rec in recommendations[:max_changes]:
            if hasattr(new_params, rec.parameter):
                setattr(new_params, rec.parameter, rec.suggested_value)

        return new_params

    def get_summary(self, recommendations: List[Recommendation]) -> str:
        """Get human-readable summary of recommendations."""
        if not recommendations:
            return "No parameter adjustments recommended. Current settings look good!"

        lines = [f"## Parameter Recommendations ({len(recommendations)} suggestions)\n"]

        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. **{rec.parameter}**: {rec.current_value} → {rec.suggested_value}")
            lines.append(f"   - {rec.reason}")
            lines.append(f"   - Confidence: {rec.confidence*100:.0f}%")
            lines.append("")

        return "\n".join(lines)
