# moondream2 GGUF container (phi2 architecture)
# Uses pre-compiled llama-server binaries from packages/
# C++ OpenAI-compatible API server
#
# Build: docker build -t moondream2 -f moondream2/Dockerfile .
#
# Environment variables (defaults from moondream_worker.py):
#   MODEL_PATH     — LLM GGUF path
#   MMPROJ_PATH    — mmproj GGUF path
#   N_GPU_LAYERS   — GPU offload layers       (default: 15)
#   N_THREADS      — CPU threads              (default: 4)
#   N_BATCH        — batch size               (default: 128)
#   CTX_SIZE       — context size             (default: 1024)
#   FLASH_ATTN     — FlashAttention on/off    (default: on)
#   PORT           — server port              (default: 8001)
FROM dustynv/l4t-pytorch:r36.4.0

# Deploy pre-compiled llama-server binaries
COPY packages/llama-server-binaries.tar.gz /tmp/
RUN tar xzf /tmp/llama-server-binaries.tar.gz -C /usr/local/bin/ && \
    rm /tmp/llama-server-binaries.tar.gz
ENV LD_LIBRARY_PATH=/usr/local/bin:$LD_LIBRARY_PATH
ENV PATH=/usr/local/bin:$PATH

# ── Defaults (from moondream_worker.py) ──
ENV MODEL_PATH=/model/moondream2-q4_k.gguf
ENV MMPROJ_PATH=/model/moondream2-mmproj-f16.gguf
ENV N_GPU_LAYERS=15
ENV N_THREADS=4
ENV N_BATCH=128
ENV CTX_SIZE=1024
ENV FLASH_ATTN=on
ENV PORT=8001

# Image input: moondream2 vision encoder ~378×378

# moondream2 (phi2) needs custom chat template
CMD ["sh", "-c", "exec llama-server \
    -m \"$MODEL_PATH\" \
    --mmproj \"$MMPROJ_PATH\" \
    --host 0.0.0.0 --port \"$PORT\" \
    --n-gpu-layers \"$N_GPU_LAYERS\" \
    --threads \"$N_THREADS\" \
    --batch-size \"$N_BATCH\" \
    --ctx-size \"$CTX_SIZE\" \
    --flash-attn \"$FLASH_ATTN\" \
    --chat-template \"{% for message in messages %}{% if message['role'] == 'user' %}<image>\\n\\nQuestion: {% for part in message['content'] %}{% if part['type'] == 'text' %}{{ part['text'] }}{% endif %}{% endfor %}\\n\\nAnswer: {% else %}{{ message['content'] }}{% endif %}{% endfor %}\""]
