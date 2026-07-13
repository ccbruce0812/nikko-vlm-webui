"""YOLO overlay: payload builder (b64 JPEG) + response parser (bbox coords)."""
import json
import logging

logger = logging.getLogger(__name__)

INFER_MAX_DIM = 1280


def prepare_payload(b64: str, prompt: str, max_tokens: int) -> str:
    """Build Router API JSON payload from base64 JPEG."""
    return json.dumps({
        "model": "yolo",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": "Detect objects"},
            ]
        }],
        "max_tokens": min(max_tokens, 1024),
    })
