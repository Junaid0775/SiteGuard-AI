"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.detection.detector import Detection  # noqa: E402
from src.utils.paths import load_settings, source_dataset_dir  # noqa: E402

TRAINED_WEIGHTS = PROJECT_ROOT / load_settings()["model"]["trained_weights"]


def det(name: str, conf: float, x1: float, y1: float, x2: float, y2: float) -> Detection:
    """Build a Detection by class name (class_id is not used by the compliance logic)."""
    ids = {"helmet": 0, "gloves": 1, "vest": 2, "boots": 3, "goggles": 4, "Person": 5, "no_helmet": 6,
           "no_goggle": 7, "no_gloves": 8, "no_boots": 9, "forklift": 10, "no_vest": 11}
    return Detection(ids[name], name, conf, x1, y1, x2, y2)


@pytest.fixture
def make_det():
    return det


@pytest.fixture(scope="session", autouse=True)
def isolate_evidence_storage(tmp_path_factory):
    """Fix 6 (2026-11-23): every EventManager created during the tests writes evidence to a temporary folder,
    never to production evidence storage (outputs/evidence/). Production files are neither written nor deleted."""
    import os

    previous = os.environ.get("SITEGUARD_EVIDENCE_DIR")
    os.environ["SITEGUARD_EVIDENCE_DIR"] = str(tmp_path_factory.mktemp("evidence"))
    yield
    if previous is None:
        os.environ.pop("SITEGUARD_EVIDENCE_DIR", None)
    else:
        os.environ["SITEGUARD_EVIDENCE_DIR"] = previous


@pytest.fixture(scope="session", autouse=True)
def remove_test_outputs():
    """Delete annotated videos that the dashboard tests write into outputs/videos/.

    Only files created during this test session are removed; existing files are kept. Evidence is no longer written
    to outputs/ during tests (isolate_evidence_storage), so outputs/evidence/ is not touched here any more.
    """
    from src.utils.paths import OUTPUTS_DIR

    folders = [OUTPUTS_DIR / "videos"]
    before = {p for f in folders if f.exists() for p in f.iterdir()}
    yield
    for f in folders:
        if f.exists():
            for p in f.iterdir():
                if p not in before and p.is_file():
                    p.unlink()


@pytest.fixture(scope="session")
def dataset_root() -> Path:
    root = source_dataset_dir()
    if not root.exists():
        pytest.skip(f"original dataset not found at {root}")
    return root


@pytest.fixture(scope="session")
def sample_val_image(dataset_root) -> Path:
    return sorted((dataset_root / "images" / "val").glob("*.jpg"))[0]


@pytest.fixture(scope="session")
def detector():
    if not TRAINED_WEIGHTS.exists():
        pytest.skip("trained model models/trained/best.pt not found - run training first")
    from src.detection.detector import PPEDetector

    return PPEDetector(weights=TRAINED_WEIGHTS).load()
