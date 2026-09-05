"""Online KDE Rounded Corners step: supply-chain and lifecycle guards."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from types import SimpleNamespace

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


def _pin_round_corners_state(monkeypatch, tmp_path: Path) -> Path:
    state_dir = tmp_path / "state"
    monkeypatch.setattr(rounded, "STATE_DIR", state_dir)
    monkeypatch.setattr(
        rounded, "PREV_ROUND_CORNERS_FILE",
        state_dir / "rounded-corners-previous.json",
    )
    return state_dir


def _snapshot_payload(
    size: tuple[bool, str | None] = (True, "12"),
    inactive: tuple[bool, str | None] = (False, None),
) -> dict:
    return {
        "version": rounded._ROUND_CORNERS_STATE_VERSION,
        "keys": {
            "Size": {"present": size[0], "value": size[1]},
            "InactiveCornerRadius": {
                "present": inactive[0], "value": inactive[1],
            },
        },
    }


def test_install_places_artifacts_and_enables_effect(monkeypatch, tmp_path):
    _seed_artifacts(monkeypatch, tmp_path)
    _pin_round_corners_state(monkeypatch, tmp_path)
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
    monkeypatch.setattr(
        rounded, "_read_round_corners_key", lambda _key: (False, None),
    )

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
    # No pre-install snapshot or project-specific ownership marker exists.
    # The keys may belong to an independent install, so leave them untouched.
    radius_writes = [w for w in writes if "Round-Corners" in w]
    assert radius_writes == []


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

    existing = {
        "Size": (True, "12"),
        "InactiveCornerRadius": (True, ""),
    }
    monkeypatch.setattr(
        rounded, "_read_round_corners_key", lambda key: existing[key],
    )

    rounded.install()

    snapshot = json.loads(rounded.PREV_ROUND_CORNERS_FILE.read_text())
    assert snapshot == _snapshot_payload(
        size=(True, "12"), inactive=(True, ""),
    )

    # Reinstalling must not clobber the already-captured pre-install
    # value with our own radius.
    monkeypatch.setattr(
        rounded,
        "_read_round_corners_key",
        lambda _key: (_ for _ in ()).throw(
            AssertionError("reinstall replaced the one-time snapshot")
        ),
    )
    rounded.install()
    snapshot_after_reinstall = json.loads(
        rounded.PREV_ROUND_CORNERS_FILE.read_text()
    )
    assert snapshot_after_reinstall == snapshot


def test_uninstall_restores_preexisting_round_corners_value(monkeypatch, tmp_path):
    """uninstall() must restore the user's own Size=12 rather than
    deleting it — those keys can belong to an existing stock KDE
    Rounded Corners setup that predates this installer."""
    state_dir = _pin_round_corners_state(monkeypatch, tmp_path)
    state_dir.mkdir(parents=True)
    rounded.PREV_ROUND_CORNERS_FILE.write_text(
        json.dumps(_snapshot_payload(
            size=(True, "12"), inactive=(True, ""),
        ))
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
    assert any("InactiveCornerRadius" in w and w[-1] == ""
               and "--delete" not in w
              for w in radius_writes)
    assert not rounded.PREV_ROUND_CORNERS_FILE.exists()


def test_restore_treats_option_like_snapshot_as_literal_value(
        monkeypatch, tmp_path):
    state_dir = _pin_round_corners_state(monkeypatch, tmp_path)
    state_dir.mkdir(parents=True)
    rounded.PREV_ROUND_CORNERS_FILE.write_text(
        json.dumps(_snapshot_payload(
            size=(True, "--delete"), inactive=(False, None),
        ))
    )
    writes: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        rounded, "kw_write", lambda *args: writes.append(args) or True,
    )

    assert rounded._restore_round_corners_keys(legacy_install=False) is True
    size_write = next(write for write in writes if "Size" in write)
    assert size_write[-2:] == ("--", "--delete")


def test_key_reader_distinguishes_absent_from_present_empty(monkeypatch):
    monkeypatch.setattr(rounded, "have", lambda command: command == "kreadconfig6")
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        key = command[command.index("--key") + 1]
        sentinel = command[command.index("--default") + 1]
        stdout = sentinel + "\n" if key == "Size" else "\n"
        return SimpleNamespace(returncode=0, stdout=stdout)

    monkeypatch.setattr(rounded, "run_user", fake_run)

    assert rounded._read_round_corners_key("Size") == (False, None)
    assert rounded._read_round_corners_key("InactiveCornerRadius") == (True, "")
    assert all(call[-1].startswith("__mttkde_absent_") for call in calls)


def test_key_reader_reports_subprocess_failure(monkeypatch):
    monkeypatch.setattr(rounded, "have", lambda _command: True)
    warnings: list[str] = []
    monkeypatch.setattr(rounded, "warn", warnings.append)
    monkeypatch.setattr(
        rounded,
        "run_user",
        lambda command, **kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(command, kwargs["timeout"])
        ),
    )

    assert rounded._read_round_corners_key("Size") is None
    assert any("could not read" in warning for warning in warnings)


def _assert_install_stops_before_mutation(monkeypatch, tmp_path: Path) -> None:
    installed: list[tuple] = []
    writes: list[tuple] = []
    dbus_calls: list[tuple] = []
    failures: list[str] = []
    monkeypatch.setattr(
        rounded, "sudo_install_file",
        lambda *args: installed.append(args) or True,
    )
    monkeypatch.setattr(
        rounded, "kw_write", lambda *args: writes.append(args) or True,
    )
    monkeypatch.setattr(
        rounded, "qdbus_call", lambda *args: dbus_calls.append(args) or True,
    )
    monkeypatch.setattr(rounded, "fail", failures.append)

    rounded.install()

    assert installed == []
    assert writes == []
    assert dbus_calls == []
    assert any("could not be preserved" in failure for failure in failures)


def test_install_fails_closed_when_snapshot_read_fails(monkeypatch, tmp_path):
    _seed_artifacts(monkeypatch, tmp_path)
    _pin_round_corners_state(monkeypatch, tmp_path)
    monkeypatch.setattr(rounded, "LICENSE_FILE", tmp_path / "installed/license")
    monkeypatch.setattr(rounded, "_read_round_corners_key", lambda _key: None)

    _assert_install_stops_before_mutation(monkeypatch, tmp_path)
    assert not rounded.PREV_ROUND_CORNERS_FILE.exists()


@pytest.mark.parametrize("failure_stage", ["write", "replace"])
def test_install_fails_closed_when_snapshot_cannot_be_saved(
    monkeypatch, tmp_path, failure_stage,
):
    _seed_artifacts(monkeypatch, tmp_path)
    state_dir = _pin_round_corners_state(monkeypatch, tmp_path)
    monkeypatch.setattr(rounded, "LICENSE_FILE", tmp_path / "installed/license")
    monkeypatch.setattr(
        rounded, "_read_round_corners_key", lambda _key: (False, None),
    )

    if failure_stage == "write":
        original_write = Path.write_text

        def fail_snapshot_write(path, *args, **kwargs):
            if path.name.startswith(".rounded-corners-previous.json"):
                raise OSError("simulated write failure")
            return original_write(path, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fail_snapshot_write)
    else:
        monkeypatch.setattr(
            rounded.os,
            "replace",
            lambda _source, _destination: (_ for _ in ()).throw(
                OSError("simulated replace failure")
            ),
        )

    _assert_install_stops_before_mutation(monkeypatch, tmp_path)
    assert not rounded.PREV_ROUND_CORNERS_FILE.exists()
    assert list(state_dir.iterdir()) == []


def test_uninstall_retains_recovery_state_when_restore_write_fails(
    monkeypatch, tmp_path,
):
    state_dir = _pin_round_corners_state(monkeypatch, tmp_path)
    state_dir.mkdir(parents=True)
    original = json.dumps(_snapshot_payload()) + "\n"
    rounded.PREV_ROUND_CORNERS_FILE.write_text(original)
    monkeypatch.setattr(rounded, "LICENSE_FILE", tmp_path / "installed/license")
    writes: list[tuple[str, ...]] = []
    removed: list[Path] = []
    dbus_calls: list[tuple[str, ...]] = []
    failures: list[str] = []

    def fail_first_restore(*args):
        writes.append(args)
        return "Size" not in args

    monkeypatch.setattr(rounded, "kw_write", fail_first_restore)
    monkeypatch.setattr(
        rounded, "sudo_remove", lambda path, label=None: removed.append(path) or True,
    )
    monkeypatch.setattr(
        rounded, "qdbus_call", lambda *args: dbus_calls.append(args) or True,
    )
    monkeypatch.setattr(rounded, "fail", failures.append)

    rounded.uninstall()

    assert len(writes) == 2
    assert rounded.PREV_ROUND_CORNERS_FILE.read_text() == original
    assert removed == []
    assert dbus_calls == []
    assert any("removal stopped" in failure for failure in failures)


def test_uninstall_retains_unreadable_recovery_state_without_mutating_config(
    monkeypatch, tmp_path,
):
    state_dir = _pin_round_corners_state(monkeypatch, tmp_path)
    state_dir.mkdir(parents=True)
    rounded.PREV_ROUND_CORNERS_FILE.write_text("{not-json}\n")
    writes: list[tuple[str, ...]] = []
    removed: list[Path] = []
    monkeypatch.setattr(
        rounded, "kw_write", lambda *args: writes.append(args) or True,
    )
    monkeypatch.setattr(
        rounded, "sudo_remove", lambda path, label=None: removed.append(path) or True,
    )
    monkeypatch.setattr(rounded, "fail", lambda _message: None)

    rounded.uninstall()

    assert rounded.PREV_ROUND_CORNERS_FILE.read_text() == "{not-json}\n"
    assert writes == []
    assert removed == []


def test_uninstall_migrates_pre_snapshot_project_install(monkeypatch, tmp_path):
    _pin_work(monkeypatch, tmp_path)
    state_dir = _pin_round_corners_state(monkeypatch, tmp_path)
    license_file = tmp_path / "share/licenses/project/rounded.txt"
    license_file.parent.mkdir(parents=True)
    license_file.write_text("project ownership marker\n")
    monkeypatch.setattr(rounded, "LICENSE_FILE", license_file)
    current = {
        "Size": (True, str(rounded.CORNER_RADIUS)),
        # A post-install user customization must survive migration.
        "InactiveCornerRadius": (True, "17"),
    }
    monkeypatch.setattr(
        rounded, "_read_round_corners_key", lambda key: current[key],
    )
    writes: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        rounded, "kw_write", lambda *args: writes.append(args) or True,
    )
    monkeypatch.setattr(rounded, "sudo_remove", lambda *args: True)
    monkeypatch.setattr(rounded, "qdbus_call", lambda *args: True)
    monkeypatch.setattr(rounded, "info", lambda _message: None)

    rounded.uninstall()

    radius_writes = [write for write in writes if "Round-Corners" in write]
    # The legacy license proves that our installer ran, but not that Size=28
    # was absent beforehand. Preserve it rather than guessing ownership.
    assert any(
        "Size" in write and write[-1] == "28" and "--delete" not in write
        for write in radius_writes
    )
    assert any(
        "InactiveCornerRadius" in write and write[-1] == "17"
        for write in radius_writes
    )
    assert not rounded.PREV_ROUND_CORNERS_FILE.exists()
    assert state_dir.is_dir()


def test_uninstall_retry_keeps_exact_snapshot_after_interrupted_cleanup(
        monkeypatch, tmp_path):
    """A crash after restoring config but before removing the legacy license
    must not make a retry reinterpret an original user-owned value of 28 as
    the project's old preset."""
    _pin_work(monkeypatch, tmp_path)
    state_dir = _pin_round_corners_state(monkeypatch, tmp_path)
    state_dir.mkdir(parents=True)
    rounded.PREV_ROUND_CORNERS_FILE.write_text(json.dumps(
        _snapshot_payload(size=(True, "28"), inactive=(False, None))
    ) + "\n")
    license_file = tmp_path / "share/licenses/project/rounded.txt"
    license_file.parent.mkdir(parents=True)
    license_file.write_text("project ownership marker\n")
    monkeypatch.setattr(rounded, "LICENSE_FILE", license_file)
    monkeypatch.setattr(rounded, "_plugin_dir", lambda: tmp_path / "plugins")
    monkeypatch.setattr(rounded, "SHADER_DIR", tmp_path / "shaders")
    monkeypatch.setattr(rounded, "_locale_destinations", lambda: [])
    monkeypatch.setattr(rounded, "qdbus_call", lambda *args: True)
    monkeypatch.setattr(rounded, "info", lambda _message: None)
    writes: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        rounded, "kw_write", lambda *args: writes.append(args) or True,
    )

    def interrupt_at_license(path, _label=None):
        if path == license_file:
            raise RuntimeError("simulated process interruption")
        return True

    monkeypatch.setattr(rounded, "sudo_remove", interrupt_at_license)
    with pytest.raises(RuntimeError, match="interruption"):
        rounded.uninstall()

    assert rounded.PREV_ROUND_CORNERS_FILE.is_file()
    assert license_file.is_file()

    # A retry must consume the retained snapshot without recapturing the live
    # project value through the legacy-migration heuristic.
    monkeypatch.setattr(
        rounded,
        "_read_round_corners_key",
        lambda _key: (_ for _ in ()).throw(
            AssertionError("retry must use the retained exact snapshot")
        ),
    )

    def remove_on_retry(path, _label=None):
        if path == license_file:
            path.unlink()
        return True

    monkeypatch.setattr(rounded, "sudo_remove", remove_on_retry)
    writes.clear()
    rounded.uninstall()

    radius_writes = [write for write in writes if "Round-Corners" in write]
    assert any(
        "Size" in write and write[-1] == "28" and "--delete" not in write
        for write in radius_writes
    )
    assert not rounded.PREV_ROUND_CORNERS_FILE.exists()
    assert not license_file.exists()


def test_legacy_migration_stops_if_recovery_snapshot_cannot_be_saved(
    monkeypatch, tmp_path,
):
    _pin_work(monkeypatch, tmp_path)
    _pin_round_corners_state(monkeypatch, tmp_path)
    license_file = tmp_path / "installed/license"
    license_file.parent.mkdir(parents=True)
    license_file.write_text("marker\n")
    monkeypatch.setattr(rounded, "LICENSE_FILE", license_file)
    monkeypatch.setattr(
        rounded,
        "_read_round_corners_key",
        lambda _key: (True, str(rounded.CORNER_RADIUS)),
    )
    monkeypatch.setattr(
        rounded.os,
        "replace",
        lambda _source, _destination: (_ for _ in ()).throw(
            OSError("simulated replace failure")
        ),
    )
    writes: list[tuple[str, ...]] = []
    removed: list[Path] = []
    monkeypatch.setattr(
        rounded, "kw_write", lambda *args: writes.append(args) or True,
    )
    monkeypatch.setattr(
        rounded, "sudo_remove", lambda path, label=None: removed.append(path) or True,
    )
    monkeypatch.setattr(rounded, "fail", lambda _message: None)

    rounded.uninstall()

    assert writes == []
    assert removed == []
    assert license_file.is_file()
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
