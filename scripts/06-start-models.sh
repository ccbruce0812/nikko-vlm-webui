#!/usr/bin/env bash
# ============================================================
# 06-start-models.sh
# Interactive model launcher. Always starts Router.
# All VLM models use the llama-cpp image .
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ---- VLM defaults (llama-server params) ----
# reason2
R2_MODEL="Cosmos-Reason2-2B-heretic.IQ4_XS.gguf"
R2_MMPROJ="mmproj-Cosmos-Reason2-2B-F16.gguf"
R2_GPU_LAYERS=12; R2_THREADS=4; R2_BATCH=64; R2_UBATCH=32; R2_CTX=4096
R2_FLASH="on"; R2_PARALLEL=1
R2_URL="http://reason2:8002"
R2_CACHE_K="q4_0"; R2_CACHE_V="q4_0"; R2_NO_CACHE_IDLE="on"

# moondream2
MD_MODEL="moondream2-q4_k.gguf"
MD_MMPROJ="moondream2-mmproj-f16.gguf"
MD_GPU_LAYERS=15; MD_THREADS=4; MD_BATCH=64; MD_UBATCH=32; MD_CTX=2048
MD_FLASH="on"; MD_PARALLEL=1
MD_CHAT_TEMPLATE='{% for message in messages %}{% if message['\''role'\''] == '\''user'\'' %}<image>\n\n{{ message['\''content'\''] }}\n\n{% else %}{{ message['\''content'\''] }}{% endif %}{% endfor %}'

MD_URL="http://moondream2:8001"
MD_CACHE_K="q4_0"; MD_CACHE_V="q4_0"; MD_NO_CACHE_IDLE="on"

# yolo
YL_URL="http://yolo:8003"

# router
RTR_PORT=8080
RTR_CACHE_TTL=2
RTR_TIMEOUT=120
RTR_CONNECT_TIMEOUT=5


# ---- Power mode ----
echo "=== Power mode ==="
if ! sudo nvpmodel -q 2>/dev/null | grep -qE "25W|MAXN"; then
    echo "→ Setting mode 2 (MAXN_SUPER 25W)"
    sudo nvpmodel -m 2
else
    echo "✓ MAXN_SUPER (25W)"
fi
sudo jetson_clocks
echo "✓ jetson_clocks"

# ---- nvargus-daemon ----
echo ""
echo "=== nvargus-daemon ==="
sudo systemctl restart nvargus-daemon
sleep 2
echo "✓ restarted"

# ---- Memory tuning ----
echo ""
echo "=== Memory tuning ==="
sudo sysctl -w vm.swappiness=10
sudo sysctl -w vm.vfs_cache_pressure=200
sudo sysctl -w vm.min_free_kbytes=65536
sudo sync
sudo sysctl -w vm.drop_caches=3
sudo sysctl -w vm.compact_memory=1
echo "✓ cache dropped + memory compacted"

# ---- Clear old model containers ----
echo ""
echo "=== Clearing old containers ==="
for c in reason2 moondream2 yolo; do
    if sudo docker ps -a --format '{{.Names}}' | grep -q "^${c}$"; then
        echo "→ Removing ${c}..."
        sudo docker rm -f "$c" 2>/dev/null || true
    fi
done
echo "✓ old containers cleared"

# ---- Interactive model selection ----
echo ""
echo "============================================"
echo " Select Model"
echo "============================================"
echo "  1) reason2          "
echo "  2) moondream2       "
echo "  3) yolo             "
echo "  4) reason2 + yolo"
echo "  5) moondream2 + yolo"
echo "  q) Router only"
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

# ---- Model parameter overrides ----
if $START_REASON2; then
    echo ""
    echo "=== reason2 parameters (Enter to keep default, empty=skip flag) ==="
    read -p "  MODEL        [${R2_MODEL}]: " v; R2_MODEL="${v:-$R2_MODEL}"
    read -p "  MMPROJ       [${R2_MMPROJ}]: " v; R2_MMPROJ="${v:-$R2_MMPROJ}"
    read -p "  N_GPU_LAYERS [${R2_GPU_LAYERS}]: " v; R2_GPU_LAYERS="${v:-$R2_GPU_LAYERS}"
    read -p "  N_THREADS    [${R2_THREADS}]: " v; R2_THREADS="${v:-$R2_THREADS}"
    read -p "  N_BATCH      [${R2_BATCH}]: " v; R2_BATCH="${v:-$R2_BATCH}"
    read -p "  UBATCH_SIZE  [${R2_UBATCH}]: " v; R2_UBATCH="${v:-$R2_UBATCH}"
    read -p "  CTX_SIZE     [${R2_CTX}]: " v; R2_CTX="${v:-$R2_CTX}"
    read -p "  FLASH_ATTN   [${R2_FLASH}]: " v; R2_FLASH="${v}"
    read -p "  N_PARALLEL   [${R2_PARALLEL}]: " v; R2_PARALLEL="${v:-$R2_PARALLEL}"
    read -p "  URL          [${R2_URL}]: " v; R2_URL="${v:-$R2_URL}"
    read -p "  CACHE_K      [${R2_CACHE_K}]: " v; R2_CACHE_K="${v:-$R2_CACHE_K}"
    read -p "  CACHE_V      [${R2_CACHE_V}]: " v; R2_CACHE_V="${v:-$R2_CACHE_V}"
    read -p "  NO_CACHE_IDLE [${R2_NO_CACHE_IDLE}]: " v; R2_NO_CACHE_IDLE="${v}"
fi

if $START_MOONDREAM2; then
    echo ""
    echo "=== moondream2 parameters (Enter to keep default, empty=skip flag) ==="
    read -p "  MODEL        [${MD_MODEL}]: " v; MD_MODEL="${v:-$MD_MODEL}"
    read -p "  MMPROJ       [${MD_MMPROJ}]: " v; MD_MMPROJ="${v:-$MD_MMPROJ}"
    read -p "  N_GPU_LAYERS [${MD_GPU_LAYERS}]: " v; MD_GPU_LAYERS="${v:-$MD_GPU_LAYERS}"
    read -p "  N_THREADS    [${MD_THREADS}]: " v; MD_THREADS="${v:-$MD_THREADS}"
    read -p "  N_BATCH      [${MD_BATCH}]: " v; MD_BATCH="${v:-$MD_BATCH}"
    read -p "  UBATCH_SIZE  [${MD_UBATCH}]: " v; MD_UBATCH="${v:-$MD_UBATCH}"
    read -p "  CTX_SIZE     [${MD_CTX}]: " v; MD_CTX="${v:-$MD_CTX}"
    read -p "  FLASH_ATTN   [${MD_FLASH}]: " v; MD_FLASH="${v:-$MD_FLASH}"
    read -p "  CHAT_TEMPLATE [${MD_CHAT_TEMPLATE:-none}]: " v; MD_CHAT_TEMPLATE="${v:-$MD_CHAT_TEMPLATE}"
    read -p "  N_PARALLEL   [${MD_PARALLEL}]: " v; MD_PARALLEL="${v:-$MD_PARALLEL}"
    read -p "  URL          [${MD_URL}]: " v; MD_URL="${v:-$MD_URL}"
    read -p "  CACHE_K      [${MD_CACHE_K}]: " v; MD_CACHE_K="${v:-$MD_CACHE_K}"
    read -p "  CACHE_V      [${MD_CACHE_V}]: " v; MD_CACHE_V="${v:-$MD_CACHE_V}"
    read -p "  NO_CACHE_IDLE [${MD_NO_CACHE_IDLE}]: " v; MD_NO_CACHE_IDLE="${v:-$MD_NO_CACHE_IDLE}"
fi

if $START_YOLO; then
    echo ""
    echo "=== yolo parameters (Enter to keep default) ==="
    read -p "  URL [${YL_URL}]: " v; YL_URL="${v:-$YL_URL}"
fi

# ---- Router parameter overrides ----
echo ""
echo "=== router parameters (Enter to keep default) ==="
read -p "  PORT           [${RTR_PORT}]: " v; RTR_PORT="${v:-$RTR_PORT}"
read -p "  CACHE_TTL      [${RTR_CACHE_TTL}]: " v; RTR_CACHE_TTL="${v:-$RTR_CACHE_TTL}"
read -p "  TIMEOUT        [${RTR_TIMEOUT}]: " v; RTR_TIMEOUT="${v:-$RTR_TIMEOUT}"
read -p "  CONNECT_TIMEOUT [${RTR_CONNECT_TIMEOUT}]: " v; RTR_CONNECT_TIMEOUT="${v:-$RTR_CONNECT_TIMEOUT}"

# ---- Create network + start Router ----
echo ""
echo "=== Network + Router ==="
sudo docker network create vlm-net 2>/dev/null || echo "  vlm-net already exists"

sudo docker rm -f router 2>/dev/null || true
sudo docker run -d --name router --network vlm-net -p "${RTR_PORT}:${RTR_PORT}" \
    router \
    python3 router.py \
        --port "${RTR_PORT}" \
        --moondream2-url "${MD_URL}" \
        --reason2-url "${R2_URL}" \
        --yolo-url "${YL_URL}" \
        --cache-ttl "${RTR_CACHE_TTL}" \
        --timeout "${RTR_TIMEOUT}" \
        --connect-timeout "${RTR_CONNECT_TIMEOUT}"
echo "  ✓ router :${RTR_PORT}"

# ---- Start models ----
if $START_REASON2; then
    echo ""
    echo "=== Starting reason2  ==="
    sudo docker run -d --name reason2 --runtime nvidia --network vlm-net \
        -v "${PROJECT_DIR}/models/reason2:/model:ro" \
        llama-cpp \
        llama-server \
	    --cache-ram 0 --no-cache-idle-slots \
            -m "/model/${R2_MODEL}" \
            --mmproj "/model/${R2_MMPROJ}" \
            --host 0.0.0.0 --port "${R2_URL##*:}" \
            --n-gpu-layers "${R2_GPU_LAYERS}" \
            --threads "${R2_THREADS}" \
            --batch-size "${R2_BATCH}" \
            --ubatch-size "${R2_UBATCH}" \
            --ctx-size "${R2_CTX}" \
            ${R2_FLASH:+--flash-attn ${R2_FLASH}} \
            --parallel "${R2_PARALLEL}" \
            ${R2_NO_CACHE_IDLE:+--no-cache-idle-slots} \
            --cache-type-k "${R2_CACHE_K}" --cache-type-v "${R2_CACHE_V}"
    echo "  ✓ reason2 started"
fi

if $START_MOONDREAM2; then
    echo ""
    echo "=== Starting moondream2  ==="
    sudo docker run -d --name moondream2 --runtime nvidia --network vlm-net \
        -v "${PROJECT_DIR}/models/moondream2:/model:ro" \
        llama-cpp \
        llama-server \
	    --cache-ram 0 --no-cache-idle-slots \
            -m "/model/${MD_MODEL}" \
            --mmproj "/model/${MD_MMPROJ}" \
            ${MD_CHAT_TEMPLATE:+--chat-template "${MD_CHAT_TEMPLATE}"} \
            --host 0.0.0.0 --port "${MD_URL##*:}" \
            --n-gpu-layers "${MD_GPU_LAYERS}" \
            --threads "${MD_THREADS}" \
            --batch-size "${MD_BATCH}" \
            --ubatch-size "${MD_UBATCH}" \
            --ctx-size "${MD_CTX}" \
            ${MD_FLASH:+--flash-attn ${MD_FLASH}} \
            --parallel "${MD_PARALLEL}" \
            ${MD_NO_CACHE_IDLE:+--no-cache-idle-slots} \
            --cache-type-k "${MD_CACHE_K}" --cache-type-v "${MD_CACHE_V}"
    echo "  ✓ moondream2 started"
fi

if $START_YOLO; then
    echo ""
    echo "=== Starting yolo ==="
    sudo docker run -d --name yolo --runtime nvidia --network vlm-net \
        -v "${PROJECT_DIR}/models/yolo:/model:ro" \
        yolo \
        python3 server.py \
            --port "${YL_URL##*:}"
    echo "  ✓ yolo started"
fi

# ---- Poll for models ----
echo ""
echo "=== Waiting for models to load ==="
EXPECTED=0
if $START_REASON2 || $START_MOONDREAM2; then EXPECTED=$((EXPECTED + 1)); fi
if $START_YOLO; then EXPECTED=$((EXPECTED + 1)); fi
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
    echo "  reason2:    MODEL=$R2_MODEL MMPROJ=$R2_MMPROJ GPU=$R2_GPU_LAYERS THREADS=$R2_THREADS BATCH=$R2_BATCH UBATCH=$R2_UBATCH CTX=$R2_CTX FLASH=${R2_FLASH:-off} PARALLEL=$R2_PARALLEL URL=$R2_URL CACHE_K=$R2_CACHE_K CACHE_V=$R2_CACHE_V NO_CACHE_IDLE=${R2_NO_CACHE_IDLE:-off}"
fi
if $START_MOONDREAM2; then
    echo "  moondream2: MODEL=$MD_MODEL MMPROJ=$MD_MMPROJ GPU=$MD_GPU_LAYERS THREADS=$MD_THREADS BATCH=$MD_BATCH UBATCH=$MD_UBATCH CTX=$MD_CTX FLASH=${MD_FLASH:-off} CHAT_TEMPLATE=${MD_CHAT_TEMPLATE:-none} PARALLEL=$MD_PARALLEL URL=$MD_URL CACHE_K=$MD_CACHE_K CACHE_V=$MD_CACHE_V NO_CACHE_IDLE=${MD_NO_CACHE_IDLE:-off}"
fi
if $START_YOLO; then
    echo "  yolo:       PyTorch + ultralytics (url $YL_URL)"
fi

echo ""
echo "✓ Done. Models available at:"
curl -s http://localhost:8080/v1/models 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  (router unreachable)"
