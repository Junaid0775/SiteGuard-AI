"""Fix 2: uplink resolution hints in the SDP answer. In-process aiortc only; no network, browser or camera."""

import asyncio

import pytest
from aiortc import RTCPeerConnection

from src.ui import live_video


async def answer_sdp() -> str:
    offerer, answerer = RTCPeerConnection(), RTCPeerConnection()
    try:
        offerer.addTransceiver("video", direction="sendrecv")
        await offerer.setLocalDescription(await offerer.createOffer())
        await answerer.setRemoteDescription(offerer.localDescription)
        return (await answerer.createAnswer()).sdp
    finally:
        await offerer.close()
        await answerer.close()


@pytest.fixture(autouse=True)
def restore_codec():
    yield
    live_video.configure_uplink_hints(enabled=False)


def test_hints_reach_the_sdp_answer():
    live_video.configure_uplink_hints()
    sdp = asyncio.run(answer_sdp())
    assert "x-google-start-bitrate=2500" in sdp and "x-google-min-bitrate=1500" in sdp and "x-google-max-bitrate=4000" in sdp


def test_rollback_removes_every_hint():
    live_video.configure_uplink_hints()
    assert live_video.configure_uplink_hints(enabled=False) == {}
    assert "x-google" not in asyncio.run(answer_sdp())


def test_configure_is_idempotent():
    first = live_video.configure_uplink_hints()
    assert live_video.configure_uplink_hints() == first == {
        "x-google-start-bitrate": 2500, "x-google-min-bitrate": 1500, "x-google-max-bitrate": 4000}
