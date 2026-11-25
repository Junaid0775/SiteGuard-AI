"""YOLO26m hardware readiness and smoke tests (spec §7.2-7.3). Isolated in experiments/yolo26m/.

    .venv/bin/python scripts/engineering/yolo26m_smoke.py inference
    .venv/bin/python scripts/engineering/yolo26m_smoke.py train --batch 8      # 1 epoch on 10 % of train

Nothing outside experiments/yolo26m/ is written. models/trained/best.pt is never touched (--no-promote).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "experiments" / "yolo26m"
WEIGHTS = ROOT / "models" / "pretrained" / "yolo26m.pt"


def memory_pressure_free_pct() -> float | None:
    try:
        out = subprocess.run(["memory_pressure"], capture_output=True, text=True, timeout=20).stdout
        m = re.search(r"free percentage:\s*(\d+)%", out)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def swap_used_mb() -> float | None:
    try:
        out = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout
        m = re.search(r"used = ([\d.]+)M", out)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def inference() -> dict:
    import cv2
    import numpy as np
    import torch

    from src.utils.paths import configure_ultralytics, source_dataset_dir

    configure_ultralytics()
    from ultralytics import YOLO

    res = {"weights": str(WEIGHTS.relative_to(ROOT)), "sha256": hashlib.sha256(WEIGHTS.read_bytes()).hexdigest(),
           "size_bytes": WEIGHTS.stat().st_size, "mps_available": torch.backends.mps.is_available(),
           "mps_built": torch.backends.mps.is_built(), "memory_free_pct_before": memory_pressure_free_pct()}
    t0 = time.perf_counter()
    m = YOLO(str(WEIGHTS))
    res["load_s"] = round(time.perf_counter() - t0, 3)
    res.update(task=m.task, yaml=m.model.yaml.get("yaml_file"), scale=m.model.yaml.get("scale"), nc=len(m.names),
               params=sum(p.numel() for p in m.model.parameters()))
    imgs = [cv2.imread(str(p)) for p in sorted((source_dataset_dir() / "images" / "val").glob("*.jpg"))[:24]]
    t1 = time.perf_counter()
    r = m.predict(imgs[0], imgsz=640, device="mps", verbose=False)[0]
    res["first_predict_s"] = round(time.perf_counter() - t1, 3)
    res["backend_device"] = str(m.predictor.model.device)
    res["param_device"] = str(next(m.predictor.model.model.parameters()).device)
    lat = []
    for im in imgs[:20]:
        t = time.perf_counter()
        r = m.predict(im, imgsz=640, device="mps", verbose=False)[0]
        lat.append(((time.perf_counter() - t) * 1000, r.speed["inference"]))
    w = np.array([x for x, _ in lat]); inf = np.array([y for _, y in lat])
    res["single_image"] = {"runs": len(lat), "wall_ms_mean": round(float(w.mean()), 2), "wall_ms_p95": round(float(np.percentile(w, 95)), 2),
                           "inference_ms_mean": round(float(inf.mean()), 2), "inference_ms_median": round(float(np.median(inf)), 2),
                           "inference_ms_p95": round(float(np.percentile(inf, 95)), 2)}
    t2 = time.perf_counter()
    rs = m.predict(imgs[:8], imgsz=640, device="mps", verbose=False, batch=8)
    res["batch8_predict"] = {"wall_s": round(time.perf_counter() - t2, 3), "images": len(rs),
                             "inference_ms_per_image": round(float(np.mean([x.speed["inference"] for x in rs])), 2)}
    res["mps_current_allocated_mb"] = round(torch.mps.current_allocated_memory() / 1e6, 1)
    res["mps_driver_allocated_mb"] = round(torch.mps.driver_allocated_memory() / 1e6, 1)
    res["memory_free_pct_after"] = memory_pressure_free_pct()
    res["swap_used_mb"] = swap_used_mb()
    (OUT / "benchmarks").mkdir(parents=True, exist_ok=True)
    (OUT / "benchmarks" / "smoke_inference.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=1))
    return res


def train(batch: int, fraction: float, epochs: int) -> dict:
    """Run src.training.train in a subprocess while sampling system memory pressure."""
    name = f"smoke_b{batch}_f{int(fraction * 100)}_e{epochs}"
    log = OUT / "logs" / f"{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(ROOT / ".venv/bin/python"), "-m", "src.training.train", "--weights", str(WEIGHTS.relative_to(ROOT)),
           "--epochs", str(epochs), "--batch", str(batch), "--fraction", str(fraction), "--no-promote",
           "--project", "experiments/yolo26m/training", "--name", name]
    samples, stop = [], threading.Event()

    def sampler():
        while not stop.is_set():
            samples.append((time.time(), memory_pressure_free_pct(), swap_used_mb()))
            stop.wait(5)

    th = threading.Thread(target=sampler, daemon=True)
    swap0 = swap_used_mb()
    th.start()
    t0 = time.time()
    with open(log, "w") as f:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    dur = time.time() - t0
    stop.set(); th.join()
    text = log.read_text(errors="ignore")
    gpu = [float(x) for x in re.findall(r"\s(\d+\.\d+)G\s", text)]
    iters = re.findall(r"(\d+\.\d+)(it/s|s/it)", text)
    warn = sorted({l.strip()[:160] for l in text.splitlines() if "WARNING" in l or "fallback" in l.lower() or "not supported" in l.lower()})
    free = [s[1] for s in samples if s[1] is not None]
    res = {"command": " ".join(cmd), "returncode": rc, "seconds": round(dur, 1), "batch": batch, "fraction": fraction, "epochs": epochs,
           "ultralytics_gpu_mem_gb_max": max(gpu) if gpu else None, "last_iter_speed": iters[-1] if iters else None,
           "memory_free_pct_min": min(free) if free else None, "memory_free_pct_samples": len(free),
           "swap_used_mb_before": swap0, "swap_used_mb_after": swap_used_mb(), "warnings": warn[:15],
           "log": str(log.relative_to(ROOT)), "run_dir": f"experiments/yolo26m/training/{name}"}
    (OUT / "benchmarks" / f"{name}.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("what", choices=["inference", "train"])
    a.add_argument("--batch", type=int, default=8)
    a.add_argument("--fraction", type=float, default=0.1)
    a.add_argument("--epochs", type=int, default=1)
    args = a.parse_args()
    inference() if args.what == "inference" else train(args.batch, args.fraction, args.epochs)
