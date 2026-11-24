#!/usr/bin/env bash
# Phase 4 demonstrations: scaling, rolling update and rollback.
#
# ArgoCD self-heal would immediately revert these manual changes (that is the point of GitOps),
# so pause auto-sync first and resume it afterwards:
#   argocd app set taskmanager --sync-policy none        # before
#   argocd app set taskmanager --sync-policy automated --self-heal --auto-prune   # after
#
# Usage: scripts/k8s-demo.sh scale|rolling-update|rollback|history|all [color]
set -euo pipefail
NS=taskmanager
COLOR="${2:-blue}"
DEPLOY="taskmanager-${COLOR}"
REPO="${DOCKER_REPO:-deepanshunegi06/taskmanager}"

banner() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

scale() {
  banner "Scaling ${DEPLOY} to 5 replicas"
  kubectl -n "$NS" scale deployment "$DEPLOY" --replicas=5
  kubectl -n "$NS" rollout status deployment "$DEPLOY" --timeout=120s
  kubectl -n "$NS" get pods -l "app=taskmanager,color=${COLOR}" -o wide
  banner "HPA status (auto scaling between 2 and 6)"
  kubectl -n "$NS" get hpa "$DEPLOY"
}

rolling_update() {
  local tag="${NEW_TAG:-1.1.0}"
  banner "Rolling update ${DEPLOY} -> ${REPO}:${tag} (maxSurge=1, maxUnavailable=0)"
  kubectl -n "$NS" set image deployment/"$DEPLOY" taskmanager="${REPO}:${tag}"
  kubectl -n "$NS" set env deployment/"$DEPLOY" APP_VERSION="$tag"
  kubectl -n "$NS" annotate deployment/"$DEPLOY" kubernetes.io/change-cause="update to ${tag}" --overwrite
  kubectl -n "$NS" rollout status deployment "$DEPLOY" --timeout=180s
  history
}

rollback() {
  banner "Rolling back ${DEPLOY} to the previous revision"
  kubectl -n "$NS" rollout undo deployment/"$DEPLOY"
  kubectl -n "$NS" rollout status deployment "$DEPLOY" --timeout=180s
  kubectl -n "$NS" get deployment "$DEPLOY" -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
  history
}

history() {
  banner "Rollout history"
  kubectl -n "$NS" rollout history deployment/"$DEPLOY"
}

case "${1:-all}" in
  scale) scale ;;
  rolling-update) rolling_update ;;
  rollback) rollback ;;
  history) history ;;
  all) scale; rolling_update; rollback ;;
  *) echo "usage: $0 scale|rolling-update|rollback|history|all [blue|green]"; exit 1 ;;
esac
