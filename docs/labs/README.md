# DevOps lab submission records

Prepared for Deepanshu Negi (2301350026), ENSP461.

Each PDF answers the matching question in the 27 November live session. Observed results are separated from configuration and reproduction steps.

| Lab | Question | Topic | File |
|---|---|---|---|
| 1 | 1 | Record all commands | [Lab_1_Q01.pdf](Lab_1_Q01.pdf) |
| 1 | 2 | CI/CD workflow report | [Lab_1_Q02.pdf](Lab_1_Q02.pdf) |
| 1 | 3 | Automated application deployment | [Lab_1_Q03.pdf](Lab_1_Q03.pdf) |
| 1 | 4 | Install and configure Git and Jenkins | [Lab_1_Q04.pdf](Lab_1_Q04.pdf) |
| 1 | 5 | Version control with Git | [Lab_1_Q05.pdf](Lab_1_Q05.pdf) |
| 1 | 6 | Basic Jenkins CI/CD pipeline | [Lab_1_Q06.pdf](Lab_1_Q06.pdf) |
| 1 | 7 | Jenkinsfile stages | [Lab_1_Q07.pdf](Lab_1_Q07.pdf) |
| 2 | 1 | Kubernetes application deployment | [Lab_2_Q01.pdf](Lab_2_Q01.pdf) |
| 2 | 2 | Rolling updates, rollback and scaling | [Lab_2_Q02.pdf](Lab_2_Q02.pdf) |
| 2 | 3 | Containerization and orchestration report | [Lab_2_Q03.pdf](Lab_2_Q03.pdf) |
| 2 | 4 | Dockerfile, image and container behavior | [Lab_2_Q04.pdf](Lab_2_Q04.pdf) |
| 2 | 5 | Manage Docker containers and images | [Lab_2_Q05.pdf](Lab_2_Q05.pdf) |
| 2 | 6 | Docker storage | [Lab_2_Q06.pdf](Lab_2_Q06.pdf) |
| 2 | 7 | Docker networking | [Lab_2_Q07.pdf](Lab_2_Q07.pdf) |
| 2 | 8 | Continuous deployment to Kubernetes | [Lab_2_Q08.pdf](Lab_2_Q08.pdf) |
| 2 | 9 | Docker and Kubernetes experiment record | [Lab_2_Q09.pdf](Lab_2_Q09.pdf) |
| 3 | 1 | Ansible configuration automation | [Lab_3_Q01.pdf](Lab_3_Q01.pdf) |
| 3 | 2 | Terraform infrastructure provisioning | [Lab_3_Q02.pdf](Lab_3_Q02.pdf) |
| 3 | 3 | Centralized logging | [Lab_3_Q03.pdf](Lab_3_Q03.pdf) |
| 3 | 4 | DevSecOps pipeline | [Lab_3_Q04.pdf](Lab_3_Q04.pdf) |
| 3 | 5 | Prometheus and Grafana monitoring | [Lab_3_Q05.pdf](Lab_3_Q05.pdf) |
| 3 | 6 | Feature flags, load and Selenium tests | [Lab_3_Q06.pdf](Lab_3_Q06.pdf) |
| 3 | 7 | Monitoring, logging and DevSecOps report | [Lab_3_Q07.pdf](Lab_3_Q07.pdf) |
| 4 | 1 | Disaster recovery | [Lab_4_Q01.pdf](Lab_4_Q01.pdf) |
| 4 | 2 | Automated testing gates | [Lab_4_Q02.pdf](Lab_4_Q02.pdf) |
| 4 | 3 | Blue-green deployment | [Lab_4_Q03.pdf](Lab_4_Q03.pdf) |
| 4 | 4 | GitOps delivery | [Lab_4_Q04.pdf](Lab_4_Q04.pdf) |
| 4 | 5 | Advanced deployment strategies report | [Lab_4_Q05.pdf](Lab_4_Q05.pdf) |
| 4 | 6 | Secret management | [Lab_4_Q06.pdf](Lab_4_Q06.pdf) |
| 4 | 7 | Canary deployment | [Lab_4_Q07.pdf](Lab_4_Q07.pdf) |

## Verified results

- Jenkins build #2: SUCCESS; source checkout, Bandit, pytest, deployment readiness and archived reports.
- Unit/integration suite: 95 passed; 98.56% coverage with the added feature-flag checks.
- Load verification after worker-pool fix: 1,000/1,000 readiness requests succeeded.
- Minikube: manifest deployment, 3-replica scaling, rolling update, rollback and Service request verified.
- ArgoCD: Synced/Healthy; manual replica drift returned to Git desired state in 2.21 seconds.
- Blue-green: 103 sampled requests during switching, 0 errors.
- Canary: green responses 22/200 at 10%, 95/200 at 50%, 200/200 at 100%.
- Recovery: source and restored database both contained 109 tasks; 0.463 seconds for this small local dump/restore/check run.
- Final failover sample: 30/30 requests served by green.
- Terraform: local replicas provisioned and scaled from 2 to 3; Ansible second run changed=0.
- Fluentd parsed and Elasticsearch indexed 100 real application log records.

## Limits and findings

- Ubuntu Git is verified; Jenkins ran in a Linux container rather than an Ubuntu systemd service.
- Exact Logstash ingestion was not verified; the verified logging path is EFK.
- Direct-dependency audit found Flask advisory PYSEC-2026-2151 (3.0.3; fix listed as 3.1.3).
- Bandit: three low findings, zero medium/high. Local lab controller/plugin versions should be upgraded before production.
- AWS resources were not created; local Terraform avoids cloud cost. No production deployment or webhook delivery is claimed.
- Runtime credentials, vault keys, state files, raw database dumps and personal browsing data are excluded.
