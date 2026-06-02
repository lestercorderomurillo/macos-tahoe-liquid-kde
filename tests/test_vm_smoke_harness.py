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
        "cloud-init-gentoo.yaml",
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
        "run-gentoo.sh",
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


def test_run_gentoo_uses_latest_official_cloudinit_image():
    script = _read("run-gentoo.sh")
    assert "latest-di-amd64-cloudinit.txt" in script
    assert "di-amd64-cloudinit-" in script
    assert "cloud-init-gentoo.yaml" in script
    assert "snapshot_date" in script
    assert "OVMF.4m.fd" in script


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
        "cloud-init-gentoo.yaml",
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
    # Garuda smoke: enable Chaotic-AUR (the repo every real Garuda
    # install consumes) and rebrand /etc/os-release as ID=garuda so
    # distro.current_distro() reports `garuda`. Garuda does NOT publish
    # standalone keyring/mirrorlist .pkg.tar.zst files on its own repo
    # (verified 2026-05-31 against builds.garudalinux.org/repos/garuda
    # — zero matches), so the smoke deliberately skips the historical
    # `garuda-keyring-` / `garuda-mirrorlist-` scrape path that was
    # silently 404'ing the whole provisioning run.
    assert "install_chaotic_aur" in garuda
    assert "brand_as_garuda" in garuda
    assert "chaotic-keyring-" in garuda
    assert "pacman-key --populate chaotic" in garuda
    assert "[chaotic-aur]" in garuda
    assert "ID=garuda" in garuda
    assert "=== garuda-repos ===" in garuda

    gentoo = _read("cloud-init-gentoo.yaml")
    assert "emerge-webrsync --revert=@GENTOO_SNAPSHOT_DATE@" in gentoo
    assert "eselect profile list" in gentoo
    assert "desktop/plasma/systemd" in gentoo
    assert "distfiles.gentoo.org/releases/amd64/binpackages/23.0/x86-64/" in gentoo
    assert "getbinpkg" in gentoo
    # `--binpkg-respect-use=y` (was `=n`) forces source-rebuild of any
    # binhost package whose USE doesn't match the local config rather
    # than pretending the binhost USE doesn't matter. The `=n` path
    # let portage accept binhost packages then fail later when the
    # USE-dep tracker hit a `wayland?(opengl)`-style REQUIRED_USE on
    # a parent — switching to `=y` gives portage room to source-build
    # the mismatched package instead of dead-ending in autounmask.
    assert "binpkg-respect-use=y" in gentoo
    assert "binpkg-changed-deps=n" in gentoo
    # Disable 32-bit ABI to avoid the expat[abi_x86_32] multilib chain
    # the default stage3 profile pulls through fontconfig/harfbuzz/
    # freetype. The theme stack doesn't need 32-bit anywhere; forcing
    # no-multilib via ABI_X86="64" is honest unblocking, not a hack.
    assert 'ABI_X86="64"' in gentoo
    assert "--autounmask-write" in gentoo
    # autounmask must actually merge (continue=y) AND keep going past
    # individual package failures so a single broken atom doesn't
    # blow up the whole smoke. Without these the autounmask pass
    # writes config files then exits without merging anything,
    # leaving the guest unable to launch Plasma — the failure mode
    # this clause was added to prevent.
    assert "--autounmask-continue=y" in gentoo
    assert "--keep-going=y" in gentoo
    assert "--update --deep --newuse" in gentoo
    assert "etc-update --automode -5" in gentoo
    # Single plasma-meta target instead of pinning plasma-workspace +
    # plasma-desktop + kwin separately. The pinned variant triggers
    # an unresolvable qtdeclarative:6 slot conflict between binhost
    # qcoro and the ebuild tree; plasma-meta lets portage solve the
    # whole graph at once with a consistent slot set.
    assert "kde-plasma/plasma-meta" in gentoo
    assert "x11-misc/sddm" in gentoo
    # spectacle lives under kde-plasma/ in the Gentoo ::gentoo repo,
    # NOT kde-apps/ — the latter was the regression that wedged the
    # autounmask helper in three retry loops with `emerge: there are
    # no ebuilds to satisfy "kde-apps/spectacle"` before the smoke
    # gave up.
    assert "kde-plasma/spectacle" in gentoo
    assert "kde-apps/spectacle" not in gentoo
    assert "=== gentoo-profile ===" in gentoo

    nobara = _read("cloud-init-nobara.yaml")
    # Nobara smoke: point at GloriousEggroll's COPR project on
    # download.copr.fedorainfracloud.org/results/gloriouseggroll/
    # nobara-<N>/ — the canonical source documented in
    # Nobara-Project/nobara-repo-tools. Earlier revisions of this
    # smoke pointed at repos.fyralabs.com/nobara<N>/, but Fyra Labs
    # publishes Terra Linux (terra<N>/), not Nobara, and every key /
    # repo URL under that namespace 404'd — every dnf install ran
    # against an empty repo and the provisioning script crashed
    # silently.
    assert "install_nobara_repos" in nobara
    assert "copr.fedorainfracloud.org/results/gloriouseggroll" in nobara
    assert "RPM-GPG-KEY-nobara" in nobara
    assert "[nobara]" in nobara
    assert "--allowerasing" in nobara
    assert "ID=nobara" in nobara
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
        "cloud-init-gentoo.yaml",
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
    for name in (
        "run-fedora.sh",
        "run-arch.sh",
        "run-cachyos.sh",
        "run-manjaro.sh",
        "run-endeavouros.sh",
        "run-garuda.sh",
        "run-gentoo.sh",
        "run-nobara.sh",
        "run-opensuse.sh",
    ):
        script = _read(name)
        assert "SKIP:" not in script
        assert "exit 2" not in script
