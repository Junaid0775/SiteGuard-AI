import numpy as np, cv2
from src.compliance.compliance_analyzer import ComplianceAnalyzer, ComplianceRules
from src.detection.annotate import STATUS_COLORS
from src.detection.camera_processor import LiveFrameProcessor
from src.detection.detector import Detection
from src.detection.video_processor import process_video
W, H = 400, 300
BOX = np.array(STATUS_COLORS["uncertain"])
def frame(k):
    img = np.full((H, W, 3), 128, np.uint8); img[:20, :20] = (k * 7) % 251; return img
def box_x(k): return 20 + 10 * (k % 30)
def has_box_at(img, x): return bool(np.abs(img[150, x].astype(int) - BOX).max() <= 2)
class FakeDetector:
    image_size = 640
    def detect(self, img, confidence=None, image_size=None):
        m = int(img[5, 5, 0]); k = next(k for k in range(2000) if (k * 7) % 251 == m); x = box_x(k)
        return [Detection(5, "Person", 0.9, float(x), 60.0, float(x + 63), 260.0)]
AN = lambda: ComplianceAnalyzer(ComplianceRules(required_ppe=("helmet",)))
def test_old_live_every3_shows_old_boxes_on_new_frame():
    p = LiveFrameProcessor(FakeDetector(), AN(), None, process_every_n=3, image_size=640)
    p.process(frame(1)); out2 = p.process(frame(2))
    stale = has_box_at(out2, box_x(1)) and int(out2[5, 5, 0]) == (2 * 7) % 251
    assert not stale, "STALE: frame 1 boxes drawn on frame 2"
def test_old_video_stride5_shows_old_boxes(tmp_path, monkeypatch):
    src = tmp_path / "in.avi"; wr = cv2.VideoWriter(str(src), cv2.VideoWriter_fourcc(*"MJPG"), 10, (W, H))
    [wr.write(frame(k)) for k in range(10)]; wr.release()
    written = []
    class FW:
        def write(self, img): written.append(img.copy())
        def release(self): pass
    monkeypatch.setattr("src.detection.video_processor.open_writer", lambda *a, **k: FW())
    process_video(src, tmp_path / "o.mp4", FakeDetector(), AN(), None, frame_stride=5)
    stale = [k for k, img in enumerate(written) if k % 5 and has_box_at(img, box_x(k - k % 5))]
    assert not stale, f"STALE boxes on frames {stale}"
