# Live VLM WebUI

> This document covers the live-vlm-webui Docker container.

> For Docker backend, model setup, and system configuration see [readme.md](readme.md).

## Overview

Official NVIDIA live-vlm-webui (`ghcr.io/nvidia-ai-iot/live-vlm-webui:latest-jetson-orin`),
customized with Jetson GPU monitor fix and pre-configured for the local Router API.
Provides a browser-based WebRTC frontend that relays CSI camera frames (via RTSP server)
and dispatches VLM inference through the Router at `localhost:8080`.

## Architecture

```
Browser ──WebRTC──► live-vlm-webui (:8090, host network)
                         │
                         ├── RTSP ──► rtsp-server (:8554, host network) ──► CSI Camera
                         │
                         └── HTTP ──► router (:8080, vlm-net) ──► model container
```

The WebUI uses host networking (`--network host`) for WebRTC (needs direct UDP) and
RTSP relay (connects to `localhost:8554`).  Model inference goes through the Router
API on the `vlm-net` bridged network.

## Pipeline

```
CSI Camera → rtsp-server (H.264 RTSP) → live-vlm-webui (WebRTC relay) → Browser
                                   live-vlm-webui → Router API → Model → Response → overlay
```

The WebUI streams the RTSP feed to the browser as WebRTC.  When the user submits a
prompt, the WebUI captures the current frame, sends it to the Router API, and displays
the inference result as an overlay.

## Requirements

- RTSP server running (`rtsp-server` container, see [rtsp-server.md](rtsp-server.md))
- Router running (`router` container on `vlm-net`)
- At least one model container running (reason2 / moondream2 / yolo)
- Docker image built: `sudo docker build -t live-vlm-webui live-vlm-webui/`

## Build

```bash
sudo docker build -t live-vlm-webui live-vlm-webui/
```

> 📄 Script: `scripts/05-build-all.sh` (builds all containers)

## Dockerfile Customizations

The Dockerfile applies two changes on top of the official image:

### 1. GPU Monitor Patch

`patch_gpu_monitor.py` fixes GPU utilization reporting for Jetson:
- Adds `/sys/devices/platform/*/gpu.0/load` fallback when jtop returns 0
- Skips nvidia-smi fallback on Jetson (VRAM=0 is normal with unified memory)

### 2. API Defaults

Pre-configured environment variables point to the local Router:

| Variable | Value |
|----------|-------|
| `LIVE_VLM_API_BASE` | `http://localhost:8080/v1` |
| `LIVE_VLM_DEFAULT_MODEL` | `reason2` |

## Start / Stop

| Action | Script |
|--------|--------|
| Start | `bash scripts/20-start-live-vlm-webui.sh [OPTIONS]` |
| Stop | `bash scripts/21-stop-live-vlm-webui.sh` |

The start script checks that no existing instance is running, removes any stale
container, then launches with the specified port (default 8090).

### CLI Options (20-start)

```
  --port N             WebUI listening port (default: 8090)
  --help, -h           show usage
```

Example:

```bash
bash scripts/20-start-live-vlm-webui.sh --port 8091
```

### Manual docker run

```bash
sudo docker run -d --name live-vlm-webui \
    --network host \
    --runtime nvidia \
    --privileged \
    -v /sys:/sys:ro \
    live-vlm-webui
```

## Access

```
http://<jetson-ip>:8090
```

Local access from Jetson desktop:

```
http://localhost:8090
```

The browser connects via WebRTC (ICE/DTLS/SCTP/SRTP).  Ensure the Jetson and the
client browser are on the same network (no NAT traversal).

## Troubleshooting

### 1. WebUI starts but shows black screen

RTSP server is not running or started after WebUI.  The WebUI tries 5 reconnection
attempts then gives up.  Start RTSP server first, then WebUI:

```bash
bash scripts/18-start-rtsp-server.sh
sudo docker restart live-vlm-webui
```

### 2. GPU monitor always shows 0%

Normal on Jetson with unified memory. The `patch_gpu_monitor.py` fix is already
applied in the Dockerfile — GPU load is read from sysfs.  If still 0%, the container
may have been built without the patch.

### 3. WebRTC connection fails (ICE disconnected)

WebUI uses `--network host` for direct UDP.  If the browser is behind NAT or a
different subnet, WebRTC may fail.  Ensure browser and Jetson are on the same LAN.

### 4. Prompt submitted but no response / error

Check Router and model container logs:

```bash
sudo docker logs router
sudo docker logs reason2
```

Ensure the model container is running and registered with the Router
(`curl http://localhost:8080/v1/models`).
