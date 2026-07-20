import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

from steps._helpers import (
    HOME, fail, feat_enabled, have, info, kw_write, ok, qdbus_call, theme_mode, warn,
)
from distro import kde_libexec_binary, user_service_manager_command
from utils import qdbus_cmd, run_user
from theme_switch import (
    _apply_wallpaper_snapshot,
    cycle_widget_style_live,
    _current_wallpapers,
    _wallpapers_from_config,
    _write_wallpapers_to_config,
    reset_kde_color_scheme_config,
    _theme_wallpaper_snapshot,
    _apply_lookandfeel_live,
    reconfigure_kwin_preserving_foreign_effects,
)
from steps.theme_switch import start_gtk_sync_watcher

# Cache files / dirs flushed during install + uninstall before Plasma reloads.
_CACHES = (
    ".cache/icon-cache.kcache",
    ".cache/kiconthemes",
    ".cache/ksvg-elements",
    ".cache/gtk-3.0",
    ".cache/gtk-4.0",
)
_CACHE_GLOBS = (
    ".cache/plasma-svgelements-*",
    ".cache/plasma_theme_*",
    ".cache/plasmashell*",
    ".cache/ksycoca6*",
)

_FONTS_INSTALL = {
    "font":                 "SF Pro Text,10,-1,5,50,0,0,0,0,0",
    "menuFont":             "SF Pro Text,10,-1,5,50,0,0,0,0,0",
    "toolBarFont":          "SF Pro Text,10,-1,5,50,0,0,0,0,0",
    "taskbarFont":          "SF Pro Text,10,-1,5,50,0,0,0,0,0",
    "smallestReadableFont": "SF Pro Text,8,-1,5,50,0,0,0,0,0",
    "fixed":                "SF Mono,10,-1,5,50,0,0,0,0,0",
}
_FONTS_RESET = {
    "font":                 "Noto Sans,10,-1,5,50,0,0,0,0,0",
    "menuFont":             "Noto Sans,10,-1,5,50,0,0,0,0,0",
    "toolBarFont":          "Noto Sans,10,-1,5,50,0,0,0,0,0",
    "taskbarFont":          "Noto Sans,10,-1,5,50,0,0,0,0,0",
    "smallestReadableFont": "Noto Sans,8,-1,5,50,0,0,0,0,0",
    "fixed":                "Hack,10,-1,5,50,0,0,0,0,0",
}

# Timeout for the fire-and-forget live-apply calls; run_user has none.
_LIVE_APPLY_TIMEOUT = 15
_BREEZE_WALLPAPER = Path("/usr/share/wallpapers/Next")


def _run_live(cmd: list[str]) -> bool:
    """Run a best-effort live-apply command, bounded by a timeout so a
    stuck KDE endpoint can't freeze the installer. OSError covers a
    missing or non-executable binary — a live nicety must degrade to a
    skip, never crash the install."""
    try:
        return run_user(
            cmd, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=_LIVE_APPLY_TIMEOUT,
        ).returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


# The standalone switcher chains its own 15-20s bounded subcalls (wallpaper,
# cursor, kvantum); a shared 15s cap would kill it mid-apply.
_THEME_SWITCH_TIMEOUT = 90


def _run_theme_switch_install(switch: Path) -> int | None:
    """Exit code of the standalone switcher, or None when it could not
    finish (timeout, or the binary failed to launch)."""
    try:
        result = run_user(
            [str(switch), theme_mode(), "install"], check=False,
            capture_output=True, text=True,
            timeout=_THEME_SWITCH_TIMEOUT,
        )
        # The switcher deliberately leaves third-party effect settings intact
        # and emits a precise recovery warning if KWin still cannot reload one.
        # Do not hide that warning behind the installer's captured subprocess.
        for line in (result.stderr or "").splitlines():
            if "your KWin effect" in line:
                warn(line.removeprefix("theme apply: "))
        return result.returncode
    except subprocess.TimeoutExpired:
        return None
    except OSError as exc:
        warn(f"theme switch could not run: {exc}")
        return None


def _refresh_desktop_database() -> None:
    """Rebuild mimeinfo.cache: a stale cache leaves launcher/taskbar apps
    missing after a theme switch. User dir as user; the system dir needs root."""
    from steps._helpers import _as_root
    if not have("update-desktop-database"):
        return
    user_apps = HOME / ".local/share/applications"
    if user_apps.is_dir():
        _run_live(["update-desktop-database", str(user_apps)])
    sys_apps = Path("/usr/share/applications")
    if sys_apps.is_dir():
        try:
            with _as_root():
                subprocess.run(
                    ["update-desktop-database", str(sys_apps)],
                    check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=_LIVE_APPLY_TIMEOUT,
                )
        except (subprocess.TimeoutExpired, OSError, PermissionError):
            pass


def _flush_caches() -> None:
    for sub in _CACHES:
        p = HOME / sub
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            try: p.unlink()
            except OSError: pass
    for pat in _CACHE_GLOBS:
        for p in HOME.glob(pat):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                try: p.unlink()
                except OSError: pass
    # Refresh mimeinfo.cache before sycoca so kbuildsycoca6 sees every app.
    _refresh_desktop_database()
    if have("kbuildsycoca6"):
        _run_live(["kbuildsycoca6", "--noincremental"])
    ok("Caches flushed")


def _live_plasma_ready_quick() -> bool:
    """Probe whether live Plasma mutations are worth trying. Uninstall
    restarts plasmashell anyway, so a missing display/shell means skip the
    live niceties and let the restart pick up the on-disk config."""
    import os as _os
    if not (_os.environ.get("DISPLAY") or _os.environ.get("WAYLAND_DISPLAY")):
        return False
    try:
        return subprocess.run(
            ["pgrep", "-x", "plasmashell"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=3,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def install() -> None:
    if have("kwriteconfig6") and feat_enabled("FONTS"):
        for key, val in _FONTS_INSTALL.items():
            kw_write("--file", "kdeglobals", "--group", "General",
                     "--key", key, val)
        kw_write("--file", "kdeglobals", "--group", "WM",
                 "--key", "activeFont", "SF Pro Display,11,-1,5,63,0,0,0,0,0")
        ok("Fonts installed")

    _flush_caches()

    switch = HOME / ".local/bin/mac-tahoe-theme-switch"
    if switch.is_file() and (switch.stat().st_mode & 0o111):
        # "install" context skips live plasmashell mutation (first-session and
        # QML teardown races); the final Plasma restart loads theme from config.
        rc = _run_theme_switch_install(switch)
        if rc == 0:
            ok(f"Theme applied ({theme_mode()})")
        elif rc is None:
            warn("Theme switch did not finish, config may be partial")
        else:
            warn(f"Theme switch failed (exit {rc})")
    else:
        # A restored backup or stray chmod can leave the switcher
        # non-executable; a silent skip would show all-green output with
        # the theme never live-applied.
        warn(f"Theme switcher missing or not executable ({switch}) — "
             "theme not live-applied")

    print("  …  Reconfiguring KWin", end="\r", flush=True)
    if feat_enabled("ACRYLIC_GLASS"):
        qdbus_call("org.kde.KWin", "/Effects",
                   "org.kde.kwin.Effects.loadEffect", "liquidglass")
        time.sleep(1)
    # The switcher already protects foreign effects during its own
    # reconfigure. Protect this install-tail reconfigure as well; otherwise a
    # compatible Rounded Corners effect could be restored and immediately
    # dropped again by the very next call.
    reconfigure_kwin_preserving_foreign_effects()
    time.sleep(3)
    ok("KWin reconfigured ")

    watcher = start_gtk_sync_watcher()
    if watcher is True:
        ok("Native light/dark sync active")
    elif watcher is False:
        warn("Native light/dark sync could not start; it will retry at login")


def _run_quick(cmd: list[str], *, capture_output: bool = False):
    try:
        kwargs = {"check": False, "timeout": 8}
        if capture_output:
            kwargs["capture_output"] = True
            kwargs["text"] = True
        else:
            kwargs["stdout"] = subprocess.DEVNULL
            kwargs["stderr"] = subprocess.DEVNULL
        return run_user(cmd, **kwargs)
    except (OSError, subprocess.TimeoutExpired):
        if capture_output:
            return subprocess.CompletedProcess(cmd, 124, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 124)


def _plasma_pids() -> set[int]:
    result = _run_quick(["pgrep", "-x", "plasmashell"], capture_output=True)
    pids: set[int] = set()
    for line in result.stdout.splitlines():
        try:
            pids.add(int(line))
        except ValueError:
            pass
    return pids


def _wait_for_old_plasma_exit(pids: set[int], attempts: int = 12) -> bool:
    for _ in range(attempts):
        if not (_plasma_pids() & pids):
            return True
        time.sleep(0.5)
    return not (_plasma_pids() & pids)


def _wait_for_plasma_start(attempts: int = 30) -> bool:
    for _ in range(attempts):
        if _plasma_pids():
            return True
        time.sleep(0.5)
    return bool(_plasma_pids())


def _hard_kill_plasma(systemd: bool) -> None:
    command = user_service_manager_command(
        "kill", "--signal=KILL", "plasma-plasmashell")
    killed_via_systemd = (
        systemd and command is not None and _run_quick(command).returncode == 0
    )
    if killed_via_systemd and not _plasma_pids():
        return
    for pid in _plasma_pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def _start_plasma(systemd: bool) -> bool:
    command = user_service_manager_command("start", "plasma-plasmashell")
    if systemd and command is not None:
        if _run_quick(command).returncode == 0:
            return True
    from utils import drop_privs_in_child as _drop
    try:
        subprocess.Popen(
            ["kstart", "plasmashell"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
            preexec_fn=_drop,
        )
        return True
    except OSError:
        return False


def restart_plasma() -> None:

    print("  …  Restarting Plasma", end="\r", flush=True)
    # let panels created by the layout script fully initialise
    time.sleep(6)

    restart_command = user_service_manager_command(
        "restart", "plasma-plasmashell")
    systemd = restart_command is not None

    original_pids = _plasma_pids()
    stopped = not original_pids

    # Ask Plasma to quit through its supported endpoint first so it can flush
    # panel state. A broken QML teardown is bounded and falls through.
    if not stopped and have("kquitapp6"):
        quit_result = _run_quick(["kquitapp6", "plasmashell"])
        if quit_result.returncode == 0:
            stopped = _wait_for_old_plasma_exit(original_pids)

    # systemd's restart is the second graceful path (SIGTERM + managed start).
    restarted_via_systemd = False
    if not stopped and systemd:
        restart_accepted = (
            restart_command is not None
            and _run_quick(restart_command).returncode == 0
        )
        # A successful job submission is not proof the wedged old shell went
        # away.  Require its PID to disappear before trusting the managed
        # restart; otherwise continue to the bounded hard-stop fallback.
        restarted_via_systemd = (
            restart_accepted and _wait_for_old_plasma_exit(original_pids)
        )

    # Keep the proven hard-stop behavior only as the final fallback. OpenRC
    # has no user service manager, so a failed kquitapp6 lands here directly.
    if not stopped and not restarted_via_systemd:
        _hard_kill_plasma(systemd)
        _wait_for_old_plasma_exit(original_pids, attempts=6)

    if not restarted_via_systemd:
        _start_plasma(systemd)

    started = _wait_for_plasma_start()
    if not started and restarted_via_systemd:
        # A successful restart job can still leave the unit inactive. Retry an
        # explicit managed start, then the init-agnostic kstart fallback.
        _start_plasma(systemd)
        started = _wait_for_plasma_start(attempts=10)
        if not started:
            _start_plasma(False)
            started = _wait_for_plasma_start(attempts=10)
    time.sleep(4)
    if started:
        ok("Plasma restarted ")
    else:
        warn("Plasma restart did not produce a running shell")


def _scrub_kdedefaults() -> None:
    # The scrub lives in a bundled kconf_update helper; run just
    # that one here — uninstall must not touch appletsrc or install anything.
    from steps.kconf_update import run_migration
    run_migration("mac-tahoe-scrub-kdedefaults.sh")
    ok("kdedefaults cleaned")


def uninstall() -> None:
    # Keep Breeze on disk as the source of truth, then best-effort the live
    # switch only when the full Plasma session is ready enough for it.
    if have("kwriteconfig6"):
        kw_write("--file", "kdeglobals", "--group", "KDE",
                 "--key", "LookAndFeelPackage", "org.kde.breeze.desktop")

    _scrub_kdedefaults()
    live_ready = _live_plasma_ready_quick()

    plasmarc = HOME / ".config/plasmarc"
    if plasmarc.is_file():
        text = plasmarc.read_text()
        # Strip [Theme-plasmathemeexplorer] when it caches our theme name.
        text = re.sub(
            r"\[Theme-plasmathemeexplorer\][^\[]*?(?=\n\[|\Z)",
            "", text,
        )
        plasmarc.write_text(text)

    if have("kwriteconfig6"):
        if feat_enabled("FONTS"):
            for key, val in _FONTS_RESET.items():
                kw_write("--file", "kdeglobals", "--group", "General",
                         "--key", key, val)
            kw_write("--file", "kdeglobals", "--group", "WM",
                     "--key", "activeFont", "Noto Sans,10,-1,5,50,0,0,0,0,0")
            ok("Fonts reset")
        if feat_enabled("CURSORS"):
            cursor_reset = (
                live_ready
                and have("plasma-apply-cursortheme")
                and _run_live(["plasma-apply-cursortheme", "breeze_cursors"])
            )
            if not cursor_reset:
                cursor_reset = kw_write(
                    "--file", "kcminputrc", "--group", "Mouse",
                    "--key", "cursorTheme", "breeze_cursors",
                )
            if cursor_reset:
                ok("Cursor reset")
            else:
                warn("Cursor reset failed")
        # Reset icons UNCONDITIONALLY (not gated on the ICONS feature): the
        # MacTahoe icon dirs are deleted later, so point config at breeze first.
        changeicons = kde_libexec_binary("plasma-changeicons")
        icons_reset = (
            live_ready
            and changeicons is not None
            and _run_live([str(changeicons), "breeze"])
        )
        if not icons_reset:
            icons_reset = kw_write(
                "--file", "kdeglobals", "--group", "Icons",
                "--key", "Theme", "breeze",
            )
        if icons_reset:
            ok("Icons reset")
        else:
            warn("Icons reset failed")
        if feat_enabled("WALLPAPERS"):
            if not _BREEZE_WALLPAPER.is_dir():
                warn("Wallpaper reset skipped: Breeze wallpaper not found")
            else:
                live_reset = (
                    live_ready
                    and have("plasma-apply-wallpaperimage")
                    and _run_live([
                        "plasma-apply-wallpaperimage",
                        str(_BREEZE_WALLPAPER),
                    ])
                )
                # If the supported live helper is unavailable or fails, write
                # each desktop containment through kwriteconfig6.  The final
                # Plasma restart then loads Breeze without depending on DBus.
                disk_reset = False
                if not live_reset:
                    current = (_current_wallpapers() if live_ready
                               else _wallpapers_from_config())
                    snapshot = _theme_wallpaper_snapshot(
                        current, _BREEZE_WALLPAPER)
                    disk_reset = (_apply_wallpaper_snapshot(snapshot)
                                  if live_ready
                                  else _write_wallpapers_to_config(snapshot))
                if live_reset or disk_reset:
                    ok("Wallpaper reset")
                elif not have("plasma-apply-wallpaperimage"):
                    warn("Wallpaper reset failed: live helper not found and "
                         "desktop config could not be updated")
                elif not live_ready:
                    warn("Wallpaper reset failed: no live Plasma session and "
                         "desktop config could not be updated")
                else:
                    warn("Wallpaper reset failed")
        if reset_kde_color_scheme_config("BreezeLight"):
            ok("Color scheme reset")
        else:
            warn("Color scheme reset failed")

    _flush_caches()

    # Unresponsive session is fine by design — the final plasmashell restart
    # picks up the on-disk Breeze config (see _live_plasma_ready_quick).
    if live_ready:
        if _apply_lookandfeel_live("org.kde.breeze.desktop"):
            ok("Look-and-feel applied live")
        else:
            warn("Live Breeze look-and-feel apply skipped")

    # Qt apps started under Kvantum keep its style instance alive after the
    # LAF switch; cycling widgetStyle forces re-instantiation without restart.
    if live_ready:
        if not cycle_widget_style_live("Breeze"):
            warn("Widget style cycle failed")

    if live_ready and qdbus_cmd() is not None:
        qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
        time.sleep(2)
        ok("KWin reconfigured")
