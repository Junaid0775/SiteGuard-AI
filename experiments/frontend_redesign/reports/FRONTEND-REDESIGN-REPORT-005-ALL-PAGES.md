# FRONTEND-REDESIGN-REPORT-005 — Phase 4: Remaining Pages

**Status:** Phase 4 complete. Phase 5 (responsive and accessibility hardening) has **not** started.
**Rollback point:** `experiments/frontend_redesign/backups/20261124-phase3/` (`app.py`, `theme.py`, `components.py` as they were after Phase 3).
**Validation type:** automated tests, plus headless-browser screenshots from a temporary server that used a copy of the events database and a temporary evidence folder. No camera was started.

## 1. Files changed

| File | Change | Lines vs Phase 3 |
|---|---|---|
| `app.py` | Sections of six pages placed in keyed panels (`st.container(key="sg-panel-…")`). Single-series charts changed from amber to gold. A spinner was added around the existing video-processing call. | 691 raw, but only **53 when indentation is ignored**; most of the diff is re-indentation inside the new `with` blocks |
| `src/ui/theme.py` | Phase 4 CSS: expander, file-uploader and form surfaces, flatter metric tiles inside panels, the Live Monitoring status panel, the three-dot spinner, and wrapping for long values in key/value tables | 37 |
| `src/ui/components.py` | Removed the unused Phase 3 `loading_dots()` helper, which the spinner styling replaces | 5 |
| `tests/test_frontend_redesign.py` | 4 new tests (Section 5) | +4 tests |

**Not changed:**
- `page_live` is byte-identical to the Phase 0 backup, and a new test locks its hash.
- `src/ui/live_video.py` is unchanged.
- No detection, compliance, event, database, threshold or model code was touched.

## 2. Page and function preservation matrix

| Page | Original features (all kept) | Presentation change | Verified by |
|---|---|---|---|
| **Live Monitoring** | START/STOP, device select, status badges, troubleshooting and privacy captions, live status fragment (fps, drops, p95, errors, workers, detections, session events), session save on STOP | **CSS only.** The status column became an opaque panel. It has no blur because it refreshes every second while the camera runs. The video column and the camera component are not styled | Page hash test; screenshots at 1920, 1440, 1024 (status panel stacks under the video, Fix 3) and 390 |
| **Image Inspection** | Uploader (multi-file), format/limit caption, "Record potential violations" toggle, per-image original and annotated images, download, event warning, Compliance analysis and Detections tabs, advisory | "Images to inspect" input panel and one result panel per image. The divider between images was removed, because the panels separate them | Browser run: a dataset validation image was uploaded and processed. The result panel showed both images, download, a 3-event warning, tabs and the compliance table. The detection spinner showed three dots |
| **Video Inspection** | Uploader, caption, "Analyse every Nth frame", "Maximum frames", "Record events", Analyse button, real progress bar, 5 result metrics, sampling caption, annotated video with download, class / worker / event tables, advisory | "Video to analyse" input panel. Annotated-video and tables panels for the result. During processing the existing progress bar is kept, and a spinner (three dots) now runs next to it | New AppTest renders the result section from a stored summary (metrics, missing-video error, title). Screenshots of the input state. **No video was processed in the browser** (see Section 6) |
| **Safety Events** | Status explanation, 5 status metrics, filters (category, source, review status, date range), filtered table, CSV download, event picker, review form (status and notes), evidence image or missing-file message | Filters panel, table panel (count, table, CSV download), review panel and evidence panel | New AppTest (seeded event): three filters, table and review section present. Full-page screenshot |
| **Analytics** | Scope line, metric definitions, 4 metrics, 4 charts (detections by class, events by category, events over time, review status by source), advisory | One panel per chart; single-series bars are gold. "Missing PPE" stays amber as the highlighted series | Full-page screenshot; existing analytics tests |
| **Model Evaluation** | Section 1 (YOLO26n metrics, per-class chart and table, confusion matrix, PR curve and training-curve tabs); 2 (same-split comparison); 3 (E3 research result with "Not promoted / Not selectable / Research result only" badges); 4 (known limitations); 5 (viewpoint experiment) | Each numbered section is one panel; bar series are gold. Wording, numbers and E3 labels are unchanged | New AppTest: sections 1, 2 and 5 present. Full-page screenshot |
| **Settings / About** | Read-only notice; Detection, Events, Compliance rules, and Video and live processing tables; Active model selector with "Use this model"; identity table; class list; About text; software versions; camera validation note; disclaimer | Detection/Events panel, Compliance/processing panel, Model panel, About panel | New AppTest: all five section titles and the Active model selector present. Full-page screenshot |

Controls not clicked on purpose:
- **Save review** would write to the database.
- **Use this model** would write `configs/settings.yaml`.
- **START** would activate the camera.
- **Download** buttons were checked only for presence.

## 3. Three-dot loading indicator

- **Approach:** Streamlit's own spinner icon is hidden and replaced by three gold dots that brighten in sequence. A spinner exists only while real work runs, so the dots never stay on an idle page. No artificial delay was added.
- **Where the dots appear:**
  - "Running detection..." (image inspection, existing spinner).
  - "Analysing video on this computer..." (new spinner around the existing `process_video` call). The real progress bar is unchanged.
  - Streamlit's model-loading spinner.
- **Verified in a browser:**
  - The DOM is `stSpinner > div > [span(stSpinnerIcon), div[role=status]]`. The icon span is hidden and the dots are drawn by `::before`.
  - Screenshot: `evidence/phase4_all_pages/full/spinner_three_dots_1440.png`.
  - With `prefers-reduced-motion: reduce` the computed animation is `none`. A separate rule is needed because `*` does not match pseudo-elements.
- **Removed helper:** the Phase 3 `loading_dots()` helper was never shown and has been removed.

## 4. Issue found and fixed during review

On Settings, the Events table was 424 px wide inside a 376 px column. The long value `outputs/siteguard_events.db` pushed the table past the new panel border and was clipped. This was already the case before Phase 4, but it was invisible without a panel edge.

- Value cells of key/value tables now wrap long values (`overflow-wrap: anywhere` on the value column only).
- Labels keep whole words.
- The fix was re-checked in a browser after restarting the temporary server.

## 5. Tests

`.venv/bin/python -m pytest -q` gives **200 passed** (196 after Phase 3, plus 4 new):

1. `page_live` source hash equals the Phase 0 version (camera lifecycle, start guard and frame callback untouched).
2. The spinner CSS draws three dots and stops animating under reduced motion.
3. Safety Events (seeded event), Model Evaluation and Settings / About keep their controls and section titles inside the new panels.
4. Video Inspection result panels render from a stored summary.

**Rendering cost check:**
- Safety Events and Model Evaluation were timed with and without the panel blur in headless Chrome (software rendering).
- Render time was 0.5 s in both cases and the screenshot took 0.1–0.2 s, so the blur has no measurable cost.
- Some capture runs were briefly slow early in the session (minutes on one page). This could not be reproduced, and the same pages then rendered in 0.5 s.

## 6. Evidence

| Set | Location | Coverage |
|---|---|---|
| Before | `experiments/frontend_redesign/evidence/phase2_after/` | All pages in the shared shell, before Phase 4 page styling (8 pages × 1920, 1440, 1024, 390) |
| After | `experiments/frontend_redesign/evidence/phase4_all_pages/` | 8 pages × 1920 × 1080, 1440 × 900, 1024 × 768, 390 × 844 (32 shots), images redacted |
| Full-page | `experiments/frontend_redesign/evidence/phase4_all_pages/full/` | 1440-wide full-length captures of every page, the Image Inspection result and the spinner |

The Image Inspection result capture is not redacted. It shows only a public validation image from the Construction-PPE dataset (CC BY 4.0) and no private frame.

**Video was not run in the browser.** The app writes annotated videos to the production `outputs/videos/` folder. To avoid creating files there, the video result panels were verified with AppTest instead of a screenshot.

## 7. Integrity

- **Production events database:** hash unchanged (`789bf6cb…`). The upload test wrote 3 events and 1 inspection to the temporary copy only, and 3 evidence images to the temporary folder only.
- **`outputs/evidence/`:** still 135 files (134 images plus `.gitkeep`). There are no new files, and your 4 camera events from 15:49–15:50 are untouched.
- **YOLO26n:** hash unchanged (`890dc61f…`). E3 is still not selectable.
- **`static/`:** holds only `siteguard_background.webp`.
- **Port 8502:** your dashboard was not touched. The temporary server ran on 8616 and bound to localhost only.
- **Not done:** no push, no deployment.

## 8. Remaining inconsistencies (for Phase 5)

1. **Phones (< 640 px):** metric tiles on Safety Events, Analytics, Model Evaluation and Video stack one per row (Streamlit default), which makes long columns. Overview already shows its KPI cards 2 per row.
2. **Unequal panel heights** in two-column rows: Settings (Detection vs Compliance), Safety Events (review vs evidence), and the Overview lower row (from Phase 3).
3. **Date range field** on Safety Events is cut at 1440 px ("2026/11/19 – 2026/11").
4. **Metric label "Confirmed by reviewer"** wraps, so that tile is taller than its neighbours.
5. **Analytics** repeats each chart's subject in both the panel title and the chart title (unchanged wording from before).
6. **Long paths** in key/value tables now wrap mid-word (intended, so they stay inside the panel).
7. **Live Monitoring video column** is still about 550 px wide at 1440 px. This remains your open decision on narrowing the scene on that page only.
8. **The spinner styling depends on Streamlit's spinner DOM.** Streamlit is pinned at 1.67.0; recheck after any upgrade.
9. **Overview at 1440 px** (unchanged in Phase 4; its screenshot is pixel-identical to Phase 3): the KPI footnotes and "Not running" wrap, so the cards differ in height, and the KPI row sits almost against the lower panels.
