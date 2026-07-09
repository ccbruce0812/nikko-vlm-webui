FROM dustynv/l4t-pytorch:r36.4.0

COPY llama-cpp-binaries.tgz /tmp/
RUN tar xzf /tmp/llama-cpp-binaries.tgz -C /usr/local && rm /tmp/llama-cpp-binaries.tgz

ENV LD_LIBRARY_PATH=/usr/local/lib:/usr/local/cuda/lib64:$LD_LIBRARY_PATH
