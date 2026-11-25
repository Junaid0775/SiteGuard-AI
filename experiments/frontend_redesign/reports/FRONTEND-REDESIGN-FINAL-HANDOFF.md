# SiteGuard AI: Reference-Locked Frontend Redesign, Final Handoff

**Date:** 24 November 2026
**Specification:** `docs/frontend_redesign/SiteGuard_AI_Reference_Locked_Frontend_Master_Specification.md`
**Reference image:** `experiments/frontend_redesign/reference/approved_reference_2047x331.png`
**Phase reports:** `experiments/frontend_redesign/reports/FRONTEND-REDESIGN-REPORT-001` to `-007`

## Final gate

| Gate condition | Result |
|---|---|
| No critical page broken | All 8 pages render in automated tests and in 80 audited browser views (8 pages × 10 widths) with no overflow, clipping or server error |
| No core workflow missing | Every original feature is kept (Section 2). Upload, inspection, event recording, review, CSV export, model selection and live-session handling are covered by passing tests |
| No unexpected protected-area change | Every file changed since Phase 0 is accounted for (Section 9) |
| No skipped tests | 204 passed, 0 failed, **0 skipped** |

**The redesign is complete**, subject to the known limitations in Section 10. The most important limitation: live camera streaming was not re-tested with the new design, because camera tests were excluded from this programme.

## 1. Implementation summary

| Phase | Result |
|---|---|
| 0 Discovery | Inventory, 24 baseline screenshots, 189 tests passing, rollback backup |
| 1 Design system | Tokens, components and responsive plan. The supplied original scenic image was verified (2843 × 1600) and its provenance recorded. Static-file serving was checked for safety |
| 2 Shared shell | Persistent scenic background (one cached WebP), angular gold boundary, brand promise, navy sidebar with icons and amber active state, real status pill. The server binds to `localhost` only |
| 3 Overview | Four KPI cards (People detected, Pending review, Potential alerts, Camera status), live-site feed panel (true camera state, no fake video), recent alerts, monitoring activity, system status. All values bound to existing data and checked against the database |
| 4 Remaining pages | Panels on all seven other pages. Live Monitoring styled by CSS only (camera code unchanged). Three-dot loading indicator for real work only. Gold chart series |
| 5 Responsive and accessibility | 19 defects fixed, including fullscreen charts trapped inside panels, cut-off metric values, contrast failures, invisible keyboard focus in the navigation, and page overflow on tablets and phones |
| 6 Regression and integrity | Full suite, protected-file audit, proof that `app.py` changes are presentation-only, and a performance comparison with the Phase 0 version |

## 2. Page inventory

| Page | Original functions (all kept) | Redesign |
|---|---|---|
| Overview | Scope line, event and inspection totals, task shortcuts, recent events, events by category, active model and metrics | Four KPI cards, feed panel with last live session and Open Live Monitoring, recent alerts (5), events per day (14 days), system status, category chart, active-model panel |
| Live Monitoring | START/STOP, device selection, status badges, help and privacy captions, live status (fps, drops, p95, errors, workers, detections, session events), session save on STOP | Status column as a panel. **Camera code byte-identical to Phase 0** (locked by a test) |
| Image Inspection | Multi-image upload, record toggle, original and annotated images, download, event warning, compliance and detection tabs | Input panel; one result panel per image; three-dot indicator during detection |
| Video Inspection | Upload, sampling and frame-limit controls, record toggle, Analyse, real progress bar, five result metrics, annotated video and download, tables | Input panel; result panels; three-dot indicator during analysis next to the real progress bar |
| Safety Events | Status explanation, five status metrics, filters, table, CSV export, event picker, review form, evidence image | Filters, table, review and evidence panels |
| Analytics | Scope, definitions, four metrics, four charts | One panel per chart; gold series |
| Model Evaluation | Sections 1–5 (YOLO26n metrics and plots, comparison, E3 research result, limitations, viewpoint study) | One panel per section. E3 remains "Not promoted / Not selectable / Research result only" |
| Settings / About | Read-only thresholds and rules, model selector (registered models only), identity table, classes, About, versions, disclaimer | Four panels |

## 3. File changes

Line counts are against the Phase 0 backup.

| File | Change |
|---|---|
| `app.py` | Modified: +461 / −378 lines, now 1,190. **Presentation only:** 27 of 29 functions are identical to Phase 0 once layout wrappers are removed. The remaining differences are the approved Overview rebuild, two helpers, and display-only sidebar additions (Report 007 §2.1) |
| `src/ui/theme.py` | Modified: +291 / −11, now 419 lines. Tokens, shell CSS, panels, responsive and accessibility rules |
| `src/ui/components.py` | Modified: +47 / −2, now 156 lines. Header status, KPI card, panel title, alert list, camera-off frame |
| `.streamlit/config.toml` | Modified: palette colours, `address = "localhost"`, `enableStaticServing = true` |
| `static/siteguard_background.webp` | Added: 485,612 bytes, 2843 × 1600, derived from the original image. The only file in `static/` (enforced by a test) |
| `assets/images/SiteGuard_AI_Cinematic_Construction_Background_1600h.png`, `assets/images/PROVENANCE.md` | Added: the supplied original image (unchanged) and its provenance |
| `docs/frontend_redesign/SiteGuard_AI_Reference_Locked_Frontend_Master_Specification.md` | Added: copy of the specification |
| `tests/test_frontend_redesign.py` | Added: 15 tests |
| `experiments/frontend_redesign/` | Added: reference image, reports, evidence, backups and audit tools |

**Verified unchanged:**
- `src/ui/live_video.py` and all other code under `src/`.
- `configs/`, `models/`, the dataset, `requirements.txt`.
- The events database and the evidence files.

## 4. Test results

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q` (final run, 24 Nov 2026) | **204 passed, 0 failed, 0 skipped**, 20.4 s |

Phase 0 had 189 tests passing. The 189 existing tests are unchanged and 15 redesign tests were added. They cover:
- the static-file whitelist;
- the original image and its provenance;
- the local-only configuration;
- the shell on every page;
- the Overview KPIs (no compliance rate or fake percentage);
- the Live page code lock;
- the spinner and reduced motion;
- page controls;
- video result panels;
- contrast;
- keyboard focus;
- no fullscreen-trapping CSS;
- narrow-layout rules.

The test categories required by the specification are mapped in Report 007 §1.

## 5. Screenshot evidence index

All screenshots are under `experiments/frontend_redesign/`. Evidence images are hidden (redacted) unless stated.

| Folder | Content |
|---|---|
| `reference/` | Approved reference (2047 × 331) |
| `evidence/baseline/` | Before: 8 pages × 1440, 1024, 390 px (24) |
| `evidence/phase2_after/` | Shared shell: 8 pages × 1920, 1440, 1024, 390 px (32) |
| `evidence/phase3_overview/` | Overview × 1920, 1440, 1024, 820, 390 px (5) |
| `evidence/phase4_all_pages/` | All pages × 1920, 1440, 1024, 390 px (32). `full/` holds full-length pages at 1440 px, an Image Inspection result (public dataset image, not redacted) and the loading indicator (10) |
| `evidence/phase5_responsive/` | 8 pages × 10 widths (80 JPEG), `audit_results.json`, keyboard focus capture, loading indicator at 360 px |
| `evidence/phase6_regression/` | `perf_results.json` (Phase 0 and current measurements) |
| `evidence/phase7_handoff/` | `reference_vs_overview_1920x1080.jpg`: the reference above the redesigned Overview at 16:9 |

## 6. Responsive verification

8 pages were checked at 1920, 1600, 1440, 1280, 1024, 820, 768, 430, 390 and 360 px. Details are in Report 006.

- **Overflow and clipping:** none in any view, except the Settings model selector, which shortens its long description with "…".
- **Heights and spacing:** cards, tiles and side-by-side panels are equal in height (0 px difference), and there is a 16 px gap below the KPI row.
- **Sidebar:** open at 820 px and wider; collapsed behind the menu button at 768 px and below.
- **KPI cards:** 4 in a row at 1200 px and wider; 2 × 2 on tablets; 2 per row on phones.
- **Panels and tiles:** rows of panels stack at 1000 px and below; metric tiles go two per row when narrow.
- **Scene and boundary:**
  - At 1200 px and wider, the scene sits on the right with the gold boundary.
  - At 1500 px and wider, the brand promise is also shown.
  - Between 768 and 1199 px, the scene becomes a faint full background.
  - On phones, it becomes a darkened top band.
- **Loading indicator:** checked at 1440 and 360 px; it stops animating when reduced motion is requested.

## 7. Accessibility

- **Contrast (WCAG AA):** all text tokens are at least 4.5:1 after the Phase 5 fixes:
  - body 15.7:1;
  - secondary text 8.7:1;
  - metadata 6.1:1;
  - primary button 8.1:1 (was 2.3:1);
  - active navigation 5.1:1 (was 4.3:1).
- **Not colour alone:** every status is also written as text.
- **Icon-only controls:** all have an accessible label (0 unlabelled in 80 views).
- **Keyboard focus:** visible on every Tab stop, including the navigation (fixed in Phase 5; checked with real key presses).
- **Headings:** one `h1` per page.
- **Reduced motion:** respected.
- **Touch targets:** buttons and navigation rows at least 44 px high on phones.
- **Critical information:** never in small metadata text.
- **Not met:**
  - Images have no `alt` attribute (Streamlit's `st.image` has no such option); each has a visible caption.
  - Sections use `h3` after the page `h1`, skipping `h2`.

## 8. Performance

Measured against the Phase 0 frontend under identical conditions (headless Chrome, 1440 × 900); details in Report 007 §3.

| Measure | Result |
|---|---|
| Server startup | Same (0.23–0.28 s before, 0.23–0.24 s now) |
| Page load and page switch | Same: median 0.23 s and 0.11 s |
| Scrolling | 60 fps on both, no dropped frames. Main-thread time during scrolling is higher because of the fixed scenic background (up to 3× on the longest page) |
| Memory | JavaScript heap unchanged; server +7 % |
| Background image | 474 KB WebP (the original PNG is 4.7 MB). Never re-requested while moving between pages |
| CSS | 23.9 KB per full rerun (was 4.0 KB) |
| Blur effects | Panel blur removed (it trapped fullscreen views) |
| Custom components | None added |
| Live Monitoring page cost | 0.9 % idle main thread; under 1 ms of style work per status update |

## 9. Protected areas: integrity statement

Every file changed after the Phase 0 backup (24 Nov 15:32:59) was listed and explained (Report 007 §2). None of the following was changed by this programme:

| Area | Evidence |
|---|---|
| YOLO26n checkpoint | SHA-256 `890dc61fd024b247…` |
| E3 research candidate | SHA-256 `590d7d6e8510f3c1…`; still not registered or selectable |
| Dataset `../construction-ppe/` | 0 files modified |
| Inference, compliance, event, evaluation and training code | 0 files modified under `src/` outside `src/ui/` |
| Thresholds and rules | `configs/settings.yaml` unchanged since 22 Nov, `configs/dataset.yaml` since 19 Nov |
| Events database | SHA-256 `789bf6cb3fa567ea…`, last written 24 Nov 15:50:20 by your dashboard on port 8502 (your 4 live events) |
| Evidence images | 135 files; the 4 newest are your live events from 15:49–15:50 |
| Camera and WebRTC | `src/ui/live_video.py` and `page_live` identical to Phase 0 (hash test) |
| Dependencies | `requirements.txt` unchanged; no package installed or updated |

All browser testing used temporary copies of the database and temporary evidence folders. The only exceptions are runtime files that the app and the existing tests always write: the application log, a generated dataset file and the Ultralytics settings (Report 007 §2).

## 10. Known limitations

1. **Live camera not re-validated.**
   - Streaming with the new design was not tested, because camera tests were excluded.
   - The physical-camera validation from the camera programme is still pending.
   - The rare START no-op seen there (2 in about 600 starts) remains an open risk.
2. **Live video width (your open decision).** The Live video column is 552 px at 1440 px and 509 px at 1280 px, below the 640-px stream. The video scales down and is never cropped. Narrowing the scenic background on that page only would give it more room.
3. **Styling differences from the reference.**
   - No glass blur on panels (removed because it broke fullscreen).
   - Rectangular panels rather than chamfered ones.
   - Muted KPI icon tiles rather than bright ones.
4. **Reference values not reproduced on purpose.** These were replaced with real data, as approved:
   - the 94.2 % compliance rate;
   - the "Active" camera status;
   - the clock;
   - the 69 % processing bar;
   - the "1920 × 1080 · 30 FPS" label;
   - the live thumbnail.
5. **Performance trade-offs.**
   - The fixed scenic background raises scrolling cost (still 60 fps).
   - The `:has()` layout rules add under 1 ms per page update.
   - CSS is 23.9 KB per full rerun.
   - Server memory is 7 % higher.
6. **Background caching.** Streamlit's file server sends no caching header and no `304`, so a full browser reload sometimes downloads the background image again from this computer.
7. **Minor display limits.**
   - Settings model selector: the long description is shortened with "…".
   - Images have no `alt` text.
   - Tab bars scroll sideways on phones.
8. **Not tested:**
   - Safari and Firefox (only Chrome was used);
   - a GPU-rendered browser window;
   - 200 % zoom directly (it behaves like the 720-px layout).
9. **Streamlit DOM dependency.** The CSS relies on Streamlit's internal element names and structure. Streamlit is pinned at 1.67.0; recheck the pages after any upgrade.
10. **Slow stop.** Stopping the server can take 12–14 s after browser sessions have been open, the same as before the redesign.

## 11. How to launch

Your current dashboard on port 8502 (PID 61252, started 23 Nov) predates both the camera fixes and this redesign. Stop it first (Section 12), then:

```bash
cd "/Users/junaidahmad/Desktop/471 Project/SiteGuard-AI"
.venv/bin/streamlit run app.py --server.port 8502
```

Open `http://localhost:8502`. The configuration binds the server to this computer only; other devices on the network cannot connect. Port 8501 belongs to another project and was not touched.

## 12. How to stop

- **Started in a terminal:** press `Ctrl+C` in that terminal.
- **Otherwise:**
  1. Find the process: `lsof -ti tcp:8502 -sTCP:LISTEN`.
  2. Stop it: `kill <PID>`.
  3. Check that `lsof -ti tcp:8502 -sTCP:LISTEN` prints nothing. Stopping can take up to about 15 s.

If the camera is running, press **STOP** on Live Monitoring before stopping the server, so the session is saved and the camera is released.

## 13. How to roll back

The backups are plain file copies; the project is not a Git repository.

**Full rollback to the pre-redesign frontend:**

```bash
cd "/Users/junaidahmad/Desktop/471 Project/SiteGuard-AI"
B=experiments/frontend_redesign/backups/20261124-phase0
cp "$B/app.py" app.py
cp "$B/theme.py" "$B/components.py" src/ui/
cp "$B/config.toml" .streamlit/config.toml
mv tests/test_frontend_redesign.py "$B/"   # these tests check the redesign and would fail after a rollback
```

Then restart the app. `.venv/bin/python -m pytest -q` should report 189 passed, the Phase 0 count. This rollback was not executed during the programme, so that number has not been re-checked after a rollback.

> **Security note:** the Phase 0 `config.toml` does not contain `address = "localhost"`. After a rollback, add that line under `[server]`, or start with `--server.address localhost`. Otherwise the app listens on all network interfaces. `static/` can stay; it is not served without `enableStaticServing`.

**Rollback to the end of Phase 4** (before the responsive and accessibility fixes):

```bash
B=experiments/frontend_redesign/backups/20261124-phase4
cp "$B/app.py" app.py
cp "$B/theme.py" "$B/components.py" src/ui/
cp "$B/test_frontend_redesign.py" tests/
```

The Phase 2 and Phase 3 backups hold `app.py`, `theme.py` and `components.py` from those points. Use them only for reference: the later tests would fail against them.

## 14. Nothing pushed or deployed

- **No push:** the project is not a Git repository (`git rev-parse` reports "not a git repository"), so nothing was committed or pushed.
- **No deployment or exposure:** nothing was deployed or published, and no network service was exposed. All servers used in this programme ran on `localhost` and were stopped afterwards.
- **No uploads:** no image, video, screenshot, database or other project data was uploaded to an external service.
- **No external assets:** fonts and icons are Streamlit's bundled files.
- **Running app:** your dashboard on port 8502 was not stopped or modified.

---

## Addendum, 25 November 2026: closer match to the reference

On your request ("exactly the same as the reference"), the look was brought much closer to the reference image. Data stays real.

**What changed** (presentation only; backup in `experiments/frontend_redesign/backups/20261125-pre-ditto/`):
- **Sidebar.** Hexagonal gold logo, "SiteGuard AI / Construction Safety", condensed type, reference-style icons, glowing amber pill for the active page, "Settings" label (the page value is still "Settings / About").
- **Header.** No kicker. Title and subtitle on the left; "● System Online · time" on the right.
  - The time is this computer's clock, kept current by a 15-second script in the page.
  - The script triggers no Streamlit reruns, so the camera session is not touched.
- **Overview.**
  - "Site Overview" title band.
  - Slanted KPI cards with gold rim light and bright icon tiles (orange, green, red, blue).
  - Live Site Feed with OFFLINE badge and a bottom bar ("No live stream · ● Camera off").
  - Recent Alerts with filled icon tiles and View All link.
  - Monitoring Activity as a glowing bar strip.
  - System Processing panel with status lines and a bar that is full only when the last analysis completed.
- **Scene.** Dark angular slogan panel with gold edges at the bottom right (1400 px and wider).
- **Fonts.** Avenir Next Condensed for headings and labels (a macOS system font; nothing downloaded).

**Still different from the reference, on purpose.** These would show invented data in a safety tool:
- 94.2 % compliance rate (no validated compliance measure exists; the card shows Pending Review);
- "Active" camera on Overview (the camera only runs on Live Monitoring);
- the site photo inside Live Site Feed;
- "1920 × 1080 · 30 FPS";
- "Analyzing data… 69 %".

Panel glass blur also stays off, because it broke fullscreen charts.

**Verification:**
- `.venv/bin/python -m pytest -q`: 205 passed.
- Browser audit of all 8 pages at 10 widths: no overflow or clipping, except the known Settings model-selector "…". Overview was re-audited at 11 widths including 1470 px.
- Fullscreen charts still fill the screen.
- Database, evidence, models, `static/` and camera code unchanged.

**Evidence:** `experiments/frontend_redesign/evidence/reference_match/`.

**Restart done (25 Nov 00:38).** The stale dashboard (PID 61252) was stopped at your request, and a fresh one runs on `localhost:8502` (PID 10755) with automatic rerun on file save. Final verification, all pages, accessibility and performance results are in `FRONTEND-REDESIGN-REPORT-008-REFERENCE-MATCH.md` (205 tests passed).
