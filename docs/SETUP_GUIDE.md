# Setup & demo runbook

Follow these steps in order to bring up the whole pipeline and collect the screenshots for the report.
Two environments are supported:

* **Laptop lab** (free): Docker Desktop + minikube. Jenkins and SonarQube run in Docker.
* **Cloud** (bonus): Terraform creates AWS EC2 machines and Ansible turns them into a kubeadm cluster.

Prerequisites: Git, Docker, kubectl, minikube, Helm, (for cloud) Terraform ≥ 1.5, Ansible ≥ 2.15, AWS CLI.

---

## 1. Git (Phase 1)

```bash
git clone https://github.com/deepanshunegi06/devops-capstone-task-manager.git
cd devops-capstone-task-manager
git log --oneline --graph --all        # 📸 branch + merge history
git log --merges                       # 📸 includes the merge-conflict resolution commit
```

## 2. Run the tests and the app locally

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
pytest --cov                           # 📸 33 passed, 97% coverage
```

## 3. Docker (Phase 3)

```bash
cp env.example .env                    # set real passwords
docker build -t deepanshunegi06/taskmanager:1.0.0 .
docker images | grep taskmanager       # 📸 image
docker compose up -d --build
docker compose ps                      # 📸 app, db, nginx all "healthy"/"running"
open http://localhost:8080             # 📸 login page, dashboard
scripts/smoke-test.sh --url http://localhost:8080
```

## 4. Jenkins + SonarQube (Phases 2 and 9)

```bash
cp jenkins/env.example jenkins/.env    # fill Docker Hub token, GitHub PAT, passwords
cp ~/.kube/config jenkins/kubeconfig   # (minikube: use `minikube kubectl -- config view --flatten`)
docker compose -f jenkins/docker-compose.yml --env-file jenkins/.env up -d --build
```

1. SonarQube <http://localhost:9000> (admin/admin → change) → *My Account → Security* → generate a
   token → put it in `jenkins/.env` as `SONAR_TOKEN` → `docker compose ... up -d` again.
2. SonarQube → *Administration → Configuration → Webhooks* → add `http://jenkins:8080/sonarqube-webhook/`
   (needed by the Quality Gate stage).
3. Jenkins <http://localhost:8081> - the multibranch job **taskmanager** already exists (JCasC).
4. Expose Jenkins to GitHub: `ngrok http 8081`, set `JENKINS_URL` to the ngrok URL, then in GitHub
   *Settings → Webhooks* add `<ngrok-url>/github-webhook/` (content type JSON, "just the push event").
5. Push any commit → the pipeline starts automatically. 📸 Stage view, test report, coverage report,
   SonarQube dashboard + quality gate, Trivy report, credentials page (values hidden), RBAC roles page.

## 5. Kubernetes + GitOps (Phases 4, 10, 11)

```bash
minikube start --cpus 4 --memory 8g
minikube addons enable ingress
minikube addons enable metrics-server
scripts/create-k8s-secret.sh                        # prints the admin password once

kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v2.13.1/manifests/install.yaml
kubectl -n argocd rollout status deploy/argocd-server
kubectl apply -f argocd/project.yaml -f argocd/application.yaml

kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
kubectl -n argocd port-forward svc/argocd-server 8443:443   # https://localhost:8443  📸 app tree "Synced/Healthy"

kubectl -n taskmanager get all,cm,secret,pv,pvc,hpa,ingress     # 📸
echo "$(minikube ip) taskmanager.local preview.taskmanager.local" | sudo tee -a /etc/hosts
open http://taskmanager.local                                    # 📸 footer shows "blue deployment"
```

### Scaling, rolling update, rollback (Phase 4)

```bash
argocd app set taskmanager --sync-policy none      # pause GitOps self-heal for the manual demo
scripts/k8s-demo.sh scale                          # 📸 5 pods
NEW_TAG=1.1.0 scripts/k8s-demo.sh rolling-update   # 📸 rollout status + history
scripts/k8s-demo.sh rollback                       # 📸 back to the previous revision
argocd app set taskmanager --sync-policy automated --self-heal --auto-prune
```

### Blue-Green (Phase 10)

```bash
scripts/blue-green.sh status
scripts/blue-green.sh deploy 1.1.0 --push          # ArgoCD rolls green to 1.1.0
open http://preview.taskmanager.local              # 📸 footer "v1.1.0 · green"
scripts/blue-green.sh switch --push                # live traffic -> green
open http://taskmanager.local                      # 📸 footer now "green"
scripts/blue-green.sh rollback --push              # instant rollback to blue
```
(In the full pipeline, Jenkins does the `deploy` step automatically and asks for approval before `switch`.)

### Helm alternative (bonus)
```bash
helm template taskmanager helm/taskmanager | less
helm upgrade --install taskmanager helm/taskmanager -n taskmanager-helm --create-namespace
```

## 6. Monitoring (Phase 7)

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
kubectl create namespace monitoring
kubectl -n monitoring create secret generic grafana-admin \
  --from-literal=admin-user=admin --from-literal=admin-password="$(openssl rand -hex 12)"
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  -n monitoring -f monitoring/k8s/kube-prometheus-values.yaml
kubectl apply -f monitoring/k8s/
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80
```
Open Grafana → *Task Manager → Task Manager - Overview*. 📸 CPU, memory, container health, request
rate, latency, error rate, tasks by status. Prometheus → *Status → Targets* 📸, *Alerts* 📸.

Docker Compose variant: `docker compose -f docker-compose.yml -f monitoring/docker-compose.monitoring.yml up -d`.

## 7. Logging (Phase 8)

```bash
kubectl apply -f logging/k8s/
kubectl -n logging rollout status ds/fluentd
kubectl -n logging port-forward svc/kibana 5601:5601
```
Kibana → *Stack Management → Data views* → create `taskmanager-app-*`, `k8s-containers-*`, `k8s-node-*`.
📸 Discover with app logs filtered by `level: ERROR` or `request_id`, container logs from other
namespaces, kubelet logs.

AI log analysis (bonus):
```bash
kubectl -n logging port-forward svc/elasticsearch 9200:9200 &
python scripts/log_analyzer.py --es http://localhost:9200 --index 'taskmanager-app-*' --minutes 60
```

## 8. Terraform + Ansible on AWS (Phases 5, 6, bonus cloud)

```bash
cd terraform
terraform init
terraform plan  -var-file=environments/dev.tfvars -var="admin_cidr=$(curl -s ifconfig.me)/32"   # 📸
terraform apply -var-file=environments/dev.tfvars -var="admin_cidr=$(curl -s ifconfig.me)/32"   # 📸 outputs
cd ../ansible
ansible-galaxy collection install -r requirements.yml
cp group_vars/all/vault.yml.example group_vars/all/vault.yml && ansible-vault encrypt group_vars/all/vault.yml
ansible-playbook -i inventory/generated.ini site.yml --ask-vault-pass                                   # 📸 PLAY RECAP
ansible-playbook -i inventory/generated.ini playbooks/configure.yml --ask-vault-pass                    # 📸 idempotent: changed=0
# ...demo...
cd ../terraform && terraform destroy -var-file=environments/dev.tfvars -var="admin_cidr=$(curl -s ifconfig.me)/32"
```

## Screenshot checklist for the report

- [ ] `git log --graph` and the merge-conflict resolution commit
- [ ] pytest + coverage output
- [ ] Jenkins stage view (all green), test trend, coverage report, credentials page, role strategy
- [ ] SonarQube project dashboard + Quality Gate passed
- [ ] Trivy scan output
- [ ] `docker images`, `docker compose ps`
- [ ] App: login, dashboard, new task, mobile view (already in `docs/screenshots/`)
- [ ] `kubectl get all,cm,secret,pv,pvc,hpa,ingress -n taskmanager`
- [ ] scaling to 5 pods, rollout history, rollback
- [ ] ArgoCD application tree (Synced / Healthy) and a sync triggered by a Git commit
- [ ] blue-green: preview on green, switch, footer colour change
- [ ] Grafana dashboard, Prometheus targets + alerts
- [ ] Kibana Discover with app / container / kubelet logs
- [ ] `terraform plan` / `apply` outputs, `ansible-playbook` PLAY RECAP

## Demo video outline (10-15 min)

1. (1 min) Problem + architecture diagram
2. (1 min) App tour: register, login, CRUD, mobile view, REST call with curl
3. (2 min) Git branches + merge-conflict commit; push a change
4. (3 min) Jenkins pipeline running automatically: tests, SonarQube gate, Trivy, image push, GitOps commit
5. (2 min) ArgoCD syncs; preview on idle colour; approve; traffic switches; instant rollback
6. (1 min) Scaling / rolling update / rollback commands
7. (2 min) Grafana dashboard + Kibana logs + log analyzer
8. (1 min) Terraform + Ansible run, wrap-up
