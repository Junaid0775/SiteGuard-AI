"""Fix 2: PREPARED, NOT MERGED. Nothing in app.py or src/ imports this module.

Problem (CAMERA-QUALITY-REPORT-001): Chrome captures 1280x720 but sends 640x360 or 480x270, because its bandwidth estimate
towards the Python WebRTC peer (aiortc) starts low and rises slowly.

Approach: add Chrome's codec parameters x-google-start-bitrate / min-bitrate / max-bitrate to aiortc's local VP8 codec.
aiortc copies local codec parameters into its SDP answer (rtcpeerconnection.find_common_codecs, sdp.py a=fmtp), and Chrome
applies them to the stream it SENDS. Effects are limited to the browser-to-server direction: aiortc's own encoder ignores
these parameters, and the camera capture request (ideal 1280x720) is unchanged.

These x-google-* parameters are a Chrome-specific, non-standard mechanism. Safari and Firefox ignore them.

Use only in the probe (SG_PROBE_FIX2=start:min:max, kbit/s). disable() removes every hint (rollback check).
"""

from __future__ import annotations

HINT_KEYS = ("x-google-start-bitrate", "x-google-min-bitrate", "x-google-max-bitrate")


def _vp8_codecs() -> list:
    from aiortc.codecs import CODECS

    codecs = [c for c in CODECS["video"] if c.mimeType.lower() == "video/vp8"]
    if not codecs:
        raise RuntimeError("aiortc has no VP8 codec registered")
    return codecs


def enable(start_kbps: int = 2500, min_kbps: int = 1500, max_kbps: int = 4000) -> dict[str, int]:
    """Add the hints to aiortc's VP8 codec for this process. Applies to connections negotiated afterwards."""
    if not 0 < min_kbps <= start_kbps <= max_kbps:
        raise ValueError(f"invalid range: min {min_kbps}, start {start_kbps}, max {max_kbps} kbit/s")
    hints = {"x-google-start-bitrate": int(start_kbps), "x-google-min-bitrate": int(min_kbps),
             "x-google-max-bitrate": int(max_kbps)}
    for codec in _vp8_codecs():
        codec.parameters.update(hints)
    return hints


def disable() -> None:
    """Rollback: remove every hint, restoring aiortc's original VP8 parameters."""
    for codec in _vp8_codecs():
        for key in HINT_KEYS:
            codec.parameters.pop(key, None)


def active() -> dict:
    return {k: v for k, v in _vp8_codecs()[0].parameters.items() if k in HINT_KEYS}
