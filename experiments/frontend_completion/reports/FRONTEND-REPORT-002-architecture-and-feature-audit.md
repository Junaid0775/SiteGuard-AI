# FRONTEND-REPORT-002 — Phase 1: architecture and feature audit

**Status:** PASS (audit complete; defects listed in §5). **Date:** 2026-11-23, 11:15–11:25 IST.

## 1. Files inspected

- `app.py` (all 809 lines).
- `tests/test_app.py` (all).
- `.streamlit/config.toml`.
- `src/detection/{detector.py, model_registry.py, camera_processor.py, image_processor.py, video_processor.py}`: signatures and constants.
- `src/events/{event_manager.py, event_store.py}`: public methods, `REVIEW_STATUSES`, the `SITEGUARD_EVENTS_DB` override.
- `src/reporting/report_generator.py`: `CATEGORY_LABELS`, `DISCLAIMER`, report frames, CSV.
- `src/compliance/compliance_analyzer.py`: `STATUS_LABELS`.
- `experiments/evaluation/trained_best/metrics.json`.
- The collected test list (156 tests in 14 files).

## 2. Architecture

The application is **Streamlit-only**: one Python process, with no separate frontend, API server or build chain.

```
Browser (localhost:8502) ──HTTP/websocket──> Streamlit server: app.py (reruns top-to-bottom on every interaction)
   │                                            ├─ sidebar radio "Navigation" ─> one page_* function per page
   │                                            ├─ get_detector()  [st.cache_resource] -> PPEDetector().load()  (registry: configs/settings.yaml)
   │                                            ├─ get_store()     [st.cache_resource] -> EventStore()  (outputs/siteguard_events.db)
   │                                            ├─ get_analyzer()  -> ComplianceAnalyzer(ComplianceRules)  (thresholds from settings)
   │                                            ├─ Image:  decode_image_bytes -> inspect_image -> EventManager.process (optional) -> add_inspection
   │                                            ├─ Video:  process_video(..., progress=bar) -> EventManager -> add_inspection
   └─ WebRTC (streamlit-webrtc, no STUN/TURN) ──> queued_frames_callback -> LiveFrameProcessor.process_latest (latest-frame policy)
                                                   └─ live stats: @st.fragment(run_every=1 s) -> LiveFrameProcessor.snapshot()
```

**Session state:**
- `st.session_state.cfg` holds the runtime settings, initialised by `default_cfg()` from `configs/settings.yaml`, with the image size taken from the active registry entry.
- It also holds `image_results` (an upload cache that prevents duplicate events on rerun), `last_video`, `live_processor`, `live_key` and `live_was_playing`.

**Styling:**
- `.streamlit/config.toml` defines a light palette and a dark palette (accent `#E8793F` dark / `#C8561F` light). The palette follows the viewer's operating-system theme.
- About 10 lines of inline CSS in `app.py` (`sg-kicker`, `sg-note`).
- `ACCENT = "#D9622B"` and a neutral colour list are hard-coded for Plotly.

**Shared helpers in `app.py`:** `page_header`, `status_badge`, `compliance_panel`, `plotly_style`, `save_inspection` and `settings_signature`. There is no separate component module.

## 3. Feature inventory

| Feature | Status | Source | Data and backend | Existing tests | Needed |
|---|---|---|---|---|---|
| Navigation (8 pages, sidebar radio) | Working | `app.py` (`PAGES`, `PAGE_FUNCTIONS`) | — | `test_page_renders_without_exception` × 8 | Visual |
| Sidebar model status | Working | `app.py` sidebar | `PPEDetector.info()` (key, architecture, size, SHA prefix, device, fallback warning) | registry tests | Visual |
| Overview | Working | `page_overview` | `EventStore.list_events` / `list_inspections`; `experiments/evaluation/trained_best/metrics.json` | render; `test_overview_shows_empty_state_without_data` | Visual and **wording**: totals have no stated time window; validation metrics without split size in the tiles |
| Live Monitoring | Working in code; **physical camera not verifiable headless** | `page_live` | streamlit-webrtc, `LiveFrameProcessor`, `snapshot()` (1 s fragment) | `test_live_page_handles_missing_webrtc_runtime`; `test_frame_sync.py` (13) for R1 and session restart | Visual. Promote the snapshot metrics from a caption to a status panel. Add an explicit state display |
| Image Inspection | Working | `page_image` | `decode_image_bytes` (types jpg/jpeg/png/bmp/webp, ≤ 25 MB, ≤ 8000 px), `inspect_image`, `EventManager` (toggle "Record potential violations as safety events", default on) | `test_image_upload_flow_records_events_and_csv`, `test_invalid_image_upload_shows_error` | Visual, format guidance, "detector confidence" wording |
| Video Inspection | Working | `page_video` | `process_video` with progress callback; types mp4/mov/avi/mkv/m4v; upload ≤ 500 MB (server setting); raw upload deleted after processing | `test_video_upload_flow`, `test_invalid_video_upload_shows_error_state` | Visual, guidance |
| Safety Events | Working | `page_events` | `EventStore.list_events` (filters: category, source, status, date), `update_review_status`, `events_to_csv_bytes`, evidence `st.image` | `test_review_status_update_from_events_page`, CSV caption in the image test | Visual. Status explanation and readable status names |
| CSV export | Working | `page_events` (download button) | `events_to_csv_bytes` | `test_events_csv_report` (unit) | — |
| Evidence display | Working | `page_events` | `evidence_path` per event | `test_evidence_*` | Missing-file message exists |
| Analytics | Working | `page_analytics` | events and inspections | render | Chart titles with time range and axis labels; readable status names |
| Model Evaluation | Working, **incomplete content** | `page_evaluation` | `trained_best/metrics.json` (YOLO26n, "val (official dataset validation split, 200 images)"), Ultralytics plots, training curve, viewpoint experiment | render | Add the accuracy-programme research results (E3, non-selectable) and the limitations, read from the JSON files and the model card |
| Settings / About | Working, but **violates the read-only threshold policy** | `page_settings` | sliders and inputs for thresholds, inference size and event rules, plus a **"Save as defaults" button that writes `configs/settings.yaml`**; model selector over registry entries (only `yolo26n_baseline`) | render | **Functional fix:** make thresholds read-only and remove the write button. Keep the registry-based selector |
| Model loader and fallback | Working | `src/detection/detector.py`, `model_registry.py` | registry in `configs/settings.yaml` | 14 + 6 tests | None |
| `LiveFrameProcessor` | Working | `src/detection/camera_processor.py` | `process_latest`, `snapshot`, `close`, `reset_session` | `test_frame_sync.py`, `test_pipeline_integration.py` | None |
| `EventManager` / `EventStore` | Working | `src/events/` | SQLite; `SITEGUARD_EVENTS_DB` override for tests | `test_events_and_reports.py`, `test_compliance_regression.py` | None |
| Webcam lifecycle | Working in code | `page_live` | STOP: the inspection record is saved, then `processor.close()`; restart creates a new processor and session | frame-sync tests | Verify that the stream stops when leaving the page (browser needed) |

## 4. Constraints from the tests

`tests/test_app.py` drives the real `app.py` with `AppTest`. The redesign must keep the following:

1. **Navigation:** the first sidebar radio is the page navigation, and its values are the 8 page names.
2. **Titles:** each page shows an `st.title` containing its name (the text before " /").
3. **Sidebar:** **no buttons and no images** in the sidebar. `at.button[0]` must be "Analyse video" on the Video page, and `at.get("image")` must contain exactly the original and annotated images on the Image page.
4. **Overview empty state:** an `st.info` containing "No safety events recorded yet".
5. **Live page without a server runtime:** an `st.error` containing "live camera component could not start".
6. **Image page:**
   - `file_uploader[0]` is the image uploader;
   - the metrics "Potential violation", "Compliant evidence" and "Uncertain" are shown;
   - errors read "Cannot read <name>".
7. **Video page:**
   - `number_input[0]` is the stride and `number_input[1]` the maximum frames;
   - `button[0]` is "Analyse video";
   - the metrics are labelled "Frames read", "Frames analysed" and "Events recorded";
   - errors contain "could not be opened" or "no readable frames".
8. **Safety Events page:**
   - a caption reads "N of M events";
   - a selectbox is labelled "Review status";
   - `text_area[0]` holds the notes;
   - the button is labelled "Save review".

These are existing tested behaviours and stay unchanged.

## 5. Defects and gaps

| # | Severity | Finding | Spec reference |
|---|---|---|---|
| D1 | **High (policy)** | The Settings page exposes editable detection, compliance and event thresholds, inference size and live and video processing defaults. "Save as defaults" writes them to `configs/settings.yaml`. Session-level slider changes also alter the thresholds used by Image, Video and Live for that browser session | §5.9, §6.4, test 21; handoff §3.4 |
| D2 | High (policy) | "Inference resolution" can override the model's registry size, against the rule "use `detector.image_size`" | §6.3 |
| D3 | Medium | Overview totals ("Potential violation events", "Frames analysed") have no stated time window or source. The model tiles say "Validation mAP50" without the split size | §5.2, §6.7 |
| D4 | Medium | Model Evaluation lacks the accuracy-programme results and the disclosure of limitations (E3 research result, held-back test context, real-site gap, dark-image weakness, unreviewed labels, single seed, incomplete experiments) | §5.8 |
| D5 | Medium | Live status: the received, rendered and dropped figures and the p95 are inside one long caption. There is no explicit "error" state. The physical-camera test status is not shown | §5.3, §6.5 |
| D6 | Low | Analytics and Overview charts lack a time range in their titles. Review statuses are shown as raw codes (`pending_review`). Axis labels are partly default | §5.7 |
| D7 | Low | The theme follows the operating system: light or dark. The specification asks for a dark industrial design. Plotly colours are hard-coded in several places | §4.1 |
| D8 | Low | Confidence columns are labelled "Confidence", not "Detector confidence" | §6.4 |

**No broken workflow was found.** All 156 tests pass (REPORT-001).

## 6. Architecture decision

**Keep Streamlit and redesign in place.**

**Reasons:**
- Every workflow already works and is tested through `AppTest` against `app.py`.
- A React frontend would need an API layer over the detector, event store and WebRTC pipeline: a second server, a new contract and a build chain. That is exactly what spec §3.3 forbids when it risks the deadline.
- Streamlit 1.67 supports a dark theme in configuration, custom CSS, fragments, dialogs and column layouts. That is enough for a professional dark industrial dashboard.

**Approach:**
1. Add a forced dark theme in `.streamlit/config.toml`.
2. Add a small `src/ui/` package: theme tokens and CSS, a Plotly template, shared presentation components, and a read-only loader for evaluation results.
3. Restyle each `page_*` function in `app.py` without changing any business call.
4. Make Settings read-only (D1, D2).
5. Add the research-results section (D4).

No new dependency is needed.

## 7. Protected-asset check

Nothing was modified in Phase 1, which only read files.

## 8. Next phase

Phase 2: the design system and the file-level implementation plan, including the explicit handling of D1.
