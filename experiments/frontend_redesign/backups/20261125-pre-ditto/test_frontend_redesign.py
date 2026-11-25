"""Frontend redesign Phase 2: shared shell, static asset and local-only server settings."""

import hashlib
import tomllib
from pathlib import Path

from PIL import Image
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
ORIGINAL = ROOT / "assets/images/SiteGuard_AI_Cinematic_Construction_Background_1600h.png"
ORIGINAL_SHA256 = "565376e21a0e1e532b0be4da1be01fc7cbe7f32ad785d382b5bc16e08957f0ec"
PAGES = ["Overview", "Live Monitoring", "Image Inspection", "Video Inspection", "Safety Events", "Analytics",
         "Model Evaluation", "Settings / About"]


def test_static_folder_holds_only_the_approved_background():
    """Everything in static/ is served to the browser, hidden files included, so nothing else may be there."""
    found = sorted(p.relative_to(STATIC).as_posix() for p in STATIC.rglob("*"))
    assert found == ["siteguard_background.webp"]


def test_background_is_a_full_size_copy_of_the_original():
    with Image.open(STATIC / "siteguard_background.webp") as im:
        assert im.format == "WEBP" and im.size == (2843, 1600)


def test_original_image_and_provenance_are_preserved():
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == ORIGINAL_SHA256
    assert "original generated asset" in (ORIGINAL.parent / "PROVENANCE.md").read_text()


def test_server_is_local_only_and_serves_static_files():
    server = tomllib.loads((ROOT / ".streamlit/config.toml").read_text())["server"]
    assert server["address"] == "localhost"
    assert server["enableStaticServing"] is True


def test_shell_css_uses_the_static_background_and_is_click_through():
    from src.ui import theme

    assert theme.BACKGROUND_URL in theme.SHELL_CSS
    assert "pointer-events: none" in theme.SHELL_CSS and "prefers-reduced-motion" in theme.SHELL_CSS


def test_every_page_renders_inside_the_shell(tmp_path, monkeypatch):
    monkeypatch.setenv("SITEGUARD_EVENTS_DB", str(tmp_path / "events.db"))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    for page in PAGES:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, page
        assert at.sidebar.radio[0].value == page
        assert any("siteguard_background.webp" in m.value for m in at.markdown), page
        assert any("sg-status-pill" in m.value for m in at.markdown), page


def test_overview_shows_the_approved_kpis_and_no_invented_values(tmp_path, monkeypatch):
    monkeypatch.setenv("SITEGUARD_EVENTS_DB", str(tmp_path / "events.db"))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception
    kpis = [m.value for m in at.markdown if 'class="sg-kpi ' in m.value]
    assert len(kpis) == 4
    text = " ".join(kpis)
    for label in ("People detected", "Pending review", "Potential alerts", "Camera status", "Not running"):
        assert label in text
    assert "%" not in text  # no compliance rate and no progress percentage
    assert not any("compliance rate" in m.value.lower() for m in at.markdown)
    buttons = {b.label for b in at.button}
    assert {"Open Live Monitoring", "View all in Safety Events", "Inspect an image", "Inspect a video"} <= buttons


# ------------------------------------------------------------------ Phase 4: remaining pages
PAGE_LIVE_SHA256 = "c8fdf33c65812883feda0d7ad13cb98328bb1d6fb2866443e695b395d4cc3fa1"  # page_live as of the Phase 0 backup


def test_live_page_code_is_unchanged_by_the_redesign():
    """Live Monitoring is styled through CSS only. The camera lifecycle, start guard and frame callback in page_live
    must stay byte-identical to the version validated by the camera programme."""
    import ast

    source = (ROOT / "app.py").read_text()
    fn = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "page_live")
    assert hashlib.sha256(ast.get_source_segment(source, fn).encode()).hexdigest() == PAGE_LIVE_SHA256


def test_spinner_shows_three_dots_and_respects_reduced_motion():
    from src.ui.theme import SHELL_CSS

    assert '[data-testid="stSpinner"] > div::before' in SHELL_CSS and "@keyframes sg-dot-seq" in SHELL_CSS
    reduced = SHELL_CSS[SHELL_CSS.rindex("prefers-reduced-motion"):]
    assert '[data-testid="stSpinner"] > div::before { animation: none !important; }' in reduced


def test_restyled_pages_keep_their_controls(tmp_path, monkeypatch, make_det):
    """Panels are presentation only: the existing widgets and section titles are still rendered."""
    import streamlit as st

    from src.compliance.compliance_analyzer import ComplianceAnalyzer, ComplianceRules
    from src.events.event_manager import EventManager
    from src.events.event_store import EventStore

    db = tmp_path / "phase4.db"
    monkeypatch.setenv("SITEGUARD_EVENTS_DB", str(db))
    st.cache_resource.clear()
    result = ComplianceAnalyzer(ComplianceRules(required_ppe=("helmet",))).analyze(
        [make_det("Person", 0.9, 100, 100, 200, 400), make_det("no_helmet", 0.9, 130, 90, 170, 130)])
    EventManager(EventStore(db), "image", "synthetic.jpg", save_evidence=False).process(result, now=0.0)
    try:
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
        at.sidebar.radio[0].set_value("Safety Events").run()
        assert not at.exception
        assert {"Category", "Source", "Review status"} <= {m.label for m in at.multiselect}
        assert "Review an event" in [h.value for h in at.subheader] and at.dataframe
        at.sidebar.radio[0].set_value("Model Evaluation").run()
        titles = " ".join(h.value for h in at.subheader)
        assert not at.exception
        for section in ("1. Active model", "2. Same-split", "5. Viewpoint"):
            assert section in titles
        at.sidebar.radio[0].set_value("Settings / About").run()
        titles = [h.value for h in at.subheader]
        assert not at.exception and {"Detection", "Events", "Compliance rules", "Model", "About"} <= set(titles)
        assert any(s.label == "Active model" for s in at.selectbox)
    finally:
        st.cache_resource.clear()


def test_video_result_panels_render_from_a_stored_summary(tmp_path, monkeypatch):
    """The result panels of Video Inspection render from the summary kept in session state (no processing is run)."""
    import types

    import streamlit as st

    monkeypatch.setenv("SITEGUARD_EVENTS_DB", str(tmp_path / "video.db"))
    st.cache_resource.clear()
    summary = types.SimpleNamespace(
        frames_read=30, frames_processed=30, sampling_policy="every frame analysed", seconds_elapsed=1.2, events=[],
        suppressed_repeats=0, stopped_early=False, inference_ms={"median": 9.0, "p95": 12.0}, frames_not_analysed=0,
        output_path=tmp_path / "missing.mp4", class_counts={"Person": 30}, worker_status_frames={"compliant_evidence": 30})
    try:
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
        at.session_state["last_video"] = summary
        at.sidebar.radio[0].set_value("Video Inspection").run()
        assert not at.exception
        assert {"Frames read", "Frames analysed", "Processing time", "Events recorded", "Repeats suppressed"} <= {m.label for m in at.metric}
        assert any("annotated output video is missing" in e.value for e in at.error)
        assert "Result" in [h.value for h in at.subheader]
    finally:
        st.cache_resource.clear()


# ------------------------------------------------------------------ Phase 5: responsive and accessibility hardening
def _contrast(fg: str, bg: str) -> float:
    def lum(hex_colour: str) -> float:
        channels = [int(hex_colour.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    hi, lo = sorted((lum(fg), lum(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _mix(fg: str, alpha: float, bg: str) -> str:
    f = [int(fg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(bg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(alpha * x + (1 - alpha) * y):02X}" for x, y in zip(f, b))


def test_text_colours_meet_wcag_aa_contrast():
    """Normal-size text needs 4.5:1. Values are the tokens in SHELL_CSS over their real backgrounds."""
    from src.ui.theme import SHELL_CSS

    ink, navy, amber = "#080D14", "#0F1824", "#E49A32"
    panel = _mix("#121923", 0.90, ink)
    assert "--sg-muted-2: #8D98A5" in SHELL_CSS
    assert _contrast("#8D98A5", panel) >= 4.5 and _contrast("#8D98A5", navy) >= 4.5  # metadata text
    assert '[data-testid^="stBaseButton-primary"] p' in SHELL_CSS and "color: #0B1119 !important" in SHELL_CSS
    assert _contrast("#0B1119", amber) >= 4.5  # primary button label (white on amber was 2.3:1)
    assert "rgba(228, 154, 50, .22)" in SHELL_CSS
    assert _contrast(amber, _mix(amber, 0.22, navy)) >= 4.5  # active navigation label


def test_keyboard_focus_is_visible_on_the_navigation():
    from src.ui.theme import SHELL_CSS

    assert 'label:has(input:focus-visible) { outline: 2px solid var(--sg-amber)' in SHELL_CSS


def test_panels_do_not_trap_fullscreen_views():
    """backdrop-filter (like transform or containment) makes a panel the containing block of position:fixed children,
    which kept Streamlit's fullscreen charts, tables and images inside the panel."""
    import re

    from src.ui.theme import CSS, SHELL_CSS

    assert not re.search(r"backdrop-filter\s*:", CSS + SHELL_CSS)
    # containment is used only on blocks that hold metric tiles or the model identity table, never charts or tables
    assert SHELL_CSS.count("container-type: inline-size") == 2


def test_narrow_layout_rules_are_present():
    from src.ui.theme import SHELL_CSS

    assert "@container sg-metric-row (max-width: 640px)" in SHELL_CSS  # metric tiles two per row instead of cut values
    assert '[data-testid="stImageContainer"] { min-width: 0 !important' in SHELL_CSS  # fixed-width plots never overflow
    assert "@media (max-width: 1000px)" in SHELL_CSS  # rows of panels stack on narrow content
    assert '[data-testid^="stBaseButton"] { min-height: 44px; }' in SHELL_CSS  # touch-sized buttons on phones
