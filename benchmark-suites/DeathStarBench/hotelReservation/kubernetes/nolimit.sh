#!/bin/bash
set -euo pipefail

MAX_PODS=250
NODES=$(kubectl get nodes -o name | sed 's|^node/||')

for NODE in $NODES; do
  echo "Setting maxPods=$MAX_PODS on $NODE"
  ssh -o StrictHostKeyChecking=no "$NODE" "
    sudo sed -i '/^maxPods:/d' /var/lib/kubelet/config.yaml
    echo 'maxPods: $MAX_PODS' | sudo tee -a /var/lib/kubelet/config.yaml > /dev/null
    sudo systemctl restart kubelet
  "
done

