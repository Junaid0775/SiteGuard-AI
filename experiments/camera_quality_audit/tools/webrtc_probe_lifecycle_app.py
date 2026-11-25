"""Diagnostic launcher for the start-failure investigation. Not part of the application.

Runs the unchanged probe (or the real app.py) with three additions, none of which wraps a library call:
* streamlit-webrtc's own DEBUG lifecycle messages are kept, with millisecond timestamps;
* SIGUSR1 dumps all Python thread stacks (code locations only, never frames or pixel data);
* for the probe only, SG_PROBE_VARIANT adds a 150 ms delay plus one Streamlit yield point either before or after the
  webrtc_streamer call, as a controlled test of the suspected cause.
"""
import faulthandler
import json
import logging
import os
import signal
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KEEP = ("not rendered", "Reset the stopped", "Stopping worker", "stopping WebRTC worker", "Create a new worker",
        "Rerun to send the SDP answer")


class LifecycleHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if any(k in message for k in KEEP):
            with open(os.environ["SG_PROBE_LIFECYCLE_LOG"], "a") as f:
                f.write(json.dumps({"t": int(record.created * 1000), "logger": record.name, "message": message}) + "\n")


if not hasattr(sys, "_sg_lifecycle_ready"):
    sys._sg_lifecycle_ready = True
    sys._sg_stack_file = open(os.environ["SG_PROBE_STACK_LOG"], "w")
    faulthandler.register(signal.SIGUSR1, file=sys._sg_stack_file, all_threads=True, chain=False)
    _handler = LifecycleHandler()
    for _name in ("streamlit_webrtc.component", "streamlit_webrtc.webrtc"):
        _logger = logging.getLogger(_name)
        _logger.setLevel(logging.DEBUG)
        _logger.addHandler(_handler)
        _logger.propagate = False

if os.environ.get("SG_PROBE_TARGET") == "dashboard":
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    _target = ROOT / "app.py"
    _source = _target.read_text()
else:
    _target = Path(__file__).with_name("webrtc_probe_app.py")
    _source = _target.read_text()
    _variant = os.environ.get("SG_PROBE_VARIANT", "none")
    _extra = "time.sleep(0.15); st.empty()\n"
    if _variant == "before":
        _marker = "ctx = webrtc_streamer("
    elif _variant == "after":
        _marker = 'st.write("playing" if ctx.state.playing else "stopped")'
    elif _variant == "guard":  # test only: the library's orphan-context reset cannot fire; each would-be reset is logged
        _marker = "ctx = webrtc_streamer("
        _extra = (
            "import json as _json, os as _os, time as _time\n"
            "from streamlit_webrtc import component as _wc\n"
            "_existing = st.session_state.get('siteguard-live')\n"
            "_run = _wc.get_script_run_count(_wc.get_this_session_info())\n"
            "if _existing is not None and _existing._last_rendered_run_count is not None and _run > _existing._last_rendered_run_count + 1:\n"
            "    with open(_os.environ['SG_PROBE_LIFECYCLE_LOG'], 'a') as _f:\n"
            "        _f.write(_json.dumps({'t': int(_time.time() * 1000), 'logger': 'guard', 'message': 'guard suppressed reset',\n"
            "                              'worker_alive': _existing._get_worker() is not None, 'gap': _run - _existing._last_rendered_run_count - 1}) + '\\n')\n"
            "    _existing._last_rendered_run_count = _run - 1\n"
        )
    else:
        _marker = None
    if _marker:
        if _source.count(_marker) != 1:
            raise RuntimeError(f"variant marker not found exactly once: {_marker}")
        _source = _source.replace(_marker, _extra + _marker)

globals()["__file__"] = str(_target)
exec(compile(_source, str(_target), "exec"), globals())
