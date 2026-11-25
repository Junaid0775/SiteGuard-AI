"""Model registry, validation, rollback and switching (accuracy programme Phase 7, spec §9).

Checkpoints are only read. The YOLO26m checkpoint of the engineering phase stands in for "a YOLO26m candidate";
temporary copies are used for the corrupt / wrong-class-mapping cases, so no real checkpoint is modified.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.compliance.compliance_analyzer import ComplianceAnalyzer, ComplianceRules
from src.detection.camera_processor import LiveFrameProcessor
from src.detection.detector import IncompatibleModelError, ModelNotFoundError, PPEDetector
from src.detection.image_processor import inspect_image
from src.detection.model_registry import ModelRegistry
from src.detection.video_processor import process_video
from src.events.event_store import EventStore, InspectionRecord
from src.utils.paths import PROJECT_ROOT, class_names, load_settings, source_dataset_dir

YOLO26N = PROJECT_ROOT / "models" / "trained" / "best.pt"
YOLO26M = PROJECT_ROOT / "experiments" / "yolo26m" / "training" / "yolo26m_e30_b4" / "weights" / "best.pt"
N_SHA = "890dc61fd024b247eda19753a1787a5b9ac16ff0236b2f72e06ae6814c995b9b"
pytestmark = pytest.mark.skipif(not (YOLO26N.exists() and YOLO26M.exists()), reason="checkpoints not available")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def settings_with(registry: dict, active: str, fallback: str | None = "yolo26n_baseline") -> dict:
    s = copy.deepcopy(load_settings())
    s["model"]["registry"] = registry
    s["model"]["active"] = active
    s["model"]["fallback"] = fallback
    return s


BASE = {"weights": str(YOLO26N), "architecture": "yolo26n", "image_size": 640}


def frame() -> np.ndarray:
    return cv2.imread(str(sorted((source_dataset_dir() / "images" / "val").glob("*.jpg"))[0]))


def analyzer() -> ComplianceAnalyzer:
    return ComplianceAnalyzer(ComplianceRules.from_settings())


def test_shipped_settings_keep_yolo26n_active_and_as_fallback():
    reg = ModelRegistry.from_settings(load_settings())
    assert reg.active == "yolo26n_baseline" and reg.fallback == "yolo26n_baseline"
    assert reg.get("yolo26n_baseline").weights == YOLO26N


def test_legacy_settings_without_registry_still_work():
    s = copy.deepcopy(load_settings())
    s["model"].pop("registry", None)
    s["model"].pop("active", None)
    s["model"].pop("fallback", None)
    reg = ModelRegistry.from_settings(s)
    assert list(reg.entries) == ["default"] and reg.get("default").weights == YOLO26N


def test_yolo26n_rollback_entry_loads_and_reports_identity():
    det = PPEDetector(settings=settings_with({"yolo26n_baseline": BASE}, "yolo26n_baseline")).load()
    info = det.info()
    assert det.status == "active" and det.model_key == "yolo26n_baseline"
    assert det.identity["sha256"] == N_SHA and det.identity["architecture"] == "yolo26n"
    assert info["image_size"] == 640 and info["model_key"] == "yolo26n_baseline"


def test_yolo26m_entry_loads_with_its_own_image_size():
    reg = {"yolo26n_baseline": BASE, "m": {"weights": str(YOLO26M), "architecture": "yolo26m", "image_size": 896}}
    det = PPEDetector(settings=settings_with(reg, "m")).load()
    assert det.status == "active" and det.identity["architecture"] == "yolo26m" and det.image_size == 896
    assert det.names == class_names()


def test_missing_active_checkpoint_falls_back_to_yolo26n(tmp_path):
    reg = {"yolo26n_baseline": BASE, "m": {"weights": str(tmp_path / "missing.pt"), "architecture": "yolo26m"}}
    det = PPEDetector(settings=settings_with(reg, "m")).load()
    assert det.status == "fallback" and det.model_key == "yolo26n_baseline"
    assert any("not found" in e for e in det.load_errors)


def test_corrupt_active_checkpoint_falls_back_and_is_left_untouched(tmp_path):
    bad = tmp_path / "corrupt.pt"
    bad.write_bytes(b"not a checkpoint" * 1000)
    before = sha(bad)
    reg = {"yolo26n_baseline": BASE, "m": {"weights": str(bad), "architecture": "yolo26m"}}
    det = PPEDetector(settings=settings_with(reg, "m")).load()
    assert det.status == "fallback" and "cannot be loaded" in det.load_errors[0]
    assert sha(bad) == before


def test_wrong_class_mapping_is_never_loaded(tmp_path):
    import torch

    ck = torch.load(YOLO26N, map_location="cpu", weights_only=False)
    m = ck.get("ema") or ck["model"]
    names = dict(m.names)
    names[6], names[7] = names[7], names[6]  # swap no_helmet / no_goggle
    m.names = names
    wrong = tmp_path / "swapped_classes.pt"
    torch.save(ck, wrong)
    with pytest.raises(IncompatibleModelError, match="class mapping"):
        PPEDetector(weights=wrong).load()
    reg = {"yolo26n_baseline": BASE, "bad": {"weights": str(wrong), "architecture": "yolo26n"}}
    det = PPEDetector(settings=settings_with(reg, "bad")).load()
    assert det.status == "fallback" and "class mapping" in det.load_errors[0]


def test_architecture_mismatch_is_rejected():
    reg = {"yolo26n_baseline": BASE, "m": {"weights": str(YOLO26N), "architecture": "yolo26m"}}
    det = PPEDetector(settings=settings_with(reg, "m")).load()
    assert det.status == "fallback" and "architecture" in det.load_errors[0]


def test_model_card_hash_mismatch_is_rejected(tmp_path):
    card = tmp_path / "card.json"
    card.write_text(json.dumps({"checkpoint_sha256": "0" * 64}))
    reg = {"yolo26n_baseline": BASE, "m": {"weights": str(YOLO26M), "architecture": "yolo26m", "card": str(card)}}
    det = PPEDetector(settings=settings_with(reg, "m")).load()
    assert det.status == "fallback" and "SHA-256" in det.load_errors[0]


def test_no_usable_model_raises_instead_of_loading_anything(tmp_path):
    reg = {"a": {"weights": str(tmp_path / "x.pt")}, "b": {"weights": str(tmp_path / "y.pt")}}
    with pytest.raises(ModelNotFoundError):
        PPEDetector(settings=settings_with(reg, "a", "b")).load()


def test_environment_variable_overrides_active_model(monkeypatch):
    monkeypatch.setenv("SITEGUARD_MODEL", "m")
    reg = {"yolo26n_baseline": BASE, "m": {"weights": str(YOLO26M), "architecture": "yolo26m"}}
    assert ModelRegistry.from_settings(settings_with(reg, "yolo26n_baseline")).active == "m"


def test_switching_models_starts_a_new_live_session_and_writes_nothing(tmp_path):
    before = {p: sha(p) for p in (YOLO26N, YOLO26M)}
    store = EventStore(tmp_path / "events.db")
    reg = {"yolo26n_baseline": BASE, "m": {"weights": str(YOLO26M), "architecture": "yolo26m", "image_size": 640}}
    img = frame()
    sessions = []
    for key in ("yolo26n_baseline", "m", "yolo26n_baseline"):
        det = PPEDetector(settings=settings_with(reg, key)).load()
        proc = LiveFrameProcessor(det, analyzer(), store)
        out = proc.process(img)
        snap = proc.snapshot()
        assert out.shape == img.shape and snap["frames_analysed"] == 1 and snap["errors"] == 0
        assert snap["inference_imgsz"] == det.image_size
        sessions.append(snap["session_id"])
        proc.close()
    assert len(set(sessions)) == 3
    assert {p: sha(p) for p in (YOLO26N, YOLO26M)} == before


def test_image_and_video_processing_with_the_yolo26m_entry(tmp_path):
    reg = {"yolo26n_baseline": BASE, "m": {"weights": str(YOLO26M), "architecture": "yolo26m", "image_size": 640}}
    det = PPEDetector(settings=settings_with(reg, "m")).load()
    result = inspect_image(frame(), det, analyzer())
    assert result is not None
    clip = PROJECT_ROOT / "data" / "test_media" / "test_site_clip.mp4"
    summary = process_video(clip, tmp_path / "out.mp4", det, analyzer(), max_frames=20)
    assert summary.frames_processed == 20 and summary.frames_not_analysed == 0 and (tmp_path / "out.mp4").exists()


def test_model_changes_never_reset_the_events_database(tmp_path):
    db = tmp_path / "events.db"
    store = EventStore(db)
    store.add_inspection(InspectionRecord("INSP-1", "2026-11-22T00:00:00", "image", "unit test", 1, 1))
    before = sha(db)
    reg = {"yolo26n_baseline": BASE, "m": {"weights": str(YOLO26M), "architecture": "yolo26m"}}
    for key in ("m", "yolo26n_baseline"):
        PPEDetector(settings=settings_with(reg, key)).load()
        EventStore(db)  # re-opening (as after a restart) must not recreate or clear tables
    assert sha(db) == before and len(EventStore(db).list_inspections()) == 1
