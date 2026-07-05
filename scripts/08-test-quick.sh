#!/usr/bin/env bash
# ============================================================
# Quick validation: test running models with test/test_bus.jpg
# Reference: README.md → Manual Testing → 6. Quick Validation
# ============================================================
set -euo pipefail

echo "=== Detecting running models ==="
python3 -c "
import base64, json, urllib.request, sys, os

# 1. Query which models are running
req = urllib.request.Request('http://localhost:8080/v1/models')
try:
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    running = [m['id'] for m in resp.get('data', [])]
    print(f'Router reports models: {running}')
except Exception as e:
    print(f'⚠ Router unreachable: {e}')
    sys.exit(1)

if not running:
    print('⚠ No models running. Start a model first (e.g., bash scripts/06-start-models.sh)')
    sys.exit(0)

# 2. Read test image
test_img = 'test/test_bus.jpg'
if not os.path.exists(test_img):
    print(f'⚠ Test image not found: {test_img}')
    sys.exit(1)
with open(test_img, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()

# 3. Test each model in fixed order (skip if not running)
for model in ['reason2', 'moondream2', 'yolo']:
    if model not in running:
        print(f'\n=== {model} ===')
        print(f'  ⊘ not running, skipped')
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
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
        text = resp['choices'][0]['message']['content']
        print(f'\n=== {model} ===')
        print(f'  ✓ {text[:200]}')
    except Exception as e:
        print(f'\n=== {model} ===')
        print(f'  ✗ Error: {e}')

print('\n=== Done ===')
"
