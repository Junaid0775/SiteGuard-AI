# FRONTEND-REDESIGN-REPORT-007 — Phase 6: Regression, Performance and Integrity Audit

**Status:** Phase 6 complete. Phase 7 (final handoff) has **not** started.
**Code under audit:** the state after Phase 5. No application file was changed in Phase 6.
**Gate result:** **no unexplained protected-file modification**, so nothing was reverted.

## 1. Automated tests

`.venv/bin/python -m pytest -q` gives **204 passed in 19.7 s**. The Phase 0 baseline was 189 passed in 19.1 s; 15 redesign tests were added and no existing test was changed.

| Category required by the spec | Covered by |
|---|---|
| Existing automated suite | All 204 tests |
| Page navigation | `test_app.py::test_page_renders_without_exception` (all 8 pages); `test_frontend_redesign.py` (all pages render inside the shell) |
| Existing components | `test_frontend_ui.py` (model status, selector, E3 research-only, fallback, model-load failure) |
| Form and control interaction | `test_app.py`: image upload flow with events and CSV, video upload flow, invalid image and video uploads, **Save review** form. `test_frontend_redesign.py`: filters, review section, evaluation sections, model selector |
| Empty states | `test_app.py::test_overview_shows_empty_state_without_data`, `test_frontend_ui.py::test_analytics_and_events_show_honest_empty_states` |
| Responsive | Phase 5 browser audit (80 views, Report 006) and its CSS rule tests |
| Camera UI integration, safe fixtures only | `test_live_start_guard.py` (11), `test_uplink_hints.py` (3), `test_live_audit.py` (13), missing-WebRTC runtime, leaving the Live page closes the session, `page_live` hash lock. **No camera and no WebRTC session was started** |
| Event rendering, non-production fixtures | `test_frontend_ui.py` (temporary databases), `test_frontend_redesign.py` (seeded temporary database), viewing every page writes nothing to the events database |
| CSS and layout regression | `test_frontend_redesign.py`: static whitelist, shell, contrast, focus, fullscreen containment rule, narrow-layout rules |
| Startup and shutdown | Section 4 |

Per file: 15 `test_frontend_redesign`, 15 `test_compliance_regression`, 15 `test_compliance`, 15 `test_app`, 14 `test_model_registry`, 13 `test_resolution_coordinates`, 13 `test_live_audit`, 13 `test_frame_sync`, 13 `test_dataset`, 12 `test_training_overrides`, 11 `test_live_start_guard`, 10 `test_frontend_ui`, 10 `test_events_and_reports`, 8 `test_image_and_model`, 6 `test_accuracy_candidate`, 5 `test_model_loading`, 5 `test_annotation_overlay`, 4 `test_pipeline_integration`, 4 `test_evidence_isolation`, 3 `test_uplink_hints`.

## 2. Protected-file audit

**Method:** list every file modified after the Phase 0 backup was taken (24 Nov 15:32:59) and account for each one. Caches, `.venv` and this programme's own reports, evidence and backups are excluded from the list.

| Protected area | Result |
|---|---|
| Models and checkpoints | Unchanged. YOLO26n `890dc61f…`, E3 candidate `590d7d6e…`; the newest file under `models/` is from 23 Nov 03:15 |
| Dataset `../construction-ppe/` | 0 files modified |
| Inference, compliance, events, evaluation, training and utility code (`src/` except `src/ui/`) | 0 files modified |
| Thresholds (`configs/settings.yaml`, `configs/dataset.yaml`) | Unchanged since 22 Nov and 19 Nov |
| Event persistence (`src/events/`) | Unchanged |
| Database schema and data | `outputs/siteguard_events.db` last written 24 Nov 15:50:20 by your dashboard on port 8502 (your 4 live events, recorded in the Phase 0 report). Hash `789bf6cb…` unchanged through Phases 1–6 |
| Evidence files | 135 files. The newest 4 (15:49–15:50) are your live events, and none were created by this programme |
| Camera and WebRTC transport and lifecycle | `src/ui/live_video.py` identical to the Phase 0 backup. `page_live` byte-identical (hash test). `webrtc_streamer` arguments unchanged |
| Dependencies | `requirements.txt` unchanged (19 Nov). No package installed or updated in `.venv` since Phase 0 |
| Configuration | `.streamlit/config.toml` changed in Phase 2 as approved: palette colours, `address = "localhost"`, `enableStaticServing = true`. No other key changed |

**Every modified file accounted for:**

| Files | Explanation |
|---|---|
| `app.py`, `src/ui/theme.py`, `src/ui/components.py`, `tests/test_frontend_redesign.py`, `.streamlit/config.toml`, `static/siteguard_background.webp`, `assets/images/` (original PNG and `PROVENANCE.md`), `docs/frontend_redesign/` | Approved redesign work, Phases 1–5 |
| `tests/test_uplink_hints.py`, `experiments/camera_quality_audit/logs/…`, `CAMERA-FIX-FINAL-REPORT.md` (15:32–15:39) | Final steps of the approved camera-fix programme, which finished while Phase 0 began |
| `outputs/siteguard_events.db` and 4 evidence images (15:49–15:50), `experiments/frontend_completion/logs/dashboard_8502.log` | Written by your running dashboard on port 8502 |
| `outputs/logs/siteguard_app.log` | Append-only application log. Every app process adds a model-load line, including test runs and the temporary servers |
| `data/generated/dataset_resolved.yaml` | Generated file ("do not edit by hand"), rewritten by the existing dataset tests. Content checked: mirror path and the 12 classes in the fixed order |
| `.ultralytics/Ultralytics/settings.json` | Ultralytics runtime settings, rewritten on model load (`sync: false`) |

### 2.1 `app.py`: presentation-only proof

Both versions of `app.py` (Phase 0 and now) were parsed into syntax trees. Layout-only constructs were then removed from both:
- `st.container` and `st.spinner` wrappers;
- `panel_title()` and `st.divider()` calls;
- `enumerate()` used for container keys;
- the colour token name `GOLD`, which was mapped back to `ACCENT`.

After this, **27 of 29 functions are identical to Phase 0**, including every page function except Overview and all data, inspection, review and live-session functions.

| Difference left | Explanation |
|---|---|
| `page_overview` | Rebuilt in Phase 3 as approved. It reads only existing values (audited against the database in Report 004) |
| `_when`, `_active_model_panel` (added) | Date formatting, and the original Overview model block moved unchanged into a function |
| Imports, `NAV_ICONS`, `SOURCE_LABELS`, `REVIEW_TONE` | Display helpers |
| Sidebar | `format_func` adds icons. The navigation values, the `nav` key and the deep links are unchanged. The header status and the footer line are display only |

## 3. Performance comparison

**Method:**
- **Two isolated copies.** One copy runs the Phase 0 frontend (backed-up `app.py`, `theme.py`, `components.py`, `live_video.py` and `config.toml`). The other runs the current frontend. Each has its own copy of the events database and an empty `outputs/` folder. Models, configuration and experiment results are shared read-only.
- **Same conditions.** Both ran in turn on the same machine, under the same headless Chrome (software rendering, 1440 × 900).
- **Interpretation.** The numbers compare the two versions. A normal browser with GPU rendering will be faster in absolute terms.
- **Records.** Raw results are in `evidence/phase6_regression/perf_results.json`; the scripts are in `experiments/frontend_redesign/tools/`.

| Measure | Phase 0 | Now | Assessment |
|---|---|---|---|
| Server start to ready (3 starts) | 0.23–0.28 s | 0.23–0.24 s | Same |
| First render after start (includes model load) | 1.21 s | 0.96 s | Same (within noise) |
| Full page load, median of 8 pages (3 loads each) | 0.23 s (0.17–0.36) | 0.23 s (0.18–0.35) | Same |
| Sidebar page switch, median of 8 pages | 0.11 s | 0.11 s | Same |
| JavaScript heap, median of 8 pages | 60 MB | 57 MB | Same |
| DOM nodes, median of 8 pages | 4,210 | 4,870 | +16 % (panel and card markup) |
| Style work per DOM change (class change plus forced layout) | about 0 ms | 0.3–1.0 ms (Live Monitoring 0.45 ms) | Cost of the `:has()` layout rules. The Live status panel updates once per second, so this is under 1 ms per second |
| Scrolling frame time, p95 / max (Overview, Model Evaluation) | 17 / 18 ms | 17 / 18 ms | 60 fps in both; no dropped frames |
| Main-thread time during a 2 s scroll, Overview | 38 ms | 55 ms | More repainting: the scenic background is fixed |
| Main-thread time during a 2 s scroll, Model Evaluation (longest page) | 107 ms | 308 ms | Same cause; still no dropped frames |
| Live Monitoring idle, main-thread time over 10 s | 54 ms | 89 ms | 0.9 % of one thread |
| Overview full load, data received | 1 KB HTTP + 27 KB WebSocket | 476 KB HTTP (background image) + 63 KB WebSocket | Background image (474 KB); injected CSS grew from 4.0 KB to 23.9 KB per full rerun |
| Server memory (RSS) after visiting all pages | 438 MB | 467 MB | +7 % |

**Spec checklist:**

- **Background is local and not reloaded unnecessarily.**
  - The image is served from `static/` on this computer.
  - Navigating between pages requested it **0 times in 7 page switches**.
  - Three full reloads were served from the browser cache (0 bytes).
  - Streamlit sends an ETag but no `Cache-Control`, and answers a conditional request with a full `200` instead of `304`. After the browser's heuristic cache expires, a full reload therefore downloads the 474 KB again from localhost.
- **Image size optimised.** WebP quality 88 is 474 KB, against 4.74 MB for the PNG (−90 %). The full 2843 × 1600 size keeps the scene sharp on large screens. Phones download the same file.
- **Expensive CSS effects avoided.**
  - The panel blur was removed in Phase 5.
  - The only animation is the loading dots, shown while real work runs.
  - The remaining cost is the fixed background repainting while scrolling (table above). Frames stayed at 60 fps.
- **CPU and memory of custom components.** No custom component was added; all new elements are HTML through `st.markdown`. The WebRTC component predates the redesign, and its code is unchanged.
- **Camera performance not sacrificed.**
  - The camera code path is unchanged: `page_live` and `live_video.py` are identical to Phase 0.
  - Decoration on Live Monitoring is static: no blur, no animation, and an opaque status panel.
  - The measured page costs are idle 0.9 % and 0.45 ms of style work per status update.
  - Streaming itself was **not** measured, because camera tests are excluded from this programme.

## 4. Startup and shutdown

| Check | Phase 0 | Now |
|---|---|---|
| Start to ready, 3 cold starts | 0.23–0.28 s | 0.23–0.24 s |
| Stop (SIGTERM) with no open session, 3 times | 0.40–0.46 s, exit code 0, port released | 0.43–0.45 s, exit code 0, port released |
| Stop after browser sessions (including a Live Monitoring visit) | 11.9 s, exit code 0, port released | 14.4 s, exit code 0, port released |
| Exceptions or tracebacks in server logs (all runs) | 0 | 0 |

Both versions take 12–14 s to stop after browser sessions have been open, so this delay is not caused by the redesign. The current server binds to `localhost` only (Report 003); the temporary copies were also started with `--server.address localhost`.

## 5. Known limitations

1. **Camera streaming was not measured with the redesigned page.** Camera tests are excluded from this programme. Only the page's own costs were measured (idle, style updates, scrolling). A run with Chrome's fake camera (no physical camera, no frames saved) could measure it, but needs your approval.
2. **Headless software rendering.** All timings come from headless Chrome without GPU, so they are valid as a comparison, not as absolute figures.
3. **Scrolling repaint cost.** The fixed scenic background makes scrolling cost more main-thread time (up to 3× on the longest page), still at 60 fps. Moving the scene onto its own fixed layer would remove this. That is a larger CSS change and was not made in this audit phase.
4. **Style work from `:has()` rules.** They add 0.3–1.0 ms per DOM change. Negligible at the Live page's one update per second.
5. **CSS per full rerun.** The injected CSS is 23.9 KB (was 4.0 KB), sent over the local WebSocket on each full rerun, not on status updates. A separate stylesheet would avoid this, but needs a second file in `static/` (whitelist change).
6. **Background caching.** Streamlit's static handler sends no `Cache-Control` and does not return `304`. After the browser's heuristic cache expires, a full reload re-downloads the 474 KB image from this computer. It is never re-requested during in-app navigation.
7. **Server memory** is 29 MB higher (+7 %) after visiting all pages.
8. **Stopping takes 12–14 s** after browser sessions have been open, in both versions.
9. **Runtime files.** Test runs and temporary servers append to `outputs/logs/siteguard_app.log` and rewrite `data/generated/dataset_resolved.yaml` and the Ultralytics settings. This is existing behaviour and none of them is a protected data file.
10. **Still open from earlier phases:**
    - **Live video width:** your decision on the Live Monitoring scene width (video 552 px at 1440 and 509 px at 1280).
    - **Port 8502:** restart the dashboard there; it still runs the pre-redesign code.

## 6. Evidence and tools

- `experiments/frontend_redesign/evidence/phase6_regression/perf_results.json`: raw performance data for both versions.
- `experiments/frontend_redesign/tools/`: the scripts used in Phases 4–6.
  - Browser probe and audit: `p4_probe.py`, `p5_audit.py`, `p5_eval.py`, `audit.js`.
  - Performance harness: `p6_perf.py`.
  - Presentation-only AST check: `ast_audit.py`.
  - They talk only to local servers.
