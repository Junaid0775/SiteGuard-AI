"""Isolated test page for the live-video start guard. Run only through guard_regression.py or run_probe.py.

SG_GUARD_MODE:
  off         the current app.py or probe, exactly as on disk
  candidate   the source is patched in memory to call live_start_guard.py; no file is changed
  production  app.py as on disk, for use after the guard has been integrated
SG_GUARD_TARGET: dashboard (real app.py; the caller sets a temporary database and evidence folder) or probe.

Added for testing only: streamlit-webrtc's own lifecycle messages are logged, every run-count jump is logged, and with
SG_GUARD_CMD set a background thread reports thread and worker counts and can force a run-count jump, a rerun burst or a
dropped connection. No frame or pixel data is logged.
"""
import asyncio
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
for _p in (str(HERE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

MODE = os.environ.get("SG_GUARD_MODE", "off")
TARGET = os.environ.get("SG_GUARD_TARGET", "dashboard")
LOG_PATH = os.environ["SG_GUARD_LOG"]
KEEP = ("not rendered", "Reset the stopped", "Stopping worker", "stopping WebRTC worker", "Create a new worker", "Rerun to send the SDP answer")


def write_log(record: dict) -> None:
    record.setdefault("t", int(time.time() * 1000))
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")


class LifecycleHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if any(k in message for k in KEEP):
            write_log({"t": int(record.created * 1000), "logger": record.name, "message": message})


def active_session():
    from streamlit.runtime.runtime import Runtime

    sessions = Runtime.instance()._session_mgr.list_active_sessions()
    return sessions[0] if sessions else None


def run_command(cmd: dict) -> None:
    from streamlit_webrtc.webrtc import _live_workers

    write_log({"logger": "control", "message": f"command {cmd.get('cmd')}"})
    info = active_session()
    if info is None:
        return
    app = info.session
    loop = app._event_loop
    if cmd["cmd"] == "jump":
        def jump() -> None:
            info.script_run_count += 1
            app.request_rerun(None)
        loop.call_soon_threadsafe(jump)
    elif cmd["cmd"] == "rerun":
        for _ in range(int(cmd.get("n", 1))):
            loop.call_soon_threadsafe(app.request_rerun, None)
            time.sleep(float(cmd.get("interval_ms", 25)) / 1000)
    elif cmd["cmd"] == "drop":
        for worker in list(_live_workers):
            if worker.pc:
                asyncio.run_coroutine_threadsafe(worker.pc.close(), worker._loop)


def control_loop(status_path: Path, cmd_path: Path) -> None:
    import psutil
    from streamlit_webrtc.webrtc import _live_workers

    process, last = psutil.Process(), 0.0
    while True:
        time.sleep(0.02)
        try:
            if time.time() - last >= 0.1:
                last = time.time()
                names = [t.name for t in threading.enumerate()]
                workers = list(_live_workers)
                status = {"t": last, "workers": len(workers), "decoders": sum(n.endswith("-decoder") for n in names),
                          "processors": sum(n.startswith("async_media_processor") for n in names), "threads": len(names),
                          "pc_states": [w.pc.connectionState for w in workers if w.pc], "rss_mb": round(process.memory_info().rss / 1e6, 1)}
                tmp = status_path.with_suffix(".tmp")
                tmp.write_text(json.dumps(status))
                tmp.replace(status_path)
            if cmd_path.exists():
                cmd = json.loads(cmd_path.read_text())
                cmd_path.unlink()
                run_command(cmd)
        except Exception as exc:  # the monitor must never disturb the server under test
            write_log({"logger": "control", "message": f"monitor error {type(exc).__name__}: {exc}"})


if not hasattr(sys, "_sg_guard_ready"):
    sys._sg_guard_ready = True
    if os.environ.get("SG_UPLINK_HINTS"):  # Fix 2 evaluation only: start:min:max kbit/s
        sys.path.insert(0, str(ROOT / "experiments/camera_quality_audit/fixes/fix2_prepared"))
        import uplink_hints

        write_log({"logger": "fix2", "message": f"uplink hints {uplink_hints.enable(*(int(v) for v in os.environ['SG_UPLINK_HINTS'].split(':')))}"})
    _handler = LifecycleHandler()
    for _name in ("streamlit_webrtc.component", "streamlit_webrtc.webrtc"):
        _logger = logging.getLogger(_name)
        _logger.setLevel(logging.DEBUG)
        _logger.addHandler(_handler)
        _logger.propagate = False
    if os.environ.get("SG_GUARD_CMD"):
        import streamlit_webrtc  # noqa: F401  (must first import in the script thread, or its component is not registered)

        threading.Thread(target=control_loop, args=(Path(os.environ["SG_GUARD_STATUS"]), Path(os.environ["SG_GUARD_CMD"])),
                         name="sg-guard-control", daemon=True).start()


def logged_protect(real):
    """Wraps the guard to record each run-count jump it meets. The guard's own decision is unchanged."""
    from streamlit_webrtc import component as wc

    def protect(state, key):
        context = state.get(key)
        previous = getattr(context, "_last_rendered_run_count", None) if context is not None else None
        session = wc.get_this_session_info()
        current = wc.get_script_run_count(session) if session else None
        jumped = previous is not None and current is not None and current > previous + 1
        result = real(state, key)
        if jumped:
            write_log({"logger": "guard", "message": "run-count jump", "protected": result, "gap": current - previous - 1,
                       "worker_alive": context._get_worker() is not None})
        return result
    return protect


def patched(source: str, replacements: list) -> str:
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError(f"patch target not found exactly once: {old[:60]!r}")
        source = source.replace(old, new)
    return source


DASHBOARD_PATCH = [
    ('if page != "Live Monitoring":\n    close_live_session_if_left()\n',
     'if page != "Live Monitoring":\n    close_live_session_if_left()\n'
     'if page != "Live Monitoring" or _err is not None:  # these runs do not render the video component\n'
     '    mark_live_component_absent(st.session_state)\n'),
    ('            ctx = webrtc_streamer(\n                key="siteguard-live",',
     '            protect_live_stream(st.session_state, "siteguard-live")\n            ctx = webrtc_streamer(\n                key="siteguard-live",'),
    ('never cropped\n            )\n        except Exception as exc:  # e.g. no Streamlit server runtime, or WebRTC unavailable\n',
     'never cropped\n            )\n            clear_live_component_absent(st.session_state)\n'
     '        except Exception as exc:  # e.g. no Streamlit server runtime, or WebRTC unavailable\n'
     '            mark_live_component_absent(st.session_state)\n'),
]
PROBE_PATCH = [
    ("ctx = webrtc_streamer(", 'protect_live_stream(st.session_state, "siteguard-live")\nctx = webrtc_streamer('),
    ('st.write("playing" if ctx.state.playing else "stopped")',
     'clear_live_component_absent(st.session_state)\nst.write("playing" if ctx.state.playing else "stopped")'),
]

_target = Path(os.environ.get("SG_GUARD_APP") or ROOT / "app.py") if TARGET == "dashboard" else ROOT / "experiments/camera_quality_audit/tools/webrtc_probe_app.py"
if MODE == "candidate":
    import live_start_guard as _guard

    protect_live_stream = logged_protect(_guard.protect_live_stream)
    mark_live_component_absent = _guard.mark_live_component_absent
    clear_live_component_absent = _guard.clear_live_component_absent
elif MODE == "production":
    import src.ui.live_video as _live_video

    if not hasattr(_live_video, "_sg_real_protect"):
        _live_video._sg_real_protect = _live_video.protect_live_stream
        _live_video.protect_live_stream = logged_protect(_live_video._sg_real_protect)
if not hasattr(sys, "_sg_guard_code"):
    _source = _target.read_text()
    if MODE == "candidate":
        _source = patched(_source, DASHBOARD_PATCH if TARGET == "dashboard" else PROBE_PATCH)
    sys._sg_guard_code = compile(_source, str(_target), "exec", dont_inherit=True)
globals()["__file__"] = str(_target)
exec(sys._sg_guard_code, globals())
