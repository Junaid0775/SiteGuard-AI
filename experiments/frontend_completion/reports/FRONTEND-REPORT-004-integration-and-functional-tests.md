# FRONTEND-REPORT-004 — Phase 4: integration and functional testing

**Status:** PASS for every check that can run without the physical camera. The live start/stop with a real camera is **BLOCKED**, pending the owner's approval (spec §7.3). **Date:** 2026-11-23, 11:15–11:26 IST.

## 1. What was implemented (Phase 3, summarised; details in REPORT-006)

**Files:**

| File | Purpose |
|---|---|
| `app.py` | Rewritten presentation. Same backend calls. Pre-change copy in `backups/20261123-phase0/app.py` |
| `src/ui/theme.py` | Design tokens, CSS, Plotly styling |
| `src/ui/components.py` | Shared presentation components |
| `src/ui/evaluation_data.py` | Read-only loaders for the evaluation results |
| `.streamlit/config.toml` | Forced dark theme; `client.toolbarMode = "minimal"` removes the developer menu and the **Deploy** button |
| `tests/test_frontend_ui.py` | 10 new tests |

**Behaviour changes (all recorded):**
1. **Settings are read-only.** The threshold, inference-size, event and processing widgets are gone, and so is "Save as defaults", which wrote `configs/settings.yaml`. Mandated by spec §5.9 and §6.4 and handoff §3.4.
2. **Inference image size** now comes from `detector.image_size` (handoff §3.3).
3. **Live cleanup:** an open live session is saved (if it analysed frames) and closed when another page is shown.
4. **Deep links:** `?page=<name>` opens a page and keeps it on browser reload.
5. **Model-loading errors:** a `KeyError` or `ValueError` from model construction (for example a mistyped `SITEGUARD_MODEL`) now shows a blocking error instead of a crash. This is UI only; `src/detection/` is unchanged.
6. **Shortcuts:** the Overview has shortcut buttons for the main workflows.

## 2. Regression suite

| Run | Command | Result |
|---|---|---|
| Before the frontend changes (Phase 0, 11:07) | `.venv/bin/python -m pytest -q -p no:cacheprovider` | **156 passed**, 0 failed, 0 skipped |
| After the frontend changes (11:25) | same | **166 passed**, 0 failed, 0 skipped (156 existing + 10 new); `logs/phase4_pytest_full.txt` |

- **Unchanged tests:** no existing test was changed, weakened or removed.
- **One test fix:** the first run of the new test file had 1 failure in my own new test. `AppTest` returns a selectbox's formatted labels, not its raw keys, so the assertion was corrected to compare the key part. This was a test-construction error, not an application defect.

## 3. Functional checks (spec §7.2)

| # | Check | Method and evidence | Status |
|---|---|---|---|
| 1 | Application starts with the documented command | `.venv/bin/streamlit run app.py --server.port 8599 …`: health `ok` in 2 s; restarted 3 times (`logs/phase4_server_8599.log`, `logs/phase5_server_8599.log`) | PASS |
| 2 | Navigation between pages | `test_page_renders_without_exception` × 8; `test_viewing_every_page_writes_nothing_to_the_events_database`; screenshots of all 8 pages via `?page=` | PASS |
| 3 | Overview with real data and with empty data | Screenshot `01_overview_1440x900.png` (real local database: 33 events, 6 inspections); `test_overview_shows_empty_state_without_data` | PASS |
| 4 | Image inspection, valid image | `test_image_upload_flow_records_events_and_csv` (dataset val image, temporary database): 2 images, the 3 compliance metrics, events recorded once, no duplicate on rerun | PASS |
| 5 | Image inspection, invalid or corrupt input | `test_invalid_image_upload_shows_error` ("Cannot read broken.jpg: …") | PASS |
| 6 | Video inspection, supported video | `test_video_upload_flow` (`data/test_media/test_site_clip.mp4`, 60 frames, all analysed, events equal to the stored count) | PASS |
| 7 | Video inspection, unsupported or corrupt input | `test_invalid_video_upload_shows_error_state` | PASS |
| 8 | Live monitoring start and stop | **Physical camera not used.** It needs the owner's explicit approval. The START control renders and the camera does not start on page load (screenshots `02_live_monitoring_*`). Without a server runtime the page reports a clear error (`test_live_page_handles_missing_webrtc_runtime`). The start/stop code path is unchanged from the tested engineering version | **BLOCKED** (pending approval) |
| 9 | Live cleanup releases resources | Server side: `test_leaving_the_live_page_closes_the_live_session` (new). The processor is removed and closed when navigating away. A closed processor returns raw frames only (`camera_processor.py`). STOP keeps the existing save-and-close path. Browser-side release of the camera needs a real camera | PASS (server side); browser side **BLOCKED** |
| 10 | Live metrics reflect `snapshot()` | The status panel reads `received_fps`, `analysed_fps`, `rendered_fps`, `frames_dropped_queue`, `inference_ms.p95`, `errors`, `session_id` and `inference_imgsz` directly from `LiveFrameProcessor.snapshot()` (code review). `test_frame_sync.py` (13) covers the snapshot values. Live values with a camera: not run | PASS (static) |
| 11 | No stale boxes on newer frames | `test_frame_sync.py`: `test_video_output_frames_only_carry_their_own_boxes`, `test_camera_restart_discards_old_session_results` (existing, passing). The live callback is unchanged | PASS |
| 12 | Safety events show persisted data | Screenshot `05_safety_events_1440x900_redacted.png` (real database, 33 events; evidence image hidden for privacy); `test_image_upload_flow…` (caption "N of N events") | PASS |
| 13 | Review actions use only existing APIs | `test_review_status_update_from_events_page` (`EventStore.update_review_status`); new test: no create, merge or delete control | PASS |
| 14 | Analytics with real data and empty data | Screenshot `06_analytics_1440x900.png`; `test_analytics_and_events_show_honest_empty_states` | PASS |
| 15 | Model evaluation wording and sources | `test_model_evaluation_shows_e3_only_as_a_research_result`: "Not promoted", "Not selectable", "160 images … same dataset"; no metric labelled "accuracy"; no button on the page. Screenshots `07_model_evaluation_*` | PASS |
| 16 | YOLO26n active by default | `test_yolo26n_is_the_active_model_by_default`; sidebar `yolo26n_baseline` | PASS |
| 17 | E3 not selectable | `test_model_selector_lists_only_registered_models_and_never_e3`; the registry holds only `yolo26n_baseline`; `test_accuracy_candidate.py::test_not_promoted_candidate_is_never_the_active_model` | PASS |
| 18 | Missing or incompatible model handled | `test_model_loading_failure_blocks_inspection` (blocking error, no upload offered); registry tests for missing, corrupt and wrong-mapping checkpoints (14) | PASS |
| 19 | Fallback status visible | `test_fallback_status_is_visible` (sidebar badge "Fallback model in use" plus a warning with `load_errors`) | PASS |
| 20 | No UI write to the events database except approved APIs | `test_viewing_every_page_writes_nothing_to_the_events_database` (hash unchanged across all 8 pages). Code review: writes happen only through `EventManager.process` (image, video, live), `EventStore.update_review_status` and `EventStore.add_inspection` | PASS |
| 21 | No threshold editing possible | `test_settings_page_has_no_threshold_editing_and_writes_nothing` (no slider, number input, multiselect or save button on Settings; `configs/settings.yaml` hash unchanged) | PASS |
| 22 | CSV export | "Download CSV report" button rendered (screenshot); `events_to_csv_bytes` is unchanged and unit-tested (`test_events_csv_report`, `test_empty_events_csv_has_headers`) | PASS |
| 23 | Stop and restart without corrupting state | The server was stopped (SIGINT or `pkill`) and restarted 3 times. The real database is read-only checked: `PRAGMA integrity_check` = `ok`, 33 events and 6 inspections, modification time still **2026-11-20 21:19:11** (`logs/phase4_events_db_check.txt`) | PASS |

## 4. Camera test (spec §7.3)

**Not run.** The owner has not yet approved it in this phase. Live status everywhere in the UI reads "Physical-camera validation … pending".
- **When approved:** a session of about 30 seconds (2 × 12 s with `scripts/engineering/realtime_eval.py camera`, or START and STOP in the dashboard). Frames are processed locally and are not saved.
- Release of the camera is verified afterwards.

## 5. Performance and stability

- **Model caching:** the model loads once per server process (`st.cache_resource`), and navigation does not reload it. In the server log, model identity is logged once per process.
- **Page timing:** pages render in about 1–3 s in headless Chrome. The screenshot tool waits for the title and then 2.5 s for the charts.
- **Table size:** event tables use Streamlit's virtualised dataframe, so large histories stay responsive. The Overview shows the 8 newest events only.
- **Frame-rate claims:** no frame rate is claimed for E3 beyond the recorded replay (23.7 analysed fps). YOLO26n's 29.8 fps is labelled a replay result.

## 6. Defects found and fixed in Phase 4

| Defect | Fix |
|---|---|
| Page kicker clipped under the Streamlit toolbar | Top padding increased |
| Chart titles and tile labels truncated | Shorter titles with a subtitle line; normal-case metric labels |
| Chart legends overlapping titles | Legends moved below the plots |
| Live status tiles unreadable at 1024 px | Replaced by a compact status table |
| "Deploy" button visible (invites public deployment) | `client.toolbarMode = "minimal"` |
| Confusion-matrix and PR images very large | Fixed width of 760 px with captions |

## 7. Protected assets

- **Events database:** unchanged (§3, item 23).
- **Checkpoints and dataset:** not touched. Verified by integrity manifest in REPORT-006.
- **`configs/settings.yaml`:** unchanged (hash checked by test 21).

**Next:** Phase 5, the visual review.
