"""R1 frame/result synchronisation tests (spec §4.7, §12.1).

Deterministic frames + a mocked detector: the fake detector returns a Person box whose
x-position encodes the frame it was run on, so a box drawn on the wrong frame is visible
in the pixels. No camera is used here (physical-camera checks are separate).
"""

from __future__ import annotations

import threading
import time

import cv2
import numpy as np
import pytest

from src.compliance.compliance_analyzer import ComplianceAnalyzer, ComplianceRules
from src.detection.annotate import STATUS_COLORS
from src.detection.camera_processor import TIMING_WINDOW, LiveFrameProcessor, OpenCVFrameSource, StaleResultError
from src.detection.detector import Detection
from src.detection.video_processor import process_video

W, H = 400, 300
BOX_COLOR = np.array(STATUS_COLORS["uncertain"])  # a lone Person -> 'uncertain' worker box colour


def frame(k: int) -> np.ndarray:
    """Uniform grey frame whose marker pixel value identifies frame k."""
    img = np.full((H, W, 3), 128, np.uint8)
    img[:20, :20] = (k * 7) % 251
    return img


def box_x(k: int) -> int:
    return 20 + 10 * (k % 30)


class FakeDetector:
    """Box position depends ONLY on the frame content it is given."""

    image_size = 640
    weights = "fake.pt"

    def __init__(self, delay_for: dict[int, float] | None = None, fail_for: set[int] | None = None):
        self.delay_for, self.fail_for = delay_for or {}, fail_for or set()
        self.calls: list[tuple[int, int]] = []  # (frame k, imgsz)

    def detect(self, img, confidence=None, image_size=None):
        marker = int(img[5, 5, 0])
        k = next(k for k in range(0, 2000) if (k * 7) % 251 == marker)
        self.calls.append((k, image_size))
        if k in self.delay_for:
            time.sleep(self.delay_for[k])
        if k in self.fail_for:
            raise RuntimeError(f"inference failed on frame {k}")
        x = box_x(k)
        return [Detection(5, "Person", 0.9, float(x), 60.0, float(x + 63), 260.0)]  # 63 px: right edge never equals another left edge


def has_box_at(img: np.ndarray, x: int) -> bool:
    return bool(np.abs(img[150, x].astype(int) - BOX_COLOR).max() <= 2)


def make_proc(det=None, every_n=1) -> LiveFrameProcessor:
    analyzer = ComplianceAnalyzer(ComplianceRules(required_ppe=("helmet",)))
    return LiveFrameProcessor(det or FakeDetector(), analyzer, None, process_every_n=every_n, image_size=640)


def test_result_rendered_only_on_its_source_frame():
    p = make_proc()
    for k in range(1, 8):
        out = p.process(frame(k))
        assert has_box_at(out, box_x(k)), f"frame {k} missing its own box"
        assert not has_box_at(out, box_x(k - 1)), f"frame {k} shows the box of frame {k - 1}"


def test_render_refuses_a_result_from_another_frame():
    p = make_proc()
    p1, p2 = p.new_packet(frame(1)), p.new_packet(frame(2))
    r1 = p.infer(p1)
    assert r1.source_frame_id == p1.frame_id
    with pytest.raises(StaleResultError):
        p.render(p2, r1)
    assert has_box_at(p.render(p1, r1), box_x(1))


def test_slow_result_for_n_never_lands_on_n_plus_1():
    det = FakeDetector(delay_for={1: 0.3})
    p = make_proc(det)
    outputs = {}
    t = threading.Thread(target=lambda: outputs.__setitem__(1, p.process(frame(1))))
    t.start()
    time.sleep(0.05)               # frame 2 arrives while frame 1 is still being inferred
    outputs[2] = p.process(frame(2))
    t.join()
    assert has_box_at(outputs[2], box_x(2)) and not has_box_at(outputs[2], box_x(1))
    assert has_box_at(outputs[1], box_x(1)) and not has_box_at(outputs[1], box_x(2))


def test_latest_frame_policy_drops_and_counts_superseded_frames():
    p = make_proc()
    out = p.process_queue([frame(k) for k in range(1, 51)])
    s = p.snapshot()
    assert s["frames_received"] == 50 and s["frames_dropped_queue"] == 49 and s["frames_analysed"] == 1
    assert has_box_at(out, box_x(50)) and not has_box_at(out, box_x(49))
    assert [k for k, _ in p.detector.calls] == [50]  # superseded frames were never analysed


def test_frame_ids_unique_increasing_and_unique_across_sessions():
    p = make_proc()
    ids = [p.new_packet(frame(1)).frame_id for _ in range(1000)]
    assert ids == sorted(ids) and len(set(ids)) == 1000
    s1 = p.session_id
    p.reset_session()
    assert p.session_id != s1
    assert {(s1, i) for i in ids}.isdisjoint({(p.session_id, p.new_packet(frame(1)).frame_id) for _ in range(10)})


def test_buffers_stay_bounded():
    p = make_proc()
    for k in range(TIMING_WINDOW + 400):
        p.process(frame(k))
    st = p.stats
    for buf in (st.inference_ms, st.receive_to_render_ms, st.displayed_result_age_ms, st.received_times,
                st.analysed_times, st.rendered_times, st.recent_events):
        assert len(buf) <= TIMING_WINDOW


def test_reduced_analysis_shows_previous_annotated_frame_not_old_boxes_on_new_frame():
    p = make_proc(every_n=3)
    out1 = p.process(frame(1))
    out2, out3 = p.process(frame(2)), p.process(frame(3))
    out4 = p.process(frame(4))
    assert np.array_equal(out2, out1) and np.array_equal(out3, out1)  # frame 1 shown as it was
    assert has_box_at(out4, box_x(4))
    s = p.snapshot()
    assert s["frames_held"] == 2 and s["frames_analysed"] == 2


def test_camera_restart_discards_old_session_results():
    det = FakeDetector(delay_for={1: 0.3})
    p = make_proc(det, every_n=2)
    outputs = {}
    t = threading.Thread(target=lambda: outputs.__setitem__(1, p.process(frame(1))))
    t.start()
    time.sleep(0.05)
    p.reset_session()              # camera restarted while frame 1 (old session) is in flight
    t.join()
    assert np.array_equal(outputs[1], frame(1))                 # old result discarded, no boxes
    assert p.snapshot()["frames_analysed"] == 0                 # nothing leaked into the new session
    out = p.process(frame(5))
    assert has_box_at(out, box_x(5)) and not has_box_at(out, box_x(1))


def test_inference_exception_does_not_block_processing():
    det = FakeDetector(fail_for={2})
    p = make_proc(det)
    p.process(frame(1))
    t0 = time.monotonic()
    out2 = p.process(frame(2))
    out3 = p.process(frame(3))
    assert time.monotonic() - t0 < 1.0
    assert np.array_equal(out2, frame(2))                       # failed frame shown without boxes
    assert has_box_at(out3, box_x(3))
    s = p.snapshot()
    assert s["errors"] == 1 and s["error"] is None              # recovered on the next frame


def test_stop_releases_and_blocks_further_rendering(monkeypatch):
    p = make_proc(every_n=2)
    p.process(frame(1))
    p.close()
    assert np.array_equal(p.process(frame(2)), frame(2)) and p._held is None

    released = []

    class FakeCap:
        def isOpened(self):
            return True

        def read(self):
            return True, frame(1)

        def release(self):
            released.append(True)

    monkeypatch.setattr(cv2, "VideoCapture", lambda *a, **k: FakeCap())
    src = OpenCVFrameSource(0)
    assert src.open() and src.read() is not None
    src.close()
    assert released == [True] and src.cap is None


def test_latency_and_rates_are_measured():
    det = FakeDetector(delay_for={k: 0.005 for k in range(1, 30)})
    p = make_proc(det)
    for k in range(1, 30):
        p.process(frame(k))
    s = p.snapshot()
    assert s["inference_ms"]["mean"] >= 5.0
    assert s["receive_to_render_ms"]["median"] >= s["inference_ms"]["median"]
    assert s["analysed_fps"] and s["rendered_fps"] and s["received_fps"]


@pytest.mark.parametrize("stride", [1, 3])
def test_video_output_frames_only_carry_their_own_boxes(tmp_path, monkeypatch, stride):
    src = tmp_path / "in.avi"
    wr = cv2.VideoWriter(str(src), cv2.VideoWriter_fourcc(*"MJPG"), 10, (W, H))
    for k in range(12):
        wr.write(frame(k))
    wr.release()

    written = []

    class FakeWriter:
        def write(self, img):
            written.append(img.copy())

        def release(self):
            pass

    monkeypatch.setattr("src.detection.video_processor.open_writer", lambda *a, **k: FakeWriter())
    det = FakeDetector()
    analyzer = ComplianceAnalyzer(ComplianceRules(required_ppe=("helmet",)))
    s = process_video(src, tmp_path / "out.mp4", det, analyzer, None, frame_stride=stride, image_size=640)
    assert s.frames_read == 12 and len(written) == 12
    assert s.frames_processed == len(range(0, 12, stride)) and s.frames_not_analysed == 12 - s.frames_processed
    rows = list(__import__("csv").DictReader(open(s.frame_log_path)))
    for k, img in enumerate(written):
        analysed = k % stride == 0
        assert has_box_at(img, box_x(k)) == analysed
        for j in range(12):
            if j != k:
                assert not has_box_at(img, box_x(j)) or box_x(j) == box_x(k)
        assert rows[k]["frame_index"] == str(k)
        assert rows[k]["boxes_from_frame"] == (str(k) if analysed else "")
    assert all(c[1] == 640 for c in det.calls)
