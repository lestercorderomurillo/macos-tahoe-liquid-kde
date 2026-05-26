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
    "/etc/sddm.conf.d/mac-tahoe.conf",
    "/usr/share/sounds/MacTahoe",
    "/usr/share/wallpapers/MacTahoe",
])
def test_validate_path_accepts_allowed_roots(path):
    assert preflight._validate_path(path) is None


def test_validate_path_accepts_qmake6_reported_qt6_roots():
    """Qt6 plugin / QML roots come from distro.qt6_*_dir() at validate
    time, so the allowed-roots list adapts to whatever libdir
    convention this distro uses. On Arch that's /usr/lib/qt6, on
    Fedora /usr/lib64/qt6, on Debian /usr/lib/x86_64-linux-gnu/qt6 —
    all should validate cleanly."""
    from distro import qt6_plugins_dir, qt6_qml_dir, Qt6PathsMissing
    try:
        plugins = str(qt6_plugins_dir())
        qml = str(qt6_qml_dir())
    except Qt6PathsMissing:
        pytest.skip("qmake6 not on PATH in this test environment")
    for path in (
        f"{plugins}/plasma/applets/foo.so",
        f"{qml}/plasma/applet/org/kde/foo",
    ):
        assert preflight._validate_path(path) is None, path


@pytest.mark.parametrize("path,reason", [
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


def test_validate_path_rejects_root_when_home_is_user(monkeypatch, tmp_path):
    """/root paths leak the privilege-escalated user's home — ONLY a
    problem when the real user's home is somewhere else (the typical
    sudo-drop scenario). Pinning a user home explicitly so this stays
    deterministic regardless of who runs the test."""
    fake_home = tmp_path / "home/lester"
    fake_home.mkdir(parents=True)
    monkeypatch.setattr(preflight, "_HOME", fake_home)
    got = preflight._validate_path("/root/.local/share/icons")
    assert got is not None
    assert "leaks /root home" in got


def test_validate_path_accepts_root_when_home_is_root(monkeypatch, tmp_path):
    """Container / embedded scenario: the only user IS root, /root IS
    the legitimate home. /root paths must NOT be rejected then,
    otherwise the installer can't run on those targets."""
    monkeypatch.setattr(preflight, "_HOME", Path("/root"))
    assert preflight._validate_path("/root/.local/share/icons") is None
    assert preflight._validate_path("/root/.config/kdeglobals") is None


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


# ── 3. Qt6 path discovery (lives in distro.py now) ──────────────────────

def test_qt6_query_returns_none_when_no_tools_present(monkeypatch):
    """When neither qmake6, qtpaths6, nor pkg-config is on PATH the
    private query chain returns None. The public ``qt6_plugins_dir()``
    then falls back to the per-distro libdir table (verified against
    on-disk reality) — see the two tests below for both paths."""
    import distro
    monkeypatch.setattr(distro.shutil, "which", lambda _: None)
    assert distro._qt6_plugins_query() is None
    assert distro._qt6_qml_query() is None


def test_qt6_falls_back_to_known_libdir_when_qmake6_missing(monkeypatch):
    """v0.15.1: if qmake6 / qtpaths6 / pkg-config are all absent but
    /etc/os-release identifies a distro whose Qt6 libdir we know AND
    that libdir actually exists on disk, return it. Plasma 6 must
    already be installed for the dir to exist, so we're not guessing
    — just reading what's already there."""
    import distro
    monkeypatch.setattr(distro.shutil, "which", lambda _: None)
    monkeypatch.setattr(distro, "_QT_PLUGINS_CACHE", None)
    monkeypatch.setattr(distro, "_QT_QML_CACHE", None)
    monkeypatch.setattr(distro, "current_distro", lambda: "arch")
    monkeypatch.setattr(distro, "distro_id_like", lambda: ())
    monkeypatch.setattr(distro, "_fallback_qt6_libdir",
                        lambda: distro.Path("/usr/lib/qt6")
                                if distro.Path("/usr/lib/qt6").is_dir() else None)
    # Skip the assertion on a host where /usr/lib/qt6 doesn't exist;
    # those hosts will hit Qt6PathsMissing instead (covered below).
    if not distro.Path("/usr/lib/qt6").is_dir():
        pytest.skip("/usr/lib/qt6 not present on this host")
    assert str(distro.qt6_plugins_dir()) == "/usr/lib/qt6/plugins"
    assert str(distro.qt6_qml_dir()) == "/usr/lib/qt6/qml"


def test_qt6_raises_when_no_tools_and_no_fallback_dir(monkeypatch, tmp_path):
    """If qmake6 is missing AND the per-distro libdir doesn't exist on
    disk (e.g. an unrecognised distro, or Plasma 6 isn't installed
    yet), refuse to guess. Better to fail loudly than write .so files
    to a directory Qt6 doesn't scan."""
    import distro
    monkeypatch.setattr(distro.shutil, "which", lambda _: None)
    monkeypatch.setattr(distro, "_QT_PLUGINS_CACHE", None)
    monkeypatch.setattr(distro, "_QT_QML_CACHE", None)
    monkeypatch.setattr(distro, "_fallback_qt6_libdir", lambda: None)
    with pytest.raises(distro.Qt6PathsMissing):
        distro.qt6_plugins_dir()
    with pytest.raises(distro.Qt6PathsMissing):
        distro.qt6_qml_dir()


def test_install_destinations_anchor_to_qmake6_libdir(monkeypatch, tmp_path):
    """The v0.14.x Gentoo regression was: qmake6 reports
    ``/usr/lib64/qt6/plugins`` but the installer hardcoded
    ``/usr/lib/qt6/plugins`` for its writes. After v0.15.0 every Qt
    destination is rooted at the qmake6-reported dir; this test
    pretends the libdir lives under a tmp path and asserts each step's
    destination still resolves inside it.

    If a future refactor silently re-introduces a ``/usr/lib`` literal,
    relative_to() raises ValueError and the test pins it."""
    import distro
    fake_plugins = tmp_path / "fake-lib64/qt6/plugins"
    fake_qml = tmp_path / "fake-lib64/qt6/qml"
    monkeypatch.setattr(distro, "_QT_PLUGINS_CACHE", fake_plugins)
    monkeypatch.setattr(distro, "_QT_QML_CACHE", fake_qml)

    from steps import acrylic_glass, globalmenu, plasmoids
    for label, dest, expected_root in (
        ("globalmenu .so",       globalmenu.DEST_SO,             fake_plugins),
        ("globalmenu QML",       globalmenu.DEST_QML_DIR,        fake_qml),
        ("taskmanager .so",      plasmoids.TASKMANAGER_DEST_SO,  fake_plugins),
        ("taskmanager QML",      plasmoids.TASKMANAGER_DEST_QML, fake_qml),
        ("acrylic-glass plugin", acrylic_glass._plugin_dir(),    fake_plugins),
    ):
        # relative_to() raises ValueError if dest is not under root —
        # that IS the failure mode the v0.14.x Gentoo bug hit.
        dest.relative_to(expected_root)


def test_qt6_query_skips_tools_that_exit_nonzero(monkeypatch):
    """A qmake6 that exits non-zero (broken Qt install, sandboxed env)
    must not be treated as a successful path discovery — fall through
    to the next tool in the chain. With every tool failing AND the
    libdir fallback stubbed out, qt6_plugins_dir() raises."""
    from types import SimpleNamespace
    import distro
    monkeypatch.setattr(distro.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(
        distro.subprocess, "run",
        lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="oops"),
    )
    monkeypatch.setattr(distro, "_QT_PLUGINS_CACHE", None)
    monkeypatch.setattr(distro, "_fallback_qt6_libdir", lambda: None)
    assert distro._qt6_plugins_query() is None
    with pytest.raises(distro.Qt6PathsMissing):
        distro.qt6_plugins_dir()
