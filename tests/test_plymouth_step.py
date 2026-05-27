"""Tests for the Plymouth boot splash step.

Two flavours:

1. **Theme-file integrity.** Parse the shipped ``.plymouth`` INI, walk
   the ``.script`` for ``Image("…")`` references, and check bracket
   balance. These catch the kind of regression where a rename leaves
   a dangling asset reference and Plymouth silently falls back to its
   text splash on the next boot.

2. **Install / uninstall behaviour.** Stub ``sudo_install_tree`` /
   ``sudo_remove`` / ``_as_root`` and the ``plymouth-set-default-theme``
   subprocess to confirm: the previous theme is snapshotted before we
   touch anything, the activate call carries ``-R`` (without it the
   initramfs is never rebuilt and the new splash never appears), a
   broken metadata file aborts BEFORE activation, and uninstall always
   restores the snapshot — or falls back to ``bgrt`` when state is
   missing.
"""

import configparser
import re
from contextlib import contextmanager
from pathlib import Path

import pytest

from steps import plymouth


REPO = Path(__file__).resolve().parent.parent
THEME_SRC = REPO / "src/offline/plymouth/MacTahoeLiquidKde"


# ──────────────────────── theme-file integrity ──────────────────────────


def test_plymouth_metadata_parses():
    meta = THEME_SRC / "MacTahoeLiquidKde.plymouth"
    assert meta.is_file(), f"missing metadata: {meta}"
    cp = configparser.ConfigParser(strict=True)
    cp.read(str(meta), encoding="utf-8")
    assert "Plymouth Theme" in cp.sections()
    assert "script" in cp.sections()
    assert cp.get("Plymouth Theme", "Name") == "MacTahoeLiquidKde"
    assert cp.get("Plymouth Theme", "ModuleName") == "script"
    image_dir = cp.get("script", "ImageDir")
    script_file = cp.get("script", "ScriptFile")
    assert image_dir == "/usr/share/plymouth/themes/MacTahoeLiquidKde"
    assert script_file == (
        "/usr/share/plymouth/themes/MacTahoeLiquidKde/MacTahoeLiquidKde.script"
    )


def test_plymouth_script_references_resolve():
    script = THEME_SRC / "MacTahoeLiquidKde.script"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    refs = re.findall(r'Image\("([^"]+)"\)', text)
    assert refs, "script declares no Image() refs — typo in regex or theme?"
    missing = [r for r in refs if not (THEME_SRC / r).is_file()]
    assert not missing, f"dangling image refs: {missing}"


def test_plymouth_script_brackets_balanced():
    """Plymouth's parser silently falls back to text when brackets are
    unbalanced. Validate manually since we have no parser to run."""
    script = THEME_SRC / "MacTahoeLiquidKde.script"
    raw = script.read_text(encoding="utf-8")
    # Strip string literals and line comments so a `#` or `}` inside
    # text doesn't pollute the count.
    no_strings = re.sub(r'"[^"]*"', '""', raw)
    no_comments = re.sub(r"#.*$", "", no_strings, flags=re.MULTILINE)
    for open_ch, close_ch, name in (
        ("{", "}", "braces"),
        ("(", ")", "parens"),
        ("[", "]", "brackets"),
    ):
        n_open = no_comments.count(open_ch)
        n_close = no_comments.count(close_ch)
        assert n_open == n_close, (
            f"unbalanced {name}: open={n_open} close={n_close}"
        )


def test_plymouth_theme_directory_is_minimal():
    """The theme ships exactly: metadata, the .script, the logo
    (PNG + SVG source), and the two progress-bar assets (PNG + SVG
    source for each). Anything else (LICENSE-* attribution leftovers,
    dialog PNGs, the upstream's progress_box / progress_bar names)
    would be dead weight — and worse, would imply behaviour the
    .script doesn't actually implement."""
    actual = {p.name for p in THEME_SRC.iterdir() if p.is_file()}
    expected = {
        "MacTahoeLiquidKde.plymouth",
        "MacTahoeLiquidKde.script",
        "boot.png",
        "boot.svg",
        "progress_track.png",
        "progress_track.svg",
        "progress_fill.png",
        "progress_fill.svg",
    }
    assert actual == expected, (
        f"theme dir drift: extra={actual - expected} "
        f"missing={expected - actual}"
    )


def test_plymouth_script_has_no_fork_attribution():
    """The .script was rewritten from scratch. There must be no
    'forked from X', no upstream author names, no Pear-OS references
    leaking into the header — per CLAUDE.md branding policy."""
    text = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    meta = (THEME_SRC / "MacTahoeLiquidKde.plymouth").read_text(encoding="utf-8")
    blacklist = (
        "forked",
        "fork of",
        "based on",
        "navisjayaseelan",
        "apple-mac-plymouth",
        "pear os",
        "pearos",
    )
    for needle in blacklist:
        assert needle.lower() not in text.lower(), (
            f"{needle!r} found in .script — rewrite, don't attribute"
        )
        assert needle.lower() not in meta.lower(), (
            f"{needle!r} found in .plymouth — rewrite, don't attribute"
        )


def test_plymouth_script_paints_black_background():
    """A non-black background flashes between GRUB and the splash if
    the .script ever crashes mid-init. Pinning both top + bottom colours
    to pure black means the worst-case render is a black screen — the
    same colour the kernel was on a tick earlier."""
    text = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    assert "Window.SetBackgroundTopColor(0, 0, 0)" in text
    assert "Window.SetBackgroundBottomColor(0, 0, 0)" in text


def test_plymouth_script_scales_logo_dynamically():
    """The whole point of the rewrite was to drop the upstream's
    7-resolution if/elif ladder in favour of a single proportional
    scale. The 0.07 factor matches what upstream apple-mac-plymouth
    shipped (hardcoded 100-220px depending on resolution); 0.10–0.18
    looked oversized at real boot on 4K (the high-res source PNG
    downscales crisper than upstream's tiny PNG, so visually
    'bigger' at the same percentage)."""
    text = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    assert "0.07" in text, "missing dynamic-scale ratio 0.07"
    # Math.Int() rounds the float scale back to an int pixel size —
    # without it Plymouth refuses to render fractional pixel widths.
    assert "Math.Int" in text
    # Source loaded once, scaled per-monitor inside the for loop.
    assert "logo_source.Scale(logo_target, logo_target)" in text


def test_plymouth_script_centers_logo_after_scale():
    """Centering math must happen AFTER the scale or the logo lands
    off-centre at non-1080p resolutions. Compute against the SCALED
    sprite's GetWidth()/GetHeight(), not the source image dimensions."""
    text = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    assert re.search(
        r"SetX\s*\(\s*Window\.GetX\(\)\s*\+\s*screen_w\s*/\s*2"
        r"\s*-\s*logo_image\.GetWidth\(\)\s*/\s*2\s*\)",
        text,
    ), "missing horizontally-centered SetX(Window.GetX() + screen_w/2 - logo_image.GetWidth()/2)"
    assert re.search(
        r"SetY\s*\(\s*Window\.GetY\(\)\s*\+\s*screen_h\s*/\s*2"
        r"\s*-\s*logo_image\.GetHeight\(\)\s*/\s*2\s*\)",
        text,
    ), "missing vertically-centered SetY(Window.GetY() + screen_h/2 - logo_image.GetHeight()/2)"


def test_plymouth_script_handles_portrait_orientation():
    """Tablets / rotated panels report screen_w < screen_h. Without an
    explicit branch the logo would scale to 18% of HEIGHT on a portrait
    display, which is visually too big. Branch on the smaller axis."""
    text = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    assert re.search(r"screen_w\s*<\s*screen_h", text), (
        "no portrait branch — logo will overflow on rotated displays"
    )


def test_plymouth_script_loads_each_image_only_once():
    """Image() reads from disk every call. Calling it inside a callback
    or per-monitor loop would re-read the file on every tick / window.
    Pin the load-once invariant for all three sources."""
    text = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    for name in ("boot.png", "progress_track.png", "progress_fill.png"):
        refs = re.findall(rf'Image\("{re.escape(name)}"\)', text)
        assert len(refs) == 1, (
            f"{name} must be loaded exactly once, found {len(refs)} calls"
        )


def test_plymouth_script_wires_required_callbacks():
    """Plymouth invokes named callbacks for quit + boot progress +
    message display. Without them the splash either crashes or
    silently shows a stale frame when the boot path tries to surface
    fsck/recovery messages or progress."""
    text = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    for cb in (
        "Plymouth.SetQuitFunction",
        "Plymouth.SetBootProgressFunction",
        "Plymouth.SetDisplayMessageFunction",
        "Plymouth.SetHideMessageFunction",
    ):
        assert cb in text, f"missing callback wiring: {cb}"


def test_plymouth_script_does_not_implement_password_callback():
    """LUKS prompts fall back to Plymouth's built-in text dialog.
    We deliberately don't ship password UI assets, so wiring
    SetPasswordFunction would crash the moment a LUKS prompt fires
    (missing entry/bullet references). Strip comments before checking
    — the header comment lists the callback as 'deliberately NOT
    wired', and that mention is intentional."""
    raw = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    no_comments = re.sub(r"#.*$", "", raw, flags=re.MULTILINE)
    assert "SetPasswordFunction" not in no_comments, (
        "password callback requires entry/bullet PNGs we don't ship"
    )


def test_plymouth_script_does_not_reference_deleted_assets():
    """The dialog assets (box, lock, entry, bullet) AND the upstream's
    progress_box / progress_bar PNG names were dropped. Our own
    progress assets are progress_track.png + progress_fill.png — make
    sure no stale Image() reference points at the old names, since
    Plymouth would silently text-splash on the first boot that hit
    the missing-asset path."""
    text = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    for name in ("box.png", "lock.png", "entry.png", "bullet.png",
                 "progress_box.png", "progress_bar.png"):
        assert name not in text, (
            f"stale reference to deleted asset: {name}"
        )


def test_plymouth_script_message_state_initialised():
    """on_show_message stacks console messages top-left; that requires
    a parallel array + counter + running Y offset declared at module
    scope. Missing any of the three would crash the first time a
    message arrived."""
    text = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    for sym in ("message_y", "message_sprites", "message_count"):
        assert sym in text, f"message bookkeeping symbol missing: {sym}"


def test_plymouth_script_uses_single_window_logic():
    """v0.13.0 tried to iterate Window.GetCount() and build per-monitor
    sprite arrays. That works in plymouth's X11 plugin (used by our
    render harness) but ships BLACK on plymouth's DRM renderer at real
    boot — both monitors black, no logo. The DRM renderer mirrors a
    single Sprite across every connected display automatically, so the
    correct approach is single-Window logic with NO loop over heads."""
    raw = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    # Strip comments before forbidding patterns — the header comment
    # explains the v0.13.0 mistake, those literal mentions are fine.
    code = re.sub(r"#.*$", "", raw, flags=re.MULTILINE)
    # The bare (no-index) Window calls — plymouth handles mirroring.
    assert "Window.GetWidth()" in code
    assert "Window.GetHeight()" in code
    assert "Window.GetX()" in code
    assert "Window.GetY()" in code
    # Forbid the v0.13.0 multi-monitor approach as ACTUAL CODE.
    assert "Window.GetCount()" not in code, (
        "Window.GetCount() loop ships black on DRM renderer — see v0.13.0 regression"
    )
    assert "window_count" not in code, (
        "per-monitor enumeration broke real-boot rendering"
    )


def test_plymouth_script_shutdown_layout_shares_boot_path():
    """Mode-specific centering drift (the upstream bug where shutdown's
    icon was slightly off from boot's) is impossible if BOTH modes go
    through the same SetX/SetY math. Enforce that the script has no
    mode-conditional logo positioning — the only mode branch should be
    progress visibility."""
    text = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    # Mode literals appear only in: `mode = Plymouth.GetMode()` and the
    # `show_progress = (mode == "boot")` predicate (and comments).
    mode_string_uses = [
        ln for ln in text.splitlines()
        if re.search(r'mode\s*==\s*"(boot|shutdown|reboot)"', ln)
    ]
    # Only one comparison: the show_progress predicate. Anything else
    # would be a per-mode layout branch.
    assert len(mode_string_uses) == 1, (
        f"unexpected mode-conditional code: {mode_string_uses}"
    )
    assert "show_progress" in mode_string_uses[0]


def test_plymouth_script_progress_visibility_gated_by_mode():
    """The progress bar is conceptually only meaningful on boot —
    shutdown/reboot have no monotonic completion to track. Both the
    SetBootProgressFunction binding AND the track's visibility must
    be gated on the boot-mode predicate."""
    text = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    assert re.search(
        r'show_progress\s*=\s*\(\s*mode\s*==\s*"boot"\s*\)', text,
    ), "show_progress must derive from mode == 'boot'"
    # The callback binding only runs when show_progress is true.
    assert re.search(
        r"if\s*\(\s*show_progress\s*\)\s*\n?\s*Plymouth\.SetBootProgressFunction",
        text,
    ), "SetBootProgressFunction must be guarded by show_progress"
    # The track sprite is hidden on non-boot modes.
    assert "!show_progress" in text, (
        "track sprite visibility must invert show_progress on non-boot"
    )


def test_plymouth_script_progress_bar_scales_horizontally():
    """The fill grows in WIDTH only — height stays fixed. If you scale
    both axes, the bar warps as progress advances."""
    text = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    assert re.search(
        r"fill_source\.Scale\(\s*Math\.Int\(\s*bar_w\s*\*\s*progress\s*\)"
        r"\s*,\s*bar_h\s*\)",
        text,
    ), "fill.Scale must be (bar_w * progress, bar_h) — width only"


def test_plymouth_script_clamps_progress_range():
    """Plymouth occasionally sends progress values slightly outside
    [0, 1] near the boot-finished tick. Without clamps the fill ends
    up wider than the track, or Scale() is called with a negative
    width which silently produces a zero-sized image."""
    text = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    assert re.search(r"if\s*\(\s*progress\s*<\s*0\s*\)", text), (
        "missing lower-bound clamp on progress"
    )
    assert re.search(r"if\s*\(\s*progress\s*>\s*1\s*\)", text), (
        "missing upper-bound clamp on progress"
    )


def test_plymouth_script_progress_bar_positioned_below_logo():
    """The bar's Y must derive from the logo sprite — not from a
    screen-percentage constant. That keeps the bar at a fixed gap
    below the logo regardless of resolution / aspect ratio."""
    text = (THEME_SRC / "MacTahoeLiquidKde.script").read_text(encoding="utf-8")
    assert re.search(
        r"bar_y\s*=\s*logo\.GetY\(\)\s*\+\s*logo_image\.GetHeight\(\)",
        text,
    ), "bar_y must be derived from logo sprite + logo image height"


def test_plymouth_step_module_has_install_paths_pinned():
    """The system theme dir is a kernel-adjacent path. Pin it so a
    refactor that drifts ``DEST`` somewhere harmless doesn't leave the
    theme orphaned next to plymouthd's actual search path."""
    assert str(plymouth.DEST) == (
        "/usr/share/plymouth/themes/MacTahoeLiquidKde"
    )
    assert plymouth.THEME_NAME == "MacTahoeLiquidKde"
    assert plymouth.FALLBACK_THEME == "bgrt"


# ──────────────────────── install / uninstall ───────────────────────────


@contextmanager
def _noop_as_root():
    yield


class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _stub(monkeypatch, *, have_bin=True, current_theme="breeze",
          activate_rc=0):
    """Wire stubs that capture every effectful call the step makes.

    Returns a ``calls`` dict whose values are:
    - ``"subprocess"`` → list of (argv, kwargs).
    - ``"install_tree"`` / ``"remove"`` → list of (src/path, dest).
    - ``"as_root"`` → bool flagging whether the context manager fired.
    """
    calls = {"subprocess": [], "install_tree": [], "remove": [], "as_root": False}

    monkeypatch.setattr(plymouth, "have", lambda cmd: have_bin)
    # Install tests assert on the activation flow, not the boot prereqs.
    # The prereq check has its own dedicated tests below, so neutralise
    # it here to prevent host-state leakage (real /proc/cmdline, real
    # /etc/mkinitcpio.conf) from flipping assertions on different CI
    # machines.
    monkeypatch.setattr(plymouth, "_check_prereqs", lambda: (False, False))

    def fake_run(argv, **kwargs):
        calls["subprocess"].append((list(argv), kwargs))
        # First no-arg call queries the current theme.
        if argv == [plymouth.PLYMOUTH_BIN]:
            return _FakeProc(stdout=(current_theme or "") + "\n")
        # Any -R call is an activation. Default to success.
        if len(argv) >= 3 and argv[1] == "-R":
            return _FakeProc(returncode=activate_rc, stderr="boom\n")
        return _FakeProc()

    monkeypatch.setattr(plymouth.subprocess, "run", fake_run)

    @contextmanager
    def fake_as_root():
        calls["as_root"] = True
        yield

    monkeypatch.setattr(plymouth, "_as_root", fake_as_root)

    def fake_install_tree(src, dest, label=None):
        calls["install_tree"].append((Path(src), Path(dest)))
        Path(dest).mkdir(parents=True, exist_ok=True)
        # Stage a *valid* theme on disk so _validate_theme passes.
        meta = Path(dest) / "MacTahoeLiquidKde.plymouth"
        meta.write_text(
            "[Plymouth Theme]\n"
            "Name=MacTahoeLiquidKde\n"
            "ModuleName=script\n"
            "\n"
            "[script]\n"
            "ImageDir=/usr/share/plymouth/themes/MacTahoeLiquidKde\n"
            "ScriptFile=/usr/share/plymouth/themes/MacTahoeLiquidKde/MacTahoeLiquidKde.script\n"
        )
        script = Path(dest) / "MacTahoeLiquidKde.script"
        script.write_text(
            'logo = Image("boot.png");\n'
            'Window.SetBackgroundTopColor(0, 0, 0);\n'
        )
        (Path(dest) / "boot.png").write_bytes(b"\x89PNG\r\n")
        return True

    monkeypatch.setattr(plymouth, "sudo_install_tree", fake_install_tree)

    def fake_remove(path, label=None):
        calls["remove"].append(Path(path))
        return True

    monkeypatch.setattr(plymouth, "sudo_remove", fake_remove)

    return calls


def _activation_calls(calls):
    return [argv for argv, _ in calls["subprocess"]
            if len(argv) >= 2 and argv[1] == "-R"]


def test_install_skips_when_plymouth_binary_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR",
                        tmp_path / ".local/state/mac-tahoe-liquid-kde")
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE",
                        tmp_path / ".local/state/mac-tahoe-liquid-kde/plymouth-previous-theme")
    calls = _stub(monkeypatch, have_bin=False)
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest")

    plymouth.install()

    assert calls["install_tree"] == []
    assert _activation_calls(calls) == []
    assert not calls["as_root"]


def test_install_snapshots_previous_theme(tmp_path, monkeypatch):
    state_dir = tmp_path / ".local/state/mac-tahoe-liquid-kde"
    prev_file = state_dir / "plymouth-previous-theme"
    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR", state_dir)
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE", prev_file)
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest/MacTahoeLiquidKde")

    calls = _stub(monkeypatch, have_bin=True, current_theme="breeze")
    plymouth.install()

    assert prev_file.is_file()
    assert prev_file.read_text().strip() == "breeze"
    # Activation ran with -R + our theme name.
    assert [plymouth.PLYMOUTH_BIN, "-R", "MacTahoeLiquidKde"] in _activation_calls(calls)
    assert calls["as_root"]


def test_install_does_not_overwrite_snapshot_with_own_name(tmp_path, monkeypatch):
    """Re-running ./install when our theme is already active must NOT
    overwrite the snapshot with our own name — otherwise uninstall
    would loop back to us and bgrt is never reached."""
    state_dir = tmp_path / "state"
    prev_file = state_dir / "plymouth-previous-theme"
    state_dir.mkdir(parents=True)
    prev_file.write_text("breeze\n")

    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR", state_dir)
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE", prev_file)
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest/MacTahoeLiquidKde")

    _stub(monkeypatch, have_bin=True, current_theme="MacTahoeLiquidKde")
    plymouth.install()

    assert prev_file.read_text().strip() == "breeze"


def test_install_aborts_on_invalid_metadata(tmp_path, monkeypatch):
    """A broken .plymouth on disk MUST NOT trigger the activate call.
    Leaving the previous theme intact is the whole point of the
    pre-activation validation."""
    state_dir = tmp_path / "state"
    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR", state_dir)
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE",
                        state_dir / "plymouth-previous-theme")
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest/MacTahoeLiquidKde")

    calls = _stub(monkeypatch, have_bin=True, current_theme="breeze")

    # Override the staged-theme fake to write a broken metadata file.
    def broken_install_tree(src, dest, label=None):
        calls["install_tree"].append((Path(src), Path(dest)))
        Path(dest).mkdir(parents=True, exist_ok=True)
        (Path(dest) / "MacTahoeLiquidKde.plymouth").write_text(
            "[Plymouth Theme]\nName=MacTahoeLiquidKde\n"
            # Missing [script] section, missing ScriptFile.
        )
        return True

    monkeypatch.setattr(plymouth, "sudo_install_tree", broken_install_tree)
    plymouth.install()

    # The query call ran (no-arg) but no -R call did.
    assert _activation_calls(calls) == []


def test_install_activation_call_includes_R_flag(tmp_path, monkeypatch):
    """The -R flag is what triggers the initramfs rebuild. Without it
    the on-disk theme is set but no initrd ever picks it up, so the
    next boot keeps showing the previous splash — a silent regression
    that's near-impossible to spot manually."""
    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE",
                        tmp_path / "state/plymouth-previous-theme")
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest/MacTahoeLiquidKde")

    calls = _stub(monkeypatch, have_bin=True)
    plymouth.install()

    for argv in _activation_calls(calls):
        assert "-R" in argv, f"activation call missing -R: {argv}"


def test_install_attempts_rollback_when_activation_fails(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    prev_file = state_dir / "plymouth-previous-theme"
    prev_file.write_text("breeze\n")

    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR", state_dir)
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE", prev_file)
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest/MacTahoeLiquidKde")

    calls = _stub(monkeypatch, have_bin=True, current_theme="breeze",
                  activate_rc=1)
    plymouth.install()

    activations = _activation_calls(calls)
    # First activation: ours (failed). Second: rollback to breeze.
    assert activations[0] == [plymouth.PLYMOUTH_BIN, "-R", "MacTahoeLiquidKde"]
    assert activations[-1] == [plymouth.PLYMOUTH_BIN, "-R", "breeze"]


def test_uninstall_restores_snapshot(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    prev_file = state_dir / "plymouth-previous-theme"
    prev_file.write_text("bgrt\n")

    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR", state_dir)
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE", prev_file)
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest/MacTahoeLiquidKde")

    calls = _stub(monkeypatch, have_bin=True)
    plymouth.uninstall()

    assert _activation_calls(calls) == [[plymouth.PLYMOUTH_BIN, "-R", "bgrt"]]
    assert calls["remove"] == [tmp_path / "dest/MacTahoeLiquidKde"]
    assert not prev_file.is_file()


def test_uninstall_falls_back_to_bgrt_without_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR", tmp_path / "state-missing")
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE",
                        tmp_path / "state-missing/plymouth-previous-theme")
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest/MacTahoeLiquidKde")

    calls = _stub(monkeypatch, have_bin=True)
    plymouth.uninstall()

    assert _activation_calls(calls) == [[plymouth.PLYMOUTH_BIN, "-R", "bgrt"]]


def test_uninstall_avoids_loop_when_snapshot_is_our_own_name(tmp_path, monkeypatch):
    """If the snapshot file somehow contains our own theme name
    (corrupt state, manual edit), uninstall must NOT activate ourselves
    again — fall back to bgrt instead."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    prev_file = state_dir / "plymouth-previous-theme"
    prev_file.write_text("MacTahoeLiquidKde\n")

    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR", state_dir)
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE", prev_file)
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest/MacTahoeLiquidKde")

    calls = _stub(monkeypatch, have_bin=True)
    plymouth.uninstall()

    assert _activation_calls(calls) == [[plymouth.PLYMOUTH_BIN, "-R", "bgrt"]]


def test_uninstall_continues_when_plymouth_binary_missing(tmp_path, monkeypatch):
    """If the distro stripped plymouth between install and uninstall
    we still want to remove our theme dir + state file, just without
    the restore call."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    prev_file = state_dir / "plymouth-previous-theme"
    prev_file.write_text("breeze\n")

    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR", state_dir)
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE", prev_file)
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest/MacTahoeLiquidKde")

    calls = _stub(monkeypatch, have_bin=False)
    plymouth.uninstall()

    assert _activation_calls(calls) == []
    assert calls["remove"] == [tmp_path / "dest/MacTahoeLiquidKde"]


# ──────────────────────── boot-side prerequisites ──────────────────────


def _stub_prereq_paths(tmp_path, monkeypatch, *, cmdline="splash quiet",
                       mkinitcpio_hooks="HOOKS=(base udev plymouth filesystems)",
                       mkinitcpio_modules="MODULES=()",
                       has_grub=True, has_mkinitcpio=True):
    proc_cmdline = tmp_path / "cmdline"
    proc_cmdline.write_text(cmdline + "\n")
    mki = tmp_path / "mkinitcpio.conf"
    if has_mkinitcpio:
        mki.write_text(f"{mkinitcpio_modules}\nBINARIES=()\n{mkinitcpio_hooks}\n")
    grub = tmp_path / "grub"
    if has_grub:
        grub.write_text('GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"\n')

    monkeypatch.setattr(plymouth, "PROC_CMDLINE", proc_cmdline)
    monkeypatch.setattr(plymouth, "MKINITCPIO_CONF", mki)
    monkeypatch.setattr(plymouth, "GRUB_DEFAULT", grub)


def test_prereqs_no_warnings_when_splash_and_hook_present(tmp_path, monkeypatch):
    _stub_prereq_paths(tmp_path, monkeypatch,
                       cmdline="BOOT_IMAGE=/vmlinuz root=UUID=xxx rw quiet splash")
    splash_missing, hook_missing = plymouth._check_prereqs()
    assert splash_missing is False
    assert hook_missing is False


def test_prereqs_flag_splash_missing_in_kernel_cmdline(tmp_path, monkeypatch):
    _stub_prereq_paths(tmp_path, monkeypatch, cmdline="quiet rw")
    splash_missing, _hook_missing = plymouth._check_prereqs()
    assert splash_missing is True


def test_prereqs_flag_mkinitcpio_hooks_missing_plymouth(tmp_path, monkeypatch):
    _stub_prereq_paths(
        tmp_path, monkeypatch,
        mkinitcpio_hooks="HOOKS=(base udev autodetect modconf filesystems)",
    )
    _splash_missing, hook_missing = plymouth._check_prereqs()
    assert hook_missing is True


def test_prereqs_ignore_commented_hooks_line(tmp_path, monkeypatch):
    """A commented-out HOOKS line should not satisfy the check — even if
    it mentions plymouth. The HOOKS line that actually drives mkinitcpio
    is the uncommented one."""
    _stub_prereq_paths(
        tmp_path, monkeypatch,
        mkinitcpio_hooks=(
            "# HOOKS=(base udev plymouth filesystems)\n"
            "HOOKS=(base udev filesystems)"
        ),
    )
    _splash_missing, hook_missing = plymouth._check_prereqs()
    assert hook_missing is True


def test_prereqs_skip_mkinitcpio_check_when_file_absent(tmp_path, monkeypatch):
    """Fedora / Debian / Ubuntu don't use mkinitcpio. The check should
    silently skip rather than nag those users about a config file they
    don't have."""
    _stub_prereq_paths(tmp_path, monkeypatch, has_mkinitcpio=False,
                       cmdline="quiet splash")
    splash_missing, hook_missing = plymouth._check_prereqs()
    assert splash_missing is False
    assert hook_missing is False


def test_grub_patch_appends_splash_when_missing(tmp_path, monkeypatch):
    """v0.15.3: GRUB cmdline auto-patch. If GRUB_CMDLINE_LINUX_DEFAULT
    is missing 'splash', the installer appends it (preserving every
    other token), keeps a .mttkde.bak backup, and the new value lands
    on disk. Existing 'splash' tokens are left alone — idempotent
    re-runs don't duplicate the flag."""
    grub = tmp_path / "etc/default/grub"
    grub.parent.mkdir(parents=True, exist_ok=True)
    grub.write_text(
        'GRUB_DEFAULT=0\n'
        'GRUB_TIMEOUT=5\n'
        'GRUB_CMDLINE_LINUX_DEFAULT="quiet loglevel=3"\n'
        'GRUB_CMDLINE_LINUX=""\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(plymouth, "GRUB_DEFAULT", grub)

    # _patch_grub_add_splash uses _as_root() — stub it to a no-op
    # context manager so the test doesn't need real root.
    import contextlib
    monkeypatch.setattr(plymouth, "_as_root", contextlib.nullcontext)

    assert plymouth._patch_grub_add_splash() is True
    text = grub.read_text(encoding="utf-8")
    assert 'GRUB_CMDLINE_LINUX_DEFAULT="quiet loglevel=3 splash"' in text
    # Backup landed alongside.
    bak = grub.with_suffix(grub.suffix + ".mttkde.bak")
    assert bak.is_file()
    assert "quiet loglevel=3" in bak.read_text(encoding="utf-8")
    assert "splash" not in bak.read_text(encoding="utf-8").split("\n")[2]

    # Second invocation must be a no-op (idempotent).
    assert plymouth._patch_grub_add_splash() is True
    text2 = grub.read_text(encoding="utf-8")
    # Still exactly one 'splash' token in the cmdline line.
    cmdline_line = [ln for ln in text2.splitlines()
                    if ln.startswith("GRUB_CMDLINE_LINUX_DEFAULT")][0]
    assert cmdline_line.split().count("splash") == 0  # 'splash' is inside quotes
    assert cmdline_line.count("splash") == 1


def test_grub_patch_refuses_to_invent_missing_cmdline_line(tmp_path, monkeypatch):
    """If /etc/default/grub has no GRUB_CMDLINE_LINUX_DEFAULT line at
    all, the user's config is non-standard. Refuse to invent one —
    silently writing a new line could conflict with whatever
    distro-specific cmdline mechanism they're using."""
    import contextlib
    grub = tmp_path / "etc/default/grub"
    grub.parent.mkdir(parents=True, exist_ok=True)
    grub.write_text(
        'GRUB_DEFAULT=0\nGRUB_TIMEOUT=5\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(plymouth, "GRUB_DEFAULT", grub)
    monkeypatch.setattr(plymouth, "_as_root", contextlib.nullcontext)

    assert plymouth._patch_grub_add_splash() is False
    # File unchanged.
    assert "GRUB_CMDLINE_LINUX_DEFAULT" not in grub.read_text(encoding="utf-8")


def test_grub_auto_patch_disabled_via_env(monkeypatch):
    """The --no-grub-modify CLI flag exports MTTKDE_NO_GRUB_MODIFY=1.
    Plymouth's gating helper must respect that so the auto-patch
    branch is skipped and the warn() path runs instead."""
    monkeypatch.setenv("MTTKDE_NO_GRUB_MODIFY", "1")
    assert plymouth._grub_auto_patch_enabled() is False

    monkeypatch.delenv("MTTKDE_NO_GRUB_MODIFY", raising=False)
    assert plymouth._grub_auto_patch_enabled() is True


def test_grub_auto_patch_accepts_yes_and_true_for_opt_out(monkeypatch):
    """Users might write MTTKDE_NO_GRUB_MODIFY=true or =yes — the env
    parser should recognise the common forms so opt-out works
    regardless of the value style the user picked."""
    for val in ("1", "true", "TRUE", "yes", "YES"):
        monkeypatch.setenv("MTTKDE_NO_GRUB_MODIFY", val)
        assert plymouth._grub_auto_patch_enabled() is False, val
    for val in ("0", "false", "no", "", "off"):
        monkeypatch.setenv("MTTKDE_NO_GRUB_MODIFY", val)
        # Anything not in the affirmative set means auto-patch stays on.
        # ("off" isn't in the affirmative list either — silently fall
        # through to enabled. Documented in plymouth.py.)
        assert plymouth._grub_auto_patch_enabled() is True, val


def test_grub_patch_preserves_existing_tokens(tmp_path, monkeypatch):
    """Adding splash must not lose any of the user's other kernel
    parameters. The v0.15.3 patcher splits on whitespace inside the
    quotes — verify a realistic Fedora-style cmdline survives the
    rewrite intact."""
    import contextlib
    grub = tmp_path / "etc/default/grub"
    grub.parent.mkdir(parents=True, exist_ok=True)
    grub.write_text(
        'GRUB_CMDLINE_LINUX_DEFAULT="rhgb quiet rd.luks.uuid=luks-xx '
        'rd.lvm.lv=fedora/root rd.lvm.lv=fedora/swap"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(plymouth, "GRUB_DEFAULT", grub)
    monkeypatch.setattr(plymouth, "_as_root", contextlib.nullcontext)

    assert plymouth._patch_grub_add_splash() is True

    line = [ln for ln in grub.read_text().splitlines()
            if ln.startswith("GRUB_CMDLINE_LINUX_DEFAULT")][0]
    # Every original token still present.
    for tok in ("rhgb", "quiet", "rd.luks.uuid=luks-xx",
                "rd.lvm.lv=fedora/root", "rd.lvm.lv=fedora/swap"):
        assert tok in line, f"{tok} dropped from {line!r}"
    # And splash appended.
    assert "splash" in line


def test_grub_patch_handles_single_quotes(tmp_path, monkeypatch):
    """Some distros (Debian / SUSE templates) use single quotes around
    the cmdline. The regex must match both quote styles or the patcher
    silently does nothing on those distros."""
    import contextlib
    grub = tmp_path / "etc/default/grub"
    grub.parent.mkdir(parents=True, exist_ok=True)
    grub.write_text(
        "GRUB_CMDLINE_LINUX_DEFAULT='quiet loglevel=3'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(plymouth, "GRUB_DEFAULT", grub)
    monkeypatch.setattr(plymouth, "_as_root", contextlib.nullcontext)

    assert plymouth._patch_grub_add_splash() is True
    assert "splash" in grub.read_text()


def test_grub_patch_backup_keeps_truly_original(tmp_path, monkeypatch):
    """The .mttkde.bak must be the file BEFORE any patcher run, even
    across multiple install runs. If a user installs twice, the
    second run must NOT overwrite the backup with the first run's
    already-patched output — otherwise the rollback path is gone."""
    import contextlib
    grub = tmp_path / "etc/default/grub"
    grub.parent.mkdir(parents=True, exist_ok=True)
    original = 'GRUB_CMDLINE_LINUX_DEFAULT="quiet"\n'
    grub.write_text(original, encoding="utf-8")
    monkeypatch.setattr(plymouth, "GRUB_DEFAULT", grub)
    monkeypatch.setattr(plymouth, "_as_root", contextlib.nullcontext)

    plymouth._patch_grub_add_splash()
    # Simulate a second invocation: re-modify the file, then run again.
    grub.write_text(
        'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash extra_param"\n',
        encoding="utf-8",
    )
    plymouth._patch_grub_add_splash()

    bak = grub.with_suffix(grub.suffix + ".mttkde.bak")
    assert bak.read_text() == original, (
        "second run overwrote the original backup — rollback path lost"
    )


# ── GRUB regenerate fallback chain ──────────────────────────────────


def test_grub_regenerate_picks_first_available_binary(tmp_path, monkeypatch):
    """On Arch / openSUSE / Gentoo the binary is ``grub-mkconfig``; on
    Fedora / RHEL it's ``grub2-mkconfig``. The regenerate helper
    walks every (binary, output) candidate and uses the first match
    whose binary is on PATH and whose output directory exists."""
    import contextlib
    import subprocess as sp
    monkeypatch.setattr(plymouth, "_as_root", contextlib.nullcontext)

    # Pretend only grub2-mkconfig + /boot/grub2 exist (Fedora layout).
    monkeypatch.setattr(plymouth, "have", lambda c: c == "grub2-mkconfig")
    real_is_dir = type(tmp_path).is_dir

    def fake_is_dir(self):
        if str(self) == "/boot/grub2":
            return True
        if str(self) == "/boot/grub":
            return False
        return real_is_dir(self)
    monkeypatch.setattr("pathlib.Path.is_dir", fake_is_dir)

    invocations: list[list[str]] = []

    def fake_run(argv, **kwargs):
        invocations.append(list(argv))
        return sp.CompletedProcess(argv, 0, "", "")
    monkeypatch.setattr(plymouth.subprocess, "run", fake_run)

    assert plymouth._regenerate_grub_config() is True
    assert invocations == [["grub2-mkconfig", "-o", "/boot/grub2/grub.cfg"]]


def test_grub_regenerate_returns_false_when_nothing_matches(tmp_path, monkeypatch):
    """If neither ``grub-mkconfig`` nor ``grub2-mkconfig`` is on PATH
    (systemd-boot / refind / limine user, or stripped-down distro),
    the helper returns False without crashing and the install step
    surfaces a warning instead of an exception."""
    monkeypatch.setattr(plymouth, "have", lambda _c: False)
    # No subprocess.run should be reachable at all in this scenario.
    monkeypatch.setattr(
        plymouth.subprocess, "run",
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("subprocess.run called with no available binary")
        ),
    )
    assert plymouth._regenerate_grub_config() is False


def test_grub_regenerate_falls_through_when_first_binary_fails(tmp_path, monkeypatch):
    """If the first matching binary exits non-zero (e.g. broken Fedora
    grub2 stub), the helper must try the next (binary, output)
    candidate before giving up. Otherwise a single distro-specific
    quirk masks a working alternative."""
    import contextlib
    import subprocess as sp
    monkeypatch.setattr(plymouth, "_as_root", contextlib.nullcontext)
    # Both binaries on PATH, both output dirs exist.
    monkeypatch.setattr(plymouth, "have", lambda _c: True)
    monkeypatch.setattr("pathlib.Path.is_dir", lambda self: True)

    invocations: list[list[str]] = []

    def fake_run(argv, **kwargs):
        invocations.append(list(argv))
        # First call (grub-mkconfig → /boot/grub/grub.cfg) fails.
        # Second call (grub2-mkconfig → /boot/grub2/grub.cfg) succeeds.
        if len(invocations) == 1:
            return sp.CompletedProcess(argv, 1, "", "boom")
        return sp.CompletedProcess(argv, 0, "", "")
    monkeypatch.setattr(plymouth.subprocess, "run", fake_run)

    assert plymouth._regenerate_grub_config() is True
    assert len(invocations) == 2
    assert invocations[0][0] == "grub-mkconfig"
    assert invocations[1][0] == "grub2-mkconfig"


# The "GPU module in MODULES blocks simpledrm" warning was removed:
# the correlation between MODULES=(amdgpu) and the corner-rendered
# shutdown splash wasn't strong enough to justify nagging users about
# it during every install. The mechanism is still documented in
# plymouth.py:_check_prereqs as a note for future debugging.


# ──────────────────────── static safety net ─────────────────────────────


def test_install_sets_use_simpledrm_in_plymouthd_conf(tmp_path, monkeypatch):
    """Fixes the corner-rendered shutdown splash bug: at shutdown the
    GPU driver unloads BEFORE plymouth shows the shutdown splash, the
    kernel console framebuffer drops to ~1024x768, and the splash
    renders in a tiny corner of the high-res panel. Forcing
    UseSimpledrm=true keeps plymouth on the UEFI GOP framebuffer
    which survives DRM driver unloads. Write it to plymouthd.conf
    during install."""
    conf = tmp_path / "plymouthd.conf"
    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE",
                        tmp_path / "state/plymouth-previous-theme")
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest/MacTahoeLiquidKde")
    monkeypatch.setattr(plymouth, "PLYMOUTHD_CONF", conf)
    _stub(monkeypatch, have_bin=True, current_theme="breeze")
    plymouth.install()

    assert conf.is_file(), "install must create/touch plymouthd.conf"
    text = conf.read_text(encoding="utf-8")
    assert "[Daemon]" in text
    assert "UseSimpledrm" in text
    assert "true" in text.lower()


def test_install_preserves_unrelated_plymouthd_conf_keys(tmp_path, monkeypatch):
    """If the user (or distro) has other keys in plymouthd.conf, our
    UseSimpledrm write must NOT clobber them. configparser round-trip
    keeps every existing key intact."""
    conf = tmp_path / "plymouthd.conf"
    conf.write_text(
        "[Daemon]\n"
        "Theme=breeze\n"
        "ShowDelay=0\n"
        "\n"
        "[Custom]\n"
        "SomeUserKey=value\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE",
                        tmp_path / "state/plymouth-previous-theme")
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest/MacTahoeLiquidKde")
    monkeypatch.setattr(plymouth, "PLYMOUTHD_CONF", conf)
    _stub(monkeypatch, have_bin=True, current_theme="breeze")
    plymouth.install()

    text = conf.read_text(encoding="utf-8")
    # Our key landed.
    assert "UseSimpledrm" in text
    # Existing keys survived.
    assert "Theme = breeze" in text or "Theme=breeze" in text
    assert "ShowDelay" in text
    assert "SomeUserKey" in text
    assert "[Custom]" in text


def test_install_writes_plymouthd_conf_without_spaces_around_equals(tmp_path, monkeypatch):
    """``plymouth-set-default-theme`` is a bash script that parses
    plymouthd.conf with broken whitespace stripping: when the file has
    ``Theme = Foo`` (spaces around ``=``), KEY_NAME comes out as ``Theme ``
    (trailing space), the ``[[ "Theme " == "Theme" ]]`` comparison fails,
    and the script falls through to the distro defaults file (which has
    ``Theme=bgrt``). plymouthd at boot/shutdown then loads bgrt instead
    of MacTahoeLiquidKde — exactly the shutdown splash regression that
    shipped with v0.13.8 (configparser's default write format uses spaces).

    Writing with ``space_around_delimiters=False`` produces the
    ``Key=Value`` format plymouth-set-default-theme can actually read."""
    conf = tmp_path / "plymouthd.conf"
    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE",
                        tmp_path / "state/plymouth-previous-theme")
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest/MacTahoeLiquidKde")
    monkeypatch.setattr(plymouth, "PLYMOUTHD_CONF", conf)
    _stub(monkeypatch, have_bin=True, current_theme="MacTahoeLiquidKde")
    plymouth.install()

    text = conf.read_text(encoding="utf-8")
    # Every key=value line uses Key=Value (no spaces). Section headers
    # ([Daemon]) are allowed to be on their own line.
    for line in text.splitlines():
        if not line or line.startswith("[") or line.startswith("#"):
            continue
        assert "=" in line, f"unexpected non-INI line: {line!r}"
        key, _, _value = line.partition("=")
        # configparser writes 'key = value' by default. We need NO trailing
        # space on the key — that's what plymouth-set-default-theme's
        # broken parser chokes on.
        assert not key.endswith(" "), (
            f"plymouthd.conf line has trailing space on key — "
            f"plymouth-set-default-theme will fail to find it: {line!r}"
        )
    # And there must be NO ' = ' anywhere in a value-bearing line.
    for line in text.splitlines():
        if line and not line.startswith("[") and not line.startswith("#"):
            assert " = " not in line, (
                f"plymouthd.conf line has ' = ' separator — "
                f"plymouth-set-default-theme can't parse this: {line!r}"
            )


def test_install_survives_duplicate_theme_lines_in_plymouthd_conf(tmp_path, monkeypatch):
    """``plymouth-set-default-theme`` writes ``Theme=…`` on every -R run
    WITHOUT deduping prior entries, and casual hand-edits often produce
    ``Theme = …`` with surrounding whitespace — configparser treats both
    forms as the same key, so the file gets ``DuplicateOptionError`` on
    parse with ``strict=True``. That used to abort the UseSimpledrm write
    entirely (visible as ``plymouthd.conf unparseable
    (DuplicateOptionError) — leaving UseSimpledrm setting unchanged`` on
    every install). Now the read uses ``strict=False``, which both
    tolerates the duplicates AND collapses them on write-back."""
    conf = tmp_path / "plymouthd.conf"
    conf.write_text(
        "[Daemon]\n"
        "Theme=MacTahoeLiquidKde\n"
        "Theme = MacTahoeLiquidKde\n"
        "UseSimpledrm = true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE",
                        tmp_path / "state/plymouth-previous-theme")
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest/MacTahoeLiquidKde")
    monkeypatch.setattr(plymouth, "PLYMOUTHD_CONF", conf)
    _stub(monkeypatch, have_bin=True, current_theme="MacTahoeLiquidKde")
    plymouth.install()

    text = conf.read_text(encoding="utf-8")
    # Duplicates collapsed: exactly one Theme= line and one UseSimpledrm.
    assert text.count("Theme") == 1, \
        f"expected exactly one Theme line, got:\n{text}"
    assert text.count("UseSimpledrm") == 1, \
        f"expected exactly one UseSimpledrm line, got:\n{text}"
    # File is still parseable in strict mode after our normalization —
    # the next install pass won't hit DuplicateOptionError either.
    cp = configparser.ConfigParser(strict=True)
    cp.optionxform = str
    cp.read(str(conf), encoding="utf-8")
    assert cp.get("Daemon", "UseSimpledrm") == "true"


def test_uninstall_removes_use_simpledrm_override(tmp_path, monkeypatch):
    """Uninstall should put plymouthd.conf back to a state that
    doesn't reflect our override — the previous theme may not need
    or want UseSimpledrm forced. Leaving our line behind is install-
    state leak."""
    conf = tmp_path / "plymouthd.conf"
    conf.write_text(
        "[Daemon]\n"
        "Theme=MacTahoeLiquidKde\n"
        "UseSimpledrm=true\n"
        "ShowDelay=0\n",
        encoding="utf-8",
    )
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    prev_file = state_dir / "plymouth-previous-theme"
    prev_file.write_text("breeze\n")
    monkeypatch.setattr(plymouth, "HOME", tmp_path)
    monkeypatch.setattr(plymouth, "STATE_DIR", state_dir)
    monkeypatch.setattr(plymouth, "PREV_THEME_FILE", prev_file)
    monkeypatch.setattr(plymouth, "DEST", tmp_path / "dest/MacTahoeLiquidKde")
    monkeypatch.setattr(plymouth, "PLYMOUTHD_CONF", conf)
    _stub(monkeypatch, have_bin=True)
    plymouth.uninstall()

    text = conf.read_text(encoding="utf-8")
    assert "UseSimpledrm" not in text, (
        f"uninstall left UseSimpledrm in plymouthd.conf: {text!r}"
    )
    # But unrelated keys (ShowDelay) survive.
    assert "ShowDelay" in text


def test_no_activation_call_in_source_lacks_R_flag():
    """Static scan: every ``plymouth-set-default-theme <name>`` call
    in the module must carry ``-R``. The query form (no name) is fine."""
    source = (REPO / "src/scripts/steps/plymouth.py").read_text()
    # Find every list literal that starts with PLYMOUTH_BIN.
    activation_lines = [
        ln for ln in source.splitlines()
        if "PLYMOUTH_BIN" in ln and ("-R" in ln or "[PLYMOUTH_BIN," in ln)
    ]
    # Any line that constructs an argv with PLYMOUTH_BIN and a theme name
    # (i.e. has a third element) must include "-R".
    for ln in activation_lines:
        if "[PLYMOUTH_BIN," in ln and "theme" in ln.lower():
            assert "-R" in ln, f"activation without -R: {ln.strip()}"


# ── _grub_is_active_bootloader (v0.15.5 hardening) ──────────────────────


def test_grub_active_requires_both_file_and_regen_binary(tmp_path, monkeypatch):
    """v0.15.5: ``GRUB_DEFAULT.is_file()`` alone is a leftover trap.
    Many users migrated from GRUB to systemd-boot / Limine / rEFInd
    and the file is still on disk from the previous install. Patching
    it does nothing because no regen tool exists to materialise it.
    The new gate requires BOTH conditions."""
    grub = tmp_path / "etc/default/grub"
    grub.parent.mkdir(parents=True, exist_ok=True)
    grub.write_text('GRUB_CMDLINE_LINUX_DEFAULT="quiet"\n', encoding="utf-8")
    monkeypatch.setattr(plymouth, "GRUB_DEFAULT", grub)

    # Case 1: file exists, no regen binary on PATH → not active.
    monkeypatch.setattr(plymouth, "have", lambda _c: False)
    assert plymouth._grub_is_active_bootloader() is False

    # Case 2: file exists, grub-mkconfig present → active.
    monkeypatch.setattr(plymouth, "have", lambda c: c == "grub-mkconfig")
    assert plymouth._grub_is_active_bootloader() is True

    # Case 3: file exists, grub2-mkconfig present (Fedora variant) → active.
    monkeypatch.setattr(plymouth, "have", lambda c: c == "grub2-mkconfig")
    assert plymouth._grub_is_active_bootloader() is True

    # Case 4: file absent → not active even if regen tool installed.
    grub.unlink()
    monkeypatch.setattr(plymouth, "have", lambda _c: True)
    assert plymouth._grub_is_active_bootloader() is False


def test_install_skips_grub_patch_when_no_regen_binary(tmp_path, monkeypatch):
    """A systemd-boot user with a leftover /etc/default/grub from a
    previous install must NOT have that file patched — patching it
    is a no-op (no grub.cfg gets regenerated) and the .mttkde.bak
    backup just clutters their filesystem. install() must fall
    through to the warn() path instead."""
    import contextlib

    grub = tmp_path / "etc/default/grub"
    grub.parent.mkdir(parents=True, exist_ok=True)
    original = 'GRUB_CMDLINE_LINUX_DEFAULT="quiet"\n'
    grub.write_text(original, encoding="utf-8")

    monkeypatch.setattr(plymouth, "GRUB_DEFAULT", grub)
    monkeypatch.setattr(plymouth, "_as_root", contextlib.nullcontext)
    # No regen binary on PATH — simulates a systemd-boot / limine user.
    monkeypatch.setattr(plymouth, "have", lambda _c: False)

    # The active-bootloader gate must return False, so install's
    # auto-patch branch is skipped. We don't need to run install()
    # end-to-end here; the gate is the load-bearing piece.
    assert plymouth._grub_is_active_bootloader() is False

    # File on disk must be untouched (no patch happened).
    assert grub.read_text() == original
    # No backup file created.
    bak = grub.with_suffix(grub.suffix + ".mttkde.bak")
    assert not bak.exists()
