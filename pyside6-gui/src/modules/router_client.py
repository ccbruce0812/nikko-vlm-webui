"""
Async HTTP client for Router API.
Runs aiohttp in a dedicated QThread — non-blocking to the UI.
"""
import json
import asyncio
import logging
from PySide6.QtCore import QThread, Signal

import aiohttp

logger = logging.getLogger(__name__)

ROUTER_URL = "http://localhost:8080"


class RouterClient(QThread):
    """Async client: model discovery + chat completions via Router API."""

    models_ready = Signal(list)        # [(model_id, owned_by), ...]
    result_ready = Signal(str, str)    # (model_name, response_text)
    error_occurred = Signal(str)       # error message
    status_message = Signal(str)

    def __init__(self):
        super().__init__()
        self._loop = None
        self._pending = []  # list of (model, payload_json_str)

    # ----- public API (called from main thread) -----

    def fetch_models(self):
        """Trigger async model discovery. Result via models_ready signal."""
        self._pending.append(("__models__", None))

    def send_inference(self, model, image_b64, prompt, max_tokens):
        """Enqueue an inference request. Result via result_ready signal."""
        payload = json.dumps({
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}"
                    }},
                ]
            }],
            "max_tokens": max_tokens,
        })
        self._pending.append((model, payload))

    def send_raw_payload(self, payload_str: str):
        """Send a pre-built JSON payload (prepared by overlay module)."""
        model = json.loads(payload_str)["model"]
        self._pending.append((model, payload_str))

    # ----- thread -----

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._worker())
        except RuntimeError:
            pass  # event loop stopped during shutdown

    async def _worker(self):
        connector = aiohttp.TCPConnector(limit=2)
        async with aiohttp.ClientSession(connector=connector) as session:
            while not self.isInterruptionRequested():
                if not self._pending:
                    await asyncio.sleep(0.05)
                    continue

                model, payload = self._pending.pop(0)

                if model == "__models__":
                    await self._do_fetch_models(session)
                else:
                    await self._do_inference(session, model, payload)

    async def _do_fetch_models(self, session):
        try:
            async with session.get(
                f"{ROUTER_URL}/v1/models", timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                data = await resp.json()
                models = [(m["id"], m.get("owned_by", "")) for m in data.get("data", [])]
                self.models_ready.emit(models)
                self.status_message.emit(f"Found {len(models)} model(s)")
        except Exception as e:
            self.error_occurred.emit(f"Model discovery failed: {e}")

    async def _do_inference(self, session, model, payload):
        try:
            self.status_message.emit(f"Inferring {model}...")
            async with session.post(
                f"{ROUTER_URL}/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=120, connect=5),
            ) as resp:
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                self.result_ready.emit(model, content)
                self.status_message.emit(f"{model} done")
        except Exception as e:
            self.error_occurred.emit(f"Inference error ({model}): {e}")

    def stop(self):
        self.requestInterruption()
        if hasattr(self, '_loop'):
            if self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
            self.wait(2000)
