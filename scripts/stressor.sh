#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Training dataset collection for CPU power model (stress-ng)
# - Dense-low + coarse-high worker counts (default for 64 cores)
# - Adds topology diversity: PACK / SPREAD / SMT-heavy / cross-socket
# - Removes sleep stressor
# - Ensures stressors are terminated before starting the next one
# ============================================================

# --------------------------
# Dependencies
# --------------------------
for bin in stress-ng timeout; do
  command -v "$bin" >/dev/null 2>&1 || { echo "[ERROR] missing dependency: $bin"; exit 1; }
done
command -v setsid >/dev/null 2>&1 || { echo "[ERROR] missing dependency: setsid"; exit 1; }

# --------------------------
# Tunables (override via env)
# --------------------------
DURATION="${DURATION:-5s}"              # stress-ng --timeout
GUARD_TIMEOUT="${GUARD_TIMEOUT:-12s}"   # outer guard via timeout; must exceed DURATION
WARMUP_SEC="${WARMUP_SEC:-5}"           # before the whole suite
COOLDOWN_SEC="${COOLDOWN_SEC:-1}"       # between runs
MAX_WORKERS="${MAX_WORKERS:-$(nproc --all)}"

ENABLE_NUMA="${ENABLE_NUMA:-1}"
ENABLE_TOPOLOGY="${ENABLE_TOPOLOGY:-1}"

# Keep VM allocations safe by default; override if you want more aggressive memory traffic.
VM_BYTES_PER_WORKER="${VM_BYTES_PER_WORKER:-128M}"
HDD_BYTES="${HDD_BYTES:-256M}"
MATRIX_SIZE="${MATRIX_SIZE:-2048}"

# Dense-low/coarse-high worker list for 64 cores:
# 1..8 + 10,12,14,16,20,24,28,32,40,48,56,64  => 20 points
if [[ -n "${WORKER_COUNTS:-}" ]]; then
  read -r -a worker_counts <<< "${WORKER_COUNTS}"
else
  worker_counts=(1 2 3 4 5 6 7 8 10 12 14 16 20 24 28 32 40 48 56 64)
fi
# Trim to MAX_WORKERS and de-dup
worker_counts=($(for w in "${worker_counts[@]}"; do
  [[ "$w" =~ ^[0-9]+$ ]] || continue
  (( w >= 1 && w <= MAX_WORKERS )) && echo "$w"
done | awk '!seen[$0]++'))
if ((${#worker_counts[@]}==0)); then worker_counts=(1); fi

# CPU-load sweep (DVFS/turbo regimes)
cpu_loads=(10 25 50 75 90 100)

echo "[INFO] max_cores=$(nproc --all), MAX_WORKERS=$MAX_WORKERS"
echo "[INFO] worker_counts=${worker_counts[*]}"
echo "[INFO] duration=$DURATION guard=$GUARD_TIMEOUT warmup=${WARMUP_SEC}s cooldown=${COOLDOWN_SEC}s"

sleep "$WARMUP_SEC"

# --------------------------
# Stressors (sleep removed)
# --------------------------
stressors=(
  cpu io aio vm hdd fork matrix cache sock malloc pthread sem fallocate
  switch dup flock mmap numa pipe lockbus timer dentry zlib icache
  idle-page l1cache userfaultfd x86syscall ipsec-mb
)

# Optional “DL-ish” memory BW stressors if your stress-ng build has them
dl_mem_bw_candidates=(stream memrate)

# ============================================================
# Process control: run each command in its own process group and
# always kill the whole group afterward (no leftovers).
# ============================================================
ACTIVE_PGID=""

cleanup_children() {
  if [[ -n "${ACTIVE_PGID:-}" ]]; then
    kill -TERM -- "-$ACTIVE_PGID" 2>/dev/null || true
    sleep 0.2
    kill -KILL -- "-$ACTIVE_PGID" 2>/dev/null || true
    ACTIVE_PGID=""
  fi
}
trap cleanup_children EXIT INT TERM

run_grouped() {
  local label="$1"; shift
  echo ""
  echo "[RUN] $label"
  echo "      CMD: $*"

  # New session -> its own process group
  setsid timeout -k 2s "$GUARD_TIMEOUT" "$@" &
  local pid=$!
  ACTIVE_PGID="$pid"

  set +e
  wait "$pid"
  local rc=$?
  set -e

  # Always tear down entire process group
  kill -TERM -- "-$pid" 2>/dev/null || true
  sleep 0.2
  kill -KILL -- "-$pid" 2>/dev/null || true
  ACTIVE_PGID=""

  sleep "$COOLDOWN_SEC"

  if (( rc != 0 )); then
    echo "[WARN] exit=$rc for: $label (continuing)"
  fi
}

run_pair() {
  # Run two stress-ng commands concurrently; each in its own process group.
  local label="$1"; shift
  local cmd1=("$@")  # we’ll split below using a marker
}

# stress-ng option sanity: lightweight existence check without doing real work
has_stressor() {
  local s="$1"
  stress-ng --"$s" 1 --timeout 0.01s --dry-run >/dev/null 2>&1
}

# Per-stressor parameterization (important for “representative” regimes)
stressor_args() {
  local s="$1"
  case "$s" in
    vm)     echo "--vm-bytes $VM_BYTES_PER_WORKER --vm-keep" ;;
    hdd)    echo "--hdd-bytes $HDD_BYTES" ;;
    io|aio) echo "--iomix 50" ;;
    matrix) echo "--matrix-size $MATRIX_SIZE" ;;
    *)      echo "" ;;
  esac
}

run_stressor() {
  local s="$1" w="$2"
  if ! has_stressor "$s"; then
    echo "[SKIP] stressor '$s' not supported by this stress-ng build"
    return 0
  fi
  local extra; extra="$(stressor_args "$s")"
  # shellcheck disable=SC2086
  run_grouped "single:$s w=$w" stress-ng --"$s" "$w" --timeout "$DURATION" $extra
}

run_two_stressors() {
  local s1="$1" w1="$2" s2="$3" w2="$4"
  if ! has_stressor "$s1" || ! has_stressor "$s2"; then
    echo "[SKIP] pair $s1+$s2 (unsupported stressor)"
    return 0
  fi
  local extra1 extra2
  extra1="$(stressor_args "$s1")"
  extra2="$(stressor_args "$s2")"

  echo ""
  echo "[RUN] pair:$s1(w=$w1) + $s2(w=$w2)"

  setsid timeout -k 2s "$GUARD_TIMEOUT" stress-ng --"$s1" "$w1" --timeout "$DURATION" $extra1 &
  local p1=$!
  setsid timeout -k 2s "$GUARD_TIMEOUT" stress-ng --"$s2" "$w2" --timeout "$DURATION" $extra2 &
  local p2=$!

  set +e
  wait "$p1"; local rc1=$?
  wait "$p2"; local rc2=$?
  set -e

  # Kill both process groups (in case anything lingered)
  kill -TERM -- "-$p1" 2>/dev/null || true
  kill -TERM -- "-$p2" 2>/dev/null || true
  sleep 0.2
  kill -KILL -- "-$p1" 2>/dev/null || true
  kill -KILL -- "-$p2" 2>/dev/null || true

  sleep "$COOLDOWN_SEC"
  if (( rc1 != 0 || rc2 != 0 )); then
    echo "[WARN] pair exit rc1=$rc1 rc2=$rc2 (continuing)"
  fi
}

# ============================================================
# NUMA discovery and helpers
# ============================================================
declare -A node_cpulist=()
numa_nodes=()

if command -v lscpu >/dev/null 2>&1; then
  while IFS=, read -r cpu node; do
    [[ "$cpu" =~ ^[0-9]+$ ]] || continue
    [[ "$node" =~ ^-?[0-9]+$ ]] || continue
    (( node < 0 )) && node=0
    if [[ -n "${node_cpulist[$node]:-}" ]]; then
      node_cpulist[$node]="${node_cpulist[$node]},$cpu"
    else
      node_cpulist[$node]="$cpu"
      numa_nodes+=("$node")
    fi
  done < <(lscpu -p=CPU,NODE 2>/dev/null | sed -e 's/#.*//g' | sed '/^\s*$/d')

  if ((${#numa_nodes[@]}>0)); then
    IFS=$'\n' numa_nodes=($(printf "%s\n" "${numa_nodes[@]}" | sort -n | uniq))
    unset IFS
  fi
fi

if ((${#numa_nodes[@]}==0)); then
  numa_nodes=(0)
  node_cpulist[0]="0-$(($(nproc --all)-1))"
fi

echo "[INFO] NUMA nodes detected: ${numa_nodes[*]}"
for n in "${numa_nodes[@]}"; do
  echo "[INFO] node $n cpus: ${node_cpulist[$n]}"
done

first_core_of_node() {
  local node="$1"
  local list="${node_cpulist[$node]}"
  if [[ "$list" == *","* ]]; then
    echo "${list%%,*}"
  else
    echo "${list%%-*}"
  fi
}

run_stressor_numa() {
  local s="$1" w="$2" cpu_node="$3" mem_node="$4"
  if ! has_stressor "$s"; then
    echo "[SKIP] stressor '$s' not supported by this stress-ng build"
    return 0
  fi
  local extra; extra="$(stressor_args "$s")"

  if command -v numactl >/dev/null 2>&1; then
    # shellcheck disable=SC2086
    run_grouped "numa:$s w=$w cpu_node=$cpu_node mem_node=$mem_node" \
      numactl --cpunodebind="$cpu_node" --membind="$mem_node" \
      stress-ng --"$s" "$w" --timeout "$DURATION" $extra
  else
    # best-effort fallback: pin to a core in that node
    local core; core="$(first_core_of_node "$cpu_node")"
    # shellcheck disable=SC2086
    run_grouped "taskset:$s w=$w core=$core (no numactl)" \
      stress-ng --"$s" "$w" --taskset "$core" --timeout "$DURATION" $extra
  fi
}

run_pair_numa_split() {
  local s1="$1" w1="$2" node1="$3"
  local s2="$4" w2="$5" node2="$6"

  if ! has_stressor "$s1" || ! has_stressor "$s2"; then
    echo "[SKIP] numa pair $s1+$s2 (unsupported stressor)"
    return 0
  fi
  command -v numactl >/dev/null 2>&1 || { echo "[SKIP] numa split requires numactl"; return 0; }

  local extra1 extra2
  extra1="$(stressor_args "$s1")"
  extra2="$(stressor_args "$s2")"

  echo ""
  echo "[RUN] numa-pair:$s1(node=$node1,w=$w1) + $s2(node=$node2,w=$w2)"

  setsid timeout -k 2s "$GUARD_TIMEOUT" \
    numactl --cpunodebind="$node1" --membind="$node1" \
    stress-ng --"$s1" "$w1" --timeout "$DURATION" $extra1 &
  local p1=$!

  setsid timeout -k 2s "$GUARD_TIMEOUT" \
    numactl --cpunodebind="$node2" --membind="$node2" \
    stress-ng --"$s2" "$w2" --timeout "$DURATION" $extra2 &
  local p2=$!

  set +e
  wait "$p1"; local rc1=$?
  wait "$p2"; local rc2=$?
  set -e

  kill -TERM -- "-$p1" 2>/dev/null || true
  kill -TERM -- "-$p2" 2>/dev/null || true
  sleep 0.2
  kill -KILL -- "-$p1" 2>/dev/null || true
  kill -KILL -- "-$p2" 2>/dev/null || true

  sleep "$COOLDOWN_SEC"
  if (( rc1 != 0 || rc2 != 0 )); then
    echo "[WARN] numa-pair exit rc1=$rc1 rc2=$rc2 (continuing)"
  fi
}

# ============================================================
# Topology helpers (PACK / SPREAD / SMT-heavy / cross-socket)
# ============================================================
declare -A core_to_cpus=()   # "socket:core" -> "cpu0,cpu1"
declare -A node_to_cpus=()   # node -> "cpu,cpu,..."
declare -A node_to_cores=()  # node -> "socket:core socket:core ..."

build_topology_maps() {
  mapfile -t CPU_ROWS < <(lscpu -p=CPU,CORE,SOCKET,NODE 2>/dev/null | sed 's/#.*//' | sed '/^\s*$/d' || true)
  ((${#CPU_ROWS[@]}==0)) && return 1

  for row in "${CPU_ROWS[@]}"; do
    IFS=, read -r cpu core sock node <<< "$row"
    [[ "$node" == "-1" ]] && node=0
    local key="${sock}:${core}"

    core_to_cpus[$key]="${core_to_cpus[$key]:+${core_to_cpus[$key]},}${cpu}"
    node_to_cpus[$node]="${node_to_cpus[$node]:+${node_to_cpus[$node]},}${cpu}"

    if [[ " ${node_to_cores[$node]:-} " != *" $key "* ]]; then
      node_to_cores[$node]="${node_to_cores[$node]:+${node_to_cores[$node]} }$key"
    fi
  done
  return 0
}

cpuset_pack() { # node, nthreads
  local node="$1" n="$2"
  IFS=, read -r -a cpus <<< "${node_to_cpus[$node]:-}"
  unset IFS
  if ((${#cpus[@]}==0)); then echo "0"; return; fi
  local out=("${cpus[@]:0:$n}")
  IFS=,; echo "${out[*]}"; unset IFS
}

cpuset_spread_cores_first_thread() { # node, nthreads (one HW thread per physical core)
  local node="$1" n="$2"
  local out=()
  local count=0
  local cores="${node_to_cores[$node]:-}"
  if [[ -z "$cores" ]]; then echo "0"; return; fi

  for key in $cores; do
    local first="${core_to_cpus[$key]%%,*}"
    out+=("$first"); ((count++))
    ((count>=n)) && break
  done
  IFS=,; echo "${out[*]}"; unset IFS
}

cpuset_smt_heavy() { # node, nthreads (fill siblings before moving to next core)
  local node="$1" n="$2"
  local out=()
  local count=0
  local cores="${node_to_cores[$node]:-}"
  if [[ -z "$cores" ]]; then echo "0"; return; fi

  for key in $cores; do
    IFS=, read -r -a sibs <<< "${core_to_cpus[$key]}"
    unset IFS
    for c in "${sibs[@]}"; do
      out+=("$c"); ((count++))
      ((count>=n)) && break 2
    done
  done
  IFS=,; echo "${out[*]}"; unset IFS
}

run_stressor_cpuset() {
  local s="$1" w="$2" cpuset="$3" mode="$4"
  if ! has_stressor "$s"; then
    echo "[SKIP] stressor '$s' not supported by this stress-ng build"
    return 0
  fi
  [[ -z "$cpuset" ]] && cpuset="0"
  local extra; extra="$(stressor_args "$s")"
  # shellcheck disable=SC2086
  run_grouped "topo:$mode $s w=$w cpuset=$cpuset" \
    stress-ng --"$s" "$w" --taskset "$cpuset" --timeout "$DURATION" $extra
}

# ============================================================
# PHASES
# ============================================================

echo ""
echo "[PHASE 0] idle baseline"
sleep "$COOLDOWN_SEC"

echo ""
echo "[PHASE 1] single stressors (dense-low/coarse-high worker sweep)"
for s in "${stressors[@]}"; do
  for w in "${worker_counts[@]}"; do
    run_stressor "$s" "$w"
  done
done

echo ""
echo "[PHASE 2] DL-like mixes (compute + memory) to help BERT/CNN-training regimes"
mix_w="${worker_counts[-1]}"
mix_w2=$(( mix_w / 2 ))
(( mix_w2 < 1 )) && mix_w2=1

# Always-available mix
run_two_stressors matrix "$mix_w2" vm "$mix_w2"

# Optional: matrix/cpu + (stream/memrate) if present
for mems in "${dl_mem_bw_candidates[@]}"; do
  if has_stressor "$mems"; then
    run_two_stressors matrix "$mix_w2" "$mems" "$mix_w2"
    run_two_stressors cpu    "$mix_w2" "$mems" "$mix_w2"
  fi
done

# Crypto-ish + memory
run_two_stressors ipsec-mb "$mix_w2" vm "$mix_w2"

echo ""
echo "[PHASE 3] curated pairs (representative mixes; avoids NxN explosion)"
pairs=(
  "cpu io"
  "cpu aio"
  "cpu hdd"
  "cpu sock"
  "cpu pipe"
  "cpu pthread"
  "cpu sem"
  "matrix cache"
  "matrix malloc"
  "vm cache"
  "vm sock"
  "vm pipe"
  "fork pthread"
  "switch pthread"
  "lockbus pthread"
)
for p in "${pairs[@]}"; do
  read -r s1 s2 <<< "$p"
  run_two_stressors "$s1" "$mix_w2" "$s2" "$mix_w2"
done

echo ""
echo "[PHASE 4] NUMA locality / remote-memory effects"
if [[ "$ENABLE_NUMA" == "1" ]] && ((${#numa_nodes[@]} >= 2)); then
  n0="${numa_nodes[0]}"
  n1="${numa_nodes[1]}"

  run_stressor_numa matrix "$mix_w2" "$n0" "$n0"
  run_stressor_numa vm     "$mix_w2" "$n0" "$n0"
  run_stressor_numa matrix "$mix_w2" "$n0" "$n1"
  run_stressor_numa cpu    "$mix_w2" "$n0" "$n1"
  run_pair_numa_split matrix "$mix_w2" "$n0" vm "$mix_w2" "$n1"
else
  echo "[INFO] skipping NUMA phase (single node or disabled)"
fi

echo ""
echo "[PHASE 5] pinned single-core load sweep (DVFS/turbo coverage)"
max_cores="$(nproc --all)"
pin_cores=(0)
for n in "${numa_nodes[@]}"; do
  pin_cores+=("$(first_core_of_node "$n")")
done
# uniq
IFS=$'\n' pin_cores=($(printf "%s\n" "${pin_cores[@]}" | sort -n | uniq))
unset IFS

for core in "${pin_cores[@]}"; do
  (( core >= 0 && core < max_cores )) || continue
  for load in "${cpu_loads[@]}"; do
    run_grouped "pin:cpu core=$core load=$load" \
      stress-ng --cpu 1 --taskset "$core" --timeout "$DURATION" --cpu-load "$load"

    if has_stressor ipsec-mb; then
      run_grouped "pin:ipsec-mb core=$core" \
        stress-ng --ipsec-mb 1 --taskset "$core" --timeout "$DURATION"
    fi

    if has_stressor matrix; then
      # shellcheck disable=SC2046
      run_grouped "pin:matrix core=$core" \
        stress-ng --matrix 1 --taskset "$core" --timeout "$DURATION" $(stressor_args matrix)
    fi
  done
done

echo ""
echo "[PHASE 6] topology diversity (PACK / SPREAD / SMT-heavy / cross-socket spread)"
if [[ "$ENABLE_TOPOLOGY" == "1" ]] && command -v lscpu >/dev/null 2>&1 && build_topology_maps; then
  topo_stressors=(cpu matrix vm ipsec-mb cache)

  # Keep topology sweep bounded: representative worker counts
  topo_workers=(1 2 4 8 16 32 64)
  topo_workers=($(for w in "${topo_workers[@]}"; do (( w <= MAX_WORKERS )) && echo "$w"; done))

  node0="${numa_nodes[0]}"
  node1="${numa_nodes[1]:-$node0}"
  dual_node=0
  ((${#numa_nodes[@]} >= 2)) && dual_node=1

  for s in "${topo_stressors[@]}"; do
    has_stressor "$s" || { echo "[SKIP] topo stressor $s unsupported"; continue; }
    for w in "${topo_workers[@]}"; do
      (( w >= 1 && w <= MAX_WORKERS )) || continue

      run_stressor_cpuset "$s" "$w" "$(cpuset_pack "$node0" "$w")" "PACK(node${node0})"
      run_stressor_cpuset "$s" "$w" "$(cpuset_spread_cores_first_thread "$node0" "$w")" "SPREAD(node${node0})"
      run_stressor_cpuset "$s" "$w" "$(cpuset_smt_heavy "$node0" "$w")" "SMT-heavy(node${node0})"

      if (( dual_node == 1 )); then
        # Cross-node spread: half on node0, half on node1 (best-effort)
        w0=$(( (w+1)/2 )); w1=$(( w/2 ))
        c0="$(cpuset_spread_cores_first_thread "$node0" "$w0")"
        c1="$(cpuset_spread_cores_first_thread "$node1" "$w1")"
        run_stressor_cpuset "$s" "$w" "${c0}${c1:+,}${c1}" "CROSS(node${node0}+node${node1})"
      fi
    done
  done
else
  echo "[INFO] skipping topology phase (disabled or cannot parse lscpu topology)"
fi

echo ""
echo "[DONE] All stress tests completed."

