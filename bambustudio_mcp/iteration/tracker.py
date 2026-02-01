"""
Iteration Tracker - Track print attempts and outcomes.

Stores print history in SQLite for analysis and improvement recommendations.
"""

import asyncio
import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import aiosqlite

from bambustudio_mcp.config import config
from bambustudio_mcp.slicer.parameters import SlicingParameters
from bambustudio_mcp.camera.detector import DefectType


@dataclass
class PrintIteration:
    """Record of a single print attempt."""
    iteration_id: str
    model_name: str
    model_path: str
    created_at: datetime

    # Scaling info
    original_dimensions: Optional[Dict[str, float]] = None
    scale_factor: Optional[float] = None
    scaled_dimensions: Optional[Dict[str, float]] = None

    # Parameters used
    parameters: Optional[Dict[str, Any]] = None
    preset_name: Optional[str] = None

    # Outcome
    status: str = "pending"  # pending, printing, completed, failed, cancelled
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    print_time_minutes: Optional[int] = None

    # Quality assessment
    quality_score: Optional[float] = None
    defects_detected: List[str] = field(default_factory=list)
    defect_count: int = 0

    # Notes
    notes: str = ""
    improvement_suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "iteration_id": self.iteration_id,
            "model_name": self.model_name,
            "model_path": self.model_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "original_dimensions": self.original_dimensions,
            "scale_factor": self.scale_factor,
            "scaled_dimensions": self.scaled_dimensions,
            "parameters": self.parameters,
            "preset_name": self.preset_name,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "print_time_minutes": self.print_time_minutes,
            "quality_score": self.quality_score,
            "defects_detected": self.defects_detected,
            "defect_count": self.defect_count,
            "notes": self.notes,
            "improvement_suggestions": self.improvement_suggestions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PrintIteration":
        """Create from dictionary."""
        return cls(
            iteration_id=data["iteration_id"],
            model_name=data["model_name"],
            model_path=data["model_path"],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            original_dimensions=data.get("original_dimensions"),
            scale_factor=data.get("scale_factor"),
            scaled_dimensions=data.get("scaled_dimensions"),
            parameters=data.get("parameters"),
            preset_name=data.get("preset_name"),
            status=data.get("status", "pending"),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            print_time_minutes=data.get("print_time_minutes"),
            quality_score=data.get("quality_score"),
            defects_detected=data.get("defects_detected", []),
            defect_count=data.get("defect_count", 0),
            notes=data.get("notes", ""),
            improvement_suggestions=data.get("improvement_suggestions", []),
        )


class IterationTracker:
    """
    Tracks print iterations and outcomes for continuous improvement.

    Uses SQLite for persistent storage of print history.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize tracker.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path or config.database_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database schema."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS iterations (
                    iteration_id TEXT PRIMARY KEY,
                    model_name TEXT NOT NULL,
                    model_path TEXT,
                    created_at TEXT NOT NULL,
                    data TEXT NOT NULL
                )
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_name
                ON iterations(model_name)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON iterations(created_at)
            """)

            await db.commit()

        self._initialized = True

    async def _ensure_initialized(self) -> None:
        """Ensure database is initialized."""
        if not self._initialized:
            await self.initialize()

    async def create_iteration(
        self,
        model_name: str,
        model_path: str,
        scale_factor: Optional[float] = None,
        original_dimensions: Optional[Dict[str, float]] = None,
        scaled_dimensions: Optional[Dict[str, float]] = None,
        parameters: Optional[SlicingParameters] = None,
        preset_name: Optional[str] = None,
    ) -> PrintIteration:
        """
        Create a new print iteration record.

        Args:
            model_name: Name of the model being printed
            model_path: Path to model file
            scale_factor: Applied scale factor
            original_dimensions: Original model dimensions
            scaled_dimensions: Scaled model dimensions
            parameters: Slicing parameters used
            preset_name: Name of preset used

        Returns:
            PrintIteration record
        """
        await self._ensure_initialized()

        import uuid
        iteration = PrintIteration(
            iteration_id=str(uuid.uuid4())[:8],
            model_name=model_name,
            model_path=model_path,
            created_at=datetime.now(),
            scale_factor=scale_factor,
            original_dimensions=original_dimensions,
            scaled_dimensions=scaled_dimensions,
            parameters=parameters.to_dict() if parameters else None,
            preset_name=preset_name,
        )

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO iterations (iteration_id, model_name, model_path, created_at, data) VALUES (?, ?, ?, ?, ?)",
                (iteration.iteration_id, model_name, model_path,
                 iteration.created_at.isoformat(), json.dumps(iteration.to_dict())),
            )
            await db.commit()

        return iteration

    async def update_iteration(self, iteration: PrintIteration) -> None:
        """Update an existing iteration record."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE iterations SET data = ? WHERE iteration_id = ?",
                (json.dumps(iteration.to_dict()), iteration.iteration_id),
            )
            await db.commit()

    async def get_iteration(self, iteration_id: str) -> Optional[PrintIteration]:
        """Get an iteration by ID."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT data FROM iterations WHERE iteration_id = ?",
                (iteration_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return PrintIteration.from_dict(json.loads(row[0]))
        return None

    async def get_iterations_for_model(
        self,
        model_name: str,
        limit: int = 10,
    ) -> List[PrintIteration]:
        """
        Get all iterations for a specific model.

        Args:
            model_name: Name of the model
            limit: Maximum number of results

        Returns:
            List of iterations, newest first
        """
        await self._ensure_initialized()

        iterations = []
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT data FROM iterations WHERE model_name = ? ORDER BY created_at DESC LIMIT ?",
                (model_name, limit),
            ) as cursor:
                async for row in cursor:
                    iterations.append(PrintIteration.from_dict(json.loads(row[0])))

        return iterations

    async def get_recent_iterations(self, limit: int = 20) -> List[PrintIteration]:
        """Get most recent iterations across all models."""
        await self._ensure_initialized()

        iterations = []
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT data FROM iterations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ) as cursor:
                async for row in cursor:
                    iterations.append(PrintIteration.from_dict(json.loads(row[0])))

        return iterations

    async def record_outcome(
        self,
        iteration_id: str,
        status: str,
        quality_score: Optional[float] = None,
        defects: Optional[List[str]] = None,
        notes: str = "",
        print_time_minutes: Optional[int] = None,
    ) -> Optional[PrintIteration]:
        """
        Record the outcome of a print attempt.

        Args:
            iteration_id: ID of the iteration
            status: Final status (completed, failed, cancelled)
            quality_score: Quality score 0-100
            defects: List of defect types detected
            notes: Additional notes
            print_time_minutes: Actual print time

        Returns:
            Updated iteration or None if not found
        """
        iteration = await self.get_iteration(iteration_id)
        if not iteration:
            return None

        iteration.status = status
        iteration.completed_at = datetime.now()
        iteration.quality_score = quality_score
        iteration.defects_detected = defects or []
        iteration.defect_count = len(iteration.defects_detected)
        iteration.notes = notes
        iteration.print_time_minutes = print_time_minutes

        # Calculate improvement suggestions based on defects
        iteration.improvement_suggestions = self._generate_suggestions(defects or [])

        await self.update_iteration(iteration)
        return iteration

    def _generate_suggestions(self, defects: List[str]) -> List[str]:
        """Generate improvement suggestions based on defects."""
        suggestions = []
        defect_set = set(defects)

        if DefectType.LAYER_SHIFT.value in defect_set:
            suggestions.append("Check belt tension and mechanical stability")
            suggestions.append("Reduce print speed")
            suggestions.append("Ensure printer is on stable surface")

        if DefectType.STRINGING.value in defect_set:
            suggestions.append("Increase retraction distance (try +0.5mm)")
            suggestions.append("Increase retraction speed (try +10mm/s)")
            suggestions.append("Lower nozzle temperature (try -5°C)")

        if DefectType.WARPING.value in defect_set:
            suggestions.append("Increase bed temperature (try +5°C)")
            suggestions.append("Add or increase brim width")
            suggestions.append("Use enclosure if available")
            suggestions.append("Slow down first layer")

        if DefectType.BLOB.value in defect_set:
            suggestions.append("Enable coasting in slicer")
            suggestions.append("Reduce extrusion multiplier slightly")
            suggestions.append("Adjust seam position")

        if DefectType.SPAGHETTI.value in defect_set:
            suggestions.append("Check bed adhesion - clean and level bed")
            suggestions.append("Increase first layer height")
            suggestions.append("Slow down first layer significantly")
            suggestions.append("Use brim or raft for better adhesion")

        if DefectType.UNDER_EXTRUSION.value in defect_set:
            suggestions.append("Increase flow rate/extrusion multiplier")
            suggestions.append("Check for clogged nozzle")
            suggestions.append("Increase nozzle temperature")

        if DefectType.OVER_EXTRUSION.value in defect_set:
            suggestions.append("Decrease flow rate/extrusion multiplier")
            suggestions.append("Calibrate E-steps")

        return suggestions

    async def get_model_statistics(self, model_name: str) -> Dict[str, Any]:
        """
        Get statistics for a model's print history.

        Args:
            model_name: Name of the model

        Returns:
            Statistics dictionary
        """
        iterations = await self.get_iterations_for_model(model_name, limit=100)

        if not iterations:
            return {"model_name": model_name, "total_attempts": 0}

        completed = [i for i in iterations if i.status == "completed"]
        failed = [i for i in iterations if i.status == "failed"]

        quality_scores = [i.quality_score for i in completed if i.quality_score is not None]

        all_defects = []
        for i in iterations:
            all_defects.extend(i.defects_detected)

        defect_counts = {}
        for d in all_defects:
            defect_counts[d] = defect_counts.get(d, 0) + 1

        return {
            "model_name": model_name,
            "total_attempts": len(iterations),
            "completed": len(completed),
            "failed": len(failed),
            "success_rate": len(completed) / len(iterations) * 100 if iterations else 0,
            "average_quality_score": sum(quality_scores) / len(quality_scores) if quality_scores else None,
            "best_quality_score": max(quality_scores) if quality_scores else None,
            "common_defects": dict(sorted(defect_counts.items(), key=lambda x: -x[1])[:5]),
            "latest_iteration": iterations[0].to_dict() if iterations else None,
        }
