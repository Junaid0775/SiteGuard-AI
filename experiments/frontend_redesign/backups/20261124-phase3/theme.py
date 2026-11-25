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
SCENE_PROMISE = '<div class="sg-scene-promise" aria-hidden="true"><b>Safer Sites.</b>Smarter Tomorrow.</div>'

SHELL_CSS = """
<style>
  :root {
    --sg-ink: #080D14; --sg-navy: #0F1824; --sg-graphite: #161D27;
    --sg-panel: rgba(18, 25, 35, 0.90); --sg-panel-raised: rgba(28, 37, 49, 0.92);
    --sg-border: rgba(214, 162, 77, 0.24); --sg-border-soft: rgba(255, 255, 255, 0.06);
    --sg-gold: #D6A24D; --sg-amber: #E49A32; --sg-ivory: #F3F0E8; --sg-muted: #AEB6BF; --sg-muted-2: #778391;
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
    border: 1px solid var(--sg-border); border-radius: 6px; box-shadow: 0 8px 24px rgba(0, 0, 0, .28); backdrop-filter: blur(6px);
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
  .sg-kpi-foot { font-size: .72rem; color: var(--sg-muted-2); margin-top: .1rem; }
  .sg-kpi-value.sg-kpi-text { font-size: 1.35rem; padding: .2rem 0; }
  .st-key-sg-kpis .sg-kpi { min-height: 112px; }
  [class*="st-key-sg-panel-"] {
    background: var(--sg-panel); border: 1px solid var(--sg-border); border-radius: 6px; padding: 1rem 1.05rem 1.1rem;
    box-shadow: 0 8px 24px rgba(0, 0, 0, .28); backdrop-filter: blur(6px);
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
  .sg-dots { display: inline-flex; gap: 5px; align-items: center; vertical-align: middle; }
  .sg-dots i { width: 6px; height: 6px; border-radius: 50%; background: var(--sg-gold); animation: sg-dot 1.2s infinite ease-in-out; }
  .sg-dots i:nth-child(2) { animation-delay: .15s; }
  .sg-dots i:nth-child(3) { animation-delay: .3s; }
  @keyframes sg-dot { 0%, 80%, 100% { opacity: .25; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-3px); } }
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
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
""".replace("__BG__", BACKGROUND_URL).replace("__BOUNDARY__", BOUNDARY_URI)


def inject_css() -> None:
    st.markdown(CSS + SHELL_CSS + SCENE_PROMISE, unsafe_allow_html=True)


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
