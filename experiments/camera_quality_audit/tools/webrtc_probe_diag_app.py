"""Start-failure diagnostics: runs the unchanged webrtc_probe_app.py with server-side stage logging added.

Run only through start_diagnostics.py. Not part of the application; imports nothing into production code.

Logged to SG_PROBE_STAGE_LOG (JSON lines, millisecond wall clock, shared with the browser log because both run on this Mac):
  script_start / script_end / script_interrupted   every Streamlit script run and the WebRTC state it ended with
  srv_pc_created, srv_<method>_call / _ok / _err    aiortc RTCPeerConnection offer/answer/close steps
  srv_connection, srv_ice, srv_gathering, srv_signaling, srv_track   aiortc state changes
No media content is logged. aiortc is wrapped in this process only.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import aiortc

STAGE_LOG = Path(os.environ["SG_PROBE_STAGE_LOG"])


def stage(name: str, **extra) -> None:
    with STAGE_LOG.open("a") as f:
        f.write(json.dumps({"name": name, "where": "server", "t": int(time.time() * 1000), **extra}) + "\n")


def instrument() -> None:
    cls = aiortc.RTCPeerConnection
    if getattr(cls, "_sg_wrapped", False):
        return
    cls._sg_wrapped = True
    original_init = cls.__init__

    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        stage("srv_pc_created")
        self.on("connectionstatechange", lambda: stage("srv_connection", state=self.connectionState))
        self.on("iceconnectionstatechange", lambda: stage("srv_ice", state=self.iceConnectionState))
        self.on("icegatheringstatechange", lambda: stage("srv_gathering", state=self.iceGatheringState))
        self.on("signalingstatechange", lambda: stage("srv_signaling", state=self.signalingState))
        self.on("track", lambda track: stage("srv_track", kind=track.kind))

    cls.__init__ = __init__

    def wrap(method: str):
        original = getattr(cls, method)

        async def wrapped(self, *args, **kwargs):
            description = args[0] if args else None
            extra = {}
            if method == "addIceCandidate":  # kind of candidate only; the IP address is never logged
                extra = {"mdns": str(getattr(description, "ip", "")).endswith(".local"), "protocol": getattr(description, "protocol", None),
                         "end_of_candidates": description is None}
            stage(f"srv_{method}_call", type=getattr(description, "type", None), **extra)
            try:
                result = await original(self, *args, **kwargs)
            except BaseException as exc:
                stage(f"srv_{method}_err", error=f"{type(exc).__name__}: {exc}")
                raise
            stage(f"srv_{method}_ok")
            return result

        setattr(cls, method, wrapped)

    for name in ("setRemoteDescription", "createAnswer", "setLocalDescription", "addIceCandidate", "close"):
        wrap(name)


instrument()
stage("script_start")
try:
    source = Path(__file__).with_name("webrtc_probe_app.py")
    exec(compile(source.read_text(), str(source), "exec"), globals())
    _ctx = globals().get("ctx")
    stage("script_end", playing=bool(_ctx and _ctx.state.playing), signalling=bool(_ctx and _ctx.state.signalling))
except BaseException as exc:  # Streamlit reruns and stops arrive as control-flow exceptions
    stage("script_interrupted", exc=type(exc).__name__)
    raise
