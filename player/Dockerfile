# Player container: RTSP streaming from MP4 files
FROM arm64v8/ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
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
CMD ["python3", "gst_rtsp_server.py"]
