# REPORT-002 — Environment Setup

**Date:** 2026-11-19 **Status:** Complete

## A. Task summary

- **Requested:** a Python environment with PyTorch, Ultralytics, OpenCV, Streamlit, streamlit-webrtc, NumPy, Pandas, Plotly, PyYAML and pytest; an MPS check; and a pretrained model that loads.
- **Done:** all of the above.
- **Completion:** full.

## B. Technical implementation

- **Virtual environment:** `SiteGuard-AI/.venv`, created by `uv` with CPython 3.12.16. 3.12 was chosen over the system 3.10 because current PyTorch and Ultralytics wheels target it, and it is uv-managed, so no global installs were needed.
- **Pretrained model:** `yolo26n.pt` (YOLO26 nano). It is in Ultralytics 8.4.215's `GITHUB_ASSETS_STEMS`, so it is a supported release asset. The file came from `https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt` and was saved to `models/pretrained/yolo26n.pt` (5,544,453 bytes, sha256 `9b09cc8b…`). The model has 2,572,280 parameters, 80 COCO classes and task `detect`.
- **Ultralytics settings:** `YOLO_CONFIG_DIR` is set to `SiteGuard-AI/.ultralytics` by `src/utils/paths.py`, so Ultralytics' settings file stays inside the project. Anonymous usage analytics (`sync`) are turned **off**, and `runs_dir` points to `experiments/`.
- **Streamlit:** `.streamlit/config.toml` sets `gatherUsageStats = false`.

### Installed versions (key packages)

torch 2.15.0, torchvision 0.29.2, ultralytics 8.4.215, opencv-python 5.1.0.95, numpy 2.5.5, pandas 3.1.1, plotly 7.1.0, pyyaml 6.0.3, pillow 13.0.0, streamlit 1.67.0, streamlit-webrtc 0.79.1 (aiortc 1.16.0, av 19.0.2), pytest 9.2.0. All are pinned in `requirements.txt`.

## C. Files created

| File | Purpose |
|---|---|
| `.venv/` | Virtual environment (not for version control) |
| `requirements.txt` | Pinned dependencies |
| `.gitignore` | Excludes the venv, weights, generated data and outputs |
| `models/pretrained/yolo26n.pt` | Pretrained starting weights |
| `.ultralytics/Ultralytics/settings.json`, `Arial.ttf` | Local Ultralytics config and plot font |
| `.streamlit/config.toml` | Theme and telemetry settings |

## D. Files modified

None outside the project. Note: before `YOLO_CONFIG_DIR` was configured, the first `import ultralytics` automatically created `~/Library/Application Support/Ultralytics/settings.json` (Ultralytics default behaviour). It is harmless and unused by SiteGuard, and can be deleted.

## E. Commands executed

```bash
uv venv --python 3.12 .venv
UV_HTTP_TIMEOUT=300 uv pip install --python .venv/bin/python torch torchvision ultralytics opencv-python \
    streamlit streamlit-webrtc numpy pandas plotly pyyaml pytest pillow
curl -sSL -o models/pretrained/yolo26n.pt https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt
.venv/bin/python -c "import torch; print(torch.backends.mps.is_available())"
```

## F. Testing and verification

| Test | What | Result |
|---|---|---|
| Imports | All packages import | PASS |
| MPS | `torch.backends.mps.is_available()` and a 512×512 matmul on `mps` | PASS (True) |
| Pretrained load | `YOLO("models/pretrained/yolo26n.pt")` gives a DetectionModel with 80 classes | PASS |
| Pretrained predict on MPS | One val image | PASS (4.2 ms inference) |

## G. Model and dataset status

Pretrained YOLO26n is ready. Custom training is in REPORT-004.

## H. Errors and resolutions

| Error | Cause | Resolution |
|---|---|---|
| `invalid peer certificate: UnknownIssuer` and `"Sophos SSL CA…" certificate is not trusted` | Sophos TLS inspection on this network intercepts some HTTPS downloads | Retried without `--system-certs`. The failures were intermittent, and later attempts succeeded. |
| `network timeout` (torch 132 MB), DNS lookup failures | Unstable network | Set `UV_HTTP_TIMEOUT=300` and retried. Fourth attempt succeeded. |
| Ultralytics `ConnectionError … Download failure` for yolo26n.pt | Same network issue (connection reset) | Downloaded with `curl` and retried. Second attempt succeeded. |
| `objc: Class AVFFrameReceiver is implemented in both …cv2… and …av…` | OpenCV and PyAV each bundle FFmpeg's `libavdevice` | Warning only. All tests pass, including video and webcam-processor tests. Documented under limitations. |

## I. Acceptance criteria

| Criterion | Status |
|---|---|
| Python environment configured | PASS |
| PyTorch, Ultralytics, MPS verified | PASS |
| Pretrained model loads | PASS |

## J. Remaining work

None for this task.

## K. Next task

Dataset configuration (REPORT-003).
