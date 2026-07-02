# RTSP server container: CSI camera (CAM0 / IMX219) via nvarguscamerasrc
# dustynv/l4t-pytorch already has nvarguscamerasrc / nvvidconv plugins
#
# docker run requires:
#   --runtime nvidia --network host
#   --device=/dev/video0 --device=/dev/media0
#   -v /tmp:/tmp              # nvargus-daemon socket (/tmp/argus_socket)
FROM dustynv/l4t-pytorch:r36.4.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-rtsp \
    gir1.2-gst-rtsp-server-1.0 \
    python3-gi python3-gst-1.0 \
    gstreamer1.0-libav \
    && rm -rf /var/lib/apt/lists/*

COPY gst_rtsp_server.py /app/gst_rtsp_server.py
WORKDIR /app
EXPOSE 8554

# WIDTH / HEIGHT / FPS / SENSOR_ID configurable via env vars
CMD ["python3", "gst_rtsp_server.py"]
