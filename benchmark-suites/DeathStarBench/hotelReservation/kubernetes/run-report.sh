#!/bin/bash

# === CONFIG ===
WRK_BIN="../wrk"
SCRIPT="../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua"
TARGET_URL=$(kubectl get svc frontend -o jsonpath='http://{.spec.clusterIP}:{.spec.ports[0].port}')
RATE=700000
THREADS=32
CONNECTIONS=60
DURATION=100
INTERVAL=1  # seconds

# === OUTPUT ===
OUT_DIR="./wrk-benchmark-log"
mkdir -p "$OUT_DIR"
LOG_FILE="$OUT_DIR/node_cpu_usage.log"
PEAK_FILE="$OUT_DIR/peak_cpu_usage.dat"
WRK_OUT="$OUT_DIR/wrk_output.dat"

# === CLEAR OLD ===
rm -f "$LOG_FILE" "$PEAK_FILE" "$WRK_OUT"

echo "[INFO] Starting wrk..."
$WRK_BIN -D exp -t $THREADS -c $CONNECTIONS -d ${DURATION}s -L -s "$SCRIPT" "$TARGET_URL" -R $RATE > "$WRK_OUT" &
WRK_PID=$!

echo "[INFO] Sampling node CPU usage every ${INTERVAL}s..."
while kill -0 "$WRK_PID" 2>/dev/null; do
    echo "$(date +%s)" >> "$LOG_FILE"
    kubectl top nodes --no-headers >> "$LOG_FILE"
    echo "---" >> "$LOG_FILE"
    sleep "$INTERVAL"
done

echo "[INFO] Benchmark complete. Computing peak CPU usage..."

# === Compute Peak CPU Usage per Node ===
awk '
/^[0-9]+$/ { next }  # skip timestamp lines
/^---$/ { next }      # skip separators
{
  node = $1
  cpu_raw = $2
  # Convert to millicores
  if (cpu_raw ~ /m$/) {
    cpu = int(substr(cpu_raw, 1, length(cpu_raw)-1))
  } else {
    cpu = int(cpu_raw * 1000)
  }
  if (cpu > peak[node]) {
    peak[node] = cpu
  }
}
END {
  for (node in peak) {
    printf "%s: %.2f cores\n", node, peak[node] / 1000
  }
}
' "$LOG_FILE" > "$PEAK_FILE"

