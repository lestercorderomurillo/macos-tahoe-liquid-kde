import json
import os
import re
import shutil
import subprocess
import sys
import time
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
from log import (
    banner, errors, fail, note, ok, progress_done, progress_reset, step, warn,
)
from preflight import run_preflight
from state import RunTracker
from step_runner import run_phase, step_deps, step_exists, step_has_phase, step_module
from utils import have, kw_read, pkg_sync_install, run_user


ALL_FEATURES = [
    "wallpapers", "fonts", "cursors", "plasma_theme", "window_decorations",
    "kvantum", "color_schemes", "icons", "plasmoids", "acrylic_glass",
    "global_theme", "layout", "sounds", "gtk", "sddm", "plymouth", "apps",
    "nautilus", "portals", "apply_theme",
]

# Walk order for the install/uninstall loop.
# 1. Core visual foundations first.
# 2. Shell components that the panel layout depends on next.
# 3. App integrations last.
# ``layout`` is iterated here for completeness but skipped during the loop —
# it runs after the apply step so it sees the new panel/dock packages already
# on disk, and may be retried once after the Plasma restart if the first pass
# raced plasmashell's plugin discovery.
INSTALL_ORDER = [
    "fonts", "color_schemes", "plasma_theme", "window_decorations",
    "kvantum", "gtk", "icons", "cursors", "global_theme", "wallpapers",
    "plasmoids", "globalmenu", "acrylic_glass",
    "layout", "nautilus", "portals", "plymouth",
]

FEATURE_DESC = {
    "wallpapers": "Wallpaper collection",
    "fonts": "SF Pro and SF Mono",
    "cursors": "Cursor theme",
    "plasma_theme": "Desktop theme",
    "window_decorations": "Window decorations",
    "kvantum": "Qt widget style",
    "color_schemes": "Color schemes",
    "icons": "Icon set",
    "plasmoids": "Plasma widgets",
    "globalmenu": "Global menu",
    "acrylic_glass": "Blur effect",
    "global_theme": "Global theme",
    "layout": "Top bar and dock",
    "sounds": "System sounds",
    "gtk": "GTK theme",
    "sddm": "Login screen",
    "plymouth": "Boot splash",
    "apps": "App tweaks",
    "nautilus": "Nautilus file manager",
    "portals": "Native KDE dialogs",
    "apply_theme": "Set as default after install",
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
    --plymouth         Boot splash screen (Plymouth)
    --apps             App configuration tweaks
    --nautilus         Install Nautilus and set as default file manager
    --portals          Route FileChooser/AppChooser to KDE (fixes stale dialogs)
    --no-apply-theme   Install all files but DON'T switch Plasma over to the
                       new look (no look-and-feel apply, layout, or restart).
                       Stage the install now; re-run with --apply-theme later.
    --no-grub-modify   Don't auto-edit /etc/default/grub for the boot
                       splash kernel cmdline (prints manual fix instead)

  Persistence:
    --save             Save current flags to features.json
    --reset            Reset features.json to all-true defaults
    --check-update     Check GitHub for a newer release and exit
    --preflight        Run preflight checks (sudo, paths, Qt6, IDs) and exit
    --restart          Restart Plasma shell. Standalone (no other flags)
                       skips install entirely; combined with --only or
                       --no-X the install runs first and restart happens
                       at the end (the install always restarts anyway)

Examples:
  ./install                              # install everything
  ./install --no-gtk --no-sddm           # skip GTK and SDDM
  ./install --only --fonts --icons       # install only fonts and icons
  ./install --dark --save                # dark mode, remember setting
  ./install --reset                      # restore defaults
  ./install --check-update               # see if a newer release is out
  ./install --restart                    # just kick plasmashell, don't reinstall
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
    --plymouth         Restore previous boot splash and rebuild initramfs
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
        self.check_update = False
        self.preflight_only = False
        self.restart_only = False
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
        elif arg == "--check-update":
            p.check_update = True
        elif arg == "--preflight":
            p.preflight_only = True
        elif arg == "--restart":
            p.restart_only = True
        elif arg == "--no-grub-modify":
            # Plymouth's GRUB cmdline auto-patch is opt-in by default;
            # this flag turns it off so the installer prints the
            # warning + manual instructions instead of editing
            # /etc/default/grub.
            os.environ["MTTKDE_NO_GRUB_MODIFY"] = "1"
        elif arg.startswith("--no-"):
            key = arg[5:].replace("-", "_")
            if key in ALL_FEATURES:
                p.cli_overrides[key] = False
        elif arg.startswith("--"):
            key = arg[2:].replace("-", "_")
            if key in ALL_FEATURES:
                p.cli_overrides[key] = True
    return p


# ── version checker ─────────────────────────────────────────────────────
GITHUB_RELEASES_URL = (
    "https://api.github.com/repos/"
    "lestercorderomurillo/macos-tahoe-liquid-kde/releases/latest"
)


def parse_semver(version: str) -> tuple[int, int, int]:
    """Permissive semver tuple. Strips a leading ``v``, ignores trailing
    pre-release / build metadata (``-rc1``, ``+meta``), pads short versions
    with zeros. Returns ``(0, 0, 0)`` on garbage rather than raising — a
    bad release tag should never block the installer."""
    if not version:
        return (0, 0, 0)
    s = version.strip().lstrip("vV").split("-", 1)[0].split("+", 1)[0]
    parts = s.split(".")
    out: list[int] = []
    for p in parts[:3]:
        try:
            out.append(int(p))
        except ValueError:
            out.append(0)
    while len(out) < 3:
        out.append(0)
    return (out[0], out[1], out[2])


def fetch_latest_release(timeout: float = 2.5) -> str | None:
    """Hit the GitHub releases API for the latest tag. Returns the bare
    version string (``0.8.0``) or ``None`` if anything goes wrong — offline,
    rate-limited, GitHub 5xx, JSON shape changed, …"""
    if os.environ.get("MAC_TAHOE_NO_UPDATE_CHECK", "").lower() == "true":
        return None
    try:
        import urllib.request
        req = urllib.request.Request(
            GITHUB_RELEASES_URL,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "mac-tahoe-liquid-kde-installer"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    tag = data.get("tag_name")
    return tag.lstrip("vV") if isinstance(tag, str) else None


_CLEAR_LINE = "\r\033[2K"
_VERSION_CHECK_READ_PAUSE = 2.0


def check_for_updates(verbose: bool = False, inline: bool = False) -> bool:
    """Print an upgrade banner when GitHub has a newer release. Returns
    ``True`` if an update is available.

    ``inline=True`` prints a transient ``Checking for updates…`` line and
    overwrites it in place with the verdict, then pauses ~2s so the
    verdict has time to register before the install scrolls it away. Used
    by the install flow so the user sees the network round-trip happen
    and gets a confirmation of where they stand on every run.

    ``verbose=True`` (without inline) is for the standalone
    ``--check-update`` flag — it always announces the verdict, even when
    up to date or offline, but skips the pause."""
    if inline:
        # confirm() already trails with a blank line, so we go straight
        # into the transient "Checking…" line.
        print("  \033[2mChecking for updates…\033[0m", end="", flush=True)

    current = read_version()
    latest = fetch_latest_release()

    if inline:
        print(_CLEAR_LINE, end="", flush=True)

    if latest is None:
        if verbose or inline:
            print("  \033[2mCould not reach GitHub — skipping update check\033[0m")
        if inline:
            time.sleep(_VERSION_CHECK_READ_PAUSE)
        return False
    if parse_semver(latest) > parse_semver(current):
        print(f"  \033[1;33mUpdate available: {current} → {latest}\033[0m")
        print(f"  \033[2mUpdates fix style breakage when KDE / Plasma /"
              f" Kvantum upstream changes\033[0m")
        print(f"  \033[2mbreak our overrides, plus crash fixes for"
              f" custom plasmoids.\033[0m")
        print(f"  \033[2mRun: git pull && ./install\033[0m")
        if inline:
            time.sleep(_VERSION_CHECK_READ_PAUSE)
        return True
    if verbose or inline:
        # Match ok() exactly: two spaces, ✓, two spaces, message — no
        # extra padding before the glyph or doubled blank lines around it.
        print(f"  \033[0;32m✓\033[0m  On the latest version ({current})")
    if inline:
        time.sleep(_VERSION_CHECK_READ_PAUSE)
    return False


def _git(*args: str, capture: bool = False):
    """Run a git command inside the repo as the invoking user (NOT root —
    pulling as root would leave root-owned objects in the user's repo).
    ``run_user`` drops privileges in the child. Returns the CompletedProcess
    (or None if git isn't available / the call raised)."""
    if not have("git"):
        return None
    try:
        return run_user(
            ["git", "-C", str(REPO_ROOT), *args],
            check=False,
            capture_output=capture,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _repo_is_clean_git_checkout() -> bool:
    """True only when REPO_ROOT is a git working tree with NO uncommitted
    changes. We refuse to auto-pull over local edits — a pull could fail
    on conflicts or silently shadow the user's work."""
    if not (REPO_ROOT / ".git").exists():
        return False
    inside = _git("rev-parse", "--is-inside-work-tree", capture=True)
    if inside is None or inside.returncode != 0 or inside.stdout.strip() != "true":
        return False
    status = _git("status", "--porcelain", capture=True)
    if status is None or status.returncode != 0:
        return False
    return status.stdout.strip() == ""


def auto_update_and_reexec(argv: list[str]) -> None:
    """When a newer release exists, pull it and re-exec ``./install`` so the
    freshly-pulled code does the install — an in-flight ``git pull`` can't
    upgrade the already-loaded installer otherwise.

    Bails (and lets the current version install) on any of: the recursion
    guard already set, not a clean git checkout, git missing, or the pull
    failing. Every bail prints a one-line reason and the manual command, so
    the user is never left stuck.

    The recursion guard ``MAC_TAHOE_UPDATED`` is exported before the re-exec
    so the new process skips the update check entirely and proceeds straight
    to installing — no pull/re-exec loop."""
    if os.environ.get("MAC_TAHOE_UPDATED") == "1":
        return  # already re-exec'd after a successful pull; just install

    if not _repo_is_clean_git_checkout():
        note("Not a clean git checkout — skipping auto-update")
        print("  \033[2mUpdate manually: git pull && ./install\033[0m")
        return

    print("  \033[2mPulling the latest release…\033[0m")
    pull = _git("pull", "--ff-only", capture=True)
    if pull is None or pull.returncode != 0:
        warn("git pull failed — installing the current version")
        if pull is not None and pull.stderr:
            print(f"  \033[2m{pull.stderr.strip().splitlines()[-1]}\033[0m")
        print("  \033[2mUpdate manually: git pull && ./install\033[0m")
        return

    ok(f"Updated to {read_version()} — restarting installer")

    # Re-exec the ./install wrapper (REPO_ROOT/install) so the newly-pulled
    # cli.py runs. Real UID is still 0 here, so the new process stays root
    # and repeats the same euid-drop hop. argv is the install flags only;
    # the wrapper re-derives its own path.
    installer = REPO_ROOT / "install"
    os.environ["MAC_TAHOE_UPDATED"] = "1"
    try:
        os.execv(str(installer), [str(installer), *argv])
    except OSError as exc:
        warn(f"could not restart installer ({exc}) — installing current version")
        os.environ.pop("MAC_TAHOE_UPDATED", None)


def apply_overrides(feat: dict[str, object], parsed: ParsedArgs) -> dict[str, object]:
    if parsed.do_reset:
        feat = dict(DEFAULT_FEATURES)
        save_features(feat)
        ok("features.json reset to defaults")

    if parsed.only_mode:
        for k in ALL_FEATURES:
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
    os.environ["THEME_MODE"] = str(feat.get("theme_mode", "auto"))
    for k in ALL_FEATURES:
        os.environ[f"FEAT_{k.upper()}"] = _b(feat.get(k, True))


def _b(v: object) -> str:
    return "true" if v else "false"


def _detect_plasma_version() -> str | None:
    """Best-effort Plasma version probe.

    Some distros / wrappers print the version to stderr instead of stdout,
    and Qt can prepend warnings before the actual version line. Parse both
    streams and accept either ``major.minor`` or ``major.minor.patch``.
    If the binary output is weird, fall back to the installed package
    version from the native distro package manager.
    """
    probes = (
        ["plasmashell", "--version"],
        ["plasmashell", "-v"],
        ["pacman", "-Q", "plasma-workspace"],
        ["rpm", "-q", "plasma-workspace"],
        ["dpkg-query", "-W", "-f=${Version}", "plasma-workspace"],
    )
    pat = re.compile(r"(?<!\d)(\d+)\.(\d+)(?:\.(\d+))?(?!\d)")
    for cmd in probes:
        if not have(cmd[0]):
            continue
        try:
            res = run_user(
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            continue
        blob = "\n".join(part for part in (res.stdout, res.stderr) if part)
        m = pat.search(blob)
        if not m:
            continue
        patch = m.group(3) or "0"
        return f"{m.group(1)}.{m.group(2)}.{patch}"
    return None


def verify_plasma() -> bool:
    # Test-mode bypass for the VM boot-splash harness. The Plymouth step
    # only needs plymouth-set-default-theme + a working initramfs path;
    # KDE Plasma is irrelevant for boot-splash rendering. The harness
    # sets this env var when SSH-driving `./install --only --plymouth`
    # inside a vanilla Arch cloud image (which has no Plasma installed).
    # NEVER set this in a real user-facing install — it would happily
    # write KDE configs to a system that can't load them.
    if os.environ.get("MTTKDE_SKIP_PLASMA_CHECK") == "1":
        warn("MTTKDE_SKIP_PLASMA_CHECK=1 — bypassing Plasma version check (test mode)")
        return True
    if not have("plasmashell"):
        fail("KDE Plasma not found")
        print("     MacTahoe Liquid KDE requires KDE Plasma 6.6+.", file=sys.stderr)
        return False
    ver = _detect_plasma_version()
    if not ver:
        warn("Could not detect plasmashell version")
        return True
    major_s, minor_s, _ = ver.split(".", 2)
    major, minor = int(major_s), int(minor_s)
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
    # Test-mode bypass for the SSH-driven VM harness. Without this, a
    # non-tty install session falls through to ``input()`` which reads
    # from the bash heredoc — fragile and easy to deadlock.
    if os.environ.get("MTTKDE_NO_CONFIRM") == "1":
        print("  MTTKDE_NO_CONFIRM=1 — auto-accepting (test mode)")
        print()
        return True
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
    return True


def _restore_user_session_env(uid: int) -> None:
    """Best-effort recovery of the invoking user's graphical session env.

    ``sudo`` commonly strips ``XDG_RUNTIME_DIR`` / ``DBUS_SESSION_BUS_ADDRESS``
    and display variables. That is enough to make ``plasmashell --version``
    abort with no output and to leave later ``qdbus`` layout resets talking
    to nowhere. Seed the well-known ``/run/user/<uid>`` paths first, then ask
    the user systemd manager for the real session environment.
    """
    runtime_dir = Path(f"/run/user/{uid}")
    bus = runtime_dir / "bus"
    if runtime_dir.is_dir():
        os.environ.setdefault("XDG_RUNTIME_DIR", str(runtime_dir))
    if bus.exists():
        os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={bus}")

    if not have("systemctl"):
        return
    try:
        res = run_user(
            ["systemctl", "--user", "show-environment"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return
    if res.returncode != 0:
        return

    wanted = {
        "DBUS_SESSION_BUS_ADDRESS",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XAUTHORITY",
        "XDG_CURRENT_DESKTOP",
        "XDG_RUNTIME_DIR",
        "XDG_SESSION_TYPE",
    }
    for line in res.stdout.splitlines():
        key, _, value = line.partition("=")
        if key in wanted and value:
            os.environ[key] = value


def _require_root_and_drop_to_user(op: str = "install") -> bool:
    """Hard precondition for install/uninstall: it only runs when
    invoked with root privileges (``sudo ./install`` /
    ``sudo ./uninstall``). Qt6 only walks the plugin + QML directories
    its own build was configured against (queried from qmake6 via
    ``paths.qt6_plugins_dir`` / ``qt6_qml_dir`` — typically under
    ``/usr/lib`` or ``/usr/lib64`` depending on the distro); user-path
    destinations are not discoverable, so .so files and runtime QML
    for the C++ plasmoids and KWin effect MUST land in the
    Qt-reported libdir. That means sudo upfront is mandatory.

    Once root is verified, drop the effective UID/GID to ``SUDO_USER``
    so all file writes land with normal user ownership. The few
    operations that genuinely need root (.so installs to the system
    Qt6 libdir, QML modules, etc.) re-elevate via the
    ``sudo_install_file`` / ``sudo_install_tree`` / ``sudo_remove``
    helpers, which call
    ``os.seteuid(0)`` for the duration of one operation and restore
    the user's UID immediately after. Real UID stays at 0 throughout,
    so the seteuid trip back to root always succeeds.
    """
    if os.geteuid() != 0:
        print(file=sys.stderr)
        print(f"  \033[0;31m{op.capitalize()} must be run as root.\033[0m",
              file=sys.stderr)
        print(f"  \033[2mRe-run as:\033[0m  sudo ./{op}", file=sys.stderr)
        print(file=sys.stderr)
        return False

    sudo_user = os.environ.get("SUDO_USER")
    sudo_uid_str = os.environ.get("SUDO_UID")
    sudo_gid_str = os.environ.get("SUDO_GID")
    if not sudo_user or not sudo_uid_str or not sudo_gid_str:
        print(file=sys.stderr)
        print("  \033[0;31mCould not determine the invoking user.\033[0m",
              file=sys.stderr)
        print("  \033[2m`SUDO_USER` is not set — running as the root login "
              "directly is not supported.\033[0m", file=sys.stderr)
        print(file=sys.stderr)
        return False

    sudo_uid = int(sudo_uid_str)
    sudo_gid = int(sudo_gid_str)
    try:
        import pwd
        user_home = pwd.getpwuid(sudo_uid).pw_dir
    except KeyError:
        user_home = f"/home/{sudo_user}"

    # Point HOME / USER / LOGNAME at the real user so every later
    # ``Path.home()`` / kwriteconfig6 invocation writes under the user's
    # tree, not under /root.
    os.environ["HOME"] = user_home
    os.environ["USER"] = sudo_user
    os.environ["LOGNAME"] = sudo_user
    # Some sudo configs preserve root-owned XDG paths (notably
    # XDG_STATE_HOME on openSUSE). If we leave those behind, helpers
    # like RunTracker still try to write under /root even after HOME is
    # corrected. Only rewrite values that are missing or still point at
    # root so custom user XDG overrides survive.
    for key, suffix in (
        ("XDG_CONFIG_HOME", ".config"),
        ("XDG_DATA_HOME", ".local/share"),
        ("XDG_CACHE_HOME", ".cache"),
        ("XDG_STATE_HOME", ".local/state"),
    ):
        value = os.environ.get(key, "")
        if not value or value == "/root" or value.startswith("/root/"):
            os.environ[key] = f"{user_home}/{suffix}"

    # Drop privileges with seteuid (reversible) — real UID stays 0 so
    # ``sudo_install_file`` can hop back to root for /usr/lib writes.
    # Group has to drop first so the effective uid switch doesn't lose
    # the right to call setegid afterwards.
    os.setegid(sudo_gid)
    os.seteuid(sudo_uid)
    _restore_user_session_env(sudo_uid)
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


def _read_config_cascade(file: str, group: str, prop: str) -> str:
    """Read a KDE config key the same way Plasma resolves it: check
    ``~/.config/kdedefaults/<file>`` (where ``plasma-apply-lookandfeel``
    writes its keys) before ``~/.config/<file>``. ``kreadconfig6`` only
    looks at the main file, so the post-install verification missed
    every key the live LAF apply had stamped into kdedefaults instead."""
    home = Path(os.environ.get("HOME") or str(Path.home()))
    for candidate in (home / ".config/kdedefaults" / file,
                      home / ".config" / file):
        if not candidate.is_file():
            continue
        section = None
        try:
            text = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", ";")):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                continue
            if section == group and "=" in line:
                k, _, v = line.partition("=")
                if k.strip() == prop and v:
                    return v
    return ""


def verify_config(feat: dict[str, object]) -> None:
    for key, file, group, prop, expected, label in _VERIFY_CHECKS:
        if not feat.get(key, True):
            continue
        actual = _read_config_cascade(file, group, prop)
        # Fall back to kreadconfig6 if the cascade scan came up empty —
        # keeps the check resilient to whatever Plasma version
        # rearrangement does next.
        if not actual:
            actual = kw_read(file, group, prop)
        if expected in actual:
            ok(label)
        else:
            fail(f"{label} (expected {expected}, got {actual or 'empty'})")


def should_process(feature: str, feat: dict[str, object]) -> bool:
    if feature == "globalmenu":
        return bool(feat.get("plasmoids", True))
    return bool(feat.get(feature, True))


def _layout_is_installed() -> bool:
    mod = step_module("layout")
    probe = getattr(mod, "is_installed", None) if mod is not None else None
    return bool(callable(probe) and probe())


# Features whose install must succeed for the desktop to function.
# These are the compiled .so + QML drops — the dock, the global menu,
# the KWin glass effect. If any of these fails to install, abort the
# whole installer rather than ship a half-broken desktop.
CRITICAL_INSTALL_FEATURES = {"globalmenu", "plasmoids", "acrylic_glass"}


def _build_features(feat: dict[str, object]) -> list[str]:
    """Features whose step exposes a build() phase AND is enabled.

    These are the C++ components — globalmenu, plasmoids (taskmanager),
    acrylic_glass. Building these is mandatory: if any fails, the whole
    install aborts before any artefact lands on disk."""
    out: list[str] = []
    for feature in INSTALL_ORDER:
        if not should_process(feature, feat):
            continue
        if not step_has_phase(feature, "build"):
            continue
        out.append(feature)
    return out


def _run_builds_or_abort(feat: dict[str, object]) -> bool:
    """Run every build phase upfront. If any build fails OR any expected
    artefact is missing afterwards, return False — the caller aborts the
    whole installer.

    Build runs *before* the install loop so we never ship a half-built
    desktop where some compiled .so landed but a sibling didn't. Each
    step exposes ``build_artifacts() -> list[Path]`` for the post-build
    check; modules without that helper just rely on errors[] surfacing."""
    builds = _build_features(feat)
    if not builds:
        ok("no compiled components selected — skipping build phase")
        return True

    failed: list[str] = []
    for i, feature in enumerate(builds):
        label = feature.replace("_", " ")
        # note() already trails with a blank line, so skip the leading
        # blank for the first iteration to avoid a doubled gap below
        # the step header.
        if i:
            print()
        print(f"  \033[1mBuilding {label}\033[0m")
        if not run_phase(feature, "build"):
            failed.append(feature)
            continue

        mod = step_module(feature)
        artifacts = getattr(mod, "build_artifacts", None) if mod else None
        if not callable(artifacts):
            continue
        missing = [p for p in artifacts() if not p.exists()]
        if missing:
            for p in missing:
                fail(f"{label}: build artefact missing: {p}")
            failed.append(feature)

    if failed:
        print()
        fail(f"build phase failed for: {', '.join(failed)}")
        print("  \033[2mAll compiled components must build before any "
              "install step runs.\033[0m")
        print("  \033[2mFix the build errors above (typically missing KF6/Qt6 "
              "dev packages) and re-run.\033[0m")
        return False
    return True


_BASE_DEPS = [
    ("curl", "curl"), ("unzip", "unzip"),
    ("fc-cache", "fontconfig"), ("kwriteconfig6", "kconfig"),
    ("cmake", "cmake"), ("g++", "gcc"),
    ("pkg-config", "pkgconf"), ("dbus-monitor", "dbus"),
]


def _check_deps(feat: dict[str, object]) -> None:
    # Collect every dep the selected features need, probe each PACKAGE
    # directly (pacman -Q etc), and install only the genuinely-missing
    # ones. Installing only what's absent avoids upgrading already-present
    # packages — a -Sy upgrade of one KDE package against the rest of the
    # system is the classic partial-upgrade file-conflict trap.
    from distro import package_for, package_installed

    tokens: list[tuple[str, str]] = list(_BASE_DEPS)
    for feature in INSTALL_ORDER:
        if not should_process(feature, feat):
            continue
        if not step_exists(feature):
            continue
        tokens.extend(step_deps(feature))

    pkgs = sorted({package_for(cmd, pkg) for cmd, pkg in tokens})
    missing = [p for p in pkgs if not package_installed(p)]
    for p in pkgs:
        if p not in missing:
            ok(p)
    if missing:
        warn(f"installing missing: {', '.join(missing)}")
        pkg_sync_install(*missing)
    else:
        ok("all dependencies present")


def _flush_icon_cache_signal() -> None:
    home = Path.home()
    for sub in (".cache/icon-cache.kcache", ".cache/kiconthemes"):
        shutil.rmtree(home / sub, ignore_errors=True)
    run_user(
        ["dbus-send", "--session", "--type=signal",
         "/KIconLoader", "org.kde.KIconLoader.iconChanged", "int32:0"],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _print_done(verb: str) -> None:
    print()
    print(f"\033[0;32m\033[1m  ── Done\033[0m")
    if not errors:
        ok(f"MacTahoe Liquid KDE {verb} successfully")
        print(f"  \033[0;90mReport bugs at: https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new\033[0m")
        print()
        return
    # Snapshot — fail() appends to errors, so iterating the live list
    # while calling fail() is an infinite loop. Print directly here.
    issues = list(errors)
    warn(f"{len(issues)} issue(s):")
    for e in issues:
        print(f"  \033[0;31m✗\033[0m  {e}", file=sys.stderr)
    print(f"  \033[0;90mReport bugs at: https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new\033[0m")
    print()


def run_install(argv: list[str]) -> int:
    parsed = parse_args(argv)
    if parsed.help:
        print(INSTALL_HELP)
        return 0
    if parsed.check_update:
        return 0 if not check_for_updates(verbose=True) else 0

    # Install needs root: the C++ plasmoids and KWin effect drop .so
    # files into the Qt6 plugin dir and runtime QML into the Qt6 QML
    # dir (qmake6-reported; /usr/lib on Arch/Fedora, /usr/lib64 on
    # Gentoo, /usr/lib/x86_64-linux-gnu on Debian-multiarch). User
    # paths are not discoverable. ``sudo ./install`` is the supported
    # entry.
    if not _require_root_and_drop_to_user("install"):
        return 1

    feat = apply_overrides(load_features(), parsed)
    export_env(feat)

    if parsed.preflight_only:
        banner(read_version())
        return 0 if run_preflight("install") else 1

    # ``--restart`` standalone (no install flags) bypasses every install
    # step and just kicks plasmashell. When combined with install flags
    # (``--only --acrylic-glass --restart``, ``--no-X --restart``, etc.)
    # the install runs normally — the final ``run_phase("apply",
    # "restart_plasma")`` at the end of run_install already restarts
    # Plasma, so ``--restart`` in that combo is implicit. The standalone
    # form is the useful one: iterating on a piece, you reinstall once
    # with ``--only --X`` and then re-kick plasmashell with ``--restart``
    # in subsequent runs without re-doing the install.
    if parsed.restart_only and not parsed.only_mode and not parsed.cli_overrides:
        banner(read_version())
        step("Restarting Plasma")
        note("Restarts Plasma shell — no install, no config changes")
        run_phase("apply", "restart_plasma")
        return 0

    tracker = RunTracker("install", argv, str(feat.get("theme_mode", "auto")))
    tracker.start()
    progress_reset()
    rc = 0
    try:
        if not SRC_DIR.is_dir():
            print("  \033[0;31m  Run from repo root.\033[0m", file=sys.stderr)
            rc = 1
            return rc

        banner(read_version())
        if not confirm("In development — Install at your own risk.\n"
                       "  Do not install on production / work systems."):
            tracker.mark_aborted()
            return 0
        if check_for_updates(inline=True):
            # Pull the newer release and re-exec so the new code installs.
            # Returns (and we install the current version) if the repo isn't
            # a clean git checkout, git is missing, or the pull fails.
            auto_update_and_reexec(argv)

        if not run_preflight("install"):
            fail("preflight failed — refusing to install")
            rc = 1
            return rc

        step("Verification")
        note("Checks KDE version and required tools")
        if not verify_plasma():
            return 1

        step("Dependencies")
        note("Checking and installing required tools")
        _check_deps(feat)

        # Build all C++ components upfront. If any fails to compile or
        # any expected artefact is missing, abort BEFORE the install
        # loop runs — half-installed desktops are worse than a clean
        # bail with a build log to follow.
        step("Building Compiled Components")
        note("Builds C++ plasmoids and KWin effects — must succeed before install")
        if not _run_builds_or_abort(feat):
            return 1

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

            # Build phase already ran in the dedicated step above.
            # No download phase any more — all assets are bundled under
            # src/offline/ since v0.18.0 (wallpapers since v0.17.0).
            if not run_phase(feature, "install") and feature in CRITICAL_INSTALL_FEATURES:
                fail(f"{label} install failed — aborting "
                     "(critical compiled component)")
                return 1

        step("Installing Theme Switcher")
        note("Installs the auto light/dark theme switcher")
        run_phase("theme_switch", "install")

        if feat.get("apply_theme", True):
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

            if feat.get("layout", True) and step_exists("layout") and not _layout_is_installed():
                step("Retrying Layout")
                note("Retries the panel layout after Plasma reloads new plasmoids")
                run_phase("layout", "install")
        else:
            step("Skipping Activation")
            note("--no-apply-theme: files installed but Plasma left untouched. "
                 "Re-run with --apply-theme to switch over.")

        _print_done("installed")
        if not errors:
            tracker.mark_completed()
        rc = 1 if errors else 0
        return rc
    except KeyboardInterrupt:
        tracker.mark_aborted()
        print("\n  Aborted.", file=sys.stderr)
        rc = 130
        return rc
    finally:
        progress_done(rc)
        tracker.finalize(rc)


def run_uninstall(argv: list[str]) -> int:
    parsed = parse_args(argv)
    if parsed.help:
        print(UNINSTALL_HELP)
        return 0

    if not _require_root_and_drop_to_user("uninstall"):
        return 1

    feat = apply_overrides(load_features(), parsed)
    export_env(feat)

    tracker = RunTracker("uninstall", argv, str(feat.get("theme_mode", "auto")))
    tracker.start()
    progress_reset()
    rc = 0
    try:
        if not SRC_DIR.is_dir():
            print("  \033[0;31m  Run from repo root.\033[0m", file=sys.stderr)
            rc = 1
            return rc

        banner(read_version())
        if not confirm("This will reset your desktop to Breeze defaults."):
            tracker.mark_aborted()
            return 0
        check_for_updates(inline=True)

        if not run_preflight("uninstall"):
            fail("preflight failed — refusing to uninstall")
            rc = 1
            return rc

        step("Verification")
        note("Checks KDE version")
        if not verify_plasma():
            rc = 1
            return rc

        # Uninstall is a two-stage flow: first put the user's desktop back
        # into a working Breeze state while our assets still exist on disk,
        # then remove the MacTahoe payload afterwards as cleanup.
        step("Removing Theme Switcher")
        note("Stops and removes the auto light/dark theme switcher")
        run_phase("theme_switch", "uninstall")

        if feat.get("layout", True) and step_exists("layout"):
            step("Resetting Layout")
            note("Resets panel layout to default")
            run_phase("layout", "uninstall")

        step("Applying Changes")
        note("Resets to Breeze defaults before removing theme assets")
        run_phase("apply", "uninstall")

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

        step("Restarting Plasma")
        note("Restarts Plasma shell to finalize changes")
        run_phase("apply", "restart_plasma")

        _print_done("uninstalled")
        if not errors:
            tracker.mark_completed()
        rc = 1 if errors else 0
        return rc
    except KeyboardInterrupt:
        tracker.mark_aborted()
        print("\n  Aborted.", file=sys.stderr)
        rc = 130
        return rc
    finally:
        progress_done(rc)
        tracker.finalize(rc)
