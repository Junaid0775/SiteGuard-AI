# FRONTEND-REPORT-006 — Phase 6: final documentation and handoff

**Status:** **Frontend complete; physical-camera validation pending** (it needs the project owner's approval and presence). **Date:** 2026-11-23, 11:35 IST.

## 1. Executive summary

The SiteGuard AI dashboard was completed in place, in Streamlit.

**What changed:**
- a dark industrial theme with one restrained safety-orange accent;
- shared presentation components;
- honest scope lines on every aggregate figure;
- a live status panel built from `LiveFrameProcessor.snapshot()`;
- a read-only Settings page;
- a Model Evaluation page that shows the accuracy-programme results with exact metric, split and size wording.

**What did not change:**
- backend, inference, compliance rules, event logic, thresholds, database, dataset and checkpoints;
- YOLO26n is still the active and default model;
- E3 stays a non-selectable, not-promoted research result.

**Results:**
- **Tests:** 166 of 166 pass (156 existing, unchanged, plus 10 new).
- **Startup:** the application starts in about 2 s.
- **Integrity:** verification shows no change to the dataset, the checkpoints, the events database or the evidence.

## 2. What was implemented

| Area | Implementation |
|---|---|
| Theme | `.streamlit/config.toml`: forced dark base, charcoal surfaces (`#121417`, `#1A1E23`), accent `#E07A3F`, semantic status colours, small radius, chart palette, sidebar palette. `client.toolbarMode = "minimal"` hides the developer menu and the Deploy button |
| Components | `src/ui/theme.py` (tokens, CSS including narrow-window rules and a visible focus outline, Plotly styling); `src/ui/components.py` (page header, scope note, badges with text, key-value tables, model identity, advisory); `src/ui/evaluation_data.py` (read-only loaders for the evaluation files and the model card) |
| Shell | Brand block (text only), navigation list with an active-page accent, model status (Active / Fallback warning / No usable model), notice. `?page=` deep links |
| Overview | Scope line (the stored data's time range, and "zero events is not proof of compliance"); 5 tiles; task shortcuts; recent events (readable status, detector confidence); category chart with time range; active-model identity and development-set metrics |
| Live Monitoring | State badge (Stopped / Connecting / Running / Error); camera starts only on START; "frames not saved"; physical-camera validation shown as pending; status table from `snapshot()` (received, analysed and rendered fps, dropped, inference p95, errors); workers, detections, session events; open session closed when leaving the page |
| Image Inspection | Format and limit guidance from code; record-toggle explanation; original and annotated result; "detector confidence" wording |
| Video Inspection | Format guidance; 500 MB limit; the note "offline time is not a real-time claim"; same inputs and button; missing-output error |
| Safety Events | Status explanation; status tiles; filters; readable table; CSV export; review form (existing API only); missing-evidence error |
| Analytics | Scope line; definitions; 4 charts with titles, time ranges and axis units |
| Model Evaluation | YOLO26n development-set results (split and size named); same-split comparison with E3; E3 research block (not promoted, not selectable; 160-image same-dataset held-back test; targets, intervals and n per class; real-scene vs close-up; replay); limitations; viewpoint experiment |
| Settings / About | Read-only settings tables; registry-only model selector (one entry); identity with the full SHA-256; classes; software versions; camera status; disclaimer |

## 3. Architecture decision

**Streamlit kept and redesigned in place** (REPORT-002 §6). The reasons:
- every workflow was already working and tested;
- a separate frontend would have needed a new API server and build chain, and that risked the deadline;
- the Streamlit theme and CSS were sufficient for the required design.

No new dependency was added.

## 4. Files changed

| File | Change | Pre-change copy |
|---|---|---|
| `app.py` | Presentation rewrite; same backend calls | `experiments/frontend_completion/backups/20261123-phase0/app.py` |
| `.streamlit/config.toml` | Dark theme, toolbar minimal | `…/backups/20261123-phase0/config.toml` |
| `README.md` | Sections 11, 12, 13.2, **13.3 (new)**, 14 and **16 (new)** updated; ML documentation preserved | `…/backups/20261123-phase0/README.md` |
| `src/ui/__init__.py`, `theme.py`, `components.py`, `evaluation_data.py` | **New** | — |
| `tests/test_frontend_ui.py` | **New**, 10 tests | — |
| `SiteGuard_AI_Frontend_Completion_Master_Specification.md` | **New** (copy of the specification) | — |
| `experiments/frontend_completion/` | Reports 001–006, logs, screenshots, the screenshot tool (`tools/capture_screenshots.py`), backups | — |

**Restoring the previous frontend:** copy the three backup files back over `app.py`, `.streamlit/config.toml` and `README.md`. The `src/ui/` modules and the new test file are then unused and can stay.

## 5. Files deliberately not changed

- `configs/settings.yaml` and `configs/dataset.yaml`;
- `src/detection/*`, `src/compliance/*`, `src/events/*`, `src/reporting/*`, `src/training/*`, `src/evaluation/*`, `src/utils/*`;
- all checkpoints and model cards;
- `outputs/siteguard_events.db` and `outputs/evidence/`;
- `../construction-ppe/`;
- `experiments/accuracy_improvement/*`;
- all existing tests.

## 6. Test results

| Run | Result |
|---|---|
| Baseline before changes (11:07) | 156 passed |
| Final (after the last change) | **166 passed, 0 failed, 0 skipped** (`.venv/bin/python -m pytest -q`) |

Functional checks 1–23: see REPORT-004 §3. 21 PASS. Check 8 (live start/stop with a camera) and the browser half of check 9 are **BLOCKED**, pending camera approval.

## 7. Application startup verification

- **Command:** `.venv/bin/streamlit run app.py --server.port 8599 --server.address 127.0.0.1`.
- **Result:** `/_stcore/health` returned `ok` after 2 s, and `GET /` returned HTTP 200. The server was started and stopped 4 times without error, and its logs show no exception.
- **Your running dashboard (port 8502, PID 34056):** left running. It picks up the new `app.py` on reload. **Restart it** to apply the new `.streamlit/config.toml`, which controls the dark theme and the hidden Deploy button.

## 8. Model status

| Model | Status |
|---|---|
| YOLO26n `yolo26n_baseline`, `models/trained/best.pt`, sha256 `890dc61fd024b247eda19753a1787a5b9ac16ff0236b2f72e06ae6814c995b9b` | **Active and fallback**, unchanged |
| YOLO26m E3 `yolo26m_e3_896_v1`, sha256 `590d7d6e8510f3c121ee74df38bf10028b67b212cd35c50da0916bce9f6b60e6` | **Not promoted, not registered, not selectable.** Shown only as a research result |

## 9. ML metrics and limitations (as displayed)

**Active model, YOLO26n:**
- **Split:** the development set, 200 images and 2,961 objects (the original validation split; Ultralytics val).
- **Results:** precision 0.832, recall 0.681, mAP50 0.734, mAP50-95 0.523.

**E3, held-back test:**
- **Split:** 160 images and 2,480 objects of the **same dataset**. This is not real-site footage and not a live-camera result.
- **Results:** mAP50 0.847, mAP50-95 0.644, precision 0.885 and recall 0.862 at confidence 0.25.
- **Missing-PPE recall:** 0.739, 0.650, 0.522, 0.796 and 0.688 for no_helmet, no_gloves, no_goggle, no_boots and no_vest, each against a target of 0.90.

**Limitations shown on the page:**
- missing-PPE recall well below 0.90;
- real-site photos versus close-ups: mAP50 0.59 against 0.95;
- weaker on dark images;
- 178 suspect labels unreviewed;
- a single training seed;
- experiments not run;
- the camera test pending;
- a benchmark is not a guarantee of site performance.

**Wording:** no "accuracy %" and no "production-qualified" wording anywhere (test 15).

## 10. Camera test status

**Pending.** It was not run because the owner's explicit approval is required (spec §7.3).
- **Proposed test:** about 30 seconds, the dashboard's START then STOP, or `scripts/engineering/realtime_eval.py camera --seconds 12` for YOLO26n.
- Frames are processed locally and are **not saved**.
- Release of the camera is verified afterwards.

## 11. Known bugs and limitations

1. Physical camera not validated with this build (see above).
2. At 1024 px, two tile help icons sit close to their two-line labels. This is cosmetic.
3. The test suite appends to the real application log `outputs/logs/siteguard_app.log`. This was pre-existing and is a minor issue.
4. The superseded interim screenshot `evidence/screenshots/01_overview_1440x900_redacted.png` is kept; deleting files was avoided.
5. All model limitations listed in §9 and in REPORT-025.

## 12. Launch instructions

```bash
cd ~/Desktop/471\ Project/SiteGuard-AI
.venv/bin/streamlit run app.py --server.port 8502        # port 8501 is used by another local project on this Mac
# open http://localhost:8502   (pages: http://localhost:8502/?page=Model%20Evaluation, etc.)
```

## 13. Demonstration walkthrough (about 6 minutes)

1. **Overview.** Show the active model, YOLO26n with its full identity in Settings. Point out the scope line with the stored events' time range and the "zero events is not proof" note.
2. **Image Inspection.** Upload a dataset image, for example from `../construction-ppe/images/val/`. Show the original and the result, the per-worker compliance cards with Potential violation, Compliant evidence and Uncertain, and the "detector confidence" wording.
   - Switch off "Record potential violations" if the demo should not add events.
3. **Video Inspection.** Analyse `data/test_media/test_site_clip.mp4` with "Maximum frames" set to 120 or so for speed. Show the progress bar, the summary tiles and the annotated video. Note that offline time is not a real-time claim.
4. **Safety Events.** Show the filters, the readable statuses and the CSV export. Set one event's review status to "False positive" with a note. That is the only write the UI makes.
5. **Analytics.** Show that each chart names its metric and time range, and the definitions.
6. **Model Evaluation.** Show the YOLO26n development-set results with the split named, then the same-split comparison, then E3 labelled *Not promoted / Not selectable*, its 160-image same-dataset held-back results against the targets, and the limitations.
7. **Live Monitoring.** Show the STOP / START flow only with the owner's consent. Otherwise explain the status panel and the pending camera validation.
8. **Settings / About.** Show that thresholds are read-only, that the selector lists only `yolo26n_baseline`, and the disclaimer.

## 14. Evidence

- **Screenshots:** `experiments/frontend_completion/evidence/screenshots/` (16 final captures at 1440 × 900 and 1024 × 768; the Safety Events captures have images hidden).
- **Review crops:** `evidence/review/`.
- **Logs:** `experiments/frontend_completion/logs/`, covering the baselines, test runs, database check, server logs and integrity verification.
- **Reports:** FRONTEND-REPORT-001 to 006.

## 15. Deferred work

- the physical-camera validation;
- the human review of the 178 suspect labels;
- further ML work (REPORT-025 §11);
- per-class alert thresholds (a policy decision);
- a test-only application log path;
- optional: collapse the sidebar automatically on narrow windows.

## 16. Publication

**No public push, deployment, hosting or upload happened.**
- The project is not a Git repository.
- Nothing was sent to an external service.
- Screenshots were taken locally with headless Chrome, against `127.0.0.1` only.
- The Streamlit Deploy button is now hidden.

## 17. Protected-asset verification

**Command:** `.venv/bin/python scripts/accuracy/integrity_manifest.py verify experiments/accuracy_improvement/manifests/20261123-110740_frontend_phase0 --json experiments/frontend_completion/logs/phase6_integrity_verify.json`

| Set | Result |
|---|---|
| Original dataset (2,004 files) | **0 changed, 0 missing, 0 new** |
| Key checkpoints | **0 critical violations** (YOLO26n `890dc61f…`, E3 `590d7d6e…`, earlier YOLO26m `399c4e5b…` unchanged) |
| Protected files changed (4) | `app.py`, `.streamlit/config.toml`, `README.md` (all intended, with backups); `experiments/frontend_completion/logs/phase0_baseline.txt` (this programme's own log, which was still being written when the manifest was taken) |
| User data (317 files) | Only `outputs/logs/siteguard_app.log` changed (the application log, appended by the tests and the test server). **Events database and evidence unchanged** |

**Events database, read-only check** (`logs/phase4_events_db_check.txt`): `PRAGMA integrity_check` = `ok`; 33 events and 6 inspections; modification time still **2026-11-20 21:19:11**; sha256 `edb958eb452e7dd7…`.

## 18. Demonstration readiness checklist (spec §9.3)

| Item | Status |
|---|---|
| Starts reliably using the documented instructions | PASS |
| YOLO26n loads as the active and default model | PASS |
| E3 not selectable | PASS |
| Model metadata, fallback and error states handled | PASS |
| All navigation items work | PASS |
| Image inspection tested | PASS |
| Video inspection tested | PASS |
| Live monitoring: pending camera status disclosed | PASS (disclosed); physical camera **pending** |
| Event list and evidence viewing with existing data | PASS |
| Analytics shows real data or honest empty states | PASS |
| Model metrics labelled correctly | PASS |
| No fake events or fake metrics | PASS |
| Full regression suite passes | PASS (166 of 166) |
| README and final handoff report complete | PASS |
| Protected data and model hashes unchanged | PASS |
| No public deployment or push | PASS |

**Final status: frontend complete; physical-camera validation pending.**
