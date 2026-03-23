# Setup

## Install

Run `mac-bench` without cloning the repo:

```bash
uvx --from git+https://github.com/araa47/mac-bench mac-bench doctor
```

Install it as a local tool:

```bash
uv tool install git+https://github.com/araa47/mac-bench
mac-bench doctor
```

Run it from source:

```bash
git clone https://github.com/araa47/mac-bench
cd mac-bench
uv sync --all-extras --dev
uv run mac-bench doctor
```

## LM Studio Checklist

1. Install [LM Studio](https://lmstudio.ai/).
2. Start LM Studio.
3. Enable the local server on `http://127.0.0.1:1234`.
4. Download one or more vision-capable models.
5. Confirm the environment:

```bash
mac-bench doctor
mac-bench list-models --format gguf
```

## Download Models

Examples:

```bash
mac-bench download qwen/qwen3-vl-8b --mlx
mac-bench download qwen/qwen2.5-vl-7b --gguf
mac-bench download allenai/olmocr-2-7b --gguf
```

## Prepare Images

Use your own images in any folder:

```bash
mac-bench vision benchmark --images-dir /path/to/images --format gguf
```

If you want sanitized publishable copies with neutral names:

```bash
mac-bench vision sanitize-images /path/to/private-images sample-images
```

## Run The Vision Benchmark

Benchmark every installed vision model:

```bash
mac-bench vision benchmark --images-dir images --format gguf
```

On Apple Silicon, compare `gguf` and `mlx` in separate runs when you care about optimization. Mixing formats in one published leaderboard makes it harder to reason about backend differences.

Skip models you already know you do not want to publish or re-test:

```bash
mac-bench vision benchmark \
  --images-dir images \
  --format gguf \
  --exclude-model qwen/qwen3.5-35b-a3b
```

Benchmark only selected models:

```bash
mac-bench vision benchmark \
  --images-dir images \
  --format gguf \
  --model allenai/olmocr-2-7b \
  --model qwen/qwen2.5-vl-7b
```

Quick smoke test:

```bash
mac-bench vision benchmark --images-dir images --format gguf --limit-images 3
```

Outputs are written to `runs/` by default:

- `runs/latest.md`
- `runs/latest.json`
- `runs/latest.html`
- `runs/index.html`
- timestamped report copies for each run

Re-render markdown and HTML from an existing JSON payload:

```bash
mac-bench vision render-report --input runs/latest.json --output-dir runs
```

## GitHub Pages

The HTML report is self-contained, so you can publish it directly from a static folder:

```bash
mac-bench vision benchmark \
  --images-dir images \
  --format gguf \
  --exclude-model qwen/qwen3.5-35b-a3b \
  --output-dir docs
```

That produces `docs/index.html` plus matching JSON and Markdown files. Commit `docs/` and configure GitHub Pages to serve from the repository `docs` folder.

## Custom Prompts

Inline prompt:

```bash
mac-bench vision benchmark \
  --images-dir images \
  --prompt "Describe the visible person in one sentence."
```

Prompt file:

```bash
mac-bench vision benchmark \
  --images-dir images \
  --prompt-file examples/prompts/doorbell-person.txt
```

## Request Profiles

Profiles let you benchmark the same models against multiple request configurations.

Example profile file:

- [examples/profiles/brief.json](examples/profiles/brief.json)
- [examples/profiles/detailed.json](examples/profiles/detailed.json)

Run a profile matrix:

```bash
mac-bench vision benchmark \
  --images-dir images \
  --profile brief=examples/profiles/brief.json \
  --profile detailed=examples/profiles/detailed.json
```

Profile files can override:

- `prompt_text`
- `temperature`
- `max_tokens`
- any additional top-level JSON fields supported by LM Studio's `chat/completions` endpoint

Note: LM Studio officially documents `reasoning` controls on the `responses` endpoint. The `vision` suite currently uses `chat/completions`, so reasoning-specific overrides should be treated as experimental unless you confirm support in your local LM Studio build.

## Example Doorbell Prompt

- [examples/prompts/doorbell-person.txt](examples/prompts/doorbell-person.txt)

This is the prompt used in the example benchmark linked from the main README.
