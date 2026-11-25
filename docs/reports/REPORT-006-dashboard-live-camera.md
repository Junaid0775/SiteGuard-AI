# REPORT-006 — Streamlit Dashboard and Live Camera

**Date:** 2026-11-19 **Status:** Complete, except the manual browser-webcam check (see I)

## A. Task summary

- **Requested:** a professional dashboard with 8 sections (Overview, Live Monitoring, Image, Video, Safety Events, Analytics, Model Evaluation, Settings/About), real data only, light/dark support, a restrained orange accent and a live webcam via streamlit-webrtc.
- **Done:** all 8 pages. Every number comes from the SQLite database or real evaluation files, and empty states are shown when no data exists.
- **Completion:** partial on one point. The webcam *processing* is tested automatically, but the *browser camera* still needs a person to click START and grant permission.

## B. Technical implementation

- **`app.py`:** a sidebar radio for navigation and cached resources (`get_detector`, `get_store`). Session-level settings (`st.session_state.cfg`) are initialised from `configs/settings.yaml`, and **Save as defaults** writes them back.
- **Theme:** `.streamlit/config.toml` defines `[theme.light]` and `[theme.dark]` palettes (neutral backgrounds, orange `#C8561F` / `#E8793F` primary). Streamlit follows the system setting and can be switched under *Settings*. There are no gradients, neon colours or animations. Status colours: red for potential violation, green for compliant evidence, amber for uncertain.
- **Pages:**
  - *Overview:* KPIs, recent events, category chart, model status with real val metrics.
  - *Live:* `webrtc_streamer` in SENDRECV mode with built-in START/STOP, `rtc_configuration={"iceServers": []}` (no external STUN), async processing, and a 1-second auto-refresh `st.fragment` showing frames analysed, inference ms, workers, detections and new events. Permission guidance is shown when the camera is stopped. An inspection record is saved when the camera stops.
  - *Image:* multi-upload, original and annotated images, compliance cards, detection table, JPG download. Results are cached per file hash and settings, so reruns never re-record events.
  - *Video:* stride and frame-limit controls, progress bar, H.264 output player and download. The raw upload is deleted after processing.
  - *Safety Events:* filters (category, source, review status, date), table, CSV download, evidence preview and a review form.
  - *Analytics:* metric definitions, KPIs, detections by class, events by category, events over time (hourly or daily), source × review status.
  - *Model Evaluation:* overall and per-class metrics, confusion matrix, PR curve, training curves and the viewpoint table/chart with caveats.
  - *Settings:* all thresholds, required PPE, cooldown, persistence, video/live sampling, model info, disclaimer.
- **Honesty rules:** "Person detections" is labelled *not unique workers*, and no compliance percentage is shown.
- **Graceful failure:** a missing model gives an error plus `st.stop()`. A WebRTC failure gives an error message instead of a crash.

## C. Files created

| File | Purpose |
|---|---|
| `app.py` | Dashboard |
| `.streamlit/config.toml` | Theme, upload limit (500 MB), usage stats off |
| `tests/test_app.py` | AppTest smoke and flow tests |

## D. Files modified

| File | Change |
|---|---|
| `app.py` | Wrapped `webrtc_streamer` in try/except after AppTest showed that it crashes without a server runtime (`Mock object has no attribute '_session_mgr'`). Added labels for the new viewpoint control groups. |

## E. Commands executed

```bash
.venv/bin/python -m pytest tests/test_app.py -q
.venv/bin/streamlit run app.py --server.port 8502 --server.address localhost
curl -s http://localhost:8502/_stcore/health        # -> ok
```

Port 8501 was already in use by another local project (`472 Project`). That process was left untouched, and SiteGuard runs on **8502**.

## F. Testing and verification

| Test | What | Result |
|---|---|---|
| `test_page_renders_without_exception` ×8 | Every page renders with the trained model loaded | PASS (8/8) |
| `test_live_page_handles_missing_webrtc_runtime` | The Live page shows a clear error, not a crash, without a server runtime | PASS |
| `test_overview_shows_empty_state_without_data` | Empty state shown on a fresh DB | PASS |
| `test_image_upload_flow_records_events_and_csv` | Upload a real val image. Expect 2 images shown, 3 status metrics, events > 0 in the DB, no duplicate events on rerun, the Safety Events page lists them, and 1 inspection record | PASS |
| `test_invalid_image_upload_shows_error` | Corrupt upload produces an error message | PASS |
| `test_video_upload_flow` | Upload the test clip with a 60-frame limit and click Analyse. Expect 60 frames read, 12 analysed, the event metric equal to the DB count, and 1 inspection | PASS |
| `test_review_status_update_from_events_page` | Review form saves `false_positive` and the notes to SQLite | PASS |
| Real server boot | `streamlit run` and `/_stcore/health` | PASS (`ok`, port 8502) |
| `test_live_frame_processor_on_real_frames` | The frame callback logic on real frames (6 frames received, 3 analysed, no error) | PASS |
| Browser webcam (START, permission, live overlay, STOP) | Needs a person at the browser | **NOT RUN** (manual step, see I) |

## G. Model and dataset status

The dashboard uses `models/trained/best.pt`.

## H. Errors and resolutions

| Error | Fix |
|---|---|
| `AttributeError: Mock object has no attribute '_session_mgr'` (streamlit-webrtc under AppTest) | try/except with a user-facing message, plus a dedicated test |
| `Port 8501 is not available` | Another app owns 8501; SiteGuard uses 8502 |
| AppTest element type for `st.image` is `"image"`, not `"imgs"` | Test corrected |

## I. Acceptance criteria

| Criterion | Status |
|---|---|
| Image upload works in the dashboard | PASS (AppTest with a real image) |
| Video processing works in the dashboard | PASS (AppTest with the test clip) |
| Event history and CSV export | PASS |
| No invented statistics | PASS (all values from the DB or eval files; empty states tested) |
| Live webcam works, or a specific blocker is documented | **Blocker:** browser camera permission requires a human. Frame processing is verified automatically. Manual check: open http://localhost:8502, go to *Live Monitoring*, click START, allow the camera, and check that the annotated video, *Frames analysed* and detections update, then click STOP and check for the "Live session saved" message. |

## J. Remaining work

The manual webcam check above.

## K. Next task

Viewpoint experiment and final documentation (REPORT-007).
