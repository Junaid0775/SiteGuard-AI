"""Camera quality audit (CAMERA-QUALITY-REPORT-001): diagnostic copy of the dashboard's live WebRTC pipeline.

Run only through run_probe.py. Not part of the application.

* webrtc_streamer is called with exactly the arguments of app.py (page_live): SENDRECV, ideal 1280x720, no audio,
  no ICE servers, async processing, queued_video_frames_callback with the latest-frame policy.
* SG_PROBE_MODE=pipeline: the frame goes through the real LiveFrameProcessor (active YOLO26n via the registry,
  draw_compliance) as in the dashboard. SG_PROBE_MODE=identity: the frame is returned unchanged (transport-only test).
* Logged (JSON lines, SG_PROBE_LOG): per received frame its width/height/pixel format and queue length, per returned
  frame its shape, and per encoded frame the codec, encoded size and the encoder's target bitrate (aiortc encoders
  are wrapped in THIS process only). Pixel data is never written; images are never saved.
* With SG_PROBE_REFERENCE (path of the synthetic source image, identity mode only) the PSNR of each received frame
  against that reference is logged.
* No event database, no evidence: events go to an EventManager with store=None and save_evidence=False.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import streamlit as st  # noqa: E402

from src.utils.paths import load_settings  # noqa: E402,F401  (sets YOLO_CONFIG_DIR before ultralytics)

import av  # noqa: E402
import aiortc.codecs.h264 as h264  # noqa: E402
import aiortc.codecs.vpx as vpx  # noqa: E402
from streamlit_webrtc import WebRtcMode, webrtc_streamer  # noqa: E402

from src.compliance.compliance_analyzer import ComplianceAnalyzer, ComplianceRules  # noqa: E402
from src.detection.camera_processor import LiveFrameProcessor  # noqa: E402
from src.detection.detector import PPEDetector  # noqa: E402
from src.events.event_manager import EventManager  # noqa: E402

LOG = Path(os.environ["SG_PROBE_LOG"])
if not logging.getLogger("aiortc").handlers:  # connection-state log lines go to probe_server.log (no media content)
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    for _n in ("aiortc", "aioice", "streamlit_webrtc"):
        logging.getLogger(_n).addHandler(_h)
        logging.getLogger(_n).setLevel(logging.INFO)
        logging.getLogger(_n).propagate = False
MODE = os.environ.get("SG_PROBE_MODE", "pipeline")
REF_PATH = os.environ.get("SG_PROBE_REFERENCE")
_lock = threading.Lock()


def log(rec: dict) -> None:
    rec["t"] = round(time.time(), 4)
    with _lock, LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = float(np.mean((a.astype(np.float32) - b.astype(np.float32)) ** 2))
    return 99.0 if mse == 0 else round(10 * np.log10(255.0 ** 2 / mse), 2)


@st.cache_resource
def instrument_encoders() -> bool:
    for cls, name in ((vpx.Vp8Encoder, "VP8"), (h264.H264Encoder, "H264")):
        original = cls.encode

        def encode(self, frame, force_keyframe=False, _orig=original, _name=name):
            t0 = time.perf_counter()
            payloads, timestamp = _orig(self, frame, force_keyframe)
            log({"kind": "encode", "codec": _name, "w": frame.width, "h": frame.height, "in_fmt": frame.format.name,
                 "bytes": sum(len(p) for p in payloads), "target_bitrate": getattr(self, "target_bitrate", None),
                 "keyframe": bool(force_keyframe), "enc_ms": round((time.perf_counter() - t0) * 1000, 2)})
            return payloads, timestamp

        cls.encode = encode
    return True


@st.cache_resource
def detector() -> PPEDetector:
    return PPEDetector().load()


@st.cache_resource
def reference() -> np.ndarray | None:
    return cv2.imread(REF_PATH) if REF_PATH and MODE == "identity" else None


class NoEvidenceProcessor(LiveFrameProcessor):
    """The dashboard's LiveFrameProcessor, but events are neither stored nor saved as evidence (audit constraint)."""

    def _start_session(self) -> None:
        super()._start_session()
        self.events = EventManager(None, "live_camera", "camera quality probe", cooldown_seconds=self.cooldown_seconds,
                                   min_consecutive_hits=self.min_consecutive_hits, save_evidence=False)


BITRATE = os.environ.get("SG_PROBE_BITRATE", "library")
if BITRATE != "library":  # same function the dashboard uses (src/ui/live_video.py)
    from src.ui.live_video import configure_return_video_bitrate

    d_, lo_, hi_ = (int(v) for v in BITRATE.split(":"))
    configure_return_video_bitrate(d_, lo_, hi_)
instrument_encoders()
st.title("SiteGuard camera quality probe")
st.caption(f"mode={MODE}; diagnostic only; nothing is saved.")
det = detector()
s = load_settings()
if "probe_processor" not in st.session_state:
    st.session_state.probe_processor = NoEvidenceProcessor(
        det, ComplianceAnalyzer(ComplianceRules.from_settings()), None, process_every_n=s["live"]["process_every_n_frames"],
        image_size=det.image_size, confidence=s["inference"]["confidence_threshold"],
        cooldown_seconds=s["events"]["cooldown_seconds"], min_consecutive_hits=int(s["events"]["min_consecutive_hits"]))
processor: LiveFrameProcessor = st.session_state.probe_processor
ref = reference()


async def queued_frames_callback(frames):
    newest = frames[-1]
    rec = {"kind": "recv", "w": newest.width, "h": newest.height, "fmt": newest.format.name, "queued": len(frames)}
    img = newest.to_ndarray(format="bgr24")
    if MODE == "identity":
        out = img
        if ref is not None:
            r = ref if ref.shape[:2] == img.shape[:2] else cv2.resize(ref, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_AREA)
            rec["psnr_vs_source"] = psnr(img, r)
    else:
        media_t = float(newest.pts * newest.time_base) if newest.pts is not None and newest.time_base else None
        t0 = time.monotonic()
        out = processor.process_latest(img, dropped=len(frames) - 1, media_time_s=media_t)
        rec["process_ms"] = round((time.monotonic() - t0) * 1000, 1)
    rec["out_shape"] = list(out.shape)
    rec["out_is_input_object"] = out is img
    log(rec)
    return [av.VideoFrame.from_ndarray(out, format="bgr24")]


ctx = webrtc_streamer(
    key="siteguard-live",
    mode=WebRtcMode.SENDRECV,
    queued_video_frames_callback=queued_frames_callback,
    media_stream_constraints={"video": {"width": {"ideal": 1280}, "height": {"ideal": 720}}, "audio": False},
    rtc_configuration={"iceServers": []},
    async_processing=True,
    **({"video_html_attrs": __import__("src.ui.live_video", fromlist=["VIDEO_HTML_ATTRS"]).VIDEO_HTML_ATTRS}
       if os.environ.get("SG_PROBE_HTML_ATTRS") == "1" else {}),
)
st.write("playing" if ctx.state.playing else "stopped")
