# YOLO container (object detection)
# Base: jetson-containers l4t-pytorch (CUDA 12.6 + PyTorch 2.4)
FROM dustynv/l4t-pytorch:r36.4.0

# Override pip index to use standard PyPI (jetson-containers index not reachable during build)
RUN pip install --no-cache-dir -i https://pypi.org/simple/ ultralytics "numpy<2"

# OpenCV runtime deps (libxcb for cv2.imshow support)  
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb1 libxcb-render0 libxcb-shm0 libxcb-xfixes0 \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Simple REST API server for YOLO inference
COPY yolo_server.py /app/yolo_server.py
WORKDIR /app
EXPOSE 8003
CMD ["python3", "yolo_server.py"]
