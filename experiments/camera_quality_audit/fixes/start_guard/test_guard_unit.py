"""Unit tests of the candidate guard against the real streamlit-webrtc context code. No browser, camera or model."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit_webrtc import component

sys.path.insert(0, str(Path(__file__).parent))
import live_start_guard as guard  # noqa: E402

KEY = "siteguard-live"


class FakeWorker:
    backend = "aiortc"

    def __init__(self) -> None:
        self.stops = 0

    def stop(self, timeout: float = 1.0) -> None:
        self.stops += 1


@pytest.fixture
def lib(monkeypatch):
    """The library's own context function, with a controllable Streamlit run count and session state."""
    state: dict = {}
    info = SimpleNamespace(script_run_count=5)
    monkeypatch.setattr(component, "st", SimpleNamespace(session_state=state))
    monkeypatch.setattr(component, "get_this_session_info", lambda: info)
    monkeypatch.setattr(component, "get_script_run_count", lambda i: i.script_run_count)
    context = component._get_or_create_context(KEY)
    worker = FakeWorker()
    context._set_worker(worker)
    context._set_state(component.WebRtcStreamerState(playing=True, signalling=False))
    return SimpleNamespace(state=state, info=info, context=context, worker=worker)


def render(lib) -> None:
    component._get_or_create_context(KEY)


def test_library_stops_worker_on_jump_without_guard(lib):
    lib.info.script_run_count += 2
    render(lib)
    assert lib.worker.stops == 1 and lib.context._get_worker() is None


def test_guard_keeps_worker_on_jump(lib):
    lib.info.script_run_count += 2
    assert guard.protect_live_stream(lib.state, KEY) is True
    render(lib)
    assert lib.worker.stops == 0 and lib.context._get_worker() is lib.worker
    assert lib.context.state.playing is True


def test_library_stores_current_count_after_guard(lib):
    lib.info.script_run_count += 2
    guard.protect_live_stream(lib.state, KEY)
    render(lib)
    assert lib.context._last_rendered_run_count == 7


def test_guard_keeps_worker_across_repeated_jumps(lib):
    for _ in range(5):
        lib.info.script_run_count += 3
        guard.protect_live_stream(lib.state, KEY)
        render(lib)
    assert lib.worker.stops == 0


def test_genuine_absence_still_resets(lib):
    guard.mark_live_component_absent(lib.state)
    lib.info.script_run_count += 2
    assert guard.protect_live_stream(lib.state, KEY) is False
    render(lib)
    assert lib.worker.stops == 1 and lib.context._get_worker() is None
    assert lib.context.state.playing is False


def test_marker_stays_until_a_normal_render_clears_it(lib):
    guard.mark_live_component_absent(lib.state)
    assert guard.protect_live_stream(lib.state, KEY) is False
    assert guard.protect_live_stream(lib.state, KEY) is False  # an interrupted run must not lose the marker
    guard.clear_live_component_absent(lib.state)
    assert guard.protect_live_stream(lib.state, KEY) is True


def test_no_context_is_a_no_op():
    assert guard.protect_live_stream({}, KEY) is False


def test_unsupported_library_version_is_a_no_op(lib, monkeypatch):
    monkeypatch.setattr(guard.metadata, "version", lambda name: "0.80.0")
    lib.info.script_run_count += 2
    assert guard.protect_live_stream(lib.state, KEY) is False
    render(lib)
    assert lib.worker.stops == 1


def test_missing_private_attribute_is_a_no_op():
    state = {KEY: SimpleNamespace()}
    assert guard.protect_live_stream(state, KEY) is False
    assert not hasattr(state[KEY], "_last_rendered_run_count")


def test_installed_library_is_the_supported_version():
    assert guard.guard_supported(), "streamlit-webrtc changed: re-validate the live start guard before using it"
