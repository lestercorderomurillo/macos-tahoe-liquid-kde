"""Bundled Qt 6 Kvantum engine fallback for Debian-family hosts."""

from __future__ import annotations

import hashlib
import json


def _neon(monkeypatch, kvantum, destination):
    monkeypatch.setattr(kvantum, "current_distro", lambda: "neon")
    monkeypatch.setattr(kvantum, "distro_id_like", lambda: ("ubuntu", "debian"))
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
