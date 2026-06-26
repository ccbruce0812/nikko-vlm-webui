# moondream2 GGUF container
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

CMD ["llama-server", \
     "-m", "/model/moondream2-q4_k.gguf", \
     "--mmproj", "/model/moondream2-mmproj-f16.gguf", \
     "--host", "0.0.0.0", "--port", "8001", \
     "--n-gpu-layers", "99", "--ctx-size", "2048", \
     "--cache-type-k", "q4_0", "--cache-type-v", "q4_0", \
     "--flash-attn", "on", \
     "--chat-template", "{% for message in messages %}{% if message['role'] == 'user' %}<image>\n\nQuestion: {% for part in message['content'] %}{% if part['type'] == 'text' %}{{ part['text'] }}{% endif %}{% endfor %}\n\nAnswer: {% else %}{{ message['content'] }}{% endif %}{% endfor %}"]
