"""Distro-detection layer: Qt6 dirs, libdir, package-manager commands.
The ONLY place per-distro paths or package managers are allowed. Never
assume a path — when no Qt6 query tool exists, raise Qt6PathsMissing
with a distro hint instead of guessing."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class Qt6PathsMissing(RuntimeError):
    """No Qt6 query tool (qmake6 / qtpaths6 / pkg-config) on PATH — the
    installer refuses to guess Qt's scan path."""


# ── /etc/os-release ──────────────────────────────────────────────────


_OS_RELEASE_PATH = Path("/etc/os-release")
_DISTRO_CACHE: str | None = None


def _parse_os_release(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        if not key:
            continue
        v = value.strip()
        if (v.startswith('"') and v.endswith('"')) or \
           (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        out[key.strip()] = v
    return out


def current_distro() -> str:
    """Lowercase os-release ID; ``"unknown"`` when /etc/os-release is
    missing or unreadable (callers fall back to a generic hint)."""
    global _DISTRO_CACHE
    if _DISTRO_CACHE is not None:
        return _DISTRO_CACHE
    try:
        text = _OS_RELEASE_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        _DISTRO_CACHE = "unknown"
        return _DISTRO_CACHE
    fields = _parse_os_release(text)
    _DISTRO_CACHE = (fields.get("ID") or "unknown").lower()
    return _DISTRO_CACHE


def distro_id_like() -> tuple[str, ...]:
    """Lowercase os-release ID_LIKE chain, so downstream distros inherit
    their parent's package-manager mappings without per-id wiring."""
    try:
        text = _OS_RELEASE_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    fields = _parse_os_release(text)
    return tuple(s for s in fields.get("ID_LIKE", "").lower().split() if s)


# ── Qt6 plugin / QML directories ─────────────────────────────────────


_QT_PLUGINS_CACHE: Path | None = None
_QT_QML_CACHE: Path | None = None


def _run_query(cmd: list[str]) -> str | None:
    if not shutil.which(cmd[0]):
        return None
    try:
        res = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    out = res.stdout.strip()
    return out or None


def _qt6_plugins_query() -> str | None:
    for cmd in (
        ["qmake6", "-query", "QT_INSTALL_PLUGINS"],
        ["qtpaths6", "--plugin-dir"],
        ["pkg-config", "--variable=plugindir", "Qt6Core"],
    ):
        out = _run_query(cmd)
        if out:
            return out
    return None


def _qt6_qml_query() -> str | None:
    for cmd in (
        ["qmake6", "-query", "QT_INSTALL_QML"],
        ["pkg-config", "--variable=qmldir", "Qt6Qml"],
    ):
        out = _run_query(cmd)
        if out:
            return out
    return None


# Hint surfaced when qmake6 is missing; downstreams reach their base
# distro's row via ID_LIKE.
_QT6_TOOLS_HINTS: dict[str, str] = {
    "arch":          "pacman -S qt6-tools",
    "gentoo":        "emerge dev-qt/qttools:6",
    "fedora":        "dnf install qt6-qttools-devel",
    "rhel":          "dnf install qt6-qttools-devel",
    "centos":        "dnf install qt6-qttools-devel",
    "opensuse":      "zypper install qt6-core-devel",
    "debian":        "apt install qt6-base-dev-tools",
    "ubuntu":        "apt install qt6-base-dev-tools",
    "alpine":        "apk add qt6-qttools-dev",
    "void":          "xbps-install -S qt6-tools-devel",
    "nixos":         "nix-shell -p qt6.qttools",
    "solus":         "eopkg install qt6-tools-devel",
}


def qt6_install_hint() -> str:
    """Install command for Qt6 dev tools on this distro; falls back to
    ID_LIKE parents, then a generic multi-distro hint."""
    distro = current_distro()
    if distro in _QT6_TOOLS_HINTS:
        return _QT6_TOOLS_HINTS[distro]
    for parent in distro_id_like():
        if parent in _QT6_TOOLS_HINTS:
            return _QT6_TOOLS_HINTS[parent]
    return ("Install Qt6 dev tooling for your distro. "
            + " | ".join(f"{k}: {v}" for k, v in _QT6_TOOLS_HINTS.items()))


# Consulted only when no Qt6 query tool is installed AND the dir exists
# on disk; otherwise Qt6PathsMissing — never guess a scan path.
_QT6_LIBDIR_FALLBACK: dict[str, str] = {
    # Arch-family (all share /usr/lib/qt6 layout)
    "arch":          "/usr/lib/qt6",
    "cachyos":       "/usr/lib/qt6",
    "manjaro":       "/usr/lib/qt6",
    "endeavouros":   "/usr/lib/qt6",
    "garuda":        "/usr/lib/qt6",
    "artix":         "/usr/lib/qt6",
    "kaos":          "/usr/lib/qt6",
    # SteamOS 3.x is Arch-based + immutable; paths work, /usr writes
    # need `steamos-readonly disable` first.
    "steamos":       "/usr/lib/qt6",
    "holoiso":       "/usr/lib/qt6",
    # Gentoo-family
    "gentoo":        "/usr/lib64/qt6",
    # RPM-family (all use /usr/lib64)
    "fedora":        "/usr/lib64/qt6",
    "rhel":          "/usr/lib64/qt6",
    "centos":        "/usr/lib64/qt6",
    "nobara":        "/usr/lib64/qt6",
    "rocky":         "/usr/lib64/qt6",
    "almalinux":     "/usr/lib64/qt6",
    "openmandriva":  "/usr/lib64/qt6",
    "mageia":        "/usr/lib64/qt6",
    # SUSE-family
    "opensuse":      "/usr/lib64/qt6",
    "opensuse-tumbleweed": "/usr/lib64/qt6",
    "opensuse-leap": "/usr/lib64/qt6",
}


def _fallback_qt6_libdir() -> Path | None:
    distro = current_distro()
    libdir = _QT6_LIBDIR_FALLBACK.get(distro)
    if libdir is None:
        for parent in distro_id_like():
            libdir = _QT6_LIBDIR_FALLBACK.get(parent)
            if libdir:
                break
    if libdir is None:
        return None
    p = Path(libdir)
    return p if p.is_dir() else None


def qt6_plugins_dir() -> Path:
    """The dir Qt6 actually scans for plugins: qmake6 / qtpaths6 /
    pkg-config, else the on-disk per-distro fallback, else
    :class:`Qt6PathsMissing`."""
    global _QT_PLUGINS_CACHE
    if _QT_PLUGINS_CACHE is not None:
        return _QT_PLUGINS_CACHE
    reported = _qt6_plugins_query()
    if reported is not None:
        _QT_PLUGINS_CACHE = Path(reported)
        return _QT_PLUGINS_CACHE
    libdir = _fallback_qt6_libdir()
    if libdir is not None:
        candidate = libdir / "plugins"
        if candidate.is_dir():
            _QT_PLUGINS_CACHE = candidate
            return _QT_PLUGINS_CACHE
    raise Qt6PathsMissing(
        "No Qt6 query tool found (qmake6 / qtpaths6 / pkg-config) and no "
        "fallback plugin directory exists on disk. Install with: "
        f"{qt6_install_hint()}"
    )


def qt6_qml_dir() -> Path:
    """Qt6 QML module dir; same detection + fallback rules as
    :func:`qt6_plugins_dir`."""
    global _QT_QML_CACHE
    if _QT_QML_CACHE is not None:
        return _QT_QML_CACHE
    reported = _qt6_qml_query()
    if reported is not None:
        _QT_QML_CACHE = Path(reported)
        return _QT_QML_CACHE
    libdir = _fallback_qt6_libdir()
    if libdir is not None:
        candidate = libdir / "qml"
        if candidate.is_dir():
            _QT_QML_CACHE = candidate
            return _QT_QML_CACHE
    raise Qt6PathsMissing(
        "No Qt6 query tool found (qmake6 / pkg-config) and no fallback "
        "QML directory exists on disk. Install with: "
        f"{qt6_install_hint()}"
    )


# ── System libdir (32-bit vs 64-bit vs multiarch) ────────────────────


def system_lib_dir() -> Path:
    """System 64-bit libdir, derived from the Qt6 plugin dir
    (``/usr/lib64/qt6/plugins`` → ``/usr/lib64``) so it matches the
    distro's actual convention."""
    parent = qt6_plugins_dir().parent
    if parent.name == "qt6":
        return parent.parent
    return parent


# ── Package manager + per-distro package name map ────────────────────
#
# deps() tokens are ``<cmd>:<arch-pkg>``; this table translates the Arch
# package name to the current distro's. Add a distro by adding rows.

_PACKAGE_MAP: dict[str, dict[str, str]] = {
    "g++": {
        "arch":     "gcc",
        "debian":   "g++",
        "ubuntu":   "g++",
        "fedora":   "gcc-c++",
        "rhel":     "gcc-c++",
        "centos":   "gcc-c++",
        "opensuse": "gcc-c++",
        "alpine":   "g++",
        "void":     "gcc",
        "gentoo":   "sys-devel/gcc",
    },
    # Separate row so qt6_install_hint() stays the single source of the
    # human-facing message.
    "qmake6": {
        "arch":     "qt6-tools",
        "debian":   "qt6-base-dev-tools",
        "ubuntu":   "qt6-base-dev-tools",
        "fedora":   "qt6-qttools-devel",
        "rhel":     "qt6-qttools-devel",
        "opensuse": "qt6-core-devel",
        "gentoo":   "dev-qt/qttools:6",
    },
    # Package AND binary names vary per distro (Fedora ships
    # ``qdbus-qt6``, not ``qdbus6`` — hence utils.qdbus_cmd() probes
    # several names). Values confirmed via container probes (2026-05).
    "qdbus6": {
        "arch":     "qt6-tools",
        "debian":   "qdbus-qt6",
        "ubuntu":   "qdbus-qt6",
        "fedora":   "qt6-qttools",
        "rhel":     "qt6-qttools",
        "centos":   "qt6-qttools",
        "opensuse": "qt6-tools-qdbus",
        "alpine":   "qt6-qttools",
        "void":     "qt6-tools",
        "gentoo":   "dev-qt/qttools",
    },
    "kvantummanager": {
        "arch":     "kvantum",
        "fedora":   "kvantum",
        "rhel":     "kvantum",
        "centos":   "kvantum",
        "opensuse": "kvantum-manager",
        "debian":   "qt-style-kvantum",
        "ubuntu":   "qt-style-kvantum",
        "alpine":   "kvantum-qt6",
        "void":     "kvantum",
        "gentoo":   "x11-themes/kvantum",
    },
    # Fedora splits plymouth-set-default-theme into plymouth-scripts.
    "plymouth-set-default-theme": {
        "arch":     "plymouth",
        "debian":   "plymouth",
        "ubuntu":   "plymouth",
        "fedora":   "plymouth-scripts",
        "rhel":     "plymouth-scripts",
        "centos":   "plymouth-scripts",
        "opensuse": "plymouth",
        "alpine":   "plymouth",
        "void":     "plymouth",
        "gentoo":   "sys-boot/plymouth",
    },
    # Fedora splits the script renderer out of base plymouth; other
    # distros fall through to the main package.
    "plymouth-script-plugin": {
        "fedora":   "plymouth-plugin-script",
        "rhel":     "plymouth-plugin-script",
        "centos":   "plymouth-plugin-script",
    },
    # Fedora's canonical /usr/bin/pkg-config provider is the
    # ``pkgconf-pkg-config`` shim; plain ``pkgconf`` doesn't exist there.
    "pkg-config": {
        "arch":     "pkgconf",
        "debian":   "pkgconf",
        "ubuntu":   "pkgconf",
        "fedora":   "pkgconf-pkg-config",
        "rhel":     "pkgconf-pkg-config",
        "centos":   "pkgconf-pkg-config",
        "opensuse": "pkgconf-pkg-config",
        "alpine":   "pkgconf",
        "void":     "pkgconf",
        "gentoo":   "dev-util/pkgconf",
    },
    # desktop-file-utils everywhere; only Gentoo needs the category prefix.
    "update-desktop-database": {
        "gentoo":   "dev-util/desktop-file-utils",
    },
    "fc-cache": {
        "arch":     "fontconfig",
        "debian":   "fontconfig",
        "ubuntu":   "fontconfig",
        "fedora":   "fontconfig",
        "rhel":     "fontconfig",
        "centos":   "fontconfig",
        "opensuse": "fontconfig",
        "alpine":   "fontconfig",
        "void":     "fontconfig",
        "gentoo":   "media-libs/fontconfig",
    },
    # openSUSE splits cmake-full / cmake-mini; the ``cmake`` virtual
    # pulls full, so plain "cmake" stays safe everywhere.
    "cmake": {
        "arch":     "cmake",
        "debian":   "cmake",
        "ubuntu":   "cmake",
        "fedora":   "cmake",
        "rhel":     "cmake",
        "centos":   "cmake",
        "opensuse": "cmake",
        "alpine":   "cmake",
        "void":     "cmake",
        "gentoo":   "dev-build/cmake",
    },
    "ecm": {
        "arch":     "extra-cmake-modules",
        "debian":   "extra-cmake-modules",
        "ubuntu":   "extra-cmake-modules",
        "fedora":   "extra-cmake-modules",
        "rhel":     "extra-cmake-modules",
        "centos":   "extra-cmake-modules",
        "opensuse": "kf6-extra-cmake-modules",
        "alpine":   "extra-cmake-modules",
        "void":     "extra-cmake-modules",
        "gentoo":   "kde-frameworks/extra-cmake-modules",
    },
    # CMake component providers. openSUSE splits per-component -devel
    # packages, so each component is its own logical dep.
    "qt6-gui-cmake": {
        "arch":     "qt6-base",
        "debian":   "qt6-base-dev",
        "ubuntu":   "qt6-base-dev",
        "fedora":   "qt6-qtbase-devel",
        "rhel":     "qt6-qtbase-devel",
        "centos":   "qt6-qtbase-devel",
        "opensuse": "qt6-gui-devel",
        "alpine":   "qt6-qtbase-dev",
        "void":     "qt6-base-devel",
        "gentoo":   "dev-qt/qtbase:6",
    },
    "qt6-widgets-cmake": {
        "arch":     "qt6-base",
        "debian":   "qt6-base-dev",
        "ubuntu":   "qt6-base-dev",
        "fedora":   "qt6-qtbase-devel",
        "rhel":     "qt6-qtbase-devel",
        "centos":   "qt6-qtbase-devel",
        "opensuse": "qt6-widgets-devel",
        "alpine":   "qt6-qtbase-dev",
        "void":     "qt6-base-devel",
        "gentoo":   "dev-qt/qtbase:6",
    },
    "qt6-dbus-cmake": {
        "arch":     "qt6-base",
        "debian":   "qt6-base-dev",
        "ubuntu":   "qt6-base-dev",
        "fedora":   "qt6-qtbase-devel",
        "rhel":     "qt6-qtbase-devel",
        "centos":   "qt6-qtbase-devel",
        "opensuse": "qt6-dbus-devel",
        "alpine":   "qt6-qtbase-dev",
        "void":     "qt6-base-devel",
        "gentoo":   "dev-qt/qtbase:6",
    },
    "qt6-qml-cmake": {
        "arch":     "qt6-declarative",
        "debian":   "qt6-declarative-dev",
        "ubuntu":   "qt6-declarative-dev",
        "fedora":   "qt6-qtdeclarative-devel",
        "rhel":     "qt6-qtdeclarative-devel",
        "centos":   "qt6-qtdeclarative-devel",
        "opensuse": "qt6-qml-devel",
        "alpine":   "qt6-qtdeclarative-dev",
        "void":     "qt6-declarative-devel",
        "gentoo":   "dev-qt/qtdeclarative:6",
    },
    "qt6-uitools-cmake": {
        "arch":     "qt6-tools",
        "debian":   "qt6-tools-dev",
        "ubuntu":   "qt6-tools-dev",
        "fedora":   "qt6-qttools-devel",
        "rhel":     "qt6-qttools-devel",
        "centos":   "qt6-qttools-devel",
        "opensuse": "qt6-uitools-devel",
        "alpine":   "qt6-qttools-dev",
        "void":     "qt6-tools",
        "gentoo":   "dev-qt/qttools:6",
    },
    "make": {
        "arch":     "make",
        "debian":   "make",
        "ubuntu":   "make",
        "fedora":   "make",
        "rhel":     "make",
        "centos":   "make",
        "opensuse": "make",
        "alpine":   "make",
        "void":     "make",
        # 2026-06: Gentoo moved make sys-devel/ → dev-build/ (like cmake).
        "gentoo":   "dev-build/make",
    },
    # Extracts the bundled offline icon tarballs (src/offline/icons/*.tar.zst).
    "zstd": {
        "arch":     "zstd",
        "debian":   "zstd",
        "ubuntu":   "zstd",
        "fedora":   "zstd",
        "rhel":     "zstd",
        "centos":   "zstd",
        "opensuse": "zstd",
        "alpine":   "zstd",
        "void":     "zstd",
        "gentoo":   "app-arch/zstd",
    },
    # ── KF6 frameworks ────────────────────────────────────────────────
    # Tokens are cmake component names prefixed ``kf6-`` so they never
    # collide with a real binary — the shutil.which probe is bypassed
    # for them (see preflight). Values probed via containers (2026-06).
    "kf6-config-cmake": {
        "arch":     "kconfig",
        "fedora":   "kf6-kconfig-devel",
        "rhel":     "kf6-kconfig-devel",
        "centos":   "kf6-kconfig-devel",
        "opensuse": "kf6-kconfig-devel",
        "gentoo":   "kde-frameworks/kconfig:6",
    },
    "kf6-configwidgets-cmake": {
        "arch":     "kconfigwidgets",
        "fedora":   "kf6-kconfigwidgets-devel",
        "rhel":     "kf6-kconfigwidgets-devel",
        "centos":   "kf6-kconfigwidgets-devel",
        "opensuse": "kf6-kconfigwidgets-devel",
        "gentoo":   "kde-frameworks/kconfigwidgets:6",
    },
    "kf6-coreaddons-cmake": {
        "arch":     "kcoreaddons",
        "fedora":   "kf6-kcoreaddons-devel",
        "rhel":     "kf6-kcoreaddons-devel",
        "centos":   "kf6-kcoreaddons-devel",
        "opensuse": "kf6-kcoreaddons-devel",
        "gentoo":   "kde-frameworks/kcoreaddons:6",
    },
    "kf6-crash-cmake": {
        "arch":     "kcrash",
        "fedora":   "kf6-kcrash-devel",
        "rhel":     "kf6-kcrash-devel",
        "centos":   "kf6-kcrash-devel",
        "opensuse": "kf6-kcrash-devel",
        "gentoo":   "kde-frameworks/kcrash:6",
    },
    "kf6-globalaccel-cmake": {
        "arch":     "kglobalaccel",
        "fedora":   "kf6-kglobalaccel-devel",
        "rhel":     "kf6-kglobalaccel-devel",
        "centos":   "kf6-kglobalaccel-devel",
        "opensuse": "kf6-kglobalaccel-devel",
        "gentoo":   "kde-frameworks/kglobalaccel:6",
    },
    "kf6-guiaddons-cmake": {
        "arch":     "kguiaddons",
        "fedora":   "kf6-kguiaddons-devel",
        "rhel":     "kf6-kguiaddons-devel",
        "centos":   "kf6-kguiaddons-devel",
        "opensuse": "kf6-kguiaddons-devel",
        "gentoo":   "kde-frameworks/kguiaddons:6",
    },
    "kf6-i18n-cmake": {
        "arch":     "ki18n",
        "fedora":   "kf6-ki18n-devel",
        "rhel":     "kf6-ki18n-devel",
        "centos":   "kf6-ki18n-devel",
        "opensuse": "kf6-ki18n-devel",
        "gentoo":   "kde-frameworks/ki18n:6",
    },
    "kf6-kcmutils-cmake": {
        "arch":     "kcmutils",
        "fedora":   "kf6-kcmutils-devel",
        "rhel":     "kf6-kcmutils-devel",
        "centos":   "kf6-kcmutils-devel",
        "opensuse": "kf6-kcmutils-devel",
        "gentoo":   "kde-frameworks/kcmutils:6",
    },
    "kf6-kio-cmake": {
        "arch":     "kio",
        "fedora":   "kf6-kio-devel",
        "rhel":     "kf6-kio-devel",
        "centos":   "kf6-kio-devel",
        "opensuse": "kf6-kio-devel",
        "gentoo":   "kde-frameworks/kio:6",
    },
    "kf6-notifications-cmake": {
        "arch":     "knotifications",
        "fedora":   "kf6-knotifications-devel",
        "rhel":     "kf6-knotifications-devel",
        "centos":   "kf6-knotifications-devel",
        "opensuse": "kf6-knotifications-devel",
        "gentoo":   "kde-frameworks/knotifications:6",
    },
    "kf6-service-cmake": {
        "arch":     "kservice",
        "fedora":   "kf6-kservice-devel",
        "rhel":     "kf6-kservice-devel",
        "centos":   "kf6-kservice-devel",
        "opensuse": "kf6-kservice-devel",
        "gentoo":   "kde-frameworks/kservice:6",
    },
    "kf6-widgetsaddons-cmake": {
        "arch":     "kwidgetsaddons",
        "fedora":   "kf6-kwidgetsaddons-devel",
        "rhel":     "kf6-kwidgetsaddons-devel",
        "centos":   "kf6-kwidgetsaddons-devel",
        "opensuse": "kf6-kwidgetsaddons-devel",
        "gentoo":   "kde-frameworks/kwidgetsaddons:6",
    },
    "kf6-windowsystem-cmake": {
        "arch":     "kwindowsystem",
        "fedora":   "kf6-kwindowsystem-devel",
        "rhel":     "kf6-kwindowsystem-devel",
        "centos":   "kf6-kwindowsystem-devel",
        "opensuse": "kf6-kwindowsystem-devel",
        "gentoo":   "kde-frameworks/kwindowsystem:6",
    },
    "kf6-itemmodels-cmake": {
        "arch":     "kitemmodels",
        "fedora":   "kf6-kitemmodels-devel",
        "rhel":     "kf6-kitemmodels-devel",
        "centos":   "kf6-kitemmodels-devel",
        "opensuse": "kf6-kitemmodels-devel",
        "gentoo":   "kde-frameworks/kitemmodels:6",
    },
    # ── Plasma / KSysGuard / plasma-workspace ─────────────────────────
    "plasma-cmake": {
        "arch":     "libplasma",
        "fedora":   "libplasma-devel",
        "rhel":     "libplasma-devel",
        "centos":   "libplasma-devel",
        "opensuse": "libplasma6-devel",
        "gentoo":   "kde-plasma/libplasma",
    },
    "plasma-activities-cmake": {
        "arch":     "plasma-activities",
        "fedora":   "plasma-activities-devel",
        "rhel":     "plasma-activities-devel",
        "centos":   "plasma-activities-devel",
        "opensuse": "plasma6-activities-devel",
        "gentoo":   "kde-plasma/plasma-activities",
    },
    "plasma-activities-stats-cmake": {
        "arch":     "plasma-activities-stats",
        "fedora":   "plasma-activities-stats-devel",
        "rhel":     "plasma-activities-stats-devel",
        "centos":   "plasma-activities-stats-devel",
        "opensuse": "plasma6-activities-stats-devel",
        "gentoo":   "kde-plasma/plasma-activities-stats",
    },
    "ksysguard-cmake": {
        "arch":     "libksysguard",
        "fedora":   "libksysguard-devel",
        "rhel":     "libksysguard-devel",
        "centos":   "libksysguard-devel",
        "opensuse": "libksysguard6-devel",
        "gentoo":   "kde-plasma/libksysguard",
    },
    # plasma-workspace ships both cmake configs in one -devel package;
    # separate tokens keep preflight failure messages precise.
    "libnotificationmanager-cmake": {
        "arch":     "plasma-workspace",
        "fedora":   "plasma-workspace-devel",
        "rhel":     "plasma-workspace-devel",
        "centos":   "plasma-workspace-devel",
        "opensuse": "plasma6-workspace-devel",
        "gentoo":   "kde-plasma/plasma-workspace",
    },
    "libtaskmanager-cmake": {
        "arch":     "plasma-workspace",
        "fedora":   "plasma-workspace-devel",
        "rhel":     "plasma-workspace-devel",
        "centos":   "plasma-workspace-devel",
        "opensuse": "plasma6-workspace-devel",
        "gentoo":   "kde-plasma/plasma-workspace",
    },
    # ── KWin + KDecoration (acrylic-glass effect) ─────────────────────
    "kwin-cmake": {
        "arch":     "kwin",
        "fedora":   "kwin-devel",
        "rhel":     "kwin-devel",
        "centos":   "kwin-devel",
        "opensuse": "kwin6-devel",
        "gentoo":   "kde-plasma/kwin",
    },
    "kdecoration-cmake": {
        "arch":     "kdecoration",
        "fedora":   "kdecoration-devel",
        "rhel":     "kdecoration-devel",
        "centos":   "kdecoration-devel",
        "opensuse": "kdecoration6-devel",
        "gentoo":   "kde-plasma/kdecoration",
    },
    # ── libepoxy + X11 / XCB headers ──────────────────────────────────
    "epoxy-cmake": {
        "arch":     "libepoxy",
        "debian":   "libepoxy-dev",
        "ubuntu":   "libepoxy-dev",
        "fedora":   "libepoxy-devel",
        "rhel":     "libepoxy-devel",
        "centos":   "libepoxy-devel",
        "opensuse": "libepoxy-devel",
        "alpine":   "libepoxy-dev",
        "void":     "libepoxy-devel",
        "gentoo":   "media-libs/libepoxy",
    },
    "x11-cmake": {
        "arch":     "libx11",
        "debian":   "libx11-dev",
        "ubuntu":   "libx11-dev",
        "fedora":   "libX11-devel",
        "rhel":     "libX11-devel",
        "centos":   "libX11-devel",
        "opensuse": "libX11-devel",
        "alpine":   "libx11-dev",
        "void":     "libX11-devel",
        "gentoo":   "x11-libs/libX11",
    },
    "xcb-cmake": {
        "arch":     "libxcb",
        "debian":   "libxcb1-dev",
        "ubuntu":   "libxcb1-dev",
        "fedora":   "libxcb-devel",
        "rhel":     "libxcb-devel",
        "centos":   "libxcb-devel",
        "opensuse": "libxcb-devel",
        "alpine":   "libxcb-dev",
        "void":     "libxcb-devel",
        "gentoo":   "x11-libs/libxcb",
    },
    # Vulkan loader + headers — needed transitively by KWin 6.7+'s config.
    "vulkan-loader-cmake": {
        "arch":     "vulkan-icd-loader",
        "debian":   "libvulkan-dev",
        "ubuntu":   "libvulkan-dev",
        "fedora":   "vulkan-loader-devel",
        "rhel":     "vulkan-loader-devel",
        "centos":   "vulkan-loader-devel",
        # openSUSE ships the loader dev files in `vulkan-devel`, NOT
        # `vulkan-loader` (`zypper install vulkan-loader` → not found/104).
        "opensuse": "vulkan-devel",
        "alpine":   "vulkan-loader-dev",
        "void":     "Vulkan-Loader-devel",
        "gentoo":   "media-libs/vulkan-loader",
    },
    # vulkan/vulkan.h — split from the loader on Fedora/openSUSE.
    "vulkan-headers-cmake": {
        "arch":     "vulkan-headers",
        "debian":   "libvulkan-dev",
        "ubuntu":   "libvulkan-dev",
        "fedora":   "vulkan-headers",
        "rhel":     "vulkan-headers",
        "centos":   "vulkan-headers",
        "opensuse": "vulkan-headers",
        "alpine":   "vulkan-headers",
        "void":     "Vulkan-Headers",
        "gentoo":   "dev-util/vulkan-headers",
    },
}


def package_for(cmd: str, fallback_pkg: str | None = None) -> str:
    """Translate a deps() cmd token to this distro's package name;
    ``fallback_pkg`` (the Arch name) covers tokens absent from the map."""
    distro = current_distro()
    row = _PACKAGE_MAP.get(cmd, {})
    if distro in row:
        return row[distro]
    for parent in distro_id_like():
        if parent in row:
            return row[parent]
    return fallback_pkg or cmd


_PACKAGE_MANAGER_INSTALL: dict[str, list[str]] = {
    # Root, NON-INTERACTIVE — every entry carries its assume-yes flag.
    # Debian/Ubuntu/Alpine/Void absent on purpose (no KF6 -cmake rows
    # in _PACKAGE_MAP) → UnsupportedDistroError.
    "arch":     ["pacman", "-S", "--noconfirm", "--needed"],
    "gentoo":   ["emerge", "--ask=n", "--quiet", "--noreplace"],
    "fedora":   ["dnf", "install", "-y"],
    "rhel":     ["dnf", "install", "-y"],
    "centos":   ["dnf", "install", "-y"],
    "opensuse": ["zypper", "--non-interactive", "install", "--no-recommends"],
}

# Sync the db first or a stale db 404s on rotated mirrors. None = the
# install command refreshes on its own.
_PACKAGE_MANAGER_SYNC: dict[str, list[str] | None] = {
    "arch":     ["pacman", "-Sy", "--noconfirm"],
    "gentoo":   None,
    "fedora":   None,
    "rhel":     None,
    "centos":   None,
    "opensuse": None,
}


def package_manager_sync_cmd() -> list[str] | None:
    """Db-refresh command for this distro, or None if install refreshes
    on its own. Raises UnsupportedDistroError like the install variant."""
    distro = current_distro()
    for name in (distro, *distro_id_like()):
        if name in _PACKAGE_MANAGER_SYNC:
            cmd = _PACKAGE_MANAGER_SYNC[name]
            return list(cmd) if cmd else None
    raise UnsupportedDistroError(
        f"No package manager mapping for distro {distro!r}. "
        f"Add a row to distro._PACKAGE_MANAGER_SYNC."
    )


class UnsupportedDistroError(RuntimeError):
    """Current os-release id has no package-manager mapping; callers
    bail cleanly or fall through to a manual install hint."""


def package_manager_install_cmd() -> list[str]:
    """Non-interactive install command prefix (caller appends packages).
    Raises :class:`UnsupportedDistroError` for unmapped distros."""
    distro = current_distro()
    if distro in _PACKAGE_MANAGER_INSTALL:
        return list(_PACKAGE_MANAGER_INSTALL[distro])
    for parent in distro_id_like():
        if parent in _PACKAGE_MANAGER_INSTALL:
            return list(_PACKAGE_MANAGER_INSTALL[parent])
    raise UnsupportedDistroError(
        f"No package manager mapping for distro {distro!r}. "
        f"Add a row to distro._PACKAGE_MANAGER_INSTALL."
    )


_PLASMA_VERSION_PACKAGES: dict[str, tuple[str, ...]] = {
    "arch": ("plasma-workspace",),
    "fedora": ("plasma-workspace",),
    "rhel": ("plasma-workspace",),
    "centos": ("plasma-workspace",),
    "debian": ("plasma-workspace",),
    "ubuntu": ("plasma-workspace",),
    # openSUSE renamed the Plasma 6 packages; keep fallbacks.
    "opensuse": ("plasma6-workspace", "plasma6-desktop", "plasma-workspace"),
}


def _package_version_query_builder():
    distro = current_distro()
    family = (distro, *distro_id_like())
    if any(name in ("fedora", "rhel", "centos", "opensuse") for name in family):
        return lambda pkg: ["rpm", "-q", "--qf", "%{VERSION}\n", pkg]
    if "arch" in family:
        return lambda pkg: ["pacman", "-Q", pkg]
    if any(name in ("debian", "ubuntu") for name in family):
        return lambda pkg: ["dpkg-query", "-W", "-f=${Version}\n", pkg]
    return None


def package_installed(pkg: str) -> bool:
    """True when the package manager reports ``pkg`` installed; False
    when the distro has no query builder (caller just attempts install)."""
    build_cmd = _package_version_query_builder()
    if build_cmd is None:
        return False
    return _run_query(build_cmd(pkg)) is not None


def plasma_version_probe_cmds() -> tuple[list[str], ...]:
    """Package-metadata fallback probes for the Plasma version —
    ``plasmashell --version`` hangs or returns nothing on some sessions."""
    distro = current_distro()
    packages = _PLASMA_VERSION_PACKAGES.get(distro)
    if packages is None:
        for parent in distro_id_like():
            packages = _PLASMA_VERSION_PACKAGES.get(parent)
            if packages:
                break
    if not packages:
        return ()
    build_cmd = _package_version_query_builder()
    if build_cmd is None:
        return ()
    return tuple(build_cmd(pkg) for pkg in packages)
