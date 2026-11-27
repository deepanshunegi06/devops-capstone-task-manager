#!/usr/bin/env bash
# Reproducible Ubuntu instructions. Do not disable signature or TLS checks.
set -euo pipefail
sudo apt-get update
sudo apt-get install -y git fontconfig openjdk-21-jre wget gpg ca-certificates
sudo wget -O /usr/share/keyrings/jenkins-keyring.asc https://pkg.jenkins.io/debian-stable/jenkins.io-2026.key
echo 'deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/' | sudo tee /etc/apt/sources.list.d/jenkins.list
sudo apt-get update
sudo apt-get install -y jenkins
git --version
java -version
git config --global user.name 'Deepanshu Negi'
git config --global user.email 'deepanshunegi06@users.noreply.github.com'
sudo systemctl enable --now jenkins
sudo systemctl status jenkins --no-pager
