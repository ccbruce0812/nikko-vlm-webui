"""Shared defaults for CLI args and UI controls."""

DEFAULTS = {
    "camera_id": 0,
    "resolution": "1920x1080@30",   # default resolution
    "perception_model": "yolo",
    "reasoning_model": "reason2",
    "interval": 1000,
    "prompt": "Describe this image in one sentence without coordinates or numbers.",
    "max_tokens": 512,
    "router_url": "http://localhost:8080",
    "ram_threshold": 5.5,
}
