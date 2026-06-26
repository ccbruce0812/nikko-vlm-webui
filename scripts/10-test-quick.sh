#!/usr/bin/env bash
# ============================================================
# 快速驗證：產生單色測試圖並一次測試三個模型
# 對應 README.md → 手動測試 → 快速驗證
# 前提：Router 已啟動在 localhost:8080
# ============================================================
set -euo pipefail

echo "=== 快速驗證三個模型 ==="
echo "（確保 Router 已在 localhost:8080 執行）"
echo ""

python3 -c "
import base64, json, urllib.request
from PIL import Image
import io

for color, model in [('blue','cosmos-reason2-2b'),('red','moondream2'),('white','yolo')]:
    img = Image.new('RGB', (640,480), color=color)
    buf = io.BytesIO(); img.save(buf, format='JPEG')
    b64 = base64.b64encode(buf.getvalue()).decode()
    
    prompt = 'Describe this image.' if model != 'yolo' else 'Detect objects'
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
        resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
        text = resp['choices'][0]['message']['content']
        print(f'{model} ({color}): {text[:80]}')
    except Exception as e:
        print(f'{model} ({color}): ERROR - {e}')
"
