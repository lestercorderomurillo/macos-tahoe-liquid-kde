"""Static guards for the Acrylic Glass CMake fallback paths."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent / "src/offline/kwin-effects/acrylic-glass"


def test_acrylic_glass_fails_cleanly_without_kwin_dev_support():
    top = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "if(NOT GLASS_WAYLAND AND NOT GLASS_X11)" in top
    assert "Acrylic Glass requires KWin development files for Wayland or X11." in top


def test_acrylic_glass_only_configures_kcm_when_a_kwin_backend_is_available():
    src = (ROOT / "src/CMakeLists.txt").read_text(encoding="utf-8")
    assert "if(GLASS_WAYLAND OR GLASS_X11)" in src
    assert "add_subdirectory(kcm)" in src
