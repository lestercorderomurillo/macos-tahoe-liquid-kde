#!/bin/bash
# openSUSE Tumbleweed KDE smoke test: boot the official Minimal-VM
# cloud image, install Plasma, then run the full install + uninstall
# flow in a real session.

set -euo pipefail

VM_ID="opensuse"
VM_LABEL="openSUSE Tumbleweed Minimal-VM Cloud"
IMAGE_LABEL="$VM_LABEL"
IMAGE_URL="https://download.opensuse.org/tumbleweed/appliances/openSUSE-Tumbleweed-Minimal-VM.x86_64-Cloud.qcow2"
IMAGE_FILENAME="opensuse-tumbleweed-cloud.qcow2"
CLOUD_INIT_FILE="$(cd "$(dirname "$0")" && pwd)/cloud-init-opensuse.yaml"
SSH_PORT=2224
VNC_DISPLAY=127.0.0.1:3
SMOKE_TIMEOUT_SECS=5400

source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
vm_smoke_main
