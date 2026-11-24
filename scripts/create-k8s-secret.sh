#!/usr/bin/env bash
# Create the application Secret with random values (never committed to Git).
# Prints the generated admin password once so you can log in.
set -euo pipefail
NS="${1:-taskmanager}"

kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

if kubectl -n "$NS" get secret taskmanager-secret >/dev/null 2>&1; then
  echo "Secret taskmanager-secret already exists in $NS - leaving it unchanged."
  exit 0
fi

ADMIN_PASSWORD="$(openssl rand -hex 12)"
kubectl -n "$NS" create secret generic taskmanager-secret \
  --from-literal=POSTGRES_USER=taskmanager \
  --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 16)" \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)" \
  --from-literal=ADMIN_PASSWORD="$ADMIN_PASSWORD"

echo "Secret created. Admin login -> username: admin  password: $ADMIN_PASSWORD"
