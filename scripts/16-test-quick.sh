#!/usr/bin/env bash
# ============================================================
# 快速驗證：用 test/test_bus.jpg 測試所有運行中的模型
# 對應 README.md → 手動測試 → 快速驗證
# 前提：Router 已啟動在 localhost:8080
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TEST_IMG="$PROJECT_DIR/test/test_bus.jpg"

if [ ! -f "$TEST_IMG" ]; then
    echo "❌ 找不到測試圖：$TEST_IMG"
    exit 1
fi

echo "=== 快速驗證模型 ==="

python3 -c "
import base64, json, urllib.request, sys

# 1. 查詢目前有哪些模型在運行
try:
    req = urllib.request.Request('http://localhost:8080/v1/models')
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    running = [m['id'] for m in resp.get('data', [])]
    print(f'Router 回報模型: {running}')
except Exception as e:
    print(f'❌ 無法連線 Router: {e}')
    sys.exit(1)

if not running:
    print('⚠ 沒有任何模型在運行，請先啟動至少一個模型')
    sys.exit(0)

# 2. 讀取測試圖片
with open('$TEST_IMG', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()

# 3. 只測試 Router 回報的模型（照固定順序）
ALL_MODELS = ['reason2', 'moondream2', 'yolo']
for model in ALL_MODELS:
    if model not in running:
        print(f'⊘ {model}: 未運行，跳過')
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

    try:
        req = urllib.request.Request('http://localhost:8080/v1/chat/completions',
            data=data, headers={'Content-Type':'application/json'})
        resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
        text = resp['choices'][0]['message']['content']
        print(f'✓ {model}: {text[:100]}')
    except Exception as e:
        print(f'✗ {model}: ERROR - {e}')
"
