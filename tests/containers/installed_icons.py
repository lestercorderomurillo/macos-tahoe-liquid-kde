"""Install the shipped icon component in a disposable home and load it with Qt."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def check_installed(root):
    from PyQt6.QtGui import QGuiApplication, QIcon
    from interface_icons import APPLICATION_ALIASES, INTERFACE_ICONS
    from icon_toolset import BASE

    app = QGuiApplication([])
    QIcon.setThemeSearchPaths([str(root)])
    QIcon.setFallbackSearchPaths([])
    QIcon.setFallbackThemeName("")
    decoded = set()
    names = {"view-app-grid", "user-trash", "user-trash-full", "folder-open", *INTERFACE_ICONS}
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme-root", type=Path, help="Check themes already installed here")
    args = parser.parse_args()
    if args.theme_root:
        check_installed(args.theme_root.resolve(strict=True))
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
        subprocess.run([sys.executable, __file__, "--theme-root",
                        str(Path(home) / ".local/share/icons")], check=True, env=env)


if __name__ == "__main__":
    main()
