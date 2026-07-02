# Reason2 GGUF container (qwen3vl architecture, formerly Cosmos-Reason2)
# Uses pre-compiled llama-server binaries from packages/
# C++ OpenAI-compatible API server
#
# Build: docker build -t reason2 -f reason2/Dockerfile .
#
# Environment variables (defaults from reason2_worker.py):
#   MODEL_PATH     — LLM GGUF path           (default: IQ4_XS)
#   MMPROJ_PATH    — mmproj GGUF path
#   N_GPU_LAYERS   — GPU offload layers       (default: 12)
#   N_THREADS      — CPU threads              (default: 4)
#   N_BATCH        — batch size               (default: 256)
#   CTX_SIZE       — context size             (default: 2048)
#   FLASH_ATTN     — FlashAttention on/off    (default: on)
#   PORT           — server port              (default: 8002)
FROM dustynv/l4t-pytorch:r36.4.0

# Deploy pre-compiled llama-server binaries
COPY packages/llama-server-binaries.tar.gz /tmp/
RUN tar xzf /tmp/llama-server-binaries.tar.gz -C /usr/local/bin/ && \
    rm /tmp/llama-server-binaries.tar.gz
ENV LD_LIBRARY_PATH=/usr/local/bin:$LD_LIBRARY_PATH
ENV PATH=/usr/local/bin:$PATH

# ── Defaults (from reason2_worker.py) ──
ENV MODEL_PATH=/model/Cosmos-Reason2-2B-heretic.IQ4_XS.gguf
ENV MMPROJ_PATH=/model/mmproj-Cosmos-Reason2-2B-F16.gguf
ENV N_GPU_LAYERS=12
ENV N_THREADS=4
ENV N_BATCH=256
ENV CTX_SIZE=2048
ENV FLASH_ATTN=on
ENV PORT=8002

# Image input: mmproj auto-resizes to 768×768

CMD ["sh", "-c", "exec llama-server \
    -m \"$MODEL_PATH\" \
    --mmproj \"$MMPROJ_PATH\" \
    --host 0.0.0.0 --port \"$PORT\" \
    --n-gpu-layers \"$N_GPU_LAYERS\" \
    --threads \"$N_THREADS\" \
    --batch-size \"$N_BATCH\" \
    --ctx-size \"$CTX_SIZE\" \
    --cache-type-k q4_0 --cache-type-v q4_0 \
    --flash-attn \"$FLASH_ATTN\""]
