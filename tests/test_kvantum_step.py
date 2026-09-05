"""Bundled Qt 6 Kvantum engine fallback for Debian-family hosts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


def _neon(monkeypatch, kvantum, destination):
    monkeypatch.setattr(kvantum, "is_debian_family", lambda: True)
    monkeypatch.setattr(kvantum, "_engine_destination", lambda: destination)


def test_neon_uses_build_deps_when_qt6_engine_is_missing(monkeypatch, tmp_path):
    from steps import kvantum

    _neon(monkeypatch, kvantum, tmp_path / "plugins/styles/libkvantum.so")

    deps = set(kvantum.deps())

    assert "qt6-svg-cmake:qt6-svg" in deps
    assert "xext-cmake:libxext" in deps
    assert "kvantummanager:kvantum" not in deps


def test_neon_keeps_unmarked_distro_qt6_engine(monkeypatch, tmp_path):
    from steps import kvantum

    destination = tmp_path / "plugins/styles/libkvantum.so"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"distro-owned")
    _neon(monkeypatch, kvantum, destination)
    monkeypatch.setattr(kvantum, "ENGINE_MARKER", tmp_path / "missing-marker")

    assert kvantum.deps() == []
    assert kvantum.build_artifacts() == []


def test_bundled_archive_extracts_only_after_digest_check(monkeypatch, tmp_path):
    from steps import kvantum

    work = tmp_path / "work"
    source = work / f"Kvantum-{kvantum.ENGINE_VERSION}"
    monkeypatch.setattr(kvantum, "ENGINE_WORK", work)
    monkeypatch.setattr(kvantum, "ENGINE_SOURCE", source)

    assert kvantum._extract_bundled_engine() is True
    assert (source / "Kvantum/CMakeLists.txt").is_file()
    assert (source / "Kvantum/COPYING").is_file()

    corrupt = tmp_path / "Kvantum-corrupt.tar.xz"
    corrupt.write_bytes(kvantum.ENGINE_ARCHIVE.read_bytes() + b"corrupt")
    monkeypatch.setattr(kvantum, "ENGINE_ARCHIVE", corrupt)
    failures = []
    monkeypatch.setattr(kvantum, "fail", failures.append)

    assert kvantum._extract_bundled_engine() is False
    assert any("checksum mismatch" in message for message in failures)


def test_build_compiles_only_the_qt6_style_target(monkeypatch, tmp_path):
    from steps import kvantum

    calls = []
    monkeypatch.setattr(kvantum, "_bundled_engine_required", lambda: True)
    monkeypatch.setattr(kvantum, "_extract_bundled_engine", lambda: True)
    monkeypatch.setattr(kvantum, "ENGINE_SOURCE", tmp_path / "source")
    monkeypatch.setattr(kvantum, "ENGINE_BUILD", tmp_path / "build")
    monkeypatch.setattr(
        kvantum,
        "cmake_build",
        lambda *args, **kwargs: calls.append((args, kwargs)) or True,
    )

    kvantum.build()

    assert calls[0][1]["targets"] == ("kvantum",)


def test_marker_is_prepared_before_any_system_install(monkeypatch, tmp_path):
    from steps import kvantum

    build = tmp_path / "build"
    artifact = build / "style/libkvantum.so"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"plugin")
    source = tmp_path / "source"
    license_source = source / "Kvantum/COPYING"
    license_source.parent.mkdir(parents=True)
    license_source.write_text("GPL-3.0\n")
    work = tmp_path / "work"
    installs: list[tuple] = []
    failures: list[str] = []

    monkeypatch.setattr(kvantum, "_bundled_engine_required", lambda: True)
    monkeypatch.setattr(kvantum, "ENGINE_BUILD", build)
    monkeypatch.setattr(kvantum, "ENGINE_SOURCE", source)
    monkeypatch.setattr(kvantum, "ENGINE_WORK", work)
    monkeypatch.setattr(
        kvantum, "_engine_destination",
        lambda: tmp_path / "plugins/styles/libkvantum.so",
    )
    monkeypatch.setattr(
        kvantum, "sudo_install_file",
        lambda *args: installs.append(args) or True,
    )
    monkeypatch.setattr(kvantum, "fail", failures.append)

    real_write_text = Path.write_text

    def fail_marker_write(path, *args, **kwargs):
        if path == work / "kvantum-engine.json":
            raise OSError("disk full")
        return real_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_marker_write)

    assert kvantum._install_bundled_engine() is False
    assert installs == []
    assert any("marker could not be prepared" in message for message in failures)


def test_non_object_ownership_marker_is_not_trusted(monkeypatch, tmp_path):
    from steps import kvantum

    destination = tmp_path / "plugins/styles/libkvantum.so"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"plugin")
    marker = tmp_path / "kvantum-engine.json"
    marker.write_text("[]\n")
    monkeypatch.setattr(kvantum, "_engine_destination", lambda: destination)
    monkeypatch.setattr(kvantum, "ENGINE_MARKER", marker)

    assert kvantum._engine_matches_ownership_marker() is False


def test_pending_marker_owns_old_and_new_plugin_during_reinstall(
        monkeypatch, tmp_path):
    from steps import kvantum

    destination = tmp_path / "plugins/styles/libkvantum.so"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"old plugin")
    marker = tmp_path / "share/kvantum-engine.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({
        "version": "old",
        "plugin_sha256": hashlib.sha256(b"old plugin").hexdigest(),
    }))
    license_dest = tmp_path / "share/Kvantum.txt"
    build = tmp_path / "build"
    artifact = build / "style/libkvantum.so"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"new plugin")
    source = tmp_path / "source"
    license_source = source / "Kvantum/COPYING"
    license_source.parent.mkdir(parents=True)
    license_source.write_text("GPL-3.0\n")
    calls: list[Path] = []

    monkeypatch.setattr(kvantum, "_bundled_engine_required", lambda: True)
    monkeypatch.setattr(kvantum, "_engine_destination", lambda: destination)
    monkeypatch.setattr(kvantum, "ENGINE_MARKER", marker)
    monkeypatch.setattr(kvantum, "ENGINE_LICENSE", license_dest)
    monkeypatch.setattr(kvantum, "ENGINE_BUILD", build)
    monkeypatch.setattr(kvantum, "ENGINE_SOURCE", source)
    monkeypatch.setattr(kvantum, "ENGINE_WORK", tmp_path / "work")

    def install_file(src, dest, _label):
        calls.append(dest)
        # The marker published before replacement must recognize the old file.
        if dest == destination:
            assert kvantum._engine_matches_ownership_marker() is True
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(Path(src).read_bytes())
        # It must also recognize the new file immediately after replacement.
        if dest == destination:
            assert kvantum._engine_matches_ownership_marker() is True
        return True

    monkeypatch.setattr(kvantum, "sudo_install_file", install_file)

    assert kvantum._install_bundled_engine() is True
    assert calls == [marker, destination, license_dest, marker]
    final = json.loads(marker.read_text())
    assert final["plugin_sha256"] == hashlib.sha256(b"new plugin").hexdigest()
    assert "state" not in final
    assert "previous_plugin_sha256" not in final


def test_failed_reinstall_leaves_pending_marker_owning_previous_plugin(
        monkeypatch, tmp_path):
    from steps import kvantum

    destination = tmp_path / "plugins/styles/libkvantum.so"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"old plugin")
    marker = tmp_path / "share/kvantum-engine.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({
        "plugin_sha256": hashlib.sha256(b"old plugin").hexdigest(),
    }))
    build = tmp_path / "build"
    artifact = build / "style/libkvantum.so"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"new plugin")
    source = tmp_path / "source"
    license_source = source / "Kvantum/COPYING"
    license_source.parent.mkdir(parents=True)
    license_source.write_text("GPL-3.0\n")

    monkeypatch.setattr(kvantum, "_bundled_engine_required", lambda: True)
    monkeypatch.setattr(kvantum, "_engine_destination", lambda: destination)
    monkeypatch.setattr(kvantum, "ENGINE_MARKER", marker)
    monkeypatch.setattr(kvantum, "ENGINE_LICENSE", tmp_path / "share/Kvantum.txt")
    monkeypatch.setattr(kvantum, "ENGINE_BUILD", build)
    monkeypatch.setattr(kvantum, "ENGINE_SOURCE", source)
    monkeypatch.setattr(kvantum, "ENGINE_WORK", tmp_path / "work")

    def fail_plugin(src, dest, _label):
        if dest == marker:
            dest.write_bytes(Path(src).read_bytes())
            return True
        return False

    monkeypatch.setattr(kvantum, "sudo_install_file", fail_plugin)

    assert kvantum._install_bundled_engine() is False
    pending = json.loads(marker.read_text())
    assert pending["state"] == "pending"
    assert kvantum._engine_matches_ownership_marker() is True
    assert destination.read_bytes() == b"old plugin"


def test_uninstall_removes_only_the_digest_owned_engine(monkeypatch, tmp_path):
    from steps import kvantum

    destination = tmp_path / "plugins/styles/libkvantum.so"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"ours")
    marker = tmp_path / "share/kvantum-engine.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({
        "version": kvantum.ENGINE_VERSION,
        "plugin_sha256": hashlib.sha256(b"ours").hexdigest(),
    }))
    license_file = tmp_path / "share/Kvantum.txt"
    license_file.write_text("GPL-3.0")

    monkeypatch.setattr(kvantum, "_engine_destination", lambda: destination)
    monkeypatch.setattr(kvantum, "ENGINE_MARKER", marker)
    monkeypatch.setattr(kvantum, "ENGINE_LICENSE", license_file)
    monkeypatch.setattr(
        kvantum,
        "sudo_remove",
        lambda path, _label=None: path.unlink(missing_ok=True) or True,
    )

    kvantum._remove_bundled_engine()

    assert not destination.exists()
    assert not marker.exists()
    assert not license_file.exists()


def test_uninstall_preserves_engine_replaced_by_distro(monkeypatch, tmp_path):
    from steps import kvantum

    destination = tmp_path / "plugins/styles/libkvantum.so"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"distro replacement")
    marker = tmp_path / "kvantum-engine.json"
    marker.write_text(json.dumps({
        "version": kvantum.ENGINE_VERSION,
        "plugin_sha256": hashlib.sha256(b"old project build").hexdigest(),
    }))
    license_file = tmp_path / "Kvantum.txt"
    license_file.write_text("GPL-3.0")
    warnings = []

    monkeypatch.setattr(kvantum, "_engine_destination", lambda: destination)
    monkeypatch.setattr(kvantum, "ENGINE_MARKER", marker)
    monkeypatch.setattr(kvantum, "ENGINE_LICENSE", license_file)
    monkeypatch.setattr(kvantum, "warn", warnings.append)
    monkeypatch.setattr(
        kvantum,
        "sudo_remove",
        lambda path, _label=None: path.unlink(missing_ok=True) or True,
    )

    kvantum._remove_bundled_engine()

    assert destination.read_bytes() == b"distro replacement"
    assert not marker.exists()
    assert warnings and "leaving" in warnings[0]


def test_uninstall_retains_recovery_marker_when_owned_engine_remove_fails(
        monkeypatch, tmp_path):
    from steps import kvantum

    destination = tmp_path / "plugins/styles/libkvantum.so"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"ours")
    marker = tmp_path / "share/kvantum-engine.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({
        "plugin_sha256": hashlib.sha256(b"ours").hexdigest(),
    }))
    license_file = tmp_path / "share/Kvantum.txt"
    license_file.write_text("GPL-3.0")
    failures: list[str] = []

    monkeypatch.setattr(kvantum, "_engine_destination", lambda: destination)
    monkeypatch.setattr(kvantum, "ENGINE_MARKER", marker)
    monkeypatch.setattr(kvantum, "ENGINE_LICENSE", license_file)
    monkeypatch.setattr(kvantum, "fail", failures.append)
    monkeypatch.setattr(kvantum, "sudo_remove", lambda *_args: False)

    kvantum._remove_bundled_engine()

    assert destination.is_file()
    assert marker.is_file()
    assert license_file.is_file()
    assert any("retaining" in failure for failure in failures)


@pytest.mark.parametrize("unreadable", ["marker", "plugin"])
def test_uninstall_retains_recovery_when_ownership_cannot_be_read(
        monkeypatch, tmp_path, unreadable):
    from steps import kvantum

    destination = tmp_path / "plugins/styles/libkvantum.so"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"ours")
    marker = tmp_path / "share/kvantum-engine.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({
        "plugin_sha256": hashlib.sha256(b"ours").hexdigest(),
    }))
    license_file = tmp_path / "share/Kvantum.txt"
    license_file.write_text("GPL-3.0")
    failures: list[str] = []

    monkeypatch.setattr(kvantum, "_engine_destination", lambda: destination)
    monkeypatch.setattr(kvantum, "ENGINE_MARKER", marker)
    monkeypatch.setattr(kvantum, "ENGINE_LICENSE", license_file)
    monkeypatch.setattr(kvantum, "fail", failures.append)
    monkeypatch.setattr(
        kvantum, "sudo_remove",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("cleanup must not run without ownership proof")
        ),
    )

    if unreadable == "marker":
        real_read_text = Path.read_text

        def fail_marker_read(path, *args, **kwargs):
            if path == marker:
                raise OSError("transient read failure")
            return real_read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", fail_marker_read)
    else:
        monkeypatch.setattr(
            kvantum, "_sha256",
            lambda _path: (_ for _ in ()).throw(OSError("transient read failure")),
        )

    kvantum._remove_bundled_engine()

    assert destination.is_file()
    assert marker.is_file()
    assert license_file.is_file()
    assert failures and "retaining" in failures[0]


@pytest.mark.parametrize("payload", ["{not-json}\n", "[]\n", '{"plugin_sha256":"nope"}\n'])
def test_uninstall_retains_invalid_ownership_marker_for_recovery(
        monkeypatch, tmp_path, payload):
    from steps import kvantum

    destination = tmp_path / "plugins/styles/libkvantum.so"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"possibly ours")
    marker = tmp_path / "share/kvantum-engine.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(payload)
    license_file = tmp_path / "share/Kvantum.txt"
    license_file.write_text("GPL-3.0")
    failures: list[str] = []

    monkeypatch.setattr(kvantum, "_engine_destination", lambda: destination)
    monkeypatch.setattr(kvantum, "ENGINE_MARKER", marker)
    monkeypatch.setattr(kvantum, "ENGINE_LICENSE", license_file)
    monkeypatch.setattr(kvantum, "fail", failures.append)
    monkeypatch.setattr(
        kvantum, "sudo_remove",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("invalid ownership proof must not remove anything")
        ),
    )

    kvantum._remove_bundled_engine()

    assert destination.is_file()
    assert marker.is_file()
    assert license_file.is_file()
    assert failures and "retaining" in failures[0]
