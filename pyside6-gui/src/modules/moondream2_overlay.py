"""Moondream2 overlay: prepare_payload + fill_display_meta (caption bar)."""
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
    })


def fill_display_meta(display_meta, result: dict,
                      w: int, h: int, s: float, ds: float,
                      label_idx: int) -> int:
    """Draw caption bar. Returns new label_idx."""
    elapsed = result.get("elapsed_ms", 0)
    response = result.get("response", "").lstrip()
    if not response:
        return label_idx

    text = f"Elapsed: {elapsed:.0f}ms\n{response}"
    chars_per_line = 120
    segments = text.split("\n")
    lines = []
    for seg in segments:
        seg = seg.strip()
        while len(seg) > chars_per_line:
            lines.append(seg[:chars_per_line])
            seg = seg[chars_per_line:]
        if seg:
            lines.append(seg)
    lines = lines[:5]

    cap_w = int(w * 0.95)
    cap_line_h = int(14 * s * ds)
    cap_margin = int(h * 0.12)
    cap_x = int((w - cap_w) // 2)
    cap_text_h = cap_line_h * len(lines)
    cap_y = int(h - cap_margin - cap_text_h)

    display_meta.num_rects += 1
    bg = display_meta.rect_params[display_meta.num_rects - 1]
    bg.left = cap_x
    bg.top = cap_y
    bg.width = cap_w
    bg.height = cap_text_h + cap_margin
    bg.border_width = 0
    bg.has_bg_color = 0
    bg.bg_color.set(0.0, 0.0, 0.0, 0.6)

    for li, line in enumerate(lines):
        cap = display_meta.text_params[label_idx]; label_idx += 1
        cap.display_text = line
        cap.x_offset = cap_x + int(4 * s)
        cap.y_offset = cap_y + int(2 * s) + li * cap_line_h
        cap.font_params.font_name = "Monospace"
        cap.font_params.font_size = int(16 * s)
        cap.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
        cap.set_bg_clr = 1
        cap.text_bg_clr.set(0.0, 0.0, 0.0, 0.6)

    return label_idx
