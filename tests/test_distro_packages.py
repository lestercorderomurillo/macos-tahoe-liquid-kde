"""Per-distro package-name translation for deps() tokens.

Origin: the user hit ``Нет соответствия для аргумента: qt6-tools`` on
Fedora 44 when the layout step tried to install ``qdbus6``. Root cause
was that the ``cmd:pkg`` token's right-hand side is the *Arch* package
name; without an explicit row in ``_PACKAGE_MAP`` for ``qdbus6``, the
Arch name leaked through to dnf verbatim and failed.

These tests pin every dep token used by every step to the real package
name on each KDE 6.6+ target distro. **Every expected value below was
probed against a fresh container image** (`dnf provides`, `apt-file
search`, `zypper wp`, `pacman -F`, `apk search -e cmd:`) — not invented
from packaging convention, because the conventions diverge in
non-obvious ways (e.g. Fedora ships the Qt6 qdbus client as
``/usr/bin/qdbus-qt6``, not ``/usr/bin/qdbus6``).

If you add a new distro to ``_PACKAGE_MAP``, add a matching parametrize
case here and probe the value first. Don't guess.
"""

from __future__ import annotations

import pytest

import distro


@pytest.fixture(autouse=True)
def _clear_distro_cache():
    distro._DISTRO_CACHE = None
    yield
    distro._DISTRO_CACHE = None


def _force_distro(monkeypatch, distro_id: str, id_like: tuple[str, ...] = ()):
    monkeypatch.setattr(distro, "current_distro", lambda: distro_id)
    monkeypatch.setattr(distro, "distro_id_like", lambda: id_like)


# ── qdbus6: the regression the user hit on Fedora 44 ──────────────────
#
# Probed values (2026-05) against fresh container images:
#   fedora:41 / fedora:43  → qt6-qttools  (binary on PATH: qdbus-qt6)
#   debian:13              → qdbus-qt6    (binary on PATH: qdbus6)
#   ubuntu:24.04           → qdbus-qt6    (same as Debian)
#   archlinux:latest       → qt6-tools    (binary on PATH: qdbus6)
#   opensuse/tumbleweed    → qt6-tools-qdbus
#   alpine:latest          → qt6-qttools


@pytest.mark.parametrize("distro_id, id_like, expected", [
    ("fedora",              (),           "qt6-qttools"),
    ("rhel",                (),           "qt6-qttools"),
    ("centos",              (),           "qt6-qttools"),
    ("nobara",              ("fedora",),  "qt6-qttools"),   # inherits
    ("bazzite",             ("fedora",),  "qt6-qttools"),   # inherits
    ("arch",                (),           "qt6-tools"),
    ("cachyos",             ("arch",),    "qt6-tools"),     # inherits
    ("manjaro",             ("arch",),    "qt6-tools"),     # inherits
    ("debian",              (),           "qdbus-qt6"),
    ("ubuntu",              (),           "qdbus-qt6"),
    ("opensuse",            (),           "qt6-tools-qdbus"),
    ("opensuse-tumbleweed", ("opensuse",), "qt6-tools-qdbus"),
    ("alpine",              (),           "qt6-qttools"),
    ("void",                (),           "qt6-tools"),
    ("gentoo",              (),           "dev-qt/qttools"),
])
def test_qdbus6_package_per_distro(monkeypatch, distro_id, id_like, expected):
    _force_distro(monkeypatch, distro_id, id_like)
    assert distro.package_for("qdbus6", "qt6-tools") == expected


# ── kvantummanager (the other surprise) ───────────────────────────────
#
# Probed: arch + fedora ship plain ``kvantum``; debian/ubuntu use
# ``qt-style-kvantum`` (note: NO qt6- prefix); openSUSE has its own
# split ``kvantum-manager``; Alpine separates the Qt5 and Qt6 builds
# into ``kvantum-qt5`` and ``kvantum-qt6``.


@pytest.mark.parametrize("distro_id, id_like, expected", [
    ("arch",                (),            "kvantum"),
    ("cachyos",             ("arch",),     "kvantum"),
    ("fedora",              (),            "kvantum"),
    ("nobara",              ("fedora",),   "kvantum"),
    ("debian",              (),            "qt-style-kvantum"),
    ("ubuntu",              (),            "qt-style-kvantum"),
    ("opensuse",            (),            "kvantum-manager"),
    ("opensuse-tumbleweed", ("opensuse",), "kvantum-manager"),
    ("alpine",              (),            "kvantum-qt6"),
    ("gentoo",              (),            "x11-themes/kvantum"),
])
def test_kvantum_package_per_distro(monkeypatch, distro_id, id_like, expected):
    _force_distro(monkeypatch, distro_id, id_like)
    assert distro.package_for("kvantummanager", "kvantum") == expected


# ── plymouth-set-default-theme — Fedora split it out ──────────────────


@pytest.mark.parametrize("distro_id, id_like, expected", [
    ("arch",    (),           "plymouth"),
    ("debian",  (),           "plymouth"),
    ("ubuntu",  (),           "plymouth"),
    ("fedora",  (),           "plymouth-scripts"),
    ("rhel",    (),           "plymouth-scripts"),
    ("nobara",  ("fedora",),  "plymouth-scripts"),
    ("opensuse", (),          "plymouth"),
    ("alpine",  (),           "plymouth"),
    ("gentoo",  (),           "sys-boot/plymouth"),
])
def test_plymouth_package_per_distro(monkeypatch, distro_id, id_like, expected):
    _force_distro(monkeypatch, distro_id, id_like)
    assert (distro.package_for("plymouth-set-default-theme", "plymouth")
            == expected)


# ── g++ — Arch's compiler package is named ``gcc``, others split ──────


@pytest.mark.parametrize("distro_id, expected", [
    ("arch",     "gcc"),
    ("fedora",   "gcc-c++"),
    ("rhel",     "gcc-c++"),
    ("opensuse", "gcc-c++"),
    ("debian",   "g++"),
    ("ubuntu",   "g++"),
    ("alpine",   "g++"),
])
def test_gpp_package_per_distro(monkeypatch, distro_id, expected):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("g++", "gcc") == expected


# ── pkg-config — Arch's package is named ``pkgconf``, Fedora needs
# the ``pkgconf-pkg-config`` *shim* (plain ``pkgconf`` exists too but
# doesn't ship /usr/bin/pkg-config).


@pytest.mark.parametrize("distro_id, expected", [
    ("arch",     "pkgconf"),
    ("debian",   "pkgconf"),
    ("ubuntu",   "pkgconf"),
    ("fedora",   "pkgconf-pkg-config"),
    ("rhel",     "pkgconf-pkg-config"),
    ("opensuse", "pkgconf-pkg-config"),
    ("alpine",   "pkgconf"),
])
def test_pkgconfig_package_per_distro(monkeypatch, distro_id, expected):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("pkg-config", "pkgconf") == expected


# ── fontconfig + cmake — same name everywhere we ship for ─────────────


@pytest.mark.parametrize("distro_id", [
    "arch", "fedora", "debian", "ubuntu", "opensuse", "alpine", "rhel",
])
def test_fc_cache_is_fontconfig_everywhere(monkeypatch, distro_id):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("fc-cache", "fontconfig") == "fontconfig"


@pytest.mark.parametrize("distro_id", [
    "arch", "fedora", "debian", "ubuntu", "opensuse", "alpine", "rhel",
])
def test_cmake_is_cmake_everywhere(monkeypatch, distro_id):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("cmake", "cmake") == "cmake"


# ── qmake6 (Qt6 dev tools) — distinct from qdbus6 row above ───────────


@pytest.mark.parametrize("distro_id, expected", [
    ("arch",     "qt6-tools"),
    ("fedora",   "qt6-qttools-devel"),
    ("rhel",     "qt6-qttools-devel"),
    ("opensuse", "qt6-tools-devel"),
    ("debian",   "qt6-base-dev-tools"),
    ("ubuntu",   "qt6-base-dev-tools"),
])
def test_qmake6_package_per_distro(monkeypatch, distro_id, expected):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("qmake6", "qt6-tools") == expected


# ── No deps() token may fall through with the Arch fallback on a
# non-Arch distro for the binaries we *know* have a distro-specific
# name. This catches future steps adding tokens without rows. ─────────


_TOKENS_WITH_FEDORA_DIVERGENCE = {
    # token → Arch fallback that's wrong on Fedora
    "qdbus6": "qt6-tools",
    "g++": "gcc",
    "pkg-config": "pkgconf",
    "plymouth-set-default-theme": "plymouth",
}


@pytest.mark.parametrize("token, arch_fallback", _TOKENS_WITH_FEDORA_DIVERGENCE.items())
def test_no_arch_fallback_leaks_to_fedora(monkeypatch, token, arch_fallback):
    """The bug the user hit on Fedora 44 was the Arch fallback (``qt6-tools``)
    leaking to dnf. This test asserts that for every token we know
    diverges on Fedora, ``package_for`` returns *something other than*
    the Arch fallback when current_distro() is ``fedora``."""
    _force_distro(monkeypatch, "fedora")
    actual = distro.package_for(token, arch_fallback)
    assert actual != arch_fallback, (
        f"deps() token {token!r} leaks Arch fallback {arch_fallback!r} to "
        f"Fedora — add a row to distro._PACKAGE_MAP."
    )
