# FRONTEND-REDESIGN-REPORT-002 — Phase 1: Design System and Asset Plan

**Status:** Phase 1 complete. **No application file was changed.** Phase 2 waits for your go-ahead.
**Inputs:** the approved Phase 0 decisions (24 November 2026), the reference screenshot, and the supplied scenic image.

## 1. Files added in Phase 1 (no application code)

| File | Purpose |
|---|---|
| `docs/frontend_redesign/SiteGuard_AI_Reference_Locked_Frontend_Master_Specification.md` | Versioned copy of the master specification. It is byte-identical to the file in `~/Downloads` (SHA-256 `3461a750…`) |
| `assets/images/SiteGuard_AI_Cinematic_Construction_Background_1600h.png` | The supplied original image, copied unchanged. The original in `~/Downloads` was left in place |
| `assets/images/PROVENANCE.md` | Provenance: an original generated asset supplied by the project owner, not a stock photograph |

## 2. Scenic asset verification and plan

| Check | Result |
|---|---|
| File exists | Yes, at `assets/images/SiteGuard_AI_Cinematic_Construction_Background_1600h.png` |
| Dimensions | **2843 × 1600**, RGB, matching the stated size |
| Size | 4.85 MB PNG |
| SHA-256 | `565376e21a0e1e532b0be4da1be01fc7cbe7f32ad785d382b5bc16e08957f0ec`, identical to the Downloads copy |
| Web-optimised copy (trial) | WebP at quality 88 is 0.49 MB, about one-tenth of the PNG. It is a derived file and the PNG stays untouched |

**Plan (Phase 2):** serve the derived WebP once from `static/siteguard_background.webp`. CSS on the app container will display it as `cover`, anchored right-centre, so the tower crane, the unfinished building and the worker with the tablet stay in the scenic region. A gradient overlay darkens the dashboard area and the image itself is never edited. Because the URL never changes, the browser caches the image and it does not reload on navigation or reruns.

## 3. Static file serving: safety verification

This was tested on a temporary, separate Streamlit 1.67.0 app (port 8615); the project was not changed.

| Request | Result |
|---|---|
| `/app/static/bg.webp` | 200 `image/webp`, the intended asset |
| `/app/static/` (folder listing) | 404 |
| `/app/static/../secret.db` and encoded variants `%2e%2e`, `..%2f` | 400, blocked |
| `/secret.db`, `/app.py`, `/app/app.py` | Streamlit's page HTML only; file contents not exposed |
| `/app/static/.env` (hidden file placed inside `static/`) | **200, contents exposed** |
| Network binding with `--server.address localhost` | 127.0.0.1 only |

**Conclusion:** Streamlit serves only files placed inside `static/`; path traversal is blocked. **Everything inside `static/` is readable by anyone who can reach the port**, including hidden files.

**Safeguards for Phase 2:**

1. `static/` will hold exactly one file, the background WebP.
2. A new test fails if any other file appears there.
3. **Add `address = "localhost"` to `.streamlit/config.toml`.** Today the README start command sets no address, and Streamlit then listens on all network interfaces. This change makes local-only the default. The process on port 8502 is already started with `--server.address localhost`.

Evidence, database files, models and user data stay outside `static/`, so none of them can be served.

## 4. Design tokens

Values blend the specification with colours measured from the supplied image (dominant colours: slate `#45485C`, deep brown `#191110`, warm sunset `#BA7C5A`, amber light `#F1A550`).

| Token | Value | Use |
|---|---|---|
| `--sg-ink` | `#080D14` | Page base behind the scene |
| `--sg-navy` | `#0F1824` | Sidebar |
| `--sg-graphite` | `#161D27` | Main surface |
| `--sg-panel` | `rgba(18, 25, 35, 0.90)` | Cards and panels |
| `--sg-panel-raised` | `rgba(28, 37, 49, 0.92)` | Hover and raised surfaces |
| `--sg-border` | `rgba(214, 162, 77, 0.24)` | Fine warm panel edge |
| `--sg-border-soft` | `rgba(255, 255, 255, 0.06)` | Separators |
| `--sg-gold` | `#D6A24D` | Architectural lines, chart series |
| `--sg-amber` | `#E49A32` | Active navigation, primary button (replaces `#E07A3F`) |
| `--sg-ivory` | `#F3F0E8` | Primary text |
| `--sg-muted` | `#AEB6BF` | Secondary text |
| `--sg-muted-2` | `#778391` | Metadata |
| `--sg-ok` / `--sg-warn` / `--sg-critical` / `--sg-info` | `#3FA66B` / `#E0A030` / `#E5484D` / `#5B8DEF` | Status only, always with a text label |
| Scene overlay | `linear-gradient(90deg, rgba(8,13,20,.97) 0%, rgba(8,13,20,.93) 62%, rgba(8,13,20,.45) 80%, rgba(8,13,20,.20) 100%)` | Keeps the dashboard readable; the scene shows on the right |
| Radius | 6 px panels, 4 px buttons and inputs | Angular look of the reference |
| Shadow | `0 8px 24px rgba(0,0,0,.35)` on panels only | Restrained depth |
| Glass | `backdrop-filter: blur(6px)` on panels over the scene only, with an opaque fallback | Selective glass treatment |
| Spacing scale | 4, 8, 12, 16, 24, 32 px | All layouts |

**Typography:** keep Streamlit's bundled local sans-serif (no font downloads). Numbers use `font-variant-numeric: tabular-nums`.

| Element | Size and weight |
|---|---|
| Page title | 1.75rem, 600 |
| KPI value | 1.9rem, 600, tabular |
| KPI label | 0.8rem, 500 |
| Panel title | 1rem, 600 |
| Metadata | 0.78rem, never used for safety-critical text |

**Icons:** Streamlit's bundled Material Symbols (`:material/...:`): no new dependency and no emoji. Navigation keeps its current values. Icons are added only through `format_func`, so deep links, session state and tests are unchanged.

## 5. Shell architecture (Phase 2)

| Element | Approach |
|---|---|
| Scenery layer | CSS background on `[data-testid="stApp"]`: overlay gradient, then image, then `--sg-ink`; `background-attachment: fixed`, so it persists across pages |
| Gold boundary | One fixed pseudo-element carrying a thin angled SVG polyline at the content/scene boundary; `pointer-events: none`; hidden below 1024 px |
| Brand promise | "Safer Sites. Smarter Tomorrow." in a fixed, `aria-hidden` element in the scene area; wide screens only |
| Content width | Main container left-aligned, capped so the scene keeps about 20–25 % of wide screens |
| Sidebar | Navy panel, brand block, Material icons, amber active state with a left bar, footer label "Local system" |
| Header | Kicker, title and subtitle, plus a truthful status pill from real model state (for example "Model loaded · mps") |
| Loading dots | Three 6 px dots, staggered 1.2 s opacity animation, static under `prefers-reduced-motion`. Shown only during real work, inside the existing `st.spinner` and progress blocks |

## 6. Component patterns

| Component | Specification |
|---|---|
| KPI card | 40 px icon tile with semantic tint, label, tabular value, one-line footnote; panel surface with warm edge |
| Alert list | Severity icon plus text label, event title, source and time metadata, fine separators, link to Safety Events. "Potential" wording kept |
| Panel | Title row with an optional action, panel surface, consistent padding |
| Status pill | Dot plus text (colour is never the only cue) |
| Video container | Existing component untouched; framed only by the surrounding panel |
| Tables | Existing `st.dataframe`, themed through config colours; horizontal scroll on small screens |
| Buttons and inputs | Amber primary, ghost secondary, dark fields, visible gold focus ring |
| Empty state | Icon, message and next action; no fake values |

## 7. Responsive plan

| Width | Layout |
|---|---|
| ≥ 1440 px | Full sidebar; scene about 22 % on the right with the gold boundary; 4 KPI cards in one row; Overview lower row in 3 columns |
| 1200–1439 px | Scene about 15 %; 4 KPI cards; lower row in 2 columns |
| 1024–1199 px | Scene becomes a faint full background (darker overlay) and the boundary is hidden; KPI cards 2 × 2; panels in 2 columns; Live page already stacks below 1200 px |
| 768–1023 px | Streamlit's collapsible sidebar; KPI cards in 2 columns; panels stacked |
| < 768 px | Single column; scene as a darkened top band; KPI cards in 2 columns; tables scroll; touch-sized controls |

## 8. Page-by-page implementation map

| Page | Phase | Planned presentation change | Data source (unchanged) |
|---|---|---|---|
| Overview | 3 | Header and status pill; KPI cards (People Detected, Pending Review, Potential Alerts, Camera Status); camera panel (true state, last live-session summary, Open Live Monitoring); recent alerts (5); monitoring activity (events over time); honest system panel (model loaded, device, last inspection time) | Existing events and inspections tables, `model_error()`, `get_detector().info()`, session state |
| Live Monitoring | 4 | Header and panel styling; status panel | **Camera block untouched** |
| Image Inspection | 4 | Upload panel, result cards, loading dots during real detection | Existing pipeline |
| Video Inspection | 4 | Input panel, existing progress restyled, result cards | Existing pipeline |
| Safety Events | 4 | Filter bar, table, evidence panel and review badges restyled | Existing store |
| Analytics | 4 | Chart panels, gold series, empty states | Existing aggregations |
| Model Evaluation | 4 | Metric cards, comparison tables; YOLO26n active, E3 labelled experimental | Existing stored results |
| Settings / About | 4 | Read-only information panels | Existing settings |

**Camera Status truthfulness:** leaving Live Monitoring closes the live session, so on Overview the card reads "Not running" and shows the last live session (time, frames, events) from stored records. It never shows a hard-coded "Active".

## 9. Phase 2 file plan

| File | Change |
|---|---|
| `src/ui/theme.py` | Tokens, shell, scenery, boundary, sidebar, panels, buttons, inputs, loading dots, breakpoints |
| `src/ui/components.py` | Header with status pill, KPI card, panel, status pill, alert list, loading dots |
| `app.py` | Sidebar markup and navigation icons (`format_func`), header calls. No data, logic or camera changes |
| `.streamlit/config.toml` | `primaryColor` set to amber, `enableStaticServing = true`, `address = "localhost"` |
| `static/siteguard_background.webp` (new) | Derived from the original PNG |
| `tests/test_frontend_redesign.py` (new) | Shell renders on every page, `static/` whitelist, navigation values unchanged |

## 10. Risks carried into Phase 2

- The CSS relies on Streamlit test IDs (`stApp`, `stSidebar`), which may change on upgrade. Streamlit is pinned at 1.67.0, and the rules stay scoped.
- `backdrop-filter` costs GPU time over large areas, so it is limited to panels. CPU will be checked against the camera page in Phase 6.
- The `address = "localhost"` default blocks access from other devices on the network. This is intended for a local-only system.
