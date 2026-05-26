"""Cross-distro test runner. Lives inside each per-distro container.

Tier 1 — the cheap stuff:
  * qmake6 is on PATH and returns a non-empty plugin / QML directory.
  * distro.qt6_plugins_dir() / qt6_qml_dir() return exactly what
    qmake6 reports — no hardcoded assumption sneaked back in.
  * distro.current_distro() resolves to a sensible /etc/os-release id.
  * The full pytest suite passes against this distro's real Python +
    Qt6 layout.

Tier 2 — the dep layer:
  * distro.package_manager_install_cmd() returns a real binary that
    exists on PATH (proves the table covers this distro).
  * distro.package_for(...) maps the common deps() tokens to packages
    that exist in the distro's repos (probes with pacman -Si / dnf
    info / apt show / etc.).

What this still does NOT prove:
  * The full ./install pipeline (needs plasmashell + KWin running).
  * CMake find_package for KDE / KF6 / KWin — would require pulling
    in the entire Plasma 6 dev SDK. Out of scope for v0.15.0.

If both tiers pass, the v0.15.0 install will (a) land .so / QML
where Qt6 actually scans, and (b) know how to install its missing
build deps via the right package manager.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path("/repo")
sys.path.insert(0, str(REPO / "src/scripts"))


def _q(label: str, cmd: list[str]) -> str | None:
    print(f"  ── {label}")
    if not shutil.which(cmd[0]):
        print(f"     SKIP: {cmd[0]} not on PATH")
        return None
    res = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"     FAIL: {' '.join(cmd)} returned {res.returncode}")
        print(f"           {res.stderr.strip()}")
        return None
    out = res.stdout.strip()
    print(f"     {out}")
    return out


def step_qmake6_directly() -> tuple[str | None, str | None]:
    print("=== qmake6 path discovery ===")
    plugins = _q("QT_INSTALL_PLUGINS", ["qmake6", "-query", "QT_INSTALL_PLUGINS"])
    qml = _q("QT_INSTALL_QML", ["qmake6", "-query", "QT_INSTALL_QML"])
    return plugins, qml


def step_distro_layer(expected_plugins: str | None,
                      expected_qml: str | None) -> bool:
    print("\n=== distro.py layer (Qt6 paths) ===")
    import distro

    print(f"  current_distro(): {distro.current_distro()}")
    print(f"  qt6_install_hint(): {distro.qt6_install_hint()}")
    try:
        layer_plugins = str(distro.qt6_plugins_dir())
        layer_qml = str(distro.qt6_qml_dir())
        layer_lib = str(distro.system_lib_dir())
    except distro.Qt6PathsMissing as exc:
        print(f"  FAIL: Qt6PathsMissing — {exc}")
        return False

    print(f"  qt6_plugins_dir():  {layer_plugins}")
    print(f"  qt6_qml_dir():      {layer_qml}")
    print(f"  system_lib_dir():   {layer_lib}")

    ok = True
    if expected_plugins and layer_plugins != expected_plugins:
        print(f"  FAIL: qt6_plugins_dir mismatch — qmake6 said "
              f"{expected_plugins!r}, layer said {layer_plugins!r}")
        ok = False
    if expected_qml and layer_qml != expected_qml:
        print(f"  FAIL: qt6_qml_dir mismatch — qmake6 said "
              f"{expected_qml!r}, layer said {layer_qml!r}")
        ok = False
    if ok:
        print("  PASS: distro layer agrees with qmake6")
    return ok


def step_package_manager_layer() -> bool:
    """Tier 2: the distro layer knows how to install packages here, AND
    the common deps() tokens map to packages that exist in the distro's
    repos. Probes the repo with the distro-native ``show / info / -Si``
    command; finding a package is treated as PASS, not finding it as
    FAIL with the name we tried."""
    print("\n=== distro.py layer (package manager) ===")
    import distro

    try:
        cmd = distro.package_manager_install_cmd()
    except distro.UnsupportedDistroError as exc:
        print(f"  FAIL: {exc}")
        return False

    binary = cmd[0]
    print(f"  package_manager_install_cmd(): {' '.join(cmd)}")
    if not shutil.which(binary):
        print(f"  FAIL: {binary} is not on PATH")
        return False
    print(f"  PASS: {binary} is on PATH")

    # Probe each common deps() token. If the mapped package doesn't
    # exist in the distro's repo, the install would fail at runtime —
    # better to know now.
    probers = {
        "arch":     ["pacman", "-Si"],
        "gentoo":   ["emerge", "--search-",  ],  # gentoo uses --search; handled below
        "fedora":   ["dnf", "info", "--quiet"],
        "rhel":     ["dnf", "info", "--quiet"],
        "centos":   ["dnf", "info", "--quiet"],
        "opensuse": ["zypper", "--non-interactive", "info"],
        "debian":   ["apt", "show"],
        "ubuntu":   ["apt", "show"],
    }
    d = distro.current_distro()
    if d not in probers:
        for parent in distro.distro_id_like():
            if parent in probers:
                d = parent
                break
    probe = probers.get(d)
    if probe is None:
        print(f"  SKIP: no repo-probe for distro {distro.current_distro()!r}")
        return True

    ok = True
    for cmd_token in ("cmake", "g++", "pkg-config", "qmake6"):
        pkg = distro.package_for(cmd_token, cmd_token)
        print(f"  ── probe {cmd_token!r} → {pkg!r}")
        if d == "gentoo":
            # Gentoo doesn't have a clean info-only command; check
            # /var/db/repos/gentoo/<category>/<name> instead.
            cat, _, name = pkg.partition("/")
            if not cat or not name:
                print(f"     SKIP: cannot parse gentoo atom {pkg!r}")
                continue
            ebuild_dir = Path(f"/var/db/repos/gentoo/{cat}/{name.split(':')[0]}")
            if ebuild_dir.is_dir():
                print(f"     PASS: {ebuild_dir} exists")
            else:
                print(f"     FAIL: no ebuild at {ebuild_dir}")
                ok = False
            continue
        res = subprocess.run(
            [*probe, pkg], check=False, capture_output=True, text=True,
        )
        if res.returncode != 0:
            print(f"     FAIL: probe returned {res.returncode}")
            print(f"           stderr: {res.stderr.strip()[:200]}")
            ok = False
        else:
            print(f"     PASS")
    return ok


def step_preflight_destinations() -> bool:
    """Run the same path-allowlist regex that the real preflight uses
    against every step's known install destination. Catches a refactor
    that adds a new .so without listing it in _enumerate_destinations,
    AND proves that on THIS distro all the destinations sit in
    allowed roots (Qt6 plugin dir + Qt6 QML dir + $HOME-relative)."""
    print("\n=== preflight: destination paths ===")
    import preflight
    ok = True
    for label, path in preflight._enumerate_destinations():
        reason = preflight._validate_path(path)
        if reason is None:
            print(f"  PASS: {label} → {path}")
        else:
            print(f"  FAIL: {label} → {path}  ({reason})")
            ok = False
    return ok


def step_pytest() -> bool:
    print("\n=== pytest ===")
    res = subprocess.run(
        ["python3", "-m", "pytest", "tests/", "-q",
         # Skip tests that need the live KDE session — none of those
         # work inside a stage3 / stripped-down container.
         "--ignore=tests/test_vm_harness.py",
         "-x"],
        check=False, cwd=str(REPO),
    )
    return res.returncode == 0


def main() -> int:
    plugins, qml = step_qmake6_directly()
    layer_ok = step_distro_layer(plugins, qml)
    pkg_ok = step_package_manager_layer()
    preflight_ok = step_preflight_destinations()
    tests_ok = step_pytest()

    print("\n=== summary ===")
    print(f"  qmake6 plugins:     {plugins or '(missing)'}")
    print(f"  qmake6 qml:         {qml or '(missing)'}")
    print(f"  Qt6 layer:          {'PASS' if layer_ok else 'FAIL'}")
    print(f"  Package mgr layer:  {'PASS' if pkg_ok else 'FAIL'}")
    print(f"  Preflight paths:    {'PASS' if preflight_ok else 'FAIL'}")
    print(f"  Pytest suite:       {'PASS' if tests_ok else 'FAIL'}")

    if plugins is None or qml is None:
        print("  → qmake6 not available — install qt6-tools (or equivalent)")
        return 1
    if not (layer_ok and pkg_ok and preflight_ok and tests_ok):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
