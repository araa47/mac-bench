"""Download and prepare a small LFW subset for face-recognition benchmarking.

LFW (Labeled Faces in the Wild) is the standard academic benchmark for
unconstrained face verification.  This module downloads a curated subset of
~30 images and defines 15 verification pairs (10 same-person, 5 different-person)
so that a local model can be evaluated without fetching the full 13k-image archive.

Images are sourced via scikit-learn's LFW fetcher (handles mirrors automatically),
with a fallback to direct HTTP download from the UMass server.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FacePair:
    image_a_path: Path
    image_b_path: Path
    person_a: str
    person_b: str
    is_same_person: bool


@dataclass(slots=True)
class FaceDataset:
    pairs: list[FacePair]
    images_dir: Path
    name: str  # e.g. "lfw_subset"


# ---------------------------------------------------------------------------
# Curated pair definitions
# ---------------------------------------------------------------------------

# Each entry is (person_name, image_number).  We pick subjects known to have
# many photos in LFW so that low-numbered images are guaranteed to exist.

# 10 matched (same-person) pairs ----------------------------------------
_SAME_PAIRS: list[tuple[str, int, str, int]] = [
    ("George_W_Bush", 1, "George_W_Bush", 2),
    ("George_W_Bush", 3, "George_W_Bush", 4),
    ("Colin_Powell", 1, "Colin_Powell", 2),
    ("Colin_Powell", 3, "Colin_Powell", 4),
    ("Tony_Blair", 1, "Tony_Blair", 2),
    ("Tony_Blair", 3, "Tony_Blair", 4),
    ("Donald_Rumsfeld", 1, "Donald_Rumsfeld", 2),
    ("Gerhard_Schroeder", 1, "Gerhard_Schroeder", 2),
    ("Hugo_Chavez", 1, "Hugo_Chavez", 2),
    ("Ariel_Sharon", 1, "Ariel_Sharon", 2),
]

# 5 mismatched (different-person) pairs ---------------------------------
_DIFF_PAIRS: list[tuple[str, int, str, int]] = [
    ("George_W_Bush", 5, "Colin_Powell", 5),
    ("Tony_Blair", 5, "Gerhard_Schroeder", 3),
    ("Donald_Rumsfeld", 3, "Hugo_Chavez", 3),
    ("Ariel_Sharon", 3, "George_W_Bush", 6),
    ("Colin_Powell", 6, "Tony_Blair", 6),
]

LFW_DIRECT_URL = "http://vis-www.cs.umass.edu/lfw/images"


def _image_filename(person: str, number: int) -> str:
    return f"{person}_{number:04d}.jpg"


def _collect_unique_images() -> list[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    images: list[tuple[str, int]] = []
    for pairs in (_SAME_PAIRS, _DIFF_PAIRS):
        for person_a, num_a, person_b, num_b in pairs:
            for person, num in ((person_a, num_a), (person_b, num_b)):
                key = (person, num)
                if key not in seen:
                    seen.add(key)
                    images.append(key)
    return images


def _write_pairs_json(pairs_path: Path, dataset: FaceDataset) -> None:
    records: list[dict[str, object]] = []
    for pair in dataset.pairs:
        records.append(
            {
                "image_a": str(pair.image_a_path),
                "image_b": str(pair.image_b_path),
                "person_a": pair.person_a,
                "person_b": pair.person_b,
                "is_same_person": pair.is_same_person,
            }
        )
    pairs_path.write_text(json.dumps(records, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Download strategies
# ---------------------------------------------------------------------------


def _ensure_sklearn_lfw() -> Path | None:
    """Use sklearn to fetch LFW (handles mirrors). Return the lfw_funneled dir."""
    try:
        from sklearn.datasets import (
            fetch_lfw_people,  # type: ignore[import-untyped,unused-ignore]
        )

        # This triggers the full dataset download if not already cached.
        # min_faces_per_person=1 ensures all subjects are fetched.
        print("Using scikit-learn to fetch LFW dataset (cached after first run)...")
        fetch_lfw_people(min_faces_per_person=1, resize=1.0)

        # sklearn caches to ~/scikit_learn_data/lfw_home/lfw_funneled/
        sklearn_dir = Path.home() / "scikit_learn_data" / "lfw_home" / "lfw_funneled"
        if sklearn_dir.is_dir():
            return sklearn_dir
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        print(f"  sklearn fetch failed: {exc}")
    return None


def _download_via_httpx(
    images_dir: Path,
    unique_images: list[tuple[str, int]],
) -> None:
    """Fallback: download individual images directly from UMass server."""
    import httpx

    total = len(unique_images)
    print(f"Downloading {total} LFW images via HTTP ...")

    with httpx.Client(timeout=30.0) as client:
        for idx, (person, number) in enumerate(unique_images, 1):
            filename = _image_filename(person, number)
            dest = images_dir / person / filename
            if dest.exists() and dest.stat().st_size > 0:
                print(f"  [{idx}/{total}] {filename} (cached)")
                continue
            url = f"{LFW_DIRECT_URL}/{person}/{filename}"
            print(f"  [{idx}/{total}] {filename} ... ", end="", flush=True)
            dest.parent.mkdir(parents=True, exist_ok=True)
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()
            dest.write_bytes(response.content)
            print("ok")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def download_dataset(output_dir: Path) -> FaceDataset:
    """Download the LFW subset and return a :class:`FaceDataset`.

    Strategy: try sklearn first (handles mirrors, caching). If sklearn is not
    installed, fall back to direct HTTP download from UMass.
    """
    images_dir = output_dir / "lfw_subset"
    images_dir.mkdir(parents=True, exist_ok=True)

    unique_images = _collect_unique_images()
    total = len(unique_images)

    # Check if all images already exist locally
    all_present = all(
        (images_dir / person / _image_filename(person, number)).exists()
        for person, number in unique_images
    )

    if all_present:
        print(f"All {total} images already present in {images_dir}")
    else:
        # Strategy 1: try sklearn (handles mirrors and caching)
        sklearn_dir = _ensure_sklearn_lfw()
        if sklearn_dir is not None:
            print(f"Copying {total} images from sklearn cache ...")
            for idx, (person, number) in enumerate(unique_images, 1):
                filename = _image_filename(person, number)
                src = sklearn_dir / person / filename
                dest = images_dir / person / filename
                if dest.exists() and dest.stat().st_size > 0:
                    print(f"  [{idx}/{total}] {filename} (cached)")
                    continue
                if src.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    print(f"  [{idx}/{total}] {filename} (copied)")
                else:
                    print(f"  [{idx}/{total}] {filename} NOT FOUND in sklearn cache")
        else:
            # Strategy 2: direct HTTP download
            _download_via_httpx(images_dir, unique_images)

    # Build FacePair objects ------------------------------------------------
    pairs: list[FacePair] = []

    for person_a, num_a, person_b, num_b in _SAME_PAIRS:
        pairs.append(
            FacePair(
                image_a_path=images_dir / person_a / _image_filename(person_a, num_a),
                image_b_path=images_dir / person_b / _image_filename(person_b, num_b),
                person_a=person_a,
                person_b=person_b,
                is_same_person=True,
            )
        )

    for person_a, num_a, person_b, num_b in _DIFF_PAIRS:
        pairs.append(
            FacePair(
                image_a_path=images_dir / person_a / _image_filename(person_a, num_a),
                image_b_path=images_dir / person_b / _image_filename(person_b, num_b),
                person_a=person_a,
                person_b=person_b,
                is_same_person=False,
            )
        )

    dataset = FaceDataset(pairs=pairs, images_dir=images_dir, name="lfw_subset")

    # Persist pairs.json for reproducibility --------------------------------
    pairs_path = images_dir / "pairs.json"
    _write_pairs_json(pairs_path, dataset)
    print(f"Wrote pair definitions to {pairs_path}")

    print(
        f"Dataset ready: {len(pairs)} pairs "
        f"({sum(p.is_same_person for p in pairs)} same, "
        f"{sum(not p.is_same_person for p in pairs)} different)"
    )

    return dataset


def load_dataset(output_dir: Path) -> FaceDataset:
    """Load a previously downloaded dataset from *output_dir*."""
    images_dir = output_dir / "lfw_subset"
    pairs_path = images_dir / "pairs.json"
    if not pairs_path.exists():
        raise FileNotFoundError(
            f"pairs.json not found in {images_dir}. Run download_dataset first."
        )

    records = json.loads(pairs_path.read_text(encoding="utf-8"))
    pairs: list[FacePair] = []
    for rec in records:
        pairs.append(
            FacePair(
                image_a_path=Path(rec["image_a"]),
                image_b_path=Path(rec["image_b"]),
                person_a=rec["person_a"],
                person_b=rec["person_b"],
                is_same_person=rec["is_same_person"],
            )
        )
    return FaceDataset(pairs=pairs, images_dir=images_dir, name="lfw_subset")


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
    ds = download_dataset(dest)
    for pair in ds.pairs:
        tag = "SAME" if pair.is_same_person else "DIFF"
        print(f"  {tag}: {pair.image_a_path.name} <-> {pair.image_b_path.name}")
