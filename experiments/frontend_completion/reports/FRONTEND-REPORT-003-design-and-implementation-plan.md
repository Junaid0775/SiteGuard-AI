# FRONTEND-REPORT-003 — Phase 2: design system and implementation plan

**Status:** PASS (plan complete; approval gate checked in §7). **Date:** 2026-11-23, 11:25–11:35 IST.

## 1. Architecture

The application stays in **Streamlit, redesigned in place** (REPORT-002 §6).
- There is no new server, API, build chain or dependency.
- Every page keeps calling the same backend functions it calls today.

## 2. Design tokens

**Dark industrial theme:** charcoal surfaces, one restrained safety-orange accent, and neutral greys.

| Token | Value | Use |
|---|---|---|
| `bg` | `#121417` | page background |
| `surface` | `#1A1E23` | sidebar, cards, inputs (Streamlit `secondaryBackgroundColor`) |
| `surface-2` | `#222830` | table headers, raised panels |
| `border` | `#2E353E` | 1 px borders, dividers |
| `text` | `#E4E6E8` | body text |
| `muted` | `#9AA3AE` | captions, secondary text |
| `accent` | `#E07A3F` | primary buttons, active navigation, key highlights (only one accent colour) |
| `danger` | `#E5484D` | "Potential violation" (always with its text label) |
| `ok` | `#3FA66B` | "Compliant evidence" (always with its text label) |
| `warn` | `#D9A23B` | "Uncertain", fallback model, pending states (always with text) |
| `info` | `#5B8DEF` | neutral informational badges |

**Typography:**
- Streamlit's bundled sans-serif. No external font downloads, so the app works offline and makes no third-party requests.
- Headings weight 600.
- Tabular numerals for metrics.
- Base radius small (4–6 px). No gradients, glow or glass effects.

**Charts:**
- Plotly with transparent backgrounds and muted grid lines.
- Categorical colours: accent, then neutral steel and blue-grey tones.
- Every chart has a title that states the metric and the time range, plus labelled axes.

## 3. Shared components (new package `src/ui/`)

| Module | Content | Business logic? |
|---|---|---|
| `src/ui/theme.py` | Token constants, the CSS string and `inject_css()`, the Plotly layout helper `style_fig()`, category and status colour maps | None |
| `src/ui/components.py` | `page_header` (keeps `st.title`, which the tests require); `section`; status badges with text; `kpi_row`; `empty_state`; `source_note` (for every aggregate); `model_identity_panel` (from `PPEDetector.info()`); `readonly_table`; `disclaimer` | Presentation only |
| `src/ui/evaluation_data.py` | Read-only loaders for the evaluation JSON and CSV files and the model card, returning `None` when a file is missing. Used only by Model Evaluation and Overview | Reads files; computes nothing |

## 4. Page-by-page plan (`app.py`)

| Page | Changes | Data source (unchanged) |
|---|---|---|
| Shell and sidebar | Forced dark theme; brand block in HTML (no `st.image`, because the tests count images); styled navigation radio with key `nav` (values unchanged); model status block (Active / **Fallback** warning with `load_errors`; key, architecture, size, SHA-256 prefix labelled as a prefix); advisory note. **No buttons in the sidebar** | `PPEDetector.info()` |
| Overview | KPI tiles with an explicit **scope line**: "all stored records, first to last timestamp" (from the data). Pending-review count; review-status breakdown; recent-events table with readable status; events-by-category chart with its time range; active-model panel with **development-set** metrics labelled "original val split = development set, 200 images"; shortcut buttons that switch the navigation; empty states kept, including the tested text "No safety events recorded yet" | `EventStore`, `trained_best/metrics.json` |
| Live Monitoring | Explicit state badge (Stopped / Connecting / Running / Error); a status panel from `snapshot()` with **received, analysed and rendered fps, dropped frames, inference p95, receive-to-render p95 and errors**; session ID and inference size; "Detector confidence" column; physical-camera validation shown as **pending**; advisory text. Camera starts only when the user presses START (unchanged). **Cleanup on navigation:** when another page is shown, an open live processor is saved (if it analysed frames) and closed. A closed processor returns raw frames, never boxes. Tested error text kept | `LiveFrameProcessor` |
| Image Inspection | Format guidance from `SUPPORTED_IMAGE_TYPES`, `MAX_IMAGE_BYTES` and `MAX_IMAGE_SIDE`; explanation of the "record events" toggle; per-file result card (exactly two `st.image` calls: original and annotated); compliance panel with text status badges; "Detector confidence" columns | `decode_image_bytes`, `inspect_image`, `EventManager` |
| Video Inspection | Guidance from `SUPPORTED_VIDEO_TYPES` and the 500 MB server limit; inputs in the same order (stride, maximum frames); same "Analyse video" button; progress bar; result KPIs with the same labels; a note that offline processing time is not a real-time claim | `process_video`, `EventManager` |
| Safety Events | Status legend (event = potential violation; review statuses explained); review-status counts; filters unchanged; table with readable status; CSV download; review form unchanged (labels kept); evidence panel with an explicit "evidence file missing" message | `EventStore` |
| Analytics | Scope line (time range, record counts); charts: events over time, events by category, review-status distribution, events by source, detections by class (summed over analysed frames). Titles, axis labels and empty states. Definitions kept | `EventStore` |
| Model Evaluation | **A.** Active model YOLO26n: development-set metrics, per-class table, plots and training curves (existing), labelled with split and size. **B.** Same-split comparison on the development set (200 images): YOLO26n against the E3 research candidate. **C.** "Research candidate E3, not promoted, not selectable": 160-image held-back test from the same dataset (not real-site footage), headline metrics against targets, missing-PPE recall, runtime replay, gate outcome. **D.** Known limitations. **E.** Viewpoint experiment (existing). No promotion control | `trained_best/metrics.json`, `experiments/accuracy_improvement/evaluation/*/summary.json`, `error_analysis/comparison_dev_vs_E1/comparison.csv`, `qualification/realtime/*.json`, E3 `model_card.json` |
| Settings / About | **Read-only:** detection, compliance, event, video and live settings shown as tables. Sliders, inputs and "Save as defaults" removed. Model section: active model identity with the full SHA-256; the registry-based selector **kept** (it lists only registry entries, today only `yolo26n_baseline`; E3 is not registered); class list; software versions; about; limitations; physical-camera status | `configs/settings.yaml` (read), `ModelRegistry`, `PPEDetector.info()` |

**Handling of D1 and D2 (REPORT-002 §5):**
- **Change:** threshold editing is removed from the UI. The thresholds keep their values: the session configuration is always `default_cfg()` from `configs/settings.yaml`.
- **Mandate:** spec §5.9, §6.4 and test 21, and handoff §3.4. This is not a change to thresholds or compliance logic.
- **Record:** it is a public-behaviour change, recorded here and in REPORT-006.
- Inference calls use `detector.image_size` (handoff §3.3).

**Robustness addition (UI only):**
- **Current behaviour:** a registry key that does not exist (for example a mistyped `SITEGUARD_MODEL`) raises `KeyError` in `PPEDetector()`. The page then crashes.
- **Change:** the UI adapter treats `KeyError` and `ValueError` from model construction like `ModelNotFoundError`, and shows a blocking error.
- `src/detection/` is not changed.

## 5. Files

**Expected to change:**
- `app.py`;
- `.streamlit/config.toml` (dark theme tokens);
- `README.md` (Phase 6);
- new: `src/ui/__init__.py`, `src/ui/theme.py`, `src/ui/components.py`, `src/ui/evaluation_data.py`, `tests/test_frontend_ui.py`;
- reports and evidence under `experiments/frontend_completion/`.

**Explicitly not changed:**
- `configs/settings.yaml` and `configs/dataset.yaml`;
- `src/detection/*`, `src/compliance/*`, `src/events/*`, `src/reporting/*`, `src/training/*`, `src/evaluation/*`;
- all checkpoints and model cards;
- `outputs/` (database, evidence);
- the original dataset;
- `experiments/accuracy_improvement/*`;
- existing tests.

## 6. Testing plan

1. **Existing suite:** 156 tests, which must stay green. The constraints are in REPORT-002 §4.
2. **New tests** in `tests/test_frontend_ui.py`, using `AppTest` with a temporary events database:
   - Settings has no editable threshold widget and no "Save as defaults" button (test 21);
   - the model selector offers only registry keys, and E3 is absent (test 17);
   - the active model shown is `yolo26n_baseline` (test 16);
   - the fallback warning is shown when the detector reports `fallback` (test 19);
   - a blocking error appears when model loading fails (test 18);
   - Model Evaluation shows "not promoted" and the held-back test context, with no button (test 15);
   - visiting every page writes nothing to the events database (test 20);
   - Events and Analytics show readable statuses and honest empty states (tests 12 and 14).
3. **Startup check:** `streamlit run` on port 8599, health check and HTTP 200 (test 1).
4. **Headless screenshots:** captured with the local Chrome in headless mode, if available, for the visual review.
5. **Physical camera:** not run without the owner's approval. The status stays **pending**.

## 7. Approval gate (spec §4.5)

| Does the plan change… | Answer |
|---|---|
| model loading | **No.** Still `PPEDetector()` through `get_detector()`; UI-level error handling only |
| compliance logic | **No.** Same `ComplianceRules` from settings |
| event ownership | **No.** Events only through `EventManager` / `EventStore`; reviews only through `update_review_status` |
| thresholds | **No.** Values unchanged. Editing is removed from the UI, as mandated |
| database schema | **No** |
| protected checkpoints | **No** |

**No approval is needed. Phase 3 proceeds.**
