"""Preflight: prove the basics work BEFORE any install/uninstall step
touches disk. Nine fail-fast checks, in order, all visible to the user
(see run_preflight; documented in AGENTS.md)."""

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
        fail("real UID is not root — sudo not active (run: sudo ./install)")
        return False

    if os.geteuid() == 0:
        warn("running as effective root — privilege drop did not happen")

    from steps._helpers import _as_root

    try:
        probe_dir = qt6_plugins_dir()
    except Qt6PathsMissing as exc:
        fail(str(exc))
        return False

    probe = probe_dir / f".mttkde-preflight-{os.getpid()}"
    print(f"  probe path: {probe}")
    try:
        with _as_root():
            probe_dir.mkdir(parents=True, exist_ok=True)
            probe.write_text("ok\n")
            content = probe.read_text()
            probe.unlink()
        if content != "ok\n":
            fail(f"sudo hop wrote {content!r}, expected 'ok\\n'")
            return False
    except OSError as exc:
        fail(f"sudo hop failed ({exc.__class__.__name__}: {exc})")
        return False
    except PermissionError as exc:
        fail(f"sudo hop denied ({exc})")
        return False
    ok(f"sudo hop ok — wrote, read, removed {probe.name}")
    return True


# Resolved per call — a module-global cache leaked monkeypatched $HOME
# across pytest boundaries. Indirection kept so tests can patch _home().
_HOME: Path | None = None


def _home() -> Path:
    return _HOME if _HOME is not None else Path.home()


def _allowed_roots() -> tuple[re.Pattern, ...]:
    home = re.escape(str(_home()))
    # Qt roots come from qmake6 so nonstandard libdirs (Gentoo /usr/lib64,
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
        re.compile(rf"^{home}/(\.local|\.config|\.cache)(/|$)"),
        *qt_patterns,
        re.compile(r"^/etc/sddm\.conf\.d(/|$)"),
        re.compile(r"^/etc/plymouth(/|$)"),
        re.compile(r"^/usr/share/(kwin|licenses|locale|sounds|plasma|plymouth|wallpapers)(/|$)"),
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
        return "outside allowed roots ($HOME, Qt6 plugin/QML dirs from qmake6, /etc/sddm.conf.d, /etc/plymouth, /usr/share)"
    return None


def _enumerate_destinations() -> list[tuple[str, Path]]:
    """Known install destinations per step module. Imported lazily so
    module-level ``Path.home()`` runs AFTER the privilege drop."""
    from steps import acrylic_glass, globalmenu, plasmoids, rounded_corners

    dests: list[tuple[str, Path]] = [
        ("globalmenu .so", globalmenu.DEST_SO),
        ("globalmenu QML module", globalmenu.DEST_QML_DIR),
        ("plasmoids share dir", plasmoids.DEST_DIR),
        ("taskmanager .so", plasmoids.TASKMANAGER_DEST_SO),
        ("taskmanager QML module", plasmoids.TASKMANAGER_DEST_QML),
        ("acrylic-glass plugin dir", acrylic_glass._plugin_dir()),
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
        fail("Qt6 installation paths not found — cannot verify install "
             f"destinations. Install qmake6 with: {qt6_install_hint()}")
        return False
    for label, path in dests:
        reason = _validate_path(path)
        if reason is None:
            ok(f"{label}: {path}")
        else:
            fail(f"{label}: {path} ({reason})")
            all_ok = False
    return all_ok


def _check_qt_paths() -> bool:
    """Cross-check every compiled-step destination against qmake6's
    reported plugin / QML dirs so a hardcoded libdir can't regress past
    the distro layer — Gentoo reports /usr/lib64 while others report /usr/lib."""
    try:
        plugins = qt6_plugins_dir()
        qml = qt6_qml_dir()
    except Qt6PathsMissing as exc:
        fail(str(exc))
        return False

    from steps import acrylic_glass, globalmenu, plasmoids, rounded_corners
    qt_destinations = [
        ("globalmenu .so", globalmenu.DEST_SO, plugins),
        ("globalmenu QML module", globalmenu.DEST_QML_DIR, qml),
        ("taskmanager .so", plasmoids.TASKMANAGER_DEST_SO, plugins),
        ("taskmanager QML module", plasmoids.TASKMANAGER_DEST_QML, qml),
        ("acrylic-glass plugin dir", acrylic_glass._plugin_dir(), plugins),
        ("rounded-corners plugin dir", rounded_corners._plugin_dir(), plugins),
    ]
    cross_ok = True
    for label, dest, expected_root in qt_destinations:
        try:
            dest.relative_to(expected_root)
        except ValueError:
            fail(f"{label}: {dest} is NOT under qmake6's {expected_root} — "
                 f"hardcoded libdir slipped past the distro layer")
            cross_ok = False
    if not cross_ok:
        return False

    print(f"  Qt plugins: {plugins}")
    print(f"  Qt qml:     {qml}")
    ok(f"Qt plugin path discovered: {plugins}")
    ok(f"Qt QML path discovered: {qml}")
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
            last_error = f"{label} timed out"
            continue
        except OSError as exc:
            last_error = f"{label} failed: {exc}"
            continue
        out = (res.stdout or res.stderr or "").strip()
        if not out:
            last_error = f"{label} returned nothing"
            continue
        match = _PLASMA_VERSION_RE.search(out)
        if match:
            return match, label
        last_error = f"{label} output unparseable: {out!r}"

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
        fail("plasmashell not on PATH — KDE Plasma is not installed")
        return False
    match, source = _probe_plasma_version()
    if not match:
        fail(source or "could not detect Plasma version")
        return False
    major = int(match.group(1))
    minor = int(match.group(2))
    print(f"  plasmashell {major}.{minor}")
    if source and source != "plasmashell --version":
        note(f"Plasma version source: {source}")
    if (major, minor) < _MIN_PLASMA:
        fail(f"Plasma {major}.{minor} is too old — need "
             f"{_MIN_PLASMA[0]}.{_MIN_PLASMA[1]}+ for the compiled "
             "plasmoids to load")
        return False
    ok(f"Plasma {major}.{minor} meets the {_MIN_PLASMA[0]}.{_MIN_PLASMA[1]}+ minimum")
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
        fail(f"missing: {', '.join(missing)} — install plasma-workspace "
             "(or your distro's equivalent — same package that brings "
             "kded6 / plasmashell)")
        return False
    ok("kwriteconfig6 + kreadconfig6 present")
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
            ok("DBus session bus reachable via XDG_RUNTIME_DIR/bus")
            return True
        fail("DBus session bus not reachable — DBUS_SESSION_BUS_ADDRESS "
             "is unset and $XDG_RUNTIME_DIR/bus doesn't exist. Live "
             "theme apply will fail; log out, log back in, then re-run.")
        return False
    ok(f"DBus session bus reachable ({addr.split(',')[0]})")
    return True


# ── kded6 running ───────────────────────────────────────────────────


def _check_kded_running() -> bool:
    """kded6 hosts the live-apply services; when it's down, live
    ``plasma-apply-lookandfeel`` calls succeed but silently no-op."""
    if not shutil.which("pgrep"):
        warn("pgrep not on PATH — skipping kded6 health check "
             "(install procps-ng to enable)")
        return True
    try:
        res = subprocess.run(
            ["pgrep", "-x", "kded6"],
            check=False, capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        warn(f"could not probe kded6 ({exc}) — skipping")
        return True
    if res.returncode != 0:
        warn("kded6 is not running — live theme apply may silently "
             "no-op. After install: `kquitapp6 kded6 && kded6 &` (or "
             "log out and back in).")
        return True
    ok("kded6 is running")
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
        warn("disk space probe skipped — Qt6 plugin dir unknown")
        return True

    # Walk up to the nearest existing parent (leaf may not exist yet).
    probe = qt_dir
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        usr_free_mb = shutil.disk_usage(str(probe)).free // (1024 * 1024)
    except OSError as exc:
        warn(f"could not stat {probe} for free space ({exc}) — skipping")
        return True
    print(f"  free on {probe}: {usr_free_mb} MB")

    home_probe = _home()
    while not home_probe.exists() and home_probe != home_probe.parent:
        home_probe = home_probe.parent
    try:
        home_free_mb = shutil.disk_usage(str(home_probe)).free // (1024 * 1024)
    except OSError as exc:
        warn(f"could not stat {home_probe} for free space ({exc}) — skipping")
        return True
    print(f"  free on {home_probe}: {home_free_mb} MB")

    all_ok = True
    if usr_free_mb < _MIN_FREE_USR_MB:
        fail(f"only {usr_free_mb} MB free on {probe} — need at least "
             f"{_MIN_FREE_USR_MB} MB for compiled plasmoids + KWin effect")
        all_ok = False
    if home_free_mb < _MIN_FREE_HOME_MB:
        fail(f"only {home_free_mb} MB free on {home_probe} — need at "
             f"least {_MIN_FREE_HOME_MB} MB for icons / wallpapers / "
             "themes")
        all_ok = False
    if all_ok:
        ok(f"disk space OK ({usr_free_mb} MB on system, "
           f"{home_free_mb} MB on $HOME)")
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
        warn(f"plasmoids dir missing: {_PLASMOID_DIR}")
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
            fail(f"{dir_name}: metadata.json missing KPlugin.Id")
            all_ok = False
            continue

        if plugin_id != dir_name:
            fail(f"{dir_name}: dir name does not match metadata.Id "
                 f"({plugin_id})")
            all_ok = False
            continue

        ok(f"{dir_name}: Id={plugin_id}")

        if layout_text and plugin_id not in layout_text:
            # Optional / user-placed plasmoids aren't in the layout —
            # note, don't fail.
            print(f"       └ not referenced in layout JS (optional)")
    return all_ok


def run_preflight(op: str = "install") -> bool:
    """Returns True only if every hard-fail check passes (kded6 and
    missing-path disk probes are soft — warn only). The plasmoid ID
    check is skipped on uninstall: an ID drift can't ship from there."""
    step("Preflight")
    note("Verifies sudo, paths, Qt6, KDE version, config tools, DBus, "
         "kded6, disk space, plasmoid IDs")

    total = 9 if op == "install" else 8
    n = 0

    n += 1; print(f"  ── {n}/{total} sudo escalation hop ───")
    sudo_ok = _check_sudo_escalation()
    print()

    n += 1; print(f"  ── {n}/{total} destination paths ─────")
    paths_ok = _check_paths()
    print()

    n += 1; print(f"  ── {n}/{total} Qt6 plugin search ─────")
    qt_ok = _check_qt_paths()
    print()

    n += 1; print(f"  ── {n}/{total} KDE Plasma version ────")
    plasma_ok = _check_plasma_version()
    print()

    n += 1; print(f"  ── {n}/{total} KDE config tools ──────")
    kde_tools_ok = _check_kde_config_tools()
    print()

    n += 1; print(f"  ── {n}/{total} DBus session bus ──────")
    dbus_ok = _check_dbus_session()
    print()

    n += 1; print(f"  ── {n}/{total} kded6 health (soft) ───")
    _check_kded_running()  # soft — never blocks install
    print()

    n += 1; print(f"  ── {n}/{total} disk space ────────────")
    disk_ok = _check_disk_space()
    print()

    if op == "install":
        n += 1; print(f"  ── {n}/{total} plasmoid ID consistency ─")
        ids_ok = _check_plasmoid_ids()
    else:
        ids_ok = True

    return (sudo_ok and paths_ok and qt_ok and plasma_ok
            and kde_tools_ok and dbus_ok and disk_ok and ids_ok)
