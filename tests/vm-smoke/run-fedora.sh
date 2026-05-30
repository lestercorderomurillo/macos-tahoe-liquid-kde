#!/bin/bash
# Fedora KDE smoke test: boot a real Fedora Cloud Base VM, let
# cloud-init install KDE, reboot into a real Plasma session, run
# ./install + ./uninstall, capture logs + a screenshot, then shut down.

set -euo pipefail

FEDORA_VER=44
VM_ID="fedora"
VM_LABEL="Fedora ${FEDORA_VER} Cloud Base"
IMAGE_LABEL="$VM_LABEL"
IMAGE_URL="https://download.fedoraproject.org/pub/fedora/linux/releases/${FEDORA_VER}/Cloud/x86_64/images/Fedora-Cloud-Base-Generic-${FEDORA_VER}-1.7.x86_64.qcow2"
IMAGE_FILENAME="fedora-cloud-${FEDORA_VER}.qcow2"
CLOUD_INIT_FILE="$(cd "$(dirname "$0")" && pwd)/cloud-init.yaml"
SSH_PORT=2222
VNC_DISPLAY=127.0.0.1:1

source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
vm_smoke_main
