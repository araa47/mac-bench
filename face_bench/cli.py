from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    name="face-bench", help="Face recognition benchmark for local models."
)

_dataset_dir = typer.Option(Path("face_data"), help="Directory to store dataset")
_output_dir = typer.Option(Path("docs/face-recognition"), help="Output directory")


@app.command()
def download_dataset(
    output_dir: Annotated[Path, _dataset_dir],
) -> None:
    """Download the LFW face recognition subset."""
    from .dataset import download_dataset as do_download

    dataset = do_download(output_dir)
    typer.echo(f"Dataset ready: {len(dataset.pairs)} pairs in {dataset.images_dir}")


@app.command()
def list_models() -> None:
    """List available face recognition models."""
    from .benchmark import get_available_models

    models = get_available_models()
    if not models:
        typer.echo("No face recognition libraries installed.")
        typer.echo(
            "Install with: pip install face-recognition deepface tf-keras insightface onnxruntime"
        )
        raise typer.Exit(1)
    typer.echo(f"Available models ({len(models)}):")
    for m in models:
        typer.echo(f"  - {m['name']} ({m['library']}) - {m['ram_estimate']}")


@app.command()
def benchmark(
    dataset_dir: Annotated[Path, typer.Option(help="Dataset directory")] = Path(
        "face_data"
    ),
    models: Annotated[
        str, typer.Option(help="Comma-separated model names or 'all'")
    ] = "all",
    output_dir: Annotated[Path, _output_dir] = Path("docs/face-recognition"),
    output_name: Annotated[
        str, typer.Option(help="Output file base name")
    ] = "face-benchmark",
) -> None:
    """Run the face recognition benchmark."""
    from .benchmark import run_face_benchmark
    from .dataset import download_dataset, load_dataset
    from .reporting import write_face_reports

    # Ensure dataset exists
    if not (dataset_dir / "pairs.json").exists():
        typer.echo("Dataset not found, downloading...")
        dataset = download_dataset(dataset_dir)
    else:
        dataset = load_dataset(dataset_dir)

    model_list = None if models == "all" else models.split(",")
    typer.echo(f"Running benchmark with {len(dataset.pairs)} pairs...")
    run = run_face_benchmark(dataset, model_list)

    typer.echo(f"Benchmark complete. Writing reports to {output_dir}...")
    artifacts = write_face_reports(output_dir, output_name, run)
    typer.echo(f"JSON:  {artifacts['json_path']}")
    typer.echo(f"HTML:  {artifacts['html_path']}")
    typer.echo(f"Index: {artifacts['index_html_path']}")


@app.command()
def render_report(
    input_file: Annotated[Path, typer.Option(help="Input JSON file")],
    output_dir: Annotated[Path, _output_dir] = Path("docs/face-recognition"),
) -> None:
    """Render HTML report from existing JSON results."""
    import json

    from .reporting import build_face_html_report

    payload = json.loads(input_file.read_text(encoding="utf-8"))
    html = build_face_html_report(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / "index.html"
    dest.write_text(html, encoding="utf-8")
    typer.echo(f"Report written to {dest}")


def main() -> None:
    app()
