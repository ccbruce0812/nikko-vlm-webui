"""Moondream2 overlay: prepare_payload."""
import json


def prepare_payload(b64: str, prompt: str, max_tokens: int) -> str:
    return json.dumps({
        "model": "moondream2",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": prompt},
            ]
        }],
        "max_tokens": min(max_tokens, 512),
        "cache_prompt": False,
    })
