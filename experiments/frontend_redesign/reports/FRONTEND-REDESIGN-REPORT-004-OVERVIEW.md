# FRONTEND-REDESIGN-REPORT-004 — Phase 3: Overview Page

**Status:** Phase 3 complete. Phase 4 (remaining pages) has **not** started.
**Rollback point:** `experiments/frontend_redesign/backups/20261124-phase2/` (`app.py`, `theme.py`, `components.py` as they were after Phase 2).

## 1. Files changed

| File | Lines vs Phase 2 | Change |
|---|---|---|
| `app.py` | 140 | `page_overview` rebuilt; helpers `SOURCE_LABELS`, `REVIEW_TONE`, `_when`; the active-model block moved unchanged into `_active_model_panel()`. **`page_live` is identical to Phase 0** |
| `src/ui/components.py` | 42 | New `icon`, `kpi_card`, `panel_title`, `alert_list`, `camera_frame`, `loading_dots`. All dynamic text is HTML-escaped |
| `src/ui/theme.py` | 66 | CSS for KPI cards, panels (`st-key-sg-panel-*`), alert list, camera-off frame, three-dot animation, and the Overview breakpoints |
| `tests/test_frontend_redesign.py` | +1 test | Four approved KPIs, "Not running", no `%` and no compliance rate, all four shortcut buttons present |

`src/ui/live_video.py` is unchanged. No camera, ML, compliance, threshold, event or database code was touched.

## 2. Layout, matching the reference

1. Header: gold kicker, the real status pill, title, subtitle, and the existing scope line (kept for honesty).
2. **KPI strip** of four cards with icon tiles.
3. **Lower row:**
   - Live site feed: a camera-off frame, the last live session, and Open Live Monitoring.
   - Recent alerts: the 5 newest, with View all.
   - A stack of Monitoring activity and System status.
4. **Second row** (existing Overview features, kept): Events by category and Active model with the YOLO26n development metrics.

All four former "Start a task" shortcuts are kept: Open Live Monitoring (feed panel), View all in Safety Events (alerts panel), and Inspect an image / Inspect a video (system panel). Inspections run and frames analysed moved into the System status "Stored records" line, so no information was lost.

## 3. Data-binding audit

Each panel reads only existing data; no new calculation logic was added. Values were checked against direct SQL counts on a copy of the events database.

| Panel | Source | Shown | Database |
|---|---|---|---|
| People detected | `SUM(inspections.person_detections)` | 7,961 | 7,961 |
| Pending review | Events with `review_status = 'pending_review'` | 44 | 44 |
| Potential alerts | `COUNT(events)` | 44 | 44 |
| Camera status | `session_state.live_was_playing`. Leaving Live Monitoring closes the session, so on Overview it is always "Not running" | Not running | Session state |
| Last live session | Newest `inspections` row with `source_type = 'live_camera'` | 24 Nov 2026 15:50 · 159 frames · 2 events | Same row |
| Recent alerts | `list_events().head(5)`: category label, source, time and review status as text | 5 rows | Same rows |
| Monitoring activity | Stored event timestamps counted per day over the last 14 days, zero-filled | Bars | Same counts |
| System status | `model_error()`, `get_detector().info()` (model key, device, 640 px), newest inspection time, stored totals | yolo26n_baseline, mps | Same |

**Truthfulness rules applied:**

- There is no compliance rate, no progress percentage, no hard-coded "Active" and no clock.
- Alert wording stays "Potential …". Icons follow the review status: amber for pending review, red only for reviewer-confirmed events, grey for dismissed or false-positive. The status is always also written as text.
- The feed panel never shows an image. It says the camera is not running and that live video appears on Live Monitoring after START.
- The three-dot indicator (`loading_dots()` and its CSS) exists but is not shown on Overview, because Overview has no real loading operation. It will be attached to real work in Phase 4 (image detection, video processing).

## 4. Tests and evidence

- `.venv/bin/python -m pytest -q` gives **196 passed**.
- An existing test expected the original empty-state message on Overview. The wording was kept exactly, so that test passes unchanged.
- **Screenshots:** `experiments/frontend_redesign/evidence/phase3_overview/`, Overview at 1920 × 1080, 1440 × 900, 1024 × 768, 820 × 1180 and 390 × 844. They use a copy of the events database with evidence images redacted. No server errors occurred.

| Width | Result |
|---|---|
| 1920 | Composition closest to the reference: KPI strip, three-panel row and scene with gold boundary and brand promise |
| 1440 | Same structure; the scene is narrower |
| 1024 / 820 | KPI cards 2 × 2; the feed panel goes full width; alerts and the activity/system stack sit side by side |
| 390 | KPI cards 2 per row; panels stacked; the scene is the darkened top band |

## 5. Integrity

- Events database hash is unchanged (`789bf6cb…`) and only a copy was read.
- There are still 135 evidence files, including your 4 events from 15:49–15:50.
- The models were not touched, and nothing was pushed or deployed.

## 6. Known limitations

- Panels in the lower row have unequal heights; the alerts list is taller than the feed panel.
- At 1440 px the "Monitoring activity" title wraps and the chart is compact. Both are cosmetic and will be tuned in the Phase 5 responsive pass.
- The reference shows illustrative values (for example a 94.2 % compliance rate and "1920 × 1080 · 30 FPS"). These were deliberately not reproduced because the application has no such data.
