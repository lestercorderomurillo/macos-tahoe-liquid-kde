"""Regression coverage for the two-pass Gentoo/OpenRC VM harness."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
VM = (REPO / "vm").read_text()
CLOUD_PATH = REPO / ".vm/cloud-init/gentoo-openrc.yaml"
CLOUD = CLOUD_PATH.read_text()


def _provision_script() -> str:
    """Return cloud-init's YAML block scalar exactly as bash receives it."""
    content = CLOUD.split("    content: |\n", 1)[1]
    content = content.split("\nruncmd:\n", 1)[0]
    return "\n".join(
        line[6:] if line.startswith("      ") else line
        for line in content.splitlines()
    ) + "\n"


def test_vm_lists_gentoo_openrc():
    result = subprocess.run(
        [str(REPO / "vm"), "list"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "gentoo-openrc" in result.stdout.splitlines()


def test_gentoo_openrc_provision_script_is_valid_bash():
    result = subprocess.run(
        ["bash", "-n"],
        input=_provision_script(),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_gentoo_openrc_profile_load_temporarily_disables_nounset():
    assert re.search(
        r"set \+u\s+source /etc/profile\s+set -u",
        _provision_script(),
    )


def test_gentoo_openrc_selects_merged_usr_plasma_profile():
    selector = _provision_script().split("select_plasma_profile()", 1)[1]
    selector = selector.split("configure_binhost()", 1)[0]
    assert "grep -v 'systemd'" in selector
    assert "grep -v 'split-usr'" in selector


def test_gentoo_openrc_disk_has_bios_efi_and_root_partitions():
    script = _provision_script()
    assert "--typecode=1:EF02" in script
    assert "--typecode=2:EF00" in script
    assert "--typecode=3:8300" in script
    assert 'EFI_PART="${DISK}2"' in script
    assert 'ROOT_PART="${DISK}3"' in script


def test_gentoo_openrc_accepts_only_the_required_firmware_license():
    script = _provision_script()
    assert "package.license/linux-firmware" in script
    assert "sys-kernel/linux-firmware linux-fw-redistributable" in script
    assert "ACCEPT_LICENSE=" not in script


def test_gentoo_openrc_preseeds_binary_kernel_initramfs_use_flag():
    assert "sys-kernel/installkernel dracut" in _provision_script()


def test_gentoo_images_resolve_through_official_latest_pointers():
    assert "latest-di-amd64-cloudinit.txt" in VM
    assert "latest-stage3-amd64-desktop-openrc.txt" in CLOUD
    # Gentoo timestamps end in Z. The loose awk filter must admit that
    # suffix before the strict Bash regex validates the full filename.
    assert r"[0-9TZ]+\.qcow2" in VM
    assert r"[0-9TZ]+\.tar\.xz" in CLOUD
    assert r"[0-9T]+\.qcow2" not in VM
    assert r"[0-9T]+\.tar\.xz" not in CLOUD
    assert not re.search(r"di-amd64-cloudinit-\d{8}T\d{6}Z", VM)
    assert not re.search(
        r"stage3-amd64-desktop-openrc-\d{8}T\d{6}Z",
        CLOUD,
    )
