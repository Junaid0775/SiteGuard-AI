"""Fix 6 (camera-quality programme, 2026-11-23): tests and diagnostic scripts never write production evidence.

Regression for the incident in CAMERA-QUALITY-REPORT-001 §8: a replay diagnostic created LiveFrameProcessor(..., store=None),
whose EventManager still saved an evidence image into outputs/evidence/. These tests snapshot the production evidence
folder (names, sizes, modification times) and prove it is unchanged while events (with evidence) are really created.
Only dataset images are used; no webcam frame is read.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import cv2
import pytest

from src.events.event_manager import EventManager
from src.utils.diagnostics import production_evidence_dir, use_temporary_evidence_dir
from src.utils.paths import PROJECT_ROOT, source_dataset_dir

VIOLATION_IMAGE = "ultralytics-ppe-nov2026-022.jpg"  # val image with labelled no_helmet / no_vest workers


def snapshot(folder: Path) -> dict[str, tuple[int, int]]:
    return {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in folder.iterdir()} if folder.exists() else {}


def load_realtime_eval():
    path = PROJECT_ROOT / "scripts" / "engineering" / "realtime_eval.py"
    spec = importlib.util.spec_from_file_location("realtime_eval_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_tests_use_temporary_evidence_storage():
    configured = Path(os.environ["SITEGUARD_EVIDENCE_DIR"]).resolve()
    assert configured != production_evidence_dir()
    assert EventManager(None, "image", "x.jpg").evidence_dir.resolve() == configured


def test_diagnostic_replay_script_never_writes_production_evidence(detector, monkeypatch):
    production = production_evidence_dir()
    before = snapshot(production)
    monkeypatch.delenv("SITEGUARD_EVIDENCE_DIR", raising=False)  # as when the script is run on its own
    module = load_realtime_eval()  # its import-time guard must redirect evidence to a temporary folder
    redirected = Path(os.environ["SITEGUARD_EVIDENCE_DIR"]).resolve()
    assert redirected != production and module.DIAGNOSTIC_EVIDENCE_DIR.resolve() == redirected
    frame = cv2.imread(str(source_dataset_dir() / "images" / "val" / VIOLATION_IMAGE))
    # 10 fps pacing so every frame is analysed (latest-frame policy drops frames while the model warms up)
    perf, per_frame = module.paced_live_run(detector, [frame.copy() for _ in range(15)], [i / 10 for i in range(15)])
    assert perf["errors"] == 0 and perf["frames_analysed"] > 3
    written = list(redirected.glob("*.jpg"))
    assert written, "the replay created no event, so this test would not prove anything"
    assert snapshot(production) == before


def test_guard_never_points_at_production_storage(monkeypatch):
    monkeypatch.setenv("SITEGUARD_EVIDENCE_DIR", str(production_evidence_dir()))
    path = use_temporary_evidence_dir()
    assert path.resolve() != production_evidence_dir()
    assert Path(os.environ["SITEGUARD_EVIDENCE_DIR"]).resolve() == path.resolve()


def test_dashboard_image_flow_keeps_production_evidence_unchanged(detector, tmp_path, monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    from src.events.event_store import EventStore

    monkeypatch.setenv("SITEGUARD_EVENTS_DB", str(tmp_path / "isolation.db"))
    st.cache_resource.clear()
    production = production_evidence_dir()
    before = snapshot(production)
    img = source_dataset_dir() / "images" / "val" / VIOLATION_IMAGE
    at = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=300).run()
    at.sidebar.radio[0].set_value("Image Inspection").run()
    at.file_uploader[0].set_value((img.name, img.read_bytes(), "image/jpeg")).run()
    assert not at.exception
    events = EventStore(tmp_path / "isolation.db").list_events()
    assert len(events) > 0
    assert all(str(p).startswith(os.environ["SITEGUARD_EVIDENCE_DIR"]) for p in events["evidence_path"])
    assert snapshot(production) == before
    st.cache_resource.clear()
