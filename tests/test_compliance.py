"""Worker association and compliance classification (pure logic, no model needed)."""

from __future__ import annotations

from src.compliance.compliance_analyzer import (
    COMPLIANT_EVIDENCE,
    POTENTIAL_VIOLATION,
    UNCERTAIN,
    ComplianceAnalyzer,
    ComplianceRules,
)
from src.compliance.worker_association import AssociationParams, associate_items, containment, iou

RULES = ComplianceRules(
    required_ppe=("helmet", "vest"),
    person_confidence=0.4,
    violation_confidence=0.5,
    evidence_confidence=0.4,
    conflict_iou=0.5,
    association=AssociationParams(min_containment=0.6, ambiguity_margin=0.15, person_box_margin=0.1),
)
WORKER_A = (100, 100, 200, 400)
WORKER_B = (400, 100, 500, 400)
HEAD_A = (130, 90, 170, 130)
HEAD_B = (430, 90, 470, 130)
TORSO_A = (110, 160, 190, 260)
TORSO_B = (410, 160, 490, 260)


def analyze(dets, rules=RULES):
    return ComplianceAnalyzer(rules).analyze(dets)


# ---------------------------------------------------------------- geometry
def test_iou_and_containment():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert abs(iou((0, 0, 10, 10), (5, 0, 15, 10)) - 1 / 3) < 1e-9
    assert containment((2, 2, 4, 4), (0, 0, 10, 10)) == 1.0
    assert containment((8, 0, 12, 10), (0, 0, 10, 10)) == 0.5


# -------------------------------------------------------------- association
def test_each_item_goes_to_the_correct_worker(make_det):
    a, b = make_det("Person", 0.9, *WORKER_A), make_det("Person", 0.9, *WORKER_B)
    ha, hb = make_det("helmet", 0.8, *HEAD_A), make_det("no_helmet", 0.8, *HEAD_B)
    res = associate_items([a, b], [ha, hb], RULES.association)
    assert res.assigned[0] == [ha]
    assert res.assigned[1] == [hb]
    assert not res.ambiguous and not res.unassigned


def test_item_between_overlapping_workers_is_ambiguous(make_det):
    a = make_det("Person", 0.9, 100, 100, 200, 400)
    c = make_det("Person", 0.9, 150, 100, 250, 400)
    helmet = make_det("no_helmet", 0.9, 160, 90, 190, 130)  # centred exactly between both workers
    res = associate_items([a, c], [helmet], RULES.association)
    assert res.ambiguous == [helmet]
    assert res.assigned == {0: [], 1: []}


def test_item_outside_every_worker_is_unassigned(make_det):
    a = make_det("Person", 0.9, *WORKER_A)
    far = make_det("no_helmet", 0.9, 700, 50, 740, 90)
    res = associate_items([a], [far], RULES.association)
    assert res.unassigned == [far]


def test_one_detection_is_never_assigned_twice(make_det):
    a = make_det("Person", 0.9, 100, 100, 200, 400)
    c = make_det("Person", 0.9, 120, 100, 260, 400)
    item = make_det("no_vest", 0.9, 115, 160, 185, 260)
    res = associate_items([a, c], [item], RULES.association)
    total = sum(len(v) for v in res.assigned.values()) + len(res.ambiguous) + len(res.unassigned)
    assert total == 1


def test_forklift_is_not_personal_equipment(make_det):
    a = make_det("Person", 0.9, *WORKER_A)
    res = associate_items([a], [make_det("forklift", 0.9, 110, 300, 190, 390)], RULES.association)
    assert res.assigned[0] == [] and not res.unassigned


# ---------------------------------------------------------- classification
def test_explicit_negative_gives_potential_violation(make_det):
    r = analyze([make_det("Person", 0.9, *WORKER_A), make_det("no_helmet", 0.8, *HEAD_A), make_det("vest", 0.8, *TORSO_A)])
    w = r.workers[0]
    assert w.items["helmet"].status == POTENTIAL_VIOLATION
    assert w.items["vest"].status == COMPLIANT_EVIDENCE
    assert w.status == POTENTIAL_VIOLATION
    assert [v.item for v in w.violations] == ["helmet"]


def test_missing_detection_is_uncertain_not_violation(make_det):
    # Only a person: no helmet box and no no_helmet box -> we cannot conclude anything.
    r = analyze([make_det("Person", 0.9, *WORKER_A)])
    w = r.workers[0]
    assert w.items["helmet"].status == UNCERTAIN
    assert w.status == UNCERTAIN
    assert w.violations == []


def test_all_required_ppe_present_is_compliant_evidence(make_det):
    r = analyze([make_det("Person", 0.9, *WORKER_A), make_det("helmet", 0.7, *HEAD_A), make_det("vest", 0.6, *TORSO_A)])
    assert r.workers[0].status == COMPLIANT_EVIDENCE


def test_low_confidence_negative_is_uncertain(make_det):
    r = analyze([make_det("Person", 0.9, *WORKER_A), make_det("no_helmet", 0.3, *HEAD_A), make_det("vest", 0.8, *TORSO_A)])
    assert r.workers[0].items["helmet"].status == UNCERTAIN
    assert r.workers[0].status == UNCERTAIN


def test_conflicting_boxes_in_same_region_are_uncertain(make_det):
    r = analyze([
        make_det("Person", 0.9, *WORKER_A),
        make_det("no_helmet", 0.55, *HEAD_A),
        make_det("helmet", 0.85, 131, 91, 171, 131),
        make_det("vest", 0.8, *TORSO_A),
    ])
    assert r.workers[0].items["helmet"].status == UNCERTAIN
    assert "conflicting" in r.workers[0].items["helmet"].reason


def test_low_confidence_person_is_not_a_worker(make_det):
    r = analyze([make_det("Person", 0.2, *WORKER_A), make_det("no_helmet", 0.9, *HEAD_A)])
    assert r.workers == []
    assert len(r.unassigned_negative(0.5)) == 1  # shown to the user, but never an alert


def test_ambiguous_negative_does_not_create_violation(make_det):
    a = make_det("Person", 0.9, 100, 100, 200, 400)
    c = make_det("Person", 0.9, 150, 100, 250, 400)
    r = analyze([a, c, make_det("no_helmet", 0.95, 160, 90, 190, 130)])
    assert all(w.status != POTENTIAL_VIOLATION for w in r.workers)
    assert len(r.ambiguous) == 1


def test_workers_are_numbered_left_to_right(make_det):
    r = analyze([make_det("Person", 0.9, *WORKER_B), make_det("Person", 0.9, *WORKER_A)])
    assert [w.worker_ref for w in r.workers] == ["W1", "W2"]
    assert r.workers[0].person.x1 == WORKER_A[0]


def test_required_items_come_from_rules(make_det):
    rules = ComplianceRules(required_ppe=("helmet",), association=RULES.association)
    r = analyze([make_det("Person", 0.9, *WORKER_A), make_det("helmet", 0.9, *HEAD_A)], rules)
    assert list(r.workers[0].items) == ["helmet"]
    assert r.workers[0].status == COMPLIANT_EVIDENCE
