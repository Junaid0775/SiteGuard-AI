"""Timestamped SHA-256 integrity manifests (accuracy-improvement specification, §0.1 rules 1-7 and Phase 0).

    .venv/bin/python scripts/accuracy/integrity_manifest.py create <tag>
    .venv/bin/python scripts/accuracy/integrity_manifest.py verify <manifest_dir> [--json <out.json>]

create writes experiments/accuracy_improvement/manifests/<YYYYmmdd-HHMMSS>_<tag>/ with:
  dataset.csv    every file of the ORIGINAL dataset (../construction-ppe). Read-only; never modified.
  protected.csv  checkpoints, pretrained weights, configs, generated dataset configs, docs, reports,
                 specifications, source code, tests, scripts and earlier experiment evidence.
  user_data.csv  SQLite events database, evidence images, user outputs and the private webcam audit files.
                 These are hashed locally only; they are never copied, uploaded or opened for viewing.
  summary.json   counts, key checkpoint identities, the active checkpoint, and dataset provenance checks
                 (pre-project baseline data/dataset_baseline.sha256 and the dataset's own manifest.jsonl).

verify recomputes every hash in one manifest directory, prints CHANGED / MISSING files, and lists files that
are NEW in the original dataset directory. The exit code is 1 if the dataset or a key checkpoint changed.

Nothing is modified by this script. The symlink mirror data/dataset_mirror/ is not hashed file by file
(its links point at the dataset files that are hashed); its link targets are checked instead.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

PROJECT = Path(__file__).resolve().parents[2]
DATASET = PROJECT.parent / "construction-ppe"
OUT_ROOT = PROJECT / "experiments" / "accuracy_improvement" / "manifests"
FIELDS = ["path", "size_bytes", "sha256", "mtime_iso", "role"]
SKIP_PARTS = {".venv", "__pycache__", ".pytest_cache", ".git"}

KEY_CHECKPOINTS = {
    "models/trained/best.pt": "ACTIVE application checkpoint (YOLO26n) - never overwrite",
    "models/trained/last.pt": "YOLO26n last-epoch checkpoint - preserve",
    "experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt": "previously evaluated YOLO26m checkpoint - never overwrite",
    "experiments/yolo26m/training/yolo26m_e30_b4/weights/last.pt": "YOLO26m last-epoch checkpoint - preserve",
    "models/pretrained/yolo26n.pt": "pretrained YOLO26n starting weights",
    "models/pretrained/yolo26m.pt": "pretrained YOLO26m starting weights",
}
# Written continuously by the running dashboard process; a change here is expected and not a violation.
VOLATILE = {"outputs/streamlit_server.log"}

PROTECTED_DIRS = ["configs", ".streamlit", "data", "docs", "src", "tests", "scripts", "models", "experiments"]
EXCLUDED_PREFIXES = ("data/dataset_mirror/", "experiments/accuracy_improvement/", "experiments/live_audit/webcam/")
USER_DATA_DIRS = ["outputs", "experiments/live_audit/webcam"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_files(root: Path):
    if not root.exists():
        return
    for p in sorted(root.rglob("*")):
        if p.name == ".DS_Store" or any(part in SKIP_PARTS for part in p.parts):
            continue
        if p.is_symlink() or not p.is_file():
            continue
        yield p


def make_row(p: Path, base: Path, role: str) -> dict:
    st = p.stat()
    return {"path": p.relative_to(base).as_posix(), "size_bytes": st.st_size, "sha256": sha256(p),
            "mtime_iso": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"), "role": role}


def protected_role(rel: str) -> str:
    if rel in KEY_CHECKPOINTS:
        return KEY_CHECKPOINTS[rel]
    if rel.endswith(".pt"):
        return "checkpoint (earlier experiment) - preserve"
    for prefix, role in (("configs/", "configuration"), (".streamlit/", "dashboard configuration"),
                         ("data/generated/", "generated dataset configuration"), ("data/", "project data / metadata"),
                         ("docs/reports/", "report"), ("docs/", "documentation"), ("src/", "application source"),
                         ("tests/", "test"), ("scripts/", "script"), ("experiments/", "experiment evidence"),
                         ("models/", "model artefact")):
        if rel.startswith(prefix):
            return role
    if rel == "app.py":
        return "application source"
    if rel.endswith(".md"):
        return "specification / README"
    return "project configuration"


def user_role(rel: str) -> str:
    if rel.endswith("siteguard_events.db"):
        return "SQLite events database (user data)"
    if rel.startswith("outputs/evidence/"):
        return "event evidence image (user data)"
    if rel.startswith("experiments/live_audit/webcam/"):
        return "PRIVATE webcam audit material (local only)"
    if rel in VOLATILE:
        return "volatile dashboard server log"
    return "user output"


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def dataset_checks(rows: list[dict]) -> dict:
    by_rel = {r["path"]: r["sha256"] for r in rows}
    out: dict = {"files": len(rows)}
    baseline = PROJECT / "data" / "dataset_baseline.sha256"
    if baseline.exists():
        base = {}
        for line in baseline.read_text(encoding="utf-8").splitlines():
            if line.strip():
                h, rel = line.split(None, 1)
                base[rel.strip()] = h
        out["pre_project_baseline"] = {
            "entries": len(base),
            "matched": sum(1 for k, h in base.items() if by_rel.get(k) == h),
            "changed": sorted(k for k, h in base.items() if k in by_rel and by_rel[k] != h),
            "missing": sorted(k for k in base if k not in by_rel),
            "not_in_baseline": sorted(k for k in by_rel if k not in base),
        }
    manifest = DATASET / "manifest.jsonl"
    if manifest.exists():
        entries = [json.loads(l) for l in manifest.read_text(encoding="utf-8").splitlines() if l.strip()]
        matched = mismatched = absent = 0
        splits: dict[str, int] = {}
        for e in entries:
            splits[e["split"]] = splits.get(e["split"], 0) + 1
            rel = f"construction-ppe/images/{e['split']}/{e['file']}"
            if rel not in by_rel:
                absent += 1
            elif by_rel[rel] == e["sha256"]:
                matched += 1
            else:
                mismatched += 1
        out["dataset_own_manifest_jsonl"] = {"entries": len(entries), "image_hash_matched": matched,
                                             "image_hash_mismatched": mismatched, "image_absent": absent,
                                             "split_counts": splits}
    return out


def mirror_checks() -> dict:
    mirror = PROJECT / "data" / "dataset_mirror"
    links = [p for p in mirror.rglob("*") if p.is_symlink()]
    into_dataset = broken = 0
    for p in links:
        target = p.resolve()
        if not target.exists():
            broken += 1
        elif DATASET.resolve() in target.parents:
            into_dataset += 1
    regular = [p.relative_to(PROJECT).as_posix() for p in mirror.rglob("*") if p.is_file() and not p.is_symlink()]
    return {"symlinks": len(links), "resolve_into_original_dataset": into_dataset, "broken": broken,
            "regular_files": regular}


def create(tag: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = OUT_ROOT / f"{stamp}_{tag}"
    out.mkdir(parents=True, exist_ok=False)

    dataset_rows = [make_row(p, DATASET.parent, "ORIGINAL dataset - read-only") for p in iter_files(DATASET)]

    protected: list[Path] = [p for p in PROJECT.iterdir() if p.is_file() and p.name != ".DS_Store"]
    for d in PROTECTED_DIRS:
        protected += list(iter_files(PROJECT / d))
    protected_rows = []
    for p in sorted(set(protected)):
        rel = p.relative_to(PROJECT).as_posix()
        if rel.startswith(EXCLUDED_PREFIXES) or rel.startswith("outputs/"):
            continue
        protected_rows.append(make_row(p, PROJECT, protected_role(rel)))

    user_rows = []
    for d in USER_DATA_DIRS:
        for p in iter_files(PROJECT / d):
            rel = p.relative_to(PROJECT).as_posix()
            user_rows.append(make_row(p, PROJECT, user_role(rel)))

    write_csv(out / "dataset.csv", dataset_rows)
    write_csv(out / "protected.csv", protected_rows)
    write_csv(out / "user_data.csv", user_rows)

    settings = yaml.safe_load((PROJECT / "configs" / "settings.yaml").read_text(encoding="utf-8"))
    by_path = {r["path"]: r for r in protected_rows}
    summary = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "tag": tag,
        "counts": {"dataset": len(dataset_rows), "protected": len(protected_rows), "user_data": len(user_rows)},
        "bytes": {"dataset": sum(r["size_bytes"] for r in dataset_rows),
                  "protected": sum(r["size_bytes"] for r in protected_rows),
                  "user_data": sum(r["size_bytes"] for r in user_rows)},
        "active_checkpoint_setting": settings["model"]["trained_weights"],
        "key_checkpoints": {rel: ({"sha256": by_path[rel]["sha256"], "size_bytes": by_path[rel]["size_bytes"], "role": role}
                                  if rel in by_path else "MISSING") for rel, role in KEY_CHECKPOINTS.items()},
        "events_database": next(({"path": r["path"], "sha256": r["sha256"], "size_bytes": r["size_bytes"]}
                                 for r in user_rows if r["path"].endswith("siteguard_events.db")), "MISSING"),
        "dataset_checks": dataset_checks(dataset_rows),
        "dataset_mirror": mirror_checks(),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(out.relative_to(PROJECT).as_posix())
    print(json.dumps(summary["counts"]), json.dumps(summary["bytes"]))
    return out


def verify(manifest_dir: Path, json_out: Path | None) -> int:
    result: dict = {"verified_at": datetime.now().isoformat(timespec="seconds"), "manifest_dir": str(manifest_dir)}
    critical = 0
    for name, base in (("dataset.csv", DATASET.parent), ("protected.csv", PROJECT), ("user_data.csv", PROJECT)):
        changed, missing, volatile = [], [], []
        listed = set()
        with open(manifest_dir / name, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                listed.add(row["path"])
                p = base / row["path"]
                if not p.exists():
                    missing.append(row["path"])
                elif sha256(p) != row["sha256"]:
                    (volatile if row["path"] in VOLATILE else changed).append(row["path"])
        entry = {"listed": len(listed), "changed": changed, "missing": missing, "volatile_changed": volatile}
        if name == "dataset.csv":
            now = {p.relative_to(DATASET.parent).as_posix() for p in iter_files(DATASET)}
            entry["new_files"] = sorted(now - listed)
            critical += len(changed) + len(missing) + len(entry["new_files"])
        else:
            critical += sum(1 for rel in changed + missing if rel in KEY_CHECKPOINTS)
        result[name] = entry
        print(f"{name}: listed={len(listed)} changed={len(changed)} missing={len(missing)} "
              f"volatile_changed={len(volatile)}" + (f" new={len(entry['new_files'])}" if 'new_files' in entry else ""))
        for rel in changed + missing:
            print("   ", "CHANGED" if rel in changed else "MISSING", rel)
    result["critical_violations"] = critical
    print("critical violations (dataset or key checkpoint):", critical)
    if json_out:
        json_out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return critical


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("create", "verify"):
        raise SystemExit(__doc__)
    if sys.argv[1] == "create":
        create(sys.argv[2])
    else:
        jo = Path(sys.argv[sys.argv.index("--json") + 1]) if "--json" in sys.argv else None
        raise SystemExit(1 if verify(Path(sys.argv[2]), jo) else 0)
