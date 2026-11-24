#!/usr/bin/env bash
# Wait until a Deployment's pod template uses the expected image (i.e. ArgoCD has synced Git).
# Usage: scripts/wait-for-image.sh <namespace> <deployment> <image> [timeout-seconds]
set -euo pipefail
NS="$1"; DEPLOY="$2"; IMAGE="$3"; TIMEOUT="${4:-300}"
END=$(( $(date +%s) + TIMEOUT ))
while (( $(date +%s) < END )); do
  CURRENT=$(kubectl -n "$NS" get deployment "$DEPLOY" -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true)
  if [[ "$CURRENT" == "$IMAGE" ]]; then
    echo "${DEPLOY} now uses ${IMAGE}"
    exit 0
  fi
  echo "waiting for ArgoCD sync (${DEPLOY}: ${CURRENT:-<none>} -> ${IMAGE})"
  sleep 10
done
echo "timed out waiting for ${DEPLOY} to use ${IMAGE}" >&2
exit 1
