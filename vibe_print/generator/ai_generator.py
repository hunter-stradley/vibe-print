"""
AI Model Generator - Integration with AI-powered 3D generation services.

Supports multiple AI 3D generation APIs for creating organic/complex models
that are difficult to generate parametrically.

Supported services:
- Meshy (text-to-3D and image-to-3D)
- Tripo3D (text-to-3D)
- OpenAI Point-E / Shap-E (experimental)
"""

import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List
import httpx

from vibe_print.generator.parametric import GeneratedModel


class AIProvider(str, Enum):
    """Supported AI 3D generation providers."""
    MESHY = "meshy"
    TRIPO3D = "tripo3d"
    POINT_E = "point_e"
    LOCAL = "local"  # Local models like stable-dreamfusion


@dataclass
class AIGenerationRequest:
    """Request for AI 3D generation."""
    prompt: str
    style: str = "realistic"  # realistic, cartoon, sculpture, etc.
    reference_image_path: Optional[Path] = None
    negative_prompt: str = ""

    # Quality settings
    resolution: str = "medium"  # low, medium, high
    format: str = "glb"  # glb, obj, stl

    # Provider-specific options
    provider_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIGenerationStatus:
    """Status of an AI generation job."""
    job_id: str
    provider: AIProvider
    status: str  # pending, processing, completed, failed
    progress: float = 0.0
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "provider": self.provider.value,
            "status": self.status,
            "progress": round(self.progress * 100, 1),
            "result_url": self.result_url,
            "error": self.error_message,
        }


class AIModelGenerator:
    """
    AI-powered 3D model generation.

    Integrates with cloud AI services to generate 3D models from
    text descriptions and/or reference images.
    """

    # API endpoints
    MESHY_API_BASE = "https://api.meshy.ai/v2"
    TRIPO3D_API_BASE = "https://api.tripo3d.ai/v1"

    def __init__(
        self,
        meshy_api_key: Optional[str] = None,
        tripo3d_api_key: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ):
        """
        Initialize AI generator.

        Args:
            meshy_api_key: Meshy API key (or set MESHY_API_KEY env var)
            tripo3d_api_key: Tripo3D API key (or set TRIPO3D_API_KEY env var)
            output_dir: Directory for downloaded models
        """
        self.meshy_key = meshy_api_key or os.getenv("MESHY_API_KEY", "")
        self.tripo3d_key = tripo3d_api_key or os.getenv("TRIPO3D_API_KEY", "")

        self.output_dir = output_dir or Path.home() / ".bambustudio-mcp" / "ai_generated"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._active_jobs: Dict[str, AIGenerationStatus] = {}

    def get_available_providers(self) -> List[Dict[str, Any]]:
        """Get list of available AI providers."""
        providers = []

        if self.meshy_key:
            providers.append({
                "name": "meshy",
                "display_name": "Meshy",
                "capabilities": ["text-to-3d", "image-to-3d"],
                "formats": ["glb", "obj", "fbx", "stl"],
                "available": True,
            })

        if self.tripo3d_key:
            providers.append({
                "name": "tripo3d",
                "display_name": "Tripo3D",
                "capabilities": ["text-to-3d"],
                "formats": ["glb", "obj"],
                "available": True,
            })

        if not providers:
            providers.append({
                "name": "none",
                "display_name": "No AI Provider Configured",
                "capabilities": [],
                "formats": [],
                "available": False,
                "setup_hint": "Set MESHY_API_KEY or TRIPO3D_API_KEY environment variable",
            })

        return providers

    async def generate_text_to_3d(
        self,
        prompt: str,
        style: str = "realistic",
        provider: Optional[AIProvider] = None,
        negative_prompt: str = "",
    ) -> AIGenerationStatus:
        """
        Generate a 3D model from a text description.

        Args:
            prompt: Description of the model to generate
            style: Art style (realistic, cartoon, sculpture)
            provider: Which AI provider to use
            negative_prompt: What to avoid in the generation

        Returns:
            AIGenerationStatus with job ID for tracking
        """
        # Select provider
        if provider is None:
            if self.meshy_key:
                provider = AIProvider.MESHY
            elif self.tripo3d_key:
                provider = AIProvider.TRIPO3D
            else:
                return AIGenerationStatus(
                    job_id="",
                    provider=AIProvider.LOCAL,
                    status="failed",
                    error_message="No AI provider configured. Set MESHY_API_KEY or TRIPO3D_API_KEY.",
                )

        if provider == AIProvider.MESHY:
            return await self._meshy_text_to_3d(prompt, style, negative_prompt)
        elif provider == AIProvider.TRIPO3D:
            return await self._tripo3d_text_to_3d(prompt, style)
        else:
            return AIGenerationStatus(
                job_id="",
                provider=provider,
                status="failed",
                error_message=f"Provider {provider.value} not implemented",
            )

    async def generate_image_to_3d(
        self,
        image_path: Path | str,
        prompt: Optional[str] = None,
    ) -> AIGenerationStatus:
        """
        Generate a 3D model from a reference image.

        Args:
            image_path: Path to reference image
            prompt: Optional text guidance

        Returns:
            AIGenerationStatus with job ID
        """
        image_path = Path(image_path)
        if not image_path.exists():
            return AIGenerationStatus(
                job_id="",
                provider=AIProvider.MESHY,
                status="failed",
                error_message=f"Image not found: {image_path}",
            )

        if self.meshy_key:
            return await self._meshy_image_to_3d(image_path, prompt)
        else:
            return AIGenerationStatus(
                job_id="",
                provider=AIProvider.MESHY,
                status="failed",
                error_message="Image-to-3D requires Meshy API key",
            )

    async def get_job_status(self, job_id: str) -> Optional[AIGenerationStatus]:
        """Get status of a generation job."""
        if job_id in self._active_jobs:
            status = self._active_jobs[job_id]

            # Refresh status from API if processing
            if status.status == "processing":
                if status.provider == AIProvider.MESHY:
                    return await self._meshy_get_status(job_id)
                elif status.provider == AIProvider.TRIPO3D:
                    return await self._tripo3d_get_status(job_id)

            return status

        return None

    async def download_result(
        self,
        job_id: str,
        output_format: str = "stl",
    ) -> Optional[GeneratedModel]:
        """
        Download completed model.

        Args:
            job_id: Generation job ID
            output_format: Desired format (stl, glb, obj)

        Returns:
            GeneratedModel with path to downloaded file
        """
        status = await self.get_job_status(job_id)
        if not status or status.status != "completed" or not status.result_url:
            return None

        # Download the model
        async with httpx.AsyncClient() as client:
            response = await client.get(status.result_url, timeout=120)
            if response.status_code != 200:
                return None

            # Save to file
            output_path = self.output_dir / f"{job_id}.{output_format}"
            with open(output_path, "wb") as f:
                f.write(response.content)

            return GeneratedModel(
                name=job_id,
                output_path=output_path,
                format=output_format,
                method=f"ai_{status.provider.value}",
                generation_notes=[f"AI generated with {status.provider.value}"],
            )

    # =========================================================================
    # Meshy API Implementation
    # =========================================================================

    async def _meshy_text_to_3d(
        self,
        prompt: str,
        style: str,
        negative_prompt: str,
    ) -> AIGenerationStatus:
        """Generate with Meshy text-to-3D API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.MESHY_API_BASE}/text-to-3d",
                headers={
                    "Authorization": f"Bearer {self.meshy_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "mode": "preview",  # preview or refine
                    "prompt": prompt,
                    "art_style": style,
                    "negative_prompt": negative_prompt,
                },
                timeout=30,
            )

            if response.status_code != 200 and response.status_code != 202:
                return AIGenerationStatus(
                    job_id="",
                    provider=AIProvider.MESHY,
                    status="failed",
                    error_message=f"Meshy API error: {response.text}",
                )

            data = response.json()
            job_id = data.get("result", "")

            status = AIGenerationStatus(
                job_id=job_id,
                provider=AIProvider.MESHY,
                status="processing",
                progress=0.0,
            )

            self._active_jobs[job_id] = status
            return status

    async def _meshy_image_to_3d(
        self,
        image_path: Path,
        prompt: Optional[str],
    ) -> AIGenerationStatus:
        """Generate with Meshy image-to-3D API."""
        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.MESHY_API_BASE}/image-to-3d",
                headers={
                    "Authorization": f"Bearer {self.meshy_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "image_url": f"data:image/png;base64,{image_data}",
                    "enable_pbr": True,
                },
                timeout=30,
            )

            if response.status_code not in (200, 202):
                return AIGenerationStatus(
                    job_id="",
                    provider=AIProvider.MESHY,
                    status="failed",
                    error_message=f"Meshy API error: {response.text}",
                )

            data = response.json()
            job_id = data.get("result", "")

            status = AIGenerationStatus(
                job_id=job_id,
                provider=AIProvider.MESHY,
                status="processing",
            )

            self._active_jobs[job_id] = status
            return status

    async def _meshy_get_status(self, job_id: str) -> AIGenerationStatus:
        """Get Meshy job status."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.MESHY_API_BASE}/text-to-3d/{job_id}",
                headers={"Authorization": f"Bearer {self.meshy_key}"},
                timeout=30,
            )

            if response.status_code != 200:
                return self._active_jobs.get(job_id, AIGenerationStatus(
                    job_id=job_id,
                    provider=AIProvider.MESHY,
                    status="failed",
                ))

            data = response.json()
            status = data.get("status", "PENDING")
            progress = data.get("progress", 0) / 100.0

            result_status = AIGenerationStatus(
                job_id=job_id,
                provider=AIProvider.MESHY,
                status="completed" if status == "SUCCEEDED" else "processing" if status == "PENDING" else "failed",
                progress=progress,
                result_url=data.get("model_urls", {}).get("glb"),
            )

            self._active_jobs[job_id] = result_status
            return result_status

    # =========================================================================
    # Tripo3D API Implementation
    # =========================================================================

    async def _tripo3d_text_to_3d(
        self,
        prompt: str,
        style: str,
    ) -> AIGenerationStatus:
        """Generate with Tripo3D text-to-3D API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.TRIPO3D_API_BASE}/generation",
                headers={
                    "Authorization": f"Bearer {self.tripo3d_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "prompt": prompt,
                    "style": style,
                },
                timeout=30,
            )

            if response.status_code not in (200, 202):
                return AIGenerationStatus(
                    job_id="",
                    provider=AIProvider.TRIPO3D,
                    status="failed",
                    error_message=f"Tripo3D API error: {response.text}",
                )

            data = response.json()
            job_id = data.get("task_id", "")

            status = AIGenerationStatus(
                job_id=job_id,
                provider=AIProvider.TRIPO3D,
                status="processing",
            )

            self._active_jobs[job_id] = status
            return status

    async def _tripo3d_get_status(self, job_id: str) -> AIGenerationStatus:
        """Get Tripo3D job status."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.TRIPO3D_API_BASE}/generation/{job_id}",
                headers={"Authorization": f"Bearer {self.tripo3d_key}"},
                timeout=30,
            )

            if response.status_code != 200:
                return self._active_jobs.get(job_id, AIGenerationStatus(
                    job_id=job_id,
                    provider=AIProvider.TRIPO3D,
                    status="failed",
                ))

            data = response.json()
            task_status = data.get("status", "pending")

            result_status = AIGenerationStatus(
                job_id=job_id,
                provider=AIProvider.TRIPO3D,
                status="completed" if task_status == "success" else "processing" if task_status == "pending" else "failed",
                progress=data.get("progress", 0) / 100.0,
                result_url=data.get("output", {}).get("model"),
            )

            self._active_jobs[job_id] = result_status
            return result_status


# Convenience functions
async def generate_from_text(
    prompt: str,
    style: str = "realistic",
) -> AIGenerationStatus:
    """Quick text-to-3D generation."""
    generator = AIModelGenerator()
    return await generator.generate_text_to_3d(prompt, style)


async def generate_from_image(
    image_path: Path | str,
) -> AIGenerationStatus:
    """Quick image-to-3D generation."""
    generator = AIModelGenerator()
    return await generator.generate_image_to_3d(image_path)
