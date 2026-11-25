"""Smoke-test every dashboard page with Streamlit's headless AppTest runner.

The browser webcam itself cannot be exercised here (it needs a real browser and
camera permission); this only checks that each page renders without errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PAGES = ["Overview", "Live Monitoring", "Image Inspection", "Video Inspection",
         "Safety Events", "Analytics", "Model Evaluation", "Settings / About"]


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    import streamlit as st

    monkeypatch.setenv("SITEGUARD_EVENTS_DB", str(tmp_path / "app_test.db"))
    st.cache_resource.clear()  # make get_store() open the temporary database
    yield tmp_path / "app_test.db"
    st.cache_resource.clear()


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page):
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, [e.message for e in at.exception]
    assert any(page.split(" /")[0] in t.value for t in at.title), f"title for {page} not shown"


def test_live_page_handles_missing_webrtc_runtime():
    # AppTest has no real server runtime, so streamlit-webrtc cannot start here.
    # The page must report this clearly instead of crashing.
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.sidebar.radio[0].set_value("Live Monitoring").run()
    assert not at.exception
    assert any("live camera component could not start" in e.value for e in at.error)


def test_overview_shows_empty_state_without_data():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert any("No safety events recorded yet" in i.value for i in at.info)


def _open(page: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=300).run()
    at.sidebar.radio[0].set_value(page).run()
    return at


def test_image_upload_flow_records_events_and_csv(detector, temp_db):
    from src.events.event_store import EventStore
    from src.utils.paths import source_dataset_dir

    # A crowded close-up validation image that contains explicit missing-PPE labels.
    img = source_dataset_dir() / "images" / "val" / "ultralytics-ppe-nov2026-022.jpg"
    at = _open("Image Inspection")
    at.file_uploader[0].set_value((img.name, img.read_bytes(), "image/jpeg")).run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.get("image")) == 2  # original + annotated
    labels = [m.label for m in at.metric]
    assert {"Potential violation", "Compliant evidence", "Uncertain"} <= set(labels)
    n_events = EventStore(temp_db).count_events()
    assert n_events > 0, "this image contains labelled no_helmet/no_vest workers"
    # Rerunning the page with the same upload must not record the events again.
    at.run()
    assert EventStore(temp_db).count_events() == n_events
    # Safety Events page lists them and offers the CSV download.
    at.sidebar.radio[0].set_value("Safety Events").run()
    assert not at.exception
    assert any(f"{n_events} of {n_events} events" in c.value for c in at.caption)
    assert len(EventStore(temp_db).list_inspections()) == 1


def test_invalid_image_upload_shows_error(detector):
    at = _open("Image Inspection")
    at.file_uploader[0].set_value(("broken.jpg", b"not an image at all" * 20, "image/jpeg")).run()
    assert not at.exception
    assert any("Cannot read broken.jpg" in e.value for e in at.error)


def test_video_upload_flow(detector, temp_db):
    from src.events.event_store import EventStore
    from src.utils.paths import DATA_DIR

    clip = DATA_DIR / "test_media" / "test_site_clip.mp4"
    if not clip.exists():
        pytest.skip("run scripts/make_test_video.py first")
    at = _open("Video Inspection")
    at.file_uploader[0].set_value((clip.name, clip.read_bytes(), "video/mp4")).run()
    at.number_input[1].set_value(60).run()  # read only 60 frames to keep the test short
    at.button[0].click().run()
    assert not at.exception, [e.message for e in at.exception]
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Frames read"] == "60"
    # R1 (REPORT-012): offline video now analyses every frame by default (was every 5th, with stale boxes in between).
    assert metrics["Frames analysed"] == "60"
    assert int(metrics["Events recorded"]) == EventStore(temp_db).count_events()
    assert len(EventStore(temp_db).list_inspections()) == 1


def test_review_status_update_from_events_page(detector, temp_db, make_det):
    from src.compliance.compliance_analyzer import ComplianceAnalyzer, ComplianceRules
    from src.events.event_manager import EventManager
    from src.events.event_store import EventStore

    store = EventStore(temp_db)
    rules = ComplianceRules(required_ppe=("helmet",))
    result = ComplianceAnalyzer(rules).analyze([make_det("Person", 0.9, 100, 100, 200, 400), make_det("no_helmet", 0.9, 130, 90, 170, 130)])
    event = EventManager(store, "image", "synthetic.jpg", save_evidence=False).process(result, now=0.0)[0]
    at = _open("Safety Events")
    assert not at.exception
    review_box = [s for s in at.selectbox if s.label == "Review status"][0]
    review_box.set_value("false_positive")
    at.text_area[0].input("Shadow mistaken for bare head")
    [b for b in at.button if b.label == "Save review"][0].click().run()
    assert not at.exception
    row = EventStore(temp_db).list_events().iloc[0]
    assert row["event_id"] == event.event_id
    assert row["review_status"] == "false_positive"
    assert row["notes"] == "Shadow mistaken for bare head"


def test_invalid_video_upload_shows_error_state(detector):
    at = _open("Video Inspection")
    at.file_uploader[0].set_value(("broken.mp4", b"not a real video file" * 50, "video/mp4")).run()
    at.button[0].click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("could not be opened" in e.value or "no readable frames" in e.value for e in at.error)
