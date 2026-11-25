"""Model loading and safe switching (spec §12.3). Checkpoints are only read; hashes prove nothing was overwritten."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from src.detection.detector import ModelNotFoundError, PPEDetector
from src.utils.paths import PROJECT_ROOT, class_names

YOLO26N = PROJECT_ROOT / "models" / "trained" / "best.pt"
YOLO26M = PROJECT_ROOT / "experiments" / "yolo26m" / "training" / "yolo26m_e30_b4" / "weights" / "best.pt"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def frame():
    from src.utils.paths import source_dataset_dir
    import cv2

    return cv2.imread(str(sorted((source_dataset_dir() / "images" / "val").glob("*.jpg"))[0]))


@pytest.mark.parametrize("weights,arch", [(YOLO26N, "yolo26n.yaml"), (YOLO26M, "yolo26m.yaml")])
def test_checkpoint_loads_with_12_class_mapping(weights, arch):
    if not weights.exists():
        pytest.skip(f"{weights.relative_to(PROJECT_ROOT)} not trained yet")
    det = PPEDetector(weights=weights).load()
    assert det.model.task == "detect"
    assert det.model.model.yaml.get("yaml_file") == arch
    assert det.names == class_names() and len(det.names) == 12
    out = det.detect(frame())
    assert all(o.class_name in det.names.values() for o in out)


def test_missing_checkpoint_raises_clear_error(tmp_path):
    with pytest.raises(ModelNotFoundError, match="not found"):
        PPEDetector(weights=tmp_path / "nope.pt").load()


def test_invalid_checkpoint_raises_and_leaves_file_untouched(tmp_path):
    bad = tmp_path / "corrupt.pt"
    bad.write_bytes(b"this is not a torch checkpoint" * 100)
    before = sha(bad)
    with pytest.raises(Exception):
        PPEDetector(weights=bad).load()
    assert sha(bad) == before


def test_switching_models_never_writes_checkpoints():
    paths = [p for p in (YOLO26N, YOLO26M) if p.exists()]
    before = {p: sha(p) for p in paths}
    dets = [PPEDetector(weights=p).load() for p in paths]
    img = frame()
    for det in dets:
        det.detect(img)
    assert {p: sha(p) for p in paths} == before
    assert sha(YOLO26N) == "890dc61fd024b247eda19753a1787a5b9ac16ff0236b2f72e06ae6814c995b9b"  # production checkpoint
