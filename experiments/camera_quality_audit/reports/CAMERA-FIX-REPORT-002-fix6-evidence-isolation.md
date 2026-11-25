# CAMERA-FIX-REPORT-002 — Phase 2: Fix 6, keeping tests and diagnostics out of production evidence

**Date:** 2026-11-23, 12:37–12:47 IST. **Status:** **implemented and verified.**

## 1. Problem (wider than first reported)

`EventManager` saves an evidence JPEG whenever `save_evidence=True`, which is the default, **even when `store=None`**. The default folder is `events.evidence_dir` = `outputs/evidence/`. The problem shows up in three places:

1. **Diagnostic scripts:**
   - `scripts/engineering/realtime_eval.py` (`paced_live_run`, `camera`);
   - `scripts/engineering/measure_r1_r2.py`;
   - `src/evaluation/live_audit.py` (`run_webcam`).

   All of them use `LiveFrameProcessor(..., store=None)`. That combination produced the 03:18 webcam evidence file.
2. **The test suite (found in this phase).** Dashboard and pipeline tests wrote evidence into `outputs/evidence/`. A session fixture in `tests/conftest.py` then **deleted every file that appeared there during the test session**. If the dashboard had recorded a real event during a test run, its evidence would have been deleted.
3. **Video outputs.** The same cleanup pattern still applies to annotated test videos in `outputs/videos/`. This is pre-existing and out of the approved scope; see §6.

## 2. Changes

| File | Function or setting | Change |
|---|---|---|
| `src/events/event_manager.py` | `EventManager.__init__` (line 85) | `evidence_dir or os.environ.get("SITEGUARD_EVIDENCE_DIR") or cfg["evidence_dir"]` (+ `import os`). Mirrors the existing `SITEGUARD_EVENTS_DB` override of `EventStore`. **Production behaviour is unchanged** when the variable is unset, as in the dashboard. No persistence rule was changed |
| `src/utils/diagnostics.py` | **new** `production_evidence_dir()`, `use_temporary_evidence_dir()` | Points `SITEGUARD_EVIDENCE_DIR` at a fresh temporary folder unless a non-production folder is already set. It never accepts the production folder |
| `scripts/engineering/realtime_eval.py` | module start (line 41–44) | `DIAGNOSTIC_EVIDENCE_DIR = use_temporary_evidence_dir()` |
| `scripts/engineering/measure_r1_r2.py` | module start | same |
| `src/evaluation/live_audit.py` | `run_webcam()` (start) | same call, only in this webcam-replay function |
| `tests/conftest.py` | **new** session fixture `isolate_evidence_storage` | Every test writes evidence to a session temporary folder |
| `tests/conftest.py` | `remove_test_outputs` | **No longer deletes anything in `outputs/evidence/`**; it still cleans only `outputs/videos/` |
| `tests/test_evidence_isolation.py` | **new**, 4 tests | See §3 |

Pre-change copies are in `experiments/camera_quality_audit/fixes/backups/*.before_fix6`.

## 3. Regression tests (`tests/test_evidence_isolation.py`)

| Test | What it proves |
|---|---|
| `test_tests_use_temporary_evidence_storage` | During tests, `EventManager` resolves to the temporary folder, not production |
| `test_diagnostic_replay_script_never_writes_production_evidence` | With the variable **unset**, as when the script runs on its own, importing `realtime_eval.py` redirects evidence. Its real `paced_live_run` then replays 15 dataset frames with no-helmet workers. The test checks that **an evidence image really is written to the temporary folder** (so it is not vacuous) and that **the production folder snapshot (names, sizes, modification times) is unchanged** |
| `test_guard_never_points_at_production_storage` | Even if the variable is set to production, the guard redirects to a temporary folder |
| `test_dashboard_image_flow_keeps_production_evidence_unchanged` | The full dashboard image flow (`AppTest`) creates events whose evidence paths are all in the temporary folder; production is unchanged |

## 4. Results

| Measurement | Before | After |
|---|---|---|
| Full suite | 166 passed | **170 passed** in 18.8 s (166 + 4 new) |
| Files written to `outputs/evidence/` by a full test run | written, then deleted at teardown | **0**. The listing (name, size, modification time) of all 131 production files is identical before and after the full suite |
| Diagnostic replay evidence | production folder | a temporary folder (`siteguard-diagnostic-evidence-*`) |

Fix 6 affects test and diagnostic paths only, so frame rate, latency, CPU and memory are unaffected. The dashboard code path is unchanged when `SITEGUARD_EVIDENCE_DIR` is unset.

## 5. Rollback

Copy the five `*.before_fix6` files back and delete `src/utils/diagnostics.py` and `tests/test_evidence_isolation.py`. This is not recommended, because it re-introduces the deletion hazard.

## 6. Remaining risk (out of scope; not changed)

`tests/conftest.py::remove_test_outputs` still deletes annotated **videos** created in `outputs/videos/` during a test session. That includes a video the dashboard might write at the same moment. It could be fixed the same way, with a `SITEGUARD_VIDEO_OUTPUT_DIR` override, if approved.
