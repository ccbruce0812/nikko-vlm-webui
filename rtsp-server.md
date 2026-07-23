# RTSP Server

This document covers the CSI camera RTSP streaming server.<br>
For Docker backend, model setup, and system configuration see [readme.md](readme.md).

## Overview

Streams the CSI camera as an H.264 RTSP feed via nvarguscamerasrc.<br>
The stream is consumed by `live-vlm-webui` or any standard RTSP client (VLC, ffplay, GStreamer).

### 1. Architecture

```mermaid
flowchart LR
    csi["Camera"]
    gst["Gstreamer<br>Pipeline"]
    server["rtsp-server"]
    client["RTSP Client"]

    csi --> gst --> server --> client
```

### 2. Pipeline

```
nvarguscamerasrc sensor-id=X
  ! video/x-raw(memory:NVMM),width=W,height=H,framerate=FPS/1
  ! nvvidconv
  ! video/x-raw,format=I420
  ! x264enc speed-preset=ultrafast tune=zerolatency bitrate=2000
  ! h264parse
  ! rtph264pay name=pay0 pt=96
```

| Stage | Element | Purpose |
|-------|---------|---------|
| Capture | `nvarguscamerasrc` | CSI camera hardware-accelerated capture (NVMM zero-copy) |
| Convert | `nvvidconv` | NVMM → I420 color conversion |
| Encode | `x264enc` | CPU H.264 encoding |
| Mux | `h264parse` | H.264 stream formatting |
| Payload | `rtph264pay` | RTP packetization for RTSP delivery |

## Install & Launch

### 1. Install

Run the setup scripts in order (`01-disable-gui.sh` through `05-build-all.sh`) —
this configures Xorg, OpenBox, Camera, Super power mode,
Memory tuning, Downloads models, and builds all Docker images.<br>
The `rtsp-server` image is built as part of `05-build-all.sh`.

### 2. Launch

```bash
bash scripts/11-start-rtsp-server.sh [OPTIONS]
```

Interactive launcher — prompts for each parameter (press Enter for defaults).<br>
Checks Xorg is running, restarts `nvargus-daemon`, then launches the RTSP container
with `-p PORT:PORT` and CLI arguments passed directly to `rtsp-server.py`.

| Option | Default | Description |
|--------|---------|-------------|
| `--camera-id N` | 0 | Camera ID |
| `--resolution WxH@FPS` | `1920x1080@30` | Stream resolution |
| `--port N` | 8554 | RTSP listening port |
| `--path PATH` | `/stream` | RTSP mount path |
| `--help, -h` | — | Show usage |

> 📄 Start: `scripts/11-start-rtsp-server.sh`
> 📄 Stop: `scripts/12-stop-rtsp-server.sh`

### 3. Access

```
rtsp://<jetson-ip>:<port>/<path>
```

Local test:

```bash
gst-launch-1.0 rtspsrc location=rtsp://<jetson-ip>:<port>/<path> latency=0 \
    ! rtph264depay ! h264parse ! avdec_h264 ! autovideosink
```

## Troubleshooting

### 1. RTSP stream shows ~3 fps instead of 30

Same Argus root cause as the GUI — see [pyside6-gui.md §1](pyside6-gui.md).
Xorg must be running with `DISPLAY=:0` for full-speed camera capture.

### 2. CMA / NVMM allocation failure

Same root cause as the GUI pipeline — see [pyside6-gui.md §2](pyside6-gui.md).

