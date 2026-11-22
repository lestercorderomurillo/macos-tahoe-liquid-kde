"""Menu bar colours that follow the wallpaper (#146)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/scripts"))
import menubar_contrast as mc

L, D, S = mc.LIGHT, mc.DARK, mc.SUFFIX


@pytest.mark.parametrize("current, luminances, expected", [
    (L, [0.2], L + S),          # light mode, dark wallpaper: dark bar, light text
    (L, [0.9], L),              # light mode, light wallpaper: plain light style
    (L + S, [0.9], L),          # the wallpaper became light again
    (D, [0.9], D + S),          # dark mode, light wallpaper: light bar, dark text
    (D, [0.2], D),
    (D + S, [0.1], D),
    (L, [0.5], L),              # between the thresholds: keep the current bar
    (L + S, [0.5], L + S),
    (L, [0.1, 0.3], L + S),     # several screens: their mean decides
    ("Breeze", [0.1], "Breeze"),  # a style that is not MacTahoe stays untouched
    (L, [], L),                 # nothing measured: keep the current bar
])
def test_style_for_wallpaper(current, luminances, expected):
    assert mc.wanted_style(current, luminances) == expected


def test_variant_names_keep_the_appearance_word():
    # The light/dark switcher reads the appearance from the Plasma style's
    # name; a variant must never contain the other appearance's word.
    sys.path.insert(0, str(ROOT / "src/scripts"))
    from theme_switch import _named_mode
    assert _named_mode(L + S) == "light"
    assert _named_mode(D + S) == "dark"


def test_reads_static_and_slideshow_wallpapers(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.jpg"
    a.write_bytes(b"x"); b.write_bytes(b"x")
    rc = tmp_path / "appletsrc"
    rc.write_text(
        "[Containments][1][Wallpaper][org.kde.image][General]\nImage=file://" + str(a) + "\n\n"
        "[Containments][2][Wallpaper][org.kde.slideshow][General]\nImage=" + str(b) + "\n\n"
        "[Containments][3][Wallpaper][org.kde.image][General]\nImage=file://" + str(a) + "\n")
    assert mc.wallpapers(rc) == [a, b]


def test_measures_the_top_of_the_wallpaper(tmp_path):
    from PIL import Image
    image = Image.new("RGB", (400, 300), "white")
    image.paste((0, 0, 0), (0, 0, 400, 30))  # dark band behind the menu bar
    image.save(tmp_path / "w.png")
    assert mc.top_luminance(tmp_path / "w.png") < 0.1


def test_installer_builds_both_variants(tmp_path, monkeypatch):
    from steps import plasma_theme
    staging = tmp_path / "staging"
    for name in plasma_theme.VARIANTS:
        theme = staging / name
        theme.mkdir(parents=True)
        (theme / "metadata.json").write_text(json.dumps({"KPlugin": {"Id": name, "Name": name, "Name[de]": name}}))
        (theme / "metadata.desktop").write_text(f"[Desktop Entry]\nName={name}\nName[de]={name}\nX-KDE-PluginInfo-Name={name}\n")
        (theme / "look").write_text(name)
    for name in plasma_theme.VARIANTS:
        variant = plasma_theme._wallpaper_variant(staging, name)
        other = plasma_theme.WALLPAPER_SOURCES[name][0]
        assert variant.name == name + S
        assert (variant / "look").read_text() == other
        assert (variant / "colors").is_file()
        meta = json.loads((variant / "metadata.json").read_text())["KPlugin"]
        assert meta["Id"] == meta["Name"] == name + S and "Name[de]" not in meta
        desktop = (variant / "metadata.desktop").read_text()
        assert f"Name={name + S}\n" in desktop and "Name[de]" not in desktop
        assert f"X-KDE-PluginInfo-Name={name + S}" in desktop
