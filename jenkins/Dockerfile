# Jenkins controller with every CLI the Jenkinsfile needs baked in.
FROM jenkins/jenkins:lts-jdk17

USER root
ARG TRIVY_VERSION=0.57.1
ARG HADOLINT_VERSION=2.12.0
ARG YQ_VERSION=4.44.3
ARG KUBECTL_VERSION=1.31.2
ARG SONAR_SCANNER_VERSION=6.2.1.4610

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip curl unzip git ca-certificates gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli docker-buildx-plugin \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN ARCH=$(dpkg --print-architecture) \
    && curl -fsSL "https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" -o /usr/local/bin/kubectl \
    && curl -fsSL "https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_${ARCH}" -o /usr/local/bin/yq \
    && curl -fsSL "https://github.com/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}/hadolint-Linux-$(uname -m)" -o /usr/local/bin/hadolint \
    && chmod +x /usr/local/bin/kubectl /usr/local/bin/yq /usr/local/bin/hadolint \
    && curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin "v${TRIVY_VERSION}" \
    && curl -fsSL "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-${SONAR_SCANNER_VERSION}-linux-x64.zip" -o /tmp/ss.zip \
    && unzip -q /tmp/ss.zip -d /opt && mv /opt/sonar-scanner-* /opt/sonar-scanner && rm /tmp/ss.zip \
    && ln -s /opt/sonar-scanner/bin/sonar-scanner /usr/local/bin/sonar-scanner

# Plugins + Configuration-as-Code (no click-ops; the whole controller is reproducible).
COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt
COPY casc.yaml /var/jenkins_home/casc.yaml
ENV CASC_JENKINS_CONFIG=/var/jenkins_home/casc.yaml \
    JAVA_OPTS="-Djenkins.install.runSetupWizard=false"

USER jenkins
