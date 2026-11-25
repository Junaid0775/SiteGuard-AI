# FRONTEND-REDESIGN-REPORT-008 — Reference Match (all phases)

**Date:** 25 November 2026
**Request:** make the application look the same as the approved reference image, then complete all phases.
**Status:** complete. Presentation only; no camera, detection, compliance, event, database or model code changed.
**Rollback point:** `experiments/frontend_redesign/backups/20261125-pre-ditto/` (`app.py`, `theme.py`, `components.py` and the redesign tests before this update).

## 1. Localhost fix

The dashboard on port 8502 had been running since 23 November (PID 61252). It still held the pre-redesign `src/ui/theme.py` in memory, so the new `app.py` failed with `ImportError: cannot import name 'GOLD'`. The file on disk was correct.

At your request the old process was stopped. A fresh one was started on the same address (`localhost:8502`, PID 10755) with automatic rerun on file save, so changes appear in the browser as they are made. It runs detached and keeps running after this session.

## 2. What changed

| Area | Change, following the reference |
|---|---|
| Sidebar | Hexagonal gold logo; "SiteGuard AI / Construction Safety"; condensed type; outline icons; glowing amber pill for the active page; "Settings" label (page value unchanged) |
| Page header | No kicker. Title (and subtitle) left; "● System Online · time" right, using this computer's clock |
| Overview | "Site Overview" band; slanted KPI cards with gold rim light and bright icon tiles; Live Site Feed with OFFLINE badge and info bar; Recent Alerts with filled tiles and View All; Monitoring Activity bar strip; System Processing panel with bar; scope note moved to the bottom |
| All pages | Metric tiles in the same slanted, gold-rimmed card style; condensed headings and panel titles; rounded glass panels with gold rim |
| Scene | Dark angular slogan panel with gold edges and "Safer Sites. Smarter Tomorrow." at the bottom right (1400 px and wider) |
| Type | Avenir Next Condensed (macOS system font; nothing downloaded) |

**Clock.** The time is rendered from this computer's clock and refreshed by one constant 15-second script (`st.html`).
- It triggers no Streamlit reruns, so the live camera session is unaffected.
- Measured idle cost on Live Monitoring: about 1 ms of main-thread time per 10 s.
- A CSS-only clock was tried first and rejected: it cost 258 ms per 10 s, with 60 style recalculations per second.

**Kept truthful on purpose.** The reference's sample values are not shown as real data:
- the 94.2 % compliance rate (the card shows Pending Review);
- "Active" camera on Overview;
- a site photo in the feed;
- "1920 × 1080 · 30 FPS";
- "Analyzing data… 69 %".

Panel glass blur stays off, because it trapped fullscreen charts (Report 006).

## 3. Verification

| Check | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | **205 passed**, 0 failed, 0 skipped. Redesign tests updated for the new labels; one test added for the status line and clock script |
| Browser audit: 8 pages × 10 widths (1920–360 px) | No page overflow, clipped text, cut metric, element outside its panel or unequal heights. The only flag is the Settings model selector, which shortens its long description with "…" (accepted earlier). Overview was also audited at 1470 px, about your MacBook's browser width |
| Accessibility | One `h1` per page and no unlabelled controls. Touch targets are at least 44 px on phones |
| Contrast (WCAG AA, ≥ 4.5:1) | KPI and metric labels 11.0; values 11.8; gold links 7.0; OFFLINE badge 10.2; panel meta 7.9; sidebar labels 11.1; active page 5.5; KPI footnotes 4.6 at the lightest point of the card |
| Fullscreen | Chart fullscreen fills the viewport (1446 × 842 px at 1470 × 900) |
| Performance (headless Chrome, as in Report 007) | Page load 0.30 s (Overview), 0.37 s (Model Evaluation). Scrolling at 60 fps. Live Monitoring idle about 1 ms per 10 s; 0.68 ms of style work per status update |
| Camera code | `page_live` byte-identical (hash test); `src/ui/live_video.py` unchanged |

## 4. Integrity

- **Models:** YOLO26n `890dc61f…` unchanged; E3 untouched.
- **`static/`:** still only the approved background.
- **Your own activity:** the events database and evidence folder changed after the restart, by your own use of the dashboard:
  - two live camera sessions saved at 00:41 and 00:42 on 25 Nov (537 and 164 frames analysed, 2 potential events);
  - one image inspection at 00:42 (1 potential event).
  - Result: database hash `d3d9ce8e…`, evidence folder 138 files.
  - All checks by this programme used temporary copies, so none of these records came from this work, and none were modified.

## 5. Evidence

`experiments/frontend_redesign/evidence/reference_match/` contains:
- **Screenshots:** every page at 1470 × 830, Overview at 1920 × 1080, 1440 × 900 and 390 × 844 (images redacted).
- **`audit/`:** 80 JPEG views plus `audit_results.json`.

## 6. Remaining limitations

- **Live Monitoring video width:** still your open decision; the video is about 550 px at 1440 px.
- **Demo mode** with the reference's sample values is not implemented. If it is wanted, it should be off by default and clearly labelled "DEMO DATA".
- **Selective glass blur** is not used (fullscreen conflict).
- **Narrow tablets:** KPI footnotes wrap to two lines on narrow cards.
- **Streamlit dependency:** the CSS depends on Streamlit 1.67 element structure; recheck the pages after any upgrade.
