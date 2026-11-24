# Git workflow (Phase 1)

Branching model (simplified Git Flow):

```
main      ── production; every commit is deployable, Jenkins deploys from here
develop   ── integration branch
feature/* ── one branch per feature, merged into develop with --no-ff
```

Branches used in this project:

| Branch | Content |
|---|---|
| `feature/flask-app` | application code + tests |
| `feature/docker` | Dockerfile, Compose, Nginx |
| `feature/jenkins-ci` | Jenkinsfile, Jenkins/SonarQube as code |
| `feature/kubernetes` | K8s manifests, Helm chart, ArgoCD, blue-green scripts |
| `feature/infra-automation` | Ansible + Terraform |
| `feature/observability` | Prometheus, Grafana, EFK, log analyzer |
| `feature/footer-version` / `feature/footer-health` | two branches that edited the same line - used to demonstrate a merge conflict |

## Merge conflict demonstration

Both footer branches changed the footer line in `taskmanager/templates/base.html`:

```
<<<<<<< HEAD
    v{{ app_version }} · <span class="color-tag color-{{ deploy_color }}">{{ deploy_color }}</span> deployment
=======
    Task Manager v{{ app_version }} · <a href="/health/ready">health</a>
>>>>>>> feature/footer-health
```

Resolution: keep both ideas - the version, the deployment colour (needed for the blue-green demo) and the
health link - then `git add` + `git commit`. The resolution commit is visible with:

```bash
git log --oneline --graph --all
git log --merges
git show <merge-commit>      # shows the combined resolution
```

Useful commands for the viva:

```bash
git branch -a                          # all branches
git log --oneline --graph --decorate   # visual history
git diff develop..main                 # what is about to be released
```
