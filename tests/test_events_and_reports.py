"""Event deduplication, SQLite storage and CSV reports."""

from __future__ import annotations

import io

import pandas as pd
import pytest

from src.compliance.compliance_analyzer import ComplianceAnalyzer, ComplianceRules
from src.compliance.worker_association import AssociationParams
from src.events.event_manager import EventManager
from src.events.event_store import EventStore, InspectionRecord
from src.reporting.report_generator import events_to_csv_bytes, inspections_report_frame, summary_report

RULES = ComplianceRules(required_ppe=("helmet",), association=AssociationParams())


@pytest.fixture
def store(tmp_path):
    return EventStore(tmp_path / "events.db")


def violation_frame(make_det, dx: float = 0.0):
    dets = [make_det("Person", 0.9, 100 + dx, 100, 200 + dx, 400), make_det("no_helmet", 0.8, 130 + dx, 90, 170 + dx, 130)]
    return ComplianceAnalyzer(RULES).analyze(dets)


def test_single_image_creates_one_event(make_det, store):
    em = EventManager(store, "image", "test.jpg", save_evidence=False)
    events = em.process(violation_frame(make_det), now=0.0)
    assert len(events) == 1
    assert events[0].category == "no_helmet"
    assert store.count_events() == 1


def test_continuing_violation_is_deduplicated(make_det, store):
    em = EventManager(store, "video", "clip.mp4", cooldown_seconds=30, min_consecutive_hits=3, save_evidence=False)
    created = []
    for i in range(50):  # 50 frames, 0.2 s apart = 10 s, worker drifts slightly
        created += em.process(violation_frame(make_det, dx=i * 0.5), now=i * 0.2)
    assert len(created) == 1
    assert store.count_events() == 1
    assert em.suppressed > 0


def test_persistence_requires_min_hits(make_det, store):
    em = EventManager(store, "video", "clip.mp4", min_consecutive_hits=3, save_evidence=False)
    assert em.process(violation_frame(make_det), now=0.0) == []
    assert em.process(violation_frame(make_det), now=0.2) == []
    assert len(em.process(violation_frame(make_det), now=0.4)) == 1


def test_new_event_after_cooldown(make_det, store):
    em = EventManager(store, "video", "clip.mp4", cooldown_seconds=5, min_consecutive_hits=1, candidate_timeout_seconds=100, save_evidence=False)
    assert len(em.process(violation_frame(make_det), now=0.0)) == 1
    assert em.process(violation_frame(make_det), now=3.0) == []
    assert len(em.process(violation_frame(make_det), now=6.0)) == 1


def test_different_worker_regions_are_separate_events(make_det, store):
    em = EventManager(store, "video", "clip.mp4", min_consecutive_hits=1, save_evidence=False)
    assert len(em.process(violation_frame(make_det, dx=0), now=0.0)) == 1
    assert len(em.process(violation_frame(make_det, dx=500), now=0.1)) == 1


def test_compliant_frames_create_no_events(make_det, store):
    em = EventManager(store, "image", "ok.jpg", save_evidence=False)
    dets = [make_det("Person", 0.9, 100, 100, 200, 400), make_det("helmet", 0.9, 130, 90, 170, 130)]
    assert em.process(ComplianceAnalyzer(RULES).analyze(dets), now=0.0) == []


def test_review_status_update_and_filters(make_det, store):
    em = EventManager(store, "image", "a.jpg", save_evidence=False)
    ev = em.process(violation_frame(make_det), now=0.0)[0]
    store.update_review_status(ev.event_id, "confirmed", "checked on site")
    df = store.list_events(statuses=["confirmed"])
    assert list(df["event_id"]) == [ev.event_id]
    assert df.iloc[0]["notes"] == "checked on site"
    assert store.list_events(categories=["no_vest"]).empty
    with pytest.raises(ValueError):
        store.update_review_status(ev.event_id, "approved")


def test_events_csv_report(make_det, store):
    em = EventManager(store, "image", "a.jpg", save_evidence=False)
    em.process(violation_frame(make_det), now=0.0)
    csv_bytes = events_to_csv_bytes(store.list_events())
    df = pd.read_csv(io.BytesIO(csv_bytes))
    for col in ("Date/time", "Event category", "Source", "Confidence", "Review status"):
        assert col in df.columns
    assert df.iloc[0]["Event category"] == "Potential missing helmet"
    assert df.iloc[0]["Source"] == "image"
    assert df.iloc[0]["Review status"] == "pending_review"


def test_empty_events_csv_has_headers(store):
    df = pd.read_csv(io.BytesIO(events_to_csv_bytes(store.list_events())))
    assert df.empty and "Event category" in df.columns


def test_inspection_records_and_summary(store):
    store.add_inspection(InspectionRecord("INS-1", "2026-11-19T10:00:00", "image", "a.jpg", 1, 3, {"Person": 3, "helmet": 2}, 1, {}))
    ins = store.list_inspections()
    assert len(ins) == 1
    expanded = inspections_report_frame(ins)
    assert expanded.iloc[0]["detections_Person"] == 3
    summary = summary_report(store.list_events(), ins)
    assert summary["person_detections"] == 3 and summary["events_total"] == 0
