"""Hash manifests for protected assets (engineering phase, spec §2.3).

    .venv/bin/python scripts/engineering/hash_manifest.py create  <out_dir>
    .venv/bin/python scripts/engineering/hash_manifest.py verify  <manifest.csv>

`create` writes:
  protected_assets_manifest.csv  - checkpoints, configs, generated dataset configs, experiment artifacts, reports
  dataset_manifest.csv           - every file of the ORIGINAL dataset (read-only)
Each row: path, size_bytes, sha256, mtime_iso, role.

`verify` recomputes the hashes of a manifest and reports any changed or missing file.
Nothing is modified by this script.
"""

from __future__ import annotations

import csv
import hashlib
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
DATASET = PROJECT.parent / "construction-ppe"

ROLE_RULES = [
    ("models/trained/best.pt", "PRODUCTION checkpoint (YOLO26n) - never overwrite"),
    ("models/trained/", "trained model artefact"),
    ("models/pretrained/", "pretrained starting weights"),
    ("experiments/", "experiment artefact"),
    ("configs/", "configuration"),
    ("data/generated/", "generated dataset configuration"),
    ("data/", "project data/metadata"),
    (".streamlit/", "dashboard configuration"),
    ("docs/reports/", "report"),
    ("docs/", "documentation"),
    ("requirements.txt", "dependency specification"),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def role_for(rel: str) -> str:
    for prefix, role in ROLE_RULES:
        if rel == prefix or rel.startswith(prefix):
            return role
    return "other"


def rows_for(files, base: Path, role: str | None = None):
    for p in sorted(files):
        if p.name == ".DS_Store" or not p.is_file():
            continue
        st = p.stat()
        rel = p.relative_to(base).as_posix()
        yield {"path": rel, "size_bytes": st.st_size, "sha256": sha256(p),
               "mtime_iso": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
               "role": role or role_for(rel)}


def write_csv(path: Path, rows) -> int:
    rows = list(rows)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "size_bytes", "sha256", "mtime_iso", "role"])
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def create(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    protected = []
    for pattern in ("models/**/*", "configs/*", ".streamlit/*", "requirements.txt", "data/generated/**/*",
                    "data/viewpoint_metadata.csv", "data/dataset_baseline.sha256", "data/test_media/*",
                    "docs/reports/*.md", "docs/*.md"):
        protected += list(PROJECT.glob(pattern))
    # experiment artefacts (exclude the engineering-phase folder itself, which is being written now)
    protected += [p for p in PROJECT.glob("experiments/**/*") if "engineering_phase" not in p.parts]
    n1 = write_csv(out_dir / "protected_assets_manifest.csv", rows_for(set(protected), PROJECT))
    n2 = write_csv(out_dir / "dataset_manifest.csv", rows_for(DATASET.rglob("*"), DATASET.parent, "ORIGINAL dataset - read-only"))
    print(f"protected assets: {n1} files; original dataset: {n2} files -> {out_dir}")


def verify(manifest: Path) -> int:
    base = DATASET.parent if manifest.name.startswith("dataset") else PROJECT
    changed = missing = 0
    with open(manifest, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            p = base / row["path"]
            if not p.exists():
                missing += 1
                print("MISSING", row["path"])
            elif sha256(p) != row["sha256"]:
                changed += 1
                print("CHANGED", row["path"])
    print(f"verify {manifest.name}: changed={changed} missing={missing}")
    return changed + missing


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("create", "verify"):
        raise SystemExit(__doc__)
    if sys.argv[1] == "create":
        create(Path(sys.argv[2]))
    else:
        raise SystemExit(1 if verify(Path(sys.argv[2])) else 0)
