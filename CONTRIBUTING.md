# Contributing

1. Install dependencies: `uv sync --all-extras --dev`
2. Make your changes.
3. Ensure type checking passes: `uv run ty check`
4. Ensure pre-commit hooks pass: `uv run prek run --all-files`
5. Ensure tests pass with no regression in coverage: `uv run -m pytest --cov --cov-report=term-missing`
   A coverage report is also posted automatically on each PR.
6. Submit a PR.
