"""Online KDE Rounded Corners step: supply-chain and lifecycle guards."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import tarfile
from pathlib import Path

import pytest

from steps import rounded_corners as rounded


def _pin_work(monkeypatch, tmp_path: Path) -> Path:
    work = tmp_path / "online/kde-rounded-corners"
    source = work / f"KDE-Rounded-Corners-{rounded.UPSTREAM_VERSION}"
    monkeypatch.setattr(rounded, "WORK", work)
    monkeypatch.setattr(
        rounded, "ARCHIVE",
        work / f"KDE-Rounded-Corners-{rounded.UPSTREAM_VERSION}.tar.gz",
    )
    monkeypatch.setattr(rounded, "SOURCE", source)
    monkeypatch.setattr(rounded, "BUILD", work / "build")
    monkeypatch.setattr(rounded, "_DOWNLOAD_READY", False)
    return work


def _source_archive(path: Path, root: str, *, traversal: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as archive:
        cmake = b"project(rounded)\n"
        info = tarfile.TarInfo(f"{root}/CMakeLists.txt")
        info.size = len(cmake)
        archive.addfile(info, io.BytesIO(cmake))
        if traversal:
            payload = b"escape\n"
            bad = tarfile.TarInfo(f"{root}/../../escape")
            bad.size = len(payload)
            archive.addfile(bad, io.BytesIO(payload))


def test_upstream_release_pin_is_complete():
    assert rounded.UPSTREAM_VERSION == "0.9.0"
    assert len(rounded.UPSTREAM_COMMIT) == 40
    assert len(rounded.UPSTREAM_SHA256) == 64
    assert f"tags/v{rounded.UPSTREAM_VERSION}.tar.gz" in rounded.UPSTREAM_URL


def test_download_fetches_verifies_and_extracts(monkeypatch, tmp_path):
    work = _pin_work(monkeypatch, tmp_path)
    fixture = tmp_path / "fixture.tar.gz"
    _source_archive(fixture, rounded.SOURCE.name)
    monkeypatch.setattr(
        rounded, "UPSTREAM_SHA256",
        hashlib.sha256(fixture.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        rounded, "fetch",
        lambda url, dest, referer=None: shutil.copy2(fixture, dest) is not None,
    )
    messages: list[str] = []
    monkeypatch.setattr(rounded, "ok", messages.append)

    rounded.download()

    assert rounded.download_ready() is True
    assert (rounded.SOURCE / "CMakeLists.txt").is_file()
    assert rounded.ARCHIVE.is_file()
    assert any("downloaded and verified" in message for message in messages)
    assert work.is_dir()


def test_download_reuses_verified_cache(monkeypatch, tmp_path):
    _pin_work(monkeypatch, tmp_path)
    _source_archive(rounded.ARCHIVE, rounded.SOURCE.name)
    monkeypatch.setattr(
        rounded, "UPSTREAM_SHA256",
        hashlib.sha256(rounded.ARCHIVE.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        rounded, "fetch",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")),
    )
    messages: list[str] = []
    monkeypatch.setattr(rounded, "ok", messages.append)

    rounded.download()

    assert rounded.download_ready() is True
    assert any("verified cache" in message for message in messages)


def test_download_rejects_checksum_mismatch(monkeypatch, tmp_path):
    _pin_work(monkeypatch, tmp_path)
    payload = tmp_path / "bad.tar.gz"
    payload.write_bytes(b"not the pinned archive")
    monkeypatch.setattr(
        rounded, "fetch",
        lambda url, dest, referer=None: shutil.copy2(payload, dest) is not None,
    )
    failures: list[str] = []
    monkeypatch.setattr(rounded, "fail", failures.append)

    rounded.download()

    assert rounded.download_ready() is False
    assert not rounded.ARCHIVE.exists()
    assert any("checksum mismatch" in message for message in failures)


def test_download_rejects_parent_traversal(monkeypatch, tmp_path):
    _pin_work(monkeypatch, tmp_path)
    _source_archive(rounded.ARCHIVE, rounded.SOURCE.name, traversal=True)
    monkeypatch.setattr(
        rounded, "UPSTREAM_SHA256",
        hashlib.sha256(rounded.ARCHIVE.read_bytes()).hexdigest(),
    )
    failures: list[str] = []
    monkeypatch.setattr(rounded, "fail", failures.append)

    rounded.download()

    assert rounded.download_ready() is False
    assert not (tmp_path / "escape").exists()
    assert any("unsafe archive path" in message for message in failures)


def _seed_artifacts(monkeypatch, tmp_path: Path) -> None:
    _pin_work(monkeypatch, tmp_path)
    paths = rounded.build_artifacts()
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"artifact")
    rounded.SOURCE.mkdir(parents=True, exist_ok=True)
    (rounded.SOURCE / "LICENSE").write_text("GPL-3.0\n")


def test_install_places_artifacts_and_enables_effect(monkeypatch, tmp_path):
    _seed_artifacts(monkeypatch, tmp_path)
    plugins = tmp_path / "qt/plugins"
    shaders = tmp_path / "share/kwin/shaders"
    license_file = tmp_path / "share/licenses/rounded.txt"
    monkeypatch.setattr(rounded, "_plugin_dir", lambda: plugins)
    monkeypatch.setattr(rounded, "SHADER_DIR", shaders)
    monkeypatch.setattr(rounded, "LOCALE_DIR", tmp_path / "share/locale")
    monkeypatch.setattr(rounded, "LICENSE_FILE", license_file)
    installed: list[tuple[Path, Path]] = []
    writes: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        rounded, "sudo_install_file",
        lambda src, dst, label: installed.append((src, dst)) or True,
    )
    monkeypatch.setattr(
        rounded, "kw_write", lambda *args: writes.append(args) or True,
    )
    dbus_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        rounded, "qdbus_call", lambda *args: dbus_calls.append(args) or True,
    )
    monkeypatch.setattr(rounded, "_effect_active", lambda: True)
    monkeypatch.setattr(rounded.time, "sleep", lambda _: None)
    monkeypatch.setattr(rounded, "ok", lambda _: None)
    monkeypatch.setattr(rounded, "info", lambda _: None)

    rounded.install()

    destinations = {dst for _, dst in installed}
    assert plugins / "kwin/effects/plugins/kwin4_effect_shapecorners.so" in destinations
    assert plugins / "kwin/effects/configs/kwin_shapecorners_config.so" in destinations
    assert shaders / "shapecorners.frag" in destinations
    assert shaders / "shapecorners_core.frag" in destinations
    assert license_file in destinations
    plugin_writes = [write for write in writes if "shapecornersEnabled" in write]
    assert plugin_writes
    assert "false" in plugin_writes[0]
    assert "true" in plugin_writes[-1]
    radius_writes = [write for write in writes if "Round-Corners" in write]
    assert rounded.CORNER_RADIUS == 28
    assert any("Size" in write and "28" in write for write in radius_writes)
    assert any(
        "InactiveCornerRadius" in write and "28" in write
        for write in radius_writes
    )
    assert any(
        any(argument.endswith(".loadEffect") for argument in call)
        for call in dbus_calls
    )


def _pin_round_corners_state(monkeypatch, tmp_path: Path) -> Path:
    state_dir = tmp_path / "state"
    monkeypatch.setattr(rounded, "STATE_DIR", state_dir)
    monkeypatch.setattr(
        rounded, "PREV_ROUND_CORNERS_FILE",
        state_dir / "rounded-corners-previous.json",
    )
    return state_dir


def test_uninstall_disables_effect_and_removes_owned_files(monkeypatch, tmp_path):
    _seed_artifacts(monkeypatch, tmp_path)
    _pin_round_corners_state(monkeypatch, tmp_path)
    plugins = tmp_path / "qt/plugins"
    shaders = tmp_path / "share/kwin/shaders"
    license_file = tmp_path / "share/licenses/rounded.txt"
    monkeypatch.setattr(rounded, "_plugin_dir", lambda: plugins)
    monkeypatch.setattr(rounded, "SHADER_DIR", shaders)
    monkeypatch.setattr(rounded, "LOCALE_DIR", tmp_path / "share/locale")
    monkeypatch.setattr(rounded, "LICENSE_FILE", license_file)
    removed: list[Path] = []
    writes: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        rounded, "sudo_remove", lambda path, label=None: removed.append(path) or True,
    )
    monkeypatch.setattr(
        rounded, "kw_write", lambda *args: writes.append(args) or True,
    )
    monkeypatch.setattr(rounded, "qdbus_call", lambda *args: True)
    monkeypatch.setattr(rounded, "info", lambda _: None)

    rounded.uninstall()

    assert plugins / "kwin/effects/plugins/kwin4_effect_shapecorners.so" in removed
    assert plugins / "kwin/effects/configs/kwin_shapecorners_config.so" in removed
    assert shaders / "shapecorners.frag" in removed
    assert shaders / "shapecorners_core.frag" in removed
    assert license_file in removed
    assert any("shapecornersEnabled" in write and "false" in write for write in writes)
    assert not rounded.WORK.exists()
    # No pre-install snapshot existed (fresh install/uninstall in this
    # test) — Round-Corners keys should be deleted, not restored to a
    # bogus value.
    radius_writes = [w for w in writes if "Round-Corners" in w]
    assert all("--delete" in w for w in radius_writes)


def test_install_snapshots_preexisting_round_corners_keys_once(monkeypatch, tmp_path):
    """A user's own stock KDE Rounded Corners KCM setup (Size=12, no
    InactiveCornerRadius) must be captured before install() overwrites
    it, and NOT overwritten again by a later reinstall — mirrors the
    Plymouth UseSimpledrm snapshot-once contract."""
    _seed_artifacts(monkeypatch, tmp_path)
    state_dir = _pin_round_corners_state(monkeypatch, tmp_path)
    monkeypatch.setattr(rounded, "_plugin_dir", lambda: tmp_path / "qt/plugins")
    monkeypatch.setattr(rounded, "SHADER_DIR", tmp_path / "share/kwin/shaders")
    monkeypatch.setattr(rounded, "LOCALE_DIR", tmp_path / "share/locale")
    monkeypatch.setattr(rounded, "LICENSE_FILE", tmp_path / "share/licenses/rounded.txt")
    monkeypatch.setattr(rounded, "sudo_install_file", lambda *a, **k: True)
    monkeypatch.setattr(rounded, "kw_write", lambda *args: True)
    monkeypatch.setattr(rounded, "qdbus_call", lambda *args: True)
    monkeypatch.setattr(rounded, "_effect_active", lambda: True)
    monkeypatch.setattr(rounded.time, "sleep", lambda _: None)
    monkeypatch.setattr(rounded, "ok", lambda _: None)
    monkeypatch.setattr(rounded, "info", lambda _: None)

    existing = {"Size": "12", "InactiveCornerRadius": ""}
    monkeypatch.setattr(rounded, "kw_read",
                        lambda _file, _group, key: existing[key])

    rounded.install()

    snapshot = json.loads(rounded.PREV_ROUND_CORNERS_FILE.read_text())
    assert snapshot == {"Size": "12", "InactiveCornerRadius": None}

    # Reinstalling must not clobber the already-captured pre-install
    # value with our own radius.
    monkeypatch.setattr(rounded, "kw_read",
                        lambda _file, _group, key: str(rounded.CORNER_RADIUS))
    rounded.install()
    snapshot_after_reinstall = json.loads(
        rounded.PREV_ROUND_CORNERS_FILE.read_text()
    )
    assert snapshot_after_reinstall == {"Size": "12", "InactiveCornerRadius": None}


def test_uninstall_restores_preexisting_round_corners_value(monkeypatch, tmp_path):
    """uninstall() must restore the user's own Size=12 rather than
    deleting it — those keys can belong to an existing stock KDE
    Rounded Corners setup that predates this installer."""
    state_dir = _pin_round_corners_state(monkeypatch, tmp_path)
    state_dir.mkdir(parents=True)
    rounded.PREV_ROUND_CORNERS_FILE.write_text(
        json.dumps({"Size": "12", "InactiveCornerRadius": None})
    )
    monkeypatch.setattr(rounded, "_plugin_dir", lambda: tmp_path / "qt/plugins")
    monkeypatch.setattr(rounded, "SHADER_DIR", tmp_path / "share/kwin/shaders")
    monkeypatch.setattr(rounded, "LOCALE_DIR", tmp_path / "share/locale")
    monkeypatch.setattr(rounded, "LICENSE_FILE", tmp_path / "share/licenses/rounded.txt")
    monkeypatch.setattr(rounded, "sudo_remove", lambda *a, **k: True)
    monkeypatch.setattr(rounded, "qdbus_call", lambda *args: True)
    monkeypatch.setattr(rounded, "info", lambda _: None)
    writes: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        rounded, "kw_write", lambda *args: writes.append(args) or True,
    )

    rounded.uninstall()

    radius_writes = [w for w in writes if "Round-Corners" in w]
    assert any("Size" in w and "12" in w and "--delete" not in w
              for w in radius_writes)
    assert any("InactiveCornerRadius" in w and "--delete" in w
              for w in radius_writes)
    assert not rounded.PREV_ROUND_CORNERS_FILE.exists()


def test_build_requires_completed_online_phase(monkeypatch, tmp_path):
    _pin_work(monkeypatch, tmp_path)
    failures: list[str] = []
    monkeypatch.setattr(rounded, "fail", failures.append)
    monkeypatch.setattr(
        rounded, "cmake_build",
        lambda *a: (_ for _ in ()).throw(AssertionError("build attempted")),
    )

    rounded.build()

    assert any("online phase did not complete" in message for message in failures)


def test_dependencies_cover_upstream_kwin_qt_and_graphics_sdk():
    deps = set(rounded.deps())
    assert {
        "qt6-coreprivate-cmake:qt6-base",
        "kf6-configwidgets-cmake:kconfigwidgets",
        "kf6-i18n-cmake:ki18n",
        "kf6-kcmutils-cmake:kcmutils",
        "kwin-cmake:kwin",
        "epoxy-cmake:libepoxy",
        "xcb-cmake:libxcb",
        "wayland-cmake:wayland",
        "drm-cmake:libdrm",
    } <= deps
