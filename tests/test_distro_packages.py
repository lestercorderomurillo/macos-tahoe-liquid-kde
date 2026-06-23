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


@pytest.mark.parametrize("distro_id, id_like, expected", [
    ("fedora",  (),           "plymouth-plugin-script"),
    ("rhel",    (),           "plymouth-plugin-script"),
    ("centos",  (),           "plymouth-plugin-script"),
    ("nobara",  ("fedora",),  "plymouth-plugin-script"),
])
def test_plymouth_script_plugin_package_per_fedora_family(
    monkeypatch, distro_id, id_like, expected,
):
    _force_distro(monkeypatch, distro_id, id_like)
    assert (distro.package_for("plymouth-script-plugin", "plymouth")
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


@pytest.mark.parametrize("distro_id, expected", [
    ("arch", "extra-cmake-modules"),
    ("fedora", "extra-cmake-modules"),
    ("debian", "extra-cmake-modules"),
    ("ubuntu", "extra-cmake-modules"),
    ("opensuse", "kf6-extra-cmake-modules"),
    ("alpine", "extra-cmake-modules"),
    ("rhel", "extra-cmake-modules"),
    ("gentoo", "kde-frameworks/extra-cmake-modules"),
])
def test_ecm_package_per_distro(monkeypatch, distro_id, expected):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("ecm", "extra-cmake-modules") == expected


@pytest.mark.parametrize("distro_id, expected", [
    ("arch", "qt6-base"),
    ("fedora", "qt6-qtbase-devel"),
    ("debian", "qt6-base-dev"),
    ("ubuntu", "qt6-base-dev"),
    ("opensuse", "qt6-gui-devel"),
    ("alpine", "qt6-qtbase-dev"),
    ("rhel", "qt6-qtbase-devel"),
    ("gentoo", "dev-qt/qtbase:6"),
])
def test_qt6_gui_cmake_package_per_distro(monkeypatch, distro_id, expected):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("qt6-gui-cmake", "qt6-base") == expected


@pytest.mark.parametrize("distro_id, expected", [
    ("arch", "qt6-base"),
    ("fedora", "qt6-qtbase-devel"),
    ("debian", "qt6-base-dev"),
    ("ubuntu", "qt6-base-dev"),
    ("opensuse", "qt6-widgets-devel"),
    ("alpine", "qt6-qtbase-dev"),
    ("rhel", "qt6-qtbase-devel"),
    ("gentoo", "dev-qt/qtbase:6"),
])
def test_qt6_widgets_cmake_package_per_distro(monkeypatch, distro_id, expected):
    _force_distro(monkeypatch, distro_id)
    assert (distro.package_for("qt6-widgets-cmake", "qt6-base")
            == expected)


@pytest.mark.parametrize("distro_id, expected", [
    ("arch", "qt6-base"),
    ("fedora", "qt6-qtbase-devel"),
    ("debian", "qt6-base-dev"),
    ("ubuntu", "qt6-base-dev"),
    ("opensuse", "qt6-dbus-devel"),
    ("alpine", "qt6-qtbase-dev"),
    ("rhel", "qt6-qtbase-devel"),
    ("gentoo", "dev-qt/qtbase:6"),
])
def test_qt6_dbus_cmake_package_per_distro(monkeypatch, distro_id, expected):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("qt6-dbus-cmake", "qt6-base") == expected


@pytest.mark.parametrize("distro_id, expected", [
    ("arch", "qt6-declarative"),
    ("fedora", "qt6-qtdeclarative-devel"),
    ("debian", "qt6-declarative-dev"),
    ("ubuntu", "qt6-declarative-dev"),
    ("opensuse", "qt6-qml-devel"),
    ("alpine", "qt6-qtdeclarative-dev"),
    ("rhel", "qt6-qtdeclarative-devel"),
    ("gentoo", "dev-qt/qtdeclarative:6"),
])
def test_qt6_qml_cmake_package_per_distro(monkeypatch, distro_id, expected):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("qt6-qml-cmake", "qt6-declarative") == expected


@pytest.mark.parametrize("distro_id, expected", [
    ("arch", "qt6-tools"),
    ("fedora", "qt6-qttools-devel"),
    ("debian", "qt6-tools-dev"),
    ("ubuntu", "qt6-tools-dev"),
    ("opensuse", "qt6-uitools-devel"),
    ("alpine", "qt6-qttools-dev"),
    ("rhel", "qt6-qttools-devel"),
    ("gentoo", "dev-qt/qttools:6"),
])
def test_qt6_uitools_cmake_package_per_distro(monkeypatch, distro_id, expected):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("qt6-uitools-cmake", "qt6-tools") == expected


@pytest.mark.parametrize("distro_id, expected", [
    ("arch", "make"),
    ("fedora", "make"),
    ("debian", "make"),
    ("ubuntu", "make"),
    ("opensuse", "make"),
    ("alpine", "make"),
    ("rhel", "make"),
    ("gentoo", "dev-build/make"),
])
def test_make_package_per_distro(monkeypatch, distro_id, expected):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("make", "make") == expected


# ── qmake6 (Qt6 dev tools) — distinct from qdbus6 row above ───────────


@pytest.mark.parametrize("distro_id, expected", [
    ("arch",     "qt6-tools"),
    ("fedora",   "qt6-qttools-devel"),
    ("rhel",     "qt6-qttools-devel"),
    ("opensuse", "qt6-core-devel"),
    ("debian",   "qt6-base-dev-tools"),
    ("ubuntu",   "qt6-base-dev-tools"),
])
def test_qmake6_package_per_distro(monkeypatch, distro_id, expected):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("qmake6", "qt6-tools") == expected


@pytest.mark.parametrize("distro_id, id_like, expected", [
    ("arch", (), (["pacman", "-Q", "plasma-workspace"],)),
    ("cachyos", ("arch",), (["pacman", "-Q", "plasma-workspace"],)),
    ("fedora", (), (["rpm", "-q", "--qf", "%{VERSION}\n", "plasma-workspace"],)),
    (
        "opensuse-tumbleweed",
        ("opensuse",),
        (
            ["rpm", "-q", "--qf", "%{VERSION}\n", "plasma6-workspace"],
            ["rpm", "-q", "--qf", "%{VERSION}\n", "plasma6-desktop"],
            ["rpm", "-q", "--qf", "%{VERSION}\n", "plasma-workspace"],
        ),
    ),
    ("ubuntu", (), (["dpkg-query", "-W", "-f=${Version}\n", "plasma-workspace"],)),
])
def test_plasma_version_probe_cmds_per_distro(monkeypatch, distro_id, id_like, expected):
    _force_distro(monkeypatch, distro_id, id_like)
    assert distro.plasma_version_probe_cmds() == expected


# ── No deps() token may fall through with the Arch fallback on a
# non-Arch distro for the binaries we *know* have a distro-specific
# name. This catches future steps adding tokens without rows. ─────────


_TOKENS_WITH_FEDORA_DIVERGENCE = {
    # token → Arch fallback that's wrong on Fedora
    "qdbus6": "qt6-tools",
    "qt6-gui-cmake": "qt6-base",
    "qt6-widgets-cmake": "qt6-base",
    "qt6-dbus-cmake": "qt6-base",
    "qt6-qml-cmake": "qt6-declarative",
    "qt6-uitools-cmake": "qt6-tools",
    "g++": "gcc",
    "pkg-config": "pkgconf",
    "plymouth-set-default-theme": "plymouth",
    # v0.17.5: every compiled step's KF6 / Plasma / KWin token has a
    # distinct Fedora name (kf6-...-devel / ...-devel / kwin-devel).
    # If a future step adds a deps() token but forgets the _PACKAGE_MAP
    # row, the Arch package leaks to dnf and the build dies the same
    # way it did in v0.17.5. This list keeps the safety net wide.
    "kf6-config-cmake": "kconfig",
    "kf6-configwidgets-cmake": "kconfigwidgets",
    "kf6-coreaddons-cmake": "kcoreaddons",
    "kf6-crash-cmake": "kcrash",
    "kf6-globalaccel-cmake": "kglobalaccel",
    "kf6-guiaddons-cmake": "kguiaddons",
    "kf6-i18n-cmake": "ki18n",
    "kf6-kcmutils-cmake": "kcmutils",
    "kf6-kio-cmake": "kio",
    "kf6-notifications-cmake": "knotifications",
    "kf6-service-cmake": "kservice",
    "kf6-widgetsaddons-cmake": "kwidgetsaddons",
    "kf6-windowsystem-cmake": "kwindowsystem",
    "kf6-itemmodels-cmake": "kitemmodels",
    "plasma-cmake": "libplasma",
    "plasma-activities-cmake": "plasma-activities",
    "plasma-activities-stats-cmake": "plasma-activities-stats",
    "ksysguard-cmake": "libksysguard",
    "libnotificationmanager-cmake": "plasma-workspace",
    "libtaskmanager-cmake": "plasma-workspace",
    "kwin-cmake": "kwin",
    "kdecoration-cmake": "kdecoration",
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


# ── KF6 frameworks — probed against fresh container images (2026-06):
#   Arch (pacman -F):          ``k<name>``           (kcoreaddons, ki18n, …)
#   Fedora (dnf repoquery):    ``kf6-k<name>-devel``
#   openSUSE (zypper search):  ``kf6-k<name>-devel`` (same as Fedora)
#   Gentoo:                    ``kde-frameworks/k<name>:6``
# Don't re-shape the per-distro names from convention — every value
# below was probed; the openSUSE prefix is ``kf6-`` (not ``kf6-k``),
# so e.g. KIO is ``kf6-kio-devel`` not ``kf6-io-devel``.

_KF6_TOKENS = [
    ("kf6-config-cmake",        "kconfig",
     "kf6-kconfig-devel",        "kde-frameworks/kconfig:6"),
    ("kf6-configwidgets-cmake", "kconfigwidgets",
     "kf6-kconfigwidgets-devel", "kde-frameworks/kconfigwidgets:6"),
    ("kf6-coreaddons-cmake",    "kcoreaddons",
     "kf6-kcoreaddons-devel",    "kde-frameworks/kcoreaddons:6"),
    ("kf6-crash-cmake",         "kcrash",
     "kf6-kcrash-devel",         "kde-frameworks/kcrash:6"),
    ("kf6-globalaccel-cmake",   "kglobalaccel",
     "kf6-kglobalaccel-devel",   "kde-frameworks/kglobalaccel:6"),
    ("kf6-guiaddons-cmake",     "kguiaddons",
     "kf6-kguiaddons-devel",     "kde-frameworks/kguiaddons:6"),
    ("kf6-i18n-cmake",          "ki18n",
     "kf6-ki18n-devel",          "kde-frameworks/ki18n:6"),
    ("kf6-kcmutils-cmake",      "kcmutils",
     "kf6-kcmutils-devel",       "kde-frameworks/kcmutils:6"),
    ("kf6-kio-cmake",           "kio",
     "kf6-kio-devel",            "kde-frameworks/kio:6"),
    ("kf6-notifications-cmake", "knotifications",
     "kf6-knotifications-devel", "kde-frameworks/knotifications:6"),
    ("kf6-service-cmake",       "kservice",
     "kf6-kservice-devel",       "kde-frameworks/kservice:6"),
    ("kf6-widgetsaddons-cmake", "kwidgetsaddons",
     "kf6-kwidgetsaddons-devel", "kde-frameworks/kwidgetsaddons:6"),
    ("kf6-windowsystem-cmake",  "kwindowsystem",
     "kf6-kwindowsystem-devel",  "kde-frameworks/kwindowsystem:6"),
    # KItemModels: required by the dock-taskmanager + globalmenu plasmoid
    # CMakeLists. Arch's `kcoreaddons` meta pulls it transitively so
    # missing it from the Dockerfile silently worked there; Fedora's
    # `kf6-kcoreaddons-devel` does NOT, which is how the regression
    # surfaced as a `FindKF6ItemModels.cmake` failure in CI.
    ("kf6-itemmodels-cmake",    "kitemmodels",
     "kf6-kitemmodels-devel",    "kde-frameworks/kitemmodels:6"),
]


@pytest.mark.parametrize("token,arch,fedora,gentoo", _KF6_TOKENS)
def test_kf6_framework_packages_per_distro(monkeypatch, token, arch, fedora, gentoo):
    # Arch / CachyOS / Manjaro / EndeavourOS / Garuda all share the
    # Arch row through current_distro() or ID_LIKE; we pick the parent
    # explicitly so the test fails loudly when the row is missing
    # rather than silently falling back to the Arch token.
    _force_distro(monkeypatch, "arch")
    assert distro.package_for(token, arch) == arch
    _force_distro(monkeypatch, "fedora")
    assert distro.package_for(token, arch) == fedora
    _force_distro(monkeypatch, "nobara", ("fedora",))
    assert distro.package_for(token, arch) == fedora
    _force_distro(monkeypatch, "opensuse")
    assert distro.package_for(token, arch) == fedora
    _force_distro(monkeypatch, "opensuse-tumbleweed", ("opensuse",))
    assert distro.package_for(token, arch) == fedora
    _force_distro(monkeypatch, "gentoo")
    assert distro.package_for(token, arch) == gentoo


# ── Plasma / KSysGuard / plasma-workspace cmake configs ──────────────


_PLASMA_TOKENS = [
    # token, arch, fedora, opensuse, gentoo
    ("plasma-cmake",
     "libplasma", "libplasma-devel", "libplasma6-devel",
     "kde-plasma/libplasma"),
    ("plasma-activities-cmake",
     "plasma-activities", "plasma-activities-devel", "plasma6-activities-devel",
     "kde-plasma/plasma-activities"),
    ("plasma-activities-stats-cmake",
     "plasma-activities-stats", "plasma-activities-stats-devel",
     "plasma6-activities-stats-devel",
     "kde-plasma/plasma-activities-stats"),
    ("ksysguard-cmake",
     "libksysguard", "libksysguard-devel", "libksysguard6-devel",
     "kde-plasma/libksysguard"),
    # LibNotificationManager and LibTaskManager both live in
    # plasma-workspace's -devel package — preserved as two logical
    # tokens so the deps() in plasmoids.py / globalmenu.py reads
    # naturally and a failure names the right cmake config.
    ("libnotificationmanager-cmake",
     "plasma-workspace", "plasma-workspace-devel", "plasma6-workspace-devel",
     "kde-plasma/plasma-workspace"),
    ("libtaskmanager-cmake",
     "plasma-workspace", "plasma-workspace-devel", "plasma6-workspace-devel",
     "kde-plasma/plasma-workspace"),
]


@pytest.mark.parametrize("token,arch,fedora,opensuse,gentoo", _PLASMA_TOKENS)
def test_plasma_packages_per_distro(
    monkeypatch, token, arch, fedora, opensuse, gentoo,
):
    _force_distro(monkeypatch, "arch")
    assert distro.package_for(token, arch) == arch
    _force_distro(monkeypatch, "fedora")
    assert distro.package_for(token, arch) == fedora
    _force_distro(monkeypatch, "nobara", ("fedora",))
    assert distro.package_for(token, arch) == fedora
    _force_distro(monkeypatch, "opensuse")
    assert distro.package_for(token, arch) == opensuse
    _force_distro(monkeypatch, "gentoo")
    assert distro.package_for(token, arch) == gentoo


# ── KWin + KDecoration (acrylic-glass effect only) ───────────────────


@pytest.mark.parametrize("distro_id, id_like, expected", [
    ("arch",                (),             "kwin"),
    ("cachyos",             ("arch",),      "kwin"),
    ("fedora",              (),             "kwin-devel"),
    ("nobara",              ("fedora",),    "kwin-devel"),
    ("opensuse",            (),             "kwin6-devel"),
    ("opensuse-tumbleweed", ("opensuse",),  "kwin6-devel"),
    ("gentoo",              (),             "kde-plasma/kwin"),
])
def test_kwin_cmake_package_per_distro(monkeypatch, distro_id, id_like, expected):
    _force_distro(monkeypatch, distro_id, id_like)
    assert distro.package_for("kwin-cmake", "kwin") == expected


@pytest.mark.parametrize("distro_id, id_like, expected", [
    ("arch",                (),             "kdecoration"),
    ("cachyos",             ("arch",),      "kdecoration"),
    ("fedora",              (),             "kdecoration-devel"),
    ("nobara",              ("fedora",),    "kdecoration-devel"),
    ("opensuse",            (),             "kdecoration6-devel"),
    ("opensuse-tumbleweed", ("opensuse",),  "kdecoration6-devel"),
    ("gentoo",              (),             "kde-plasma/kdecoration"),
])
def test_kdecoration_cmake_package_per_distro(
    monkeypatch, distro_id, id_like, expected,
):
    _force_distro(monkeypatch, distro_id, id_like)
    assert distro.package_for("kdecoration-cmake", "kdecoration") == expected


# ── libepoxy + X11 / XCB headers ─────────────────────────────────────


@pytest.mark.parametrize("distro_id, expected", [
    ("arch",     "libepoxy"),
    ("fedora",   "libepoxy-devel"),
    ("opensuse", "libepoxy-devel"),
    ("gentoo",   "media-libs/libepoxy"),
])
def test_epoxy_cmake_package_per_distro(monkeypatch, distro_id, expected):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("epoxy-cmake", "libepoxy") == expected


@pytest.mark.parametrize("distro_id, expected", [
    ("arch",     "libx11"),
    ("fedora",   "libX11-devel"),
    ("opensuse", "libX11-devel"),
    ("gentoo",   "x11-libs/libX11"),
])
def test_x11_cmake_package_per_distro(monkeypatch, distro_id, expected):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("x11-cmake", "libx11") == expected


@pytest.mark.parametrize("distro_id, expected", [
    ("arch",     "libxcb"),
    ("fedora",   "libxcb-devel"),
    ("opensuse", "libxcb-devel"),
    ("gentoo",   "x11-libs/libxcb"),
])
def test_xcb_cmake_package_per_distro(monkeypatch, distro_id, expected):
    _force_distro(monkeypatch, distro_id)
    assert distro.package_for("xcb-cmake", "libxcb") == expected


# ── Vulkan loader + headers (KWin 6.7+ transitive build dep) ─────────
# Regression: a CachyOS / Intel-Skylake user hit "KWin missing vulkan"
# because KWin 6.7's exported config pulls find_dependency(Vulkan) and
# the loader/headers weren't installed. These must resolve on every
# supported distro, and CachyOS must inherit the arch names via ID_LIKE.


@pytest.mark.parametrize("distro_id, id_like, expected", [
    ("arch",     (),         "vulkan-icd-loader"),
    ("cachyos",  ("arch",),  "vulkan-icd-loader"),   # the reported box
    ("fedora",   (),         "vulkan-loader-devel"),
    ("opensuse", (),         "vulkan-loader"),
    ("gentoo",   (),         "media-libs/vulkan-loader"),
])
def test_vulkan_loader_package_per_distro(
        monkeypatch, distro_id, id_like, expected):
    _force_distro(monkeypatch, distro_id, id_like)
    assert distro.package_for(
        "vulkan-loader-cmake", "vulkan-icd-loader") == expected


@pytest.mark.parametrize("distro_id, id_like, expected", [
    ("arch",     (),         "vulkan-headers"),
    ("cachyos",  ("arch",),  "vulkan-headers"),
    ("fedora",   (),         "vulkan-headers"),
    ("opensuse", (),         "vulkan-headers"),
    ("gentoo",   (),         "dev-util/vulkan-headers"),
])
def test_vulkan_headers_package_per_distro(
        monkeypatch, distro_id, id_like, expected):
    _force_distro(monkeypatch, distro_id, id_like)
    assert distro.package_for(
        "vulkan-headers-cmake", "vulkan-headers") == expected


# package-manager install command: supported families resolve; the
# unsupported ones raise UnsupportedDistroError.


@pytest.mark.parametrize("distro_id, id_like, expected", [
    ("arch",                (),            ["pacman", "-S", "--noconfirm", "--needed"]),
    ("cachyos",             ("arch",),     ["pacman", "-S", "--noconfirm", "--needed"]),
    ("fedora",              (),            ["dnf", "install", "-y"]),
    ("nobara",              ("fedora",),   ["dnf", "install", "-y"]),
    ("rhel",                (),            ["dnf", "install", "-y"]),
    ("opensuse-tumbleweed", ("opensuse",), ["zypper", "--non-interactive", "install", "--no-recommends"]),
    ("gentoo",              (),            ["emerge", "--quiet", "--noreplace"]),
])
def test_install_cmd_for_supported_families(monkeypatch, distro_id, id_like, expected):
    _force_distro(monkeypatch, distro_id, id_like)
    assert distro.package_manager_install_cmd() == expected


@pytest.mark.parametrize("distro_id", ["debian", "ubuntu", "alpine", "void"])
def test_install_cmd_raises_for_unsupported_distros(monkeypatch, distro_id):
    _force_distro(monkeypatch, distro_id)
    with pytest.raises(distro.UnsupportedDistroError):
        distro.package_manager_install_cmd()
