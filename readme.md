# Reason2 + moondream2 + YOLO GGUF Container Inference Platform

## Overview

Multi-model VLM inference on NVIDIA Jetson Orin Nano via Docker containers, using the jetson-containers ecosystem for CUDA management.

### 1. Architecture

```mermaid
flowchart LR
    Browser["Browser"]
    WebUI["live-vlm-webui<br/>:8090"]
    Router["Router<br/>:8080"]
    Moon["moondream2 GGUF<br/>:8001"]
    Cosmos["Reason2 GGUF<br/>:8002"]
    YOLO["YOLO TensorRT<br/>:8003"]

    Browser --> WebUI --> Router
    Router --> Moon
    Router --> Cosmos
    Router --> YOLO
```

### 2. Router Dynamic Model Detection

Router auto-probes backend containers. `/v1/models` only returns actually running models.

- Container stops → auto-removed from list
- Container starts → appears within 3 seconds
- WebUI model dropdown updates in real-time

### 3. Hardware Requirements

- **NVIDIA Jetson Orin Nano** (JetPack 6.2.1 / L4T R36.4.7)
- CUDA 12.6 (GPU Driver 540.4.0)
- RAM: 7.4GB
- Storage: 30GB+ free (Docker images ~20GB + models ~3.5GB)

## Prerequisites

### 1. Prepare SD Card

Download the [JetPack 6.2.1 Super SD Card Image](https://developer.nvidia.com/downloads/embedded/L4T/r36_Release_v4.4/jp62-r1-orin-nano-sd-card-image.zip) and flash to SD card using [balenaEtcher](https://github.com/balena-io/etcher/releases/download/v2.1.6/balenaEtcher-2.1.6.Setup.exe). Insert the card and boot.

### 2. Complete Setup in Terminal

- Generate SSH key locally and copy to remote (passwordless login)

Generate SSH Key

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

Press Enter to accept defaults:

```text
~/.ssh/id_ed25519
~/.ssh/id_ed25519.pub
```

Copy public key to remote:

```bash
ssh-copy-id user@remote_host
```

Example:

```bash
ssh-copy-id john@192.168.1.100
```

Enter remote password on first connection.

- Test passwordless login

```bash
ssh user@remote_host
```

Example:

```bash
ssh john@192.168.1.100
```

If `ssh-copy-id` not available, copy manually:

```bash
cat ~/.ssh/id_ed25519.pub | ssh user@remote_host "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

- Configure sudoers for passwordless sudo

Edit sudoers:

```bash
sudo visudo
```

Add:

```text
username ALL=(ALL) NOPASSWD: ALL
```

Example:

```text
john ALL=(ALL) NOPASSWD: ALL
```

Test:

```bash
sudo -k
sudo ls /root
```

Recommended: use `/etc/sudoers.d/`:

```bash
echo 'john ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/john
sudo chmod 440 /etc/sudoers.d/john
```

Verify:

```bash
sudo visudo -c
```

This approach is cleaner than editing `/etc/sudoers` directly.

After this step, you can SSH into the system without password or sudo prompts.

- Copy project to remote

Assuming login as john to 192.168.0.100:

```bash
git clone git@github.com:ccbruce0812/nikko-vlm-webui.git
scp -r nikko-vlm-webui john@192.168.0.100:~/
```

All subsequent operations happen inside `nikko-vlm-webui` on the remote.

### 3. Disable GUI

Jetson Orin Nano boots into graphical desktop by default (graphical.target), consuming ~500MB RAM.
This platform is fully operated via WebUI; switching to text mode frees memory for containers.

WiFi is managed by NetworkManager: its systemd unit already has `WantedBy=multi-user.target`,
so WiFi auto-starts after switching targets — no extra config needed.

```bash
# Switch boot target to multi-user.target (disable GUI)
sudo systemctl set-default multi-user.target

# Verify NetworkManager is enabled under multi-user.target
sudo systemctl is-enabled NetworkManager
# Should return "enabled". If disabled/masked/static, enable manually:
sudo systemctl enable NetworkManager

# Ensure WiFi auto-connect is configured
nmcli dev wifi list                          # list available WiFi
sudo nmcli dev wifi connect "SSID" password "YOUR_PASSWORD"
# NetworkManager saves the connection; auto-reconnects on boot

# Reboot to verify
sudo reboot
# After boot, confirm: WiFi connected (ping external), docker available, RAM freed
```

> 📄 Script: `scripts/01-disable-gui.sh` (run: `bash scripts/01-disable-gui.sh`)

> **Verification checklist** (after reboot):
> ```bash
> systemctl get-default             # → multi-user.target
> nmcli -t -f ACTIVE,SSID dev wifi  # → should show yes:YOUR_SSID
> free -h                           # → available should be ~400-500MB higher
> ```

### 4. System Configuration

Jetson Orin Nano GPU uses CMA (Contiguous Memory Allocator) to dynamically allocate from system RAM.

**CSI Camera**: CAM0 with IMX219, configured via `jetson-io.py` for device tree overlay.
After setup, `/dev/video0` appears for rtsp-server to capture via nvarguscamerasrc.

**Super Mode**: Standard MAXN is only 15W. After flashing JetPack 6.1+ SD card image, delete
`/etc/nvpmodel.conf` and reboot. The system regenerates a config with **25W MAXN** —
NVIDIA's official "Super Mode" (1.7x AI performance boost).

Steps in order: CSI camera setup → Check/Enable Super Mode → MAXN (25W) → Lock clocks → Tune NVMap/kernel → Compact memory
Goal: **maximize GPU-available contiguous memory**.

```bash
# Check current status
echo "=== Current nvpmodel mode ==="
sudo nvpmodel -q
echo ""
echo "=== CSI camera status ==="
ls -la /dev/video* 2>/dev/null || echo "  No /dev/video* detected"
echo ""
echo "=== Current CMA / GPU available memory ==="
cat /proc/meminfo | grep -E "^Cma|^MemAvailable"
free -h

# Configure CSI camera (CAM0 / IMX219)
# If /dev/video0 missing, use jetson-io.py to set device tree overlay
if [ ! -e /dev/video0 ]; then
  echo "⚠ /dev/video0 not found"
  echo "→ sudo /opt/nvidia/jetson-io/jetson-io.py"
  echo "  Select Configure for compatible camera → IMX219 → Save and reboot"
fi

# Check Super Mode (25W) support
# If nvpmodel -q doesn't show 25W or MAXN Super, delete old config and reboot
sudo nvpmodel -q | grep -q "25W\|MAXN Super" || {
  echo "⚠ Currently only supports standard 15W MAXN"
  echo "→ sudo rm -rf /etc/nvpmodel.conf && sudo reboot"
  echo "  (Requires JetPack 6.1+ SD card image flashed; config regenerates after reboot)"
}

# Set MAXN Super Mode (25W)
sudo nvpmodel -m 2
echo "→ MAXN mode 2 (Super Mode 25W)"

# Lock max clocks (CPU + GPU + EMC)
sudo jetson_clocks
echo "→ clocks locked"

# Tune NVMap / kernel params (increase CMA allocatable space)
# Lower swap tendency: prevent GPU data from being swapped to eMMC
sudo sysctl -w vm.swappiness=10
# Higher cache reclaim pressure: free dentry/inode cache for CMA
sudo sysctl -w vm.vfs_cache_pressure=200
# Higher vm.min_free_kbytes: reserve more contiguous free pages for CMA
sudo sysctl -w vm.min_free_kbytes=65536
# Set NVMap external pool size: limit GPU userspace memory pool
# (Not available on Orin Nano, failure is expected)
sudo sh -c 'echo 1024 > /sys/kernel/debug/tegra_nvmap/ext_pool_size' 2>/dev/null || true

# Compact memory (maximize CMA contiguous blocks)
sudo sync
sudo sysctl -w vm.drop_caches=3
sudo sysctl -w vm.compact_memory=1

# Verify
echo ""
echo "=== CMA / GPU available memory after tuning ==="
cat /proc/meminfo | grep -E "^Cma|^MemAvailable"
free -h
echo ""
echo "nvpmodel mode: $(sudo nvpmodel -q | grep 'NV Power Mode')"
```

> 📄 Script: `scripts/02-system-config.sh` (run: `bash scripts/02-system-config.sh`)

### 5. Install Basic Packages

```bash
# Docker should be pre-installed (JetPack 6.x)
# Verify nvidia-container-runtime
sudo docker info | grep Runtime

# Install python3-venv (required by model download script)
sudo apt-get install -y python3-venv
```

> 📄 Script: `scripts/03-install-deps.sh` (run: `bash scripts/03-install-deps.sh`)

## Model Download

Use `scripts/04-download-models.sh` for one-click download, or follow manual steps below:

### 1. Create venv and install dependencies

```bash
python3 -m venv /tmp/model-dl-venv
source /tmp/model-dl-venv/bin/activate
pip install huggingface_hub ultralytics onnx
```

### 2. Reason2 (IQ4_XS)

```bash
mkdir -p models/reason2
cd models/reason2

# LLM (IQ4_XS, ~970MB)
hf download mradermacher/Cosmos-Reason2-2B-heretic-GGUF \
    Cosmos-Reason2-2B-heretic.IQ4_XS.gguf --local-dir .

# mmproj (F16, ~782MB)
hf download apolo13x/Cosmos-Reason2-2B-GGUF \
    mmproj-Cosmos-Reason2-2B-F16.gguf --local-dir .

cd ../..
```

### 3. moondream2 (q4_k)

```bash
mkdir -p models/moondream2
cd models/moondream2

hf download salivosa/moondream2-gguf \
    moondream2-q4_k.gguf moondream2-mmproj-f16.gguf --local-dir .

cd ../..
```

### 4. YOLO (TensorRT)

Requires Jetson GPU. Export with `quantize=16` (FP16).

```bash
mkdir -p models/yolo
cd models/yolo

# Download YOLOv8n PyTorch model (~6.5MB)
python3 -c "
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
import shutil
shutil.move('yolov8n.pt', '.')
print('Downloaded yolov8n.pt')
"

# Export TensorRT engine (FP16, ~13MB)
python3 -c "
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
model.export(format='engine', device=0, quantize=16, imgsz=640)
import shutil
shutil.move('yolov8n.engine', '.')
print('TensorRT engine exported')
"

cd ../..
```

### 5. Clean up venv

```bash
deactivate
rm -rf /tmp/model-dl-venv
```

> 📄 Script: `scripts/04-download-models.sh` (run: `bash scripts/04-download-models.sh`)

## Build Containers

### 1. Build Instructions

Model containers include Dockerfile, docker-compose.yml, and download script. Utility containers have only Dockerfile.

```bash
# Run from nikko-vlm-webui root

# Pull base image (L4T PyTorch)
sudo docker pull dustynv/l4t-pytorch:r36.4.0

# Router (API gateway, dynamic model detection, ~168MB)
sudo docker build -t router router/

# WebUI (official live-vlm-webui + GPU fix + API defaults, ~1.5GB)
sudo docker build -t live-vlm-webui live-vlm-webui/

# Reason2 (llama-server pre-built binaries, ~2GB)
sudo docker build -t reason2 -f reason2/Dockerfile .

# moondream2 (llama-server pre-built binaries, ~2GB)
sudo docker build -t moondream2 -f moondream2/Dockerfile .

# YOLO (PyTorch + ultralytics + TensorRT, ~13GB)
sudo docker build -t yolo yolo/

# RTSP Server (CSI camera streaming, optional, ~2GB)
sudo docker build -t rtsp-server rtsp-server/
```

> 📄 Script: `scripts/05-build-all.sh` (run: `bash scripts/05-build-all.sh`)

### 2. Image ↔ Container Mapping

| Image | Container | Port | Purpose |
|-------|-----------|------|---------|
| `router` | `router` | 8080 | API gateway, dynamic model detection |
| `moondream2` | `moondream2` | 8001 | moondream2 GGUF inference |
| `reason2` | `reason2` | 8002 | Reason2 GGUF inference |
| `yolo` | `yolo` | 8003 | YOLO TensorRT object detection |
| `live-vlm-webui` | `live-vlm-webui` | 8090 | Web frontend, WebRTC camera |
| `rtsp-server` | `rtsp-server` | 8554 | CSI camera RTSP stream (IMX219 / CAM0) |

## Start Services

### 1. docker-compose

Three stacks, start/stop from their respective directories:

```bash
# Run from nikko-vlm-webui root

# Reason2 stack
(cd reason2 && sudo docker compose up -d)      # start
(cd reason2 && sudo docker compose down)       # stop

# or moondream2 stack
(cd moondream2 && sudo docker compose up -d)   # start
(cd moondream2 && sudo docker compose down)    # stop

# or YOLO stack
(cd yolo && sudo docker compose up -d)         # start
(cd yolo && sudo docker compose down)          # stop
```

> 📄 Start: `scripts/06-start-reason2.sh` / `08-start-moondream2.sh` / `10-start-yolo.sh`
> 📄 Stop: `scripts/07-stop-reason2.sh` / `09-stop-moondream2.sh` / `11-stop-yolo.sh`

### 2. Manual docker run (Recommended — Interactive Script)

**Do NOT run multiple models simultaneously** (shared CMA memory; Orin Nano has only 7.4GB RAM).
The script prompts you to pick one model and optionally start RTSP Server.

```bash
bash scripts/12-start-manual.sh
```

Script flow:
1. Auto-starts Router + WebUI (required infrastructure)
2. Interactive model selection (Reason2 / moondream2 / YOLO — pick one)
3. Ask whether to start RTSP Server (CSI camera streaming, optional)

For individual manual control, reference commands below:

```bash
# Create shared network (once)
sudo docker network create vlm-net

# Router (required)
sudo docker run -d --name router --network vlm-net -p 8080:8080 router

# Pick one model (do NOT start multiple):
# Reason2 (~2.6GB GPU)
sudo docker run -d --name reason2 --runtime nvidia --network vlm-net \
    -v "$(pwd)/models/reason2:/model:ro" reason2

# moondream2 (~2.6GB GPU)
sudo docker run -d --name moondream2 --runtime nvidia --network vlm-net \
    -v "$(pwd)/models/moondream2:/model:ro" moondream2

# YOLO (~1.5GB GPU)
sudo docker run -d --name yolo --runtime nvidia --network vlm-net \
    -v "$(pwd)/models/yolo:/model:ro" yolo

# WebUI (required, host network)
sudo docker run -d --name live-vlm-webui --network host --runtime nvidia --privileged \
    -v /sys:/sys:ro -v /run/jtop.sock:/run/jtop.sock:ro live-vlm-webui

# RTSP Server (optional, CSI camera streaming)
sudo docker run -d --name rtsp-server --runtime nvidia --network host \
    --device=/dev/video0 --device=/dev/media0 \
    -v /tmp:/tmp \
    -e WIDTH=1280 -e HEIGHT=720 -e FPS=30 rtsp-server
```

> 📄 Script: `scripts/12-start-manual.sh` (run: `bash scripts/12-start-manual.sh`)
> 📄 Stop all: `scripts/13-stop-manual.sh`

## Manual Testing

All tests go through Router (port 8080). The only per-model difference is the `"model"` field.

### 1. Prepare Test Image (base64 encode)

```bash
# Generate test image with PIL or encode existing image
python3 -c "
import base64
with open('test.jpg', 'rb') as f:
    print(base64.b64encode(f.read()).decode())
" > /tmp/test_b64.txt
B64=$(cat /tmp/test_b64.txt)
```

### 2. Reason2 (image description)

```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"reason2\",
    \"messages\": [{\"role\":\"user\",\"content\":[
      {\"type\":\"text\",\"text\":\"Describe this image in one sentence.\"},
      {\"type\":\"image_url\",\"image_url\":{\"url\":\"data:image/jpeg;base64,$B64\"}}
    ]}],
    \"max_tokens\": 100
  }" | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])"
```

### 3. moondream2 (image description)

```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"moondream2\",
    \"messages\": [{\"role\":\"user\",\"content\":[
      {\"type\":\"text\",\"text\":\"Describe this image in one sentence.\"},
      {\"type\":\"image_url\",\"image_url\":{\"url\":\"data:image/jpeg;base64,$B64\"}}
    ]}],
    \"max_tokens\": 100
  }" | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])"
```

### 4. YOLO (object detection)

```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"yolo\",
    \"messages\": [{\"role\":\"user\",\"content\":[
      {\"type\":\"text\",\"text\":\"Detect objects\"},
      {\"type\":\"image_url\",\"image_url\":{\"url\":\"data:image/jpeg;base64,$B64\"}}
    ]}],
    \"max_tokens\": 200
  }" | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])"
```

### 5. List Available Models

```bash
curl -s http://localhost:8080/v1/models | python3 -m json.tool
```

### 6. Quick Validation (using test/test_bus.jpg)

First checks `/v1/models` to see which models are running, then only tests available models.

```bash
# Query available models → test only running ones
python3 -c "
import base64, json, urllib.request, sys

# 1. Query which models are running
req = urllib.request.Request('http://localhost:8080/v1/models')
resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
running = [m['id'] for m in resp.get('data', [])]
print(f'Router reports models: {running}')

if not running:
    print('⚠ No models running')
    sys.exit(0)

# 2. Read test image
with open('test/test_bus.jpg', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()

# 3. Test only models reported by Router (in fixed order)
for model in ['reason2', 'moondream2', 'yolo']:
    if model not in running:
        print(f'⊘ {model}: not running, skipped')
        continue

    prompt = 'Describe this image in one sentence.' if model != 'yolo' else 'Detect objects'
    data = json.dumps({
        'model': model,
        'messages': [{'role':'user','content':[
            {'type':'text','text':prompt},
            {'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{b64}'}}
        ]}],
        'max_tokens': 100
    }).encode()

    req = urllib.request.Request('http://localhost:8080/v1/chat/completions',
        data=data, headers={'Content-Type':'application/json'})
    resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
    text = resp['choices'][0]['message']['content']
    print(f'✓ {model}: {text[:100]}')
"
```

> 📄 Script: `scripts/16-test-quick.sh` (run: `bash scripts/16-test-quick.sh`)

## Performance Data

| Metric | Reason2 IQ4_XS | moondream2 q4_k | YOLO |
|--------|----------------|-----------------|------|
| Model size | LLM 970MB + mmproj 782MB | LLM 877MB + mmproj 868MB | 6.5MB |
| Image size | ~2GB (pre-built binaries) | ~2GB (pre-built binaries) | 13.3GB |
| Build time | ~30 min (from source) | ~30 sec (binaries) | ~85 sec |
| Prompt speed | 72.9 tok/s | 299 tok/s | — |
| Generation speed | 19.5 tok/s | 22.7 tok/s | — |
| Chat Template | qwen3vl (native) | moondream2 custom Jinja | — |
| Purpose | VLM description | VLM description | Object detection |

## Memory Usage

| State | RAM Available | GPU Available |
|-------|--------------|---------------|
| Super Mode (25W) idle | 5.4 GiB | 5.4 GiB |
| Reason2 loaded | ~3.0 GiB | ~2.8 GiB |
| Reason2 + moondream2 together | ~1.5 GiB | ~0.5 GiB |

## Troubleshooting

### 1. reason2 fails to start: CUDA out of memory

- **When**: manually starting reason2 and yolo (or moondream2) simultaneously, not via docker-compose
- **Cause**: two models competing for GPU CMA memory; reason2 mmproj needs ~1.1GB
- **Fix**: stop other models, start reason2, then restore

```bash
sudo docker stop yolo
sudo docker start reason2
sleep 35
sudo docker start yolo
```

> 📄 Script: `scripts/17-troubleshoot-reason2-oom.sh`

### 1.1 Tuning Model Parameters (OOM or Performance)

All model parameters are pre-configured in Dockerfiles with Jetson Orin Nano optimized defaults. No changes normally needed.
To override, pass `-e` environment variables:

```bash
# Example: lower reason2 GPU layers to free memory
sudo docker run -d --name reason2 --runtime nvidia \
    -v "$(pwd)/models/reason2:/model:ro" \
    -e N_GPU_LAYERS=8 reason2

# Example: increase moondream2 ctx size for longer conversations
sudo docker run -d --name moondream2 --runtime nvidia \
    -v "$(pwd)/models/moondream2:/model:ro" \
    -e CTX_SIZE=2048 moondream2
```

| Container | Tunable Parameters (env vars) | Defaults |
|-----------|------------------------------|----------|
| reason2 | `N_GPU_LAYERS` `N_THREADS` `N_BATCH` `CTX_SIZE` `FLASH_ATTN` | 12 / 4 / 256 / 2048 / on |
| moondream2 | `N_GPU_LAYERS` `N_THREADS` `N_BATCH` `CTX_SIZE` `FLASH_ATTN` | 15 / 4 / 128 / 1024 / on |
| yolo | (no llama-server params) | — |

### 2. llama-server: libllama-server-impl.so not found

- **When**: only the `llama-server` binary was copied, not its dependent .so files
- **Cause**: llama-server dynamically links libllama-server-impl.so, libllama.so, etc.
- **Fix**: Dockerfile copies entire `build/bin/` directory and sets `LD_LIBRARY_PATH`

### 3. --flash-attn: unknown value

- **When**: using latest llama.cpp with bare `--flash-attn`
- **Cause**: newer llama.cpp requires explicit value `on|off|auto`
- **Fix**: use `--flash-attn on`

### 4. moondream2 returns blank

- **When**: calling moondream2 via OpenAI API format
- **Cause**: moondream2 is phi2 architecture; standard chat template is incompatible
- **Fix**: add custom `--chat-template`:

```
--chat-template "{% for message in messages %}{% if message['role'] == 'user' %}<image>\n\nQuestion: {% for part in message['content'] %}{% if part['type'] == 'text' %}{{ part['text'] }}{% endif %}{% endfor %}\n\nAnswer: {% else %}{{ message['content'] }}{% endif %}{% endfor %}"
```

### 5. WebUI GPU monitor always shows 0%

- **When**: using official live-vlm-webui image on Jetson
- **Cause**: Jetson uses shared memory; jtop returns GPU=0 in Docker containers
- **Fix**: built into `live-vlm-webui/Dockerfile` (patch_gpu_monitor.py)

### 6. WebUI camera not working

- **When**: WebUI using bridge network mode
- **Cause**: WebRTC needs direct UDP connection; Docker bridge NAT blocks it
- **Fix**: use `--network host` (already built into docker-compose.yml)

### 7. Disk space full

- **When**: too many Docker images accumulated
- **Cause**: base images + build cache consuming space
- **Fix**:

```bash
sudo docker system prune -af
```

> 📄 Script: `scripts/18-cleanup-disk.sh` (run: `bash scripts/18-cleanup-disk.sh`)

## File Structure

### Local / Remote (dev machine / Jetson, symmetric)

```
./
├── router/
│   ├── Dockerfile
│   └── router.py                 # dynamic model detection
├── reason2/
│   ├── Dockerfile                # llama-server from source
│   ├── docker-compose.yml        # reason2 + router + webui
│   └── download_model.sh         # IQ4_XS LLM + F16 mmproj
├── moondream2/
│   ├── Dockerfile                # llama-server pre-built binaries
│   ├── docker-compose.yml        # moondream2 + router + webui
│   └── download_model.sh         # q4_k LLM + f16 mmproj
├── yolo/
│   ├── Dockerfile                # PyTorch + ultralytics + TensorRT
│   ├── docker-compose.yml        # yolo + router + webui
│   ├── yolo_server.py            # OpenAI-compatible API server
│   └── download_model.sh         # YOLO → TensorRT engine export
├── live-vlm-webui/
│   ├── Dockerfile                # official live-vlm-webui + GPU fix + API defaults
│   └── patch_gpu_monitor.py      # Jetson GPU monitor fix
├── rtsp-server/
│   ├── Dockerfile                # GStreamer CSI RTSP server
│   └── gst_rtsp_server.py        # nvarguscamerasrc → nvvidconv → x264enc → RTSP
├── models/
│   ├── reason2/
│   ├── moondream2/
│   └── yolo/
├── test/
├── scripts/
│   ├── 01-disable-gui.sh               # disable GUI + WiFi auto-login
│   ├── 02-system-config.sh             # CSI camera + Super Mode 25W + NVMap + memory tuning
│   ├── 03-install-deps.sh              # install basic packages
│   ├── 04-download-models.sh           # download all models
│   ├── 05-build-all.sh                 # build all containers
│   ├── 06-start-reason2.sh             # start Reason2 stack
│   ├── 07-stop-reason2.sh              # stop Reason2
│   ├── 08-start-moondream2.sh          # start moondream2 stack
│   ├── 09-stop-moondream2.sh           # stop moondream2
│   ├── 10-start-yolo.sh                # start YOLO stack
│   ├── 11-stop-yolo.sh                 # stop YOLO
│   ├── 12-start-manual.sh              # interactive container launcher
│   ├── 13-stop-manual.sh               # stop all manually started containers
│   ├── 14-start-rtsp-server.sh         # start RTSP Server (CSI camera, optional)
│   ├── 15-stop-rtsp-server.sh          # stop RTSP Server
│   ├── 16-test-quick.sh                # quick model validation
│   ├── 17-troubleshoot-reason2-oom.sh  # Reason2 OOM fix
│   └── 18-cleanup-disk.sh              # Docker disk cleanup
├── readme.md
├── log.md
└── porting.md
```
