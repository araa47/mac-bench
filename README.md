# 🖥️ mac-bench

**Open benchmark suite for local AI models on Apple Silicon.**

I wanted to run vision and face recognition models locally on my Mac mini — no cloud, no subscriptions, no sending camera feeds to someone else's servers. Before buying extra hardware, I benchmarked a bunch of tiny models to see if any were actually usable. Turns out, a 1.2B-parameter model describes images in **0.36 seconds** using **1.2 GB of RAM**. You don't need a beefy GPU rig for this stuff.

`mac-bench` packages what I learned: reproducible benchmarks for **vision** (image description) and **face recognition** (verification), with fully static HTML dashboards you can host anywhere.

## 📊 Live Dashboards

- **[Homepage](https://araa47.github.io/mac-bench/)** — overview + links to both benchmarks
- **[Vision Benchmark](https://araa47.github.io/mac-bench/vision/)** — image description leaderboard
- **[Face Recognition Benchmark](https://araa47.github.io/mac-bench/face-recognition/)** — face verification leaderboard

## 🏆 Vision Benchmark — Top 5

**Machine**: Mac mini / Apple M4 Pro / 64 GB · 28 models tested · [Full results →](https://araa47.github.io/mac-bench/vision/)

| Rank | Model | RAM | Avg Latency | Tokens/s | Success |
|:---:|---|---:|---:|---:|:---:|
| 🥇 | [`smolvlm-500m-instruct`](https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct) | — | 0.211s | 78.8 | 5/5 |
| 🥈 | [`liquid/lfm2.5-1.2b`](https://huggingface.co/liquid/lfm2.5-1.2b) | 1.16 GiB | 0.359s | 80.9 | 5/5 |
| 🥉 | [`moondream-2b-2025-04-14`](https://huggingface.co/vikhyatk/moondream2) | 3.49 GiB | 1.476s | 48.1 | 5/5 |
| 4 | [`nvidia/nemotron-3-nano`](https://huggingface.co/nvidia/Nemotron-3-Nano) | 16.57 GiB | 2.601s | 61.1 | 5/5 |
| 5 | [`mistralai/ministral-3-3b`](https://huggingface.co/mistralai/Ministral-3b-instruct-2410) | 2.78 GiB | 2.684s | 15.1 | 5/5 |

## 🏆 Face Recognition — Top 5

**15 LFW verification pairs** (10 same-person + 5 different-person) · all local, CPU only · [Full results →](https://araa47.github.io/mac-bench/face-recognition/)

| Rank | Model | Library | Accuracy | F1 | Avg Verify Time | RAM |
|:---:|---|---|---:|---:|---:|---:|
| 🥇 | [InsightFace-buffalo_l](https://github.com/deepinsight/insightface) | insightface | 100.0% | 100.0% | 0.184s | 896 MB |
| 🥈 | [DeepFace-ArcFace](https://github.com/serengil/deepface) | deepface | 93.3% | 94.7% | 0.376s | 133 MB |
| 🥉 | [DeepFace-SFace](https://github.com/serengil/deepface) | deepface | 86.7% | 88.9% | 0.249s | 85 MB |
| 4 | [DeepFace-Facenet](https://github.com/serengil/deepface) | deepface | 80.0% | 82.3% | 0.343s | 199 MB |
| 5 | [DeepFace-VGG-Face](https://github.com/serengil/deepface) | deepface | 73.3% | 75.0% | 0.587s | 1706 MB |

## 🚀 Quick Start

### Vision Benchmark

```bash
uv sync --all-extras --dev
uv run python -m mac_bench doctor
uv run python -m mac_bench list-models --format gguf
uv run python -m mac_bench vision benchmark \
  --images-dir docs/images \
  --prompt-file examples/prompts/doorbell-person.txt \
  --preserve-image-names \
  --format gguf \
  --context-length 8192 \
  --load-settle-seconds 5 \
  --unload-settle-seconds 5 \
  --output-dir docs
```

### Face Recognition Benchmark

```bash
uv sync --all-extras --dev
uv pip install deepface tf-keras insightface onnxruntime opencv-python

uv run python -m face_bench download-dataset
uv run python -m face_bench benchmark --output-dir docs/face-recognition
```

Direct from GitHub:

```bash
uvx --from git+https://github.com/araa47/mac-bench mac-bench doctor
uvx --from git+https://github.com/araa47/mac-bench mac-bench list-models
```

More setup detail in [SETUP.md](SETUP.md).

## 📁 What Gets Tested

### Vision

Every model gets the same prompt, the same images, and the same LM Studio API path. Measures: load memory, per-image latency, token throughput, success rate, blank answers, crashes, and reasoning leaks.

- Images: [docs/images](docs/images) · [Credits](docs/images/CREDITS.md)
- Prompt: [examples/prompts/doorbell-person.txt](examples/prompts/doorbell-person.txt)

### Face Recognition

Every library gets the same 15 [LFW](http://vis-www.cs.umass.edu/lfw/) face-verification pairs. Measures: accuracy, precision, recall, F1, time per pair, and RAM.

- Images: [docs/face-recognition/images](docs/face-recognition/images) · [Credits](docs/face-recognition/images/CREDITS.md)

## 🌐 GitHub Pages

Both dashboards are fully static HTML. Publish from the `docs/` folder:

```bash
# Vision
uv run python -m mac_bench vision benchmark \
  --images-dir docs/images \
  --prompt-file examples/prompts/doorbell-person.txt \
  --preserve-image-names --format gguf \
  --context-length 8192 \
  --output-dir docs

# Face recognition
uv run python -m face_bench benchmark \
  --output-dir docs/face-recognition
```

Point GitHub Pages at the `docs` folder → `https://araa47.github.io/mac-bench/`

## 🛠️ Development

```bash
uv sync --all-extras --dev
uv run ty check
uv run prek run --all-files
uv run -m pytest
```
