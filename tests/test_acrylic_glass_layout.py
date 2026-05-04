# USELESS: kcfg/UI structure schema check only — never asserts the effect actually loads in KWin
"""Structure + schema checks for the Acrylic Glass KWin effect.

Verifies the v0.7.7 layout: renamed shaders, no legacy files, consistent
cross-references between .qrc / CMakeLists / .kcfg / .ui / C++ strings.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def effect_root(repo) -> Path:
    return repo / "src/offline/kwin-effects/acrylic-glass"


@pytest.fixture(scope="module")
def effect_src(effect_root) -> Path:
    return effect_root / "src"


# ── dead files are gone ───────────────────────────────────────────────────
_LEGACY_FILES = [
    "src/blur.cpp", "src/blur.h",
    "src/blur.kcfg", "src/blurconfig.kcfgc",
    "src/settings.cpp", "src/settings.h",
    "src/kcm/blur_config.cpp", "src/kcm/blur_config.h",
    "src/kcm/blur_config.ui", "src/kcm/blur_config.qrc",
    "src/kcm/about.html", "src/kcm/config.qrc",
    "src/shaders/onscreen_rounded.glsl",
    "src/shaders/onscreen_rounded_core.glsl",
    "src/shaders/onscreen_rounded.vert",
    "src/shaders/onscreen_rounded_core.vert",
    "src/shaders/glass_color.glsl",
]


@pytest.mark.parametrize("rel", _LEGACY_FILES)
def test_legacy_file_gone(effect_root, rel):
    assert not (effect_root / rel).exists(), f"{rel} should have been removed"


# ── new layout exists ─────────────────────────────────────────────────────
_EXPECTED_FILES = [
    "src/effect.cpp", "src/effect.h", "src/main.cpp",
    "src/glass.kcfg", "src/glassconfig.kcfgc",
    "src/liquidglass.qrc", "src/metadata.json",
    "src/CMakeLists.txt",
    "src/kcm/config.cpp", "src/kcm/config.h", "src/kcm/config.ui",
    "src/kcm/CMakeLists.txt",
    "src/shaders/glass.glsl", "src/shaders/glass_core.glsl",
    "src/shaders/glass.vert", "src/shaders/glass_core.vert",
    "src/shaders/sdf.glsl", "src/shaders/blur.glsl",
    "src/shaders/distort.glsl", "src/shaders/highlight.glsl",
    "src/shaders/downsample.frag", "src/shaders/upsample.frag",
    "src/shaders/noise.frag", "src/shaders/texture.frag",
    "src/shaders/vertex.vert",
]


@pytest.mark.parametrize("rel", _EXPECTED_FILES)
def test_expected_file_present(effect_root, rel):
    assert (effect_root / rel).is_file(), f"{rel} missing from new layout"


# ── cross-file reference consistency ──────────────────────────────────────
# glass.frag / glass_core.frag are produced at CMake configure time by
# preprocess_shader_includes() from the matching .glsl sources, and are
# gitignored. For those two, verify the .glsl source exists instead.
_QRC_GENERATED = {
    "shaders/glass.frag":      "shaders/glass.glsl",
    "shaders/glass_core.frag": "shaders/glass_core.glsl",
}


def test_qrc_shader_paths_point_at_real_files(effect_src):
    qrc = ET.parse(effect_src / "liquidglass.qrc").getroot()
    refs = [f.text for f in qrc.findall(".//file")]
    assert refs, "qrc had no <file> entries"
    for ref in refs:
        if ref in _QRC_GENERATED:
            src = _QRC_GENERATED[ref]
            assert (effect_src / src).is_file(), \
                f"qrc references generated {ref} but source {src} missing"
            continue
        assert (effect_src / ref).is_file(), \
            f"qrc references {ref} but file does not exist"


def test_qrc_has_glass_shaders_and_no_legacy_names(effect_src):
    text = (effect_src / "liquidglass.qrc").read_text()
    for name in ("shaders/glass.frag", "shaders/glass_core.frag",
                 "shaders/glass.vert", "shaders/glass_core.vert"):
        assert name in text, f"qrc missing {name}"
    assert "onscreen_rounded" not in text


def test_effect_cpp_loads_glass_shaders(effect_src):
    text = (effect_src / "effect.cpp").read_text()
    assert "shaders/glass.vert" in text
    assert "shaders/glass.frag" in text
    assert "onscreen_rounded" not in text


def test_cmake_preprocesses_glass_not_onscreen_rounded(effect_src):
    text = (effect_src / "CMakeLists.txt").read_text()
    assert "preprocess_shader_includes(shaders/glass.glsl" in text
    assert "preprocess_shader_includes(shaders/glass_core.glsl" in text
    assert "onscreen_rounded" not in text
    assert "blur.cpp" not in text
    assert "blurconfig.kcfgc" not in text
    assert "effect.cpp" in text
    assert "glassconfig.kcfgc" in text


def test_kcm_cmake_points_at_config_not_blur_config(effect_src):
    text = (effect_src / "kcm/CMakeLists.txt").read_text()
    assert "blur_config" not in text
    assert "about" not in text.lower()
    assert "config.cpp" in text and "config.h" in text
    assert "config.ui" in text


def test_main_cpp_includes_effect_header(effect_src):
    text = (effect_src / "main.cpp").read_text()
    assert '#include "effect.h"' in text
    assert '#include "blur.h"' not in text


def test_config_cpp_uses_new_names(effect_src):
    text = (effect_src / "kcm/config.cpp").read_text()
    assert '#include "config.h"' in text
    assert '#include "glassconfig.h"' in text
    assert 'blur_config' not in text


def test_config_h_uses_renamed_ui_class(effect_src):
    text = (effect_src / "kcm/config.h").read_text()
    assert '#include "ui_config.h"' in text
    assert "GlassEffectConfig ui" in text
    assert "BlurEffectConfig" not in text


def test_config_ui_form_class_renamed(effect_src):
    text = (effect_src / "kcm/config.ui").read_text()
    assert "<class>GlassEffectConfig</class>" in text
    assert "BlurEffectConfig" not in text


def test_kcfgc_references_renamed_kcfg(effect_src):
    text = (effect_src / "glassconfig.kcfgc").read_text()
    assert "File=glass.kcfg" in text
    assert "blur.kcfg" not in text


# ── kcfg schema integrity ─────────────────────────────────────────────────
_KCFG_NS = {"k": "http://www.kde.org/standards/kcfg/1.0"}
_EXPECTED_KCFG_KEYS = {
    "BlurStrength", "NoiseStrength", "BlurDecorations",
    "WindowClasses", "BlurMatching", "BlurNonMatching",
    "WindowCornerRadius", "DockCornerRadius", "PopupCornerRadius",
    "RoundCornersOfMaximizedWindows", "RgbDriftStrength",
    "MagnifyGlassStrength", "RefractionWidth",
    "HighlightWidth", "HighlightStrength",
}


def _kcfg_entries(path: Path) -> set[str]:
    root = ET.parse(path).getroot()
    return {e.get("name") for e in root.iter(f"{{{_KCFG_NS['k']}}}entry")}


def test_kcfg_contains_expected_keys(effect_src):
    keys = _kcfg_entries(effect_src / "glass.kcfg")
    missing = _EXPECTED_KCFG_KEYS - keys
    assert not missing, f"glass.kcfg missing keys: {sorted(missing)}"


# ── .ui widgets match kcfg entries ────────────────────────────────────────
def test_ui_widgets_cover_all_kcfg_keys(effect_src):
    ui_text = (effect_src / "kcm/config.ui").read_text()
    kcfg_keys = _kcfg_entries(effect_src / "glass.kcfg")
    widget_names = set(re.findall(r'name="kcfg_(\w+)"', ui_text))
    missing = kcfg_keys - widget_names
    assert not missing, \
        f".ui is missing kcfg_<name> widgets for: {sorted(missing)}"
