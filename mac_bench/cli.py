from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from .benchmark import run_benchmark, sanitize_image_directory
from .entities import DEFAULT_PERSON_PROMPT, BenchmarkError, RequestProfile
from .lm_studio import download_model, list_installed_models, run_doctor
from .reporting import load_run_from_json, write_reports

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
vision_app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Benchmark image and multimodal prompts against local models.",
)
app.add_typer(vision_app, name="vision")


def read_prompt(
    prompt: str | None,
    prompt_file: Path | None,
) -> str:
    if prompt and prompt_file:
        raise BenchmarkError("Use either --prompt or --prompt-file, not both.")
    if prompt_file is not None:
        return prompt_file.read_text(encoding="utf-8").strip()
    if prompt is not None:
        return prompt.strip()
    return DEFAULT_PERSON_PROMPT


def load_profile_payload(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BenchmarkError(f"Profile file must contain a JSON object: {path}")
    return payload


def build_request_profiles(
    *,
    prompt: str | None,
    prompt_file: Path | None,
    temperature: float,
    max_tokens: int,
    profile_specs: list[str],
) -> list[RequestProfile]:
    base_prompt = read_prompt(prompt, prompt_file)
    if not profile_specs:
        return [
            RequestProfile(
                name="default",
                prompt_text=base_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={},
            )
        ]

    profiles: list[RequestProfile] = []
    for spec in profile_specs:
        if "=" not in spec:
            raise BenchmarkError(
                "Profile specs must use NAME=path/to/profile.json syntax."
            )
        name, raw_path = spec.split("=", maxsplit=1)
        path = Path(raw_path)
        payload = load_profile_payload(path)
        profile_prompt = payload.pop("prompt_text", base_prompt)
        profile_temperature = payload.pop("temperature", temperature)
        profile_max_tokens = payload.pop("max_tokens", max_tokens)
        if not isinstance(profile_prompt, str):
            raise BenchmarkError(f"`prompt_text` must be a string in {path}")
        if not isinstance(profile_temperature, int | float):
            raise BenchmarkError(f"`temperature` must be numeric in {path}")
        if not isinstance(profile_max_tokens, int):
            raise BenchmarkError(f"`max_tokens` must be an integer in {path}")
        profiles.append(
            RequestProfile(
                name=name.strip(),
                prompt_text=profile_prompt.strip(),
                temperature=float(profile_temperature),
                max_tokens=profile_max_tokens,
                extra_body=payload,
            )
        )
    return profiles


def report_name(prefix: str = "mac-bench-vision") -> str:
    return f"{prefix}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"


def handle_benchmark_error(exc: BenchmarkError) -> None:
    typer.secho(str(exc), fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1) from exc


@app.command()
def doctor(
    base_url: Annotated[
        str,
        typer.Option(help="LM Studio local server base URL."),
    ] = "http://127.0.0.1:1234",
) -> None:
    try:
        checks = asyncio.run(run_doctor(base_url))
    except BenchmarkError as exc:
        handle_benchmark_error(exc)
        return

    exit_code = 0
    for check in checks:
        icon = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}[check.status]
        typer.echo(f"[{icon}] {check.name}: {check.detail}")
        if check.guidance:
            typer.echo(f"      {check.guidance}")
        if check.status == "fail":
            exit_code = 1
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("list-models")
def list_models(
    include_non_vision: Annotated[
        bool,
        typer.Option(
            "--include-non-vision",
            help="Show all installed LLMs instead of vision models only.",
        ),
    ] = False,
    format: Annotated[
        list[str] | None,
        typer.Option(
            "--format",
            help="Only show models in the named format. Repeat as needed.",
        ),
    ] = None,
) -> None:
    try:
        models = list_installed_models()
    except BenchmarkError as exc:
        handle_benchmark_error(exc)
        return

    if not include_non_vision:
        models = [model for model in models if model.vision]
    if format:
        normalized_formats = {item.strip().lower() for item in format if item.strip()}
        models = [
            model
            for model in models
            if model.format.strip().lower() in normalized_formats
        ]
    if not models:
        typer.echo("No matching models found.")
        return
    for model in models:
        typer.echo(
            " | ".join(
                [
                    model.model_key,
                    model.display_name,
                    model.format,
                    model.params or "?",
                    "vision" if model.vision else "text-only",
                ]
            )
        )


@app.command()
def download(
    model: Annotated[str, typer.Argument(help="Model name or model@quantization.")],
    mlx: Annotated[bool, typer.Option(help="Prefer MLX search results.")] = False,
    gguf: Annotated[bool, typer.Option(help="Prefer GGUF search results.")] = False,
    yes: Annotated[bool, typer.Option(help="Auto-approve LM Studio prompts.")] = True,
) -> None:
    try:
        exit_code = download_model(
            model_name=model,
            include_mlx=mlx,
            include_gguf=gguf,
            yes=yes,
        )
    except BenchmarkError as exc:
        handle_benchmark_error(exc)
        return
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@vision_app.command("sanitize-images")
def sanitize_images(
    source_dir: Annotated[
        Path,
        typer.Argument(help="Directory containing the original local images."),
    ] = Path("images"),
    destination_dir: Annotated[
        Path,
        typer.Argument(help="Directory that will receive anonymized copies."),
    ] = Path("sample-images"),
    prefix: Annotated[
        str,
        typer.Option(help="Filename prefix for anonymized images."),
    ] = "sample",
    move_files: Annotated[
        bool,
        typer.Option("--move", help="Move files instead of copying them."),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option(help="Overwrite destination files if they already exist."),
    ] = False,
) -> None:
    try:
        copies = sanitize_image_directory(
            source_dir=source_dir,
            destination_dir=destination_dir,
            prefix=prefix,
            move_files=move_files,
            overwrite=overwrite,
        )
    except BenchmarkError as exc:
        handle_benchmark_error(exc)
        return
    typer.echo(f"Wrote {len(copies)} anonymized image(s) to {destination_dir}")


@vision_app.command()
def benchmark(
    images_dir: Annotated[
        Path,
        typer.Option(help="Directory containing benchmark images."),
    ] = Path("images"),
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory for generated markdown, JSON, and HTML reports."),
    ] = Path("runs"),
    model: Annotated[
        list[str] | None,
        typer.Option(
            "--model", help="Benchmark only the named model. Repeat as needed."
        ),
    ] = None,
    exclude_model: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude-model",
            help="Skip the named installed model. Repeat as needed.",
        ),
    ] = None,
    format: Annotated[
        list[str] | None,
        typer.Option(
            "--format",
            help="Benchmark only the named model format. Repeat as needed.",
        ),
    ] = None,
    limit_images: Annotated[
        int | None,
        typer.Option(help="Process only the first N images."),
    ] = None,
    base_url: Annotated[
        str,
        typer.Option(help="LM Studio local server base URL."),
    ] = "http://127.0.0.1:1234",
    include_non_vision: Annotated[
        bool,
        typer.Option(help="Include non-vision installed models."),
    ] = False,
    keep_loaded: Annotated[
        bool,
        typer.Option(help="Keep the final benchmarked model loaded."),
    ] = False,
    prompt: Annotated[
        str | None,
        typer.Option(help="Inline prompt text for the default request profile."),
    ] = None,
    prompt_file: Annotated[
        Path | None,
        typer.Option(help="Read the default prompt from a text file."),
    ] = None,
    temperature: Annotated[
        float,
        typer.Option(help="Default temperature for request profiles."),
    ] = 0.0,
    max_tokens: Annotated[
        int,
        typer.Option(help="Default max_tokens for request profiles."),
    ] = 160,
    profile: Annotated[
        list[str] | None,
        typer.Option(
            "--profile",
            help="Request profile using NAME=path/to/profile.json. Repeat to benchmark a matrix.",
        ),
    ] = None,
    memory_target_gib: Annotated[
        float,
        typer.Option(help="RAM target used for the recommendation summary."),
    ] = 32.0,
    preserve_image_names: Annotated[
        bool,
        typer.Option(help="Keep original image file names in the reports."),
    ] = False,
    output_name: Annotated[
        str | None,
        typer.Option(help="Optional report name prefix override."),
    ] = None,
) -> None:
    try:
        profiles = build_request_profiles(
            prompt=prompt,
            prompt_file=prompt_file,
            temperature=temperature,
            max_tokens=max_tokens,
            profile_specs=list(profile or []),
        )
        run = asyncio.run(
            run_benchmark(
                images_dir=images_dir,
                requested_models=list(model or []) or None,
                excluded_models=list(exclude_model or []) or None,
                allowed_formats=list(format or []) or None,
                limit_images=limit_images,
                base_url=base_url,
                keep_loaded=keep_loaded,
                include_non_vision=include_non_vision,
                request_profiles=profiles,
                memory_target_gib=memory_target_gib,
                preserve_image_names=preserve_image_names,
                show_progress=True,
            )
        )
        artifacts = write_reports(
            output_dir=output_dir,
            report_name=output_name or report_name(),
            run=run,
        )
    except BenchmarkError as exc:
        handle_benchmark_error(exc)
        return
    typer.echo(f"Markdown report: {artifacts.markdown_path}")
    typer.echo(f"Raw results: {artifacts.json_path}")
    typer.echo(f"HTML dashboard: {artifacts.html_path}")
    typer.echo(f"GitHub Pages entrypoint: {artifacts.index_html_path}")


@vision_app.command("render-report")
def render_report(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Existing benchmark JSON payload to render into markdown and HTML.",
        ),
    ] = Path("runs/latest.json"),
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory for generated markdown, JSON, and HTML reports."),
    ] = Path("runs"),
    output_name: Annotated[
        str | None,
        typer.Option(help="Optional report name prefix override."),
    ] = None,
) -> None:
    try:
        run = load_run_from_json(input_path)
        artifacts = write_reports(
            output_dir=output_dir,
            report_name=output_name or input_path.stem,
            run=run,
        )
    except BenchmarkError as exc:
        handle_benchmark_error(exc)
        return
    typer.echo(f"Markdown report: {artifacts.markdown_path}")
    typer.echo(f"Raw results: {artifacts.json_path}")
    typer.echo(f"HTML dashboard: {artifacts.html_path}")
    typer.echo(f"GitHub Pages entrypoint: {artifacts.index_html_path}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
