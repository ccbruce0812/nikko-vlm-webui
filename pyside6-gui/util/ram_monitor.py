#!/usr/bin/env python3
"""RAM monitor: restart reason2/moondream2 containers when system RAM exceeds threshold.

Usage: python3 ram_monitor.py <threshold-gib> [interval-sec]
  threshold-gib  — RAM threshold in GiB (e.g. 5.5)
  interval-sec   — check interval in seconds (default: 5)

Sends SIGTERM to itself when parent (invoker_pid) dies.
"""

import os, signal, subprocess, sys, time

THRESHOLD_GIB = float(sys.argv[1]) if len(sys.argv) > 1 else 5.5
INTERVAL_SEC = int(sys.argv[2]) if len(sys.argv) > 2 else 5
RESTART_COOLDOWN = 30
INVOKER_PID = int(os.environ.get("INVOKER_PID", os.getppid()))
CONTAINERS = ["reason2", "moondream2"]


def _get_ram_gib():
    """Read /proc/meminfo, return used RAM in GiB."""
    mem = {}
    with open("/proc/meminfo") as f:
        for line in f:
            if ":" in line:
                key, val = line.split(":", 1)
                val = val.strip().split()[0]
                mem[key] = int(val) if val.isdigit() else 0
    total = mem.get("MemTotal", 1)
    avail = mem.get("MemAvailable", 0)
    return (total - avail) / (1024 ** 2)


def _container_exists(name):
    """Check if container exists (not necessarily running)."""
    r = subprocess.run(
        ["sudo", "docker", "inspect", name],
        capture_output=True,
        timeout=5,
    )
    return r.returncode == 0


def _restart_container(name):
    """Restart a Docker container."""
    try:
        subprocess.run(
            ["sudo", "docker", "restart", name],
            check=True,
            timeout=60,
            capture_output=True,
        )
        print(f"[RAM] restarted {name}")
    except subprocess.CalledProcessError as e:
        print(f"[RAM] failed to restart {name}: {e}")
    except subprocess.TimeoutExpired:
        print(f"[RAM] timeout restarting {name}")


def _parent_alive():
    """Check if invoker process still exists."""
    try:
        os.kill(INVOKER_PID, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def main():
    print(f"[RAM] monitoring threshold={THRESHOLD_GIB}GiB interval={INTERVAL_SEC}s invoker_pid={INVOKER_PID}")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # ignore Ctrl-C, parent handles it

    while _parent_alive():
        ram_gib = _get_ram_gib()
        ts = time.strftime("%Y-%m-%d %H:%M:%S")

        if ram_gib > THRESHOLD_GIB:
            print(f"[RAM] {ts} used={ram_gib:.2f}GiB > {THRESHOLD_GIB}GiB, restarting...")
            for name in CONTAINERS:
                if _container_exists(name):
                    _restart_container(name)
            time.sleep(RESTART_COOLDOWN)
        else:
            print(f"[RAM] {ts} used={ram_gib:.2f}GiB")
            time.sleep(INTERVAL_SEC)

    print("[RAM] invoker ended, exiting")


if __name__ == "__main__":
    main()
