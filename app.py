"""SiteGuard AI - Streamlit dashboard.

Start with:
    .venv/bin/streamlit run app.py

All numbers on every page come from real model output stored in the local
SQLite database (outputs/siteguard_events.db) or from real evaluation files in
experiments/. Nothing is invented: when there is no data, the page says so.

Frontend completion (2026-11-23, experiments/frontend_completion/): dark industrial theme, shared presentation
components in src/ui/, read-only settings (thresholds can no longer be edited from the UI), model-evaluation
page with the accuracy-programme research results. Backend calls are unchanged; the previous version of this
file is kept in experiments/frontend_completion/backups/20261123-phase0/app.py.
"""

from __future__ import annotations

import hashlib
import json
import platform
import tempfile
import time
import uuid
from datetime import date, datetime, time as dtime
from importlib import metadata
from pathlib import Path

import cv2
import os

import pandas as pd
import plotly.express as px
import streamlit as st
import yaml

from src.utils.paths import (  # must be imported before ultralytics (sets YOLO_CONFIG_DIR)
    EXPERIMENTS_DIR,
    OUTPUTS_DIR,
    SETTINGS_CONFIG,
    TRAINED_DIR,
    ensure_output_dirs,
    load_settings,
)
from src.compliance.compliance_analyzer import (
    COMPLIANT_EVIDENCE,
    POTENTIAL_VIOLATION,
    STATUS_LABELS,
    UNCERTAIN,
    ComplianceAnalyzer,
    ComplianceRules,
)
from src.detection.detector import IncompatibleModelError, ModelNotFoundError, PPEDetector
from src.detection.model_registry import ModelRegistry, file_sha256
from src.utils.logging_config import setup_logging
from src.detection.image_processor import (
    MAX_IMAGE_BYTES,
    MAX_IMAGE_SIDE,
    SUPPORTED_IMAGE_TYPES,
    InvalidImageError,
    decode_image_bytes,
    encode_jpeg,
    inspect_image,
)
from src.detection.video_processor import SUPPORTED_VIDEO_TYPES, InvalidVideoError, process_video
from src.events.event_manager import EventManager
from src.events.event_store import REVIEW_STATUSES, EventStore, InspectionRecord
from src.reporting.report_generator import CATEGORY_LABELS, DISCLAIMER, events_report_frame, events_to_csv_bytes, inspections_report_frame
from src.ui import evaluation_data
from src.ui.live_video import (
    VIDEO_HTML_ATTRS,
    applied_return_video_bitrate,
    clear_live_component_absent,
    configure_return_video_bitrate,
    configure_uplink_hints,
    mark_live_component_absent,
    protect_live_stream,
)
from src.ui.components import (
    advisory,
    empty_state,
    fmt_num,
    kv_table,
    model_identity_rows,
    model_status_line,
    page_header,
    review_badge_md,
    review_label,
    scope_note,
    status_badge_md,
)
from src.ui.theme import ACCENT, CATEGORICAL, GOLD, REVIEW_COLORS, REVIEW_LABELS, inject_css, style_fig
from src.ui.components import activity_bars, alert_list, camera_frame, kpi_card, panel_title, processing_status, set_header_status

st.set_page_config(page_title="SiteGuard AI", page_icon=":material/health_and_safety:", layout="wide")
ensure_output_dirs()
inject_css()

PAGES = [
    "Overview", "Live Monitoring", "Image Inspection", "Video Inspection",
    "Safety Events", "Analytics", "Model Evaluation", "Settings / About",
]
# Errors that mean "no usable model": the two documented ones (ML handoff §3.1) plus a registry key that does not
# exist (e.g. a mistyped SITEGUARD_MODEL), which PPEDetector() reports as KeyError. Handled in the UI only.
MODEL_ERRORS = (ModelNotFoundError, IncompatibleModelError, KeyError, ValueError)
CAMERA_VALIDATION = ("Physical-camera validation of the current build: **pending** (needs the project owner present; "
                     "see REPORT-024 §B7). Recorded replay results are not a physical-camera result.")


@st.cache_resource
def app_logging():
    """Application log (active model identity, fallbacks): outputs/logs/siteguard_app.log. Configured once per process."""
    return setup_logging(log_file=OUTPUTS_DIR / "logs" / "siteguard_app.log")


app_logging()


def active_image_size(s: dict) -> int:
    """One inference size for image, video and live (R2): the active model's registry size, else inference.image_size."""
    try:
        reg = ModelRegistry.from_settings(s)
        return int(reg.get(reg.active).image_size or s["inference"]["image_size"])
    except (KeyError, TypeError, ValueError):
        return int(s["inference"]["image_size"])


# --------------------------------------------------------------------------- state
def default_cfg() -> dict:
    """Runtime settings, always read from configs/settings.yaml (read-only in the UI: ML handoff §3.4)."""
    s = load_settings()
    return {
        "confidence": s["inference"]["confidence_threshold"],
        "image_size": active_image_size(s),
        "required_ppe": list(s["compliance"]["required_ppe"]),
        "person_confidence": s["compliance"]["person_confidence"],
        "violation_confidence": s["compliance"]["violation_confidence"],
        "evidence_confidence": s["compliance"]["evidence_confidence"],
        "cooldown_seconds": s["events"]["cooldown_seconds"],
        "min_consecutive_hits": s["events"]["min_consecutive_hits"],
        "frame_stride": s["video"]["frame_stride"],
        "max_frames": s["video"]["max_frames"],
        "live_every_n": s["live"]["process_every_n_frames"],
    }


st.session_state.cfg = default_cfg()
cfg: dict = st.session_state.cfg


@st.cache_resource(show_spinner="Loading SiteGuard model...")
def get_detector() -> PPEDetector:
    return PPEDetector().load()


@st.cache_resource
def get_store() -> EventStore:
    return EventStore()


@st.cache_data(show_spinner=False)
def checkpoint_sha256(path: str, mtime: float) -> str:
    """Full SHA-256 of the loaded checkpoint (cached per file version) for the Settings page."""
    return file_sha256(Path(path))


def get_analyzer() -> ComplianceAnalyzer:
    rules = ComplianceRules.from_settings({
        "required_ppe": cfg["required_ppe"],
        "person_confidence": cfg["person_confidence"],
        "violation_confidence": cfg["violation_confidence"],
        "evidence_confidence": cfg["evidence_confidence"],
    })
    return ComplianceAnalyzer(rules)


def model_error() -> Exception | None:
    try:
        get_detector()
        return None
    except MODEL_ERRORS as exc:
        return exc


def detector_or_stop() -> PPEDetector:
    try:
        return get_detector()
    except MODEL_ERRORS as exc:
        st.error(f"No usable model is available (active and fallback both failed). Inspection is disabled. {exc}")
        st.stop()


def model_ready() -> bool:
    return model_error() is None


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except (OSError, json.JSONDecodeError):
        return None


def rgb(img_bgr):
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def settings_signature() -> str:
    return hashlib.sha1(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:10]


def save_inspection(source_type: str, source_name: str, frames: int, persons: int, class_counts: dict, events: int) -> None:
    get_store().add_inspection(InspectionRecord(
        inspection_id=f"INS-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}",
        timestamp=datetime.now().isoformat(timespec="seconds"),
        source_type=source_type, source_name=source_name, frames_processed=frames,
        person_detections=persons, class_counts=class_counts, events_created=events, settings=dict(cfg),
    ))


def go_to(page_name: str) -> None:
    st.session_state.nav = page_name


def time_range_text(events: pd.DataFrame, inspections: pd.DataFrame) -> str:
    stamps = pd.concat([pd.to_datetime(events["timestamp"]) if not events.empty else pd.Series(dtype="datetime64[ns]"),
                        pd.to_datetime(inspections["timestamp"]) if not inspections.empty else pd.Series(dtype="datetime64[ns]")])
    if stamps.empty:
        return "no records"
    return f"{stamps.min():%d %b %Y %H:%M} to {stamps.max():%d %b %Y %H:%M}"


def events_display_frame(events: pd.DataFrame) -> pd.DataFrame:
    """Readable event table for the UI (display only: stored values and the CSV export are unchanged)."""
    df = events_report_frame(events)
    for col in df.columns:
        if "status" in col.lower():
            df[col] = df[col].map(lambda v: REVIEW_LABELS.get(v, v))
    return df.rename(columns={c: "Detector confidence" for c in df.columns if c.lower() == "confidence"})


def compliance_panel(result) -> None:
    counts = result.counts
    c1, c2, c3 = st.columns(3)
    c1.metric("Potential violation", counts[POTENTIAL_VIOLATION], border=True,
              help="Required PPE item judged missing for a worker (missing-PPE box at or above the alert threshold).")
    c2.metric("Compliant evidence", counts[COMPLIANT_EVIDENCE], border=True,
              help="Required PPE item visibly detected on the worker.")
    c3.metric("Uncertain", counts[UNCERTAIN], border=True,
              help="Not enough visual evidence either way. Uncertain is never counted as compliant.")
    if not result.workers:
        st.info("No worker (Person) detected above the person-confidence threshold, so no compliance assessment was made.")
    for w in result.workers:
        with st.container(border=True):
            st.markdown(f"**{w.worker_ref}** · person detector confidence {w.person.confidence:.2f} · "
                        f"{status_badge_md(w.status, STATUS_LABELS)}")
            rows = [{"PPE item": a.item, "Status": STATUS_LABELS[a.status],
                     "Detector confidence": None if a.confidence is None else round(a.confidence, 2), "Reason": a.reason}
                    for a in w.items.values()]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    floating = result.unassigned_negative(cfg["violation_confidence"])
    if floating or result.ambiguous:
        st.caption(
            f"{len(floating)} missing-PPE detection(s) could not be linked to exactly one worker "
            f"({len(result.ambiguous)} ambiguous between overlapping workers). They are shown on the image "
            "but do not create events."
        )


def close_live_session_if_left() -> None:
    """Spec §5.3 / §6.5: when another page is shown, an open live session is saved (if it analysed frames) and closed.
    A closed LiveFrameProcessor returns raw frames only, so no stale boxes can be drawn afterwards."""
    proc = st.session_state.pop("live_processor", None)
    if proc is None:
        return
    snap = proc.snapshot()
    if snap["frames_analysed"] > 0 and not st.session_state.get("live_saved"):
        save_inspection("live_camera", "browser webcam", snap["frames_analysed"], snap["person_detections"],
                        snap["class_counts"], len(proc.events.events_created))
    proc.close()
    st.session_state.live_was_playing = False
    st.session_state.pop("live_key", None)


# ------------------------------------------------------------------------- sidebar
NAV_ICONS = {"Overview": "home", "Live Monitoring": "videocam", "Image Inspection": "image",
             "Video Inspection": "video_library", "Safety Events": "notifications", "Analytics": "query_stats",
             "Model Evaluation": "deployed_code", "Settings / About": "settings"}  # Material Symbols bundled with Streamlit
NAV_LABELS = {"Settings / About": "Settings"}  # display only; page values, deep links and session keys are unchanged
with st.sidebar:
    st.markdown(
        '<div class="sg-brand"><div class="sg-brand-mark" aria-hidden="true"></div><div><div class="sg-brand-name">SiteGuard AI</div>'
        '<div class="sg-brand-sub">Construction Safety</div></div></div>',
        unsafe_allow_html=True,
    )
    if "nav" not in st.session_state and st.query_params.get("page") in PAGES:
        st.session_state.nav = st.query_params.get("page")  # deep link, e.g. ?page=Safety%20Events
    page = st.radio("Navigation", PAGES, label_visibility="collapsed", key="nav",
                    format_func=lambda p: f":material/{NAV_ICONS.get(p, 'circle')}: {NAV_LABELS.get(p, p)}")  # values unchanged
    if st.query_params.get("page") != page:
        st.query_params["page"] = page  # keeps the current page on browser reload
    st.markdown('<div class="sg-side-label">Model</div>', unsafe_allow_html=True)
    _err = model_error()
    if _err is None:
        _info = get_detector().info()
        set_header_status("System Online")
        st.markdown(model_status_line(_info))
        if _info.get("status") == "fallback":
            st.warning("The configured model could not be used, so the fallback model is running: "
                       + "; ".join(_info.get("load_errors", [])))
        st.caption(f"`{_info.get('model_key') or Path(_info['weights']).name}` · {_info.get('architecture') or 'unknown'} · "
                   f"{_info['image_size']} px · sha256 `{_info.get('sha256', '?')}`… · `{_info['device']}`")
    else:
        set_header_status("Model unavailable", "critical")
        st.markdown(":red-badge[No usable model]")
        st.caption(f"Inspection is disabled until a valid model is configured. {_err}")
    st.markdown('<div class="sg-side-label">Notice</div>', unsafe_allow_html=True)
    st.caption("Decision support only. Detections are potential issues for human review, not confirmed violations.")
    st.markdown('<div class="sg-side-foot">Local system · runs on this computer only</div>', unsafe_allow_html=True)

if page != "Live Monitoring":
    close_live_session_if_left()
if page != "Live Monitoring" or _err is not None:  # these runs do not render the video component (start guard)
    mark_live_component_absent(st.session_state)


# ======================================================================== PAGES
SOURCE_LABELS = {"live_camera": "Live camera", "image": "Image", "video": "Video"}
# Review status -> (tone, icon). A stored event stays "potential" unless a reviewer confirmed it.
REVIEW_TONE = {"pending_review": ("warn", "warning"), "confirmed": ("critical", "error"),
               "false_positive": ("muted", "block"), "dismissed": ("muted", "remove_done")}


def _when_short(ts) -> str:
    """Time only for today, day and month this year, full date otherwise."""
    t = pd.to_datetime(ts, errors="coerce")
    if pd.isna(t):
        return "-"
    now = pd.Timestamp.now()
    return t.strftime("%H:%M") if t.date() == now.date() else t.strftime("%d %b %H:%M" if t.year == now.year else "%d %b %Y %H:%M")


def _when(ts) -> str:
    t = pd.to_datetime(ts, errors="coerce")
    return "unknown time" if pd.isna(t) else t.strftime("%d %b %Y %H:%M")


def page_overview() -> None:
    store = get_store()
    events = store.list_events()
    inspections = store.list_inspections()
    pending = int((events["review_status"] == "pending_review").sum()) if not events.empty else 0
    persons = int(inspections["person_detections"].sum()) if not inspections.empty else 0
    frames = int(inspections["frames_processed"].sum()) if not inspections.empty else 0
    live = inspections[inspections["source_type"] == "live_camera"] if not inspections.empty else inspections
    last_live = live.sort_values("timestamp").iloc[-1] if not live.empty else None
    last_any = inspections.sort_values("timestamp").iloc[-1] if not inspections.empty else None
    camera_running = bool(st.session_state.get("live_was_playing", False))  # leaving Live Monitoring closes the session

    # Layout follows the approved reference; every value comes from the stored records or the live model state.
    with st.container(key="sg-ov-hero"):
        page_header("Dashboard", "Site Overview", "Real-time safety monitoring for a safer workplace")
        with st.container(key="sg-kpis"):
            k = st.columns(4)
            with k[0]:
                kpi_card("People Detected", f"{persons:,}", "group", "orange", "Boxes, not unique workers")
            with k[1]:
                kpi_card("Pending Review", f"{pending:,}", "shield", "green", "Awaiting human review")
            with k[2]:
                kpi_card("Potential Alerts", f"{len(events):,}", "warning", "red", "Not confirmed violations")
            with k[3]:
                kpi_card("Camera Status", "Running" if camera_running else "Not running", "videocam", "blue",
                         "Runs on Live Monitoring")

    with st.container(key="sg-ov-lower"):
        feed_col, alert_col, side_col = st.columns([1.45, 1.15, 1.35])
        with feed_col, st.container(key="sg-panel-feed"):
            panel_title("Live Site Feed", badge="LIVE" if camera_running else "OFFLINE", badge_tone="live" if camera_running else "off")
            camera_frame(camera_running)
            st.caption(("Last live session: " + _when_short(last_live["timestamp"]) + f" · {int(last_live['frames_processed']):,} frames"
                        f" · {int(last_live['events_created'])} potential event(s)") if last_live is not None else "No live session recorded yet.")
            with st.container(key="sg-head-feedlink", horizontal=True, horizontal_alignment="right"):
                st.button("Open Live Monitoring →", on_click=go_to, args=("Live Monitoring",), type="tertiary")
        with alert_col, st.container(key="sg-panel-alerts"):
            with st.container(key="sg-head-alerts"):
                h1, h2 = st.columns([1.3, 1], vertical_alignment="center")
                with h1:
                    panel_title("Recent Alerts")
                h2.button("View All →", on_click=go_to, args=("Safety Events",), type="tertiary")
            if events.empty:
                st.info("No safety events recorded yet. Run an image, video or live inspection to generate real events.")
            else:
                rows = []
                for _, e in events.head(3).iterrows():
                    tone, ic = REVIEW_TONE.get(e["review_status"], ("warn", "warning"))
                    rows.append({"icon": ic, "tone": tone, "title": CATEGORY_LABELS.get(e["category"], e["category"]),
                                 "meta": f"{SOURCE_LABELS.get(e['source_type'], e['source_type'])} · {_when_short(e['timestamp'])} · "
                                         f"{review_label(e['review_status'])}"})
                alert_list(rows)
        with side_col:
            with st.container(key="sg-panel-activity"):
                panel_title("Monitoring Activity", "Last 14 days")
                if events.empty:
                    st.caption("No events stored yet.")
                else:
                    end = pd.Timestamp.now().normalize()
                    days = pd.date_range(end - pd.Timedelta(days=13), end, freq="D")
                    counts = pd.to_datetime(events["timestamp"], errors="coerce").dt.normalize().value_counts().reindex(days, fill_value=0)
                    activity_bars([int(c) for c in counts.values], [d.strftime("%d %b") for d in days], "potential event",
                                  "Potential events per day over the last 14 days")
            with st.container(key="sg-panel-system"):
                ready = model_error() is None
                panel_title("System Processing", "Ready" if ready else "Model unavailable")
                lines = []
                if ready:
                    _i = get_detector().info()
                    lines.append(f"{_i.get('model_key') or Path(_i['weights']).name} loaded · {_i['device']} · {_i['image_size']} px")
                else:
                    lines.append("No usable model: inspections are blocked until a model loads.")
                lines.append(("Last analysis: " + SOURCE_LABELS.get(last_any["source_type"], last_any["source_type"]) + " · "
                              + _when_short(last_any["timestamp"]) + f" · {int(last_any['frames_processed']):,} frame(s)")
                             if last_any is not None else "No analysis run yet.")
                lines.append(f"Stored: {len(events):,} events · {len(inspections):,} inspections · {frames:,} frames")
                processing_status(lines, complete=last_any is not None, label="Complete" if last_any is not None else "Idle")
                with st.container(key="sg-head-actions", horizontal=True, horizontal_alignment="distribute", wrap=True):
                    st.button("Inspect an image →", on_click=go_to, args=("Image Inspection",), type="tertiary")
                    st.button("Inspect a video →", on_click=go_to, args=("Video Inspection",), type="tertiary")

    with st.container(key="sg-ov-more"):
        cat_col, model_col = st.columns([1, 1.4])
        with cat_col, st.container(key="sg-panel-categories"):
            panel_title("Events by category", "All stored potential events")
            if events.empty:
                st.caption("No data yet.")
            else:
                vc = events["category"].map(CATEGORY_LABELS).fillna(events["category"]).value_counts().reset_index()
                vc.columns = ["Category", "Events"]
                fig = px.bar(vc, x="Events", y="Category", orientation="h", color_discrete_sequence=[GOLD],
                             title=f"Potential violation events per category<br><sup>{time_range_text(events, events.iloc[0:0])}</sup>")
                st.plotly_chart(style_fig(fig, 280, x_title="Events (count)", y_title=""), width="stretch")
                rs = events["review_status"].map(review_label).value_counts()
                st.caption("Review status: " + " · ".join(f"{k} {v}" for k, v in rs.items()))
        with model_col, st.container(key="sg-panel-model"):
            panel_title("Active model")
            _active_model_panel()
    scope_note(f"Scope: <b>all records stored locally</b> in <code>outputs/siteguard_events.db</code> "
               f"({time_range_text(events, inspections)}). Zero events is not proof that a site is compliant.")


def _active_model_panel() -> None:
    err = model_error()
    if err is not None:
        st.error(f"No usable model is available. {err}")
        return
    info = get_detector().info()
    left, right = st.columns([2, 3])
    with left:
        st.markdown(model_status_line(info))
        kv_table(model_identity_rows(info))
    with right:
        metrics = evaluation_data.active_model_dev_metrics()
        if metrics and info.get("model_key") == "yolo26n_baseline":
            o = metrics["overall"]
            cols = st.columns(4)
            cols[0].metric("mAP50", f"{o['mAP50']:.3f}", border=True)
            cols[1].metric("mAP50-95", f"{o['mAP50-95']:.3f}", border=True)
            cols[2].metric("Precision", f"{o['precision']:.3f}", border=True)
            cols[3].metric("Recall", f"{o['recall']:.3f}", border=True)
            st.caption("YOLO26n on the **development set** (original validation split, 200 images; Ultralytics val). "
                       "Same-dataset images, not real-site footage. Details and limitations: Model Evaluation.")
        else:
            st.caption("No evaluation file for the loaded model. See Model Evaluation.")




def page_live() -> None:
    page_header("Real-time", "Live Monitoring",
                "Browser webcam analysed frame by frame on this computer. The camera starts only when you press START.")
    detector = detector_or_stop()
    try:
        from streamlit_webrtc import WebRtcMode, webrtc_streamer
        import av
    except ImportError as exc:  # pragma: no cover - dependency problem
        st.error(f"streamlit-webrtc is not installed: {exc}")
        return
    from src.detection.camera_processor import LiveFrameProcessor

    # Fix 1 (camera-quality programme): return-video VP8 bitrate 4 Mbit/s instead of aiortc's 0.5 Mbit/s default
    # (benchmark: CAMERA-FIX-REPORT-004). Process-wide and idempotent; applies to streams started after this call.
    configure_return_video_bitrate()
    configure_uplink_hints()  # Fix 2: Chrome sends 1280x720 instead of a bandwidth-limited 640x360

    key = (settings_signature(), detector.model_key)
    if st.session_state.get("live_key") != key or "live_processor" not in st.session_state:
        st.session_state.live_processor = LiveFrameProcessor(
            detector, get_analyzer(), get_store(), process_every_n=cfg["live_every_n"],
            image_size=detector.image_size, confidence=cfg["confidence"], cooldown_seconds=cfg["cooldown_seconds"],
            min_consecutive_hits=int(cfg["min_consecutive_hits"]),
        )
        st.session_state.live_key = key
        st.session_state.live_saved = False
    processor: LiveFrameProcessor = st.session_state.live_processor

    async def queued_frames_callback(frames):
        # R1: latest-frame policy. Only the newest queued frame is analysed; older ones are counted as dropped.
        # The returned frame carries only the boxes computed on that same frame.
        newest = frames[-1]
        media_t = float(newest.pts * newest.time_base) if newest.pts is not None and newest.time_base else None
        out = processor.process_latest(newest.to_ndarray(format="bgr24"), dropped=len(frames) - 1, media_time_s=media_t)
        return [av.VideoFrame.from_ndarray(out, format="bgr24")]

    # Fix 3: video column wide enough for a 640-px stream at 1440 px; below 1200 px the status panel moves under the
    # video so the video keeps most of the width (rule in src/ui/theme.py).
    left, right = st.container(key="sg-live-layout").columns([2, 1])
    with left:
        try:
            protect_live_stream(st.session_state, "siteguard-live")  # start guard, see src/ui/live_video.py
            ctx = webrtc_streamer(
                key="siteguard-live",
                mode=WebRtcMode.SENDRECV,
                queued_video_frames_callback=queued_frames_callback,
                media_stream_constraints={"video": {"width": {"ideal": 1280}, "height": {"ideal": 720}}, "audio": False},
                rtc_configuration={"iceServers": []},  # local use only: no external STUN/TURN servers contacted
                async_processing=True,
                video_html_attrs=VIDEO_HTML_ATTRS,  # Fix 3: shown at most at its own resolution, aspect kept, never cropped
            )
            clear_live_component_absent(st.session_state)
        except Exception as exc:  # e.g. no Streamlit server runtime, or WebRTC unavailable
            mark_live_component_absent(st.session_state)
            st.error(f"The live camera component could not start ({type(exc).__name__}: {exc}). "
                     "Run the app with `streamlit run app.py` and open it in a browser.")
            st.caption(CAMERA_VALIDATION)
            return
        playing = bool(ctx.state.playing)
        snap0 = processor.snapshot()
        if snap0["error"]:
            st.markdown(":red-badge[Error] Processing error, see the status panel.")
        elif playing:
            st.markdown(":green-badge[Running] Camera running. Press STOP to end the session and release the camera.")
        elif ctx.state.signalling:
            st.markdown(":orange-badge[Connecting] Waiting for the browser camera...")
        else:
            st.markdown(":gray-badge[Stopped] Camera off. Press START to begin.")
            st.caption(
                "If the camera does not start: allow camera access in the browser's address bar, close other apps "
                "using the camera (Zoom, FaceTime), and on macOS allow the browser under System Settings > "
                "Privacy & Security > Camera. Use http://localhost (browsers block cameras on non-secure remote URLs)."
            )
        br = applied_return_video_bitrate() or {}
        st.caption("Frames are processed in memory and are not saved. Only evidence images of recorded events are stored. "
                   "The video is shown at its received resolution (never stretched); returned video is encoded at up to "
                   f"{br.get('max', 0) / 1e6:.1f} Mbit/s. " + CAMERA_VALIDATION)

    # Save a live-session inspection record once the user stops the camera.
    was_playing = st.session_state.get("live_was_playing", False)
    if was_playing and not playing:
        snap = processor.snapshot()
        if snap["frames_analysed"] > 0:
            save_inspection("live_camera", "browser webcam", snap["frames_analysed"], snap["person_detections"],
                            snap["class_counts"], len(processor.events.events_created))
            st.success(f"Live session saved: {snap['frames_analysed']} frames analysed, "
                       f"{len(processor.events.events_created)} event(s).")
        processor.close()  # release frames/results; a restart creates a new session
        st.session_state.pop("live_processor", None)
        st.session_state.live_saved = True
    st.session_state.live_was_playing = playing

    with right:
        @st.fragment(run_every=1.0 if playing else None)
        def live_stats():
            snap = processor.snapshot()
            fmt = lambda v, unit="": "-" if v is None else f"{v:.1f}{unit}"
            inf, r2r = snap["inference_ms"] or {}, snap["receive_to_render_ms"] or {}
            st.markdown("**Live status**")
            kv_table([
                ("Received fps", fmt(snap["received_fps"])),
                ("Analysed fps", fmt(snap["analysed_fps"])),
                ("Rendered fps", fmt(snap["rendered_fps"])),
                ("Dropped frames", str(snap["frames_dropped_queue"])),
                ("Inference p95", fmt(inf.get("p95"), " ms")),
                ("Errors", str(snap["errors"])),
            ])
            st.caption("Measured by `LiveFrameProcessor.snapshot()`, refreshed every second while the camera runs. "
                       "Dropped = frames superseded by a newer frame before analysis; p95 = slow-end inference time.")
            st.caption(
                f"Model `{detector.model_key or Path(detector.weights).name}` at {snap['inference_imgsz']} px · "
                f"session `{snap['session_id']}` · frames analysed {snap['frames_analysed']} · inference median "
                f"{fmt(inf.get('median'), ' ms')} · received-to-rendered p95 {fmt(r2r.get('p95'), ' ms')} · "
                "boxes are drawn only on the frame they were computed on."
            )
            if snap["error"]:
                st.error(f"Processing error: {snap['error']}")
            st.markdown("**Workers in latest analysed frame**")
            if snap["last_worker_rows"]:
                st.dataframe(pd.DataFrame(snap["last_worker_rows"]), hide_index=True, width="stretch")
            else:
                st.caption("No worker detected in the latest frame." if snap["frames_analysed"] else "Waiting for frames.")
            st.markdown("**Current detections**")
            if snap["last_detections"]:
                st.dataframe(pd.DataFrame(snap["last_detections"]).rename(columns={"confidence": "detector confidence"}),
                             hide_index=True, width="stretch", height=180)
            else:
                st.caption("None.")
            st.markdown(f"**New potential events this session** ({len(snap['recent_events'])})")
            if snap["recent_events"]:
                st.dataframe(pd.DataFrame([{"Time": e.timestamp[11:], "Category": CATEGORY_LABELS.get(e.category, e.category),
                                            "Detector confidence": e.confidence, "Worker": e.worker_ref} for e in snap["recent_events"]]),
                             hide_index=True, width="stretch")
            else:
                st.caption(f"None yet. A violation must persist for {processor.events.min_hits} analysed frames; "
                           f"repeats are suppressed for {processor.events.cooldown:.0f} s.")
            advisory("Potential events need human review on the Safety Events page. "
                     "Not seeing an event is not proof of compliance.")
        live_stats()


def page_image() -> None:
    page_header("Inspection", "Image Inspection", "Detect workers, PPE and missing PPE in site photographs.")
    detector = detector_or_stop()
    with st.container(key="sg-panel-image-input"):
        panel_title("Images to inspect")
        files = st.file_uploader("Upload image(s)", type=list(SUPPORTED_IMAGE_TYPES), accept_multiple_files=True)
        st.caption(f"Formats: {', '.join(SUPPORTED_IMAGE_TYPES)} · up to {MAX_IMAGE_BYTES // (1024 * 1024)} MB and "
                   f"{MAX_IMAGE_SIDE} px per side · inference at {detector.image_size} px with model `{detector.model_key}` · "
                   "images are processed on this computer.")
        record = st.toggle("Record potential violations as safety events", value=True,
                           help="On: potential violations are stored in the local events database for review (with an evidence image). "
                                "Off: analyse only, nothing is stored except the inspection record.")
    if not files:
        st.info("Upload one or more JPG/PNG images to begin.")
        return
    analyzer = get_analyzer()
    results_cache = st.session_state.setdefault("image_results", {})
    for idx, f in enumerate(files):
        data = f.getvalue()
        key = hashlib.sha1(data).hexdigest() + settings_signature() + str(record)
        with st.container(key=f"sg-panel-image-{idx}"):
            st.subheader(f.name)
            if key not in results_cache:
                try:
                    img = decode_image_bytes(data, f.name)
                except InvalidImageError as exc:
                    st.error(f"Cannot read {f.name}: {exc}")
                    continue
                with st.spinner("Running detection..."):
                    insp = inspect_image(img, detector, analyzer, confidence=cfg["confidence"], image_size=detector.image_size)
                events = []
                if record:
                    em = EventManager(get_store(), "image", f.name)
                    events = em.process(insp.compliance, now=time.time(), evidence_frame=insp.annotated)
                save_inspection("image", f.name, 1, len(insp.compliance.workers), insp.class_counts(), len(events))
                results_cache[key] = (insp, events)
            insp, events = results_cache[key]
            c1, c2 = st.columns(2)
            c1.image(rgb(insp.image), caption="Original", width="stretch")
            c2.image(rgb(insp.annotated), caption="Detection result (boxes drawn on this image only)", width="stretch")
            st.download_button("Download annotated image", encode_jpeg(insp.annotated), file_name=f"{Path(f.name).stem}_siteguard.jpg",
                               mime="image/jpeg", key=f"dl-{key}")
            if events:
                st.warning(f"{len(events)} potential violation event(s) recorded for review: "
                           + ", ".join(f"{e.worker_ref} {CATEGORY_LABELS[e.category]}" for e in events))
            elif record:
                st.caption("No new potential-violation event was recorded for this image.")
            tab1, tab2 = st.tabs(["Compliance analysis", f"Detections ({len(insp.detections)})"])
            with tab1:
                compliance_panel(insp.compliance)
            with tab2:
                counts = insp.class_counts()
                if counts:
                    st.dataframe(pd.DataFrame(sorted(counts.items()), columns=["Class", "Count"]), hide_index=True)
                    rows = pd.DataFrame(insp.detection_rows())
                    st.dataframe(rows.rename(columns={c: "detector confidence" for c in rows.columns if c == "confidence"}),
                                 hide_index=True, width="stretch")
                    st.caption("Detector confidence is the model's score, not a calibrated probability.")
                else:
                    st.caption("No objects detected above the confidence threshold.")
            advisory()


def page_video() -> None:
    page_header("Inspection", "Video Inspection",
                "Analyse recorded site footage offline. Every frame is analysed unless you choose a sampling interval.")
    detector = detector_or_stop()
    with st.container(key="sg-panel-video-input"):
        panel_title("Video to analyse")
        f = st.file_uploader("Upload a video", type=list(SUPPORTED_VIDEO_TYPES))
        st.caption(f"Formats: {', '.join(SUPPORTED_VIDEO_TYPES)} · upload limit 500 MB (server setting) · inference at "
                   f"{detector.image_size} px with model `{detector.model_key}` · the raw upload is deleted after processing. "
                   "Offline processing time is not a real-time throughput figure.")
        c1, c2, c3 = st.columns(3)
        stride = c1.number_input("Analyse every Nth frame", 1, 30, int(cfg["frame_stride"]),
                                 help="1 = every frame. With N > 1 the frames in between are kept but shown without boxes and "
                                      "tagged 'not analysed' - boxes are only ever drawn on the frame they were computed on.")
        max_frames = c2.number_input("Maximum frames to read", 30, 20000, int(cfg["max_frames"]), step=100)
        record = c3.toggle("Record events", value=True, help="Store potential violations in the local events database for review.")
        if f is None:
            st.info("Upload an MP4/MOV/AVI video to begin.")
        elif st.button("Analyse video", type="primary"):
            upload_dir = OUTPUTS_DIR / "videos" / "_uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=upload_dir, suffix=Path(f.name).suffix, delete=False) as tmp:
                tmp.write(f.getvalue())
                tmp_path = Path(tmp.name)
            out_path = OUTPUTS_DIR / "videos" / f"{Path(f.name).stem}_siteguard_{datetime.now().strftime('%Y%m%d-%H%M%S')}.mp4"
            bar = st.progress(0.0, text="Starting...")
            em = EventManager(get_store(), "video", f.name, cooldown_seconds=cfg["cooldown_seconds"],
                              min_consecutive_hits=cfg["min_consecutive_hits"]) if record else None
            try:
                with st.spinner("Analysing video on this computer..."):
                    summary = process_video(tmp_path, out_path, detector, get_analyzer(), em, frame_stride=int(stride),
                                            max_frames=int(max_frames), confidence=cfg["confidence"], image_size=detector.image_size,
                                            progress=lambda p, t: bar.progress(p, text=t))
            except InvalidVideoError as exc:
                st.error(str(exc))
                return
            finally:
                tmp_path.unlink(missing_ok=True)  # do not keep the raw upload
            save_inspection("video", f.name, summary.frames_processed, summary.person_detections, summary.class_counts, len(summary.events))
            st.session_state.last_video = summary
    summary = st.session_state.get("last_video")
    if summary is None:
        return
    st.subheader("Result")
    c = st.columns(5)
    c[0].metric("Frames read", summary.frames_read, border=True)
    c[1].metric("Frames analysed", summary.frames_processed, border=True,
                help=f"Sampling policy: {getattr(summary, 'sampling_policy', 'every frame analysed')}.")
    c[2].metric("Processing time", f"{summary.seconds_elapsed:.1f} s", border=True)
    c[3].metric("Events recorded", len(summary.events), border=True)
    c[4].metric("Repeats suppressed", summary.suppressed_repeats, border=True, help="Detections of an already-reported issue inside the cooldown window.")
    if summary.stopped_early:
        st.warning("Processing stopped at the frame limit; the output covers only the first part of the video.")
    inf = getattr(summary, "inference_ms", None) or {}
    st.caption(f"Sampling: {getattr(summary, 'sampling_policy', 'every frame analysed')} · frames not analysed: "
               f"{getattr(summary, 'frames_not_analysed', 0)} · inference {detector.image_size} px, "
               f"{inf.get('median', '-')} ms median / {inf.get('p95', '-')} ms p95 per analysed frame.")
    left, right = st.columns([3, 2])
    with left, st.container(key="sg-panel-video-output"):
        panel_title("Annotated video")
        if summary.output_path.exists():
            st.video(str(summary.output_path))
            st.download_button("Download annotated video", summary.output_path.read_bytes(), file_name=summary.output_path.name, mime="video/mp4")
        else:
            st.error("The annotated output video is missing from outputs/videos/.")
    with right, st.container(key="sg-panel-video-tables"):
        st.markdown("**Detections per class (summed over analysed frames)**")
        if summary.class_counts:
            st.dataframe(pd.DataFrame(sorted(summary.class_counts.items(), key=lambda x: -x[1]), columns=["Class", "Detections"]), hide_index=True, width="stretch")
        else:
            st.caption("No detections.")
        st.markdown("**Worker assessments (worker-frames)**")
        st.dataframe(pd.DataFrame([{"Status": STATUS_LABELS[k], "Worker-frames": v} for k, v in summary.worker_status_frames.items()]), hide_index=True, width="stretch")
        if summary.events:
            st.markdown("**Potential violation events**")
            st.dataframe(pd.DataFrame([{"Video time (s)": e.media_time_s, "Category": CATEGORY_LABELS[e.category], "Detector confidence": e.confidence, "Worker": e.worker_ref} for e in summary.events]), hide_index=True, width="stretch")
    advisory()


def page_events() -> None:
    page_header("Review", "Safety Events", "Potential PPE violations recorded from real detections. Review and export them here.")
    store = get_store()
    all_events = store.list_events()
    if all_events.empty:
        empty_state("No events recorded yet.", "Events are created only by the detection pipeline (image, video or live) "
                    "when a potential violation persists; this page never creates or edits events except their review status.")
        return
    with st.expander("What the statuses mean", expanded=False):
        st.markdown(
            "- Every event is a **potential PPE violation** found by the model and kept after the persistence and cooldown rules. "
            "It is not a confirmed violation.\n"
            "- **Review status** is set by a person: " + " · ".join(review_badge_md(s) for s in REVIEW_STATUSES) + ".\n"
            "- Compliant evidence and uncertain assessments are shown during inspection but do not create events."
        )
    rs = all_events["review_status"].value_counts()
    k = st.columns(len(REVIEW_STATUSES) + 1)
    k[0].metric("All events", len(all_events), border=True)
    for i, s in enumerate(REVIEW_STATUSES, start=1):
        k[i].metric(review_label(s), int(rs.get(s, 0)), border=True)
    with st.container(key="sg-panel-event-filters"):
        panel_title("Filters")
        c1, c2, c3, c4 = st.columns(4)
        cats = c1.multiselect("Category", sorted(all_events["category"].unique()), format_func=lambda c: CATEGORY_LABELS.get(c, c))
        srcs = c2.multiselect("Source", sorted(all_events["source_type"].unique()))
        stats = c3.multiselect("Review status", REVIEW_STATUSES, format_func=review_label)
        first = pd.to_datetime(all_events["timestamp"]).min().date()
        dates = c4.date_input("Date range", (first, date.today()))
    start = datetime.combine(dates[0], dtime.min) if isinstance(dates, (tuple, list)) and len(dates) >= 1 else None
    end = datetime.combine(dates[1], dtime.max) if isinstance(dates, (tuple, list)) and len(dates) == 2 else None
    events = store.list_events(categories=cats or None, sources=srcs or None, statuses=stats or None, start=start, end=end)
    with st.container(key="sg-panel-event-table"):
        st.caption(f"{len(events)} of {len(all_events)} events match the filters.")
        if events.empty:
            st.info("No event matches these filters.")
        else:
            st.dataframe(events_display_frame(events), hide_index=True, width="stretch")
        st.download_button("Download CSV report", events_to_csv_bytes(events), file_name=f"siteguard_events_{date.today()}.csv", mime="text/csv", type="primary")
    if events.empty:
        return
    st.subheader("Review an event")
    left, right = st.columns([2, 3])
    with left, st.container(key="sg-panel-event-review"):
        event_id = st.selectbox("Event", events["event_id"].tolist())
        row = events[events["event_id"] == event_id].iloc[0]
        st.markdown(f"**{CATEGORY_LABELS.get(row['category'], row['category'])}** {review_badge_md(row['review_status'])}")
        st.caption(f"{row['timestamp']} · {row['source_type']} `{row['source_name']}` · worker {row['worker_ref']} · "
                   f"detector confidence {row['confidence']:.2f}")
        with st.form("review"):
            status = st.selectbox("Review status", REVIEW_STATUSES, index=REVIEW_STATUSES.index(row["review_status"]),
                                  format_func=review_label)
            notes = st.text_area("Notes", value=row["notes"] or "")
            if st.form_submit_button("Save review"):
                store.update_review_status(event_id, status, notes)
                st.success("Saved.")
                st.rerun()
        st.caption("Only the review status and notes can be changed here. Events are never created, merged or deleted from the dashboard.")
    with right, st.container(key="sg-panel-event-evidence"):
        panel_title("Evidence")
        path = row["evidence_path"]
        if isinstance(path, str) and Path(path).exists():
            st.image(path, caption="Evidence frame (worker box outlined in orange)", width="stretch")
        elif isinstance(path, str) and path:
            st.error(f"The evidence image recorded for this event is missing: `{path}`.")
        else:
            st.caption("No evidence image stored for this event.")


def page_analytics() -> None:
    page_header("Insights", "Analytics", "Statistics computed from stored events and inspection records.")
    store = get_store()
    events, inspections = store.list_events(), store.list_inspections()
    if events.empty and inspections.empty:
        st.info("No data yet. Analytics appear after the first inspection.")
        return
    rng = time_range_text(events, inspections)
    scope_note(f"Scope: <b>all locally stored records</b>, {rng} · {len(events)} events · {len(inspections)} inspections.")
    with st.expander("Metric definitions", expanded=False):
        st.markdown(
            "- **Event**: a potential PPE violation after deduplication (cooldown and persistence rules). One event is not one person.\n"
            "- **Person detections**: Person boxes at or above the worker-confidence threshold, summed over every analysed frame. The same worker in 100 frames counts 100 times; "
            "SiteGuard does not track identities, so this is **not** a count of unique workers.\n"
            "- **PPE detections by class**: number of boxes of each class summed over analysed frames.\n"
            "- No compliance percentage is shown: without identity tracking there is no validated denominator. "
            "Fewer events does not mean a safer site."
        )
    c = st.columns(4)
    c[0].metric("Events", len(events), border=True)
    c[1].metric("Inspections", len(inspections), border=True)
    c[2].metric("Frames analysed", int(inspections["frames_processed"].sum()) if not inspections.empty else 0, border=True)
    c[3].metric("Person detections", int(inspections["person_detections"].sum()) if not inspections.empty else 0, border=True)

    left, right = st.columns(2)
    with left, st.container(key="sg-panel-an-classes"):
        st.subheader("Detections by class")
        if not inspections.empty:
            ins = inspections_report_frame(inspections)
            det_cols = [col for col in ins.columns if col.startswith("detections_")]
            totals = ins[det_cols].sum().rename(lambda s: s.replace("detections_", "")).sort_values(ascending=True).reset_index()
            totals.columns = ["Class", "Detections"]
            totals["Type"] = totals["Class"].apply(lambda s: "Missing PPE" if s.startswith("no_") else ("Person" if s == "Person" else "PPE / other"))
            fig = px.bar(totals, x="Detections", y="Class", color="Type", orientation="h",
                         title=f"Boxes per class, summed over analysed frames<br><sup>{rng}</sup>",
                         color_discrete_map={"Missing PPE": ACCENT, "Person": "#7C8B9C", "PPE / other": "#4F6D8A"})
            st.plotly_chart(style_fig(fig, 400, x_title="Detections (boxes, count)", y_title="Class"), width="stretch")
        else:
            st.caption("No inspections yet.")
    with right, st.container(key="sg-panel-an-categories"):
        st.subheader("Events by category")
        if not events.empty:
            vc = events["category"].map(CATEGORY_LABELS).fillna(events["category"]).value_counts().reset_index()
            vc.columns = ["Category", "Events"]
            fig = px.bar(vc, x="Category", y="Events", color_discrete_sequence=[GOLD],
                         title=f"Potential violation events per category<br><sup>{rng}</sup>")
            st.plotly_chart(style_fig(fig, 400, x_title="Category", y_title="Events (count)"), width="stretch")
        else:
            st.caption("No events yet.")
    if not events.empty:
        left, right = st.columns(2)
        with left, st.container(key="sg-panel-an-time"):
            st.subheader("Events over time")
            ev = events.copy()
            ev["time"] = pd.to_datetime(ev["timestamp"])
            span_hours = (ev["time"].max() - ev["time"].min()).total_seconds() / 3600
            freq, label = ("h", "Hour") if span_hours <= 72 else ("D", "Day")
            series = ev.set_index("time").resample(freq).size().rename("Events").reset_index()
            fig = px.bar(series, x="time", y="Events", color_discrete_sequence=[GOLD],
                         title=f"Events per {label.lower()}<br><sup>{rng}</sup>")
            st.plotly_chart(style_fig(fig, x_title=f"{label} (local time)", y_title="Events (count)"), width="stretch")
        with right, st.container(key="sg-panel-an-review"):
            st.subheader("Review status by source")
            grp = events.assign(Review=events["review_status"].map(review_label)).groupby(["source_type", "Review"]).size().rename("Events").reset_index()
            fig = px.bar(grp, x="source_type", y="Events", color="Review", color_discrete_map=REVIEW_COLORS,
                         title=f"Events per source and review status<br><sup>{rng}</sup>")
            st.plotly_chart(style_fig(fig, x_title="Source", y_title="Events (count)"), width="stretch")
    advisory("Counts describe what the model reported, not the true number of violations on site.")


def page_evaluation() -> None:
    page_header("Model", "Model Evaluation",
                "Measured results only. Every figure names its metric, its dataset split and its size.")
    with st.container(key="sg-panel-eval-active"):
        st.subheader("1. Active model: YOLO26n (development set)")
        metrics = read_json(EXPERIMENTS_DIR / "evaluation" / "trained_best" / "metrics.json")
        if not metrics:
            st.info("No evaluation results yet. Run `python -m src.evaluation.evaluate`.")
        else:
            o = metrics["overall"]
            c = st.columns(4)
            c[0].metric("Precision", f"{o['precision']:.3f}", border=True)
            c[1].metric("Recall", f"{o['recall']:.3f}", border=True)
            c[2].metric("mAP50", f"{o['mAP50']:.3f}", border=True)
            c[3].metric("mAP50-95", f"{o['mAP50-95']:.3f}", border=True)
            st.caption(f"Split: {metrics['split']} = the **development set** · image size {metrics['image_size']} · "
                       "Ultralytics val (conf 0.001, NMS IoU 0.7; precision and recall at the max-F1 confidence). "
                       "These images share the style of the training set, so this measures in-distribution performance, "
                       "not generalisation to other cameras or real sites.")
            pc = pd.DataFrame(metrics["per_class"]).T.reset_index().rename(columns={"index": "Class"})
            left, right = st.columns([3, 2])
            with left:
                fig = px.bar(pc.sort_values("mAP50"), x="mAP50", y="Class", orientation="h", color_discrete_sequence=[GOLD], range_x=[0, 1],
                             title="Per-class mAP50, development set (200 images)")
                st.plotly_chart(style_fig(fig, 400, x_title="mAP50 (0-1)", y_title="Class"), width="stretch")
            with right:
                st.dataframe(pc, hide_index=True, width="stretch", height=400)
            plots = Path(metrics["plots_dir"])
            tabs = st.tabs(["Confusion matrix (normalised)", "Precision-recall curve", "Training curves"])
            with tabs[0]:
                p = plots / "confusion_matrix_normalized.png"
                if p.exists():
                    st.image(str(p), width=760, caption="Ultralytics confusion matrix, development set (200 images), normalised per true class")
                else:
                    st.caption("Not available.")
            with tabs[1]:
                p = plots / "BoxPR_curve.png"
                if p.exists():
                    st.image(str(p), width=760, caption="Precision-recall curve per class, development set (200 images)")
                else:
                    st.caption("Not available.")
            with tabs[2]:
                source = read_json(TRAINED_DIR / "MODEL_SOURCE.json")
                run_dir = Path(source["run_dir"]) if source else None
                if run_dir and (run_dir / "results.csv").exists():
                    res = pd.read_csv(run_dir / "results.csv")
                    res.columns = [col.strip() for col in res.columns]
                    long = res.melt(id_vars="epoch", value_vars=["metrics/mAP50(B)", "metrics/mAP50-95(B)", "metrics/precision(B)", "metrics/recall(B)"],
                                    var_name="Metric", value_name="Value")
                    long["Metric"] = long["Metric"].str.replace("metrics/", "").str.replace("(B)", "")
                    st.plotly_chart(style_fig(px.line(long, x="epoch", y="Value", color="Metric", title="Validation metrics per training epoch"),
                                              x_title="Epoch", y_title="Value (0-1)"), width="stretch")
                    meta = read_json(run_dir / "training_metadata.json")
                    if meta:
                        st.caption(f"{meta['epochs_completed']} epochs in {meta['duration_seconds'] / 60:.1f} min on `{meta['train_params']['device']}`; "
                                   f"Ultralytics {meta['versions']['ultralytics']}, torch {meta['versions']['torch']}.")
                else:
                    st.caption("Training log not found.")

    research_section()

    with st.container(key="sg-panel-eval-viewpoint"):
        st.subheader("5. Viewpoint generalisation experiment")
        st.caption("Separate from the results above. A model trained only on frontal / eye-level images is tested "
                   "on side and overhead images it never saw during training.")
        vp_files = sorted((EXPERIMENTS_DIR / "viewpoint_results").glob("viewpoint_metrics_*.json"))
        if not vp_files:
            st.info("Not run yet. See docs/EVALUATION.md for the procedure.")
            return
        labels = {
            "frontal_val": "Frontal (val)", "side_all": "Side (all, held out)", "overhead_all": "Overhead (all, held out)",
            "low_angle_all": "Low angle (all, held out)", "non_frontal_all": "All non-frontal (held out)",
            "non_frontal_val": "Non-frontal (val)", "frontal_scene_val": "Frontal wide-scene (val)",
            "frontal_closeup_val": "Frontal close-up (val)", "side_closeup_all": "Side close-up (held out)",
            "overhead_scene_all": "Overhead wide-scene (held out)", "side_val": "Side (val)", "overhead_val": "Overhead (val)",
        }
        results = {vf.stem.replace("viewpoint_metrics_", ""): read_json(vf) for vf in vp_files}
        frontal_only = results.get("viewpoint_frontal_only")
        if frontal_only:
            g = frontal_only["groups"]
            st.markdown("**Frontal-only model** - " + frontal_only.get("description", ""))
            main_groups = ["frontal_val", "side_all", "overhead_all", "low_angle_all", "non_frontal_all"]
            c = st.columns(3)
            c[0].metric("Frontal val mAP50-95", f"{g['frontal_val']['mAP50-95']:.3f}", border=True)
            c[1].metric("Side (held out) mAP50-95", f"{g['side_all']['mAP50-95']:.3f}",
                        delta=f"{g['side_all']['mAP50-95'] - g['frontal_val']['mAP50-95']:+.3f} vs frontal", border=True)
            c[2].metric("Overhead (held out) mAP50-95", f"{g['overhead_all']['mAP50-95']:.3f}",
                        delta=f"{g['overhead_all']['mAP50-95'] - g['frontal_val']['mAP50-95']:+.3f} vs frontal", border=True)
            rows = [{"Group": labels.get(k, k), "Images": v["images"], "Boxes": v["instances"], "Precision": round(v["precision"], 3),
                     "Recall": round(v["recall"], 3), "mAP50": round(v["mAP50"], 3), "mAP50-95": round(v["mAP50-95"], 3),
                     "Main comparison": k in main_groups} for k, v in g.items()]
            df = pd.DataFrame(rows)
            fig = px.bar(df[df["Main comparison"]], x="Group", y="mAP50-95", text="Images", color_discrete_sequence=[GOLD], range_y=[0, 1],
                         title="Frontal-only model: mAP50-95 per viewpoint group (n = images)")
            fig.update_traces(texttemplate="n=%{text}", textposition="outside")
            st.plotly_chart(style_fig(fig, x_title="Viewpoint group", y_title="mAP50-95 (0-1)"), width="stretch")
            st.dataframe(df.drop(columns=["Main comparison"]), hide_index=True, width="stretch")
        main = results.get("main_model_all_views")
        if frontal_only and main:
            st.markdown("**Same val-split images, two models** - does training on all viewpoints close the gap?")
            shared = [k for k in main["groups"] if k in frontal_only["groups"]]
            cmp = pd.DataFrame([
                {"Group": labels.get(k, k), "Images": main["groups"][k]["images"],
                 "Frontal-only model": round(frontal_only["groups"][k]["mAP50-95"], 3),
                 "Main model (all views)": round(main["groups"][k]["mAP50-95"], 3)} for k in shared
            ])
            long = cmp.melt(id_vars=["Group", "Images"], var_name="Model", value_name="mAP50-95")
            fig = px.bar(long, x="Group", y="mAP50-95", color="Model", barmode="group", range_y=[0, 1],
                         color_discrete_map={"Frontal-only model": "#7C8B9C", "Main model (all views)": GOLD},
                         title="mAP50-95 per viewpoint group, frontal-only vs main model")
            st.plotly_chart(style_fig(fig, x_title="Viewpoint group", y_title="mAP50-95 (0-1)"), width="stretch")
            st.dataframe(cmp, hide_index=True, width="stretch")
        st.caption("Viewpoint labels were assigned by visual inspection of thumbnails (an AI assistant; human spot-check advised). "
                   "Frontal and side images are mostly close-ups while overhead images are mostly wide scenes, so the overhead drop "
                   "mixes viewpoint with smaller objects and a different image source. Low-angle (13 images) and frontal wide-scene "
                   "(7 images) groups are too small to be reliable. Full discussion: docs/EVALUATION.md.")


def research_section() -> None:
    """Accuracy-programme results (REPORT-022..025). E3 is shown as a research result only: not promoted, not selectable."""
    with st.container(key="sg-panel-eval-compare"):
        st.subheader("2. Same-split comparison on the development set")
        cmp = evaluation_data.dev_comparison()
        if cmp is None:
            st.info("Comparison file not found (experiments/accuracy_improvement/error_analysis/comparison_dev_vs_E1/comparison.csv).")
        else:
            df = pd.DataFrame(cmp["rows"]).set_index("Model").T.reset_index().rename(columns={"index": "Metric (development set)"})
            st.dataframe(df, hide_index=True, width="stretch")
            b = (cmp.get("bootstrap_e3_minus_yolo26n") or {}).get("mAP50_audit")
            st.caption(f"Split: {cmp['split']} · mAP50/mAP50-95 from Ultralytics val; precision and recall at detection confidence 0.25 "
                       "(the application operating point). The development set also selected both models' training checkpoints, "
                       "so these numbers are optimistic."
                       + (f" Paired bootstrap, E3 minus YOLO26n, mAP50 (audit evaluator): {b['mean']:+.3f} "
                          f"(95% interval {b['ci95'][0]:+.3f} to {b['ci95'][1]:+.3f})." if b else "")
                       + f" Source: `{cmp['source']}`.")

    with st.container(key="sg-panel-eval-e3"):
        st.subheader("3. Research candidate E3 (YOLO26m, 896 px)")
        r = evaluation_data.e3_research()
        if r is None:
            st.info("Accuracy-programme results not found (model card or held-back test summary missing).")
            return
        st.markdown(":orange-badge[Not promoted] :gray-badge[Not selectable in this application] :gray-badge[Research result only]")
        st.caption("E3 failed the promotion gates defined before testing. YOLO26n remains the active model. "
                   f"Decision: `{r['sources']['decision']}`.")
        t = r["test"]
        left, right = st.columns([3, 2])
        with left:
            def ci(v):
                return f"{v[0]:.3f} to {v[1]:.3f}" if v else "-"
            rows = [
                {"Metric": "mAP50", "E3 result": fmt_num(t["mAP50"]), "95% interval": "-", "Target": "≥ 0.93", "Met": "No" if (t["mAP50"] or 0) < 0.93 else "Yes"},
                {"Metric": "mAP50-95", "E3 result": fmt_num(t["mAP50-95"]), "95% interval": "-", "Target": "≥ 0.80 (stretch)", "Met": "No" if (t["mAP50-95"] or 0) < 0.80 else "Yes"},
                {"Metric": "Precision at detection confidence 0.25", "E3 result": fmt_num(t["precision_op"]), "95% interval": ci(t["precision_ci"]), "Target": "≥ 0.90", "Met": "No" if (t["precision_op"] or 0) < 0.90 else "Yes"},
                {"Metric": "Recall at detection confidence 0.25", "E3 result": fmt_num(t["recall_op"]), "95% interval": ci(t["recall_ci"]), "Target": "≥ 0.90", "Met": "No" if (t["recall_op"] or 0) < 0.90 else "Yes"},
            ]
            for c_ in evaluation_data.MISSING_PPE:
                v = t["missing_recall"].get(c_)
                rows.append({"Metric": f"{c_} recall at 0.25 (n = {t['missing_instances'].get(c_) or '?'})", "E3 result": fmt_num(v),
                             "95% interval": ci(t["missing_recall_ci"].get(c_)), "Target": "≥ 0.90", "Met": "No" if (v or 0) < 0.90 else "Yes"})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            st.caption(f"Held-back (locked) test: **{t['images']} images, {t['objects']:,} objects, from the same dataset** - not real-site "
                       "footage and not a live-camera result. Evaluated once with a frozen checkpoint. Intervals: image bootstrap, "
                       f"1,000 resamples. Source: `{r['sources']['test']}`.")
        with right:
            fam = r["family"]
            if fam:
                st.markdown("**Real-site photos vs close-ups (same held-back test)**")
                st.dataframe(pd.DataFrame([
                    {"Image type": "Real-site photos in the dataset (source-*)", "Images": fam.get("source", {}).get("images"), "mAP50": fmt_num(fam.get("source", {}).get("mAP50"))},
                    {"Image type": "Generated close-ups in the dataset", "Images": fam.get("ultralytics-ppe", {}).get("images"), "mAP50": fmt_num(fam.get("ultralytics-ppe", {}).get("mAP50"))},
                ]), hide_index=True, width="stretch")
            rp = r["replay"]
            if rp.get("e3") and rp.get("yolo26n"):
                st.markdown("**Recorded webcam replay (149 frames at about 30 fps)**")
                st.dataframe(pd.DataFrame([
                    {"Model": "YOLO26n (active)", "Analysed fps": fmt_num(rp["yolo26n"]["analysed_fps"], 1), "Dropped": rp["yolo26n"]["dropped"],
                     "Inference mean": fmt_num(rp["yolo26n"]["inference_mean_ms"], 1, " ms")},
                    {"Model": "E3 (896 px)", "Analysed fps": fmt_num(rp["e3"]["analysed_fps"], 1), "Dropped": rp["e3"]["dropped"],
                     "Inference mean": fmt_num(rp["e3"]["inference_mean_ms"], 1, " ms")},
                ]), hide_index=True, width="stretch")
                st.caption("Replay of recorded frames on this MacBook Air M5, not a physical-camera test and not a guarantee for other hardware.")
            card = r["card"]
            st.caption(f"Checkpoint `{card['checkpoint']}` · SHA-256 `{card['checkpoint_sha256']}` · {card['architecture']} at "
                       f"{card['image_size']} px · registered in settings: {'yes' if card['registered_in_settings'] else 'no'}.")

    with st.container(key="sg-panel-eval-limits"):
        st.subheader("4. Known limitations")
        dark = r.get("dark") or {}
        st.markdown(
            "- **Missing-PPE recall is far below 0.90** for every class, for both models; tiny objects and boots vs `no_boots` "
            "confusion dominate the misses. Many potential violations will not be detected.\n"
            f"- **Real-site generalisation gap:** on the held-back test, real-site photos reach mAP50 "
            f"{fmt_num(r['family'].get('source', {}).get('mAP50'))} against {fmt_num(r['family'].get('ultralytics-ppe', {}).get('mAP50'))} on close-ups.\n"
            f"- **Dark images:** on artificially darkened development images E3 scores mAP50 {fmt_num(dark.get('e3_candidate'))} "
            f"against {fmt_num(dark.get('yolo26n'))} for YOLO26n.\n"
            "- **Labels:** 178 suspect annotations remain unreviewed; part of the measured error may be label noise.\n"
            "- **Single training seed** per configuration; run-to-run variation is not measured. Longer training, tiling and the "
            "combined configuration were not run.\n"
            "- **Physical-camera validation is pending**; all real-time figures above come from a recorded replay.\n"
            "- These are benchmark results on one public dataset. They do not guarantee performance on a real site."
        )


def page_settings() -> None:
    page_header("Configuration", "Settings / About",
                "Read-only view of the configuration in use. Thresholds and rules are fixed in configs/settings.yaml.")
    s = load_settings()
    st.info("Detection, compliance and event thresholds are **read-only** in the dashboard. Changing them is a "
            "compliance-policy decision that needs approval and re-qualification of the model (ML handoff §3.4).")
    left, right = st.columns(2)
    with left, st.container(key="sg-panel-set-detection"):
        st.subheader("Detection")
        kv_table([
            ("Detection confidence threshold (inference.confidence_threshold)", s["inference"]["confidence_threshold"]),
            ("NMS IoU threshold (inference.iou_threshold)", s["inference"]["iou_threshold"]),
            ("Inference image size (active registry entry)", f"{cfg['image_size']} px"),
            ("Device setting", s["inference"].get("device", "auto")),
        ])
        st.subheader("Events")
        e = s["events"]
        kv_table([
            ("Cooldown between repeats (events.cooldown_seconds)", f"{e['cooldown_seconds']} s"),
            ("Persistence before an event (events.min_consecutive_hits)", f"{e['min_consecutive_hits']} analysed frames"),
            ("Same-worker match IoU (events.match_iou)", e.get("match_iou", "-")),
            ("Candidate timeout (events.candidate_timeout_seconds)", f"{e.get('candidate_timeout_seconds', '-')} s"),
            ("Events database", e["database"]),
            ("Evidence folder", e["evidence_dir"]),
        ])
    with right, st.container(key="sg-panel-set-compliance"):
        st.subheader("Compliance rules")
        cp = s["compliance"]
        kv_table([
            ("Required PPE (compliance.required_ppe)", ", ".join(cp["required_ppe"])),
            ("Person confidence to count as a worker", cp["person_confidence"]),
            ("Missing-PPE confidence for a potential violation (alert threshold)", cp["violation_confidence"]),
            ("PPE confidence for compliant evidence", cp["evidence_confidence"]),
            ("Minimum containment in the person box", cp.get("min_containment", "-")),
            ("Ambiguity margin between workers", cp.get("ambiguity_margin", "-")),
            ("Person box margin", cp.get("person_box_margin", "-")),
            ("Conflicting-evidence IoU", cp.get("conflict_iou", "-")),
        ])
        st.subheader("Video and live processing")
        kv_table([
            ("Video: analyse every Nth frame (default)", s["video"]["frame_stride"]),
            ("Video: maximum frames (default)", s["video"]["max_frames"]),
            ("Live: analyse every Nth frame", s["live"]["process_every_n_frames"]),
        ])
    st.caption("All confidence values are detector confidence scores, not calibrated probabilities.")

    with st.container(key="sg-panel-set-model"):
        st.subheader("Model")
        reg = ModelRegistry.from_settings(s)
        keys = list(reg.entries)
        m1, m2 = st.columns([3, 1])
        choice = m1.selectbox("Active model", keys, index=keys.index(reg.active) if reg.active in keys else 0,
                              format_func=lambda k: f"{k} - {reg.entries[k].description}" if reg.entries[k].description else k,
                              help="Only models registered in configs/settings.yaml are listed. The accuracy-programme candidate E3 "
                                   f"is not registered and cannot be selected. Fallback: {reg.fallback}.")
        if m2.button("Use this model", disabled=choice == reg.active or bool(os.environ.get("SITEGUARD_MODEL"))):
            cfg_yaml = yaml.safe_load(SETTINGS_CONFIG.read_text())
            cfg_yaml["model"]["active"] = choice
            SETTINGS_CONFIG.write_text(yaml.safe_dump(cfg_yaml, sort_keys=False))
            load_settings.cache_clear()
            get_detector.clear()
            st.rerun()
        if os.environ.get("SITEGUARD_MODEL"):
            st.caption(f"The environment variable SITEGUARD_MODEL={os.environ['SITEGUARD_MODEL']} overrides this setting.")
        st.caption(f"Registered models: {len(keys)} ({', '.join(keys)}). A model change applies to new inspections and starts a new live session.")
        err = model_error()
        if err is None:
            info = get_detector().info()
            weights = Path(info["weights"])
            full = checkpoint_sha256(str(weights), weights.stat().st_mtime) if weights.exists() else None
            left, right = st.columns([3, 2])
            with left:
                st.markdown(model_status_line(info))
                kv_table(model_identity_rows(info, full_sha256=full))
                if info.get("load_errors"):
                    st.warning("Load errors: " + "; ".join(info["load_errors"]))
            with right:
                st.markdown("**Classes (fixed order from configs/dataset.yaml)**")
                st.dataframe(pd.DataFrame(list(info["class_names"].items()), columns=["ID", "Class"]), hide_index=True, height=300)
        else:
            st.error(f"No usable model is available. {err}")

    with st.container(key="sg-panel-set-about"):
        st.subheader("About")
        def ver(pkg: str) -> str:
            try:
                return metadata.version(pkg)
            except metadata.PackageNotFoundError:
                return "not installed"
        st.markdown(
            "SiteGuard AI is an academic computer-vision prototype for construction-site PPE monitoring. A YOLO26n detector "
            "fine-tuned on the Ultralytics Construction-PPE dataset (CC BY 4.0) finds workers, PPE and explicit missing-PPE cases. "
            "A rule-based analyzer links items to workers and reports potential violations, compliant evidence or uncertainty. "
            "Everything runs locally; no image, video or camera frame leaves this computer."
        )
        st.caption(f"Software: Python {platform.python_version()} · Streamlit {ver('streamlit')} · Ultralytics {ver('ultralytics')} · "
                   f"torch {ver('torch')} · OpenCV {ver('opencv-python') if ver('opencv-python') != 'not installed' else ver('opencv-python-headless')}.")
        st.markdown(f"**Camera:** {CAMERA_VALIDATION}")
        st.warning(DISCLAIMER + " Not detecting a helmet is not proof that a helmet is missing, and no detected event is not "
                   "proof of compliance. It is not a certified safety system. Model limitations: see Model Evaluation.")


PAGE_FUNCTIONS = {
    "Overview": page_overview, "Live Monitoring": page_live, "Image Inspection": page_image, "Video Inspection": page_video,
    "Safety Events": page_events, "Analytics": page_analytics, "Model Evaluation": page_evaluation, "Settings / About": page_settings,
}
PAGE_FUNCTIONS[page]()
