from pathlib import Path

import pytest

from steps import cursors, fonts, icons, wallpapers


def _mute_step_logs(monkeypatch, module, failures):
    if hasattr(module, "fail"):
        monkeypatch.setattr(module, "fail", lambda msg: failures.append(msg))
    for name in ("info", "ok", "reinstall"):
        if hasattr(module, name):
            monkeypatch.setattr(module, name, lambda _msg: None)


def _seed_fonts(cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    font = cache / "SF-Pro.ttf"
    font.write_bytes(b"font")
    return font


def _seed_icons(cache: Path) -> Path:
    theme = cache / "MacTahoeLiquidKde-Icons"
    theme.mkdir(parents=True, exist_ok=True)
    index = theme / "index.theme"
    index.write_text("[Icon Theme]\nName=MacTahoe\n")
    return index


def _seed_cursors(cache: Path) -> Path:
    theme = cache / "MacTahoeLiquidKde"
    (theme / "cursors").mkdir(parents=True, exist_ok=True)
    (theme / "index.theme").write_text("[Icon Theme]\nName=MacTahoe\n")
    cursor = theme / "cursors/left_ptr"
    cursor.write_text("cursor")
    return cursor


def _seed_wallpapers(cache: Path) -> Path:
    theme = cache / "MacTahoe"
    images = theme / "contents/images"
    images.mkdir(parents=True, exist_ok=True)
    (theme / "metadata.json").write_text("{}\n")
    wallpaper = images / "3840x2160.png"
    wallpaper.write_bytes(b"png")
    return wallpaper


@pytest.mark.parametrize(
    "module,seeder,relative_output",
    [
        (fonts, _seed_fonts, Path("SF-Pro.ttf")),
        (icons, _seed_icons, Path("MacTahoeLiquidKde-Icons/index.theme")),
        (cursors, _seed_cursors, Path("MacTahoeLiquidKde/cursors/left_ptr")),
        (wallpapers, _seed_wallpapers, Path("MacTahoe/contents/images/3840x2160.png")),
    ],
)
def test_install_uses_legacy_cache_when_new_build_cache_is_empty(
    tmp_path, monkeypatch, module, seeder, relative_output
):
    build_cache = tmp_path / "build-cache"
    legacy_cache = tmp_path / "legacy-cache"
    dest = tmp_path / "dest"
    failures = []

    seeder(legacy_cache)
    monkeypatch.setattr(module, "CACHE", build_cache)
    monkeypatch.setattr(module, "LEGACY_CACHE", legacy_cache)
    monkeypatch.setattr(module, "DEST_DIR", dest)
    _mute_step_logs(monkeypatch, module, failures)

    if module is fonts:
        monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: None)
    if module is icons:
        monkeypatch.setattr(module.shutil, "which", lambda _cmd: None)

    module.install()

    assert not failures
    assert (dest / relative_output).exists()


def test_fonts_prefer_new_build_cache_over_legacy_cache(tmp_path, monkeypatch):
    build_cache = tmp_path / "build-cache"
    legacy_cache = tmp_path / "legacy-cache"
    dest = tmp_path / "dest"

    new_font = _seed_fonts(build_cache)
    old_font = legacy_cache / "SF-Mono.ttf"
    old_font.parent.mkdir(parents=True, exist_ok=True)
    old_font.write_bytes(b"legacy")

    monkeypatch.setattr(fonts, "CACHE", build_cache)
    monkeypatch.setattr(fonts, "LEGACY_CACHE", legacy_cache)
    monkeypatch.setattr(fonts, "DEST_DIR", dest)
    monkeypatch.setattr(fonts.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(fonts, "fail", lambda _msg: None)
    monkeypatch.setattr(fonts, "info", lambda _msg: None)
    monkeypatch.setattr(fonts, "ok", lambda _msg: None)
    monkeypatch.setattr(fonts, "reinstall", lambda _msg: None)

    fonts.install()

    assert (dest / new_font.name).is_file()
    assert not (dest / old_font.name).exists()
