#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl apply -f . --recursive
kubectl get pods
