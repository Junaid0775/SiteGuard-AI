# SiteGuard AI — Frontend Visual Implementation Master Specification
## Reference-Locked Cinematic Industrial Dashboard
**Project:** SiteGuard AI — Intelligent Real-Time Construction Site PPE Compliance Monitoring System  
**Workspace:** `~/Desktop/471 Project/SiteGuard-AI/`  
**Existing application:** Python + Streamlit  
**Current local dashboard port:** `8502`  
**Implementation agent:** Claude Code in VS Code  
**Document type:** Single master specification; execute sequentially by phase  
**Priority:** Preserve existing functionality and data integrity while implementing the approved visual direction.

---

# 0. Executive directive

Rebuild the frontend presentation of the existing SiteGuard AI application to closely reproduce the user's approved reference screenshot.

The approved design direction is:

**Premium Industrial + Spatial UI + Cinematic Construction Environment**, with selective glass-like surfaces.

The uploaded reference screenshot is the primary visual authority. It is not a loose mood board. Reproduce its overall composition, proportions, palette, hierarchy, atmosphere, angular geometry, sidebar, KPI strip, monitoring panels, and right-side construction-site scene as closely as the existing application architecture reasonably permits.

The desired result should look like a polished, premium, enterprise construction-safety product—not a generic Streamlit dashboard, not a neon cyberpunk interface, and not an old-fashioned industrial control panel.

The implementation must be done in the existing project in place. Do not create a replacement application, do not migrate frameworks, and do not rewrite the backend simply to achieve the visual design.

## 0.1 Non-negotiable project preservation

The current application already contains important working functionality. This task is a frontend visual and UX implementation, not an ML or backend redevelopment project.

Preserve all of the following unless a specific change is explicitly approved by the user:

- Active model remains **YOLO26n**.
- Experimental E3 / YOLO26m remains non-selectable and must not become the active model.
- Existing inference pipeline, model weights, preprocessing, postprocessing and detection behaviour.
- Existing conservative PPE compliance logic and interpretation rules.
- Existing thresholds and threshold configuration.
- Existing event creation, event persistence, event identifiers, evidence association and database behaviour.
- Existing database schema, records and migrations.
- Existing original dataset and labels. Treat the dataset as read-only.
- Existing model evaluation results and experiment artifacts.
- Existing camera/WebRTC quality and START reliability improvements.
- Existing 1280×720 Chrome incoming video configuration, bitrate changes, video sizing behaviour and run-count guard.
- Existing camera permission and lifecycle behaviour.
- Existing local-only operation.
- Existing page capabilities and workflows.
- Existing settings and configuration semantics.

Do not delete, overwrite, regenerate, rename, move or “clean up” model files, checkpoints, datasets, database files, safety-event evidence or experiment reports.

Do not change thresholds, detection rules, model selection, camera transport, event logic, database schema or inference code for visual convenience.

Do not conduct a new physical webcam test as part of this frontend task. Use safe UI fixtures, synthetic data, existing non-sensitive test fixtures or mock presentation data. A physical camera test requires separate explicit user approval.

Do not push to GitHub, publish, deploy, expose a network service, or upload project data. The application remains local.

## 0.2 Required working relationship

Claude Code is the implementation agent. Work in the existing VS Code workspace. The user expects a comprehensive implementation with reports after each phase.

For every phase:
1. Inspect before editing.
2. Define the exact scope.
3. Make the smallest safe set of changes.
4. Run relevant tests.
5. Compare behaviour before and after.
6. Capture evidence.
7. Write a detailed phase report.
8. Stop at the phase gate and present the report before proceeding when the gate requires approval.

Never claim a test passed unless it was actually run and its output was inspected. Never claim visual parity merely because the page loads.

---

# 1. Reference screenshot: visual specification

## 1.1 Reference interpretation

The approved screenshot is a very wide desktop dashboard composition. Its visual structure is:

1. A dark, fixed left navigation rail.
2. A broad central dashboard surface with dark graphite/navy styling.
3. A right-side cinematic construction-site environment at dusk.
4. A large angular gold boundary/architectural frame that visually separates the interface from the environment.
5. A compact top header and system status.
6. Four KPI cards in a horizontal strip.
7. A lower row containing a live site feed, recent alerts and monitoring activity.
8. A system-processing/progress panel beneath or adjacent to the monitoring activity.
9. A concise brand promise in the scenic region: **“Safer Sites. Smarter Tomorrow.”**

The screenshot is a design reference. Text and sample values inside the image are not authoritative application data. Do not hard-code its illustrative values into production widgets.

## 1.2 Composition and relative proportions

Use the screenshot's visual balance as the target, adapting intelligently to the actual viewport:

- Left navigation: approximately 12–14% of the wide desktop composition.
- Main dashboard workspace: approximately 62–68%.
- Cinematic scenic region: approximately 20–25%.
- Top KPI cards: a single horizontal row on wide screens.
- Main content: visually dense but not cramped.
- Scenery must be visible as an intentional design element, not merely a tiny wallpaper strip.
- Gold architectural boundary should create a strong transition between dashboard and scenery without obstructing content.
- Main panels should have enough opacity and contrast to preserve legibility over the environmental background.

These are visual proportions, not rigid CSS pixel requirements. At smaller widths, reflow rather than shrink the entire desktop composition.

## 1.3 Visual identity

### Base palette

Use a restrained, premium industrial palette. Establish CSS variables or the equivalent central theme tokens.

Suggested starting values (Claude may tune slightly after screenshot comparison):

| Token | Suggested value | Purpose |
|---|---|---|
| `--sg-ink` | `#080D14` | Deepest page background |
| `--sg-navy` | `#101A27` | Sidebar and deep surfaces |
| `--sg-graphite` | `#171E27` | Main dashboard surface |
| `--sg-panel` | `rgba(20, 28, 38, 0.90)` | Main cards |
| `--sg-panel-raised` | `rgba(31, 40, 51, 0.92)` | Elevated cards |
| `--sg-border` | `rgba(207, 166, 99, 0.25)` | Restrained warm edge |
| `--sg-gold` | `#D6A24D` | Primary architectural accent |
| `--sg-amber` | `#E49A32` | Selected navigation and highlights |
| `--sg-ivory` | `#F3F0E8` | Primary text |
| `--sg-muted` | `#AEB6BF` | Secondary text |
| `--sg-muted-2` | `#778391` | Tertiary text |

Use status colours only where semantically appropriate:
- Green for healthy/connected/confirmed status.
- Amber for warning/review-needed status.
- Red for critical/error status.
- Blue may be used sparingly for camera/video/system information.

Do not turn the overall interface into a multicolour dashboard. KPI icons may have subtle semantic colour treatments, but the dominant visual identity must remain graphite/navy/gold.

### Prohibited visual treatments

- No neon cyan, neon purple, neon green or glowing rainbow gradients.
- No cyberpunk styling.
- No oversaturated accent gradients.
- No excessive glass blur that makes text or camera imagery difficult to read.
- No large rounded pill-everything design.
- No old-fashioned skeuomorphic metallic buttons.
- No thick borders around every element.
- No excessive drop shadows.
- No decorative animations that distract from safety information.
- No generic default Streamlit widgets left visually inconsistent with the theme.

## 1.4 Typography

Use a clean modern sans-serif family already available locally or bundled safely with the project. Do not make the app depend on an external font network request.

Typography hierarchy:
- Product name: compact, confident, medium/semibold.
- Page title: prominent, clear, restrained.
- KPI values: large, tabular numerals where supported.
- KPI labels: compact, medium contrast.
- Panel titles: short, semibold.
- Metadata: small but legible.
- Safety event text: readable at a glance.

Avoid ultra-thin fonts. Avoid condensed display fonts for critical information. Use consistent line heights and spacing.

## 1.5 Scenic environment

The background scenery is a core part of the approved design, not an optional decorative image.

Required appearance:
- Construction site with an unfinished multi-storey building.
- Tower cranes visible in the skyline.
- Dusk / late-afternoon / warm low-sun atmosphere.
- Realistic architectural photography or a high-quality rendered environment.
- Warm amber light against a darker blue/graphite atmosphere.
- The scenic region should occupy the right side of the wide desktop composition.
- A carefully controlled dark overlay must preserve the dashboard's contrast.
- The scenic environment should feel related to construction safety and site operations.

Implementation requirements:
- Use a local project asset, not a remote image URL.
- First inspect existing assets and project licensing/attribution.
- If a new image is required, do not silently download a copyrighted or unlicensed image. Identify the asset source and license, or request a user-provided asset.
- Keep the image in an appropriately named asset directory, for example `assets/images/siteguard_cinematic_environment.webp`, only after inspecting the actual project structure.
- Use `background-size: cover` or an equivalent responsive image treatment.
- Set deliberate background positioning so the building and cranes remain visible on common desktop aspect ratios.
- Add separate gradient overlays rather than editing the source image destructively.
- Ensure the background is not repeatedly downloaded on each page navigation.
- The scene must remain visually continuous across all application pages.
- Do not use a different unrelated background image on every page.
- Avoid placing high-contrast scene details directly behind dense text, charts or event tables.

### Persistent scenery behaviour

The scenic environment should be part of the shared application shell:
- It remains present when the user navigates between Overview, Live Monitoring, Image Inspection, Video Inspection, Safety Events, Analytics, Model Evaluation and Settings/About.
- It must not flash, reset, disappear or visibly reload during normal Streamlit reruns or navigation.
- The same image, crop, overlay and angular boundary treatment should persist.
- Page-specific content changes inside the shell; the environment remains stable.
- On narrow mobile layouts, the scenic region may become a compact top banner, a low-contrast background layer or be simplified to preserve content usability. Do not force the desktop side-scene into a narrow column.

## 1.6 Angular gold boundary

The screenshot includes a distinctive angular gold line / architectural frame around the right scenic region.

Recreate this as a restrained geometric motif:
- A diagonal or stepped boundary between dashboard and scenic region.
- Thin gold/amber stroke with controlled opacity.
- Clean joins and consistent line weight.
- It should visually frame the environment, not become a large decorative polygon that consumes content space.
- Use CSS clip-path, pseudo-elements, SVG or another maintainable method after checking compatibility with the existing Streamlit layout.
- It must not intercept pointer events.
- It must not cause horizontal overflow.
- It must remain coherent at common desktop widths.
- At smaller widths, simplify or hide the decorative line if it compromises layout.

---

# 2. Application shell and navigation

## 2.1 Shared shell

Create or refine one shared visual shell used by every page:
- Persistent left sidebar.
- Persistent cinematic background.
- Consistent top status region.
- Main content surface.
- Shared spacing, typography, borders and panel tokens.
- Consistent selected-navigation state.
- Consistent responsive breakpoints.

Do not duplicate large blocks of CSS or layout code separately across pages. Prefer the existing project architecture and a small, maintainable shared theme/layout module.

Before creating new files, inspect the actual repository and follow its naming conventions. Do not assume the examples in this document match existing filenames.

## 2.2 Sidebar

Target appearance:
- Deep navy/graphite background.
- SiteGuard AI logo/mark and wordmark at the top.
- Small descriptor: Construction Safety.
- Compact navigation list with consistent icons.
- Active item highlighted with a warm amber/gold treatment.
- Non-active items in muted ivory/grey.
- Fine separator or subtle border where appropriate.
- Footer area can contain a short brand statement or local-system label.

Navigation items, preserving existing page destinations:
1. Overview
2. Live Monitoring
3. Image Inspection
4. Video Inspection
5. Safety Events
6. Analytics
7. Model Evaluation
8. Settings / About (preserve the actual existing page naming and capabilities)

Requirements:
- Navigation must continue to work exactly as it does now.
- Do not invent new routes or remove pages.
- Keep labels readable.
- Use consistent icon family and size.
- No emoji icons in the production sidebar.
- Sidebar width must be stable on desktop.
- On tablet/mobile, use a compact/collapsible navigation pattern compatible with Streamlit.
- Avoid an overly wide sidebar that steals space from the camera feed.

## 2.3 Header

The main content header should reproduce the screenshot's restrained hierarchy:
- Page title, e.g. “Site Overview”.
- Short contextual subtitle where useful.
- System online/offline indicator sourced from actual application state if such a state already exists.
- Local time only if the application already supports it correctly; do not invent timestamps.
- Keep header compact.
- No oversized hero banner that pushes useful monitoring content below the fold.

---

# 3. Overview page

The Overview page is the primary visual benchmark. Implement this page first and use it to establish the shared design system.

## 3.1 KPI strip

Four cards in one row on wide screens:
1. People Detected
2. Compliance Rate
3. Potential Alerts
4. Camera Status

Important:
- Bind values to actual existing data sources.
- If a metric is not currently available, do not invent a value. Display a clear unavailable state or omit that metric only after reporting the limitation.
- Do not recalculate compliance using new logic.
- “Potential Alerts” must respect the current conservative event interpretation.
- Do not imply a confirmed violation where the backend only reports a potential issue.
- Camera status must reflect the actual camera/session state, not a hard-coded “Active”.
- Use tabular numerals for values.
- Use semantic icons with subtle colour accents.
- Cards should have dark, slightly translucent surfaces, fine borders and restrained depth.
- On medium widths, use two columns.
- On mobile, use one or two columns depending on available width.

## 3.2 Live site feed

The live feed is a key operational panel.

Requirements:
- Preserve the existing camera component and its lifecycle.
- Preserve the approved camera quality fixes.
- Do not change requested capture resolution, incoming resolution, bitrate, WebRTC constraints, run-count guard or camera start/stop semantics as part of this visual task.
- Do not stretch or crop the video to fill a panel.
- Maintain the correct aspect ratio.
- Ensure the visual container adapts to the available width.
- Overlay labels/status only if they do not obscure important video content.
- Use a clear camera title and camera identifier if already available.
- Show real connection status.
- Do not claim 1920×1080 or 30 FPS unless the displayed source/stream actually provides that information.
- Do not replace the real feed with a static image in production.
- Use a synthetic fixture only in isolated UI tests.

## 3.3 Recent alerts panel

Preserve the existing events/alerts source and event semantics.

Design:
- Compact vertical list.
- Clear status indicator.
- Short event title.
- Zone/camera/time metadata where available.
- Restrained red/amber/green status colours.
- Fine separators.
- “View all” navigation only if it maps to the existing Safety Events page and preserves filters/context as appropriate.

Do not:
- Create new alerts for visual demonstration.
- Change event severity or compliance interpretation.
- Change event persistence.
- Invent timestamps or zones.
- Convert “potential” events into confirmed violations.

## 3.4 Monitoring activity panel

- Reuse existing analytics/activity data.
- Keep chart labels and axes legible.
- Use amber/gold as the main chart accent.
- Avoid unnecessary animation.
- Do not fabricate a time series.
- If data is unavailable, display a clear empty state.
- Keep the panel compact enough to preserve the camera feed's prominence.

## 3.5 System processing panel

- Reflect actual processing status or actual existing system-health fields.
- Do not display fake progress percentages.
- Do not create a progress bar that appears to indicate a real operation when no such operation exists.
- If a genuine operation is running, display its real state.
- If there is no measurable progress, use a neutral status label rather than a fake percentage.

---

# 4. Loading and interaction language

## 4.1 Typing-dot loading indicator

The user explicitly requested the three-dot typing/loading treatment.

Implement a restrained three-dot animation:
- Three small circular dots.
- Sequential opacity or vertical movement.
- Amber/gold or neutral ivory, depending on contrast.
- Smooth, low-amplitude movement.
- No neon glow.
- Respect reduced-motion preferences.
- Use only while an actual operation is loading or processing.
- Do not leave a perpetual loading indicator on an idle page.

Use it consistently for:
- Genuine data-loading states.
- Genuine image/video processing states.
- Genuine model evaluation or analytics operations.
- Any existing asynchronous task where a loading state is already represented.

Do not introduce fake asynchronous delays solely to show the animation.

## 4.2 Micro-interactions

Allowed:
- Subtle hover border/brightness change.
- Small elevation change on hover.
- Smooth active-navigation transition.
- Restrained chart transitions when data changes.
- Gentle fade-in for newly loaded content if it does not interfere with Streamlit reruns.

Avoid:
- Large motion.
- Parallax that harms readability.
- Excessive blur transitions.
- Cursor-following effects.
- Animated scenery.
- Constantly moving background.
- Long page transitions.
- Anything that delays access to safety information.

## 4.3 Glass / spatial treatment

Use selective glass-like panels, not a fully transparent UI.

Panel treatment:
- Dark translucent fill with enough opacity for text contrast.
- Fine warm border.
- Small-radius or medium-radius corners consistent with screenshot.
- Subtle backdrop blur only where supported.
- restrained shadow.
- No glass treatment behind every single text label.

The spatial feeling should come from:
- Clear foreground/background separation.
- Layered panel elevations.
- The angular scenic boundary.
- Restrained shadow and lighting.
- Consistent depth hierarchy.

Do not make the interface look like a generic Apple Vision Pro concept or a floating hologram display.

---

# 5. All-page visual implementation

The Overview page establishes the system, but the entire application must be brought into the same design language.

For each page:
- Preserve every existing feature.
- Preserve current data sources.
- Preserve forms, controls, filters and navigation.
- Restyle the page without changing its business logic.
- Keep the shared scenic environment and shared shell intact.
- Use consistent panel, heading, control and table styles.
- Ensure the page works at desktop, tablet and mobile widths.

## 5.1 Live Monitoring

- Prominent video area with correct aspect ratio.
- Camera controls remain accessible and retain existing semantics.
- START/STOP states must remain unambiguous.
- Camera connection and failure messages must remain visible.
- Do not overlay scenery behind critical camera controls.
- Preserve the approved START reliability guard.
- No camera lifecycle changes.

## 5.2 Image Inspection

- Clear upload/select workflow.
- Image preview must preserve aspect ratio.
- Results and detections must be easy to inspect.
- Maintain existing processing controls and outputs.
- Use consistent result cards and status chips.
- Do not alter inference or PPE rules.

## 5.3 Video Inspection

- Clear video input and processing workflow.
- Progress/loading state only when actual processing is occurring.
- Results and event summaries remain readable.
- Preserve current video-processing behaviour and outputs.
- Avoid excessive decorative animation.

## 5.4 Safety Events

- Prioritise event readability and traceability.
- Preserve existing filters, event details and evidence access.
- Use restrained severity indicators.
- Keep event timestamps and identifiers accurate.
- Preserve the distinction between potential alerts and confirmed violations.
- Preserve database/event records and evidence associations.
- Ensure long tables remain usable on smaller screens, using horizontal scrolling or a responsive card representation without dropping fields.

## 5.5 Analytics

- Maintain existing calculations and charts.
- Improve chart hierarchy, labels, legends, spacing and empty states.
- Use amber/gold as the primary series accent, with restrained semantic supporting colours.
- Do not modify formulas or aggregation logic.
- Do not add invented analytics.

## 5.6 Model Evaluation

- Preserve the existing metrics and evaluation results.
- Maintain the current active model status: YOLO26n.
- Keep E3 / YOLO26m experimental and non-selectable.
- Do not imply that an experimental model is production-ready.
- Use clear metric cards, comparison tables and charts.
- Preserve the original metric values and provenance.
- Do not initiate model training, evaluation or checkpoint changes.

## 5.7 Settings / About

- Preserve all current settings and their semantics.
- If thresholds are read-only in the current application, keep them read-only.
- Clearly distinguish application information from editable controls.
- Do not add a deploy or publish button.
- Preserve local-only operation and existing configuration safeguards.

---

# 6. Responsive design specification

The screenshot is wide, but the actual application must be responsive.

Do not simply scale the entire desktop UI down. Recompose the layout.

## 6.1 Desktop — wide

Target widths: 1440px and above.
- Full sidebar.
- Scenic region on the right.
- Four KPI cards in one row.
- Three-column lower content arrangement where space permits.
- Camera feed receives the largest content area.
- No horizontal page scrolling.
- The scenic composition and gold boundary remain visible.

## 6.2 Desktop — standard

Target widths: 1024px–1439px.
- Sidebar remains usable, with optional compact mode if required.
- Scenic region becomes narrower but remains recognisable.
- KPI cards may use a two-by-two arrangement if required.
- Lower panels may become a two-column layout.
- Do not squeeze the live camera feed below a usable width.

## 6.3 Tablet

Target widths: 768px–1023px.
- Compact sidebar or collapsible navigation.
- Scenic background becomes a subtle top/side environmental layer.
- KPI cards in two columns.
- Camera feed remains prominent.
- Alerts and activity panels stack or use two columns according to actual width.
- No content may be hidden behind fixed navigation.

## 6.4 Mobile

Target widths: below 768px.
- Single-column content flow.
- Compact top navigation or a responsive sidebar/drawer pattern supported by the existing framework.
- Scenic background must not compete with content; use a darkened, cropped banner or subdued background.
- KPI cards use one or two columns based on available width.
- Camera video maintains aspect ratio and fits viewport width.
- Tables become scrollable or accessible card lists.
- Controls must be touch-friendly.
- No clipped labels, overlapping cards or horizontal page overflow.
- Critical safety statuses must remain visible without requiring decorative content to be scrolled past.

## 6.5 Accessibility

- Maintain sufficient text/background contrast.
- Do not rely on colour alone to communicate severity.
- Provide accessible labels for icon-only controls.
- Maintain visible keyboard focus.
- Use semantic headings.
- Respect reduced-motion settings.
- Preserve legibility at browser zoom levels.
- Do not use tiny metadata text for critical safety information.

---

# 7. Streamlit-specific implementation constraints

The existing application is Streamlit. Do not migrate to React, Next.js, Vue, Electron or another framework under this specification.

Before implementing:
- Inspect the current Streamlit version.
- Inspect existing page routing/navigation approach.
- Inspect current theme and CSS injection method.
- Inspect all existing custom components and frontend dependencies.
- Inspect `st.set_page_config`, session state usage and rerun behaviour.
- Inspect current camera component integration.
- Inspect whether the current layout uses `st.columns`, containers, tabs, custom components or other patterns.
- Identify which CSS selectors are stable and which are Streamlit internals likely to change.

Implementation guidance:
- Centralise reusable CSS/theme tokens.
- Avoid fragile selectors tied to generated Streamlit class names where possible.
- Scope custom styles to a unique application root/container where feasible.
- Do not globally hide Streamlit controls that users need.
- Do not break file uploaders, buttons, select boxes, dataframes, forms, camera controls or session state.
- Avoid injecting duplicate CSS on every rerun.
- Keep JavaScript minimal and only use it where necessary and safe.
- Do not add unneeded dependencies.
- Do not use remote scripts or CDNs.
- Do not introduce telemetry or external data transmission.
- Preserve existing application startup commands and local port behaviour.
- Preserve the current local environment and dependency lock/configuration unless a change is demonstrably required and separately documented.

If the desired screenshot cannot be achieved cleanly within Streamlit, do not begin a framework migration. Produce a technical limitation report with:
1. The exact requirement Streamlit cannot satisfy.
2. Evidence from a minimal prototype or framework limitation.
3. The least disruptive alternative.
4. Estimated scope and risk.
5. A recommendation requiring explicit user approval.

---

# 8. Required repository discovery before implementation

Phase 0 must inspect the real project before any code changes.

Workspace:
`~/Desktop/471 Project/SiteGuard-AI/`

Inspect:
- Full directory structure, excluding virtual environments and large generated folders from noisy listings.
- Main Streamlit entry point.
- Page modules.
- Shared utilities.
- CSS/theme files.
- Static assets.
- Camera/WebRTC components.
- Model-loading and inference modules (read-only inspection).
- Compliance/event logic (read-only inspection).
- Database and event persistence modules (read-only inspection).
- Tests and test configuration.
- Existing frontend reports.
- Existing camera quality and START reliability reports.
- Current application startup process and port.

Create a baseline inventory:
- Page list and functions.
- Shared shell/layout location.
- CSS/theme locations.
- Existing dependencies and versions.
- Test commands.
- Current Git status if Git is present.
- Current uncommitted changes.
- Existing assets and their dimensions.
- Existing screenshots if any.

Do not assume the repository is clean. Do not discard or overwrite user changes. Do not run destructive cleanup.

Before changes, record:
- A list of files expected to change.
- A list of protected files expected not to change.
- A test baseline.
- A rollback strategy.

If the application is currently running, do not kill an unrelated process. Ask before terminating an unknown process.

---

# 9. Protected areas and change-control rules

Treat these areas as protected unless the user explicitly authorises a change:
- Model weights/checkpoints.
- Dataset folders and annotations.
- Training/evaluation experiment folders.
- Detection and inference pipeline.
- PPE compliance rules.
- Threshold definitions and values.
- Event manager and event persistence.
- Database schema and database contents.
- Evidence files and evidence metadata.
- Camera/WebRTC transport and lifecycle logic.
- Camera resolution, bitrate, frame-rate constraints and run-count guard.
- Local-only/network configuration.
- Existing user-generated reports and documentation.

A frontend change must not indirectly modify protected behaviour.

If a frontend change requires a backend interface adjustment:
1. Stop before changing it.
2. Explain why it is necessary.
3. Identify the exact file/function/contract.
4. Propose the smallest compatible change.
5. Request approval.

Do not silently “improve” protected logic.

---

# 10. Implementation phases

Execute these phases sequentially. Each phase must end with a report. Do not skip phases or combine them to avoid evidence.

## Phase 0 — Repository discovery and baseline

Tasks:
1. Inspect the full project structure.
2. Read existing frontend completion reports and camera-quality reports.
3. Identify the current shared layout and page architecture.
4. Inventory all pages and existing interactions.
5. Identify the exact existing camera integration and verify it is not to be altered.
6. Inventory existing assets and licences.
7. Record current dependencies and versions.
8. Run the existing test suite and record the baseline.
9. Capture baseline screenshots of every existing page at representative viewport sizes, if safe and feasible.
10. Record current app behaviour and startup command.
11. Record Git status and user modifications.

Deliverables:
- `FRONTEND-REDESIGN-REPORT-001-DISCOVERY.md`
- Baseline screenshot set, stored in a new dedicated frontend redesign evidence folder.
- File-change plan.
- Protected-file list.
- Risk register.
- Baseline test results.

Gate:
Do not edit implementation files until discovery is complete and the user has received the report.

## Phase 1 — Design-system and asset plan

Tasks:
1. Translate the reference screenshot into a design token system.
2. Define exact palette, typography, spacing, panel surfaces, border, shadow and corner tokens.
3. Define desktop/tablet/mobile layout behaviour.
4. Inspect available scenic assets and licensing.
5. Determine whether an existing project asset can be used.
6. If no suitable licensed asset exists, prepare an asset requirement and request a user-provided asset or approval for a properly licensed source.
7. Define the persistent scenic shell and angular boundary approach.
8. Define component patterns for KPI cards, alerts, charts, video container, tables, buttons, inputs, empty states and loading dots.
9. Produce a design implementation map for every page.

Deliverables:
- `FRONTEND-REDESIGN-REPORT-002-DESIGN-SYSTEM.md`
- Design tokens file or documented token specification.
- Scenic asset/licence decision.
- Page-by-page implementation map.
- Desktop/tablet/mobile layout plan.

Gate:
Do not use an unlicensed or remote image. If the required scenic asset is missing, pause and ask for it or approval.

## Phase 2 — Shared application shell

Tasks:
1. Implement shared theme tokens.
2. Implement shared background/scenery layer.
3. Implement dark overlay and image positioning.
4. Implement angular gold boundary.
5. Implement shared sidebar and brand block.
6. Implement shared navigation states.
7. Implement compact header and actual system-status display.
8. Ensure shell persists across page navigation and Streamlit reruns.
9. Implement responsive sidebar behaviour.
10. Ensure the shell does not interfere with the camera or other interactive controls.

Deliverables:
- `FRONTEND-REDESIGN-REPORT-003-SHARED-SHELL.md`
- Before/after screenshots.
- Files changed and CSS/token documentation.
- Responsive verification evidence.

Gate:
All existing pages must still be reachable. No backend or protected logic changes.

## Phase 3 — Overview page implementation

Tasks:
1. Rebuild Overview layout to match the reference.
2. Implement four KPI cards using real application values.
3. Implement live feed panel without altering camera internals.
4. Implement recent alerts using existing event sources.
5. Implement monitoring activity using existing data.
6. Implement truthful processing/system status.
7. Add the requested three-dot loading treatment to real loading states.
8. Tune proportions, spacing, typography and background positioning.
9. Compare screenshots with the approved reference at wide desktop dimensions.
10. Verify no fake values or false system states are displayed.

Deliverables:
- `FRONTEND-REDESIGN-REPORT-004-OVERVIEW.md`
- Wide desktop screenshot.
- Standard desktop screenshot.
- Tablet screenshot.
- Mobile screenshot.
- Data-binding audit for each KPI/panel.
- Camera integration preservation statement backed by code diff.

Gate:
The Overview must be visually close to the reference and functionally correct before the other pages are redesigned.

## Phase 4 — Remaining pages

Implement in this order:
1. Live Monitoring.
2. Image Inspection.
3. Video Inspection.
4. Safety Events.
5. Analytics.
6. Model Evaluation.
7. Settings/About.

For each page:
- Record original features.
- Preserve existing functionality.
- Apply shared design tokens.
- Apply shared scenic shell.
- Implement responsive behaviour.
- Verify all controls.
- Capture before/after screenshots.
- Run page-specific tests.
- Record any limitations.

Deliverables:
- `FRONTEND-REDESIGN-REPORT-005-ALL-PAGES.md`
- Per-page screenshot evidence.
- Page/functionality preservation matrix.
- List of any remaining inconsistencies.

Gate:
No existing page or workflow may be silently removed.

## Phase 5 — Responsive and accessibility hardening

Test at representative viewport widths:
- 1920px
- 1600px
- 1440px
- 1280px
- 1024px
- 820px
- 768px
- 430px
- 390px
- 360px

For each:
- Check horizontal overflow.
- Check sidebar/navigation behaviour.
- Check KPI wrapping.
- Check video aspect ratio.
- Check panel stacking.
- Check table usability.
- Check text clipping and overlap.
- Check scenic image crop.
- Check gold boundary positioning.
- Check loading-dot visibility and reduced-motion behaviour.
- Check keyboard focus and contrast.

Deliverables:
- `FRONTEND-REDESIGN-REPORT-006-RESPONSIVE-ACCESSIBILITY.md`
- Viewport test matrix.
- Screenshots for representative breakpoints.
- Defect list and fixes.

Gate:
No critical content or safety status may be hidden or unreadable at supported widths.

## Phase 6 — Regression, performance and integrity audit

Run:
- Existing automated test suite.
- Page navigation tests.
- Existing component tests.
- Form/control interaction tests.
- Empty-state tests.
- Responsive tests.
- Camera UI integration tests using safe fixtures only.
- Event rendering tests using non-production fixtures.
- CSS/layout regression checks.
- Startup/shutdown checks.

Inspect the final diff for unintended modifications to:
- Models/checkpoints.
- Dataset.
- Inference code.
- Compliance rules.
- Thresholds.
- Event persistence.
- Database schema/data.
- Evidence files.
- Camera/WebRTC transport and lifecycle.
- Dependencies and configuration.

Performance:
- Compare startup time and page render responsiveness with baseline.
- Ensure the background asset is local and not reloaded unnecessarily.
- Avoid huge unoptimised images.
- Optimise image size while preserving acceptable quality.
- Avoid expensive CSS effects across large areas.
- Check CPU/memory overhead of any custom component.
- Do not sacrifice camera performance for decorative effects.

Deliverables:
- `FRONTEND-REDESIGN-REPORT-007-REGRESSION.md`
- Full test output summary.
- Protected-file diff audit.
- Performance comparison.
- Known limitations.

Gate:
Any unexplained protected-file modification is a blocker. Revert only the specific unintended change after preserving user work and documenting it.

## Phase 7 — Final handoff

Prepare:
1. Final implementation summary.
2. Final page inventory.
3. Exact file-change list.
4. Test results with commands and pass/fail counts.
5. Screenshot evidence index.
6. Responsive verification summary.
7. Accessibility summary.
8. Performance summary.
9. Protected-area integrity statement with evidence.
10. Known limitations.
11. How to launch the application.
12. How to stop the application.
13. How to roll back the frontend changes.
14. Clear confirmation that nothing was pushed or deployed.

Deliverable:
- `FRONTEND-REDESIGN-FINAL-HANDOFF.md`

Final gate:
Do not claim completion if any critical page is broken, a core workflow is missing, a protected area changed unexpectedly, or tests were skipped.

---

# 11. Screenshot comparison and visual quality criteria

Use the user's uploaded screenshot as the reference image throughout the task.

Compare at the same or closest practical aspect ratio. The reference is an unusually wide panoramic composition, so also create a realistic 16:9 desktop comparison to assess actual application use.

Review:
- Sidebar width and visual weight.
- Brand placement.
- Page-title alignment.
- KPI strip proportions.
- Main camera panel prominence.
- Alert panel density.
- Monitoring activity placement.
- Scenic image composition.
- Gold boundary angle and position.
- Overall darkness and contrast.
- Amber/gold restraint.
- Panel opacity and separation.
- Typography hierarchy.
- Whitespace and spacing.
- Overall premium/industrial impression.

Do not chase pixel-perfect matching at the expense of responsive usability or functional controls.

The screenshot includes generated/mockup text and decorative elements that may not be perfectly accurate. Reproduce the design language and composition, not typographical mistakes or inaccurate data.

## 11.1 Visual acceptance criteria

A reviewer should be able to identify the approved reference design immediately.

Acceptance:
- Dominant palette is graphite/navy/black with warm amber/gold.
- No neon styling.
- Construction-site-at-dusk scene remains visible on the right side on wide desktop.
- Scenic background persists across all pages.
- Angular gold boundary is present and restrained.
- Sidebar closely follows the reference hierarchy.
- Overview contains the four KPI concepts, live feed, recent alerts, monitoring activity and truthful system status.
- Camera aspect ratio is preserved.
- Panels have controlled depth and selective glass treatment.
- Text is legible.
- Responsive layouts are intentional.
- No fake data is presented as real.
- Existing workflows continue to function.

---

# 12. Testing rules and evidence standards

Evidence must be reproducible and traceable.

For every test, report:
- Exact command or test procedure.
- Environment/version where relevant.
- Expected result.
- Actual result.
- Pass/fail.
- Evidence path.
- Any caveat.

For screenshot evidence:
- Record viewport dimensions.
- Record page name.
- Record whether data is fixture/mock or real application data.
- Do not include sensitive/private camera footage.
- Do not save physical webcam frames.
- Do not create fake safety events in the real database.
- Store synthetic visual test artifacts in a clearly labelled test/evidence directory.

Do not report “all tests passed” when only a subset was run. State the exact scope.

Do not delete existing evidence. Do not overwrite existing reports. Create new report names for this redesign.

---

# 13. Rollback and failure handling

Before implementation:
- Record Git status.
- Preserve all pre-existing user changes.
- Create a safe rollback point using the repository's existing conventions, or a clearly documented backup that does not duplicate huge model/dataset files.
- Do not run destructive Git commands.
- Do not use `git reset --hard`, `git clean -fd`, broad deletion commands or force operations.

If a phase breaks the application:
1. Stop further implementation.
2. Capture the error.
3. Identify the smallest failing change.
4. Restore only the affected frontend change from the known safe state.
5. Re-run the baseline test.
6. Report the incident.

If the scenic asset cannot be licensed or obtained:
- Do not substitute an arbitrary image.
- Pause the scenic implementation.
- Keep the existing application functional.
- Request a suitable user-provided image or approval for a licensed asset.

---

# 14. Final instructions to Claude Code

You are implementing a reference-locked frontend redesign of an existing working construction PPE monitoring application.

Your priorities, in order:
1. Preserve existing application behaviour and data integrity.
2. Match the approved screenshot's visual identity.
3. Keep the scenic environment persistent across navigation.
4. Make the design responsive and accessible.
5. Preserve the approved camera improvements.
6. Provide detailed, evidence-backed reports after every phase.

Do not:
- Redesign the ML pipeline.
- Change model selection.
- Train models.
- Change compliance logic.
- Change thresholds.
- Change event/database behaviour.
- Modify camera transport/lifecycle.
- Replace Streamlit.
- Add cloud services.
- Add external telemetry.
- Push or deploy.
- Invent data.
- Use unlicensed imagery.
- Skip reports or gates.

Do:
- Inspect first.
- Use the screenshot as the visual source of truth.
- Reuse the existing architecture.
- Centralise styling.
- Implement the Overview first.
- Extend the shared visual system to every page.
- Test all supported viewports.
- Provide exact evidence and a final handoff.

**Begin with Phase 0 only. Do not implement Phase 1 or later until the Phase 0 discovery report has been completed and presented.**
