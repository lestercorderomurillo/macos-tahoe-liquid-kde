import shutil
import subprocess
import time
from pathlib import Path

from steps._helpers import (
    build_dir, cmake_build, fail, info, kw_write, ok, offline, qdbus_call,
    sudo_remove, warn,
)

SRC = offline("kwin-effects/acrylic-glass")
BUILD = build_dir("kwin-effects/acrylic-glass")
HOME = Path.home()
USER_PLUGIN_DIR = HOME / ".local/lib/qt6/plugins"


def deps():
    return ["cmake", "g++:gcc", "pkg-config:pkgconf"]


def _plugin_dir() -> Path:
    for cmd in (
        ["qmake6", "-query", "QT_INSTALL_PLUGINS"],
        ["qtpaths6", "--plugin-dir"],
        ["pkg-config", "--variable=plugindir", "Qt6Core"],
    ):
        if shutil.which(cmd[0]):
            res = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return Path(res.stdout.strip())
    return Path("/usr/lib/qt6/plugins")


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
    ("BlurStrength", "3"), ("BorderWidth", "32"),
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


def _user_dest(rel: str) -> Path:
    """User-path destination for a kwin effect .so. Qt6 plugin search
    walks ``~/.local/lib/qt6/plugins`` by default (and we ensure it via
    QT_PLUGIN_PATH on plasma restart anyway), so installing here makes
    the entire install sudo-free — no more pam_unix conversation-failed
    cascade just to drop a .so in /usr/lib."""
    return USER_PLUGIN_DIR / rel


def install() -> None:
    system_dir = _plugin_dir()
    effect_so = BUILD / "src/liquidglass.so"
    config_so = BUILD / "src/kcm/kwin_liquidglass_config.so"
    dest_effect = _user_dest("kwin/effects/plugins/liquidglass.so")
    dest_config = _user_dest("kwin/effects/configs/kwin_liquidglass_config.so")
    legacy_effect = system_dir / "kwin/effects/plugins/liquidglass.so"
    legacy_config = system_dir / "kwin/effects/configs/kwin_liquidglass_config.so"

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

    # Note: legacy /usr/lib cleanup intentionally lives in uninstall()
    # only — install is sudoless. New install puts everything under
    # ~/.local/lib/qt6/plugins/ which Plasma searches first, so a
    # leftover system-path .so does not shadow the new install; it
    # only persists until the user runs ``sudo ./uninstall``.

    dest_effect.parent.mkdir(parents=True, exist_ok=True)
    dest_config.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(effect_so, dest_effect)
        ok("Acrylic Glass installed")
    except OSError as exc:
        fail(f"Acrylic Glass install failed: {exc}")
        return
    try:
        shutil.copy2(config_so, dest_config)
        ok("Acrylic Glass KCM installed")
    except OSError as exc:
        warn(f"Acrylic Glass KCM install failed: {exc}")

    for key, value in _PRESET:
        kw_write("--file", "kwinrc", "--group", "Effect-liquidglass",
                 "--key", key, value)
    ok("Acrylic Glass preset installed")
    kw_write("--file", "kwinrc", "--group", "Plugins",
             "--key", "liquidglassEnabled", "true")
    ok("Acrylic Glass installed (active after Plasma restart)")


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

    # User-path uninstall (no sudo needed).
    for so in (_user_dest("kwin/effects/plugins/liquidglass.so"),
               _user_dest("kwin/effects/configs/kwin_liquidglass_config.so")):
        if so.is_file():
            try:
                so.unlink()
                ok(so.name)
            except OSError as exc:
                fail(f"{so.name} ({exc})")
    # Clean up any leftover system-path install too. The uninstall path
    # demands ``sudo ./uninstall`` so this can actually delete root-owned
    # files.
    system_dir = _plugin_dir()
    for so in (system_dir / "kwin/effects/plugins/liquidglass.so",
               system_dir / "kwin/effects/configs/kwin_liquidglass_config.so"):
        sudo_remove(so, f"{so.name} (legacy /usr/lib)")
    info("Acrylic Glass removed")
