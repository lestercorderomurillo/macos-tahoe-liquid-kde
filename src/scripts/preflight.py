"""Preflight: prove the basics work BEFORE any install/uninstall step
touches disk.

Four checks, in order, all visible to the user:

1. **Sudo escalation hop.** The CLI bailed unless invoked via
   ``sudo ./install`` (real UID 0) and then dropped effective UID to
   ``SUDO_USER``. Here we exercise the round trip: hop back to root via
   ``_as_root()``, touch a probe under the Qt6 plugin dir reported by
   ``qmake6`` (``paths.qt6_plugins_dir()``), drop back. Catches read-
   only ``/usr``, missing dir, sandbox restrictions, and broken sudo
   configs *before* a single artefact lands.

2. **Destination paths.** Walk every step's known destination, print it,
   regex-validate against the allowed roots (``$HOME``, the Qt6 plugin
   / QML dirs discovered from ``qmake6``, ``/etc/sddm.conf.d``).
   Rejects ``/root/`` (means privilege drop didn't happen), ``//``,
   ``..``, and stray ``/tmp/`` destinations.

3. **Qt6 plugin search path.** ``qmake6 -query QT_INSTALL_PLUGINS`` is
   the directory Qt6 actually walks at runtime. Our compiled ``.so``
   destinations must sit inside it. v0.8.4-0.8.6 shipped to
   ``~/.local/lib/qt6/`` which isn't on Qt's path — Plasma silently
   ignored the dock and global menu. This check makes that regression
   impossible to ship again.

4. **Plasmoid ID consistency.** For each plasmoid in
   ``src/offline/plasmoids/``, the directory name, the metadata.json
   ``KPlugin.Id``, and the layout JS ``addWidget`` reference all have
   to spell the same plugin id. A mismatch means plasmashell either
   loads the wrong package or fails to find it.
"""

import json
import os
import re
from pathlib import Path

from log import fail, note, ok, step, warn
from distro import Qt6PathsMissing, qt6_plugins_dir, qt6_qml_dir
from paths import OFFLINE_DIR


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


_HOME = None


def _home() -> Path:
    global _HOME
    if _HOME is None:
        _HOME = Path.home()
    return _HOME


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
            # optional / user-placed), so warn rather than fail.
            print(f"     not referenced in layout JS (optional)")
    return all_ok


def run_preflight(op: str = "install") -> bool:
    """Run all preflight checks. Returns ``True`` only if everything
    passes — caller bails out otherwise.

    Skips the plasmoid ID consistency check on uninstall (uninstall
    doesn't reinstall packages, so an ID drift can't ship from there).
    """
    step("Preflight")
    note("Verifies sudo escalation, paths, Qt6 search, and plasmoid IDs")

    print(f"  ── 1/4 sudo escalation hop ───")
    sudo_ok = _check_sudo_escalation()
    print()

    print(f"  ── 2/4 destination paths ─────")
    paths_ok = _check_paths()
    print()

    print(f"  ── 3/4 Qt6 plugin search ─────")
    qt_ok = _check_qt_paths()
    print()

    print(f"  ── 4/4 plasmoid ID consistency ─")
    if op == "install":
        ids_ok = _check_plasmoid_ids()
    else:
        ok("skipped on uninstall")
        ids_ok = True

    return sudo_ok and paths_ok and qt_ok and ids_ok
