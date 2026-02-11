#!/usr/bin/env bash
# hpa_roundtrip.sh – set every Deployment-HPA in “default” to 1 replica,
#                    wait for rollout, then restore the saved values.
set -euo pipefail
NS=default

declare -A MIN MAX        # Bash ≥4 associative arrays

# ─── shrink to 1 replica ─────────────────────────────────────────────────────
for H in $(kubectl -n "$NS" get hpa -o name); do
  [[ $(kubectl -n "$NS" get "$H" -o jsonpath='{.spec.scaleTargetRef.kind}') != "Deployment" ]] && continue

  N=$(basename "$H")
  MIN[$N]=$(kubectl -n "$NS" get "$H" -o jsonpath='{.spec.minReplicas}')
  MAX[$N]=$(kubectl -n "$NS" get "$H" -o jsonpath='{.spec.maxReplicas}')

  # set both to 1
  kubectl -n "$NS" patch "$H" --type=merge -p '{"spec":{"minReplicas":1,"maxReplicas":1}}'

  DEP=$(kubectl -n "$NS" get "$H" -o jsonpath='{.spec.scaleTargetRef.name}')
  kubectl -n "$NS" scale deployment "$DEP" --replicas=1
done

# wait until each Deployment has exactly 1 ready ReplicaSet
for D in $(kubectl -n "$NS" get deploy -o name); do
  kubectl -n "$NS" rollout status "$D" --timeout=120s
done

# ─── restore original settings ───────────────────────────────────────────────
for N in "${!MIN[@]}"; do
  kubectl -n "$NS" patch "hpa/$N" --type=merge \
    -p='{"spec":{"minReplicas":'"${MIN[$N]}"',"maxReplicas":'"${MAX[$N]}"'}}'
done
echo "[done] HPAs restored; clean benchmark state ready."


for d in frontend geo jaeger memcached-profile memcached-rate memcached-reserve profile rate recommendation reservation search user; do
  kubectl patch hpa $d --type='merge' -p '{
    "spec":{
      "minReplicas":1,
      "maxReplicas":180,
      "metrics":[{"type":"Resource","resource":{"name":"cpu","target":{"type":"Utilization","averageUtilization":50}}}]
    }
  }'
done


