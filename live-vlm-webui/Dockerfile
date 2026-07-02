# live-vlm-webui with Jetson GPU fix + pre-configured for local router
FROM ghcr.io/nvidia-ai-iot/live-vlm-webui:latest-jetson-orin

# Patch gpu_monitor.py for Jetson (skip nvidia-smi fallback)
COPY patch_gpu_monitor.py /tmp/patch_gpu_monitor.py
RUN python3 /tmp/patch_gpu_monitor.py && rm /tmp/patch_gpu_monitor.py

# Pre-configure API defaults to local router
ENV LIVE_VLM_API_BASE=http://localhost:8080/v1
ENV LIVE_VLM_DEFAULT_MODEL=reason2

EXPOSE 8090
ENTRYPOINT ["live-vlm-webui"]
CMD ["--host", "0.0.0.0", "--port", "8090", \
     "--api-base", "http://localhost:8080/v1", \
     "--api-key", "***", \
     "--model", "reason2"]
