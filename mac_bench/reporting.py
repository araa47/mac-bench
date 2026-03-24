from __future__ import annotations

import html
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from string import Template
from typing import cast

from .benchmark import preferred_memory_value
from .entities import (
    BenchmarkError,
    BenchmarkImage,
    BenchmarkRun,
    ImageBenchmarkResult,
    InstalledModel,
    ModelBenchmarkResult,
    RequestProfile,
)


@dataclass(slots=True)
class ReportArtifacts:
    json_path: Path
    markdown_path: Path
    html_path: Path
    latest_json_path: Path
    latest_markdown_path: Path
    latest_html_path: Path
    index_html_path: Path


def result_label(result: ModelBenchmarkResult) -> str:
    return f"{result.model_key} [{result.profile_name}]"


def format_optional(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.3f}"


def escape_table_cell(text: str) -> str:
    return text.replace("|", "\\|")


def image_display_title(image: BenchmarkImage) -> str:
    if image.title:
        return image.title
    return image.label


def build_image_payload(
    image: BenchmarkImage,
    report_path: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {"label": image.label}
    if image.title:
        payload["title"] = image.title
    if report_path:
        payload["report_path"] = report_path
    if image.page_url:
        payload["page_url"] = image.page_url
    if image.source_url:
        payload["source_url"] = image.source_url
    if image.author:
        payload["author"] = image.author
    if image.license_name:
        payload["license_name"] = image.license_name
    if image.license_url:
        payload["license_url"] = image.license_url
    return payload


def normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    min_value = min(values)
    max_value = max(values)
    if min_value == max_value:
        return [0.5 for _ in values]
    return [(value - min_value) / (max_value - min_value) for value in values]


def success_ratio(result: ModelBenchmarkResult) -> float:
    if result.images_benchmarked == 0:
        return 0.0
    return result.successful_images / result.images_benchmarked


def is_stable_result(result: ModelBenchmarkResult) -> bool:
    return (
        result.images_benchmarked > 0
        and result.successful_images == result.images_benchmarked
        and result.average_latency_seconds is not None
    )


def ordered_results(
    model_results: list[ModelBenchmarkResult],
) -> list[ModelBenchmarkResult]:
    return sorted(
        model_results,
        key=lambda result: (
            0 if is_stable_result(result) else 1,
            result.average_latency_seconds or float("inf"),
            preferred_memory_value(result) or float("inf"),
            -success_ratio(result),
            result.model_key,
            result.profile_name,
        ),
    )


def build_speed_vs_memory_chart(model_results: list[ModelBenchmarkResult]) -> str:
    plottable = [
        result
        for result in ordered_results(model_results)
        if result.average_latency_seconds is not None
        and preferred_memory_value(result) is not None
    ]
    if not plottable:
        return "_No chart data available._"
    latencies = [result.average_latency_seconds or 0.0 for result in plottable]
    memories = [preferred_memory_value(result) or 0.0 for result in plottable]
    speed_scores = [1 - value for value in normalize(latencies)]
    memory_scores = normalize(memories)
    lines = ["```mermaid", "quadrantChart", "    title Speed vs memory footprint"]
    lines.append("    x-axis Slow --> Fast")
    lines.append("    y-axis Low RAM --> High RAM")
    lines.append("    quadrant-1 Fast but heavy")
    lines.append("    quadrant-2 Best zone")
    lines.append("    quadrant-3 Light but slower")
    lines.append("    quadrant-4 Heavy and slower")
    for result, speed_score, memory_score in zip(
        plottable, speed_scores, memory_scores, strict=True
    ):
        lines.append(
            f'    "{result_label(result)}": [{speed_score:.3f}, {memory_score:.3f}]'
        )
    lines.append("```")
    return "\n".join(lines)


def build_latency_chart(model_results: list[ModelBenchmarkResult]) -> str:
    plottable = [
        result
        for result in ordered_results(model_results)
        if result.average_latency_seconds is not None
    ]
    if not plottable:
        return "_No chart data available._"
    labels = ", ".join(f'"{result_label(result)}"' for result in plottable)
    values = ", ".join(
        f"{(result.average_latency_seconds or 0.0):.3f}" for result in plottable
    )
    max_latency = max(result.average_latency_seconds or 0.0 for result in plottable)
    upper_bound = max(1.0, round(max_latency + 1.0, 2))
    return "\n".join(
        [
            "```mermaid",
            "xychart-beta",
            '    title "Average image latency by result"',
            f"    x-axis [{labels}]",
            f'    y-axis "Seconds" 0 --> {upper_bound}',
            f"    bar [{values}]",
            "```",
        ]
    )


def build_markdown_report(run: BenchmarkRun) -> str:
    lines: list[str] = []
    sorted_results = ordered_results(run.model_results)
    lines.append("# mac-bench Vision Benchmark")
    lines.append("")
    lines.append(f"- Ran at: `{run.started_at:%Y-%m-%d %H:%M:%S %Z}`")
    lines.append(f"- Finished at: `{run.finished_at:%Y-%m-%d %H:%M:%S %Z}`")
    lines.append(f"- Duration: `{run.finished_at - run.started_at}`")
    if (
        run.machine.get("model_name")
        or run.machine.get("chip")
        or run.machine.get("total_memory_gb")
    ):
        lines.append(
            "- Machine: "
            f"`{run.machine.get('model_name', 'Unknown')}` / "
            f"`{run.machine.get('chip', 'Unknown chip')}` / "
            f"`{run.machine.get('total_memory_gb', '?')} GB RAM`"
        )
    lines.append("")
    lines.append("## What This Run Tested")
    lines.append("")
    if len(run.request_profiles) == 1:
        profile = run.request_profiles[0]
        lines.append(f"- Request profile: `{profile.name}`")
        lines.append(f"- Temperature: `{profile.temperature}`")
        lines.append(f"- Max tokens: `{profile.max_tokens}`")
    else:
        lines.append(f"- Request profiles: `{len(run.request_profiles)}`")
        for profile in run.request_profiles:
            lines.append(
                f"  - `{profile.name}` with `temperature={profile.temperature}` and `max_tokens={profile.max_tokens}`"
            )
    lines.append(f"- Images: `{len(run.images)}`")
    lines.append("")
    lines.append("## Prompt")
    lines.append("")
    lines.append("```text")
    lines.append(run.prompt_text)
    lines.append("```")
    lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    recommended_model = run.summary.get("recommended_model")
    recommended_profile = run.summary.get("recommended_profile")
    if isinstance(recommended_model, str):
        latency = run.summary.get("recommended_model_avg_latency_seconds")
        reason = run.summary.get("recommended_model_reason")
        profile_suffix = (
            f" / `{recommended_profile}`"
            if isinstance(recommended_profile, str)
            else ""
        )
        lines.append(
            f"- Recommended result: `{recommended_model}`{profile_suffix} "
            f"at `{latency:.3f}s` average latency."
        )
        if isinstance(reason, str):
            lines.append(f"- Why: {reason}")
    else:
        lines.append("- No stable result completed the full image set.")
    smallest_model = run.summary.get("smallest_stable_model")
    smallest_profile = run.summary.get("smallest_stable_profile")
    smallest_memory = run.summary.get("smallest_stable_model_memory_gib")
    if isinstance(smallest_model, str) and isinstance(smallest_memory, float):
        profile_suffix = (
            f" / `{smallest_profile}`" if isinstance(smallest_profile, str) else ""
        )
        lines.append(
            f"- Lightest stable result: `{smallest_model}`{profile_suffix} "
            f"at `{smallest_memory:.2f} GiB`."
        )
    lines.append("")
    lines.append("## Charts")
    lines.append("")
    lines.append("### Speed vs Memory")
    lines.append("")
    lines.append(build_speed_vs_memory_chart(sorted_results))
    lines.append("")
    lines.append("### Average Latency")
    lines.append("")
    lines.append(build_latency_chart(sorted_results))
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        "| Model | Profile | Format | Load RAM GiB | Avg s | Median s | Tok/s | Success | Reasoning |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---|")
    for result in sorted_results:
        lines.append(
            "| "
            f"`{result.model_key}` | "
            f"`{result.profile_name}` | "
            f"`{result.format}` | "
            f"{format_optional(preferred_memory_value(result))} | "
            f"{format_optional(result.average_latency_seconds)} | "
            f"{format_optional(result.median_latency_seconds)} | "
            f"{format_optional(result.completion_tokens_per_second)} | "
            f"{result.successful_images}/{result.images_benchmarked} | "
            f"{'yes' if result.reasoning_seen else 'no'} |"
        )
    lines.append("")
    if run.excluded_models:
        lines.append("## Excluded Installed Models")
        lines.append("")
        for model in run.excluded_models:
            reason = "not vision-capable" if not model.vision else "not selected"
            lines.append(f"- `{model.model_key}`: {reason}")
        lines.append("")
    lines.append("## Images")
    lines.append("")
    for image in run.images:
        line = f"- `{image.label}`"
        if image.title:
            line += f": {image.title}"
        if image.license_name:
            line += f" ({image.license_name})"
        lines.append(line)
    lines.append("")
    for result in sorted_results:
        lines.append(f"## {result.display_name} / {result.profile_name}")
        lines.append("")
        lines.append(f"- Model key: `{result.model_key}`")
        lines.append(f"- Identifier used for API: `{result.identifier}`")
        lines.append(f"- Format: `{result.format}`")
        if result.variant:
            lines.append(f"- Variant: `{result.variant}`")
        if result.params:
            lines.append(f"- Params: `{result.params}`")
        if result.estimated_total_memory_gib is not None:
            lines.append(
                f"- Estimated total memory: `{result.estimated_total_memory_gib:.2f} GiB`"
            )
        if result.reported_memory_gib is not None:
            lines.append(
                f"- Reported load memory: `{result.reported_memory_gib:.2f} GiB`"
            )
        if result.load_time_seconds is not None:
            lines.append(f"- Load time: `{result.load_time_seconds:.2f}s`")
        if result.average_latency_seconds is not None:
            lines.append(
                f"- Average image latency: `{result.average_latency_seconds:.3f}s`"
            )
        if result.median_latency_seconds is not None:
            lines.append(
                f"- Median image latency: `{result.median_latency_seconds:.3f}s`"
            )
        if result.completion_tokens_per_second is not None:
            lines.append(
                f"- Completion throughput: `{result.completion_tokens_per_second:.3f} tokens/s`"
            )
        lines.append(
            f"- Success rate: `{result.successful_images}/{result.images_benchmarked}`"
        )
        if result.benchmark_error:
            lines.append(f"- Benchmark error: `{result.benchmark_error}`")
        lines.append("")
        lines.append(
            "| Image | Time s | Prompt Tokens | Completion Tokens | Reasoning | Response |"
        )
        lines.append("|---|---:|---:|---:|---|---|")
        for image_result in result.results:
            response = image_result.response_text or "-"
            response = response.replace("\n", "<br>")
            error_text = (
                image_result.error.replace("\n", "<br>") if image_result.error else ""
            )
            if error_text:
                response = f"ERROR: {error_text}"
            lines.append(
                "| "
                f"`{image_result.image_label}` | "
                f"{image_result.elapsed_seconds:.3f} | "
                f"{image_result.prompt_tokens or '-'} | "
                f"{image_result.completion_tokens or '-'} | "
                f"{'yes' if image_result.reasoning_present else 'no'} | "
                f"{escape_table_cell(response)} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_json_payload(
    run: BenchmarkRun,
    report_paths: dict[str, str] | None = None,
) -> dict[str, object]:
    image_payload = [
        build_image_payload(
            image, report_paths.get(image.label) if report_paths else image.report_path
        )
        for image in run.images
    ]
    return {
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat(),
        "prompt": run.prompt_text,
        "machine": run.machine,
        "images": image_payload,
        "request_profiles": [asdict(profile) for profile in run.request_profiles],
        "summary": run.summary,
        "models": [asdict(result) for result in run.model_results],
        "excluded_models": [asdict(model) for model in run.excluded_models],
    }


def build_html_report(
    payload: dict[str, object],
    report_title: str = "mac-bench Vision Benchmark",
) -> str:
    machine_raw = payload.get("machine")
    summary_raw = payload.get("summary")
    machine_label = "Unknown machine"
    if isinstance(machine_raw, dict):
        machine = cast(dict[str, object], machine_raw)
        parts = [
            str(machine.get("model_name") or "").strip(),
            str(machine.get("chip") or "").strip(),
            (
                f"{machine.get('total_memory_gb')} GB RAM"
                if machine.get("total_memory_gb") is not None
                else ""
            ),
        ]
        machine_label = " / ".join(part for part in parts if part) or machine_label
    stable_count = ""
    if isinstance(summary_raw, dict):
        summary = cast(dict[str, object], summary_raw)
        if summary.get("stable_model_count") is not None:
            stable_count = f"{summary['stable_model_count']} stable results"

    payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    template = Template("""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>$title</title>
  <meta name="description" content="Static benchmark dashboard for mac-bench vision runs.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #f4efe5;
      --bg-strong: #e7dcc9;
      --panel: rgba(255, 252, 246, 0.82);
      --panel-strong: rgba(255, 248, 238, 0.95);
      --line: rgba(52, 41, 31, 0.14);
      --ink: #1f1a17;
      --muted: #6e6258;
      --accent: #b84f32;
      --accent-soft: rgba(184, 79, 50, 0.14);
      --teal: #236d6a;
      --gold: #a0771b;
      --danger: #a63d40;
      --shadow: 0 24px 80px rgba(54, 36, 20, 0.14);
      --radius: 28px;
      --mono: "IBM Plex Mono", monospace;
      --body: "IBM Plex Sans", sans-serif;
      --display: "Fraunces", serif;
      --hero-bg: linear-gradient(135deg, rgba(255, 250, 241, 0.98), rgba(248, 238, 223, 0.9));
      --hero-glow: rgba(184, 79, 50, 0.28);
      --card-bg: linear-gradient(180deg, rgba(255, 250, 244, 0.9), rgba(252, 245, 236, 0.76));
      --card-border: rgba(52, 41, 31, 0.08);
      --row-bg: rgba(255, 252, 246, 0.76);
      --row-hover: rgba(184, 79, 50, 0.04);
      --prompt-bg: rgba(255, 252, 246, 0.72);
      --chip-bg: rgba(184, 79, 50, 0.08);
      --chip-border: rgba(184, 79, 50, 0.12);
      --pill-bg: rgba(255, 252, 246, 0.9);
      --pill-border: rgba(52, 41, 31, 0.1);
      --track-bg: rgba(31, 26, 17, 0.08);
      --track-border: rgba(52, 41, 31, 0.06);
      --table-bg: rgba(255, 252, 246, 0.8);
      --table-border: rgba(52, 41, 31, 0.09);
      --th-bg: rgba(244, 239, 229, 0.82);
      --empty-bg: rgba(255, 252, 246, 0.54);
      --empty-border: rgba(52, 41, 31, 0.18);
      --fact-bg: rgba(244, 239, 229, 0.72);
      --fact-border: rgba(52, 41, 31, 0.07);
      --details-bg: rgba(255, 252, 246, 0.82);
      --details-border: rgba(52, 41, 31, 0.08);
      --mini-bg: rgba(255, 252, 246, 0.78);
      --mini-border: rgba(52, 41, 31, 0.08);
      --rank-bg: linear-gradient(135deg, rgba(184, 79, 50, 0.16), rgba(35, 109, 106, 0.18));
      --grid-opacity: 0.08;
      --body-bg: linear-gradient(180deg, #f8f3ea 0%, var(--bg) 42%, #efe5d7 100%);
      --body-glow-a: rgba(184, 79, 50, 0.18);
      --body-glow-b: rgba(35, 109, 106, 0.18);
      --chart-rect: rgba(255,252,246,0.42);
      --chart-grid: rgba(52,41,31,0.12);
      --chart-axis: rgba(31,26,23,0.7);
      --chart-bar-bg: rgba(31,26,23,0.08);
      --chart-bar-fg: rgba(184,79,50,0.82);
      --stable-badge-color: #104341;
      --stable-badge-bg: rgba(35, 109, 106, 0.12);
      --stable-badge-border: rgba(35, 109, 106, 0.18);
      --partial-badge-color: #6f5208;
      --partial-badge-bg: rgba(160, 119, 27, 0.12);
      --partial-badge-border: rgba(160, 119, 27, 0.2);
      --failed-badge-color: #7d2226;
      --failed-badge-bg: rgba(166, 61, 64, 0.12);
      --failed-badge-border: rgba(166, 61, 64, 0.2);
      --dot-stroke: rgba(31,26,23,0.55);
      --chart-label: #1f1a17;
    }

    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) {
        --bg: #161413;
        --bg-strong: #221f1d;
        --panel: rgba(28, 26, 24, 0.92);
        --panel-strong: rgba(34, 32, 28, 0.95);
        --line: rgba(255, 255, 255, 0.1);
        --ink: #e4dfda;
        --muted: #968e86;
        --accent: #e0734f;
        --accent-soft: rgba(224, 115, 79, 0.14);
        --teal: #52c4be;
        --gold: #d4a83a;
        --danger: #e06868;
        --shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
        --hero-bg: linear-gradient(135deg, rgba(28, 26, 22, 0.98), rgba(32, 28, 24, 0.9));
        --hero-glow: rgba(224, 115, 79, 0.15);
        --card-bg: linear-gradient(180deg, rgba(36, 33, 30, 0.9), rgba(30, 28, 25, 0.76));
        --card-border: rgba(255, 255, 255, 0.07);
        --row-bg: rgba(36, 33, 30, 0.76);
        --row-hover: rgba(224, 115, 79, 0.06);
        --prompt-bg: rgba(28, 26, 22, 0.72);
        --chip-bg: rgba(224, 115, 79, 0.1);
        --chip-border: rgba(224, 115, 79, 0.16);
        --pill-bg: rgba(36, 33, 30, 0.9);
        --pill-border: rgba(255, 255, 255, 0.08);
        --track-bg: rgba(255, 255, 255, 0.07);
        --track-border: rgba(255, 255, 255, 0.04);
        --table-bg: rgba(28, 26, 22, 0.8);
        --table-border: rgba(255, 255, 255, 0.08);
        --th-bg: rgba(22, 20, 18, 0.82);
        --empty-bg: rgba(28, 26, 22, 0.54);
        --empty-border: rgba(255, 255, 255, 0.14);
        --fact-bg: rgba(22, 20, 18, 0.72);
        --fact-border: rgba(255, 255, 255, 0.06);
        --details-bg: rgba(28, 26, 22, 0.82);
        --details-border: rgba(255, 255, 255, 0.08);
        --mini-bg: rgba(36, 33, 30, 0.78);
        --mini-border: rgba(255, 255, 255, 0.08);
        --rank-bg: linear-gradient(135deg, rgba(224, 115, 79, 0.2), rgba(82, 196, 190, 0.2));
        --grid-opacity: 0.03;
        --body-bg: linear-gradient(180deg, #121110 0%, var(--bg) 42%, #1a1816 100%);
        --body-glow-a: rgba(224, 115, 79, 0.1);
        --body-glow-b: rgba(82, 196, 190, 0.1);
        --chart-rect: rgba(28,26,22,0.42);
        --chart-grid: rgba(255,255,255,0.1);
        --chart-axis: rgba(255,255,255,0.5);
        --chart-bar-bg: rgba(255,255,255,0.07);
        --chart-bar-fg: rgba(224,115,79,0.85);
        --stable-badge-color: #6ee0da;
        --stable-badge-bg: rgba(82, 196, 190, 0.12);
        --stable-badge-border: rgba(82, 196, 190, 0.22);
        --partial-badge-color: #e8c460;
        --partial-badge-bg: rgba(212, 168, 58, 0.12);
        --partial-badge-border: rgba(212, 168, 58, 0.22);
        --failed-badge-color: #f09090;
        --failed-badge-bg: rgba(224, 104, 104, 0.12);
        --failed-badge-border: rgba(224, 104, 104, 0.22);
        --dot-stroke: rgba(255,255,255,0.4);
        --chart-label: var(--ink);
      }
    }

    [data-theme="dark"] {
      --bg: #161413;
      --bg-strong: #221f1d;
      --panel: rgba(28, 26, 24, 0.92);
      --panel-strong: rgba(34, 32, 28, 0.95);
      --line: rgba(255, 255, 255, 0.1);
      --ink: #e4dfda;
      --muted: #968e86;
      --accent: #e0734f;
      --accent-soft: rgba(224, 115, 79, 0.14);
      --teal: #52c4be;
      --gold: #d4a83a;
      --danger: #e06868;
      --shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
      --hero-bg: linear-gradient(135deg, rgba(28, 26, 22, 0.98), rgba(32, 28, 24, 0.9));
      --hero-glow: rgba(224, 115, 79, 0.15);
      --card-bg: linear-gradient(180deg, rgba(36, 33, 30, 0.9), rgba(30, 28, 25, 0.76));
      --card-border: rgba(255, 255, 255, 0.07);
      --row-bg: rgba(36, 33, 30, 0.76);
      --row-hover: rgba(224, 115, 79, 0.06);
      --prompt-bg: rgba(28, 26, 22, 0.72);
      --chip-bg: rgba(224, 115, 79, 0.1);
      --chip-border: rgba(224, 115, 79, 0.16);
      --pill-bg: rgba(36, 33, 30, 0.9);
      --pill-border: rgba(255, 255, 255, 0.08);
      --track-bg: rgba(255, 255, 255, 0.07);
      --track-border: rgba(255, 255, 255, 0.04);
      --table-bg: rgba(28, 26, 22, 0.8);
      --table-border: rgba(255, 255, 255, 0.08);
      --th-bg: rgba(22, 20, 18, 0.82);
      --empty-bg: rgba(28, 26, 22, 0.54);
      --empty-border: rgba(255, 255, 255, 0.14);
      --fact-bg: rgba(22, 20, 18, 0.72);
      --fact-border: rgba(255, 255, 255, 0.06);
      --details-bg: rgba(28, 26, 22, 0.82);
      --details-border: rgba(255, 255, 255, 0.08);
      --mini-bg: rgba(36, 33, 30, 0.78);
      --mini-border: rgba(255, 255, 255, 0.08);
      --rank-bg: linear-gradient(135deg, rgba(224, 115, 79, 0.2), rgba(82, 196, 190, 0.2));
      --grid-opacity: 0.03;
      --body-bg: linear-gradient(180deg, #121110 0%, var(--bg) 42%, #1a1816 100%);
      --body-glow-a: rgba(224, 115, 79, 0.1);
      --body-glow-b: rgba(82, 196, 190, 0.1);
      --chart-rect: rgba(28,26,22,0.42);
      --chart-grid: rgba(255,255,255,0.1);
      --chart-axis: rgba(255,255,255,0.5);
      --chart-bar-bg: rgba(255,255,255,0.07);
      --chart-bar-fg: rgba(224,115,79,0.85);
      --stable-badge-color: #6ee0da;
      --stable-badge-bg: rgba(82, 196, 190, 0.12);
      --stable-badge-border: rgba(82, 196, 190, 0.22);
      --partial-badge-color: #e8c460;
      --partial-badge-bg: rgba(212, 168, 58, 0.12);
      --partial-badge-border: rgba(212, 168, 58, 0.22);
      --failed-badge-color: #f09090;
      --failed-badge-bg: rgba(224, 104, 104, 0.12);
      --failed-badge-border: rgba(224, 104, 104, 0.22);
      --dot-stroke: rgba(255,255,255,0.4);
      --chart-label: var(--ink);
    }

    * {
      box-sizing: border-box;
    }

    html {
      scroll-behavior: smooth;
    }

    body {
      margin: 0;
      color: var(--ink);
      font-family: var(--body);
      background:
        radial-gradient(circle at top left, var(--body-glow-a), transparent 32%),
        radial-gradient(circle at top right, var(--body-glow-b), transparent 28%),
        var(--body-bg);
      min-height: 100vh;
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: var(--grid-opacity);
      background-image:
        linear-gradient(rgba(31, 26, 23, 0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(31, 26, 23, 0.05) 1px, transparent 1px);
      background-size: 36px 36px;
      mask-image: radial-gradient(circle at center, black 55%, transparent 88%);
    }

    a {
      color: inherit;
    }

    .page {
      width: min(1240px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0 64px;
      position: relative;
      z-index: 1;
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }

    .hero {
      padding: 28px;
      position: relative;
      overflow: hidden;
      background: var(--hero-bg), var(--panel);
    }

    .hero::after {
      content: "";
      position: absolute;
      width: 320px;
      height: 320px;
      right: -96px;
      top: -140px;
      border-radius: 50%;
      background: radial-gradient(circle at center, var(--hero-glow), transparent 70%);
      pointer-events: none;
    }

    .theme-toggle {
      position: absolute;
      top: 20px;
      right: 20px;
      z-index: 2;
      background: var(--pill-bg);
      border: 1px solid var(--pill-border);
      border-radius: 999px;
      padding: 8px 14px;
      cursor: pointer;
      font: 500 0.78rem/1 var(--mono);
      color: var(--muted);
      transition: background 0.2s, color 0.2s;
    }

    .theme-toggle:hover {
      color: var(--ink);
      background: var(--card-bg);
    }

    .eyebrow {
      font: 600 0.72rem/1.2 var(--mono);
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 14px;
    }

    h1,
    h2,
    h3 {
      margin: 0;
      font-family: var(--display);
      font-weight: 700;
      letter-spacing: -0.03em;
    }

    h1 {
      font-size: clamp(2.3rem, 5vw, 4.8rem);
      line-height: 0.94;
      max-width: 9ch;
    }

    .hero-copy {
      max-width: 70ch;
      margin-top: 16px;
      font-size: 1.02rem;
      line-height: 1.72;
      color: var(--muted);
    }

    .hero-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 20px;
    }

    .meta-pill,
    .stat-note,
    .badge,
    .mini-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      font-size: 0.82rem;
      line-height: 1;
    }

    .meta-pill {
      padding: 10px 14px;
      background: var(--pill-bg);
      border: 1px solid var(--pill-border);
    }

    .layout {
      display: grid;
      gap: 18px;
      margin-top: 18px;
    }

    .split {
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 18px;
      align-items: stretch;
    }

    .panel-body {
      padding: 24px;
    }

    .section-kicker {
      font: 600 0.74rem/1.2 var(--mono);
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 10px;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 16px;
    }

    .summary-card {
      padding: 18px;
      border-radius: 22px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
    }

    .summary-label {
      font: 500 0.74rem/1.2 var(--mono);
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--muted);
    }

    .summary-value {
      margin-top: 10px;
      font-family: var(--display);
      font-size: clamp(1.3rem, 2.2vw, 2.1rem);
      line-height: 1;
    }

    .summary-subtext {
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.5;
    }

    .prompt-box {
      background: var(--prompt-bg);
      border: 1px solid var(--pill-border);
      border-radius: 22px;
      padding: 18px;
      white-space: pre-wrap;
      font-size: 0.95rem;
      line-height: 1.72;
      color: var(--ink);
    }

    .profiles {
      margin-top: 14px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .profile-chip {
      min-width: 180px;
      padding: 14px 16px;
      border-radius: 18px;
      background: var(--chip-bg);
      border: 1px solid var(--chip-border);
    }

    .profile-chip strong {
      display: block;
      margin-bottom: 6px;
    }

    .sample-gallery {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin-top: 18px;
    }

    .sample-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 22px;
      padding: 12px;
    }

    .sample-thumb {
      width: 100%;
      aspect-ratio: 4 / 3;
      border: 0;
      border-radius: 16px;
      overflow: hidden;
      padding: 0;
      cursor: zoom-in;
      background: rgba(31, 26, 17, 0.08);
    }

    .sample-thumb img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }

    .sample-title {
      margin-top: 10px;
      font-weight: 600;
      line-height: 1.4;
    }

    .sample-meta {
      margin-top: 6px;
      color: var(--muted);
      font-size: 0.84rem;
      line-height: 1.5;
    }

    .leaderboard {
      display: grid;
      gap: 12px;
    }

    .leader-row {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) auto;
      gap: 14px;
      align-items: center;
      padding: 14px 16px;
      border-radius: 20px;
      background: var(--row-bg);
      border: 1px solid var(--card-border);
    }

    .rank {
      width: 42px;
      height: 42px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      font: 600 0.88rem/1 var(--mono);
      background: var(--rank-bg);
      color: var(--ink);
      flex-shrink: 0;
    }

    .leader-name {
      font-weight: 600;
      font-size: 1rem;
      line-height: 1.35;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .model-link {
      color: var(--accent);
      text-decoration: none;
      transition: opacity 0.15s;
    }

    .model-link:hover {
      opacity: 0.75;
      text-decoration: underline;
    }

    .leader-meta {
      color: var(--muted);
      margin-top: 4px;
      font-size: 0.92rem;
    }

    .leader-score {
      text-align: right;
    }

    .leader-score strong {
      display: block;
      font-family: var(--display);
      font-size: 1.55rem;
      line-height: 1;
    }

    .chart-grid {
      display: grid;
      grid-template-columns: 1.2fr 1fr;
      gap: 18px;
    }

    .chart-stack {
      display: grid;
      gap: 18px;
    }

    .chart-shell {
      min-height: 280px;
    }

    .chart-shell svg {
      width: 100%;
      height: auto;
      display: block;
    }

    .chart-bars {
      display: grid;
      gap: 14px;
    }

    .metric-row {
      display: grid;
      grid-template-columns: minmax(0, 220px) minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
    }

    .metric-label {
      font-size: 0.94rem;
      line-height: 1.45;
      overflow-wrap: anywhere;
    }

    .metric-value {
      font: 500 0.84rem/1.2 var(--mono);
      color: var(--muted);
      white-space: nowrap;
    }

    .chart-caption {
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.55;
    }

    .empty-state {
      min-height: 220px;
      display: grid;
      place-items: center;
      color: var(--muted);
      border: 1px dashed var(--empty-border);
      border-radius: 22px;
      background: var(--empty-bg);
      text-align: center;
      padding: 18px;
    }

    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }

    .mini-badge {
      padding: 9px 12px;
      background: var(--mini-bg);
      border: 1px solid var(--mini-border);
    }

    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      flex: none;
    }

    .dot.stable {
      background: var(--teal);
    }

    .dot.partial {
      background: var(--gold);
    }

    .dot.failed {
      background: var(--danger);
    }

    .reliability-list {
      display: grid;
      gap: 10px;
    }

    .reliability-row {
      display: grid;
      grid-template-columns: minmax(0, 220px) minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
    }

    .reliability-row .leader-name {
      white-space: normal;
      overflow: visible;
    }

    .track {
      width: 100%;
      height: 16px;
      border-radius: 999px;
      background: var(--track-bg);
      overflow: hidden;
      border: 1px solid var(--track-border);
    }

    .track-fill {
      height: 100%;
      border-radius: inherit;
    }

    .track-fill.stable {
      background: linear-gradient(90deg, rgba(35, 109, 106, 0.96), rgba(70, 146, 143, 0.88));
    }

    .track-fill.partial {
      background: linear-gradient(90deg, rgba(160, 119, 27, 0.96), rgba(205, 164, 72, 0.88));
    }

    .track-fill.failed {
      background: linear-gradient(90deg, rgba(166, 61, 64, 0.96), rgba(214, 111, 104, 0.88));
    }

    .status-note {
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.4;
    }

    .table-wrap {
      overflow: auto;
      border-radius: 22px;
      border: 1px solid var(--table-border);
      background: var(--table-bg);
      -webkit-overflow-scrolling: touch;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 820px;
    }

    th,
    td {
      padding: 14px 16px;
      border-bottom: 1px solid var(--card-border);
      text-align: left;
      vertical-align: top;
      font-size: 0.94rem;
    }

    th {
      font: 600 0.75rem/1.2 var(--mono);
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--muted);
      background: var(--th-bg);
      position: sticky;
      top: 0;
      z-index: 1;
    }

    tbody tr:hover {
      background: var(--row-hover);
    }

    .num {
      text-align: right;
      font-variant-numeric: tabular-nums;
    }

    code,
    .mono {
      font-family: var(--mono);
    }

    .badge {
      padding: 8px 12px;
      border: 1px solid transparent;
    }

    .badge.stable {
      color: var(--stable-badge-color);
      background: var(--stable-badge-bg);
      border-color: var(--stable-badge-border);
    }

    .badge.partial {
      color: var(--partial-badge-color);
      background: var(--partial-badge-bg);
      border-color: var(--partial-badge-border);
    }

    .badge.failed {
      color: var(--failed-badge-color);
      background: var(--failed-badge-bg);
      border-color: var(--failed-badge-border);
    }

    .details-list {
      display: grid;
      gap: 14px;
    }

    details {
      border: 1px solid var(--details-border);
      border-radius: 22px;
      background: var(--details-bg);
      overflow: hidden;
    }

    summary {
      list-style: none;
      cursor: pointer;
      padding: 18px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
    }

    summary::-webkit-details-marker {
      display: none;
    }

    .details-title {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }

    .details-meta {
      color: var(--muted);
      font-size: 0.9rem;
    }

    .details-body {
      padding: 0 20px 20px;
    }

    .fact-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }

    .fact {
      padding: 14px;
      border-radius: 18px;
      background: var(--fact-bg);
      border: 1px solid var(--fact-border);
    }

    .fact strong {
      display: block;
      margin-bottom: 6px;
      font: 600 0.72rem/1.2 var(--mono);
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }

    .response-cell {
      max-width: 440px;
      line-height: 1.55;
      overflow-wrap: break-word;
      word-break: break-word;
    }

    .result-image-cell {
      min-width: 220px;
    }

    .result-image {
      display: grid;
      grid-template-columns: 92px minmax(0, 1fr);
      gap: 12px;
      align-items: start;
    }

    .result-thumb {
      width: 92px;
      aspect-ratio: 4 / 3;
      border-radius: 14px;
      overflow: hidden;
      border: 0;
      padding: 0;
      cursor: zoom-in;
      background: rgba(31, 26, 17, 0.08);
    }

    .result-thumb img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }

    .result-image-meta {
      display: grid;
      gap: 6px;
    }

    .result-image-title {
      font-weight: 600;
      line-height: 1.4;
    }

    .result-image-links {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      font-size: 0.84rem;
      color: var(--muted);
    }

    .text-link {
      color: var(--accent);
      text-decoration: none;
    }

    .text-link:hover {
      text-decoration: underline;
    }

    .section-desc {
      color: var(--muted);
      font-size: 0.94rem;
      line-height: 1.6;
      margin-top: 6px;
      margin-bottom: 14px;
      max-width: 70ch;
    }

    .scatter-legend {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 6px 16px;
      margin-top: 14px;
    }

    .scatter-legend-item {
      display: flex;
      align-items: baseline;
      gap: 8px;
      font-size: 0.88rem;
      line-height: 1.45;
    }

    .scatter-num {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 22px;
      height: 22px;
      border-radius: 50%;
      font: 600 0.72rem/1 var(--mono);
      color: white;
      flex-shrink: 0;
    }

    .footer-note {
      margin-top: 18px;
      color: var(--muted);
      font-size: 0.9rem;
      line-height: 1.6;
    }

    .image-modal {
      width: min(1100px, calc(100vw - 32px));
      max-height: calc(100vh - 32px);
      border: 1px solid var(--details-border);
      border-radius: 28px;
      padding: 0;
      background: var(--panel-strong);
      color: var(--ink);
      box-shadow: var(--shadow);
    }

    .image-modal::backdrop {
      background: rgba(14, 10, 7, 0.72);
      backdrop-filter: blur(8px);
    }

    .image-modal-body {
      padding: 18px;
      display: grid;
      gap: 14px;
    }

    .image-modal-head {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
    }

    .image-modal-close {
      border: 1px solid var(--pill-border);
      background: var(--pill-bg);
      color: var(--ink);
      border-radius: 999px;
      padding: 8px 12px;
      cursor: pointer;
      font: 500 0.78rem/1 var(--mono);
    }

    .image-modal-figure {
      margin: 0;
      border-radius: 20px;
      overflow: hidden;
      background: rgba(31, 26, 17, 0.08);
    }

    .image-modal-figure img {
      display: block;
      width: 100%;
      height: auto;
      max-height: calc(100vh - 220px);
      object-fit: contain;
      background: rgba(31, 26, 17, 0.08);
    }

    .image-modal-caption {
      color: var(--muted);
      font-size: 0.9rem;
      line-height: 1.6;
    }

    @media (max-width: 1080px) {
      .split,
      .chart-grid {
        grid-template-columns: 1fr;
      }

      .summary-grid,
      .fact-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @media (max-width: 720px) {
      .page {
        width: min(100vw - 20px, 1240px);
        padding-top: 12px;
      }

      .hero,
      .panel-body {
        padding: 18px;
      }

      .summary-grid,
      .fact-grid {
        grid-template-columns: 1fr;
      }

      .reliability-row {
        grid-template-columns: 1fr;
      }

      .metric-row {
        grid-template-columns: 1fr;
      }

      .result-image {
        grid-template-columns: 1fr;
      }

      .result-thumb {
        width: 100%;
        max-width: 220px;
      }

      h1 {
        max-width: none;
      }
    }
  </style>
</head>
<body>
  <div class="page">
    <header class="panel hero">
      <button class="theme-toggle" id="theme-toggle" aria-label="Toggle dark/light mode">Light / Dark</button>
      <div class="eyebrow">Vision Benchmark Report</div>
      <h1 id="page-title">$title</h1>
      <p class="hero-copy" id="hero-copy">
        Automated local benchmark comparing vision-capable LLMs on $machine_label.
        Each model was asked to describe the same set of images, and we measured latency, memory use, throughput, and reliability. $stable_count
      </p>
      <div class="hero-meta" id="hero-meta"></div>
      <div class="summary-grid" id="summary-grid"></div>
    </header>

    <div class="layout">
      <section class="split">
        <article class="panel panel-body">
          <div class="section-kicker">Prompt</div>
          <h2>What the run actually asked</h2>
          <p class="section-desc">Every model received the exact same prompt and images. The prompt below was sent as the user message alongside each test image.</p>
          <div class="prompt-box" id="prompt-box"></div>
          <div class="profiles" id="profiles"></div>
          <div class="sample-gallery" id="sample-gallery"></div>
        </article>
        <article class="panel panel-body">
          <div class="section-kicker">Leaderboard</div>
          <h2>Fastest reliable results</h2>
          <p class="section-desc">Top 5 models that successfully processed every image, ranked by average response time. Click a model name to view it in LM Studio.</p>
          <div class="leaderboard" id="leaderboard"></div>
          <p class="footer-note">
            Ranking favors fully successful runs first, then lower average latency and lower memory use.
          </p>
        </article>
      </section>

      <section class="chart-grid">
        <article class="panel panel-body">
          <div class="section-kicker">Speed vs Size</div>
          <h2>Latency vs memory footprint</h2>
          <p class="section-desc">Each bubble is a model. Position shows the trade-off between response speed (vertical) and RAM usage (horizontal). Bubble size reflects token throughput. Ideal models sit in the bottom-left corner: fast and light.</p>
          <div class="chart-shell" id="scatter-chart"></div>
          <div class="legend">
            <span class="mini-badge"><span class="dot stable"></span> Stable (all images OK)</span>
            <span class="mini-badge"><span class="dot partial"></span> Partial (some failures)</span>
            <span class="mini-badge"><span class="dot failed"></span> Failed (no successes)</span>
          </div>
        </article>
        <div class="chart-stack">
          <article class="panel panel-body">
            <div class="section-kicker">Latency</div>
            <h2>Average response time</h2>
            <p class="section-desc">How long each stable model takes on average to describe an image. Shorter bars are faster.</p>
            <div class="chart-shell" id="latency-chart"></div>
          </article>
          <article class="panel panel-body">
            <div class="section-kicker">Reliability</div>
            <h2>Success rate by model</h2>
            <p class="section-desc">What fraction of test images each model handled without errors. A full bar means every image got a valid response.</p>
            <div class="reliability-list" id="reliability-chart"></div>
          </article>
        </div>
      </section>

      <section class="chart-grid">
        <article class="panel panel-body">
          <div class="section-kicker">Memory</div>
          <h2>RAM usage comparison</h2>
          <p class="section-desc">How much system memory each model requires when loaded. Lower is better, especially on machines with limited RAM.</p>
          <div class="chart-shell" id="memory-chart"></div>
        </article>
        <article class="panel panel-body">
          <div class="section-kicker">Throughput</div>
          <h2>Token generation speed</h2>
          <p class="section-desc">How many completion tokens each model generates per second. Higher throughput means faster, more detailed responses.</p>
          <div class="chart-shell" id="throughput-chart"></div>
        </article>
      </section>

      <section class="chart-grid">
        <article class="panel panel-body">
          <div class="section-kicker">Efficiency</div>
          <h2>Tokens per second per GiB</h2>
          <p class="section-desc">A combined efficiency metric: how many tokens each model generates per second for each GiB of RAM it uses. Higher is better — it rewards models that are both fast and lightweight.</p>
          <div class="chart-shell" id="efficiency-chart"></div>
        </article>
        <article class="panel panel-body">
          <div class="section-kicker">Load Time</div>
          <h2>Model loading speed</h2>
          <p class="section-desc">How long each model takes to load into memory from disk. Shorter load times mean faster cold starts.</p>
          <div class="chart-shell" id="load-time-chart"></div>
        </article>
      </section>

      <section class="panel panel-body">
        <div class="section-kicker">Latency Spread</div>
        <h2>Min / Median / Max latency per model</h2>
        <p class="section-desc">Shows the range of response times across images for each stable model. A tight spread indicates consistent performance; a wide spread means the model is sensitive to image complexity.</p>
        <div class="chart-shell" id="latency-spread-chart"></div>
      </section>

      <section class="panel panel-body">
        <div class="section-kicker">Heatmap</div>
        <h2>Per-image latency heatmap</h2>
        <p class="section-desc">Each cell shows how long a model took to respond to a specific image. Darker cells mean slower responses. Helps identify which images are hardest for each model.</p>
        <div class="chart-shell" id="latency-heatmap" style="overflow-x:auto"></div>
      </section>

      <section class="chart-grid">
        <article class="panel panel-body">
          <div class="section-kicker">Format Comparison</div>
          <h2>GGUF vs safetensors performance</h2>
          <p class="section-desc">Average latency and throughput grouped by model format. Compares how different weight formats perform on Apple Silicon.</p>
          <div class="chart-shell" id="format-comparison-chart"></div>
        </article>
        <article class="panel panel-body">
          <div class="section-kicker">Speed Tiers</div>
          <h2>Models by response time tier</h2>
          <p class="section-desc">Models grouped into speed tiers: under 2s (real-time), 2–5s (interactive), and 5s+ (batch). The green zone marks the sub-2-second target.</p>
          <div class="chart-shell" id="speed-tier-chart"></div>
        </article>
      </section>

      <section class="panel panel-body">
        <div class="section-kicker">Responses</div>
        <h2>Side-by-side response comparison</h2>
        <p class="section-desc">For each test image, compare what every model actually said. Useful for judging response quality and accuracy beyond just speed.</p>
        <div class="details-list" id="response-comparison"></div>
      </section>

      <section class="panel panel-body">
        <div class="section-kicker">Summary Table</div>
        <h2>All benchmarked results</h2>
        <p class="section-desc">Full metrics for every model tested. Click a model name to open it in LM Studio. RAM is the memory used while the model is loaded; Avg/Median are per-image response times; Tok/s is completion token throughput.</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Result</th>
                <th>Format</th>
                <th class="num">RAM GiB</th>
                <th class="num">Avg s</th>
                <th class="num">Median s</th>
                <th class="num">Tok/s</th>
                <th>Success</th>
                <th>Reasoning</th>
              </tr>
            </thead>
            <tbody id="summary-table"></tbody>
          </table>
        </div>
      </section>

      <section class="panel panel-body">
        <div class="section-kicker">Model Detail</div>
        <h2>Per-image outputs</h2>
        <p class="section-desc">Expand any model to see exactly how it responded to each test image, including timing, token counts, and the raw response text.</p>
        <div class="details-list" id="model-details"></div>
      </section>
    </div>
  </div>

  <dialog class="image-modal" id="image-modal">
    <div class="image-modal-body">
      <div class="image-modal-head">
        <div>
          <div class="section-kicker">Benchmark Image</div>
          <h3 id="image-modal-title">Image preview</h3>
        </div>
        <button class="image-modal-close" id="image-modal-close" type="button">Close</button>
      </div>
      <figure class="image-modal-figure">
        <img id="image-modal-img" alt="">
      </figure>
      <div class="image-modal-caption" id="image-modal-caption"></div>
    </div>
  </dialog>

  <script id="benchmark-data" type="application/json">$payload_json</script>
  <script>
    const rawData = document.getElementById("benchmark-data");
    const data = JSON.parse(rawData.textContent);
    const models = Array.isArray(data.models) ? data.models.slice() : [];
    const summary = data.summary && typeof data.summary === "object" ? data.summary : {};
    const requestProfiles = Array.isArray(data.request_profiles) ? data.request_profiles : [];
    const machine = data.machine && typeof data.machine === "object" ? data.machine : {};
    const images = normalizeImages(data.images);
    const imageMap = new Map(images.map((image) => [image.label, image]));

    /* Theme toggle */
    (function initTheme() {
      const saved = localStorage.getItem("bench-theme");
      if (saved === "dark" || saved === "light") {
        document.documentElement.setAttribute("data-theme", saved);
      }
      const btn = document.getElementById("theme-toggle");
      if (btn) {
        btn.addEventListener("click", function () {
          const current = document.documentElement.getAttribute("data-theme");
          const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
          let next;
          if (current === "dark") {
            next = "light";
          } else if (current === "light") {
            next = "dark";
          } else {
            next = prefersDark ? "light" : "dark";
          }
          document.documentElement.setAttribute("data-theme", next);
          localStorage.setItem("bench-theme", next);
        });
      }
    })();

    function byId(id) {
      return document.getElementById(id);
    }

    function normalizeImages(rawImages) {
      if (!Array.isArray(rawImages)) {
        return [];
      }
      return rawImages
        .map((item) => {
          if (typeof item === "string") {
            return { label: item, title: item, report_path: null };
          }
          if (!item || typeof item !== "object" || typeof item.label !== "string") {
            return null;
          }
          return {
            label: item.label,
            title: typeof item.title === "string" ? item.title : item.label,
            report_path: typeof item.report_path === "string" ? item.report_path : null,
            page_url: typeof item.page_url === "string" ? item.page_url : null,
            source_url: typeof item.source_url === "string" ? item.source_url : null,
            author: typeof item.author === "string" ? item.author : null,
            license_name: typeof item.license_name === "string" ? item.license_name : null,
            license_url: typeof item.license_url === "string" ? item.license_url : null,
          };
        })
        .filter(Boolean);
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function imageInfo(label) {
      return imageMap.get(String(label || "")) || { label: String(label || "image"), title: String(label || "image"), report_path: null };
    }

    function imageAttribution(image) {
      const parts = [];
      if (image.author) {
        parts.push("By " + image.author);
      }
      if (image.license_name) {
        parts.push(image.license_name);
      }
      return parts.join(" · ");
    }

    function imagePreviewButton(image, className) {
      if (!image.report_path) {
        return '<div class="' + className + '"></div>';
      }
      return (
        '<button type="button" class="' + className + '" data-image-label="' + escapeHtml(image.label) + '">' +
        '<img src="' + escapeHtml(image.report_path) + '" alt="' + escapeHtml(image.title || image.label) + '">' +
        "</button>"
      );
    }

    function imageLinks(image) {
      const links = [];
      if (image.report_path) {
        links.push('<a class="text-link" href="' + escapeHtml(image.report_path) + '" target="_blank" rel="noopener">Open image</a>');
      }
      if (image.page_url) {
        links.push('<a class="text-link" href="' + escapeHtml(image.page_url) + '" target="_blank" rel="noopener">Source page</a>');
      }
      if (image.license_url && image.license_name) {
        links.push('<a class="text-link" href="' + escapeHtml(image.license_url) + '" target="_blank" rel="noopener">' + escapeHtml(image.license_name) + "</a>");
      }
      return links.join(" ");
    }

    function renderImageCell(label) {
      const image = imageInfo(label);
      return (
        '<div class="result-image">' +
        imagePreviewButton(image, "result-thumb") +
        '<div class="result-image-meta">' +
        '<div class="result-image-title">' + escapeHtml(image.title || image.label) + '</div>' +
        '<div class="status-note"><code>' + escapeHtml(image.label) + "</code></div>" +
        (imageAttribution(image) ? '<div class="status-note">' + escapeHtml(imageAttribution(image)) + "</div>" : "") +
        '<div class="result-image-links">' + imageLinks(image) + "</div>" +
        "</div>" +
        "</div>"
      );
    }

    function preferredMemory(model) {
      if (typeof model.reported_memory_gib === "number") {
        return model.reported_memory_gib;
      }
      if (typeof model.estimated_total_memory_gib === "number") {
        return model.estimated_total_memory_gib;
      }
      return null;
    }

    function successRatio(model) {
      const total = typeof model.images_benchmarked === "number" ? model.images_benchmarked : 0;
      if (!total) {
        return 0;
      }
      return (typeof model.successful_images === "number" ? model.successful_images : 0) / total;
    }

    function isStable(model) {
      return Boolean(
        typeof model.average_latency_seconds === "number" &&
        typeof model.images_benchmarked === "number" &&
        typeof model.successful_images === "number" &&
        model.images_benchmarked > 0 &&
        model.successful_images === model.images_benchmarked
      );
    }

    function modelStatus(model) {
      const ratio = successRatio(model);
      if (isStable(model)) {
        return "stable";
      }
      if (ratio > 0) {
        return "partial";
      }
      return "failed";
    }

    function resultLabel(model) {
      return String(model.model_key || "unknown") + " [" + String(model.profile_name || "default") + "]";
    }

    function shortResultLabel(model) {
      const key = String(model.model_key || "unknown");
      return key.length > 32 ? key.slice(0, 29) + "..." : key;
    }

    function modelUrl(model) {
      const key = String(model.model_key || "");
      if (!key || !key.includes("/")) { return ""; }
      return "https://lmstudio.ai/models/" + encodeURI(key);
    }

    function linkedName(model, text) {
      const url = modelUrl(model);
      const display = escapeHtml(text || resultLabel(model));
      if (url) {
        return '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener" class="model-link">' + display + "</a>";
      }
      return display;
    }

    function sortModels(a, b) {
      const stableDiff = Number(isStable(b)) - Number(isStable(a));
      if (stableDiff !== 0) {
        return stableDiff;
      }
      const latencyDiff =
        (typeof a.average_latency_seconds === "number" ? a.average_latency_seconds : Number.POSITIVE_INFINITY) -
        (typeof b.average_latency_seconds === "number" ? b.average_latency_seconds : Number.POSITIVE_INFINITY);
      if (latencyDiff !== 0) {
        return latencyDiff;
      }
      const memoryDiff = (preferredMemory(a) ?? Number.POSITIVE_INFINITY) - (preferredMemory(b) ?? Number.POSITIVE_INFINITY);
      if (memoryDiff !== 0) {
        return memoryDiff;
      }
      return successRatio(b) - successRatio(a);
    }

    function formatFixed(value, digits) {
      if (typeof value !== "number" || !Number.isFinite(value)) {
        return "—";
      }
      return value.toFixed(digits);
    }

    function formatSuccess(model) {
      const success = typeof model.successful_images === "number" ? model.successful_images : 0;
      const total = typeof model.images_benchmarked === "number" ? model.images_benchmarked : 0;
      return String(success) + "/" + String(total);
    }

    function formatDate(value) {
      if (typeof value !== "string") {
        return "Unknown";
      }
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) {
        return escapeHtml(value);
      }
      return date.toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        timeZoneName: "short",
      });
    }

    function formatDuration(startedAt, finishedAt) {
      const start = new Date(startedAt);
      const finish = new Date(finishedAt);
      if (Number.isNaN(start.getTime()) || Number.isNaN(finish.getTime())) {
        return "Unknown";
      }
      let remaining = Math.max(0, Math.round((finish.getTime() - start.getTime()) / 1000));
      const hours = Math.floor(remaining / 3600);
      remaining -= hours * 3600;
      const minutes = Math.floor(remaining / 60);
      const seconds = remaining - minutes * 60;
      const parts = [];
      if (hours) {
        parts.push(String(hours) + "h");
      }
      if (minutes || hours) {
        parts.push(String(minutes) + "m");
      }
      parts.push(String(seconds) + "s");
      return parts.join(" ");
    }

    function badge(label, status) {
      return '<span class="badge ' + status + '">' + escapeHtml(label) + "</span>";
    }

    function renderSummaryCards(sortedModels, stableModels) {
      const recommended = stableModels[0] || null;
      const lightest = stableModels
        .slice()
        .sort((a, b) => (preferredMemory(a) ?? Number.POSITIVE_INFINITY) - (preferredMemory(b) ?? Number.POSITIVE_INFINITY))[0] || null;
      const cards = [
        {
          label: "Benchmarked",
          value: String(summary.model_count ?? sortedModels.length),
          subtext: String(data.images?.length ?? 0) + " images across " + String(requestProfiles.length || 1) + " profile(s)",
        },
        {
          label: "Stable",
          value: String(summary.stable_model_count ?? stableModels.length),
          subtext: stableModels.length ? "Fully completed image set" : "No stable completions",
        },
        {
          label: "Fastest Stable",
          value: recommended ? formatFixed(recommended.average_latency_seconds, 3) + "s" : "—",
          subtext: recommended ? resultLabel(recommended) : "No stable result",
        },
        {
          label: "Lightest Stable",
          value: lightest && preferredMemory(lightest) !== null ? formatFixed(preferredMemory(lightest), 2) + " GiB" : "—",
          subtext: lightest ? resultLabel(lightest) : "No stable result",
        },
      ];
      byId("summary-grid").innerHTML = cards
        .map(
          (card) =>
            '<div class="summary-card">' +
            '<div class="summary-label">' + escapeHtml(card.label) + "</div>" +
            '<div class="summary-value">' + escapeHtml(card.value) + "</div>" +
            '<div class="summary-subtext">' + escapeHtml(card.subtext) + "</div>" +
            "</div>"
        )
        .join("");
    }

    function renderMeta() {
      const meta = [
        "Started " + formatDate(data.started_at),
        "Finished " + formatDate(data.finished_at),
        "Duration " + formatDuration(data.started_at, data.finished_at),
        String(machine.model_name || "Unknown machine"),
        String(machine.chip || "Unknown chip"),
        machine.total_memory_gb ? String(machine.total_memory_gb) + " GB RAM" : "Memory unknown",
      ];
      byId("hero-meta").innerHTML = meta
        .map((item) => '<span class="meta-pill">' + escapeHtml(item) + "</span>")
        .join("");
    }

    function renderPrompt() {
      byId("prompt-box").textContent = typeof data.prompt === "string" ? data.prompt : "";
      byId("profiles").innerHTML = requestProfiles
        .map((profile) => {
          const extra = profile.extra_body && typeof profile.extra_body === "object" ? Object.keys(profile.extra_body) : [];
          return (
            '<div class="profile-chip">' +
            "<strong>" + escapeHtml(profile.name || "default") + "</strong>" +
            '<div class="status-note">temperature ' + escapeHtml(String(profile.temperature ?? "0.0")) +
            " · max_tokens " + escapeHtml(String(profile.max_tokens ?? "—")) + "</div>" +
            '<div class="status-note">' +
            (extra.length ? escapeHtml("extra fields: " + extra.join(", ")) : "default request body") +
            "</div>" +
            "</div>"
          );
        })
        .join("");
    }

    function renderSampleGallery() {
      byId("sample-gallery").innerHTML = images
        .map((image) => {
          return (
            '<article class="sample-card">' +
            imagePreviewButton(image, "sample-thumb") +
            '<div class="sample-title">' + escapeHtml(image.title || image.label) + "</div>" +
            '<div class="sample-meta"><code>' + escapeHtml(image.label) + "</code></div>" +
            (imageAttribution(image) ? '<div class="sample-meta">' + escapeHtml(imageAttribution(image)) + "</div>" : "") +
            "</article>"
          );
        })
        .join("");
    }

    function initImageModal() {
      var modal = byId("image-modal");
      var modalImg = byId("image-modal-img");
      var modalTitle = byId("image-modal-title");
      var modalCaption = byId("image-modal-caption");
      if (!modal || !modalImg || !modalTitle || !modalCaption) {
        return;
      }

      document.addEventListener("click", function (event) {
        var target = event.target;
        if (!(target instanceof Element)) {
          return;
        }
        var button = target.closest("[data-image-label]");
        if (!button) {
          return;
        }
        var image = imageInfo(button.getAttribute("data-image-label"));
        if (!image.report_path) {
          return;
        }
        modalTitle.textContent = image.title || image.label;
        modalImg.src = image.report_path;
        modalImg.alt = image.title || image.label;
        modalCaption.innerHTML =
          '<div><code>' + escapeHtml(image.label) + "</code></div>" +
          (imageAttribution(image) ? '<div>' + escapeHtml(imageAttribution(image)) + "</div>" : "") +
          (image.page_url ? '<div><a class="text-link" href="' + escapeHtml(image.page_url) + '" target="_blank" rel="noopener">Original source page</a></div>' : "");
        modal.showModal();
      });

      byId("image-modal-close").addEventListener("click", function () {
        modal.close();
      });
      modal.addEventListener("click", function (event) {
        var rect = modal.getBoundingClientRect();
        var inBounds =
          rect.top <= event.clientY &&
          event.clientY <= rect.top + rect.height &&
          rect.left <= event.clientX &&
          event.clientX <= rect.left + rect.width;
        if (!inBounds) {
          modal.close();
        }
      });
    }

    function renderLeaderboard(sortedModels, stableModels) {
      const rows = stableModels.slice(0, 5);
      if (!rows.length) {
        byId("leaderboard").innerHTML = '<div class="empty-state">No stable results completed the entire image set.</div>';
        return;
      }
      byId("leaderboard").innerHTML = rows
        .map((model, index) => {
          const memory = preferredMemory(model);
          return (
            '<div class="leader-row">' +
            '<div class="rank">#' + String(index + 1) + "</div>" +
            '<div>' +
            '<div class="leader-name">' + linkedName(model) + "</div>" +
            '<div class="leader-meta">' +
            escapeHtml(String(model.format || "unknown")) +
            " · " +
            escapeHtml(memory !== null ? formatFixed(memory, 2) + " GiB" : "RAM unknown") +
            " · " +
            escapeHtml(formatFixed(model.completion_tokens_per_second, 3) + " tok/s") +
            "</div>" +
            "</div>" +
            '<div class="leader-score"><strong>' + escapeHtml(formatFixed(model.average_latency_seconds, 3)) + 's</strong><span class="status-note">' +
            escapeHtml(formatSuccess(model)) + " success</span></div>" +
            "</div>"
          );
        })
        .join("");
    }

    function renderScatter(sortedModels) {
      const plottable = sortedModels.filter((model) => preferredMemory(model) !== null && typeof model.average_latency_seconds === "number");
      if (!plottable.length) {
        byId("scatter-chart").innerHTML = '<div class="empty-state">No results had both latency and memory data.</div>';
        return;
      }

      const width = 760;
      const height = 440;
      const margin = { top: 28, right: 28, bottom: 52, left: 64 };
      const plotWidth = width - margin.left - margin.right;
      const plotHeight = height - margin.top - margin.bottom;
      const memoryValues = plottable.map((model) => preferredMemory(model));
      const latencyValues = plottable.map((model) => model.average_latency_seconds);
      const memoryRange = Math.max(...memoryValues) - Math.min(...memoryValues);
      const latencyRange = Math.max(...latencyValues) - Math.min(...latencyValues);
      const memoryPad = memoryRange * 0.08 || 0.5;
      const latencyPad = latencyRange * 0.08 || 0.5;
      const minMemory = Math.min(...memoryValues) - memoryPad;
      const maxMemory = Math.max(...memoryValues) + memoryPad;
      const minLatency = Math.min(...latencyValues) - latencyPad;
      const maxLatency = Math.max(...latencyValues) + latencyPad;

      function scale(value, min, max, size) {
        if (max === min) { return size / 2; }
        return ((value - min) / (max - min)) * size;
      }
      function xFor(model) {
        return margin.left + scale(preferredMemory(model), minMemory, maxMemory, plotWidth);
      }
      function yFor(model) {
        return margin.top + plotHeight - scale(model.average_latency_seconds, minLatency, maxLatency, plotHeight);
      }
      function radiusFor(model) {
        var throughput = typeof model.completion_tokens_per_second === "number" ? model.completion_tokens_per_second : 0;
        return Math.max(10, Math.min(22, 10 + throughput / 4));
      }
      function colorFor(model) {
        var status = modelStatus(model);
        var style = getComputedStyle(document.documentElement);
        if (status === "stable") { return style.getPropertyValue("--teal").trim() || "#236d6a"; }
        if (status === "partial") { return style.getPropertyValue("--gold").trim() || "#a0771b"; }
        return style.getPropertyValue("--danger").trim() || "#a63d40";
      }

      var xTicks = 5;
      var yTicks = 5;
      var grid = [];
      for (var i = 0; i <= xTicks; i++) {
        var gx = margin.left + (plotWidth / xTicks) * i;
        var xVal = minMemory + ((maxMemory - minMemory) / xTicks) * i;
        grid.push('<line x1="' + gx + '" y1="' + margin.top + '" x2="' + gx + '" y2="' + (margin.top + plotHeight) + '" stroke="var(--chart-grid)" stroke-dasharray="4 6" />');
        grid.push('<text x="' + gx + '" y="' + (height - 16) + '" text-anchor="middle" fill="var(--muted)" font-size="11" font-family="IBM Plex Mono">' + escapeHtml(xVal.toFixed(1)) + "</text>");
      }
      for (var j = 0; j <= yTicks; j++) {
        var gy = margin.top + plotHeight - (plotHeight / yTicks) * j;
        var yVal = minLatency + ((maxLatency - minLatency) / yTicks) * j;
        grid.push('<line x1="' + margin.left + '" y1="' + gy + '" x2="' + (margin.left + plotWidth) + '" y2="' + gy + '" stroke="var(--chart-grid)" stroke-dasharray="4 6" />');
        grid.push('<text x="' + (margin.left - 10) + '" y="' + (gy + 4) + '" text-anchor="end" fill="var(--muted)" font-size="11" font-family="IBM Plex Mono">' + escapeHtml(yVal.toFixed(1)) + "</text>");
      }

      /* Draw numbered dots instead of inline labels to avoid overlap */
      var dots = plottable.map(function (model, idx) {
        var x = xFor(model);
        var y = yFor(model);
        var r = radiusFor(model);
        var color = colorFor(model);
        var mem = preferredMemory(model);
        var lat = model.average_latency_seconds;
        var num = String(idx + 1);
        return '<g>' +
          '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="' + color + '" fill-opacity="0.78" stroke="var(--dot-stroke)" stroke-width="1.5" />' +
          '<text x="' + x + '" y="' + (y + 4.5) + '" text-anchor="middle" fill="white" font-size="11" font-weight="600" font-family="IBM Plex Mono" pointer-events="none">' + num + '</text>' +
          '<title>' + escapeHtml(resultLabel(model) + " | " + formatFixed(mem, 2) + " GiB | " + formatFixed(lat, 3) + "s") + '</title>' +
          '</g>';
      }).join("");

      var svg = '<svg viewBox="0 0 ' + width + ' ' + height + '" role="img" aria-label="Latency versus memory scatter chart">' +
        '<rect x="0" y="0" width="' + width + '" height="' + height + '" rx="22" fill="var(--chart-rect)" />' +
        grid.join("") +
        '<line x1="' + margin.left + '" y1="' + (margin.top + plotHeight) + '" x2="' + (margin.left + plotWidth) + '" y2="' + (margin.top + plotHeight) + '" stroke="var(--chart-axis)" stroke-width="1.3" />' +
        '<line x1="' + margin.left + '" y1="' + margin.top + '" x2="' + margin.left + '" y2="' + (margin.top + plotHeight) + '" stroke="var(--chart-axis)" stroke-width="1.3" />' +
        '<text x="' + (margin.left + plotWidth / 2) + '" y="' + (height - 4) + '" text-anchor="middle" fill="var(--muted)" font-size="12" font-family="IBM Plex Mono">Memory footprint (GiB)</text>' +
        '<text x="16" y="' + (margin.top + plotHeight / 2) + '" transform="rotate(-90 16 ' + (margin.top + plotHeight / 2) + ')" text-anchor="middle" fill="var(--muted)" font-size="12" font-family="IBM Plex Mono">Avg latency (s) — lower is better</text>' +
        dots +
        '</svg>';

      /* Build legend that maps numbers to model names */
      var legendHtml = '<div class="scatter-legend">' + plottable.map(function (model, idx) {
        var color = colorFor(model);
        var mem = preferredMemory(model);
        var lat = model.average_latency_seconds;
        var tps = model.completion_tokens_per_second;
        return '<div class="scatter-legend-item">' +
          '<span class="scatter-num" style="background:' + color + '">' + String(idx + 1) + '</span>' +
          '<span>' + linkedName(model) +
          ' <span class="status-note">' + escapeHtml(formatFixed(mem, 1) + " GiB · " + formatFixed(lat, 2) + "s · " + formatFixed(tps, 1) + " tok/s") + '</span></span>' +
          '</div>';
      }).join("") + '</div>';

      byId("scatter-chart").innerHTML = svg + legendHtml;
    }

    function renderMetricBars(options) {
      var items = Array.isArray(options.items) ? options.items : [];
      if (!items.length) {
        byId(options.targetId).innerHTML = '<div class="empty-state">No chart data available.</div>';
        return;
      }
      var maxValue = Math.max.apply(null, items.map(function (item) { return options.valueFor(item) || 0; }));
      byId(options.targetId).innerHTML =
        '<div class="chart-bars">' +
        items.map(function (item) {
          var value = options.valueFor(item) || 0;
          var width = maxValue === 0 ? 0 : (value / maxValue) * 100;
          var color = isStable(item) ? "var(--teal)" : successRatio(item) > 0 ? "var(--gold)" : "var(--danger)";
          return (
            '<div class="metric-row">' +
            '<div class="metric-label">' + linkedName(item, shortResultLabel(item)) + "</div>" +
            '<div class="track"><div class="track-fill" style="width:' + String(Math.max(0, Math.min(100, width))) + '%; background:' + color + ';"></div></div>' +
            '<div class="metric-value">' + escapeHtml(options.valueLabel(item)) + "</div>" +
            "</div>"
          );
        }).join("") +
        "</div>";
    }

    function renderLatencyChart(stableModels) {
      if (!stableModels.length) {
        byId("latency-chart").innerHTML = '<div class="empty-state">No fully successful runs to rank.</div>';
        return;
      }
      renderMetricBars({
        targetId: "latency-chart",
        items: stableModels.slice(0, 8),
        valueFor: function (model) { return model.average_latency_seconds; },
        valueLabel: function (model) { return formatFixed(model.average_latency_seconds, 3) + "s"; },
      });
    }

    function renderReliability(sortedModels) {
      byId("reliability-chart").innerHTML = sortedModels
        .map((model) => {
          const ratio = successRatio(model);
          const status = modelStatus(model);
          const reasoning = model.reasoning_seen ? "reasoning seen" : "no reasoning";
          return (
            '<div class="reliability-row">' +
            '<div><div class="leader-name">' + escapeHtml(shortResultLabel(model)) + "</div>" +
            '<div class="status-note">' + escapeHtml(reasoning) + "</div></div>" +
            '<div class="track"><div class="track-fill ' + status + '" style="width:' + String(Math.max(0, Math.min(100, ratio * 100))) + '%"></div></div>' +
            '<div>' + badge(formatSuccess(model), status) + "</div>" +
            "</div>"
          );
        })
        .join("");
    }

    function renderMemoryChart(sortedModels) {
      var plottable = sortedModels.filter(function (model) { return preferredMemory(model) !== null; });
      if (!plottable.length) {
        byId("memory-chart").innerHTML = '<div class="empty-state">No memory data available.</div>';
        return;
      }
      plottable = plottable.slice().sort(function (a, b) { return (preferredMemory(a) || 0) - (preferredMemory(b) || 0); });
      renderMetricBars({
        targetId: "memory-chart",
        items: plottable.slice(0, 10),
        valueFor: function (model) { return preferredMemory(model); },
        valueLabel: function (model) { return formatFixed(preferredMemory(model), 2) + " GiB"; },
      });
    }

    function renderThroughputChart(sortedModels) {
      var plottable = sortedModels.filter(function (model) { return typeof model.completion_tokens_per_second === "number" && model.completion_tokens_per_second > 0; });
      if (!plottable.length) {
        byId("throughput-chart").innerHTML = '<div class="empty-state">No throughput data available.</div>';
        return;
      }
      plottable.sort(function (a, b) { return (b.completion_tokens_per_second || 0) - (a.completion_tokens_per_second || 0); });
      renderMetricBars({
        targetId: "throughput-chart",
        items: plottable.slice(0, 10),
        valueFor: function (model) { return model.completion_tokens_per_second; },
        valueLabel: function (model) { return formatFixed(model.completion_tokens_per_second, 1) + " tok/s"; },
      });
    }

    function renderEfficiencyChart(sortedModels) {
      var plottable = sortedModels.filter(function (model) {
        return typeof model.completion_tokens_per_second === "number" && model.completion_tokens_per_second > 0 && preferredMemory(model) !== null && preferredMemory(model) > 0;
      });
      if (!plottable.length) {
        byId("efficiency-chart").innerHTML = '<div class="empty-state">No efficiency data available.</div>';
        return;
      }
      function efficiency(model) {
        return model.completion_tokens_per_second / preferredMemory(model);
      }
      plottable.sort(function (a, b) { return efficiency(b) - efficiency(a); });
      renderMetricBars({
        targetId: "efficiency-chart",
        items: plottable.slice(0, 10),
        valueFor: efficiency,
        valueLabel: function (model) { return formatFixed(efficiency(model), 2) + " tok/s/GiB"; },
      });
    }

    function renderLoadTimeChart(sortedModels) {
      var plottable = sortedModels.filter(function (model) {
        return typeof model.load_time_seconds === "number" && model.load_time_seconds > 0;
      });
      if (!plottable.length) {
        byId("load-time-chart").innerHTML = '<div class="empty-state">No load time data available.</div>';
        return;
      }
      plottable.sort(function (a, b) { return (a.load_time_seconds || 0) - (b.load_time_seconds || 0); });
      renderMetricBars({
        targetId: "load-time-chart",
        items: plottable.slice(0, 10),
        valueFor: function (model) { return model.load_time_seconds; },
        valueLabel: function (model) { return formatFixed(model.load_time_seconds, 2) + "s"; },
      });
    }

    function renderLatencySpread(stableModels) {
      if (!stableModels.length) {
        byId("latency-spread-chart").innerHTML = '<div class="empty-state">No stable models to show spread for.</div>';
        return;
      }
      var spreads = stableModels.map(function (model) {
        var results = Array.isArray(model.results) ? model.results : [];
        var times = results.map(function (r) { return r.elapsed_seconds; }).filter(function (t) { return typeof t === "number"; }).sort(function (a, b) { return a - b; });
        if (!times.length) return null;
        var min = times[0];
        var max = times[times.length - 1];
        var mid = times.length % 2 === 0 ? (times[times.length / 2 - 1] + times[times.length / 2]) / 2 : times[Math.floor(times.length / 2)];
        return { model: model, min: min, median: mid, max: max };
      }).filter(Boolean);
      if (!spreads.length) {
        byId("latency-spread-chart").innerHTML = '<div class="empty-state">No per-image timing data available.</div>';
        return;
      }
      var globalMax = Math.max.apply(null, spreads.map(function (s) { return s.max; }));
      var barHtml = spreads.map(function (s) {
        var leftPct = (s.min / globalMax) * 100;
        var widthPct = ((s.max - s.min) / globalMax) * 100;
        var medPct = (s.median / globalMax) * 100;
        return (
          '<div class="metric-row">' +
          '<div class="metric-label">' + linkedName(s.model, shortResultLabel(s.model)) + '</div>' +
          '<div class="track" style="position:relative">' +
          '<div style="position:absolute;left:' + leftPct + '%;width:' + Math.max(widthPct, 0.5) + '%;height:100%;background:var(--teal);opacity:0.35;border-radius:4px"></div>' +
          '<div style="position:absolute;left:' + medPct + '%;width:2px;height:100%;background:var(--teal)"></div>' +
          '</div>' +
          '<div class="metric-value" style="min-width:10em;font-size:0.82rem">' + escapeHtml(formatFixed(s.min, 2) + ' / ' + formatFixed(s.median, 2) + ' / ' + formatFixed(s.max, 2) + 's') + '</div>' +
          '</div>'
        );
      }).join('');
      byId("latency-spread-chart").innerHTML = '<div class="chart-bars">' + barHtml + '</div>';
    }

    function renderLatencyHeatmap(sortedModels) {
      var modelsWithResults = sortedModels.filter(function (m) { return Array.isArray(m.results) && m.results.length > 0; });
      if (!modelsWithResults.length || !images.length) {
        byId("latency-heatmap").innerHTML = '<div class="empty-state">No per-image data for heatmap.</div>';
        return;
      }
      var imageLabels = images.map(function (img) { return img.label; });
      var allTimes = [];
      modelsWithResults.forEach(function (m) {
        m.results.forEach(function (r) {
          if (typeof r.elapsed_seconds === "number") allTimes.push(r.elapsed_seconds);
        });
      });
      if (!allTimes.length) {
        byId("latency-heatmap").innerHTML = '<div class="empty-state">No timing data for heatmap.</div>';
        return;
      }
      var minTime = Math.min.apply(null, allTimes);
      var maxTime = Math.max.apply(null, allTimes);
      var range = maxTime - minTime || 1;

      function cellColor(t) {
        if (typeof t !== "number") return "var(--chart-rect)";
        var ratio = (t - minTime) / range;
        var r = Math.round(35 + ratio * 130);
        var g = Math.round(109 - ratio * 60);
        var b = Math.round(106 - ratio * 40);
        return "rgb(" + r + "," + g + "," + b + ")";
      }

      var headerCells = '<th style="position:sticky;left:0;z-index:2;background:var(--surface)">Model</th>' +
        imageLabels.map(function (label) {
          var img = imageInfo(label);
          var short = (img.title || label).length > 12 ? (img.title || label).slice(0, 10) + ".." : (img.title || label);
          return '<th style="writing-mode:vertical-lr;font-size:0.72rem;padding:4px 2px">' + escapeHtml(short) + '</th>';
        }).join('');

      var bodyRows = modelsWithResults.map(function (model) {
        var resultMap = {};
        (model.results || []).forEach(function (r) { resultMap[r.image_label] = r; });
        var cells = imageLabels.map(function (label) {
          var r = resultMap[label];
          var t = r ? r.elapsed_seconds : null;
          var bg = cellColor(t);
          var text = typeof t === "number" ? formatFixed(t, 2) : "—";
          return '<td style="background:' + bg + ';color:#fff;text-align:center;font-size:0.78rem;padding:3px 6px;font-family:IBM Plex Mono,monospace" title="' + escapeHtml(shortResultLabel(model) + ' × ' + label + ': ' + text + 's') + '">' + escapeHtml(text) + '</td>';
        }).join('');
        return '<tr><td style="position:sticky;left:0;z-index:1;background:var(--surface);white-space:nowrap;font-size:0.82rem;padding:4px 8px">' + escapeHtml(shortResultLabel(model)) + '</td>' + cells + '</tr>';
      }).join('');

      var legendHtml = '<div style="display:flex;align-items:center;gap:8px;margin-top:8px;font-size:0.78rem;color:var(--muted)">' +
        '<span>' + formatFixed(minTime, 1) + 's</span>' +
        '<div style="flex:1;max-width:200px;height:10px;border-radius:4px;background:linear-gradient(to right,rgb(35,109,106),rgb(165,49,66))"></div>' +
        '<span>' + formatFixed(maxTime, 1) + 's</span>' +
        '</div>';

      byId("latency-heatmap").innerHTML =
        '<table style="border-collapse:collapse;width:100%"><thead><tr>' + headerCells + '</tr></thead><tbody>' + bodyRows + '</tbody></table>' + legendHtml;
    }

    function renderFormatComparison(sortedModels) {
      var stableByFormat = {};
      sortedModels.forEach(function (m) {
        if (typeof m.average_latency_seconds !== "number") return;
        var fmt = (m.format || "unknown").toLowerCase();
        if (!stableByFormat[fmt]) stableByFormat[fmt] = [];
        stableByFormat[fmt].push(m);
      });
      var formats = Object.keys(stableByFormat).sort();
      if (formats.length < 1) {
        byId("format-comparison-chart").innerHTML = '<div class="empty-state">Not enough format data.</div>';
        return;
      }
      var rows = formats.map(function (fmt) {
        var ms = stableByFormat[fmt];
        var avgLat = ms.reduce(function (s, m) { return s + m.average_latency_seconds; }, 0) / ms.length;
        var avgTok = ms.reduce(function (s, m) { return s + (m.completion_tokens_per_second || 0); }, 0) / ms.length;
        var avgMem = ms.filter(function (m) { return preferredMemory(m) !== null; });
        var memVal = avgMem.length > 0 ? avgMem.reduce(function (s, m) { return s + preferredMemory(m); }, 0) / avgMem.length : null;
        return { format: fmt, count: ms.length, avgLat: avgLat, avgTok: avgTok, avgMem: memVal };
      });
      var maxLat = Math.max.apply(null, rows.map(function (r) { return r.avgLat; }));
      var maxTok = Math.max.apply(null, rows.map(function (r) { return r.avgTok; }));
      var colors = { gguf: "#5b8def", safetensors: "#e5704b", mlx: "#50c878" };
      var html = rows.map(function (r) {
        var barColor = colors[r.format] || "#888";
        var latPct = maxLat > 0 ? (r.avgLat / maxLat * 100) : 0;
        var tokPct = maxTok > 0 ? (r.avgTok / maxTok * 100) : 0;
        return '<div style="margin-bottom:16px">' +
          '<div style="font-weight:600;font-size:0.9rem;margin-bottom:4px">' + escapeHtml(r.format.toUpperCase()) +
          ' <span class="status-note">(' + r.count + ' model' + (r.count !== 1 ? 's' : '') + ')</span></div>' +
          '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">' +
          '<span style="width:70px;font-size:0.78rem;color:var(--muted)">Latency</span>' +
          '<div style="flex:1;height:18px;background:var(--chart-grid);border-radius:4px;overflow:hidden">' +
          '<div style="width:' + latPct + '%;height:100%;background:' + barColor + ';border-radius:4px;transition:width .3s"></div></div>' +
          '<span class="mono" style="font-size:0.82rem;min-width:55px;text-align:right">' + formatFixed(r.avgLat, 2) + 's</span></div>' +
          '<div style="display:flex;align-items:center;gap:8px">' +
          '<span style="width:70px;font-size:0.78rem;color:var(--muted)">Tok/s</span>' +
          '<div style="flex:1;height:18px;background:var(--chart-grid);border-radius:4px;overflow:hidden">' +
          '<div style="width:' + tokPct + '%;height:100%;background:' + barColor + ';opacity:0.7;border-radius:4px;transition:width .3s"></div></div>' +
          '<span class="mono" style="font-size:0.82rem;min-width:55px;text-align:right">' + formatFixed(r.avgTok, 1) + '</span></div>' +
          (r.avgMem !== null ? '<div style="font-size:0.78rem;color:var(--muted);margin-top:2px;margin-left:78px">Avg RAM: ' + formatFixed(r.avgMem, 2) + ' GiB</div>' : '') +
          '</div>';
      }).join('');
      byId("format-comparison-chart").innerHTML = html;
    }

    function renderSpeedTierChart(sortedModels) {
      var tiers = [
        { label: "Real-time (< 2s)", max: 2, color: "#50c878", models: [] },
        { label: "Interactive (2–5s)", max: 5, color: "#f0ad4e", models: [] },
        { label: "Batch (5s+)", max: Infinity, color: "#d9534f", models: [] }
      ];
      sortedModels.forEach(function (m) {
        if (typeof m.average_latency_seconds !== "number") return;
        for (var i = 0; i < tiers.length; i++) {
          if (m.average_latency_seconds < tiers[i].max) {
            tiers[i].models.push(m);
            break;
          }
        }
      });
      var maxLat = Math.max.apply(null, sortedModels.filter(function (m) { return typeof m.average_latency_seconds === "number"; }).map(function (m) { return m.average_latency_seconds; }).concat([1]));
      var html = tiers.map(function (tier) {
        if (!tier.models.length) {
          return '<div style="margin-bottom:16px;opacity:0.5">' +
            '<div style="font-weight:600;font-size:0.9rem;margin-bottom:4px;color:' + tier.color + '">' + escapeHtml(tier.label) + '</div>' +
            '<div style="font-size:0.82rem;color:var(--muted);font-style:italic">No models in this tier</div></div>';
        }
        var modelBars = tier.models.sort(function (a, b) { return a.average_latency_seconds - b.average_latency_seconds; }).map(function (m) {
          var pct = Math.max(3, m.average_latency_seconds / maxLat * 100);
          var tokInfo = m.completion_tokens_per_second ? " · " + formatFixed(m.completion_tokens_per_second, 1) + " tok/s" : "";
          return '<div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">' +
            '<span style="min-width:180px;font-size:0.82rem;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + escapeHtml(shortResultLabel(m)) + '">' + escapeHtml(shortResultLabel(m)) + '</span>' +
            '<div style="flex:1;height:20px;background:var(--chart-grid);border-radius:4px;overflow:hidden">' +
            '<div style="width:' + pct + '%;height:100%;background:' + tier.color + ';border-radius:4px;transition:width .3s"></div></div>' +
            '<span class="mono" style="font-size:0.82rem;min-width:100px;text-align:right">' + formatFixed(m.average_latency_seconds, 3) + 's' + escapeHtml(tokInfo) + '</span></div>';
        }).join('');
        return '<div style="margin-bottom:20px">' +
          '<div style="font-weight:600;font-size:0.9rem;margin-bottom:8px;color:' + tier.color + '">' + escapeHtml(tier.label) +
          ' <span class="status-note">(' + tier.models.length + ')</span></div>' + modelBars + '</div>';
      }).join('');
      byId("speed-tier-chart").innerHTML = html;
    }

    function renderResponseComparison(sortedModels) {
      var modelsWithResults = sortedModels.filter(function (m) { return Array.isArray(m.results) && m.results.length > 0; });
      if (!modelsWithResults.length || !images.length) {
        byId("response-comparison").innerHTML = '<div class="empty-state">No response data to compare.</div>';
        return;
      }
      var imageLabels = images.map(function (img) { return img.label; });
      var html = imageLabels.map(function (label) {
        var img = imageInfo(label);
        var responses = modelsWithResults.map(function (model) {
          var result = (model.results || []).find(function (r) { return r.image_label === label; });
          var text = result ? (result.error ? "ERROR: " + result.error : (result.response_text || "—")) : "—";
          var time = result && typeof result.elapsed_seconds === "number" ? formatFixed(result.elapsed_seconds, 2) + "s" : "—";
          return (
            '<div style="border:1px solid var(--chart-grid);border-radius:8px;padding:12px;flex:1;min-width:250px">' +
            '<div style="font-weight:600;margin-bottom:4px">' + escapeHtml(shortResultLabel(model)) + ' <span class="status-note">' + escapeHtml(time) + '</span></div>' +
            '<div style="font-size:0.85rem;white-space:pre-wrap;max-height:200px;overflow-y:auto">' + escapeHtml(text) + '</div>' +
            '</div>'
          );
        }).join('');
        return (
          '<details>' +
          '<summary>' +
          '<div class="details-title">' +
          '<strong>' + escapeHtml(img.title || label) + '</strong>' +
          '<span class="status-note">' + escapeHtml(label) + '</span>' +
          '</div>' +
          '</summary>' +
          '<div class="details-body" style="display:flex;flex-wrap:wrap;gap:12px">' + responses + '</div>' +
          '</details>'
        );
      }).join('');
      byId("response-comparison").innerHTML = html;
    }

    function renderSummaryTable(sortedModels) {
      byId("summary-table").innerHTML = sortedModels
        .map((model) => {
          const status = modelStatus(model);
          return (
            "<tr>" +
            "<td><strong>" + linkedName(model) + "</strong></td>" +
            "<td>" + escapeHtml(String(model.format || "unknown")) + "</td>" +
            '<td class="num mono">' + escapeHtml(preferredMemory(model) !== null ? formatFixed(preferredMemory(model), 3) : "—") + "</td>" +
            '<td class="num mono">' + escapeHtml(formatFixed(model.average_latency_seconds, 3)) + "</td>" +
            '<td class="num mono">' + escapeHtml(formatFixed(model.median_latency_seconds, 3)) + "</td>" +
            '<td class="num mono">' + escapeHtml(formatFixed(model.completion_tokens_per_second, 3)) + "</td>" +
            "<td>" + badge(formatSuccess(model), status) + "</td>" +
            "<td>" + badge(model.reasoning_seen ? "yes" : "no", model.reasoning_seen ? "partial" : "stable") + "</td>" +
            "</tr>"
          );
        })
        .join("");
    }

    function fact(label, value) {
      return '<div class="fact"><strong>' + escapeHtml(label) + "</strong>" + escapeHtml(value) + "</div>";
    }

    function renderModelDetails(sortedModels) {
      byId("model-details").innerHTML = sortedModels
        .map((model) => {
          const facts = [
            fact("Format", String(model.format || "unknown")),
            fact("Memory", preferredMemory(model) !== null ? formatFixed(preferredMemory(model), 2) + " GiB" : "unknown"),
            fact("Latency", typeof model.average_latency_seconds === "number" ? formatFixed(model.average_latency_seconds, 3) + "s avg" : "no stable latency"),
            fact("Success", formatSuccess(model)),
          ].join("");

          const rows = Array.isArray(model.results)
            ? model.results
                .map((result) => {
                  const response = result.error ? "ERROR: " + result.error : (result.response_text || "—");
                  return (
                    "<tr>" +
                    '<td class="result-image-cell">' + renderImageCell(result.image_label || "image") + "</td>" +
                    '<td class="num mono">' + escapeHtml(formatFixed(result.elapsed_seconds, 3)) + "</td>" +
                    '<td class="num mono">' + escapeHtml(result.prompt_tokens != null ? String(result.prompt_tokens) : "—") + "</td>" +
                    '<td class="num mono">' + escapeHtml(result.completion_tokens != null ? String(result.completion_tokens) : "—") + "</td>" +
                    "<td>" + badge(result.reasoning_present ? "yes" : "no", result.reasoning_present ? "partial" : "stable") + "</td>" +
                    '<td class="response-cell">' + escapeHtml(response) + "</td>" +
                    "</tr>"
                  );
                })
                .join("")
            : "";

          return (
            "<details>" +
            "<summary>" +
            '<div class="details-title">' +
            "<strong>" + linkedName(model) + "</strong>" +
            badge(formatSuccess(model), modelStatus(model)) +
            "</div>" +
            '<div class="details-meta">' + escapeHtml(String(model.identifier || "unknown identifier")) + "</div>" +
            "</summary>" +
            '<div class="details-body">' +
            '<div class="fact-grid">' + facts + "</div>" +
            '<div class="table-wrap"><table><thead><tr><th>Image</th><th class="num">Time s</th><th class="num">Prompt</th><th class="num">Completion</th><th>Reasoning</th><th>Response</th></tr></thead><tbody>' + rows + "</tbody></table></div>" +
            "</div>" +
            "</details>"
          );
        })
        .join("");
    }

    const sortedModels = models.slice().sort(sortModels);
    const stableModels = sortedModels.filter(isStable);

    renderMeta();
    renderPrompt();
    renderSampleGallery();
    renderSummaryCards(sortedModels, stableModels);
    renderLeaderboard(sortedModels, stableModels);
    renderScatter(sortedModels);
    renderLatencyChart(stableModels);
    renderReliability(sortedModels);
    renderMemoryChart(sortedModels);
    renderThroughputChart(sortedModels);
    renderEfficiencyChart(sortedModels);
    renderLoadTimeChart(sortedModels);
    renderLatencySpread(stableModels);
    renderLatencyHeatmap(sortedModels);
    renderFormatComparison(sortedModels);
    renderSpeedTierChart(sortedModels);
    renderResponseComparison(sortedModels);
    renderSummaryTable(sortedModels);
    renderModelDetails(sortedModels);
    initImageModal();
  </script>
</body>
</html>
""")
    return template.substitute(
        title=html.escape(report_title),
        machine_label=html.escape(machine_label),
        stable_count=html.escape(stable_count),
        payload_json=payload_json,
    )


def _require_dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise BenchmarkError(f"Expected {label} to be a JSON object.")
    return cast(dict[str, object], value)


def _require_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise BenchmarkError(f"Expected {label} to be a JSON array.")
    return cast(list[object], value)


def _require_str(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise BenchmarkError(f"Expected {label} to be a string.")
    return value


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise BenchmarkError("Expected an optional string field in benchmark JSON.")


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    raise BenchmarkError("Expected an optional number field in benchmark JSON.")


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise BenchmarkError("Expected an optional integer field in benchmark JSON.")


def _require_float(value: object, label: str) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    raise BenchmarkError(f"Expected {label} to be a number.")


def _require_int(value: object, label: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise BenchmarkError(f"Expected {label} to be an integer.")


def benchmark_run_from_payload(payload: dict[str, object]) -> BenchmarkRun:
    started_at = datetime.fromisoformat(
        _require_str(payload.get("started_at"), "started_at")
    )
    finished_at = datetime.fromisoformat(
        _require_str(payload.get("finished_at"), "finished_at")
    )
    prompt_text = _require_str(payload.get("prompt"), "prompt")
    machine = _require_dict(payload.get("machine"), "machine")

    images: list[BenchmarkImage] = []
    for raw_image in _require_list(payload.get("images"), "images"):
        if isinstance(raw_image, str):
            images.append(BenchmarkImage(source_path=Path(raw_image), label=raw_image))
            continue

        image_dict = _require_dict(raw_image, "image")
        label = _require_str(image_dict.get("label"), "images[].label")
        report_path = _optional_str(image_dict.get("report_path"))
        images.append(
            BenchmarkImage(
                source_path=Path(report_path) if report_path else Path(label),
                label=label,
                title=_optional_str(image_dict.get("title")),
                page_url=_optional_str(image_dict.get("page_url")),
                source_url=_optional_str(image_dict.get("source_url")),
                author=_optional_str(image_dict.get("author")),
                license_name=_optional_str(image_dict.get("license_name")),
                license_url=_optional_str(image_dict.get("license_url")),
                report_path=report_path,
            )
        )

    request_profiles = [
        RequestProfile(
            name=_require_str(item_dict.get("name"), "request_profiles[].name"),
            prompt_text=_require_str(
                item_dict.get("prompt_text"), "request_profiles[].prompt_text"
            ),
            temperature=_require_float(
                item_dict.get("temperature"), "request_profiles[].temperature"
            ),
            max_tokens=_require_int(
                item_dict.get("max_tokens"), "request_profiles[].max_tokens"
            ),
            extra_body=_require_dict(
                item_dict.get("extra_body"), "request_profiles[].extra_body"
            ),
        )
        for item_dict in (
            _require_dict(item, "request profile")
            for item in _require_list(
                payload.get("request_profiles"), "request_profiles"
            )
        )
    ]

    model_results: list[ModelBenchmarkResult] = []
    for item in _require_list(payload.get("models"), "models"):
        item_dict = _require_dict(item, "model result")
        image_results = [
            ImageBenchmarkResult(
                image_label=_require_str(
                    image_dict.get("image_label"), "models[].results[].image_label"
                ),
                elapsed_seconds=_require_float(
                    image_dict.get("elapsed_seconds"),
                    "models[].results[].elapsed_seconds",
                ),
                prompt_tokens=_optional_int(image_dict.get("prompt_tokens")),
                completion_tokens=_optional_int(image_dict.get("completion_tokens")),
                total_tokens=_optional_int(image_dict.get("total_tokens")),
                response_text=_require_str(
                    image_dict.get("response_text"), "models[].results[].response_text"
                ),
                reasoning_present=bool(image_dict.get("reasoning_present")),
                reasoning_preview=_optional_str(image_dict.get("reasoning_preview")),
                finish_reason=_optional_str(image_dict.get("finish_reason")),
                error=_optional_str(image_dict.get("error")),
            )
            for image_dict in (
                _require_dict(result, "image result")
                for result in _require_list(
                    item_dict.get("results"), "models[].results"
                )
            )
        ]
        model_results.append(
            ModelBenchmarkResult(
                model_key=_require_str(
                    item_dict.get("model_key"), "models[].model_key"
                ),
                display_name=_require_str(
                    item_dict.get("display_name"), "models[].display_name"
                ),
                identifier=_require_str(
                    item_dict.get("identifier"), "models[].identifier"
                ),
                profile_name=_require_str(
                    item_dict.get("profile_name"), "models[].profile_name"
                ),
                format=_require_str(item_dict.get("format"), "models[].format"),
                params=_optional_str(item_dict.get("params")),
                variant=_optional_str(item_dict.get("variant")),
                estimated_gpu_memory_gib=_optional_float(
                    item_dict.get("estimated_gpu_memory_gib")
                ),
                estimated_total_memory_gib=_optional_float(
                    item_dict.get("estimated_total_memory_gib")
                ),
                load_time_seconds=_optional_float(item_dict.get("load_time_seconds")),
                reported_memory_gib=_optional_float(
                    item_dict.get("reported_memory_gib")
                ),
                average_latency_seconds=_optional_float(
                    item_dict.get("average_latency_seconds")
                ),
                median_latency_seconds=_optional_float(
                    item_dict.get("median_latency_seconds")
                ),
                min_latency_seconds=_optional_float(
                    item_dict.get("min_latency_seconds")
                ),
                max_latency_seconds=_optional_float(
                    item_dict.get("max_latency_seconds")
                ),
                completion_tokens_per_second=_optional_float(
                    item_dict.get("completion_tokens_per_second")
                ),
                total_prompt_tokens=_require_int(
                    item_dict.get("total_prompt_tokens"),
                    "models[].total_prompt_tokens",
                ),
                total_completion_tokens=_require_int(
                    item_dict.get("total_completion_tokens"),
                    "models[].total_completion_tokens",
                ),
                images_benchmarked=_require_int(
                    item_dict.get("images_benchmarked"),
                    "models[].images_benchmarked",
                ),
                successful_images=_require_int(
                    item_dict.get("successful_images"),
                    "models[].successful_images",
                ),
                failed_images=_require_int(
                    item_dict.get("failed_images"), "models[].failed_images"
                ),
                reasoning_seen=bool(item_dict.get("reasoning_seen")),
                benchmark_error=_optional_str(item_dict.get("benchmark_error")),
                results=image_results,
            )
        )

    excluded_models = [
        InstalledModel(
            model_key=_require_str(
                item_dict.get("model_key"), "excluded_models[].model_key"
            ),
            display_name=_require_str(
                item_dict.get("display_name"), "excluded_models[].display_name"
            ),
            format=_require_str(item_dict.get("format"), "excluded_models[].format"),
            architecture=_optional_str(item_dict.get("architecture")),
            publisher=_optional_str(item_dict.get("publisher")),
            vision=bool(item_dict.get("vision")),
            trained_for_tool_use=bool(item_dict.get("trained_for_tool_use")),
            params=_optional_str(item_dict.get("params")),
            size_bytes=_optional_int(item_dict.get("size_bytes")),
            variant=_optional_str(item_dict.get("variant")),
            max_context_length=_optional_int(item_dict.get("max_context_length")),
        )
        for item_dict in (
            _require_dict(item, "excluded model")
            for item in _require_list(payload.get("excluded_models"), "excluded_models")
        )
    ]

    return BenchmarkRun(
        started_at=started_at,
        finished_at=finished_at,
        prompt_text=prompt_text,
        machine=machine,
        images=images,
        request_profiles=request_profiles,
        summary=_require_dict(payload.get("summary"), "summary"),
        model_results=model_results,
        excluded_models=excluded_models,
    )


def load_run_from_json(path: Path) -> BenchmarkRun:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BenchmarkError(f"Expected benchmark JSON object in {path}")
    run = benchmark_run_from_payload(payload)
    for image in run.images:
        if not image.source_path.is_absolute():
            image.source_path = (path.parent / image.source_path).resolve()
    return run


def copy_report_images(run: BenchmarkRun, output_dir: Path) -> dict[str, str]:
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    copied_paths: dict[str, str] = {}
    for image in run.images:
        if not image.source_path.is_file():
            continue
        destination = image_dir / image.label
        if image.source_path.resolve() != destination.resolve():
            shutil.copy2(image.source_path, destination)
        relative_path = destination.relative_to(output_dir).as_posix()
        image.report_path = relative_path
        copied_paths[image.label] = relative_path
    return copied_paths


def write_reports(
    output_dir: Path, report_name: str, run: BenchmarkRun
) -> ReportArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{report_name}.json"
    markdown_path = output_dir / f"{report_name}.md"
    html_path = output_dir / f"{report_name}.html"
    latest_json_path = output_dir / "latest.json"
    latest_markdown_path = output_dir / "latest.md"
    latest_html_path = output_dir / "latest.html"
    index_html_path = output_dir / "index.html"

    report_paths = copy_report_images(run, output_dir)
    json_payload = build_json_payload(run, report_paths)
    json_blob = json.dumps(json_payload, indent=2)
    markdown_blob = build_markdown_report(run)
    html_blob = build_html_report(json_payload)

    json_path.write_text(json_blob + "\n", encoding="utf-8")
    latest_json_path.write_text(json_blob + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_blob, encoding="utf-8")
    latest_markdown_path.write_text(markdown_blob, encoding="utf-8")
    html_path.write_text(html_blob, encoding="utf-8")
    latest_html_path.write_text(html_blob, encoding="utf-8")
    index_html_path.write_text(html_blob, encoding="utf-8")
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")

    return ReportArtifacts(
        json_path=json_path,
        markdown_path=markdown_path,
        html_path=html_path,
        latest_json_path=latest_json_path,
        latest_markdown_path=latest_markdown_path,
        latest_html_path=latest_html_path,
        index_html_path=index_html_path,
    )
