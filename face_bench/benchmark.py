"""Face recognition benchmark -- verifies same/different person pairs across
multiple local face-recognition libraries and model backends.

Every model adapter gracefully handles missing dependencies so the benchmark
can run with whatever subset of libraries happens to be installed.
"""

from __future__ import annotations

import platform
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .dataset import FaceDataset, FacePair

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class PairResult:
    pair_index: int
    person_a: str
    person_b: str
    is_same_person: bool  # ground truth
    predicted_same: bool
    similarity_score: float
    elapsed_seconds: float
    error: str | None


@dataclass
class ModelResult:
    model_name: str
    library: str
    accuracy: float  # 0-1
    precision: float
    recall: float
    f1_score: float
    avg_time_per_pair: float
    total_time: float
    ram_usage_mb: float
    pair_results: list[PairResult]
    error: str | None


@dataclass
class BenchmarkRun:
    started_at: datetime
    finished_at: datetime
    machine: dict[str, object]
    dataset_name: str
    num_pairs: int
    model_results: list[ModelResult]


# ---------------------------------------------------------------------------
# All known model identifiers
# ---------------------------------------------------------------------------

ALL_MODELS: list[dict[str, str]] = [
    {
        "name": "face_recognition",
        "library": "face_recognition",
        "install": "pip install face-recognition",
        "ram_estimate": "~100 MB",
    },
    {
        "name": "DeepFace-VGG-Face",
        "library": "deepface",
        "install": "pip install deepface tf-keras",
        "ram_estimate": "~580 MB",
    },
    {
        "name": "DeepFace-Facenet",
        "library": "deepface",
        "install": "pip install deepface tf-keras",
        "ram_estimate": "~100 MB",
    },
    {
        "name": "DeepFace-ArcFace",
        "library": "deepface",
        "install": "pip install deepface tf-keras",
        "ram_estimate": "~130 MB",
    },
    {
        "name": "DeepFace-SFace",
        "library": "deepface",
        "install": "pip install deepface opencv-python",
        "ram_estimate": "~10 MB",
    },
    {
        "name": "InsightFace-buffalo_l",
        "library": "insightface",
        "install": "pip install insightface onnxruntime",
        "ram_estimate": "~1.5 GB",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HARDWARE_MEMORY_PATTERN = re.compile(r"Memory: ([0-9]+) GB")


def _get_ram_bytes() -> int:
    """Return current max-resident-set size in bytes, or 0 on failure."""
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # macOS reports bytes; Linux reports kilobytes.
        if platform.system() == "Darwin":
            return usage
        return usage * 1024
    except Exception:  # noqa: BLE001
        pass
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]

        return psutil.Process().memory_info().rss
    except Exception:  # noqa: BLE001
        return 0


def _ram_mb() -> float:
    """Return current RAM usage in megabytes."""
    raw = _get_ram_bytes()
    return raw / (1024 * 1024) if raw else 0.0


def collect_machine_info() -> dict[str, object]:
    """Gather basic hardware / OS information (mirrors mac_bench pattern)."""
    info: dict[str, object] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }
    if platform.system() != "Darwin":
        return info
    try:
        completed = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            check=False,
            capture_output=True,
            text=True,
        )
        hardware = (completed.stdout or "") + (completed.stderr or "")
    except FileNotFoundError:
        return info

    memory_match = _HARDWARE_MEMORY_PATTERN.search(hardware)
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


def _compute_metrics(
    pair_results: list[PairResult],
) -> tuple[float, float, float, float]:
    """Return (accuracy, precision, recall, f1) from a list of pair results."""
    if not pair_results:
        return 0.0, 0.0, 0.0, 0.0

    tp = fp = tn = fn = 0
    for pr in pair_results:
        if pr.error is not None:
            # Treat errored pairs as incorrect predictions.
            if pr.is_same_person:
                fn += 1
            else:
                tn += 1
            continue
        if pr.is_same_person and pr.predicted_same:
            tp += 1
        elif pr.is_same_person and not pr.predicted_same:
            fn += 1
        elif not pr.is_same_person and pr.predicted_same:
            fp += 1
        else:
            tn += 1

    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return accuracy, precision, recall, f1


def _build_model_result(
    *,
    model_name: str,
    library: str,
    pair_results: list[PairResult],
    total_time: float,
    ram_before_mb: float,
    ram_after_mb: float,
    error: str | None = None,
) -> ModelResult:
    accuracy, precision, recall, f1 = _compute_metrics(pair_results)
    count = len(pair_results) or 1
    return ModelResult(
        model_name=model_name,
        library=library,
        accuracy=round(accuracy, 4),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1, 4),
        avg_time_per_pair=round(total_time / count, 4),
        total_time=round(total_time, 4),
        ram_usage_mb=round(max(ram_after_mb - ram_before_mb, 0.0), 2),
        pair_results=pair_results,
        error=error,
    )


def _error_model_result(model_name: str, library: str, error: str) -> ModelResult:
    return ModelResult(
        model_name=model_name,
        library=library,
        accuracy=0.0,
        precision=0.0,
        recall=0.0,
        f1_score=0.0,
        avg_time_per_pair=0.0,
        total_time=0.0,
        ram_usage_mb=0.0,
        pair_results=[],
        error=error,
    )


# ---------------------------------------------------------------------------
# Model adapters
# ---------------------------------------------------------------------------


def benchmark_face_recognition(pairs: list[FacePair]) -> ModelResult:
    """Benchmark the *face_recognition* library (dlib ResNet)."""
    model_name = "face_recognition"
    library = "face_recognition"

    try:
        import face_recognition  # type: ignore[import-untyped,unused-ignore]
    except ImportError:
        return _error_model_result(
            model_name, library, "face_recognition library is not installed."
        )

    ram_before = _ram_mb()
    pair_results: list[PairResult] = []
    total_start = time.perf_counter()

    for idx, pair in enumerate(pairs):
        start = time.perf_counter()
        try:
            img_a = face_recognition.load_image_file(str(pair.image_a_path))
            img_b = face_recognition.load_image_file(str(pair.image_b_path))
            encs_a = face_recognition.face_encodings(img_a)
            encs_b = face_recognition.face_encodings(img_b)
            if not encs_a or not encs_b:
                elapsed = time.perf_counter() - start
                pair_results.append(
                    PairResult(
                        pair_index=idx,
                        person_a=pair.person_a,
                        person_b=pair.person_b,
                        is_same_person=pair.is_same_person,
                        predicted_same=False,
                        similarity_score=0.0,
                        elapsed_seconds=round(elapsed, 4),
                        error="No face detected in one or both images.",
                    )
                )
                continue
            distance = face_recognition.face_distance([encs_a[0]], encs_b[0])[0]
            similarity = 1.0 - float(distance)
            predicted_same = float(distance) < 0.6
            elapsed = time.perf_counter() - start
            pair_results.append(
                PairResult(
                    pair_index=idx,
                    person_a=pair.person_a,
                    person_b=pair.person_b,
                    is_same_person=pair.is_same_person,
                    predicted_same=predicted_same,
                    similarity_score=round(similarity, 6),
                    elapsed_seconds=round(elapsed, 4),
                    error=None,
                )
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start
            pair_results.append(
                PairResult(
                    pair_index=idx,
                    person_a=pair.person_a,
                    person_b=pair.person_b,
                    is_same_person=pair.is_same_person,
                    predicted_same=False,
                    similarity_score=0.0,
                    elapsed_seconds=round(elapsed, 4),
                    error=str(exc),
                )
            )

    total_time = time.perf_counter() - total_start
    ram_after = _ram_mb()
    return _build_model_result(
        model_name=model_name,
        library=library,
        pair_results=pair_results,
        total_time=total_time,
        ram_before_mb=ram_before,
        ram_after_mb=ram_after,
    )


def benchmark_deepface(pairs: list[FacePair], model_name_backend: str) -> ModelResult:
    """Benchmark a DeepFace backend (VGG-Face, Facenet, ArcFace, SFace)."""
    display_name = f"DeepFace-{model_name_backend}"
    library = "deepface"

    try:
        from deepface import (
            DeepFace,  # type: ignore[import-untyped,unused-ignore]
        )
    except ImportError:
        return _error_model_result(
            display_name, library, "deepface library is not installed."
        )

    ram_before = _ram_mb()
    pair_results: list[PairResult] = []
    total_start = time.perf_counter()

    for idx, pair in enumerate(pairs):
        start = time.perf_counter()
        try:
            result = DeepFace.verify(
                img1_path=str(pair.image_a_path),
                img2_path=str(pair.image_b_path),
                model_name=model_name_backend,
                enforce_detection=False,
            )
            verified: bool = result.get("verified", False)
            distance: float = float(result.get("distance", 0.0))
            # Convert distance to a similarity score (lower distance = higher
            # similarity).  Threshold varies by model; DeepFace already applies
            # its own threshold for the ``verified`` flag.
            threshold: float = float(result.get("threshold", 1.0))
            similarity = max(1.0 - distance / threshold, 0.0) if threshold else 0.0
            elapsed = time.perf_counter() - start
            pair_results.append(
                PairResult(
                    pair_index=idx,
                    person_a=pair.person_a,
                    person_b=pair.person_b,
                    is_same_person=pair.is_same_person,
                    predicted_same=verified,
                    similarity_score=round(similarity, 6),
                    elapsed_seconds=round(elapsed, 4),
                    error=None,
                )
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start
            pair_results.append(
                PairResult(
                    pair_index=idx,
                    person_a=pair.person_a,
                    person_b=pair.person_b,
                    is_same_person=pair.is_same_person,
                    predicted_same=False,
                    similarity_score=0.0,
                    elapsed_seconds=round(elapsed, 4),
                    error=str(exc),
                )
            )

    total_time = time.perf_counter() - total_start
    ram_after = _ram_mb()
    return _build_model_result(
        model_name=display_name,
        library=library,
        pair_results=pair_results,
        total_time=total_time,
        ram_before_mb=ram_before,
        ram_after_mb=ram_after,
    )


def benchmark_insightface(pairs: list[FacePair]) -> ModelResult:
    """Benchmark InsightFace with the buffalo_l recognition model."""
    model_name = "InsightFace-buffalo_l"
    library = "insightface"

    try:
        import numpy as np  # type: ignore[import-untyped,unused-ignore]
        from insightface.app import (
            FaceAnalysis,  # type: ignore[import-untyped,unused-ignore]
        )
    except ImportError:
        return _error_model_result(
            model_name,
            library,
            "insightface or numpy is not installed.",
        )

    ram_before = _ram_mb()

    try:
        app = FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=-1, det_size=(640, 640))
    except Exception as exc:  # noqa: BLE001
        return _error_model_result(
            model_name, library, f"Failed to load buffalo_l model: {exc}"
        )

    ram_after_load = _ram_mb()

    pair_results: list[PairResult] = []
    total_start = time.perf_counter()

    for idx, pair in enumerate(pairs):
        start = time.perf_counter()
        try:
            import cv2  # type: ignore[import-untyped,unused-ignore]

            img_a = cv2.imread(str(pair.image_a_path))
            img_b = cv2.imread(str(pair.image_b_path))
            if img_a is None or img_b is None:
                elapsed = time.perf_counter() - start
                pair_results.append(
                    PairResult(
                        pair_index=idx,
                        person_a=pair.person_a,
                        person_b=pair.person_b,
                        is_same_person=pair.is_same_person,
                        predicted_same=False,
                        similarity_score=0.0,
                        elapsed_seconds=round(elapsed, 4),
                        error="Failed to read one or both images.",
                    )
                )
                continue

            faces_a = app.get(img_a)
            faces_b = app.get(img_b)
            if not faces_a or not faces_b:
                elapsed = time.perf_counter() - start
                pair_results.append(
                    PairResult(
                        pair_index=idx,
                        person_a=pair.person_a,
                        person_b=pair.person_b,
                        is_same_person=pair.is_same_person,
                        predicted_same=False,
                        similarity_score=0.0,
                        elapsed_seconds=round(elapsed, 4),
                        error="No face detected in one or both images.",
                    )
                )
                continue

            emb_a = faces_a[0].embedding
            emb_b = faces_b[0].embedding

            # Cosine similarity.
            norm_a = np.linalg.norm(emb_a)
            norm_b = np.linalg.norm(emb_b)
            if norm_a == 0 or norm_b == 0:
                cosine_sim = 0.0
            else:
                cosine_sim = float(np.dot(emb_a, emb_b) / (norm_a * norm_b))

            predicted_same = cosine_sim > 0.4
            elapsed = time.perf_counter() - start
            pair_results.append(
                PairResult(
                    pair_index=idx,
                    person_a=pair.person_a,
                    person_b=pair.person_b,
                    is_same_person=pair.is_same_person,
                    predicted_same=predicted_same,
                    similarity_score=round(cosine_sim, 6),
                    elapsed_seconds=round(elapsed, 4),
                    error=None,
                )
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start
            pair_results.append(
                PairResult(
                    pair_index=idx,
                    person_a=pair.person_a,
                    person_b=pair.person_b,
                    is_same_person=pair.is_same_person,
                    predicted_same=False,
                    similarity_score=0.0,
                    elapsed_seconds=round(elapsed, 4),
                    error=str(exc),
                )
            )

    total_time = time.perf_counter() - total_start
    ram_after = _ram_mb()
    return _build_model_result(
        model_name=model_name,
        library=library,
        pair_results=pair_results,
        total_time=total_time,
        ram_before_mb=ram_before,
        ram_after_mb=max(ram_after, ram_after_load),
    )


# ---------------------------------------------------------------------------
# Model registry -- maps canonical names to callables
# ---------------------------------------------------------------------------

_MODEL_DISPATCH: dict[str, Any] = {
    "face_recognition": lambda pairs: benchmark_face_recognition(pairs),
    "DeepFace-VGG-Face": lambda pairs: benchmark_deepface(pairs, "VGG-Face"),
    "DeepFace-Facenet": lambda pairs: benchmark_deepface(pairs, "Facenet"),
    "DeepFace-ArcFace": lambda pairs: benchmark_deepface(pairs, "ArcFace"),
    "DeepFace-SFace": lambda pairs: benchmark_deepface(pairs, "SFace"),
    "InsightFace-buffalo_l": lambda pairs: benchmark_insightface(pairs),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_available_models() -> list[dict[str, str]]:
    """Return list of models that can be run (libraries installed)."""
    available: list[dict[str, str]] = []

    ram_estimates = {
        "face_recognition": "~100 MB",
        "DeepFace-VGG-Face": "~580 MB",
        "DeepFace-Facenet": "~100 MB",
        "DeepFace-ArcFace": "~130 MB",
        "DeepFace-SFace": "~10 MB",
        "InsightFace-buffalo_l": "~1.5 GB",
    }

    # face_recognition
    try:
        import face_recognition  # type: ignore[import-untyped,unused-ignore]  # noqa: F401

        available.append(
            {
                "name": "face_recognition",
                "library": "face_recognition",
                "ram_estimate": ram_estimates["face_recognition"],
            }
        )
    except ImportError:
        pass

    # deepface
    try:
        from deepface import (  # type: ignore[import-untyped,unused-ignore]  # noqa: F401
            DeepFace,
        )

        for backend in ("VGG-Face", "Facenet", "ArcFace", "SFace"):
            name = f"DeepFace-{backend}"
            available.append(
                {
                    "name": name,
                    "library": "deepface",
                    "ram_estimate": ram_estimates[name],
                }
            )
    except ImportError:
        pass

    # insightface
    try:
        from insightface.app import (  # type: ignore[import-untyped,unused-ignore]  # noqa: F401
            FaceAnalysis,
        )

        available.append(
            {
                "name": "InsightFace-buffalo_l",
                "library": "insightface",
                "ram_estimate": ram_estimates["InsightFace-buffalo_l"],
            }
        )
    except ImportError:
        pass

    return available


def run_face_benchmark(
    dataset: FaceDataset,
    models: list[str] | None = None,
) -> BenchmarkRun:
    """Run the face verification benchmark across selected models.

    Parameters
    ----------
    dataset:
        A ``FaceDataset`` containing labelled face pairs.
    models:
        Optional list of model names to benchmark.  When *None*, every model
        whose library is installed will be benchmarked.  Unknown names are
        silently skipped.
    """
    started_at = datetime.now(UTC)
    machine = collect_machine_info()

    if models is None:
        available = get_available_models()
        selected_names = [m["name"] for m in available]
    else:
        selected_names = [m for m in models if m in _MODEL_DISPATCH]

    model_results: list[ModelResult] = []
    for name in selected_names:
        dispatch = _MODEL_DISPATCH.get(name)
        if dispatch is None:
            model_results.append(
                _error_model_result(name, "unknown", f"Unknown model: {name}")
            )
            continue
        print(f"  Benchmarking {name} ...", flush=True)
        result = dispatch(dataset.pairs)
        model_results.append(result)
        status = "OK" if result.error is None else f"ERROR: {result.error}"
        print(
            f"  {name}: accuracy={result.accuracy:.2%}  "
            f"F1={result.f1_score:.2%}  "
            f"avg={result.avg_time_per_pair:.3f}s/pair  "
            f"RAM~{result.ram_usage_mb:.0f} MB  "
            f"[{status}]",
            flush=True,
        )

    finished_at = datetime.now(UTC)
    return BenchmarkRun(
        started_at=started_at,
        finished_at=finished_at,
        machine=machine,
        dataset_name=dataset.name,
        num_pairs=len(dataset.pairs),
        model_results=model_results,
    )
