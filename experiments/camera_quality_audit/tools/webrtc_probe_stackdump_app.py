"""Diagnostic launcher: the unchanged webrtc_probe_app.py plus a Python stack dump of all threads on SIGUSR1.

Nothing is wrapped. faulthandler writes from a C signal handler, so it works even if a thread holds the GIL. Only code
locations are written (no frames, no pixel data).
"""
import faulthandler
import os
import signal
import sys
from pathlib import Path

if not hasattr(sys, "_sg_stack_file"):
    sys._sg_stack_file = open(os.environ["SG_PROBE_STACK_LOG"], "w")
    faulthandler.register(signal.SIGUSR1, file=sys._sg_stack_file, all_threads=True, chain=False)

_source = Path(__file__).with_name("webrtc_probe_app.py")
exec(compile(_source.read_text(), str(_source), "exec"), globals())
