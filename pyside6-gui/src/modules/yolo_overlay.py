"""YOLO bbox color override for nvinfer → nvdsosd (live pipeline)."""
import pyds


def override_bbox_colors(frame_meta) -> None:
    """Apply per-class golden-ratio colors to NvDsObjectMeta before nvdsosd draws."""
    l_obj = frame_meta.obj_meta_list
    while l_obj is not None:
        try:
            obj = pyds.NvDsObjectMeta.cast(l_obj.data)
        except StopIteration:
            break
        c = obj.class_id
        obj.rect_params.border_color.set(
            (c * 0.6180339887 * 3.7) % 1.0,
            (c * 0.6180339887 * 7.3) % 1.0,
            (c * 0.6180339887 * 11.3) % 1.0, 1.0)
        obj.text_params.set_bg_clr = 1
        obj.text_params.text_bg_clr.set(
            (c * 0.6180339887 * 3.7) % 1.0,
            (c * 0.6180339887 * 7.3) % 1.0,
            (c * 0.6180339887 * 11.3) % 1.0, 0.6)
        try:
            l_obj = l_obj.next
        except StopIteration:
            break
