"""Guest-only actions for repeatable README photographs."""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path.home() / "release-capture"
REPO = ROOT / "source"
sys.path.insert(0, str(REPO / "src/scripts"))
from release_capture_guest import arrange, launch, plasma, run, session, windows
from release_screenshots import EDITIONS


def scene(action, edition, *args):
    session()
    profile = json.loads((ROOT / "release_capture_profile.json").read_text())
    if action == "clock":
        run("sudo", "date", "--set", profile["clock"])
        return {}
    documents = Path.home() / "Documents"
    documents.mkdir(exist_ok=True)
    note = documents / "Field Notes.txt"
    if not note.exists():
        note.write_text(
            "Field Notes\n\nCoastal walk\n\nPacific overlook\nCypress grove\nEvening light\n"
        )
    wallpaper = json.loads(
        plasma(
            'print(JSON.stringify(desktops().map(d=>{d.currentConfigGroup=["Wallpaper","org.kde.image","General"];return d.readConfig("Image");})))'
        )
    )
    expected = (Path.home() / ".local/share/wallpapers" / EDITIONS[edition][0]).as_uri()
    if len(wallpaper) != 1 or not (
        wallpaper[0] == expected or wallpaper[0].startswith(expected + "/")
    ):
        raise RuntimeError(f"Unexpected desktop wallpaper: {wallpaper}")
    if action == "editor":
        run(
            "systemd-run",
            "--user",
            "--collect",
            "--setenv=WAYLAND_DISPLAY=" + os.environ["WAYLAND_DISPLAY"],
            "kate",
            "--new",
            str(note),
        )
        for _ in range(40):
            matches = [
                w for w in windows() if w["type"] == 0 and note.name in w["caption"]
            ]
            if len(matches) == 1:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("Field Notes editor did not appear")
        arrange(
            {matches[0]["caption"]: {"x": 390, "y": 185, "width": 980, "height": 620}}
        )
    elif action == "finder":
        accent = args[0]
        from contextlib import redirect_stdout

        from installer_choices import COLORS, defaults
        from steps import gtk

        mode = args[1]
        os.environ["MTTKDE_WIZARD_OPTIONS"] = json.dumps(
            defaults() | {"color": accent, "appearance": mode}
        )
        with redirect_stdout(sys.stderr):
            gtk.install()
            run(
                str(Path.home() / ".local/bin/mac-tahoe-theme-switch"),
                mode,
                timeout=180,
            )
        if (
            "accent-color"
            in run("gsettings", "list-keys", "org.gnome.desktop.interface").splitlines()
        ):
            run(
                "gsettings",
                "set",
                "org.gnome.desktop.interface",
                "accent-color",
                accent,
            )
        for name in ("Fieldwork", "Photographs", "Sketches"):
            (documents / name).mkdir(exist_ok=True)
        launch(REPO, "finder")
        arrange({"Documents": {"x": 450, "y": 185, "width": 1000, "height": 620}})
        return {"accent": accent, "color": COLORS[accent]}
    elif action == "dock":
        from contextlib import redirect_stdout

        from readme_dock_photo import appearance

        with redirect_stdout(sys.stderr):
            return appearance(
                args[0],
                args[1],
                json.loads((ROOT / "release_capture_profile.json").read_text()),
            )
    elif action == "clipboard":
        run(
            "qdbus6",
            "org.kde.klipper",
            "/klipper",
            "org.kde.klipper.klipper.setClipboardContents",
            "Field Notes · Coastal walk",
        )
    elif action == "notify-group":
        for name in ("Coastal walk", "Cypress grove", "Pacific overlook"):
            run(
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.freedesktop.Notifications",
                "--object-path",
                "/org/freedesktop/Notifications",
                "--method",
                "org.freedesktop.Notifications.Notify",
                "Files",
                "0",
                "system-file-manager",
                "Field Notes",
                name,
                "[]",
                "{'desktop-entry': <'org.kde.dolphin'>}",
                "2000",
            )
        time.sleep(7)
    elif action == "notify":
        run(
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.freedesktop.Notifications",
            "--object-path",
            "/org/freedesktop/Notifications",
            "--method",
            "org.freedesktop.Notifications.Notify",
            "Files",
            "0",
            "system-file-manager",
            "Field Notes",
            "Saved to Documents",
            "[]",
            "{'desktop-entry': <'org.kde.dolphin'>}",
            "3500",
        )
        time.sleep(4)
    elif action == "snapshot":

        def visible(rows):
            return [
                (w["id"], w["geometry"])
                for w in rows
                if not w["hidden"] and w["type"] not in (5,)
            ]

        for attempt in range(3):
            before = windows()
            run("spectacle", "-b", "-n", "-f", "-o", str(ROOT / "readme.png"))
            if visible(before) == visible(windows()):
                return {"windows": before, "wallpaper_uri": wallpaper[0]}
            time.sleep(0.4)
        raise RuntimeError("Window geometry changed during exposure")
    return {}


if __name__ == "__main__":
    print(json.dumps(scene(*sys.argv[1:])))
