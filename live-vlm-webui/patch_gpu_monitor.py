#!/usr/bin/env python3
"""Patch live-vlm-webui gpu_monitor.py for Jetson GPU stats."""
path = "/app/src/live_vlm_webui/gpu_monitor.py"

with open(path) as f:
    code = f.read()

# Fix 1: sysfs GPU load fallback (reliable in Docker, bypasses jtop)
old1 = 'gpu_percent = (\n                    self.jtop_instance.stats.get("GPU", 0)\n                    if isinstance(self.jtop_instance.stats, dict)\n                    else 0\n                )'
new1 = '''gpu_percent = (
                    self.jtop_instance.stats.get("GPU", 0)
                    if isinstance(self.jtop_instance.stats, dict)
                    else 0
                )
                if gpu_percent == 0:
                    try:
                        import glob
                        for p in glob.glob("/sys/devices/platform/*/*.gpu/load") or glob.glob("/sys/devices/platform/*/gpu/load"):
                            with open(p) as f: gpu_percent = int(f.read().strip()) / 10.0
                            break
                    except: pass'''
code = code.replace(old1, new1)

# Fix 2: skip nvidia-smi fallback on Jetson (VRAM=0 is normal)
old2 = '''                if (
                    vram_total_gb == 0
                    or gpu_percent == 0
                    or not isinstance(self.jtop_instance.stats, dict)
                    or not isinstance(memory, dict)
                ):'''
new2 = '''                is_jetson = any(x in (self.gpu_name or "") for x in ["Orin", "Thor", "Jetson", "nvgpu"])
                if (
                    (vram_total_gb == 0 and not is_jetson)
                    or gpu_percent == 0
                    or not isinstance(self.jtop_instance.stats, dict)
                    or (not isinstance(memory, dict) and not is_jetson)
                ):'''
code = code.replace(old2, new2)

with open(path, "w") as f:
    f.write(code)
compile(code, path, "exec")
print("GPU monitor patched for Jetson")
