"""
System monitor: GPU / CPU / RAM via /sys and /proc (no jetson-stats dependency).
"""
import logging

logger = logging.getLogger(__name__)


def read_stats():
    """Return dict: gpu(%), cpu(%), ram(GiB), vram(GiB)."""
    stats = {}
    # GPU
    try:
        with open("/sys/devices/platform/gpu.0/load") as f:
            stats["gpu"] = int(f.read().strip()) / 10.0
    except Exception:
        stats["gpu"] = 0
    # CPU
    try:
        with open("/proc/stat") as f:
            cols = f.readline().split()
        if len(cols) >= 5:
            total = sum(int(cols[i]) for i in (1, 2, 3, 4))
            idle = int(cols[4])
            if total > 0:
                stats["_cpu_total"] = total
                stats["_cpu_idle"] = idle
    except Exception:
        stats["_cpu_total"] = 0
        stats["_cpu_idle"] = 0
    stats["cpu"] = 0
    # RAM
    try:
        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    mem[k.strip()] = int(v.strip().split()[0])
        total_kb = mem.get("MemTotal", 1)
        avail_kb = mem.get("MemAvailable", 0)
        stats["ram"] = (total_kb - avail_kb) / (1024 ** 2)
    except Exception:
        stats["ram"] = 0
    stats["vram"] = stats["ram"]
    return stats


def compute_cpu_pct(prev, curr):
    """Compute CPU % from two /proc snapshots."""
    if not prev or not curr:
        return 0
    td = curr.get("_cpu_total", 0) - prev.get("_cpu_total", 0)
    if td <= 0:
        return 0
    return 100.0 * (td - (curr.get("_cpu_idle", 0) - prev.get("_cpu_idle", 0))) / td
