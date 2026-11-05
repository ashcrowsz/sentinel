#!/usr/bin/env bash
set -euo pipefail
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=servicelb --write-kubeconfig-mode=600" sh -
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
