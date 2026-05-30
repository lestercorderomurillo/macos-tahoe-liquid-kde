#!/bin/bash
# CachyOS KDE smoke test: boot the official Arch cloud image, switch
# the guest onto the official CachyOS repos, then run the full install
# + uninstall flow in a real Plasma session.

set -euo pipefail

VM_ID="cachyos"
VM_LABEL="CachyOS Repo-Backed Cloud Smoke"
IMAGE_LABEL="Arch Linux cloud image for CachyOS repo smoke"
IMAGE_URL="https://geo.mirror.pkgbuild.com/images/latest/Arch-Linux-x86_64-cloudimg.qcow2"
IMAGE_FILENAME="arch-linux-cloudimg.qcow2"
CLOUD_INIT_FILE="$(cd "$(dirname "$0")" && pwd)/cloud-init-cachyos.yaml"
SSH_PORT=2225
VNC_DISPLAY=127.0.0.1:4
SMOKE_TIMEOUT_SECS=7200

source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
vm_smoke_main
