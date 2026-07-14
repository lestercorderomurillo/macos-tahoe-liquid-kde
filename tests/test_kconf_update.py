"""Regression tests for the embedded kconf_update config migrations.

These cover issue #56: the hand-written regex migrations (kdedefaults scrub,
malformed [Colors:*] scrub, appletsrc dock-ID rename) moved to official
kconf_update scripts bundled under src/offline/kconf_update/. The scripts are
exercised directly so the migration logic is verified without needing the
kconf_update binary present.
"""

import subprocess
from pathlib import Path

import pytest


def _run_script(script: Path, target: Path) -> None:
    subprocess.run(["sh", str(script), str(target)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_kconf_update_assets_present(offline):
    base = offline / "kconf_update"
    for name in ("mac-tahoe-scrub-kdedefaults",
                 "mac-tahoe-scrub-colorgroups",
                 "mac-tahoe-migrate-appletsrc"):
        assert (base / (name + ".sh")).is_file(), f"missing helper {name}.sh"
        assert (base / (name + ".upd")).is_file(), f"missing {name}.upd"
        upd = (base / (name + ".upd")).read_text()
        assert f"Id={name}" in upd, f"{name}.upd must declare its Id"
        assert f"Script={name}.sh" in upd, f"{name}.upd must call {name}.sh"


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
