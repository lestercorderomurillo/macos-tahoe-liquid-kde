from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

from distro import is_debian_family, qt6_plugins_dir
from steps._helpers import (
    HOME, build_dir, cmake_build, fail, have, info, kw_write, offline, ok,
    reinstall, sudo_install_file, sudo_remove, warn,
)
from utils import run_user

DEST_DIR = HOME / ".config/Kvantum/mac-tahoe-liquid-kde"
DEST_DIR_DARK = HOME / ".config/Kvantum/mac-tahoe-liquid-kdeDark"

_THEMES = ("mac-tahoe-liquid-kde", "mac-tahoe-liquid-kdeDark")

ENGINE_VERSION = "1.1.8"
ENGINE_COMMIT = "058534fc15d1798c3887590166f05c598e8e946c"
ENGINE_SHA256 = "7aa9099345e48048ebdad768f583944ac042f87b216fa0b26a169c7e05425047"
ENGINE_ARCHIVE = offline("kvantum-engine", f"Kvantum-{ENGINE_VERSION}.tar.xz")
ENGINE_WORK = build_dir("kvantum-engine")
ENGINE_SOURCE = ENGINE_WORK / f"Kvantum-{ENGINE_VERSION}"
ENGINE_BUILD = ENGINE_WORK / "build"
ENGINE_MARKER = Path("/usr/share/mac-tahoe-liquid-kde/kvantum-engine.json")
ENGINE_LICENSE = Path(
    "/usr/share/licenses/mac-tahoe-liquid-kde/Kvantum.txt"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _engine_destination() -> Path:
    return qt6_plugins_dir() / "styles/libkvantum.so"


def _engine_matches_ownership_marker() -> bool:
    destination = _engine_destination()
    if not ENGINE_MARKER.is_file() or not destination.is_file():
        return False
    try:
        marker = json.loads(ENGINE_MARKER.read_text(encoding="utf-8"))
        return marker.get("plugin_sha256") == _sha256(destination)
    except (OSError, ValueError, TypeError):
        return False


def _bundled_engine_required() -> bool:
    """Whether this host needs our offline Qt 6 engine.

    Debian-family releases can lag on Qt 5-only Kvantum packages. Never
    overwrite an unmarked distro-owned Qt 6 plugin; keep rebuilding only a
    plugin whose ownership marker and digest prove that we installed it.
    """
    if not is_debian_family():
        return False
    destination = _engine_destination()
    if not destination.is_file():
        return True
    return _engine_matches_ownership_marker()


def deps():
    if _bundled_engine_required():
        return [
            "qmake6:qt6-base",
            "qt6-svg-cmake:qt6-svg",
            "cmake",
            "make",
            "g++:gcc",
            "kf6-windowsystem-cmake:kwindowsystem",
            "x11-cmake:libx11",
            "xext-cmake:libxext",
        ]
    if is_debian_family():
        # A distro-owned Qt 6 style plugin is sufficient. Theme selection has
        # a kwriteconfig6 fallback and does not require Kvantum Manager.
        return []
    return ["kvantummanager:kvantum"]


def _extract_bundled_engine() -> bool:
    if not ENGINE_ARCHIVE.is_file():
        fail(f"Kvantum Qt 6 source archive missing: {ENGINE_ARCHIVE}")
        return False
    actual = _sha256(ENGINE_ARCHIVE)
    if actual != ENGINE_SHA256:
        fail(
            "Kvantum Qt 6 source checksum mismatch "
            f"(expected {ENGINE_SHA256}, got {actual})"
        )
        return False

    staging = ENGINE_WORK / ".extracting"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(ENGINE_ARCHIVE, "r:xz") as archive:
            members = archive.getmembers()
            if not members:
                raise ValueError("archive is empty")
            for member in members:
                relative = PurePosixPath(member.name)
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or not relative.parts
                    or relative.parts[0] != ENGINE_SOURCE.name
                ):
                    raise ValueError(f"unsafe archive path: {member.name}")
                if not (member.isfile() or member.isdir()):
                    raise ValueError(f"unsafe archive member: {member.name}")
            archive.extractall(staging, members=members)
        extracted = staging / ENGINE_SOURCE.name
        if not (extracted / "Kvantum/CMakeLists.txt").is_file():
            raise ValueError("Kvantum/CMakeLists.txt missing from archive")
        shutil.rmtree(ENGINE_SOURCE, ignore_errors=True)
        extracted.replace(ENGINE_SOURCE)
        return True
    except (OSError, tarfile.TarError, ValueError) as exc:
        fail(f"Kvantum Qt 6 source archive rejected ({exc})")
        return False
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def build_artifacts() -> list[Path]:
    if not _bundled_engine_required():
        return []
    return [ENGINE_BUILD / "style/libkvantum.so"]


def build() -> None:
    if not _bundled_engine_required():
        return
    if not _extract_bundled_engine():
        return
    cmake_build(
        ENGINE_SOURCE / "Kvantum",
        ENGINE_BUILD,
        f"Kvantum Qt 6 engine v{ENGINE_VERSION}",
        targets=("kvantum",),
    )


def _install_bundled_engine() -> bool:
    if not _bundled_engine_required():
        return True
    artifact = ENGINE_BUILD / "style/libkvantum.so"
    license_source = ENGINE_SOURCE / "Kvantum/COPYING"
    if not artifact.is_file() or not license_source.is_file():
        fail("Kvantum Qt 6 build artefacts missing")
        return False

    destination = _engine_destination()
    if not sudo_install_file(
        artifact, destination, f"Kvantum Qt 6 engine v{ENGINE_VERSION} installed"
    ):
        return False
    if not sudo_install_file(
        license_source, ENGINE_LICENSE, "Kvantum GPL-3.0 license installed"
    ):
        sudo_remove(destination, "incomplete Kvantum Qt 6 engine")
        return False

    marker_source = ENGINE_WORK / "kvantum-engine.json"
    marker_source.write_text(
        json.dumps(
            {
                "version": ENGINE_VERSION,
                "commit": ENGINE_COMMIT,
                "source_sha256": ENGINE_SHA256,
                "plugin_sha256": _sha256(artifact),
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    if not sudo_install_file(
        marker_source, ENGINE_MARKER, "Kvantum bundled-source marker installed"
    ):
        sudo_remove(destination, "incomplete Kvantum Qt 6 engine")
        sudo_remove(ENGINE_LICENSE, "incomplete Kvantum license")
        return False
    return True


def _install_one(name: str) -> None:
    src = offline("kvantum/mac-tahoe-liquid-kde")
    dst = (DEST_DIR_DARK if "Dark" in name else DEST_DIR)
    dst.mkdir(parents=True, exist_ok=True)
    for ext in (".kvconfig", ".svg"):
        f = src / f"{name}{ext}"
        if f.is_file():
            shutil.copy2(f, dst / f.name)
        else:
            warn(f"Kvantum file {f.name} not found")


def install() -> None:
    src = offline("kvantum/mac-tahoe-liquid-kde")
    if not src.is_dir():
        fail(f"Kvantum theme source not found at {src}")
        return

    if not _install_bundled_engine():
        return

    existed = any(
        (d.is_dir() and any(d.glob("*.kvconfig")))
         for d in (DEST_DIR, DEST_DIR_DARK)
    )

    for name in _THEMES:
        _install_one(name)

    if any((DEST_DIR / f"{_THEMES[0]}{e}").is_file() for e in (".kvconfig", ".svg")):
        ok("mac-tahoe-liquid-kde theme (installed)")
    else:
        fail("mac-tahoe-liquid-kde theme (copy failed)")
        return

    if any((DEST_DIR_DARK / f"{_THEMES[1]}{e}").is_file() for e in (".kvconfig", ".svg")):
        if existed:
            reinstall("mac-tahoe-liquid-kdeDark theme")
        else:
            ok("mac-tahoe-liquid-kdeDark theme (installed)")
    else:
        fail("mac-tahoe-liquid-kdeDark theme (copy failed)")
        return

    if kw_write("--file", "kdeglobals", "--group", "KDE",
                "--key", "widgetStyle", "kvantum"):
        ok("Widget style installed")
    else:
        warn("Widget style not applied — kwriteconfig6 unavailable "
             "(install plasma-workspace or your distro's equivalent)")
    info("Kvantum Qt styling installed")


def _remove_bundled_engine() -> None:
    if not ENGINE_MARKER.is_file():
        return
    destination = _engine_destination()
    try:
        marker = json.loads(ENGINE_MARKER.read_text(encoding="utf-8"))
        expected = marker.get("plugin_sha256")
    except (OSError, ValueError, TypeError):
        expected = None

    if destination.is_file() and expected and _sha256(destination) == expected:
        sudo_remove(destination, "bundled Kvantum Qt 6 engine")
    elif destination.exists():
        warn(
            "Kvantum Qt 6 engine changed since installation — leaving the "
            "distro/user-owned plugin in place"
        )
    sudo_remove(ENGINE_MARKER, "Kvantum bundled-source marker")
    sudo_remove(ENGINE_LICENSE, "Kvantum bundled-source license")


def uninstall() -> None:
    any_was_installed = False
    for d in (DEST_DIR, DEST_DIR_DARK):
        if d.is_dir():
            any_was_installed = True
    if any_was_installed:
        if kw_write("--file", "kdeglobals", "--group", "KDE",
                    "--key", "widgetStyle", "Breeze"):
            ok("Widget style reset to Breeze")
        if have("kvantummanager"):
            env = os.environ.copy()
            env["QT_QPA_PLATFORM"] = "offscreen"
            run_user(
                ["kvantummanager", "--set", "Default"],
                check=False, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        for d in (DEST_DIR, DEST_DIR_DARK):
            try:
                shutil.rmtree(d)
            except OSError:
                pass
    if any(d.is_dir() for d in (DEST_DIR, DEST_DIR_DARK)):
        fail("MacTahoeLiquidKde themes (some leftovers)")
    elif any_was_installed:
        ok("MacTahoeLiquidKde themes removed")
    else:
        ok("MacTahoeLiquidKde themes (not installed)")
    _remove_bundled_engine()
    shutil.rmtree(ENGINE_WORK, ignore_errors=True)
    info("Kvantum Qt styling removed")
