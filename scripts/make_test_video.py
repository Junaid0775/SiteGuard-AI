"""Create a short test video from dataset VALIDATION images.

No real site video footage is available in this project, so this script builds
a slideshow-style clip: each chosen validation image is shown for a few seconds
with a slow zoom (simulating a moving/zooming camera). It is only used to test
the video pipeline and event deduplication. It is NOT real CCTV footage.

Images come from the Ultralytics Construction-PPE dataset (CC BY 4.0).

    .venv/bin/python scripts/make_test_video.py
"""

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.utils.paths import DATA_DIR, source_dataset_dir  # noqa: E402

FPS, SECONDS_PER_IMAGE, SIZE = 15, 3, (1280, 720)


def frames_for(img: np.ndarray, n: int):
    h, w = img.shape[:2]
    target_ratio = SIZE[0] / SIZE[1]
    for i in range(n):
        zoom = 1.0 + 0.15 * i / max(1, n - 1)  # slow zoom in
        cw = min(w, int(h * target_ratio)) / zoom
        ch = cw / target_ratio
        cx, cy = w / 2, h / 2
        x1, y1 = int(max(0, cx - cw / 2)), int(max(0, cy - ch / 2))
        crop = img[y1:y1 + int(ch), x1:x1 + int(cw)]
        yield cv2.resize(crop, SIZE, interpolation=cv2.INTER_AREA)


def main() -> None:
    val = sorted((source_dataset_dir() / "images" / "val").glob("*.jpg"))
    # A mix of wide scene images ("source-*") and close-ups ("ultralytics-*").
    chosen = [p for p in val if p.name.startswith("ultralytics")][:4] + [p for p in val if p.name.startswith("source")][:2]
    out = DATA_DIR / "test_media" / "test_site_clip.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"avc1"), FPS, SIZE)
    if not writer.isOpened():
        writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), FPS, SIZE)
    for p in chosen:
        for frame in frames_for(cv2.imread(str(p)), FPS * SECONDS_PER_IMAGE):
            writer.write(frame)
    writer.release()
    (out.parent / "SOURCES.txt").write_text(
        "test_site_clip.mp4 is a slideshow built by scripts/make_test_video.py from these\n"
        "Ultralytics Construction-PPE validation images (CC BY 4.0). It is not real video footage.\n"
        + "".join(f"{p.name}\n" for p in chosen),
        encoding="utf-8",
    )
    print(f"Wrote {out} ({len(chosen) * FPS * SECONDS_PER_IMAGE} frames at {FPS} fps)")


if __name__ == "__main__":
    main()
