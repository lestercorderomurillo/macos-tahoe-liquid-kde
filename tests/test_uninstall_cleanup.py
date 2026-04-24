"""Uninstall fully resets KDE state — kdedefaults, plasmarc, kwinrc.

Guards the "half-uninstall" bug: kdedefaults/, plasmarc's
[Theme-plasmathemeexplorer], and kwinrc's [Effect-liquidglass] used to
keep mac/tahoe/liquid references after uninstall, so Plasma re-applied
our theme via the look-and-feel "defaults" layer on next login.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from .conftest import has_command


pytestmark = pytest.mark.skipif(
    not has_command("kwriteconfig6"),
    reason="kwriteconfig6 not available",
)


def _seed_residue(sandbox: Path) -> None:
    cfg = sandbox / ".config"
    (cfg / "kdedefaults").mkdir(parents=True, exist_ok=True)
    (cfg / "kdeglobals").write_text(
        "[General]\n"
        "ColorScheme=MacTahoeLiquidKdeDark\n"
        "\n"
        "[KDE]\n"
        "LookAndFeelPackage=org.kde.mac-tahoe-liquid-kde.dark\n"
        "widgetStyle=kvantum-dark\n"
    )
    (cfg / "kdedefaults/kdeglobals").write_text(
        "[General]\nColorScheme=MacTahoeLiquidKdeDark\n"
        "\n[Icons]\nTheme=MacTahoeLiquidKde-Icons-dark\n"
    )
    (cfg / "kdedefaults/plasmarc").write_text(
        "[Theme]\nname=MacTahoeLiquidKde-Dark\n"
    )
    (cfg / "kdedefaults/kcminputrc").write_text(
        "[Mouse]\ncursorTheme=MacTahoeLiquidKde-Dark\n"
    )
    (cfg / "kdedefaults/kwinrc").write_text(
        "[org.kde.kdecoration2]\n"
        "library=org.kde.kwin.aurorae\n"
        "theme=__aurorae__svg__MacTahoeLiquidKde-Dark\n"
    )
    (cfg / "kdedefaults/ksplashrc").write_text(
        "[KSplash]\nTheme=org.kde.mac-tahoe-liquid-kde.dark\n"
    )
    (cfg / "kdedefaults/package").write_text("org.kde.mac-tahoe-liquid-kde.dark\n")
    (cfg / "plasmarc").write_text(
        "[Theme]\nname=default\n\n"
        "[Theme-plasmathemeexplorer]\nname=MacTahoeLiquidKde-Dark\n\n"
        "[Wallpapers]\nusersWallpapers=/tmp/x\n"
    )
    (cfg / "kwinrc").write_text(
        "[Effect-liquidglass]\n"
        "liquidglassEnabled=false\n"
        "macsimize6Enabled=false\n\n"
        "[Plugins]\nliquidglassEnabled=true\n"
    )


def _run_step_uninstall(step: str, sandbox: Path, repo: Path) -> None:
    env = {**os.environ, "HOME": str(sandbox),
           "XDG_CONFIG_HOME": str(sandbox / ".config"),
           "XDG_DATA_HOME": str(sandbox / ".local/share")}
    rc = subprocess.run(
        ["python3", "-c",
         f"from installer.steps.{step} import uninstall; uninstall()"],
        check=False, env=env, cwd=str(repo / "src/scripts"),
    ).returncode
    assert rc == 0


def test_apply_uninstall_cleans_kdedefaults(sandbox, repo):
    _seed_residue(sandbox)
    _run_step_uninstall("apply", sandbox, repo)

    cfg = sandbox / ".config"
    pattern = re.compile(r"MacTahoe|mac-tahoe|liquid", re.IGNORECASE)

    # LookAndFeelPackage no longer points at our LAF.
    assert "mac-tahoe-liquid" not in (cfg / "kdeglobals").read_text()

    assert "mac-tahoe-liquid" not in (cfg / "kdedefaults/package").read_text()
    for fn in ("kdeglobals", "plasmarc", "kcminputrc", "kwinrc", "ksplashrc"):
        text = (cfg / "kdedefaults" / fn).read_text()
        assert not pattern.search(text), f"{fn} still references our theme"

    assert "[Theme-plasmathemeexplorer]" not in (cfg / "plasmarc").read_text()


def test_acrylic_glass_uninstall_strips_group(sandbox, repo):
    _seed_residue(sandbox)
    _run_step_uninstall("acrylic_glass", sandbox, repo)
    assert "[Effect-liquidglass]" not in (sandbox / ".config/kwinrc").read_text()


def test_portals_uninstall_removes_conf(sandbox, repo):
    portal_dir = sandbox / ".config/xdg-desktop-portal"
    portal_dir.mkdir(parents=True, exist_ok=True)
    (portal_dir / "kde-portals.conf").write_text(
        "[preferred]\norg.freedesktop.impl.portal.Settings=gtk\n"
    )
    _run_step_uninstall("portals", sandbox, repo)
    assert not (portal_dir / "kde-portals.conf").exists()
