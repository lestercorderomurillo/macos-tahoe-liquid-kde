import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from paths import (
    CONFIG_FILE,
    LEGACY_STEPS_DIR,
    OFFLINE_DIR,
    REPO_ROOT,
    SRC_DIR,
    STEPS_DIR,
    read_version,
)
from log import banner, errors, fail, note, ok, step, warn
from state import RunTracker
from step_runner import run_phase, step_deps, step_exists, step_has_phase
from utils import auto_dep, have, kw_read


ALL_FEATURES = [
    "wallpapers", "fonts", "cursors", "plasma_theme", "window_decorations",
    "kvantum", "color_schemes", "icons", "plasmoids", "acrylic_glass",
    "global_theme", "layout", "sounds", "gtk", "sddm", "apps", "nautilus",
    "portals", "no_download",
]

# Walk order for the install/uninstall loop. ``layout`` is iterated here for
# completeness but skipped during the loop — it runs after the apply step so
# it sees the new panel/dock packages already on disk.
INSTALL_ORDER = [
    "wallpapers", "fonts", "cursors", "icons", "plasma_theme",
    "window_decorations", "kvantum", "color_schemes", "gtk",
    "plasmoids", "globalmenu", "acrylic_glass", "global_theme",
    "layout", "nautilus", "portals",
]

FEATURE_DESC = {
    "wallpapers": "macOS wallpaper collection",
    "fonts": "SF Pro and SF Mono typefaces",
    "cursors": "macOS-style cursors",
    "plasma_theme": "Plasma desktop theme (light and dark)",
    "window_decorations": "macOS-style Aurorae window decorations",
    "kvantum": "Kvantum Qt widget style theme",
    "color_schemes": "Color schemes (light and dark)",
    "icons": "macOS-style icon set",
    "plasmoids": "Custom Plasma widgets",
    "globalmenu": "Global Menu C++ applet",
    "acrylic_glass": "Acrylic Glass KWin blur effect",
    "global_theme": "Plasma global theme (look-and-feel)",
    "layout": "Panel layout (top bar + dock)",
    "sounds": "Notification and event sounds",
    "gtk": "GTK 2/3/4 theme",
    "sddm": "Login screen theme",
    "apps": "App configuration tweaks",
    "nautilus": "Nautilus file manager (default on KDE)",
    "portals": "Route FileChooser / AppChooser to KDE (fixes stale dialog colors)",
}

INSTALL_HELP = """\
Usage: ./install [OPTIONS]

Options:
  --help, -h           Show this help message and exit

  Theme mode:
    --light            Force light theme
    --dark             Force dark theme
    --auto             Automatic switching via sunrise/sunset (default)

  Feature flags (prefix with --no- to disable):
    --only             Disable all features first, then enable only those listed
    --wallpapers       macOS wallpaper collection
    --fonts            SF Pro and SF Mono typefaces
    --cursors          macOS-style cursors
    --plasma-theme     Translucent panels and dock
    --window-decorations  Aurorae window title bars
    --kvantum          Kvantum Qt widget style
    --color-schemes    Light and Dark palettes
    --icons            macOS-style icon set
    --plasmoids        Custom Plasma widgets (Menu, Launcher, Trashcan)
    --acrylic-glass    KWin blur + rounded corners effect
    --global-theme     Plasma global theme (look-and-feel package)
    --layout           Panel layout (top bar + dock)
    --sounds           Notification and event sounds
    --gtk              GTK 2/3/4 theme
    --sddm             Login screen theme
    --apps             App configuration tweaks
    --nautilus         Install Nautilus and set as default file manager
    --portals          Route FileChooser/AppChooser to KDE (fixes stale dialogs)
    --no-download      Skip downloads, use cached assets

  Persistence:
    --save             Save current flags to features.json
    --reset            Reset features.json to all-true defaults

Examples:
  ./install                              # install everything
  ./install --no-gtk --no-sddm           # skip GTK and SDDM
  ./install --only --fonts --icons       # install only fonts and icons
  ./install --dark --save                # dark mode, remember setting
  ./install --reset                      # restore defaults
"""

UNINSTALL_HELP = """\
Usage: ./uninstall [OPTIONS]

Options:
  --help, -h           Show this help message and exit

  Feature flags (prefix with --no- to skip):
    --only             Disable all features first, then enable only those listed
    --wallpapers       Remove wallpaper collection
    --fonts            Remove SF Pro and SF Mono fonts
    --cursors          Remove macOS-style cursors
    --plasma-theme     Remove Plasma desktop theme
    --window-decorations  Remove Aurorae window decorations
    --kvantum          Remove Kvantum theme
    --color-schemes    Remove color schemes
    --icons            Remove icon themes
    --plasmoids        Remove custom Plasma widgets
    --acrylic-glass    Remove KWin blur effect
    --global-theme     Remove Plasma global theme
    --layout           Reset panel layout to default
    --sounds           Remove notification sounds
    --gtk              Remove GTK theme
    --sddm             Remove login screen theme
    --apps             Reset app configuration

Examples:
  ./uninstall                       # uninstall everything
  ./uninstall --icons --cursors     # only remove icons and cursors
"""


DEFAULT_FEATURES: dict[str, object] = {f: True for f in ALL_FEATURES}
DEFAULT_FEATURES["theme_mode"] = "auto"


def load_features() -> dict[str, object]:
    if not CONFIG_FILE.is_file():
        return dict(DEFAULT_FEATURES)
    try:
        data = json.loads(CONFIG_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_FEATURES)
    out = dict(DEFAULT_FEATURES)
    for k, v in data.items():
        if k in DEFAULT_FEATURES:
            out[k] = v
    return out


def save_features(feat: dict[str, object]) -> None:
    lines = ["{"]
    for k in ALL_FEATURES:
        v = feat.get(k, True)
        lines.append(f'  "{k}":'.ljust(24) + f"{'true' if v else 'false'},")
    lines.append(f'  "theme_mode":'.ljust(24) + f'"{feat.get("theme_mode", "auto")}"')
    lines.append("}")
    CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ParsedArgs:
    def __init__(self):
        self.theme_mode: str | None = None
        self.do_save = False
        self.do_reset = False
        self.only_mode = False
        self.cli_overrides: dict[str, bool] = {}
        self.help = False


def parse_args(argv: list[str]) -> ParsedArgs:
    p = ParsedArgs()
    for arg in argv:
        if arg in ("-h", "--help"):
            p.help = True
        elif arg == "--light":
            p.theme_mode = "light"
        elif arg == "--dark":
            p.theme_mode = "dark"
        elif arg == "--auto":
            p.theme_mode = "auto"
        elif arg == "--only":
            p.only_mode = True
        elif arg == "--save":
            p.do_save = True
        elif arg == "--reset":
            p.do_reset = True
        elif arg in ("--no-download", "--offline"):
            p.cli_overrides["no_download"] = True
        elif arg == "--download":
            p.cli_overrides["no_download"] = False
        elif arg.startswith("--no-"):
            key = arg[5:].replace("-", "_")
            if key in ALL_FEATURES:
                p.cli_overrides[key] = False
        elif arg.startswith("--"):
            key = arg[2:].replace("-", "_")
            if key in ALL_FEATURES:
                p.cli_overrides[key] = True
    return p


def apply_overrides(feat: dict[str, object], parsed: ParsedArgs) -> dict[str, object]:
    if parsed.do_reset:
        feat = dict(DEFAULT_FEATURES)
        save_features(feat)
        ok("features.json reset to defaults")

    if parsed.only_mode:
        for k in ALL_FEATURES:
            if k != "no_download":
                feat[k] = False

    for k, v in parsed.cli_overrides.items():
        feat[k] = v

    if parsed.theme_mode:
        feat["theme_mode"] = parsed.theme_mode
    elif feat.get("theme_mode") not in ("auto", "light", "dark"):
        feat["theme_mode"] = "auto"

    if parsed.do_save:
        save_features(feat)
        ok("features.json saved")
    return feat


def export_env(feat: dict[str, object]) -> None:
    """Export FEAT_* and THEME_MODE into ``os.environ`` so step modules
    can read them via steps._helpers.feat_enabled / theme_mode."""
    os.environ["NO_DOWNLOAD"] = _b(feat.get("no_download", True))
    os.environ["THEME_MODE"] = str(feat.get("theme_mode", "auto"))
    for k in ALL_FEATURES:
        os.environ[f"FEAT_{k.upper()}"] = _b(feat.get(k, True))


def _b(v: object) -> str:
    return "true" if v else "false"


def verify_plasma() -> bool:
    if not have("plasmashell"):
        fail("KDE Plasma not found")
        print("     MacTahoe Liquid KDE requires KDE Plasma 6.6+.", file=sys.stderr)
        return False
    res = subprocess.run(
        ["plasmashell", "--version"],
        check=False, capture_output=True, text=True,
    )
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", res.stdout)
    if not m:
        warn("Could not detect plasmashell version")
        return True
    major, minor = int(m.group(1)), int(m.group(2))
    ver = f"{major}.{minor}.{m.group(3)}"
    if (major, minor) < (6, 6):
        fail(f"KDE Plasma {ver} (6.6+ required)")
        return False
    ok(f"KDE Plasma {ver}")
    if CONFIG_FILE.is_file():
        ok("features.json loaded")
    return True


def confirm(msg: str) -> bool:
    print()
    print(f"  \033[0;31m\033[1m{msg}\033[0m")
    print()
    try:
        with open("/dev/tty", "r+") as tty:
            tty.write("  Continue? [Y/n] ")
            tty.flush()
            answer = tty.readline().strip()
    except OSError:
        try:
            answer = input("  Continue? [Y/n] ")
        except EOFError:
            answer = ""
    if answer.lower() == "n":
        print("  Aborted.")
        return False
    print()
    return _prime_sudo()


def _prime_sudo() -> bool:
    # VSCode's integrated terminal (and other pty setups) can leave
    # bytes in the TTY input buffer between commands — OSC 633 shell
    # integration responses, mouse reporting, stray escapes. Sudo
    # consumes those bytes as the start of the password and reports
    # "Sorry, try again." on a correct password. Flush the input buffer
    # and reset the TTY to canonical/echo mode before prompting.
    try:
        import termios
        fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
        try:
            termios.tcflush(fd, termios.TCIFLUSH)
        finally:
            os.close(fd)
    except (OSError, ImportError):
        pass
    subprocess.run(
        ["stty", "sane"], check=False,
        stderr=subprocess.DEVNULL,
    )

    rc = subprocess.run(
        ["sudo", "-v", "-p", "  [sudo] password for %u: "],
        check=False,
    ).returncode
    if rc != 0:
        print("  \033[0;31msudo required.\033[0m", file=sys.stderr)
        return False
    return True


_VERIFY_CHECKS = [
    ("icons", "kdeglobals", "Icons", "Theme",
     "MacTahoeLiquidKde-Icons", "Icon theme"),
    ("color_schemes", "kdeglobals", "General", "ColorScheme",
     "MacTahoeLiquidKde", "Color scheme"),
    ("cursors", "kcminputrc", "Mouse", "cursorTheme",
     "MacTahoeLiquidKde", "Cursor theme"),
    ("plasma_theme", "plasmarc", "Theme", "name",
     "MacTahoeLiquidKde", "Plasma theme"),
    ("window_decorations", "kwinrc", "org.kde.kdecoration2", "theme",
     "__aurorae__svg__MacTahoeLiquidKde", "Window decorations"),
]


def verify_config(feat: dict[str, object]) -> None:
    for key, file, group, prop, expected, label in _VERIFY_CHECKS:
        if not feat.get(key, True):
            continue
        actual = kw_read(file, group, prop)
        if expected in actual:
            ok(label)
        else:
            fail(f"{label} (expected {expected}, got {actual or 'empty'})")


def has_cache(feature: str, no_download: bool) -> bool:
    if not no_download:
        return False
    for base in (STEPS_DIR, LEGACY_STEPS_DIR):
        cache = base / feature.replace("_", "-")
        if feature == "wallpapers" and any((cache / "MacTahoe/contents/images").glob("*")):
            return True
        if feature == "fonts" and any((*cache.glob("*.otf"), *cache.glob("*.ttf"))):
            return True
        if feature == "cursors" and (cache / "MacTahoeLiquidKde/cursors").is_dir():
            return True
        if feature == "icons" and (cache / "MacTahoeLiquidKde-Icons").is_dir():
            return True
    return False


def should_process(feature: str, feat: dict[str, object]) -> bool:
    if feature == "globalmenu":
        return bool(feat.get("plasmoids", True))
    return bool(feat.get(feature, True))


_BASE_DEPS = [
    ("curl", "curl"), ("unzip", "unzip"),
    ("fc-cache", "fontconfig"), ("kwriteconfig6", "kconfig"),
    ("cmake", "cmake"), ("g++", "gcc"),
    ("pkg-config", "pkgconf"), ("dbus-monitor", "dbus"),
]


def _check_deps(feat: dict[str, object]) -> None:
    seen: set[str] = set()

    def dep(cmd: str, pkg: str) -> None:
        if cmd in seen:
            return
        seen.add(cmd)
        auto_dep(cmd, pkg)

    for cmd, pkg in _BASE_DEPS:
        dep(cmd, pkg)
    for feature in INSTALL_ORDER:
        if not should_process(feature, feat):
            continue
        if not step_exists(feature):
            continue
        for cmd, pkg in step_deps(feature):
            dep(cmd, pkg)


def _flush_icon_cache_signal() -> None:
    home = Path.home()
    for sub in (".cache/icon-cache.kcache", ".cache/kiconthemes"):
        shutil.rmtree(home / sub, ignore_errors=True)
    subprocess.run(
        ["dbus-send", "--session", "--type=signal",
         "/KIconLoader", "org.kde.KIconLoader.iconChanged", "int32:0"],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _print_done(verb: str) -> None:
    print()
    print(f"\033[0;32m\033[1m  ── Done\033[0m")
    if not errors:
        ok(f"MacTahoe Liquid KDE {verb} successfully")
    else:
        warn(f"{len(errors)} issue(s):")
        for e in errors:
            fail(e)
    print()


def run_install(argv: list[str]) -> int:
    parsed = parse_args(argv)
    if parsed.help:
        print(INSTALL_HELP)
        return 0

    feat = apply_overrides(load_features(), parsed)
    export_env(feat)

    tracker = RunTracker("install", argv, str(feat.get("theme_mode", "auto")))
    tracker.start()
    rc = 0
    try:
        if not SRC_DIR.is_dir():
            print("  \033[0;31m  Run from repo root.\033[0m", file=sys.stderr)
            return 1

        banner(read_version())
        if not confirm("In development — Install at your own risk."):
            tracker.mark_aborted()
            return 0

        step("Verification")
        note("Checks KDE version and required tools")
        if not verify_plasma():
            return 1

        step("Dependencies")
        note("Checking and installing required tools")
        _check_deps(feat)

        for feature in INSTALL_ORDER:
            if feature == "layout":
                continue
            if not should_process(feature, feat):
                continue
            if not step_exists(feature):
                continue
            label = feature.replace("_", " ")
            step(f"Installing {label}")
            note(FEATURE_DESC.get(feature, ""))

            if step_has_phase(feature, "download"):
                if has_cache(feature, bool(feat.get("no_download", True))):
                    ok(f"{label} already downloaded")
                else:
                    run_phase(feature, "download")
            if step_has_phase(feature, "build"):
                run_phase(feature, "build")
            run_phase(feature, "install")

        step("Installing Theme Switcher")
        note("Installs the auto light/dark theme switcher")
        run_phase("theme_switch", "install")

        step("Applying Changes")
        note("Applies settings, flushes caches, restarts KWin")
        run_phase("apply", "install")

        # Layout runs after apply so it sees the new panel/dock packages
        # already on disk. The Plasma JS scripting API otherwise fails to
        # find the custom plasmoids by ID.
        if feat.get("layout", True) and step_exists("layout"):
            step("Installing Layout")
            note(FEATURE_DESC["layout"])
            run_phase("layout", "install")

        _flush_icon_cache_signal()

        step("Verification")
        note("Checking theme configuration was applied")
        verify_config(feat)

        step("Restarting Plasma")
        note("Restarts Plasma shell to load all changes")
        run_phase("apply", "restart_plasma")

        _print_done("installed")
        if not errors:
            tracker.mark_completed()
        return 0
    except KeyboardInterrupt:
        tracker.mark_aborted()
        print("\n  Aborted.", file=sys.stderr)
        return 130
    finally:
        tracker.finalize(rc)


def run_uninstall(argv: list[str]) -> int:
    parsed = parse_args(argv)
    if parsed.help:
        print(UNINSTALL_HELP)
        return 0

    feat = apply_overrides(load_features(), parsed)
    export_env(feat)

    tracker = RunTracker("uninstall", argv, str(feat.get("theme_mode", "auto")))
    tracker.start()
    rc = 0
    try:
        if not SRC_DIR.is_dir():
            print("  \033[0;31m  Run from repo root.\033[0m", file=sys.stderr)
            return 1

        banner(read_version())
        if not confirm("This will reset your desktop to Breeze defaults."):
            tracker.mark_aborted()
            return 0

        step("Verification")
        note("Checks KDE version")
        if not verify_plasma():
            return 1

        for feature in INSTALL_ORDER:
            if feature == "layout":
                continue
            if not should_process(feature, feat):
                continue
            if not step_exists(feature):
                continue
            label = feature.replace("_", " ")
            step(f"Removing {label}")
            note(FEATURE_DESC.get(feature, ""))
            run_phase(feature, "uninstall")

        step("Removing Theme Switcher")
        note("Stops and removes the auto light/dark theme switcher")
        run_phase("theme_switch", "uninstall")

        if feat.get("layout", True) and step_exists("layout"):
            step("Resetting Layout")
            note("Resets panel layout to default")
            run_phase("layout", "uninstall")

        step("Applying Changes")
        note("Resets to Breeze defaults and flushes caches")
        run_phase("apply", "uninstall")

        step("Restarting Plasma")
        note("Restarts Plasma shell to finalize changes")
        run_phase("apply", "restart_plasma")

        _print_done("uninstalled")
        if not errors:
            tracker.mark_completed()
        return 0
    except KeyboardInterrupt:
        tracker.mark_aborted()
        print("\n  Aborted.", file=sys.stderr)
        return 130
    finally:
        tracker.finalize(rc)
