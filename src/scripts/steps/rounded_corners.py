"""Online KDE Rounded Corners integration.

The upstream source is deliberately not mirrored in ``src/offline``.  Each
release is pinned here by tag, commit and archive digest; the download phase
accepts only those exact bytes before the normal compiled-component phase is
allowed to run.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tarfile
import time
from pathlib import Path, PurePosixPath

from distro import qt6_plugins_dir
from steps._helpers import (
    build_dir,
    cmake_build,
    fail,
    info,
    kw_write,
    ok,
    qdbus_call,
    sudo_install_file,
    sudo_remove,
    warn,
)
from utils import fetch, qdbus_cmd, run_user


UPSTREAM_VERSION = "0.9.0"
UPSTREAM_COMMIT = "96e5dc7ba681af088a6297053593c2dd0cf041c9"
UPSTREAM_URL = (
    "https://github.com/matinlotfali/KDE-Rounded-Corners/"
    f"archive/refs/tags/v{UPSTREAM_VERSION}.tar.gz"
)
UPSTREAM_SHA256 = "4acaf2dad31a22cbfa009bdce836b969177996527237eb8c62c8393e03622c5f"
UPSTREAM_PROJECT_URL = "https://github.com/matinlotfali/KDE-Rounded-Corners"

EFFECT_ID = "kwin4_effect_shapecorners"
CORNER_RADIUS = 28
WORK = build_dir("online/kde-rounded-corners")
ARCHIVE = WORK / f"KDE-Rounded-Corners-{UPSTREAM_VERSION}.tar.gz"
SOURCE = WORK / f"KDE-Rounded-Corners-{UPSTREAM_VERSION}"
BUILD = WORK / "build"
_DOWNLOAD_READY = False

SHADER_DIR = Path("/usr/share/kwin/shaders")
LOCALE_DIR = Path("/usr/share/locale")
LOCALES = ("de", "es", "hu", "nl", "ru", "zh")
LICENSE_FILE = Path(
    "/usr/share/licenses/mac-tahoe-liquid-kde/KDE-Rounded-Corners.txt"
)


def deps():
    return [
        "qmake6:qt6-base",
        "qt6-dbus-cmake:qt6-base",
        "qt6-coreprivate-cmake:qt6-base",
        "cmake",
        "ecm:extra-cmake-modules",
        "make",
        "g++:gcc",
        "pkg-config:pkgconf",
        "kf6-configwidgets-cmake:kconfigwidgets",
        "kf6-i18n-cmake:ki18n",
        "kf6-kcmutils-cmake:kcmutils",
        "kwin-cmake:kwin",
        "epoxy-cmake:libepoxy",
        "xcb-cmake:libxcb",
        "wayland-cmake:wayland",
        "drm-cmake:libdrm",
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_is_valid(path: Path) -> bool:
    return path.is_file() and _sha256(path) == UPSTREAM_SHA256


def _extract_verified_archive() -> bool:
    staging = WORK / ".extracting"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    expected_root = SOURCE.name
    try:
        with tarfile.open(ARCHIVE, "r:gz") as archive:
            members = archive.getmembers()
            if not members:
                raise ValueError("archive is empty")
            for member in members:
                relative = PurePosixPath(member.name)
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or not relative.parts
                    or relative.parts[0] != expected_root
                ):
                    raise ValueError(f"unsafe archive path: {member.name}")
                # Source releases need regular files and directories only.
                # Reject links and special nodes so extraction cannot escape
                # the staging tree through a crafted upstream archive.
                if not (member.isfile() or member.isdir()):
                    raise ValueError(f"unsafe archive member: {member.name}")
            archive.extractall(staging, members=members)
        extracted = staging / expected_root
        if not (extracted / "CMakeLists.txt").is_file():
            raise ValueError("CMakeLists.txt missing from archive")
        shutil.rmtree(SOURCE, ignore_errors=True)
        extracted.replace(SOURCE)
        return True
    except (OSError, tarfile.TarError, ValueError) as exc:
        fail(f"KDE Rounded Corners archive rejected ({exc})")
        return False
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def download() -> None:
    """Fetch and verify the one online component before any build starts."""
    global _DOWNLOAD_READY
    _DOWNLOAD_READY = False
    WORK.mkdir(parents=True, exist_ok=True)
    cached = _archive_is_valid(ARCHIVE)
    if not cached:
        ARCHIVE.unlink(missing_ok=True)
        partial = ARCHIVE.with_suffix(ARCHIVE.suffix + ".part")
        partial.unlink(missing_ok=True)
        if not fetch(UPSTREAM_URL, partial, referer=UPSTREAM_PROJECT_URL):
            fail(f"KDE Rounded Corners v{UPSTREAM_VERSION} download failed")
            return
        actual = _sha256(partial)
        if actual != UPSTREAM_SHA256:
            partial.unlink(missing_ok=True)
            fail(
                "KDE Rounded Corners checksum mismatch "
                f"(expected {UPSTREAM_SHA256}, got {actual})"
            )
            return
        partial.replace(ARCHIVE)

    if not _extract_verified_archive():
        return
    _DOWNLOAD_READY = True
    suffix = " (verified cache)" if cached else ""
    ok(f"KDE Rounded Corners v{UPSTREAM_VERSION} downloaded and verified{suffix}")


def download_ready() -> bool:
    """Let the orchestrator skip this optional feature after a soft failure."""
    return _DOWNLOAD_READY


def build_artifacts() -> list[Path]:
    return [
        BUILD / "bin/kwin/effects/plugins/kwin4_effect_shapecorners.so",
        BUILD / "bin/kwin/effects/configs/kwin_shapecorners_config.so",
        BUILD / "src/shaders/shapecorners.frag",
        BUILD / "src/shaders/shapecorners_core.frag",
    ]


def _plugin_dir() -> Path:
    return qt6_plugins_dir()


def build() -> None:
    if not (SOURCE / "CMakeLists.txt").is_file():
        fail("KDE Rounded Corners source missing — online phase did not complete")
        return
    cmake_build(SOURCE, BUILD, "KDE Rounded Corners")


def _effect_active() -> bool:
    qdbus = qdbus_cmd()
    if not qdbus:
        return False
    try:
        result = run_user(
            [qdbus, "org.kde.KWin", "/Effects", "org.kde.kwin.Effects.activeEffects"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return EFFECT_ID in (result.stdout or "")


def _locale_artifacts() -> list[tuple[Path, Path]]:
    out: list[tuple[Path, Path]] = []
    locale_root = BUILD / "locale"
    if not locale_root.is_dir():
        return out
    for source in sorted(locale_root.glob("*/LC_MESSAGES/kcmcorners.mo")):
        lang = source.parents[1].name
        out.append((source, LOCALE_DIR / lang / "LC_MESSAGES/kcmcorners.mo"))
    return out


def _locale_destinations() -> list[Path]:
    return [LOCALE_DIR / lang / "LC_MESSAGES/kcmcorners.mo" for lang in LOCALES]


def install() -> None:
    effect, config, *shaders = build_artifacts()
    if not all(path.is_file() for path in (effect, config, *shaders)):
        fail("KDE Rounded Corners build artefacts missing")
        return

    kw_write(
        "--file", "kwinrc", "--group", "Plugins",
        "--key", "shapecornersEnabled", "false",
    )
    qdbus_call(
        "org.kde.KWin", "/Effects",
        "org.kde.kwin.Effects.unloadEffect", EFFECT_ID,
    )
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    time.sleep(1)

    plugin_dir = _plugin_dir()
    destinations = (
        (effect, plugin_dir / "kwin/effects/plugins/kwin4_effect_shapecorners.so",
         "KDE Rounded Corners effect installed"),
        (config, plugin_dir / "kwin/effects/configs/kwin_shapecorners_config.so",
         "KDE Rounded Corners settings installed"),
        (shaders[0], SHADER_DIR / "shapecorners.frag",
         "KDE Rounded Corners shader installed"),
        (shaders[1], SHADER_DIR / "shapecorners_core.frag",
         "KDE Rounded Corners core shader installed"),
    )
    for source, destination, label in destinations:
        if not sudo_install_file(source, destination, label):
            return

    for source, destination in _locale_artifacts():
        if not sudo_install_file(source, destination, f"Rounded Corners locale: {destination.parts[-3]}"):
            warn(f"KDE Rounded Corners locale failed: {destination.parts[-3]}")

    license_source = SOURCE / "LICENSE"
    if license_source.is_file():
        sudo_install_file(
            license_source,
            LICENSE_FILE,
            "KDE Rounded Corners GPL-3.0 license installed",
        )

    radius_configured = True
    for key in ("Size", "InactiveCornerRadius"):
        if not kw_write(
            "--file", "kwinrc", "--group", "Round-Corners",
            "--key", key, str(CORNER_RADIUS),
        ):
            radius_configured = False
    if radius_configured:
        ok(f"KDE Rounded Corners radius set to {CORNER_RADIUS}")
    else:
        warn("KDE Rounded Corners radius could not be set — kwriteconfig6 failed")

    if not kw_write(
        "--file", "kwinrc", "--group", "Plugins",
        "--key", "shapecornersEnabled", "true",
    ):
        warn("KDE Rounded Corners could not be enabled — kwriteconfig6 failed")
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    qdbus_call(
        "org.kde.KWin", "/Effects",
        "org.kde.kwin.Effects.loadEffect", EFFECT_ID,
    )
    if _effect_active():
        ok("KDE Rounded Corners loaded")
    else:
        ok("KDE Rounded Corners installed (log out and back in to activate)")
    info(f"KDE Rounded Corners v{UPSTREAM_VERSION} installed from verified upstream source")


def uninstall() -> None:
    qdbus_call(
        "org.kde.KWin", "/Effects",
        "org.kde.kwin.Effects.unloadEffect", EFFECT_ID,
    )
    kw_write(
        "--file", "kwinrc", "--group", "Plugins",
        "--key", "shapecornersEnabled", "false",
    )
    # install() writes [Round-Corners] Size/InactiveCornerRadius directly
    # (there's no per-plugin config namespace to scope them under) — strip
    # both back out so a stock KDE Rounded Corners KCM installed later
    # doesn't inherit our radius as its default.
    for key in ("Size", "InactiveCornerRadius"):
        kw_write(
            "--file", "kwinrc", "--group", "Round-Corners",
            "--key", key, "--delete",
        )
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")

    plugin_dir = _plugin_dir()
    for path in (
        plugin_dir / "kwin/effects/plugins/kwin4_effect_shapecorners.so",
        plugin_dir / "kwin/effects/configs/kwin_shapecorners_config.so",
        SHADER_DIR / "shapecorners.frag",
        SHADER_DIR / "shapecorners_core.frag",
        LICENSE_FILE,
    ):
        sudo_remove(path, path.name)
    for destination in _locale_destinations():
        sudo_remove(destination, f"Rounded Corners locale: {destination.parts[-3]}")
    shutil.rmtree(WORK, ignore_errors=True)
    info("KDE Rounded Corners removed")
