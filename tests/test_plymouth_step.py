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
    monkeypatch.setattr(plymouth, "_check_prereqs", lambda: [])

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
                       has_grub=True, has_mkinitcpio=True):
    proc_cmdline = tmp_path / "cmdline"
    proc_cmdline.write_text(cmdline + "\n")
    mki = tmp_path / "mkinitcpio.conf"
    if has_mkinitcpio:
        mki.write_text(f"MODULES=()\nBINARIES=()\n{mkinitcpio_hooks}\n")
    grub = tmp_path / "grub"
    if has_grub:
        grub.write_text('GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"\n')

    monkeypatch.setattr(plymouth, "PROC_CMDLINE", proc_cmdline)
    monkeypatch.setattr(plymouth, "MKINITCPIO_CONF", mki)
    monkeypatch.setattr(plymouth, "GRUB_DEFAULT", grub)


def test_prereqs_no_warnings_when_splash_and_hook_present(tmp_path, monkeypatch):
    _stub_prereq_paths(tmp_path, monkeypatch,
                       cmdline="BOOT_IMAGE=/vmlinuz root=UUID=xxx rw quiet splash")
    assert plymouth._check_prereqs() == []


def test_prereqs_warn_when_kernel_cmdline_lacks_splash(tmp_path, monkeypatch):
    _stub_prereq_paths(tmp_path, monkeypatch, cmdline="quiet rw")
    warnings = plymouth._check_prereqs()
    assert any("splash" in w for w in warnings)


def test_prereqs_warn_when_mkinitcpio_hooks_missing_plymouth(tmp_path, monkeypatch):
    _stub_prereq_paths(
        tmp_path, monkeypatch,
        mkinitcpio_hooks="HOOKS=(base udev autodetect modconf filesystems)",
    )
    warnings = plymouth._check_prereqs()
    assert any("mkinitcpio" in w for w in warnings)


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
    warnings = plymouth._check_prereqs()
    assert any("mkinitcpio" in w for w in warnings)


def test_prereqs_skip_mkinitcpio_check_when_file_absent(tmp_path, monkeypatch):
    """Fedora / Debian / Ubuntu don't use mkinitcpio. The check should
    silently skip rather than nag those users about a config file they
    don't have."""
    _stub_prereq_paths(tmp_path, monkeypatch, has_mkinitcpio=False,
                       cmdline="quiet splash")
    assert plymouth._check_prereqs() == []


def test_prereqs_warn_directs_to_grub_when_grub_present(tmp_path, monkeypatch):
    _stub_prereq_paths(tmp_path, monkeypatch, cmdline="quiet")
    warnings = plymouth._check_prereqs()
    # GRUB present → instruction should mention /etc/default/grub, not
    # systemd-boot or limine.
    splash_warns = [w for w in warnings if "splash" in w]
    assert splash_warns
    assert any("/etc/default/grub" in w for w in splash_warns)


def test_prereqs_warn_directs_to_other_loaders_when_no_grub(tmp_path, monkeypatch):
    _stub_prereq_paths(tmp_path, monkeypatch, cmdline="quiet", has_grub=False)
    warnings = plymouth._check_prereqs()
    splash_warns = [w for w in warnings if "splash" in w]
    assert splash_warns
    assert any("systemd-boot" in w or "limine" in w for w in splash_warns)


# ──────────────────────── static safety net ─────────────────────────────


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
