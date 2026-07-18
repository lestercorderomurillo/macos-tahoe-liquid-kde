"""Test suite for MacTahoe Liquid KDE.

What is actually covered:

1. **Static / shape tests** (this directory). Cheap, run in seconds,
   validate file layout, plasmoid ID consistency, regex shape of
   generated configs, the public surface of step modules, and the
   per-distro package-name map. Catch directory-rename / metadata-Id
   drift before it ships. They cannot prove the install works on a
   live KDE session.

2. **Per-distro container matrix** at ``tests/containers/``. One
   Dockerfile per supported distro (arch, cachyos, manjaro, garuda,
   endeavouros, gentoo, fedora, nobara, opensuse). Inside
   each container, ``run_in_container.py`` runs the pytest suite
   against that distro's real Python + Qt6 layout, then probes
   ``distro.package_for(token)`` against the distro's real repo
   metadata. Run with ``./tests/containers/run_matrix.sh``.

What is NOT covered by any layer in this tree:

- The full ``sudo ./install`` → preflight → step loop → uninstall
  pipeline. That needs a live Plasma 6 session, KWin running, KDED
  alive, and is only exercised by the maintainer on bare metal.
- ``find_package(KF6 ...)`` for the C++ plugins (would require
  pulling the full Plasma 6 dev SDK into every container image).
- Live theme-switch DBus calls — preflight has a sudo-hop probe
  but the actual ``plasma-apply-lookandfeel`` step is mocked.
- Journal scans for crash signatures use ``--since "24 hours
  ago"`` and so can flap on unrelated historical events; they are
  symptom guards, not commit-tied regression tests.

When something breaks on a real install that this suite did not
catch, the right answer is usually a new probe in
``tests/containers/run_in_container.py`` (per-distro repo / runtime
behaviour) rather than another mocked sandbox test here.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src" / "scripts"))
sys.path.insert(0, str(REPO / "src" / "installer"))


@pytest.fixture(scope="session")
def repo() -> Path:
    return REPO


@pytest.fixture(scope="session")
def src(repo) -> Path:
    return repo / "src"


@pytest.fixture(scope="session")
def offline(src) -> Path:
    return src / "offline"


@pytest.fixture(scope="session")
def steps_dir(repo) -> Path:
    return repo / "build/steps"


@pytest.fixture
def sandbox(tmp_path, monkeypatch) -> Path:
    """Empty $HOME / $XDG_CONFIG_HOME / $XDG_DATA_HOME under ``tmp_path``.

    GitLab runners (and many CI systems) export XDG_CONFIG_HOME pointing
    at the runner user's real config — without overriding it, every
    sandboxed write escapes the sandbox and assertions read stale data.
    """
    home = tmp_path / "home"
    cfg = home / ".config"
    data = home / ".local/share"
    for d in (home, cfg, data, home / ".cache",
              data / "color-schemes"):
        d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    return home


@pytest.fixture
def seeded_color_schemes(sandbox, offline) -> Path:
    """Sandbox + the two MacTahoe .colors files dropped into XDG_DATA_HOME."""
    target = sandbox / ".local/share/color-schemes"
    for variant in ("Light", "Dark"):
        src = offline / "color-schemes" / f"MacTahoeLiquidKde{variant}.colors"
        if src.is_file():
            shutil.copy2(src, target / src.name)
    return sandbox


def ini_get(file: Path, section: str, key: str) -> str:
    """Read an INI value the way bash _ini_get did, including ``\\x5d\\x5b`` decoding."""
    if not file.is_file():
        return ""
    current: str | None = None
    for raw in file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip()
        if line.startswith("[") and line.endswith("]"):
            sec = line[1:-1]
            sec = sec.replace("\\x5d", "]").replace("\\x5b", "[")
            sec = sec.replace("\\x5D", "]").replace("\\x5B", "[")
            current = sec
            continue
        if current == section and "=" in line:
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v
    return ""


@pytest.fixture
def ini_reader():
    return ini_get


def seed_breeze_light(sandbox: Path) -> None:
    (sandbox / ".config/kdeglobals").write_text(
        "[General]\n"
        "ColorScheme=BreezeLight\n"
        "Name=Breeze Light\n"
        "\n"
        "[Colors:Button]\n"
        "BackgroundNormal=252,252,252\n"
        "BackgroundAlternate=163,212,250\n"
        "DecorationFocus=61,174,233\n"
        "ForegroundNormal=35,38,41\n"
        "\n"
        "[Colors:Window]\n"
        "BackgroundNormal=239,240,241\n"
        "ForegroundNormal=35,38,41\n"
        "\n"
        "[Colors:View]\n"
        "BackgroundNormal=255,255,255\n"
        "ForegroundNormal=35,38,41\n"
        "\n"
        "[ColorEffects:Disabled]\n"
        "Color=56,56,56\n"
        "ColorAmount=0\n"
        "\n"
        "[KDE]\n"
        "widgetStyle=Breeze\n"
    )


def seed_breeze_dark(sandbox: Path) -> None:
    (sandbox / ".config/kdeglobals").write_text(
        "[General]\n"
        "ColorScheme=BreezeDark\n"
        "Name=Breeze Dark\n"
        "\n"
        "[Colors:Button]\n"
        "BackgroundNormal=49,54,59\n"
        "BackgroundAlternate=77,77,77\n"
        "DecorationFocus=61,174,233\n"
        "ForegroundNormal=239,240,241\n"
        "\n"
        "[Colors:Window]\n"
        "BackgroundNormal=42,46,50\n"
        "ForegroundNormal=239,240,241\n"
        "\n"
        "[Colors:View]\n"
        "BackgroundNormal=35,38,41\n"
        "ForegroundNormal=239,240,241\n"
    )


@pytest.fixture
def seed_breeze():
    return type("seed", (), {"light": seed_breeze_light, "dark": seed_breeze_dark})


@pytest.fixture
def kwriteconfig_required():
    if not shutil.which("kwriteconfig6"):
        pytest.skip("kwriteconfig6 not available")


def has_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None


_SESSION_JOURNAL_CURSOR: str | None = None


def _capture_session_journal_cursor() -> str | None:
    """Snapshot the user journal's current cursor at pytest session
    start. Returned cursor strings are opaque tokens like
    ``s=...;i=...;b=...;m=...;t=...;x=...`` — pass back via
    ``--after-cursor=<token>`` to limit a query to events that came
    AFTER this moment.

    Why we need this: a wall-clock window like
    ``--since "24 hours ago"`` makes the crash-guard tests flap when
    yesterday's unrelated coredump happens to match the regex, and
    makes green runs misleading because they don't prove the
    current commit's plugin ever loaded — only that nothing crashed
    in the last 24h. Anchoring to the session cursor scopes the scan
    to "events during this pytest run", which is what we actually
    want to assert about."""
    if not shutil.which("journalctl"):
        return None
    try:
        res = subprocess.run(
            ["journalctl", "--user", "-n", "1", "--show-cursor",
             "--no-pager", "--output=cat"],
            check=False, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    # Output ends with "-- cursor: <token>" on its own line.
    for line in res.stdout.splitlines():
        s = line.strip()
        if s.startswith("-- cursor:"):
            return s.split(":", 1)[1].strip()
    return None


@pytest.fixture(scope="session", autouse=True)
def _journal_session_cursor():
    """Pin a session-start cursor that journal-scanning tests can
    pass to ``journalctl --after-cursor=...`` so their scans only
    cover events that happened DURING the pytest run."""
    global _SESSION_JOURNAL_CURSOR
    _SESSION_JOURNAL_CURSOR = _capture_session_journal_cursor()
    yield _SESSION_JOURNAL_CURSOR


def journal_session_cursor() -> str | None:
    """Public accessor — test modules call this to read the cursor
    captured at session start without importing the module global."""
    return _SESSION_JOURNAL_CURSOR


@pytest.fixture(autouse=True)
def _reset_preflight_home_cache():
    """Guarantee preflight._HOME starts every test at None.

    The slot (drained per call, but kept as an override so tests can
    pin a fake home) can leak across tests: the sandbox fixture's
    monkeypatch of $HOME primes _HOME to a tmpdir, and on teardown
    $HOME is restored but the module global is not.
    A later test (test_check_paths_passes_for_production_destinations)
    then reads the stale tmpdir and rejects a legitimate production
    destination. Reset before AND after so neither a careless test
    nor a careless future fixture can poison the next case."""
    import preflight
    preflight._HOME = None
    yield
    preflight._HOME = None


# Binaries we shim with no-ops for any test that invokes step code in a
# subprocess (where Python-level monkeypatching can't reach). Each is one
# that has been observed to escape the sandbox at least once:
#   systemctl               — disables the maintainer's live theme timer
#   kvantummanager          — flips the live Kvantum theme
#   gsettings               — writes to dconf (no XDG sandboxing possible)
#   plasma-apply-*          — talks to live plasmashell over DBus
#   kbuildsycoca6           — rebuilds the live KDE service cache
LIVE_SHIM_BINARIES = (
    "systemctl",
    "kvantummanager",
    "gsettings",
    "plasma-apply-lookandfeel",
    "plasma-apply-wallpaperimage",
    "plasma-apply-cursortheme",
    "kbuildsycoca6",
)


def make_live_shim_dir(tmp_path: Path) -> Path:
    """Create a dir of no-op shims for LIVE_SHIM_BINARIES, suitable for
    prepending to PATH in a subprocess. The shim logs each invocation to
    ``calls.log`` in the same dir so tests can assert ``foo --user`` was
    actually reached (catches the case where a future regression bypasses
    PATH with an absolute path)."""
    shim_dir = tmp_path / "shimbin"
    shim_dir.mkdir(exist_ok=True)
    log = shim_dir / "calls.log"
    for name in LIVE_SHIM_BINARIES:
        shim = shim_dir / name
        shim.write_text(
            f'#!/bin/sh\nprintf "%s %s\\n" "{name}" "$*" >> "{log}"\nexit 0\n'
        )
        shim.chmod(0o755)
    return shim_dir


# ── live-state safety net (session-scoped) ───────────────────────────────
#
# Tests should never modify the maintainer's live KDE/systemd state, but the
# sandbox fixture only redirects HOME / XDG_*. Anything that contacts the
# user systemd manager (``systemctl --user``), Kvantum config, dconf, or
# uses an absolute path bypasses the sandbox and can silently disable the
# maintainer's ``mac-tahoe-liquid-kde-theme.timer``.
#
# This fixture snapshots a hand-picked set of live files + systemctl unit
# state at session start, restores them at session end if they drifted,
# and reports the drift loudly so the offending test can't hide.

_LIVE_FILES = (
    ".config/kdeglobals",
    ".config/plasmarc",
    ".config/kwinrc",
    ".config/kcminputrc",
    ".config/Kvantum/kvantum.kvconfig",
    ".config/gtk-3.0/settings.ini",
    ".config/gtk-4.0/settings.ini",
    ".gtkrc-2.0",
    ".config/plasma-org.kde.plasma.desktop-appletsrc",
)

_LIVE_UNITS = (
    "mac-tahoe-liquid-kde-theme.timer",
    "mac-tahoe-liquid-kde-theme.service",
    "mac-tahoe-liquid-kde-theme-apply.service",
)


def _snapshot_file(path: Path) -> tuple[str, bytes | None]:
    try:
        return (str(path), path.read_bytes() if path.is_file() else None)
    except OSError:
        return (str(path), None)


def _extract_wallpaper_path(appletsrc_bytes: bytes) -> str:
    """Parse the first ``Image=...`` value out of a plasma appletsrc dump.
    Returns the wallpaper path (file:// URL or plain path) or '' if none.
    Used to re-issue the wallpaper apply after restoring a drifted file."""
    for raw in appletsrc_bytes.decode("utf-8", errors="replace").splitlines():
        line = raw.strip()
        if line.startswith("Image="):
            val = line[len("Image="):]
            if val.startswith("file://"):
                val = val[len("file://"):]
            return val
    return ""


def _snapshot_unit(unit: str) -> dict[str, str]:
    if not shutil.which("systemctl"):
        return {}

    def q(*verb: str) -> str:
        try:
            return subprocess.run(
                ["systemctl", "--user", *verb, unit],
                check=False, capture_output=True, text=True, timeout=5,
            ).stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            return ""

    return {"enabled": q("is-enabled"), "active": q("is-active")}


def _restore_file(path: Path, original: bytes | None) -> tuple[bool, str]:
    """Return (drifted, short-summary-of-diff)."""
    current = path.read_bytes() if path.is_file() else None
    if current == original:
        return (False, "")
    if original is None:
        summary = f"+created ({len(current or b'')} bytes)"
    elif current is None:
        summary = f"-deleted ({len(original)} bytes)"
    else:
        diff = len(current) - len(original)
        summary = f"{diff:+d} bytes"
        # Dump the pre/post pair to /tmp so the maintainer can diff them.
        dump = Path("/tmp") / f"mttkde-leak-{path.name}"
        try:
            dump.with_suffix(".before").write_bytes(original)
            dump.with_suffix(".after").write_bytes(current)
            summary += f" → diff /tmp/mttkde-leak-{path.name}.before .after"
        except OSError:
            pass
    try:
        if original is None:
            if path.is_file():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(original)
        return (True, summary)
    except OSError as exc:
        return (True, f"{summary} (restore failed: {exc})")


def _restore_unit(unit: str, original: dict[str, str]) -> bool:
    if not original or not shutil.which("systemctl"):
        return False
    now = _snapshot_unit(unit)
    drifted = False
    if now.get("enabled") != original.get("enabled"):
        drifted = True
        verb = "enable" if original["enabled"] == "enabled" else "disable"
        subprocess.run(["systemctl", "--user", verb, unit],
                       check=False, capture_output=True, timeout=10)
    if now.get("active") != original.get("active"):
        drifted = True
        verb = "start" if original["active"] == "active" else "stop"
        subprocess.run(["systemctl", "--user", verb, unit],
                       check=False, capture_output=True, timeout=10)
    return drifted


@pytest.fixture(autouse=True, scope="session")
def _live_state_safety_net(request):
    """Snapshot live KDE/systemd state at session start; restore on teardown.

    Any drift triggers a session-finish printed warning naming the file or
    unit that moved, so an escaping test is loud rather than silent — but
    state is restored either way so the maintainer's desktop doesn't end
    the test session in a half-broken configuration.

    Opt out with ``MAC_TAHOE_SKIP_LIVE_SAFETY_NET=1`` (CI, where there is
    no live session to protect)."""
    if os.environ.get("MAC_TAHOE_SKIP_LIVE_SAFETY_NET") == "1":
        yield
        return

    home = Path.home()
    files_before = [_snapshot_file(home / rel) for rel in _LIVE_FILES]
    units_before = {u: _snapshot_unit(u) for u in _LIVE_UNITS}

    yield

    drifted_files: list[tuple[str, str]] = []
    for rel, (path_str, original) in zip(_LIVE_FILES, files_before):
        drifted, summary = _restore_file(Path(path_str), original)
        if drifted:
            drifted_files.append((rel, summary))
            # appletsrc holds the wallpaper path, but plasmashell caches the
            # active wallpaper in memory — restoring the file alone leaves
            # the screen on whatever the offending test commanded over DBus.
            # Re-issue the wallpaper apply so the running session matches
            # the restored file. Best-effort: missing tool / DBus failure
            # is fine, the file is still the source of truth.
            if rel == ".config/plasma-org.kde.plasma.desktop-appletsrc" \
                    and original is not None and shutil.which("plasma-apply-wallpaperimage"):
                wp = _extract_wallpaper_path(original)
                if wp:
                    subprocess.run(
                        ["plasma-apply-wallpaperimage", wp],
                        check=False, capture_output=True, timeout=15,
                    )

    drifted_units: list[str] = []
    for unit, original in units_before.items():
        if _restore_unit(unit, original):
            drifted_units.append(unit)

    if drifted_files or drifted_units:
        rep = request.config.pluginmanager.get_plugin("terminalreporter")
        msg = ["LIVE-STATE LEAK DETECTED — restored from snapshot:"]
        for rel, summary in drifted_files:
            msg.append(f"  file: {rel} ({summary})")
        for unit in drifted_units:
            msg.append(f"  unit: {unit}")
        msg.append("  → a test escaped the sandbox, OR plasmashell wrote")
        msg.append("    spontaneously during the run; track it down.")
        if rep is not None:
            rep.write_sep("=", "live-state safety net")
            for line in msg:
                rep.write_line(line)
        else:
            print("\n".join(msg), file=sys.stderr)
