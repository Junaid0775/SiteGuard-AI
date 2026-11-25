"""Diagnostic launcher: the unchanged webrtc_probe_app.py run through exec() with no other change (control for the launcher itself)."""
from pathlib import Path

_source = Path(__file__).with_name("webrtc_probe_app.py")
exec(compile(_source.read_text(), str(_source), "exec"), globals())
