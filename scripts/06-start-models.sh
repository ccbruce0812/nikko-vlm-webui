#!/usr/bin/env bash
# ============================================================
# 06-start-models.sh
# Interactive model launcher — picks one model, always starts Router.
# Reason2 and moondream2 are mutually exclusive. YOLO can run solo
# or paired with a VLM. WebUI and RTSP are started separately.
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ---- Defaults (from Dockerfiles) ----
# reason2
R2_GPU_LAYERS=12; R2_THREADS=4; R2_BATCH=256; R2_CTX=2048; R2_FLASH=on; R2_PORT=8002
# moondream2
MD_GPU_LAYERS=15; MD_THREADS=4; MD_BATCH=128; MD_CTX=1024; MD_FLASH=on; MD_PORT=8001
# yolo
YL_PORT=8003

usage() {
    echo "Usage: bash scripts/06-start-models.sh"
    echo ""
    echo "  Interactive model launcher."
    echo "  Always starts Router. Pick one VLM (reason2/moondream2),"
    echo "  YOLO, or a combo."
    exit 0
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
fi

# ---- 1. Power mode ----
echo "=== Power mode ==="
if ! sudo nvpmodel -q 2>/dev/null | grep -q "NV Power Mode: MAXN_SUPER"; then
    echo "→ Setting mode 2 (MAXN_SUPER 25W)"
    sudo nvpmodel -m 2
else
    echo "✓ MAXN_SUPER (25W)"
fi
sudo jetson_clocks
echo "✓ jetson_clocks"

# ---- 2. nvargus-daemon ----
echo ""
echo "=== nvargus-daemon ==="
sudo systemctl restart nvargus-daemon
sleep 2
echo "✓ restarted"

# ---- 3. Memory tuning ----
echo ""
echo "=== Memory tuning ==="
sudo sysctl -w vm.swappiness=10
sudo sysctl -w vm.vfs_cache_pressure=200
sudo sysctl -w vm.min_free_kbytes=65536
sudo sync
sudo sysctl -w vm.drop_caches=3
sudo sysctl -w vm.compact_memory=1
echo "✓ cache dropped + memory compacted"

# ---- 4. Clear old model containers ----
echo ""
echo "=== Clearing old containers ==="
for c in reason2 moondream2 yolo; do
    if sudo docker ps -a --format '{{.Names}}' | grep -q "^${c}$"; then
        echo "→ Removing ${c}..."
        sudo docker rm -f "$c" 2>/dev/null || true
    fi
done
echo "✓ old containers cleared"

# ---- 5. Interactive model selection ----
echo ""
echo "============================================"
echo " Select Model"
echo "============================================"
echo "  1) Reason2          (~2.6GB)"
echo "  2) moondream2       (~2.6GB)"
echo "  3) YOLO             (~1.5GB)"
echo "  4) Reason2 + YOLO"
echo "  5) moondream2 + YOLO"
echo "  q) Router only (no model)"
echo ""
read -p "  Choose [1/2/3/4/5/q]: " choice

START_REASON2=false
START_MOONDREAM2=false
START_YOLO=false

case "$choice" in
    1) START_REASON2=true ;;
    2) START_MOONDREAM2=true ;;
    3) START_YOLO=true ;;
    4) START_REASON2=true; START_YOLO=true ;;
    5) START_MOONDREAM2=true; START_YOLO=true ;;
    *) echo "→ Router only" ;;
esac

# ---- 6. Model parameter overrides (VLM only) ----
if $START_REASON2; then
    echo ""
    echo "=== Reason2 parameters (Enter to keep default) ==="
    read -p "  N_GPU_LAYERS [${R2_GPU_LAYERS}]: " v; R2_GPU_LAYERS="${v:-$R2_GPU_LAYERS}"
    read -p "  N_THREADS     [${R2_THREADS}]: " v; R2_THREADS="${v:-$R2_THREADS}"
    read -p "  N_BATCH      [${R2_BATCH}]: " v; R2_BATCH="${v:-$R2_BATCH}"
    read -p "  CTX_SIZE    [${R2_CTX}]: " v; R2_CTX="${v:-$R2_CTX}"
    read -p "  FLASH_ATTN   [${R2_FLASH}]: " v; R2_FLASH="${v:-$R2_FLASH}"
fi

if $START_MOONDREAM2; then
    echo ""
    echo "=== moondream2 parameters (Enter to keep default) ==="
    read -p "  N_GPU_LAYERS [${MD_GPU_LAYERS}]: " v; MD_GPU_LAYERS="${v:-$MD_GPU_LAYERS}"
    read -p "  N_THREADS     [${MD_THREADS}]: " v; MD_THREADS="${v:-$MD_THREADS}"
    read -p "  N_BATCH      [${MD_BATCH}]: " v; MD_BATCH="${v:-$MD_BATCH}"
    read -p "  CTX_SIZE    [${MD_CTX}]: " v; MD_CTX="${v:-$MD_CTX}"
    read -p "  FLASH_ATTN   [${MD_FLASH}]: " v; MD_FLASH="${v:-$MD_FLASH}"
fi

# ---- 7. Create network + start Router ----
echo ""
echo "=== Network + Router ==="
sudo docker network create vlm-net 2>/dev/null || echo "  vlm-net already exists"

sudo docker rm -f router 2>/dev/null || true
sudo docker run -d --name router --network vlm-net -p 8080:8080 router
echo "  ✓ router :8080"

# ---- 8. Start models ----
if $START_REASON2; then
    echo ""
    echo "=== Starting Reason2 ==="
    sudo docker run -d --name reason2 --runtime nvidia --network vlm-net \
        -v "${PROJECT_DIR}/models/reason2:/model:ro" \
        -e N_GPU_LAYERS="$R2_GPU_LAYERS" \
        -e N_THREADS="$R2_THREADS" \
        -e N_BATCH="$R2_BATCH" \
        -e CTX_SIZE="$R2_CTX" \
        -e FLASH_ATTN="$R2_FLASH" \
        reason2
    echo "  ✓ reason2 started (loading ~35s)"
fi

if $START_MOONDREAM2; then
    echo ""
    echo "=== Starting moondream2 ==="
    sudo docker run -d --name moondream2 --runtime nvidia --network vlm-net \
        -v "${PROJECT_DIR}/models/moondream2:/model:ro" \
        -e N_GPU_LAYERS="$MD_GPU_LAYERS" \
        -e N_THREADS="$MD_THREADS" \
        -e N_BATCH="$MD_BATCH" \
        -e CTX_SIZE="$MD_CTX" \
        -e FLASH_ATTN="$MD_FLASH" \
        moondream2
    echo "  ✓ moondream2 started (loading ~30s)"
fi

if $START_YOLO; then
    echo ""
    echo "=== Starting YOLO ==="
    sudo docker run -d --name yolo --runtime nvidia --network vlm-net \
        -v "${PROJECT_DIR}/models/yolo:/model:ro" \
        yolo
    echo "  ✓ yolo started (loading ~15s)"
fi

# ---- 9. Poll for models ----
echo ""
echo "=== Waiting for models to load ==="
EXPECTED=0
if $START_REASON2 || $START_MOONDREAM2; then EXPECTED=$((EXPECTED + 1)); fi
if $START_YOLO; then EXPECTED=$((EXPECTED + 1)); fi
# Always expect at least 1 (router is queryable immediately, models take time)
TIMEOUT=180
INTERVAL=3
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    COUNT=$(curl -s http://localhost:8080/v1/models 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('data',[])))" 2>/dev/null || echo 0)
    if [ "$COUNT" -ge "$EXPECTED" ] && [ "$COUNT" -gt 0 ]; then
        echo "  ✓ $COUNT model(s) ready (${ELAPSED}s)"
        break
    fi
    echo -n "."
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done
echo ""
echo ""
echo "============================================"
echo " Container Status"
echo "============================================"
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "=== Model parameters ==="
if $START_REASON2; then
    echo "  reason2:  GPU=$R2_GPU_LAYERS THREADS=$R2_THREADS BATCH=$R2_BATCH CTX=$R2_CTX FLASH=$R2_FLASH"
fi
if $START_MOONDREAM2; then
    echo "  moondream2: GPU=$MD_GPU_LAYERS THREADS=$MD_THREADS BATCH=$MD_BATCH CTX=$MD_CTX FLASH=$MD_FLASH"
fi
if $START_YOLO; then
    echo "  yolo:      PyTorch + ultralytics (no llama params)"
fi

echo ""
echo "✓ Done. Models available at:"
curl -s http://localhost:8080/v1/models 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  (router unreachable)"
