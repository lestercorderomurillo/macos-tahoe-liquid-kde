"""Regression tests for the embedded kconf_update config migrations.

The hand-written regex migrations (kdedefaults scrub, malformed
[Colors:*] scrub, appletsrc dock-ID rename) live in kconf_update
scripts bundled under src/offline/kconf_update/. The helpers are exercised
directly, both with an explicit target (installer contract) and argless via
$HOME (KF6 kconf_update contract, which passes no arguments).
"""

import os
import subprocess
from pathlib import Path


def _run_script(script: Path, *args: Path, env: dict | None = None) -> None:
    subprocess.run(["sh", str(script), *map(str, args)], check=True,
                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_kconf_update_assets_present(offline):
    base = offline / "kconf_update"
    for name in ("mac-tahoe-scrub-kdedefaults",
                 "mac-tahoe-scrub-colorgroups",
                 "mac-tahoe-migrate-appletsrc"):
        assert (base / (name + ".sh")).is_file(), f"missing helper {name}.sh"
        assert (base / (name + ".upd")).is_file(), f"missing {name}.upd"
        upd = (base / (name + ".upd")).read_text().splitlines()
        # KF6 kconf_update skips .upd files whose first line isn't Version=6
        # and no longer parses File= entries at all.
        assert upd[0] == "Version=6", f"{name}.upd must start with Version=6"
        assert f"Id={name}" in upd, f"{name}.upd must declare its Id"
        assert f"Script={name}.sh,sh" in upd, f"{name}.upd must call {name}.sh"
        assert not any(line.startswith("File=") for line in upd), \
            f"{name}.upd: File= is not part of the KF6 .upd format"


def test_scrub_kdedefaults_removes_mac_tahoe_values(tmp_path, offline):
    script = offline / "kconf_update/mac-tahoe-scrub-kdedefaults.sh"
    d = tmp_path / "kdedefaults"
    d.mkdir()
    (d / "kdeglobals").write_text(
        "[KDE]\nLookAndFeelPackage=MacTahoeLiquidKde-Dark\n"
        "ColorScheme=MacTahoeLiquidKdeDark\n")
    (d / "plasmarc").write_text("SomeOther=1\nTheme=MacTahoeLiquidKde-Dark\n")
    (d / "package").write_text("MacTahoeLiquidKde-Dark\n")
    for fn in ("kdeglobals", "plasmarc", "package"):
        _run_script(script, d / fn)
    kg = (d / "kdeglobals").read_text()
    assert "ColorScheme=MacTahoeLiquidKdeDark" not in kg
    # LookAndFeelPackage is outside the scrubbed key list, so it stays.
    assert "LookAndFeelPackage=MacTahoeLiquidKde-Dark" in kg
    assert "Theme=MacTahoeLiquidKde-Dark" not in (d / "plasmarc").read_text()
    assert (d / "package").read_text().strip() == "org.kde.breeze.desktop"


def test_scrub_kdedefaults_leaves_unrelated_config_alone(tmp_path, offline):
    script = offline / "kconf_update/mac-tahoe-scrub-kdedefaults.sh"
    d = tmp_path / "kdedefaults"
    d.mkdir()
    # No MacTahoe/Liquid marker: package must NOT be reset to Breeze, and
    # themes merely containing "mac" (e.g. Macchiato) must survive.
    (d / "package").write_text("org.kde.breezedark.desktop\n")
    (d / "kdeglobals").write_text(
        "[KDE]\nColorScheme=CatppuccinMacchiato\nTheme=WhiteSur\n")
    for fn in ("package", "kdeglobals"):
        _run_script(script, d / fn)
    assert (d / "package").read_text().strip() == "org.kde.breezedark.desktop"
    kg = (d / "kdeglobals").read_text()
    assert "ColorScheme=CatppuccinMacchiato" in kg
    assert "Theme=WhiteSur" in kg


def test_scrub_colorgroups_drops_malformed_header(tmp_path, offline):
    script = offline / "kconf_update/mac-tahoe-scrub-colorgroups.sh"
    f = tmp_path / "kdeglobals"
    f.write_text(
        "[Colors:View]\nBackgroundNormal=239,240,241\n"
        "[Colors:Button]\\x5d\\x5bBad]\nBackgroundNormal=0,0,0\n"
        "[Colors:Window]\nBackgroundNormal=1,1,1\n")
    _run_script(script, f)
    out = f.read_text()
    assert "[Colors:Button]" not in out
    assert "BackgroundNormal=0,0,0" not in out
    assert "[Colors:View]" in out
    assert "[Colors:Window]" in out


def test_migrate_appletsrc_renames_dock_ids(tmp_path, offline):
    script = offline / "kconf_update/mac-tahoe-migrate-appletsrc.sh"
    f = tmp_path / "appletsrc"
    f.write_text(
        "plugin=org.kde.plasma.icontasks\n"
        "plugin=org.kde.plasma.taskmanager\n"
        "plugin=org.kde.mac-tahoe-liquid-kde.icontasks\n"
        "plugin=org.kde.mac-tahoe-liquid-kde.taskmanager\n")
    _run_script(script, f)
    out = f.read_text()
    assert "org.kde.mac.tahoe.liquid.icontasks" in out
    assert "org.kde.mac.tahoe.liquid.taskmanager" in out
    assert "org.kde.plasma.icontasks" not in out
    assert "org.kde.plasma.taskmanager" not in out
    assert "org.kde.mac-tahoe-liquid-kde.icontasks" not in out
    assert "org.kde.mac-tahoe-liquid-kde.taskmanager" not in out


def test_appletsrc_migration_gated_on_plasmoids_feature(monkeypatch):
    import steps.kconf_update as kc
    monkeypatch.delenv("FEAT_PLASMOIDS", raising=False)
    assert "mac-tahoe-migrate-appletsrc.sh" in kc._enabled_scripts()
    monkeypatch.setenv("FEAT_PLASMOIDS", "false")
    assert "mac-tahoe-migrate-appletsrc.sh" not in kc._enabled_scripts()


def test_install_skips_appletsrc_when_plasmoids_disabled(tmp_path, monkeypatch):
    """--no-plasmoids must neither run the dock-ID rename nor leave its .upd
    behind for kconf_update to run it at login."""
    import steps.kconf_update as kc
    monkeypatch.setenv("FEAT_PLASMOIDS", "false")
    monkeypatch.setattr(kc, "KCONF_UPDATE_DIR", tmp_path / "kconf_update")
    monkeypatch.setattr(kc, "HOME", tmp_path)
    cfg = tmp_path / ".config"
    cfg.mkdir()
    appletsrc = cfg / "plasma-org.kde.plasma.desktop-appletsrc"
    appletsrc.write_text("plugin=org.kde.plasma.icontasks\n")
    kc.install()
    installed = tmp_path / "kconf_update"
    assert (installed / "mac-tahoe-scrub-kdedefaults.upd").is_file()
    assert not (installed / "mac-tahoe-migrate-appletsrc.sh").exists()
    assert not (installed / "mac-tahoe-migrate-appletsrc.upd").exists()
    assert appletsrc.read_text() == "plugin=org.kde.plasma.icontasks\n"


def test_helpers_self_locate_when_run_argless(tmp_path, offline):
    """KF6 kconf_update runs scripts with no arguments: each helper must find
    its live config files from $XDG_CONFIG_HOME / $HOME on its own."""
    cfg = tmp_path / ".config"
    (cfg / "kdedefaults").mkdir(parents=True)
    (cfg / "kdedefaults/package").write_text("MacTahoeLiquidKde-Dark\n")
    (cfg / "kdedefaults/plasmarc").write_text("Theme=MacTahoeLiquidKde-Dark\n")
    (cfg / "kdeglobals").write_text(
        "[Colors:Button]\\x5d\\x5bBad]\nBackgroundNormal=0,0,0\n"
        "[Colors:Window]\nBackgroundNormal=1,1,1\n")
    (cfg / "plasma-org.kde.plasma.desktop-appletsrc").write_text(
        "plugin=org.kde.plasma.icontasks\n")
    env = {k: v for k, v in os.environ.items() if k != "XDG_CONFIG_HOME"}
    env["HOME"] = str(tmp_path)
    for name in ("mac-tahoe-scrub-kdedefaults.sh",
                 "mac-tahoe-scrub-colorgroups.sh",
                 "mac-tahoe-migrate-appletsrc.sh"):
        _run_script(offline / "kconf_update" / name, env=env)
    assert (cfg / "kdedefaults/package").read_text().strip() == \
        "org.kde.breeze.desktop"
    assert "MacTahoe" not in (cfg / "kdedefaults/plasmarc").read_text()
    assert "[Colors:Button]" not in (cfg / "kdeglobals").read_text()
    assert "org.kde.mac.tahoe.liquid.icontasks" in \
        (cfg / "plasma-org.kde.plasma.desktop-appletsrc").read_text()
