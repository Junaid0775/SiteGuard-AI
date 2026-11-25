"""Build numbered contact sheets of every dataset image for manual viewpoint labelling.

Output: data/viewpoint_sheets/sheet_XX.jpg and data/viewpoint_sheets/index.csv
(index number -> split, filename). Sheets are only a viewing aid; the original
images are read, never modified.
"""
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.utils.paths import DATA_DIR, source_dataset_dir  # noqa: E402

COLS, ROWS, TW, TH = 6, 5, 260, 195
out_dir = DATA_DIR / "viewpoint_sheets"
out_dir.mkdir(parents=True, exist_ok=True)
root = source_dataset_dir()
items = []
for split in ("train", "val"):
    for p in sorted((root / "images" / split).glob("*.jpg")):
        items.append((split, p))

with open(out_dir / "index.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["index", "split", "filename"])
    for i, (split, p) in enumerate(items):
        w.writerow([i, split, p.name])

per = COLS * ROWS
for s in range(0, len(items), per):
    sheet = np.full((ROWS * TH, COLS * TW, 3), 255, np.uint8)
    for k, (split, p) in enumerate(items[s:s + per]):
        img = cv2.imread(str(p))
        h, w = img.shape[:2]
        scale = min(TW / w, TH / h)
        th = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        r, c = divmod(k, COLS)
        y0, x0 = r * TH, c * TW
        sheet[y0:y0 + th.shape[0], x0:x0 + th.shape[1]] = th
        label = str(s + k)
        cv2.rectangle(sheet, (x0, y0), (x0 + 48, y0 + 22), (0, 0, 0), -1)
        cv2.putText(sheet, label, (x0 + 3, y0 + 17), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.imwrite(str(out_dir / f"sheet_{s // per:02d}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
print(len(items), "images,", (len(items) + per - 1) // per, "sheets in", out_dir)
