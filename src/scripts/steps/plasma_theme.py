from localization import tr
import json
import re
import shutil
import subprocess

from glass_surfaces import apply_plasma_surface_defaults

from steps._helpers import (
    DATA_HOME, HOME, fail, info, install_tree, kw_write, offline, remove_tree, temp_dir, warn,
)

DEST_DIR = DATA_HOME / "plasma/desktoptheme"
LEGACY = ("MacTahoe-Dark", "MacTahoe-Light")
VARIANTS = ("MacTahoeLiquidKde-Dark", "MacTahoeLiquidKde-Light")

# Menu bar colours that follow the wallpaper (#146). Each "-WallpaperBar"
# variant is the other appearance's style and colours under a name that keeps
# this appearance's word, so the light/dark switcher never reads it as an
# appearance change. menubar_contrast.py picks the plain style or the variant.
WALLPAPER_SUFFIX = "-WallpaperBar"
WALLPAPER_SOURCES = {"MacTahoeLiquidKde-Light": ("MacTahoeLiquidKde-Dark", "MacTahoeLiquidKdeDark.colors"),
                     "MacTahoeLiquidKde-Dark": ("MacTahoeLiquidKde-Light", "MacTahoeLiquidKdeLight.colors")}
MENUBAR_BIN = HOME / ".local/bin/mac-tahoe-menubar-contrast"
MENUBAR_UNITS = ("mac-tahoe-liquid-kde-menubar.service", "mac-tahoe-liquid-kde-menubar.timer",
                 "mac-tahoe-liquid-kde-menubar.path")
SYSTEMD_USER = HOME / ".config/systemd/user"


def _wallpaper_variant(staging, name: str) -> "Path | None":
    """Build ``<name>-WallpaperBar`` from the other style and its colours."""
    look, colors = WALLPAPER_SOURCES[name]
    styled = staging / look
    if not styled.is_dir():
        return None
    target = staging / (name + WALLPAPER_SUFFIX)
    shutil.copytree(styled, target)
    shutil.copyfile(offline("color-schemes", colors), target / "colors")
    variant = name + WALLPAPER_SUFFIX
    meta = target / "metadata.json"
    data = json.loads(meta.read_text(encoding="utf-8"))
    plugin = data["KPlugin"]
    for key in [k for k in plugin if k.startswith(("Name", "Description"))]:
        del plugin[key]
    plugin.update(Id=variant, Name=variant,
                  Description="Menu bar colours for a wallpaper of the other brightness")
    meta.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    desktop = target / "metadata.desktop"
    if desktop.is_file():
        text = re.sub(r"(?m)^Name(\[[^]]*\])?=.*\n", "", desktop.read_text(encoding="utf-8"))
        text = re.sub(r"(?m)^X-KDE-PluginInfo-Name=.*$", "X-KDE-PluginInfo-Name=" + variant, text)
        desktop.write_text(text.replace("[Desktop Entry]\n", f"[Desktop Entry]\nName={variant}\n", 1), encoding="utf-8")
    return target


def _user_manager(*args: str) -> bool:
    from distro import user_service_manager_command
    from utils import run_user
    command = user_service_manager_command(*args)
    if command is None:
        return False
    try:
        return run_user(command, check=False, timeout=10, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _install_menubar_contrast() -> None:
    from paths import REPO_ROOT
    from localization_bundle import standalone_source
    from steps._scheduler import cron_command, install_periodic, is_systemd
    source = REPO_ROOT / "src/scripts/menubar_contrast.py"
    MENUBAR_BIN.parent.mkdir(parents=True, exist_ok=True)
    MENUBAR_BIN.write_text(standalone_source(source.read_text(encoding="utf-8")), encoding="utf-8")
    MENUBAR_BIN.chmod(0o755)
    if is_systemd():
        SYSTEMD_USER.mkdir(parents=True, exist_ok=True)
        for unit in MENUBAR_UNITS:
            shutil.copyfile(offline(unit), SYSTEMD_USER / unit)
        _user_manager("daemon-reload")
        if not (_user_manager("enable", "--now", MENUBAR_UNITS[1])
                and _user_manager("enable", "--now", MENUBAR_UNITS[2])):
            warn(tr("Menu bar colours will not follow the wallpaper: the user timer could not be enabled"))
    elif not install_periodic("menubar", 1, cron_command(MENUBAR_BIN)):
        warn(tr("Menu bar colours will not follow the wallpaper: the user timer could not be enabled"))


def _uninstall_menubar_contrast() -> None:
    from steps._scheduler import is_systemd, remove_periodic
    if is_systemd():
        for unit in MENUBAR_UNITS[1:]:
            _user_manager("disable", "--now", unit)
        for unit in MENUBAR_UNITS:
            (SYSTEMD_USER / unit).unlink(missing_ok=True)
        _user_manager("daemon-reload")
    else:
        remove_periodic("menubar")
    MENUBAR_BIN.unlink(missing_ok=True)

def install() -> None:
    src = offline("plasma-theme")
    if not src.is_dir():
        fail(tr('Plasma theme source not found at {src}', src=src))
        return
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # Purge legacy names from pre-0.6.2 installs.
    for stale in LEGACY:
        shutil.rmtree(DEST_DIR / stale, ignore_errors=True)

    n = 0
    with temp_dir("plasma-surfaces-") as staging:
        for v in VARIANTS:
            if not (src / v).is_dir():
                continue
            source = staging / v
            shutil.copytree(src / v, source)
            apply_plasma_surface_defaults(source)
            from theme_accent import apply as apply_accent
            apply_accent(source)
        for v in VARIANTS:
            source = staging / v
            if source.is_dir() and install_tree(source, DEST_DIR / v, v):
                n += 1
        for v in VARIANTS:
            variant = _wallpaper_variant(staging, v)
            if variant is not None:
                install_tree(variant, DEST_DIR / variant.name, variant.name)
    info(tr('{n} Plasma themes installed/reinstalled', n=n))
    _install_menubar_contrast()


def uninstall() -> None:
    _uninstall_menubar_contrast()
    n = 0
    for v in VARIANTS:
        remove_tree(DEST_DIR / (v + WALLPAPER_SUFFIX))
        remove_tree(DEST_DIR / (v + "-ReducedTransparency"))
        if remove_tree(DEST_DIR / v, v):
            n += 1
    if not kw_write("--file", "plasmarc", "--group", "Theme",
                    "--key", "name", "default"):
        warn(tr("Active Plasma theme not reset to 'default' — kwriteconfig6 unavailable. Files are removed but Plasma will still try to load MacTahoeLiquidKde until you set plasmarc:Theme.name=default manually."))
    info(tr('{n} Plasma themes removed', n=n))
