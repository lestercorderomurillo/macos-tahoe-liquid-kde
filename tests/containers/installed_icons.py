"""Install the shipped icon component in a disposable home and load it with Qt."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def check_archive_inventory(root, archive):
    listing = subprocess.check_output(["tar", "--zstd", "-tf", str(archive)], text=True)
    members = [Path(line) for line in listing.splitlines()]
    assets = [member for member in members if member.suffix.lower() in (".svg", ".png", ".xpm")]
    if not assets:
        raise RuntimeError("The archive has no icon artwork")
    missing = [member for member in assets if not (root / member).is_file()]
    if missing:
        raise RuntimeError(f"{len(missing)} archive icons missing from installation: {missing[:10]}")


DOCK_ICONS = ("view-app-grid", "file-manager", "firefox", "internet-mail", "org.kde.merkuro.calendar",
              "tomboy", "shotwell", "gnome-music", "smplayer", "org.kde.discover", "systemsettings")
TRASH_ICONS = ("user-trash", "user-trash-full")


def check_installed(root, dock_plugin, materials):
    from PyQt6.QtGui import QGuiApplication, QIcon
    from interface_icons import APPLICATION_ALIASES, INTERFACE_ICONS
    from icon_toolset import BASE

    app = QGuiApplication([])
    if dock_plugin is not None:
        check_dock_resources(dock_plugin)
    QIcon.setThemeSearchPaths([str(root)])
    QIcon.setFallbackSearchPaths([])
    QIcon.setFallbackThemeName("")
    decoded = set()
    names = {"folder-open", *DOCK_ICONS, *TRASH_ICONS, *INTERFACE_ICONS}
    names.update(Path(alias).stem for alias in APPLICATION_ALIASES)
    failures = []
    for theme in (BASE, BASE + "-dark"):
        directory = root / theme
        if not (directory / "index.theme").is_file():
            raise RuntimeError(f"Missing installed theme {theme}")
        QIcon.setThemeName(theme)
        for path in directory.rglob("*"):
            if path.suffix.lower() not in (".svg", ".png", ".xpm"):
                continue
            target = path.resolve(strict=True)
            if not target.is_relative_to(root):
                raise RuntimeError(f"Icon points outside installed theme: {path}")
            names.add(path.stem)
            if target not in decoded:
                decoded.add(target)
                if QIcon(str(target)).pixmap(32, 32).isNull():
                    failures.append(f"decode {path.relative_to(root)}")
        for name in sorted(names):
            if not QIcon.hasThemeIcon(name) or QIcon.fromTheme(name).pixmap(32, 32).isNull():
                failures.append(f"lookup {theme}/{name}")
        print(f"{theme}: checked {len(names)} icon names", flush=True)
    print(f"Decoded {len(decoded)} distinct icon files with Qt {app.platformName()}")
    if failures:
        raise RuntimeError(f"{len(failures)} icon failures: " + ", ".join(failures[:50]))

    if materials:
        check_dock_materials(root)


def check_dock_materials(root):
    from PyQt6.QtGui import QIcon
    from icon_toolset import installer_themes

    with tempfile.TemporaryDirectory() as temp:
        for style, tint in (("regular", "#007aff"), ("dark", "#007aff"),
                            ("clear", "#007aff"), ("glass", "#ff3b30"), ("glass", "#007aff")):
            output = Path(temp) / (style + tint)
            selected = list(DOCK_ICONS)
            if style in ("clear", "glass"):
                selected.extend(TRASH_ICONS)
            themes = installer_themes(root, output, style, tint, icons=selected)
            QIcon.setThemeSearchPaths([str(output), str(root)])
            for theme in themes:
                QIcon.setThemeName(theme)
                for name in selected:
                    file = output / theme / "apps/256" / (name + ".png")
                    source = QIcon(str(file)).pixmap(48, 48)
                    actual = QIcon.fromTheme(name).pixmap(48, 48)
                    if source.isNull() or actual.toImage() != source.toImage():
                        raise RuntimeError(f"{theme}/{name} does not render its generated artwork")
            print(f"Verified Dock material {style} {tint} in both modes", flush=True)


def check_dock_resources(plugin):
    from PyQt6.QtCore import QFile, QIODevice, QPluginLoader
    from PyQt6.QtGui import QIcon
    from dock_apps import CANDIDATES

    loader = QPluginLoader(str(plugin.resolve(strict=True)))
    if not loader.load():
        raise RuntimeError(f"Cannot load built Dock plugin: {loader.errorString()}")
    prefix = ":/qt/qml/plasma/applet/org/kde/mac/tahoe/liquid/taskmanager/icons"
    artwork = (Path(__file__).resolve().parents[2] / "src/offline/plasmoids"
               / "org.kde.mac.tahoe.liquid.taskmanager/contents/icons")
    for mode in ("light", "dark"):
        for role in CANDIDATES:
            name = f"{mode}/{role}.svg"
            resource = QFile(f"{prefix}/{name}")
            if not resource.open(QIODevice.OpenModeFlag.ReadOnly):
                raise RuntimeError(f"Missing embedded Dock resource {name}")
            if bytes(resource.readAll()) != (artwork / name).read_bytes():
                raise RuntimeError(f"Wrong artwork embedded for {name}")
            if QIcon(resource.fileName()).pixmap(48, 48).isNull():
                raise RuntimeError(f"Could not render embedded Dock icon {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme-root", type=Path, help="Check themes already installed here")
    parser.add_argument("--archive", type=Path, help="Compare installed files with the source archive")
    parser.add_argument("--dock-plugin", type=Path, help="Load the matrix-built Dock module")
    parser.add_argument("--materials", action="store_true", help="Render the generated Dock appearances")
    args = parser.parse_args()
    if args.theme_root:
        root = args.theme_root.resolve(strict=True)
        if args.archive:
            check_archive_inventory(root, args.archive)
        check_installed(root, args.dock_plugin, args.materials)
        return
    with tempfile.TemporaryDirectory(prefix="installed-icons-") as home:
        progress = Path(home) / "progress"
        progress.touch(mode=0o600)
        env = {
            "PATH": os.environ["PATH"], "HOME": home, "TMPDIR": home,
            "QT_QPA_PLATFORM": "offscreen", "QT_QPA_PLATFORMTHEME": "generic",
            "XDG_DATA_DIRS": home, "XDG_CONFIG_DIRS": home,
            "MTTKDE_PROGRESS_FILE": str(progress),
            "XDG_RUNTIME_DIR": home, "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src/scripts"),
        }
        subprocess.run([sys.executable, "-c",
                        "from steps import icons; from log import errors; "
                        "icons.install(); raise SystemExit(bool(errors))"], check=True, env=env)
        command = [sys.executable, __file__, "--theme-root", str(Path(home) / ".local/share/icons")]
        archive = Path(__file__).resolve().parents[2] / "src/offline/icons/MacTahoeLiquidKde-Icons.tar.zst"
        command.extend(["--archive", str(archive)])
        if args.materials:
            command.append("--materials")
        if args.dock_plugin:
            command.extend(["--dock-plugin", str(args.dock_plugin.resolve(strict=True))])
        subprocess.run(command, check=True, env=env)


if __name__ == "__main__":
    main()
