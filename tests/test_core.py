from __future__ import annotations

import importlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

core = importlib.import_module("mac_bench.core")
lm_studio = importlib.import_module("mac_bench.lm_studio")


def build_demo_run(image_path: Path | None = None) -> Any:
    image_result = core.ImageBenchmarkResult(
        image_label="sample-01.jpg",
        elapsed_seconds=1.23,
        prompt_tokens=12,
        completion_tokens=20,
        total_tokens=32,
        response_text="A person wearing a blue jacket and carrying a bag.",
        reasoning_present=True,
        reasoning_preview="preview",
        finish_reason="stop",
        error=None,
    )
    model_result = core.ModelBenchmarkResult(
        model_key="demo/model",
        display_name="Demo Model",
        identifier="demo-model",
        profile_name="default",
        format="mlx",
        params="4B",
        variant="demo/model@4bit",
        estimated_gpu_memory_gib=3.2,
        estimated_total_memory_gib=3.2,
        load_time_seconds=4.0,
        reported_memory_gib=3.8,
        average_latency_seconds=1.23,
        median_latency_seconds=1.23,
        min_latency_seconds=1.23,
        max_latency_seconds=1.23,
        completion_tokens_per_second=16.26,
        total_prompt_tokens=12,
        total_completion_tokens=20,
        images_benchmarked=1,
        successful_images=1,
        failed_images=0,
        reasoning_seen=True,
        benchmark_error=None,
        results=[image_result],
    )
    profile = core.RequestProfile(
        name="default",
        prompt_text=core.DEFAULT_PERSON_PROMPT,
        temperature=0.0,
        max_tokens=160,
        extra_body={},
    )
    return core.BenchmarkRun(
        started_at=datetime(2026, 3, 23, 12, 0, tzinfo=UTC),
        finished_at=datetime(2026, 3, 23, 12, 10, tzinfo=UTC),
        prompt_text=core.DEFAULT_PERSON_PROMPT,
        machine={
            "model_name": "Mac mini",
            "chip": "Apple M4 Pro",
            "total_memory_gb": 64,
        },
        images=[
            core.BenchmarkImage(
                source_path=image_path or Path("images/private.jpg"),
                label="sample-01.jpg",
                title="Demo doorstep frame",
            )
        ],
        request_profiles=[profile],
        summary={
            "recommended_model": "demo/model",
            "recommended_profile": "default",
            "recommended_model_avg_latency_seconds": 1.23,
            "recommended_model_reason": "Fastest stable result within the 32 GiB target.",
            "smallest_stable_model": "demo/model",
            "smallest_stable_profile": "default",
            "smallest_stable_model_memory_gib": 3.8,
        },
        model_results=[model_result],
        excluded_models=[],
    )


def test_prompt_mentions_people_not_environment() -> None:
    prompt = core.DEFAULT_PERSON_PROMPT.lower()
    assert "person or people" in prompt
    assert "do not mention the environment" in prompt
    assert "objects they are wearing or carrying" in prompt


def test_build_summary_prefers_fastest_model_under_target() -> None:
    image_result = core.ImageBenchmarkResult(
        image_label="sample-01.jpg",
        elapsed_seconds=1.0,
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
        response_text="A person in a jacket.",
        reasoning_present=False,
        reasoning_preview=None,
        finish_reason="stop",
        error=None,
    )
    fast = core.ModelBenchmarkResult(
        model_key="fast/model",
        display_name="Fast",
        identifier="fast",
        profile_name="default",
        format="mlx",
        params="4B",
        variant="fast/model@4bit",
        estimated_gpu_memory_gib=4.0,
        estimated_total_memory_gib=4.0,
        load_time_seconds=2.0,
        reported_memory_gib=4.5,
        average_latency_seconds=0.9,
        median_latency_seconds=0.9,
        min_latency_seconds=0.9,
        max_latency_seconds=0.9,
        completion_tokens_per_second=1.0,
        total_prompt_tokens=1,
        total_completion_tokens=1,
        images_benchmarked=1,
        successful_images=1,
        failed_images=0,
        reasoning_seen=False,
        benchmark_error=None,
        results=[image_result],
    )
    slow = core.ModelBenchmarkResult(
        model_key="slow/model",
        display_name="Slow",
        identifier="slow",
        profile_name="default",
        format="gguf",
        params="7B",
        variant="slow/model@q4_k_m",
        estimated_gpu_memory_gib=6.0,
        estimated_total_memory_gib=6.0,
        load_time_seconds=3.0,
        reported_memory_gib=7.0,
        average_latency_seconds=1.4,
        median_latency_seconds=1.4,
        min_latency_seconds=1.4,
        max_latency_seconds=1.4,
        completion_tokens_per_second=1.0,
        total_prompt_tokens=1,
        total_completion_tokens=1,
        images_benchmarked=1,
        successful_images=1,
        failed_images=0,
        reasoning_seen=True,
        benchmark_error=None,
        results=[image_result],
    )

    summary = core.build_summary([slow, fast])

    assert summary["recommended_model"] == "fast/model"
    assert summary["recommended_profile"] == "default"
    assert summary["model_count"] == 2


def test_markdown_report_includes_summary_and_image_rows() -> None:
    run = build_demo_run()

    report = core.build_markdown_report(run)

    assert "Recommended result" in report
    assert "Speed vs Memory" in report
    assert "`sample-01.jpg`" in report
    assert "Demo Model / default" in report


def test_html_report_includes_dashboard_content() -> None:
    run = build_demo_run()

    report = core.build_html_report(core.build_json_payload(run))

    assert "Vision Benchmark Report" in report
    assert "Latency vs memory footprint" in report
    assert "demo/model" in report
    assert "benchmark-data" in report


def test_write_reports_writes_html_index_and_latest(tmp_path: Path) -> None:
    source_image = tmp_path / "source.jpg"
    source_image.write_bytes(b"demo-image")
    run = build_demo_run(source_image)

    artifacts = core.write_reports(tmp_path, "demo-report", run)

    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()
    assert artifacts.html_path.exists()
    assert artifacts.latest_html_path.exists()
    assert artifacts.index_html_path.exists()
    assert (tmp_path / "images" / "sample-01.jpg").exists()
    assert (tmp_path / ".nojekyll").exists()


def test_choose_models_respects_exclusions() -> None:
    selected = core.choose_models(
        installed_models=[
            core.InstalledModel(
                model_key="keep/model",
                display_name="Keep",
                format="gguf",
                architecture=None,
                publisher=None,
                vision=True,
                trained_for_tool_use=False,
                params=None,
                size_bytes=None,
                variant=None,
                max_context_length=None,
            ),
            core.InstalledModel(
                model_key="skip/model",
                display_name="Skip",
                format="gguf",
                architecture=None,
                publisher=None,
                vision=True,
                trained_for_tool_use=False,
                params=None,
                size_bytes=None,
                variant=None,
                max_context_length=None,
            ),
        ],
        requested_models=None,
        include_non_vision=False,
        excluded_models={"skip/model"},
    )

    assert [model.model_key for model in selected] == ["keep/model"]


def test_choose_models_respects_format_filter() -> None:
    selected = core.choose_models(
        installed_models=[
            core.InstalledModel(
                model_key="keep/model",
                display_name="Keep",
                format="gguf",
                architecture=None,
                publisher=None,
                vision=True,
                trained_for_tool_use=False,
                params=None,
                size_bytes=None,
                variant=None,
                max_context_length=None,
            ),
            core.InstalledModel(
                model_key="skip/model",
                display_name="Skip",
                format="safetensors",
                architecture=None,
                publisher=None,
                vision=True,
                trained_for_tool_use=False,
                params=None,
                size_bytes=None,
                variant=None,
                max_context_length=None,
            ),
        ],
        requested_models=None,
        include_non_vision=False,
        excluded_models=None,
        allowed_formats={"gguf"},
    )

    assert [model.model_key for model in selected] == ["keep/model"]


def test_should_retry_transient_image_error_matches_lm_studio_image_failure() -> None:
    result = core.ImageBenchmarkResult(
        image_label="sample-01.jpg",
        elapsed_seconds=1.0,
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        response_text="",
        reasoning_present=False,
        reasoning_preview=None,
        finish_reason=None,
        error='HTTP 400 from http://127.0.0.1:1234/v1/chat/completions: {"error":"failed to process image"}',
    )

    assert core.should_retry_transient_image_error(result) is True


def test_should_retry_transient_image_error_ignores_non_transient_error() -> None:
    result = core.ImageBenchmarkResult(
        image_label="sample-01.jpg",
        elapsed_seconds=1.0,
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        response_text="",
        reasoning_present=False,
        reasoning_preview=None,
        finish_reason=None,
        error="Blank final response.",
    )

    assert core.should_retry_transient_image_error(result) is False


def test_should_retry_with_higher_token_budget_only_for_reasoning_length_blank() -> (
    None
):
    retryable = core.ImageBenchmarkResult(
        image_label="sample-01.jpg",
        elapsed_seconds=1.0,
        prompt_tokens=999,
        completion_tokens=160,
        total_tokens=1159,
        response_text="",
        reasoning_present=True,
        reasoning_preview="analysis",
        finish_reason="length",
        error="Blank final response.",
    )
    non_retryable = core.ImageBenchmarkResult(
        image_label="sample-01.jpg",
        elapsed_seconds=1.0,
        prompt_tokens=999,
        completion_tokens=160,
        total_tokens=1159,
        response_text="",
        reasoning_present=False,
        reasoning_preview=None,
        finish_reason="length",
        error="Blank final response.",
    )

    assert core.should_retry_with_higher_token_budget(retryable) is True
    assert core.should_retry_with_higher_token_budget(non_retryable) is False


def test_load_model_passes_context_length(monkeypatch: Any) -> None:
    commands: list[list[str]] = []

    def fake_run_command(command: list[str]) -> str:
        commands.append(command)
        return "Model loaded successfully in 1.23s.\n(4.56 GiB)"

    monkeypatch.setattr(lm_studio, "run_command", fake_run_command)
    monkeypatch.setattr(lm_studio, "lms_binary", lambda: Path("/usr/bin/lms"))

    load_result = core.load_model(
        "demo/model",
        "demo-identifier",
        context_length=8192,
    )

    assert commands == [
        [
            "/usr/bin/lms",
            "load",
            "demo/model",
            "-y",
            "--identifier",
            "demo-identifier",
            "--context-length",
            "8192",
        ]
    ]
    assert load_result.load_time_seconds == 1.23
    assert load_result.reported_memory_gib == 4.56
