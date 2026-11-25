# FRONTEND-REDESIGN-REPORT-006 — Phase 5: Responsive and Accessibility Hardening

**Status:** Phase 5 complete. Phase 6 (regression, performance and integrity audit) has **not** started.
**Rollback point:** `experiments/frontend_redesign/backups/20261124-phase4/` (`app.py`, `theme.py`, `components.py` and the redesign tests as they were after Phase 4).

**Validation method:**
- **Automated audit:** every page at every width listed in the specification (8 pages × 10 widths = 80 views). It measures overflow, clipping and alignment in the browser.
- **Visual review:** representative screenshots.
- **Keyboard test:** real Tab and Arrow key presses.
- **Contrast:** calculated with the WCAG 2.x formula.

All checks used a temporary server with a copy of the events database. No camera was started.

## 1. Files changed

| File | Change |
|---|---|
| `src/ui/theme.py` | 94 changed lines: Phase 5 CSS block, metadata colour token, panel blur removed |
| `tests/test_frontend_redesign.py` | 4 new tests (Section 6) |

`app.py`, `components.py` and `live_video.py` are unchanged. No camera, detection, compliance, event, database, threshold or model code was touched.

## 2. Defects found and fixed

| # | Defect | Where / since | Fix | Verified |
|---|---|---|---|---|
| 1 | **Fullscreen charts, tables and images trapped inside their panel.** The panel blur (`backdrop-filter`) makes a panel the containing block of fixed-position children, so Streamlit's fullscreen view rendered inside the panel box | All panels, since Phase 3 | Blur removed from panels and KPI cards. They sit on the dark overlay, so the visual difference is negligible | Analytics chart fullscreen: 1416 × 414 px at (−154, 459) before, **1416 × 842 px at (12, 46)** after (viewport 1440 × 900) |
| 2 | **White text on the amber primary button: 2.3:1 contrast** (WCAG AA needs 4.5:1) | All primary buttons | Ink text (`#0B1119`), **8.1:1** | Computed button colour in the browser; test |
| 3 | Active navigation label (amber on amber tint): **4.3:1** | Sidebar | Lighter tint (22 % instead of 30 %): **5.1:1** | Test |
| 4 | Metadata text `#778391`: 4.6:1, marginal | KPI footnotes, panel meta, sidebar footer | `#8D98A5`: **6.1:1**; KPI footnote size .72 rem raised to .75 rem | Test |
| 5 | **No visible keyboard focus in the navigation.** The radio circle that showed focus was hidden in Phase 2 | Sidebar, since Phase 2 | Amber 2 px outline on the focused row | Real Tab key: focus ring shown; Arrow Down opened Live Monitoring (`keyboard_focus_navigation_1440.png`) |
| 6 | **Overview "Active model" values cut off** ("0.7", "Precisi"): four tiles of 53 px each | Overview, since Phase 3 | The identity table and metrics stack when the panel is narrow, and metric rows go to two tiles per row | Audit: no cut metric at any width |
| 7 | KPI cards of unequal height, overlapping the next row by 14 px (Streamlit pulls markdown up by 1 rem) | Overview | Equal heights; markdown margin reset | Height difference 0 px and gap 16 px at every width |
| 8 | Panels side by side with unequal heights | Overview, Safety Events, Settings, Analytics, Video | The last panel of each column fills the row height | Panel bottom difference **0 px in all 80 views** |
| 9 | Metric tiles one per row on phones (very long pages) and unequal tile heights | Safety Events, Analytics, Model Evaluation, Video, Image | Metric rows switch to two tiles per row when the row is ≤ 640 px; tiles in a row have equal height | Audit and screenshots at 820–360 |
| 10 | **Horizontal page overflow of 35–434 px** at ≤ 1024 px: two plots are requested at a fixed 760 px, and their flex container kept that width | Model Evaluation | Image container `min-width: 0`, so images scale down | Page overflow 0 at all widths |
| 11 | Metric delta text cut ("+0.040 vs frontal") | Model Evaluation, phones | Deltas wrap | Audit |
| 12 | Selected event ID and review status cut in the narrow review column | Safety Events, 820 px | Rows of panels stack when the viewport is ≤ 1000 px | Audit |
| 13 | "Record events" label clipped | Video Inspection, 820 px | Settings row goes one control per line at 769–1000 px | Audit |
| 14 | Date range cut ("2026/11/19 – 2026/11") | Safety Events, 1440 and 820 px | Wider date column at ≥ 1200 px; a full row on tablets | Screenshot |
| 15 | Settings tables wider than their columns | Settings, 820 px | Stacked by the rule in #12 | Audit |
| 16 | Chart titles cut on phones (Plotly SVG text cannot wrap) | Model Evaluation, Analytics | Chart titles 12 px below 768 px | Screenshot at 360 px |
| 17 | Panel meta text squeezing the title ("Monitoring activity" wrapping) | Overview, 1440 px | The meta text moves below the title when space is short | Screenshot |
| 18 | Touch targets under 44 px | Phones | Buttons and navigation rows at least 44 px high | Smallest button measured at 44 px at 430, 390 and 360 px |
| 19 | 3 rem side padding kept on tablets after the scene disappears | 768–1100 px | 1.5 rem, giving 48 px more content width | Screenshot |

## 3. Viewport test matrix

All 8 pages were audited at each width (80 views). "Overflow" and "Clipping" are measured in the browser: page scroll width, cut text, cut input values, cut metric tiles, elements beyond the viewport, and elements outside their panel.

| Width | Overflow | Clipping | Sidebar | KPI cards | Rows of panels | Metric rows | Scene | Gold boundary | Brand promise | Live video column |
|---|---|---|---|---|---|---|---|---|---|---|
| 1920 | None | None* | Open, 300 px | 4 in a row | Side by side | Single row | Right side, `cover` | 492 px | Shown | 680 px |
| 1600 | None | None* | Open | 4 in a row | Side by side | Single row | Right side | 300 px | Shown | 595 px |
| 1440 | None | None* | Open | 4 in a row | Side by side | Single row | Right side | 204 px | Hidden (< 1500) | 552 px |
| 1280 | None | None* | Open | 4 in a row | Side by side | Single row | Narrow strip | 108 px | Hidden | 509 px |
| 1024 | None | None* | Open | 2 × 2 | Side by side | Single row | Faint full background | Hidden | Hidden | 676 px (status panel below) |
| 820 | None | None* | Open | 2 × 2 | **Stacked** | 2 per row | Faint full background | Hidden | Hidden | 472 px |
| 768 | None | None* | Collapsed (menu button) | 2 × 2 | Stacked | Single row or 2 per row | Faint full background | Hidden | Hidden | 719 px |
| 430 | None | None* | Collapsed | 2 per row | Stacked | 2 per row | Dark top band (`auto 290px`) | Hidden | Hidden | 398 px |
| 390 | None | None* | Collapsed | 2 per row | Stacked | 2 per row | Dark top band | Hidden | Hidden | 358 px |
| 360 | None | None* | Collapsed | 2 per row | Stacked | 2 per row | Dark top band | Hidden | Hidden | 328 px |

\* Except the accepted Settings model-selector truncation (Section 5, item 1).

**Measured at every width and page:**
- KPI, metric and panel height differences within a row: 0 px.
- Gap between the KPI row and the next row: 16 px.
- One `h1` per page.
- No icon-only control without an accessible label.

**Three-dot loading indicator:** visible at 1440 px (Phase 4) and 360 px (`spinner_three_dots_360.png`). With reduced motion requested, the computed animation is `none`. The CSS does not depend on width.

**Video aspect ratio:** the Live video keeps its aspect ratio and is scaled, never cropped (camera Fix 3, unchanged). It was **not re-tested with a running camera**, because camera tests are outside this task.

## 4. Accessibility checks

| Requirement (spec §6.5) | Result |
|---|---|
| Sufficient contrast | All text tokens ≥ 4.5:1 after fixes 2–4: ivory 15.7, muted 8.7, metadata 6.1, captions 6.3, primary button 8.1, active navigation 5.1. Status colours as non-text ≥ 3:1: warn 7.9, critical 4.6, ok 5.9 |
| Colour not the only cue | Every status is also written as text (alerts, badges, pills) |
| Labels for icon-only controls | 0 unlabelled controls in 80 views |
| Visible keyboard focus | Tab walk on Overview and Safety Events: every stop shows an indicator. Navigation fixed (#5). Dataframe cells draw their focus ring on the grid canvas, which a CSS check cannot detect |
| Semantic headings | One `h1` per page. Sections use `h3` (`st.subheader`), so `h2` is skipped. Unchanged from before the redesign |
| Reduced motion | Spinner dots and all CSS animations stop |
| Zoom | 200 % zoom on a 1440-px window behaves like a 720-px viewport. That layout is covered by the 768-px and 430-px checks; 200 % zoom itself was **not captured separately** |
| No tiny text for critical safety information | Potential-violation titles 0.9 rem and status pill 0.78 rem. Footnotes and metadata (0.74–0.76 rem) carry no critical information |

## 5. Accepted limitations

1. **Settings, "Active model" selector:** the long description is shortened with an ellipsis, which is standard selector behaviour. The model key (`yolo26n_baseline`) stays visible, and the full text is in the dropdown and the identity table below.
2. **Images have no `alt` attribute:** Streamlit 1.67 has no alt-text parameter for `st.image`. Each of the three images (the evidence frame and two evaluation plots) has a visible caption next to it.
3. **Tab bars on phones scroll sideways** (Model Evaluation). This is Streamlit's standard tab list.
4. **Live video narrower than the stream** at 1440 px (552 px) and 1280 px (509 px). This is still your open decision on narrowing the scene on Live Monitoring only. The video scales down and is never cropped.
5. **Stretched panels:** with equal heights, shorter panels (for example the Live site feed on Overview) now have empty space at the bottom.
6. **Audit false positive:** a hidden date-picker helper input was flagged outside its panel and excluded.

## 6. Tests

`.venv/bin/python -m pytest -q` gives **204 passed** (200 after Phase 4, plus 4 new):

1. Text colour contrast meets WCAG AA: metadata, primary button and active navigation, calculated from the tokens.
2. The navigation has a visible keyboard focus rule.
3. No `backdrop-filter` is used (fullscreen must not be trapped), and containment is limited to the two blocks that hold only metric tiles or the model table.
4. Narrow-layout rules are present: metric-row wrapping, image container, panel stacking, 44 px touch targets.

## 7. Evidence

`experiments/frontend_redesign/evidence/phase5_responsive/` holds:
- **80 screenshots:** 8 pages × 1920, 1600, 1440, 1280, 1024, 820, 768, 430, 390 and 360 px; JPEG with images redacted.
- **`audit_results.json`:** every measurement for each view.
- **`keyboard_focus_navigation_1440.png`.**
- **`spinner_three_dots_360.png`.**

## 8. Integrity

- **Production events database:** hash unchanged (`789bf6cb…`).
- **`outputs/evidence/`:** 135 files (no new files; your 4 camera events untouched).
- **YOLO26n:** hash unchanged (`890dc61f…`).
- **`static/`:** holds only the approved background.
- **Port 8502:** your dashboard was not touched. Temporary servers ran on localhost only and are stopped.
- **Not done:** no push, no deployment.
