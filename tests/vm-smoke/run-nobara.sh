#!/bin/bash
# Nobara KDE smoke test: boot the Fedora Cloud Base image, add the
# Nobara repos (Fyra Labs), and let dnf swap Fedora's plasma-workspace
# for Nobara's forked plasma-workspace before installing the rest of
# the KDE stack. Then run the full install + uninstall flow in a real
# Plasma session.

set -euo pipefail

VM_ID="nobara"
VM_LABEL="Nobara Repo-Overlay Cloud Smoke"
IMAGE_LABEL="Fedora 44 Cloud Base for Nobara repo smoke"
IMAGE_URL="https://download.fedoraproject.org/pub/fedora/linux/releases/44/Cloud/x86_64/images/Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2"
IMAGE_FILENAME="fedora-cloud-44.qcow2"
CLOUD_INIT_FILE="$(cd "$(dirname "$0")" && pwd)/cloud-init-nobara.yaml"
SSH_PORT=2229
VNC_DISPLAY=127.0.0.1:8
SMOKE_TIMEOUT_SECS=7200

source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
vm_smoke_main
