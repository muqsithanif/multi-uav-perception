#!/usr/bin/env python3
"""Download and safely extract official VisDrone2019-DET train/val archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "visdrone_sources.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--splits",
        nargs="+",
        choices=("train", "val"),
        default=("train", "val"),
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Print the resolved plan without downloading or writing files.",
    )
    return parser.parse_args()


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_config(config: dict[str, Any], splits: list[str] | tuple[str, ...]) -> None:
    required = {
        "dataset",
        "task",
        "official_repository",
        "raw_root",
        "manifest_path",
        "minimum_free_gib",
        "archives",
    }
    missing = sorted(required.difference(config))
    if missing:
        raise ValueError(f"Missing source config keys: {', '.join(missing)}")
    for split in splits:
        if split not in config["archives"]:
            raise ValueError(f"Split is absent from source config: {split}")
        split_config = config["archives"][split]
        split_required = {
            "filename",
            "google_drive_file_id",
            "extracted_directory",
            "expected_image_count",
        }
        split_missing = sorted(split_required.difference(split_config))
        if split_missing:
            raise ValueError(
                f"Missing {split} config keys: {', '.join(split_missing)}"
            )


def assert_free_space(root: Path, minimum_free_gib: float) -> int:
    root.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(root).free
    required_bytes = int(minimum_free_gib * 1024**3)
    if free_bytes < required_bytes:
        raise RuntimeError(
            f"Insufficient free space: {free_bytes} bytes available, "
            f"{required_bytes} required"
        )
    return free_bytes


def assert_safe_archive(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.infolist():
        member_path = (destination / member.filename).resolve()
        if not member_path.is_relative_to(destination):
            raise ValueError(f"Unsafe path in archive: {member.filename}")


def extract_archive(archive_path: Path, raw_root: Path, extracted_dir: Path) -> None:
    if extracted_dir.exists():
        return
    with zipfile.ZipFile(archive_path) as archive:
        assert_safe_archive(archive, raw_root)
        archive.extractall(raw_root)
    if not extracted_dir.is_dir():
        raise RuntimeError(
            f"Expected extracted directory is missing: {extracted_dir}"
        )


def validate_extracted_split(
    extracted_dir: Path, expected_image_count: int
) -> dict[str, Any]:
    images_dir = extracted_dir / "images"
    annotations_dir = extracted_dir / "annotations"
    if not images_dir.is_dir() or not annotations_dir.is_dir():
        raise RuntimeError(
            f"Expected images/ and annotations/ under {extracted_dir}"
        )
    images = sorted(images_dir.glob("*.jpg"))
    annotations = sorted(annotations_dir.glob("*.txt"))
    image_stems = {path.stem for path in images}
    annotation_stems = {path.stem for path in annotations}
    if len(images) != expected_image_count:
        raise RuntimeError(
            f"Image count mismatch for {extracted_dir.name}: "
            f"expected {expected_image_count}, found {len(images)}"
        )
    if image_stems != annotation_stems:
        missing_annotations = sorted(image_stems - annotation_stems)[:10]
        missing_images = sorted(annotation_stems - image_stems)[:10]
        raise RuntimeError(
            "Image/annotation pairing mismatch; "
            f"missing annotations={missing_annotations}, "
            f"missing images={missing_images}"
        )
    return {
        "extracted_directory": relative_path(extracted_dir),
        "image_count": len(images),
        "annotation_count": len(annotations),
        "pairing_complete": True,
    }


def download_archive(file_id: str, archive_path: Path) -> None:
    if archive_path.is_file():
        return
    try:
        import gdown
    except ImportError as exc:
        raise RuntimeError(
            "gdown is required; install requirements-day2.txt first"
        ) from exc

    part_path = archive_path.with_suffix(archive_path.suffix + ".part")
    downloaded = gdown.download(
        id=file_id,
        output=str(part_path),
        quiet=False,
        resume=True,
    )
    if downloaded is None or not part_path.is_file() or part_path.stat().st_size == 0:
        raise RuntimeError(f"Download failed for Google Drive file {file_id}")
    os.replace(part_path, archive_path)


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    validate_config(config, args.splits)
    raw_root = repo_path(config["raw_root"])
    manifest_path = repo_path(config["manifest_path"])

    plan = {
        "dataset": config["dataset"],
        "task": config["task"],
        "raw_root": relative_path(raw_root),
        "manifest_path": relative_path(manifest_path),
        "splits": {
            split: config["archives"][split] for split in args.splits
        },
    }
    if args.plan:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    free_bytes_before = assert_free_space(
        raw_root, float(config["minimum_free_gib"])
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "dataset": config["dataset"],
        "task": config["task"],
        "created_at_utc": datetime.now(UTC).isoformat(),
        "source_config": relative_path(config_path),
        "official_repository": config["official_repository"],
        "license_status": config.get("license_status"),
        "free_bytes_before": free_bytes_before,
        "splits": {},
    }

    for split in args.splits:
        split_config = config["archives"][split]
        archive_path = raw_root / split_config["filename"]
        extracted_dir = raw_root / split_config["extracted_directory"]
        download_archive(split_config["google_drive_file_id"], archive_path)
        archive_sha256 = sha256_file(archive_path)
        extract_archive(archive_path, raw_root, extracted_dir)
        split_record = validate_extracted_split(
            extracted_dir, int(split_config["expected_image_count"])
        )
        split_record.update(
            {
                "archive_path": relative_path(archive_path),
                "archive_size_bytes": archive_path.stat().st_size,
                "archive_sha256": archive_sha256,
                "google_drive_file_id": split_config["google_drive_file_id"],
            }
        )
        manifest["splits"][split] = split_record

    write_manifest(manifest_path, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise
