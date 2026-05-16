"""Plymouth boot splash — installs the MacTahoeLiquidKde theme to
``/usr/share/plymouth/themes/`` and activates it via Plymouth's own
``-R`` flag (which rebuilds the initramfs through whatever the distro
uses: mkinitcpio / dracut / update-initramfs).

Safety model:
1. Snapshot the previously-active theme to a state file BEFORE activating
   ours, so uninstall can restore it. Fallback target is ``bgrt`` — the
   universal Plymouth theme present on every distro that ships plymouth.
2. Validate the freshly-installed .plymouth metadata parses AND every
   image referenced in the .script actually exists, BEFORE running
   ``-R``. A broken theme that's never activated leaves the boot path
   on the previous theme.
3. ``plymouth-set-default-theme -R`` runs under a 60s timeout. If it
   fails non-zero, we attempt to restore the snapshot before surfacing.
4. The step fails soft when ``plymouth-set-default-theme`` is missing —
   Plymouth is not universally installed on every Plasma distro and the
   rest of the desktop should still install cleanly.
"""

import configparser
import re
import subprocess
from pathlib import Path

from steps._helpers import (
    HOME, _as_root, fail, info, ok, offline, sudo_install_tree, sudo_remove, warn,
)
from utils import have


THEME_NAME = "MacTahoeLiquidKde"
FALLBACK_THEME = "bgrt"
SYSTEM_THEMES_DIR = Path("/usr/share/plymouth/themes")
DEST = SYSTEM_THEMES_DIR / THEME_NAME
STATE_DIR = HOME / ".local/state/mac-tahoe-liquid-kde"
PREV_THEME_FILE = STATE_DIR / "plymouth-previous-theme"

PLYMOUTH_BIN = "plymouth-set-default-theme"
ACTIVATE_TIMEOUT_SEC = 60

MKINITCPIO_CONF = Path("/etc/mkinitcpio.conf")
GRUB_DEFAULT = Path("/etc/default/grub")
PROC_CMDLINE = Path("/proc/cmdline")


def deps():
    # ``cmd:pkg`` form — the binary is ``plymouth-set-default-theme``
    # but the package it ships in is just ``plymouth`` on every distro
    # we've seen (arch, fedora, opensuse, debian/ubuntu, suse). Without
    # the colon split, ``auto_dep`` would try to install a package named
    # ``plymouth-set-default-theme`` and fail on every distro.
    return ["plymouth-set-default-theme:plymouth"]


def _check_prereqs() -> list[str]:
    """Return a list of human-readable warnings for missing boot-side
    Plymouth prerequisites. We DO NOT auto-fix any of these — editing
    mkinitcpio.conf in the wrong order can brick encrypted boot, and
    editing the kernel cmdline through /etc/default/grub assumes GRUB
    (systemd-boot, refind, limine users all have different paths). We
    detect, we warn, we tell the user the exact command to run.

    The current kernel cmdline lives in /proc/cmdline (reflects the
    running boot — what the user is staring at right now). The
    bootloader-side cmdline lives in /etc/default/grub for GRUB users.
    Mismatch is fine; either having ``splash`` is enough to render the
    splash on the next boot if the loader regenerates."""
    warnings: list[str] = []

    # ── kernel cmdline: need ``splash`` for plymouthd to actually draw ──
    try:
        cmdline = PROC_CMDLINE.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        cmdline = ""
    if " splash" not in (" " + cmdline):
        if GRUB_DEFAULT.is_file():
            warnings.append(
                "kernel cmdline missing 'splash' — add it to "
                "GRUB_CMDLINE_LINUX_DEFAULT in /etc/default/grub, then run: "
                "sudo grub-mkconfig -o /boot/grub/grub.cfg"
            )
        else:
            warnings.append(
                "kernel cmdline missing 'splash' — add it to your bootloader "
                "configuration (systemd-boot: /boot/loader/entries/*.conf, "
                "limine: /boot/limine.conf)"
            )

    # ── initramfs hook: arch / cachyos / manjaro use mkinitcpio ──
    # Other distros (fedora dracut, debian initramfs-tools) embed plymouth
    # support automatically once the package is installed, so we only
    # check the mkinitcpio path.
    if MKINITCPIO_CONF.is_file():
        try:
            mki = MKINITCPIO_CONF.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            mki = ""
        hooks_line = next(
            (ln for ln in mki.splitlines()
             if ln.strip().startswith("HOOKS=") and not ln.strip().startswith("#")),
            "",
        )
        if "plymouth" not in hooks_line:
            warnings.append(
                "/etc/mkinitcpio.conf HOOKS line is missing 'plymouth' — "
                "add it after 'udev' (or 'systemd' on systemd-init) and "
                "BEFORE 'encrypt'/'filesystems', then run: "
                "sudo mkinitcpio -P"
            )

    return warnings


def _current_default_theme() -> str | None:
    """Read the currently-active Plymouth theme. The no-arg form of
    ``plymouth-set-default-theme`` prints the name on stdout. Returns
    None on any failure — uninstall callers treat that as "fall back
    to bgrt" rather than crashing the run."""
    try:
        res = subprocess.run(
            [PLYMOUTH_BIN],
            check=False, capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    name = (res.stdout or "").strip()
    return name or None


def _validate_theme(theme_dir: Path) -> str | None:
    """Return None if the theme on disk looks valid, otherwise a short
    error string. Parses the .plymouth metadata and confirms every
    Image("…") reference in the .script resolves."""
    meta_path = theme_dir / f"{THEME_NAME}.plymouth"
    script_path = theme_dir / f"{THEME_NAME}.script"

    if not meta_path.is_file():
        return f"metadata missing: {meta_path}"
    if not script_path.is_file():
        return f"script missing: {script_path}"

    cp = configparser.ConfigParser(strict=True)
    try:
        cp.read(str(meta_path), encoding="utf-8")
    except configparser.Error as exc:
        return f"metadata unparseable ({exc.__class__.__name__})"

    if "Plymouth Theme" not in cp.sections():
        return "metadata missing [Plymouth Theme] section"
    if "script" not in cp.sections():
        return "metadata missing [script] section"
    for key in ("Name", "ModuleName"):
        if not cp.get("Plymouth Theme", key, fallback=""):
            return f"metadata missing {key}"
    for key in ("ImageDir", "ScriptFile"):
        if not cp.get("script", key, fallback=""):
            return f"metadata missing script.{key}"

    try:
        script_text = script_path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"script unreadable ({exc})"
    refs = re.findall(r'Image\("([^"]+)"\)', script_text)
    for ref in refs:
        if not (theme_dir / ref).is_file():
            return f"script references missing asset: {ref}"
    return None


def _run_as_root(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Spawn ``cmd`` with effective UID 0 — the CLI dropped to the
    invoking user but kept real UID 0, so ``_as_root()`` flips euid back
    for the duration of the subprocess. The child inherits euid=0 and
    runs as root, which ``plymouth-set-default-theme`` requires (it
    writes /etc/plymouth/plymouthd.conf and rebuilds the initramfs)."""
    with _as_root():
        return subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=timeout,
        )


def _activate(theme: str) -> bool:
    """Set ``theme`` as the default AND rebuild the initramfs. The -R
    flag is mandatory: without it the theme is changed in
    /etc/plymouth/plymouthd.conf but the new images never make it into
    the initrd, so the next boot keeps showing the previous splash."""
    try:
        res = _run_as_root([PLYMOUTH_BIN, "-R", theme], ACTIVATE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        fail(f"{PLYMOUTH_BIN} -R {theme} timed out after {ACTIVATE_TIMEOUT_SEC}s")
        return False
    except OSError as exc:
        fail(f"{PLYMOUTH_BIN}: {exc}")
        return False
    if res.returncode != 0:
        tail = (res.stderr or res.stdout or "").strip().splitlines()[-5:]
        fail(f"{PLYMOUTH_BIN} -R {theme} failed (exit {res.returncode})")
        for line in tail:
            print(f"     \033[2m{line}\033[0m")
        return False
    return True


def _save_previous(name: str) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        PREV_THEME_FILE.write_text(name + "\n", encoding="utf-8")
    except OSError as exc:
        warn(f"could not snapshot previous Plymouth theme ({exc})")


def _read_previous() -> str:
    try:
        text = PREV_THEME_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return FALLBACK_THEME
    # An empty file or a snapshot of our own theme name would loop the
    # uninstall back to ourselves — fall back to bgrt instead.
    if not text or text == THEME_NAME:
        return FALLBACK_THEME
    return text


def install() -> None:
    if not have(PLYMOUTH_BIN):
        warn(f"{PLYMOUTH_BIN} not found — skipping boot splash")
        return

    previous = _current_default_theme()
    # Don't snapshot ourselves — a re-run shouldn't overwrite the user's
    # original theme with our own name.
    if previous and previous != THEME_NAME:
        _save_previous(previous)

    if not sudo_install_tree(offline("plymouth", THEME_NAME), DEST, "Boot splash files"):
        return

    err = _validate_theme(DEST)
    if err:
        fail(f"Boot splash validation failed: {err}")
        info("Theme files left on disk but NOT activated — previous splash still active")
        return

    if not _activate(THEME_NAME):
        # Activation failed. Try to put the previous theme back so the
        # next boot has a working splash. If we never snapshotted (first
        # run with our theme name already active, somehow) the fallback
        # is the universal bgrt.
        snapshot = _read_previous()
        warn(f"attempting rollback to {snapshot}")
        _activate(snapshot)
        return

    ok("Boot splash activated")

    prereq_warnings = _check_prereqs()
    if prereq_warnings:
        # Theme is on disk + set as default + initrd was rebuilt with the
        # theme files. But plymouth still won't show at boot if the
        # initramfs lacks the plymouth hook or the kernel has no `splash`
        # flag. Tell the user exactly what to do — DO NOT auto-edit
        # mkinitcpio.conf or grub config.
        warn("boot splash files are installed, but the splash will NOT "
             "appear at next boot until you fix the items below:")
        for line in prereq_warnings:
            warn(line)
    else:
        info(f"Next reboot will show the {THEME_NAME} splash.")
    info(f"Rollback: sudo {PLYMOUTH_BIN} -R $(cat {PREV_THEME_FILE})")


def uninstall() -> None:
    previous = _read_previous()

    if have(PLYMOUTH_BIN):
        if _activate(previous):
            ok(f"Boot splash restored to {previous}")
        else:
            warn(f"could not restore boot splash to {previous} — continuing cleanup")
    else:
        warn(f"{PLYMOUTH_BIN} not available — skipping splash restore")

    sudo_remove(DEST, "Boot splash files")

    try:
        if PREV_THEME_FILE.is_file():
            PREV_THEME_FILE.unlink()
            ok("Plymouth state cleared")
    except OSError:
        pass
