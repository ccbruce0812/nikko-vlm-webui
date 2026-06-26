#!/bin/bash
# Download moondream2 GGUF models (q4_k LLM + f16 mmproj)
set -e
DEST=/home/brucehsu/project/models/moondream2
mkdir -p "$DEST"

echo "=== moondream2 q4_k + mmproj (salivosa) ==="
hf download salivosa/moondream2-gguf \
    moondream2-q4_k.gguf moondream2-mmproj-f16.gguf --local-dir "$DEST"

echo "=== Done ==="
ls -lh "$DEST"
