"""Security-sensitive step helper tests."""

from __future__ import annotations

import os

from steps import _helpers


def test_temp_dir_is_private_unique_and_self_cleaning(tmp_path, monkeypatch):
    """A planted predictable path must never control staging contents."""
    monkeypatch.setattr(_helpers.tempfile, "tempdir", str(tmp_path))
    victim = tmp_path / "victim"
    victim.mkdir()
    planted = tmp_path / f"mttkde-test-{os.getpid()}"
    planted.symlink_to(victim, target_is_directory=True)

    with _helpers.temp_dir("mttkde-test") as staging:
        assert staging.parent == tmp_path
        assert staging != planted
        assert staging.stat().st_mode & 0o777 == 0o700
        (staging / "owned").write_text("safe\n")

    assert not staging.exists()
    assert planted.is_symlink()
    assert victim.is_dir()
