"""Static checks for the Plymouth render harness in ``tests/vm/``.

The harness no longer involves Docker / Xvfb / QEMU. It just runs
plymouthd in debug mode on the host against XWayland, screenshots
plymouth's window, then cleans up. We can't drive an interactive
sudo + screen-flash from pytest, so the rendering itself isn't a
pytest test — it's `./test --vm`. But the script has invariants
worth pinning:

- It copies the theme into ``/usr/share/plymouth/themes/`` (the
  standard plymouth dev workflow — see plymouth's own theme docs at
  freedesktop.org/wiki/Software/Plymouth/Themes/).
- It pins plymouth's theme via ``--kernel-command-line``, NOT by
  running ``plymouth-set-default-theme`` — which would touch the
  user's real /etc/plymouth/plymouthd.conf and trigger ``mkinitcpio
  -P``.
- It refuses to run without root (EUID==0) — plymouthd needs root,
  and trying to prompt for sudo from inside the script triggers
  the pam_faillock cascade on terminals where sudo can't read the
  password (VSCode integrated, tmux+OSC133). User is expected to
  invoke as ``sudo ./test --vm`` — same convention as ``./uninstall``.
- It auto-installs missing deps (plymouth / imagemagick / xwininfo).
- It traps EXIT / INT / TERM so a Ctrl-C mid-render still removes
  the copied theme dir and chowns the output back to SUDO_USER.
- It renders both ``boot`` and ``shutdown`` modes so the .script's
  ``Plymouth.GetMode() == 'boot'`` branch is exercised on both sides.
"""

from pathlib import Path


VM_DIR = Path(__file__).resolve().parent / "vm"


def _read(name: str) -> str:
    return (VM_DIR / name).read_text(encoding="utf-8")


# ── render harness file presence ────────────────────────────────────────


def test_render_harness_files_present():
    """The harness is one shell script plus the shared UI helpers.
    README is a separate file; output/ is gitignored."""
    for name in ("render.sh", "_ui.sh"):
        assert (VM_DIR / name).is_file(), f"missing tests/vm/{name}"


def test_render_sh_is_executable():
    """A non-executable render.sh just prints a confusing 'permission
    denied' on first run."""
    import os
    assert os.access(VM_DIR / "render.sh", os.X_OK), \
        "render.sh must be chmod +x"


def test_old_harness_files_are_gone():
    """We've cycled through QEMU, Docker, and Xorg-dummy approaches —
    each was replaced wholesale. Stale files from old approaches will
    confuse anyone reading tests/vm/ for the first time, and stale
    docs link to commands that no longer exist."""
    for stale in (
        # QEMU approach
        "build-base.sh",
        "run-test.sh",
        "run-in-docker.sh",
        "Dockerfile.runner",
        "screendump.py",
        "cloud-init",
        # Docker + Xvfb / Xorg-dummy approach
        "Dockerfile.render",
        "render-inside.sh",
        "xorg-dummy.conf",
    ):
        assert not (VM_DIR / stale).exists(), (
            f"old harness file still present: tests/vm/{stale}"
        )


# ── render.sh invariants ────────────────────────────────────────────────


def test_render_sh_handles_display_when_invoked_via_sudo():
    """When called as `sudo ./test --vm`, sudo's env-keep may or may
    not preserve DISPLAY / XAUTHORITY depending on the user's
    sudoers. Default DISPLAY to :0 (the only sane value for a
    single-seat box) and read XAUTHORITY from $SUDO_USER's home.
    Without that fallback, plymouth's X11 plugin and the screenshot
    tools can't connect to the X server."""
    script = _read("render.sh")
    # Default DISPLAY when sudo strips it.
    assert 'DISPLAY:=' in script, \
        "render.sh must default DISPLAY when sudo strips it"
    # Read XAUTHORITY from SUDO_USER's home.
    assert "SUDO_USER" in script
    assert "XAUTHORITY" in script
    assert ".Xauthority" in script


def test_render_sh_auto_installs_missing_deps():
    """First-run experience should not be 'X: command not found'.
    Plymouth (the daemon being tested), spectacle (Wayland-native
    screenshot via KDE's KWin.ScreenShot2 DBus — X11 tools can't
    capture the composited display on Wayland), xwininfo (locate
    plymouth's window), xdotool (force-activate plymouth's window
    before the capture — shutdown mode doesn't always retain focus,
    and spectacle --activewindow would otherwise grab whatever stole
    focus, like a code editor)."""
    script = _read("render.sh")
    assert "pacman -S" in script
    for pkg in ("plymouth", "spectacle", "xorg-xwininfo", "xdotool"):
        assert pkg in script, (
            f"render.sh must auto-install '{pkg}'"
        )


def test_render_sh_forces_focus_to_plymouth_before_capture():
    """spectacle --activewindow captures whatever has focus. Plymouth
    sometimes doesn't claim/retain it (shutdown mode in particular),
    so an editor or terminal window underneath sneaks into the
    screenshot. xdotool windowactivate forces plymouth to be the
    active window right before the capture."""
    script = _read("render.sh")
    assert "xdotool windowactivate" in script, (
        "must activate plymouth's window before spectacle --activewindow"
    )


def test_render_sh_requires_root_does_not_prompt_internally():
    """The pam_faillock cascade: in some terminals (VSCode integrated
    with OSC133, tmux, sandboxes) sudo's password prompt can't read
    the password — three wrong reads and the account is locked. Same
    convention as ./uninstall: check EUID up front, tell the user to
    re-run with sudo, NEVER prompt from inside the script."""
    script = _read("render.sh")
    assert "EUID -ne 0" in script or "EUID -eq 0" in script, (
        "render.sh must check EUID, not call sudo internally"
    )
    assert "Re-run as:  sudo ./test --vm" in script, (
        "render.sh must tell the user the canonical re-invocation line"
    )
    # And it must NOT actually invoke sudo as a command from inside
    # the script — that's what triggers the broken-password-prompt
    # cascade. The string "sudo ./test --vm" in the user-facing
    # message is fine; what we forbid is any `sudo <cmd>` invocation.
    forbidden = ("sudo cp", "sudo rm", "sudo plymouthd",
                 "sudo plymouth ", "sudo pacman", "sudo kill",
                 "sudo chown", "sudo -v")
    for cmd in forbidden:
        assert cmd not in script, (
            f"render.sh must not invoke `{cmd}` — root upfront, not inline sudo"
        )


def test_render_sh_chowns_output_back_to_invoking_user():
    """We run as root, but the output PNGs + plymouthd logs should
    end up readable by whoever ran `sudo ./test --vm` — otherwise
    they need another sudo to `cat` their own test artifacts. The
    cleanup trap chowns the dir back to $SUDO_USER."""
    script = _read("render.sh")
    assert "SUDO_USER" in script
    assert "chown" in script


def test_render_sh_copies_theme_per_plymouth_dev_convention():
    """Plymouth's own theme docs say: drop your theme into
    /usr/share/plymouth/themes/THEMENAME/. We follow that — plain
    cp, then cleanup with rm -rf on EXIT."""
    script = _read("render.sh")
    assert "cp -r" in script, \
        "render.sh must copy the theme into the system path"
    assert 'rm -rf "$DEST"' in script or "rm -rf $DEST" in script, \
        "render.sh must clean up the copy on exit"


def test_render_sh_refuses_to_clobber_real_install():
    """If the user has already run ./install, /usr/share/plymouth/
    themes/MacTahoeLiquidKde is a real directory with files we don't
    own. cp -r would merge over it and the cleanup rm -rf would
    delete their real install. Refuse instead."""
    script = _read("render.sh")
    assert "-e \"$DEST\"" in script or "-e $DEST" in script, (
        "render.sh must check for an existing install before copying"
    )
    assert "./uninstall" in script, (
        "render.sh should point user at ./uninstall when refusing"
    )


def test_render_sh_avoids_initramfs_rebuild():
    """``plymouth-set-default-theme -R`` triggers mkinitcpio -P which
    rewrites the user's real initramfs. A TEST must never do that.
    Pin the theme via --kernel-command-line instead."""
    script = _read("render.sh")
    assert "--kernel-command-line=" in script
    assert "plymouth.theme=MacTahoeLiquidKde" in script
    # And explicitly NOT calling the real activation tool.
    assert "plymouth-set-default-theme" not in script, (
        "render.sh must not run plymouth-set-default-theme — that "
        "rebuilds the user's initramfs"
    )


def test_render_sh_runs_plymouthd_in_debug_mode():
    """``plymouthd --no-daemon --debug`` is the standard "render once,
    log everything" invocation theme authors use during development."""
    script = _read("render.sh")
    assert "plymouthd" in script
    assert "--no-daemon" in script
    assert "--debug" in script


def test_render_sh_renders_each_relevant_mode():
    """Our .script branches on ``Plymouth.GetMode() == 'boot'`` to
    show/hide the progress bar. We must render both branches —
    plymouthd's --mode supports boot + shutdown (reboot isn't a
    distinct render path)."""
    script = _read("render.sh")
    assert "boot shutdown" in script or "boot reboot shutdown" in script, \
        "render.sh must iterate over plymouth modes"
    assert '--mode="$MODE"' in script or '--mode=boot' in script


def test_render_sh_uses_spectacle_for_wayland_capture():
    """X11 tools (scrot, import, xwd) cannot capture the composited
    Wayland display — they only see XWayland's internal framebuffer,
    which stays black even when plymouth is visibly on screen. On
    KDE Plasma, spectacle is the canonical screenshot tool: it talks
    to KWin's org.kde.KWin.ScreenShot2 DBus interface, which IS the
    compositor and sees everything."""
    script = _read("render.sh")
    assert "spectacle" in script
    # And explicitly NOT the X11-only tools that fail silently on Wayland.
    for x11_only in ("scrot ", "magick import", "import -window"):
        assert x11_only not in script, (
            f"render.sh must not use {x11_only!r} — Wayland needs spectacle"
        )
    # Forensic: log plymouth's WID even though we don't capture by it.
    assert "xwininfo" in script
    assert "plymouthd" in script  # awk match pattern in the WID dump


def test_render_sh_runs_screenshot_as_invoking_user():
    """On KDE Wayland, only the user owning the session can ask the
    compositor for a screenshot — root cannot reach KWin's screenshot
    DBus interface. Drop privileges to $SUDO_USER for spectacle,
    reconstructing the session env (XDG_RUNTIME_DIR /
    DBUS_SESSION_BUS_ADDRESS / WAYLAND_DISPLAY) that sudo stripped."""
    script = _read("render.sh")
    assert "runuser -u" in script and '"$SUDO_USER"' in script, (
        "screenshot must run as $SUDO_USER, not root"
    )
    for var in (
        "XDG_RUNTIME_DIR",
        "DBUS_SESSION_BUS_ADDRESS",
        "WAYLAND_DISPLAY",
    ):
        assert var in script, (
            f"render.sh must reconstruct {var} for the user-context screenshot"
        )


def test_render_sh_cleans_up_symlink_on_any_exit():
    """A trap on EXIT / INT / TERM ensures Ctrl-C or any error
    removes our /usr/share/plymouth/themes symlink. Without this,
    a botched test leaves stale state that confuses ./install."""
    script = _read("render.sh")
    assert "cleanup()" in script
    trap_lines = [
        ln for ln in script.splitlines()
        if ln.strip().startswith("trap ") and "cleanup" in ln
    ]
    assert trap_lines, "render.sh must trap cleanup"
    trap_signals = trap_lines[0]
    for sig in ("EXIT", "INT", "TERM"):
        assert sig in trap_signals, (
            f"cleanup trap must fire on {sig} (currently: {trap_signals})"
        )


# ── /test runner integration ───────────────────────────────────────────


def test_top_level_test_script_routes_vm_flag_to_render():
    """``./test --vm`` is the user-facing entry point. It must dispatch
    to the render harness — none of the long-dead QEMU / Docker paths."""
    runner = (VM_DIR.parent.parent / "test").read_text(encoding="utf-8")
    assert "--vm" in runner
    assert "_run_vm_harness" in runner
    assert "render.sh" in runner
    # The defunct paths must be gone.
    assert "run-in-docker.sh" not in runner
    assert "Dockerfile.render" not in runner


def test_ui_helpers_still_present():
    """_ui.sh is reused by render.sh — keep the same UI vocab across
    every harness command so the output styling stays consistent."""
    ui = _read("_ui.sh")
    for fn in ("ui_section", "ui_step", "ui_ok", "ui_fail", "ui_info"):
        assert f"{fn}()" in ui, f"_ui.sh missing {fn}"


def test_gitignore_excludes_render_output():
    """Captured PNGs + plymouth debug logs must not end up in commits."""
    gi = (VM_DIR.parent.parent / ".gitignore").read_text(encoding="utf-8")
    assert "tests/vm/output/" in gi
