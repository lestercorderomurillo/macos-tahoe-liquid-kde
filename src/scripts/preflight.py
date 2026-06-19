"""Preflight: prove the basics work BEFORE any install/uninstall step
touches disk.

Nine checks, in order, all visible to the user:

1. **Sudo escalation hop.** The CLI bailed unless invoked via
   ``sudo ./install`` (real UID 0) and then dropped effective UID to
   ``SUDO_USER``. Exercise the round trip: hop back to root via
   ``_as_root()``, touch a probe under the Qt6 plugin dir reported by
   ``qmake6`` (``distro.qt6_plugins_dir()``), drop back. Catches read-
   only ``/usr``, missing dir, sandbox restrictions, and broken sudo
   configs *before* a single artefact lands.

2. **Destination paths.** Walk every step's known destination, print it,
   regex-validate against the allowed roots (``$HOME``, the Qt6 plugin
   / QML dirs discovered from ``qmake6``, ``/etc/sddm.conf.d``).

3. **Qt6 plugin search path.** ``qmake6 -query QT_INSTALL_PLUGINS`` is
   the directory Qt6 actually walks at runtime. Our compiled ``.so``
   destinations must sit inside it. v0.8.4-0.8.6 shipped to
   ``~/.local/lib/qt6/`` which isn't on Qt's path — Plasma silently
   ignored the dock and global menu. Make that regression impossible.

4. **KDE Plasma version.** Confirm ``plasmashell --version`` reports
   ≥6.6. The compiled plasmoids link against Plasma 6.6+ headers, so
   anything older silently fails to load with no useful error in the
   installer's output.

5. **KDE config tools.** ``kwriteconfig6`` and ``kreadconfig6`` are the
   only way the installer writes / reads kdeglobals. v0.15.5 made
   each step warn when these are missing, but having the preflight
   bail with a single actionable message is friendlier than 12 warns
   spread across the install run.

6. **DBus session bus.** Live theme apply, KWin reconfigure, plasma-
   apply-lookandfeel — all of them need a session bus. Without it the
   install completes but Plasma never reloads the new theme until the
   user logs out and back in (which they won't realise they need to
   do, because the installer reported success).

7. **kded6 running.** kded6 hosts the lookandfeelautoswitcher and the
   notify-on-config-change service the install relies on. If it's
   crashed (rare but happens after kded plugin updates), live applies
   silently no-op.

8. **Disk space for /usr writes.** The compiled .so / QML modules
   total ~5-10 MB. If /usr is full or quota'd, the install fails
   mid-stream and leaves the system half-themed. Better to fail
   loudly at preflight.

9. **Plasmoid ID consistency.** For each plasmoid in
   ``src/offline/plasmoids/``, the directory name, the metadata.json
   ``KPlugin.Id``, and the layout JS ``addWidget`` reference all have
   to spell the same plugin id. Skipped on uninstall.
"""

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


# Resolved per-call, not cached. The previous module-global cache
# leaked across pytest test boundaries: a test that legitimately
# set $HOME via monkeypatch (sandbox fixture in conftest.py) would
# prime _HOME to a tmpdir, monkeypatch would restore $HOME on
# teardown but the module-global stayed, and the next test calling
# _home() read the stale tmpdir. The cost of recomputing is a
# single os.environ.get("HOME") — not worth the test-ordering
# fragility. Keep the indirection so tests can still
# monkeypatch.setattr(preflight, "_home", lambda: Path("/root"))
# to exercise the /root-is-the-real-home branch.
_HOME: Path | None = None


def _home() -> Path:
    return _HOME if _HOME is not None else Path.home()


def _allowed_roots() -> tuple[re.Pattern, ...]:
    home = re.escape(str(_home()))
    # Qt6 plugin / QML roots come from qmake6 so distros that put them
    # under /usr/lib64/qt6 (Gentoo, openSUSE multilib) or
    # /usr/lib/x86_64-linux-gnu/qt6 (Debian / Ubuntu multiarch) validate
    # without a hand-maintained list of distro libdirs.
    try:
        qt_plugins = re.escape(str(qt6_plugins_dir()))
        qt_qml = re.escape(str(qt6_qml_dir()))
        qt_patterns = (
            re.compile(rf"^{qt_plugins}(/|$)"),
            re.compile(rf"^{qt_qml}(/|$)"),
        )
    except Qt6PathsMissing:
        # The Qt path check (step 3/4) reports the missing qmake6 with a
        # distro hint; here we just refuse to validate /usr/lib/qt6 by
        # convention so we don't accidentally green-light writes that
        # land outside the real Qt search path.
        qt_patterns = ()
    return (
        re.compile(rf"^{home}/(\.local|\.config|\.cache)(/|$)"),
        *qt_patterns,
        re.compile(r"^/etc/sddm\.conf\.d(/|$)"),
        re.compile(r"^/etc/plymouth(/|$)"),
        re.compile(r"^/usr/share/(sounds|plasma|plymouth|wallpapers)(/|$)"),
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
    # /root is forbidden ONLY when it isn't the real user's home dir.
    # In production, sudo drops effective UID to SUDO_USER so Path.home()
    # points at /home/<user>; a path starting with /root then means the
    # sudo drop didn't apply and writes would land in root's home.
    # In a container (or any single-user-as-root setup), root *is* the
    # real user — its home is /root and writing there is legitimate.
    home = str(_home())
    if s.startswith("/root/") or s == "/root":
        if home != "/root" and not s.startswith(home + "/"):
            return "leaks /root home"
    if not any(pat.search(s) for pat in _allowed_roots()):
        return "outside allowed roots ($HOME, Qt6 plugin/QML dirs from qmake6, /etc/sddm.conf.d, /etc/plymouth, /usr/share)"
    return None


def _enumerate_destinations() -> list[tuple[str, Path]]:
    """Collect known install destinations from each step module by
    asking the module directly. Modules that don't expose destinations
    (data-only steps, fonts, etc.) just don't show up here.

    We import lazily so module-level ``Path.home()`` evaluations happen
    AFTER the privilege drop (HOME is already pointed at the real user
    by the CLI at this point)."""
    from steps import acrylic_glass, globalmenu, plasmoids

    dests: list[tuple[str, Path]] = [
        ("globalmenu .so", globalmenu.DEST_SO),
        ("globalmenu QML module", globalmenu.DEST_QML_DIR),
        ("plasmoids share dir", plasmoids.DEST_DIR),
        ("taskmanager .so", plasmoids.TASKMANAGER_DEST_SO),
        ("taskmanager QML module", plasmoids.TASKMANAGER_DEST_QML),
        ("acrylic-glass plugin dir", acrylic_glass._plugin_dir()),
    ]
    return dests


def _check_paths() -> bool:
    all_ok = True
    for label, path in _enumerate_destinations():
        reason = _validate_path(path)
        if reason is None:
            ok(f"{label}: {path}")
        else:
            fail(f"{label}: {path} ({reason})")
            all_ok = False
    return all_ok


def _check_qt_paths() -> bool:
    """Confirm qmake6 reported the same Qt6 plugin / QML directories the
    installer will write to. Since v0.15.0 the installer derives both
    destinations from qmake6 itself (see distro.qt6_plugins_dir /
    distro.qt6_qml_dir), so a mismatch here means qmake6 is missing or
    the cached value drifted — not a Plasma-vs-installer disagreement.

    This is the check that catches the v0.14.x Gentoo bug: ``Qt scans
    /usr/lib64/qt6/ but install writes to /usr/lib/qt6/``. With the
    Qt path coming from qmake6 the bug is structurally impossible —
    but we still cross-check every compiled-step destination so a
    future refactor that hardcodes a path can't silently regress past
    the layer."""
    try:
        plugins = qt6_plugins_dir()
        qml = qt6_qml_dir()
    except Qt6PathsMissing as exc:
        fail(str(exc))
        return False

    # Cross-check: every destination that lives under "Qt's libdir" must
    # actually be rooted at qmake6's reported plugin / QML dir. If a
    # step still hardcodes /usr/lib/qt6 and we're on a /usr/lib64 distro,
    # this catches the mismatch before any file lands.
    from steps import acrylic_glass, globalmenu, plasmoids
    qt_destinations = [
        ("globalmenu .so", globalmenu.DEST_SO, plugins),
        ("globalmenu QML module", globalmenu.DEST_QML_DIR, qml),
        ("taskmanager .so", plasmoids.TASKMANAGER_DEST_SO, plugins),
        ("taskmanager QML module", plasmoids.TASKMANAGER_DEST_QML, qml),
        ("acrylic-glass plugin dir", acrylic_glass._plugin_dir(), plugins),
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
    """Confirm plasmashell reports ≥6.6. We compile against Plasma
    6.6+ headers, so an older runtime silently fails to load the
    applets (plasmashell logs at debug level and the user sees an
    empty panel slot).

    Must drop privileges in the child (real UID 0 + effective UID
    SUDO_USER triggers Qt6's setuid guard — ``getuid() != geteuid()``
    aborts with ``FATAL: The application binary appears to be running
    setuid, this is a security hole.`` before reading any args). Use
    ``run_user`` which sets ``preexec_fn=drop_privs_in_child`` so the
    forked child runs as the invoking user with matching real / effective
    / saved UIDs."""
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
    """kwriteconfig6 + kreadconfig6 ship together in plasma-workspace
    on every supported distro. Each step that touches kdeglobals
    already has a `kw_write()` -> `warn()` guard (v0.15.5), but
    surfacing the gap here means one clear error instead of N
    scattered warnings during install."""
    missing = []
    for binary in ("kwriteconfig6", "kreadconfig6"):
        if not shutil.which(binary):
            missing.append(binary)
    if missing:
        # Cross-distro hint via the same mechanism qt6 uses.
        fail(f"missing: {', '.join(missing)} — install plasma-workspace "
             "(or your distro's equivalent — same package that brings "
             "kded6 / plasmashell)")
        return False
    ok("kwriteconfig6 + kreadconfig6 present")
    return True


# ── DBus session bus ────────────────────────────────────────────────


def _check_dbus_session() -> bool:
    """Live theme apply, ``plasma-apply-lookandfeel``, ``KWin
    reconfigure`` — they all dial the session bus. Without it the
    install completes but Plasma never reloads the new theme until
    the user logs out and back in. We don't want the install to
    *silently* require a re-login."""
    addr = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    if not addr:
        # Some sudo configs strip DBUS_SESSION_BUS_ADDRESS. If the
        # bus socket is at the canonical XDG path, accept that as
        # proof the bus is up — the live-apply helpers in steps/
        # already re-discover the address through `systemctl --user
        # show-environment`.
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
    """kded6 hosts lookandfeelautoswitcher (the live-mode-switch
    daemon) and the notify-on-config-change service. If it's not
    running, our live ``plasma-apply-lookandfeel`` calls succeed but
    silently no-op until the user restarts plasma."""
    if not shutil.which("pgrep"):
        # procps not installed — skip rather than fail, since pgrep
        # isn't strictly required for the install.
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
        # Not a hard fail — install can still complete; user just may
        # need to re-login to see the theme.
        return True
    ok("kded6 is running")
    return True


# ── disk space ──────────────────────────────────────────────────────


# .so + QML modules total ~10 MB in production. We require 50 MB free
# as a comfortable margin (the install also writes ~20 MB of icons /
# wallpapers / kvantum theme into $HOME — different filesystem, but
# we check both anyway).
_MIN_FREE_USR_MB = 50
_MIN_FREE_HOME_MB = 100


def _check_disk_space() -> bool:
    """Compiled artefacts go under Qt6's plugin dir (system, root-
    owned). User assets go under $HOME. If either is full, the install
    fails mid-stream and leaves the desktop half-themed. Better to
    bail loud now."""
    try:
        qt_dir = qt6_plugins_dir()
    except Qt6PathsMissing:
        # Step 3 already failed with a hint; nothing useful to add.
        warn("disk space probe skipped — Qt6 plugin dir unknown")
        return True

    # Walk up to the nearest existing parent if the leaf doesn't
    # exist yet (Qt6 plugin dir may be missing on a brand-new system).
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
            # Not every plasmoid is referenced in the layout (some are
            # optional / user-placed), so note rather than fail. The
            # tree-branch glyph ties the note to the ✓ line above it —
            # without it the bare indented line reads as an orphan.
            print(f"       └ not referenced in layout JS (optional)")
    return all_ok


def run_preflight(op: str = "install") -> bool:
    """Run all preflight checks. Returns ``True`` only if every
    hard-fail check passes — caller bails otherwise.

    Some checks are soft (kded6, disk-space-on-missing-paths) and emit
    a warn() without failing the run; they're labelled as "soft" in
    the inline notes.

    Skips the plasmoid ID consistency check on uninstall (uninstall
    doesn't reinstall packages, so an ID drift can't ship from there).
    """
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
