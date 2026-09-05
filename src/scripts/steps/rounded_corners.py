"""Online KDE Rounded Corners integration.

The upstream source is deliberately not mirrored in ``src/offline``.  Each
release is pinned here by tag, commit and archive digest; the download phase
accepts only those exact bytes before the normal compiled-component phase is
allowed to run.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
import uuid
from pathlib import Path, PurePosixPath

from distro import qt6_plugins_dir
from steps._helpers import (
    HOME,
    build_dir,
    cmake_build,
    fail,
    have,
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

STATE_DIR = HOME / ".local/state/mac-tahoe-liquid-kde"
PREV_ROUND_CORNERS_FILE = STATE_DIR / "rounded-corners-previous.json"
_ROUND_CORNERS_KEYS = ("Size", "InactiveCornerRadius")
_ROUND_CORNERS_STATE_VERSION = 1


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


def _read_round_corners_key(key: str) -> tuple[bool, str | None] | None:
    """Return ``(present, value)`` without collapsing an empty value into
    an absent key. ``None`` means the read itself failed.

    ``kw_read`` deliberately exposes a simple string API and therefore uses
    ``""`` for both an absent key and a failed read. Ownership snapshots need
    a stronger contract, so use kreadconfig's per-call default sentinel here.
    """
    if not have("kreadconfig6"):
        warn("could not snapshot Rounded Corners settings — "
             "kreadconfig6 is unavailable")
        return None

    sentinel = f"__mttkde_absent_{uuid.uuid4().hex}__"
    try:
        result = run_user(
            [
                "kreadconfig6", "--file", "kwinrc",
                "--group", "Round-Corners", "--key", key,
                "--default", sentinel,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        warn(f"could not read Rounded Corners setting {key} ({exc})")
        return None
    if result.returncode != 0:
        warn(f"could not read Rounded Corners setting {key} "
             f"(kreadconfig6 exited {result.returncode})")
        return None

    value = result.stdout or ""
    # kreadconfig prints one trailing line ending. Preserve every other byte,
    # including an intentionally-empty value, for an exact semantic restore.
    if value.endswith("\n"):
        value = value[:-1]
        if value.endswith("\r"):
            value = value[:-1]
    if value == sentinel:
        return False, None
    return True, value


def _validate_round_corners_snapshot(payload: object) -> dict | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("version") != _ROUND_CORNERS_STATE_VERSION:
        return None
    keys = payload.get("keys")
    if not isinstance(keys, dict):
        return None

    validated: dict[str, dict[str, object]] = {}
    for key in _ROUND_CORNERS_KEYS:
        entry = keys.get(key)
        if not isinstance(entry, dict) or not isinstance(entry.get("present"), bool):
            return None
        present = entry["present"]
        value = entry.get("value")
        if present:
            if not isinstance(value, str):
                return None
        elif value is not None:
            return None
        validated[key] = {"present": present, "value": value}
    return validated


def _load_round_corners_snapshot() -> dict | None:
    try:
        payload = json.loads(
            PREV_ROUND_CORNERS_FILE.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        warn(f"could not read previous Rounded Corners settings ({exc})")
        return None
    snapshot = _validate_round_corners_snapshot(payload)
    if snapshot is None:
        warn("previous Rounded Corners settings have an invalid shape")
    return snapshot


def _write_round_corners_snapshot(snapshot: dict) -> bool:
    payload = {
        "version": _ROUND_CORNERS_STATE_VERSION,
        "keys": snapshot,
    }
    tmp = PREV_ROUND_CORNERS_FILE.with_name(
        f".{PREV_ROUND_CORNERS_FILE.name}.{os.getpid()}.tmp"
    )
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        os.replace(tmp, PREV_ROUND_CORNERS_FILE)
        return True
    except OSError as exc:
        warn(f"could not snapshot previous Rounded Corners settings ({exc})")
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


def _capture_round_corners_snapshot() -> dict | None:
    snapshot: dict[str, dict[str, object]] = {}
    for key in _ROUND_CORNERS_KEYS:
        current = _read_round_corners_key(key)
        if current is None:
            return None
        present, value = current
        snapshot[key] = {"present": present, "value": value}
    return snapshot


def _snapshot_round_corners_keys() -> bool:
    """Record whatever [Round-Corners] Size/InactiveCornerRadius were
    before install() overwrites them, so uninstall() can restore that
    exact state instead of unconditionally deleting the keys. Those
    keys may predate this installer — a user could have an existing
    stock KDE Rounded Corners KCM setup with its own radius — so
    blindly stripping them on uninstall would destroy settings we
    don't own. Snapshot once: like Plymouth's UseSimpledrm snapshot,
    a second install() must not overwrite an already-captured
    pre-install value with our own radius.
    """
    if PREV_ROUND_CORNERS_FILE.exists():
        # Snapshot once, but never trust a corrupt/unreadable marker as proof
        # that it is safe to overwrite the live user settings.
        return _load_round_corners_snapshot() is not None
    snapshot = _capture_round_corners_snapshot()
    return snapshot is not None and _write_round_corners_snapshot(snapshot)


def _restore_round_corners_keys(*, legacy_install: bool) -> bool:
    """Restore the captured [Round-Corners] keys (or remove them, if
    they were absent before install()) instead of always deleting."""
    if PREV_ROUND_CORNERS_FILE.exists():
        snapshot = _load_round_corners_snapshot()
        if snapshot is None:
            return False
    elif legacy_install:
        # A project-specific license proves only that an older installer ran;
        # it cannot prove whether a live value (even our preset 28) predated
        # that install. Migrate conservatively by preserving the exact current
        # presence/value. Only a real pre-install snapshot may authorize a
        # later deletion.
        snapshot = _capture_round_corners_snapshot()
        if snapshot is None or not _write_round_corners_snapshot(snapshot):
            return False
    else:
        # No snapshot and no project ownership marker: these settings may
        # belong entirely to an independent Rounded Corners installation.
        return True

    restored = True
    for key in _ROUND_CORNERS_KEYS:
        entry = snapshot[key]
        if entry["present"]:
            args = (
                "--file", "kwinrc", "--group", "Round-Corners",
                "--key", key, "--", entry["value"],
            )
        else:
            args = (
                "--file", "kwinrc", "--group", "Round-Corners",
                "--key", key, "--delete",
            )
        if not kw_write(*args):
            restored = False
    if not restored:
        warn("previous Rounded Corners settings could not be restored — "
             "recovery state retained")
        return False
    return True


def install() -> None:
    effect, config, *shaders = build_artifacts()
    if not all(path.is_file() for path in (effect, config, *shaders)):
        fail("KDE Rounded Corners build artefacts missing")
        return

    if not _snapshot_round_corners_keys():
        fail("KDE Rounded Corners not installed — previous radius settings "
             "could not be preserved")
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
    for key in _ROUND_CORNERS_KEYS:
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
    # Restore first. If any read/write fails, leave both recovery state and
    # installed ownership markers in place so a later uninstall can retry.
    if not _restore_round_corners_keys(
        legacy_install=LICENSE_FILE.is_file(),
    ):
        fail("KDE Rounded Corners removal stopped — previous radius settings "
             "could not be restored")
        return

    qdbus_call(
        "org.kde.KWin", "/Effects",
        "org.kde.kwin.Effects.unloadEffect", EFFECT_ID,
    )
    kw_write(
        "--file", "kwinrc", "--group", "Plugins",
        "--key", "shapecornersEnabled", "false",
    )
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")

    plugin_dir = _plugin_dir()
    cleanup_ok = True
    for path in (
        plugin_dir / "kwin/effects/plugins/kwin4_effect_shapecorners.so",
        plugin_dir / "kwin/effects/configs/kwin_shapecorners_config.so",
        SHADER_DIR / "shapecorners.frag",
        SHADER_DIR / "shapecorners_core.frag",
        LICENSE_FILE,
    ):
        existed = path.exists() or path.is_symlink()
        if not sudo_remove(path, path.name) and existed:
            cleanup_ok = False
    for destination in _locale_destinations():
        existed = destination.exists() or destination.is_symlink()
        if not sudo_remove(
            destination,
            f"Rounded Corners locale: {destination.parts[-3]}",
        ) and existed:
            cleanup_ok = False
    if not cleanup_ok:
        fail("KDE Rounded Corners removal incomplete — recovery state retained")
        return

    # Clear the ownership snapshot last. If the process is interrupted during
    # artifact/license cleanup, a retry must use this exact snapshot rather
    # than mistake the still-present legacy license for proof that an original
    # user value equal to our old preset (28) belongs to the project.
    if PREV_ROUND_CORNERS_FILE.exists():
        try:
            PREV_ROUND_CORNERS_FILE.unlink()
        except OSError as exc:
            fail(f"could not clear Rounded Corners recovery state ({exc})")
            return
    shutil.rmtree(WORK, ignore_errors=True)
    info("KDE Rounded Corners removed")
