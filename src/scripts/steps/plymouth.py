"""Plymouth boot splash: installs the theme to /usr/share/plymouth/themes/
and activates via ``plymouth-set-default-theme -R`` (rebuilds the initramfs).
Contract: snapshot the previous theme, then validate BEFORE activating."""

import configparser
import os
import re
import shutil
import subprocess
from pathlib import Path

from distro import package_for, system_lib_dir
from steps._helpers import (
    HOME, _as_root, fail, info, ok, offline, sudo_install_tree, sudo_remove, warn,
)
from utils import have, pkg_install


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
PLYMOUTHD_CONF = Path("/etc/plymouth/plymouthd.conf")


def deps():
    # cmd:pkg — the binary ships in the plain ``plymouth`` package everywhere.
    return ["plymouth-set-default-theme:plymouth"]


def _check_prereqs() -> tuple[bool, bool]:
    """Return ``(splash_missing, mkinitcpio_missing_hook)``. /proc/cmdline
    and /etc/default/grub may disagree; either carrying ``splash`` is enough
    for the next boot."""
    # ── kernel cmdline: need ``splash`` for plymouthd to actually draw ──
    try:
        cmdline = PROC_CMDLINE.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        cmdline = ""
    splash_missing = " splash" not in (" " + cmdline)

    # ── initramfs hook: arch / cachyos / manjaro use mkinitcpio ─
    # dracut / initramfs-tools embed plymouth automatically; only mkinitcpio
    # needs the explicit HOOKS entry.
    mkinitcpio_missing_hook = False
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
        mkinitcpio_missing_hook = "plymouth" not in hooks_line

    return splash_missing, mkinitcpio_missing_hook


def _grub_auto_patch_enabled() -> bool:
    """Opt-out: MTTKDE_NO_GRUB_MODIFY=1 (the CLI's --no-grub-modify) keeps
    /etc/default/grub untouched."""
    return os.environ.get("MTTKDE_NO_GRUB_MODIFY", "").lower() not in (
        "1", "true", "yes",
    )


def _grub_is_active_bootloader() -> bool:
    """GRUB counts as active only when BOTH /etc/default/grub AND a regen
    binary exist — the file alone is a common leftover after migrating to
    systemd-boot / Limine / rEFInd, and patching it would do nothing."""
    if not GRUB_DEFAULT.is_file():
        return False
    return have("grub-mkconfig") or have("grub2-mkconfig")


_GRUB_CMDLINE_RE = re.compile(
    r'^(\s*GRUB_CMDLINE_LINUX_DEFAULT\s*=\s*)(["\'])(.*?)\2(\s*)$',
    re.MULTILINE,
)


def _patch_grub_add_splash() -> bool:
    """Append ``splash`` to GRUB_CMDLINE_LINUX_DEFAULT iff missing, keeping
    a .bak beside the file. True when the file ends in the expected state."""
    try:
        with _as_root():
            text = GRUB_DEFAULT.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        warn(f"could not read {GRUB_DEFAULT} ({exc})")
        return False

    match = _GRUB_CMDLINE_RE.search(text)
    if match is None:
        # Non-standard config — refuse to invent the line.
        warn(f"{GRUB_DEFAULT} has no GRUB_CMDLINE_LINUX_DEFAULT line — "
             "skipping auto-patch")
        return False

    prefix, quote, params, suffix = match.groups()
    tokens = params.split()
    if "splash" in tokens:
        return True  # already correct, nothing to write

    tokens.append("splash")
    new_line = f"{prefix}{quote}{' '.join(tokens)}{quote}{suffix}"
    new_text = text[:match.start()] + new_line + text[match.end():]

    backup = GRUB_DEFAULT.with_suffix(GRUB_DEFAULT.suffix + ".mttkde.bak")
    try:
        with _as_root():
            # Keep the oldest backup — that's the true original.
            if not backup.exists():
                shutil.copy2(GRUB_DEFAULT, backup)
            tmp = GRUB_DEFAULT.with_name(GRUB_DEFAULT.name + ".mttkde-tmp")
            tmp.write_text(new_text, encoding="utf-8")
            shutil.copystat(GRUB_DEFAULT, tmp)
            tmp.replace(GRUB_DEFAULT)
    except OSError as exc:
        warn(f"could not patch {GRUB_DEFAULT} ({exc})")
        return False
    return True


# grub-mkconfig (Arch/Gentoo/openSUSE) vs grub2-mkconfig (Fedora/RHEL);
# either tool can own either output path, so try every combination.
_GRUB_REGENERATE_CANDIDATES = (
    ("grub-mkconfig",  "/boot/grub/grub.cfg"),
    ("grub2-mkconfig", "/boot/grub2/grub.cfg"),
    ("grub-mkconfig",  "/boot/grub2/grub.cfg"),
    ("grub2-mkconfig", "/boot/grub/grub.cfg"),
)


def _regenerate_grub_config() -> bool:
    """Run ``grub[2]-mkconfig -o <output>`` for whichever (binary, output)
    pair exists; True on the first success."""
    for binary, output in _GRUB_REGENERATE_CANDIDATES:
        if not have(binary):
            continue
        output_dir = Path(output).parent
        if not output_dir.is_dir():
            continue
        try:
            with _as_root():
                res = subprocess.run(
                    [binary, "-o", output],
                    check=False, capture_output=True, text=True,
                    timeout=120,
                )
        except (subprocess.TimeoutExpired, OSError) as exc:
            warn(f"{binary} -o {output} failed: {exc}")
            continue
        if res.returncode == 0:
            return True
        warn(f"{binary} -o {output} exited {res.returncode}: "
             f"{(res.stderr or '').strip().splitlines()[-1:] or ['(no output)']}")
    return False


def _current_default_theme() -> str | None:
    """Currently-active theme (no-arg plymouth-set-default-theme prints it).
    None on any failure — callers fall back to bgrt."""
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
    """None if the theme looks valid, else a short error. Parses the
    .plymouth metadata and checks every Image("…") in the .script resolves."""
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


def _script_plugin_path() -> Path:
    return system_lib_dir() / "plymouth/script.so"


def _ensure_script_plugin() -> bool:
    script_plugin = _script_plugin_path()
    if script_plugin.is_file():
        return True
    pkg = package_for("plymouth-script-plugin", "plymouth")
    warn(f"{script_plugin} missing — installing {pkg}...")
    if not pkg_install(pkg):
        warn("Plymouth script plugin install failed — leaving previous splash active")
        return False
    if script_plugin.is_file():
        ok("Plymouth script plugin installed")
        return True
    warn(f"{script_plugin} still missing after installing {pkg} — leaving previous splash active")
    return False


def _run_as_root(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Spawn ``cmd`` with euid 0 — plymouth-set-default-theme needs root
    (it writes plymouthd.conf and rebuilds the initramfs)."""
    with _as_root():
        return subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=timeout,
        )


def _activate(theme: str) -> bool:
    """Set ``theme`` as default AND rebuild the initramfs. -R is mandatory —
    without it the new images never reach the initrd."""
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


def _set_plymouthd_simpledrm(enabled: bool) -> bool:
    """Toggle ``[Daemon] UseSimpledrm``. The GPU driver unloads before the
    shutdown splash, so plymouth falls back to a tiny fbcon framebuffer and
    renders in a corner; UseSimpledrm=true pins the UEFI GOP framebuffer."""
    # strict=False: plymouth-set-default-theme appends duplicate Theme= lines
    # without deduping; strict=True raised DuplicateOptionError and we bailed.
    cp = configparser.ConfigParser(strict=False)
    # plymouthd keys are case-sensitive — preserve existing casing and write
    # UseSimpledrm capitalized.
    cp.optionxform = str
    if PLYMOUTHD_CONF.is_file():
        try:
            cp.read(str(PLYMOUTHD_CONF), encoding="utf-8")
        except configparser.Error as exc:
            warn(f"plymouthd.conf unparseable ({exc.__class__.__name__}) — "
                 "leaving UseSimpledrm setting unchanged")
            return False
    if not cp.has_section("Daemon"):
        cp.add_section("Daemon")
    if enabled:
        cp.set("Daemon", "UseSimpledrm", "true")
    elif cp.has_option("Daemon", "UseSimpledrm"):
        cp.remove_option("Daemon", "UseSimpledrm")
    else:
        return True  # already absent, nothing to do

    try:
        with _as_root():
            PLYMOUTHD_CONF.parent.mkdir(parents=True, exist_ok=True)
            tmp = PLYMOUTHD_CONF.with_name(PLYMOUTHD_CONF.name + ".mttkde-tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                # space_around_delimiters=False is LOAD-BEARING: plymouth's
                # shell parser leaves trailing space on keys ("Theme ") and
                # then falls back to the distro default (bgrt) at shutdown.
                cp.write(fh, space_around_delimiters=False)
            tmp.replace(PLYMOUTHD_CONF)
    except OSError as exc:
        warn(f"could not update {PLYMOUTHD_CONF} ({exc})")
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

    if not _ensure_script_plugin():
        info("Theme files left on disk but NOT activated — previous splash still active")
        return

    if not _activate(THEME_NAME):
        # Roll back so the next boot has a working splash; with no snapshot
        # the fallback is the universal bgrt.
        snapshot = _read_previous()
        warn(f"attempting rollback to {snapshot}")
        _activate(snapshot)
        return

    ok("Boot splash activated")

    if _set_plymouthd_simpledrm(True):
        ok("Forced UseSimpledrm=true (fixes corner-rendered shutdown splash)")

    splash_missing, mkinitcpio_missing_hook = _check_prereqs()

    # Auto-patch the GRUB cmdline only when ``splash`` is missing, the user
    # hasn't opted out, and GRUB is genuinely the active bootloader.
    grub_active = _grub_is_active_bootloader()
    if splash_missing and _grub_auto_patch_enabled() and grub_active:
        if _patch_grub_add_splash():
            ok("Added 'splash' to GRUB_CMDLINE_LINUX_DEFAULT")
            if _regenerate_grub_config():
                ok("Regenerated bootloader config")
                splash_missing = False  # remediation succeeded
            else:
                warn("could not regenerate bootloader config — run "
                     "grub-mkconfig manually before next reboot")

    if splash_missing or mkinitcpio_missing_hook:
        warn("boot splash files are installed, but the splash will NOT "
             "appear at next boot until you fix the items below:")
        if splash_missing:
            if grub_active:
                # User opted out or _patch_grub_add_splash() refused.
                warn("kernel cmdline missing 'splash' — add it to "
                     "GRUB_CMDLINE_LINUX_DEFAULT in /etc/default/grub, "
                     "then run: sudo grub-mkconfig -o /boot/grub/grub.cfg "
                     "(or re-run the installer without "
                     "MTTKDE_NO_GRUB_MODIFY=1)")
            elif GRUB_DEFAULT.is_file():
                # Leftover /etc/default/grub, no regen binary — a different
                # bootloader is active.
                warn("kernel cmdline missing 'splash'. Found a leftover "
                     "/etc/default/grub but no grub-mkconfig / "
                     "grub2-mkconfig on PATH — your active bootloader is "
                     "likely systemd-boot / Limine / rEFInd. Edit the "
                     "appropriate loader config manually (systemd-boot: "
                     "/boot/loader/entries/*.conf, limine: "
                     "/boot/limine.conf, rEFInd: /boot/EFI/refind/"
                     "refind.conf).")
            else:
                warn("kernel cmdline missing 'splash' — add it to your "
                     "bootloader configuration (systemd-boot: "
                     "/boot/loader/entries/*.conf, limine: "
                     "/boot/limine.conf)")
        if mkinitcpio_missing_hook:
            warn("/etc/mkinitcpio.conf HOOKS line is missing 'plymouth' "
                 "— add it after 'udev' (or 'systemd' on systemd-init) "
                 "and BEFORE 'encrypt'/'filesystems', then run: "
                 "sudo mkinitcpio -P")
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

    # Drop the UseSimpledrm override — the restored theme may not want it.
    if _set_plymouthd_simpledrm(False):
        ok("UseSimpledrm override removed")

    sudo_remove(DEST, "Boot splash files")

    try:
        if PREV_THEME_FILE.is_file():
            PREV_THEME_FILE.unlink()
            ok("Plymouth state cleared")
    except OSError:
        pass
