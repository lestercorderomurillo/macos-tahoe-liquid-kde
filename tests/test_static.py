"""Static guards that protect cross-cutting invariants.

Only guards that catch *cross-cutting* drift belong here (refactors
that affect every distro / every step / every release). Don't add
tests that pin artist choices or duplicate the install step's own
fail-fast checks. Each guard protects against a specific real bug
or a specific class of regression that has no other home in the
suite.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest


# ── basic launch surface ──────────────────────────────────────────────


def test_version_is_semver(repo):
    """VERSION is the single source of truth read by paths.read_version()
    and printed by the install banner. If this file drifts or gets
    malformed (e.g. two lines from a botched merge), the banner
    prints the wrong version. Pin the shape so that fails CI."""
    assert re.fullmatch(r"\d+\.\d+\.\d+", (repo / "VERSION").read_text().strip())


def test_look_and_feel_does_not_bypass_smart_wallpaper_owner(repo):
    """KDE applies a look-and-feel package before the switcher saves state.
    Wallpaper defaults here would erase the outgoing custom background before
    its independent light/dark choice could be preserved."""
    root = repo / "src/offline/look-and-feel"
    defaults = sorted(root.glob("*/contents/defaults"))
    assert defaults
    for path in defaults:
        assert "[Wallpaper]" not in path.read_text()


def test_init_specific_user_manager_calls_stay_in_distro_layer(repo):
    """Executable source must ask distro.py for the active user manager.
    Direct calls silently break OpenRC when the systemd package happens to be
    installed but is not PID 1."""
    offenders = []
    source = repo / "src"
    checked_suffixes = {".py", ".qml", ".cpp", ".h", ".xml"}
    for path in source.rglob("*"):
        if not path.is_file() or path.suffix not in checked_suffixes:
            continue
        if path.name == "distro.py":
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if "systemctl" in line:
                offenders.append(f"{path.relative_to(repo)}:{lineno}")
    assert not offenders, "direct user-manager calls: " + ", ".join(offenders)


@pytest.mark.parametrize(
    "entry", ["install", "uninstall", "legacy-install", "legacy-uninstall"])
def test_entry_point_exists(repo, entry):
    p = repo / entry
    assert p.is_file() and p.stat().st_mode & 0o111


@pytest.mark.parametrize("script", ["install", "uninstall",
                                    "legacy-install", "legacy-uninstall"])
def test_help_exits_zero(repo, script):
    """`./install --help` and `./uninstall --help` must not crash. This
    catches a class of bug where an import-time error in cli.py only
    surfaces when the script tries to do anything (which `--help`
    short-circuits past)."""
    rc = subprocess.run([str(repo / script), "--help"], check=False).returncode
    assert rc == 0


# ── distro layer is the only place that knows per-distro details ──────


def test_distro_layer_exposes_public_api(repo):
    """``distro.py`` is the documented choke point for everything that
    varies between Linux distros (Qt6 plugin/QML dirs, libdir suffix,
    package manager). Tests + steps + preflight + container probe all
    import from this public surface. If a refactor renames or removes
    one of these, every caller breaks. Pin the surface so renames are
    deliberate, not silent."""
    text = (repo / "src/scripts/distro.py").read_text()
    for name in ("qt6_plugins_dir", "qt6_qml_dir", "Qt6PathsMissing",
                 "current_distro", "qt6_install_hint",
                 "package_for", "package_manager_install_cmd",
                 "UnsupportedDistroError"):
        assert f"def {name}" in text or f"class {name}" in text, name


def test_no_hardcoded_package_manager_outside_distro_layer(repo):
    """Only ``distro.py`` is allowed to name a specific package manager
    INSTALL command. Anything else has to go through
    ``distro.package_manager_install_cmd()`` so adding a new distro
    means adding ONE row, not hunting through every step.

    Failure mode: a step that shells out to ``pacman -S foo``
    directly works on Arch and silently no-ops on every other
    distro — exactly the bug shape the distro-layer abstraction
    exists to prevent.

    ``pacman -Q`` (a query, not an install) is allowed in cli.py
    because the update-check reads the local package version; only
    INSTALL invocations are forbidden."""
    scripts = repo / "src/scripts"
    forbidden = re.compile(
        r"\b(yay\s|paru\s|apt-get\s|dnf install|"
        r"zypper install|emerge --|xbps-install|apk add)\b|"
        r"\bpacman\s+-S\b"
    )
    allowlist = {scripts / "distro.py"}
    offenders: list[str] = []
    for py in scripts.rglob("*.py"):
        if py in allowlist:
            continue
        text = py.read_text()
        in_doc = False
        doc_open = None
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            if doc_open is None:
                for q in ('"""', "'''"):
                    if stripped.startswith(q):
                        if stripped.count(q) >= 2:
                            in_doc = False
                            break
                        doc_open = q
                        in_doc = True
                        break
            elif doc_open in stripped:
                in_doc = False
                doc_open = None
                continue
            if in_doc:
                continue
            if stripped.startswith("#"):
                continue
            if forbidden.search(line):
                offenders.append(f"{py.relative_to(repo)}:{line_no}: {line.strip()}")
    assert not offenders, (
        "Hardcoded package-manager INSTALL invocation outside the distro layer:\n  "
        + "\n  ".join(offenders)
    )


def test_no_hardcoded_qt6_libdir(repo):
    """Anywhere outside ``distro.py`` (the distro-detection layer) and
    ``paths.py`` (where the per-distro libdir map is *documented* in a
    comment), no executable line is allowed to hardcode
    ``/usr/lib/qt6`` or ``/usr/lib64/qt6``. Production code MUST go
    through ``distro.qt6_plugins_dir()`` / ``distro.qt6_qml_dir()``.

    Assuming Arch's ``/usr/lib/qt6`` everywhere breaks installs on
    Gentoo + Debian (different libdirs).

    Comment lines and docstrings are allowed to mention the example
    paths — that's how we document the per-distro variation."""
    scripts = repo / "src/scripts"
    forbidden = re.compile(r"/usr/lib(?:64)?/qt6")
    allowlist = {scripts / "distro.py", scripts / "paths.py"}
    offenders: list[str] = []
    for py in scripts.rglob("*.py"):
        if py in allowlist:
            continue
        text = py.read_text()
        in_docstring = False
        docstring_open = None
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            if docstring_open is None:
                for quote in ('"""', "'''"):
                    if stripped.startswith(quote):
                        if stripped.count(quote) >= 2:
                            in_docstring = False
                            break
                        docstring_open = quote
                        in_docstring = True
                        break
            elif docstring_open in stripped:
                in_docstring = False
                docstring_open = None
                continue
            if in_docstring:
                continue
            if stripped.startswith("#"):
                continue
            if forbidden.search(line):
                offenders.append(f"{py.relative_to(repo)}:{line_no}: {line.strip()}")
    assert not offenders, (
        "Hardcoded Qt6 libdir found outside the distro layer "
        "(executable code, not comments/docstrings):\n  "
        + "\n  ".join(offenders)
    )


# ── online-step allowlist ─────────────────────────────────────────────


def test_only_rounded_corners_step_may_download(repo):
    """Rounded Corners is the sole, explicit online exception. Everything
    else must remain reproducibly bundled under ``src/offline``."""
    steps = repo / "src/scripts/steps"
    # urllib.parse is string handling (nautilus.py URL-escapes paths);
    # only the fetch machinery and literal URLs are download signals.
    forbidden = re.compile(r"urllib\.(?:request|error)|\burlopen\b|https?://")
    offenders: list[str] = []
    for py in steps.rglob("*.py"):
        if py.name == "rounded_corners.py":
            continue
        text = py.read_text()
        in_doc = False
        doc_open = None
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            if doc_open is None:
                for q in ('"""', "'''"):
                    if stripped.startswith(q):
                        if stripped.count(q) >= 2:
                            in_doc = False
                            break
                        doc_open = q
                        in_doc = True
                        break
            elif doc_open in stripped:
                in_doc = False
                doc_open = None
                continue
            if in_doc:
                continue
            if stripped.startswith("#"):
                continue
            if forbidden.search(line):
                offenders.append(f"{py.relative_to(repo)}:{line_no}: {line.strip()}")
    assert not offenders, (
        "Network fetch found outside the rounded-corners allowlist:\n  "
        + "\n  ".join(offenders)
    )


def test_rounded_corners_online_source_is_immutable(repo):
    """An online step may never track a moving branch or unverified bytes."""
    text = (repo / "src/scripts/steps/rounded_corners.py").read_text()
    assert 'UPSTREAM_VERSION = "0.9.0"' in text
    assert re.search(r'UPSTREAM_COMMIT = "[0-9a-f]{40}"', text)
    assert re.search(r'UPSTREAM_SHA256 = "[0-9a-f]{64}"', text)
    assert "archive/refs/tags/v{UPSTREAM_VERSION}.tar.gz" in text
    assert "def download()" in text
    assert "fetch(UPSTREAM_URL" in text
    assert "latest" not in text.lower()
    assert "/master" not in text and "/main" not in text


def test_panel_colorizer_bundled_offline(offline):
    """The layout step installs Panel Colorizer from the offline bundle,
    so the bundle must ship a complete kpackage: metadata.json whose
    KPlugin.Id matches the directory name, plus contents/."""
    bundle = offline / "plasmoids/luisbocanegra.panel.colorizer"
    metadata = bundle / "metadata.json"
    assert metadata.is_file(), f"missing {metadata}"
    assert (bundle / "contents").is_dir(), f"missing {bundle / 'contents'}"
    data = json.loads(metadata.read_text())
    assert data["KPlugin"]["Id"] == bundle.name


# ── single-source-of-truth pins on the theme-switcher rewrite ─────────


def test_theme_switch_no_legacy_entry_points(repo):
    """``apply()`` is the theme switcher's single entry point. If any
    of these names (watch_loop, sync_auto_mode_on_startup,
    _spawn_deferred_live_apply, _deferred_live_apply_loop) reappear,
    a maintainer is re-introducing the multi-entry-point design whose
    racing paths cause stale-palette cascades. The apply()-as-only-
    path invariant is load-bearing."""
    text = (repo / "src/scripts/theme_switch.py").read_text()
    for forbidden in ("watch_loop", "sync_auto_mode_on_startup",
                      "_spawn_deferred_live_apply",
                      "_deferred_live_apply_loop"):
        assert forbidden not in text, (
            f"{forbidden!r} is a removed entry point — everything is "
            f"collapsed into apply(); separate live-apply paths race "
            f"the config writes."
        )


def test_theme_switch_has_no_global_sync(repo):
    """_kwrite() must never os.sync() after each kwriteconfig6 call —
    a machine-wide dirty-page flush repeated 130+ times per apply is
    slow enough to blow the installer's child timeout."""
    text = (repo / "src/scripts/theme_switch.py").read_text()
    assert "os.sync(" not in text, (
        "os.sync() is back in theme_switch.py — per-write global flushes "
        "blow the installer child timeout"
    )


def test_acrylic_glass_qrc_entries_all_staged_by_cmake(repo):
    """The effect's qrc is compiled from the BUILD dir (shader
    preprocessing must not write into the source checkout), so every
    shader the qrc references must be staged there by src/CMakeLists.txt,
    either copied via LIQUIDGLASS_SHADER_STATIC or generated by
    preprocess_shader_includes. An entry missing from both only explodes
    at rcc time on the user's machine, never in CI."""
    base = repo / "src/offline/kwin-effects/acrylic-glass/src"
    qrc = (base / "liquidglass.qrc").read_text()
    cml = (base / "CMakeLists.txt").read_text()

    entries = re.findall(r"<file>shaders/([^<]+)</file>", qrc)
    assert entries, "liquidglass.qrc parse produced no shader entries"
    missing = [e for e in entries if e not in cml]
    assert not missing, (
        f"liquidglass.qrc references shaders never staged into the build "
        f"dir by CMakeLists.txt: {missing}"
    )
    # The preprocessor writes into the build tree, never the checkout.
    assert 'file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/' in cml
    assert 'file(WRITE "${CMAKE_CURRENT_SOURCE_DIR}' not in cml


def test_acrylic_glass_ships_default_blur_denylist(offline):
    """WindowClasses ships as a blacklist (BlurMatching defaults false) with
    three entries baked in: cairo-dock (glassing the dock window
    renders a phantom panel behind it), kwin_wayland (KWin's own
    input-method candidate popups report that resource class, and
    glassing them produces a huge misplaced border), and
    linux-wallpaperengine (same artifact on its live-wallpaper
    surface). All three must survive edits to the kcfg default."""
    kcfg = (offline / "kwin-effects/acrylic-glass/src/glass.kcfg").read_text()
    m = re.search(
        r'<entry name="WindowClasses" type="String">\s*'
        r"<default>(.*?)</default>",
        kcfg, re.DOTALL,
    )
    assert m, "WindowClasses entry not found in glass.kcfg"
    denylist = [line.strip() for line in m.group(1).splitlines() if line.strip()]
    assert "cairo-dock" in denylist
    assert "kwin_wayland" in denylist
    assert "linux-wallpaperengine" in denylist

    matching = re.search(
        r'<entry name="BlurMatching" type="Bool">\s*<default>(\w+)</default>',
        kcfg,
    )
    assert matching and matching.group(1) == "false", (
        "BlurMatching default flipped to true — WindowClasses would now "
        "act as a whitelist, silently un-excluding the denylist entries"
    )


def test_no_legacy_apply_service_in_offline(offline):
    """Only the single oneshot service file ships — never a split
    apply.service / watch.service pair. Leftover units would
    re-enable the dead watch path on upgrade (systemctl
    daemon-reload picks them up)."""
    assert not (offline / "mac-tahoe-liquid-kde-theme-apply.service").exists()


# ── features.json + cli features stay in sync ─────────────────────────


def test_features_json_and_cli_feature_list_match(repo):
    """Each feature toggle is read from features.json + listed in
    cli.ALL_FEATURES. If one is added to features.json without an
    entry in cli.py (or vice versa) the install loop quietly skips
    or crashes depending on which way the mismatch goes."""
    feats = json.loads((repo / "features.json").read_text())
    text = (repo / "src/scripts/cli.py").read_text()
    # Every feature in features.json must be referenced as a string
    # literal somewhere in cli.py (ALL_FEATURES, INSTALL_ORDER, or
    # FEATURE_DESC).
    missing = [k for k in feats if f'"{k}"' not in text]
    assert not missing, (
        f"features.json keys not referenced in cli.py: {missing}"
    )


# ── README "tests count" badge stays honest ──────────────────────────


def test_readme_tests_count_badge_matches_collected_count(repo):
    """The README ships a ``tests-NNN_passing`` shields.io badge. The
    badge is hand-edited because the alternative (dynamic shields
    endpoint pointing at a Gist updated by CI) needs infra for
    something that changes ~3 times a year.

    To stop the badge from drifting, pin the number here.
    When the suite grows or shrinks, run ``./test`` to get the new
    count, edit the README badge, and re-run this test.

    The badge format is ``tests-<count>_passing``. Match against the
    actual ``--collect-only`` count of the same pytest invocation
    the README is documenting."""
    readme = (repo / "README.md").read_text()
    m = re.search(r"tests-(\d+)_passing", readme)
    assert m, (
        "README is missing the ``tests-NNN_passing`` badge. Restore "
        "it next to the other shields.io badges at the top of the "
        "README."
    )
    badge_count = int(m.group(1))

    # Count what pytest actually collects today, without running
    # anything. Counting via --collect-only is what the badge claims
    # to count.
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         str(repo / "tests")],
        capture_output=True, text=True,
        env={**os.environ, "MAC_TAHOE_SKIP_LIVE_SAFETY_NET": "1"},
    )
    last = [ln for ln in res.stdout.splitlines() if "tests collected" in ln]
    assert last, (
        f"pytest --collect-only did not report a count:\n"
        f"stdout tail:\n{res.stdout[-500:]}\n"
        f"stderr tail:\n{res.stderr[-500:]}"
    )
    actual_count = int(last[0].split()[0])

    assert badge_count == actual_count, (
        f"README badge says {badge_count} tests but pytest collects "
        f"{actual_count}. Edit the ``tests-NNN_passing`` badge in "
        f"README.md to {actual_count}."
    )


# ── dark popup surfaces keep mirrored light/dark alpha ────────────────
#
# GTK client-side popups never receive compositor blur, so a literal
# ``transparent`` background on a popup surface renders as see-through
# garbage. The dark sheets must mirror the light variant's alpha fills.

_GTK3_POPUP_SELECTORS = (
    "popover.background",
    ".background.csd > menu, .background.popup > menu",
    "window.background:not(.csd):not(.popup) > menu > menu",
    "#MozillaGtkWidget > window.background > menu",
    "#MozillaGtkWidget > widget > scrolledwindow > textview",
    "popover.background entry",
    ".app-notification",
    ".budgie-popover.background",
    ".raven",
)

_DARK_GTK3_SHEETS = (
    "gtk/MacTahoeLiquidKde-Dark/gtk-3.0/gtk.css",
    "gtk/MacTahoeLiquidKde-Dark/gtk-3.0/gtk-dark.css",
    "gtk/MacTahoeLiquidKde-Light/gtk-3.0/gtk-dark.css",
)


def _css_background_colors(text: str) -> dict[str, list[str]]:
    """Map selector line -> its ``background-color`` declarations."""
    out: dict[str, list[str]] = {}
    selector = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.endswith("{"):
            selector = stripped[:-1].strip()
        elif stripped == "}":
            selector = None
        elif selector and stripped.startswith("background-color:"):
            out.setdefault(selector, []).append(stripped)
    return out


@pytest.mark.parametrize("sheet", _DARK_GTK3_SHEETS)
def test_dark_gtk3_popup_surfaces_keep_alpha(offline, sheet):
    decls = _css_background_colors((offline / sheet).read_text())
    for sel in _GTK3_POPUP_SELECTORS:
        assert sel in decls, (
            f"{sheet}: selector ``{sel}`` lost its background-color "
            f"declaration — popup surfaces need a real fill."
        )
        for d in decls[sel]:
            assert not re.search(r"\btransparent\b", d), (
                f"{sheet}: ``{sel}`` has ``{d}`` — popup surfaces must "
                f"mirror the light variant's rgba alpha, never "
                f"``transparent``."
            )


def test_dark_gtk3_sheet_copies_stay_identical(offline):
    dark = (offline / _DARK_GTK3_SHEETS[1]).read_bytes()
    light_copy = (offline / _DARK_GTK3_SHEETS[2]).read_bytes()
    assert dark == light_copy, (
        "MacTahoeLiquidKde-Light/gtk-3.0/gtk-dark.css must stay a "
        "byte-identical copy of MacTahoeLiquidKde-Dark/gtk-3.0/"
        "gtk-dark.css — fix one, copy over the other."
    )


def test_kvantum_dark_popup_parity(offline):
    kv = offline / "kvantum/mac-tahoe-liquid-kde"
    dark_defaults = (
        offline / "look-and-feel/MacTahoeLiquidKde-Dark/contents/defaults"
    ).read_text()
    assert "widgetStyle=kvantum\n" in dark_defaults
    assert "widgetStyle=kvantum-dark" not in dark_defaults, (
        "widgetStyle is the Qt plugin name; the light/dark Kvantum profile is "
        "selected separately by mac-tahoe-theme-switch."
    )
    conf = (kv / "mac-tahoe-liquid-kdeDark.kvconfig").read_text()
    assert "blur_only_active_window=false" in conf, (
        "Dark kvconfig must keep blur_only_active_window=false like the "
        "light variant — true leaves unfocused popups unblurred AND "
        "translucent."
    )
    menubar = conf.split("[MenuBar]", 1)[1].split("[", 1)[0]
    for key in ("frame.element=menubar", "interior.element=menubar"):
        assert key in menubar, (
            f"Dark kvconfig [MenuBar] must carry {key} like the light "
            f"variant — element=none renders no menubar surface at all."
        )
    for svg in ("mac-tahoe-liquid-kde.svg", "mac-tahoe-liquid-kdeDark.svg"):
        text = (kv / svg).read_text()
        elems = [e for e in re.findall(r"<[a-z]+[^>]*>", text)
                 if 'id="tooltip-normal"' in e]
        assert elems, f"{svg}: tooltip-normal element missing"
        for e in elems:
            assert re.search(r'style="[^"]*\bopacity:1\b', e), (
                f"{svg}: tooltip-normal must be fully opaque "
                f"(opacity:1) — tooltips get no reliable blur."
            )


def test_kvantum_mode_profiles_have_matching_surface_colors(offline):
    """Kvantum's SVG assets have literal menu fills, so respect_DE alone
    cannot make the light profile render dark. Keep the mode/profile mapping
    tied to their actual surface colors."""
    import theme_switch

    kv = offline / "kvantum/mac-tahoe-liquid-kde"
    expected = {
        "light": ("mac-tahoe-liquid-kde", "#f5f5f58C"),
        "dark": ("mac-tahoe-liquid-kdeDark", "#2424248C"),
    }
    for mode, (profile, surface) in expected.items():
        assert theme_switch._kvantum_theme(mode) == profile
        config = (kv / f"{profile}.kvconfig").read_text()
        assert f"window.color={surface}" in config


def test_gtk4_named_colors_all_defined(offline):
    sheets = sorted((offline / "gtk").glob("MacTahoeLiquidKde-*/gtk-4.0/*.css"))
    assert sheets, "no gtk-4.0 sheets found"
    skip = {"define", "import", "keyframes", "media", "charset"}
    for f in sheets:
        css = f.read_text()
        defined = set(re.findall(r"@define-color ([a-z_0-9]+)", css))
        refs = set(re.findall(r"@([a-z_][a-z_0-9]*)", css)) - skip
        missing = sorted(refs - defined)
        assert not missing, (
            f"{f.name}: named colors referenced but never defined: "
            f"{missing}. Only libadwaita apps define these at runtime; "
            f"plain GTK4 apps get invalid declarations and popovers "
            f"fall back to transparent."
        )
