"""Record the software and hardware environment (accuracy-improvement specification, Phase 0).

    .venv/bin/python scripts/accuracy/phase0_environment.py <out_dir>

Writes <out_dir>/environment.json (Python, key library versions, MPS availability and a measured MPS
operation, the project's actual device selection, memory, swap, power, thermal and disk state) and
<out_dir>/packages.txt (every installed distribution with its version). Nothing is installed or changed.
"""

from __future__ import annotations

import importlib.metadata as md
import json
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))


def run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as exc:  # pragma: no cover - diagnostic only
        return f"ERROR {exc}"


def dist_version(name: str):
    try:
        return md.version(name)
    except md.PackageNotFoundError:
        return None


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    env: dict = {"recorded_at": datetime.now().isoformat(timespec="seconds")}

    env["python"] = {"version": sys.version.split()[0], "executable": sys.executable, "prefix": sys.prefix,
                     "base_prefix": sys.base_prefix, "is_virtualenv": sys.prefix != sys.base_prefix,
                     "implementation": platform.python_implementation()}

    env["distributions"] = {n: dist_version(n) for n in (
        "ultralytics", "torch", "torchvision", "opencv-python", "opencv-python-headless", "opencv-contrib-python",
        "numpy", "pillow", "albumentations", "streamlit", "streamlit-webrtc", "pandas", "scipy", "pyyaml",
        "matplotlib", "plotly", "pytest", "av", "aiortc")}

    import cv2
    import numpy
    import PIL
    import torch
    runtime = {"torch": torch.__version__, "cv2": cv2.__version__, "numpy": numpy.__version__, "PIL": PIL.__version__}
    try:
        import albumentations
        runtime["albumentations"] = albumentations.__version__
    except ImportError:
        runtime["albumentations"] = None
    import ultralytics
    runtime["ultralytics"] = ultralytics.__version__
    env["runtime_import_versions"] = runtime

    mps: dict = {"built": torch.backends.mps.is_built(), "available": torch.backends.mps.is_available()}
    if mps["available"]:
        x = torch.randn(2048, 2048, device="mps")
        torch.mps.synchronize()
        t = time.perf_counter()
        for _ in range(10):
            y = x @ x
        torch.mps.synchronize()
        mps["matmul_2048x2048_x10_ms"] = round((time.perf_counter() - t) * 1000, 1)
        mps["result_device"] = str(y.device)
        if hasattr(torch.mps, "recommended_max_memory"):
            mps["recommended_max_memory_gb"] = round(torch.mps.recommended_max_memory() / 1e9, 2)
        mps["driver_allocated_mb_after_test"] = round(torch.mps.driver_allocated_memory() / 1e6, 1)
    env["mps"] = mps

    from src.detection.detector import resolve_device
    from src.training.train import pick_device
    env["project_device_selection"] = {"inference_resolve_device('auto')": resolve_device("auto"),
                                       "training_pick_device('auto')": pick_device("auto")}

    from ultralytics import settings as ul_settings
    env["ultralytics_settings"] = {k: ul_settings.get(k) for k in ("datasets_dir", "runs_dir", "weights_dir", "sync")}

    sysctl = {k: run(["sysctl", "-n", k]) for k in ("hw.model", "machdep.cpu.brand_string", "hw.memsize", "hw.ncpu",
                                                     "hw.perflevel0.physicalcpu", "hw.perflevel1.physicalcpu", "vm.swapusage")}
    env["hardware"] = {"model": sysctl["hw.model"], "cpu": sysctl["machdep.cpu.brand_string"],
                       "memory_gb": round(int(sysctl["hw.memsize"]) / 2**30, 1) if sysctl["hw.memsize"].isdigit() else sysctl["hw.memsize"],
                       "logical_cpus": sysctl["hw.ncpu"], "performance_cores": sysctl["hw.perflevel0.physicalcpu"],
                       "efficiency_cores": sysctl["hw.perflevel1.physicalcpu"]}
    env["os"] = {"sw_vers": run(["sw_vers"]).replace("\t", " ").splitlines(), "uname": platform.uname()._asdict()}

    mp = run(["memory_pressure"])
    m = re.search(r"System-wide memory free percentage:\s*(\d+)%", mp)
    env["memory"] = {"system_free_percent": int(m.group(1)) if m else None, "swapusage": sysctl["vm.swapusage"],
                     "vm_stat_head": run(["vm_stat"]).splitlines()[:12]}
    env["power"] = {"pmset_batt": run(["pmset", "-g", "batt"]).splitlines(),
                    "pmset_therm": run(["pmset", "-g", "therm"]).splitlines(),
                    "low_power_mode": [l.strip() for l in run(["pmset", "-g"]).splitlines() if "lowpowermode" in l]}
    du = shutil.disk_usage(PROJECT)
    env["disk"] = {"free_gb": round(du.free / 1e9, 1), "total_gb": round(du.total / 1e9, 1)}

    (out_dir / "environment.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
    pkgs = sorted(f"{d.metadata['Name']}=={d.version}" for d in md.distributions() if d.metadata["Name"])
    (out_dir / "packages.txt").write_text("\n".join(pkgs) + "\n", encoding="utf-8")
    print(json.dumps({k: env[k] for k in ("python", "runtime_import_versions", "mps", "project_device_selection",
                                          "hardware", "memory", "disk")}, indent=1))
    print("packages:", len(pkgs))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
