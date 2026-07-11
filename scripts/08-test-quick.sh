#!/usr/bin/env bash
# ============================================================
# Quick validation: test running models with 20 test images
# ============================================================
set -euo pipefail

echo "=== Detecting running models ==="
python3 << 'PYEOF'
import base64, json, urllib.request, sys, os, glob, time

# 1. Query which models are running
try:
    resp = json.loads(urllib.request.urlopen(
        urllib.request.Request("http://localhost:8080/v1/models"), timeout=10).read())
    running = [m["id"] for m in resp.get("data", [])]
    print(f"Router reports models: {running}")
except Exception as e:
    print(f"⚠  Router unreachable: {e}")
    sys.exit(1)

if not running:
    print("⚠  No models running. Start a model first (e.g., bash scripts/06-start-models.sh)")
    sys.exit(0)

# 2. Find test images
imgs = sorted(glob.glob("test/test_*.jpg"))
if not imgs:
    print("⚠  No test_*.jpg images found in test/")
    sys.exit(1)
print(f"Testing {len(imgs)} images...")

# 3. Load all images once
img_data = {}
for p in imgs:
    with open(p, "rb") as f:
        img_data[os.path.basename(p)] = base64.b64encode(f.read()).decode()

# 4. Test each model
for model in ["reason2", "moondream2", "yolo"]:
    if model not in running:
        print(f"\n=== {model}: not running, skipped ===")
        continue

    print(f"\n=== {model} ({len(imgs)} images) ===")
    prompt = "Describe this image in one sentence." if model != "yolo" else "Detect objects"
    success, empty, error = 0, 0, 0

    for name in sorted(img_data.keys()):
        data = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_data[name]}"}},
                {"type": "text", "text": prompt},
            ]}],
            "max_tokens": 100,
        }).encode()

        try:
            req = urllib.request.Request("http://localhost:8080/v1/chat/completions",
                data=data, headers={"Content-Type": "application/json"})
            resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
            text = resp["choices"][0]["message"]["content"]
            if text.strip():
                success += 1
                print(f"  {name}: ✓  ({len(text)} chars) {text[:60]}...")
            else:
                empty += 1
                print(f"  {name}: EMPTY")
        except Exception as e:
            error += 1
            print(f"  {name}: ✗  {e}")
        time.sleep(0.5)

    print(f"  → {success}/{len(imgs)} success, {empty} empty, {error} error")

print("\n=== Done ===")
PYEOF
