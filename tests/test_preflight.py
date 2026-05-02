"""Preflight invariants — the four checks that gate every install run.

Each check is exercised against the real repo state (no mocks for the
plasmoid tree or the Qt6 path discovery), so a refactor that drifts
the layout JS, the metadata IDs, or the install destinations gets
caught here before it ships."""

import json
from pathlib import Path

import pytest

import preflight
from paths import OFFLINE_DIR


# ── 1. destination-path regex ────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "/usr/lib/qt6/plugins/plasma/applets/foo.so",
    "/usr/lib/qt6/qml/plasma/applet/org/kde/foo",
    "/etc/sddm.conf.d/mac-tahoe.conf",
    "/usr/share/sounds/MacTahoe",
    "/usr/share/wallpapers/MacTahoe",
])
def test_validate_path_accepts_allowed_roots(path):
    assert preflight._validate_path(path) is None


@pytest.mark.parametrize("path,reason", [
    ("/root/anything", "leaks /root home"),
    ("/tmp/payload", "tmp path used as install dest"),
    ("/usr/lib//qt6/plugins/foo", "double slash"),
    ("/usr/lib/qt6/plugins/../etc/passwd", "parent traversal"),
    ("/etc/passwd", "outside allowed roots"),
    ("/var/log/anything", "outside allowed roots"),
])
def test_validate_path_rejects_dangerous_paths(path, reason):
    got = preflight._validate_path(path)
    assert got is not None
    assert reason in got


def test_validate_path_accepts_user_home():
    home = preflight._home()
    assert preflight._validate_path(str(home / ".local/share/icons")) is None
    assert preflight._validate_path(str(home / ".config/kdeglobals")) is None
    assert preflight._validate_path(str(home / ".cache/foo")) is None


def test_enumerate_destinations_covers_all_compiled_steps():
    """Every step that ships a compiled artefact must have its install
    destination listed in ``_enumerate_destinations`` — otherwise a new
    ``.so`` could ship to an unvalidated path and the regex check would
    silently miss it."""
    labels = {label for label, _ in preflight._enumerate_destinations()}
    # Compiled C++ destinations.
    assert "globalmenu .so" in labels
    assert "globalmenu QML module" in labels
    assert "taskmanager .so" in labels
    assert "taskmanager QML module" in labels
    assert "acrylic-glass plugin dir" in labels


def test_check_paths_passes_for_production_destinations():
    """The production destinations must all sit in allowed roots —
    this is what the install-time check asserts. If a refactor adds a
    ``.so`` destination outside ``$HOME`` / ``/usr/lib/qt6`` /
    ``/etc/sddm.conf.d`` / ``/usr/share``, this test catches it."""
    for label, path in preflight._enumerate_destinations():
        reason = preflight._validate_path(path)
        assert reason is None, f"{label}: {path} → {reason}"


# ── 2. plasmoid ID consistency ───────────────────────────────────────────

def test_plasmoid_id_consistency_across_repo():
    """For every plasmoid in ``src/offline/plasmoids/``: directory name
    must equal ``metadata.json`` ``KPlugin.Id``. Was an actual bug in
    v0.9.0 — globalmenu's source dir was kebab-case while the .so /
    QML / layout JS / cmake target all used dotted form. v0.10 renamed
    the dir; this test pins it so the drift can't come back."""
    plasmoids = OFFLINE_DIR / "plasmoids"
    assert plasmoids.is_dir(), plasmoids

    seen = 0
    for plasmoid_dir in sorted(plasmoids.iterdir()):
        if not plasmoid_dir.is_dir():
            continue
        metadata = plasmoid_dir / "metadata.json"
        if not metadata.is_file():
            continue
        seen += 1
        plugin_id = json.loads(metadata.read_text())["KPlugin"]["Id"]
        assert plasmoid_dir.name == plugin_id, (
            f"directory ``{plasmoid_dir.name}`` does not match metadata "
            f"KPlugin.Id ``{plugin_id}`` — Qt QML module URI requires "
            f"the path-form to match the dotted Id, and Plasma resolves "
            f"the package by directory name. Mismatch = applet doesn't load."
        )
    assert seen >= 4, f"expected at least 4 plasmoids, saw {seen}"


def test_layout_js_references_real_plasmoid_ids():
    """Every ``addWidget("...")`` call in the layout JS for a custom
    plasmoid must resolve to a metadata Id that exists on disk —
    otherwise the layout script silently leaves a hole in the panel
    when plasmashell can't find the package."""
    layout_js = (OFFLINE_DIR / "layouts/mac-tahoe.js").read_text()
    plasmoids_dir = OFFLINE_DIR / "plasmoids"
    real_ids = {
        json.loads((p / "metadata.json").read_text())["KPlugin"]["Id"]
        for p in plasmoids_dir.iterdir()
        if (p / "metadata.json").is_file()
    }
    # Custom MacTahoe plasmoid IDs in the layout JS.
    import re
    addwidget_calls = re.findall(
        r'addWidget\("(org\.kde\.mac[^"]+)"\)', layout_js,
    )
    for plugin_id in addwidget_calls:
        assert plugin_id in real_ids, (
            f"layout JS references ``{plugin_id}`` but no plasmoid "
            f"with that metadata.Id exists in src/offline/plasmoids/"
        )


# ── 3. Qt6 plugin-path query ─────────────────────────────────────────────

def test_qmake6_query_returns_none_when_qmake6_missing(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda _: None)
    assert preflight._qmake6_query("QT_INSTALL_PLUGINS") is None


def test_qmake6_query_handles_subprocess_failure(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(preflight.shutil, "which", lambda _: "/usr/bin/qmake6")
    monkeypatch.setattr(
        preflight, "run_user",
        lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="oops"),
    )
    assert preflight._qmake6_query("QT_INSTALL_PLUGINS") is None
