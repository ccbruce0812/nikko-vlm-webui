"""Reason2 overlay: payload builder (b64 JPEG)."""
import json


def prepare_payload(b64: str, prompt: str, max_tokens: int) -> str:
    """Build Router API JSON payload from base64 JPEG."""
    return json.dumps({
        "model": "reason2",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": prompt},
            ]
        }],
        "max_tokens": min(max_tokens, 2048),
    })
