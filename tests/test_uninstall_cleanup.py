# USELESS: text content of kdedefaults/plasmarc/kwinrc — live Plasma session reset behavior is not validated
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

from .conftest import has_command, make_live_shim_dir


pytestmark = pytest.mark.skipif(
    not has_command("kwriteconfig6"),
    reason="kwriteconfig6 not available",
)


@pytest.fixture
def live_shim(tmp_path):
    """Shim dir for live-session binaries — see conftest.LIVE_SHIM_BINARIES."""
    return make_live_shim_dir(tmp_path)


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


def _run_step_uninstall(step: str, sandbox: Path, repo: Path,
                        shim_dir: Path | None = None) -> None:
    env = {**os.environ, "HOME": str(sandbox),
           "XDG_CONFIG_HOME": str(sandbox / ".config"),
           "XDG_DATA_HOME": str(sandbox / ".local/share"),
           "MAC_TAHOE_SKIP_LIVE_APPLY": "true"}
    if shim_dir is not None:
        # Prepend the shim dir so subprocesses spawned by the step (notably
        # ``apply.uninstall`` invoking ``plasma-apply-wallpaperimage`` to
        # revert the desktop wallpaper to ``/usr/share/wallpapers/Next``)
        # hit our no-op shims instead of the maintainer's live plasmashell.
        # MAC_TAHOE_SKIP_LIVE_APPLY only gates theme_switch's live-tool path
        # — apply.py's WALLPAPERS reset is not behind that flag.
        env["PATH"] = f"{shim_dir}{os.pathsep}{env.get('PATH', '')}"
    rc = subprocess.run(
        ["python3", "-c",
         f"from steps.{step} import uninstall; uninstall()"],
        check=False, env=env, cwd=str(repo / "src/scripts"),
    ).returncode
    assert rc == 0


def test_apply_uninstall_cleans_kdedefaults(sandbox, repo, live_shim):
    _seed_residue(sandbox)
    _run_step_uninstall("apply", sandbox, repo, shim_dir=live_shim)

    cfg = sandbox / ".config"
    pattern = re.compile(r"MacTahoe|mac-tahoe|liquid", re.IGNORECASE)

    # LookAndFeelPackage no longer points at our LAF.
    assert "mac-tahoe-liquid" not in (cfg / "kdeglobals").read_text()

    assert "mac-tahoe-liquid" not in (cfg / "kdedefaults/package").read_text()
    for fn in ("kdeglobals", "plasmarc", "kcminputrc", "kwinrc", "ksplashrc"):
        text = (cfg / "kdedefaults" / fn).read_text()
        assert not pattern.search(text), f"{fn} still references our theme"

    assert "[Theme-plasmathemeexplorer]" not in (cfg / "plasmarc").read_text()


def test_acrylic_glass_uninstall_strips_group(sandbox, repo, live_shim):
    _seed_residue(sandbox)
    _run_step_uninstall("acrylic_glass", sandbox, repo, shim_dir=live_shim)
    assert "[Effect-liquidglass]" not in (sandbox / ".config/kwinrc").read_text()


def test_portals_uninstall_removes_conf(sandbox, repo, live_shim):
    portal_dir = sandbox / ".config/xdg-desktop-portal"
    portal_dir.mkdir(parents=True, exist_ok=True)
    (portal_dir / "kde-portals.conf").write_text(
        "[preferred]\norg.freedesktop.impl.portal.Settings=gtk\n"
    )
    _run_step_uninstall("portals", sandbox, repo, shim_dir=live_shim)
    assert not (portal_dir / "kde-portals.conf").exists()
