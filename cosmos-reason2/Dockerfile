# Cosmos-Reason2 GGUF container (qwen3vl architecture)
# Base: jetson-containers (CUDA 12.6 + build tools)
# Builds llama.cpp from source for llama-server (OpenAI-compatible API)
ARG BASE_IMAGE=dustynv/llama_cpp:r36.4.0
FROM ${BASE_IMAGE} AS builder

# Clone and build llama.cpp with CUDA + Flash Attention
WORKDIR /build
RUN git clone --depth 1 https://github.com/ggerganov/llama.cpp.git && \
    cd llama.cpp && \
    cmake -B build \
        -DGGML_CUDA=ON \
        -DGGML_CUDA_FA=ON \
        -DCMAKE_CUDA_ARCHITECTURES=87 \
        -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build --config Release -j$(nproc)

# Runtime stage
FROM ${BASE_IMAGE}
COPY --from=builder /build/llama.cpp/build/bin/ /usr/local/bin/
ENV LD_LIBRARY_PATH=/usr/local/bin:$LD_LIBRARY_PATH
ENV PATH=/usr/local/bin:$PATH

# Cosmos Reason2 uses qwen3vl architecture
# --repeat-penalty: prevents IQ4_XS output repetition
CMD ["llama-server", \
     "-m", "/model/Cosmos-Reason2-2B-heretic.IQ4_XS.gguf", \
     "--mmproj", "/model/mmproj-Cosmos-Reason2-2B-F16.gguf", \
     "--host", "0.0.0.0", "--port", "8002", \
     "--n-gpu-layers", "99", "--ctx-size", "2048", \
     "--cache-type-k", "q4_0", "--cache-type-v", "q4_0", \
     "--flash-attn", "on", \
     "--repeat-penalty", "1.15", "--repeat-last-n", "256"]
