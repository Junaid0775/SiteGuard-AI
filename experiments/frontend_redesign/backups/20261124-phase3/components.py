"""Shared presentation components for the SiteGuard AI dashboard.

Rules applied everywhere:
* every status is written as text (colour is only a second cue);
* dynamic text placed inside HTML is escaped;
* unknown values are shown as "Unknown" / "-", never guessed;
* detector scores are called "detector confidence", never probability.
"""

from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

from src.ui.theme import REVIEW_BADGE, REVIEW_LABELS, STATUS_BADGE


def set_header_status(text: str, level: str = "ok") -> None:
    """Called once per run by app.py with the real model state; every page header shows it."""
    st.session_state["_sg_header_status"] = (text, level if level in ("ok", "critical") else "ok")


def page_header(kicker: str, title: str, caption: str | None = None) -> None:
    """Kicker and status pill, st.title (tests look for the page name in st.title), one-line description."""
    text, level = st.session_state.get("_sg_header_status", ("System online", "ok"))
    st.markdown(f'<div class="sg-header-row"><div class="sg-kicker">{html.escape(kicker)}</div>'
                f'<div class="sg-status-pill sg-{level}"><span class="sg-dot"></span>{html.escape(text)}</div></div>',
                unsafe_allow_html=True)
    st.title(title)
    if caption:
        st.caption(caption)


def scope_note(text: str) -> None:
    """Small muted line stating the scope / source / time window of the figures that follow (markdown allowed)."""
    st.markdown(f'<div class="sg-scope">{text}</div>', unsafe_allow_html=True)


def esc(value) -> str:
    return html.escape(str(value))


def status_badge_md(status: str, labels: dict[str, str]) -> str:
    """Markdown badge for a compliance status, with its text label."""
    return f":{STATUS_BADGE.get(status, 'gray')}-badge[{labels.get(status, status)}]"


def review_label(status: str) -> str:
    return REVIEW_LABELS.get(status, status)


def review_badge_md(status: str) -> str:
    return f":{REVIEW_BADGE.get(status, 'gray')}-badge[{review_label(status)}]"


def empty_state(message: str, hint: str | None = None) -> None:
    st.info(message)
    if hint:
        st.caption(hint)


def kv_table(rows: list[tuple[str, str]]) -> None:
    """Read-only key/value table (values are escaped; `code` spans allowed via the (label, value, True) form)."""
    body = []
    for row in rows:
        label, value = row[0], row[1]
        is_code = len(row) > 2 and row[2]
        cell = f"<code>{esc(value)}</code>" if is_code else esc(value)
        body.append(f"<tr><td>{esc(label)}</td><td>{cell}</td></tr>")
    st.markdown(f'<table class="sg-kv">{"".join(body)}</table>', unsafe_allow_html=True)


def fmt_num(v, digits: int = 3, unit: str = "") -> str:
    if v is None:
        return "-"
    try:
        return f"{float(v):.{digits}f}{unit}"
    except (TypeError, ValueError):
        return "-"


def model_status_line(info: dict) -> str:
    """One-line model status (markdown) used in the sidebar and on Overview."""
    if info.get("status") == "fallback":
        return ":orange-badge[Fallback model in use]"
    if info.get("status") in ("active", "explicit weights"):
        return ":green-badge[Model loaded]"
    return ":gray-badge[Model status unknown]"


def model_identity_rows(info: dict, full_sha256: str | None = None) -> list[tuple]:
    """Identity rows from PPEDetector.info(). The SHA-256 prefix is labelled as a prefix; the full hash only when given."""
    weights = Path(str(info.get("weights", "")))
    try:
        weights_display = str(weights.relative_to(Path.cwd()))
    except ValueError:
        weights_display = weights.name
    rows = [
        ("Registry key", info.get("model_key") or "Unknown", True),
        ("Status", {"active": "Active", "fallback": "Fallback (active model could not be used)",
                    "explicit weights": "Explicit weights"}.get(info.get("status"), "Unknown")),
        ("Architecture", info.get("architecture") or "Unknown"),
        ("Inference image size", f"{info['image_size']} px" if info.get("image_size") else "Unknown"),
        ("Checkpoint", weights_display, True),
    ]
    if full_sha256:
        rows.append(("SHA-256", full_sha256, True))
    elif info.get("sha256"):
        rows.append(("SHA-256 (first 16 hex characters)", f"{info['sha256']}", True))
    rows.append(("Device", info.get("device") or "Unknown"))
    rows.append(("Classes", str(len(info.get("class_names", {}))) if info.get("class_names") else "Unknown"))
    return rows


def advisory(text: str | None = None) -> None:
    st.caption(text or "Advisory only: detections are potential issues for human review, not confirmed violations. "
               "No detected event is not proof of compliance.")


# ------------------------------------------------------------------ redesign components (Phase 3)
def icon(name: str) -> str:
    """Material Symbols ligature (font bundled with Streamlit); decorative, hidden from screen readers."""
    return f'<span class="sg-icon" aria-hidden="true">{html.escape(name)}</span>'


def kpi_card(label: str, value: str, icon_name: str, tone: str = "gold", foot: str | None = None) -> None:
    foot_html = f'<div class="sg-kpi-foot">{html.escape(foot)}</div>' if foot else ""
    text_cls = "" if str(value).replace(",", "").replace(".", "").isdigit() else " sg-kpi-text"  # words get a smaller size
    st.markdown(f'<div class="sg-kpi sg-tone-{html.escape(tone)}"><div class="sg-kpi-icon">{icon(icon_name)}</div>'
                f'<div class="sg-kpi-body"><div class="sg-kpi-label">{html.escape(label)}</div>'
                f'<div class="sg-kpi-value{text_cls}">{html.escape(str(value))}</div>{foot_html}</div></div>', unsafe_allow_html=True)


def panel_title(title: str, meta: str | None = None) -> None:
    meta_html = f'<span class="sg-panel-meta">{html.escape(meta)}</span>' if meta else ""
    st.markdown(f'<div class="sg-panel-title"><span>{html.escape(title)}</span>{meta_html}</div>', unsafe_allow_html=True)


def alert_list(rows: list[dict]) -> None:
    """rows: icon, tone, title, meta. The status is always written in the text, never shown by colour alone."""
    items = "".join(f'<div class="sg-alert sg-tone-{html.escape(r["tone"])}">{icon(r["icon"])}<div>'
                    f'<div class="sg-alert-title">{html.escape(r["title"])}</div>'
                    f'<div class="sg-alert-meta">{html.escape(r["meta"])}</div></div></div>' for r in rows)
    st.markdown(f'<div class="sg-alerts">{items}</div>', unsafe_allow_html=True)


def camera_frame(running: bool) -> None:
    """Placeholder frame for the Overview feed panel. It never shows an image: the camera runs only on Live Monitoring."""
    state = "Camera running on Live Monitoring" if running else "Camera not running"
    note = ("Live video is shown on Live Monitoring." if running else
            "Live video appears on Live Monitoring after you press START. Leaving that page closes the camera session.")
    st.markdown(f'<div class="sg-feed" role="img" aria-label="{html.escape(state)}">{icon("videocam" if running else "videocam_off")}'
                f'<div class="sg-feed-state">{html.escape(state)}</div><div class="sg-feed-note">{html.escape(note)}</div></div>',
                unsafe_allow_html=True)


def loading_dots(label: str = "Working") -> str:
    """Three-dot indicator for real work in progress only; static when reduced motion is requested."""
    return f'<span class="sg-dots" role="status" aria-label="{html.escape(label)}"><i></i><i></i><i></i></span>'
