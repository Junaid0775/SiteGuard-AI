"""Diagnostic launcher: the unchanged webrtc_probe_app.py, except PyAV and aiortc are imported BEFORE OpenCV (import-order test)."""
import aiortc  # noqa: F401
import av  # noqa: F401
from pathlib import Path

_source = Path(__file__).with_name("webrtc_probe_app.py")
exec(compile(_source.read_text(), str(_source), "exec"), globals())
