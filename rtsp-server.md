# RTSP Server

> This document covers the CSI camera RTSP streaming server.
> For Docker backend, model setup, and system configuration see [readme.md](readme.md).

## Overview

Streams the CSI camera (IMX219, CAM0) as an H.264 RTSP feed via nvarguscamerasrc.
The stream is consumed by `live-vlm-webui` (WebRTC relay) or any standard RTSP
client (VLC, ffplay, GStreamer).

## Pipeline

```
nvarguscamerasrc camera-id=0
  ! video/x-raw(memory:NVMM),width=1280,height=720,framerate=30/1
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
| Encode | `x264enc` | CPU H.264 encoding (ultrafast + zerolatency, 2000 kbps) |
| Mux | `h264parse` | H.264 stream formatting |
| Payload | `rtph264pay` | RTP packetization for RTSP delivery |

## Requirements

- Xorg running (`xorg.service`, see [readme.md §5](readme.md))
- `DISPLAY=:0` set
- `nvargus-daemon` restarted
- CSI camera configured via `jetson-io.py` (IMX219-A, CAM0)
- Docker image built: `sudo docker build -t rtsp-server rtsp-server/`

## Start / Stop

| Action | Script |
|--------|--------|
| Start | `bash scripts/20-start-rtsp-server.sh [OPTIONS]` |
| Stop | `bash scripts/20-stop-rtsp-server.sh` |

Both scripts check that Xorg is running before proceeding, set `DISPLAY=:0`,
and restart `nvargus-daemon`.  The stop script only removes the Docker container
— Xorg remains managed by systemd (`xorg.service`).

### 1. CLI Options (19-start)

```
  --camera-id N        CSI camera sensor (default: 0)
  --resolution WxH@FPS  e.g. 1920x1080@30 (default: 1920x1080@30)
  --port N             RTSP listening port (default: 8554)
  --path PATH          RTSP mount path (default: /stream)
  --help, -h           show usage
```

Example:

```bash
bash scripts/20-start-rtsp-server.sh --resolution 1920x1080@30 --port 8555
```

### 2. Manual docker run

```bash
sudo docker run -d \
    --name rtsp-server \
    --runtime nvidia \
    --network host \
    --device=/dev/video0 \
    --device=/dev/media0 \
    -v /tmp:/tmp \
    -e WIDTH=1920 -e HEIGHT=1080 -e FPS=30 \
    rtsp-server
```

### 3. Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WIDTH` | 1280 | Frame width |
| `HEIGHT` | 720 | Frame height |
| `FPS` | 30 | Target framerate |
| `RTSP_PORT` | 8554 | RTSP listening port |
| `RTSP_PATH` | /stream | RTSP mount path |
| `SENSOR_ID` | 0 | CSI camera sensor (0 = CAM0) |

## Access

```
rtsp://<jetson-ip>:8554/stream
```

Local test:

```bash
ffplay rtsp://localhost:8554/stream
# or
gst-launch-1.0 rtspsrc location=rtsp://localhost:8554/stream latency=0 \
    ! rtph264depay ! h264parse ! avdec_h264 ! autovideosink
```

## Troubleshooting

### 1. RTSP stream shows ~3 fps instead of 30

Xorg is not running. Verify:

```bash
pgrep Xorg                     # should show PID
echo $DISPLAY                  # should be :0
sudo systemctl restart nvargus-daemon
```

### 2. Connection refused from live-vlm-webui

`live-vlm-webui` uses `--network host` and connects to `localhost:8554`.
Ensure RTSP server is started **before** live-vlm-webui.  If WebUI was started
first, it will permanently give up after 5 reconnection attempts — restart
WebUI after RTSP is running:

```bash
sudo docker restart live-vlm-webui
```

