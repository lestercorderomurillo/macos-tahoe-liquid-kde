"""Static guards that protect cross-cutting invariants.

This file used to contain ~128 tests: SVG decode, SVG parity,
file-existence walks under ``src/offline/``, README documentation
markers, "summary is the last print" cosmetics, etc. Most of that
was pinning artist choices or duplicating the install step's own
fail-fast checks. Removed in the v0.17.4 test-suite nuke.

What survives here: guards that catch *cross-cutting* drift
(refactors that affect every distro / every step / every release).
Each one protects against a specific shipped bug or a specific
class of regression that has no other home in the suite.
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
    and printed by the install banner. v0.17.2 shipped with this file
    out of sync with the git tag — the banner printed v0.17.1 on a
    v0.17.2 install. Pin the shape so a future malformed VERSION
    (e.g. "0.17.2\n0.17.3\n" from a botched merge) fails CI."""
    assert re.fullmatch(r"\d+\.\d+\.\d+", (repo / "VERSION").read_text().strip())


def test_install_entry_exists(repo):
    p = repo / "install"
    assert p.is_file() and p.stat().st_mode & 0o111


def test_uninstall_entry_exists(repo):
    p = repo / "uninstall"
    assert p.is_file() and p.stat().st_mode & 0o111


@pytest.mark.parametrize("script", ["install", "uninstall"])
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

    Real regression this caught: a step at one point shelled out to
    ``pacman -S foo`` directly. That worked on Arch and silently
    no-op'd on every other distro — exactly the bug shape the
    distro-layer abstraction was introduced to prevent.

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

    Real regression this caught: v0.14.x assumed Arch's ``/usr/lib/qt6``
    everywhere and broke installs on Gentoo + Debian (different libdirs).

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


# ── single-source-of-truth pins on the theme-switcher rewrite ─────────


def test_theme_switch_no_legacy_entry_points(repo):
    """The v0.14.2 rewrite collapsed several historical entry points
    (watch_loop, sync_auto_mode_on_startup, _spawn_deferred_live_apply,
    _deferred_live_apply_loop) into a single ``apply()``. If any of
    those names reappear, a maintainer is re-introducing the multi-
    entry-point design that produced the v0.13.x cascade. The
    apply()-as-only-path invariant is load-bearing."""
    text = (repo / "src/scripts/theme_switch.py").read_text()
    for forbidden in ("watch_loop", "sync_auto_mode_on_startup",
                      "_spawn_deferred_live_apply",
                      "_deferred_live_apply_loop"):
        assert forbidden not in text, (
            f"{forbidden!r} is a deprecated entry point — the v0.14.2 "
            f"rewrite collapsed everything into apply(). Re-introducing "
            f"it brings back the v0.13.x bug cascade."
        )


def test_theme_switch_has_no_global_sync(repo):
    """Issues #36/#37: _kwrite() used to os.sync() after every
    kwriteconfig6 call — a machine-wide dirty-page flush repeated 130+
    times per apply, slow enough to blow the installer's child timeout."""
    text = (repo / "src/scripts/theme_switch.py").read_text()
    assert "os.sync(" not in text, (
        "os.sync() is back in theme_switch.py — per-write global flushes "
        "are the issue #36/#37 regression"
    )


def test_no_legacy_apply_service_in_offline(offline):
    """The split apply.service / watch.service design from earlier
    versions is gone — only the single oneshot service file ships now.
    Leftover units would re-enable the dead watch path on upgrade
    (systemctl daemon-reload picks them up)."""
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

    To stop the badge from drifting (the previous 691_passing badge
    was already stale by hundreds of tests), pin the number here.
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


# ── issue #11: dark popup surfaces keep mirrored light/dark alpha ─────
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
            f"declaration — popup surfaces need a real fill (issue #11)."
        )
        for d in decls[sel]:
            assert not re.search(r"\btransparent\b", d), (
                f"{sheet}: ``{sel}`` has ``{d}`` — popup surfaces must "
                f"mirror the light variant's rgba alpha, never "
                f"``transparent`` (issue #11)."
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
    conf = (kv / "mac-tahoe-liquid-kdeDark.kvconfig").read_text()
    assert "blur_only_active_window=false" in conf, (
        "Dark kvconfig must keep blur_only_active_window=false like the "
        "light variant — true leaves unfocused popups unblurred AND "
        "translucent (issue #11)."
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
                f"(opacity:1) — tooltips get no reliable blur (issue #11)."
            )


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
            f"fall back to transparent (issue #11)."
        )
