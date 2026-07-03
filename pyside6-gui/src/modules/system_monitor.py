"""
System monitor: reads GPU / CPU / RAM from /proc and /sys.
No jetson-stats dependency.
"""
import logging

logger = logging.getLogger(__name__)


def read_stats():
    """Return dict with keys: gpu(%), _cpu_total, _cpu_idle, ram(GiB), vram(GiB)."""
    stats = {}
    # GPU
    try:
        with open("/sys/devices/gpu.0/load") as f:
            stats["gpu"] = int(f.read().strip()) / 10.0  # 0-1000 → 0-100%
    except Exception:
        stats["gpu"] = 0

    # CPU snapshot (raw totals for delta calculation)
    try:
        with open("/proc/stat") as f:
            cols = f.readline().split()
        if len(cols) >= 5:
            stats["_cpu_total"] = sum(int(cols[i]) for i in (1, 2, 3, 4))
            stats["_cpu_idle"] = int(cols[4])
    except Exception:
        stats["_cpu_total"] = 0
        stats["_cpu_idle"] = 0

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
        stats["ram"] = (total_kb - avail_kb) / (1024**2)  # GiB
    except Exception:
        stats["ram"] = 0
    stats["vram"] = stats["ram"]  # Jetson unified memory

    return stats


def compute_cpu_pct(prev, curr):
    """Compute CPU usage % between two read_stats() snapshots."""
    if not prev or not curr:
        return 0
    td = curr["_cpu_total"] - prev["_cpu_total"]
    if td <= 0:
        return 0
    return 100.0 * (td - (curr["_cpu_idle"] - prev["_cpu_idle"])) / td
