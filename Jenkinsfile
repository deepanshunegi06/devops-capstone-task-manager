// =====================================================================================
//  Task Manager - CI/CD pipeline (ENSP461 DevOps capstone)
//
//  Trigger : GitHub webhook on every push (githubPush) + SCM polling fallback.
//  Flow    : checkout -> lint/SAST -> unit tests + coverage -> SonarQube + quality gate
//            -> package (wheel + Docker image) -> Hadolint/Trivy scan -> smoke test
//            -> push image -> GitOps: bump image tag of the *idle* colour in Git
//            -> ArgoCD syncs -> verify preview -> approve -> switch traffic (blue-green)
//
//  Jenkins credentials used (Manage Jenkins > Credentials) - nothing is hard-coded:
//    dockerhub-creds  (Username/Password)  Docker Hub user + access token
//    github-token     (Username/Password)  GitHub user + PAT with repo scope (GitOps push)
//    sonar-token      (Secret text)        configured inside the 'sonarqube' server entry
//    kubeconfig       (Secret file)        read-only kubeconfig used for preview checks
//    slack-webhook    (Secret text)        optional - Slack incoming webhook URL
// =====================================================================================

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 45, unit: 'MINUTES')
    }

    triggers {
        githubPush()                       // fires on every git push (webhook -> /github-webhook/)
        pollSCM('H/5 * * * *')             // fallback if the webhook cannot reach Jenkins
    }

    parameters {
        booleanParam(name: 'AUTO_PROMOTE', defaultValue: false,
                     description: 'Switch live traffic to the new colour without manual approval')
    }

    environment {
        APP_NAME     = 'taskmanager'
        DOCKER_REPO  = 'deepanshunegi06/taskmanager'
        GITOPS_REPO  = 'github.com/deepanshunegi06/devops-capstone-task-manager.git'
        K8S_NS       = 'taskmanager'
        PYTHONUNBUFFERED = '1'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.GIT_SHORT = sh(script: 'git rev-parse --short=7 HEAD', returnStdout: true).trim()
                    env.IMAGE_TAG = "${env.BUILD_NUMBER}-${env.GIT_SHORT}"
                    env.LAST_MSG  = sh(script: 'git log -1 --pretty=%B', returnStdout: true).trim()
                    // Commits made by this pipeline (GitOps tag bumps) must not re-trigger it.
                    env.SKIP_BUILD = env.LAST_MSG.contains('[skip ci]') ? 'true' : 'false'
                    if (env.SKIP_BUILD == 'true') {
                        currentBuild.description = 'GitOps commit - skipped'
                        echo 'Commit made by the pipeline itself; skipping.'
                    }
                }
            }
        }

        stage('Setup Python') {
            when { environment name: 'SKIP_BUILD', value: 'false' }
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --quiet --upgrade pip
                    pip install --quiet -r requirements-dev.txt build
                '''
            }
        }

        stage('Static checks') {
            when { environment name: 'SKIP_BUILD', value: 'false' }
            parallel {
                stage('Lint (flake8)') {
                    steps { sh '. .venv/bin/activate && flake8 taskmanager tests wsgi.py' }
                }
                stage('SAST (bandit)') {
                    steps {
                        sh '''
                            . .venv/bin/activate
                            mkdir -p reports
                            bandit -r taskmanager -f json -o reports/bandit.json || true
                            bandit -r taskmanager -ll    # fail on medium+ severity findings
                        '''
                    }
                }
                stage('Dockerfile lint (hadolint)') {
                    steps { sh 'hadolint --failure-threshold error Dockerfile' }
                }
            }
        }

        stage('Unit tests + coverage') {
            when { environment name: 'SKIP_BUILD', value: 'false' }
            steps {
                sh '''
                    . .venv/bin/activate
                    mkdir -p reports
                    pytest --junitxml=reports/junit.xml \
                           --cov --cov-report=xml:coverage.xml --cov-report=html:reports/coverage
                '''
            }
            post {
                always {
                    junit 'reports/junit.xml'
                    recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']],
                                   qualityGates: [[threshold: 85.0, metric: 'LINE', baseline: 'PROJECT']])
                    publishHTML(target: [reportDir: 'reports/coverage', reportFiles: 'index.html',
                                         reportName: 'Coverage Report', keepAll: true, allowMissing: true])
                }
            }
        }

        stage('SonarQube analysis') {
            when { environment name: 'SKIP_BUILD', value: 'false' }
            steps {
                withSonarQubeEnv('sonarqube') {          // server URL + token come from Jenkins config
                    sh "sonar-scanner -Dsonar.projectVersion=${env.IMAGE_TAG}"
                }
            }
        }

        stage('Quality gate') {
            when { environment name: 'SKIP_BUILD', value: 'false' }
            steps {
                timeout(time: 10, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Package') {
            when { environment name: 'SKIP_BUILD', value: 'false' }
            parallel {
                stage('Python wheel') {
                    steps {
                        sh '. .venv/bin/activate && python -m build --wheel --outdir dist/'
                        archiveArtifacts artifacts: 'dist/*.whl', fingerprint: true
                    }
                }
                stage('Docker image') {
                    steps {
                        sh """
                            docker build \
                              --build-arg APP_VERSION=${env.IMAGE_TAG} \
                              --build-arg GIT_COMMIT=${env.GIT_COMMIT} \
                              -t ${DOCKER_REPO}:${env.IMAGE_TAG} -t ${DOCKER_REPO}:latest .
                        """
                    }
                }
            }
        }

        stage('Image security scan (Trivy)') {
            when { environment name: 'SKIP_BUILD', value: 'false' }
            steps {
                sh """
                    mkdir -p reports
                    trivy image --no-progress --format table --output reports/trivy.txt ${DOCKER_REPO}:${env.IMAGE_TAG}
                    trivy image --no-progress --exit-code 1 --severity CRITICAL --ignore-unfixed ${DOCKER_REPO}:${env.IMAGE_TAG}
                    trivy config --exit-code 0 --severity HIGH,CRITICAL k8s/ > reports/trivy-k8s.txt
                """
            }
            post { always { archiveArtifacts artifacts: 'reports/trivy*.txt', allowEmptyArchive: true } }
        }

        stage('Container smoke test') {
            when { environment name: 'SKIP_BUILD', value: 'false' }
            steps {
                sh """
                    docker rm -f tm-smoke 2>/dev/null || true
                    docker run -d --name tm-smoke -e SECRET_KEY=smoke -e DATABASE_URL=sqlite:////tmp/smoke.db \
                        ${DOCKER_REPO}:${env.IMAGE_TAG}
                    ./scripts/smoke-test.sh tm-smoke
                """
            }
            post { always { sh 'docker rm -f tm-smoke || true' } }
        }

        stage('Push image') {
            when { allOf { branch 'main'; environment name: 'SKIP_BUILD', value: 'false' } }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                                  usernameVariable: 'DOCKER_USER',
                                                  passwordVariable: 'DOCKER_TOKEN')]) {
                    sh '''
                        echo "$DOCKER_TOKEN" | docker login -u "$DOCKER_USER" --password-stdin
                        docker push ${DOCKER_REPO}:${IMAGE_TAG}
                        docker push ${DOCKER_REPO}:latest
                        docker logout
                    '''
                }
            }
        }

        stage('GitOps: deploy to idle colour') {
            when { allOf { branch 'main'; environment name: 'SKIP_BUILD', value: 'false' } }
            steps {
                script {
                    env.LIVE_COLOR = sh(script: "yq '.spec.selector.color' k8s/app/service.yaml", returnStdout: true).trim()
                    env.IDLE_COLOR = env.LIVE_COLOR == 'blue' ? 'green' : 'blue'
                    echo "Live colour: ${env.LIVE_COLOR} -> deploying ${env.IMAGE_TAG} to ${env.IDLE_COLOR}"
                }
                sh """
                    yq -i '.spec.template.spec.containers[0].image = "${DOCKER_REPO}:${IMAGE_TAG}"' k8s/app/deployment-${IDLE_COLOR}.yaml
                    yq -i '(.spec.template.spec.containers[0].env[] | select(.name == "APP_VERSION")).value = "${IMAGE_TAG}"' k8s/app/deployment-${IDLE_COLOR}.yaml
                """
                gitopsPush("deploy ${env.IMAGE_TAG} to ${env.IDLE_COLOR} [skip ci]")
            }
        }

        stage('Verify idle colour (preview)') {
            when { allOf { branch 'main'; environment name: 'SKIP_BUILD', value: 'false' } }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                        # ArgoCD auto-syncs within ~3 min; poll until the idle deployment runs the new tag.
                        ./scripts/wait-for-image.sh ${K8S_NS} ${APP_NAME}-${IDLE_COLOR} ${DOCKER_REPO}:${IMAGE_TAG} 300
                        kubectl -n ${K8S_NS} rollout status deployment/${APP_NAME}-${IDLE_COLOR} --timeout=180s
                        kubectl -n ${K8S_NS} run preview-check-${BUILD_NUMBER} --rm -i --restart=Never \
                            --image=curlimages/curl:8.10.1 -- \
                            curl -fsS http://${APP_NAME}-preview/health/ready
                    """
                }
            }
        }

        stage('Approve traffic switch') {
            when {
                allOf {
                    branch 'main'
                    environment name: 'SKIP_BUILD', value: 'false'
                    expression { !params.AUTO_PROMOTE }
                }
            }
            steps {
                timeout(time: 30, unit: 'MINUTES') {
                    input message: "Switch live traffic from ${env.LIVE_COLOR} to ${env.IDLE_COLOR}?", ok: 'Switch'
                }
            }
        }

        stage('Blue-green switch') {
            when { allOf { branch 'main'; environment name: 'SKIP_BUILD', value: 'false' } }
            steps {
                sh """
                    yq -i '.spec.selector.color = "${IDLE_COLOR}"' k8s/app/service.yaml
                    yq -i '.spec.selector.color = "${LIVE_COLOR}"' k8s/app/service-preview.yaml
                """
                gitopsPush("switch live traffic to ${env.IDLE_COLOR} (${env.IMAGE_TAG}) [skip ci]")
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
            sh 'docker image prune -f || true'
        }
        success { notify('SUCCESS', 'good') }
        failure { notify('FAILURE', 'danger') }
        unstable { notify('UNSTABLE', 'warning') }
    }
}

// Commit manifest changes back to Git; ArgoCD picks them up (GitOps - Git is the source of truth).
def gitopsPush(String message) {
    withCredentials([usernamePassword(credentialsId: 'github-token',
                                      usernameVariable: 'GIT_USER', passwordVariable: 'GIT_TOKEN')]) {
        sh """
            git config user.name  'jenkins-bot'
            git config user.email 'jenkins-bot@users.noreply.github.com'
            git add k8s/app
            git diff --cached --quiet || git commit -m '${message}'
            git push https://\${GIT_USER}:\${GIT_TOKEN}@${GITOPS_REPO} HEAD:main
        """
    }
}

def notify(String status, String color) {
    if (env.SKIP_BUILD == 'true') { return }
    def msg = "${status}: ${env.JOB_NAME} #${env.BUILD_NUMBER} (${env.IMAGE_TAG ?: 'n/a'}) - ${env.BUILD_URL}"
    try {
        emailext(subject: "[Jenkins] ${status}: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                 body: msg, recipientProviders: [developers(), culprits()])
    } catch (err) { echo "Email notification skipped: ${err}" }
    try {
        withCredentials([string(credentialsId: 'slack-webhook', variable: 'SLACK_URL')]) {
            sh """curl -fsS -X POST -H 'Content-type: application/json' \
                  --data '{"text":"${msg}"}' "\$SLACK_URL" || true"""
        }
    } catch (err) { echo "Slack notification skipped: ${err}" }
}
