from __future__ import annotations

import importlib
import sys
from pathlib import Path

from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_cli_help() -> None:
    cli = importlib.import_module("mac_bench.cli")
    runner = CliRunner()

    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "vision" in result.stdout
    assert "doctor" in result.stdout


def test_vision_help() -> None:
    cli = importlib.import_module("mac_bench.cli")
    runner = CliRunner()

    result = runner.invoke(cli.app, ["vision", "--help"])

    assert result.exit_code == 0
    assert "benchmark" in result.stdout
    assert "render-report" in result.stdout
    assert "sanitize-images" in result.stdout
