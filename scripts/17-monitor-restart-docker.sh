#!/bin/bash
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 3 ]; then
  echo "usage: $0 <container-name> [threshold-gib] [interval-seconds]" >&2
  exit 1
fi

container_name="$1"
threshold_gib="${2:-6}"
interval_sec="${3:-5}"
restart_cooldown_sec="30"
meminfo="/proc/meminfo"
invoker_pid="${INVOKER_PID:-$PPID}"

get_kb() {
  local key="$1"
  local default="$2"

  awk -v k="$key" -v d="$default" '
    $1 == k ":" {
      print $2
      found = 1
      exit
    }
    END {
      if (!found) print d
    }
  ' "$meminfo"
}

get_ram_gib() {
  local total_kb
  local avail_kb

  total_kb="$(get_kb "MemTotal" 1)"
  avail_kb="$(get_kb "MemAvailable" 0)"

  awk -v total="$total_kb" -v avail="$avail_kb" 'BEGIN {
    printf "%.3f", (total - avail) / (1024 * 1024)
  }'
}

is_gt_threshold() {
  local ram_gib="$1"

  awk -v ram="$ram_gib" -v threshold="$threshold_gib" 'BEGIN {
    exit !(ram > threshold)
  }'
}

container_exists() {
  sudo docker inspect "$container_name" >/dev/null 2>&1
}

cleanup() {
  echo "exiting"
  exit 0
}

trap cleanup INT TERM HUP

if ! container_exists; then
  echo "container not found: $container_name" >&2
  exit 1
fi

echo "monitoring container: $container_name"
echo "threshold: ${threshold_gib} GiB"
echo "interval: ${interval_sec}s"
echo "invoker pid: ${invoker_pid}"

while kill -0 "$invoker_pid" 2>/dev/null; do
  ram_gib="$(get_ram_gib)"

  echo "$(date '+%Y-%m-%d %H:%M:%S') RAM used: ${ram_gib} GiB"

  if is_gt_threshold "$ram_gib"; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') RAM used > ${threshold_gib} GiB, restarting container: ${container_name}"
    sudo docker restart "$container_name"
    sleep "$restart_cooldown_sec"
  else
    sleep "$interval_sec"
  fi
done

echo "invoker ended, exiting"