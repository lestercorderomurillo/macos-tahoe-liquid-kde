"""Cross-stack guards for Tahoe's semantic corner-radius families."""

from __future__ import annotations

import gzip
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from steps import acrylic_glass, rounded_corners
from theme_metrics import (
    DIALOG_CORNER_RADIUS,
    DOCK_CORNER_RADIUS,
    MENU_CORNER_RADIUS,
    POPUP_CORNER_RADIUS,
    TOOLTIP_CORNER_RADIUS,
    WINDOW_CORNER_RADIUS,
)


def _css_rules(text: str, selector: str) -> list[str]:
    matches = re.findall(
        rf"^{re.escape(selector)}\s*\{{([^}}]*)\}}", text, re.MULTILINE
    )
    assert matches, selector
    return matches


def _has_radius(rule: str, value: str) -> bool:
    return bool(re.search(rf"border(?:-[a-z]+)*-radius:\s*{re.escape(value)}\s*;", rule))


def _svgz_text(path: Path) -> str:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return stream.read()


def test_corner_metrics_keep_distinct_surface_families():
    assert WINDOW_CORNER_RADIUS == 22
    assert DOCK_CORNER_RADIUS == 22
    assert DIALOG_CORNER_RADIUS == 14
    assert TOOLTIP_CORNER_RADIUS == 14
    assert POPUP_CORNER_RADIUS == 6
    assert MENU_CORNER_RADIUS == 0


def test_kwin_effect_presets_use_the_semantic_families():
    acrylic = dict(acrylic_glass._PRESET)
    assert "BottomCornerRadius" not in acrylic
    assert {
        key: acrylic[key]
        for key in (
            "WindowCornerRadius",
            "DockCornerRadius",
            "DialogCornerRadius",
            "TooltipCornerRadius",
            "PopupCornerRadius",
            "MenuCornerRadius",
        )
    } == {
        "WindowCornerRadius": "22",
        "DockCornerRadius": "22",
        "DialogCornerRadius": "14",
        "TooltipCornerRadius": "14",
        "PopupCornerRadius": "6",
        "MenuCornerRadius": "0",
    }

    rounded = dict(rounded_corners._PRESET)
    assert rounded["Size"] == "22"
    assert rounded["InactiveCornerRadius"] == "22"
    # The standalone effect is window-only so it cannot overwrite the
    # intentionally tighter dialog family supplied by Acrylic and SVG/CSS.
    assert rounded["IncludeDialogs"] == "false"


def test_acrylic_defaults_and_kcm_expose_every_radius_family(repo):
    source = repo / "src/offline/kwin-effects/acrylic-glass/src"
    root = ET.parse(source / "glass.kcfg").getroot()
    defaults = {
        entry.attrib["name"]: entry.findtext("{*}default")
        for entry in root.findall(".//{*}entry")
    }
    assert {
        key: float(defaults[key])
        for key in (
            "WindowCornerRadius",
            "DockCornerRadius",
            "DialogCornerRadius",
            "TooltipCornerRadius",
            "PopupCornerRadius",
            "MenuCornerRadius",
        )
    } == {
        "WindowCornerRadius": 22.0,
        "DockCornerRadius": 22.0,
        "DialogCornerRadius": 14.0,
        "TooltipCornerRadius": 14.0,
        "PopupCornerRadius": 6.0,
        "MenuCornerRadius": 0.0,
    }

    kcm = ET.parse(source / "kcm/config.ui").getroot()
    names = {widget.attrib.get("name") for widget in kcm.findall(".//widget")}
    for key in defaults:
        if key.endswith("CornerRadius") and key != "RoundCornersOfMaximizedWindows":
            assert f"kcfg_{key}" in names


def test_acrylic_routes_window_types_to_their_own_radius(repo):
    effect = (
        repo / "src/offline/kwin-effects/acrylic-glass/src/effect.cpp"
    ).read_text()
    routes = (
        ("w->isDock()", "BlurConfig::dockCornerRadius()"),
        ("w->isTooltip()", "BlurConfig::tooltipCornerRadius()"),
        ("w->isMenu()", "BlurConfig::menuCornerRadius()"),
        ("w->isPopupWindow()", "BlurConfig::popupCornerRadius()"),
        ("w->isDialog()", "BlurConfig::dialogCornerRadius()"),
    )
    positions = []
    for predicate, getter in routes:
        predicate_at = effect.index(predicate, effect.index("Resolve per-window corner"))
        getter_at = effect.index(getter, predicate_at)
        assert getter_at - predicate_at < 900
        positions.append(predicate_at)
    assert positions == sorted(positions)
    window_getter = effect.index("BlurConfig::windowCornerRadius()", positions[-1])
    assert window_getter > effect.index("} else {", positions[-1])


@pytest.mark.parametrize(
    ("relative", "radius"),
    (
        ("src/installer/InstallerWindow.qml", 22),
        ("src/installer/FeaturesWindow.qml", 22),
        ("src/installer/InstallError.qml", 22),
        (
            "src/offline/plasmoids/org.kde.mac-tahoe-liquid-kde.launcher/"
            "contents/ui/AppGridViewDelegate.qml",
            22,
        ),
        (
            "src/offline/plasmoids/org.kde.mac-tahoe-liquid-kde.launcher/"
            "contents/ui/Highlight.qml",
            10,
        ),
        (
            "src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/"
            "qml/AboutWindow.qml",
            22,
        ),
    ),
)
def test_qml_keeps_role_specific_radii(repo, relative, radius):
    text = (repo / relative).read_text()
    assert re.search(rf"\bradius:\s*{radius}\b", text), relative


@pytest.mark.parametrize(
    "relative",
    (
        "src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/qml/MenuDelegate.qml",
        "src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu/qml/main.qml",
    ),
)
def test_compact_qml_menu_tiles_keep_kirigami_radius(repo, relative):
    assert "radius: Kirigami.Units.cornerRadius" in (repo / relative).read_text()


def test_gtk3_normal_dialog_tooltip_and_popover_families_stay_distinct(repo):
    for path in (repo / "src/offline/gtk").glob("*/gtk-3.0/gtk*.css"):
        text = path.read_text()
        checks = (
            (".background.csd", "0 0 22px 22px"),
            ("decoration", "22px"),
            ("messagedialog.csd decoration", "14px"),
            ("tooltip", "14px"),
            ("popover.background", "12px"),
        )
        for selector, value in checks:
            assert any(_has_radius(rule, value) for rule in _css_rules(text, selector)), (
                path,
                selector,
                value,
            )
        # These compact controls are deliberately not part of the 22 px
        # normal-window family.
        assert "border-radius: 6px;" in text
        assert any(
            _has_radius(rule, "24px")
            for rule in _css_rules(text, "popover.emoji-picker")
        )


def test_gtk4_normal_dialog_tooltip_and_popover_families_stay_distinct(repo):
    for path in (repo / "src/offline/gtk").glob("*/gtk-4.0/gtk*.css"):
        text = path.read_text()
        checks = (
            ("window.csd", "22px"),
            ("window.dialog.message.background", "14px"),
            ("floating-sheet > sheet", "14px"),
            ("tooltip", "14px"),
            ("popover > contents", "12px"),
        )
        for selector, value in checks:
            assert any(_has_radius(rule, value) for rule in _css_rules(text, selector)), (
                path,
                selector,
                value,
            )
        assert "border-radius: 6px;" in text


def test_aurorae_window_beziers_resolve_to_22px(repo):
    root = repo / "src/offline/aurorae"
    for path in root.glob("MacTahoeLiquidKde-*/decoration.svg"):
        text = path.read_text()
        ET.fromstring(text)
        # 12.188 is the quarter-circle control distance for r=22.
        assert "12.188" in text
        assert "C 444.188" in text
        assert "13.296" not in text
        assert "13.85" not in text


def test_plasma_dialog_and_tooltip_slices_resolve_to_14px(repo):
    root = repo / "src/offline/plasma-theme"
    for variant in ("MacTahoeLiquidKde-Light", "MacTahoeLiquidKde-Dark"):
        theme = root / variant
        for relative in (
            "dialogs/background.svgz",
            "widgets/tooltip.svgz",
            "solid/dialogs/background.svgz",
            "solid/widgets/tooltip.svgz",
        ):
            text = _svgz_text(theme / relative)
            ET.fromstring(text)
            assert 'transform="matrix(2,0,0,2' in text
            # The visible corner is r=7 inside a 2x group: 7 * 2 = 14.
            assert "-3.877985,0 -7,3.122015 -7,7" in text
            assert "m 24,910.36216 c -6.093976,0 -11,4.90603 -11,11" not in text


def test_plasma_bottom_dock_slices_resolve_to_22_without_flattening_panel(repo):
    root = repo / "src/offline/plasma-theme"
    for variant in ("MacTahoeLiquidKde-Light", "MacTahoeLiquidKde-Dark"):
        theme = root / variant
        for relative in (
            "widgets/panel-background.svgz",
            "solid/widgets/panel-background.svgz",
        ):
            text = _svgz_text(theme / relative)
            ET.fromstring(text)
            # Eight south paths (four visible + four masks) use r=17.6 in a
            # 1.25x group: 17.6 * 1.25 = 22.
            assert text.count(
                "-9.750362,0 -17.6,7.849638 -17.6,17.6"
            ) == 8
            # Six generic panel paths retain their independent r=16 geometry.
            assert text.count("-8.863965,0 -16,7.13604 -16,16") == 6


def test_plasma_generic_widget_background_keeps_12px_geometry(repo):
    root = repo / "src/offline/plasma-theme"
    for variant in ("MacTahoeLiquidKde-Light", "MacTahoeLiquidKde-Dark"):
        text = _svgz_text(root / variant / "widgets/background.svgz")
        assert "h 12 c 0,-6.648 5.352,-12 12,-12" in text
