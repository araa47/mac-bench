from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_PERSON_PROMPT = (
    "Describe only the visible person or people in this image in 1 to 2 short "
    "sentences. Mention clothing, hats, glasses, masks, shoes, bags, boxes, "
    "phones, packages, or other objects they are wearing or carrying. Do not "
    "mention the environment, house, porch, background, weather, doorway, camera "
    "overlay, or timestamp text unless it is strictly necessary to identify an "
    "object on the person. If something is uncertain, say probably or possibly. "
    "If no person is visible, reply with exactly: No person visible."
)
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class BenchmarkError(RuntimeError):
    """Raised when LM Studio or the local benchmark flow fails."""


@dataclass(slots=True)
class InstalledModel:
    model_key: str
    display_name: str
    format: str
    architecture: str | None
    publisher: str | None
    vision: bool
    trained_for_tool_use: bool
    params: str | None
    size_bytes: int | None
    variant: str | None
    max_context_length: int | None


@dataclass(slots=True)
class EstimateResult:
    estimated_gpu_memory_gib: float | None
    estimated_total_memory_gib: float | None
    raw_output: str


@dataclass(slots=True)
class LoadResult:
    identifier: str
    load_time_seconds: float | None
    reported_memory_gib: float | None
    raw_output: str


@dataclass(slots=True)
class BenchmarkImage:
    source_path: Path
    label: str
    title: str | None = None
    page_url: str | None = None
    source_url: str | None = None
    author: str | None = None
    license_name: str | None = None
    license_url: str | None = None
    report_path: str | None = None


@dataclass(slots=True)
class RequestProfile:
    name: str
    prompt_text: str
    temperature: float
    max_tokens: int
    extra_body: dict[str, object]


@dataclass(slots=True)
class ImageBenchmarkResult:
    image_label: str
    elapsed_seconds: float
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    response_text: str
    reasoning_present: bool
    reasoning_preview: str | None
    finish_reason: str | None
    error: str | None


@dataclass(slots=True)
class ModelBenchmarkResult:
    model_key: str
    display_name: str
    identifier: str
    profile_name: str
    format: str
    params: str | None
    variant: str | None
    estimated_gpu_memory_gib: float | None
    estimated_total_memory_gib: float | None
    load_time_seconds: float | None
    reported_memory_gib: float | None
    average_latency_seconds: float | None
    median_latency_seconds: float | None
    min_latency_seconds: float | None
    max_latency_seconds: float | None
    completion_tokens_per_second: float | None
    total_prompt_tokens: int
    total_completion_tokens: int
    images_benchmarked: int
    successful_images: int
    failed_images: int
    reasoning_seen: bool
    benchmark_error: str | None
    results: list[ImageBenchmarkResult]


@dataclass(slots=True)
class BenchmarkRun:
    started_at: datetime
    finished_at: datetime
    prompt_text: str
    machine: dict[str, object]
    images: list[BenchmarkImage]
    request_profiles: list[RequestProfile]
    summary: dict[str, object]
    model_results: list[ModelBenchmarkResult]
    excluded_models: list[InstalledModel]


@dataclass(slots=True)
class DoctorCheck:
    name: str
    status: str
    detail: str
    guidance: str | None = None


@dataclass(slots=True)
class SanitizedImageCopy:
    source_path: Path
    destination_path: Path
