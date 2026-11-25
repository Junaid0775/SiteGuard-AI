"""CSV report generation for safety events and inspections."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.utils.paths import OUTPUTS_DIR

CATEGORY_LABELS = {
    "no_helmet": "Potential missing helmet",
    "no_vest": "Potential missing vest",
    "no_gloves": "Potential missing gloves",
    "no_boots": "Potential missing boots",
    "no_goggle": "Potential missing goggles",
}

REPORT_COLUMNS = {
    "timestamp": "Date/time",
    "category_label": "Event category",
    "source_type": "Source",
    "source_name": "Source name",
    "confidence": "Confidence",
    "review_status": "Review status",
    "event_id": "Event ID",
    "worker_ref": "Worker (per frame)",
    "media_time_s": "Video time (s)",
    "evidence_path": "Evidence image",
    "notes": "Reviewer notes",
}

DISCLAIMER = (
    "SiteGuard AI events are model-based observations of POTENTIAL PPE issues for human review. "
    "They are not confirmed violations."
)


def events_report_frame(events: pd.DataFrame) -> pd.DataFrame:
    """Rename and order event columns for a human-readable report."""
    df = events.copy()
    if df.empty:
        return pd.DataFrame(columns=list(REPORT_COLUMNS.values()))
    df["category_label"] = df["category"].map(CATEGORY_LABELS).fillna(df["category"])
    df["confidence"] = df["confidence"].round(3)
    cols = [c for c in REPORT_COLUMNS if c in df.columns]
    return df[cols].rename(columns=REPORT_COLUMNS)


def events_to_csv_bytes(events: pd.DataFrame) -> bytes:
    return events_report_frame(events).to_csv(index=False).encode("utf-8")


def save_events_report(events: pd.DataFrame, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or OUTPUTS_DIR / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"siteguard_events_{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    path.write_bytes(events_to_csv_bytes(events))
    return path


def inspections_report_frame(inspections: pd.DataFrame) -> pd.DataFrame:
    if inspections.empty:
        return inspections
    df = inspections.copy()
    counts = df["class_counts"].apply(lambda s: json.loads(s) if isinstance(s, str) else (s or {}))
    expanded = pd.json_normalize(counts).fillna(0).astype(int).add_prefix("detections_")
    df = pd.concat([df.drop(columns=["class_counts", "settings"]).reset_index(drop=True), expanded], axis=1)
    return df


def summary_report(events: pd.DataFrame, inspections: pd.DataFrame) -> dict:
    """Simple counts used by the Overview page and the inspection report."""
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "events_total": int(len(events)),
        "events_by_category": events["category"].value_counts().to_dict() if not events.empty else {},
        "events_by_source": events["source_type"].value_counts().to_dict() if not events.empty else {},
        "events_by_review_status": events["review_status"].value_counts().to_dict() if not events.empty else {},
        "inspections_total": int(len(inspections)),
        "frames_processed": int(inspections["frames_processed"].sum()) if not inspections.empty else 0,
        "person_detections": int(inspections["person_detections"].sum()) if not inspections.empty else 0,
        "disclaimer": DISCLAIMER,
    }
