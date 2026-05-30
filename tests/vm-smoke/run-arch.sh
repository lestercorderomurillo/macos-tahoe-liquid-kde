#!/bin/bash
# Arch KDE smoke test: boot the official Arch cloud image, install
# Plasma, then run the full install + uninstall flow in a real session.

set -euo pipefail

VM_ID="arch"
VM_LABEL="Arch Linux Cloud Image"
IMAGE_LABEL="Arch Linux cloud image"
IMAGE_URL="https://geo.mirror.pkgbuild.com/images/latest/Arch-Linux-x86_64-cloudimg.qcow2"
IMAGE_FILENAME="arch-linux-cloudimg.qcow2"
CLOUD_INIT_FILE="$(cd "$(dirname "$0")" && pwd)/cloud-init-arch.yaml"
SSH_PORT=2223
VNC_DISPLAY=127.0.0.1:2
SMOKE_TIMEOUT_SECS=5400

source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
vm_smoke_main
