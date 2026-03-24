from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .benchmark import BenchmarkRun


def serialize_run(run: BenchmarkRun) -> dict:
    """Convert a BenchmarkRun dataclass to a JSON-safe dict."""
    raw = asdict(run)
    raw["started_at"] = run.started_at.isoformat()
    raw["finished_at"] = run.finished_at.isoformat()
    return raw


def build_face_json_payload(run_data: dict) -> str:
    return json.dumps(run_data, indent=2, ensure_ascii=False, default=str)


def build_face_html_report(
    payload: dict,
    report_title: str = "mac-bench Face Recognition Benchmark",
) -> str:
    machine_raw = payload.get("machine", {})
    parts = [
        str(machine_raw.get("model_name", "")).strip(),
        str(machine_raw.get("chip", "")).strip(),
        (
            f"{machine_raw.get('total_memory_gb')} GB RAM"
            if machine_raw.get("total_memory_gb") is not None
            else ""
        ),
    ]
    machine_label = " / ".join(p for p in parts if p) or "Unknown machine"

    model_count = len(payload.get("model_results", []))
    num_pairs = payload.get("num_pairs", 0)

    payload_json = json.dumps(payload, ensure_ascii=False, default=str).replace(
        "</", "<\\/"
    )
    template = Template(_HTML_TEMPLATE)
    return template.safe_substitute(
        title=report_title,
        machine_label=machine_label,
        model_count=f"{model_count} models",
        num_pairs=num_pairs,
        payload_json=payload_json,
    )


def write_face_reports(
    output_dir: Path,
    report_name: str,
    run: BenchmarkRun,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    run_data = serialize_run(run)

    json_path = output_dir / f"{report_name}.json"
    html_path = output_dir / f"{report_name}.html"
    latest_json = output_dir / "latest.json"
    latest_html = output_dir / "latest.html"
    index_html = output_dir / "index.html"

    json_blob = build_face_json_payload(run_data)
    html_blob = build_face_html_report(run_data)

    json_path.write_text(json_blob + "\n", encoding="utf-8")
    latest_json.write_text(json_blob + "\n", encoding="utf-8")
    html_path.write_text(html_blob, encoding="utf-8")
    latest_html.write_text(html_blob, encoding="utf-8")
    index_html.write_text(html_blob, encoding="utf-8")
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")

    return {
        "json_path": json_path,
        "html_path": html_path,
        "latest_json_path": latest_json,
        "latest_html_path": latest_html,
        "index_html_path": index_html,
    }


_HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>$title</title>
  <meta name="description" content="Static benchmark dashboard for local face recognition models.">
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
      --correct-bg: rgba(35, 109, 106, 0.12);
      --correct-border: rgba(35, 109, 106, 0.3);
      --wrong-bg: rgba(166, 61, 64, 0.12);
      --wrong-border: rgba(166, 61, 64, 0.3);
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
        --correct-bg: rgba(82, 196, 190, 0.15);
        --correct-border: rgba(82, 196, 190, 0.35);
        --wrong-bg: rgba(224, 104, 104, 0.15);
        --wrong-border: rgba(224, 104, 104, 0.35);
      }
    }

    [data-theme="dark"] {
      --bg: #161413; --bg-strong: #221f1d;
      --panel: rgba(28, 26, 24, 0.92); --panel-strong: rgba(34, 32, 28, 0.95);
      --line: rgba(255, 255, 255, 0.1); --ink: #e4dfda; --muted: #968e86;
      --accent: #e0734f; --accent-soft: rgba(224, 115, 79, 0.14);
      --teal: #52c4be; --gold: #d4a83a; --danger: #e06868;
      --shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
      --hero-bg: linear-gradient(135deg, rgba(28, 26, 22, 0.98), rgba(32, 28, 24, 0.9));
      --hero-glow: rgba(224, 115, 79, 0.15);
      --card-bg: linear-gradient(180deg, rgba(36, 33, 30, 0.9), rgba(30, 28, 25, 0.76));
      --card-border: rgba(255, 255, 255, 0.07);
      --row-bg: rgba(36, 33, 30, 0.76); --row-hover: rgba(224, 115, 79, 0.06);
      --chip-bg: rgba(224, 115, 79, 0.1); --chip-border: rgba(224, 115, 79, 0.16);
      --pill-bg: rgba(36, 33, 30, 0.9); --pill-border: rgba(255, 255, 255, 0.08);
      --track-bg: rgba(255, 255, 255, 0.07); --track-border: rgba(255, 255, 255, 0.04);
      --table-bg: rgba(28, 26, 22, 0.8); --table-border: rgba(255, 255, 255, 0.08);
      --th-bg: rgba(22, 20, 18, 0.82);
      --empty-bg: rgba(28, 26, 22, 0.54); --empty-border: rgba(255, 255, 255, 0.14);
      --fact-bg: rgba(22, 20, 18, 0.72); --fact-border: rgba(255, 255, 255, 0.06);
      --details-bg: rgba(28, 26, 22, 0.82); --details-border: rgba(255, 255, 255, 0.08);
      --mini-bg: rgba(36, 33, 30, 0.78); --mini-border: rgba(255, 255, 255, 0.08);
      --rank-bg: linear-gradient(135deg, rgba(224, 115, 79, 0.2), rgba(82, 196, 190, 0.2));
      --grid-opacity: 0.03;
      --body-bg: linear-gradient(180deg, #121110 0%, var(--bg) 42%, #1a1816 100%);
      --body-glow-a: rgba(224, 115, 79, 0.1); --body-glow-b: rgba(82, 196, 190, 0.1);
      --chart-rect: rgba(28,26,22,0.42); --chart-grid: rgba(255,255,255,0.1);
      --chart-axis: rgba(255,255,255,0.5);
      --chart-bar-bg: rgba(255,255,255,0.07); --chart-bar-fg: rgba(224,115,79,0.85);
      --stable-badge-color: #6ee0da; --stable-badge-bg: rgba(82, 196, 190, 0.12);
      --stable-badge-border: rgba(82, 196, 190, 0.22);
      --partial-badge-color: #e8c460; --partial-badge-bg: rgba(212, 168, 58, 0.12);
      --partial-badge-border: rgba(212, 168, 58, 0.22);
      --failed-badge-color: #f09090; --failed-badge-bg: rgba(224, 104, 104, 0.12);
      --failed-badge-border: rgba(224, 104, 104, 0.22);
      --dot-stroke: rgba(255,255,255,0.4); --chart-label: var(--ink);
      --correct-bg: rgba(82, 196, 190, 0.15); --correct-border: rgba(82, 196, 190, 0.35);
      --wrong-bg: rgba(224, 104, 104, 0.15); --wrong-border: rgba(224, 104, 104, 0.35);
    }

    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }

    body {
      margin: 0; color: var(--ink); font-family: var(--body);
      background: radial-gradient(circle at top left, var(--body-glow-a), transparent 32%),
        radial-gradient(circle at top right, var(--body-glow-b), transparent 28%),
        var(--body-bg);
      min-height: 100vh;
    }
    body::before {
      content: ""; position: fixed; inset: 0; pointer-events: none;
      opacity: var(--grid-opacity);
      background-image: linear-gradient(rgba(31,26,23,0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(31,26,23,0.05) 1px, transparent 1px);
      background-size: 36px 36px;
      mask-image: radial-gradient(circle at center, black 55%, transparent 88%);
    }
    a { color: inherit; }

    .page { width: min(1240px, calc(100vw - 32px)); margin: 0 auto; padding: 28px 0 64px; position: relative; z-index: 1; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); backdrop-filter: blur(14px); }

    .hero { padding: 28px; position: relative; overflow: hidden; background: var(--hero-bg), var(--panel); }
    .hero::after {
      content: ""; position: absolute; width: 320px; height: 320px; right: -96px; top: -140px;
      border-radius: 50%; background: radial-gradient(circle at center, var(--hero-glow), transparent 70%);
      pointer-events: none;
    }

    .theme-toggle {
      position: absolute; top: 20px; right: 20px; z-index: 2;
      background: var(--pill-bg); border: 1px solid var(--pill-border);
      border-radius: 999px; padding: 8px 14px; cursor: pointer;
      font: 500 0.78rem/1 var(--mono); color: var(--muted); transition: background 0.2s, color 0.2s;
    }
    .theme-toggle:hover { color: var(--ink); background: var(--card-bg); }

    .eyebrow { font: 600 0.72rem/1.2 var(--mono); letter-spacing: 0.18em; text-transform: uppercase; color: var(--accent); margin-bottom: 14px; }
    .hero-title { font: 700 clamp(1.6rem, 3vw, 2.2rem)/1.15 var(--display); margin: 0 0 8px; }
    .hero-sub { font: 400 0.95rem/1.6 var(--body); color: var(--muted); margin: 0; max-width: 600px; }
    .hero-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
    .chip { display: inline-flex; align-items: center; gap: 6px; font: 500 0.78rem/1 var(--mono); background: var(--chip-bg); border: 1px solid var(--chip-border); border-radius: 999px; padding: 6px 14px; }

    .section { margin-top: 28px; }
    .section-title { font: 600 1.15rem/1.3 var(--display); margin: 0 0 16px; }

    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }
    .card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 18px; padding: 20px; backdrop-filter: blur(8px); }
    .card-label { font: 500 0.72rem/1.2 var(--mono); letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
    .card-value { font: 600 1.5rem/1.2 var(--display); color: var(--accent); }
    .card-detail { font: 400 0.82rem/1.4 var(--body); color: var(--muted); margin-top: 4px; }

    .rank-card { background: var(--rank-bg); border: 1px solid var(--card-border); border-radius: 18px; padding: 20px; backdrop-filter: blur(8px); }
    .rank-number { font: 700 2rem/1 var(--display); color: var(--accent); }
    .rank-name { font: 600 1rem/1.3 var(--body); margin-top: 4px; }
    .rank-meta { font: 400 0.82rem/1.4 var(--mono); color: var(--muted); margin-top: 4px; }

    .leaderboard-table { width: 100%; border-collapse: collapse; }
    .leaderboard-table th {
      font: 600 0.72rem/1.2 var(--mono); letter-spacing: 0.1em; text-transform: uppercase;
      color: var(--muted); text-align: left; padding: 10px 14px;
      background: var(--th-bg); border-bottom: 1px solid var(--table-border);
    }
    .leaderboard-table td {
      padding: 12px 14px; border-bottom: 1px solid var(--table-border);
      font: 400 0.88rem/1.4 var(--body); background: var(--row-bg);
    }
    .leaderboard-table tr:hover td { background: var(--row-hover); }
    .leaderboard-table td:first-child { font-family: var(--mono); font-weight: 500; font-size: 0.82rem; }
    .leaderboard-table .num { text-align: right; font-family: var(--mono); font-size: 0.82rem; }

    .badge {
      display: inline-flex; align-items: center; padding: 3px 10px; border-radius: 999px;
      font: 500 0.72rem/1.2 var(--mono); letter-spacing: 0.05em;
    }
    .badge.excellent { color: var(--stable-badge-color); background: var(--stable-badge-bg); border: 1px solid var(--stable-badge-border); }
    .badge.good { color: var(--partial-badge-color); background: var(--partial-badge-bg); border: 1px solid var(--partial-badge-border); }
    .badge.poor { color: var(--failed-badge-color); background: var(--failed-badge-bg); border: 1px solid var(--failed-badge-border); }

    .chart-section { background: var(--details-bg); border: 1px solid var(--details-border); border-radius: 18px; padding: 20px; margin-top: 14px; }
    .chart-section-title { font: 600 0.95rem/1.3 var(--display); margin: 0 0 14px; }

    .chart-bars { display: flex; flex-direction: column; gap: 8px; }
    .chart-bar-row { display: flex; align-items: center; gap: 12px; }
    .chart-bar-label { flex: 0 0 180px; font: 500 0.78rem/1.2 var(--mono); color: var(--ink); text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .chart-bar-track { flex: 1; height: 28px; background: var(--track-bg); border: 1px solid var(--track-border); border-radius: 6px; position: relative; overflow: hidden; }
    .chart-bar-fill { height: 100%; background: var(--chart-bar-fg); border-radius: 5px; transition: width 0.6s ease; min-width: 2px; }
    .chart-bar-value { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); font: 500 0.72rem/1 var(--mono); color: var(--ink); }

    .pair-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }
    .pair-card {
      background: var(--card-bg); border-radius: 14px; padding: 14px;
      border: 2px solid var(--card-border); transition: border-color 0.2s;
    }
    .pair-card.correct { border-color: var(--correct-border); background: var(--correct-bg); }
    .pair-card.wrong { border-color: var(--wrong-border); background: var(--wrong-bg); }
    .pair-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .pair-names { font: 500 0.82rem/1.3 var(--mono); }
    .pair-truth { font: 400 0.72rem/1 var(--mono); color: var(--muted); }
    .pair-result { font: 500 0.78rem/1.2 var(--body); margin-top: 6px; }
    .pair-score { font: 400 0.72rem/1 var(--mono); color: var(--muted); }

    .scatter-wrap { position: relative; width: 100%; max-width: 700px; margin: 0 auto; }
    .scatter-wrap svg { width: 100%; height: auto; }
    .scatter-legend { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; justify-content: center; }
    .scatter-legend-item { display: flex; align-items: center; gap: 6px; font: 400 0.78rem/1.2 var(--mono); color: var(--muted); }
    .scatter-legend-dot { width: 10px; height: 10px; border-radius: 50%; }

    .model-link { color: var(--accent); text-decoration: none; transition: opacity 0.15s; }
    .model-link:hover { opacity: 0.75; text-decoration: underline; }

    .model-detail { background: var(--details-bg); border: 1px solid var(--details-border); border-radius: 18px; padding: 20px; margin-top: 14px; }
    .model-detail-title { font: 600 1rem/1.3 var(--display); margin: 0 0 12px; }
    .fact-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; }
    .fact { background: var(--fact-bg); border: 1px solid var(--fact-border); border-radius: 10px; padding: 10px 14px; }
    .fact strong { display: block; font: 500 0.68rem/1.2 var(--mono); letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); margin-bottom: 4px; }
    .fact span { font: 500 0.92rem/1.3 var(--body); }

    .empty-state {
      text-align: center; padding: 32px; color: var(--muted);
      font: 400 0.88rem/1.5 var(--body);
      background: var(--empty-bg); border: 1px dashed var(--empty-border); border-radius: 14px;
    }

    .meta-pills { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
    .meta-pill { font: 400 0.78rem/1.2 var(--mono); color: var(--muted); background: var(--pill-bg); border: 1px solid var(--pill-border); border-radius: 999px; padding: 5px 12px; }

    .confusion-table { border-collapse: collapse; margin: 0 auto; }
    .confusion-table th, .confusion-table td {
      padding: 12px 20px; text-align: center; border: 1px solid var(--table-border);
      font: 400 0.88rem/1.4 var(--mono);
    }
    .confusion-table th { background: var(--th-bg); font-weight: 600; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.1em; }
    .confusion-table .tp { background: rgba(35, 109, 106, 0.15); font-weight: 600; }
    .confusion-table .tn { background: rgba(35, 109, 106, 0.08); }
    .confusion-table .fp { background: rgba(166, 61, 64, 0.12); }
    .confusion-table .fn { background: rgba(166, 61, 64, 0.08); }

    .nav-bar {
      position: sticky; top: 0; z-index: 100;
      background: var(--panel-strong); border-bottom: 1px solid var(--line);
      backdrop-filter: blur(16px); padding: 10px 0;
    }
    .nav-inner {
      width: min(1240px, calc(100vw - 32px)); margin: 0 auto;
      display: flex; align-items: center; gap: 16px;
    }
    .nav-back {
      display: inline-flex; align-items: center; gap: 6px;
      font: 500 0.82rem/1 var(--mono); color: var(--accent);
      text-decoration: none; padding: 6px 14px;
      background: var(--chip-bg); border: 1px solid var(--chip-border);
      border-radius: 999px; transition: background 0.2s;
    }
    .nav-back:hover { background: var(--accent-soft); }
    .nav-breadcrumb {
      font: 400 0.78rem/1.2 var(--mono); color: var(--muted);
    }
    .nav-breadcrumb a { color: var(--accent); text-decoration: none; }
    .nav-breadcrumb a:hover { text-decoration: underline; }

    @media (max-width: 700px) {
      .chart-bar-label { flex: 0 0 100px; font-size: 0.68rem; }
      .pair-grid { grid-template-columns: 1fr; }
      .cards { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <nav class="nav-bar">
    <div class="nav-inner">
      <a href="../" class="nav-back">&#8592; Home</a>
      <span class="nav-breadcrumb"><a href="../">mac-bench</a> / Face Recognition Benchmark</span>
    </div>
  </nav>
  <div class="page">
    <div class="panel hero">
      <button class="theme-toggle" onclick="toggleTheme()">Toggle theme</button>
      <div class="eyebrow">mac-bench</div>
      <h1 class="hero-title">Face Recognition Benchmark</h1>
      <p class="hero-sub">Comparing local face verification models on the LFW dataset. All models run on-device with no cloud APIs.</p>
      <div class="hero-chips" id="hero-chips"></div>
    </div>

    <div class="section">
      <div class="meta-pills" id="meta-pills"></div>
    </div>

    <div class="section">
      <h2 class="section-title">Leaderboard</h2>
      <div class="cards" id="summary-cards"></div>
    </div>

    <div class="section">
      <h2 class="section-title">Results Table</h2>
      <div class="panel" style="overflow-x:auto; border-radius:18px;">
        <table class="leaderboard-table" id="results-table">
          <thead><tr>
            <th>Model</th><th>Library</th><th class="num">Accuracy</th><th class="num">F1</th>
            <th class="num">Precision</th><th class="num">Recall</th>
            <th class="num">Avg Verify Time</th><th class="num">RAM MB</th>
          </tr></thead>
          <tbody id="results-tbody"></tbody>
        </table>
      </div>
    </div>

    <div class="section">
      <h2 class="section-title">Accuracy Comparison</h2>
      <div class="chart-section" id="accuracy-chart"></div>
    </div>

    <div class="section">
      <h2 class="section-title">Speed Comparison</h2>
      <div class="chart-section" id="speed-chart"></div>
    </div>

    <div class="section">
      <h2 class="section-title">RAM Usage</h2>
      <div class="chart-section" id="ram-chart"></div>
    </div>

    <div class="section">
      <h2 class="section-title">Accuracy vs Speed</h2>
      <div class="chart-section">
        <div class="scatter-wrap" id="scatter-chart"></div>
      </div>
    </div>

    <div class="section">
      <h2 class="section-title">Confusion Matrix (Best Model)</h2>
      <div class="chart-section" id="confusion-section"></div>
    </div>

    <div class="section">
      <h2 class="section-title">Model Details</h2>
      <div id="model-details"></div>
    </div>
  </div>

  <script id="benchmark-data" type="application/json">$payload_json</script>
  <script>
    var data = JSON.parse(document.getElementById("benchmark-data").textContent);
    var models = Array.isArray(data.model_results) ? data.model_results.slice() : [];

    function escapeHtml(s) {
      var d = document.createElement("div"); d.textContent = s; return d.innerHTML;
    }
    function byId(id) { return document.getElementById(id); }
    function pct(v) { return (v * 100).toFixed(1) + "%"; }
    function fmt(v, d) { return typeof v === "number" ? v.toFixed(d || 3) : "-"; }

    var MODEL_URLS = {
      "insightface": "https://github.com/deepinsight/insightface",
      "deepface": "https://github.com/serengil/deepface",
      "face_recognition": "https://github.com/ageitgey/face_recognition"
    };
    function modelUrl(m) {
      return MODEL_URLS[m.library] || "";
    }
    function linkedModelName(m) {
      var url = modelUrl(m);
      var name = escapeHtml(m.model_name);
      if (url) return '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener" class="model-link">' + name + '</a>';
      return name;
    }

    function accuracyBadge(acc) {
      if (acc >= 0.9) return '<span class="badge excellent">' + pct(acc) + '</span>';
      if (acc >= 0.7) return '<span class="badge good">' + pct(acc) + '</span>';
      return '<span class="badge poor">' + pct(acc) + '</span>';
    }

    // Sort: best accuracy first, then fastest
    models.sort(function(a, b) {
      var da = (a.error ? 0 : a.accuracy) || 0;
      var db = (b.error ? 0 : b.accuracy) || 0;
      if (db !== da) return db - da;
      return (a.avg_time_per_pair || 999) - (b.avg_time_per_pair || 999);
    });

    var validModels = models.filter(function(m) { return !m.error; });

    // Hero chips
    byId("hero-chips").innerHTML =
      '<span class="chip">' + escapeHtml(data.dataset_name || "LFW") + '</span>' +
      '<span class="chip">' + (data.num_pairs || 0) + ' pairs</span>' +
      '<span class="chip">' + models.length + ' models</span>';

    // Meta pills
    (function() {
      var pills = [];
      if (data.started_at) pills.push("Started " + new Date(data.started_at).toLocaleString());
      if (data.finished_at) pills.push("Finished " + new Date(data.finished_at).toLocaleString());
      var m = data.machine || {};
      if (m.model_name) pills.push(m.model_name);
      if (m.chip) pills.push(m.chip);
      if (m.total_memory_gb) pills.push(m.total_memory_gb + " GB RAM");
      byId("meta-pills").innerHTML = pills.map(function(p) {
        return '<span class="meta-pill">' + escapeHtml(p) + '</span>';
      }).join("");
    })();

    // Summary cards
    (function() {
      if (!validModels.length) {
        byId("summary-cards").innerHTML = '<div class="empty-state">No models completed the benchmark.</div>';
        return;
      }
      var best = validModels[0];
      var fastest = validModels.slice().sort(function(a,b) { return (a.avg_time_per_pair||999)-(b.avg_time_per_pair||999); })[0];
      var lightest = validModels.slice().sort(function(a,b) { return (a.ram_usage_mb||9999)-(b.ram_usage_mb||9999); })[0];

      byId("summary-cards").innerHTML =
        '<div class="rank-card"><div class="card-label">Most Accurate</div>' +
          '<div class="rank-name">' + linkedModelName(best) + '</div>' +
          '<div class="card-value">' + pct(best.accuracy) + '</div>' +
          '<div class="rank-meta">' + escapeHtml(best.library) + ' / ' + fmt(best.avg_time_per_pair) + 's per pair</div></div>' +
        '<div class="card"><div class="card-label">Fastest</div>' +
          '<div class="rank-name">' + linkedModelName(fastest) + '</div>' +
          '<div class="card-value">' + fmt(fastest.avg_time_per_pair) + 's</div>' +
          '<div class="card-detail">' + pct(fastest.accuracy) + ' accuracy</div></div>' +
        '<div class="card"><div class="card-label">Lightest</div>' +
          '<div class="rank-name">' + linkedModelName(lightest) + '</div>' +
          '<div class="card-value">' + fmt(lightest.ram_usage_mb, 0) + ' MB</div>' +
          '<div class="card-detail">' + pct(lightest.accuracy) + ' accuracy</div></div>' +
        '<div class="card"><div class="card-label">Models Tested</div>' +
          '<div class="card-value">' + models.length + '</div>' +
          '<div class="card-detail">' + validModels.length + ' completed</div></div>';
    })();

    // Results table
    (function() {
      byId("results-tbody").innerHTML = models.map(function(m, i) {
        if (m.error) {
          return '<tr><td>' + linkedModelName(m) + '</td><td>' + escapeHtml(m.library || "") +
            '</td><td colspan="6" style="color:var(--danger)">' + escapeHtml(m.error) + '</td></tr>';
        }
        return '<tr>' +
          '<td>' + linkedModelName(m) + '</td>' +
          '<td>' + escapeHtml(m.library) + '</td>' +
          '<td class="num">' + accuracyBadge(m.accuracy) + '</td>' +
          '<td class="num">' + fmt(m.f1_score) + '</td>' +
          '<td class="num">' + fmt(m.precision) + '</td>' +
          '<td class="num">' + fmt(m.recall) + '</td>' +
          '<td class="num">' + fmt(m.avg_time_per_pair) + 's</td>' +
          '<td class="num">' + fmt(m.ram_usage_mb, 0) + '</td>' +
          '</tr>';
      }).join("");
    })();

    // Bar chart helper
    function renderBars(targetId, items, valueFn, labelFn, formatFn) {
      if (!items.length) {
        byId(targetId).innerHTML = '<div class="empty-state">No data available.</div>';
        return;
      }
      var maxVal = Math.max.apply(null, items.map(valueFn));
      if (maxVal <= 0) maxVal = 1;
      byId(targetId).innerHTML = '<div class="chart-bars">' + items.map(function(item) {
        var val = valueFn(item);
        var w = Math.max(1, (val / maxVal) * 100);
        return '<div class="chart-bar-row">' +
          '<div class="chart-bar-label">' + escapeHtml(labelFn(item)) + '</div>' +
          '<div class="chart-bar-track"><div class="chart-bar-fill" style="width:' + w + '%"></div>' +
          '<span class="chart-bar-value">' + formatFn(val) + '</span></div></div>';
      }).join("") + '</div>';
    }

    // Accuracy chart
    renderBars("accuracy-chart", validModels,
      function(m) { return m.accuracy; },
      function(m) { return m.model_name; },
      function(v) { return pct(v); }
    );

    // Speed chart
    var speedSorted = validModels.slice().sort(function(a,b) { return (a.avg_time_per_pair||0)-(b.avg_time_per_pair||0); });
    renderBars("speed-chart", speedSorted,
      function(m) { return m.avg_time_per_pair; },
      function(m) { return m.model_name; },
      function(v) { return v.toFixed(3) + "s"; }
    );

    // RAM chart
    var ramSorted = validModels.slice().sort(function(a,b) { return (a.ram_usage_mb||0)-(b.ram_usage_mb||0); });
    renderBars("ram-chart", ramSorted,
      function(m) { return m.ram_usage_mb || 0; },
      function(m) { return m.model_name; },
      function(v) { return v.toFixed(0) + " MB"; }
    );

    // Scatter: accuracy vs speed
    (function() {
      var plottable = validModels.filter(function(m) { return typeof m.accuracy === "number" && typeof m.avg_time_per_pair === "number"; });
      if (!plottable.length) {
        byId("scatter-chart").innerHTML = '<div class="empty-state">No data for scatter plot.</div>';
        return;
      }
      var W = 700, H = 400, pad = {t:30, r:30, b:50, l:60};
      var pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
      var maxTime = Math.max.apply(null, plottable.map(function(m){return m.avg_time_per_pair;})) * 1.1;
      var minAcc = Math.min.apply(null, plottable.map(function(m){return m.accuracy;}));
      var accRange = 1.0 - Math.max(0, minAcc - 0.05);
      var accMin = Math.max(0, minAcc - 0.05);

      var colors = ["#b84f32","#236d6a","#a0771b","#a63d40","#5b7fbf","#8b5e3c","#6a5acd","#2e8b57"];
      var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" xmlns="http://www.w3.org/2000/svg">';
      svg += '<rect width="' + W + '" height="' + H + '" rx="12" fill="var(--chart-rect)"/>';

      // Grid
      for (var gi = 0; gi <= 4; gi++) {
        var gy = pad.t + (ph / 4) * gi;
        svg += '<line x1="' + pad.l + '" y1="' + gy + '" x2="' + (W-pad.r) + '" y2="' + gy + '" stroke="var(--chart-grid)" stroke-dasharray="4,4"/>';
        var gv = 1.0 - (gi / 4) * accRange;
        svg += '<text x="' + (pad.l-8) + '" y="' + (gy+4) + '" text-anchor="end" fill="var(--chart-axis)" font-family="var(--mono)" font-size="11">' + pct(gv) + '</text>';
      }
      for (var gj = 0; gj <= 4; gj++) {
        var gx = pad.l + (pw / 4) * gj;
        svg += '<line x1="' + gx + '" y1="' + pad.t + '" x2="' + gx + '" y2="' + (H-pad.b) + '" stroke="var(--chart-grid)" stroke-dasharray="4,4"/>';
        svg += '<text x="' + gx + '" y="' + (H-pad.b+18) + '" text-anchor="middle" fill="var(--chart-axis)" font-family="var(--mono)" font-size="11">' + (maxTime * gj / 4).toFixed(2) + 's</text>';
      }

      // Axis labels
      svg += '<text x="' + (W/2) + '" y="' + (H-5) + '" text-anchor="middle" fill="var(--chart-label)" font-family="var(--body)" font-size="13">Avg verify time (seconds)</text>';
      svg += '<text x="15" y="' + (H/2) + '" text-anchor="middle" fill="var(--chart-label)" font-family="var(--body)" font-size="13" transform="rotate(-90,15,' + (H/2) + ')">Accuracy</text>';

      var legendHtml = '<div class="scatter-legend">';
      plottable.forEach(function(m, idx) {
        var cx = pad.l + (m.avg_time_per_pair / maxTime) * pw;
        var cy = pad.t + ((1.0 - m.accuracy) / accRange) * ph;
        var c = colors[idx % colors.length];
        svg += '<circle cx="' + cx + '" cy="' + cy + '" r="8" fill="' + c + '" fill-opacity="0.7" stroke="var(--dot-stroke)" stroke-width="1.5"/>';
        legendHtml += '<span class="scatter-legend-item"><span class="scatter-legend-dot" style="background:' + c + '"></span>' + escapeHtml(m.model_name) + '</span>';
      });
      svg += '</svg>';
      legendHtml += '</div>';
      byId("scatter-chart").innerHTML = svg + legendHtml;
    })();

    // Confusion matrix for best model
    (function() {
      if (!validModels.length) {
        byId("confusion-section").innerHTML = '<div class="empty-state">No models to show confusion matrix.</div>';
        return;
      }
      var best = validModels[0];
      var pairs = Array.isArray(best.pair_results) ? best.pair_results : [];
      var tp = 0, tn = 0, fp = 0, fn = 0;
      pairs.forEach(function(p) {
        if (p.is_same_person && p.predicted_same) tp++;
        else if (!p.is_same_person && !p.predicted_same) tn++;
        else if (!p.is_same_person && p.predicted_same) fp++;
        else fn++;
      });
      byId("confusion-section").innerHTML =
        '<p style="text-align:center;color:var(--muted);font:400 0.82rem/1.4 var(--mono);margin-bottom:14px;">' + linkedModelName(best) + '</p>' +
        '<table class="confusion-table">' +
        '<tr><th></th><th>Predicted Same</th><th>Predicted Different</th></tr>' +
        '<tr><th>Actually Same</th><td class="tp">' + tp + '</td><td class="fn">' + fn + '</td></tr>' +
        '<tr><th>Actually Different</th><td class="fp">' + fp + '</td><td class="tn">' + tn + '</td></tr>' +
        '</table>';
    })();

    // Model details
    (function() {
      byId("model-details").innerHTML = models.map(function(m) {
        if (m.error) {
          return '<div class="model-detail"><div class="model-detail-title">' + linkedModelName(m) +
            '</div><div class="empty-state" style="text-align:left;">Error: ' + escapeHtml(m.error) + '</div></div>';
        }
        var facts = [
          {l:"Library", v: m.library},
          {l:"Accuracy", v: pct(m.accuracy)},
          {l:"F1 Score", v: fmt(m.f1_score)},
          {l:"Precision", v: fmt(m.precision)},
          {l:"Recall", v: fmt(m.recall)},
          {l:"Avg Verify Time", v: fmt(m.avg_time_per_pair) + "s"},
          {l:"Total Time", v: fmt(m.total_time, 1) + "s"},
          {l:"RAM Usage", v: fmt(m.ram_usage_mb, 0) + " MB"},
        ];
        var pairs = Array.isArray(m.pair_results) ? m.pair_results : [];
        var pairHtml = pairs.length ? '<div style="margin-top:14px;"><strong style="font:500 0.78rem/1.2 var(--mono);color:var(--muted);">Pair Results</strong>' +
          '<div class="pair-grid" style="margin-top:8px;">' + pairs.map(function(p) {
            var correct = p.is_same_person === p.predicted_same;
            var cls = correct ? "correct" : "wrong";
            var icon = correct ? "&#10003;" : "&#10007;";
            return '<div class="pair-card ' + cls + '">' +
              '<div class="pair-header"><span class="pair-names">' + escapeHtml(p.person_a) + ' vs ' + escapeHtml(p.person_b) + '</span>' +
              '<span class="pair-truth">' + (p.is_same_person ? "Same" : "Different") + '</span></div>' +
              '<div class="pair-result">' + icon + ' Predicted: ' + (p.predicted_same ? "Same" : "Different") +
              '</div><div class="pair-score">Similarity: ' + fmt(p.similarity_score) + '</div></div>';
          }).join("") + '</div></div>' : '';

        return '<div class="model-detail"><div class="model-detail-title">' + linkedModelName(m) + '</div>' +
          '<div class="fact-grid">' + facts.map(function(f) {
            return '<div class="fact"><strong>' + escapeHtml(f.l) + '</strong><span>' + f.v + '</span></div>';
          }).join("") + '</div>' + pairHtml + '</div>';
      }).join("");
    })();

    // Theme toggle
    function toggleTheme() {
      var html = document.documentElement;
      var current = html.getAttribute("data-theme");
      if (current === "dark") html.setAttribute("data-theme", "light");
      else if (current === "light") html.removeAttribute("data-theme");
      else html.setAttribute("data-theme", "dark");
    }
  </script>
</body>
</html>"""
