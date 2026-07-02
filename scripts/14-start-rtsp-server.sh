#!/usr/bin/env bash
# ============================================================
# 啟動 RTSP Server（選用 — CSI 攝影機即時串流）
# CAM0 / IMX219，影像大小由 WIDTH / HEIGHT 環境變數控制
# 對應 README.md → 啟動服務 → RTSP Server
# ============================================================
set -euo pipefail

echo "============================================"
echo " 啟動 RTSP Server（CSI CAM0 / IMX219）"
echo "============================================"

# 預設值
WIDTH="${WIDTH:-1280}"
HEIGHT="${HEIGHT:-720}"
FPS="${FPS:-30}"
RTSP_PORT="${RTSP_PORT:-8554}"

echo "  解析度: ${WIDTH}x${HEIGHT} @ ${FPS}fps"
echo "  RTSP:   rtsp://<jetson-ip>:${RTSP_PORT}/stream"

# 確認 CSI 相機存在
if [ ! -e /dev/video0 ]; then
    echo ""
    echo "⚠ /dev/video0 不存在！"
    echo "  請先執行：sudo /opt/nvidia/jetson-io/jetson-io.py"
    echo "  選擇「Configure for compatible camera」→ IMX219 → CAM0"
    echo "  設定完成後 reboot"
    exit 1
fi

echo ""
echo "=== 移除舊容器 ==="
sudo docker rm -f rtsp-server 2>/dev/null || true

echo ""
echo "=== 啟動 rtsp-server ==="
sudo docker run -d \
    --name rtsp-server \
    --runtime nvidia \
    --network host \
    --device=/dev/video0 \
    --device=/dev/media0 \
    -v /tmp:/tmp \
    -e WIDTH="$WIDTH" \
    -e HEIGHT="$HEIGHT" \
    -e FPS="$FPS" \
    -e RTSP_PORT="$RTSP_PORT" \
    rtsp-server

echo ""
echo "=== 等待攝影機就緒 ==="
sleep 3

# 確認容器運行
if sudo docker ps --format '{{.Names}}' | grep -q rtsp-server; then
    echo "✓ rtsp-server 已啟動"
    echo "  RTSP 串流位址: rtsp://$(hostname -I | awk '{print $1}'):${RTSP_PORT}/stream"
else
    echo "✗ rtsp-server 啟動失敗，查看日誌："
    sudo docker logs rtsp-server
    exit 1
fi
