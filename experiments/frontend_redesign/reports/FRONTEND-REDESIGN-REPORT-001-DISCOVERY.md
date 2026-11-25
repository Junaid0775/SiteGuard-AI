# FRONTEND-REDESIGN-REPORT-001 — Phase 0: Discovery and Baseline

**Specification:** SiteGuard AI Reference-Locked Frontend Master Specification, received in chat on 24 November 2026. It is not yet saved in the project root.
**Reference image:** `experiments/frontend_redesign/reference/approved_reference_2047x331.png` (2047 × 331 px, copied unchanged).
**Status:** Phase 0 complete. **No implementation file was changed.** Phase 1 waits for the decisions in Section 9.

## 1. Repository inventory

| Item | Finding |
|---|---|
| Entry point | `app.py` (single Streamlit script, about 1,100 lines). Pages are functions in `PAGE_FUNCTIONS`, selected by a sidebar `st.radio` (key `nav`), with `?page=` deep links |
| Shared UI | `src/ui/theme.py` (one CSS block injected with `st.markdown` on every run, plus Plotly styling `style_fig`), `src/ui/components.py` (`page_header`, `kv_table`, `empty_state`, `advisory`, badges, model status), `src/ui/evaluation_data.py`, `src/ui/live_video.py` (camera transport settings and start guard; **protected**) |
| Theme config | `.streamlit/config.toml`: dark theme, accent `#E07A3F`, `toolbarMode = "minimal"`, no static file serving |
| Static assets | **None.** There are no `assets/` or `static/` folders and no UI images outside datasets, outputs and experiments |
| Versions | Streamlit 1.67.0, streamlit-webrtc 0.79.1, aiortc 1.16.0, Plotly 7.1.0, pandas 3.1.1, Ultralytics 8.4.215, torch 2.15.0 |
| Version control | **Not a Git repository.** Rollback relies on file backups |
| Start command | `.venv/bin/streamlit run app.py --server.port 8502` (README). Port 8502 is in use by PID 61252, started 23 Nov 11:46, which predates all camera fixes. Port 8501 is in use by another project (not touched) |

## 2. Pages and functions (all must be preserved)

| Page | Current content |
|---|---|
| Overview | Scope line; 5 metrics (potential events, pending review, inspections run, frames analysed, person detections); 4 task buttons; recent potential events table; events-by-category chart; active model card |
| Live Monitoring | WebRTC camera (START/STOP, device select), status badge, privacy and bitrate captions, live status fragment (fps, drops, inference, workers, detections, session events). **Camera transport and lifecycle are protected** |
| Image Inspection | Upload or sample image, detection, annotated result, worker table, event creation through the existing pipeline |
| Video Inspection | Upload or sample video, processing with progress, annotated output, events |
| Safety Events | Filters, event table, evidence images, review status |
| Analytics | Charts from stored events and inspections |
| Model Evaluation | Stored metrics of YOLO26n; E3 shown as experimental only |
| Settings / About | Read-only settings, model identity, software versions, disclaimers |

## 3. Baseline evidence

- **Tests:** `.venv/bin/python -m pytest -q` gives **189 passed** (19.1 s).
- **Screenshots:** 24 files in `experiments/frontend_redesign/evidence/baseline/` covering 8 pages × 3 viewports (1440 × 900, 1024 × 768, 390 × 844). They were taken from a temporary copy of the events database on a separate port (8613), with evidence images redacted. No camera was started and the production database was not opened for writing.
- **Data state:** 135 evidence files. The events database was last modified 24 Nov 15:50:20, by 4 live-camera events at 15:49–15:50 written by the dashboard running on port 8502 (your session, not this work).
- **Rollback point:** `experiments/frontend_redesign/backups/20261124-phase0/` holds `app.py`, `theme.py`, `components.py`, `live_video.py` and `config.toml`.

## 4. Gap analysis against the reference

| Reference element | Current state |
|---|---|
| Graphite/navy and gold palette | Charcoal and orange (`#E07A3F`); close, so the tokens need retuning |
| Cinematic construction scene and angular gold boundary | Absent; needs a licensed image asset (Section 9, decision 1) |
| Sidebar brand, icons and amber active state | Brand block exists; navigation is plain radio buttons without icons |
| Header with system status and time | Kicker, title and caption only |
| Four KPI cards with icons | Five plain `st.metric` cards with different metrics |
| Live site feed on Overview | Camera exists only on Live Monitoring (decision 2) |
| Recent alerts list | Recent events table (same data, different presentation) |
| Monitoring activity bars | Category bar chart; event timestamps exist for a time chart |
| System processing panel | Absent; no measurable progress exists (decision 5) |
| Three-dot loading indicator | Absent; Streamlit spinners are used |

## 5. Protected files (must not change)

`models/**`, `../construction-ppe/**`, `data/**`, `experiments/**` results, `outputs/**` (database, evidence, reports), `configs/settings.yaml` (thresholds), `src/detection/**`, `src/compliance/**`, `src/events/**`, `src/evaluation/**`, `src/training/**`, `src/utils/**`, and `src/ui/live_video.py`. In `app.py`, the `webrtc_streamer(...)` call, the guard calls around it, the `queued_frames_callback`, and the live session save and close logic are protected.

## 6. Expected change plan (Phases 2–4)

| File | Planned change |
|---|---|
| `src/ui/theme.py` | New design tokens and CSS: shell, scenery layer, gold boundary, sidebar, cards, tables, inputs, three-dot loader, breakpoints |
| `src/ui/components.py` | New presentation helpers: KPI card, alert list, panel, status pill, loading dots, page header with status |
| `app.py` | Presentation only: page layouts, headers, sidebar markup and Overview composition. No change to data sources, logic or the camera block |
| `.streamlit/config.toml` | Palette tokens; `enableStaticServing = true` if decision 4 is approved |
| `static/` (new) | The approved scenic image, optimised (WebP) |
| `tests/test_frontend_redesign.py` (new) | Page rendering, KPI data binding, no-fake-data checks |

## 7. Risk register

| Risk | Mitigation |
|---|---|
| CSS tied to Streamlit internal `data-testid` selectors breaks on upgrade | Use `st-key-*` container classes and documented test IDs; Streamlit is pinned at 1.67.0 |
| A large background image re-sent on every rerun (base64 in CSS) | Serve it once as a cached static file (decision 4) |
| Scenery reduces text contrast | Dark gradient overlay; opaque panels over the image; contrast checks in Phase 5 |
| Overview redesign implies data that does not exist (compliance rate, live people count) | Bind only existing values; otherwise show "not available" (decision 3) |
| Visual changes disturb the camera page | The camera block stays untouched; regression scenarios from the camera work are rerun |
| No Git | File backups per phase |

## 8. Feasibility in Streamlit

The reference layout is achievable without a framework change. The sidebar, the fixed scenery layer (CSS on the app container with a pseudo-element for the gold boundary, `pointer-events: none`), the card grid (`st.columns` inside keyed containers) and the loading dots (HTML/CSS) can all be built in Streamlit. On narrow screens the scenery becomes a darkened top band, and Streamlit's own collapsible sidebar provides mobile navigation.

## 9. Decisions needed before Phase 1

1. **Scenic image (blocker).** The project has no licensed construction-at-dusk image, and the reference screenshot is too small (331 px high) to reuse. Please provide one image you are entitled to use (at least 1600 px high), or approve a specific licensed source.
2. **Live site feed on Overview.** The camera runs only on Live Monitoring, and leaving that page closes the session (protected lifecycle). **Recommended:** the Overview feed panel shows the true camera state, the last live-session summary and an "Open Live Monitoring" action. The alternative, a camera embedded on Overview, changes the camera lifecycle and needs separate approval.
3. **KPI mapping.** People Detected maps to the existing stored person-detection total. Potential Alerts maps to the potential events count. Camera Status shows the true state, which is "Not running" whenever you are on Overview. **Compliance Rate has no existing metric**, and computing one would be new logic. **Recommended:** replace it with the existing "Pending review" count.
4. **Static file serving.** **Recommended:** enable `server.enableStaticServing` so the scenic image is cached by the browser instead of resent on every rerun.
5. **System processing panel.** **Recommended:** a truthful status panel (model loaded, device, last inspection time) with no percentage bar.
