from localization import tr
import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

from distro import qt6_plugins_dir
from steps._native_build import cmake_build
from steps._helpers import (
    DATA_HOME, build_dir, fail, info, kw_write, ok, offline, qdbus_call,
    sudo_install_file, sudo_remove, warn, _as_root,
    kwin_plugin_mapping_matches as _plugin_mapping_matches,
    running_kwin_plugin_matches as _running_plugin_matches,
)
from utils import have, qdbus_cmd, run_user
from theme_switch import default_wallpaper
from installer_choices import selected

SRC = offline("kwin-effects/acrylic-glass")
BUILD = build_dir("kwin-effects/acrylic-glass")
HOME = Path.home()
LEGACY_USER_PLUGIN_DIR = HOME / ".local/lib/qt6/plugins"


def _translation_files():
    for language in ("pt_BR", "de"):
        relative = Path(language) / "LC_MESSAGES/kwin_effect_liquidglass.mo"
        yield SRC / "locale" / relative, DATA_HOME / "locale" / relative


def deps():
    dependencies = [
        "qmake6:qt6-base",
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
        "kdecoration-cmake:kdecoration",
        # XCB is REQUIRED even with the X11 path off — the Wayland code uses it.
        "epoxy-cmake:libepoxy",
        "x11-cmake:libx11",
        "xcb-cmake:libxcb",
        # Extension headers included transitively by KWin's public SDK.
        "xcb-composite-cmake:libxcb",
        "xcb-randr-cmake:libxcb",
        "xcb-res-cmake:libxcb",
        "xcb-shm-cmake:libxcb",
        "xcb-sync-cmake:libxcb",
        # KWin 6.7+ exports find_dependency(Vulkan), so find_package(KWin)
        # fails at configure time without these — even on non-Vulkan machines.
        "vulkan-loader-cmake:vulkan-icd-loader",
        "vulkan-headers-cmake:vulkan-headers",
    ]
    wayland_available = have("kwin_wayland")
    x11_available = have("kwin_x11")
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type in ("wayland", "x11"):
        # Require the running session's SDK; CMake also builds any other
        # backend whose SDK is already present, without adding packages.
        wayland_available = session_type == "wayland"
        x11_available = session_type == "x11"
    elif wayland_available or not x11_available:
        # Without a live session, prefer Wayland when both commands exist.
        # Some distros retain an X11 compatibility launcher after retiring
        # the X11 SDK; its presence must not require an unavailable package.
        wayland_available = True
        x11_available = False
    if wayland_available:
        dependencies.append("kwin-cmake:kwin")
    if x11_available:
        dependencies.append("kwin-x11-cmake:kwin-x11")
    return dependencies


def build_artifacts() -> list[Path]:
    artifacts = [BUILD / "src/kcm/kwin_liquidglass_config.so"]
    backends = [
        artifact for artifact in (
            BUILD / "src/liquidglass.so",
            BUILD / "src/liquidglass_x11.so",
        ) if artifact.is_file()
    ]
    required = {"wayland": "liquidglass.so", "x11": "liquidglass_x11.so"}.get(
        os.environ.get("XDG_SESSION_TYPE", "").lower())
    if required and BUILD / "src" / required not in backends:
        backends.append(BUILD / "src" / required)
    # An empty backend list must fail the installer's missing-artifact gate.
    artifacts.extend(backends or [BUILD / "src/liquidglass.so"])
    return artifacts


def _plugin_dir() -> Path:
    """Kept by name for preflight's _enumerate_destinations(); delegates to
    the shared qt6_plugins_dir() discovery (same raise-on-missing contract)."""
    return qt6_plugins_dir()


def build() -> None:
    if not (SRC / "CMakeLists.txt").is_file():
        return
    cmake_build(SRC, BUILD, "Acrylic Glass")


# Exact plugin IDs only; unrelated effects (including Rounded Corners) stay enabled.
CONFLICTING_BLURS = ("blur", "glass", "glass_x11", "betterblur", "forceblur", "forceblur_x11",
                     "better_blur_dx", "better_blur_dx_woapi",
                     "kwin4_effect_blur", "kwin4_effect_glass",
                     "kwin4_effect_betterblur", "kwin4_effect_forceblur")


def _loaded_effects() -> set[str] | None:
    q = qdbus_cmd()
    if not q:
        return None
    try:
        result = run_user([q, "org.kde.KWin", "/Effects",
                           "org.kde.kwin.Effects.loadedEffects"],
                          check=False, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return {item.strip() for item in (result.stdout or "").replace(",", "\n").splitlines() if item.strip()}
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _conflict_state_path() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME") or HOME / ".local/state") / "mac-tahoe-liquid-kde/blur-conflicts.json"


def _read_conflict_state(path: Path) -> dict:
    saved = json.loads(path.read_text())
    if not isinstance(saved, dict) or any(
            key not in CONFLICTING_BLURS or (value is not None and not isinstance(value, str))
            for key, value in saved.items()):
        raise ValueError("Invalid saved blur settings")
    return saved


def _plugin_setting(effect: str) -> str | None:
    sentinel = "__mttkde_absent__"
    result = run_user(["kreadconfig6", "--file", "kwinrc", "--group", "Plugins",
                       "--key", effect + "Enabled", "--default", sentinel],
                      check=False, capture_output=True, text=True, timeout=5)
    if result.returncode:
        raise OSError("Could not read KWin blur settings")
    value = (result.stdout or "").rstrip("\r\n")
    return None if value == sentinel else value


def _disable_conflicting_blurs() -> bool:
    path = _conflict_state_path()
    try:
        saved = _read_conflict_state(path) if path.exists() else {}
        current = {effect: _plugin_setting(effect) for effect in CONFLICTING_BLURS}
        # Retain the original state across reinstalls, before writing any settings.
        saved = current | saved
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(saved))
        temporary.replace(path)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        fail(tr("Could not preserve competing blur settings: {exc}", exc=exc))
        return False
    for effect in CONFLICTING_BLURS:
        if not kw_write("--file", "kwinrc", "--group", "Plugins",
                        "--key", effect + "Enabled", "false"):
            fail(tr("Could not disable competing blur: {effect}", effect=effect))
            _restore_conflicting_blurs()
            return False
        qdbus_call("org.kde.KWin", "/Effects", "org.kde.kwin.Effects.unloadEffect", effect)
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    loaded = _loaded_effects()
    if loaded is not None and loaded.intersection(CONFLICTING_BLURS):
        fail(tr("A competing blur effect is still loaded; Acrylic Glass was not activated"))
        _restore_conflicting_blurs()
        return False
    if loaded is None:
        fail(tr("Competing blurs disabled in settings, but their live unload could not be verified"))
        return False
    return True


def _restore_conflicting_blurs() -> None:
    path = _conflict_state_path()
    if not path.exists():
        return
    loaded = _loaded_effects()
    if loaded is None:
        warn(tr("Previous blur settings retained for recovery because Acrylic Glass unload could not be verified"))
        return
    if "liquidglass" in loaded:
        warn(tr("Previous blur settings retained for recovery because Acrylic Glass is still loaded"))
        return
    try:
        saved = _read_conflict_state(path)
        success = True
        for effect in CONFLICTING_BLURS:
            if effect not in saved or _plugin_setting(effect) != "false":
                continue  # Preserve subsequent user edits.
            args = ("--delete",) if saved[effect] is None else (str(saved[effect]),)
            success = kw_write("--file", "kwinrc", "--group", "Plugins",
                               "--key", effect + "Enabled", *args) and success
        if success:
            path.unlink()
        else:
            warn(tr("Some competing blur settings could not be restored"))
        qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        warn(tr("Could not restore competing blur settings: {exc}", exc=exc))


def _install_backing_tint() -> bool:
    choices = selected()
    if choices and choices["files"] == "nautilus":
        variant = "0" if choices["glass_style"] == "classic" else "1"
    elif default_wallpaper() == "MacGoldenGate":
        variant = "1"
    else:
        return True
    return kw_write("--file", "kwinrc", "--group", "Effect-liquidglass", "--key",
                    "BackingTint", variant)


_CORNER_DEFAULTS = (
    ("WindowCornerRadius", "22"),
    ("DockCornerRadius", "20"),
    ("PopupCornerRadius", "6"),
)

def _edition_preset() -> dict[str, str]:
    # The KCM and installer apply the same complete material.
    presets = json.loads((SRC / "src/presets.json").read_text())
    preset_id = "golden-gate" if default_wallpaper() == "MacGoldenGate" else "tahoe"
    choices = selected()
    if choices and choices["files"] == "nautilus":
        preset_id = "golden-gate" if choices["glass_style"] == "official" else "tahoe"
    preset = next(preset for preset in presets if preset["id"] == preset_id)
    values = dict(preset["values"])
    if choices and choices["files"] == "nautilus" and choices["glass_style"] == "tinted":
        values.update(preset.get("tinted_values", {}))
    return {key: str(value).lower() if isinstance(value, bool) else str(value)
            for key, value in values.items()} | {"MaterialPreset": str(preset["value"])}


def _install_material_preset() -> bool:
    # Installing an edition explicitly reapplies its optics. Write the selector
    # last so a failed material write cannot announce the new preset.
    for key, value in _edition_preset().items():
        if not kw_write("--file", "kwinrc", "--group", "Effect-liquidglass",
                        "--key", key, value):
            warn(tr('Acrylic Glass {key} preset not applied — kwriteconfig6 failed', key=key))
            return False
    return True


def _install_corner_defaults() -> None:
    """Seed missing radii without undoing the user's corner tuning (#89).

    The current effect has only three radius controls: popups also cover
    menus/tooltips, and normal windows cover dialogs and bottom corners.
    Preserve even explicitly empty values; failed reads never authorize a
    write. KConfig's cascade handles both user and system configuration.
    """
    _install_missing_defaults(_CORNER_DEFAULTS)


def _install_missing_defaults(defaults) -> None:
    if not have("kreadconfig6"):
        warn(tr('Acrylic Glass settings preserved — kreadconfig6 is unavailable'))
        return
    sentinel = f"__mttkde_absent_{uuid.uuid4().hex}__"
    for key, default in defaults:
        try:
            result = run_user(
                ["kreadconfig6", "--file", "kwinrc", "--group",
                 "Effect-liquidglass", "--key", key, "--default", sentinel],
                check=False, capture_output=True, text=True, timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            warn(tr('Acrylic Glass {key} preserved — could not read it ({exc})', key=key, exc=exc))
            continue
        if result.returncode != 0:
            warn(tr('Acrylic Glass {key} preserved — kreadconfig6 failed', key=key))
            continue
        if (result.stdout or "").removesuffix("\n").removesuffix("\r") == sentinel:
            if not kw_write("--file", "kwinrc", "--group", "Effect-liquidglass",
                            "--key", key, default):
                warn(tr('Acrylic Glass {key} default not applied — kwriteconfig6 failed', key=key))


def _versioned_effect_path(source: Path, directory: Path) -> Path:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    return directory / ".mttkde-liquidglass" / digest / "liquidglass.so"


def _owned_effect_paths(directory: Path) -> list[Path]:
    return [directory / "liquidglass.so", *sorted(
        path for path in (directory / ".mttkde-liquidglass").glob("*/liquidglass.so")
        if re.fullmatch(r"[0-9a-f]{64}", path.parent.name)
    )]


def _make_effect_path_readable(destination: Path) -> bool:
    try:
        with _as_root():
            for directory in (destination.parent.parent, destination.parent):
                directory.mkdir(parents=True, exist_ok=True, mode=0o755)
                directory.chmod(0o755)
            if destination.is_file():
                destination.chmod(0o644)
    except OSError as exc:
        fail(tr('Acrylic Glass plugin directory is not accessible: {exc}', exc=exc))
        return False
    return True


def _install_effect_binary(source: Path, destination: Path) -> bool:
    # Immutable filenames bypass Qt's resident-library cache. Reusing an
    # identical build must preserve its inode, not replace a mapped file.
    if destination.is_file() and not destination.is_symlink():
        if source.read_bytes() == destination.read_bytes():
            if not _make_effect_path_readable(destination):
                return False
            ok(tr('Acrylic Glass already installed'))
            return True
        fail(tr('Acrylic Glass versioned file has unexpected contents'))
        return False
    return (sudo_install_file(source, destination, tr('Acrylic Glass installed'))
            and _make_effect_path_readable(destination))


def _activate_effect_binary(destination: Path, link: Path) -> bool:
    # Qt canonicalizes this path before caching the library; the basename
    # remains liquidglass, which KDE uses as the plugin/configuration ID.
    temporary = link.with_name(f".liquidglass-link-{uuid.uuid4().hex}")
    try:
        with _as_root():
            temporary.symlink_to(destination.relative_to(link.parent))
            temporary.replace(link)
        return True
    except OSError as exc:
        fail(tr('Could not activate Acrylic Glass: {exc}', exc=exc))
        return False
    finally:
        with _as_root():
            temporary.unlink(missing_ok=True)


def _running_build_matches() -> bool | None:
    q = qdbus_cmd()
    try:
        header = (BUILD / "src/build_identity.h").read_text()
        identity = re.search(r'MTTKDE_GLASS_BUILD_ID "([0-9a-f]{64})"', header)
        if not q or not identity:
            return None
        result = run_user([q, "org.kde.KWin", "/Effects",
                           "org.kde.kwin.Effects.debug", "liquidglass", ""],
                          check=False, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() == identity[1] if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _render_status() -> str | None:
    q = qdbus_cmd()
    if not q:
        return None
    try:
        result = run_user([q, "org.kde.KWin", "/Effects",
                           "org.kde.kwin.Effects.debug", "liquidglass", "status"],
                          check=False, capture_output=True, text=True, timeout=5)
        status = (result.stdout or "").strip()
        return status if result.returncode == 0 and status in ("ready", "shader-error") else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def install() -> None:
    system_dir = _plugin_dir()
    backends = [
        (BUILD / "src/liquidglass.so", system_dir / "kwin/effects/plugins",
         system_dir / "kwin/effects/configs/kwin_liquidglass_config.so"),
        (BUILD / "src/liquidglass_x11.so", system_dir / "kwin-x11/effects/plugins",
         system_dir / "kwin-x11/effects/configs/kwin_liquidglass_config.so"),
    ]
    backends = [backend for backend in backends if backend[0].is_file()]
    config_so = BUILD / "src/kcm/kwin_liquidglass_config.so"
    if not backends:
        return
    dest_effects = [(source, directory, _versioned_effect_path(source, directory), config)
                    for source, directory, config in backends]

    for source, destination in _translation_files():
        if not sudo_install_file(source, destination, tr("Acrylic Glass translation installed: {language}",
                                                        language=destination.parts[-3]), user_owned=True):
            return

    # Disable discovery while switching versions. Qt can retain the old
    # library even after the effect instance has been unloaded.
    if not kw_write("--file", "kwinrc", "--group", "Plugins",
                    "--key", "liquidglassEnabled", "false"):
        fail(tr('Acrylic Glass could not be disabled in kwinrc'))
        return
    qdbus_call("org.kde.KWin", "/Effects",
               "org.kde.kwin.Effects.unloadEffect", "liquidglass")
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    time.sleep(2)
    loaded = _loaded_effects()
    if loaded is not None and "liquidglass" in loaded:
        kw_write("--file", "kwinrc", "--group", "Plugins", "--key", "liquidglassEnabled", "true")
        fail(tr('Acrylic Glass is still loaded; log out before upgrading'))
        return

    # Drop user-path leftovers from old sudoless installs.
    for so in (LEGACY_USER_PLUGIN_DIR / "kwin/effects/plugins/liquidglass.so",
               LEGACY_USER_PLUGIN_DIR / "kwin/effects/configs/kwin_liquidglass_config.so"):
        if so.is_file():
            try:
                so.unlink()
                ok(tr('{value1} (removed user-path leftover)', value1=so.name))
            except OSError:
                pass

    for source, effect_dir, dest_effect, dest_config in dest_effects:
        if not _install_effect_binary(source, dest_effect):
            return
        if not sudo_install_file(config_so, dest_config, tr('Acrylic Glass KCM installed')):
            warn(tr('Acrylic Glass KCM install failed'))
        if not _activate_effect_binary(dest_effect, effect_dir / "liquidglass.so"):
            return
        # Retire only our versioned files. The discovery link stays in place.
        for previous in _owned_effect_paths(effect_dir):
            if previous.parent != effect_dir and previous != dest_effect:
                if not sudo_remove(previous, tr('Previous Acrylic Glass binary removed')):
                    fail(tr('Could not retire the previous Acrylic Glass plugin'))
                    return
                with _as_root():
                    try:
                        previous.parent.rmdir()
                    except OSError:
                        pass

    material_applied = _install_material_preset()
    _install_corner_defaults()
    _install_missing_defaults((("BlurDecorations", "true"),
                               ("BlurMatching", "false"), ("BlurNonMatching", "true")))
    if not material_applied or not _install_backing_tint():
        fail(tr('Acrylic Glass material settings could not be applied'))
        return
    ok(tr('Acrylic Glass material settings ready'))
    if not _disable_conflicting_blurs():
        return
    if not kw_write("--file", "kwinrc", "--group", "Plugins",
                    "--key", "liquidglassEnabled", "true"):
        fail(tr('Acrylic Glass could not be enabled in kwinrc'))
        _restore_conflicting_blurs()
        return

    # Reload the effect instance. Qt may still retain its old shared library;
    # activeEffects alone cannot prove the newly installed code is running.
    qdbus_call("org.kde.KWin", "/Effects",
               "org.kde.kwin.Effects.unloadEffect", "liquidglass")
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    qdbus_call("org.kde.KWin", "/Effects",
               "org.kde.kwin.Effects.loadEffect", "liquidglass")

    loaded = _loaded_effects()
    status = _render_status() if loaded is not None and "liquidglass" in loaded else None
    if status == "shader-error":
        fail(tr('Acrylic Glass could not initialize its shaders; restoring the previous blur settings'))
        kw_write("--file", "kwinrc", "--group", "Plugins", "--key", "liquidglassEnabled", "false")
        qdbus_call("org.kde.KWin", "/Effects", "org.kde.kwin.Effects.unloadEffect", "liquidglass")
        _restore_conflicting_blurs()
        return
    if loaded is not None and "liquidglass" in loaded:
        identity_matches = _running_build_matches()
        if identity_matches is None:
            matches = [_running_plugin_matches(destination)
                       for _, _, destination, _ in dest_effects]
            identity_matches = (True if True in matches else
                                False if matches and all(value is False for value in matches)
                                else None)
        if identity_matches is False:
            warn(tr('Acrylic Glass installed, but KWin still has the previous plugin loaded. Log out and back in to use this update; reloading the effect or restarting Plasma is not enough.'))
        elif identity_matches is True and status == "ready":
            ok(tr('Acrylic Glass loaded'))
        elif identity_matches is True:
            warn(tr('Acrylic Glass build is loaded, but shader readiness could not be verified'))
        else:
            warn(tr('Acrylic Glass is active, but its running build could not be verified.'))
    else:
        warn(tr('Acrylic Glass installed but activation was not confirmed. Log out and back in after a KWin upgrade; if it remains inactive, check the KWin log for liquidglass shader or plugin errors.'))
        if loaded is not None:
            kw_write("--file", "kwinrc", "--group", "Plugins", "--key", "liquidglassEnabled", "false")
            _restore_conflicting_blurs()


def uninstall() -> None:
    # Persist the disabled state before asking KWin to unload the effect.
    # Unloading first can race a config notification/reconfigure and let KWin
    # immediately load the still-enabled plugin again, leaving every window
    # translucent until the user logs out even though the .so was removed.
    disabled = kw_write(
        "--file", "kwinrc", "--group", "Plugins",
        "--key", "liquidglassEnabled", "false",
    )
    unloaded = qdbus_call(
        "org.kde.KWin", "/Effects",
        "org.kde.kwin.Effects.unloadEffect", "liquidglass",
    )
    reconfigured = qdbus_call(
        "org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure",
    )
    if not disabled:
        warn(tr('Acrylic Glass could not be disabled in kwinrc'))
    if not unloaded and not reconfigured:
        # A reconfigure with liquidglassEnabled=false is an equivalent live
        # unload.  Only warn when neither live path reached KWin.
        warn(tr('Acrylic Glass live unload was not confirmed — log out once if window transparency remains'))

    # Strip the whole [Effect-liquidglass] group — leaving it behind would
    # let a reinstall keep stale tuned values.
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
    for _, destination in _translation_files():
        sudo_remove(destination, tr("Acrylic Glass translation removed: {language}",
                                    language=destination.parts[-3]))
    for so in (*_owned_effect_paths(system_dir / "kwin/effects/plugins"),
               system_dir / "kwin/effects/configs/kwin_liquidglass_config.so",
               *_owned_effect_paths(system_dir / "kwin-x11/effects/plugins"),
               system_dir / "kwin-x11/effects/configs/kwin_liquidglass_config.so"):
        sudo_remove(so, so.name)
    # Drop user-path leftovers from old sudoless installs.
    for so in (LEGACY_USER_PLUGIN_DIR / "kwin/effects/plugins/liquidglass.so",
               LEGACY_USER_PLUGIN_DIR / "kwin/effects/configs/kwin_liquidglass_config.so"):
        if so.is_file():
            try:
                so.unlink()
                ok(tr('{value1} (legacy user-path)', value1=so.name))
            except OSError as exc:
                fail(f"{so.name} ({exc})")

    # Refresh KWin's effect catalogue after the plugin files disappear.  This
    # also repaints windows immediately on sessions where unloadEffect is
    # asynchronous, instead of leaving the old effect mapped until logout.
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    _restore_conflicting_blurs()
    info(tr('Acrylic Glass removed'))
