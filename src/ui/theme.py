"""Design tokens, CSS and chart styling for the dark industrial SiteGuard AI theme.

The base palette lives in .streamlit/config.toml (Streamlit theme). This module adds the few things the theme
cannot express: page density, the sidebar navigation list, metric tiles, small badges and focus outlines.
Status colours are never used on their own; every status is also written as text.
"""

from __future__ import annotations

import urllib.parse

import streamlit as st

# ------------------------------------------------------------------ tokens (keep in sync with config.toml)
BG = "#0B1119"
SURFACE = "#161D27"
SURFACE_2 = "#1F2834"
BORDER = "#283240"
TEXT = "#F3F0E8"
MUTED = "#AEB6BF"
ACCENT = "#E49A32"   # amber: active navigation, primary actions
GOLD = "#D6A24D"     # architectural lines and the main chart series
DANGER = "#E5484D"
OK = "#3FA66B"
WARN = "#E0A030"
INFO = "#5B8DEF"

# Neutral categorical sequence for charts: gold first, then steel/blue-greys (no rainbow palettes).
CATEGORICAL = [GOLD, "#7C8B9C", "#4F6D8A", "#B9C2CC", "#8A6F52", "#5E7D6E", "#A3826A"]

# Review statuses as stored in the database -> human-readable labels (display only; stored values unchanged).
REVIEW_LABELS = {
    "pending_review": "Pending review",
    "confirmed": "Confirmed by reviewer",
    "false_positive": "False positive",
    "dismissed": "Dismissed",
}
REVIEW_COLORS = {
    "Pending review": WARN,
    "Confirmed by reviewer": DANGER,
    "False positive": "#7C8B9C",
    "Dismissed": "#4F6D8A",
}
# Badge colours (Streamlit names) per compliance status and review status.
STATUS_BADGE = {"potential_violation": "red", "compliant_evidence": "green", "uncertain": "orange"}
REVIEW_BADGE = {"pending_review": "orange", "confirmed": "red", "false_positive": "gray", "dismissed": "gray"}

CSS = f"""
<style>
  /* page density and width */
  [data-testid="stMainBlockContainer"], .block-container {{
    padding-top: 3.4rem; padding-bottom: 3rem; max-width: 1440px;
  }}
  h1 {{ font-size: 1.85rem !important; font-weight: 600 !important; letter-spacing: -0.01em; }}
  h2 {{ font-size: 1.35rem !important; font-weight: 600 !important; }}
  h3 {{ font-size: 1.08rem !important; font-weight: 600 !important; letter-spacing: 0.01em; }}
  /* kicker above page titles */
  .sg-kicker {{
    font-size: .72rem; font-weight: 600; letter-spacing: .14em; text-transform: uppercase;
    color: {ACCENT}; margin-bottom: -.55rem;
  }}
  /* brand block in the sidebar (text only: no images, so the page image count stays exact) */
  .sg-brand {{ display: flex; align-items: center; gap: .6rem; margin: .2rem 0 .1rem 0; }}
  .sg-brand-mark {{
    width: 30px; height: 30px; border-radius: 4px; background: {ACCENT}; color: {BG};
    display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: .9rem;
  }}
  .sg-brand-name {{ font-weight: 700; font-size: 1.05rem; color: {TEXT}; letter-spacing: .01em; }}
  .sg-brand-sub {{ font-size: .74rem; color: {MUTED}; margin-top: -.15rem; }}
  .sg-side-label {{
    font-size: .68rem; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: {MUTED};
    margin: .9rem 0 .3rem 0;
  }}
  /* sidebar navigation: radio rendered as a list with an accent bar on the active page */
  [data-testid="stSidebar"] [role="radiogroup"] {{ gap: 2px; }}
  [data-testid="stSidebar"] [role="radiogroup"] label {{
    width: 100%; padding: .38rem .6rem; border-radius: 4px; border-left: 3px solid transparent; margin: 0;
  }}
  [data-testid="stSidebar"] [role="radiogroup"] label:hover {{ background: {SURFACE_2}; }}
  [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
    background: {SURFACE_2}; border-left-color: {ACCENT};
  }}
  [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {{ font-weight: 600; color: {TEXT}; }}
  [data-testid="stSidebar"] [role="radiogroup"] label > div:first-child {{ display: none; }}
  /* metric tiles */
  [data-testid="stMetric"] {{ background: {SURFACE}; }}
  [data-testid="stMetricLabel"] p {{
    font-size: .8rem !important; letter-spacing: .01em; color: {MUTED} !important;
  }}
  [data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; font-weight: 600; }}
  /* small notes */
  .sg-scope {{ font-size: .8rem; color: {MUTED}; margin: -.2rem 0 .6rem 0; }}
  .sg-scope b {{ color: {TEXT}; font-weight: 600; }}
  .sg-kv {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
  .sg-kv td {{ padding: .32rem .5rem; border-bottom: 1px solid {BORDER}; vertical-align: top; }}
  .sg-kv td:first-child {{ color: {MUTED}; width: 42%; }}
  .sg-kv code {{ font-size: .8rem; word-break: break-all; }}
  /* narrow laptop windows: never cut metric values or button labels; shrink and wrap instead */
  [data-testid="stMetricValue"] div, [data-testid="stMetricLabel"] div, [data-testid="stMetricLabel"] p {{
    overflow: visible !important; text-overflow: clip !important; white-space: normal !important;
    word-break: normal !important; overflow-wrap: normal !important;
  }}
  [data-testid^="stBaseButton"] p {{ white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }}
  @media (max-width: 1280px) {{
    [data-testid="stMetricValue"] {{ font-size: 1.55rem !important; }}
    [data-testid="stMetricLabel"] p {{ font-size: .74rem !important; }}
    [data-testid="stMetric"] {{ padding: .6rem .7rem !important; }}
  }}
  /* Live Monitoring (Fix 3): on narrower windows stack the status panel under the video instead of shrinking the video */
  @media (max-width: 1200px) {{
    .st-key-sg-live-layout [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; }}
    .st-key-sg-live-layout [data-testid="stColumn"] {{ flex: 1 1 100% !important; width: 100% !important; min-width: 100% !important; }}
  }}
  /* keyboard focus must stay visible on the dark background */
  :focus-visible {{ outline: 2px solid {ACCENT} !important; outline-offset: 2px; }}
</style>
"""


# ------------------------------------------------------------------ shared shell (frontend redesign, Phase 2)
# One cached static image (static/siteguard_background.webp, derived from assets/images/; see PROVENANCE.md) sits behind
# every page. Overlays, crop and the gold boundary are CSS only; the image is never edited. The scene keeps the right
# part of wide screens (--sg-scene-w); below 1100 px it becomes a faint background, below 768 px a darkened top band.
BACKGROUND_URL = "/app/static/siteguard_background.webp"
_BOUNDARY_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' preserveAspectRatio='none'>"
    "<polyline points='17,0 3,57 25,100' fill='none' stroke='#D6A24D' stroke-width='1.6' stroke-opacity='0.85' vector-effect='non-scaling-stroke'/>"
    "<polyline points='24,0 10,57 32,100' fill='none' stroke='#D6A24D' stroke-width='1' stroke-opacity='0.35' vector-effect='non-scaling-stroke'/></svg>"
)
BOUNDARY_URI = "data:image/svg+xml," + urllib.parse.quote(_BOUNDARY_SVG)
_PANEL_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' preserveAspectRatio='none'>"
    "<polygon points='22,100 47,46 72,44 100,0 100,100' fill='#070B12' fill-opacity='0.92'/>"
    "<polyline points='22,100 47,46 72,44 100,0' fill='none' stroke='#E8B86A' stroke-width='1.8' vector-effect='non-scaling-stroke'/>"
    "<polyline points='34,100 50,66' fill='none' stroke='#E8B86A' stroke-opacity='0.45' stroke-width='1' vector-effect='non-scaling-stroke'/></svg>"
)
PANEL_URI = "data:image/svg+xml," + urllib.parse.quote(_PANEL_SVG)
SCENE_PROMISE = ('<div class="sg-scene-panel" aria-hidden="true"></div>'
                 '<div class="sg-scene-promise" aria-hidden="true"><b>Safer Sites.</b>Smarter Tomorrow.</div>')

# Keeps the header clock current. Constant, trusted script (no user input); one 15-s timer, no Streamlit reruns, so the
# live camera session is never touched.
CLOCK_SCRIPT = """<script>
(() => {
  const fmt = () => new Date().toLocaleTimeString("en-US", {hour: "numeric", minute: "2-digit"});
  const tick = () => document.querySelectorAll(".sg-clock").forEach(e => { const t = fmt(); if (e.textContent !== t) e.textContent = t; });
  tick();
  if (!window.__sgClockTimer) window.__sgClockTimer = setInterval(tick, 15000);
})();
</script>"""

SHELL_CSS = """
<style>
  :root {
    --sg-ink: #080D14; --sg-navy: #0F1824; --sg-graphite: #161D27;
    --sg-panel: rgba(18, 25, 35, 0.90); --sg-panel-raised: rgba(28, 37, 49, 0.92);
    --sg-border: rgba(214, 162, 77, 0.24); --sg-border-soft: rgba(255, 255, 255, 0.06);
    --sg-gold: #D6A24D; --sg-amber: #E49A32; --sg-ivory: #F3F0E8; --sg-muted: #AEB6BF; --sg-muted-2: #8D98A5;
    --sg-ok: #3FA66B; --sg-warn: #E0A030; --sg-critical: #E5484D; --sg-info: #5B8DEF;
    --sg-scene-w: clamp(0px, calc((100vw - 1100px) * 0.6), 30vw);
  }
  [data-testid="stApp"] {
    background:
      linear-gradient(90deg, rgba(8,13,20,.97) 0%, rgba(8,13,20,.94) calc(100% - var(--sg-scene-w) - 120px),
        rgba(8,13,20,.45) calc(100% - var(--sg-scene-w) + 40px), rgba(8,13,20,.18) 100%),
      url("__BG__") 78% center / cover no-repeat fixed,
      var(--sg-ink) !important;
  }
  [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stHeader"] { background: transparent !important; }
  [data-testid="stMainBlockContainer"] {
    max-width: none !important; padding-left: 3rem !important; padding-right: calc(var(--sg-scene-w) + 3rem) !important;
  }
  /* angular gold boundary at the dashboard/scene edge; decorative and click-through */
  [data-testid="stApp"]::after {
    content: ""; position: fixed; top: 0; right: 0; bottom: 0; width: var(--sg-scene-w);
    background: url("__BOUNDARY__") left top / 100% 100% no-repeat; pointer-events: none; z-index: 1;
  }
  .sg-scene-promise {
    position: fixed; right: 2.4vw; bottom: 10vh; width: calc(var(--sg-scene-w) * 0.72); text-align: right;
    pointer-events: none; z-index: 1; font-weight: 700; font-size: clamp(1.2rem, 1.45vw, 2rem); line-height: 1.18;
    color: var(--sg-ivory); text-shadow: 0 2px 14px rgba(0, 0, 0, .7);
  }
  .sg-scene-promise b { display: block; color: var(--sg-amber); font-weight: 700; }
  /* sidebar */
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F1824 0%, #0A111A 100%) !important; border-right: 1px solid rgba(214, 162, 77, .16) !important;
  }
  [data-testid="stSidebar"] [role="radiogroup"] label { padding: .5rem .7rem; border-radius: 6px; }
  /* hide the radio circle; the highlighted row and the bold label show the active page */
  [data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:not([data-testid="stMarkdownContainer"]) { display: none !important; }
  [data-testid="stSidebar"] [role="radiogroup"] label p { color: var(--sg-muted); font-size: .92rem; }
  [data-testid="stSidebar"] [data-testid="stRadioOption"] span[role="img"] { color: var(--sg-muted-2); margin-right: .45rem; }
  [data-testid="stSidebar"] [role="radiogroup"] label:hover { background: rgba(255, 255, 255, .04); }
  [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
    background: linear-gradient(90deg, rgba(228, 154, 50, .30), rgba(228, 154, 50, .07)) !important;
    border-left-color: var(--sg-amber) !important; box-shadow: inset 0 0 0 1px rgba(228, 154, 50, .25);
  }
  [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p,
  [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) span[role="img"] { color: var(--sg-amber) !important; }
  .sg-brand-mark {
    background: linear-gradient(135deg, #F0B45A, #C8862F) !important; color: #0B1119 !important; border-radius: 0 !important;
    width: 34px !important; height: 32px !important; clip-path: polygon(25% 3%, 75% 3%, 100% 50%, 75% 97%, 25% 97%, 0 50%);
  }
  .sg-side-foot { margin-top: 1.2rem; padding-top: .7rem; border-top: 1px solid var(--sg-border-soft); font-size: .74rem; color: var(--sg-muted-2); }
  /* page header with the real system status */
  .sg-header-row { display: flex; align-items: center; justify-content: space-between; gap: .8rem; flex-wrap: wrap; margin-bottom: -.35rem; }
  .sg-header-row .sg-kicker { margin-bottom: 0 !important; color: var(--sg-gold) !important; }
  .sg-status-pill {
    display: inline-flex; align-items: center; gap: .45rem; padding: .26rem .7rem; border-radius: 999px; font-size: .78rem;
    font-weight: 600; color: var(--sg-ivory); background: rgba(18, 25, 35, .88); border: 1px solid var(--sg-border-soft);
  }
  .sg-status-pill .sg-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--sg-ok); box-shadow: 0 0 0 3px rgba(63, 166, 107, .2); }
  .sg-status-pill.sg-critical .sg-dot { background: var(--sg-critical); box-shadow: 0 0 0 3px rgba(229, 72, 77, .2); }
  /* shared surfaces */
  [data-testid="stMetric"] {
    background: var(--sg-panel) !important; border-color: var(--sg-border) !important; border-radius: 6px !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, .28);
  }
  h1 { color: var(--sg-ivory); }
  /* ---- Phase 3: KPI cards, panels, alerts, camera frame, loading dots ---- */
  .sg-icon {
    font-family: "Material Symbols Rounded"; font-weight: 400; font-style: normal; font-size: 22px; line-height: 1;
    letter-spacing: normal; text-transform: none; white-space: nowrap; direction: ltr; font-feature-settings: "liga"; user-select: none;
  }
  .sg-kpi {
    display: flex; gap: .85rem; align-items: center; padding: .95rem 1rem; min-height: 96px; background: var(--sg-panel);
    border: 1px solid var(--sg-border); border-radius: 6px; box-shadow: 0 8px 24px rgba(0, 0, 0, .28);
  }
  .sg-kpi-icon {
    flex: 0 0 44px; height: 44px; border-radius: 6px; display: flex; align-items: center; justify-content: center;
    background: rgba(214, 162, 77, .14); color: var(--sg-gold);
  }
  .sg-tone-info .sg-kpi-icon { background: rgba(91, 141, 239, .15); color: var(--sg-info); }
  .sg-tone-warn .sg-kpi-icon { background: rgba(224, 160, 48, .16); color: var(--sg-warn); }
  .sg-tone-ok .sg-kpi-icon { background: rgba(63, 166, 107, .16); color: var(--sg-ok); }
  .sg-tone-muted .sg-kpi-icon { background: rgba(255, 255, 255, .06); color: var(--sg-muted); }
  .sg-kpi-label { font-size: .8rem; font-weight: 500; color: var(--sg-muted); }
  .sg-kpi-value { font-size: 1.9rem; font-weight: 600; line-height: 1.15; color: var(--sg-ivory); font-variant-numeric: tabular-nums; }
  .sg-kpi-foot { font-size: .75rem; color: var(--sg-muted-2); margin-top: .1rem; }
  .sg-kpi-value.sg-kpi-text { font-size: 1.35rem; padding: .2rem 0; }
  .st-key-sg-kpis .sg-kpi { min-height: 112px; }
  [class*="st-key-sg-panel-"] {
    background: var(--sg-panel); border: 1px solid var(--sg-border); border-radius: 6px; padding: 1rem 1.05rem 1.1rem;
    box-shadow: 0 8px 24px rgba(0, 0, 0, .28);  /* no backdrop blur here: it would trap fullscreen charts inside the panel */
  }
  .sg-panel-title { display: flex; justify-content: space-between; align-items: baseline; gap: .6rem; font-weight: 600; font-size: 1rem; color: var(--sg-ivory); }
  .sg-panel-meta { font-size: .74rem; font-weight: 500; color: var(--sg-muted-2); text-align: right; }
  .sg-feed {
    aspect-ratio: 16 / 9; border-radius: 4px; border: 1px solid var(--sg-border-soft); display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: .4rem; text-align: center; padding: 1rem; color: var(--sg-muted);
    background: repeating-linear-gradient(135deg, rgba(255, 255, 255, .018) 0 12px, transparent 12px 24px), rgba(8, 13, 20, .8);
  }
  .sg-feed .sg-icon { font-size: 40px; color: var(--sg-muted-2); }
  .sg-feed-state { font-weight: 600; color: var(--sg-ivory); }
  .sg-feed-note { font-size: .8rem; max-width: 36ch; }
  .sg-alerts { display: flex; flex-direction: column; }
  .sg-alert { display: flex; gap: .65rem; align-items: flex-start; padding: .55rem 0; border-bottom: 1px solid var(--sg-border-soft); }
  .sg-alert:last-child { border-bottom: 0; }
  .sg-alert .sg-icon { font-size: 20px; margin-top: .05rem; }
  .sg-alert.sg-tone-warn .sg-icon { color: var(--sg-warn); }
  .sg-alert.sg-tone-critical .sg-icon { color: var(--sg-critical); }
  .sg-alert.sg-tone-muted .sg-icon { color: var(--sg-muted-2); }
  .sg-alert-title { font-size: .9rem; font-weight: 600; color: var(--sg-ivory); }
  .sg-alert-meta { font-size: .76rem; color: var(--sg-muted); }
  /* ---- Phase 4: shared widgets on all pages ---- */
  [data-testid="stExpander"] details { background: var(--sg-panel); border-color: var(--sg-border) !important; border-radius: 6px !important; }
  [data-testid="stFileUploaderDropzone"] {
    background: rgba(8, 13, 20, .6) !important; border: 1px dashed rgba(214, 162, 77, .45) !important; border-radius: 6px !important;
  }
  [data-testid="stForm"] { background: rgba(8, 13, 20, .35); border-color: var(--sg-border-soft) !important; border-radius: 6px !important; }
  [class*="st-key-sg-panel-"] h3 { padding-top: .1rem !important; }
  .sg-kv td:last-child { overflow-wrap: anywhere; }  /* long values (paths) wrap inside their panel; labels keep whole words */
  [class*="st-key-sg-panel-"] [data-testid="stMetric"] { background: rgba(255, 255, 255, .03) !important; box-shadow: none; }
  /* Live Monitoring: the status column is an opaque panel (no blur: it refreshes every second while the camera runs).
     The video column and the camera component are not styled. */
  .st-key-sg-live-layout [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {
    background: rgba(18, 25, 35, .94); border: 1px solid var(--sg-border); border-radius: 6px; padding: 1rem 1.05rem;
  }
  /* Three-dot indicator in place of Streamlit's spinner icon. Spinners exist only while real work runs
     (image detection, video analysis, model loading), so the dots never stay on an idle page. */
  [data-testid="stSpinner"] > div > :first-child:not(:has([role="status"])) { display: none !important; }
  [data-testid="stSpinner"] > div::before {
    content: ""; display: inline-block; flex: 0 0 auto; align-self: center; width: 6px; height: 6px; margin: 0 1.9rem 0 .2rem;
    border-radius: 50%; background: rgba(214, 162, 77, .8);
    box-shadow: 11px 0 0 rgba(214, 162, 77, .8), 22px 0 0 rgba(214, 162, 77, .8); animation: sg-dot-seq 1.2s infinite ease-in-out;
  }
  @keyframes sg-dot-seq {
    0%, 100% { background: rgba(214, 162, 77, 1); box-shadow: 11px 0 0 rgba(214, 162, 77, .25), 22px 0 0 rgba(214, 162, 77, .25); }
    33% { background: rgba(214, 162, 77, .25); box-shadow: 11px 0 0 rgba(214, 162, 77, 1), 22px 0 0 rgba(214, 162, 77, .25); }
    66% { background: rgba(214, 162, 77, .25); box-shadow: 11px 0 0 rgba(214, 162, 77, .25), 22px 0 0 rgba(214, 162, 77, 1); }
  }
  @media (max-width: 1199px) {
    .st-key-sg-kpis [data-testid="stHorizontalBlock"], .st-key-sg-ov-lower [data-testid="stHorizontalBlock"],
    .st-key-sg-ov-more [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    .st-key-sg-kpis [data-testid="stColumn"], .st-key-sg-ov-lower [data-testid="stColumn"] {
      flex: 1 1 calc(50% - 1rem) !important; min-width: calc(50% - 1rem) !important;
    }
    .st-key-sg-ov-lower [data-testid="stColumn"]:first-child, .st-key-sg-ov-more [data-testid="stColumn"] {
      flex: 1 1 100% !important; min-width: 100% !important;
    }
  }
  @media (max-width: 767px) {
    .st-key-sg-ov-lower [data-testid="stColumn"] { flex: 1 1 100% !important; min-width: 100% !important; }
    .sg-kpi { min-height: 84px; padding: .75rem; gap: .6rem; }
    .sg-kpi-value { font-size: 1.45rem; }
    .sg-kpi-icon { flex-basis: 36px; height: 36px; }
  }
  @media (max-width: 1100px) {
    [data-testid="stApp"] {
      background: linear-gradient(rgba(8,13,20,.93), rgba(8,13,20,.93)), url("__BG__") 72% center / cover no-repeat fixed, var(--sg-ink) !important;
    }
  }
  @media (max-width: 1199px) { [data-testid="stApp"]::after { display: none; } }
  @media (max-width: 1499px) { .sg-scene-promise { display: none; } }
  @media (max-width: 767px) {
    [data-testid="stApp"] {
      background: linear-gradient(180deg, rgba(8,13,20,.45) 0, rgba(8,13,20,.97) 230px), url("__BG__") 72% top / auto 290px no-repeat,
        var(--sg-ink) !important;
    }
    [data-testid="stMainBlockContainer"] { padding-left: 1rem !important; padding-right: 1rem !important; }
  }
  /* ---- Phase 5: responsive and accessibility hardening ---- */
  /* contrast (WCAG AA): ink text on the amber primary button (white on amber was 2.3:1; ink is 8.1:1) */
  [data-testid^="stBaseButton-primary"], [data-testid^="stBaseButton-primary"] p,
  [data-testid^="stBaseButton-primary"] span { color: #0B1119 !important; }
  /* active navigation row: a lighter amber tint keeps the amber label above 4.5:1 (was 4.3:1) */
  [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
    background: linear-gradient(90deg, rgba(228, 154, 50, .22), rgba(228, 154, 50, .06)) !important;
  }
  /* keyboard focus on the navigation: the radio circle that normally shows focus is hidden */
  [data-testid="stSidebar"] [role="radiogroup"] label:has(input:focus-visible) { outline: 2px solid var(--sg-amber); outline-offset: 2px; }
  /* KPI cards: equal heights, and no overlap with the next row (Streamlit pulls markdown up by 1rem) */
  .st-key-sg-kpis [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
  .st-key-sg-kpis [data-testid="stColumn"] > [data-testid="stVerticalBlock"] { height: 100%; }
  .st-key-sg-kpis [data-testid="stElementContainer"] { flex: 1 1 auto; }
  .st-key-sg-kpis [data-testid="stMarkdown"], .st-key-sg-kpis [data-testid="stMarkdown"] > div,
  .st-key-sg-kpis [data-testid="stMarkdownContainer"], .st-key-sg-kpis .sg-kpi { height: 100%; }
  /* panels side by side get the same height; the last panel of a column fills the remaining height */
  [data-testid="stColumn"] > [data-testid="stVerticalBlock"]:has(> [data-testid="stLayoutWrapper"] > [class*="st-key-sg-panel-"]) { height: 100%; }
  [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:last-child:has(> [class*="st-key-sg-panel-"]) { flex: 1 1 auto; }
  [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"] > [class*="st-key-sg-panel-"] { height: 100%; }
  /* metric tiles: equal heights within a row */
  [data-testid="stColumn"] > [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] > [data-testid="stMetric"]) { height: 100%; }
  [data-testid="stElementContainer"]:has(> [data-testid="stMetric"]) { flex: 1 1 auto; }
  [data-testid="stMetric"] { height: 100%; }
  /* metric rows wrap to two tiles per row when the row is narrow (phones, tablets, narrow panels), so values are never cut */
  [data-testid="stLayoutWrapper"]:has(> [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] > [data-testid="stMetric"]) {
    container-type: inline-size; container-name: sg-metric-row;
  }
  @container sg-metric-row (max-width: 640px) {
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex: 1 1 calc(50% - .5rem) !important; min-width: calc(50% - .5rem) !important; width: auto !important; }
  }
  /* Overview "Active model": identity table and metrics stack when the panel is narrow */
  .st-key-sg-panel-model { container-type: inline-size; container-name: sg-model-panel; width: 100%; }
  @container sg-model-panel (max-width: 760px) {
    .st-key-sg-panel-model > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    .st-key-sg-panel-model > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
      flex: 1 1 100% !important; min-width: 100% !important;
    }
  }
  /* Safety Events filters: the date range gets more room on wide screens and a half row on tablets */
  @media (min-width: 1200px) {
    .st-key-sg-panel-event-filters [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex: 1 1 calc(21% - 1rem) !important; }
    .st-key-sg-panel-event-filters [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child { flex: 1 1 calc(37% - 1rem) !important; }
  }
  @media (min-width: 641px) and (max-width: 1199px) {
    .st-key-sg-panel-event-filters [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    .st-key-sg-panel-event-filters [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
      flex: 1 1 calc(50% - 1rem) !important; min-width: calc(50% - 1rem) !important;
    }
    .st-key-sg-panel-event-filters [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child { flex-basis: 100% !important; min-width: 100% !important; }
  }
  /* panel titles: the meta text moves under the title instead of squeezing it */
  .sg-panel-title { flex-wrap: wrap; row-gap: .1rem; }
  .sg-panel-meta { margin-left: auto; white-space: nowrap; }
  /* tablets: less side padding once the scene is no longer at the side */
  @media (max-width: 1100px) and (min-width: 768px) {
    [data-testid="stMainBlockContainer"] { padding-left: 1.5rem !important; padding-right: 1.5rem !important; }
  }
  /* images never wider than their panel (two evaluation plots are requested at a fixed 760 px) */
  [data-testid="stImageContainer"] { min-width: 0 !important; max-width: 100% !important; }  /* flex item: min-width auto kept the 760-px width */
  [data-testid="stImage"] img { height: auto; }
  /* metric deltas wrap instead of being cut on narrow tiles */
  [data-testid="stMetricDelta"] div, [data-testid="stMetricDelta"] p {
    white-space: normal !important; overflow: visible !important; text-overflow: clip !important;
  }
  /* rows of panels stack when the content area is narrow (tablets with the sidebar open, small laptops) */
  @media (max-width: 1000px) {
    [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"] > [class*="st-key-sg-panel-"]) {
      flex-wrap: wrap !important;
    }
    [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"] > [class*="st-key-sg-panel-"]) > [data-testid="stColumn"] {
      flex: 1 1 100% !important; min-width: 100% !important;
    }
  }
  /* Video Inspection settings row: one control per line when the sidebar leaves little room */
  @media (min-width: 769px) and (max-width: 1000px) {
    .st-key-sg-panel-video-input [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    .st-key-sg-panel-video-input [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex: 1 1 100% !important; min-width: 100% !important; }
  }
  /* phones: touch-sized controls; chart titles (SVG text, they cannot wrap) a little smaller so they fit */
  @media (max-width: 767px) {
    .js-plotly-plot .gtitle { font-size: 12px !important; }
    [data-testid^="stBaseButton"] { min-height: 44px; }
    [data-testid="stSidebar"] [role="radiogroup"] label { min-height: 44px; align-items: center; }
  }
  /* ==== Reference match (25 Nov): shapes, glows, colours and composition of the approved reference ==== */
  :root { --sg-cond: "Avenir Next Condensed", "Arial Narrow", "Roboto Condensed", sans-serif; }
  @media (min-width: 1101px) {
    [data-testid="stApp"] {
      background:
        radial-gradient(ellipse 50% 34% at 60% -4%, rgba(255, 206, 140, .13), transparent 70%),
        linear-gradient(90deg, rgba(8,13,20,.95) 0%, rgba(9,14,22,.90) calc(100% - var(--sg-scene-w) - 120px),
          rgba(8,13,20,.38) calc(100% - var(--sg-scene-w) + 40px), rgba(8,13,20,.08) 100%),
        url("__BG__") 78% center / cover no-repeat fixed, var(--sg-ink) !important;
    }
  }
  h1, h3, .sg-panel-title, .sg-kpi-label, .sg-kpi-value, .sg-brand-name, .sg-brand-sub, .sg-status-pill, .sg-alert-title,
  [data-testid="stSidebar"] [role="radiogroup"] label p, [data-testid="stBaseButton-tertiary"] p { font-family: var(--sg-cond) !important; }
  h1 { font-size: 2.2rem !important; font-weight: 700 !important; letter-spacing: 0 !important; }
  h3 { font-weight: 700 !important; }
  /* header: no kicker; status and local time at the top right of the title row */
  .sg-kicker { display: none !important; }
  [data-testid="stMainBlockContainer"] { position: relative; }
  .sg-header-row { justify-content: flex-end !important; margin: 0 !important; }
  .sg-status-pill { background: transparent !important; border: 0 !important; padding: .15rem 0 !important; font-size: 1rem !important; font-weight: 600 !important; }
  .sg-status-pill .sg-dot { width: 9px !important; height: 9px !important; box-shadow: 0 0 8px rgba(63, 208, 122, .8) !important; background: #3FD07A !important; }
  .sg-status-pill.sg-critical .sg-dot { background: var(--sg-critical) !important; box-shadow: 0 0 8px rgba(229, 72, 77, .8) !important; }
  .sg-status-pill .sg-sep { margin: 0 .5rem; color: var(--sg-muted); }
  .sg-status-pill .sg-clock { font-variant-numeric: tabular-nums; }
  @media (min-width: 1024px) {
    /* positioned within its own element container, which spans the content width */
    .sg-header-row { position: absolute; top: 2.15rem; right: 0; z-index: 3; }
    [data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] .sg-header-row) { margin-bottom: -1rem; }
    .st-key-sg-ov-hero .sg-header-row { top: 1.2rem; }
  }
  .st-key-sg-clock-script { position: absolute !important; width: 0; height: 0; overflow: hidden; }
  /* Overview hero: title, status and KPI strip on one dark glass band with a warm top light */
  .st-key-sg-ov-hero {
    position: relative; padding: 1.1rem 1.5rem 1.4rem; border-radius: 18px;
    background: radial-gradient(ellipse 60% 70% at 72% -20%, rgba(255, 206, 140, .10), transparent 70%),
      linear-gradient(180deg, rgba(28, 35, 47, .78), rgba(11, 16, 24, .86));
    border: 1px solid rgba(214, 162, 77, .26); box-shadow: 0 18px 40px rgba(0, 0, 0, .35), inset 0 1px 0 rgba(255, 224, 170, .08);
  }
  .st-key-sg-ov-hero h1 { padding-top: .2rem !important; padding-bottom: 0 !important; }
  .st-key-sg-ov-hero [data-testid="stCaptionContainer"] { margin-top: -.75rem; font-size: 1rem; color: #C9CED6; }
  /* KPI cards: slanted right edge, gold rim light, bright icon tiles */
  .st-key-sg-kpis .sg-kpi-frame { height: 100%; }
  .sg-kpi-frame { filter: drop-shadow(0 0 .7px rgba(240, 192, 110, .95)) drop-shadow(0 10px 16px rgba(0, 0, 0, .45));
    container-type: inline-size; container-name: sg-kpi; }  /* text-only block: containment cannot trap a fullscreen view */
  .sg-kpi {
    min-height: 104px; padding: .9rem 2.3rem .9rem 1rem !important; gap: .8rem !important; border: 0 !important;
    border-radius: 14px 0 0 14px !important; clip-path: polygon(0 0, 100% 0, calc(100% - 34px) 100%, 0 100%);
    background: linear-gradient(180deg, rgba(46, 54, 68, .82) 0%, rgba(20, 26, 36, .92) 58%, rgba(12, 17, 25, .96) 100%) !important;
    box-shadow: inset 0 1px 0 rgba(245, 200, 125, .42), inset 0 -1px 0 rgba(245, 200, 125, .14) !important;
  }
  .sg-kpi-icon { flex: 0 0 54px !important; height: 54px !important; border-radius: 13px !important; color: #fff !important; }
  .sg-kpi-body { min-width: 0; }
  .sg-kpi-icon .sg-icon { font-size: 31px; font-variation-settings: "FILL" 1; }
  .sg-tone-orange .sg-kpi-icon { background: linear-gradient(145deg, #FFB547, #C9650F) !important; box-shadow: 0 0 18px rgba(245, 150, 40, .5), inset 0 1px 0 rgba(255, 255, 255, .35); }
  .sg-tone-green .sg-kpi-icon { background: linear-gradient(145deg, #5BD07F, #1C7A3C) !important; box-shadow: 0 0 18px rgba(70, 190, 110, .4), inset 0 1px 0 rgba(255, 255, 255, .3); }
  .sg-tone-red .sg-kpi-icon { background: linear-gradient(145deg, #F2606A, #A1202B) !important; box-shadow: 0 0 18px rgba(230, 70, 80, .45), inset 0 1px 0 rgba(255, 255, 255, .3); }
  .sg-tone-blue .sg-kpi-icon { background: linear-gradient(145deg, #5FA2FF, #1F57C3) !important; box-shadow: 0 0 18px rgba(80, 140, 240, .45), inset 0 1px 0 rgba(255, 255, 255, .3); }
  .sg-kpi-label { font-size: 1.05rem !important; font-weight: 600 !important; color: #ECE8E0 !important; }
  .sg-kpi-value { font-size: 2.3rem !important; font-weight: 700 !important; line-height: 1.05 !important; }
  .sg-kpi-value.sg-kpi-text { font-size: 1.55rem !important; padding: .2rem 0 !important; }
  @container sg-kpi (max-width: 229px) {
    .sg-kpi { padding: .85rem 1.5rem .85rem .85rem !important; gap: .55rem !important; clip-path: polygon(0 0, 100% 0, calc(100% - 24px) 100%, 0 100%); }
    .sg-kpi-icon { flex-basis: 44px !important; height: 44px !important; border-radius: 11px !important; }
    .sg-kpi-icon .sg-icon { font-size: 25px; }
    .sg-kpi-label { font-size: .9rem !important; }
    .sg-kpi-value { font-size: 1.9rem !important; }
    .sg-kpi-value.sg-kpi-text { font-size: 1.2rem !important; }
  }
  @container sg-kpi (min-width: 180px) { .sg-kpi-label, .sg-kpi-value.sg-kpi-text { white-space: nowrap; } }
  @container sg-kpi (max-width: 179px) {
    .sg-kpi { flex-direction: column; align-items: flex-start !important; }
    .sg-kpi-icon { flex-basis: auto !important; width: 36px; height: 36px !important; }
    .sg-kpi-icon .sg-icon { font-size: 21px; }
    .sg-kpi-value { font-size: 1.6rem !important; }
  }
  /* metric tiles on every page: the KPI-card look of the reference (slanted right edge, gold rim light) */
  [data-testid="stElementContainer"]:has(> [data-testid="stMetric"]) {
    filter: drop-shadow(0 0 .6px rgba(240, 192, 110, .85)) drop-shadow(0 8px 14px rgba(0, 0, 0, .4));  /* metrics only: no fullscreen view inside */
  }
  [data-testid="stMetric"] {
    border: 0 !important; border-radius: 12px 0 0 12px !important; padding-right: 1.9rem !important;
    clip-path: polygon(0 0, 100% 0, calc(100% - 20px) 100%, 0 100%);
    background: linear-gradient(180deg, rgba(46, 54, 68, .80) 0%, rgba(20, 26, 36, .92) 58%, rgba(12, 17, 25, .96) 100%) !important;
    box-shadow: inset 0 1px 0 rgba(245, 200, 125, .40) !important;
  }
  [class*="st-key-sg-panel-"] [data-testid="stMetric"] { background: linear-gradient(180deg, rgba(40, 48, 62, .70), rgba(16, 21, 30, .85)) !important; }
  [data-testid="stMetricLabel"] p { font-family: var(--sg-cond) !important; font-size: .98rem !important; font-weight: 600 !important; color: #ECE8E0 !important; }
  [data-testid="stMetricValue"], [data-testid="stMetricValue"] div { font-family: var(--sg-cond) !important; font-weight: 700 !important; }
  /* panels: rounded dark glass with a fine gold rim */
  [class*="st-key-sg-panel-"] {
    border-radius: 14px !important; border: 1px solid rgba(214, 162, 77, .32) !important;
    background: linear-gradient(180deg, rgba(30, 37, 49, .82), rgba(12, 17, 25, .90)) !important;
    box-shadow: 0 12px 30px rgba(0, 0, 0, .38), inset 0 1px 0 rgba(255, 220, 160, .08) !important;
  }
  .st-key-sg-panel-feed { border-color: rgba(236, 186, 104, .62) !important; box-shadow: 0 0 22px rgba(228, 154, 50, .18), 0 12px 30px rgba(0, 0, 0, .38), inset 0 1px 0 rgba(255, 220, 160, .12) !important; }
  .sg-panel-title { font-size: 1.28rem !important; font-weight: 700 !important; color: #F7F3EA !important; align-items: center !important; }
  .sg-panel-meta { font-family: var(--sg-cond); font-size: .92rem !important; font-weight: 500 !important; color: var(--sg-muted) !important; }
  .sg-badge { display: inline-block; margin-left: .55rem; padding: .02rem .38rem; border-radius: 4px; font-size: .74rem; font-weight: 700; letter-spacing: .08em; vertical-align: .18rem; }
  .sg-badge-live { color: #FF5A5F; border: 1px solid rgba(255, 90, 95, .85); box-shadow: 0 0 8px rgba(255, 90, 95, .35); }
  .sg-badge-off { color: #C9CED6; border: 1px solid rgba(201, 206, 214, .55); }
  [class*="st-key-sg-head-"] [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: .5rem !important; }
  [class*="st-key-sg-head-"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child { flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; }
  [class*="st-key-sg-head-"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child { flex: 0 0 auto !important; min-width: 0 !important; width: auto !important; }
  [class*="st-key-sg-head-"] [data-testid="stColumn"]:last-child [data-testid="stVerticalBlock"] { align-items: flex-end; }
  [data-testid="stBaseButton-tertiary"] p { color: var(--sg-gold) !important; font-size: 1rem !important; font-weight: 600 !important; white-space: nowrap !important; }
  [data-testid="stBaseButton-tertiary"]:hover p { color: #F2CB7C !important; }
  @media (min-width: 768px) { [data-testid="stBaseButton-tertiary"] { min-height: 0; padding-top: 0; padding-bottom: 0; } }
  /* live-site feed frame */
  .sg-feed {
    position: relative; display: block !important; padding: 0 !important; overflow: hidden; border-radius: 10px !important;
    border: 1px solid rgba(255, 255, 255, .07) !important;
    background: radial-gradient(ellipse at 50% 40%, rgba(64, 78, 100, .38), transparent 70%),
      repeating-linear-gradient(135deg, rgba(255, 255, 255, .02) 0 12px, transparent 12px 24px), #0A0F17 !important;
  }
  .sg-feed { container-type: inline-size; container-name: sg-feed; }  /* text-only block */
  @container sg-feed (max-width: 380px) {
    .sg-feed-note { display: none; }
    .sg-feed-center .sg-icon { font-size: 32px !important; }
    .sg-feed-center { inset: 0 0 34px 0 !important; }
    .sg-feed-bar { height: 34px !important; font-size: .92rem !important; }
  }
  .sg-feed-center { position: absolute; inset: 0 0 40px 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: .35rem; text-align: center; padding: 0 1rem; }
  .sg-feed .sg-icon { font-size: 44px !important; color: #7F8A97 !important; }
  .sg-feed-bar {
    position: absolute; left: 0; right: 0; bottom: 0; height: 40px; display: flex; align-items: center; justify-content: space-between; padding: 0 .95rem;
    background: linear-gradient(0deg, rgba(0, 0, 0, .75), rgba(0, 0, 0, 0)); font-family: var(--sg-cond); font-weight: 600; font-size: 1rem; color: #F3F0E8;
  }
  .sg-feed-conn i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #8D98A5; margin-right: .45rem; vertical-align: -.02rem; }
  .sg-feed-conn.sg-on i { background: #3FD07A; box-shadow: 0 0 8px rgba(63, 208, 122, .75); }
  /* recent alerts: filled icon tiles */
  .sg-alert { align-items: center !important; gap: .8rem !important; padding: .6rem 0 !important; }
  .sg-alert-icon { flex: 0 0 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; }
  .sg-alert .sg-alert-icon .sg-icon { color: #fff !important; font-size: 23px !important; margin: 0 !important; font-variation-settings: "FILL" 1; }
  .sg-alert.sg-tone-warn .sg-alert-icon { background: linear-gradient(145deg, #FFB547, #CC6A12); box-shadow: 0 0 12px rgba(245, 150, 40, .38); }
  .sg-alert.sg-tone-critical .sg-alert-icon { background: linear-gradient(145deg, #F2606A, #A1202B); box-shadow: 0 0 12px rgba(230, 70, 80, .38); }
  .sg-alert.sg-tone-muted .sg-alert-icon { background: linear-gradient(145deg, #5B6675, #343D49); }
  .sg-alert-title { font-size: 1.02rem !important; font-weight: 700 !important; }
  .sg-alert-meta { font-family: var(--sg-cond); font-size: .9rem !important; }
  /* monitoring activity: glowing bar strip; every bar is a real count */
  .sg-bars { display: flex; align-items: flex-end; gap: 6px; height: 96px; padding-top: .35rem; }
  .sg-bars .sg-bar { flex: 1 1 0; height: 100%; display: flex; align-items: flex-end; border-radius: 3px; background: rgba(214, 162, 77, .08); }
  .sg-bars .sg-bar i { display: block; width: 100%; height: calc(var(--h) * 100%); border-radius: 3px 3px 1px 1px;
    background: linear-gradient(180deg, #FFCB66, #C77A14); box-shadow: 0 0 10px rgba(240, 160, 50, .5); }
  .sg-bars-axis { display: flex; justify-content: space-between; margin-top: .35rem; font-size: .76rem; color: var(--sg-muted-2); }
  /* system processing */
  .sg-proc-line { font-size: .92rem; color: var(--sg-muted); margin: .12rem 0; }
  .sg-proc-row { display: flex; align-items: center; gap: .75rem; margin: .6rem 0 .2rem; }
  .sg-proc-track { flex: 1; height: 7px; border-radius: 4px; background: rgba(255, 255, 255, .08); overflow: hidden; }
  .sg-proc-track i { display: block; height: 100%; width: calc(var(--w) * 100%); background: linear-gradient(90deg, #C77A14, #FFCB66); box-shadow: 0 0 8px rgba(240, 160, 50, .5); }
  .sg-proc-row span { font-family: var(--sg-cond); font-weight: 600; font-size: .95rem; color: var(--sg-ivory); }
  /* sidebar: hex logo, condensed labels, glowing amber pill for the active page */
  [data-testid="stSidebar"] { background: linear-gradient(180deg, rgba(18, 26, 38, .98) 0%, rgba(10, 15, 23, .99) 100%) !important; border-right: 1px solid rgba(214, 162, 77, .24) !important; }
  .sg-brand { gap: .75rem !important; }
  .sg-brand-mark {
    position: relative; width: 42px !important; height: 46px !important; font-size: 0 !important; border-radius: 0 !important;
    background: conic-gradient(from 200deg, #FFD27A, #E8901F, #9A520C, #F0A63A, #FFD27A) !important;
    clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%) !important;
  }
  .sg-brand-mark::after { content: ""; position: absolute; inset: 10px 9px; background: #121A26; clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%); }
  .sg-brand-name { font-size: 1.45rem !important; font-weight: 700 !important; }
  .sg-brand-sub { font-size: .98rem !important; color: #C9CED6 !important; margin-top: -.1rem !important; }
  [data-testid="stSidebar"] [role="radiogroup"] label { padding: .55rem .85rem !important; border-radius: 10px !important; border: 1px solid transparent !important; margin: 1px 0 !important; }
  [data-testid="stSidebar"] [role="radiogroup"] label p { font-size: 1.08rem !important; color: #C9CED6 !important; font-weight: 500 !important; }
  [data-testid="stSidebar"] [data-testid="stRadioOption"] span[role="img"] { color: #AEB6BF !important; }
  [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
    background: linear-gradient(90deg, rgba(232, 160, 58, .50) 0%, rgba(160, 100, 30, .30) 60%, rgba(60, 45, 25, .22) 100%) !important;
    border: 1px solid rgba(245, 190, 105, .85) !important; box-shadow: 0 0 16px rgba(228, 154, 50, .35), inset 0 1px 0 rgba(255, 230, 180, .3) !important;
  }
  [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p,
  [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) span[role="img"] { color: #FFF4DF !important; font-weight: 700 !important; }
  /* scene: dark angular slogan panel with gold edges at the bottom right (wide screens) */
  .sg-scene-panel { position: fixed; right: 0; bottom: 0; width: var(--sg-scene-w); height: 46vh; pointer-events: none; z-index: 1;
    background: url("__PANEL__") center / 100% 100% no-repeat; }
  .sg-scene-promise { z-index: 2 !important; bottom: 8vh !important; font-family: var(--sg-cond); font-size: clamp(1.15rem, 1.6vw, 2.3rem) !important;
    width: calc(var(--sg-scene-w) * .86) !important; }
  @media (min-width: 1400px) and (max-width: 1499px) { .sg-scene-promise { display: block !important; } }
  @media (max-width: 1399px) { .sg-scene-panel { display: none; } }
  @media (max-width: 767px) {
    .st-key-sg-ov-hero { padding: .8rem .8rem 1rem; }
  }
  @media (prefers-reduced-motion: reduce) {
    * { animation: none !important; transition: none !important; }
    [data-testid="stSpinner"] > div::before { animation: none !important; }  /* `*` does not match pseudo-elements */
  }
</style>
""".replace("__BG__", BACKGROUND_URL).replace("__BOUNDARY__", BOUNDARY_URI).replace("__PANEL__", PANEL_URI)


def inject_css() -> None:
    st.markdown(CSS + SHELL_CSS + SCENE_PROMISE, unsafe_allow_html=True)
    with st.container(key="sg-clock-script"):
        st.html(CLOCK_SCRIPT, unsafe_allow_javascript=True)


def style_fig(fig, height: int = 320, *, x_title: str | None = None, y_title: str | None = None):
    """Uniform Plotly styling on the dark theme: transparent background, muted grid, labelled axes."""
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=56, b=8 if not fig.layout.showlegend and len(fig.data) < 2 else 90),
        title=dict(font=dict(size=14)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, size=12),
        legend=dict(title_text="", orientation="h", yanchor="top", y=-0.28, xanchor="left", x=0),
        colorway=CATEGORICAL,
    )
    fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER, linecolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER, linecolor=BORDER)
    if x_title is not None:
        fig.update_xaxes(title_text=x_title)
    if y_title is not None:
        fig.update_yaxes(title_text=y_title)
    return fig
