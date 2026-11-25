"""Accuracy programme Phase 7: the frozen YOLO26m candidate as stored for the application (spec §9).

The candidate is stored by scripts/accuracy/promote_candidate.py as a versioned checkpoint with a model card under
models/trained/yolo26m_accuracy_candidate/<key>/. These tests check its identity and compatibility, that the
production YOLO26n checkpoint is untouched and stays the fallback, that a candidate whose card says "not promoted"
is never the active model, and that the candidate runs through the image and live pipelines at its own image size.
Checkpoints are only read.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import pytest

from src.compliance.compliance_analyzer import ComplianceAnalyzer, ComplianceRules
from src.detection.camera_processor import LiveFrameProcessor
from src.detection.detector import PPEDetector
from src.detection.image_processor import inspect_image
from src.detection.model_registry import ModelRegistry, load_validated
from src.events.event_store import EventStore
from src.utils.paths import PROJECT_ROOT, class_names, load_settings, source_dataset_dir

STORE = PROJECT_ROOT / "models" / "trained" / "yolo26m_accuracy_candidate"
CARDS = sorted(STORE.glob("*/model_card.json"))
YOLO26N = PROJECT_ROOT / "models" / "trained" / "best.pt"
N_SHA = "890dc61fd024b247eda19753a1787a5b9ac16ff0236b2f72e06ae6814c995b9b"
pytestmark = pytest.mark.skipif(not CARDS, reason="no stored accuracy-programme candidate")


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


@pytest.fixture(scope="module", params=CARDS, ids=lambda p: p.parent.name)
def card(request) -> dict:
    return json.loads(request.param.read_text())


def test_card_identity_matches_the_stored_checkpoint(card):
    ck = PROJECT_ROOT / card["checkpoint"]
    assert ck.exists() and sha(ck) == card["checkpoint_sha256"]
    assert {int(k): v for k, v in card["class_mapping"].items()} == class_names()
    assert card["architecture"] == "yolo26m" and card["image_size"] in (640, 768, 896)
    assert card["evaluation"]["dev"] is not None


def test_candidate_passes_registry_validation(card):
    _, ident = load_validated(PROJECT_ROOT / card["checkpoint"], architecture="yolo26m",
                              expected_sha256=card["checkpoint_sha256"])
    assert ident["architecture"] == "yolo26m" and ident["classes"] == len(class_names())


def test_production_yolo26n_is_untouched_and_stays_the_fallback(card):
    assert sha(YOLO26N) == N_SHA == card["rollback"]["sha256"]
    assert PROJECT_ROOT / card["checkpoint"] != YOLO26N
    assert ModelRegistry.from_settings(load_settings()).fallback == "yolo26n_baseline"


def test_card_records_the_unchanged_application_thresholds(card):
    s = load_settings()
    assert card["thresholds"]["detection_confidence"] == s["inference"]["confidence_threshold"]
    assert card["thresholds"]["nms_iou"] == s["inference"]["iou_threshold"]
    assert card["thresholds"]["compliance"] == s["compliance"]


def test_not_promoted_candidate_is_never_the_active_model(card, monkeypatch):
    monkeypatch.delenv("SITEGUARD_MODEL", raising=False)
    reg = ModelRegistry.from_settings(load_settings())
    if str(card.get("status", "")).startswith("not promoted"):
        assert card["model_key"] not in reg.entries
        assert reg.active != card["model_key"]
        assert card["registered_in_settings"] is False and card["active_default"] is False


def test_candidate_runs_image_and_live_pipelines_at_its_image_size(card, tmp_path):
    det = PPEDetector(weights=PROJECT_ROOT / card["checkpoint"], image_size=card["image_size"]).load()
    assert det.status == "explicit weights" and det.image_size == card["image_size"]
    img = cv2.imread(str(sorted((source_dataset_dir() / "images" / "val").glob("*.jpg"))[0]))
    analyzer = ComplianceAnalyzer(ComplianceRules.from_settings())
    assert inspect_image(img, det, analyzer) is not None
    proc = LiveFrameProcessor(det, analyzer, EventStore(tmp_path / "events.db"))
    out = proc.process(img)
    snap = proc.snapshot()
    proc.close()
    assert out.shape == img.shape and snap["errors"] == 0 and snap["frames_analysed"] == 1
    assert snap["inference_imgsz"] == card["image_size"]
