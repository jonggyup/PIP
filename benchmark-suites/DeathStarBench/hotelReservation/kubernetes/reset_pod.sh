#!/bin/bash
kubectl delete -f . --recursive
kubectl get all

kubectl apply -f . --recursive
kubectl get pods
