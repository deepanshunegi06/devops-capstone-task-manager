#!/usr/bin/env bash
# Smoke test a running container (or a URL) end to end: health, register, CRUD, metrics.
# Usage: scripts/smoke-test.sh <container-name>      (runs curl inside the Docker network namespace)
#        scripts/smoke-test.sh --url http://localhost:8080
set -euo pipefail

if [[ "${1:-}" == "--url" ]]; then
  BASE="$2"
  req() { curl -fsS "$@"; }
else
  CONTAINER="${1:?container name required}"
  BASE="http://127.0.0.1:5000"
  req() { docker run --rm --network "container:${CONTAINER}" curlimages/curl:8.10.1 -fsS "$@"; }
fi

echo "==> Waiting for ${BASE}/health/ready"
for i in $(seq 1 30); do
  if req "${BASE}/health/ready" >/dev/null 2>&1; then break; fi
  [[ $i -eq 30 ]] && { echo "app never became ready"; exit 1; }
  sleep 2
done

USER="smoke$(date +%s)"
echo "==> Registering ${USER}"
TOKEN=$(req -X POST -H 'Content-Type: application/json' \
  -d "{\"username\":\"${USER}\",\"password\":\"smoke-pass-123\"}" "${BASE}/api/auth/register" \
  | sed -E 's/.*"token": ?"([^"]+)".*/\1/')

echo "==> Creating a task"
req -X POST -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
  -d '{"title":"smoke test task","priority":"high"}' "${BASE}/api/tasks" | grep -q '"smoke test task"'

echo "==> Listing tasks"
req -H "Authorization: Bearer ${TOKEN}" "${BASE}/api/tasks" | grep -Eq '"count": ?1'

echo "==> Metrics"
req "${BASE}/metrics" | grep -q taskmanager_http_requests_total

echo "SMOKE TEST PASSED"
