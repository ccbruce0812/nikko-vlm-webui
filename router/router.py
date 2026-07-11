#!/usr/bin/env python3
"""Router: OpenAI-compatible API proxy. Routes to model backends by name."""

import argparse, json, logging, os, time
import asyncio
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [router] %(message)s")
logger = logging.getLogger("router")


def build_app(port: int, backends: dict, cache_ttl: int, timeout: int, connect_timeout: int):
    _availability_cache = {}
    client = httpx.AsyncClient(timeout=httpx.Timeout(float(timeout), connect=float(connect_timeout)))

    app = FastAPI(title="VLM Router", version="3.0.0")

    @app.on_event("shutdown")
    async def _shutdown():
        await client.aclose()

    async def _probe(name: str, info: dict) -> bool:
        now = time.time()
        cached = _availability_cache.get(name)
        if cached and (now - cached[1]) < cache_ttl:
            return cached[0]
        try:
            resp = await client.get(f"{info['url']}/../health", timeout=3.0)
            available = resp.status_code < 500
        except Exception:
            available = False
        _availability_cache[name] = (available, now)
        return available

    def _get_vlm_backend(model: str = None):
        """Return the base URL for a VLM backend. If model not specified, use first available."""
        if model:
            info = backends.get(model)
            if not info:
                raise HTTPException(404, f"Unknown model: {model}")
            return info["base_url"]
        for name, info in backends.items():
            if name != "yolo":
                return info["base_url"]
        raise HTTPException(404, "No VLM backend configured")

    @app.get("/v1/models")
    async def list_models():
        tasks = {name: _probe(name, info) for name, info in backends.items()}
        results = await asyncio.gather(*tasks.values())
        models = []
        for (name, info), ok in zip(backends.items(), results):
            if ok:
                models.append({"id": name, "object": "model", "created": 0, "owned_by": info.get("owned_by", "jetson")})
            else:
                logger.info(f"Model '{name}' excluded (backend unreachable)")
        return JSONResponse({"object": "list", "data": models})

    @app.get("/health")
    async def health():
        status = {}
        for name, info in backends.items():
            try:
                resp = await client.get(f"{info['url']}/../health", timeout=3.0)
                status[name] = "ok" if resp.status_code < 500 else f"status:{resp.status_code}"
            except Exception as e:
                status[name] = f"unreachable: {type(e).__name__}"
        return {"router": "ok", "backends": status}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        body = await request.json()
        model_name = body.get("model", "")
        if not model_name:
            raise HTTPException(400, "Missing 'model' field")
        info = backends.get(model_name)
        if not info:
            raise HTTPException(404, f"Unknown model: {model_name}. Available: {list(backends.keys())}")
        backend_url = info["url"]
        start = time.time()
        logger.info(f"Routing '{model_name}' → {backend_url}")
        try:
            resp = await client.post(f"{backend_url}/chat/completions", json=body, headers={"Content-Type": "application/json"})
            elapsed = time.time() - start
            logger.info(f"'{model_name}' response: {resp.status_code} ({elapsed:.2f}s)")
            if body.get("stream"):
                return StreamingResponse(resp.aiter_bytes(), media_type="text/event-stream", headers=dict(resp.headers))
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.ConnectError:
            raise HTTPException(503, f"Model '{model_name}' backend is not available")
        except httpx.TimeoutException:
            raise HTTPException(504, f"Model '{model_name}' inference timed out")

    @app.api_route("/slots/{path:path}", methods=["GET", "POST", "DELETE"])
    async def slots_proxy(request: Request, path: str, model: str = Query(None)):
        base_url = _get_vlm_backend(model)
        target = f"{base_url}/slots/{path}"
        qs = str(request.url.query).replace(f"model={model}&", "").replace(f"&model={model}", "").replace(f"?model={model}", "?") if model else str(request.url.query)
        if qs and not qs.startswith("?"):
            qs = "?" + qs
        target += qs if qs != "?" else ""
        logger.info(f"Slot action → {target}")
        body = await request.body()
        resp = await client.request(method=request.method, url=target, content=body or None, headers=dict(request.headers))
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

    return app


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="VLM Router")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--moondream2-url", default="http://moondream2:8001")
    p.add_argument("--reason2-url", default="http://reason2:8002")
    p.add_argument("--yolo-url", default="http://yolo:8003")
    p.add_argument("--cache-ttl", type=int, default=2)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--connect-timeout", type=int, default=5)
    args = p.parse_args()

    backends = {}
    if args.moondream2_url:
        base = args.moondream2_url.rstrip("/")
        backends["moondream2"] = {"base_url": base, "url": base + "/v1"}
    if args.reason2_url:
        base = args.reason2_url.rstrip("/")
        backends["reason2"] = {"base_url": base, "url": base + "/v1"}
    if args.yolo_url:
        base = args.yolo_url.rstrip("/")
        backends["yolo"] = {"base_url": base, "url": base + "/v1"}

    app = build_app(args.port, backends, args.cache_ttl, args.timeout, args.connect_timeout)

    import uvicorn
    logger.info(f"Router starting on :{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
