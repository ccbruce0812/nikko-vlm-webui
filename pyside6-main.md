# pyside6-main

> **Note: Architecture rewritten July 2026.** Inference now goes through Router HTTP API (Docker containers) instead of local llama.cpp. See [readme.md](readme.md) for the Docker backend.

## Overview

PySide6 desktop GUI for live CSI camera + VLM/YOLO inference via Router API.
Runs under Xorg + openbox (same environment as pyside6-gui).
YOLO runs automatically in background; VLM (reason2/moondream2) triggered manually.

## Install & Run

| Action | Script |
|--------|--------|
| Create venv + install deps | `bash scripts/15-install-pyside6-main.sh` |
| Start GUI | `bash scripts/16-start-pyside6-main.sh` |

Requires Router and at least one model container running (see `scripts/06-start-models.sh`).

## File Structure

```
pyside6-main/
├── main.py                         # entry point
└── src/
    ├── modules/
    │   ├── router_client.py        # HTTP client (QThread)
    │   ├── yolo_overlay.py         # YOLO box drawing
    │   ├── reason2_overlay.py      # reason2 caption
    │   ├── moondream2_overlay.py   # moondream2 caption
    │   ├── video_worker.py         # GStreamer CSI pipeline (single stream)
    │   └── system_monitor.py       # /proc + /sys GPU/CPU/RAM/VRAM
    └── ui/
        ├── main_window.py          # main window: Router API + YOLO auto + VLM submit
        ├── ai_config_panel.py      # unified model selector + prompt + result
        ├── control_panel.py        # camera / resolution / start-stop
        └── video_canvas.py         # QPainter rendering + YOLO boxes
```
