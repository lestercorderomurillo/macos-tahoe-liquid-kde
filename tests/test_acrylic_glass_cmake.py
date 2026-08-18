"""Static guards for the Acrylic Glass CMake fallback paths."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "src/offline/kwin-effects/acrylic-glass"


def test_acrylic_glass_fails_cleanly_without_kwin_dev_support():
    top = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "if(NOT GLASS_WAYLAND AND NOT GLASS_X11)" in top
    assert "Acrylic Glass requires KWin development files for Wayland or X11." in top


def test_acrylic_glass_only_configures_kcm_when_a_kwin_backend_is_available():
    src = (ROOT / "src/CMakeLists.txt").read_text(encoding="utf-8")
    assert "if(GLASS_WAYLAND OR GLASS_X11)" in src
    assert "add_subdirectory(kcm)" in src


def test_acrylic_glass_version_floor_matches_preflight():
    """The effect's CMake floor, the preflight runtime floor, and the
    README must all agree on 6.6 — they drifted once (CMake said 6.4
    while preflight blocked <6.6), which is exactly the inconsistency
    this test exists to prevent."""
    sys.path.insert(0, str(REPO / "src/scripts"))
    import preflight

    assert preflight._MIN_PLASMA == (6, 6)

    top = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "VERSION_LESS 6.6" in top
    assert "requires KDE Plasma 6.6+" in top
    # The retired 6.4 floor must not creep back.
    assert "VERSION_LESS 6.4" not in top


def test_acrylic_glass_preset_fits_kcm_ranges():
    """Installer tuning must remain representable in the effect KCM."""
    from steps import acrylic_glass

    preset = dict(acrylic_glass._PRESET)
    root = ET.parse(ROOT / "src/kcm/config.ui").getroot()
    for key in ("RgbDriftStrength", "MagnifyGlassStrength"):
        widget = root.find(f".//widget[@name='kcfg_{key}']")
        assert widget is not None
        maximum = widget.find("./property[@name='maximum']/double")
        assert maximum is not None and maximum.text is not None
        assert float(preset[key]) <= float(maximum.text)
