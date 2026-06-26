#!/bin/bash
# Download Cosmos-Reason2 GGUF models (IQ4_XS LLM + F16 mmproj)
set -e
DEST=/home/brucehsu/project/models/cosmos-reason2
mkdir -p "$DEST"

echo "=== Cosmos-Reason2-2B IQ4_XS LLM (mradermacher) ==="
hf download mradermacher/Cosmos-Reason2-2B-heretic-GGUF \
    Cosmos-Reason2-2B-heretic.IQ4_XS.gguf --local-dir "$DEST"

echo "=== Cosmos-Reason2-2B F16 mmproj (apolo13x) ==="
hf download apolo13x/Cosmos-Reason2-2B-GGUF \
    mmproj-Cosmos-Reason2-2B-F16.gguf --local-dir "$DEST"

echo "=== Done ==="
ls -lh "$DEST"
