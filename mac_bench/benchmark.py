from __future__ import annotations

import base64
import copy
import json
import mimetypes
import re
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

from .entities import (
    SUPPORTED_IMAGE_SUFFIXES,
    BenchmarkError,
    BenchmarkImage,
    BenchmarkRun,
    ImageBenchmarkResult,
    InstalledModel,
    ModelBenchmarkResult,
    RequestProfile,
    SanitizedImageCopy,
)
from .lm_studio import (
    collect_machine_info,
    estimate_model,
    list_installed_models,
    load_model,
    request_json,
    unload_all_models,
    wait_for_loaded_model,
)


def load_image_manifest(images_dir: Path) -> dict[str, dict[str, str]]:
    manifest_path = images_dir / "manifest.json"
    if not manifest_path.is_file():
        return {}

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BenchmarkError(
            f"Image manifest must contain a JSON object: {manifest_path}"
        )

    raw_images = payload.get("images")
    if not isinstance(raw_images, list):
        raise BenchmarkError(
            f"Image manifest must contain an `images` array: {manifest_path}"
        )

    manifest: dict[str, dict[str, str]] = {}
    for item in raw_images:
        if not isinstance(item, dict):
            raise BenchmarkError(
                f"Each image manifest entry must be an object: {manifest_path}"
            )
        filename = item.get("filename")
        if not isinstance(filename, str) or not filename.strip():
            raise BenchmarkError(
                f"Each image manifest entry needs a non-empty `filename`: {manifest_path}"
            )
        manifest[filename] = {
            key: value
            for key, value in item.items()
            if key != "filename" and isinstance(value, str) and value.strip()
        }
    return manifest


def supported_image_paths(images_dir: Path) -> list[Path]:
    if not images_dir.is_dir():
        raise BenchmarkError(f"Images directory not found: {images_dir}")
    return sorted(
        path
        for path in images_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
    )


def collect_images(
    images_dir: Path,
    limit: int | None,
    preserve_names: bool = False,
    label_prefix: str = "sample",
) -> list[BenchmarkImage]:
    image_paths = supported_image_paths(images_dir)
    image_manifest = load_image_manifest(images_dir)
    if limit is not None:
        image_paths = image_paths[:limit]
    if not image_paths:
        raise BenchmarkError(f"No supported image files found in {images_dir}")

    images: list[BenchmarkImage] = []
    for index, image_path in enumerate(image_paths, start=1):
        manifest_item = image_manifest.get(image_path.name, {})
        images.append(
            BenchmarkImage(
                source_path=image_path,
                label=(
                    image_path.name
                    if preserve_names
                    else f"{label_prefix}-{index:02d}{image_path.suffix.lower() or '.jpg'}"
                ),
                title=manifest_item.get("title"),
                page_url=manifest_item.get("page_url"),
                source_url=manifest_item.get("source_url"),
                author=manifest_item.get("author"),
                license_name=manifest_item.get("license_name"),
                license_url=manifest_item.get("license_url"),
            )
        )
    return images


def sanitize_image_directory(
    source_dir: Path,
    destination_dir: Path,
    prefix: str = "sample",
    move_files: bool = False,
    overwrite: bool = False,
) -> list[SanitizedImageCopy]:
    source_images = collect_images(
        source_dir, limit=None, preserve_names=False, label_prefix=prefix
    )
    destination_dir.mkdir(parents=True, exist_ok=True)
    copies: list[SanitizedImageCopy] = []
    for image in source_images:
        destination_path = destination_dir / image.label
        if destination_path.exists() and not overwrite:
            raise BenchmarkError(f"Destination already exists: {destination_path}")
        if move_files:
            image.source_path.rename(destination_path)
        else:
            shutil.copy2(image.source_path, destination_path)
        copies.append(
            SanitizedImageCopy(
                source_path=image.source_path,
                destination_path=destination_path,
            )
        )
    return copies


def choose_models(
    installed_models: list[InstalledModel],
    requested_models: list[str] | None,
    include_non_vision: bool,
    excluded_models: set[str] | None = None,
    allowed_formats: set[str] | None = None,
) -> list[InstalledModel]:
    models_by_key = {model.model_key: model for model in installed_models}
    if requested_models:
        missing = [
            model_key
            for model_key in requested_models
            if model_key not in models_by_key
        ]
        if missing:
            missing_list = ", ".join(missing)
            raise BenchmarkError(f"Requested models are not installed: {missing_list}")
        selected_models = [models_by_key[model_key] for model_key in requested_models]
    elif include_non_vision:
        selected_models = installed_models
    else:
        selected_models = [model for model in installed_models if model.vision]
    if not excluded_models:
        filtered_models = selected_models
    else:
        filtered_models = [
            model for model in selected_models if model.model_key not in excluded_models
        ]
    if not allowed_formats:
        return filtered_models
    normalized_formats = {
        item.strip().lower() for item in allowed_formats if item.strip()
    }
    return [
        model
        for model in filtered_models
        if model.format.strip().lower() in normalized_formats
    ]


def benchmark_identifier(model_key: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", model_key.lower()).strip("-")
    return f"bench-{normalized[:48]}"


def preferred_memory_value(model_result: ModelBenchmarkResult) -> float | None:
    return model_result.reported_memory_gib or model_result.estimated_total_memory_gib


def merge_request_overrides(
    payload: dict[str, Any],
    extra_body: dict[str, object],
) -> dict[str, Any]:
    merged = copy.deepcopy(payload)
    for key, value in extra_body.items():
        if key in {"model", "messages"}:
            raise BenchmarkError(
                f"Request profile cannot override reserved field `{key}`."
            )
        if (
            isinstance(value, dict)
            and isinstance(merged.get(key), dict)
            and isinstance(merged[key], dict)
        ):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


async def run_image_request(
    base_url: str,
    identifier: str,
    image: BenchmarkImage,
    profile: RequestProfile,
) -> ImageBenchmarkResult:
    mime_type = mimetypes.guess_type(image.source_path.name)[0] or "image/jpeg"
    image_base64 = base64.b64encode(image.source_path.read_bytes()).decode("ascii")
    payload: dict[str, Any] = {
        "model": identifier,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": profile.prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                    },
                ],
            }
        ],
        "temperature": profile.temperature,
        "max_tokens": profile.max_tokens,
    }
    payload = merge_request_overrides(payload, profile.extra_body)

    start = time.perf_counter()
    try:
        response = await request_json(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            data=payload,
            method="POST",
            timeout_seconds=180,
        )
    except Exception as exc:  # noqa: BLE001
        return ImageBenchmarkResult(
            image_label=image.label,
            elapsed_seconds=round(time.perf_counter() - start, 3),
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            response_text="",
            reasoning_present=False,
            reasoning_preview=None,
            finish_reason=None,
            error=str(exc),
        )

    elapsed = round(time.perf_counter() - start, 3)
    choices = response.get("choices", [])
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise BenchmarkError(
            f"Malformed completion response for {image.label}: {response}"
        )
    choice = choices[0]
    message = choice.get("message", {})
    if not isinstance(message, dict):
        raise BenchmarkError(f"Malformed message payload for {image.label}: {response}")
    usage = response.get("usage", {})
    if not isinstance(usage, dict):
        usage = {}
    reasoning_raw = message.get("reasoning_content")
    reasoning_text = reasoning_raw if isinstance(reasoning_raw, str) else ""
    content_raw = message.get("content")
    response_text = clean_response_text(
        content_raw.strip() if isinstance(content_raw, str) else ""
    )
    response_error = None
    if not response_text:
        response_error = "Blank final response."
    return ImageBenchmarkResult(
        image_label=image.label,
        elapsed_seconds=elapsed,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        total_tokens=usage.get("total_tokens"),
        response_text=response_text,
        reasoning_present=bool(reasoning_text.strip()),
        reasoning_preview=(reasoning_text.strip()[:160] or None),
        finish_reason=choice.get("finish_reason"),
        error=response_error,
    )


def clean_response_text(text: str) -> str:
    text = text.replace("<|begin_of_box|>", "").replace("<|end_of_box|>", "")
    return " ".join(text.split())


def build_model_result(
    *,
    model: InstalledModel,
    identifier: str,
    profile: RequestProfile,
    estimated_gpu_memory_gib: float | None,
    estimated_total_memory_gib: float | None,
    load_time_seconds: float | None,
    reported_memory_gib: float | None,
    image_results: list[ImageBenchmarkResult],
    benchmark_error: str | None,
) -> ModelBenchmarkResult:
    successful_results = [result for result in image_results if result.error is None]
    latencies = [result.elapsed_seconds for result in successful_results]
    total_prompt_tokens = sum(
        result.prompt_tokens or 0 for result in successful_results
    )
    total_completion_tokens = sum(
        result.completion_tokens or 0 for result in successful_results
    )
    total_latency = sum(latencies)
    return ModelBenchmarkResult(
        model_key=model.model_key,
        display_name=model.display_name,
        identifier=identifier,
        profile_name=profile.name,
        format=model.format,
        params=model.params,
        variant=model.variant,
        estimated_gpu_memory_gib=estimated_gpu_memory_gib,
        estimated_total_memory_gib=estimated_total_memory_gib,
        load_time_seconds=load_time_seconds,
        reported_memory_gib=reported_memory_gib,
        average_latency_seconds=round(mean(latencies), 3) if latencies else None,
        median_latency_seconds=round(median(latencies), 3) if latencies else None,
        min_latency_seconds=round(min(latencies), 3) if latencies else None,
        max_latency_seconds=round(max(latencies), 3) if latencies else None,
        completion_tokens_per_second=(
            round(total_completion_tokens / total_latency, 3)
            if total_completion_tokens and total_latency
            else None
        ),
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        images_benchmarked=len(image_results),
        successful_images=len(successful_results),
        failed_images=len(image_results) - len(successful_results),
        reasoning_seen=any(result.reasoning_present for result in successful_results),
        benchmark_error=benchmark_error,
        results=image_results,
    )


async def benchmark_model_profiles(
    model: InstalledModel,
    images: list[BenchmarkImage],
    profiles: list[RequestProfile],
    base_url: str,
    unload_after: bool,
) -> list[ModelBenchmarkResult]:
    identifier = benchmark_identifier(model.model_key)
    try:
        estimate = estimate_model(model.model_key)
        load = load_model(model.model_key, identifier)
        await wait_for_loaded_model(base_url=base_url, identifier=identifier)
    except Exception as exc:  # noqa: BLE001
        return [
            build_model_result(
                model=model,
                identifier=identifier,
                profile=profile,
                estimated_gpu_memory_gib=None,
                estimated_total_memory_gib=None,
                load_time_seconds=None,
                reported_memory_gib=None,
                image_results=[],
                benchmark_error=str(exc),
            )
            for profile in profiles
        ]

    results: list[ModelBenchmarkResult] = []

    try:
        for profile in profiles:
            image_results: list[ImageBenchmarkResult] = []
            benchmark_error: str | None = None
            try:
                for image in images:
                    image_results.append(
                        await run_image_request(
                            base_url=base_url,
                            identifier=identifier,
                            image=image,
                            profile=profile,
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                benchmark_error = str(exc)
            results.append(
                build_model_result(
                    model=model,
                    identifier=identifier,
                    profile=profile,
                    estimated_gpu_memory_gib=estimate.estimated_gpu_memory_gib,
                    estimated_total_memory_gib=estimate.estimated_total_memory_gib,
                    load_time_seconds=load.load_time_seconds,
                    reported_memory_gib=load.reported_memory_gib,
                    image_results=image_results,
                    benchmark_error=benchmark_error,
                )
            )
    finally:
        if unload_after:
            unload_all_models()

    return results


def build_summary(
    model_results: list[ModelBenchmarkResult],
    memory_target_gib: float = 32.0,
) -> dict[str, object]:
    stable_models = [
        model_result
        for model_result in model_results
        if model_result.successful_images == model_result.images_benchmarked
        and model_result.average_latency_seconds is not None
    ]
    within_target = [
        model_result
        for model_result in stable_models
        if (preferred_memory_value(model_result) or float("inf")) <= memory_target_gib
    ]
    recommended_model = min(
        within_target,
        key=lambda item: (
            item.average_latency_seconds or float("inf"),
            preferred_memory_value(item) or float("inf"),
        ),
        default=None,
    )
    recommendation_reason = (
        f"Fastest stable result within the {memory_target_gib:g} GiB target."
        if recommended_model is not None
        else None
    )
    if recommended_model is None:
        recommended_model = min(
            stable_models,
            key=lambda item: (
                item.average_latency_seconds or float("inf"),
                preferred_memory_value(item) or float("inf"),
            ),
            default=None,
        )
        if recommended_model is not None:
            recommendation_reason = "Fastest stable result overall."

    smallest_stable_model = min(
        stable_models,
        key=lambda item: (
            preferred_memory_value(item) or float("inf"),
            item.average_latency_seconds or float("inf"),
        ),
        default=None,
    )
    return {
        "memory_target_gib": memory_target_gib,
        "model_count": len(model_results),
        "stable_model_count": len(stable_models),
        "recommended_model": (
            recommended_model.model_key if recommended_model is not None else None
        ),
        "recommended_profile": (
            recommended_model.profile_name if recommended_model is not None else None
        ),
        "recommended_model_avg_latency_seconds": (
            recommended_model.average_latency_seconds
            if recommended_model is not None
            else None
        ),
        "recommended_model_reason": recommendation_reason,
        "smallest_stable_model": (
            smallest_stable_model.model_key
            if smallest_stable_model is not None
            else None
        ),
        "smallest_stable_profile": (
            smallest_stable_model.profile_name
            if smallest_stable_model is not None
            else None
        ),
        "smallest_stable_model_memory_gib": (
            preferred_memory_value(smallest_stable_model)
            if smallest_stable_model is not None
            else None
        ),
    }


async def run_benchmark(
    *,
    images_dir: Path,
    requested_models: list[str] | None = None,
    excluded_models: list[str] | None = None,
    allowed_formats: list[str] | None = None,
    limit_images: int | None = None,
    base_url: str = "http://127.0.0.1:1234",
    keep_loaded: bool = False,
    include_non_vision: bool = False,
    request_profiles: list[RequestProfile],
    memory_target_gib: float = 32.0,
    preserve_image_names: bool = False,
    show_progress: bool = False,
) -> BenchmarkRun:
    images = collect_images(
        images_dir=images_dir,
        limit=limit_images,
        preserve_names=preserve_image_names,
    )
    installed_models = list_installed_models()
    selected_models = choose_models(
        installed_models=installed_models,
        requested_models=requested_models,
        include_non_vision=include_non_vision,
        excluded_models=set(excluded_models or []),
        allowed_formats=set(allowed_formats or []),
    )
    if not selected_models:
        raise BenchmarkError("No benchmarkable models were selected.")

    started_at = datetime.now(UTC)
    machine = collect_machine_info()
    excluded_installed_models = [
        model
        for model in installed_models
        if model.model_key not in {selected.model_key for selected in selected_models}
    ]

    unload_all_models()
    model_results: list[ModelBenchmarkResult] = []
    for index, model in enumerate(selected_models, start=1):
        if show_progress:
            print(
                f"[{index}/{len(selected_models)}] Benchmarking {model.model_key} "
                f"across {len(request_profiles)} profile(s)...",
                flush=True,
            )
        model_results.extend(
            await benchmark_model_profiles(
                model=model,
                images=images,
                profiles=request_profiles,
                base_url=base_url,
                unload_after=not keep_loaded or index != len(selected_models),
            )
        )

    finished_at = datetime.now(UTC)
    return BenchmarkRun(
        started_at=started_at,
        finished_at=finished_at,
        prompt_text=request_profiles[0].prompt_text,
        machine=machine,
        images=images,
        request_profiles=request_profiles,
        summary=build_summary(model_results, memory_target_gib=memory_target_gib),
        model_results=model_results,
        excluded_models=excluded_installed_models,
    )
