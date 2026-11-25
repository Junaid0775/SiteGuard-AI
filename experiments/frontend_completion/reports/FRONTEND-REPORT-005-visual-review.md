# FRONTEND-REPORT-005 — Phase 5: visual refinement, responsive and performance checks

**Status:** PASS. **Date:** 2026-11-23, 11:19–11:32 IST.

## 1. Method

- **Server:** the dashboard ran on `http://127.0.0.1:8599` with the real local data (`.venv/bin/streamlit run app.py --server.port 8599 …`).
- **Capture tool:** pages were captured with the local Google Chrome in headless mode, driven through its DevTools protocol (`experiments/frontend_completion/tools/capture_screenshots.py`). Each page is opened through its `?page=` link, the tool waits for the title, then waits 2.5 s for the charts.
- **Genuine captures:** these are screenshots of the running application, not mock-ups. Nothing was sent anywhere except to the local server.
- **Viewports:**
  - **1440 × 900**, a normal laptop window;
  - **1024 × 768**, a narrow window with the sidebar open.
- **Review crops:** some review images were also taken at 1440 × 1800 or 4200 and cropped to read lower sections. They are in `evidence/review/`.

**Privacy:**
- The Safety Events page shows the evidence frame of the selected event. Most stored events come from earlier live-camera sessions and may show a person.
- That page was therefore captured **only with all images hidden** (files named `_redacted`). Every image I reviewed had images hidden whenever evidence frames could appear.
- No camera was started. In headless Chrome there is no camera, and START was never pressed.

## 2. Evidence (`experiments/frontend_completion/evidence/screenshots/`)

| Page | 1440 × 900 | 1024 × 768 |
|---|---|---|
| Overview | `01_overview_1440x900.png` | `01_overview_1024x768.png` |
| Live Monitoring (camera stopped) | `02_live_monitoring_1440x900.png` | `02_live_monitoring_1024x768.png` |
| Image Inspection (empty state) | `03_image_inspection_1440x900.png` | `03_image_inspection_1024x768.png` |
| Video Inspection (empty state) | `04_video_inspection_1440x900.png` | `04_video_inspection_1024x768.png` |
| Safety Events (images hidden) | `05_safety_events_1440x900_redacted.png` | `05_safety_events_1024x768_redacted.png` |
| Analytics | `06_analytics_1440x900.png` | `06_analytics_1024x768.png` |
| Model Evaluation | `07_model_evaluation_1440x900.png` | `07_model_evaluation_1024x768.png` |
| Settings / About | `08_settings_about_1440x900.png` | `08_settings_about_1024x768.png` |

`01_overview_1440x900_redacted.png` is the first capture of the interim design, taken before the fixes below. It is superseded but kept, because deleting evidence files is avoided.

## 3. Page-by-page review

| Page | What was checked | Result |
|---|---|---|
| Shell and sidebar | Brand block; navigation list with an accent bar on the active page (radio dot kept as a non-colour cue); model status badge; identity line (key, architecture, size, SHA prefix, device); notice. No buttons or images in the sidebar | PASS |
| Overview | Scope line with the data time range and the "zero events is not proof" note; 5 tiles; task shortcuts; recent-events table (5 columns, readable status, detector confidence); category chart with time-range subtitle and axis labels; active-model identity table; development-set metrics with split and size | PASS after fixes |
| Live Monitoring | Stopped / Connecting / Running / Error badge; START and SELECT DEVICE from the component; camera-help text; "frames not saved" note; physical-camera validation shown as **pending**; status table from `snapshot()`; workers, detections and session events; advisory text | PASS after fixes |
| Image Inspection | Formats and limits from code (jpg, jpeg, png, bmp, webp; 25 MB; 8000 px); inference size and model; record toggle with explanation; empty state | PASS |
| Video Inspection | Formats from code (mp4, mov, avi, mkv, m4v); 500 MB limit; the note "offline processing time is not a real-time figure"; inputs in the tested order; empty state | PASS |
| Safety Events | Status explanation; 5 status tiles; filters; "N of M events" caption; readable table; CSV button; review form; badge per event; evidence panel with an explicit missing-file error | PASS |
| Analytics | Scope line; definitions; 4 tiles; 4 charts with title, time-range subtitle, axis titles with units, legends below the plots | PASS after fixes |
| Model Evaluation | YOLO26n development-set tiles with the split described; per-class chart and table; confusion matrix and PR curve at 760 px with captions; same-split comparison table; E3 block with "Not promoted / Not selectable / Research result only" badges, results against targets, 95 % intervals, n per class, the 160-image same-dataset statement; real-scene vs close-up table; replay table labelled as a replay; limitations list; viewpoint experiment | PASS |
| Settings / About | Read-only notice; detection, events, compliance and processing tables with config keys; model selector (1 registered entry, button disabled); identity with the full SHA-256; classes; software versions; camera status; disclaimer | PASS |

## 4. Issues found and corrected

| # | Viewport | Issue | Correction |
|---|---|---|---|
| V1 | both | Page kicker clipped under the toolbar | Top padding 2.0 → 3.4 rem |
| V2 | both | Streamlit "Deploy" button and developer menu visible | `client.toolbarMode = "minimal"` |
| V3 | 1440 | Long chart titles truncated | Short title plus a subtitle line for the time range |
| V4 | 1440 | Tile label "Potential violation events" truncated | Label "Potential events"; full meaning in the help text |
| V5 | both | Legends overlapped chart titles (Analytics) | Legends below the plot, with a larger bottom margin |
| V6 | 1024 | Live status tiles unreadable | Replaced by a compact status table |
| V7 | 1024 | Tile values cut ("3…") and button labels cut ("Live monit…") | CSS: no ellipsis on metric values, labels or buttons; smaller tile font below 1280 px; normal word breaking |
| V8 | both | Confusion-matrix image about 1,000 px tall | Fixed width of 760 px, with captions |
| V9 | both | Uppercase tile labels too wide | Normal-case labels, muted colour |
| V10 | both | `source-*` shown with literal backticks; object count without a thousands separator | Text fixed ("Real-site photos in the dataset (source-*)"; "2,480") |

**Residual, minor:** at 1024 px the help icon of two tiles sits close to their two-line label. It is still readable. The sidebar can be collapsed for more room.

## 5. Placeholder and debug check

- **Content:** no placeholder text, fake numbers or debug widgets. Every figure is read from the database, `configs/settings.yaml`, `PPEDetector.info()` or an evaluation file.
- **Unknown values:** shown as "-" or "Unknown".
- **E3:** shown only inside Model Evaluation, labelled "Not promoted / Not selectable / Research result only". It is never shown as active and never offered in a selector (test 17).

## 6. Performance

- **Server start:** health `ok` about 2 s after launch, and the model loads once per process.
- **Page render:** about 1–3 s in headless Chrome, including the charts.
- **Stability:** no page froze, and no error or exception appeared in the server logs (`logs/phase5_server_8599.log`).
- **Live performance:** not measurable without a camera. See REPORT-004 §4.

## 7. Protected assets

Phase 5 changed only `src/ui/theme.py` (CSS), `app.py` (labels and layout) and `.streamlit/config.toml` (toolbar). Tests after the final change: **166 passed**.

**Next:** Phase 6, documentation and handoff.
