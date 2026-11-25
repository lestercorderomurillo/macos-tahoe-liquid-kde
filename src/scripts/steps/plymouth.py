"""Plymouth boot splash: installs the theme to /usr/share/plymouth/themes/
and rebuilds the initramfs through the installed distro tooling.
Contract: snapshot the previous theme, then validate BEFORE activating."""

from localization import tr

import configparser
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from distro import (
    package_for, plymouth_activation_commands, plymouth_use_simpledrm, system_lib_dir,
    plymouth_cleanup_commands, plymouth_query_command, plymouth_tools, plymouth_uses_alternatives,
)
from steps._helpers import (
    HOME, _as_root, fail, info, ok, offline, sudo_install_tree, sudo_remove, temp_dir, warn,
)
from utils import have, pkg_install


THEME_NAME = "MacTahoeLiquidKde"
FALLBACK_THEME = "bgrt"
SYSTEM_THEMES_DIR = Path("/usr/share/plymouth/themes")
DEST = SYSTEM_THEMES_DIR / THEME_NAME
STATE_DIR = HOME / ".local/state/mac-tahoe-liquid-kde"
PREV_THEME_FILE = STATE_DIR / "plymouth-previous-theme"
PREV_SIMPLEDRM_NAME = "plymouth-previous-simpledrm.json"

PLYMOUTH_BIN = "plymouth-set-default-theme"
ACTIVATE_TIMEOUT_SEC = 300

MKINITCPIO_CONF = Path("/etc/mkinitcpio.conf")
GRUB_DEFAULT = Path("/etc/default/grub")
PROC_CMDLINE = Path("/proc/cmdline")
PLYMOUTHD_CONF = Path("/etc/plymouth/plymouthd.conf")


def deps():
    # Resolve the Plymouth package; distro.py selects the activation tools.
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
        warn(tr('could not read {GRUB_DEFAULT} ({exc})', GRUB_DEFAULT=GRUB_DEFAULT, exc=exc))
        return False

    match = _GRUB_CMDLINE_RE.search(text)
    if match is None:
        # Non-standard config — refuse to invent the line.
        warn(tr('{GRUB_DEFAULT} has no GRUB_CMDLINE_LINUX_DEFAULT line — skipping auto-patch', GRUB_DEFAULT=GRUB_DEFAULT))
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
        warn(tr('could not patch {GRUB_DEFAULT} ({exc})', GRUB_DEFAULT=GRUB_DEFAULT, exc=exc))
        return False
    return True


# grub-mkconfig (Arch/openSUSE) vs grub2-mkconfig (Fedora/RHEL);
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
            warn(tr('{binary} -o {output} failed: {exc}', binary=binary, output=output, exc=exc))
            continue
        if res.returncode == 0:
            return True
        warn(tr('{binary} -o {output} exited {value3}: {value4}', binary=binary, output=output, value3=res.returncode, value4=(res.stderr or '').strip().splitlines()[-1:] or ['(no output)']))
    return False


def _current_default_theme() -> str | None:
    """Query the distro selector, preserving an alternative's exact path."""
    try:
        res = subprocess.run(
            plymouth_query_command(),
            check=False, capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if res.returncode:
        return None
    name = (res.stdout or "").strip()
    if plymouth_uses_alternatives():
        name = next((line.removeprefix("Value: ") for line in name.splitlines()
                     if line.startswith("Value: ")), "")
        # Preserve the exact registered path, including custom locations.
        if Path(name).stem == THEME_NAME:
            return THEME_NAME
    return name or None


def _validate_theme(theme_dir: Path) -> str | None:
    """None if the theme looks valid, else a short error. Parses the
    .plymouth metadata and checks every Image("…") in the .script resolves."""
    meta_path = theme_dir / f"{THEME_NAME}.plymouth"
    script_path = theme_dir / f"{THEME_NAME}.script"

    if not meta_path.is_file():
        return tr("metadata missing: {path}", path=meta_path)
    if not script_path.is_file():
        return tr("script missing: {path}", path=script_path)

    cp = configparser.ConfigParser(strict=True)
    try:
        cp.read(str(meta_path), encoding="utf-8")
    except configparser.Error as exc:
        return tr("metadata unparseable ({error})", error=exc.__class__.__name__)

    if "Plymouth Theme" not in cp.sections():
        return tr("metadata missing [Plymouth Theme] section")
    if "script" not in cp.sections():
        return tr("metadata missing [script] section")
    for key in ("Name", "ModuleName"):
        if not cp.get("Plymouth Theme", key, fallback=""):
            return tr("metadata missing {key}", key=key)
    for key in ("ImageDir", "ScriptFile"):
        if not cp.get("script", key, fallback=""):
            return tr("metadata missing script.{key}", key=key)

    try:
        script_text = script_path.read_text(encoding="utf-8")
    except OSError as exc:
        return tr("script unreadable ({error})", error=exc)
    refs = re.findall(r'Image\("([^"]+)"\)', script_text)
    for ref in refs:
        if not (theme_dir / ref).is_file():
            return tr("script references missing asset: {path}", path=ref)
    return None


def _script_plugin_path() -> Path:
    return system_lib_dir() / "plymouth/script.so"


def _ensure_script_plugin() -> bool:
    script_plugin = _script_plugin_path()
    if script_plugin.is_file():
        return True
    pkg = package_for("plymouth-script-plugin", "plymouth")
    warn(tr('{script_plugin} missing — installing {pkg}...', script_plugin=script_plugin, pkg=pkg))
    if not pkg_install(pkg):
        warn(tr('Plymouth script plugin install failed — leaving previous splash active'))
        return False
    if script_plugin.is_file():
        ok(tr('Plymouth script plugin installed'))
        return True
    warn(tr('{script_plugin} still missing after installing {pkg} — leaving previous splash active', script_plugin=script_plugin, pkg=pkg))
    return False


def _run_as_root(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Spawn ``cmd`` with euid 0 — plymouth-set-default-theme needs root
    (it writes plymouthd.conf and rebuilds the initramfs)."""
    with _as_root():
        return subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=timeout,
        )


def _activate(theme: str) -> bool:
    """Set the theme and complete the distro's initramfs rebuild transaction."""
    for command in plymouth_activation_commands(theme):
        label = " ".join(command)
        try:
            res = _run_as_root(command, ACTIVATE_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            fail(tr('{label} timed out after {ACTIVATE_TIMEOUT_SEC}s', label=label, ACTIVATE_TIMEOUT_SEC=ACTIVATE_TIMEOUT_SEC))
            return False
        except OSError as exc:
            fail(f"{label}: {exc}")
            return False
        if res.returncode != 0:
            tail = (res.stderr or res.stdout or "").strip().splitlines()[-5:]
            fail(tr('{label} failed (exit {value2})', label=label, value2=res.returncode))
            for line in tail:
                print(f"     \033[2m{line}\033[0m")
            return False
    return True


def _read_plymouthd_config() -> configparser.ConfigParser | None:
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
            warn(tr('plymouthd.conf unparseable ({value1}) — leaving UseSimpledrm setting unchanged', value1=exc.__class__.__name__))
            return None
    return cp


def _set_plymouthd_simpledrm(value: bool | str | None) -> bool:
    """Set or remove ``[Daemon] UseSimpledrm`` without clobbering config.

    ``None`` removes the key. A string is used only when restoring the exact
    value captured before install.
    """
    cp = _read_plymouthd_config()
    if cp is None:
        return False
    if not cp.has_section("Daemon"):
        cp.add_section("Daemon")
    if value is None and cp.has_option("Daemon", "UseSimpledrm"):
        cp.remove_option("Daemon", "UseSimpledrm")
    elif value is None:
        return True  # already absent, nothing to do
    else:
        if isinstance(value, bool):
            rendered = "true" if value else "0"
        else:
            rendered = value
        cp.set("Daemon", "UseSimpledrm", rendered)

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
        warn(tr('could not update {PLYMOUTHD_CONF} ({exc})', PLYMOUTHD_CONF=PLYMOUTHD_CONF, exc=exc))
        return False
    return True


def _previous_simpledrm_file() -> Path:
    return STATE_DIR / PREV_SIMPLEDRM_NAME


def _save_previous_simpledrm(*, legacy_override: bool) -> bool:
    """Snapshot the pre-install key once, preserving repeated-install state.

    Older releases tracked only the previous theme and always forced ``true``.
    When upgrading an already-active MacTahoe theme, treat that untracked value
    as our legacy override so uninstall removes it.
    """
    state_file = _previous_simpledrm_file()
    if state_file.is_file():
        return True
    cp = _read_plymouthd_config()
    if cp is None:
        return False
    present = cp.has_option("Daemon", "UseSimpledrm") and not legacy_override
    value = cp.get("Daemon", "UseSimpledrm") if present else None
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps({"present": present, "value": value}) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        warn(tr('could not snapshot previous UseSimpledrm setting ({exc})', exc=exc))
        return False
    return True


def _restore_previous_simpledrm() -> bool:
    """Restore the captured value; remove untracked legacy overrides."""
    state_file = _previous_simpledrm_file()
    try:
        payload = json.loads(state_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _set_plymouthd_simpledrm(None)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        warn(tr('could not read previous UseSimpledrm setting ({exc})', exc=exc))
        return False

    if not isinstance(payload, dict):
        warn(tr('previous UseSimpledrm state has an invalid shape'))
        return False
    if payload.get("present") is True and isinstance(payload.get("value"), str):
        return _set_plymouthd_simpledrm(payload["value"])
    return _set_plymouthd_simpledrm(None)


def _save_previous(name: str) -> bool:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        PREV_THEME_FILE.write_text(name + "\n", encoding="utf-8")
        return True
    except OSError as exc:
        fail(tr('could not snapshot previous Plymouth theme ({exc})', exc=exc))
        return False


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
    missing = [tool for tool in plymouth_tools() if not have(tool)]
    if missing:
        warn(tr('{PLYMOUTH_BIN} not found — skipping boot splash', PLYMOUTH_BIN=", ".join(missing)))
        return

    previous = _current_default_theme()
    if plymouth_uses_alternatives() and not previous:
        fail(tr('could not snapshot previous Plymouth theme ({exc})', exc="default.plymouth has no selected value"))
        return
    # Don't snapshot ourselves — a re-run shouldn't overwrite the user's
    # original theme with our own name.
    if previous and previous != THEME_NAME:
        if not _save_previous(previous):
            return

    with temp_dir("mttkde-plymouth") as temporary:
        staged = temporary / THEME_NAME
        shutil.copytree(offline("plymouth", THEME_NAME), staged)
        script = staged / f"{THEME_NAME}.script"
        prompt = json.dumps(tr("Password:"), ensure_ascii=False)
        script.write_text(script.read_text(encoding="utf-8").replace(
            'prompt = "Password:";', f'prompt = {prompt};'), encoding="utf-8")
        if not sudo_install_tree(staged, DEST, tr('Boot splash files')):
            return

    err = _validate_theme(DEST)
    if err:
        fail(tr('Boot splash validation failed: {err}', err=err))
        info(tr('Theme files left on disk but NOT activated — previous splash still active'))
        return

    if not _ensure_script_plugin():
        info(tr('Theme files left on disk but NOT activated — previous splash still active'))
        return

    # This must be written before -R: plymouth-set-default-theme rebuilds the
    # initramfs, so writing it afterward does not affect the next boot.
    if not _save_previous_simpledrm(legacy_override=previous == THEME_NAME):
        info(tr('Theme files left on disk but NOT activated — previous Plymouth renderer policy could not be saved'))
        return
    use_simpledrm = plymouth_use_simpledrm()
    if not _set_plymouthd_simpledrm(use_simpledrm):
        info(tr('Theme files left on disk but NOT activated — Plymouth renderer policy could not be applied'))
        return

    if not _activate(THEME_NAME):
        # Roll back so the next boot has a working splash; with no snapshot
        # the fallback is the universal bgrt.
        snapshot = _read_previous()
        _restore_previous_simpledrm()
        warn(tr('attempting rollback to {snapshot}', snapshot=snapshot))
        _activate(snapshot)
        return

    ok(tr('Boot splash activated'))
    if use_simpledrm:
        ok(tr('Forced UseSimpledrm=true (keeps the shutdown splash full-size)'))
    else:
        ok(tr('Set UseSimpledrm=0 for this distro (avoids the boot framebuffer jump)'))

    splash_missing, mkinitcpio_missing_hook = _check_prereqs()

    # Auto-patch the GRUB cmdline only when ``splash`` is missing, the user
    # hasn't opted out, and GRUB is genuinely the active bootloader.
    grub_active = _grub_is_active_bootloader()
    if splash_missing and _grub_auto_patch_enabled() and grub_active:
        if _patch_grub_add_splash():
            ok(tr("Added 'splash' to GRUB_CMDLINE_LINUX_DEFAULT"))
            if _regenerate_grub_config():
                ok(tr('Regenerated bootloader config'))
                splash_missing = False  # remediation succeeded
            else:
                warn(tr('could not regenerate bootloader config — run grub-mkconfig manually before next reboot'))

    if splash_missing or mkinitcpio_missing_hook:
        warn(tr('boot splash files are installed, but the splash will NOT appear at next boot until you fix the items below:'))
        if splash_missing:
            if grub_active:
                # User opted out or _patch_grub_add_splash() refused.
                warn(tr("kernel cmdline missing 'splash' — add it to GRUB_CMDLINE_LINUX_DEFAULT in /etc/default/grub, then run: sudo grub-mkconfig -o /boot/grub/grub.cfg (or re-run the installer without MTTKDE_NO_GRUB_MODIFY=1)"))
            elif GRUB_DEFAULT.is_file():
                # Leftover /etc/default/grub, no regen binary — a different
                # bootloader is active.
                warn(tr("kernel cmdline missing 'splash'. Found a leftover /etc/default/grub but no grub-mkconfig / grub2-mkconfig on PATH — your active bootloader is likely systemd-boot / Limine / rEFInd. Edit the appropriate loader config manually (systemd-boot: /boot/loader/entries/*.conf, limine: /boot/limine.conf, rEFInd: /boot/EFI/refind/refind.conf)."))
            else:
                warn(tr("kernel cmdline missing 'splash' — add it to your bootloader configuration (systemd-boot: /boot/loader/entries/*.conf, limine: /boot/limine.conf)"))
        if mkinitcpio_missing_hook:
            warn(tr("/etc/mkinitcpio.conf HOOKS line is missing 'plymouth' — add it after 'udev' (or 'systemd' on systemd-init) and BEFORE 'encrypt'/'filesystems', then run: sudo mkinitcpio -P"))
    else:
        info(tr('Next reboot will show the {THEME_NAME} splash.', THEME_NAME=THEME_NAME))
    rollback = " && ".join("sudo " + shlex.join(command)
                           for command in plymouth_activation_commands(_read_previous()))
    info(tr('Rollback: {command}', command=rollback))


def uninstall() -> None:
    previous = _read_previous()

    # Restore the renderer policy before -R rebuilds the previous theme into
    # the initramfs.
    simpledrm_restored = _restore_previous_simpledrm()
    if simpledrm_restored:
        ok(tr('Previous UseSimpledrm setting restored'))

    if all(have(tool) for tool in plymouth_tools()):
        if _activate(previous):
            ok(tr('Boot splash restored to {previous}', previous=previous))
        else:
            if plymouth_uses_alternatives():
                return
            warn(tr('could not restore boot splash to {previous} — continuing cleanup', previous=previous))
    else:
        message = tr('{PLYMOUTH_BIN} not available — skipping splash restore', PLYMOUTH_BIN=", ".join(plymouth_tools()))
        if plymouth_uses_alternatives():
            fail(message)
            return
        warn(message)

    for command in plymouth_cleanup_commands(THEME_NAME):
        try:
            result = _run_as_root(command, ACTIVATE_TIMEOUT_SEC)
        except (OSError, subprocess.TimeoutExpired) as exc:
            fail(f"{' '.join(command)}: {exc}")
            return
        if result.returncode:
            fail(f"{' '.join(command)}: {result.stderr.strip()}")
            return

    sudo_remove(DEST, tr('Boot splash files'))

    try:
        if PREV_THEME_FILE.is_file():
            PREV_THEME_FILE.unlink()
        previous_simpledrm = _previous_simpledrm_file()
        if simpledrm_restored and previous_simpledrm.is_file():
            previous_simpledrm.unlink()
        if simpledrm_restored:
            ok(tr('Plymouth state cleared'))
        else:
            ok(tr('Previous Plymouth theme state cleared'))
    except OSError:
        pass
    if not simpledrm_restored:
        warn(tr('Plymouth renderer recovery state retained because restoration failed'))
