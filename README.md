# mac-bench

`mac-bench` benchmarks local LM Studio models on macOS. The current suite is `vision`: it sends the same prompt and the same image set to each installed vision model, then records latency, RAM use, throughput, success rate, and failure modes.

This repo started from a practical Home Assistant problem: finding a local vision model that can turn doorbell snapshots into short, useful person descriptions.

## Live Report

Published report:

- <https://araa47.github.io/mac-bench/>

Repository copy:

- [Static dashboard](docs/index.html)
- [Markdown report](docs/vision-doorbell-example.md)
- [Raw JSON](docs/vision-doorbell-example.json)

## What The Vision Benchmark Tests

Every model gets:

- the same prompt
- the same local image set
- the same LM Studio OpenAI-compatible API path

The report measures:

- load memory
- per-image latency
- completion throughput
- full-set success rate
- blank answers, image-processing failures, and model crashes
- whether reasoning text leaked into the response path

The bundled public example uses 5 repo-generated doorbell and porch security-camera frames, committed as `1280px`-wide JPEGs so the benchmark corpus stays realistic without shipping oversized stock media.

- Image folder: [examples/images](examples/images)
- Credits: [examples/images/CREDITS.md](examples/images/CREDITS.md)
- Prompt: [examples/prompts/doorbell-person.txt](examples/prompts/doorbell-person.txt)

## Current Example Run

Example benchmark date: `2026-03-23`

Example machine:

- `Mac mini`
- `Apple M4 Pro`
- `64 GB RAM`

Example workload:

- 5 generated doorbell/security-camera images
- 5 installed `gguf` vision models
- 1 prompt profile

Headline result:

- Fastest stable model: `mistralai/ministral-3-3b`
- Average image latency: `2.757s`
- Load RAM: `2.78 GiB`
- Stable results: `5/5` models completed all 5 images

Current leaderboard:

| Model | Load RAM GiB | Avg Image Time s | Success | Notes |
|---|---:|---:|---:|---|
| `mistralai/ministral-3-3b` | 2.78 | 2.757 | 5/5 | Fastest stable `gguf` result |
| `allenai/olmocr-2-7b` | 5.62 | 4.722 | 5/5 | Stable after unload/load settle time between models |
| `qwen/qwen2.5-vl-7b` | 5.62 | 4.890 | 5/5 | Stable after unload/load settle time between models |
| `qwen/qwen3.5-35b-a3b` | 20.56 | 10.979 | 5/5 | Stable with adaptive retry when reasoning exhausts the default token budget |
| `qwen/qwen3.5-9b` | 6.10 | 18.482 | 5/5 | Stable with adaptive retry when reasoning exhausts the default token budget |

## Quick Start

Repo-local workflow:

```bash
uv sync --all-extras --dev
uv run python -m mac_bench doctor
uv run python -m mac_bench list-models --format gguf
uv run python -m mac_bench vision benchmark \
  --images-dir examples/images \
  --prompt-file examples/prompts/doorbell-person.txt \
  --preserve-image-names \
  --format gguf \
  --context-length 8192 \
  --load-settle-seconds 5 \
  --unload-settle-seconds 5 \
  --output-dir docs
```

Direct from GitHub with `uvx`:

```bash
uvx --from git+https://github.com/araa47/mac-bench mac-bench doctor
uvx --from git+https://github.com/araa47/mac-bench mac-bench list-models
```

More setup detail lives in [SETUP.md](SETUP.md).

## Example Commands

```bash
uv run python -m mac_bench doctor
uv run python -m mac_bench list-models --format gguf
uv run python -m mac_bench download qwen/qwen3-vl-8b --mlx
uv run python -m mac_bench vision sanitize-images images sample-images
uv run python -m mac_bench vision benchmark --images-dir images --format gguf
uv run python -m mac_bench vision benchmark --profile brief=examples/profiles/brief.json
uv run python -m mac_bench vision render-report --input docs/latest.json --output-dir docs
```

For Apple Silicon runs, benchmark `gguf` and `mlx` separately when you care about optimization. The published example uses a `gguf`-only baseline so the results do not mix inference backends.

## GitHub Pages

The HTML dashboard is fully static. To publish it from the repository:

```bash
uv run python -m mac_bench vision benchmark \
  --images-dir examples/images \
  --prompt-file examples/prompts/doorbell-person.txt \
  --preserve-image-names \
  --format gguf \
  --context-length 8192 \
  --load-settle-seconds 5 \
  --unload-settle-seconds 5 \
  --output-name vision-doorbell-example \
  --output-dir docs
```

That writes:

- `docs/index.html`
- `docs/latest.html`
- `docs/latest.json`
- `docs/latest.md`
- `docs/images/*`

Commit `docs/` and point GitHub Pages at the repository `docs` folder. For this repo, the expected public URL is `https://araa47.github.io/mac-bench/`.

## Development

```bash
uv sync --all-extras --dev
uv run ty check
uv run prek run --all-files
uv run -m pytest
```
