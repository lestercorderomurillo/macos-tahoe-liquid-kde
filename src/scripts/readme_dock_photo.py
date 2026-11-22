"""Select an actual installed icon appearance inside the README photo guest."""

import configparser
import json
import tempfile
import time
from pathlib import Path

from icon_toolset import BASE, SYSTEM_MENU_ICONS, installer_themes
from installer_choices import COLORS
from release_capture_guest import plasma, run, run_user_service, session, windows
from theme_switch import refresh_icons_live


def appearance(style, mode, profile):
    session()
    theme_root = Path.home() / ".local/share/icons"
    # The gallery demonstrates installed icon themes. The Dock's separate
    # role-artwork option deliberately overrides those themes.
    pins_by_id = {}
    for desktop_id, icon in zip(
        profile["pins"],
        (
            "system-file-manager",
            "firefox",
            "thunderbird",
            "org.kde.merkuro.calendar",
            "org.kde.marknote",
            "org.kde.gwenview",
            "elisa",
            "org.kde.haruna",
            "org.kde.discover",
            "systemsettings",
        ),
        strict=True,
    ):
        name = desktop_id.split(":")[1]
        if not (Path("/usr/share/applications") / name).is_file():
            desktop = Path.home() / ".local/share/applications" / name
            if not desktop.exists():
                desktop.parent.mkdir(parents=True, exist_ok=True)
                desktop.write_text(
                    f"[Desktop Entry]\nType=Application\nName={name}\nIcon={icon}\nExec=/usr/bin/true\n"
                )
            pins_by_id[name] = desktop.as_uri()
        else:
            pins_by_id[name] = desktop_id
    from dock_apps import CANDIDATES
    pins = [pins_by_id[desktop_id] for candidates in CANDIDATES.values()
            for desktop_id in candidates if desktop_id in pins_by_id]
    pins.insert(1, "applications:org.kde.mac-tahoe-liquid-kde.apps.desktop")
    run("kbuildsycoca6", "--noincremental")
    plasma(
        'panels().forEach(p=>p.widgets().forEach(w=>{if(w.type.endsWith(".icontasks")){w.currentConfigGroup=["General"];w.writeConfig("macOSDockIcons",false);w.writeConfig("launchers",'
        + json.dumps(pins)
        + ");}}))"
    )
    material = style if style in ("regular", "clear") else "glass"
    theme = f"{BASE}-{material.title()}-{mode.title()}"
    if material != "regular":
        cache = Path.home() / "release-capture" / ("readme-dock-icons-" + style)
        if not cache.exists():
            names = {"view-app-grid", "user-trash", "user-trash-full"}
            for app in profile["pins"]:
                filename = app.split(":")[1]
                desktop = Path("/usr/share/applications") / filename
                if not desktop.is_file():
                    desktop = Path.home() / ".local/share/applications" / filename
                parser = configparser.ConfigParser(strict=False, interpolation=None)
                if desktop.is_file():
                    parser.read(desktop)
                    names.add(parser["Desktop Entry"]["Icon"])
                names.add(filename.removesuffix(".desktop"))
            names.difference_update(SYSTEM_MENU_ICONS)
            names.add("systemsettings")
            names = [
                n
                for n in sorted(names)
                if n.startswith("user-trash")
                or any(
                    (theme_root / BASE / "apps/scalable" / (n + ext)).exists()
                    for ext in (".svg", ".png")
                )
            ]
            with tempfile.TemporaryDirectory(dir=cache.parent) as temp:
                generated = Path(temp) / "themes"
                installer_themes(
                    theme_root,
                    generated,
                    material,
                    COLORS.get(style, COLORS["blue"]),
                    icons=names,
                )
                generated.rename(cache)
        name = BASE + "-Readme-Dock-" + style + "-" + mode
        target = theme_root / name
        if not target.exists():
            target.symlink_to(cache / theme, target_is_directory=True)
        theme = name
    run(
        "kwriteconfig6",
        "--file",
        "kdeglobals",
        "--group",
        "Icons",
        "--key",
        "Theme",
        theme,
    )
    refresh_icons_live()
    run_user_service("reset-failed", "plasma-plasmashell.service")
    run_user_service("restart", "plasma-plasmashell.service")
    for _ in range(25):
        try:
            session()
            if any(w["type"] == 2 and w["geometry"]["y"] > 100 for w in windows()):
                break
        except (RuntimeError, IndexError):
            pass
        time.sleep(0.4)
    else:
        raise RuntimeError("Dock did not appear after the icon change")
    actual = run(
        "kreadconfig6", "--file", "kdeglobals", "--group", "Icons", "--key", "Theme"
    )
    if actual != theme:
        raise RuntimeError("Icon theme did not change")
    return {"macOSDockIcons": False, "icon_theme": theme, "style": style, "mode": mode}
