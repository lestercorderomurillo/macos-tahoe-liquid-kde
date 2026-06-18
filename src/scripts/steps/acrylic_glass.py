import subprocess
import time
from pathlib import Path

from distro import qt6_plugins_dir
from steps._helpers import (
    build_dir, cmake_build, fail, info, kw_write, ok, offline, qdbus_call,
    sudo_install_file, sudo_remove, warn,
)
from utils import qdbus_cmd, run_user

SRC = offline("kwin-effects/acrylic-glass")
BUILD = build_dir("kwin-effects/acrylic-glass")
HOME = Path.home()
LEGACY_USER_PLUGIN_DIR = HOME / ".local/lib/qt6/plugins"


def deps():
    return [
        "qmake6",
        "qt6-gui-cmake:qt6-base",
        "qt6-uitools-cmake:qt6-tools",
        "cmake",
        "ecm:extra-cmake-modules",
        "make",
        "g++:gcc",
        "pkg-config:pkgconf",
        # KF6 components required by the acrylic-glass CMakeLists.
        "kf6-config-cmake:kconfig",
        "kf6-configwidgets-cmake:kconfigwidgets",
        "kf6-coreaddons-cmake:kcoreaddons",
        "kf6-crash-cmake:kcrash",
        "kf6-globalaccel-cmake:kglobalaccel",
        "kf6-i18n-cmake:ki18n",
        "kf6-kio-cmake:kio",
        "kf6-service-cmake:kservice",
        "kf6-notifications-cmake:knotifications",
        "kf6-widgetsaddons-cmake:kwidgetsaddons",
        "kf6-windowsystem-cmake:kwindowsystem",
        "kf6-guiaddons-cmake:kguiaddons",
        "kf6-kcmutils-cmake:kcmutils",
        # KWin (Wayland) is mandatory: the effect refuses to configure
        # if neither GLASS_WAYLAND nor GLASS_X11 ends up enabled.
        "kwin-cmake:kwin",
        "kdecoration-cmake:kdecoration",
        # libepoxy + X11/XCB headers (XCB is REQUIRED even when X11
        # path of the effect is off — it's used by the Wayland code).
        "epoxy-cmake:libepoxy",
        "x11-cmake:libx11",
        "xcb-cmake:libxcb",
    ]


def build_artifacts() -> list[Path]:
    return [
        BUILD / "src/liquidglass.so",
        BUILD / "src/kcm/kwin_liquidglass_config.so",
    ]


def _plugin_dir() -> Path:
    """Kept for preflight's _enumerate_destinations() which calls this
    by name. Delegates to the shared discovery in paths.py so the same
    qmake6 / qtpaths6 / pkg-config chain — and the same raise-on-missing
    contract — applies across every step."""
    return qt6_plugins_dir()


def build() -> None:
    if not (SRC / "CMakeLists.txt").is_file():
        return
    for fn in ("glass_core.frag", "glass.frag"):
        try: (SRC / "src/shaders" / fn).unlink()
        except FileNotFoundError: pass
        except OSError: pass

    # Disable conflicting blur effects before build so the kwin plugin
    # loader doesn't keep the .so mapped while we replace it.
    kw_write("--file", "kwinrc", "--group", "Plugins",
             "--key", "glassEnabled", "false")
    kw_write("--file", "kwinrc", "--group", "Plugins",
             "--key", "blurEnabled", "false")
    qdbus_call("org.kde.KWin", "/Effects",
               "org.kde.kwin.Effects.unloadEffect", "glass")
    qdbus_call("org.kde.KWin", "/Effects",
               "org.kde.kwin.Effects.unloadEffect", "blur")

    cmake_build(SRC, BUILD, "Acrylic Glass")


_PRESET = (
    ("BevelStrength", "0.22"), ("BlurDecorations", "true"),
    ("BlurStrength", "5"), ("BorderWidth", "32"),
    ("BottomCornerRadius", "22"), ("Brightness", "1.0"),
    ("Contrast", "1.0"), ("DialogCornerRadius", "14"),
    ("DockCornerRadius", "20"), ("EdgeBandFactor", "0.24"),
    ("EdgeLighting", "false"), ("ExcludeDocks", "true"),
    ("GlassInactiveWindows", "true"), ("GlassThickness", "0.2"),
    ("GlowColor", "#00000000"), ("HighlightStrength", "0.30"),
    ("HighlightWidth", "24"), ("InnerShadowStrength", "0.2"),
    ("IridescenceStrength", "0.1"), ("MagnifyGlassStrength", "0.03"),
    ("MenuCornerRadius", "0"), ("NoiseStrength", "2"),
    ("PopupCornerRadius", "6"), ("RefractionEdgeSize", "0"),
    ("RefractionNormalPow", "6"), ("RefractionRGBFringing", "0"),
    ("RefractionStrength", "0"), ("RefractionWidth", "96"),
    ("RgbRinging", "12"), ("RimStrength", "0.5"),
    ("RimWidth", "32"), ("Saturation", "1.0"),
    ("ShadowStrength", "2.50"), ("SpectralMix", "1"),
    ("SpecularStrength", "0.08"), ("TintColor", "#00000000"),
    ("TooltipCornerRadius", "14"), ("WindowCornerRadius", "22"),
    ("BlurMatching", "false"), ("BlurNonMatching", "true"),
)


def install() -> None:
    system_dir = _plugin_dir()
    effect_so = BUILD / "src/liquidglass.so"
    config_so = BUILD / "src/kcm/kwin_liquidglass_config.so"
    dest_effect = system_dir / "kwin/effects/plugins/liquidglass.so"
    dest_config = system_dir / "kwin/effects/configs/kwin_liquidglass_config.so"

    if not effect_so.is_file():
        return

    # Unload before replacing the .so so kwin doesn't hold the file.
    kw_write("--file", "kwinrc", "--group", "Plugins",
             "--key", "liquidglassEnabled", "false")
    qdbus_call("org.kde.KWin", "/Effects",
               "org.kde.kwin.Effects.unloadEffect", "liquidglass")
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    time.sleep(2)
    ok("Acrylic Glass unloaded for safe upgrade")

    # Drop user-path leftovers from the v0.8.4-0.8.6 sudoless install.
    for so in (LEGACY_USER_PLUGIN_DIR / "kwin/effects/plugins/liquidglass.so",
               LEGACY_USER_PLUGIN_DIR / "kwin/effects/configs/kwin_liquidglass_config.so"):
        if so.is_file():
            try:
                so.unlink()
                ok(f"{so.name} (removed user-path leftover)")
            except OSError:
                pass

    if not sudo_install_file(effect_so, dest_effect, "Acrylic Glass installed"):
        return
    if not sudo_install_file(config_so, dest_config, "Acrylic Glass KCM installed"):
        warn("Acrylic Glass KCM install failed")

    for key, value in _PRESET:
        kw_write("--file", "kwinrc", "--group", "Effect-liquidglass",
                 "--key", key, value)
    ok("Acrylic Glass preset installed")
    kw_write("--file", "kwinrc", "--group", "Plugins",
             "--key", "liquidglassEnabled", "true")

    # Hot-load the freshly-written .so into the running KWin. The order
    # matters: unload again to drop any handle KWin's effect loader may
    # have kept on the previous binary, reconfigure so the new preset and
    # liquidglassEnabled=true are picked up, then loadEffect against the
    # file we just installed. Querying activeEffects afterwards is the
    # only honest way to know it took — loadEffect itself returns true
    # whether the effect was already loaded or freshly mapped.
    qdbus_call("org.kde.KWin", "/Effects",
               "org.kde.kwin.Effects.unloadEffect", "liquidglass")
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    qdbus_call("org.kde.KWin", "/Effects",
               "org.kde.kwin.Effects.loadEffect", "liquidglass")

    q = qdbus_cmd()
    active = ""
    if q:
        try:
            res = run_user([q, "org.kde.KWin", "/Effects",
                            "org.kde.kwin.Effects.activeEffects"],
                           check=False, capture_output=True, text=True,
                           timeout=10)
            active = res.stdout or ""
        except subprocess.TimeoutExpired:
            pass
    if "liquidglass" in active:
        ok("Acrylic Glass loaded")
    else:
        ok("Acrylic Glass installed (log out and back in to activate)")


def uninstall() -> None:
    qdbus_call("org.kde.KWin", "/Effects",
               "org.kde.kwin.Effects.unloadEffect", "liquidglass")
    kw_write("--file", "kwinrc", "--group", "Plugins",
             "--key", "liquidglassEnabled", "false")

    # Strip the entire [Effect-liquidglass] group from kwinrc — setting
    # keys to false would leave the group behind and a reinstall would
    # not reset tuned values.
    kwinrc = Path.home() / ".config/kwinrc"
    if kwinrc.is_file():
        text = kwinrc.read_text()
        if "[Effect-liquidglass]" in text:
            out: list[str] = []
            skip = False
            for line in text.splitlines():
                if line.startswith("[Effect-liquidglass]"):
                    skip = True
                    continue
                if skip and line.startswith("["):
                    skip = False
                if not skip:
                    out.append(line)
            kwinrc.write_text("\n".join(out) + "\n")

    system_dir = _plugin_dir()
    for so in (system_dir / "kwin/effects/plugins/liquidglass.so",
               system_dir / "kwin/effects/configs/kwin_liquidglass_config.so"):
        sudo_remove(so, so.name)
    # Drop user-path leftovers from the v0.8.4-0.8.6 sudoless install.
    for so in (LEGACY_USER_PLUGIN_DIR / "kwin/effects/plugins/liquidglass.so",
               LEGACY_USER_PLUGIN_DIR / "kwin/effects/configs/kwin_liquidglass_config.so"):
        if so.is_file():
            try:
                so.unlink()
                ok(f"{so.name} (legacy user-path)")
            except OSError as exc:
                fail(f"{so.name} ({exc})")
    info("Acrylic Glass removed")
