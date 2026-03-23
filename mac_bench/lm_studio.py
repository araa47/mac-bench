from __future__ import annotations

import json
import platform
import re
import subprocess
from pathlib import Path
from typing import Any

import httpx

from .entities import (
    BenchmarkError,
    DoctorCheck,
    EstimateResult,
    InstalledModel,
    LoadResult,
)

ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
FLOAT_GIB_PATTERN = re.compile(r"([0-9]+(?:\.[0-9]+)?) GiB")
LOAD_TIME_PATTERN = re.compile(r"Model loaded successfully in ([0-9]+(?:\.[0-9]+)?)s")
HARDWARE_MEMORY_PATTERN = re.compile(r"Memory: ([0-9]+) GB")


def run_command(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode != 0:
        raise BenchmarkError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n{output}"
        )
    return strip_ansi(output).strip()


def run_passthrough_command(command: list[str]) -> int:
    completed = subprocess.run(command, check=False)
    return completed.returncode


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


def lms_binary() -> Path:
    binary = Path.home() / ".lmstudio" / "bin" / "lms"
    if not binary.is_file():
        raise BenchmarkError(f"LM Studio CLI not found at {binary}")
    return binary


def detect_lms_version() -> str | None:
    candidates = (
        [str(lms_binary()), "version"],
        [str(lms_binary()), "--version"],
    )
    for command in candidates:
        try:
            output = run_command(command)
        except BenchmarkError:
            continue
        if output:
            return output.splitlines()[0].strip()
    return None


def list_installed_models() -> list[InstalledModel]:
    raw = run_command([str(lms_binary()), "ls", "--json"])
    payload = json.loads(raw)
    models: list[InstalledModel] = []
    for item in payload:
        if item.get("type") != "llm":
            continue
        variants = item.get("variants") or []
        models.append(
            InstalledModel(
                model_key=item["modelKey"],
                display_name=item["displayName"],
                format=item["format"],
                architecture=item.get("architecture"),
                publisher=item.get("publisher"),
                vision=bool(item.get("vision")),
                trained_for_tool_use=bool(item.get("trainedForToolUse")),
                params=item.get("paramsString"),
                size_bytes=item.get("sizeBytes"),
                variant=item.get("selectedVariant")
                or (variants[0] if variants else None),
                max_context_length=item.get("maxContextLength"),
            )
        )
    return models


def estimate_model(model_key: str) -> EstimateResult:
    raw_output = run_command(
        [str(lms_binary()), "load", model_key, "--estimate-only", "-y"]
    )
    return EstimateResult(
        estimated_gpu_memory_gib=parse_named_gib_value(
            raw_output, "Estimated GPU Memory"
        ),
        estimated_total_memory_gib=parse_named_gib_value(
            raw_output, "Estimated Total Memory"
        ),
        raw_output=raw_output,
    )


def load_model(model_key: str, identifier: str) -> LoadResult:
    raw_output = run_command(
        [str(lms_binary()), "load", model_key, "-y", "--identifier", identifier]
    )
    load_time_match = LOAD_TIME_PATTERN.search(raw_output)
    reported_memory_match = FLOAT_GIB_PATTERN.search(raw_output)
    return LoadResult(
        identifier=identifier,
        load_time_seconds=(
            float(load_time_match.group(1)) if load_time_match else None
        ),
        reported_memory_gib=(
            float(reported_memory_match.group(1)) if reported_memory_match else None
        ),
        raw_output=raw_output,
    )


def unload_all_models() -> None:
    run_command([str(lms_binary()), "unload", "--all"])


def download_model(
    model_name: str,
    *,
    include_mlx: bool = False,
    include_gguf: bool = False,
    yes: bool = True,
) -> int:
    command = [str(lms_binary()), "get", model_name]
    if include_mlx:
        command.append("--mlx")
    if include_gguf:
        command.append("--gguf")
    if yes:
        command.append("--yes")
    return run_passthrough_command(command)


def parse_named_gib_value(raw_output: str, label: str) -> float | None:
    for line in raw_output.splitlines():
        if line.startswith(label):
            match = FLOAT_GIB_PATTERN.search(line)
            if match:
                return float(match.group(1))
    return None


async def request_json(
    url: str,
    *,
    data: dict[str, Any] | None,
    method: str,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        try:
            response = await client.request(method, url, json=data)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BenchmarkError(
                f"HTTP {exc.response.status_code} from {url}: {exc.response.text}"
            ) from exc
        except httpx.HTTPError as exc:
            raise BenchmarkError(f"Could not reach {url}: {exc}") from exc
    payload = response.json()
    if not isinstance(payload, dict):
        raise BenchmarkError(f"Unexpected JSON payload from {url}: {payload}")
    return payload


async def fetch_loaded_model_ids(base_url: str) -> set[str]:
    payload = await request_json(
        f"{base_url.rstrip('/')}/v1/models",
        data=None,
        method="GET",
    )
    data = payload.get("data", [])
    if not isinstance(data, list):
        return set()
    model_ids: set[str] = set()
    for item in data:
        if isinstance(item, dict):
            identifier = item.get("id")
            if isinstance(identifier, str):
                model_ids.add(identifier)
    return model_ids


async def wait_for_loaded_model(
    base_url: str,
    identifier: str,
    timeout_seconds: int = 120,
) -> None:
    import asyncio

    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        loaded_models = await fetch_loaded_model_ids(base_url)
        if identifier in loaded_models:
            return
        await asyncio.sleep(1)
    raise BenchmarkError(f"Timed out waiting for model {identifier} to appear in API.")


def collect_machine_info() -> dict[str, object]:
    info: dict[str, object] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "system": platform.system(),
    }
    try:
        hardware = run_command(["system_profiler", "SPHardwareDataType"])
    except BenchmarkError:
        return info

    memory_match = HARDWARE_MEMORY_PATTERN.search(hardware)
    if memory_match:
        info["total_memory_gb"] = int(memory_match.group(1))
    chip_line = next(
        (
            line.strip()
            for line in hardware.splitlines()
            if line.strip().startswith("Chip:")
        ),
        None,
    )
    model_line = next(
        (
            line.strip()
            for line in hardware.splitlines()
            if line.strip().startswith("Model Name:")
        ),
        None,
    )
    if chip_line:
        info["chip"] = chip_line.split(":", maxsplit=1)[1].strip()
    if model_line:
        info["model_name"] = model_line.split(":", maxsplit=1)[1].strip()
    return info


async def run_doctor(base_url: str) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    system_name = platform.system()
    checks.append(
        DoctorCheck(
            name="Platform",
            status="ok" if system_name == "Darwin" else "warn",
            detail=f"Detected {system_name or 'unknown platform'}.",
            guidance=(
                None
                if system_name == "Darwin"
                else "The workflow is tuned for macOS and LM Studio on Apple Silicon."
            ),
        )
    )

    try:
        binary = lms_binary()
        version = detect_lms_version()
        checks.append(
            DoctorCheck(
                name="LM Studio CLI",
                status="ok",
                detail=(
                    f"Found at {binary}"
                    if version is None
                    else f"Found at {binary} ({version})"
                ),
            )
        )
    except BenchmarkError as exc:
        checks.append(
            DoctorCheck(
                name="LM Studio CLI",
                status="fail",
                detail=str(exc),
                guidance="Install LM Studio and make sure the bundled `lms` CLI is present.",
            )
        )
        return checks

    try:
        models = list_installed_models()
    except BenchmarkError as exc:
        checks.append(
            DoctorCheck(
                name="Installed models",
                status="fail",
                detail=str(exc),
                guidance="Verify `lms ls --json` works from this machine.",
            )
        )
        return checks

    vision_models = [model for model in models if model.vision]
    checks.append(
        DoctorCheck(
            name="Installed vision models",
            status="ok" if vision_models else "fail",
            detail=f"{len(vision_models)} vision model(s), {len(models)} total model(s).",
            guidance=(
                None
                if vision_models
                else "Download at least one vision-capable model in LM Studio."
            ),
        )
    )

    try:
        loaded_ids = await fetch_loaded_model_ids(base_url)
    except BenchmarkError as exc:
        checks.append(
            DoctorCheck(
                name="LM Studio local server",
                status="fail",
                detail=str(exc),
                guidance=(
                    "Open LM Studio and enable the local server, usually on "
                    "`http://127.0.0.1:1234`."
                ),
            )
        )
        return checks

    checks.append(
        DoctorCheck(
            name="LM Studio local server",
            status="ok",
            detail=f"Reachable at {base_url} with {len(loaded_ids)} loaded model(s).",
        )
    )
    return checks
