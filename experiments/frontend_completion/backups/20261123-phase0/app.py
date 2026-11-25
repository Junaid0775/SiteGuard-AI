"""SiteGuard AI - Streamlit dashboard.

Start with:
    .venv/bin/streamlit run app.py

All numbers on every page come from real model output stored in the local
SQLite database (outputs/siteguard_events.db) or from real evaluation files in
experiments/. Nothing is invented: when there is no data, the page says so.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
import uuid
from datetime import date, datetime, time as dtime
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
    SUPPORTED_ITEMS,
    UNCERTAIN,
    ComplianceAnalyzer,
    ComplianceRules,
)
from src.detection.detector import IncompatibleModelError, ModelNotFoundError, PPEDetector
from src.detection.model_registry import ModelRegistry
from src.utils.logging_config import setup_logging
from src.detection.image_processor import SUPPORTED_IMAGE_TYPES, InvalidImageError, decode_image_bytes, encode_jpeg, inspect_image
from src.detection.video_processor import SUPPORTED_VIDEO_TYPES, InvalidVideoError, process_video
from src.events.event_manager import EventManager
from src.events.event_store import REVIEW_STATUSES, EventStore, InspectionRecord
from src.reporting.report_generator import CATEGORY_LABELS, DISCLAIMER, events_report_frame, events_to_csv_bytes, inspections_report_frame

st.set_page_config(page_title="SiteGuard AI", page_icon=":material/health_and_safety:", layout="wide")
ensure_output_dirs()

ACCENT = "#D9622B"
NEUTRALS = ["#D9622B", "#5B6573", "#9AA3AE", "#2F6F8F", "#B08D57", "#7A5C99"]
STATUS_COLOR = {POTENTIAL_VIOLATION: "red", COMPLIANT_EVIDENCE: "green", UNCERTAIN: "orange"}
PAGES = [
    "Overview", "Live Monitoring", "Image Inspection", "Video Inspection",
    "Safety Events", "Analytics", "Model Evaluation", "Settings / About",
]

st.markdown(
    """
    <style>
      .block-container {padding-top: 2.2rem; padding-bottom: 2rem; max-width: 1400px;}
      h1, h2, h3 {letter-spacing: -0.01em;}
      .sg-kicker {font-size: .78rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #D9622B; margin-bottom: -.4rem;}
      .sg-note {font-size: .85rem; opacity: .75;}
      div[data-testid="stMetricValue"] {font-variant-numeric: tabular-nums;}
    </style>
    """,
    unsafe_allow_html=True,
)


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


if "cfg" not in st.session_state:
    st.session_state.cfg = default_cfg()
cfg: dict = st.session_state.cfg


@st.cache_resource(show_spinner="Loading SiteGuard model...")
def get_detector() -> PPEDetector:
    return PPEDetector().load()


@st.cache_resource
def get_store() -> EventStore:
    return EventStore()


def get_analyzer() -> ComplianceAnalyzer:
    rules = ComplianceRules.from_settings({
        "required_ppe": cfg["required_ppe"],
        "person_confidence": cfg["person_confidence"],
        "violation_confidence": cfg["violation_confidence"],
        "evidence_confidence": cfg["evidence_confidence"],
    })
    return ComplianceAnalyzer(rules)


def detector_or_stop() -> PPEDetector:
    try:
        return get_detector()
    except (ModelNotFoundError, IncompatibleModelError) as exc:
        st.error(f"No usable model is available (active and fallback both failed). {exc}")
        st.stop()


def model_ready() -> bool:
    try:
        get_detector()
        return True
    except (ModelNotFoundError, IncompatibleModelError):
        return False


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except (OSError, json.JSONDecodeError):
        return None


def rgb(img_bgr):
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def status_badge(status: str) -> str:
    return f":{STATUS_COLOR[status]}[**{STATUS_LABELS[status]}**]"


def page_header(kicker: str, title: str, caption: str | None = None) -> None:
    st.markdown(f'<div class="sg-kicker">{kicker}</div>', unsafe_allow_html=True)
    st.title(title)
    if caption:
        st.caption(caption)


def settings_signature() -> str:
    return hashlib.sha1(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:10]


def save_inspection(source_type: str, source_name: str, frames: int, persons: int, class_counts: dict, events: int) -> None:
    get_store().add_inspection(InspectionRecord(
        inspection_id=f"INS-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}",
        timestamp=datetime.now().isoformat(timespec="seconds"),
        source_type=source_type, source_name=source_name, frames_processed=frames,
        person_detections=persons, class_counts=class_counts, events_created=events, settings=dict(cfg),
    ))


def plotly_style(fig, height: int = 320):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30, b=10), legend_title_text="", colorway=NEUTRALS)
    return fig


def compliance_panel(result) -> None:
    counts = result.counts
    c1, c2, c3 = st.columns(3)
    c1.metric("Potential violation", counts[POTENTIAL_VIOLATION], border=True)
    c2.metric("Compliant evidence", counts[COMPLIANT_EVIDENCE], border=True)
    c3.metric("Uncertain", counts[UNCERTAIN], border=True)
    if not result.workers:
        st.info("No worker (Person) detected above the person-confidence threshold, so no compliance assessment was made.")
    for w in result.workers:
        with st.container(border=True):
            st.markdown(f"**{w.worker_ref}** - person confidence {w.person.confidence:.2f} - {status_badge(w.status)}")
            rows = [{"PPE item": a.item, "Status": STATUS_LABELS[a.status],
                     "Confidence": None if a.confidence is None else round(a.confidence, 2), "Reason": a.reason}
                    for a in w.items.values()]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    floating = result.unassigned_negative(cfg["violation_confidence"])
    if floating or result.ambiguous:
        st.caption(
            f"{len(floating)} missing-PPE detection(s) could not be linked to exactly one worker "
            f"({len(result.ambiguous)} ambiguous between overlapping workers). They are shown on the image "
            "but do not create events."
        )


# ------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### SiteGuard AI")
    st.caption("Construction-site PPE compliance monitoring")
    page = st.radio("Navigation", PAGES, label_visibility="collapsed", format_func=lambda p: p)
    st.divider()
    if model_ready():
        info = get_detector().info()
        if info.get("status") == "fallback":
            st.markdown(":orange[**Fallback model in use**]")
            st.caption("The selected model could not be used: " + "; ".join(info.get("load_errors", [])))
        else:
            st.markdown(":green[**Model loaded**]")
        st.caption(f"`{info.get('model_key') or Path(info['weights']).name}` - {info.get('architecture') or '?'} - "
                   f"{info['image_size']} px - sha256 {info.get('sha256', '?')}... - device `{info['device']}`")
    else:
        st.markdown(":orange[**Model not trained yet**]")
        st.caption("Run `python -m src.training.train`")
    st.caption("Decision support only. Detections are potential issues for human review, not confirmed violations.")


# ======================================================================== PAGES
def page_overview() -> None:
    page_header("Dashboard", "Overview", "Live summary of stored inspections and potential safety events.")
    store = get_store()
    events = store.list_events()
    inspections = store.list_inspections()
    pending = int((events["review_status"] == "pending_review").sum()) if not events.empty else 0
    c = st.columns(5)
    c[0].metric("Potential violation events", len(events), border=True)
    c[1].metric("Pending review", pending, border=True)
    c[2].metric("Inspections run", len(inspections), border=True)
    c[3].metric("Frames analysed", int(inspections["frames_processed"].sum()) if not inspections.empty else 0, border=True)
    c[4].metric("Person detections", int(inspections["person_detections"].sum()) if not inspections.empty else 0, border=True,
                help="Person boxes at or above the worker-confidence threshold, summed over all analysed frames. Not a count of unique workers.")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Recent events")
        if events.empty:
            st.info("No safety events recorded yet. Run an image, video or live inspection to generate real events.")
        else:
            st.dataframe(events_report_frame(events.head(8)).drop(columns=["Evidence image", "Reviewer notes"], errors="ignore"),
                         hide_index=True, width="stretch")
    with right:
        st.subheader("Events by category")
        if events.empty:
            st.caption("No data yet.")
        else:
            vc = events["category"].map(CATEGORY_LABELS).fillna(events["category"]).value_counts().reset_index()
            vc.columns = ["Category", "Events"]
            fig = px.bar(vc, x="Events", y="Category", orientation="h", color_discrete_sequence=[ACCENT])
            st.plotly_chart(plotly_style(fig, 280), width="stretch")

    st.subheader("Model status")
    if not model_ready():
        st.warning("No trained checkpoint at models/trained/best.pt yet.")
        return
    info = get_detector().info()
    metrics = read_json(EXPERIMENTS_DIR / "evaluation" / "trained_best" / "metrics.json")
    cols = st.columns(4)
    cols[0].metric("Classes", len(info.get("class_names", {})), border=True)
    if metrics:
        o = metrics["overall"]
        cols[1].metric("Validation mAP50", f"{o['mAP50']:.3f}", border=True)
        cols[2].metric("Validation mAP50-95", f"{o['mAP50-95']:.3f}", border=True)
        cols[3].metric("Validation recall", f"{o['recall']:.3f}", border=True)
        st.caption(f"Metrics from {metrics['split']}, evaluated {metrics['created']}.")
    else:
        cols[1].caption("Run `python -m src.evaluation.evaluate` to compute validation metrics.")
    st.caption(f"Checkpoint `{info['weights']}` (sha256 {info.get('sha256', '?')}...)")


def page_live() -> None:
    page_header("Real-time", "Live Monitoring", "Browser webcam analysed frame by frame. Press START to begin and STOP to end.")
    detector = detector_or_stop()
    try:
        from streamlit_webrtc import WebRtcMode, webrtc_streamer
        import av
    except ImportError as exc:  # pragma: no cover - dependency problem
        st.error(f"streamlit-webrtc is not installed: {exc}")
        return
    from src.detection.camera_processor import LiveFrameProcessor

    key = (settings_signature(),)
    if st.session_state.get("live_key") != key or "live_processor" not in st.session_state:
        st.session_state.live_processor = LiveFrameProcessor(
            detector, get_analyzer(), get_store(), process_every_n=cfg["live_every_n"],
            image_size=cfg["image_size"], confidence=cfg["confidence"], cooldown_seconds=cfg["cooldown_seconds"],
            min_consecutive_hits=int(cfg["min_consecutive_hits"]),
        )
        st.session_state.live_key = key
    processor: LiveFrameProcessor = st.session_state.live_processor

    async def queued_frames_callback(frames):
        # R1: latest-frame policy. Only the newest queued frame is analysed; older ones are counted as dropped.
        # The returned frame carries only the boxes computed on that same frame.
        newest = frames[-1]
        media_t = float(newest.pts * newest.time_base) if newest.pts is not None and newest.time_base else None
        out = processor.process_latest(newest.to_ndarray(format="bgr24"), dropped=len(frames) - 1, media_time_s=media_t)
        return [av.VideoFrame.from_ndarray(out, format="bgr24")]

    left, right = st.columns([3, 2])
    with left:
        try:
            ctx = webrtc_streamer(
                key="siteguard-live",
                mode=WebRtcMode.SENDRECV,
                queued_video_frames_callback=queued_frames_callback,
                media_stream_constraints={"video": {"width": {"ideal": 1280}, "height": {"ideal": 720}}, "audio": False},
                rtc_configuration={"iceServers": []},  # local use only: no external STUN/TURN servers contacted
                async_processing=True,
            )
        except Exception as exc:  # e.g. no Streamlit server runtime, or WebRTC unavailable
            st.error(f"The live camera component could not start ({type(exc).__name__}: {exc}). "
                     "Run the app with `streamlit run app.py` and open it in a browser.")
            return
        playing = bool(ctx.state.playing)
        if playing:
            st.markdown(":green[**Camera running**]")
        elif ctx.state.signalling:
            st.markdown(":orange[**Connecting to camera...**]")
        else:
            st.markdown("**Camera stopped.**")
            st.caption(
                "If the camera does not start: allow camera access in the browser's address bar, close other apps "
                "using the camera (Zoom, FaceTime), and on macOS allow the browser under System Settings > "
                "Privacy & Security > Camera. Use http://localhost (browsers block cameras on non-secure remote URLs)."
            )

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
    st.session_state.live_was_playing = playing

    with right:
        @st.fragment(run_every=1.0 if playing else None)
        def live_stats():
            snap = processor.snapshot()
            fmt = lambda v, unit="": "-" if v is None else f"{v:.1f}{unit}"
            c = st.columns(3)
            c[0].metric("Frames analysed", snap["frames_analysed"], border=True)
            c[1].metric("Analysed FPS (measured)", fmt(snap["analysed_fps"]), border=True)
            c[2].metric("Events this session", len(snap["recent_events"]), border=True)
            inf, r2r = snap["inference_ms"] or {}, snap["receive_to_render_ms"] or {}
            st.caption(
                f"Model `{detector.model_key or Path(detector.weights).name}` - inference {snap['inference_imgsz']} px - "
                f"inference {fmt(inf.get('median'), ' ms')} median / {fmt(inf.get('p95'), ' ms')} p95 - "
                f"frame received to rendered {fmt(r2r.get('p95'), ' ms')} p95 - received {fmt(snap['received_fps'])} fps, "
                f"rendered {fmt(snap['rendered_fps'])} fps - dropped (superseded) {snap['frames_dropped_queue']} - "
                f"errors {snap['errors']}. Boxes are drawn only on the frame they were computed on."
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
                st.dataframe(pd.DataFrame(snap["last_detections"]), hide_index=True, width="stretch", height=180)
            st.markdown("**New potential events**")
            if snap["recent_events"]:
                st.dataframe(pd.DataFrame([{"Time": e.timestamp[11:], "Category": CATEGORY_LABELS.get(e.category, e.category),
                                            "Confidence": e.confidence, "Worker": e.worker_ref} for e in snap["recent_events"]]),
                             hide_index=True, width="stretch")
            else:
                st.caption(f"None yet. A violation must persist for {processor.events.min_hits} analysed frames; "
                           f"repeats are suppressed for {processor.events.cooldown:.0f} s.")
        live_stats()


def page_image() -> None:
    page_header("Inspection", "Image Inspection", "Upload site photographs to detect PPE and assess potential violations.")
    detector = detector_or_stop()
    files = st.file_uploader("Upload image(s)", type=list(SUPPORTED_IMAGE_TYPES), accept_multiple_files=True)
    record = st.toggle("Record potential violations as safety events", value=True)
    if not files:
        st.info("Upload one or more JPG/PNG images to begin.")
        return
    analyzer = get_analyzer()
    results_cache = st.session_state.setdefault("image_results", {})
    for f in files:
        data = f.getvalue()
        key = hashlib.sha1(data).hexdigest() + settings_signature() + str(record)
        st.divider()
        st.subheader(f.name)
        if key not in results_cache:
            try:
                img = decode_image_bytes(data, f.name)
            except InvalidImageError as exc:
                st.error(f"Cannot read {f.name}: {exc}")
                continue
            with st.spinner("Running detection..."):
                insp = inspect_image(img, detector, analyzer, confidence=cfg["confidence"], image_size=cfg["image_size"])
            events = []
            if record:
                em = EventManager(get_store(), "image", f.name)
                events = em.process(insp.compliance, now=time.time(), evidence_frame=insp.annotated)
            save_inspection("image", f.name, 1, len(insp.compliance.workers), insp.class_counts(), len(events))
            results_cache[key] = (insp, events)
        insp, events = results_cache[key]
        c1, c2 = st.columns(2)
        c1.image(rgb(insp.image), caption="Original", width="stretch")
        c2.image(rgb(insp.annotated), caption="Annotated", width="stretch")
        st.download_button("Download annotated image", encode_jpeg(insp.annotated), file_name=f"{Path(f.name).stem}_siteguard.jpg",
                           mime="image/jpeg", key=f"dl-{key}")
        if events:
            st.warning(f"{len(events)} potential violation event(s) recorded for review: "
                       + ", ".join(f"{e.worker_ref} {CATEGORY_LABELS[e.category]}" for e in events))
        tab1, tab2 = st.tabs(["Compliance analysis", f"Detections ({len(insp.detections)})"])
        with tab1:
            compliance_panel(insp.compliance)
        with tab2:
            counts = insp.class_counts()
            if counts:
                st.dataframe(pd.DataFrame(sorted(counts.items()), columns=["Class", "Count"]), hide_index=True)
                st.dataframe(pd.DataFrame(insp.detection_rows()), hide_index=True, width="stretch")
            else:
                st.caption("No objects detected above the confidence threshold.")


def page_video() -> None:
    page_header("Inspection", "Video Inspection", "Analyse recorded site footage. Every frame is analysed unless you choose a sampling interval.")
    detector = detector_or_stop()
    f = st.file_uploader("Upload a video", type=list(SUPPORTED_VIDEO_TYPES))
    c1, c2, c3 = st.columns(3)
    stride = c1.number_input("Analyse every Nth frame", 1, 30, int(cfg["frame_stride"]),
                             help="1 = every frame. With N > 1 the frames in between are kept but shown without boxes and "
                                  "tagged 'not analysed' - boxes are only ever drawn on the frame they were computed on.")
    max_frames = c2.number_input("Maximum frames to read", 30, 20000, int(cfg["max_frames"]), step=100)
    record = c3.toggle("Record events", value=True)
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
            summary = process_video(tmp_path, out_path, detector, get_analyzer(), em, frame_stride=int(stride),
                                    max_frames=int(max_frames), confidence=cfg["confidence"], image_size=cfg["image_size"],
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
    st.divider()
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
    st.caption(f"Sampling: {getattr(summary, 'sampling_policy', 'every frame analysed')} - frames not analysed: "
               f"{getattr(summary, 'frames_not_analysed', 0)} - inference {cfg['image_size']} px, "
               f"{inf.get('median', '-')} ms median / {inf.get('p95', '-')} ms p95 per analysed frame.")
    left, right = st.columns([3, 2])
    with left:
        if summary.output_path.exists():
            st.video(str(summary.output_path))
            st.download_button("Download annotated video", summary.output_path.read_bytes(), file_name=summary.output_path.name, mime="video/mp4")
    with right:
        st.markdown("**Detections per class (summed over analysed frames)**")
        if summary.class_counts:
            st.dataframe(pd.DataFrame(sorted(summary.class_counts.items(), key=lambda x: -x[1]), columns=["Class", "Detections"]), hide_index=True, width="stretch")
        st.markdown("**Worker assessments (worker-frames)**")
        st.dataframe(pd.DataFrame([{"Status": STATUS_LABELS[k], "Worker-frames": v} for k, v in summary.worker_status_frames.items()]), hide_index=True, width="stretch")
        if summary.events:
            st.markdown("**Events**")
            st.dataframe(pd.DataFrame([{"Video time (s)": e.media_time_s, "Category": CATEGORY_LABELS[e.category], "Confidence": e.confidence, "Worker": e.worker_ref} for e in summary.events]), hide_index=True, width="stretch")


def page_events() -> None:
    page_header("Review", "Safety Events", "Potential PPE violations recorded from real detections. Review and export them here.")
    store = get_store()
    all_events = store.list_events()
    if all_events.empty:
        st.info("No events recorded yet.")
        return
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        cats = c1.multiselect("Category", sorted(all_events["category"].unique()), format_func=lambda c: CATEGORY_LABELS.get(c, c))
        srcs = c2.multiselect("Source", sorted(all_events["source_type"].unique()))
        stats = c3.multiselect("Review status", REVIEW_STATUSES)
        first = pd.to_datetime(all_events["timestamp"]).min().date()
        dates = c4.date_input("Date range", (first, date.today()))
    start = datetime.combine(dates[0], dtime.min) if isinstance(dates, (tuple, list)) and len(dates) >= 1 else None
    end = datetime.combine(dates[1], dtime.max) if isinstance(dates, (tuple, list)) and len(dates) == 2 else None
    events = store.list_events(categories=cats or None, sources=srcs or None, statuses=stats or None, start=start, end=end)
    st.caption(f"{len(events)} of {len(all_events)} events match the filters.")
    st.dataframe(events_report_frame(events), hide_index=True, width="stretch")
    st.download_button("Download CSV report", events_to_csv_bytes(events), file_name=f"siteguard_events_{date.today()}.csv", mime="text/csv", type="primary")
    if events.empty:
        return
    st.subheader("Review an event")
    left, right = st.columns([2, 3])
    with left:
        event_id = st.selectbox("Event", events["event_id"].tolist())
        row = events[events["event_id"] == event_id].iloc[0]
        st.markdown(f"**{CATEGORY_LABELS.get(row['category'], row['category'])}**")
        st.caption(f"{row['timestamp']} - {row['source_type']} `{row['source_name']}` - worker {row['worker_ref']} - confidence {row['confidence']:.2f}")
        with st.form("review"):
            status = st.selectbox("Review status", REVIEW_STATUSES, index=REVIEW_STATUSES.index(row["review_status"]))
            notes = st.text_area("Notes", value=row["notes"] or "")
            if st.form_submit_button("Save review"):
                store.update_review_status(event_id, status, notes)
                st.success("Saved.")
                st.rerun()
    with right:
        path = row["evidence_path"]
        if isinstance(path, str) and Path(path).exists():
            st.image(path, caption="Evidence frame (worker box outlined in orange)", width="stretch")
        else:
            st.caption("No evidence image stored for this event.")


def page_analytics() -> None:
    page_header("Insights", "Analytics", "Statistics computed from stored events and inspection records.")
    store = get_store()
    events, inspections = store.list_events(), store.list_inspections()
    if events.empty and inspections.empty:
        st.info("No data yet. Analytics appear after the first inspection.")
        return
    with st.expander("Metric definitions", expanded=False):
        st.markdown(
            "- **Event**: a potential PPE violation after deduplication (cooldown and persistence rules). One event is not one person.\n"
            "- **Person detections**: Person boxes at or above the worker-confidence threshold, summed over every analysed frame. The same worker in 100 frames counts 100 times; "
            "SiteGuard does not track identities, so this is **not** a count of unique workers.\n"
            "- **PPE detections by class**: number of boxes of each class summed over analysed frames.\n"
            "- No compliance percentage is shown: without identity tracking there is no validated denominator."
        )
    c = st.columns(4)
    c[0].metric("Events", len(events), border=True)
    c[1].metric("Inspections", len(inspections), border=True)
    c[2].metric("Frames analysed", int(inspections["frames_processed"].sum()) if not inspections.empty else 0, border=True)
    c[3].metric("Person detections", int(inspections["person_detections"].sum()) if not inspections.empty else 0, border=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Detections by class")
        if not inspections.empty:
            ins = inspections_report_frame(inspections)
            det_cols = [col for col in ins.columns if col.startswith("detections_")]
            totals = ins[det_cols].sum().rename(lambda s: s.replace("detections_", "")).sort_values(ascending=True).reset_index()
            totals.columns = ["Class", "Detections"]
            totals["Type"] = totals["Class"].apply(lambda s: "Missing PPE" if s.startswith("no_") else ("Person" if s == "Person" else "PPE / other"))
            fig = px.bar(totals, x="Detections", y="Class", color="Type", orientation="h",
                         color_discrete_map={"Missing PPE": ACCENT, "Person": "#5B6573", "PPE / other": "#9AA3AE"})
            st.plotly_chart(plotly_style(fig, 380), width="stretch")
    with right:
        st.subheader("Events by category")
        if not events.empty:
            vc = events["category"].map(CATEGORY_LABELS).fillna(events["category"]).value_counts().reset_index()
            vc.columns = ["Category", "Events"]
            st.plotly_chart(plotly_style(px.bar(vc, x="Category", y="Events", color_discrete_sequence=[ACCENT]), 380), width="stretch")
        else:
            st.caption("No events yet.")
    if not events.empty:
        left, right = st.columns(2)
        with left:
            st.subheader("Events over time")
            ev = events.copy()
            ev["time"] = pd.to_datetime(ev["timestamp"])
            span_hours = (ev["time"].max() - ev["time"].min()).total_seconds() / 3600
            freq, label = ("h", "Hour") if span_hours <= 72 else ("D", "Day")
            series = ev.set_index("time").resample(freq).size().rename("Events").reset_index()
            fig = px.bar(series, x="time", y="Events", color_discrete_sequence=[ACCENT], labels={"time": label})
            st.plotly_chart(plotly_style(fig), width="stretch")
        with right:
            st.subheader("Events by source and review status")
            grp = events.groupby(["source_type", "review_status"]).size().rename("Events").reset_index()
            fig = px.bar(grp, x="source_type", y="Events", color="review_status", labels={"source_type": "Source", "review_status": "Review"})
            st.plotly_chart(plotly_style(fig), width="stretch")


def page_evaluation() -> None:
    page_header("Model", "Model Evaluation", "Real validation results of the trained checkpoint. Nothing on this page is estimated.")
    metrics = read_json(EXPERIMENTS_DIR / "evaluation" / "trained_best" / "metrics.json")
    st.subheader("1. Standard validation (official val split)")
    if not metrics:
        st.info("No evaluation results yet. Run `python -m src.evaluation.evaluate`.")
    else:
        o = metrics["overall"]
        c = st.columns(4)
        c[0].metric("Precision", f"{o['precision']:.3f}", border=True)
        c[1].metric("Recall", f"{o['recall']:.3f}", border=True)
        c[2].metric("mAP50", f"{o['mAP50']:.3f}", border=True)
        c[3].metric("mAP50-95", f"{o['mAP50-95']:.3f}", border=True)
        st.caption(f"{metrics['split']} - image size {metrics['image_size']} - weights `{metrics['weights']}`. "
                   "This split shares the image style of the training set, so it measures in-distribution accuracy, "
                   "not generalisation to other cameras.")
        pc = pd.DataFrame(metrics["per_class"]).T.reset_index().rename(columns={"index": "Class"})
        left, right = st.columns([3, 2])
        with left:
            fig = px.bar(pc.sort_values("mAP50-95"), x="mAP50-95", y="Class", orientation="h", color_discrete_sequence=[ACCENT], range_x=[0, 1])
            st.plotly_chart(plotly_style(fig, 400), width="stretch")
        with right:
            st.dataframe(pc, hide_index=True, width="stretch", height=400)
        plots = Path(metrics["plots_dir"])
        tabs = st.tabs(["Confusion matrix (normalised)", "Precision-recall curve", "Training curves"])
        with tabs[0]:
            p = plots / "confusion_matrix_normalized.png"
            if p.exists():
                st.image(str(p))
            else:
                st.caption("Not available.")
        with tabs[1]:
            p = plots / "BoxPR_curve.png"
            if p.exists():
                st.image(str(p))
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
                st.plotly_chart(plotly_style(px.line(long, x="epoch", y="Value", color="Metric")), width="stretch")
                meta = read_json(run_dir / "training_metadata.json")
                if meta:
                    st.caption(f"{meta['epochs_completed']} epochs in {meta['duration_seconds'] / 60:.1f} min on `{meta['train_params']['device']}`; "
                               f"Ultralytics {meta['versions']['ultralytics']}, torch {meta['versions']['torch']}.")
            else:
                st.caption("Training log not found.")

    st.subheader("2. Viewpoint generalisation experiment")
    st.caption("Separate from the standard validation above. A model trained only on frontal / eye-level images is tested "
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
        fig = px.bar(df[df["Main comparison"]], x="Group", y="mAP50-95", text="Images", color_discrete_sequence=[ACCENT], range_y=[0, 1])
        fig.update_traces(texttemplate="n=%{text}", textposition="outside")
        st.plotly_chart(plotly_style(fig), width="stretch")
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
                     color_discrete_map={"Frontal-only model": "#9AA3AE", "Main model (all views)": ACCENT})
        st.plotly_chart(plotly_style(fig), width="stretch")
        st.dataframe(cmp, hide_index=True, width="stretch")
    st.caption("Viewpoint labels were assigned by visual inspection of thumbnails (an AI assistant; human spot-check advised). "
               "Frontal and side images are mostly close-ups while overhead images are mostly wide scenes, so the overhead drop "
               "mixes viewpoint with smaller objects and a different image source. Low-angle (13 images) and frontal wide-scene "
               "(7 images) groups are too small to be reliable. Full discussion: docs/EVALUATION.md.")


def page_settings() -> None:
    page_header("Configuration", "Settings / About")
    st.subheader("Detection")
    c1, c2 = st.columns(2)
    cfg["confidence"] = c1.slider("Detection confidence threshold", 0.05, 0.9, float(cfg["confidence"]), 0.05,
                                  help="Boxes below this confidence are discarded before any analysis.")
    cfg["image_size"] = c2.select_slider("Inference resolution (px)", [320, 416, 480, 512, 640, 768, 960, 1280], int(cfg["image_size"]))
    st.subheader("Compliance rules")
    c1, c2, c3 = st.columns(3)
    cfg["violation_confidence"] = c1.slider("Missing-PPE confidence for a potential violation", 0.2, 0.95, float(cfg["violation_confidence"]), 0.05)
    cfg["evidence_confidence"] = c2.slider("PPE confidence for compliant evidence", 0.2, 0.95, float(cfg["evidence_confidence"]), 0.05)
    cfg["person_confidence"] = c3.slider("Person confidence to count as a worker", 0.2, 0.95, float(cfg["person_confidence"]), 0.05)
    cfg["required_ppe"] = st.multiselect("Required PPE on this site", list(SUPPORTED_ITEMS), cfg["required_ppe"])
    st.subheader("Events, video and live camera")
    c1, c2, c3, c4 = st.columns(4)
    cfg["cooldown_seconds"] = c1.number_input("Event cooldown (s)", 0, 3600, int(cfg["cooldown_seconds"]))
    cfg["min_consecutive_hits"] = c2.number_input("Persistence (analysed frames)", 1, 30, int(cfg["min_consecutive_hits"]))
    cfg["live_every_n"] = c3.number_input("Live: analyse every Nth frame", 1, 30, int(cfg["live_every_n"]),
                                          help="1 = every delivered frame. With N > 1 the last correctly annotated frame is "
                                               "shown in between; old boxes are never drawn on a newer frame.")
    c4.markdown(f"**Live inference size**  \n{int(cfg['image_size'])} px (same setting as images and video)")
    c1, c2 = st.columns(2)
    cfg["frame_stride"] = c1.number_input("Video: analyse every Nth frame", 1, 30, int(cfg["frame_stride"]))
    cfg["max_frames"] = c2.number_input("Video: maximum frames", 30, 20000, int(cfg["max_frames"]), step=100)
    b1, b2 = st.columns(2)
    if b1.button("Save as defaults (configs/settings.yaml)"):
        s = yaml.safe_load(SETTINGS_CONFIG.read_text())
        s["inference"].update(confidence_threshold=cfg["confidence"], image_size=cfg["image_size"])
        s["compliance"].update(required_ppe=cfg["required_ppe"], person_confidence=cfg["person_confidence"],
                               violation_confidence=cfg["violation_confidence"], evidence_confidence=cfg["evidence_confidence"])
        s["events"].update(cooldown_seconds=cfg["cooldown_seconds"], min_consecutive_hits=cfg["min_consecutive_hits"])
        s["video"].update(frame_stride=cfg["frame_stride"], max_frames=cfg["max_frames"])
        s["live"].update(process_every_n_frames=cfg["live_every_n"], image_size=None)
        SETTINGS_CONFIG.write_text(yaml.safe_dump(s, sort_keys=False))
        load_settings.cache_clear()
        st.success("Saved.")
    if b2.button("Reset to file defaults"):
        load_settings.cache_clear()
        st.session_state.cfg = default_cfg()
        st.rerun()

    st.subheader("Model information")
    reg = ModelRegistry.from_settings(load_settings())
    keys = list(reg.entries)
    m1, m2 = st.columns([3, 1])
    choice = m1.selectbox("Active model", keys, index=keys.index(reg.active),
                          format_func=lambda k: f"{k} - {reg.entries[k].description}" if reg.entries[k].description else k,
                          help="Checkpoint used for image, video and live inspection. If it is missing or incompatible, "
                               f"the fallback model ({reg.fallback}) is loaded and a warning is shown.")
    if m2.button("Use this model", disabled=choice == reg.active or bool(os.environ.get("SITEGUARD_MODEL"))):
        s = yaml.safe_load(SETTINGS_CONFIG.read_text())
        s["model"]["active"] = choice
        SETTINGS_CONFIG.write_text(yaml.safe_dump(s, sort_keys=False))
        load_settings.cache_clear()
        get_detector.clear()
        st.session_state.cfg = default_cfg()
        st.rerun()
    if os.environ.get("SITEGUARD_MODEL"):
        st.caption(f"The environment variable SITEGUARD_MODEL={os.environ['SITEGUARD_MODEL']} overrides this setting.")
    st.caption("A model change applies to new inspections; restart a running live session (STOP, then START).")
    if model_ready():
        info = get_detector().info()
        st.json({k: v for k, v in info.items() if k != "class_names"}, expanded=False)
        st.dataframe(pd.DataFrame(list(info["class_names"].items()), columns=["ID", "Class"]), hide_index=True)
    else:
        st.caption("No trained model yet.")
    st.subheader("About")
    st.markdown(
        "SiteGuard AI is an academic computer-vision prototype. A YOLO26n detector fine-tuned on the Ultralytics "
        "Construction-PPE dataset (CC BY 4.0) finds workers, PPE and explicit missing-PPE cases. A rule-based analyzer links "
        "items to workers and reports potential violations, compliant evidence or uncertainty."
    )
    st.warning(DISCLAIMER + " Not detecting a helmet is not proof that a helmet is missing. It is not a certified safety system.")


PAGE_FUNCTIONS = {
    "Overview": page_overview, "Live Monitoring": page_live, "Image Inspection": page_image, "Video Inspection": page_video,
    "Safety Events": page_events, "Analytics": page_analytics, "Model Evaluation": page_evaluation, "Settings / About": page_settings,
}
PAGE_FUNCTIONS[page]()
