"""Static guards for container-image package-manager invariants."""


def test_arch_family_images_do_not_perform_partial_upgrades(repo):
    """Refreshing pacman metadata without upgrading the base image can mix
    Python and Expat ABIs, making pyexpat fail before the suite reaches project
    code. Every Arch-family dependency install must be a full sync upgrade.
    """
    containers = repo / "tests/containers"
    for distro in ("arch", "cachyos", "endeavouros", "garuda", "manjaro"):
        text = (containers / f"Dockerfile.{distro}").read_text()
        assert "pacman -Syu --noconfirm --needed" in text, distro
        assert "pacman -Sy --noconfirm --needed" not in text, distro
