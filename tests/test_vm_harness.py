"""Regression coverage for the graphical VM harness."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
VM = (REPO / "vm").read_text()
PLYMOUTH_RENDER = (REPO / "tests/vm/render.sh").read_text()
CLOUD_PATH = REPO / ".vm/cloud-init/gentoo-openrc.yaml"
CLOUD = CLOUD_PATH.read_text()
NEON_CLOUD_PATH = REPO / ".vm/cloud-init/neon.yaml"
SYSTEMD_CLOUD_PATHS = tuple(
    path
    for path in sorted((REPO / ".vm/cloud-init").glob("*.yaml"))
    if path != CLOUD_PATH
)


def _provision_script(path: Path = CLOUD_PATH) -> str:
    """Return cloud-init's YAML block scalar exactly as bash receives it."""
    content = path.read_text().split("    content: |\n", 1)[1]
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


def test_vm_lists_neon():
    result = subprocess.run(
        [str(REPO / "vm"), "list"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "neon" in result.stdout.splitlines()


def test_neon_vm_uses_signed_official_sources_and_qt6_build_deps():
    cloud = NEON_CLOUD_PATH.read_text()

    assert "cloud-images.ubuntu.com/noble/current" in VM
    assert "http://archive.neon.kde.org/user" in cloud
    assert "444DABCF3667D0283F894EDDE6D4736255751E5D" in cloud
    assert "Signed-By: /etc/apt/keyrings/mttkde-neon-archive-keyring.asc" in cloud
    assert "base-files" in cloud
    assert "neon-desktop" in cloud and "plasmalogin" in cloud
    assert "python3-pyqt6.qtqml" in cloud
    assert "qt6-svg-dev" in cloud and "libxext-dev" in cloud
    assert "/home/tester/macos-tahoe-liquid-kde" in cloud
    assert "--exclude=.vm" in cloud and "--exclude=build" in cloud
    assert "trusted=yes" not in cloud
    assert "add-apt-repository" not in cloud


def test_neon_provision_script_is_valid_bash():
    result = subprocess.run(
        ["bash", "-n"],
        input=_provision_script(NEON_CLOUD_PATH),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_systemd_cloud_images_dispatch_their_provisioner():
    """The provision script is a YAML block scalar.  ``runcmd`` must be a
    root key after that block, or cloud-init writes the dispatcher into the
    script instead of ever executing it and the guest stops at a bare login.
    """
    failures = []
    for path in SYSTEMD_CLOUD_PATHS:
        text = path.read_text()
        root_marker = "\nruncmd:\n"
        if root_marker not in text:
            failures.append(f"{path.name}: missing root runcmd")
            continue
        commands = text.rsplit(root_marker, 1)[1]
        if not re.search(
            r"(?m)^  - /usr/local/bin/mttkde-provision\.sh$",
            commands,
        ):
            failures.append(f"{path.name}: provisioner is not dispatched")

    assert not failures, "\n".join(failures)


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


def test_plymouth_render_harness_does_not_depend_on_active_window_focus():
    assert 'scrot --overwrite --window "$window_id"' in PLYMOUTH_RENDER
    assert "spectacle --background --nonotify --activewindow" not in PLYMOUTH_RENDER
    assert "xdotool windowactivate" not in PLYMOUTH_RENDER


def test_plymouth_render_harness_forces_visible_progress():
    assert "on_boot_progress(0, 0.65)" in PLYMOUTH_RENDER
    assert "Plymouth.SetBootProgressFunction(mttkde_harness_progress)" in PLYMOUTH_RENDER
    assert "on_boot_progress(duration, 0.65)" in PLYMOUTH_RENDER
    assert "apply_layout" not in PLYMOUTH_RENDER


def test_plymouth_render_harness_validates_pixels_and_propagates_failure():
    for invariant in (
        "captured the desktop, not Plymouth",
        "logo is missing or off-centre",
        "boot progress fill is missing",
        "shutdown unexpectedly shows a progress bar",
        "Plymouth log contains a script error",
    ):
        assert invariant in PLYMOUTH_RENDER
    assert "exit 1" in PLYMOUTH_RENDER
