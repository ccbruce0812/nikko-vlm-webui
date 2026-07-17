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


class RouterClient(QThread):
    """Async client: model discovery + chat completions via Router API."""

    result_ready = Signal(str, str)    # (model_name, response_text)
    error_occurred = Signal(str)       # error message
    status_message = Signal(str)

    def __init__(self, router_url="http://localhost:8080"):
        super().__init__()
        self._url = router_url
        self._loop = None
        self._pending = []  # list of (model, payload_json_str)

    # ----- public API (called from main thread) -----


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
        connector = aiohttp.TCPConnector(limit=4)
        async with aiohttp.ClientSession(connector=connector) as session:
            while not self.isInterruptionRequested():
                if not self._pending:
                    await asyncio.sleep(0.05)
                    continue

                model, payload = self._pending.pop(0)

                asyncio.ensure_future(self._do_inference(session, model, payload))


    async def _do_inference(self, session, model, payload):
        try:
            self.status_message.emit(f"Inferring {model}...")
            async with session.post(
                f"{self._url}/v1/chat/completions",
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
        if hasattr(self, '_loop') and self._loop.is_running():
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                self._loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
        self.wait(2000)
