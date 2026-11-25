"""Rule-based PPE compliance analysis.

Input: the raw detections for one image/frame.
Output: for every detected worker and every required PPE item, one of three
statuses:

* POTENTIAL VIOLATION  - an explicit missing-PPE box (e.g. `no_helmet`) with
  confidence >= `violation_confidence` is linked to this worker (see
  worker_association.py) and is not contradicted by a stronger PPE box in the
  same place.
* COMPLIANT EVIDENCE   - a PPE box (e.g. `helmet`) with confidence >=
  `evidence_confidence` is linked to this worker, and no qualifying missing-PPE box.
* UNCERTAIN            - anything else. Not detecting a helmet is NOT proof that
  the worker has no helmet: the head may be hidden, cut off, too small or
  simply missed by the model.

A worker's overall status is POTENTIAL VIOLATION if any item is, COMPLIANT
EVIDENCE only if every required item is, and UNCERTAIN otherwise.

These are model-based observations for a supervisor to review, not confirmed
real-world violations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.compliance.worker_association import (
    CLASS_TO_ITEM,
    PERSON_CLASS,
    AssociationParams,
    associate_items,
    iou,
)
from src.detection.detector import Detection
from src.utils.paths import load_settings

POTENTIAL_VIOLATION = "potential_violation"
COMPLIANT_EVIDENCE = "compliant_evidence"
UNCERTAIN = "uncertain"

STATUS_LABELS = {
    POTENTIAL_VIOLATION: "Potential violation",
    COMPLIANT_EVIDENCE: "Compliant evidence",
    UNCERTAIN: "Uncertain / insufficient visual evidence",
}

SUPPORTED_ITEMS = ("helmet", "vest", "gloves", "boots", "goggles")
NEGATIVE_CLASS = {"helmet": "no_helmet", "vest": "no_vest", "gloves": "no_gloves", "boots": "no_boots", "goggles": "no_goggle"}


@dataclass
class ComplianceRules:
    required_ppe: tuple[str, ...] = ("helmet", "vest", "gloves")
    person_confidence: float = 0.40
    violation_confidence: float = 0.50
    evidence_confidence: float = 0.40
    conflict_iou: float = 0.50
    association: AssociationParams = field(default_factory=AssociationParams)

    @classmethod
    def from_settings(cls, overrides: dict | None = None) -> "ComplianceRules":
        cfg = dict(load_settings()["compliance"])
        cfg.update(overrides or {})
        required = tuple(i for i in cfg["required_ppe"] if i in SUPPORTED_ITEMS)
        return cls(
            required_ppe=required,
            person_confidence=float(cfg["person_confidence"]),
            violation_confidence=float(cfg["violation_confidence"]),
            evidence_confidence=float(cfg["evidence_confidence"]),
            conflict_iou=float(cfg["conflict_iou"]),
            association=AssociationParams(
                min_containment=float(cfg["min_containment"]),
                ambiguity_margin=float(cfg["ambiguity_margin"]),
                person_box_margin=float(cfg["person_box_margin"]),
            ),
        )


@dataclass
class ItemAssessment:
    item: str
    status: str
    confidence: float | None  # confidence of the deciding detection, if any
    reason: str
    evidence: Detection | None = None


@dataclass
class WorkerAssessment:
    worker_ref: str
    person: Detection
    status: str
    items: dict[str, ItemAssessment]
    linked_detections: list[Detection]

    @property
    def violations(self) -> list[ItemAssessment]:
        return [a for a in self.items.values() if a.status == POTENTIAL_VIOLATION]


@dataclass
class ComplianceResult:
    workers: list[WorkerAssessment]
    ambiguous: list[Detection]          # items that could belong to more than one worker
    unassigned: list[Detection]         # items not inside any worker box
    all_detections: list[Detection]

    @property
    def counts(self) -> dict[str, int]:
        c = {POTENTIAL_VIOLATION: 0, COMPLIANT_EVIDENCE: 0, UNCERTAIN: 0}
        for w in self.workers:
            c[w.status] += 1
        return c

    def unassigned_negative(self, min_conf: float) -> list[Detection]:
        """Missing-PPE boxes that are confident but not linked to a worker (shown, never alerted)."""
        return [
            d for d in self.unassigned + self.ambiguous
            if d.class_name in CLASS_TO_ITEM and CLASS_TO_ITEM[d.class_name][1] and d.confidence >= min_conf
        ]

    def table_rows(self) -> list[dict]:
        rows = []
        for w in self.workers:
            row = {"Worker": w.worker_ref, "Person conf.": round(w.person.confidence, 2), "Overall": STATUS_LABELS[w.status]}
            for item, a in w.items.items():
                row[item.capitalize()] = STATUS_LABELS[a.status] + (f" ({a.confidence:.2f})" if a.confidence is not None else "")
            rows.append(row)
        return rows


class ComplianceAnalyzer:
    def __init__(self, rules: ComplianceRules | None = None) -> None:
        self.rules = rules or ComplianceRules.from_settings()

    def assess_item(self, item: str, linked: list[Detection]) -> ItemAssessment:
        r = self.rules
        neg_name = NEGATIVE_CLASS[item]
        positives = sorted((d for d in linked if d.class_name == item), key=lambda d: -d.confidence)
        negatives = sorted((d for d in linked if d.class_name == neg_name), key=lambda d: -d.confidence)
        strong_neg = [d for d in negatives if d.confidence >= r.violation_confidence]
        strong_pos = [d for d in positives if d.confidence >= r.evidence_confidence]

        if strong_neg:
            neg = strong_neg[0]
            # Conflict: a stronger PPE box covering the same region as the missing-PPE box.
            conflicting = [p for p in strong_pos if iou(p.box, neg.box) >= r.conflict_iou and p.confidence > neg.confidence]
            if conflicting:
                return ItemAssessment(item, UNCERTAIN, neg.confidence, f"conflicting '{item}' and '{neg_name}' boxes in the same region", neg)
            return ItemAssessment(item, POTENTIAL_VIOLATION, neg.confidence, f"'{neg_name}' detected on this worker", neg)
        if strong_pos:
            pos = strong_pos[0]
            return ItemAssessment(item, COMPLIANT_EVIDENCE, pos.confidence, f"'{item}' detected on this worker", pos)
        if negatives:
            return ItemAssessment(item, UNCERTAIN, negatives[0].confidence, f"'{neg_name}' below violation threshold {r.violation_confidence:.2f}", negatives[0])
        if positives:
            return ItemAssessment(item, UNCERTAIN, positives[0].confidence, f"'{item}' below evidence threshold {r.evidence_confidence:.2f}", positives[0])
        return ItemAssessment(item, UNCERTAIN, None, "no visual evidence (may be occluded, out of frame, too small or missed)")

    def analyze(self, detections: list[Detection]) -> ComplianceResult:
        r = self.rules
        workers = sorted(
            (d for d in detections if d.class_name == PERSON_CLASS and d.confidence >= r.person_confidence),
            key=lambda d: (d.x1, d.y1),
        )
        items = [d for d in detections if d.class_name in CLASS_TO_ITEM]
        assoc = associate_items(workers, items, r.association)

        assessments = []
        for idx, person in enumerate(workers):
            linked = assoc.assigned.get(idx, [])
            per_item = {item: self.assess_item(item, linked) for item in r.required_ppe}
            statuses = [a.status for a in per_item.values()]
            if POTENTIAL_VIOLATION in statuses:
                overall = POTENTIAL_VIOLATION
            elif statuses and all(s == COMPLIANT_EVIDENCE for s in statuses):
                overall = COMPLIANT_EVIDENCE
            else:
                overall = UNCERTAIN
            assessments.append(WorkerAssessment(f"W{idx + 1}", person, overall, per_item, linked))
        return ComplianceResult(assessments, assoc.ambiguous, assoc.unassigned, list(detections))
