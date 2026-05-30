#!/bin/bash
# Manjaro KDE smoke test: boot the official Arch cloud image, swap the
# guest onto Manjaro's stable repos via the manjaro-keyring +
# manjaro-system + manjaro-mirrorlist bootstrap, then run the full
# install + uninstall flow in a real Plasma session.

set -euo pipefail

VM_ID="manjaro"
VM_LABEL="Manjaro Stable Repo-Backed Cloud Smoke"
IMAGE_LABEL="Arch Linux cloud image for Manjaro repo smoke"
IMAGE_URL="https://geo.mirror.pkgbuild.com/images/latest/Arch-Linux-x86_64-cloudimg.qcow2"
IMAGE_FILENAME="arch-linux-cloudimg.qcow2"
CLOUD_INIT_FILE="$(cd "$(dirname "$0")" && pwd)/cloud-init-manjaro.yaml"
SSH_PORT=2226
VNC_DISPLAY=127.0.0.1:5
SMOKE_TIMEOUT_SECS=7200

source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
vm_smoke_main
