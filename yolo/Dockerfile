FROM dustynv/l4t-pytorch:r36.4.0

RUN pip install --no-cache-dir -i https://pypi.org/simple/ ultralytics "numpy<2"

RUN pip install --no-cache-dir \
    --index-url https://pypi.org/simple \
    --extra-index-url https://pypi.ngc.nvidia.com \
    --extra-index-url https://pypi.jetson-ai-lab.io/jp6/cu126 \
    "onnx>=1.12.0" \
    "onnxslim>=0.1.82" \
    "onnxruntime-gpu"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb1 libxcb-render0 libxcb-shm0 libxcb-xfixes0 \
    libgl1 libglib2.0-0 libopenblas0 && \
    rm -rf /var/lib/apt/lists/*

COPY server.py /app/server.py
COPY make-engine-ultralytics.py /app/make-engine-ultralytics.py
COPY DeepStream-Yolo/utils/export_yoloV8.py /app/DeepStream-Yolo/utils/export_yoloV8.py
COPY make-onnx-deepstream.py /app/make-onnx-deepstream.py
WORKDIR /app
