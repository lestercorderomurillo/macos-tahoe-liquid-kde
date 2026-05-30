"""Static checks for the VM smoke harness."""

from pathlib import Path


VM_SMOKE_DIR = Path(__file__).resolve().parent / "vm-smoke"


def _read(name: str) -> str:
    return (VM_SMOKE_DIR / name).read_text(encoding="utf-8")


def test_vm_smoke_files_present():
    for name in (
        "README.md",
        "lib.sh",
        "cloud-init.yaml",
        "cloud-init-arch.yaml",
        "cloud-init-cachyos.yaml",
        "cloud-init-endeavouros.yaml",
        "cloud-init-garuda.yaml",
        "cloud-init-manjaro.yaml",
        "cloud-init-nobara.yaml",
        "cloud-init-opensuse.yaml",
        "run-fedora.sh",
        "run-arch.sh",
        "run-opensuse.sh",
        "run-all.sh",
        "run-cachyos.sh",
        "run-manjaro.sh",
        "run-endeavouros.sh",
        "run-garuda.sh",
        "run-gentoo.sh",
        "run-nobara.sh",
    ):
        assert (VM_SMOKE_DIR / name).is_file(), f"missing tests/vm-smoke/{name}"


def test_supported_vm_scripts_use_shared_runner():
    for name in (
        "run-fedora.sh",
        "run-arch.sh",
        "run-cachyos.sh",
        "run-manjaro.sh",
        "run-endeavouros.sh",
        "run-garuda.sh",
        "run-nobara.sh",
        "run-opensuse.sh",
    ):
        script = _read(name)
        assert 'source "$(cd "$(dirname "$0")" && pwd)/lib.sh"' in script
        assert "vm_smoke_main" in script
        assert "VM_ID=" in script
        assert "IMAGE_URL=" in script
        assert "CLOUD_INIT_FILE=" in script


def test_run_fedora_uses_cloud_base_image_not_dead_live_iso():
    script = _read("run-fedora.sh")
    assert "Fedora-Cloud-Base-Generic" in script
    assert "Fedora-KDE-Live" not in script


def test_run_arch_uses_official_cloud_image():
    script = _read("run-arch.sh")
    assert "Arch-Linux-x86_64-cloudimg.qcow2" in script
    assert "archlinux-" not in script


def test_run_opensuse_uses_minimal_vm_cloud_image():
    script = _read("run-opensuse.sh")
    assert "openSUSE-Tumbleweed-Minimal-VM.x86_64-Cloud.qcow2" in script
    assert "LiveCD" not in script


def test_run_cachyos_uses_arch_cloud_image_plus_repo_bootstrap():
    script = _read("run-cachyos.sh")
    assert "Arch-Linux-x86_64-cloudimg.qcow2" in script
    assert "cloud-init-cachyos.yaml" in script


def test_run_manjaro_uses_arch_cloud_image_plus_repo_bootstrap():
    script = _read("run-manjaro.sh")
    assert "Arch-Linux-x86_64-cloudimg.qcow2" in script
    assert "cloud-init-manjaro.yaml" in script


def test_run_endeavouros_uses_arch_cloud_image_plus_repo_overlay():
    script = _read("run-endeavouros.sh")
    assert "Arch-Linux-x86_64-cloudimg.qcow2" in script
    assert "cloud-init-endeavouros.yaml" in script


def test_run_garuda_uses_arch_cloud_image_plus_chaotic_and_garuda():
    script = _read("run-garuda.sh")
    assert "Arch-Linux-x86_64-cloudimg.qcow2" in script
    assert "cloud-init-garuda.yaml" in script


def test_run_nobara_uses_fedora_cloud_image_plus_repo_overlay():
    script = _read("run-nobara.sh")
    assert "Fedora-Cloud-Base-Generic" in script
    assert "fedora-cloud-44.qcow2" in script
    assert "cloud-init-nobara.yaml" in script


def test_lib_mounts_repo_and_collects_done_sentinel():
    script = _read("lib.sh")
    assert "-virtfs" in script
    assert "smoke.done" in script
    assert "collect_artifacts" in script
    assert "cloud-init-output.log" in script


def test_cloud_init_profiles_share_smoke_guest_contract():
    for name in (
        "cloud-init.yaml",
        "cloud-init-arch.yaml",
        "cloud-init-cachyos.yaml",
        "cloud-init-endeavouros.yaml",
        "cloud-init-garuda.yaml",
        "cloud-init-manjaro.yaml",
        "cloud-init-nobara.yaml",
        "cloud-init-opensuse.yaml",
    ):
        config = _read(name)
        assert config.count("\nwrite_files:") == 1
        assert "select_plasma_session" in config
        assert "autologin.conf" in config
        assert "run-smoke.sh" in config
        assert "mttkde-smoke.desktop" in config
        assert "systemctl --no-block reboot" in config
        assert "systemctl enable --now sshd || true" in config


def test_cloud_init_profile_specific_kde_provisioning():
    config = _read("cloud-init.yaml")
    assert "@kde-desktop-environment" in config
    assert "extra-cmake-modules" in config
    assert "kf6-kitemmodels-devel" in config
    assert "libdrm-devel" in config
    assert "libplasma-devel" in config
    assert "plasma-workspace-devel" in config
    assert "kwin-devel" in config
    assert "plasmalogin" in config
    assert "sddm.service" in config

    arch = _read("cloud-init-arch.yaml")
    assert "pacman -Sy --noconfirm" in arch
    assert "plasma-meta" in arch
    assert "qt6-tools" in arch
    assert "spectacle" in arch

    cachyos = _read("cloud-init-cachyos.yaml")
    assert "bootstrap_cachyos_keyring" in cachyos
    assert "cachyos-keyring-20240331-1-any.pkg.tar.zst" in cachyos
    assert "pacman-key --populate cachyos" in cachyos
    assert "'/pacman-key --recv-keys /d'" in cachyos
    assert "cachyos-repo.tar.xz" in cachyos
    assert "./cachyos-repo.sh --install" in cachyos
    assert "cachyos-settings" in cachyos
    assert "=== cachyos-repos ===" in cachyos

    manjaro = _read("cloud-init-manjaro.yaml")
    assert "install_manjaro_repos" in manjaro
    assert "manjaro-keyring-" in manjaro
    assert "manjaro-system-" in manjaro
    assert "pacman-key --populate manjaro" in manjaro
    assert "/etc/pacman.d/mirrorlist" in manjaro
    assert "pacman -Syyuu --noconfirm" in manjaro
    assert "=== manjaro-repos ===" in manjaro

    endeavouros = _read("cloud-init-endeavouros.yaml")
    assert "install_endeavouros_repo" in endeavouros
    assert "endeavouros-keyring-" in endeavouros
    assert "endeavouros-mirrorlist-" in endeavouros
    assert "pacman-key --populate endeavouros" in endeavouros
    assert "[endeavouros]" in endeavouros
    assert "=== endeavouros-repos ===" in endeavouros

    garuda = _read("cloud-init-garuda.yaml")
    assert "install_chaotic_aur" in garuda
    assert "install_garuda_repo" in garuda
    assert "chaotic-keyring-" in garuda
    assert "garuda-mirrorlist-" in garuda
    assert "pacman-key --populate chaotic" in garuda
    assert "pacman-key --populate garuda" in garuda
    assert "[chaotic-aur]" in garuda
    assert "[garuda]" in garuda
    assert "=== garuda-repos ===" in garuda

    nobara = _read("cloud-init-nobara.yaml")
    assert "install_nobara_repos" in nobara
    assert "repos.fyralabs.com/nobara" in nobara
    assert "RPM-GPG-KEY-nobara" in nobara
    assert "[nobara-baseos]" in nobara
    assert "[nobara-appstream]" in nobara
    assert "--allowerasing" in nobara
    assert "=== nobara-repos ===" in nobara

    opensuse = _read("cloud-init-opensuse.yaml")
    assert "zypper --non-interactive refresh" in opensuse
    assert "patterns-kde-kde_plasma" in opensuse
    assert "qt6-core-devel" in opensuse
    assert "plasma6-workspace-devel" in opensuse
    assert "kwin6-devel" in opensuse
    assert "libplasma6-devel" in opensuse
    assert '/etc/sysconfig/displaymanager' in opensuse
    assert 'DISPLAYMANAGER_AUTOLOGIN="tester"' in opensuse
    assert 'DISPLAYMANAGER_PASSWORD_LESS_LOGIN="yes"' in opensuse


def test_guest_smoke_script_copies_repo_locally_and_bypasses_prompts():
    for name in (
        "cloud-init.yaml",
        "cloud-init-arch.yaml",
        "cloud-init-cachyos.yaml",
        "cloud-init-endeavouros.yaml",
        "cloud-init-garuda.yaml",
        "cloud-init-manjaro.yaml",
        "cloud-init-nobara.yaml",
        "cloud-init-opensuse.yaml",
    ):
        config = _read(name)
        assert "MTTKDE_NO_CONFIRM=1" in config
        assert "--preserve-env=MTTKDE_NO_CONFIRM" in config
        assert "--exclude=tests/vm-smoke/.work" in config
        assert "tar -C /repo" in config
        assert "sudo --preserve-env=MTTKDE_NO_CONFIRM ./install --preflight" in config
        assert "sudo --preserve-env=MTTKDE_NO_CONFIRM ./install" in config
        assert "sudo --preserve-env=MTTKDE_NO_CONFIRM ./uninstall" in config


def test_run_all_includes_real_and_skip_entries():
    script = _read("run-all.sh")
    for name in (
        "run-fedora.sh",
        "run-arch.sh",
        "run-opensuse.sh",
        "run-cachyos.sh",
        "run-manjaro.sh",
        "run-endeavouros.sh",
        "run-garuda.sh",
        "run-gentoo.sh",
        "run-nobara.sh",
    ):
        assert name in script
    assert "run-bazzite.sh" not in script
    assert "status == 2" in script


def test_skip_wrappers_are_explicit():
    # The remaining skip wrappers — distros where the smoke is still
    # a placeholder waiting for a real cloud-init flow. As they land
    # for real (like Manjaro, EndeavourOS, Garuda, Nobara did), drop
    # their entry here and add a `test_run_<distro>_uses_*` counterpart
    # above.
    for name in (
        "run-gentoo.sh",
    ):
        script = _read(name)
        assert "SKIP:" in script
        assert "exit 2" in script
