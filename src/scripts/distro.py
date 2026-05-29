"""Distro-detection layer.

Everything that varies between Linux distributions lives here:

* the Qt6 plugin / QML directories (Arch puts them under /usr/lib,
  Gentoo under /usr/lib64, Debian under /usr/lib/x86_64-linux-gnu);
* the system libdir suffix;
* the package manager + the package name for Qt6 dev tools;
* the /etc/os-release id used to pick the right package-manager hint.

The rest of the codebase imports from here so a refactor that adds
support for a new distro touches one file. Nothing else in the
codebase is allowed to hardcode ``/usr/lib/qt6`` or shell out to
``pacman`` / ``apt`` / ``dnf`` directly — call into this module.

Hard rule: never assume a path. If a Qt6 query tool isn't available,
raise :class:`Qt6PathsMissing` with a distro-appropriate hint instead
of falling back to a default that happens to work for one maintainer's
machine.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class Qt6PathsMissing(RuntimeError):
    """Qt6 plugin / QML directories could not be discovered because no
    Qt6 query tool (qmake6, qtpaths6, pkg-config Qt6Core) is on PATH.
    The installer refuses to guess — Plasma 6 won't load applets that
    sit outside Qt's actual scan path."""


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
    """Return the lowercase os-release ID (``arch``, ``cachyos``,
    ``gentoo``, ``fedora``, ``opensuse-tumbleweed``, ``debian``,
    ``ubuntu``, ...). Returns ``"unknown"`` when /etc/os-release is
    missing or unreadable — callers fall back to a generic hint."""
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
    """Return the os-release ID_LIKE chain in lowercase
    (``("arch",)`` for CachyOS, ``("debian",)`` for Ubuntu, ...). Used
    so a one-off downstream distro inherits its parent's package-manager
    hint without explicit per-id wiring."""
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


# Per-distro package-manager hint surfaced when qmake6 is missing.
# Keep the list short and grouped by base distro — downstreams reach
# the right hint through ID_LIKE in :func:`qt6_install_hint`.
_QT6_TOOLS_HINTS: dict[str, str] = {
    "arch":          "pacman -S qt6-tools",
    "gentoo":        "emerge dev-qt/qttools:6",
    "fedora":        "dnf install qt6-qttools-devel",
    "rhel":          "dnf install qt6-qttools-devel",
    "centos":        "dnf install qt6-qttools-devel",
    "opensuse":      "zypper install qt6-tools-devel",
    "debian":        "apt install qt6-base-dev-tools",
    "ubuntu":        "apt install qt6-base-dev-tools",
    "alpine":        "apk add qt6-qttools-dev",
    "void":          "xbps-install -S qt6-tools-devel",
    "nixos":         "nix-shell -p qt6.qttools",
    "solus":         "eopkg install qt6-tools-devel",
}


def qt6_install_hint() -> str:
    """One-line install command for Qt6 dev tools on the current
    distro, falling back to the parent (ID_LIKE) and then to a generic
    multi-distro hint when the distro is unknown."""
    distro = current_distro()
    if distro in _QT6_TOOLS_HINTS:
        return _QT6_TOOLS_HINTS[distro]
    for parent in distro_id_like():
        if parent in _QT6_TOOLS_HINTS:
            return _QT6_TOOLS_HINTS[parent]
    return ("Install Qt6 dev tooling for your distro. "
            + " | ".join(f"{k}: {v}" for k, v in _QT6_TOOLS_HINTS.items()))


# Per-distro Qt6 libdir fallback. Only consulted when none of the Qt6
# query tools (qmake6 / qtpaths6 / pkg-config) are installed — in which
# case we know the convention for this distro from /etc/os-release and
# verify the directory actually exists on disk before returning it.
# If neither qmake6 nor a real on-disk fallback exists, we raise
# Qt6PathsMissing — Plasma 6 won't load applets from a directory it
# doesn't scan, so refusing to install is safer than guessing.
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
    "bazzite":       "/usr/lib64/qt6",
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
    """The directory Qt6 actually scans for plugins. Queried from
    qmake6 / qtpaths6 / pkg-config in that order. If none of those
    tools are installed, fall back to the per-distro libdir convention
    (only when the directory actually exists on disk). Raises
    :class:`Qt6PathsMissing` only when neither a query tool nor a real
    fallback directory is available."""
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
    """The directory Qt6 scans for QML modules. Same detection +
    fallback rules as :func:`qt6_plugins_dir`."""
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
    """The directory under /usr that holds the system's 64-bit shared
    libraries. Derived from the Qt6 plugin dir (e.g. ``/usr/lib64/qt6``
    → ``/usr/lib64``) so it matches whatever convention the distro
    actually uses. Used by steps that drop helpers into a system
    libexec / aux dir alongside the Qt6 plugins."""
    parent = qt6_plugins_dir().parent
    # qt6_plugins_dir() typically returns .../lib/qt6/plugins; .parent
    # is .../lib/qt6, .parent.parent is .../lib (or .../lib64).
    if parent.name == "qt6":
        return parent.parent
    return parent


# ── Package manager + per-distro package name map ────────────────────
#
# Each step lists its build / runtime dependencies as ``<cmd>:<arch-pkg>``
# tokens — ``g++:gcc`` means "we shell out to g++; on Arch the package
# is ``gcc``". To install the missing package on a non-Arch host we
# need to translate the Arch package name into the equivalent name on
# the current distro. This table is the entire translation. Add a new
# distro by adding a row.

_PACKAGE_MAP: dict[str, dict[str, str]] = {
    # Each cmd-token maps distro-id → package name. The cmd-token is
    # whatever appears before the ``:`` in deps() — usually a binary
    # name (``g++``, ``cmake``) but occasionally a logical name
    # (``pkg-config``).
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
    # Qt6 dev tooling — separate row so qt6_install_hint() stays the
    # single source of truth for the human-facing install message.
    "qmake6": {
        "arch":     "qt6-tools",
        "debian":   "qt6-base-dev-tools",
        "ubuntu":   "qt6-base-dev-tools",
        "fedora":   "qt6-qttools-devel",
        "rhel":     "qt6-qttools-devel",
        "opensuse": "qt6-tools-devel",
        "gentoo":   "dev-qt/qttools:6",
    },
    # qdbus6 lives in different packages — and under different *binary
    # names* — per distro. Values below were confirmed against real
    # container probes (2026-05) by running `dnf provides`, `apt-file
    # search`, `zypper wp`, `pacman -F`, `apk search -e cmd:` against
    # fresh images. Don't trust convention — the binary name itself
    # varies (Fedora ships it as ``qdbus-qt6``, not ``qdbus6``), which
    # is why ``utils.qdbus_cmd()`` checks multiple binary names.
    "qdbus6": {
        "arch":     "qt6-tools",
        "debian":   "qdbus-qt6",          # was: qt6-tools-dev-tools (wrong)
        "ubuntu":   "qdbus-qt6",          # was: qt6-tools-dev-tools (wrong)
        "fedora":   "qt6-qttools",
        "rhel":     "qt6-qttools",
        "centos":   "qt6-qttools",
        "opensuse": "qt6-tools-qdbus",    # was: qt6-tools (wrong)
        "alpine":   "qt6-qttools",
        "void":     "qt6-tools",
        "gentoo":   "dev-qt/qttools",
    },
    # Kvantum Qt6 build. Probed names:
    #   Arch:        kvantum (Qt5 + Qt6 together)
    #   Fedora:      kvantum (single package, Qt5 + Qt6)
    #   Debian/Ubuntu: qt-style-kvantum (Qt6 build)
    #   openSUSE:    kvantum-manager
    #   Alpine:      kvantum-qt6 (Qt5 build is kvantum-qt5)
    #   Gentoo:      x11-themes/kvantum
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
    # Plymouth ships the helper script in different subpackages.
    # On Arch + Debian + openSUSE + Alpine the main ``plymouth`` package
    # carries ``plymouth-set-default-theme``; on Fedora it was split
    # into ``plymouth-scripts``.
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
    # fontconfig + pkgconf shim: the *binary* names are the same
    # everywhere but the package name varies, sometimes against the
    # Arch fallback (Fedora's ``pkgconf-pkg-config`` shim is the
    # canonical `/usr/bin/pkg-config` provider; plain ``pkgconf``
    # doesn't exist there).
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
    # cmake on openSUSE Tumbleweed is split — ``cmake-full`` includes
    # the GUI / docs, ``cmake-mini`` is the build-only flavour. Plain
    # ``cmake`` exists as a virtual that pulls full, so it's safe to
    # keep "cmake" everywhere, but document the split.
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
    # zstd — needed by the icons step to extract the bundled
    # offline tarball (src/offline/icons/*.tar.zst). Available in
    # base/core on every supported distro; the binary is plain
    # ``zstd`` everywhere and the package name matches except on
    # Gentoo (which uses category/name atoms).
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
}


def package_for(cmd: str, fallback_pkg: str | None = None) -> str:
    """Translate a deps() command token into the package name on the
    current distro. ``fallback_pkg`` (typically the Arch package name
    from the ``cmd:pkg`` token) is used when the command is unknown to
    the map — most KDE-side deps share a name across all five distros,
    so the table only needs entries where the names diverge."""
    distro = current_distro()
    row = _PACKAGE_MAP.get(cmd, {})
    if distro in row:
        return row[distro]
    for parent in distro_id_like():
        if parent in row:
            return row[parent]
    return fallback_pkg or cmd


_PACKAGE_MANAGER_INSTALL: dict[str, list[str]] = {
    # Each command is run as root. ``--noconfirm`` / ``-y`` / etc are
    # included so the call works non-interactively in a container too.
    "arch":     ["pacman", "-S", "--noconfirm", "--needed"],
    "gentoo":   ["emerge", "--quiet", "--noreplace"],
    "fedora":   ["dnf", "install", "-y"],
    "rhel":     ["dnf", "install", "-y"],
    "centos":   ["dnf", "install", "-y"],
    "opensuse": ["zypper", "--non-interactive", "install", "--no-recommends"],
    "debian":   ["apt-get", "install", "-y"],
    "ubuntu":   ["apt-get", "install", "-y"],
    "alpine":   ["apk", "add"],
    "void":     ["xbps-install", "-Sy"],
}


class UnsupportedDistroError(RuntimeError):
    """Current /etc/os-release id has no package manager mapping in
    :data:`_PACKAGE_MANAGER_INSTALL`. Surfaced so callers can decide
    whether to bail with a clear message or fall through to a manual
    install hint."""


def package_manager_install_cmd() -> list[str]:
    """Return the ``[binary, args...]`` prefix this distro's package
    manager expects for a non-interactive install. The caller appends
    package names. Raises :class:`UnsupportedDistroError` for any
    distro the map does not cover."""
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
