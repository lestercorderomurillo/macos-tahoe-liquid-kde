"""Regression coverage for the graphical VM harness."""

from __future__ import annotations

import re
import json
import subprocess
import hashlib
import os
import shutil
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
VM = (REPO / "vm").read_text()
PLYMOUTH_RENDER = (REPO / "tests/vm/render.sh").read_text()
NEON_CLOUD_PATH = REPO / ".vm/cloud-init/neon.yaml"
DEBIAN_CLOUD_PATH = REPO / ".vm/cloud-init/debian.yaml"
SYSTEMD_CLOUD_PATHS = tuple(
    path
    for path in sorted((REPO / ".vm/cloud-init").glob("*.yaml"))
)


def _provision_script(path: Path) -> str:
    """Return cloud-init's YAML block scalar exactly as bash receives it."""
    content = path.read_text().split("    content: |\n", 1)[1]
    content = content.split("\nruncmd:\n", 1)[0]
    return "\n".join(
        line[6:] if line.startswith("      ") else line
        for line in content.splitlines()
    ) + "\n"


def test_vm_excludes_retired_gentoo_targets():
    result = subprocess.run(
        [str(REPO / "vm"), "list"], check=True, capture_output=True, text=True,
    )
    assert not any("gentoo" in name for name in result.stdout.splitlines())


@pytest.mark.parametrize("distro", ["arch", "cachyos", "manjaro", "endeavouros", "garuda", "fedora", "nobara", "opensuse", "neon", "debian", "artix", "kubuntu"])
def test_vm_lists_debian_family_guests(distro):
    result = subprocess.run(
        [str(REPO / "vm"), "list"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert distro in result.stdout.splitlines()


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


def test_debian_vm_uses_testing_desktop_and_writable_guest_copy():
    cloud = DEBIAN_CLOUD_PATH.read_text()
    assert "cloud.debian.org/images/cloud/forky/daily/latest/" in VM
    assert "kde-plasma-desktop sddm" in cloud
    assert "python3-pyqt6.qtqml" in cloud
    assert "qml6-module-org-kde-plasma-plasma5support" in cloud
    assert "kde-spectacle" in cloud
    assert "/etc/sddm.conf.d/autologin.conf" in cloud
    assert "/home/tester/macos-tahoe-liquid-kde" in cloud
    assert "--exclude=.vm" in cloud and "--exclude=build" in cloud
    assert "ro,nofail" in cloud
    assert "apt/sources.list" not in cloud
    assert "trusted=yes" not in cloud
    assert "kwin-dev" not in cloud  # The installer must resolve its own SDK.


@pytest.mark.parametrize("path", SYSTEMD_CLOUD_PATHS)
def test_debian_family_provision_script_is_valid_bash(path):
    result = subprocess.run(
        ["bash", "-n"],
        input=_provision_script(path),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("mode", ["valid", "mismatch", "missing", "download-failure"])
def test_debian_vm_verifies_download_before_booting(tmp_path, mode):
    shutil.copy2(REPO / "vm", tmp_path / "vm")
    cloud_dir = tmp_path / ".vm/cloud-init"
    cloud_dir.mkdir(parents=True)
    shutil.copy2(REPO / ".vm/images.json", tmp_path / ".vm/images.json")
    shutil.copy2(DEBIAN_CLOUD_PATH, cloud_dir / "debian.yaml")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    scripts = {
        "curl": '''#!/bin/bash
while [[ "$1" != "-o" ]]; do shift; done
output="$2"
if [[ "$output" == *.SHA512SUMS ]]; then
    printf '%s  %s\\n' "$TEST_IMAGE_HASH" "$TEST_IMAGE_NAME" > "$output"
else
    printf vm-image > "$output"
    [[ "$TEST_DOWNLOAD_MODE" != download-failure ]] || exit 22
fi
''',
        "qemu-img": "#!/bin/bash\nexit 0\n",
        "genisoimage": "#!/bin/bash\nexit 0\n",
        "qemu-system-x86_64": '#!/bin/bash\nprintf "%s\\n" "$@" > "$TEST_QEMU_LOG"\n',
    }
    for name, source in scripts.items():
        binary = binaries / name
        binary.write_text(source)
        binary.chmod(0o755)
    log = tmp_path / "qemu.log"
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "TEST_IMAGE_HASH": "0" * 128 if mode == "mismatch" else hashlib.sha512(b"vm-image").hexdigest(),
        "TEST_IMAGE_NAME": "wrong.qcow2" if mode == "missing" else "debian-14-generic-amd64-daily.qcow2",
        "TEST_DOWNLOAD_MODE": mode,
        "TEST_QEMU_LOG": str(log),
    }
    result = subprocess.run([str(tmp_path / "vm"), "debian"], env=env,
                            capture_output=True, text=True, timeout=10)
    cache = tmp_path / ".vm/cache/debian-testing.qcow2"
    if mode == "valid":
        assert result.returncode == 0, result.stderr
        assert cache.read_bytes() == b"vm-image"
        arguments = log.read_text()
        assert "hostfwd=tcp:127.0.0.1:2232-:22" in arguments
        assert "mount_tag=repo,security_model=none,readonly=on" in arguments
        assert "mttkde-debian" in arguments
    else:
        assert result.returncode != 0
        assert not cache.exists()
        assert not log.exists()


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


def test_iso_targets_use_independent_verified_media():
    images = json.loads((REPO / '.vm/images.json').read_text())
    assert set(images) == {'cachyos', 'manjaro', 'endeavouros', 'garuda', 'nobara', 'artix', 'kubuntu'}
    assert len({item['url'] for item in images.values()}) == len(images)
    for name, item in images.items():
        assert item['url'].startswith('https://') and item['url'].endswith('.iso')
        assert re.fullmatch('[0-9a-f]{' + str(hashlib.new(item['algorithm']).digest_size * 2) + '}', item['digest'])
        assert not (REPO / f'.vm/cloud-init/{name}.yaml').exists()
    assert 'openrc' in images['artix']['url']


@pytest.mark.parametrize('path', SYSTEMD_CLOUD_PATHS)
def test_cloud_desktops_run_from_writable_copies(path):
    cloud = path.read_text()
    assert 'ro,nofail' in cloud
    assert '/home/tester/macos-tahoe-liquid-kde' in cloud
    assert '--exclude=build' in cloud
    assert '--exclude=.vm' in cloud
    assert 'Exec=bash' in cloud
    assert 'cd /home/tester/repo && exec' not in cloud


def test_prepare_installed_guest_script_parses():
    subprocess.run(['bash', '-n', str(REPO / 'tests/vm/prepare_guest.sh')], check=True)


def test_kubuntu_vm_pins_reported_lts_and_keeps_its_native_stack():
    image = json.loads((REPO / '.vm/images.json').read_text())['kubuntu']
    assert image['url'] == ('https://cdimage.ubuntu.com/kubuntu/releases/26.04.1/release/'
                            'kubuntu-26.04.1-desktop-amd64.iso')
    assert image['digest'] == '831e4d4bb85098339ba43d3502cd6619b27e76daf37246a084cd68a6413090b8'
    script = (REPO / 'tests/vm/prepare_guest.sh').read_text().split('    ubuntu)', 1)[1].split(';;', 1)[0]
    assert 'kubuntu-desktop' in script and '26.04' in script
    assert 'python3-pytest plasma-sdk xvfb x11-utils' in script
    assert 'upgrade' not in '\n'.join(line for line in script.splitlines() if not line.lstrip().startswith('#'))
    assert 'add-apt-repository' not in script
    subprocess.run(['bash', '-n', str(REPO / 'tests/vm/live_access.sh')], check=True)


@pytest.mark.parametrize("target,port", [("artix", 2233), ("kubuntu", 2234)])
@pytest.mark.parametrize("mode", ["valid", "mismatch", "download-failure"])
def test_iso_vm_verifies_media_and_boots_native_uefi(tmp_path, mode, target, port):
    shutil.copy2(REPO / "vm", tmp_path / "vm")
    (tmp_path / ".vm").mkdir()
    images = json.loads((REPO / ".vm/images.json").read_text())
    images[target]["digest"] = hashlib.sha256(b"vm-image").hexdigest()
    (tmp_path / ".vm/images.json").write_text(json.dumps(images))
    binaries = tmp_path / "bin"
    binaries.mkdir()
    scripts = {
        "curl": '''#!/bin/bash
while [[ "$1" != "-o" ]]; do shift; done
printf '%s' "$TEST_PAYLOAD" > "$2"
[[ "$TEST_MODE" != download-failure ]] || exit 22
''',
        "qemu-img": "#!/bin/bash\nexit 0\n",
        "genisoimage": "#!/bin/bash\nexit 99\n",
        "qemu-system-x86_64": '#!/bin/bash\nprintf "%s\\n" "$@" > "$TEST_QEMU_LOG"\n',
    }
    for name, source in scripts.items():
        binary = binaries / name
        binary.write_text(source)
        binary.chmod(0o755)
    code, variables = tmp_path / "CODE.fd", tmp_path / "VARS.fd"
    code.write_bytes(b"firmware")
    variables.write_bytes(b"variables")
    log = tmp_path / "qemu.log"
    result = subprocess.run([str(tmp_path / "vm"), target], capture_output=True,
        text=True, timeout=10, env={**os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "VM_CACHE_DIR": str(tmp_path / "cache"), "VM_RUN_DIR": str(tmp_path / "run"),
        "VM_UEFI_CODE": str(code), "VM_UEFI_VARS": str(variables),
        "TEST_PAYLOAD": "wrong" if mode == "mismatch" else "vm-image",
        "TEST_MODE": mode, "TEST_QEMU_LOG": str(log)})
    if mode == "valid":
        assert result.returncode == 0, result.stderr
        arguments = log.read_text()
        assert f"hostfwd=tcp:127.0.0.1:{port}-:22" in arguments
        assert "media=cdrom,readonly=on" in arguments
        assert f"readonly=on,file={code}" in arguments
        assert "-machine\nq35" in arguments
        assert "-b" not in arguments.splitlines()
        assert (tmp_path / f"run/{target}/OVMF_VARS.fd").read_bytes() == b"variables"
    else:
        assert result.returncode != 0
        assert not log.exists()
        assert not list((tmp_path / "cache").glob("*.iso"))


@pytest.mark.parametrize("invalid", [{}, {"unknown": {}}, {"artix": {"algorithm": "md5"}}])
def test_invalid_image_manifest_stops_before_vm_start(tmp_path, invalid):
    shutil.copy2(REPO / "vm", tmp_path / "vm")
    (tmp_path / ".vm").mkdir()
    (tmp_path / ".vm/images.json").write_text(json.dumps(invalid))
    result = subprocess.run([str(tmp_path / "vm"), "list"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "Invalid .vm/images.json" in result.stderr
