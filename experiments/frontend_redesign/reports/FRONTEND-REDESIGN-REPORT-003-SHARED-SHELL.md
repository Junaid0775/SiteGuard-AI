# FRONTEND-REDESIGN-REPORT-003 — Phase 2: Shared Application Shell

**Status:** Phase 2 complete. Phase 3 (Overview) has **not** started and waits for your review.
**Validation type:** automated tests and headless-browser screenshots taken from a temporary copy of the events database, with evidence images redacted. No camera was started.

## 1. Files changed

The rollback point is `experiments/frontend_redesign/backups/20261124-phase0/`. Line counts below are from `diff` against those backups.

| File | Changed lines | What changed |
|---|---|---|
| `src/ui/theme.py` | 125 | Tokens retuned (amber `#E49A32` accent, gold `#D6A24D` chart series, navy/graphite surfaces). New `SHELL_CSS` covers the persistent scene, overlay, gold boundary, brand promise, sidebar, header status pill, metric surfaces, breakpoints and reduced motion. `inject_css()` now emits the shell |
| `src/ui/components.py` | 12 | `set_header_status()`; `page_header()` shows the kicker and a status pill. The title stays in `st.title`, so existing tests still find page names |
| `app.py` | 10 | Navigation icons through `format_func` (page values, deep links and session keys unchanged); real model status passed to the header; sidebar footer line. **`page_live` is byte-identical to the backup** |
| `.streamlit/config.toml` | 32 | Palette (primary amber, navy sidebar, graphite surfaces, gold chart colour), `address = "localhost"`, `enableStaticServing = true` |
| `static/siteguard_background.webp` (new) | — | 485,612 bytes, 2843 × 1600, derived from the original PNG at WebP quality 88 |
| `tests/test_frontend_redesign.py` (new) | — | 6 tests (Section 4) |

**Not changed:** `src/ui/live_video.py` (0 lines) and all camera, detection, compliance, event, database, model and threshold code. The original PNG and `PROVENANCE.md` are untouched (their hashes are checked by a test).

## 2. What the shell does

| Element | Implementation |
|---|---|
| Persistent scene | One CSS background on `[data-testid="stApp"]`: dark gradient overlay, then the cached image (`cover`, anchored 78 % right), then ink. Streamlit's inner containers are transparent. Because it is the same URL on every page and rerun, there is no reload or flash |
| Scene width | `--sg-scene-w = clamp(0px, (100vw − 1100px) × 0.6, 30vw)`: 492 px at 1920, 204 px at 1440, 0 below 1100 px. Page content is padded so it never runs under the scene |
| Gold boundary | Fixed pseudo-element with two thin angled SVG lines at the scene edge, `pointer-events: none`, hidden below 1200 px |
| Brand promise | "Safer Sites. Smarter Tomorrow." fixed in the scene, `aria-hidden`, shown at 1500 px and wider |
| Sidebar | Navy gradient, hexagonal gold "SG" mark, Material icons, radio circles hidden, amber gradient and left bar on the active page, footer "Local system · runs on this computer only" |
| Header | Gold kicker; status pill fed by real state each run: "System online · Model loaded · mps", or "No usable model" in red. **No clock** (the app has no verified time source) |
| Narrow screens | 1100–767 px: the scene becomes a faint full background. Below 768 px: a darkened top band. Streamlit's own collapsible sidebar is kept |

## 3. Local-only and static-file verification

Checked on a temporary server started **without** an address flag, so the setting comes from the config alone:

| Check | Result |
|---|---|
| Listening address | **127.0.0.1 only** |
| Same port through the Mac's network IP (172.21.2.79) | **Connection refused** |
| `/app/static/siteguard_background.webp` | 200 `image/webp`, 485,612 bytes, ETag set, `nosniff` |
| Contents of `static/` | Only `siteguard_background.webp`. A test fails if anything else appears, including hidden files |

`http://localhost:<port>` keeps working on this Mac. Your running app on 8502 is still the old process; it picks up the new config when you restart it.

## 4. Tests

`.venv/bin/python -m pytest -q` gives **195 passed** (189 before plus 6 new). The new tests check:

1. `static/` holds only the approved image.
2. The WebP is a full-size 2843 × 1600 copy.
3. The original PNG hash and its provenance file are unchanged.
4. The config has `address = "localhost"` and static serving enabled.
5. The shell CSS uses the static URL, is click-through and honours reduced motion.
6. **All 8 pages render through the sidebar** with no exception, with the shell and status pill present.

## 5. Screenshots

| Set | Location | Coverage |
|---|---|---|
| Before | `experiments/frontend_redesign/evidence/baseline/` | 8 pages × 1440, 1024, 390 px (24) |
| After | `experiments/frontend_redesign/evidence/phase2_after/` | 8 pages × 1920, 1440, 1024, 390 px (32) |

Reviewed results:

- **1920:** the scene with cranes, building and worker is visible on the right; gold boundary and brand promise sit in the scene; content stays clear of it.
- **1440:** scene about 14 % of the width; the Live page shows START/STOP, status and captions intact.
- **390:** the scene is a darkened top band, the sidebar collapses and the header pill wraps cleanly.
- **Sidebar:** icons with no radio circles; the active page is amber.

No server exception occurred in any capture run.

## 6. Preservation

- Events database hash is unchanged (`789bf6cb…`), and it was only copied for screenshots.
- There are 135 evidence files, including your 4 camera events from 15:49–15:50, which were left as they are.
- The YOLO26n hash is unchanged and E3 was not touched.
- Nothing was pushed or deployed.

## 7. Known limitations (for Phase 3 onward)

- **The Live page video column is narrower at 1440 px.** The scene now takes 204 px, so the video area is about 550 px wide instead of 640 (scaled down, never stretched). At 1920 px the full 640 px fits. If you prefer, the scene can narrow on the Live page only, at the cost of perfect consistency.
- **Page contents are not yet restyled** (Overview KPI cards, alerts and activity are Phase 3; other pages are Phase 4). For example, on Overview the table's review column is clipped at 1920 px, and KPI cards stack one per row on phones.
- **The CSS depends on Streamlit test IDs** (`stApp`, `stSidebar`, `stRadioOption`, `stMainBlockContainer`). Streamlit is pinned at 1.67.0; recheck these after any upgrade.
