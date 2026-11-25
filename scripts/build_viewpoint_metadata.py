"""Turn the manual viewpoint codes (data/viewpoint_sheets/codes.txt) into
data/viewpoint_metadata.csv.

The codes were assigned by visually inspecting numbered contact sheets
(see scripts/make_contact_sheets.py). Nothing here infers a viewpoint
automatically; this script only converts the written codes into a table.
"""

import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.utils.paths import DATA_DIR, VIEWPOINT_CSV  # noqa: E402

CODE_NAMES = {"F": "frontal", "S": "side", "O": "overhead", "L": "low_angle", "U": "unclear"}
SHEET_SIZE = 30
DENSE_RANGES = [(270, 799), (859, 999)]  # close-up images; default code F, exceptions listed

sheet_dir = DATA_DIR / "viewpoint_sheets"
index_rows = list(csv.DictReader(open(sheet_dir / "index.csv", encoding="utf-8")))
codes: dict[int, str] = {}

for lo, hi in DENSE_RANGES:
    for i in range(lo, hi + 1):
        codes[i] = "F"

for line in (sheet_dir / "codes.txt").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    key, *rest = line.split()
    if key.startswith("dense_"):
        for item in rest:
            idx, code = item.split(":")
            codes[int(idx)] = code
    elif key.startswith("range"):
        start = int(key[len("range"):])
        for offset, code in enumerate(rest[0]):
            codes[start + offset] = code
    else:  # normal sheet line: "NN <30 codes>"
        start = int(key) * SHEET_SIZE
        for offset, code in enumerate(rest[0]):
            codes[start + offset] = code

missing = [int(r["index"]) for r in index_rows if int(r["index"]) not in codes]
if missing:
    raise SystemExit(f"No viewpoint code for indices: {missing[:20]} ... ({len(missing)} total)")
bad = {c for c in codes.values() if c not in CODE_NAMES}
if bad:
    raise SystemExit(f"Unknown codes: {bad}")

with open(VIEWPOINT_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["filename", "source_split", "viewpoint", "image_group", "labelling_method"])
    for r in index_rows:
        i = int(r["index"])
        group = "close_up" if any(lo <= i <= hi for lo, hi in DENSE_RANGES) else "scene"
        w.writerow([r["filename"], r["split"], CODE_NAMES[codes[i]], group, "manual visual inspection of contact-sheet thumbnails"])

table = Counter((r["split"], CODE_NAMES[codes[int(r["index"])]]) for r in index_rows)
print(f"Wrote {VIEWPOINT_CSV}")
for split in ("train", "val"):
    print(split, {v: table[(split, v)] for v in CODE_NAMES.values()})
