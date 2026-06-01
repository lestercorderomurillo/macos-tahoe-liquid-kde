#!/bin/bash
# Gentoo KDE smoke test: boot the official Gentoo cloud-init image,
# switch it onto the Plasma systemd profile, consume the official
# binhost where possible, then run the full install + uninstall flow in
# a real Plasma session.

set -euo pipefail

latest_manifest_url="https://distfiles.gentoo.org/releases/amd64/autobuilds/latest-di-amd64-cloudinit.txt"
ovmf_firmware="/usr/share/edk2/x64/OVMF.4m.fd"
script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

if [[ ! -f "$ovmf_firmware" ]]; then
    echo "required OVMF firmware not found: $ovmf_firmware" >&2
    exit 1
fi

latest_entry="$(
    curl -fsSL "$latest_manifest_url" \
        | sed -n 's#^\([^ #][^ ]*di-amd64-cloudinit-[^ ]*\.qcow2\) .*#\1#p' \
        | head -n 1
)"

if [[ -z "$latest_entry" ]]; then
    echo "failed to resolve latest Gentoo cloud-init image from $latest_manifest_url" >&2
    exit 1
fi

image_stamp="$(basename "$latest_entry" .qcow2)"
snapshot_date="${image_stamp#di-amd64-cloudinit-}"
snapshot_date="${snapshot_date%%T*}"
cloud_init_template="$script_dir/cloud-init-gentoo.yaml"
rendered_cloud_init="$repo_root/tests/vm-smoke/.work/cloud-init-gentoo-${snapshot_date}.yaml"
mkdir -p "$repo_root/tests/vm-smoke/.work"
sed "s/@GENTOO_SNAPSHOT_DATE@/${snapshot_date}/g" \
    "$cloud_init_template" > "$rendered_cloud_init"

VM_ID="gentoo"
VM_LABEL="Gentoo Cloud-Init Plasma Smoke"
IMAGE_LABEL="Gentoo official cloud-init image"
IMAGE_URL="https://distfiles.gentoo.org/releases/amd64/autobuilds/${latest_entry}"
IMAGE_FILENAME="gentoo-$(basename "$latest_entry")"
CLOUD_INIT_FILE="$rendered_cloud_init"
SSH_PORT=2230
VNC_DISPLAY=127.0.0.1:9
BOOT_TIMEOUT_SECS=1800
SMOKE_TIMEOUT_SECS=14400
OVERLAY_SIZE=80G
QEMU_CPUS=6
QEMU_MEM_MIB=12288
QEMU_EXTRA_ARGS="-bios ${ovmf_firmware}${QEMU_EXTRA_ARGS:+ ${QEMU_EXTRA_ARGS}}"

source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
vm_smoke_main
