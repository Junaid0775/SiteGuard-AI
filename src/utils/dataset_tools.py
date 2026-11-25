"""Dataset validation and preparation for SiteGuard AI.

Run from the SiteGuard-AI folder:

    .venv/bin/python -m src.utils.dataset_tools

What it does:
1. Validates the ORIGINAL dataset (read-only): image/label pairs, label format,
   class IDs, unreadable images, duplicate images and the manifest checksums.
2. Builds a symlink mirror under data/dataset_mirror/ so Ultralytics can write
   its label cache files there instead of inside the original dataset.
3. Writes data/generated/dataset_resolved.yaml with absolute paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

from src.utils.paths import (
    GENERATED_DATA_DIR,
    class_names,
    mirror_dataset_dir,
    source_dataset_dir,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLITS = ("train", "val")


class LabelFormatError(ValueError):
    """Raised when a YOLO label line is malformed."""


@dataclass
class LabelRow:
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float


def parse_label_line(line: str, num_classes: int = 12) -> LabelRow:
    """Parse one YOLO label row: `class x_center y_center width height` (normalised 0-1)."""
    parts = line.split()
    if len(parts) != 5:
        raise LabelFormatError(f"expected 5 values, got {len(parts)}: {line!r}")
    try:
        class_id = int(parts[0])
        values = [float(v) for v in parts[1:]]
    except ValueError as exc:
        raise LabelFormatError(f"non-numeric value in {line!r}") from exc
    if not 0 <= class_id < num_classes:
        raise LabelFormatError(f"class id {class_id} outside 0..{num_classes - 1}")
    if not all(0.0 <= v <= 1.0 for v in values):
        raise LabelFormatError(f"coordinates must be in [0, 1]: {line!r}")
    if values[2] <= 0 or values[3] <= 0:
        raise LabelFormatError(f"box width/height must be positive: {line!r}")
    return LabelRow(class_id, *values)


def parse_label_file(path: Path, num_classes: int = 12) -> list[LabelRow]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(parse_label_line(line, num_classes))
    return rows


def list_images(folder: Path) -> list[Path]:
    return sorted(
        p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS and not p.name.startswith(".")
    )


def is_image_readable(path: Path) -> bool:
    """True if OpenCV can decode the file into a non-empty image."""
    import cv2

    img = cv2.imread(str(path))
    return img is not None and img.size > 0


@dataclass
class ValidationReport:
    split_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    images_without_labels: list[str] = field(default_factory=list)
    labels_without_images: list[str] = field(default_factory=list)
    invalid_label_rows: list[str] = field(default_factory=list)
    unreadable_images: list[str] = field(default_factory=list)
    duplicate_images: list[list[str]] = field(default_factory=list)
    manifest_mismatches: list[str] = field(default_factory=list)
    class_counts: dict[str, dict[int, int]] = field(default_factory=dict)
    total_annotations: int = 0

    @property
    def ok(self) -> bool:
        return not (
            self.images_without_labels
            or self.labels_without_images
            or self.invalid_label_rows
            or self.unreadable_images
            or self.manifest_mismatches
        )

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["ok"] = self.ok
        return d


def validate_dataset(root: Path | None = None, check_images: bool = True) -> ValidationReport:
    """Validate the dataset without modifying it."""
    root = root or source_dataset_dir()
    names = class_names()
    report = ValidationReport()
    hashes: dict[str, list[str]] = {}

    manifest = {}
    manifest_path = root / "manifest.jsonl"
    if manifest_path.exists():
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                manifest[entry["file"]] = entry

    for split in SPLITS:
        img_dir, lbl_dir = root / "images" / split, root / "labels" / split
        images = list_images(img_dir)
        labels = sorted(p for p in lbl_dir.glob("*.txt"))
        img_stems = {p.stem for p in images}
        lbl_stems = {p.stem for p in labels}
        report.split_counts[split] = {"images": len(images), "labels": len(labels)}
        report.images_without_labels += [f"{split}/{s}" for s in sorted(img_stems - lbl_stems)]
        report.labels_without_images += [f"{split}/{s}" for s in sorted(lbl_stems - img_stems)]

        counts: Counter = Counter()
        for lbl in labels:
            for i, line in enumerate(lbl.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    row = parse_label_line(line, len(names))
                    counts[row.class_id] += 1
                except LabelFormatError as exc:
                    report.invalid_label_rows.append(f"{split}/{lbl.name}:{i}: {exc}")
        report.class_counts[split] = dict(sorted(counts.items()))
        report.total_annotations += sum(counts.values())

        for img in images:
            digest = hashlib.sha256(img.read_bytes()).hexdigest()
            hashes.setdefault(digest, []).append(f"{split}/{img.name}")
            if manifest:
                entry = manifest.get(img.name)
                if entry is None or entry.get("sha256") != digest or entry.get("split") != split:
                    report.manifest_mismatches.append(f"{split}/{img.name}")
            if check_images and not is_image_readable(img):
                report.unreadable_images.append(f"{split}/{img.name}")

    report.duplicate_images = [v for v in hashes.values() if len(v) > 1]
    return report


def build_mirror(source: Path | None = None, mirror: Path | None = None) -> Path:
    """Create data/dataset_mirror/{images,labels}/{train,val}/ filled with symlinks.

    Symlinks point at the original files, so no image or label is copied or changed.
    Existing correct links are kept; the function can be re-run safely.
    """
    source = source or source_dataset_dir()
    mirror = mirror or mirror_dataset_dir()
    for kind in ("images", "labels"):
        for split in SPLITS:
            src_dir = source / kind / split
            dst_dir = mirror / kind / split
            dst_dir.mkdir(parents=True, exist_ok=True)
            for src in sorted(src_dir.iterdir()):
                if src.name.startswith("."):
                    continue
                dst = dst_dir / src.name
                if dst.is_symlink() and Path(os.readlink(dst)) == src:
                    continue
                if dst.exists() or dst.is_symlink():
                    raise FileExistsError(f"Unexpected file in mirror, refusing to overwrite: {dst}")
                dst.symlink_to(src)
    return mirror


def write_dataset_yaml(
    out_path: Path,
    train: str | Path,
    val: str | Path,
    test: str | Path | None = None,
    root: Path | None = None,
) -> Path:
    """Write an Ultralytics data YAML with an absolute `path` and the 12 class names."""
    root = root or mirror_dataset_dir()
    data = {"path": str(root), "train": str(train), "val": str(val)}
    if test is not None:
        data["test"] = str(test)
    data["names"] = class_names()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Generated by src/utils/dataset_tools.py - do not edit by hand.\n")
        yaml.safe_dump(data, f, sort_keys=False)
    return out_path


def write_image_list(out_path: Path, images: Iterable[Path]) -> Path:
    """Write a text file with one absolute image path per line (Ultralytics list format)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(f"{p}\n" for p in images), encoding="utf-8")
    return out_path


def prepare_default_dataset() -> Path:
    """Build the mirror and the standard train/val YAML. Returns the YAML path."""
    mirror = build_mirror()
    return write_dataset_yaml(GENERATED_DATA_DIR / "dataset_resolved.yaml", "images/train", "images/val", root=mirror)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and prepare the PPE dataset.")
    parser.add_argument("--skip-image-decode", action="store_true", help="skip decoding every image")
    args = parser.parse_args()

    print(f"Original dataset: {source_dataset_dir()}")
    report = validate_dataset(check_images=not args.skip_image_decode)
    summary = report.to_dict()
    print(json.dumps({k: v for k, v in summary.items() if k != "class_counts"}, indent=2))
    names = class_names()
    print("Class counts (train / val):")
    for cid, name in names.items():
        print(f"  {cid:2d} {name:10s} {report.class_counts['train'].get(cid, 0):5d} {report.class_counts['val'].get(cid, 0):5d}")
    print(f"Total annotations: {report.total_annotations}")

    out_json = GENERATED_DATA_DIR / "dataset_validation.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Validation report saved to {out_json}")

    if not report.ok:
        raise SystemExit("Dataset validation FAILED - fix the issues above before training.")
    yaml_path = prepare_default_dataset()
    print(f"Mirror ready at {mirror_dataset_dir()}")
    print(f"Resolved dataset YAML: {yaml_path}")


if __name__ == "__main__":
    main()
