"""YOLO overlay: prepare_payload + fill_display_meta (nvdsosd bboxes)."""
import json
import math


INFER_MAX_DIM = 1280


def prepare_payload(b64: str, prompt: str, max_tokens: int) -> str:
    return json.dumps({
        "model": "yolo",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": prompt or "Detect objects"},
            ]
        }],
        "max_tokens": min(max_tokens, 1024),
    })


def fill_display_meta(display_meta, result: dict,
                      w: int, h: int, s: float, ds: float,
                      label_idx: int) -> int:
    """Draw YOLO bboxes + labels. Returns new label_idx."""
    resp = result.get("response", "")
    if not resp:
        return label_idx
    try:
        detections = json.loads(resp)
    except Exception:
        return label_idx
    if not detections:
        return label_idx

    max_dim = max(w, h)
    iw = ih = INFER_MAX_DIM
    if max_dim >= INFER_MAX_DIM:
        ratio = INFER_MAX_DIM / max_dim
        iw, ih = int(w * ratio), int(h * ratio)
    sx = w / iw
    sy = h / ih

    display_meta.num_rects = len(detections)
    for di, det in enumerate(detections):
        cls_id = det.get("class", di)
        r = cls_id * 0.6180339887
        cr, cg, cb = (r * 3.7) % 1.0, (r * 7.3) % 1.0, (r * 11.3) % 1.0

        rect = display_meta.rect_params[di]
        bbox = det.get("bbox", [0, 0, 0, 0])
        rect.left = int(bbox[0] * sx)
        rect.top = int(bbox[1] * sy)
        rect.width = int((bbox[2] - bbox[0]) * sx)
        rect.height = int((bbox[3] - bbox[1]) * sy)
        rect.border_width = int(3 * s)
        rect.border_color.set(cr, cg, cb, 1.0)
        rect.has_bg_color = 0

        tp = display_meta.text_params[label_idx]; label_idx += 1
        tp.display_text = f"{det.get('name','obj')} {det.get('confidence',0):.2f}"
        tp.x_offset = int(rect.left) + int(2 * s)
        tp.y_offset = max(0, int(rect.top) + int(2 * s))
        tp.font_params.font_name = "Monospace"
        tp.font_params.font_size = int(16 * s)
        tp.font_params.font_color.set(cr, cg, cb, 1.0)
        tp.set_bg_clr = 0

    return label_idx
