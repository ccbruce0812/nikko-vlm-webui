FROM python:3.10-slim
RUN pip install --no-cache-dir fastapi uvicorn httpx
COPY router.py /app/
WORKDIR /app
EXPOSE 8080
CMD ["uvicorn", "router:app", "--host", "0.0.0.0", "--port", "8080"]
