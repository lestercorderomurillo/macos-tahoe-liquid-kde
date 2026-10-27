"""Static guards for container-image package-manager invariants."""


def test_neon_installs_git_for_release_capture_tests(repo):
    text = (repo / "tests/containers/Dockerfile.neon").read_text()
    packages = text.split("apt-get install", 1)[1].split("&&", 1)[0].split()
    assert "git" in packages


def test_arch_family_images_do_not_perform_partial_upgrades(repo):
    """Refreshing pacman metadata without upgrading the base image can mix
    Python and Expat ABIs, making pyexpat fail before the suite reaches project
    code. Every Arch-family dependency install must be a full sync upgrade.
    """
    import re
    import shlex

    containers = repo / "tests/containers"
    for distro in ("arch", "cachyos", "endeavouros", "garuda", "manjaro", "arch-kdeunstable"):
        text = (containers / f"Dockerfile.{distro}").read_text()
        assert "pacman -Syu --noconfirm --needed" in text, distro
        commands = "\n".join(line for line in text.splitlines()
                             if not line.lstrip().startswith("#")).replace("\\\n", " ")
        for match in re.finditer(r"\bpacman -Sy\s+([^&\n]+)", commands):
            # Only signing keys may precede the full upgrade, in the same
            # successful shell chain. Never install runtime libraries here.
            packages = {arg for arg in shlex.split(match[1]) if not arg.startswith("-")}
            assert packages and packages <= {
                "archlinux-keyring", "cachyos-keyring", "manjaro-keyring"}, distro
            assert re.match(r"\s*&&\s*pacman -Syu\s", commands[match.end():]), distro


def test_retired_gentoo_has_no_ci_or_vm_targets(repo):
    for path in (repo / ".github/workflows").glob("*.yml"):
        assert "gentoo" not in path.read_text().lower(), path
    assert not list((repo / "tests/containers").glob("*gentoo*"))
    assert not list((repo / ".vm/cloud-init").glob("*gentoo*"))
    assert "continue-on-error:" not in (repo / ".github/workflows/test.yml").read_text()


def test_debian_container_uses_supported_sdk_and_both_runners(repo):
    text = (repo / "tests/containers/Dockerfile.debian").read_text()
    assert "ARG DEBIAN_SUITE=testing-slim" in text
    assert "FROM debian:${DEBIAN_SUITE}" in text
    assert 'CMD ["python3", "tests/containers/run_in_container.py"]' in text
    assert "ENV MTTKDE_X11_PLUGIN=/repo/build/container-cmake/acrylic-glass/src/liquidglass_x11.so" in text
    for package in ("kwin-x11", "kwin-x11-dev", "xvfb", "x11-utils", "dbus-daemon"):
        assert package in text
    assert "          - debian\n" in (repo / ".github/workflows/test.yml").read_text()
    assert "    debian\n" in (repo / "tests/containers/run_matrix.sh").read_text()
    # Neon uses different names for these SDKs; Debian must use its own.
    for package in ("libplasmaactivities-dev", "libplasmaactivitiesstats-dev",
                    "qt6-wayland-dev", "libxcb-composite0-dev", "libxcb-randr0-dev",
                    "libxcb-res0-dev", "libxcb-shm0-dev", "libxcb-sync-dev"):
        assert package in text


def test_every_matrix_image_installs_suite_dependencies(repo):
    import re

    workflow = (repo / '.github/workflows/test.yml').read_text()
    matrix = workflow.split('        distro:', 1)[1].split('    steps:', 1)[0]
    distros = re.findall(r'^          - ([a-z-]+)$', matrix, re.MULTILINE)
    assert distros
    for distro in distros:
        text = (repo / f'tests/containers/Dockerfile.{distro}').read_text()
        executable = '\n'.join(line for line in text.splitlines()
                               if not line.lstrip().startswith('#'))
        packages = set(executable.split())
        assert 'git' in packages, distro
        assert 'zstd' in packages, distro
        assert packages.intersection({'python-pillow', 'python3-pil', 'python3-pillow', 'python3-Pillow'}), distro
        assert packages.intersection({'librsvg', 'librsvg2-bin', 'librsvg2-tools', 'rsvg-convert'}), distro
    assert 'python-pillow' in workflow
    assert 'librsvg ' in workflow
    assert 'from PIL import Image' in workflow
    assert 'command -v rsvg-convert' in workflow
