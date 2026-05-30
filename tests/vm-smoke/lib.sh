#!/bin/bash

vm_smoke_main() {
    set -euo pipefail

    local script_dir repo_root work_root images_root vm_work out
    local console_log cidata disk image image_part cidir qemu_pid
    local boot_deadline deadline

    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    repo_root="$(cd "$script_dir/../.." && pwd)"
    work_root="$repo_root/tests/vm-smoke/.work"
    images_root="$work_root/images"
    vm_work="$work_root/${VM_ID:?VM_ID is required}"
    out="$vm_work/output"
    console_log="$vm_work/console.log"
    cidata="$vm_work/cidata.iso"
    disk="$vm_work/disk.qcow2"
    image="$images_root/${IMAGE_FILENAME:?IMAGE_FILENAME is required}"
    image_part="${image}.part"

    mkdir -p "$images_root" "$vm_work" "$out"

    need() {
        if ! command -v "$1" >/dev/null 2>&1; then
            echo "required command not found: $1" >&2
            exit 1
        fi
    }

    for cmd in curl genisoimage qemu-img qemu-system-x86_64 sshpass; do
        need "$cmd"
    done

    if [[ ! -f "$image" ]]; then
        echo "→ downloading ${IMAGE_LABEL:-$VM_LABEL} ($IMAGE_URL)"
        curl -L --fail -C - -o "$image_part" "${IMAGE_URL:?IMAGE_URL is required}"
        mv "$image_part" "$image"
    fi

    echo "→ building cloud-init drive for ${VM_LABEL:?VM_LABEL is required}"
    cidir="$(mktemp -d)"
    cp "${CLOUD_INIT_FILE:?CLOUD_INIT_FILE is required}" "$cidir/user-data"
    printf "instance-id: smoke-%s\nlocal-hostname: smoke-%s\n" "$VM_ID" "$VM_ID" \
        > "$cidir/meta-data"
    genisoimage -output "$cidata" -volid cidata -joliet -rock \
        "$cidir/user-data" "$cidir/meta-data" 2>/dev/null
    rm -rf "$cidir"

    rm -f "$disk" "$console_log"
    qemu-img create -f qcow2 -F qcow2 -b "$image" "$disk" \
        "${OVERLAY_SIZE:-40G}" >/dev/null

    cleanup_vm() {
        kill "${qemu_pid:-}" 2>/dev/null || true
        rm -f "$cidata" "$disk"
    }

    echo "→ booting ${VM_LABEL}"
    qemu-system-x86_64 \
        -enable-kvm \
        -cpu host \
        -smp "${QEMU_CPUS:-4}" \
        -m "${QEMU_MEM_MIB:-8192}" \
        -drive file="$disk",if=virtio,format=qcow2 \
        -drive file="$cidata",if=virtio,format=raw,readonly=on \
        -boot c \
        -serial file:"$console_log" \
        -virtfs local,path="$repo_root",mount_tag=repo,security_model=none,readonly=on \
        -netdev user,id=net0,hostfwd=tcp::${SSH_PORT:-2222}-:22 \
        -device virtio-net-pci,netdev=net0 \
        -device virtio-vga \
        -display "vnc=${VNC_DISPLAY:-127.0.0.1:1}" \
        ${QEMU_EXTRA_ARGS:-} \
        &
    qemu_pid=$!
    trap cleanup_vm EXIT

    SSH=(
        sshpass -p "${GUEST_PASS:-tester}" ssh
        -o StrictHostKeyChecking=no
        -o UserKnownHostsFile=/dev/null
        -o ConnectTimeout=5
        -p "${SSH_PORT:-2222}"
        "${GUEST_USER:-tester}@127.0.0.1"
    )
    SCP=(
        sshpass -p "${GUEST_PASS:-tester}" scp
        -o StrictHostKeyChecking=no
        -o UserKnownHostsFile=/dev/null
        -P "${SSH_PORT:-2222}"
    )

    collect_artifacts() {
        mkdir -p "$out"
        cp -f "$console_log" "$out/console.log" 2>/dev/null || true
        "${SSH[@]}" "test -f /home/${GUEST_USER:-tester}/smoke.log && cat /home/${GUEST_USER:-tester}/smoke.log" \
            > "$out/smoke.log" 2>/dev/null || true
        "${SCP[@]}" "${GUEST_USER:-tester}@127.0.0.1:/home/${GUEST_USER:-tester}/desktop.png" \
            "$out/desktop.png" 2>/dev/null || true
        "${SSH[@]}" "sudo test -f /var/log/mttkde-provision.log && sudo cat /var/log/mttkde-provision.log" \
            > "$out/provision.log" 2>/dev/null || true
        "${SSH[@]}" "sudo test -f /var/log/cloud-init-output.log && sudo cat /var/log/cloud-init-output.log" \
            > "$out/cloud-init-output.log" 2>/dev/null || true
    }

    show_console_tail() {
        if [[ -f "$console_log" ]]; then
            echo
            echo "=== guest console tail ($console_log) ==="
            tail -n 80 "$console_log" || true
        fi
    }

    echo "→ waiting for initial SSH"
    boot_deadline=$((SECONDS + ${BOOT_TIMEOUT_SECS:-900}))
    while (( SECONDS < boot_deadline )); do
        if "${SSH[@]}" "true" >/dev/null 2>&1; then
            echo "→ guest reachable over SSH"
            break
        fi
        sleep 5
    done

    if ! "${SSH[@]}" "true" >/dev/null 2>&1; then
        echo "✗ ${VM_LABEL} never became reachable over SSH"
        collect_artifacts
        show_console_tail
        exit 1
    fi

    echo "→ waiting for KDE provisioning + install + uninstall"
    deadline=$((SECONDS + ${SMOKE_TIMEOUT_SECS:-3600}))
    while (( SECONDS < deadline )); do
        if "${SSH[@]}" "test -f /home/${GUEST_USER:-tester}/smoke.done" >/dev/null 2>&1; then
            echo "→ smoke run completed"
            break
        fi
        sleep 10
    done

    collect_artifacts

    if [[ ! -f "$out/smoke.log" ]] || ! grep -q "=== done ===" "$out/smoke.log"; then
        echo "✗ ${VM_LABEL} smoke did not reach the done sentinel"
        if [[ -f "$out/provision.log" ]]; then
            echo
            echo "=== provision log ($out/provision.log) ==="
            cat "$out/provision.log"
        fi
        if [[ -f "$out/cloud-init-output.log" ]]; then
            echo
            echo "=== cloud-init log ($out/cloud-init-output.log) ==="
            cat "$out/cloud-init-output.log"
        fi
        show_console_tail
        exit 1
    fi

    "${SSH[@]}" "sudo systemctl poweroff" || true
    wait "$qemu_pid" 2>/dev/null || true

    echo
    echo "=== log ($out/smoke.log) ==="
    cat "$out/smoke.log"
    echo
    echo "✓ ${VM_LABEL} smoke PASS — artifacts in $out/"
    trap - EXIT
    cleanup_vm
}
