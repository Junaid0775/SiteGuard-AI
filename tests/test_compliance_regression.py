"""Phase 9 compliance regression (spec §11, §12.4): rules unchanged, behaviour verified case by case.

The detector and the compliance engine are separate; every test here uses synthetic
detections so it checks the RULES, not the model.
"""

from __future__ import annotations

import io
import time

import numpy as np
import pandas as pd
import pytest

from src.compliance.compliance_analyzer import (
    COMPLIANT_EVIDENCE,
    POTENTIAL_VIOLATION,
    UNCERTAIN,
    ComplianceAnalyzer,
    ComplianceRules,
)
from src.detection.camera_processor import LiveFrameProcessor
from src.detection.detector import Detection
from src.events.event_manager import EventManager
from src.events.event_store import EventStore
from src.reporting.report_generator import events_to_csv_bytes
from src.utils.paths import load_settings

IDS = {"helmet": 0, "gloves": 1, "vest": 2, "boots": 3, "goggles": 4, "Person": 5, "no_helmet": 6, "no_goggle": 7,
       "no_gloves": 8, "no_boots": 9, "forklift": 10, "no_vest": 11}


def d(name, conf, x1, y1, x2, y2):
    return Detection(IDS[name], name, conf, x1, y1, x2, y2)


def analyzer():
    return ComplianceAnalyzer(ComplianceRules.from_settings())  # the production rules from configs/settings.yaml


def test_production_thresholds_unchanged():
    s = load_settings()
    assert s["compliance"] == {"required_ppe": ["helmet", "vest", "gloves"], "person_confidence": 0.40, "violation_confidence": 0.50,
                               "evidence_confidence": 0.40, "min_containment": 0.60, "ambiguity_margin": 0.15,
                               "person_box_margin": 0.10, "conflict_iou": 0.50}
    e = s["events"]
    assert (e["cooldown_seconds"], e["min_consecutive_hits"], e["match_iou"], e["candidate_timeout_seconds"]) == (30, 3, 0.30, 3)


def test_no_person_gives_no_workers_and_no_events():
    r = analyzer().analyze([d("no_helmet", 0.9, 10, 10, 50, 50)])
    assert r.workers == [] and EventManager(None, "image", "x", save_evidence=False).process(r, now=0.0) == []


def test_absence_of_ppe_is_uncertain_never_a_violation():
    r = analyzer().analyze([d("Person", 0.9, 100, 100, 200, 400)])
    assert r.workers[0].status == UNCERTAIN and r.workers[0].violations == []


def test_positive_evidence_for_all_required_items_is_compliant():
    r = analyzer().analyze([d("Person", 0.9, 100, 100, 200, 400), d("helmet", 0.8, 130, 92, 170, 130),
                            d("vest", 0.8, 110, 160, 190, 260), d("gloves", 0.8, 100, 250, 125, 280)])
    assert r.workers[0].status == COMPLIANT_EVIDENCE


def test_small_ppe_box_is_associated_with_its_worker():
    r = analyzer().analyze([d("Person", 0.9, 1000, 500, 1012, 540), d("no_helmet", 0.8, 1003, 499, 1009, 506)])
    assert r.workers[0].items["helmet"].status == POTENTIAL_VIOLATION


def test_partially_visible_worker_helmet_slightly_outside_box_still_associated():
    # person box cut at the top of the frame; helmet sticks out by ~30 % of its height (within the 10 % box margin + 60 % containment)
    r = analyzer().analyze([d("Person", 0.9, 100, 0, 200, 300), d("no_helmet", 0.8, 130, -8, 170, 22)])
    assert r.workers[0].items["helmet"].status == POTENTIAL_VIOLATION


def test_missing_ppe_outside_every_person_region_never_creates_a_violation():
    r = analyzer().analyze([d("Person", 0.9, 100, 100, 200, 400), d("no_vest", 0.95, 500, 150, 600, 260)])
    assert r.workers[0].violations == [] and len(r.unassigned) == 1


def test_false_low_confidence_person_is_not_a_worker():
    r = analyzer().analyze([d("Person", 0.3, 100, 100, 200, 400), d("no_helmet", 0.9, 130, 92, 170, 130)])
    assert r.workers == []


def test_multiple_people_each_item_used_at_most_once():
    dets = [d("Person", 0.9, 100, 100, 200, 400), d("Person", 0.9, 400, 100, 500, 400), d("Person", 0.9, 700, 100, 800, 400),
            d("no_helmet", 0.8, 130, 92, 170, 130), d("helmet", 0.8, 430, 92, 470, 130), d("no_vest", 0.8, 710, 160, 790, 260)]
    r = analyzer().analyze(dets)
    used = [x for w in r.workers for x in w.linked_detections]
    assert len(used) == len({id(x) for x in used}) == 3
    assert [w.items["helmet"].status for w in r.workers] == [POTENTIAL_VIOLATION, COMPLIANT_EVIDENCE, UNCERTAIN]
    assert r.workers[2].items["vest"].status == POTENTIAL_VIOLATION


def test_overlapping_workers_make_shared_item_ambiguous_not_a_violation():
    r = analyzer().analyze([d("Person", 0.9, 100, 100, 200, 400), d("Person", 0.9, 150, 100, 250, 400),
                            d("no_helmet", 0.95, 160, 90, 190, 130)])
    assert all(w.violations == [] for w in r.workers) and len(r.ambiguous) == 1


def test_conflicting_boxes_resolve_to_uncertain():
    r = analyzer().analyze([d("Person", 0.9, 100, 100, 200, 400), d("no_helmet", 0.55, 130, 92, 170, 130),
                            d("helmet", 0.85, 131, 93, 171, 131)])
    assert r.workers[0].items["helmet"].status == UNCERTAIN


def test_worker_labels_are_frame_specific_not_identities():
    a, b = d("Person", 0.9, 100, 100, 200, 400), d("Person", 0.9, 400, 100, 500, 400)
    f1 = analyzer().analyze([a, b])
    f2 = analyzer().analyze([b])                      # same physical worker b, next frame, alone
    assert [w.worker_ref for w in f1.workers] == ["W1", "W2"]
    assert f2.workers[0].worker_ref == "W1"            # 'W2' in frame 1 is 'W1' in frame 2: labels are per frame


def _violating_frame():
    return analyzer().analyze([d("Person", 0.9, 100, 100, 200, 400), d("no_helmet", 0.9, 130, 92, 170, 130)])


def test_three_analysed_frame_persistence_and_30s_suppression(tmp_path):
    store = EventStore(tmp_path / "e.db")
    em = EventManager(store, "video", "clip.mp4", save_evidence=False)
    assert em.min_hits == 3 and em.cooldown == 30
    assert em.process(_violating_frame(), now=0.0) == [] and em.process(_violating_frame(), now=0.1) == []
    ev = em.process(_violating_frame(), now=0.2)
    assert len(ev) == 1 and ev[0].media_time_s is None and ev[0].timestamp  # ISO wall-clock timestamp recorded
    for t in np.arange(0.3, 29.0, 0.5):
        assert em.process(_violating_frame(), now=float(t)) == []            # suppressed inside 30 s
    assert len(em.process(_violating_frame(), now=31.0)) == 1                # reminder after the cooldown
    assert store.count_events() == 2


def test_evidence_review_status_database_restart_and_csv(tmp_path):
    db = tmp_path / "e.db"
    em = EventManager(EventStore(db), "image", "a.jpg", evidence_dir=tmp_path / "ev")
    ev = em.process(_violating_frame(), now=0.0, evidence_frame=np.zeros((480, 640, 3), np.uint8))[0]
    assert ev.evidence_path and (tmp_path / "ev" / f"{ev.event_id}.jpg").exists()
    assert ev.review_status == "pending_review"
    store2 = EventStore(db)                                                  # "restart": a new connection reads the data
    store2.update_review_status(ev.event_id, "confirmed", "checked")
    row = EventStore(db).list_events().iloc[0]
    assert (row["event_id"], row["review_status"], row["notes"]) == (ev.event_id, "confirmed", "checked")
    csv_df = pd.read_csv(io.BytesIO(events_to_csv_bytes(EventStore(db).list_events())))
    assert csv_df.iloc[0]["Review status"] == "confirmed" and csv_df.iloc[0]["Event category"] == "Potential missing helmet"


class ViolationDetector:
    image_size = 640

    def detect(self, img, confidence=None, image_size=None):
        return [d("Person", 0.9, 100, 100, 200, 400), d("no_helmet", 0.9, 130, 92, 170, 130)]


def test_live_pipeline_keeps_persistence_and_restart_resets_candidates():
    p = LiveFrameProcessor(ViolationDetector(), analyzer(), None)
    frame = np.zeros((480, 640, 3), np.uint8)
    p.process(frame); p.process(frame)
    assert p.events.events_created == []
    p.process(frame)
    assert len(p.events.events_created) == 1                  # 3rd analysed frame raises the event
    p.reset_session()
    p.process(frame); p.process(frame)
    assert p.events.events_created == []                       # new session: persistence starts again
