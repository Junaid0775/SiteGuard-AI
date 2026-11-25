# CAMERA-FIX-REPORT-001 — Phase 1: accidental evidence file removal and report corrections

**Date:** 2026-11-23, 12:35–12:37 IST. **Authorisation:** owner's instruction D (delete exactly one file) and E (append corrections). **Status:** PASS.

## D. Deleting `outputs/evidence/EVT-20261123-031826-215199.jpg`

**Pre-deletion checks** (record: `experiments/camera_quality_audit/fixes/phase1/target_file_record.txt`):

| Check | Result |
|---|---|
| File exists | yes |
| Path matches | real path `<project>/outputs/evidence/EVT-20261123-031826-215199.jpg`; the file name matches exactly |
| Size | 78,413 bytes |
| Modified | 2026-11-23 03:18:26 (the ML Phase 7 replay run) |
| SHA-256 | `f9d2380ca37b803c3c3ff8ba0612c876ac2065eb666eab1dd35b9425c34bc3eb` |
| Linked to an event? | **No.** Read-only query: 0 events with that ID and 0 events whose `evidence_path` references the file (40 events in the database) |

**Deletion:** `rm -- "<project>/outputs/evidence/EVT-20261123-031826-215199.jpg"` at 12:35:48. It used a literal path; no wildcard and no variable.

**Post-deletion checks:**
- The file no longer exists.
- All **131** other evidence files were hashed before and after (`other_evidence_before.sha256`, `other_evidence_after.sha256`). **`diff` shows them identical.**
- No other evidence file and no database row was touched.

## E. Correction notes

A dated "Correction note — 2026-11-23 12:36 IST" was **appended** to the end of each of these files. Nothing above the note was changed.
- `experiments/accuracy_improvement/reports/REPORT-024-qualification-and-integration.md`
- `experiments/accuracy_improvement/reports/REPORT-025-final-research-decision.md`
- `experiments/accuracy_improvement/reports/HANDOFF-ML-to-frontend.md`

**Each note states:**
- the earlier "evidence unchanged" statement was inaccurate;
- which test created the file, and why (`LiveFrameProcessor(..., store=None)` still saves evidence);
- the file's name, size, hash and creation time;
- why the integrity check missed it (it does not list new files);
- the authorised deletion, and that the cause is fixed by Fix 6;
- that all experiment results and decisions are unaffected.

## Rollback

- **The deletion cannot be undone.** No copy was kept, as authorised: the file was an unlinked private webcam frame.
- **The correction notes** can be removed by deleting the appended section. This is not recommended.

## Preservation

- Models, thresholds, compliance rules, event logic, the database and the dataset are unchanged.
- No camera was used.
