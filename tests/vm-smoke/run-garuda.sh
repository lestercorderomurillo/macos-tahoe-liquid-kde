#!/bin/bash
# Garuda Linux KDE smoke test: boot the official Arch cloud image, add
# the Chaotic-AUR repo and the Garuda repo overlay on top, then run
# the full install + uninstall flow in a real Plasma session.
#
# Both keyrings are installed by pulling the package directly from the
# vendor mirror (no pacman-key --recv-keys network roundtrip) to avoid
# the historical Chaotic-AUR keyserver flake.

set -euo pipefail

VM_ID="garuda"
VM_LABEL="Garuda Linux Repo-Overlay Cloud Smoke"
IMAGE_LABEL="Arch Linux cloud image for Garuda repo smoke"
IMAGE_URL="https://geo.mirror.pkgbuild.com/images/latest/Arch-Linux-x86_64-cloudimg.qcow2"
IMAGE_FILENAME="arch-linux-cloudimg.qcow2"
CLOUD_INIT_FILE="$(cd "$(dirname "$0")" && pwd)/cloud-init-garuda.yaml"
SSH_PORT=2228
VNC_DISPLAY=127.0.0.1:7
SMOKE_TIMEOUT_SECS=7200

source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
vm_smoke_main
