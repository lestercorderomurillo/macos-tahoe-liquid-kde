#!/bin/bash
# EndeavourOS KDE smoke test: boot the official Arch cloud image, add
# the EndeavourOS repo overlay on top of Arch, then run the full
# install + uninstall flow in a real Plasma session.
#
# EndeavourOS is Arch + a single extra repo of ~30 EOS packages, so the
# overlay is intentionally narrower than the Manjaro / CachyOS swaps:
# the base Plasma install still comes from Arch [core] / [extra].

set -euo pipefail

VM_ID="endeavouros"
VM_LABEL="EndeavourOS Repo-Overlay Cloud Smoke"
IMAGE_LABEL="Arch Linux cloud image for EndeavourOS repo smoke"
IMAGE_URL="https://geo.mirror.pkgbuild.com/images/latest/Arch-Linux-x86_64-cloudimg.qcow2"
IMAGE_FILENAME="arch-linux-cloudimg.qcow2"
CLOUD_INIT_FILE="$(cd "$(dirname "$0")" && pwd)/cloud-init-endeavouros.yaml"
SSH_PORT=2227
VNC_DISPLAY=127.0.0.1:6
SMOKE_TIMEOUT_SECS=7200

source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
vm_smoke_main
