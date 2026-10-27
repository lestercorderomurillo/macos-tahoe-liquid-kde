"""Pin integrity and build-time asset assembly for the declarative path (#86)."""
import json
import re
import shutil
import subprocess
import sys

import pytest


def test_nix_inputs_are_locked_and_share_nixpkgs(repo):
    nodes = json.loads((repo / "flake.lock").read_text())["nodes"]
    for name in ("nixpkgs", "home-manager"):
        assert re.fullmatch(r"[0-9a-f]{40}", nodes[name]["locked"]["rev"])
        assert nodes[name]["locked"]["narHash"].startswith("sha256-")
    assert nodes["home-manager"]["inputs"]["nixpkgs"] == ["nixpkgs"]
    assert "plasma-manager" not in nodes  # supplied only by consumers who want panels


@pytest.mark.parametrize("edition", ["MacTahoe", "MacGoldenGate"])
def test_nix_asset_assembly_matches_runtime_theme_names(repo, tmp_path, monkeypatch, edition, sandbox):
    import glass_surfaces
    from steps import plasma_theme, kvantum

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("glass_surfaces.py", "theme_switch.py", "launcher_defaults.py", "localization.py", "window_controls.py"):
        shutil.copy2(repo / "src/scripts" / name, scripts / name)
    shutil.copytree(repo / "src/scripts/locales", scripts / "locales")
    (scripts / "defaults.json").write_text(json.dumps({"wallpaper": edition, "launcher_preset": 1}))
    monkeypatch.setenv("PYTHONPATH", str(scripts))
    subprocess.run([sys.executable, str(repo / "nix/install-assets.py"),
                    str(repo / "src/offline"), str(tmp_path)], check=True)
    share = tmp_path / "share"
    for mode in ("Light", "Dark"):
        name = f"MacTahoeLiquidKde-{mode}"
        for prefix in ("MacTahoe", "MacGoldenGate"):
            decoration = f"{prefix}LiquidKde-{mode}"
            assert (share / "aurorae/themes" / decoration / f"{decoration}rc").is_file()
        assert (share / "plasma/look-and-feel" /
                f"org.kde.mac-tahoe-liquid-kde.{mode.lower()}" / "metadata.json").is_file()
        defaults = (share / "plasma/look-and-feel" /
                    f"org.kde.mac-tahoe-liquid-kde.{mode.lower()}" / "contents/defaults").read_text()
        assert f"theme=__aurorae__svg__{edition}LiquidKde-{mode}" in defaults
        gtk_css = (share / "themes" / name / "gtk-3.0/gtk.css").read_text()
        assert ('windows-assets/golden-gate-close-' in gtk_css) == (edition == "MacGoldenGate")
        assert (share / "themes" / name / "gtk-3.0/gtk.css").is_file()
        assert not list(share.rglob("*-ReducedTransparency"))
    assert not (share / "fonts").exists()
    assert not (share / "wallpapers").exists()
    assert not (share / "sounds").exists()
    launcher = share / "plasma/plasmoids/org.kde.mac-tahoe-liquid-kde.launcher"
    golden_gate = str(edition == "MacGoldenGate").lower()
    assert f"readonly property bool goldenGateEdition: {golden_gate}" in (
        launcher / "contents/ui/MainView.qml").read_text()
    # Both installation routes must ship identical edition surfaces, including
    # after reinstalling over the opposite edition's client fills.
    installed = tmp_path / "installed"
    monkeypatch.setattr(glass_surfaces, "default_wallpaper", lambda: edition)
    monkeypatch.setattr(plasma_theme, "DEST_DIR", installed / "plasma")
    monkeypatch.setattr(kvantum, "DEST_DIR", installed / "kvantum/light")
    monkeypatch.setattr(kvantum, "DEST_DIR_DARK", installed / "kvantum/dark")
    for current in ("MacGoldenGate" if edition == "MacTahoe" else "MacTahoe", edition):
        monkeypatch.setattr(glass_surfaces, "default_wallpaper", lambda: current)
        plasma_theme.install()
        for name in kvantum._THEMES:
            kvantum._install_one(name)
    for mode in ("Light", "Dark"):
        name = "MacTahoeLiquidKde-" + mode
        for surface in glass_surfaces.PLASMA_SURFACES:
            assert (installed / "plasma" / name / surface).read_bytes() == (
                share / "plasma/desktoptheme" / name / surface).read_bytes()
    for mode, name in zip(("light", "dark"), kvantum._THEMES):
        assert (installed / "kvantum" / mode / (name + ".svg")).read_bytes() == (
            share / "Kvantum" / name / (name + ".svg")).read_bytes()
