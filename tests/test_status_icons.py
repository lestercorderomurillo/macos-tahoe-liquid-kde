"""Battery foreground, warning colors, aliases and staged installation regressions."""
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

from status_icon_palette import FOREGROUND, SVG, apply_status_palette, palette_svg


@pytest.fixture(scope="module")
def battery_themes(repo, tmp_path_factory):
    root = tmp_path_factory.mktemp("battery-icons")
    subprocess.run(["tar", "--zstd", "-xf", str(repo / "src/offline/icons/MacTahoeLiquidKde-Icons.tar.zst"),
                    "-C", str(root)], check=True)
    return root


def test_palette_preserves_artwork_notices_and_status_colors():
    source = f'''<svg xmlns="{SVG}"><!-- Original notice --><title>Original artwork</title>
    <path d="M1 2h3" fill="#f2f2f2" color="#f2f2f2"/>
    <path d="M2 3h4" fill="#da4453"/><rect width="8" height="4" fill="#27ae60"/>
    <path style="fill:#dedede;stroke:#363636" d="M4 5h6"/></svg>'''
    result = palette_svg(source)
    assert "Original notice" in result and "Original artwork" in result
    root = ET.fromstring(result)
    paths = root.findall(f"{{{SVG}}}path")
    assert paths[0].get("d") == "M1 2h3"
    assert paths[0].get("fill") == "currentColor"
    assert paths[0].get("class") == "ColorScheme-Text"
    assert paths[0].get("color") is None
    assert paths[1].get("fill") == "#da4453"
    assert root.find(f"{{{SVG}}}rect").get("fill") == "#27ae60"
    assert paths[2].get("style") == "fill:currentColor;stroke:currentColor"
    assert palette_svg(result) == result


def test_bundled_battery_aliases_are_recolored_without_changing_geometry(battery_themes):
    paths = sorted({p.resolve() for p in battery_themes.glob("*/status/*/battery-*.svg") if p.is_file()})
    before = {p: p.read_text() for p in paths}
    aliases = {p: p.readlink() for p in battery_themes.glob("*/status/*/battery-*.svg") if p.is_symlink()}
    apply_status_palette(battery_themes)
    changed = 0
    for path, original in before.items():
        result = path.read_text()
        changed += original != result
        old = ET.fromstring(original)
        new = ET.fromstring(result)
        def geometry(root):
            return [(node.tag, {key: value for key, value in node.attrib.items()
                               if key in {"d", "x", "y", "width", "height", "rx", "ry", "transform", "viewBox"}})
                    for node in root.iter() if node.tag not in {f"{{{SVG}}}defs", f"{{{SVG}}}style"}]
        assert geometry(old) == geometry(new), path
        for node in new.iter():
            assert node.get("fill", "").lower() not in FOREGROUND, path
            assert node.get("stroke", "").lower() not in FOREGROUND, path
        assert palette_svg(result) == result
    assert changed > 50
    assert all(path.readlink() == target for path, target in aliases.items())


def test_battery_staging_rejects_external_links(tmp_path):
    icons = tmp_path / "themes"
    status = icons / "MacTahoeLiquidKde-Icons/status/22"
    status.mkdir(parents=True)
    outside = tmp_path / "outside.svg"
    outside.write_text(f'<svg xmlns="{SVG}"><path fill="#f2f2f2"/></svg>')
    (status / "battery-full.svg").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes staging"):
        apply_status_palette(icons)
    assert '#f2f2f2' in outside.read_text()


def test_icon_install_reinstall_uninstall_recolors_staged_batteries(repo, tmp_path, monkeypatch, sandbox):
    from steps import icons
    from installer_choices import selected
    assert not selected()
    dest = tmp_path / "installed"
    monkeypatch.setattr(icons, "DEST_DIR", dest)
    monkeypatch.setattr(icons, "OFFLINE_DIR", repo / "src/offline/icons")
    monkeypatch.setattr(icons.shutil, "which", lambda command: None)
    config = sandbox / ".config/plasma-org.kde.plasma.desktop-appletsrc"
    choices = "[Containments][2][Applets][7][Configuration][General]\nshowPercentage=true\n"
    config.write_text(choices)
    icons.install()
    battery = dest / "MacTahoeLiquidKde-Icons/status/16/battery-full.svg"
    fixed = battery.read_text()
    assert 'class="ColorScheme-Text"' in fixed
    battery.write_text("stale previous install")
    icons.install()
    assert battery.read_text() == fixed
    icons.uninstall()
    assert not list(dest.glob("MacTahoeLiquidKde-Icons*"))
    assert config.read_text() == choices


def test_battery_kiconloader_light_dark_light(repo, battery_themes, tmp_path):
    from icon_toolset import BASE, VARIANTS, index_text, installer_themes, theme_name

    if not shutil.which("cmake") or not shutil.which("pkg-config"):
        pytest.skip("Qt6/KF6 icon development SDK required")
    if subprocess.run(["pkg-config", "--exists", "Qt6Widgets"], check=False).returncode:
        pytest.skip("Qt6/KF6 icon development SDK required")
    from interface_icons import apply_interface_icons
    apply_interface_icons(battery_themes)
    # Exercise actual generated theme metadata: palette support is decided by
    # the selected child theme, even when the artwork comes from a base theme.
    source = tmp_path / "source" / BASE / "apps/scalable"
    source.mkdir(parents=True)
    (source / "demo.svg").write_text(
        f'<svg xmlns="{SVG}" width="64" height="64"><circle cx="32" cy="32" r="25" fill="#0000ff"/></svg>')
    from interface_icons import INTERFACE_ICONS
    for name in INTERFACE_ICONS:
        (source / (name + ".svg")).symlink_to("demo.svg")
    names = [BASE, BASE + "-dark"]
    for style in ("regular", "glass"):
        generated = tmp_path / style
        for name in installer_themes(source.parents[2], generated, style, "#007aff"):
            (battery_themes / name).symlink_to(generated / name, target_is_directory=True)
            names.append(name)
    for variant in VARIANTS:
        name = theme_name(variant)
        theme = battery_themes / name
        (theme / "apps/256").mkdir(parents=True)
        (theme / "index.theme").write_text(index_text(variant, [256]))
        names.append(name)
    build = tmp_path / "build"
    configured = subprocess.run(["cmake", "-S", str(repo / "tests/native_status_icons"), "-B", str(build)],
                                capture_output=True, text=True)
    if configured.returncode and '"KF6IconThemes"' in configured.stderr:
        pytest.skip("KF6IconThemes development SDK required")
    assert configured.returncode == 0, configured.stdout + configured.stderr
    subprocess.run(["cmake", "--build", str(build), "-j2"], check=True)
    data = tmp_path / "data"
    data.mkdir()
    (data / "icons").symlink_to(battery_themes, target_is_directory=True)
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "XDG_DATA_HOME": str(data),
           "XDG_CONFIG_HOME": str(tmp_path / "config"), "XDG_CACHE_HOME": str(tmp_path / "cache")}
    for theme in names:
        subprocess.run([str(build / "status_icon_palette"), theme, str(tmp_path / theme)],
                       env=env, check=True, timeout=90)


def test_interface_aliases_preserve_app_artwork_and_survive_reinstall(battery_themes):
    from interface_icons import INTERFACE_ICONS, apply_interface_icons
    from icon_sources import inventory
    from icon_toolset import BASE
    root = battery_themes / BASE
    application = root / "apps/scalable/gnome-power-manager.svg"
    app_before = application.read_bytes()
    apply_interface_icons(battery_themes)
    for name in INTERFACE_ICONS:
        path = root / "status/symbolic" / (name + ".svg")
        assert path.is_file()
        assert "ColorScheme-Text" in path.read_text()
        assert path.resolve().is_relative_to(battery_themes)
    assert application.read_bytes() == app_before
    before = inventory(battery_themes)
    apply_interface_icons(battery_themes)
    assert inventory(battery_themes) == before


def test_interface_aliases_reject_external_destination(tmp_path):
    from interface_icons import apply_interface_icons
    root = tmp_path / "themes/MacTahoeLiquidKde-Icons"
    (root / "status/22").mkdir(parents=True)
    (root / "status/22/camera-on.svg").write_text(f'<svg xmlns="{SVG}"/>')
    (root / "status/symbolic").mkdir()
    outside = tmp_path / "outside.svg"
    outside.write_text("preserve")
    (root / "status/symbolic/interface-camera.svg").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes staging"):
        apply_interface_icons(root.parent)
    assert outside.read_text() == "preserve"
