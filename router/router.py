#!/usr/bin/env python3
"""
Router: OpenAI-compatible API proxy for multi-model VLM inference.
Routes requests to the appropriate model container based on model name.
Dynamically discovers available models by probing backends.

Endpoints:
  GET  /v1/models          - List actually available models (probed)
  POST /v1/chat/completions - Forward to model backend based on model name
  GET  /health             - Health check for all backends
"""

import json
import time
import asyncio
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [router] %(message)s")
logger = logging.getLogger("router")

app = FastAPI(title="VLM Router", version="2.0.0")

# Model registry: all known backends
MODEL_REGISTRY = {
    "moondream2": {
        "url": "http://moondream2:8001/v1",
        "owned_by": "jetson",
    },
    "cosmos-reason2-2b": {
        "url": "http://cosmos-reason2:8002/v1",
        "owned_by": "jetson",
    },
    "yolo": {
        "url": "http://yolo:8003/v1",
        "owned_by": "jetson",
    },
}

# Cache for availability checks (avoid probing on every request)
_availability_cache = {}  # model_name -> (available: bool, timestamp: float)
CACHE_TTL = 2.0  # seconds (short to reflect container start/stop quickly)

client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0))


@app.on_event("shutdown")
async def shutdown():
    await client.aclose()


async def probe_backend(name: str, info: dict) -> bool:
    """Check if a model backend is reachable. Results cached for CACHE_TTL seconds."""
    now = time.time()
    cached = _availability_cache.get(name)
    if cached and (now - cached[1]) < CACHE_TTL:
        return cached[0]

    try:
        resp = await client.get(f"{info['url']}/../health", timeout=3.0)
        available = resp.status_code < 500
    except Exception:
        available = False

    _availability_cache[name] = (available, now)
    if available:
        logger.debug(f"Backend '{name}' is available")
    else:
        logger.debug(f"Backend '{name}' is NOT available")
    return available


@app.get("/v1/models")
async def list_models():
    """Return actually available models (probed from backends)."""
    models = []
    # Probe all backends concurrently
    tasks = {name: probe_backend(name, info) for name, info in MODEL_REGISTRY.items()}
    results = await asyncio.gather(*tasks.values())
    
    for (name, info), available in zip(MODEL_REGISTRY.items(), results):
        if available:
            models.append({
                "id": name,
                "object": "model",
                "created": 0,
                "owned_by": info["owned_by"],
            })
        else:
            logger.info(f"Model '{name}' excluded (backend unreachable)")

    return JSONResponse({"object": "list", "data": models})


@app.get("/health")
async def health():
    """Health check for router and all backends."""
    status = {}
    for name, info in MODEL_REGISTRY.items():
        try:
            resp = await client.get(f"{info['url']}/../health", timeout=3.0)
            status[name] = "ok" if resp.status_code < 500 else f"status:{resp.status_code}"
        except Exception as e:
            status[name] = f"unreachable: {type(e).__name__}"
    return {"router": "ok", "backends": status}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Proxy chat completion to the appropriate model backend."""
    body = await request.json()
    model_name = body.get("model", "")

    if not model_name:
        raise HTTPException(status_code=400, detail="Missing 'model' field")

    info = MODEL_REGISTRY.get(model_name)
    if not info:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown model: {model_name}. Available: {list(MODEL_REGISTRY.keys())}",
        )

    backend_url = info["url"]
    start = time.time()
    logger.info(f"Routing '{model_name}' → {backend_url}")

    try:
        resp = await client.post(
            f"{backend_url}/chat/completions",
            json=body,
            headers={"Content-Type": "application/json"},
        )
        elapsed = time.time() - start
        logger.info(f"'{model_name}' response: {resp.status_code} ({elapsed:.2f}s)")

        if body.get("stream"):
            return StreamingResponse(
                resp.aiter_bytes(),
                media_type="text/event-stream",
                headers=dict(resp.headers),
            )

        return JSONResponse(content=resp.json(), status_code=resp.status_code)

    except httpx.ConnectError:
        logger.error(f"Cannot connect to '{model_name}' at {backend_url}")
        raise HTTPException(
            status_code=503,
            detail=f"Model '{model_name}' backend is not available",
        )
    except httpx.TimeoutException:
        logger.error(f"Timeout for '{model_name}'")
        raise HTTPException(
            status_code=504,
            detail=f"Model '{model_name}' inference timed out",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
