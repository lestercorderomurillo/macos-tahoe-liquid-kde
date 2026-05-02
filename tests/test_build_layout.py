# USELESS: file-existence checks on offline/ — passes while runtime panel JS fails to resolve C++ plasmoid IDs
from pathlib import Path

import pytest

import cli
import paths
from steps import _helpers, acrylic_glass, globalmenu, plasmoids


def _seed_cache(base: Path, feature: str) -> None:
    cache = base / feature.replace("_", "-")
    if feature == "wallpapers":
        images = cache / "MacTahoe/contents/images"
        images.mkdir(parents=True, exist_ok=True)
        (images / "3840x2160.png").write_bytes(b"png")
    elif feature == "fonts":
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "SF-Pro.ttf").write_bytes(b"font")
    elif feature == "cursors":
        theme = cache / "MacTahoeLiquidKde"
        (theme / "cursors").mkdir(parents=True, exist_ok=True)
        (theme / "index.theme").write_text("[Icon Theme]\nName=MacTahoe\n")
        (theme / "cursors/left_ptr").write_text("cursor")
    elif feature == "icons":
        theme = cache / "MacTahoeLiquidKde-Icons"
        theme.mkdir(parents=True, exist_ok=True)
        (theme / "index.theme").write_text("[Icon Theme]\nName=MacTahoe\n")
    else:
        raise AssertionError(f"unsupported feature {feature}")


def test_paths_keep_generated_content_under_build(repo):
    assert paths.SRC_DIR == repo / "src"
    assert paths.BUILD_DIR == repo / "build"
    assert paths.STEPS_DIR == repo / "build/steps"
    assert paths.LEGACY_STEPS_DIR == repo / "src/steps"
    assert paths.OFFLINE_DIR == repo / "src/offline"


def test_helper_dirs_follow_src_build_split(monkeypatch, repo):
    for name in ("OFFLINE", "STEPS", "BUILD", "SRC"):
        monkeypatch.delenv(name, raising=False)

    assert _helpers.offline("plasmoids") == repo / "src/offline/plasmoids"
    assert _helpers.steps_dir("icons") == repo / "build/steps/icons"
    assert _helpers.build_dir("plasmoids/demo") == repo / "build/plasmoids/demo"
    assert _helpers.src_dir("mirrors") == repo / "src/mirrors"


def test_helper_dirs_honor_independent_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("OFFLINE", str(tmp_path / "offline-out"))
    monkeypatch.setenv("STEPS", str(tmp_path / "steps-out"))
    monkeypatch.setenv("BUILD", str(tmp_path / "build-out"))
    monkeypatch.setenv("SRC", str(tmp_path / "src-out"))

    assert _helpers.offline("plasmoids") == tmp_path / "offline-out/plasmoids"
    assert _helpers.steps_dir("icons") == tmp_path / "steps-out/icons"
    assert _helpers.build_dir("plasmoids/demo") == tmp_path / "build-out/plasmoids/demo"
    assert _helpers.src_dir("mirrors") == tmp_path / "src-out/mirrors"


def test_native_steps_build_outside_source_tree(repo):
    expected = {
        plasmoids.TASKMANAGER_BUILD: repo / "build/plasmoids/org.kde.mac.tahoe.liquid.taskmanager",
        globalmenu.BUILD: repo / "build/plasmoids/org.kde.mac.tahoe.liquid.globalmenu",
        acrylic_glass.BUILD: repo / "build/kwin-effects/acrylic-glass",
    }

    for actual, want in expected.items():
        assert actual == want
        assert (repo / "build") in actual.parents
        assert (repo / "src") not in actual.parents


@pytest.mark.parametrize("feature", ["wallpapers", "fonts", "cursors", "icons"])
@pytest.mark.parametrize("base_name", ["build", "legacy"])
def test_has_cache_supports_build_and_legacy_locations(monkeypatch, tmp_path, feature, base_name):
    build_root = tmp_path / "build-steps"
    legacy_root = tmp_path / "legacy-steps"
    target_root = build_root if base_name == "build" else legacy_root

    _seed_cache(target_root, feature)
    monkeypatch.setattr(cli, "STEPS_DIR", build_root)
    monkeypatch.setattr(cli, "LEGACY_STEPS_DIR", legacy_root)

    assert cli.has_cache(feature, no_download=True) is True
    assert cli.has_cache(feature, no_download=False) is False


@pytest.mark.parametrize("feature", ["wallpapers", "fonts", "cursors", "icons"])
def test_has_cache_rejects_empty_caches(monkeypatch, tmp_path, feature):
    monkeypatch.setattr(cli, "STEPS_DIR", tmp_path / "build-steps")
    monkeypatch.setattr(cli, "LEGACY_STEPS_DIR", tmp_path / "legacy-steps")
    assert cli.has_cache(feature, no_download=True) is False
