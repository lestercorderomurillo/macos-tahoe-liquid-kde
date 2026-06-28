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

GRUB cmdline auto-patch:
5. After the splash is installed + activated, if the running kernel
   cmdline is missing ``splash``, append it to
   ``GRUB_CMDLINE_LINUX_DEFAULT`` in ``/etc/default/grub`` and
   regenerate the bootloader config. Opt out with
   ``MTTKDE_NO_GRUB_MODIFY=1`` (passed by the CLI's ``--no-grub-modify``
   flag) — the user gets a warning + manual instructions instead.
"""

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
    # ``cmd:pkg`` form — the binary is ``plymouth-set-default-theme`` but
    # the package it ships in is just ``plymouth`` on every distro.
    return ["plymouth-set-default-theme:plymouth"]


def _check_prereqs() -> tuple[bool, bool]:
    """Return ``(splash_missing, mkinitcpio_missing_hook)``.

    The current kernel cmdline lives in /proc/cmdline (the running
    boot). The bootloader-side cmdline lives in /etc/default/grub for
    GRUB users. Mismatch is fine; either having ``splash`` is enough
    to render the splash on the next boot.

    The corner-rendered shutdown splash on some high-DPI displays is
    *suspected* to correlate with a GPU driver (amdgpu / i915 / etc.)
    listed in MODULES=(...). Upstream Plymouth policy (Hans de Goede)
    recommends keeping GPU drivers out of MODULES — the ``kms`` hook
    loads them later. We don't warn on this because the correlation
    isn't strong enough to be worth nagging about."""
    # ── kernel cmdline: need ``splash`` for plymouthd to actually draw ──
    try:
        cmdline = PROC_CMDLINE.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        cmdline = ""
    splash_missing = " splash" not in (" " + cmdline)

    # ── initramfs hook: arch / cachyos / manjaro use mkinitcpio ─
    # Other distros (fedora dracut, debian initramfs-tools) embed plymouth
    # support automatically once the package is installed.
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
    """The opt-out — users set MTTKDE_NO_GRUB_MODIFY=1 (or pass
    --no-grub-modify to the installer, which exports the same env)
    when they want to keep manual control over /etc/default/grub."""
    return os.environ.get("MTTKDE_NO_GRUB_MODIFY", "").lower() not in (
        "1", "true", "yes",
    )


def _grub_is_active_bootloader() -> bool:
    """Both ``/etc/default/grub`` AND a regen binary
    (``grub-mkconfig`` or ``grub2-mkconfig``) must be present before
    we touch GRUB config. Either alone is not enough:

    * ``GRUB_DEFAULT.is_file()`` alone is a leftover trap — many users
      migrated from GRUB to systemd-boot / Limine / rEFInd and the
      file is still on disk from the previous install, but patching
      it does nothing because no regen tool exists to materialise it
      into a loaded grub.cfg.
    * a regen binary alone is meaningless without the config to
      regenerate.

    Together they're a strong signal that GRUB is the active loader
    and the auto-patch will actually take effect on next boot."""
    if not GRUB_DEFAULT.is_file():
        return False
    return have("grub-mkconfig") or have("grub2-mkconfig")


_GRUB_CMDLINE_RE = re.compile(
    r'^(\s*GRUB_CMDLINE_LINUX_DEFAULT\s*=\s*)(["\'])(.*?)\2(\s*)$',
    re.MULTILINE,
)


def _patch_grub_add_splash() -> bool:
    """Append ``splash`` to GRUB_CMDLINE_LINUX_DEFAULT in
    /etc/default/grub iff it isn't already there. Keeps a ``.bak`` next
    to the file in case the user wants to inspect/revert. Returns True
    when the file ended in the expected state (already had splash, or
    we successfully added it)."""
    try:
        with _as_root():
            text = GRUB_DEFAULT.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        warn(f"could not read {GRUB_DEFAULT} ({exc})")
        return False

    match = _GRUB_CMDLINE_RE.search(text)
    if match is None:
        # File has no GRUB_CMDLINE_LINUX_DEFAULT line at all — refuse
        # to invent one. The user's GRUB config is non-standard, leave
        # it alone.
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
            # Best-effort backup. If it already exists from a prior run
            # we keep the older copy (the truly-original one).
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


# ``grub-mkconfig`` is Arch/CachyOS/Gentoo/openSUSE; ``grub2-mkconfig``
# is Fedora/RHEL/Rocky. Either tool can write to either output path
# depending on how the distro packaged it, so we try every binary +
# every output combination in order.
_GRUB_REGENERATE_CANDIDATES = (
    ("grub-mkconfig",  "/boot/grub/grub.cfg"),
    ("grub2-mkconfig", "/boot/grub2/grub.cfg"),
    ("grub-mkconfig",  "/boot/grub2/grub.cfg"),
    ("grub2-mkconfig", "/boot/grub/grub.cfg"),
)


def _regenerate_grub_config() -> bool:
    """Run ``grub[2]-mkconfig -o <output>`` for whichever (binary,
    output) pair exists on the system. Returns True on the first
    success."""
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


def _set_plymouthd_simpledrm(enabled: bool) -> bool:
    """Toggle ``[Daemon] UseSimpledrm`` in /etc/plymouth/plymouthd.conf.

    Why: at shutdown, the GPU driver (amdgpu / nvidia-drm / i915) is
    unloaded BEFORE plymouth shows the shutdown splash. plymouth then
    falls back to whatever framebuffer the kernel console still has —
    usually a tiny 1024x768 VGA — and the splash renders in a corner
    of the high-res panel (~1/4 of the screen, bottom-left or wherever
    fbcon parks it).

    Forcing UseSimpledrm=true makes plymouth always use the UEFI GOP
    framebuffer (which survives DRM driver unloads / re-inits), so the
    shutdown splash stays fullscreen at native resolution — same as
    boot. The boot path is unaffected since boot already uses simpledrm
    before the real driver loads.

    Safe to write: plymouth-set-default-theme already writes to this
    same file (it sets ``Theme=``), so we're amending a file the
    installer is already authoritative for. Uses configparser so we
    don't clobber any unrelated lines a distro/user added.
    """
    # strict=False is mandatory here: ``plymouth-set-default-theme`` writes
    # a fresh ``Theme=…`` line on every invocation WITHOUT deduping prior
    # entries (and casual hand-edits use ``Theme = …`` with surrounding
    # spaces, which look like a second key to the writer but the same one
    # to configparser). Over time the file accumulates duplicates like:
    #     [Daemon]
    #     Theme=MacTahoeLiquidKde
    #     Theme = MacTahoeLiquidKde
    # strict=True raised DuplicateOptionError on those and we silently
    # skipped applying UseSimpledrm — exactly the warning the user
    # surfaced. strict=False keeps the last value (no semantic change),
    # and the write-back below collapses the duplicates as a side effect.
    cp = configparser.ConfigParser(strict=False)
    # plymouthd's keys are case-sensitive (UseSimpledrm vs usesimpledrm
    # is a different lookup). Override the default lowercase normalizer
    # so we preserve the user's existing key casing AND write
    # UseSimpledrm with its expected capitalization.
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
                # space_around_delimiters=False is LOAD-BEARING. The
                # plymouth-set-default-theme shell script (the canonical
                # reader of this file at boot/shutdown) has a broken bash
                # whitespace strip: it splits on '=' but leaves trailing
                # space on the key — ``KEY_NAME='Theme '`` — so the
                # ``[[ "Theme " == "Theme" ]]`` comparison fails. The
                # script then falls through to the distro defaults file
                # (which has ``Theme=bgrt``) and reports our theme as
                # ``bgrt``. plymouthd at shutdown loads what the script
                # reports → shutdown splash is bgrt, not MacTahoeLiquidKde.
                # Writing without spaces around ``=`` matches the format
                # plymouth-set-default-theme itself writes and the parser
                # it can actually read back.
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
        # Activation failed. Try to put the previous theme back so the
        # next boot has a working splash. If we never snapshotted (first
        # run with our theme name already active, somehow) the fallback
        # is the universal bgrt.
        snapshot = _read_previous()
        warn(f"attempting rollback to {snapshot}")
        _activate(snapshot)
        return

    ok("Boot splash activated")

    if _set_plymouthd_simpledrm(True):
        ok("Forced UseSimpledrm=true (fixes corner-rendered shutdown splash)")

    splash_missing, mkinitcpio_missing_hook = _check_prereqs()

    # Auto-patch GRUB cmdline when ``splash`` is missing, unless the
    # user opted out or GRUB isn't actually the active bootloader.
    # Editing /etc/default/grub is a real mutation — we keep a backup
    # and only touch GRUB_CMDLINE_LINUX_DEFAULT.
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
                # GRUB is real but either the user opted out or
                # _patch_grub_add_splash() refused (non-standard config).
                warn("kernel cmdline missing 'splash' — add it to "
                     "GRUB_CMDLINE_LINUX_DEFAULT in /etc/default/grub, "
                     "then run: sudo grub-mkconfig -o /boot/grub/grub.cfg "
                     "(or re-run the installer without "
                     "MTTKDE_NO_GRUB_MODIFY=1)")
            elif GRUB_DEFAULT.is_file():
                # File exists but no regen binary — leftover from a
                # previous OS install, current system uses a different
                # bootloader.
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

    # Remove the UseSimpledrm override so the user's plymouthd.conf
    # is back to whatever default their distro shipped. The previous
    # theme may not need or want this forced.
    if _set_plymouthd_simpledrm(False):
        ok("UseSimpledrm override removed")

    sudo_remove(DEST, "Boot splash files")

    try:
        if PREV_THEME_FILE.is_file():
            PREV_THEME_FILE.unlink()
            ok("Plymouth state cleared")
    except OSError:
        pass
