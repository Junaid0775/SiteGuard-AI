"""Phase 1 suspect-annotation review manifest, thumbnails and local review page (specification §3.2).

    .venv/bin/python scripts/accuracy/phase1_review_manifest.py

Inputs:
  experiments/accuracy_improvement/data_audit/suspects_rule_based.csv   148 rule-based rows (with annotation IDs)
  experiments/dataset_audit/suspect_annotations.csv                     14 visual-review rows (REPORT-011)
  experiments/accuracy_improvement/data_audit/overlap_pairs.csv         Phase 1 new findings (overlaps)
  experiments/accuracy_improvement/data_audit/unlabelled_person_clusters.csv  Phase 1 new findings (clusters)
  experiments/accuracy_improvement/annotation_review/ai_preassessment.csv     optional, AI-assisted notes

Outputs (experiments/accuracy_improvement/annotation_review/):
  review_manifest.csv     S001-S162 = the 162 earlier suspects (S001-S051 = the 51 high-priority missing-PPE
                          rows), N001-... = new Phase 1 findings. Status 'unreviewed' until a HUMAN reviews.
  thumbs/<id>.jpg         local crops with the suspect box in red, Person boxes in green, other boxes grey
  sheets/<group>_NN.jpg   contact sheets (12 thumbnails each)
  review.html             local review page: choose a status per case and download decisions as CSV
Nothing in the original dataset is modified. Thumbnails stay local (spec §0.1 rule 8).
"""

from __future__ import annotations

import csv
import html
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT.parent / "construction-ppe"
AUDIT = ROOT / "experiments" / "accuracy_improvement" / "data_audit"
OUT = ROOT / "experiments" / "accuracy_improvement" / "annotation_review"
STATUSES = ["unreviewed", "confirmed", "corrected-in-derived-copy", "exclude-with-reason", "uncertain"]
FIELDS = ["review_id", "priority", "source", "issue_type", "reason", "image_path", "label_file", "annotation_id", "row",
          "class_id", "class_name", "xc", "yc", "w", "h", "x1_px", "y1_px", "x2_px", "y2_px", "min_side_640",
          "related_annotation_ids", "thumbnail", "review_status", "reviewer", "review_timestamp",
          "ai_preassessment", "ai_note", "notes"]
REASONS = {
    "missing_ppe_without_person": "missing-PPE box has < 60 % of its area inside any Person box (Person label missing, or association impossible)",
    "ppe_without_person": "PPE box has < 60 % of its area inside any Person box (unworn item or unlabelled person)",
    "extreme_aspect": "width/height ratio > 4 or < 0.2, unusual for this item",
    "item_as_large_as_person": "item box is >= 90 % of the area of every Person box containing it",
}


def load_labels(split: str, stem: str):
    img = cv2.imread(str(DATASET / "images" / split / f"{stem}.jpg"))
    h, w = img.shape[:2]
    rows = []
    lines = [l for l in (DATASET / "labels" / split / f"{stem}.txt").read_text().splitlines() if l.strip()]
    for i, line in enumerate(lines, 1):
        c, xc, yc, bw, bh = line.split()
        xc, yc, bw, bh = map(float, (xc, yc, bw, bh))
        rows.append((i, int(c), (xc - bw / 2) * w, (yc - bh / 2) * h, (xc + bw / 2) * w, (yc + bh / 2) * h))
    return img, rows


def draw_boxes(img, rows, focus_rows: set[int], scale: float = 1.0, offset=(0, 0)):
    for i, c, x1, y1, x2, y2 in rows:
        p1 = (int((x1 - offset[0]) * scale), int((y1 - offset[1]) * scale))
        p2 = (int((x2 - offset[0]) * scale), int((y2 - offset[1]) * scale))
        if i in focus_rows:
            continue
        colour = (60, 200, 60) if c == 5 else (170, 170, 170)
        cv2.rectangle(img, p1, p2, colour, 1)
    for i, c, x1, y1, x2, y2 in rows:
        if i in focus_rows:
            p1 = (int((x1 - offset[0]) * scale), int((y1 - offset[1]) * scale))
            p2 = (int((x2 - offset[0]) * scale), int((y2 - offset[1]) * scale))
            cv2.rectangle(img, (p1[0] - 2, p1[1] - 2), (p2[0] + 2, p2[1] + 2), (0, 0, 255), 2)


def thumbnail(case: dict, path: Path) -> None:
    split, stem = case["image_path"].split("/")[1], Path(case["image_path"]).stem
    img, rows = load_labels(split, stem)
    H, W = img.shape[:2]
    focus = {int(r) for r in str(case.get("focus_rows", "")).split() if r}
    canvas = np.full((340, 520, 3), 255, np.uint8)
    if focus:
        fb = [r for r in rows if r[0] in focus]
        x1, y1 = min(r[2] for r in fb), min(r[3] for r in fb)
        x2, y2 = max(r[4] for r in fb), max(r[5] for r in fb)
        side = max(256.0, 6 * max(x2 - x1, y2 - y1))
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        cx1, cy1 = int(max(0, min(W - side, cx - side / 2))), int(max(0, min(H - side, cy - side / 2)))
        cx2, cy2 = int(min(W, cx1 + side)), int(min(H, cy1 + side))
        crop = img[cy1:cy2, cx1:cx2].copy()
        s = 320 / max(crop.shape[:2])
        crop = cv2.resize(crop, (int(crop.shape[1] * s), int(crop.shape[0] * s)), interpolation=cv2.INTER_CUBIC)
        draw_boxes(crop, rows, focus, scale=s, offset=(cx1, cy1))
        canvas[10:10 + crop.shape[0], 10:10 + crop.shape[1]] = crop
        ov_s = 170 / W
        ov = cv2.resize(img, (170, int(H * ov_s)), interpolation=cv2.INTER_AREA)
        cv2.rectangle(ov, (int(cx1 * ov_s), int(cy1 * ov_s)), (int(cx2 * ov_s), int(cy2 * ov_s)), (0, 0, 255), 1)
        canvas[10:10 + min(ov.shape[0], 320), 340:510] = ov[:320]
    else:
        s = min(500 / W, 320 / H)
        full = cv2.resize(img, (int(W * s), int(H * s)), interpolation=cv2.INTER_AREA)
        draw_boxes(full, rows, set(), scale=s)
        canvas[10:10 + full.shape[0], 10:10 + full.shape[1]] = full
    cv2.putText(canvas, case["review_id"], (345, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(canvas, (case.get("class_name") or "image")[:14], (345, 326), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 200), 1)
    cv2.imwrite(str(path), canvas, [cv2.IMWRITE_JPEG_QUALITY, 88])


def main() -> None:
    (OUT / "thumbs").mkdir(parents=True, exist_ok=True)
    (OUT / "sheets").mkdir(exist_ok=True)
    rule = list(csv.DictReader(open(AUDIT / "suspects_rule_based.csv", encoding="utf-8")))
    visual = [r for r in csv.DictReader(open(ROOT / "experiments/dataset_audit/suspect_annotations.csv", encoding="utf-8"))
              if r["issue_type"].startswith("visual_review")]
    prio_rank = {"high": 0, "medium": 1, "low": 2}

    def rule_case(r):
        return {"priority": r["priority"], "source": "rule-based (REPORT-011, re-derived in Phase 1)", "issue_type": r["issue_type"],
                "reason": REASONS[r["issue_type"]], "image_path": r["image_path"], "label_file": r["label_file"],
                "annotation_id": r["annotation_id"], "row": r["row"], "class_id": r["class_id"], "class_name": r["class_name"],
                **{k: r[k] for k in ("xc", "yc", "w", "h", "x1_px", "y1_px", "x2_px", "y2_px", "min_side_640")},
                "focus_rows": r["row"], "related_annotation_ids": ""}

    def visual_case(r):
        split, fname = r["image_path"].split("/")[1], Path(r["image_path"]).name
        return {"priority": r["review_priority"], "source": "visual review by AI assistant (REPORT-011); image-level",
                "issue_type": r["issue_type"], "reason": r["reason"], "image_path": r["image_path"],
                "label_file": f"labels/{split}/{Path(fname).stem}.txt", "annotation_id": "image-level", "row": "",
                "class_id": "", "class_name": "", "focus_rows": "", "related_annotation_ids": ""}

    cases = sorted((rule_case(r) for r in rule), key=lambda c: (prio_rank[c["priority"]], c["issue_type"] != "missing_ppe_without_person",
                                                               c["image_path"], int(c["row"])))
    high = [c for c in cases if c["priority"] == "high"]
    rest = [c for c in cases if c["priority"] != "high"]
    vis = sorted((visual_case(r) for r in visual), key=lambda c: (prio_rank[c["priority"]], c["image_path"]))
    ordered = high + [c for c in vis if c["priority"] == "high"]
    for p in ("medium", "low"):
        ordered += [c for c in rest if c["priority"] == p] + [c for c in vis if c["priority"] == p]
    for k, c in enumerate(ordered, 1):
        c["review_id"] = f"S{k:03d}"

    # new Phase 1 findings
    new = []
    for r in csv.DictReader(open(AUDIT / "overlap_pairs.csv", encoding="utf-8")):
        if r["kind"] in ("same_class_overlap", "person_person_overlap") or r["kind"].startswith(("cross_class:goggles|no_helmet",
                                                                                                  "cross_class:no_goggle|no_helmet")):
            split, rest_ = r["annotation_a"].split("/", 1)
            stem, ra = rest_.split("#L")
            rb = r["annotation_b"].split("#L")[1]
            new.append({"priority": "medium", "source": "Phase 1 overlap analysis", "issue_type": "overlap:" + r["kind"],
                        "reason": f"{r['class_a']} and {r['class_b']} boxes overlap with IoU {r['iou']}",
                        "image_path": f"images/{split}/{stem}.jpg", "label_file": f"labels/{split}/{stem}.txt",
                        "annotation_id": r["annotation_a"], "row": ra, "class_name": r["class_a"], "class_id": "",
                        "focus_rows": f"{ra} {rb}", "related_annotation_ids": r["annotation_b"]})
    for r in csv.DictReader(open(AUDIT / "unlabelled_person_clusters.csv", encoding="utf-8")):
        ids = r["annotation_ids"].split()
        split, stem = ids[0].split("/")[0], ids[0].split("/")[1].split("#L")[0]
        new.append({"priority": "medium", "source": "Phase 1 orphan-cluster analysis", "issue_type": "likely_unlabelled_person",
                    "reason": f"{r['boxes']} PPE boxes on {r['regions']} with no Person box nearby",
                    "image_path": f"images/{split}/{stem}.jpg", "label_file": f"labels/{split}/{stem}.txt",
                    "annotation_id": ids[0], "row": ids[0].split("#L")[1], "class_name": r["classes"].split()[0], "class_id": "",
                    "focus_rows": " ".join(i.split("#L")[1] for i in ids), "related_annotation_ids": " ".join(ids[1:])})
    for k, c in enumerate(new, 1):
        c["review_id"] = f"N{k:03d}"

    ai = {}
    ai_csv = OUT / "ai_preassessment.csv"
    if ai_csv.exists():
        ai = {r["review_id"]: r for r in csv.DictReader(open(ai_csv, encoding="utf-8"))}

    all_cases = ordered + new
    for c in all_cases:
        c["thumbnail"] = f"thumbs/{c['review_id']}.jpg"
        thumbnail(c, OUT / c["thumbnail"])
        c.update({"review_status": "unreviewed", "reviewer": "", "review_timestamp": "", "notes": "",
                  "ai_preassessment": ai.get(c["review_id"], {}).get("ai_preassessment", ""),
                  "ai_note": ai.get(c["review_id"], {}).get("ai_note", "")})
    with open(OUT / "review_manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_cases)

    groups = defaultdict(list)
    for c in all_cases:
        g = "N_new" if c["review_id"].startswith("N") else ("S_high" if c["priority"] == "high" else f"S_{c['priority']}")
        groups[g].append(c)
    for g, cs in groups.items():
        for s in range(0, len(cs), 12):
            tiles = [cv2.imread(str(OUT / c["thumbnail"])) for c in cs[s:s + 12]]
            while len(tiles) < 12:
                tiles.append(np.full_like(tiles[0], 255))
            sheet = np.vstack([np.hstack(tiles[r * 3:(r + 1) * 3]) for r in range(4)])
            cv2.imwrite(str(OUT / "sheets" / f"{g}_{s // 12 + 1:02d}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])

    rows_html = []
    for c in all_cases:
        opts = "".join(f"<option>{s}</option>" for s in STATUSES)
        rows_html.append(
            f"<tr data-id='{c['review_id']}'><td><img src='{c['thumbnail']}' loading='lazy'></td>"
            f"<td><b>{c['review_id']}</b><br>{html.escape(c['priority'])}<br><small>{html.escape(c['source'])}</small></td>"
            f"<td><b>{html.escape(c.get('class_name') or 'image-level')}</b><br><code>{html.escape(c['annotation_id'])}</code>"
            f"<br><small>{html.escape(c['issue_type'])}</small><br>{html.escape(c['reason'])}"
            + (f"<br><small>related: {html.escape(c['related_annotation_ids'])}</small>" if c["related_annotation_ids"] else "")
            + (f"<br><i>AI pre-assessment (not human review): {html.escape(c['ai_preassessment'])} — {html.escape(c['ai_note'])}</i>"
               if c["ai_preassessment"] else "")
            + f"</td><td><select class='st'>{opts}</select><br><input class='nt' placeholder='reason / correction'></td></tr>")
    page = f"""<!doctype html><html><head><meta charset='utf-8'><title>SiteGuard Label Review</title>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<style>:root{{--bg:#fff;--fg:#1d1d1f;--line:#ddd}}@media (prefers-color-scheme:dark){{:root{{--bg:#1d1d1f;--fg:#f2f2f2;--line:#444}}}}
body{{background:var(--bg);color:var(--fg);font:14px -apple-system,system-ui,sans-serif;margin:16px}}table{{border-collapse:collapse;width:100%}}
td{{border-bottom:1px solid var(--line);padding:6px;vertical-align:top}}img{{width:390px;max-width:60vw}}input{{width:95%}}
.bar{{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line)}}</style></head><body>
<div class='bar'><b>SiteGuard AI — suspect label review</b> ({len(ordered)} earlier suspects S001–S{len(ordered):03d}; {len(new)} new findings N001–N{len(new):03d}).
Reviewer name: <input id='rv' style='width:160px'> <button onclick='dl()'>Download decisions CSV</button>
<br><small>Red = suspect box, green = Person boxes, grey = other labels. Choose a status only for cases you have judged.
Save the CSV as <code>experiments/accuracy_improvement/annotation_review/human_review_decisions.csv</code>.
Nothing here edits the dataset.</small></div>
<table>{''.join(rows_html)}</table>
<script>
const KEY='siteguard_review_v1';
function save(){{const d={{}};document.querySelectorAll('tr[data-id]').forEach(r=>{{d[r.dataset.id]=[r.querySelector('.st').value,r.querySelector('.nt').value]}});
try{{localStorage.setItem(KEY,JSON.stringify({{rv:document.getElementById('rv').value,d}}))}}catch(e){{}}}}
function load(){{try{{const s=JSON.parse(localStorage.getItem(KEY)||'null');if(!s)return;document.getElementById('rv').value=s.rv||'';
document.querySelectorAll('tr[data-id]').forEach(r=>{{const v=s.d[r.dataset.id];if(v){{r.querySelector('.st').value=v[0];r.querySelector('.nt').value=v[1]}}}})}}catch(e){{}}}}
function dl(){{const rv=document.getElementById('rv').value.trim();if(!rv){{alert('Enter reviewer name');return}}
const ts=new Date().toISOString();let out='review_id,review_status,reviewer,review_timestamp,notes\\n';
document.querySelectorAll('tr[data-id]').forEach(r=>{{const st=r.querySelector('.st').value;if(st==='unreviewed')return;
out+=[r.dataset.id,st,rv,ts,'"'+r.querySelector('.nt').value.replace(/"/g,'""')+'"'].join(',')+'\\n'}});
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([out],{{type:'text/csv'}}));a.download='human_review_decisions.csv';a.click()}}
document.addEventListener('change',save);document.addEventListener('input',save);load();
</script></body></html>"""
    (OUT / "review.html").write_text(page, encoding="utf-8")
    counts = defaultdict(int)
    for c in all_cases:
        counts[f"{c['review_id'][0]}/{c['priority']}"] += 1
    print(json.dumps({"earlier_suspects": len(ordered), "new_findings": len(new), "by_group": dict(counts),
                      "sheets": sorted(p.name for p in (OUT / 'sheets').iterdir())}, indent=1))


if __name__ == "__main__":
    main()
