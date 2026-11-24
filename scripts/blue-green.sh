#!/usr/bin/env bash
# Blue-green helper (GitOps way): edits the manifests in Git; ArgoCD applies them.
#   scripts/blue-green.sh status                 show live/idle colour and their images
#   scripts/blue-green.sh deploy <tag>           put <tag> on the idle colour
#   scripts/blue-green.sh switch                 send live traffic to the idle colour
#   scripts/blue-green.sh rollback               switch back (instant - old pods are still running)
# Add --push to commit and push the change (otherwise it only edits the files).
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="${DOCKER_REPO:-deepanshunegi06/taskmanager}"
PUSH=false
ARGS=()
for a in "$@"; do [[ "$a" == "--push" ]] && PUSH=true || ARGS+=("$a"); done
set -- "${ARGS[@]}"

need() { command -v "$1" >/dev/null || { echo "missing tool: $1"; exit 1; }; }
need yq

live()  { yq '.spec.selector.color' k8s/app/service.yaml; }
idle()  { [[ "$(live)" == "blue" ]] && echo green || echo blue; }
image() { yq '.spec.template.spec.containers[0].image' "k8s/app/deployment-$1.yaml"; }

commit() {
  if $PUSH; then
    git add k8s/app && git commit -m "$1" && git push
  else
    echo "(files edited - review with 'git diff', commit and push to let ArgoCD apply it)"
  fi
}

case "${1:-status}" in
  status)
    echo "LIVE : $(live)  -> $(image "$(live)")"
    echo "IDLE : $(idle)  -> $(image "$(idle)")"
    ;;
  deploy)
    TAG="${2:?usage: deploy <tag>}"; TARGET="$(idle)"
    yq -i ".spec.template.spec.containers[0].image = \"${REPO}:${TAG}\"" "k8s/app/deployment-${TARGET}.yaml"
    yq -i "(.spec.template.spec.containers[0].env[] | select(.name == \"APP_VERSION\")).value = \"${TAG}\"" "k8s/app/deployment-${TARGET}.yaml"
    echo "deployed ${TAG} to idle colour ${TARGET} (test it at http://preview.taskmanager.local)"
    commit "deploy ${TAG} to ${TARGET}"
    ;;
  switch|rollback)
    FROM="$(live)"; TO="$(idle)"
    yq -i ".spec.selector.color = \"${TO}\"" k8s/app/service.yaml
    yq -i ".spec.selector.color = \"${FROM}\"" k8s/app/service-preview.yaml
    echo "live traffic: ${FROM} -> ${TO}"
    commit "blue-green: switch live traffic ${FROM} -> ${TO}"
    ;;
  *) echo "usage: $0 status|deploy <tag>|switch|rollback [--push]"; exit 1 ;;
esac
