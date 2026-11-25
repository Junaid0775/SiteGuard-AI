"""Candidate start guard for streamlit-webrtc 0.79.1 (isolated copy; nothing in app.py or src/ imports this file).

Problem (CAMERA-START-FAILURE-DIAGNOSTIC-001): on every render the library compares Streamlit's count of finished runs
with the value it stored at the previous render. A difference above one is read as "the component was off screen", and
the library stops the live worker. During the burst of reruns after START, that count can jump by two although the user
never left the page, so a healthy connection is closed.

Guard: while every run since the last render stayed on the page that shows the video component, clear the stored value
just before calling webrtc_streamer. None is the library's own "no previous render" state, so its check is skipped for
that one call and it stores the current count as usual. Any run that does not render the component sets a marker, which
leaves the library's reset fully active for the next render.

The guard does nothing on any other library version, because it relies on one private attribute.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from importlib import metadata
from typing import Any

SUPPORTED_WEBRTC_VERSION = "0.79.1"
COMPONENT_ABSENT_KEY = "live_video_component_absent"


def guard_supported() -> bool:
    try:
        return metadata.version("streamlit-webrtc") == SUPPORTED_WEBRTC_VERSION
    except metadata.PackageNotFoundError:
        return False


def mark_live_component_absent(state: MutableMapping[str, Any]) -> None:
    """Record a run that does not render the video component, so the library's reset stays active."""
    state[COMPONENT_ABSENT_KEY] = True


def clear_live_component_absent(state: MutableMapping[str, Any]) -> None:
    """Call after webrtc_streamer has returned normally."""
    state.pop(COMPONENT_ABSENT_KEY, None)


def protect_live_stream(state: MutableMapping[str, Any], key: str) -> bool:
    """Call immediately before webrtc_streamer. Returns True when the library's run-count check is skipped for this call."""
    if not guard_supported() or state.get(COMPONENT_ABSENT_KEY, False):
        return False
    context = state.get(key)
    if context is None or not hasattr(context, "_last_rendered_run_count"):
        return False
    context._last_rendered_run_count = None
    return True
