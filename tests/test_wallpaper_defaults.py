"""Edition defaults must survive installation and scheduled invocations."""

import json
import runpy

import pytest

from installer_choices import validate
import theme_switch
from steps import theme_switch as step
from steps import wallpapers


@pytest.mark.parametrize("package", ["MacTahoe", "MacGoldenGate"])
def test_edition_selects_bundled_light_dark_package(repo, tmp_path, monkeypatch, package):
    source = tmp_path / "theme_switch.py"
    (tmp_path / "defaults.json").write_text(json.dumps({"wallpaper": package}))
    monkeypatch.setattr(theme_switch, "__file__", str(source))
    monkeypatch.setenv("XDG_DATA_HOME", str(repo / "src/offline"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("MTTKDE_WIZARD_OPTIONS", raising=False)
    expected = repo / "src/offline/wallpapers" / package
    for mode in ("light", "dark"):
        assert theme_switch._wallpaper_path(mode) == expected
    for folder in ("images", "images_dark"):
        assert list((expected / "contents" / folder).glob("*.jpg"))
    assert json.loads((expected / "metadata.json").read_text())["KPlugin"]["Id"] == package
    assert theme_switch._wallpaper_image_is_theme_managed(str(expected))
    assert package in wallpapers._FIXED_NAMES


@pytest.mark.parametrize("raw", ['{}', '[]', '{', '{"wallpaper":"../../other"}'])
def test_invalid_defaults_fall_back_safely(tmp_path, monkeypatch, raw):
    monkeypatch.setattr(theme_switch, "__file__", str(tmp_path / "theme_switch.py"))
    (tmp_path / "defaults.json").write_text(raw)
    assert theme_switch.default_wallpaper() == "MacTahoe"


def test_anime_wallpaper_is_packaged_and_survives_switching(repo, monkeypatch):
    from PIL import Image

    monkeypatch.setenv("XDG_DATA_HOME", str(repo / "src/offline"))
    monkeypatch.setenv("MTTKDE_WIZARD_OPTIONS", json.dumps(validate({"wallpaper": "anime-city"})))
    package = repo / "src/offline/wallpapers/MacAnime-RainyCrossing"
    assert theme_switch._wallpaper_path("light") == theme_switch._wallpaper_path("dark") == package
    assert theme_switch._wallpaper_image_is_theme_managed(package.as_uri())
    with Image.open(package / "contents/images/3840x2160.jpg") as image:
        assert image.size == (3840, 2160) and image.format == "JPEG"


def test_installed_default_survives_without_checkout(tmp_path, monkeypatch):
    destination = tmp_path / "bin/mac-tahoe-theme-switch"
    monkeypatch.setattr(step, "BIN_DEST", destination)
    monkeypatch.setattr(step, "SVC_DIR", tmp_path / "systemd")
    monkeypatch.setattr(step, "default_wallpaper", lambda: "MacGoldenGate")
    monkeypatch.setattr(step, "stop_gtk_sync_watcher", lambda: None)
    monkeypatch.setattr(step, "_watcher_pids", lambda: [])
    monkeypatch.setattr(step, "_teardown_gtk_sync_autostart", lambda: None)
    monkeypatch.setattr(step, "theme_mode", lambda: "dark")
    monkeypatch.setattr(step, "_teardown_units", lambda: True)
    monkeypatch.setattr(step, "remove_periodic", lambda tag: step.RemovalStatus.ABSENT)
    step.install()
    # An unrelated JSON file beside a user's executable must not override
    # the installed edition on the next login or scheduled transition.
    (destination.parent / "defaults.json").write_text('{"wallpaper":"MacTahoe"}')
    installed = runpy.run_path(str(destination))
    assert installed["default_wallpaper"]() == "MacGoldenGate"
    assert destination.stat().st_mode & 0o111


def test_update_replaces_changed_image_without_removing_watched_directory(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "installed"
    for package in (source, target):
        (package / "contents/images").mkdir(parents=True)
    folder = target / "contents/images"
    inode = folder.stat().st_ino
    (folder / "current.jpg").write_bytes(b"old")
    (folder / "retired.jpg").touch()
    (source / "contents/images/current.jpg").write_bytes(b"updated")
    assert wallpapers._update_package(source, target)
    assert folder.stat().st_ino == inode
    assert (folder / "current.jpg").read_bytes() == b"updated"
    assert not (folder / "retired.jpg").exists()
