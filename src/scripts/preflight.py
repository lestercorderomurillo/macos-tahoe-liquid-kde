"""Preflight: prove the basics work BEFORE any install/uninstall step
touches disk. Nine fail-fast checks, in order, all visible to the user
(see run_preflight; documented in AGENTS.md)."""

from localization import tr

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from log import fail, note, ok, step, warn
from distro import (
    Qt6PathsMissing,
    plasma_version_probe_cmds,
    qt6_install_hint,
    qt6_plugins_dir,
    qt6_qml_dir,
)
from paths import OFFLINE_DIR
from utils import run_user


def _check_sudo_escalation() -> bool:
    if os.getuid() != 0:
        fail(tr('real UID is not root — sudo not active (run: sudo ./install)'))
        return False

    if os.geteuid() == 0:
        warn(tr('running as effective root — privilege drop did not happen'))

    from steps._helpers import _as_root

    try:
        probe_dir = qt6_plugins_dir()
    except Qt6PathsMissing as exc:
        fail(str(exc))
        return False

    probe = probe_dir / f".mttkde-preflight-{os.getpid()}"
    print(tr('  probe path: {probe}', probe=probe))
    try:
        with _as_root():
            probe_dir.mkdir(parents=True, exist_ok=True)
            probe.write_text("ok\n")
            content = probe.read_text()
            probe.unlink()
        if content != "ok\n":
            fail(tr("sudo hop wrote {content!r}, expected 'ok\\n'", content=content))
            return False
    except OSError as exc:
        fail(tr('sudo hop failed ({value1}: {exc})', value1=exc.__class__.__name__, exc=exc))
        return False
    except PermissionError as exc:
        fail(tr('sudo hop denied ({exc})', exc=exc))
        return False
    ok(tr('sudo hop ok — wrote, read, removed {value1}', value1=probe.name))
    return True


# Resolved per call — a module-global cache leaked monkeypatched $HOME
# across pytest boundaries. Indirection kept so tests can patch _home().
_HOME: Path | None = None


def _home() -> Path:
    return _HOME if _HOME is not None else Path.home()


def _allowed_roots() -> tuple[re.Pattern, ...]:
    home = _home()
    user_roots = {
        home / ".local",
        home / ".config",
        home / ".cache",
    }
    for key in (
        "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME",
    ):
        value = os.environ.get(key)
        if not value:
            continue
        candidate = Path(value)
        # The project contract limits user writes to $HOME. Preserve a custom
        # XDG directory only when it is absolute and remains beneath that home.
        if candidate.is_absolute() and candidate != home and home in candidate.parents:
            user_roots.add(candidate)
    user_patterns = tuple(
        re.compile(rf"^{re.escape(str(root))}(/|$)")
        for root in sorted(user_roots, key=str)
    )
    # Qt roots come from qmake6 so nonstandard libdirs (openSUSE /usr/lib64,
    # Debian multiarch) validate without a hand-maintained list.
    try:
        qt_plugins = re.escape(str(qt6_plugins_dir()))
        qt_qml = re.escape(str(qt6_qml_dir()))
        qt_patterns = (
            re.compile(rf"^{qt_plugins}(/|$)"),
            re.compile(rf"^{qt_qml}(/|$)"),
        )
    except Qt6PathsMissing:
        # Don't green-light /usr/lib/qt6 by convention when qmake6 is
        # missing — the Qt path check reports it with a distro hint.
        qt_patterns = ()
    return (
        *user_patterns,
        *qt_patterns,
        re.compile(r"^/etc/sddm\.conf\.d(/|$)"),
        re.compile(r"^/etc/plymouth(/|$)"),
        re.compile(r"^/usr/share/(kwin|licenses|locale|sounds|plasma|plymouth|wallpapers|mac-tahoe-liquid-kde)(/|$)"),
    )


_FORBIDDEN = (
    (re.compile(r"//"), "double slash"),
    (re.compile(r"/\.\./"), "parent traversal"),
    (re.compile(r"^/tmp(/|$)"), "tmp path used as install dest"),
)


def _validate_path(path: Path | str) -> str | None:
    """Return a reason string when ``path`` is *not* a valid install
    destination, or ``None`` when it's fine."""
    s = str(path)
    for pat, reason in _FORBIDDEN:
        if pat.search(s):
            return reason
    # /root is forbidden only when it isn't the real user's home — in a
    # container root IS the user, so /root writes are legitimate there.
    home = str(_home())
    if s.startswith("/root/") or s == "/root":
        if home != "/root" and not s.startswith(home + "/"):
            return "leaks /root home"
    if not any(pat.search(s) for pat in _allowed_roots()):
        return "outside allowed roots (user XDG dirs, Qt6 plugin/QML dirs from qmake6, /etc/sddm.conf.d, /etc/plymouth, /usr/share)"
    return None


def _enumerate_destinations() -> list[tuple[str, Path]]:
    """Known install destinations per step module. Imported lazily so
    module-level ``Path.home()`` runs AFTER the privilege drop."""
    from steps import acrylic_glass, globalmenu, kvantum, plasmoids, rounded_corners

    dests: list[tuple[str, Path]] = [
        ("globalmenu .so", globalmenu.DEST_SO),
        ("globalmenu QML module", globalmenu.DEST_QML_DIR),
        ("globalmenu GTK login environment", globalmenu.gtk_appmenu_env_path()),
        ("plasmoids share dir", plasmoids.DEST_DIR),
        ("taskmanager .so", plasmoids.TASKMANAGER_DEST_SO),
        ("taskmanager QML module", plasmoids.TASKMANAGER_DEST_QML),
        ("launcher QML module", plasmoids.LAUNCHER_DEST_QML),
        ("acrylic-glass plugin dir", acrylic_glass._plugin_dir()),
        ("kvantum Qt6 style plugin", kvantum._engine_destination()),
        ("kvantum bundled-source marker", kvantum.ENGINE_MARKER),
        ("kvantum bundled-source license", kvantum.ENGINE_LICENSE),
        ("rounded-corners plugin dir", rounded_corners._plugin_dir()),
        ("rounded-corners shader dir", rounded_corners.SHADER_DIR),
        ("rounded-corners locale dir", rounded_corners.LOCALE_DIR),
        ("rounded-corners license", rounded_corners.LICENSE_FILE),
    ]
    return dests


def _check_paths() -> bool:
    all_ok = True
    try:
        dests = _enumerate_destinations()
    except Qt6PathsMissing:
        fail(tr('Qt6 installation paths not found — cannot verify install destinations. Install qmake6 with: {value1}', value1=qt6_install_hint()))
        return False
    for label, path in dests:
        reason = _validate_path(path)
        if reason is None:
            ok(f"{tr(label)}: {path}")
        else:
            fail(f"{tr(label)}: {path} ({tr(reason)})")
            all_ok = False
    return all_ok


def _check_qt_paths() -> bool:
    """Cross-check every compiled-step destination against qmake6's
    reported plugin / QML dirs so a hardcoded libdir can't regress past
    the distro layer — openSUSE reports /usr/lib64 while others report /usr/lib."""
    try:
        plugins = qt6_plugins_dir()
        qml = qt6_qml_dir()
    except Qt6PathsMissing as exc:
        fail(str(exc))
        return False

    from steps import acrylic_glass, globalmenu, kvantum, plasmoids, rounded_corners
    qt_destinations = [
        ("globalmenu .so", globalmenu.DEST_SO, plugins),
        ("globalmenu QML module", globalmenu.DEST_QML_DIR, qml),
        ("taskmanager .so", plasmoids.TASKMANAGER_DEST_SO, plugins),
        ("taskmanager QML module", plasmoids.TASKMANAGER_DEST_QML, qml),
        ("launcher QML module", plasmoids.LAUNCHER_DEST_QML, qml),
        ("acrylic-glass plugin dir", acrylic_glass._plugin_dir(), plugins),
        ("kvantum Qt6 style plugin", kvantum._engine_destination(), plugins),
        ("rounded-corners plugin dir", rounded_corners._plugin_dir(), plugins),
    ]
    cross_ok = True
    for label, dest, expected_root in qt_destinations:
        try:
            dest.relative_to(expected_root)
        except ValueError:
            fail(tr("{label}: {dest} is NOT under qmake6's {expected_root} — hardcoded libdir slipped past the distro layer", label=tr(label), dest=dest, expected_root=expected_root))
            cross_ok = False
    if not cross_ok:
        return False

    print(tr('  Qt plugins: {plugins}', plugins=plugins))
    print(tr('  Qt qml:     {qml}', qml=qml))
    ok(tr('Qt plugin path discovered: {plugins}', plugins=plugins))
    ok(tr('Qt QML path discovered: {qml}', qml=qml))
    return True


# ── KDE Plasma version ──────────────────────────────────────────────


_MIN_PLASMA = (6, 6)
_PLASMA_VERSION_RE = re.compile(r"\b(\d+)\.(\d+)(?:\.(\d+))?\b")


def _probe_plasma_version() -> tuple[re.Match[str] | None, str | None]:
    last_error: str | None = None
    direct_probes = (
        (["plasmashell", "--version"], "plasmashell --version"),
        (["plasmashell", "-v"], "plasmashell -v"),
    )
    for cmd, label in direct_probes:
        try:
            res = run_user(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            last_error = tr('{label} timed out', label=label)
            continue
        except OSError as exc:
            last_error = tr('{label} failed: {exc}', label=label, exc=exc)
            continue
        out = (res.stdout or res.stderr or "").strip()
        if not out:
            last_error = tr('{label} returned nothing', label=label)
            continue
        match = _PLASMA_VERSION_RE.search(out)
        if match:
            return match, label
        last_error = tr('{label} output unparseable: {out!r}', label=label, out=out)

    for cmd in plasma_version_probe_cmds():
        try:
            res = run_user(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError):
            continue
        out = "\n".join(part.strip() for part in (res.stdout, res.stderr) if part).strip()
        if not out:
            continue
        match = _PLASMA_VERSION_RE.search(out)
        if match:
            return match, "installed Plasma package metadata"
    return None, last_error


def _check_plasma_version() -> bool:
    """Confirm plasmashell reports ≥6.6 (we compile against 6.6+ headers;
    older runtimes silently fail to load the applets). Must probe via
    run_user: real UID 0 + effective SUDO_USER trips Qt6's setuid guard
    (``getuid() != geteuid()`` aborts before parsing any args)."""
    if not shutil.which("plasmashell"):
        fail(tr('plasmashell not on PATH — KDE Plasma is not installed'))
        return False
    match, source = _probe_plasma_version()
    if not match:
        fail(source or tr("could not detect Plasma version"))
        return False
    major = int(match.group(1))
    minor = int(match.group(2))
    print(tr('  plasmashell {major}.{minor}', major=major, minor=minor))
    if source and source != "plasmashell --version":
        note(tr('Plasma version source: {source}', source=tr(source)))
    if (major, minor) < _MIN_PLASMA:
        fail(tr('Plasma {major}.{minor} is too old — need {value3}.{value4}+ for the compiled plasmoids to load', major=major, minor=minor, value3=_MIN_PLASMA[0], value4=_MIN_PLASMA[1]))
        return False
    ok(tr('Plasma {major}.{minor} meets the {value3}.{value4}+ minimum', major=major, minor=minor, value3=_MIN_PLASMA[0], value4=_MIN_PLASMA[1]))
    return True


# ── KDE config tools ────────────────────────────────────────────────


def _check_kde_config_tools() -> bool:
    """One clear preflight failure instead of N scattered kw_write()
    warns when kwriteconfig6 / kreadconfig6 are missing."""
    missing = []
    for binary in ("kwriteconfig6", "kreadconfig6"):
        if not shutil.which(binary):
            missing.append(binary)
    if missing:
        fail(tr("missing: {value1} — install plasma-workspace (or your distro's equivalent — same package that brings kded6 / plasmashell)", value1=', '.join(missing)))
        return False
    ok(tr('kwriteconfig6 + kreadconfig6 present'))
    return True


# ── DBus session bus ────────────────────────────────────────────────


def _check_dbus_session() -> bool:
    """Without a session bus the install succeeds but Plasma silently
    needs a re-login to show the theme — fail loudly instead."""
    addr = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    if not addr:
        # Some sudo configs strip the address; a socket at
        # $XDG_RUNTIME_DIR/bus proves the bus is up (the installer recovers
        # the address from that socket without assuming an init system).
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
        if runtime_dir and Path(runtime_dir, "bus").exists():
            ok(tr('DBus session bus reachable via XDG_RUNTIME_DIR/bus'))
            return True
        fail(tr("DBus session bus not reachable — DBUS_SESSION_BUS_ADDRESS is unset and $XDG_RUNTIME_DIR/bus doesn't exist. Live theme apply will fail; log out, log back in, then re-run."))
        return False
    ok(tr('DBus session bus reachable ({value1})', value1=addr.split(',')[0]))
    return True


# ── kded6 running ───────────────────────────────────────────────────


def _check_kded_running() -> bool:
    """kded6 hosts the live-apply services; when it's down, live
    ``plasma-apply-lookandfeel`` calls succeed but silently no-op."""
    if not shutil.which("pgrep"):
        warn(tr('pgrep not on PATH — skipping kded6 health check (install procps-ng to enable)'))
        return True
    try:
        res = subprocess.run(
            ["pgrep", "-x", "kded6"],
            check=False, capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        warn(tr('could not probe kded6 ({exc}) — skipping', exc=exc))
        return True
    if res.returncode != 0:
        warn(tr('kded6 is not running — live theme apply may silently no-op. After install: `kquitapp6 kded6 && kded6 &` (or log out and back in).'))
        return True
    ok(tr('kded6 is running'))
    return True


# ── disk space ──────────────────────────────────────────────────────


# Artefacts total ~10 MB on /usr, ~20 MB in $HOME; margins are generous.
_MIN_FREE_USR_MB = 50
_MIN_FREE_HOME_MB = 100


def _check_disk_space() -> bool:
    """Bail loudly now rather than fail mid-stream and leave the
    desktop half-themed."""
    try:
        qt_dir = qt6_plugins_dir()
    except Qt6PathsMissing:
        # Step 3 already failed with a hint; nothing useful to add.
        warn(tr('disk space probe skipped — Qt6 plugin dir unknown'))
        return True

    # Walk up to the nearest existing parent (leaf may not exist yet).
    probe = qt_dir
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        usr_free_mb = shutil.disk_usage(str(probe)).free // (1024 * 1024)
    except OSError as exc:
        warn(tr('could not stat {probe} for free space ({exc}) — skipping', probe=probe, exc=exc))
        return True
    print(tr('  free on {probe}: {usr_free_mb} MB', probe=probe, usr_free_mb=usr_free_mb))

    home_probe = _home()
    while not home_probe.exists() and home_probe != home_probe.parent:
        home_probe = home_probe.parent
    try:
        home_free_mb = shutil.disk_usage(str(home_probe)).free // (1024 * 1024)
    except OSError as exc:
        warn(tr('could not stat {home_probe} for free space ({exc}) — skipping', home_probe=home_probe, exc=exc))
        return True
    print(tr('  free on {home_probe}: {home_free_mb} MB', home_probe=home_probe, home_free_mb=home_free_mb))

    all_ok = True
    if usr_free_mb < _MIN_FREE_USR_MB:
        fail(tr('only {usr_free_mb} MB free on {probe} — need at least {_MIN_FREE_USR_MB} MB for compiled plasmoids + KWin effect', usr_free_mb=usr_free_mb, probe=probe, _MIN_FREE_USR_MB=_MIN_FREE_USR_MB))
        all_ok = False
    if home_free_mb < _MIN_FREE_HOME_MB:
        fail(tr('only {home_free_mb} MB free on {home_probe} — need at least {_MIN_FREE_HOME_MB} MB for icons / wallpapers / themes', home_free_mb=home_free_mb, home_probe=home_probe, _MIN_FREE_HOME_MB=_MIN_FREE_HOME_MB))
        all_ok = False
    if all_ok:
        ok(tr('disk space OK ({usr_free_mb} MB on system, {home_free_mb} MB on $HOME)', usr_free_mb=usr_free_mb, home_free_mb=home_free_mb))
    return all_ok


_PLASMOID_DIR = OFFLINE_DIR / "plasmoids"
_LAYOUT_JS = OFFLINE_DIR / "layouts/mac-tahoe.js"


def _read_kplugin_id(metadata: Path) -> str | None:
    try:
        data = json.loads(metadata.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    plugin = data.get("KPlugin")
    if not isinstance(plugin, dict):
        return None
    pid = plugin.get("Id")
    return pid if isinstance(pid, str) else None


def _check_plasmoid_ids() -> bool:
    if not _PLASMOID_DIR.is_dir():
        warn(tr('plasmoids dir missing: {_PLASMOID_DIR}', _PLASMOID_DIR=_PLASMOID_DIR))
        return True

    layout_text = ""
    if _LAYOUT_JS.is_file():
        try:
            layout_text = _LAYOUT_JS.read_text()
        except OSError:
            layout_text = ""

    all_ok = True
    for plasmoid_dir in sorted(_PLASMOID_DIR.iterdir()):
        if not plasmoid_dir.is_dir():
            continue
        metadata = plasmoid_dir / "metadata.json"
        if not metadata.is_file():
            continue
        plugin_id = _read_kplugin_id(metadata)
        dir_name = plasmoid_dir.name

        if plugin_id is None:
            fail(tr('{dir_name}: metadata.json missing KPlugin.Id', dir_name=dir_name))
            all_ok = False
            continue

        if plugin_id != dir_name:
            fail(tr('{dir_name}: dir name does not match metadata.Id ({plugin_id})', dir_name=dir_name, plugin_id=plugin_id))
            all_ok = False
            continue

        ok(tr('{dir_name}: Id={plugin_id}', dir_name=dir_name, plugin_id=plugin_id))

        if layout_text and plugin_id not in layout_text:
            # Optional / user-placed plasmoids aren't in the layout —
            # note, don't fail.
            print(tr('       └ not referenced in layout JS (optional)'))
    return all_ok


def run_preflight(op: str = "install") -> bool:
    """Returns True only if every hard-fail check passes (kded6 and
    missing-path disk probes are soft — warn only). The plasmoid ID
    check is skipped on uninstall: an ID drift can't ship from there."""
    step('Preflight')
    note(tr('Verifies sudo, paths, Qt6, KDE version, config tools, DBus, kded6, disk space, plasmoid IDs'))

    total = 9 if op == "install" else 8
    n = 0

    n += 1; print(tr('  ── {n}/{total} sudo escalation hop ───', n=n, total=total))
    sudo_ok = _check_sudo_escalation()
    print()

    n += 1; print(tr('  ── {n}/{total} destination paths ─────', n=n, total=total))
    paths_ok = _check_paths()
    print()

    n += 1; print(tr('  ── {n}/{total} Qt6 plugin search ─────', n=n, total=total))
    qt_ok = _check_qt_paths()
    print()

    n += 1; print(tr('  ── {n}/{total} KDE Plasma version ────', n=n, total=total))
    plasma_ok = _check_plasma_version()
    print()

    n += 1; print(tr('  ── {n}/{total} KDE config tools ──────', n=n, total=total))
    kde_tools_ok = _check_kde_config_tools()
    print()

    n += 1; print(tr('  ── {n}/{total} DBus session bus ──────', n=n, total=total))
    dbus_ok = _check_dbus_session()
    print()

    n += 1; print(tr('  ── {n}/{total} kded6 health (soft) ───', n=n, total=total))
    _check_kded_running()  # soft — never blocks install
    print()

    n += 1; print(tr('  ── {n}/{total} disk space ────────────', n=n, total=total))
    disk_ok = _check_disk_space()
    print()

    if op == "install":
        n += 1; print(tr('  ── {n}/{total} plasmoid ID consistency ─', n=n, total=total))
        ids_ok = _check_plasmoid_ids()
    else:
        ids_ok = True

    return (sudo_ok and paths_ok and qt_ok and plasma_ok
            and kde_tools_ok and dbus_ok and disk_ok and ids_ok)
