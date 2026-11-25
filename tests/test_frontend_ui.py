"""Frontend completion (2026-11-23): checks for the redesigned dashboard against the frontend specification §7.2.

All runs use a temporary events database (SITEGUARD_EVENTS_DB). Model-loading failures are simulated by patching
PPEDetector.load in this process only; no checkpoint, setting or real database is touched.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.detection.detector import ModelNotFoundError, PPEDetector
from src.detection.model_registry import ModelRegistry
from src.utils.paths import PROJECT_ROOT, SETTINGS_CONFIG, load_settings

APP = str(PROJECT_ROOT / "app.py")
PAGES = ["Overview", "Live Monitoring", "Image Inspection", "Video Inspection",
         "Safety Events", "Analytics", "Model Evaluation", "Settings / About"]
E3_KEY = "yolo26m_e3_896_v1"


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    import streamlit as st

    monkeypatch.delenv("SITEGUARD_MODEL", raising=False)
    monkeypatch.setenv("SITEGUARD_EVENTS_DB", str(tmp_path / "ui_test.db"))
    st.cache_resource.clear()
    yield tmp_path / "ui_test.db"
    st.cache_resource.clear()


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def open_page(page: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180).run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def texts(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [i.value for i in at.info]
    parts += [w.value for w in at.warning] + [e.value for e in at.error]
    parts += [m.value for m in at.sidebar.markdown] + [c.value for c in at.sidebar.caption] + [w.value for w in at.sidebar.warning]
    return "\n".join(str(p) for p in parts)


def test_settings_page_has_no_threshold_editing_and_writes_nothing():
    before = sha(SETTINGS_CONFIG)
    at = open_page("Settings / About")
    assert len(at.slider) == 0 and len(at.select_slider) == 0
    assert len(at.number_input) == 0 and len(at.multiselect) == 0
    assert not any("Save as defaults" in b.label for b in at.button)
    assert "read-only" in texts(at)
    assert sha(SETTINGS_CONFIG) == before


def test_model_selector_lists_only_registered_models_and_never_e3():
    at = open_page("Settings / About")
    selector = [s for s in at.selectbox if s.label == "Active model"][0]
    registered = list(ModelRegistry.from_settings(load_settings()).entries)
    # AppTest returns the formatted labels ("<key> - <description>"); the key is the part before " - ".
    assert [opt.split(" - ")[0] for opt in selector.options] == registered
    assert all(E3_KEY not in opt for opt in selector.options)
    assert E3_KEY not in registered


def test_yolo26n_is_the_active_model_by_default():
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception
    assert ModelRegistry.from_settings(load_settings()).active == "yolo26n_baseline"
    assert "yolo26n_baseline" in texts(at)
    assert "Model loaded" in texts(at)


def test_fallback_status_is_visible(monkeypatch):
    original = PPEDetector.load

    def fallback_load(self):
        original(self)
        self.status = "fallback"
        self.load_errors = ["simulated_active: checkpoint not found"]
        return self

    monkeypatch.setattr(PPEDetector, "load", fallback_load)
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception
    assert "Fallback model in use" in texts(at)
    assert any("fallback model is running" in w.value and "simulated_active" in w.value for w in at.sidebar.warning)


def test_model_loading_failure_blocks_inspection(monkeypatch):
    def broken_load(self):
        raise ModelNotFoundError("simulated: no checkpoint")

    monkeypatch.setattr(PPEDetector, "load", broken_load)
    at = open_page("Image Inspection")
    assert any("No usable model is available" in e.value for e in at.error)
    assert len(at.file_uploader) == 0  # the page stops before offering an upload
    assert "No usable model" in texts(at)


def test_model_evaluation_shows_e3_only_as_a_research_result():
    at = open_page("Model Evaluation")
    t = texts(at)
    assert "Not promoted" in t and "Not selectable" in t
    assert "160 images" in t and "same dataset" in t
    assert "accuracy" not in " ".join(m.label.lower() for m in at.metric)
    assert len(at.button) == 0  # no promotion or selection control on this page


def test_viewing_every_page_writes_nothing_to_the_events_database(temp_db):
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert temp_db.exists()
    before = sha(temp_db)
    for page in PAGES:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, (page, [e.message for e in at.exception])
    assert sha(temp_db) == before


def test_events_page_shows_readable_review_status_and_no_destructive_actions(temp_db, make_det):
    from src.compliance.compliance_analyzer import ComplianceAnalyzer, ComplianceRules
    from src.events.event_manager import EventManager
    from src.events.event_store import EventStore

    result = ComplianceAnalyzer(ComplianceRules(required_ppe=("helmet",))).analyze(
        [make_det("Person", 0.9, 100, 100, 200, 400), make_det("no_helmet", 0.9, 130, 90, 170, 130)])
    EventManager(EventStore(temp_db), "image", "synthetic.jpg", save_evidence=False).process(result, now=0.0)
    at = open_page("Safety Events")
    assert {"All events", "Pending review"} <= {m.label for m in at.metric}
    assert "Pending review" in at.dataframe[0].value.to_string()
    labels = [b.label for b in at.button]
    assert not any(word in label.lower() for label in labels for word in ("delete", "merge", "create"))


def test_analytics_and_events_show_honest_empty_states():
    at = open_page("Analytics")
    assert any("No data yet" in i.value for i in at.info)
    at.sidebar.radio[0].set_value("Safety Events").run()
    assert any("No events recorded yet" in i.value for i in at.info)


def test_leaving_the_live_page_closes_the_live_session(temp_db):
    at = open_page("Live Monitoring")
    assert "live_processor" in at.session_state
    processor = at.session_state["live_processor"]
    at.sidebar.radio[0].set_value("Overview").run()
    assert not at.exception
    assert "live_processor" not in at.session_state
    assert processor.closed  # a closed processor returns raw frames only: no stale boxes after leaving
